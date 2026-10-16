"""CUENTAS (dueño, 15/10): Caja, Banco e Inversiones con UN SOLO MOTOR, en
las dos apps (Frutamax y Palmala). Solo Gerencia.

Una cuenta es un renglón de `cuentas` (nombre, tipo caja/banco/inversión,
moneda, número para los bancos y cuenta madre): otra cuenta es agregar un
renglón, no programar. Cada cuenta tiene sus conceptos (`cuentas_conceptos`,
editables); las etiquetas (persona o empresa) se arman solas al cargar.

En el listado de una cuenta entran cuatro cosas (la vista
`cuentas_todos_los_movimientos`, que decide la base):
- los movimientos cargados a mano, por foto o por Excel;
- las TRANSFERENCIAS entre cuentas, una sola fila con dos patas: Suscripción
  (banco → inversión), Rescate (inversión → banco), Depósito de efectivo
  (caja → banco) y Extracción (banco → caja). Anular o corregir una cambia
  las dos patas, porque es una sola fila;
- los cheques DEPOSITADOS desde la Cartera, con la fecha de acreditación
  ("Depósito de cheque", etiqueta: de quién era);
- y su RECHAZO, si lo hubo ("Cheque rechazado").

Nada de acá toca la base.
"""
import re
import unicodedata
from datetime import date

TIPOS = (("caja", "Caja"), ("banco", "Banco"), ("inversion", "Inversión"))
NOMBRE_DE_TIPO = dict(TIPOS)
MONEDAS = (("pesos", "Pesos", "$"), ("dolares", "Dólares", "US$"))
NOMBRE_DE_MONEDA = {m: n for m, n, _ in MONEDAS}
SIGNO_DE_MONEDA = {m: s for m, _, s in MONEDAS}
SENTIDOS = (("ingreso", "Ingreso"), ("egreso", "Egreso"))
NOMBRE_DE_SENTIDO = dict(SENTIDOS)

# Los conceptos con que nace una cuenta nueva (dueño, 15/10): los mismos que
# la Caja o el Banco de Frutamax (db/cuentas_2.sql y cuentas_3.sql), sin los
# que son solo del histórico. (nombre, ingreso/egreso o None si van los dos).
CONCEPTOS_POR_TIPO = {
    "caja": (("Saldo inicial", None), ("Cobro Mecafront", "ingreso"), ("Cobro de terceros", "ingreso"),
             ("Aporte Lionel", "ingreso"), ("Aporte Ana", "ingreso"), ("Plata del puesto", "ingreso"),
             ("Préstamo/devolución recibida", "ingreso"), ("Otros ingresos", "ingreso"),
             ("Retiro Lionel", "egreso"), ("Retiro Ana", "egreso"), ("Entrega MN", "egreso"),
             ("Plata al puesto", "egreso"), ("Compra de dólares", "egreso"), ("BP", "egreso"),
             ("Préstamo/devolución entregada", "egreso"), ("Pagos a terceros", "egreso"), ("Ajuste", None)),
    "banco": (("Saldo inicial", None), ("Transferencia recibida", "ingreso"), ("Transferencia enviada", "egreso"),
              ("Pago a proveedor", "egreso"), ("Impuestos y comisiones", "egreso"), ("Otros ingresos", "ingreso"),
              ("Otros egresos", "egreso"), ("Ajuste", None)),
    "inversion": (("Saldo inicial", None), ("Rendimiento", None), ("Ajuste", None)),
}


def importe_en(valor, moneda: str) -> str:
    """$ 1.234,56 o US$ 1.234,56 (sin el ",00" de los enteros), sin signo."""
    texto = f"{abs(float(valor)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    texto = texto[:-3] if texto.endswith(",00") else texto
    return f"{SIGNO_DE_MONEDA.get(moneda, '$')}{texto}"


def saldo_en(valor, moneda: str) -> str:
    """El saldo con su signo: −$1.234 si es negativo (se ve, en rojo)."""
    return ("−" if round(float(valor or 0), 2) < 0 else "") + importe_en(valor or 0, moneda)


def digitos(texto) -> str:
    return re.sub(r"[^0-9]", "", str(texto or ""))


