"""PANEL DE CONTROL de Gerencia (dueño, 08/10) — puro, sin base.

Un tablero de cuadros grandes, cada uno con UN número. NINGUNA cuenta es nueva:
cada cuadro junta lo que ya calcula otra pantalla, y esto solo lo resume.

  1. Rentabilidad por cliente (dueño, 16/10): mes anterior, mes en curso y
     7 días, en dos renglones: "Armado" (lo enviado) y "Recibido" (lo que
     firmó el súper), contra el costo real de lo armado menos la segunda
     cobrada que le toca al cliente.
  2. Cajas: el stock de cada caja contra su umbral (`hay_que_reponer`).
  3. Pedidos incompletos: los renglones de la alerta, más los de la cruz.
  4. Ingresos debajo del peso: cajón declarado contra cajón pesado, cada
     unidad (kilos, unidades, cubetas) sumada solo dentro de sí misma.
  5. Vales a cobrar: el total en cartera.
  6. Vacíos en depósito: el stock de pilas, todas las marcas.
  7. Rechazos: los reingresos valuados como en la Rentabilidad Real, contra
     la facturación y los bultos de Márgenes.
  8. Mermas y 9. Segunda: la cuenta de Pérdidas (`perdidas_por_periodo`), y
     para la segunda, menos lo que pagó el puesto (`lotes_de_segunda`).
"""
from datetime import date, timedelta

from core.envases import hay_que_reponer


def meses_para_comparar(hoy: date) -> dict:
    """El último mes de calendario CERRADO y el mes corriente hasta hoy."""
    primero_del_mes = hoy.replace(day=1)
    fin_anterior = primero_del_mes - timedelta(days=1)
    return {
        "anterior": {"desde": fin_anterior.replace(day=1), "hasta": fin_anterior},
        "actual": {"desde": primero_del_mes, "hasta": hoy},
    }


def segunda_cobrada_por_cliente(lotes: list[dict], guias: list[dict]) -> dict:
    """Lo que pagó el puesto por la segunda, repartido entre los clientes
    (dueño, 16/10): por artículo, en proporción a los bultos de segunda que
    salieron de las guías R de cada cliente en el mismo período.

    `lotes`: los lotes de segunda del período (`lotes_de_segunda`); cuenta el
    `importe` cobrado, un lote sin cobrar no reparte nada. `guias`: las guías
    R vigentes del período, cada una {cliente_id, articulo_id, bultos_segunda}.

    Lo que no se puede repartir no se inventa: un artículo con cobro y sin
    segunda de guías R en el período, o la parte de una guía sin cliente, va
    a "sin_repartir". Devuelve {"por_cliente": {cliente_id: pesos},
    "sin_repartir": pesos}."""
    cobrado: dict = {}
    for lote in lotes:
        if lote.get("importe") is not None:
            cobrado[lote["articulo_id"]] = cobrado.get(lote["articulo_id"], 0.0) + float(lote["importe"])
    por_cliente: dict = {}
    sin_repartir = 0.0
    for articulo_id, pesos in cobrado.items():
        de_este = [g for g in guias if g["articulo_id"] == articulo_id and float(g["bultos_segunda"] or 0) > 0]
        total = sum(float(g["bultos_segunda"]) for g in de_este)
        if not total:
            sin_repartir += pesos
            continue
        for guia in de_este:
            parte = pesos * float(guia["bultos_segunda"]) / total
            if guia.get("cliente_id") is None:
                sin_repartir += parte
            else:
                por_cliente[guia["cliente_id"]] = por_cliente.get(guia["cliente_id"], 0.0) + parte
    return {"por_cliente": {c: round(v, 2) for c, v in por_cliente.items()}, "sin_repartir": round(sin_repartir, 2)}


