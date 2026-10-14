"""PALMALA CRUCES (dueño, 14/10): la cuenta corriente interna entre Frutamax
(Lionel) y Palmala. Solo Gerencia, y SOLO en Frutamax: las tablas
(`db/palmala_cruces_1..3`, migración palmala_1) no existen en la base de
Palmala, y la app de Palmala no muestra el botón ni las consulta
(`ES_FRUTAMAX` en app/main.py).

Cada movimiento: fecha, cuenta (Pesos, Dólares socios, Dólares NDT, cada una
con su saldo), sentido ("Palmala debe" suma, "Palmala pagó" resta), importe,
concepto (lista editable) y detalle. "Pago con cheque" y "Pago con echeq"
llevan número, banco y fecha de pago (lo exige la base, salvo el histórico).
Un pago en pesos de algo en dólares son DOS movimientos, uno por cuenta: no
hay conversión entre cuentas (dueño, 14/10).

El saldo lo calcula la vista `palmala_movimientos_con_saldo`; acá solo se
escribe cómo se lee: positivo es que Palmala te debe, negativo que le debés.
Nada de acá toca la base.
"""
import re
import unicodedata
from datetime import date

from core.listado_cheques import fecha_de_la_celda, importe_de_la_celda, numero_de_la_celda

CUENTAS = (("pesos", "Pesos", "$"), ("dolares_socios", "Dólares socios", "US$"),
           ("dolares_ndt", "Dólares NDT", "US$"))
NOMBRE_DE_CUENTA = {c: n for c, n, _ in CUENTAS}
SIGNO_DE_CUENTA = {c: s for c, _, s in CUENTAS}
SENTIDOS = (("debe", "Palmala debe"), ("pago", "Palmala pagó"))
NOMBRE_DE_SENTIDO = dict(SENTIDOS)


def importe_con_signo(valor, cuenta: str) -> str:
    """$ 1.234,56 o US$ 1.234,56 (sin el ",00" de los enteros)."""
    texto = f"{abs(float(valor)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    texto = texto[:-3] if texto.endswith(",00") else texto
    return f"{SIGNO_DE_CUENTA.get(cuenta, '$')}{texto}"


def texto_del_saldo(cuenta: str, saldo) -> str:
    """Quién le debe a quién (dueño, 14/10): "Palmala te debe $X" si el saldo
    es positivo, "Le debés a Palmala $X" si es negativo."""
    valor = round(float(saldo or 0), 2)
    if valor > 0:
        return f"Palmala te debe {importe_con_signo(valor, cuenta)}"
    if valor < 0:
        return f"Le debés a Palmala {importe_con_signo(valor, cuenta)}"
    return "Están a mano"


def saldos_por_cuenta(sumas: dict) -> list[dict]:
    """Las tres cuentas, siempre, en orden, con su saldo y su texto."""
    return [{"cuenta": c, "nombre": n, "saldo": round(float(sumas.get(c) or 0), 2),
             "texto": texto_del_saldo(c, sumas.get(c) or 0)} for c, n, _ in CUENTAS]