def cuenta_por_numero(texto, cuentas: list[dict]) -> dict | None:
    """La cuenta de banco ACTIVA cuyo número es el escrito, comparando solo los
    dígitos ("CC$ 191-220-000247/7" es "1912200002477"). Un número que no es
    de ninguna, o vacío, no es de ninguna: nunca se adivina."""
    buscado = digitos(texto)
    if len(buscado) < 6:
        return None
    for c in cuentas:
        if c.get("tipo") == "banco" and c.get("activa", True) and digitos(c.get("numero")) == buscado:
            return c
    return None


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


def _importe(texto) -> float | None:
    try:
        valor = float(str(texto or "").replace(",", "."))
    except ValueError:
        return None
    return valor if valor > 0 else None


def problemas_del_movimiento(r: dict, conceptos: list[dict]) -> list[str]:
    """Lo que tiene mal un movimiento antes de guardarlo (vacío si se puede).
    Lo mismo que exige la base, dicho antes."""
    mal = []
    try:
        date.fromisoformat(str(r.get("fecha") or ""))
    except ValueError:
        mal.append("falta la fecha")
    if r.get("tipo") not in NOMBRE_DE_SENTIDO:
        mal.append("decí si es ingreso o egreso")
    if _importe(r.get("importe")) is None:
        mal.append("falta el importe")
    concepto = {c["id"]: c for c in conceptos}.get(r.get("concepto_id"))
    if concepto is None:
        mal.append("elegí el concepto" + (f" («{r['concepto_leido']}» no está en la lista)"
                                          if r.get("concepto_leido") else ""))
    elif not concepto.get("activo", True):
        mal.append(f"el concepto {concepto['nombre']} ya no se usa")
    elif concepto.get("tipo") and r.get("tipo") in NOMBRE_DE_SENTIDO and concepto["tipo"] != r["tipo"]:
        mal.append(f"{concepto['nombre']} es un {NOMBRE_DE_SENTIDO[concepto['tipo']].lower()}")
    return mal


def problemas_de_la_transferencia(r: dict, cuenta: dict, otras: dict) -> list[str]:
    mal = []
    try:
        date.fromisoformat(str(r.get("fecha") or ""))
    except ValueError:
        mal.append("falta la fecha")
    if _importe(r.get("importe")) is None:
        mal.append("falta el importe")
    otra = otras.get(r.get("otra_cuenta_id"))
    if otra is None or otra["id"] == cuenta["id"]:
        mal.append("elegí la otra cuenta")
    elif otra["moneda"] != cuenta["moneda"]:
        mal.append("las dos cuentas tienen que ser de la misma moneda")
    if r.get("sentido") not in ("sale", "entra"):
        mal.append("decí si la plata sale de esta cuenta o entra")
    return mal


def nombre_de_la_transferencia(origen: dict, destino: dict) -> str:
    """Cómo se llama, como en la vista: lo que se ve antes de guardar."""
    pares = {("banco", "inversion"): "Suscripción", ("inversion", "banco"): "Rescate",
             ("caja", "banco"): "Depósito de efectivo", ("banco", "caja"): "Extracción"}
    return pares.get((origen["tipo"], destino["tipo"]), "Transferencia")


# --- EL LISTADO -------------------------------------------------------------

FILTROS = ("desde", "hasta", "concepto", "etiqueta", "tipo")


def partes_del_filtro(filtros: dict) -> list[str]:
    """El encabezado de la exportación: lo que se filtró, en palabras."""
    partes = []
    desde, hasta = filtros.get("desde"), filtros.get("hasta")
    if desde and hasta:
        partes.append(f"del {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}")
    elif desde:
        partes.append(f"desde el {desde.strftime('%d/%m/%Y')}")
    elif hasta:
        partes.append(f"hasta el {hasta.strftime('%d/%m/%Y')}")
    if filtros.get("tipo"):
        partes.append("solo " + NOMBRE_DE_SENTIDO.get(filtros["tipo"], filtros["tipo"]).lower() + "s")
    if filtros.get("concepto"):
        partes.append(f"concepto {filtros['concepto']}")
    if filtros.get("etiqueta"):
        partes.append(f"etiqueta {filtros['etiqueta']}")
    return partes


def texto_del_filtro(partes: list[str]) -> str:
    return " · ".join(partes) or "sin filtros: todos los movimientos"