def celda_de_rentabilidad(totales: dict, segunda: float) -> dict:
    """Una celda del cuadro, con los `totales` de la Rentabilidad Real.

    La venta: lo enviado (Armado) o lo recibido (Recibido) menos lo que el
    motor ya descuenta por un rechazo de un remito que no volvió. El costo:
    el real de lo armado —mercadería, que en una caja de guía R ya trae la
    merma, la segunda y lo que falta, más el cartón— más los rechazos que se
    perdieron (a segunda o a reproceso, con su caja), menos la diferencia de
    lo devuelto al proveedor y menos la segunda cobrada que le toca. En
    Recibido, el rechazo que VUELVE AL STOCK ya viene acreditado por el motor
    (dueño, 17/10: se cuenta una sola vez, como en Rentabilidad Real); en
    Armado no hay devoluciones y esas líneas son cero. La ganancia va sobre
    el costo de la mercadería, como en Rentabilidad Real. Sin mercadería,
    pct None."""
    venta = float(totales["venta_neta"]) - float(totales.get("devoluciones_venta") or 0)
    mercaderia = float(totales["costo_mercaderia"])
    carton = float(totales["costo_envase"])
    rechazos = float(totales.get("rechazos_perdidos") or 0)
    al_proveedor = float(totales.get("diferencia_devolucion_proveedor") or 0)
    costo = mercaderia + carton + rechazos - al_proveedor - segunda
    return {"venta": round(venta, 2), "mercaderia": round(mercaderia, 2), "carton": round(carton, 2),
            "rechazos": round(rechazos, 2), "al_proveedor": round(al_proveedor, 2), "segunda": round(segunda, 2),
            "costo": round(costo, 2), "ganancia": round(venta - costo, 2),
            "pct": (venta - costo) / mercaderia * 100 if mercaderia > 0 else None,
            "afuera_bultos": float(totales.get("afuera_bultos") or 0)}


ESTADO_BAJO, ESTADO_BIEN, ESTADO_SIN_UMBRAL, ESTADO_SIN_CONTEO = "bajo", "bien", "sin_umbral", "sin_conteo"


def estado_de_las_cajas(envases: list[dict]) -> dict:
    """Cada caja con su estado contra el umbral de reposición, y cuántas están bajas.

    Bajo = `hay_que_reponer` (stock por debajo del umbral), la misma regla de
    la alerta de Cajas. Sin umbral cargado no es rojo: "sin umbral". Una caja
    a la que nunca se le hizo el conteo inicial no tiene stock: "sin conteo".
    """
    filas = []
    for envase in envases:
        if envase.get("stock") is None:
            estado = ESTADO_SIN_CONTEO
        elif envase.get("umbral_reposicion") is None:
            estado = ESTADO_SIN_UMBRAL
        elif hay_que_reponer(envase):
            estado = ESTADO_BAJO
        else:
            estado = ESTADO_BIEN
        filas.append(dict(envase, estado=estado))
    orden = {ESTADO_BAJO: 0, ESTADO_BIEN: 1, ESTADO_SIN_UMBRAL: 2, ESTADO_SIN_CONTEO: 3}
    filas.sort(key=lambda f: (orden[f["estado"]], f["nombre"].lower()))
    return {"filas": filas, "bajas": sum(1 for f in filas if f["estado"] == ESTADO_BAJO)}


def resumen_de_pedidos_incompletos(renglones: list[dict]) -> dict:
    """Cuántos PEDIDOS salieron incompletos, a partir de sus renglones.

    Un pedido es (cliente, fecha): la alerta trae el renglón con su pedido.
    """
    pedidos = {r["pedido_id"] for r in renglones}
    return {"pedidos": len(pedidos), "renglones": renglones}


UNIDADES_DEL_CAJON = ("kilo", "unidad", "cubeta")


def faltantes_por_unidad(compras: list[dict]) -> dict:
    """`kilos_debajo_del_peso` por separado para cada unidad del cajón (dueño, 08/10).

    No se convierte nada: los kilos se suman con kilos, las unidades con
    unidades y las cubetas con cubetas. Ninguna compra queda afuera. La
    unidad es la del contenido del cajón (`unidad_compra`; vacía es kilo).
    """
    return {unidad: kilos_debajo_del_peso([c for c in compras if (c.get("unidad_compra") or "kilo") == unidad])
            for unidad in UNIDADES_DEL_CAJON}


