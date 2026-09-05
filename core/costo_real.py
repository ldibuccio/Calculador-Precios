"""Rentabilidad REAL: qué dejó de verdad lo que salió del depósito — puro, sin tocar la base.

La contracara de core/rentabilidad.py (la TEÓRICA, que queda intacta
como red del dueño: bultos = lo pedido, costo de compra anclado). Esta
es la cuenta exacta, mirando lo que pasó:

    + venta real   = kilos/unidades ENVIADOS (lo que se factura) ×
                     precio de lista vigente a la fecha del pedido ×
                     (1 + Σ tasas del cliente) — MISMO listado anclado
                     que Márgenes y la teórica.
    − mercadería   = costo FIFO de los bultos que salieron por armado:
                     lotes de compra a su importe, lotes de guía R a su
                     costo de primera congelado.
    − envase       = costo de envase × unidades realmente enviadas.
    − mermas       = bultos tirados en el período × el costo FIFO de su
                     lote, partido en DOS: mercadería cruda (lotes de
                     compra y ajustes) y mercadería ya trabajada (guías R
                     y reingresos por rechazo, que ya salieron armados y
                     volvieron). No es un total nuevo — es el mismo,
                     abierto para poder ver si se está tirando materia
                     prima o trabajo, que cuesta mucho más caro. El corte
                     va por PORCIÓN consumida: una misma merma puede
                     comerse la punta de un cajón y seguir con una guía R.
    − rechazos     = los rechazos que NO volvieron al stock (fueron a
      perdidos      segunda, con o sin cambio de envase): mercadería al
                    costo congelado + envase, todo pérdida directa.
    = renta real   · utilidad % SOLO sobre mercadería (regla fija).

El reproceso es NEUTRO acá: su toma consume lotes al costo y su primera
vuelve a entrar como lote con ese mismo costo (todo a la primera) — la
plata fluye con la mercadería, sin doble conteo. Su merma interna ya
viene absorbida por la primera, y la segunda vale cero (se informa en
bultos, sin plata). Los ajustes negativos consumen lotes en la
atribución (son inventario que se fue) pero NO son pérdida del período:
son correcciones de registro.

Las DEVOLUCIONES vinculadas a pedido ("si le mandé 25 y me devolvió 5,
vendí 20" — regla que aplica SOLO acá, la teórica no se toca): cada
reingreso con vínculo resta su venta (bultos devueltos pasados a kilos
por el propio renglón, al precio del listado anclado a la fecha del
PEDIDO de origen) y acredita la mercadería al costo congelado del
reingreso — el lote devuelto queda en el stock con ese costo y se vuelve
a cargar recién cuando salga de nuevo, sin doble conteo.

El DESTINO del rechazo (elegido al cargarlo) parte esa cuenta en dos. Si
queda en stock, es lo de arriba: solo se perdió la venta del día. Si va
a segunda (tal cual, o pasando las cajas chicas de vuelta a cajón
grande), no vuelve al stock y no queda primera que absorba su costo —
como sí pasa en el reproceso normal, donde el costo viaja a la primera.
Entonces mercadería + envase de esos bultos se descuentan de la
operación normal y se imputan a la línea propia "− rechazos perdidos":
la renta da el mismo número, pero la pérdida queda nombrada en vez de
escondida adentro del costo de mercadería.

Invariante duro, y acá es PROTAGONISTA: lo que no se puede calcular no
suma como cero — va al reporte "afuera del cálculo" con motivo, bultos
y artículos. Los primeros meses va a haber más ahí que en la cuenta
(stock inicial sin costo, guías R incompletas, renglones sin kilaje):
esa lista es la hoja de ruta del dueño, no una nota al pie. Una salida
con UNA porción sin costo queda afuera ENTERA (venta incluida): mejor
un número chico y cierto que uno grande y mentiroso.
"""

from core.rentabilidad import ETIQUETAS_GRUPO, ETIQUETA_SIN_GRUPO, ORDEN_GRUPOS
from core.stock import lote_posterior_a_la_salida, lotes_senalados

