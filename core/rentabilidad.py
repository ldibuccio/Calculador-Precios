"""Rentabilidad de Pedidos: qué dejó (estimado) cada artículo pedido — puro, sin tocar la base.

La decisión de fondo, cerrada por el dueño: los bultos son LO PEDIDO, no
lo armado. Se asume que se vendió todo lo del pedido, sin ajustar — el
tilde de armado es una herramienta de trabajo del depósito, no una
medición. Esto es una estimación de rentabilidad, no facturación.

LA MISMA CUENTA QUE MÁRGENES POR ARTÍCULO (control del dueño: si los dos
miran el mismo artículo en la misma fecha, tienen que dar lo mismo). Por
eso esta función no rearma nada: recibe, por cada fecha de pedido, las
filas de calcular_listado_para_negociar_precios (app/costeo.py) ancladas
a esa fecha — precio vigente, costo de mercadería por la última compra,
envase ponderado y denominador de tasas del cliente — y aplica la
fórmula del motor (core/motor_costeo.utilidad_real_multi_concepto):

    venta neta = precio de lista × (1 + Σ tasas que suman − Σ que restan)
    costo total = mercadería + envase
    renta $ = venta neta − costo total
    utilidad % = renta / mercadería   (SOLO sobre la mercadería, nunca
                                       sobre el envase — regla fija)

Invariante duro: lo que no se puede calcular NO suma como cero. Va
aparte, con su motivo y su peso en bultos, y el total dice cuánto quedó
afuera. Cuatro motivos: sin identificar, sin conversión en la ficha,
sin costo (sin compras recientes), sin precio de venta vigente.
"""

ETIQUETAS_GRUPO = {"fruta": "Fruta", "hortaliza": "Hortaliza", "hoja": "Hoja", "pesada": "Pesada"}
ETIQUETA_SIN_GRUPO = "Sin grupo"
# El orden fijo de las secciones del reporte (None = artículos sin grupo, al final).
ORDEN_GRUPOS = ["fruta", "hortaliza", "hoja", "pesada", None]

ETIQUETAS_MOTIVO = {
    "sin_identificar": "Renglón sin identificar (no matchea ninguna ficha)",
    "sin_conversion": "Sin conversión de bultos en la ficha (contenido por caja)",
    "sin_precio": "Sin precio de venta vigente a la fecha del pedido",
    "sin_costo": "Sin compras recientes para costear (misma regla que Márgenes por Artículo)",
}


def _numero(valor):
    return float(valor) if valor is not None else None