def _normalizar(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", texto).split())


def concepto_por_nombre(nombre, conceptos: list[dict]) -> int | None:
    """El concepto ACTIVO con ese nombre (sin acentos ni mayúsculas)."""
    buscado = _normalizar(nombre)
    for c in conceptos:
        if c.get("activo", True) and _normalizar(c["nombre"]) == buscado:
            return c["id"]
    return None


def cuenta_de_la_celda(valor) -> str:
    """La cuenta de lo escrito: Pesos si no dice nada, "" si dice algo que
    no se entiende (y entonces se elige: nunca se adivina)."""
    crudo = str(valor or "").strip()
    texto = _normalizar(crudo)
    if not crudo or crudo == "$" or texto in ("peso", "pesos", "ars"):
        return "pesos"
    if "ndt" in texto:
        return "dolares_ndt"
    if "dolar" in texto or "usd" in texto or texto in ("us", "u s"):
        return "dolares_socios"
    return ""


def sentido_de_la_celda(valor) -> str:
    texto = _normalizar(valor)
    if texto.startswith(("pag", "haber", "resta")) or "pago" in texto:
        return "pago"
    if texto.startswith(("debe", "suma")):
        return "debe"
    return ""


# --- LA PLANILLA ------------------------------------------------------------

SINONIMOS = {
    "fecha": ("fecha", "dia", "fecha movimiento"),
    "importe": ("importe", "monto", "valor", "total"),
    "debe": ("debe", "palmala debe", "suma"),
    "pago": ("pago", "pagó", "pagado", "palmala pago", "haber", "resta"),
    "sentido": ("sentido", "tipo", "movimiento", "debe o pago"),
    "concepto": ("concepto", "rubro"),
    "detalle": ("detalle", "descripcion", "observacion", "observaciones", "comentario", "nota"),
    "cuenta": ("cuenta", "moneda"),
    "cheque_numero": ("cheque", "numero de cheque", "nro cheque", "n cheque", "cheque nro", "numero cheque"),
    "cheque_banco": ("banco",),
    "cheque_fecha_pago": ("fecha de pago", "fecha pago", "vencimiento", "fecha de cobro", "cobro"),
}


def reconocer_columnas(titulos: list) -> dict:
    """{campo: índice} de los títulos que se reconocen, exactos."""
    reconocidas: dict = {}
    normales = [_normalizar(t) for t in titulos]
    for campo, nombres in SINONIMOS.items():
        buscados = {_normalizar(n) for n in nombres}
        for indice, titulo in enumerate(normales):
            if titulo and titulo in buscados and indice not in reconocidas.values():
                reconocidas.setdefault(campo, indice)
    return reconocidas


def crudos_de_la_planilla(filas: list[list]) -> list[dict] | None:
    """Los movimientos de la planilla, o None si no se reconoce la fila de
    títulos (fecha y, o el importe, o las columnas Debe y Pagó)."""
    for indice, fila in enumerate(filas[:15]):
        columnas = reconocer_columnas(list(fila))
        if "fecha" not in columnas or not ("importe" in columnas or "debe" in columnas or "pago" in columnas):
            continue
        crudos = []
        for datos in filas[indice + 1:]:
            if all(v is None or str(v).strip() == "" for v in datos):
                continue
            valor = {campo: (datos[col] if col < len(datos) else None) for campo, col in columnas.items()}
            if any(_normalizar(celda).startswith(("total", "subtotal", "saldo")) for celda in datos if celda):
                continue
            crudos.append(valor)
        return crudos
    return None


def renglones_para_revisar(crudos: list[dict], conceptos: list[dict], *, hoy: date,
                           foto_de_cada: list[int] | None = None) -> list[dict]:
    """Lo leído (planilla o fotos de cheques) como renglones del formulario,
    textos que se corrigen a mano. Con columnas Debe y Pagó, el sentido sale
    de cuál tiene el importe."""
    renglones = []
    for n, crudo in enumerate(crudos):
        sentido = sentido_de_la_celda(crudo.get("sentido"))
        importe = importe_de_la_celda(crudo.get("importe"))
        if not importe:
            debe, pago = importe_de_la_celda(crudo.get("debe")), importe_de_la_celda(crudo.get("pago"))
            if debe and not pago:
                importe, sentido = debe, "debe"
            elif pago and not debe:
                importe, sentido = pago, "pago"
        if importe.startswith("-"):
            importe = importe[1:]
            sentido = sentido or "pago"
        concepto = str(crudo.get("concepto") or "").strip()
        renglones.append({
            "fecha": fecha_de_la_celda(crudo.get("fecha")) or hoy.isoformat(),
            "cuenta": cuenta_de_la_celda(crudo.get("cuenta")),
            "sentido": crudo.get("sentido_fijo") or sentido,
            "importe": importe,
            "concepto_id": crudo.get("concepto_id") or concepto_por_nombre(concepto, conceptos),
            "concepto_leido": concepto,
            "detalle": str(crudo.get("detalle") or "").strip(),
            "cheque_numero": numero_de_la_celda(crudo.get("cheque_numero")),
            "cheque_banco": str(crudo.get("cheque_banco") or "").strip(),
            "cheque_fecha_pago": fecha_de_la_celda(crudo.get("cheque_fecha_pago")),
            "foto": (foto_de_cada[n] if foto_de_cada else -1),
            "sacar": False, "tildado": False,
        })
    return renglones


def renglones_de_cheques_leidos(leidas: list[dict], conceptos: list[dict], *, hoy: date
                                ) -> tuple[list[dict], list[str]]:
    """Las fotos de CHEQUES con que Palmala paga (una lectura por foto): un
    renglón por cheque, "Palmala pagó" en Pesos, con "Pago con echeq" o
    "Pago con cheque" según el tipo, y de qué foto salió."""
    crudos, fotos, avisos = [], [], []
    con_cheque = concepto_por_nombre("Pago con cheque", conceptos)
    con_echeq = concepto_por_nombre("Pago con echeq", conceptos)
    for foto, leida in enumerate(leidas):
        if leida.get("error"):
            avisos.append(f"La foto {foto + 1} no se pudo leer: {leida['error']}")
            continue
        for cheque in leida.get("cheques") or []:
            es_echeq = str(cheque.get("tipo") or "").lower() == "echeq"
            crudos.append({"fecha": hoy, "cuenta": "pesos", "sentido_fijo": "pago", "importe": cheque.get("importe"),
                           "concepto_id": con_echeq if es_echeq else con_cheque,
                           "detalle": str(cheque.get("librador") or "").strip(),
                           "cheque_numero": cheque.get("numero"), "cheque_banco": cheque.get("banco"),
                           "cheque_fecha_pago": cheque.get("fecha_pago")})
            fotos.append(foto)
    if not crudos and not avisos:
        avisos.append("No se encontró ningún cheque en las fotos.")
    return renglones_para_revisar(crudos, conceptos, hoy=hoy, foto_de_cada=fotos), avisos


def _importe(texto) -> float | None:
    try:
        valor = float(str(texto or "").replace(",", "."))
    except ValueError:
        return None
    return valor if valor > 0 else None


def problemas_de_los_renglones(renglones: list[dict], conceptos: list[dict], claves_de_bancos: set,
                               clave_de_banco) -> list[list[str]]:
    """Por renglón, lo que tiene mal (vacío si se puede guardar). Lo mismo
    que exige la base, dicho antes de guardar."""
    por_id = {c["id"]: c for c in conceptos}
    problemas = []
    for r in renglones:
        mal = []
        try:
            date.fromisoformat(str(r.get("fecha") or ""))
        except ValueError:
            mal.append("falta la fecha")
        if r.get("cuenta") not in NOMBRE_DE_CUENTA:
            mal.append("elegí la cuenta")
        if r.get("sentido") not in NOMBRE_DE_SENTIDO:
            mal.append("decí si Palmala debe o pagó")
        if _importe(r.get("importe")) is None:
            mal.append("falta el importe")
        concepto = por_id.get(r.get("concepto_id"))
        if concepto is None:
            mal.append("elegí el concepto" + (f" («{r['concepto_leido']}» no está en la lista)"
                                              if r.get("concepto_leido") else ""))
        elif not concepto.get("activo", True):
            mal.append(f"el concepto {concepto['nombre']} ya no se usa")
        tiene_cheque = any(str(r.get(k) or "").strip() for k in ("cheque_numero", "cheque_banco", "cheque_fecha_pago"))
        if concepto is not None and concepto.get("pide_cheque"):
            if not str(r.get("cheque_numero") or "").strip():
                mal.append("falta el número del cheque")
            if not str(r.get("cheque_banco") or "").strip():
                mal.append("falta el banco")
            elif clave_de_banco(r["cheque_banco"]) not in claves_de_bancos:
                mal.append("el banco no está en la lista")
            try:
                date.fromisoformat(str(r.get("cheque_fecha_pago") or ""))
            except ValueError:
                mal.append("falta la fecha de pago del cheque")
        elif concepto is not None and tiene_cheque:
            mal.append(f"el concepto {concepto['nombre']} no lleva cheque")
        problemas.append(mal)
    return problemas


def poner_a_todos(renglones: list[dict], cambios: dict) -> int:
    """Pone los `cambios` que vienen con valor (cuenta, sentido, concepto,
    fecha) en los TILDADOS, o en todos los que no se sacaron si no hay
    ninguno tildado. Devuelve a cuántos."""
    tildados = [r for r in renglones if r.get("tildado") and not r.get("sacar")]
    destino = tildados or [r for r in renglones if not r.get("sacar")]
    for r in destino:
        if cambios.get("cuenta") in NOMBRE_DE_CUENTA:
            r["cuenta"] = cambios["cuenta"]
        if cambios.get("sentido") in NOMBRE_DE_SENTIDO:
            r["sentido"] = cambios["sentido"]
        if cambios.get("concepto_id"):
            r["concepto_id"] = cambios["concepto_id"]
        if cambios.get("fecha"):
            r["fecha"] = cambios["fecha"]
    return len(destino)


# --- FILTROS ----------------------------------------------------------------

FILTROS = ("desde", "hasta", "concepto_id", "sentido", "cuenta")


def partes_del_filtro(filtros: dict, nombre_de_concepto: dict) -> list[str]:
    """El encabezado de la exportación: lo que se filtró, en palabras."""
    partes = []
    if filtros.get("desde") or filtros.get("hasta"):
        desde = filtros["desde"].strftime("%d/%m/%Y") if filtros.get("desde") else "el principio"
        hasta = filtros["hasta"].strftime("%d/%m/%Y") if filtros.get("hasta") else "hoy"
        partes.append(f"del {desde} al {hasta}")
    if filtros.get("cuenta"):
        partes.append(f"cuenta {NOMBRE_DE_CUENTA.get(filtros['cuenta'], filtros['cuenta'])}")
    if filtros.get("sentido"):
        partes.append(NOMBRE_DE_SENTIDO.get(filtros["sentido"], filtros["sentido"]))
    if filtros.get("concepto_id"):
        partes.append(f"concepto {nombre_de_concepto.get(filtros['concepto_id'], filtros['concepto_id'])}")
    return partes


def texto_del_filtro(partes: list[str]) -> str:
    return " · ".join(partes) or "sin filtros: todos los movimientos"


def suma_de_lo_filtrado(movimientos: list[dict]) -> dict:
    """{cuenta: suma con signo} de los movimientos que se ven (sin anulados)."""
    sumas: dict = {}
    for m in movimientos:
        sumas[m["cuenta"]] = round(sumas.get(m["cuenta"], 0) + float(m["con_signo"]), 2)
    return sumas