ETIQUETAS_MOTIVO_REAL = {
    "sin_kilaje": "Renglón armado sin kilaje cargado",
    "sin_precio": "Sin precio de venta vigente a la fecha del pedido",
    "compra_sin_precio": "Consumió una compra sin precio cargado",
    "ajuste_sin_costo": "Consumió un ajuste (sin costo posible)",
    "stock_inicial_sin_costo": "Consumió stock inicial cargado sin costo",
    "reingreso_sin_costo": "Consumió un reingreso por rechazo sin costo (sin vínculo a pedido)",
    "guia_r_incompleta": "Consumió la primera de una guía R con costo incompleto",
    "compensatorio_del_corte": "Consumió el compensatorio del corte (mercadería que el modelo viejo dejó debiendo, sin costo posible)",
    "sin_lote": "Salida sin lote (salió más de lo que había en el sistema)",
    "devolucion_sin_valor": "Devolución vinculada que no se pudo valuar (renglón sin kilaje o sin precio a la fecha del pedido)",
    "rechazo_sin_costo": "Rechazo mandado a segunda sin costo congelado (no se puede valuar la pérdida)",
}

# Destinos del rechazo que NO vuelven al stock: su costo entero es
# pérdida (no queda primera que lo absorba, a diferencia del reproceso).
DESTINOS_RECHAZO_PERDIDO = ("segunda", "reproceso")

# La merma parte en dos: qué se está tirando, materia prima o trabajo.
# Tirar un cajón crudo cuesta lo que costó comprarlo; tirar un bulto que
# ya pasó por la mesa cuesta eso MÁS el laburo que se le puso, y el costo
# del lote ya lo refleja. Un lote de compra es el cajón como vino, y un
# ajuste (stock inicial, corrección de registro) se cuenta igual: es
# mercadería sin procesar. Una guía R ya pasó por la mesa, y un reingreso
# por rechazo también — salió armado y volvió.
TIPOS_LOTE_TRABAJADO = ("reproceso", "reingreso_rechazo")


def _es_trabajado(tipo_lote) -> bool:
    return tipo_lote in TIPOS_LOTE_TRABAJADO


_MOTIVO_POR_TIPO_LOTE = {
    "guia": "compra_sin_precio",
    "ajuste": "ajuste_sin_costo",
    # El stock inicial nace CON costo (el check de la base lo permite justo
    # para eso). Si igual aparece uno sin costo, es una anomalía propia y
    # se dice: mezclarlo con los ajustes mandaría a mirar donde no es.
    "stock_inicial": "stock_inicial_sin_costo",
    "reingreso_rechazo": "reingreso_sin_costo",
    "reproceso": "guia_r_incompleta",
    # El lote que el compensatorio POSITIVO del corte le crea a un artículo que
    # estaba en negativo. Sin este renglón caía en el default y se leía
    # "consumió un ajuste", que manda a buscar donde no es: no hay ningún
    # ajuste que corregir, y el motivo real —el modelo viejo dejó salidas sin
    # entrada— no se deduce de ahí.
    "cierre_modelo_viejo": "compensatorio_del_corte",
}


def _numero(valor):
    return float(valor) if valor is not None else None


