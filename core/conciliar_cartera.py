"""CONCILIAR LA CARTERA CON EL BANCO (dueño, 16/10).

Lionel sube uno o varios archivos o fotos del banco (el listado de ECHEQ en
cartera o en custodia: Excel, PDF o capturas) y se cruzan contra los cheques
que el sistema tiene EN CARTERA. Nada se guarda: es una foto de cómo están.

- Lo leído de varios archivos se junta; el mismo cheque (número, banco, monto
  y fecha de pago) que ya vino en un archivo anterior se toma una vez.
- El cruce: por número (sin ceros adelante) y banco (`clave_de_banco`); si lo
  leído no trae banco, por número y monto. Después se controlan el monto y la
  fecha de pago.
- Cuatro grupos: coinciden; en el banco y no en el sistema (faltan cargar);
  en el sistema y no en el banco (probablemente salieron sin registrarse); y
  con diferencia (mismo cheque, otro monto o fecha de pago).
- "Solo ECHEQ" (por defecto): los físicos no están en el banco, así que no se
  comparan; se muestran aparte, sin marcarlos como faltantes.

Nada de acá toca la base.
"""
from datetime import date

from core.cheques import EN_CARTERA, clave_de_banco, numero_normalizado
from core.listado_cheques import cuit_de_la_celda, fecha_de_la_celda, importe_de_la_celda


def _monto(valor) -> float | None:
    texto = importe_de_la_celda(valor)
    try:
        return round(float(texto), 2) if texto else None
    except ValueError:
        return None


def _fecha(valor) -> date | None:
    if isinstance(valor, date):
        return valor
    texto = fecha_de_la_celda(valor)
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def leido_del_banco(cheque: dict, archivo: int) -> dict:
    """Un cheque leído de un archivo, con el monto como número y la fecha como fecha."""
    return {"numero": str(cheque.get("numero") or "").strip(), "banco": str(cheque.get("banco") or "").strip(),
            "importe": _monto(cheque.get("importe")), "fecha_pago": _fecha(cheque.get("fecha_pago")),
            "cuit_librador": cuit_de_la_celda(cheque.get("cuit_librador")),
            "librador": str(cheque.get("librador") or "").strip(), "archivo": archivo}


def _clave(leido: dict) -> tuple:
    return (numero_normalizado(leido["numero"]), clave_de_banco(leido["banco"]), leido["importe"],
            leido["fecha_pago"])


def juntar_lo_leido(por_archivo: list[list[dict]]) -> tuple[list[dict], int]:
    """(los cheques de todos los archivos, cuántos se sacaron por repetidos).
    `por_archivo`: lo leído de cada archivo, en orden. El que ya vino en un
    archivo ANTERIOR no se vuelve a tomar; dentro de un mismo archivo, cada
    renglón es un cheque."""
    vistos: set = set()
    juntos, repetidos = [], 0
    for archivo, cheques in enumerate(por_archivo):
        de_este = []
        for cheque in cheques:
            leido = leido_del_banco(cheque, archivo)
            if not leido["numero"]:
                continue
            if _clave(leido) in vistos:
                repetidos += 1
                continue
            de_este.append(leido)
        vistos |= {_clave(leido) for leido in de_este}
        juntos += de_este
    return juntos, repetidos


def _es_el_mismo(leido: dict, cheque: dict) -> bool:
    """Por número y banco; si lo leído no trae banco, por número y monto."""
    if numero_normalizado(cheque["numero"]) != numero_normalizado(leido["numero"]):
        return False
    banco = clave_de_banco(leido["banco"])
    if banco:
        return clave_de_banco(cheque["banco"]) == banco
    return leido["importe"] is not None and round(float(cheque["importe"]), 2) == leido["importe"]


def diferencias(leido: dict, cheque: dict) -> list[str]:
    """Qué no coincide entre lo del banco y lo del sistema."""
    que = []
    if leido["importe"] is None or round(float(cheque["importe"]), 2) != leido["importe"]:
        que.append("monto")
    if leido["fecha_pago"] != cheque["fecha_pago"]:
        que.append("fecha de pago")
    return que


def _total(montos) -> float:
    return round(sum(float(m) for m in montos if m is not None), 2)


def cruzar_con_la_cartera(leidos: list[dict], cheques: list[dict], *, solo_echeq: bool = True) -> dict:
    """Los cuatro grupos, los físicos aparte y los totales de arriba.
    `cheques`: los del sistema (se toman los EN CARTERA)."""
    en_cartera = [c for c in cheques if c["estado"] in EN_CARTERA]
    comparables = [c for c in en_cartera if not solo_echeq or c["tipo"] == "echeq"]
    fisicos = [c for c in en_cartera if solo_echeq and c["tipo"] != "echeq"]
    usados: set = set()
    coinciden, con_diferencia, solo_banco = [], [], []
    for leido in leidos:
        candidatos = [c for c in comparables if c["id"] not in usados and _es_el_mismo(leido, c)]
        if not candidatos:
            solo_banco.append(leido)
            continue
        cheque = next((c for c in candidatos if not diferencias(leido, c)), candidatos[0])
        usados.add(cheque["id"])
        par = {"banco": leido, "sistema": cheque, "diferencias": diferencias(leido, cheque)}
        (con_diferencia if par["diferencias"] else coinciden).append(par)
    solo_sistema = [c for c in comparables if c["id"] not in usados]
    banco_total, sistema_total = _total(l["importe"] for l in leidos), _total(c["importe"] for c in comparables)
    return {
        "coinciden": coinciden, "solo_banco": solo_banco, "solo_sistema": solo_sistema,
        "con_diferencia": con_diferencia, "fisicos": fisicos, "solo_echeq": solo_echeq,
        "totales": {
            "coinciden": _total(p["sistema"]["importe"] for p in coinciden),
            "solo_banco": _total(l["importe"] for l in solo_banco),
            "solo_sistema": _total(c["importe"] for c in solo_sistema),
            "con_diferencia_banco": _total(p["banco"]["importe"] for p in con_diferencia),
            "con_diferencia_sistema": _total(p["sistema"]["importe"] for p in con_diferencia),
            "fisicos": _total(c["importe"] for c in fisicos),
        },
        "banco": {"cuantos": len(leidos), "total": banco_total},
        "sistema": {"cuantos": len(comparables), "total": sistema_total},
        "diferencia": round(banco_total - sistema_total, 2),
    }


def como_texto(leidos: list[dict]) -> list[dict]:
    """Lo leído para viajar en el formulario (JSON): la fecha como texto."""
    return [dict(l, fecha_pago=l["fecha_pago"].isoformat() if l["fecha_pago"] else None) for l in leidos]


def desde_texto(datos) -> list[dict]:
    """Lo que volvió del formulario. ValueError si no tiene la forma esperada."""
    if not isinstance(datos, list):
        raise ValueError("lo leído no es una lista")
    leidos = []
    for d in datos:
        if not isinstance(d, dict):
            raise ValueError("un cheque leído no tiene la forma esperada")
        leidos.append(leido_del_banco(d, int(d.get("archivo") or 0)))
    return leidos


def para_cargar(leidos: list[dict]) -> list[dict]:
    """Los que faltan, como los lee "Revisar cheques" (`renglones_para_revisar`):
    del listado de ECHEQ del banco, así que son ECHEQ."""
    return [{"numero": l["numero"], "banco": l["banco"], "importe": l["importe"],
             "fecha_pago": l["fecha_pago"].isoformat() if l["fecha_pago"] else "",
             "cuit_librador": l["cuit_librador"], "librador": l["librador"], "tipo": "echeq"} for l in leidos]
