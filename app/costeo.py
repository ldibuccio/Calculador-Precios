"""'Pegamento' entre las compras cargadas y el motor de costeo (core/motor_costeo.py).

Lee de la base (vía app/db.py). Nada de esto está conectado a ninguna ruta ni
pantalla real todavía — son piezas sueltas que se van armando paso a paso.

La cuenta única de costeo (plata_total/cantidad_total, sin reglas
especiales por artículo) vive en un solo lugar: _costear_compras. El costo
de envase (mango/cherry descartable vs. cartón) queda afuera a propósito en
todo este archivo — se resuelve más adelante en Ventas.
"""

from datetime import date, datetime, timedelta, timezone

from app.db import (
    listar_compras_para_costeo,
    listar_costos_envases_vigentes,
    listar_fichas_por_cliente,
    listar_precios_vigentes_por_cliente,
    obtener_cliente,
)
from core.motor_costeo import SIN_ENVASE, precio_sugerido as calcular_precio_sugerido

ARGENTINA = timezone(timedelta(hours=-3))
VENTANA_COSTEO_HORAS = 48
LIMITE_APARICION_DIAS = 15
LIMITE_COSTO_ANTERIOR_DIAS = 20
RANGO_HISTORIAL_DIAS = 40


def _costear_compras(compras: list[dict]) -> tuple[float | None, float, int]:
    """La cuenta única de costeo, sobre una lista de compras ya filtrada a UN artículo y UNA ventana.

    plata_total = suma de (importe * cantidad_cajones) de cada compra
    cantidad_total = suma de (cantidad_cajones * contenido_por_cajon) de cada compra
    costo_por_unidad_de_venta = plata_total / cantidad_total

    Las compras sin importe (compra sin precio todavía) se excluyen de la
    suma pero se cuentan. Sin ninguna compra con precio, no hay costo: se
    devuelve None (no None sale es "artículo caro", sale es "no hay dato").

    Devuelve (costo_por_unidad_de_venta o None, cantidad_total, compras_sin_precio_excluidas).
    """
    plata_total = 0.0
    cantidad_total = 0.0
    sin_precio = 0

    for compra in compras:
        if compra["importe"] is None:
            sin_precio += 1
            continue

        # float(...): psycopg2 devuelve las columnas numeric como Decimal, no
        # float — sin este cast, sumar Decimal con el acumulador (float)
        # rompe con "unsupported operand type(s) for +: 'float' and
        # 'decimal.Decimal'".
        cajones = float(compra["cantidad_cajones"])
        contenido = float(compra["contenido_por_cajon"])
        importe = float(compra["importe"])

        plata_total += importe * cajones
        cantidad_total += cajones * contenido

    if cantidad_total == 0:
        return None, 0.0, sin_precio

    return plata_total / cantidad_total, cantidad_total, sin_precio


def _envases_por_unidad_ponderado(compras: list[dict], contenido_ficha: float | None, envase_variable: bool) -> float:
    """Cuántos envases hacen falta por unidad de venta, ponderado por la cantidad real de cada compra.

    Mismo peso que _costear_compras (cajones * contenido_por_cajon de cada
    compra, solo las que tienen precio) para que el envase quede coherente
    con el costo_actual que ya se calculó sobre esas mismas compras.

    Envase FIJO: siempre 1 envase por cada "contenido_ficha" unidades (ej.
    ficha = 16 kg por Caja Grande => 1/16 cajas por kilo). Constante para
    todas las compras del artículo.

    Envase VARIABLE (mango/cherry): por cada compra se decide solo, sin
    preguntar nada nuevo: si el contenido de ESE cajón (lo que trajo esa
    compra puntual) es menor o igual al contenido de la ficha, es
    descartable (0 cajas); si es mayor, es caja chica, a razón de 1 caja
    cada "contenido_ficha" unidades — el número de corte y el "cada
    cuánto" salen siempre de la ficha, nunca hardcodeados.
    """
    if not contenido_ficha:
        return 0.0

    # float(...): psycopg2 devuelve contenido_caja (numeric) como Decimal,
    # no float — sin este cast, dividir 1.0 / contenido_ficha rompe con
    # "unsupported operand type(s) for /: 'float' and 'decimal.Decimal'".
    contenido_ficha = float(contenido_ficha)

    total_ponderado = 0.0
    cantidad_total = 0.0

    for compra in compras:
        if compra["importe"] is None:
            continue

        cajones = float(compra["cantidad_cajones"])
        contenido_compra = float(compra["contenido_por_cajon"])
        cantidad_real = cajones * contenido_compra

        if envase_variable and contenido_compra <= contenido_ficha:
            envases_por_unidad = 0.0
        else:
            envases_por_unidad = 1.0 / contenido_ficha

        total_ponderado += envases_por_unidad * cantidad_real
        cantidad_total += cantidad_real

    if cantidad_total == 0:
        return 0.0

    return total_ponderado / cantidad_total