def kilos_debajo_del_peso(compras: list[dict]) -> dict:
    """El % de lo que faltó sobre lo declarado de lo que se recibió, en UNA unidad.

    Por compra (dueño, 08/10): declarados = cajones recibidos × contenido
    declarado; pesados = cajones recibidos × contenido pesado. Solo suma lo
    que FALTÓ: una compra que pesó de más no compensa a las que pesaron de
    menos. Sin umbral.
    """
    filas, declarados_total, faltante_total = [], 0.0, 0.0
    for compra in compras:
        cajones = float(compra["cajones_recibidos"])
        declarados = cajones * float(compra["contenido_comprado"])
        pesados = cajones * float(compra["contenido_recibido"])
        faltante = max(declarados - pesados, 0.0)
        declarados_total += declarados
        faltante_total += faltante
        filas.append(dict(compra, declarados=declarados, pesados=pesados, diferencia=pesados - declarados,
                          faltante=faltante))
    pct = faltante_total / declarados_total * 100 if declarados_total else None
    return {"pct": pct, "declarados": declarados_total, "faltante": faltante_total,
            "compras": len(filas), "filas": filas}


def resumen_de_rechazos(devoluciones: list[dict], facturacion: float, bultos_vendidos: float) -> dict:
    """Los rechazos de un período en plata y en bultos, contra lo facturado y lo vendido.

    `devoluciones` son los reingresos vinculados (`devoluciones_vinculadas_por_rango`),
    valuados con `valor_por_bulto`: el costo congelado del armado, o el precio
    de SU compra si se devolvió al proveedor (opción B). El que no tiene valor
    no suma cero en silencio: sus bultos se cuentan aparte.
    """
    pesos = bultos = sin_valor = 0.0
    for devolucion in devoluciones:
        cantidad = float(devolucion["bultos"])
        bultos += cantidad
        if devolucion.get("valor_por_bulto") is None:
            sin_valor += cantidad
        else:
            pesos += cantidad * float(devolucion["valor_por_bulto"])
    return {
        "pesos": pesos,
        "bultos": bultos,
        "bultos_sin_valor": sin_valor,
        "facturacion": facturacion,
        "bultos_vendidos": bultos_vendidos,
        "pct_plata": pesos / facturacion * 100 if facturacion else None,
        "pct_bultos": bultos / bultos_vendidos * 100 if bultos_vendidos else None,
    }


def resumen_de_mermas(perdidas: dict) -> dict:
    """El renglón de mermas de Pérdidas (`perdidas_por_periodo`) y su detalle por artículo.

    El costo es el de Pérdidas: la mercadería más la caja, si era caja armada
    (regla del dueño, 21/09).
    """
    renglon = perdidas["renglones"]["merma"]
    return {"total": renglon["total"], "mercaderia": renglon["mercaderia"], "cajas": renglon["caja_pesos"],
            "bultos": renglon["bultos"], "bultos_sin_costo": renglon["bultos_sin_costo"],
            "filas": [f for f in perdidas["detalle"] if f["destino"] == "merma"]}


# LA SEGUNDA DE UNA GUÍA R VA A $0 (dueño, 08/10): su costo ya está en las cajas
# armadas —el costo del cajón entero viaja a la primera ("reproceso_toma",
# neutro en plata)— y no se mueve. Lo que paga el puesto por ella es recupero.
COSTO_DE_LA_SEGUNDA_DEL_REPROCESO = 0.0