def atribuir_costos_fifo(entradas: list[dict], salidas: list[dict]) -> list[dict]:
    """Atribuye CADA salida a los lotes que consumió, con su costo — la extensión del repartir_fifo total.

    entradas: lotes con "orden", "cantidad", "tipo_lote" y "costo_bulto"
    (None = sin precio). salidas: con "orden" y "cantidad". Se rejuega la
    historia completa: lotes del más viejo al más nuevo, salidas en orden
    cronológico, cada una consume del lote más viejo con resto QUE YA
    EXISTÍA CUANDO ELLA OCURRIÓ.

    Esa última condición es la que impide que el costeo viaje al futuro:
    sin ella, una salida de hoy se costeaba contra una compra de la semana
    que viene apenas se agotaban los lotes viejos, y un faltante quedaba
    tapado con mercadería que todavía no había llegado. Ahora esa porción
    cae a sin_lote y se ve. La comparación es por FECHA, no por momento de
    carga: un lote cargado a la tarde cubre una salida de esa misma mañana.

    Una salida SEÑALADA sale primero de SUS lotes, y por lo tanto se cuesta
    al costo de ESOS lotes — no al del cajón viejo que el FIFO hubiera
    elegido. Lo que sus lotes no cubren cae al FIFO de siempre. Son dos: la
    merma dirigida (un lote, sin cantidad) y la corrección del que arma un
    pedido (varios lotes con su cantidad, en `lotes_elegidos`). El detalle
    está en `lotes_senalados`.

    Las dirigidas se resuelven TODAS ANTES del FIFO, en una pasada aparte,
    y eso NO es una optimización: es la única forma de que esta función y
    `repartir_fifo` emparejen igual. Hasta el 02/09 acá el reclamo dirigido
    se resolvía adentro del turno cronológico de cada salida, así que una
    salida ANTERIOR sin dirigir se llevaba el lote antes de que la dirigida
    llegara a pedirlo — y quedaba el stock diciendo que el lote fue para la
    que lo eligió mientras el costo se lo cobraba a la otra. La misma regla
    escrita dos veces, separándose. Medido en producción: cero mermas
    dirigidas, así que el arreglo no movió un solo número; entró como
    blindaje antes de que el armado de pedido empiece a generar dirigidas
    de a decenas.

    El que elige GANA sobre cualquier otro reclamo, incluso el de una salida
    anterior: la está SEÑALANDO con el dedo, no adivinando. La salida
    anterior que se queda sin lote no desaparece ni se costea dos veces —
    cae a sin_lote, y se ve.

    A cada salida le agrega: "costo" ($ total, o None si alguna porción
    no tiene precio), "bultos_sin_costo", "motivos_sin_costo"
    ({motivo: bultos}) y "consumos_lotes" (qué lote cubrió cada porción,
    con su tipo, origen y cliente del lote si lo tiene — la materia prima
    de la alerta de cruce de primera de reproceso). Lo que excede los
    lotes es porción sin_lote. Devuelve las salidas en orden cronológico.
    """
    lotes = [dict(e, restante=float(e["cantidad"])) for e in sorted(entradas, key=lambda e: e["orden"])]
    resultado = sorted((dict(s) for s in salidas), key=lambda s: s["orden"])
    # La cuenta de cada salida vive afuera del bucle porque ahora se llena en
    # DOS pasadas: primero las dirigidas de todas, después el FIFO.
    cuentas = {
        id(salida): {"pendiente": float(salida["cantidad"]), "costo": 0.0,
                     "sin_costo": 0.0, "motivos": {}, "consumos": []}
        for salida in resultado
    }

    def _consumir(salida, lote, bultos):
        cuenta = cuentas[id(salida)]
        lote["restante"] -= bultos
        cuenta["pendiente"] = round(cuenta["pendiente"] - bultos, 2)
        costo_porcion = bultos * float(lote["costo_bulto"]) if lote["costo_bulto"] is not None else None
        cuenta["consumos"].append(
            {
                "tipo_lote": lote["tipo_lote"],
                "origen_id": lote.get("origen_id"),
                "cliente_lote_id": lote.get("cliente_lote_id"),
                "detalle": lote.get("detalle"),
                "bultos": bultos,
                # El costo de ESTA porción: es lo que permite partir la
                # merma en cruda y trabajada cuando una sola salida
                # consumió lotes de los dos tipos.
                "costo": costo_porcion,
            }
        )
        if lote["costo_bulto"] is not None:
            cuenta["costo"] += bultos * float(lote["costo_bulto"])
        else:
            cuenta["sin_costo"] += bultos
            motivo = _MOTIVO_POR_TIPO_LOTE.get(lote["tipo_lote"], "ajuste_sin_costo")
            cuenta["motivos"][motivo] = cuenta["motivos"].get(motivo, 0.0) + bultos

    # PASADA 1 — las dirigidas, TODAS, antes de cualquier FIFO. Es la misma
    # pasada global que hace repartir_fifo, y tiene que ser global por lo
    # mismo: si se resolviera adentro del turno de cada salida, una salida
    # anterior sin dirigir se llevaría el lote antes de que la dirigida
    # llegue a pedirlo, y las dos funciones emparejarían distinto.
    for salida in resultado:
        for lote, pedidos in lotes_senalados(lotes, salida):
            pendiente = cuentas[id(salida)]["pendiente"]
            if pendiente <= 0:
                break
            if lote["restante"] > 0:
                _consumir(salida, lote, min(lote["restante"], pedidos, pendiente))

    # PASADA 2 — el FIFO de siempre con lo que quedó pendiente. El índice
    # avanza SOLO sobre lotes agotados, que ya no vuelven (incluidos los que
    # vació la pasada de arriba). Un lote posterior a esta salida se saltea
    # pero NO se pasa de largo: una salida más nueva sí va a poder consumirlo.
    indice = 0
    for salida in resultado:
        cuenta = cuentas[id(salida)]
        while cuenta["pendiente"] > 0 and indice < len(lotes):
            lote = lotes[indice]
            if lote["restante"] <= 0:
                indice += 1
                continue
            if lote_posterior_a_la_salida(lote, salida):
                # Los lotes están ordenados: de acá en adelante son todos
                # posteriores. Esta salida no tiene con qué costearse.
                break
            _consumir(salida, lote, min(lote["restante"], cuenta["pendiente"]))
        if cuenta["pendiente"] > 0:
            cuenta["sin_costo"] += cuenta["pendiente"]
            cuenta["motivos"]["sin_lote"] = cuenta["motivos"].get("sin_lote", 0.0) + cuenta["pendiente"]

    for salida in resultado:
        cuenta = cuentas[id(salida)]
        salida["bultos_sin_costo"] = round(cuenta["sin_costo"], 2)
        salida["motivos_sin_costo"] = cuenta["motivos"]
        salida["consumos_lotes"] = cuenta["consumos"]
        salida["costo"] = round(cuenta["costo"], 2) if cuenta["sin_costo"] == 0 else None
    return resultado


