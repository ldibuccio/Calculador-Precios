"""REMITOS Y FACTURACIÓN (dueño, 01/10): estados, plazos y cuentas — puro.

UN REMITO POR ORDEN DE COMPRA. Cada pedido de Día tiene tres sucursales y
cada una su orden de compra (`pedidos_sucursales`): el remito oficial es uno
por cada una, así que un pedido lleva tres. El remito sale de OTRO sistema;
acá solo se anota su número, se congela lo que salió, se carga lo que el
súper firmó que recibió y el número de factura.

LOS ESTADOS NO SON UNA COLUMNA: salen de las fechas, igual que el estado de un
vale. Emitido (tiene número), recibido (`recibido_el`), facturado
(`factura_numero`). Anulado lo hace Gerencia con motivo, y uno facturado no
se anula (lo frena la base).

LOS RECHAZOS SE CARGAN UNA SOLA VEZ, en Depósito (`movimientos_stock` con
`pedido_renglon_id`): ahí mueven stock. El remito NO los vuelve a cargar: los
anota tal como dice el papel y los COTEJA contra lo de Depósito, renglón por
renglón. Si no coinciden, se ve en la pantalla y salta una alerta.

LO QUE SE COBRA es kilos RECIBIDOS × precio vigente a la fecha del pedido
(`precios_venta_historial`, por ficha). Es informativo: la factura la hace
otro sistema y esto sirve para controlarla.
"""

from datetime import date
from zoneinfo import ZoneInfo

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")

# Más de 4 días CORRIDOS emitido y sin volver: el camión vuelve en el día, y
# el 4 contempla un fin de semana largo o un feriado en el medio (dueño).
DIAS_REMITO_SIN_VOLVER = 4
# Más de 10 días CORRIDOS recibido y sin factura: se factura una vez por
# semana, más un fin de semana y un feriado (dueño).
DIAS_REMITO_SIN_FACTURA = 10
# La alerta de "pedidos sin remito" solo cuenta desde el despliegue (dueño):
# lo anterior nunca tuvo remito en este sistema y no es un olvido.
REMITOS_DESDE = date(2026, 10, 2)

TEXTO_DEL_ESTADO = {
    "emitido": "En viaje",
    "recibido": "Recibido, sin factura",
    "facturado": "Facturado",
    "anulado": "Anulado",
}


def estado_del_remito(remito: dict) -> str:
    """El estado sale de las fechas. Anulado manda sobre todo lo demás."""
    if remito.get("anulado_el") is not None:
        return "anulado"
    if remito.get("factura_numero"):
        return "facturado"
    if remito.get("recibido_el") is not None:
        return "recibido"
    return "emitido"


def dia_argentino(instante) -> date:
    return instante.astimezone(ARGENTINA).date()


def dias_desde(instante, hoy: date) -> int:
    """Días CORRIDOS entre el día argentino del instante y hoy."""
    return (hoy - dia_argentino(instante)).days


def sin_volver_hace_mucho(remito: dict, hoy: date) -> bool:
    return (estado_del_remito(remito) == "emitido"
            and dias_desde(remito["emitido_el"], hoy) > DIAS_REMITO_SIN_VOLVER)


def sin_factura_hace_mucho(remito: dict, hoy: date) -> bool:
    return (estado_del_remito(remito) == "recibido"
            and dias_desde(remito["recibido_el"], hoy) > DIAS_REMITO_SIN_FACTURA)


def _numero(valor):
    return None if valor is None else float(valor)


def diferencia_de_rechazo(renglon: dict) -> float | None:
    """Lo que dice el remito menos lo que cargó Depósito, en bultos.

    None mientras el remito no volvió: sin el papel no hay contra qué cotejar.
    Positivo es que el remito dice MÁS rechazo que Depósito (falta cargar un
    reingreso); negativo, que Depósito cargó de más.
    """
    remito = _numero(renglon.get("bultos_rechazados"))
    if remito is None:
        return None
    return remito - (_numero(renglon.get("rechazo_deposito")) or 0.0)


def rechazo_no_coincide(renglon: dict) -> bool:
    diferencia = diferencia_de_rechazo(renglon)
    return diferencia is not None and abs(diferencia) > 1e-9


def importe_del_renglon(renglon: dict) -> float | None:
    """Kilos RECIBIDOS × precio vigente. None si falta uno de los dos: un
    importe sin precio no es cero, y el total lo tiene que decir."""
    kilos = _numero(renglon.get("kilos_recibidos"))
    precio = _numero(renglon.get("precio"))
    if kilos is None or precio is None:
        return None
    return kilos * precio


def importe_del_remito(renglones: list[dict]) -> dict:
    """{total, sin_precio}: el total suma lo que tiene precio y `sin_precio`
    cuenta los renglones recibidos que no lo tienen. Sin esa cola, un total al
    que le faltan renglones se lee igual de cerrado."""
    total = 0.0
    sin_precio = 0
    for renglon in renglones:
        if renglon.get("kilos_recibidos") is None:
            continue
        importe = importe_del_renglon(renglon)
        if importe is None:
            sin_precio += 1
        else:
            total += importe
    return {"total": total, "sin_precio": sin_precio}


def leer_recepcion(renglones: list[dict], kilos_texto: dict, rechazo_texto: dict) -> tuple[str | None, dict]:
    """Valida lo cargado al recibir y lo devuelve como {renglon_id: (kilos, rechazados)}.

    Todos los renglones del remito, sin excepción: un remito recibido a medias
    dejaría la Rentabilidad cobrando unos renglones por lo recibido y otros por
    lo enviado. Los rechazados no pasan de los bultos que salieron (también lo
    frena la base). Con la coma o el punto como decimal, igual que el resto.
    """
    resultado = {}
    for renglon in renglones:
        rid = renglon["id"]
        nombre = renglon.get("articulo_nombre") or "un renglón"
        kilos = _leer_numero(kilos_texto.get(rid))
        if kilos is None or kilos < 0:
            return f"Falta lo recibido de {nombre}, o no es un número.", {}
        rechazo = _leer_numero(rechazo_texto.get(rid))
        if rechazo is None or rechazo < 0:
            return f"Faltan los bultos rechazados de {nombre} (si no hubo, 0).", {}
        if rechazo > float(renglon["bultos_enviados"]):
            return (f"{nombre}: rechazaron {_texto(rechazo)} bultos y salieron "
                    f"{_texto(renglon['bultos_enviados'])}."), {}
        resultado[rid] = (kilos, rechazo)
    return None, resultado


def _leer_numero(texto):
    if texto is None:
        return None
    texto = str(texto).strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _texto(valor) -> str:
    valor = float(valor)
    return str(int(valor)) if valor == int(valor) else f"{valor:g}".replace(".", ",")