def resumen_de_segunda(perdidas: dict, lotes: list[dict], rechazos: list[dict], rechazos_sin_costo: float) -> dict:
    """Lo que se perdió en segunda: el costo de TODO lo que fue a segunda menos lo que pagó el puesto.

    El puesto paga la segunda junta, así que el costo también es de toda
    (dueño, 08/10), abierto por origen:
      - pase: el renglón de segunda de Pérdidas (`perdidas_por_periodo`),
        mercadería más caja;
      - rechazo: lo que la Rentabilidad Real llama "rechazos perdidos" (los
        que fueron a segunda o a reproceso: los bultos al costo congelado del
        armado más la caja), de todos los clientes — `rechazos` trae una
        fila por artículo con `pesos` y `bultos`;
      - reproceso: `COSTO_DE_LA_SEGUNDA_DEL_REPROCESO`.
    `lotes` son los lotes al puesto del mismo período (`lotes_de_segunda`,
    por la fecha de la salida); los que no se cobraron se cuentan aparte. Los
    rechazos sin costo congelado no suman cero en silencio: se cuentan.
    """
    renglon = perdidas["renglones"]["segunda"]
    cobrados = [l for l in lotes if l["importe"] is not None]
    cobrado = sum(l["importe"] for l in cobrados)
    por_origen = {"pase": renglon["total"], "rechazo": sum(r["pesos"] for r in rechazos),
                  "reproceso": COSTO_DE_LA_SEGUNDA_DEL_REPROCESO}
    vacia = {"bultos": 0.0, "pase": 0.0, "rechazo": 0.0, "cobrado": 0.0}
    por_articulo: dict = {}
    for fila in perdidas["detalle"]:
        if fila["destino"] == "segunda":
            articulo = por_articulo.setdefault(
            fila["articulo_id"], dict(vacia, articulo_id=fila["articulo_id"], articulo=fila["articulo"]))
            articulo["pase"] += fila["total"]
            articulo["bultos"] += fila["bultos"]
    for fila in rechazos:
        articulo = por_articulo.setdefault(
            fila["articulo_id"], dict(vacia, articulo_id=fila["articulo_id"], articulo=fila["articulo"]))
        articulo["rechazo"] += fila["pesos"]
        articulo["bultos"] += fila["bultos"]
    for lote in cobrados:
        articulo = por_articulo.setdefault(
            lote["articulo_id"], dict(vacia, articulo_id=lote["articulo_id"], articulo=lote["articulo"]))
        articulo["cobrado"] += lote["importe"]
    filas = sorted(({**f, "costo": f["pase"] + f["rechazo"], "perdida": f["pase"] + f["rechazo"] - f["cobrado"]}
                    for f in por_articulo.values()), key=lambda f: (-f["perdida"], f["articulo"]))
    costo = sum(por_origen.values())
    return {"perdida": costo - cobrado, "costo": costo, "por_origen": por_origen, "cobrado": cobrado,
            "bultos": renglon["bultos"] + sum(r["bultos"] for r in rechazos),
            "rechazos_sin_costo": rechazos_sin_costo,
            "lotes_sin_cobrar": len(lotes) - len(cobrados), "filas": filas}


# PÉRDIDA TOTAL (dueño, 13/10): de cada artículo, los cinco que más plata pierden.
TOP_DE_LA_PERDIDA = 5


def resumen_de_perdida_total(mermas: dict, segunda: dict, faltante: dict, facturacion: float) -> dict:
    """Lo que se perdió en el período, en plata al COSTO, sobre lo facturado a
    precio de lista (el mismo criterio del cuadro Rechazos).

    Tres partes, cada una la de su cuadro: `mermas` (`resumen_de_mermas`),
    `segunda` (`resumen_de_segunda`: el costo de lo que fue a segunda menos lo
    cobrado) y `faltante` (`core.kilos_guia_r.faltante_en_plata`: lo que no
    quedó registrado en las guías R). Por artículo suma las tres y se queda
    con los `TOP_DE_LA_PERDIDA` que más pierden.
    """
    partes = {"merma": float(mermas["total"]), "segunda": float(segunda["perdida"]),
              "faltante": float(faltante["pesos"])}
    total = sum(partes.values())
    vacia = {"merma": 0.0, "segunda": 0.0, "faltante": 0.0}
    por_articulo: dict = {}
    for fila in mermas["filas"]:
        articulo = por_articulo.setdefault(fila["articulo_id"], dict(vacia, articulo=fila["articulo"]))
        articulo["merma"] += float(fila["total"])
    for fila in segunda["filas"]:
        articulo = por_articulo.setdefault(fila["articulo_id"], dict(vacia, articulo=fila["articulo"]))
        articulo["segunda"] += float(fila["perdida"])
    for articulo_id, fila in faltante["por_articulo"].items():
        articulo = por_articulo.setdefault(articulo_id, dict(vacia, articulo=fila["articulo"]))
        articulo["faltante"] += float(fila["pesos"])
    filas = sorted(({**f, "articulo_id": a, "total": f["merma"] + f["segunda"] + f["faltante"]}
                    for a, f in por_articulo.items()), key=lambda f: (-f["total"], f["articulo"]))
    return {
        "total": total, "partes": partes, "facturacion": facturacion,
        "pct": total / facturacion * 100 if facturacion else None,
        "pct_partes": {clave: (monto / facturacion * 100 if facturacion else None) for clave, monto in partes.items()},
        "top": filas[:TOP_DE_LA_PERDIDA],
        "guias_sin_cuenta": faltante["guias_sin_cuenta"], "guias_sin_precio": faltante["guias_sin_precio"],
    }