def calcular_costo_por_unidad_venta_reciente(cliente_id: int, momento_referencia: datetime | None = None) -> dict:
    """Costo por unidad de venta del cliente (kilo/unidad/cubeta) de cada artículo, últimas 48 hs.

    momento_referencia es el "ahora" desde el que se cuentan las 48 hs hacia
    atrás (por defecto, el momento real de la llamada, en hora argentina).

    OJO con la precisión: fecha_operacion en la base es una fecha sin hora
    (el día en que se cargó la compra), no un instante exacto. Por eso la
    ventana se resuelve por día calendario: se incluyen todas las compras
    cuya fecha_operacion cae entre el día de (momento_referencia - 48 hs) y
    el día de momento_referencia, ambos inclusive. En la práctica esto puede
    incluir un poco más de 48 hs exactas — nunca menos.

    La cuenta de costeo (ver _costear_compras) es una sola para todos los
    artículos, sin reglas especiales (ni cherry, ni mango, ni ningún otro).

    La unidad de venta para el cliente sale de fichas_logistica
    (articulo_id + cliente_id). Un artículo con compras pero SIN ficha para
    este cliente no se costea — se reporta aparte en "articulos_sin_ficha",
    nunca se salta en silencio.

    Devuelve un dict con:
      - "articulos": lista ordenada por nombre, con articulo_id,
        articulo_nombre, unidad_venta, cantidad_total,
        costo_por_unidad_de_venta, compras_sin_precio_excluidas.
      - "articulos_sin_ficha": lista ordenada por nombre (articulo_id,
        articulo_nombre) de los artículos con compras con precio en la
        ventana pero sin ficha de logística para este cliente.
    """
    if momento_referencia is None:
        momento_referencia = datetime.now(ARGENTINA)

    fecha_hasta = momento_referencia.date()
    fecha_desde = (momento_referencia - timedelta(hours=VENTANA_COSTEO_HORAS)).date()

    compras = listar_compras_para_costeo(fecha_desde, fecha_hasta)
    fichas = listar_fichas_por_cliente(cliente_id)
    unidad_venta_por_articulo = {ficha["articulo_id"]: ficha["unidad_venta"] for ficha in fichas}

    compras_por_articulo: dict[int, list[dict]] = {}
    nombres_por_articulo: dict[int, str] = {}
    for compra in compras:
        articulo_id = compra["articulo_id"]
        nombres_por_articulo[articulo_id] = compra["articulo_nombre"]
        compras_por_articulo.setdefault(articulo_id, []).append(compra)

    articulos = []
    articulos_sin_ficha = []
    for articulo_id, compras_articulo in compras_por_articulo.items():
        nombre = nombres_por_articulo[articulo_id]

        # Sin ninguna compra con precio, el artículo no se reporta en ningún
        # lado (ni costeado ni "sin ficha") — nada que decir todavía.
        costo, cantidad_total, sin_precio = _costear_compras(compras_articulo)
        if costo is None:
            continue

        unidad_venta = unidad_venta_por_articulo.get(articulo_id)
        if unidad_venta is None:
            articulos_sin_ficha.append({"articulo_id": articulo_id, "articulo_nombre": nombre})
            continue

        articulos.append(
            {
                "articulo_id": articulo_id,
                "articulo_nombre": nombre,
                "unidad_venta": unidad_venta,
                "cantidad_total": cantidad_total,
                "costo_por_unidad_de_venta": costo,
                "compras_sin_precio_excluidas": sin_precio,
            }
        )

    articulos.sort(key=lambda fila: fila["articulo_nombre"])
    articulos_sin_ficha.sort(key=lambda fila: fila["articulo_nombre"])

    return {"articulos": articulos, "articulos_sin_ficha": articulos_sin_ficha}