def totales_por(movimientos: list[dict], campo: str) -> list[dict]:
    """Por concepto o por etiqueta, lo que entró y salió de los movimientos que
    se ven (sin anulados), de mayor a menor movimiento. Sin etiqueta va como
    "Sin etiqueta"."""
    por: dict = {}
    for m in movimientos:
        if m.get("anulado"):
            continue
        nombre = m.get(campo) or ("Sin etiqueta" if campo == "etiqueta" else "Sin concepto")
        t = por.setdefault(nombre, {"nombre": nombre, "ingresos": 0.0, "egresos": 0.0, "cuantos": 0})
        t["ingresos" if m["tipo"] == "ingreso" else "egresos"] += float(m["importe"])
        t["cuantos"] += 1
    for t in por.values():
        t["ingresos"], t["egresos"] = round(t["ingresos"], 2), round(t["egresos"], 2)
        t["neto"] = round(t["ingresos"] - t["egresos"], 2)
    return sorted(por.values(), key=lambda t: (-(t["ingresos"] + t["egresos"]), t["nombre"].lower()))


def saldo_de_la_cuenta(movimientos: list[dict], hoy: date) -> dict:
    """El saldo HOY (lo de fecha futura, como un cheque que se acredita
    mañana, no entra) y lo que está por acreditarse. Sin anulados."""
    saldo = a_futuro = 0.0
    for m in movimientos:
        if m.get("anulado"):
            continue
        valor = float(m["importe"]) * (1 if m["tipo"] == "ingreso" else -1)
        if m["fecha"] > hoy:
            a_futuro += valor
        else:
            saldo += valor
    return {"saldo": round(saldo, 2), "a_futuro": round(a_futuro, 2)}


# --- CARGA POR FOTO O POR EXCEL (dueño, 15/10): la pantalla de revisión -----
# Como Palmala Cruces: lo leído se muestra para corregir y NADA se guarda solo.

SINONIMOS = {
    "fecha": ("fecha", "dia", "fecha movimiento", "fecha operacion"),
    "importe": ("importe", "monto", "valor", "total"),
    "ingreso": ("ingreso", "ingresos", "entrada", "entradas", "credito", "creditos"),
    "egreso": ("egreso", "egresos", "salida", "salidas", "debito", "debitos", "gasto", "gastos"),
    "tipo": ("tipo", "movimiento", "ingreso o egreso", "sentido"),
    "concepto": ("concepto", "rubro", "categoria"),
    "etiqueta": ("etiqueta", "de quien", "para quien", "persona", "empresa", "quien", "beneficiario", "origen"),
    "detalle": ("detalle", "descripcion", "observacion", "observaciones", "comentario", "nota", "referencia"),
}


