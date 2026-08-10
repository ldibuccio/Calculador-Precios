"""'Pegamento' entre las compras cargadas y el motor de costeo (core/motor_costeo.py).

Lee de la base (vía app/db.py). Nada de esto está conectado a ninguna ruta ni
pantalla real todavía — son piezas sueltas que se van armando paso a paso.

Paso 2: costo por unidad de venta del cliente (kilo, unidad o cubeta según
fichas_logistica), una única cuenta para todos los artículos, sin casos
especiales por artículo. El costo de envase (mango/cherry descartable vs.
cartón) queda afuera a propósito — se resuelve más adelante en Ventas.
"""

from datetime import datetime, timedelta, timezone

from app.db import listar_compras_para_costeo, listar_fichas_por_cliente

ARGENTINA = timezone(timedelta(hours=-3))
VENTANA_COSTEO_HORAS = 48


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

    Una sola cuenta para todos los artículos, sin reglas especiales (ni
    cherry, ni mango, ni ningún otro). Para cada artículo, juntando todas
    sus compras CON precio de la ventana:

        plata_total = suma de (importe * cantidad_cajones) de cada compra
        cantidad_total = suma de (cantidad_cajones * contenido_por_cajon) de cada compra
        costo_por_unidad_de_venta = plata_total / cantidad_total

    contenido_por_cajon está en la unidad en la que ese artículo se compró
    ese cajón (kilos, unidades o cubetas); cantidad_total queda expresada en
    esa misma unidad, ponderando cada compra por su cantidad real (no por
    cantidad de cajones). Las compras sin importe (compra sin precio
    todavía) se excluyen del cálculo, pero se cuentan por artículo.

    La unidad de venta para el cliente sale de fichas_logistica
    (articulo_id + cliente_id). Un artículo con compras pero SIN ficha para
    este cliente no se costea — se reporta aparte en "articulos_sin_ficha",
    nunca se salta en silencio. El envase (descartable vs. cartón, para
    mango/cherry) no entra acá: es un tema de Ventas, no de este cálculo.

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

    plata_por_articulo: dict[int, float] = {}
    cantidad_por_articulo: dict[int, float] = {}
    nombres_por_articulo: dict[int, str] = {}
    sin_precio_por_articulo: dict[int, int] = {}

    for compra in compras:
        articulo_id = compra["articulo_id"]
        nombres_por_articulo[articulo_id] = compra["articulo_nombre"]

        if compra["importe"] is None:
            sin_precio_por_articulo[articulo_id] = sin_precio_por_articulo.get(articulo_id, 0) + 1
            continue

        cajones = compra["cantidad_cajones"]
        contenido = compra["contenido_por_cajon"]

        plata_por_articulo[articulo_id] = plata_por_articulo.get(articulo_id, 0.0) + compra["importe"] * cajones
        cantidad_por_articulo[articulo_id] = cantidad_por_articulo.get(articulo_id, 0.0) + cajones * contenido

    articulos = []
    articulos_sin_ficha = []
    for articulo_id, plata_total in plata_por_articulo.items():
        nombre = nombres_por_articulo[articulo_id]
        unidad_venta = unidad_venta_por_articulo.get(articulo_id)

        if unidad_venta is None:
            articulos_sin_ficha.append({"articulo_id": articulo_id, "articulo_nombre": nombre})
            continue

        cantidad_total = cantidad_por_articulo[articulo_id]
        articulos.append(
            {
                "articulo_id": articulo_id,
                "articulo_nombre": nombre,
                "unidad_venta": unidad_venta,
                "cantidad_total": cantidad_total,
                "costo_por_unidad_de_venta": plata_total / cantidad_total,
                "compras_sin_precio_excluidas": sin_precio_por_articulo.get(articulo_id, 0),
            }
        )

    articulos.sort(key=lambda fila: fila["articulo_nombre"])
    articulos_sin_ficha.sort(key=lambda fila: fila["articulo_nombre"])

    return {"articulos": articulos, "articulos_sin_ficha": articulos_sin_ficha}