def calcular_listado_para_negociar_precios(cliente_id: int, momento_referencia: datetime | None = None) -> list[dict]:
    """Listado completo de los artículos que el cliente comercializa, para negociar precios.

    A diferencia de calcular_costo_por_unidad_venta_reciente (que arranca
    desde las compras de una ventana fija), esto arranca desde la FICHA del
    cliente: un artículo aparece si el cliente lo comercializa Y tuvo compra
    en los últimos 15 días — no importa si esa compra tiene precio cargado
    todavía. No se guarda ningún "costo anterior" en ninguna tabla: se
    reconstruye en vivo a partir de las fechas de compra ya cargadas.

    Por cada artículo con ficha para este cliente:

    1. F1 = fecha_operacion más reciente de ese artículo (con o sin precio
       cargado — F1 es sobre "hubo actividad", no sobre "hubo precio").
       Sin ninguna compra en los últimos 15 días, el artículo NO aparece
       (se considera sin stock, perecedero, nada que negociar).
    2. costo_actual = _costear_compras de las compras en [F1 - 1 día, F1].
    3. "fresco" = F1 cae dentro de las últimas 48 hs contadas desde AHORA
       (no desde F1) — mismo criterio de ventana que
       calcular_costo_por_unidad_venta_reciente.
    4. Solo para los frescos se busca costo anterior: F2 = fecha_operacion
       más reciente ANTERIOR a (F1 - 1 día). Si F2 no existe, o quedó a más
       de 20 días de F1, se descarta (costo nuevo, sin comparación válida:
       el artículo se dejó de vender y se retomó, no venía "siguiendo el
       mercado"). Si F2 es válido, costo_anterior = _costear_compras de
       [F2 - 1 día, F2], y variacion compara costo_actual vs. costo_anterior
       (redondeado al peso, para no marcar "subió/bajó" por ruido de
       centavos que ni se ve en pantalla).

    El precio vigente sale de precios_venta_historial (ver
    listar_precios_vigentes_por_cliente): se muestra aunque sea viejo, es
    justamente lo que hay que corregir si no coincide con el costo.

    precio_sugerido (ver core/motor_costeo.py precio_sugerido) se calcula
    sobre costo_actual, con descuento/utilidad vigentes del cliente y el
    costo de envase vigente de la ficha. La utilidad se aplica solo a la
    mercadería, nunca al envase; todo se divide por (1 - descuento). Para
    envase fijo, el envase sale directo de la ficha. Para envase variable
    (mango/cherry), cada compra de la ventana decide sola si fue
    descartable o caja chica comparando su propio contenido_por_cajon
    contra el contenido solicitado de la ficha (ver
    _envases_por_unidad_ponderado) — nunca un número hardcodeado. Sin
    costo_actual, no hay precio_sugerido (None).

    Devuelve una lista de dicts (frescos primero, después por nombre) con:
    articulo_id, articulo_nombre, unidad_venta, fresco, costo_actual,
    costo_anterior (o None), variacion ("subio"/"bajo"/"igual"/None),
    fecha_ultima_compra, precio_vigente (o None), precio_sugerido (o None),
    compras_sin_precio_excluidas.
    """
    if momento_referencia is None:
        momento_referencia = datetime.now(ARGENTINA)

    hoy = momento_referencia.date()
    fecha_desde_historial = hoy - timedelta(days=RANGO_HISTORIAL_DIAS)

    compras = listar_compras_para_costeo(fecha_desde_historial, hoy)
    fichas = listar_fichas_por_cliente(cliente_id)
    precios_vigentes = listar_precios_vigentes_por_cliente(cliente_id, hoy)
    precio_vigente_por_articulo = {p["articulo_id"]: p["precio"] for p in precios_vigentes}

    costos_envases = listar_costos_envases_vigentes(hoy)
    costo_por_envase_id = {c["envase_id"]: float(c["costo"]) for c in costos_envases}

    cliente = obtener_cliente(cliente_id)
    # Sin descuento/utilidad vigentes todavía, no hay con qué sugerir precio
    # (no se inventa un valor por defecto: mejor mostrar "sin precio
    # sugerido" que uno mal calculado).
    descuento = float(cliente["descuento"]) / 100 if cliente and cliente["descuento"] is not None else None
    utilidad = float(cliente["utilidad_objetivo"]) / 100 if cliente and cliente["utilidad_objetivo"] is not None else None

    compras_por_articulo: dict[int, list[dict]] = {}
    for compra in compras:
        compras_por_articulo.setdefault(compra["articulo_id"], []).append(compra)

    limite_fresco: date = (momento_referencia - timedelta(hours=VENTANA_COSTEO_HORAS)).date()
    limite_aparicion: date = hoy - timedelta(days=LIMITE_APARICION_DIAS)

    resultado = []
    for ficha in fichas:
        articulo_id = ficha["articulo_id"]
        compras_articulo = compras_por_articulo.get(articulo_id, [])
        if not compras_articulo:
            continue

        f1 = max(compra["fecha_operacion"] for compra in compras_articulo)
        if f1 < limite_aparicion:
            continue

        ventana1_desde = f1 - timedelta(days=1)
        compras_ventana1 = [c for c in compras_articulo if ventana1_desde <= c["fecha_operacion"] <= f1]
        costo_actual, _, sin_precio = _costear_compras(compras_ventana1)

        fresco = f1 >= limite_fresco

        costo_anterior = None
        variacion = None
        if fresco:
            fechas_anteriores = [c["fecha_operacion"] for c in compras_articulo if c["fecha_operacion"] < ventana1_desde]
            if fechas_anteriores:
                f2 = max(fechas_anteriores)
                if (f1 - f2).days <= LIMITE_COSTO_ANTERIOR_DIAS:
                    ventana2_desde = f2 - timedelta(days=1)
                    compras_ventana2 = [c for c in compras_articulo if ventana2_desde <= c["fecha_operacion"] <= f2]
                    costo_anterior, _, _ = _costear_compras(compras_ventana2)

                    if costo_actual is not None and costo_anterior is not None:
                        actual_redondeado = round(costo_actual)
                        anterior_redondeado = round(costo_anterior)
                        if actual_redondeado > anterior_redondeado:
                            variacion = "subio"
                        elif actual_redondeado < anterior_redondeado:
                            variacion = "bajo"
                        else:
                            variacion = "igual"

        precio_sugerido_valor = None
        if costo_actual is not None and descuento is not None and utilidad is not None:
            envases_ponderado = _envases_por_unidad_ponderado(
                compras_ventana1, ficha["contenido_caja"], ficha["envase_variable"]
            )
            costo_envase = costo_por_envase_id.get(ficha["envase_id"], SIN_ENVASE) if ficha["envase_id"] else SIN_ENVASE
            precio_sugerido_valor = calcular_precio_sugerido(
                costo_bulto=costo_actual,
                kg_bulto=1,
                costo_envase=costo_envase,
                cantidad_envases=envases_ponderado,
                descuento=descuento,
                utilidad=utilidad,
            )

        resultado.append(
            {
                "articulo_id": articulo_id,
                "articulo_nombre": ficha["articulo_nombre"],
                "unidad_venta": ficha["unidad_venta"],
                "fresco": fresco,
                "costo_actual": costo_actual,
                "costo_anterior": costo_anterior,
                "variacion": variacion,
                "fecha_ultima_compra": f1,
                "precio_vigente": precio_vigente_por_articulo.get(articulo_id),
                "precio_sugerido": precio_sugerido_valor,
                "compras_sin_precio_excluidas": sin_precio,
            }
        )

    resultado.sort(key=lambda fila: (not fila["fresco"], fila["articulo_nombre"]))
    return resultado