def calcular_rentabilidad_real(
    articulos_datos: list[dict],
    margenes_por_fecha: dict,
    cliente_id: int,
    fecha_desde,
    fecha_hasta,
    devoluciones: list[dict] | None = None,
) -> dict:
    """Arma el reporte real a partir de datos ya traídos (puro, testeable sin base).

    articulos_datos: [{articulo_id, nombre, grupo, entradas, salidas}] —
    entradas y salidas de TODA la historia del artículo (la atribución
    FIFO necesita el pasado completo; el rango solo filtra qué salidas se
    reportan). Salidas tipadas: 'armado' (con fecha = la del PEDIDO, que
    ancla el precio; unidades = kilos_enviados; cliente_id; ficha_id, que
    es lo que ancla QUÉ precio — dos fichas del mismo artículo se venden
    a precios distintos), 'merma', 'ajuste' (negativo) y 'reproceso_toma'
    (con bultos_segunda).
    margenes_por_fecha: mismo formato que la teórica, por ficha.

    La fila del reporte es por ARTÍCULO, no por ficha: es donde vive el
    stock, y la merma y la segunda son del artículo — no de una venta
    puntual, así que atribuirlas a una de dos fichas sería arbitrario. Lo
    que sí es por ficha es el PRECIO con que se valúa cada venta: si
    Banana Bolivia y Banana Ecuador salen el mismo día, cada una entra a
    la misma fila de Banana con su propio precio.

    devoluciones: los reingresos VINCULADOS del cliente en el rango, ya
    filtrados — [{bultos, fecha_pedido, kilos_enviados, bultos_armados,
    costo_por_bulto, articulo_id, articulo_nombre, grupo}]. Cada uno
    resta la venta ("mandé 25, devolvió 5: vendí 20") y acredita la
    mercadería al costo congelado; el que no se puede valuar va al
    "afuera" con motivo, jamás suma cero en silencio.
    """
    acumulado: dict = {}
    afuera: dict = {}
    fechas_incluidas = set()

    def _sumar_afuera(motivo, articulo, bultos):
        clave = (motivo, articulo["articulo_id"])
        entrada = afuera.get(clave)
        if entrada is None:
            entrada = {
                "motivo": motivo,
                "motivo_etiqueta": ETIQUETAS_MOTIVO_REAL[motivo],
                "articulo_id": articulo["articulo_id"],
                "articulo_nombre": articulo["nombre"],
                "bultos": 0.0,
            }
            afuera[clave] = entrada
        entrada["bultos"] += bultos

    def _fila(articulo):
        fila = acumulado.get(articulo["articulo_id"])
        if fila is None:
            fila = {
                "articulo_id": articulo["articulo_id"],
                "articulo_nombre": articulo["nombre"],
                "grupo": articulo["grupo"],
                "bultos": 0.0,
                "unidades": 0.0,
                "venta_neta": 0.0,
                "costo_mercaderia": 0.0,
                "costo_envase": 0.0,
                "costo_mermas": 0.0,
                "bultos_mermados": 0.0,
                # La misma merma, partida por lo que se tiró: mercadería
                # cruda o mercadería ya trabajada. Las dos suman el total.
                "costo_mermas_cruda": 0.0,
                "bultos_mermados_cruda": 0.0,
                "costo_mermas_trabajada": 0.0,
                "bultos_mermados_trabajada": 0.0,
                "segunda_bultos": 0.0,
                "devoluciones_bultos": 0.0,
                "devoluciones_venta": 0.0,
                "rechazos_perdidos": 0.0,
                "rechazos_bultos": 0.0,
            }
            acumulado[articulo["articulo_id"]] = fila
        return fila

    for articulo in articulos_datos:
        salidas = atribuir_costos_fifo(articulo["entradas"], articulo["salidas"])
        for salida in salidas:
            if not (fecha_desde <= salida["fecha"] <= fecha_hasta):
                continue

            if salida["tipo"] == "armado":
                if salida.get("cliente_id") != cliente_id:
                    continue  # venta de otro cliente: no es de esta pantalla
                fechas_incluidas.add(salida["fecha"])
                bultos = float(salida["cantidad"])
                unidades = _numero(salida.get("unidades"))
                if unidades is None:
                    _sumar_afuera("sin_kilaje", articulo, bultos)
                    continue
                # El precio lo ancla la FICHA con la que se vendió, no el
                # artículo: es lo que separa Banana Bolivia de Banana Ecuador.
                margen = margenes_por_fecha.get(salida["fecha"], {}).get(salida.get("ficha_id"))
                precio = _numero(margen.get("precio_vigente")) if margen else None
                if precio is None:
                    _sumar_afuera("sin_precio", articulo, bultos)
                    continue
                if salida["bultos_sin_costo"] > 0:
                    # Una porción sin costo deja la salida ENTERA afuera
                    # (venta incluida): número chico y cierto.
                    for motivo, cuantos in salida["motivos_sin_costo"].items():
                        _sumar_afuera(motivo, articulo, cuantos)
                    continue
                denominador = _numero(margen.get("denominador_tasas"))
                if denominador is None:
                    denominador = 1.0
                envase_unidad = _numero(margen.get("costo_envase_unidad_venta")) or 0.0
                fila = _fila(articulo)
                fila["bultos"] += bultos
                fila["unidades"] += unidades
                fila["venta_neta"] += unidades * precio * denominador
                fila["costo_mercaderia"] += salida["costo"]
                fila["costo_envase"] += unidades * envase_unidad

            elif salida["tipo"] == "merma":
                if salida["bultos_sin_costo"] > 0:
                    for motivo, cuantos in salida["motivos_sin_costo"].items():
                        _sumar_afuera(motivo, articulo, cuantos)
                    continue
                fila = _fila(articulo)
                fila["costo_mermas"] += salida["costo"]
                fila["bultos_mermados"] += float(salida["cantidad"])
                # El corte va por PORCIÓN consumida, no por movimiento: una
                # merma que no se cargó dirigida a un lote la reparte el
                # FIFO, y puede comerse la punta de un cajón crudo y seguir
                # con una guía R. Cada porción se imputa a lo que era.
                for consumo in salida["consumos_lotes"]:
                    lado = "trabajada" if _es_trabajado(consumo["tipo_lote"]) else "cruda"
                    fila[f"costo_mermas_{lado}"] += consumo["costo"]
                    fila[f"bultos_mermados_{lado}"] += consumo["bultos"]

            elif salida["tipo"] == "reproceso_toma":
                # Neutro en plata (el costo viaja a la primera); la
                # segunda se informa en bultos, sin plata.
                _fila(articulo)["segunda_bultos"] += _numero(salida.get("bultos_segunda")) or 0.0
            # 'ajuste' negativo: consume lotes en la atribución pero no es
            # pérdida del período — corrección de registro, no operación.

    for devolucion in devoluciones or []:
        articulo = {
            "articulo_id": devolucion["articulo_id"],
            "nombre": devolucion["articulo_nombre"],
            "grupo": devolucion["grupo"],
        }
        bultos = float(devolucion["bultos"])
        kilos = _numero(devolucion.get("kilos_enviados"))
        armados = _numero(devolucion.get("bultos_armados"))
        margen = margenes_por_fecha.get(devolucion["fecha_pedido"], {}).get(devolucion.get("ficha_id"))
        precio = _numero(margen.get("precio_vigente")) if margen else None
        if kilos is None or not armados or precio is None:
            _sumar_afuera("devolucion_sin_valor", articulo, bultos)
            continue
        denominador = _numero(margen.get("denominador_tasas"))
        if denominador is None:
            denominador = 1.0
        # Los kilos del renglón, proporcionales: lo devuelto se valúa con
        # el MISMO kilaje con el que se facturó lo enviado.
        unidades = kilos / armados * bultos
        costo = _numero(devolucion.get("costo_por_bulto"))
        envase_unidad = _numero(margen.get("costo_envase_unidad_venta")) or 0.0
        perdido = devolucion.get("destino_rechazo") in DESTINOS_RECHAZO_PERDIDO

        if perdido and costo is None:
            # Se sabe que se perdió pero no cuánto: número chico y cierto.
            _sumar_afuera("rechazo_sin_costo", articulo, bultos)
            continue

        fila = _fila(articulo)
        fila["devoluciones_bultos"] += bultos
        fila["devoluciones_venta"] += unidades * precio * denominador
        if perdido:
            # No vuelve al stock (va a segunda, con o sin cambio de
            # envase): no queda primera que absorba el costo, así que
            # mercadería + envase de esos bultos son pérdida directa. Se
            # descuentan de la operación normal y se imputan a su línea
            # propia: la renta da igual, pero la pérdida queda NOMBRADA
            # en vez de escondida adentro del costo de mercadería.
            fila["costo_mercaderia"] -= bultos * costo
            fila["costo_envase"] -= unidades * envase_unidad
            fila["rechazos_perdidos"] += bultos * costo + unidades * envase_unidad
            fila["rechazos_bultos"] += bultos
        elif costo is not None:
            # Queda en stock con su costo congelado: se acredita acá y se
            # vuelve a cargar recién cuando salga de nuevo — sin doble
            # conteo. Solo se perdió la venta de ese día.
            fila["costo_mercaderia"] -= bultos * costo

    def _cerrar_cuenta(fila):
        fila["costo_total"] = (
            fila["costo_mercaderia"] + fila["costo_envase"] + fila["costo_mermas"] + fila["rechazos_perdidos"]
        )
        fila["renta_pesos"] = fila["venta_neta"] - fila["devoluciones_venta"] - fila["costo_total"]
        fila["utilidad_pct"] = (
            fila["renta_pesos"] / fila["costo_mercaderia"] * 100 if fila["costo_mercaderia"] > 0 else None
        )

    filas_con_algo = [
        f for f in acumulado.values()
        if f["bultos"] or f["costo_mermas"] or f["bultos_mermados"] or f["segunda_bultos"]
        or f["devoluciones_bultos"] or f["rechazos_bultos"]
    ]
    for fila in filas_con_algo:
        _cerrar_cuenta(fila)

    grupos = []
    for clave_grupo in ORDEN_GRUPOS:
        filas = sorted(
            (f for f in filas_con_algo if f["grupo"] == clave_grupo),
            key=lambda f: f["articulo_nombre"],
        )
        if not filas:
            continue
        subtotal = {
            "bultos": sum(f["bultos"] for f in filas),
            "venta_neta": sum(f["venta_neta"] for f in filas),
            "costo_mercaderia": sum(f["costo_mercaderia"] for f in filas),
            "costo_envase": sum(f["costo_envase"] for f in filas),
            "costo_mermas": sum(f["costo_mermas"] for f in filas),
            "bultos_mermados": sum(f["bultos_mermados"] for f in filas),
            "costo_mermas_cruda": sum(f["costo_mermas_cruda"] for f in filas),
            "bultos_mermados_cruda": sum(f["bultos_mermados_cruda"] for f in filas),
            "costo_mermas_trabajada": sum(f["costo_mermas_trabajada"] for f in filas),
            "bultos_mermados_trabajada": sum(f["bultos_mermados_trabajada"] for f in filas),
            "devoluciones_bultos": sum(f["devoluciones_bultos"] for f in filas),
            "devoluciones_venta": sum(f["devoluciones_venta"] for f in filas),
            "rechazos_perdidos": sum(f["rechazos_perdidos"] for f in filas),
            "rechazos_bultos": sum(f["rechazos_bultos"] for f in filas),
        }
        _cerrar_cuenta(subtotal)
        grupos.append(
            {
                "grupo": clave_grupo,
                "etiqueta": ETIQUETAS_GRUPO.get(clave_grupo, ETIQUETA_SIN_GRUPO),
                "filas": filas,
                "subtotal": subtotal,
            }
        )

    # El "afuera del cálculo" agrupado POR MOTIVO, ordenado por peso: la
    # hoja de ruta del dueño — qué arreglar primero y cuántos bultos mueve.
    por_motivo: dict = {}
    for entrada in afuera.values():
        resumen = por_motivo.get(entrada["motivo"])
        if resumen is None:
            resumen = {
                "motivo": entrada["motivo"],
                "etiqueta": entrada["motivo_etiqueta"],
                "bultos": 0.0,
                "articulos": [],
            }
            por_motivo[entrada["motivo"]] = resumen
        resumen["bultos"] += entrada["bultos"]
        resumen["articulos"].append({"nombre": entrada["articulo_nombre"], "bultos": entrada["bultos"]})
    afuera_por_motivo = sorted(por_motivo.values(), key=lambda r: -r["bultos"])
    for resumen in afuera_por_motivo:
        resumen["articulos"].sort(key=lambda a: -a["bultos"])

    totales = {
        "bultos": sum(g["subtotal"]["bultos"] for g in grupos),
        "venta_neta": sum(g["subtotal"]["venta_neta"] for g in grupos),
        "costo_mercaderia": sum(g["subtotal"]["costo_mercaderia"] for g in grupos),
        "costo_envase": sum(g["subtotal"]["costo_envase"] for g in grupos),
        "costo_mermas": sum(g["subtotal"]["costo_mermas"] for g in grupos),
        "bultos_mermados": sum(g["subtotal"]["bultos_mermados"] for g in grupos),
        "costo_mermas_cruda": sum(g["subtotal"]["costo_mermas_cruda"] for g in grupos),
        "bultos_mermados_cruda": sum(g["subtotal"]["bultos_mermados_cruda"] for g in grupos),
        "costo_mermas_trabajada": sum(g["subtotal"]["costo_mermas_trabajada"] for g in grupos),
        "bultos_mermados_trabajada": sum(g["subtotal"]["bultos_mermados_trabajada"] for g in grupos),
        "devoluciones_bultos": sum(g["subtotal"]["devoluciones_bultos"] for g in grupos),
        "devoluciones_venta": sum(g["subtotal"]["devoluciones_venta"] for g in grupos),
        "rechazos_perdidos": sum(g["subtotal"]["rechazos_perdidos"] for g in grupos),
        "rechazos_bultos": sum(g["subtotal"]["rechazos_bultos"] for g in grupos),
        "segunda_bultos": sum(f["segunda_bultos"] for f in filas_con_algo),
        "afuera_bultos": sum(r["bultos"] for r in afuera_por_motivo),
        "afuera_motivos": len(afuera_por_motivo),
    }
    _cerrar_cuenta(totales)

    return {
        "grupos": grupos,
        "totales": totales,
        "afuera_por_motivo": afuera_por_motivo,
        "fechas_incluidas": sorted(fechas_incluidas),
    }