def calcular_rentabilidad_de_pedidos(
    renglones: list[dict],
    fichas: list[dict],
    margenes_por_fecha: dict,
    articulo_id: int | None = None,
    grupo: str | None = None,
) -> dict:
    """Arma el reporte de rentabilidad a partir de datos ya traídos (puro, testeable sin base).

    renglones: [{fecha_operacion, ficha_id (None = sin identificar),
    articulo_id, articulo_nombre, articulo_grupo, bultos}] — una fila por
    fecha y FICHA. La ficha es la clave de VENTA: dos fichas del mismo
    artículo y cliente ("Banana Bolivia" y "Banana Ecuador" para Día) son
    dos filas, cada una con su precio, su kilaje y su envase. El artículo
    viaja al lado porque es lo que agrupa y filtra por grupo.
    margenes_por_fecha: {fecha: {ficha_id: fila de
    calcular_listado_para_negociar_precios anclado a ESA fecha}} — de cada
    fila se usan precio_vigente, costo_actual, costo_envase_unidad_venta y
    denominador_tasas (todos por unidad de venta del cliente). Usar el
    MISMO listado que Márgenes por Artículo es lo que garantiza que las
    dos pantallas den idéntico.

    Filtros: articulo_id y grupo recortan los artículos IDENTIFICADOS. Los
    sin identificar no se pueden filtrar (no se sabe qué son) y aparecen
    SIEMPRE en los no calculables — ocultarlos sería descartarlos en silencio.

    Devuelve {"grupos": [{grupo, etiqueta, filas, subtotal}], "totales",
    "no_calculables", "fechas_incluidas"}. Cada fila calculable trae
    bultos, unidades, precios/costos promedio ponderados por unidad,
    venta_neta, costo_mercaderia, costo_envase, costo_total, renta_pesos y
    utilidad_pct (renta sobre MERCADERÍA, como Márgenes). Renglones con 0
    bultos no aportan nada y se saltean.
    """
    contenido_por_ficha = {}
    unidad_por_ficha = {}
    for ficha in fichas:
        contenido_por_ficha[ficha["id"]] = _numero(ficha.get("contenido_caja"))
        unidad_por_ficha[ficha["id"]] = ficha.get("unidad_venta")

    acumulado: dict = {}  # ficha_id -> fila calculable en armado
    no_calculables: dict = {}  # (motivo, ficha_id) -> {bultos, dias}
    fechas_incluidas = set()

    def _sumar_no_calculable(motivo, renglon, bultos):
        clave = (motivo, renglon.get("ficha_id"), renglon["articulo_id"])
        entrada = no_calculables.get(clave)
        if entrada is None:
            entrada = {
                "motivo": motivo,
                "motivo_etiqueta": ETIQUETAS_MOTIVO[motivo],
                "articulo_id": renglon["articulo_id"],
                "articulo_nombre": renglon["articulo_nombre"] or "Sin identificar",
                "bultos": 0.0,
                "dias": 0,
            }
            no_calculables[clave] = entrada
        entrada["bultos"] += bultos
        entrada["dias"] += 1

    for renglon in renglones:
        bultos = _numero(renglon["bultos"]) or 0.0
        if bultos == 0:
            continue  # un renglón sin cantidades no mueve plata ni pesa
        fecha = renglon["fecha_operacion"]
        fechas_incluidas.add(fecha)

        if renglon.get("ficha_id") is None:
            # Sin identificar: fuera de cualquier filtro (no se sabe qué
            # es), pero SIEMPRE a la vista en los no calculables. También
            # cae acá un renglón cuyo artículo se sabe pero cuya ficha ya
            # no existe: sin ficha no hay precio ni kilaje con qué medir.
            _sumar_no_calculable("sin_identificar", renglon, bultos)
            continue

        if articulo_id is not None and renglon["articulo_id"] != articulo_id:
            continue
        if grupo is not None and renglon["articulo_grupo"] != grupo:
            continue

        contenido = contenido_por_ficha.get(renglon["ficha_id"])
        if contenido is None or contenido <= 0:
            _sumar_no_calculable("sin_conversion", renglon, bultos)
            continue
        # La fila de Márgenes por Artículo anclada a la fecha del pedido:
        # si el artículo no está (sin compras recientes) o está sin costo,
        # no hay contra qué medir — mismo veredicto que daría esa pantalla.
        margen = margenes_por_fecha.get(fecha, {}).get(renglon["ficha_id"])
        costo_unidad = _numero(margen.get("costo_actual")) if margen else None
        if costo_unidad is None:
            _sumar_no_calculable("sin_costo", renglon, bultos)
            continue
        precio_lista = _numero(margen.get("precio_vigente"))
        if precio_lista is None:
            _sumar_no_calculable("sin_precio", renglon, bultos)
            continue
        envase_unidad = _numero(margen.get("costo_envase_unidad_venta")) or 0.0
        denominador_tasas = _numero(margen.get("denominador_tasas"))
        if denominador_tasas is None:
            denominador_tasas = 1.0

        unidades = bultos * contenido
        fila = acumulado.get(renglon["ficha_id"])
        if fila is None:
            fila = {
                "articulo_id": renglon["articulo_id"],
                "articulo_nombre": renglon["articulo_nombre"],
                "grupo": renglon["articulo_grupo"],
                "unidad_venta": unidad_por_ficha.get(renglon["ficha_id"]),
                "bultos": 0.0,
                "unidades": 0.0,
                "venta_lista": 0.0,
                "venta_neta": 0.0,
                "costo_mercaderia": 0.0,
                "costo_envase": 0.0,
            }
            acumulado[renglon["ficha_id"]] = fila
        fila["bultos"] += bultos
        fila["unidades"] += unidades
        fila["venta_lista"] += unidades * precio_lista
        # Lo que efectivamente entra: el precio de lista con las tasas del
        # cliente aplicadas (misma cuenta que Márgenes, nunca el precio crudo).
        fila["venta_neta"] += unidades * precio_lista * denominador_tasas
        fila["costo_mercaderia"] += unidades * costo_unidad
        fila["costo_envase"] += unidades * envase_unidad

    def _cerrar_cuenta(fila):
        """Los derivados de una fila o un subtotal: costo total, renta y utilidad SOBRE MERCADERÍA."""
        fila["costo_total"] = fila["costo_mercaderia"] + fila["costo_envase"]
        fila["renta_pesos"] = fila["venta_neta"] - fila["costo_total"]
        fila["utilidad_pct"] = (
            fila["renta_pesos"] / fila["costo_mercaderia"] * 100 if fila["costo_mercaderia"] else None
        )

    for fila in acumulado.values():
        fila["precio_lista_promedio"] = fila["venta_lista"] / fila["unidades"] if fila["unidades"] else None
        fila["precio_neto_promedio"] = fila["venta_neta"] / fila["unidades"] if fila["unidades"] else None
        fila["costo_promedio"] = fila["costo_mercaderia"] / fila["unidades"] if fila["unidades"] else None
        fila["envase_promedio"] = fila["costo_envase"] / fila["unidades"] if fila["unidades"] else None
        _cerrar_cuenta(fila)

    grupos = []
    for clave_grupo in ORDEN_GRUPOS:
        filas = sorted(
            (f for f in acumulado.values() if f["grupo"] == clave_grupo),
            key=lambda f: f["articulo_nombre"],
        )
        if not filas:
            continue
        subtotal = {
            "bultos": sum(f["bultos"] for f in filas),
            "venta_neta": sum(f["venta_neta"] for f in filas),
            "costo_mercaderia": sum(f["costo_mercaderia"] for f in filas),
            "costo_envase": sum(f["costo_envase"] for f in filas),
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

    lista_no_calculables = sorted(
        no_calculables.values(), key=lambda e: (e["motivo"], e["articulo_nombre"])
    )
    totales = {
        "bultos": sum(g["subtotal"]["bultos"] for g in grupos),
        "venta_neta": sum(g["subtotal"]["venta_neta"] for g in grupos),
        "costo_mercaderia": sum(g["subtotal"]["costo_mercaderia"] for g in grupos),
        "costo_envase": sum(g["subtotal"]["costo_envase"] for g in grupos),
        # Lo que quedó AFUERA, siempre a la vista: nunca sumó como cero.
        "no_calculables_casos": len(lista_no_calculables),
        "no_calculables_bultos": sum(e["bultos"] for e in lista_no_calculables),
    }
    _cerrar_cuenta(totales)

    return {
        "grupos": grupos,
        "totales": totales,
        "no_calculables": lista_no_calculables,
        "fechas_incluidas": sorted(fechas_incluidas),
    }
