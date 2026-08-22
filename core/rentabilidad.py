"""Rentabilidad de Pedidos: qué dejó (estimado) cada artículo pedido — puro, sin tocar la base.

La decisión de fondo, cerrada por el dueño: los bultos son LO PEDIDO, no
lo armado. Se asume que se vendió todo lo del pedido, sin ajustar — el
tilde de armado es una herramienta de trabajo del depósito, no una
medición. Esto es una estimación de rentabilidad, no facturación.

De dónde sale cada dato:
- Bultos: renglones de los pedidos VIGENTES del rango (los anulados por
  reemplazo no cuentan), sumados por fecha y artículo.
- Precio de venta: el vigente A LA FECHA de cada pedido (un cambio de
  precio a mitad del rango pega solo en los pedidos posteriores).
- Costo: el motor de costeo de 48 hs existente, con la fecha del pedido
  como momento de referencia (el costo real de la mercadería de ese día).
- Conversión bultos → unidad de venta: contenido_caja de la ficha.

Invariante duro: lo que no se puede calcular NO suma como cero. Va
aparte, con su motivo y su peso en bultos, y el total dice cuánto quedó
afuera. Cuatro motivos: sin identificar, sin conversión en la ficha,
sin precio vigente, sin costo (sin compras en la ventana de 48 hs).
"""

ETIQUETAS_GRUPO = {"fruta": "Fruta", "hortaliza": "Hortaliza", "hoja": "Hoja", "pesada": "Pesada"}
ETIQUETA_SIN_GRUPO = "Sin grupo"
# El orden fijo de las secciones del reporte (None = artículos sin grupo, al final).
ORDEN_GRUPOS = ["fruta", "hortaliza", "hoja", "pesada", None]

ETIQUETAS_MOTIVO = {
    "sin_identificar": "Renglón sin identificar (no matchea ninguna ficha)",
    "sin_conversion": "Sin conversión de bultos en la ficha (contenido por caja)",
    "sin_precio": "Sin precio de venta vigente a la fecha del pedido",
    "sin_costo": "Sin compras en la ventana de 48 hs (no hay costo)",
}


def _numero(valor):
    return float(valor) if valor is not None else None


