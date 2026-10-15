"""CONCILIACIÓN (dueño, 15/10): cruzar los extractos del banco con lo que
dice el sistema. Puro: no toca la base.

- Se cruza por IMPORTE con su signo (un ingreso del sistema con un crédito del
  extracto, un egreso con un débito), al centavo, y con un margen de fecha de
  ±5 DÍAS HÁBILES (lunes a viernes). La descripción no tiene que coincidir:
  "Depósito de cheque Día" en el sistema puede ser "DEP CHEQ 30-7XXXX" en el
  extracto.
- Uno a uno: un renglón del extracto con un solo movimiento del sistema, y al
  revés.
- Si hay dos del mismo importe cerca, se emparejan por la fecha MÁS CERCANA y
  quedan marcados para revisar.
- Lo que ya está conciliado no se vuelve a cruzar.
"""
from datetime import date, timedelta

MARGEN_DIAS_HABILES = 5


def dias_habiles_entre(a: date, b: date) -> int:
    """Cuántos días hábiles (lunes a viernes) hay de una fecha a la otra, sin
    contar la primera: del viernes al lunes es 1. Simétrico."""
    if a > b:
        a, b = b, a
    dias, dia = 0, a
    while dia < b:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            dias += 1
    return dias


def _centavos(valor) -> int:
    return int(round(float(valor) * 100))


def cruzar(renglones: list[dict], sistema: list[dict], margen: int = MARGEN_DIAS_HABILES) -> list[dict]:
    """Los pares {"renglon_id", "origen", "origen_id", "a_revisar"}.

    `renglones`: los del extracto SIN conciliar, {"id", "fecha", "importe"}
    (con signo: crédito positivo, débito negativo). `sistema`: los
    movimientos de la cuenta SIN conciliar y sin anular, {"origen",
    "origen_id", "fecha", "tipo", "importe"} (importe positivo).

    Se arman todos los pares posibles (mismo importe con signo, dentro del
    margen) y se toman de la fecha más cercana a la más lejana, sin repetir
    ninguno de los dos lados. Un par queda "a revisar" si alguno de sus dos
    lados tenía otro candidato."""
    candidatos = []
    for r in renglones:
        for s in sistema:
            con_signo = _centavos(s["importe"]) * (1 if s["tipo"] == "ingreso" else -1)
            if con_signo != _centavos(r["importe"]):
                continue
            distancia = dias_habiles_entre(r["fecha"], s["fecha"])
            if distancia <= margen:
                candidatos.append((distancia, abs((r["fecha"] - s["fecha"]).days), r["id"],
                                   (s["origen"], s["origen_id"])))
    cuantos_r: dict = {}
    cuantos_s: dict = {}
    for _, _, rid, sid in candidatos:
        cuantos_r[rid] = cuantos_r.get(rid, 0) + 1
        cuantos_s[sid] = cuantos_s.get(sid, 0) + 1
    usados_r, usados_s, pares = set(), set(), []
    for _, _, rid, sid in sorted(candidatos, key=lambda c: (c[0], c[1], c[2], c[3])):
        if rid in usados_r or sid in usados_s:
            continue
        usados_r.add(rid)
        usados_s.add(sid)
        pares.append({"renglon_id": rid, "origen": sid[0], "origen_id": sid[1],
                      "a_revisar": cuantos_r[rid] > 1 or cuantos_s[sid] > 1})
    return sorted(pares, key=lambda p: p["renglon_id"])


# El concepto que se SUGIERE para cargar de un toque lo que está solo en el
# extracto: por palabras de la descripción del banco. Es una sugerencia, se
# cambia antes de cargar. Solo si el concepto existe y está activo en la cuenta.
_PALABRAS = (
    (("comision", "impuesto", "iva ", "i.v.a", "sellos", "ley 25413", "25.413", "percepcion", "retencion",
      "mantenimiento", "cargo", "imp.", "deb.cred", "debitos y creditos", "ingresos brutos", "iibb"),
     "Impuestos y comisiones", "Impuestos y comisiones"),
    (("transf", "trf", "transferencia"), "Transferencia recibida", "Transferencia enviada"),
)


def _sin_acentos(texto) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii").lower()


def concepto_sugerido(descripcion, importe, conceptos: list[dict]) -> int | None:
    """El id del concepto sugerido para un renglón del extracto, o None."""
    por_nombre = {_sin_acentos(c["nombre"]): c["id"] for c in conceptos if c.get("activo", True)}
    texto = _sin_acentos(descripcion)
    positivo = float(importe) > 0
    for palabras, si_entra, si_sale in _PALABRAS:
        if any(p in texto for p in palabras):
            elegido = por_nombre.get(_sin_acentos(si_entra if positivo else si_sale))
            if elegido:
                return elegido
    return por_nombre.get("otros ingresos" if positivo else "otros egresos")


def saldo_al(movimientos: list[dict], dia: date) -> float:
    """El saldo del sistema al cierre de `dia` (sin anulados)."""
    return round(sum(float(m["importe"]) * (1 if m["tipo"] == "ingreso" else -1)
                     for m in movimientos if not m.get("anulado") and m["fecha"] <= dia), 2)