def reconocer_columnas(titulos: list) -> dict:
    """{campo: índice} de los títulos que se reconocen, exactos (sin acentos
    ni mayúsculas)."""
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
    títulos (una Fecha y, o el Importe, o las columnas Ingreso y Egreso). Las
    filas vacías y las de totales o saldos no son movimientos."""
    for indice, fila in enumerate(filas[:15]):
        columnas = reconocer_columnas(list(fila))
        if "fecha" not in columnas or not ({"importe", "ingreso", "egreso"} & set(columnas)):
            continue
        crudos = []
        for datos in filas[indice + 1:]:
            if all(v is None or str(v).strip() == "" for v in datos):
                continue
            if any(_normalizar(celda).startswith(("total", "subtotal", "saldo")) for celda in datos if celda):
                continue
            crudos.append({campo: (datos[col] if col < len(datos) else None) for campo, col in columnas.items()})
        return crudos
    return None


def tipo_de_la_celda(valor) -> str:
    texto = _normalizar(valor)
    if texto.startswith(("ingres", "entrad", "credit", "cobr")):
        return "ingreso"
    if texto.startswith(("egres", "salid", "debit", "pag", "gast")):
        return "egreso"
    return ""


def renglones_para_revisar(crudos: list[dict], conceptos: list[dict], *, hoy: date,
                           foto_de_cada: list[int] | None = None) -> list[dict]:
    """Lo leído como renglones del formulario, textos que se corrigen a mano.
    Con columnas Ingreso y Egreso, el tipo sale de cuál tiene el importe; un
    importe negativo es un egreso. El concepto se busca por nombre entre los
    de ESTA cuenta; si no está, queda vacío y se elige (nunca se adivina)."""
    from core.listado_cheques import fecha_de_la_celda, importe_de_la_celda
    renglones = []
    for n, crudo in enumerate(crudos):
        tipo = crudo.get("tipo_fijo") or tipo_de_la_celda(crudo.get("tipo"))
        importe = importe_de_la_celda(crudo.get("importe"))
        if not importe:
            ingreso, egreso = importe_de_la_celda(crudo.get("ingreso")), importe_de_la_celda(crudo.get("egreso"))
            if ingreso and not egreso:
                importe, tipo = ingreso, "ingreso"
            elif egreso and not ingreso:
                importe, tipo = egreso, "egreso"
        if importe.startswith("-"):
            importe, tipo = importe[1:], tipo or "egreso"
        concepto = str(crudo.get("concepto") or "").strip()
        renglones.append({
            "fecha": fecha_de_la_celda(crudo.get("fecha")) or hoy.isoformat(),
            "tipo": tipo, "importe": importe,
            "concepto_id": concepto_por_nombre(concepto, conceptos), "concepto_leido": concepto,
            "etiqueta": " ".join(str(crudo.get("etiqueta") or "").split()),
            "detalle": str(crudo.get("detalle") or "").strip(),
            "foto": (foto_de_cada[n] if foto_de_cada else -1), "sacar": False, "tildado": False,
        })
    return renglones


def renglones_de_comprobantes_leidos(leidas: list[dict], conceptos: list[dict], *, hoy: date
                                     ) -> tuple[list[dict], list[str]]:
    """Las fotos o PDF de comprobantes (una lectura por archivo, cada una con
    sus "movimientos"): un renglón por movimiento, con de qué foto salió."""
    crudos, fotos, avisos = [], [], []
    for foto, leida in enumerate(leidas):
        if leida.get("error"):
            avisos.append(f"La foto {foto + 1} no se pudo leer: {leida['error']}")
            continue
        for movimiento in leida.get("movimientos") or []:
            crudos.append({"fecha": movimiento.get("fecha"), "importe": movimiento.get("importe"),
                           "tipo_fijo": movimiento.get("tipo") if movimiento.get("tipo") in NOMBRE_DE_SENTIDO else "",
                           "concepto": movimiento.get("concepto"), "etiqueta": movimiento.get("quien"),
                           "detalle": movimiento.get("detalle")})
            fotos.append(foto)
    if not crudos and not avisos:
        avisos.append("No se encontró ningún movimiento en las fotos.")
    return renglones_para_revisar(crudos, conceptos, hoy=hoy, foto_de_cada=fotos), avisos


def poner_a_todos(renglones: list[dict], cambios: dict) -> int:
    """Pone los `cambios` que vienen con valor (tipo, concepto, etiqueta,
    fecha) en los TILDADOS, o en todos los que no se sacaron si no hay
    ninguno tildado. Devuelve a cuántos."""
    tildados = [r for r in renglones if r.get("tildado") and not r.get("sacar")]
    destino = tildados or [r for r in renglones if not r.get("sacar")]
    for r in destino:
        if cambios.get("tipo") in NOMBRE_DE_SENTIDO:
            r["tipo"] = cambios["tipo"]
        for campo in ("concepto_id", "etiqueta", "fecha"):
            if cambios.get(campo):
                r[campo] = cambios[campo]
    return len(destino)


def cuentas_del_hub(cuentas: list[dict]) -> tuple[list[dict], list[dict]]:
    """El orden del recuadro "Bancos y cajas" de Gerencia (dueño, 16/10): cada
    banco seguido de las inversiones que están dentro de él (después las
    inversiones sueltas), y aparte las cajas. (antes, después) de la Cartera
    de cheques, que va entre los dos. Una cuenta nueva cae en su lugar sola."""
    bancos = [c for c in cuentas if c["tipo"] == "banco"]
    ids_de_bancos = {b["id"] for b in bancos}
    antes = []
    for banco in bancos:
        antes.append(banco)
        antes.extend(c for c in cuentas if c["tipo"] == "inversion" and c.get("madre_id") == banco["id"])
    antes.extend(c for c in cuentas if c["tipo"] == "inversion" and c.get("madre_id") not in ids_de_bancos)
    return antes, [c for c in cuentas if c["tipo"] == "caja"]