def calcular_rentabilidad_de_pedidos(
    renglones: list[dict],
    fichas: list[dict],
    precios_por_fecha: dict,
    costos_por_fecha: dict,
    articulo_id: int | None = None,
    grupo: str | None = None,
) -> dict:
    """Arma el reporte de rentabilidad a partir de datos ya traídos (puro, testeable sin base).

    renglones: [{fecha_operacion, articulo_id (None = sin identificar),
    articulo_nombre, articulo_grupo, bultos}] — una fila por fecha y artículo.
    precios_por_fecha / costos_por_fecha: {fecha: {articulo_id: valor}},
    ambos por unidad de venta del cliente (la misma de la ficha).

    Filtros: articulo_id y grupo recortan los artículos IDENTIFICADOS. Los
    sin identificar no se pueden filtrar (no se sabe qué son) y aparecen
    SIEMPRE en los no calculables — ocultarlos sería descartarlos en silencio.

    Devuelve {"grupos": [{grupo, etiqueta, filas, subtotal}], "totales",
    "no_calculables", "fechas_incluidas"}. Cada fila calculable trae bultos,
    unidades, precio y costo promedio ponderado, venta, costo_total,
    renta_pesos y renta_pct. Renglones con 0 bultos no aportan nada y se saltean.
    """
    contenido_por_articulo = {}
    unidad_por_articulo = {}
    for ficha in fichas:
        contenido_por_articulo[ficha["articulo_id"]] = _numero(ficha.get("contenido_caja"))
        unidad_por_articulo[ficha["articulo_id"]] = ficha.get("unidad_venta")

    acumulado: dict = {}  # articulo_id -> fila calculable en armado
    no_calculables: dict = {}  # (motivo, articulo_id) -> {bultos, dias}
    fechas_incluidas = set()

    def _sumar_no_calculable(motivo, renglon, bultos):
        clave = (motivo, renglon["articulo_id"])
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

        if renglon["articulo_id"] is None:
            # Sin identificar: fuera de cualquier filtro (no se sabe qué
            # es), pero SIEMPRE a la vista en los no calculables.
            _sumar_no_calculable("sin_identificar", renglon, bultos)
            continue

        if articulo_id is not None and renglon["articulo_id"] != articulo_id:
            continue
        if grupo is not None and renglon["articulo_grupo"] != grupo:
            continue

        contenido = contenido_por_articulo.get(renglon["articulo_id"])
        if contenido is None or contenido <= 0:
            _sumar_no_calculable("sin_conversion", renglon, bultos)
            continue
        precio = _numero(precios_por_fecha.get(fecha, {}).get(renglon["articulo_id"]))
        if precio is None:
            _sumar_no_calculable("sin_precio", renglon, bultos)
            continue
        costo = _numero(costos_por_fecha.get(fecha, {}).get(renglon["articulo_id"]))
        if costo is None:
            _sumar_no_calculable("sin_costo", renglon, bultos)
            continue

        unidades = bultos * contenido
        fila = acumulado.get(renglon["articulo_id"])
        if fila is None:
            fila = {
                "articulo_id": renglon["articulo_id"],
                "articulo_nombre": renglon["articulo_nombre"],
                "grupo": renglon["articulo_grupo"],
                "unidad_venta": unidad_por_articulo.get(renglon["articulo_id"]),
                "bultos": 0.0,
                "unidades": 0.0,
                "venta": 0.0,
                "costo_total": 0.0,
            }
            acumulado[renglon["articulo_id"]] = fila
        fila["bultos"] += bultos
        fila["unidades"] += unidades
        fila["venta"] += unidades * precio
        fila["costo_total"] += unidades * costo

    for fila in acumulado.values():
        fila["precio_promedio"] = fila["venta"] / fila["unidades"] if fila["unidades"] else None
        fila["costo_promedio"] = fila["costo_total"] / fila["unidades"] if fila["unidades"] else None
        fila["renta_pesos"] = fila["venta"] - fila["costo_total"]
        fila["renta_pct"] = (fila["renta_pesos"] / fila["venta"] * 100) if fila["venta"] else None

    grupos = []
    for clave_grupo in ORDEN_GRUPOS:
        filas = sorted(
            (f for f in acumulado.values() if f["grupo"] == clave_grupo),
            key=lambda f: f["articulo_nombre"],
        )
        if not filas:
            continue
        venta = sum(f["venta"] for f in filas)
        costo_total = sum(f["costo_total"] for f in filas)
        grupos.append(
            {
                "grupo": clave_grupo,
                "etiqueta": ETIQUETAS_GRUPO.get(clave_grupo, ETIQUETA_SIN_GRUPO),
                "filas": filas,
                "subtotal": {
                    "bultos": sum(f["bultos"] for f in filas),
                    "venta": venta,
                    "costo_total": costo_total,
                    "renta_pesos": venta - costo_total,
                    "renta_pct": ((venta - costo_total) / venta * 100) if venta else None,
                },
            }
        )

    venta_total = sum(g["subtotal"]["venta"] for g in grupos)
    costo_total = sum(g["subtotal"]["costo_total"] for g in grupos)
    lista_no_calculables = sorted(
        no_calculables.values(), key=lambda e: (e["motivo"], e["articulo_nombre"])
    )
    totales = {
        "bultos": sum(g["subtotal"]["bultos"] for g in grupos),
        "venta": venta_total,
        "costo_total": costo_total,
        "renta_pesos": venta_total - costo_total,
        "renta_pct": ((venta_total - costo_total) / venta_total * 100) if venta_total else None,
        # Lo que quedó AFUERA, siempre a la vista: nunca sumó como cero.
        "no_calculables_casos": len(lista_no_calculables),
        "no_calculables_bultos": sum(e["bultos"] for e in lista_no_calculables),
    }

    return {
        "grupos": grupos,
        "totales": totales,
        "no_calculables": lista_no_calculables,
        "fechas_incluidas": sorted(fechas_incluidas),
    }
