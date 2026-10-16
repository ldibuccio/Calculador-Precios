"""CARTERA DE CHEQUES (dueño, 13/10): cargar un LISTADO con muchos cheques.

Un Excel (.xlsx o .xls), un CSV o un PDF (el listado de ECHEQ que baja del
banco). Las columnas pueden venir con cualquier nombre y en cualquier orden:

1. En una planilla se busca la fila de títulos y se reconoce cada columna por
   su nombre (`SINONIMOS`). Si se reconocen al menos el número y el importe,
   se lee sin la IA, celda por celda.
2. Si no (títulos raros, sin títulos, un PDF), lee la IA
   (`core.lector_cheques`), igual que la carga de compras con foto.

Lo leído va a una tabla para revisar renglón por renglón ANTES de guardar.
`problemas_de_los_renglones` dice qué tiene mal cada renglón (repetido, CUIT
inválido, falta un dato, banco que no está en la lista): esos no entran hasta
corregirlos. Nada de acá toca la base.

LISTADOS GRANDES (dueño, 14/10): con 130 cheques o más,
- el cliente se asigna solo ÚNICAMENTE si el CUIT del librador es PROPIO de un
  cliente (`clientes_cuits`, varios por cliente). Un cheque de TERCEROS no se
  asigna: si ese CUIT ya vino antes, se sugiere "La última vez vino de X"
  (`sugerencias`). Al elegir un cliente a mano, se pregunta una vez por CUIT
  si es propio (`cuits_para_preguntar`): nunca se aprende solo;
- un banco que no está se avisa UNA vez arriba (`bancos_que_faltan`), y el
  mismo banco con otro nombre es el mismo (`core.cheques.clave_de_banco`);
- "Para todos" cambia de una vez todos los renglones o solo los tildados
  (`poner_a_todos`).
"""
import csv
import io
import re
import unicodedata
from datetime import date, datetime, timedelta

from core.cheques import _banco_de_la_lista, clave_de_banco, numero_normalizado

# Los nombres con que puede venir cada columna, sin acentos ni mayúsculas.
SINONIMOS = {
    "numero": ("numero", "nro", "n", "no", "num", "cheque", "nro cheque", "numero de cheque", "numero cheque",
               "n cheque", "nro de cheque", "id echeq", "echeq", "id", "nro echeq", "numero echeq"),
    "banco": ("banco", "entidad", "banco emisor", "banco librador", "entidad emisora", "banco girado"),
    "fecha_pago": ("fecha de pago", "fecha pago", "fecha de cobro", "fecha cobro", "vencimiento",
                   "fecha de vencimiento", "fecha vencimiento", "f pago", "pago", "cobro", "fecha"),
    "importe": ("importe", "monto", "valor", "total", "importe $", "monto $", "$"),
    "cuit_librador": ("cuit", "cuit librador", "cuit del librador", "cuit emisor", "cuit firmante", "cuil",
                      "cuit/cuil", "cuit cuil", "documento"),
    "librador": ("librador", "cliente", "emisor", "razon social", "firmante", "nombre", "de quien",
                 "nombre librador", "librador nombre", "titular"),
    "tipo": ("tipo", "tipo de cheque", "clase"),
}

# La planilla modelo que se baja vacía: los títulos, en este orden.
COLUMNAS_DE_LA_PLANILLA = ("Número", "Banco", "Fecha de pago", "Importe", "CUIT del librador",
                           "Librador o cliente", "Tipo (Físico o ECHEQ)")


def _normalizar(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9$/ ]+", " ", texto).split())


def reconocer_columnas(titulos: list) -> dict:
    """{campo: índice de la columna} de los títulos que se reconocen. Primero
    las coincidencias exactas; "fecha" sola, solo si no hay otra de pago."""
    reconocidas: dict = {}
    normales = [_normalizar(t) for t in titulos]
    for campo, nombres in SINONIMOS.items():
        for indice, titulo in enumerate(normales):
            if titulo and titulo in nombres and indice not in reconocidas.values():
                reconocidas.setdefault(campo, indice)
    # Un título que CONTIENE el nombre ("Nro. de cheque emitido", "CUIT del firmante").
    for campo, nombres in SINONIMOS.items():
        if campo in reconocidas:
            continue
        for indice, titulo in enumerate(normales):
            if indice in reconocidas.values() or not titulo:
                continue
            if any(len(n) > 3 and n in titulo for n in nombres):
                reconocidas[campo] = indice
                break
    return reconocidas


def _alcanza(columnas: dict) -> bool:
    return "numero" in columnas and "importe" in columnas


def filas_de_la_planilla(contenido: bytes, tipo: str) -> list[list]:
    """Las filas de un .xlsx, .xls o .csv, como listas de valores."""
    if tipo == "xlsx":
        import openpyxl
        libro = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
        try:
            return [list(fila) for hoja in libro.worksheets for fila in hoja.iter_rows(values_only=True)]
        finally:
            libro.close()
    if tipo == "xls":
        import xlrd
        libro = xlrd.open_workbook(file_contents=contenido)
        filas = []
        for hoja in libro.sheets():
            for i in range(hoja.nrows):
                fila = []
                for celda in hoja.row(i):
                    if celda.ctype == xlrd.XL_CELL_DATE:
                        fila.append(datetime(*xlrd.xldate_as_tuple(celda.value, libro.datemode)))
                    else:
                        fila.append(celda.value)
                filas.append(fila)
        return filas
    if tipo == "csv":
        for codificacion in ("utf-8-sig", "latin-1"):
            try:
                texto = contenido.decode(codificacion)
                break
            except UnicodeDecodeError:
                continue
        primera = texto.splitlines()[0] if texto.strip() else ""
        separador = max((";", ",", "\t", "|"), key=primera.count)
        return [fila for fila in csv.reader(io.StringIO(texto), delimiter=separador)]
    raise ValueError(f"Tipo de planilla no soportado: {tipo}")


def _vacia(fila) -> bool:
    return all(v is None or str(v).strip() == "" for v in fila)


def renglones_de_la_planilla(filas: list[list]) -> list[dict] | None:
    """Los cheques de la planilla con las columnas reconocidas por su título, o
    None si no se reconocen (entonces lee la IA). La fila de títulos es la
    primera de las 15 de arriba que reconoce número e importe."""
    for indice, fila in enumerate(filas[:15]):
        columnas = reconocer_columnas(list(fila))
        if not _alcanza(columnas):
            continue
        renglones = []
        for datos in filas[indice + 1:]:
            if _vacia(datos):
                continue
            valor = {campo: (datos[col] if col < len(datos) else None) for campo, col in columnas.items()}
            if not str(valor.get("numero") or "").strip() and valor.get("importe") in (None, ""):
                continue
            # El renglón de totales del pie: "Total" en cualquier celda.
            if any(_normalizar(celda).startswith(("total", "subtotal")) for celda in datos):
                continue
            renglones.append(valor)
        return renglones
    return None


def texto_de_la_planilla(filas: list[list]) -> str:
    """La planilla como texto, para que la lea la IA."""
    return "\n".join(" | ".join(str(v).strip() for v in fila if v is not None and str(v).strip())
                     for fila in filas if not _vacia(fila))


# --- VALORES ---------------------------------------------------------------

def fecha_de_la_celda(valor) -> str:
    """AAAA-MM-DD de lo que venga: una fecha de Excel, "25/10/2026", "25-10-26",
    "2026-10-25", o un número de serie de Excel. "" si no se entiende."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, (int, float)) and 20000 < float(valor) < 80000:
        return (date(1899, 12, 30) + timedelta(days=int(valor))).isoformat()
    texto = str(valor).strip().split(" ")[0]
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return ""


def importe_de_la_celda(valor) -> str:
    """El importe como "1234.56": de un número, de "$ 1.234,56" o de "1,234.56"."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, (int, float)):
        return f"{float(valor):.2f}".rstrip("0").rstrip(".")
    texto = re.sub(r"[^0-9,.\-]", "", str(valor))
    if not texto:
        return ""
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")       # 1.234,56
        else:
            texto = texto.replace(",", "")                         # 1,234.56
    elif "," in texto:
        decimales = texto.rpartition(",")[2]
        if texto.count(",") == 1 and len(decimales) <= 2:
            texto = texto.replace(",", ".")                        # 1234,5
        else:
            texto = texto.replace(",", "")                         # 1,234 o 1,234,567
    elif texto.count(".") > 1 or (texto.count(".") == 1 and len(texto.split(".")[-1]) == 3):
        texto = texto.replace(".", "")                             # 1.234 o 1.234.567
    try:
        return f"{float(texto):.2f}".rstrip("0").rstrip(".")
    except ValueError:
        return ""


def numero_de_la_celda(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def cuit_de_la_celda(valor) -> str:
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def tipo_de_la_celda(valor) -> str:
    """ECHEQ salvo que la celda diga CLARAMENTE que es físico (dueño, 16/10):
    "Físico", "Papel". Vacío o lo que no se entiende, ECHEQ."""
    texto = _normalizar(valor)
    if "echeq" in texto or "electron" in texto:
        return "echeq"
    if "fisic" in texto or "papel" in texto:
        return "fisico"
    return "echeq"


def cuit_valido(cuit: str) -> bool:
    """11 números y el dígito verificador de la AFIP bien."""
    if not re.fullmatch(r"[0-9]{11}", cuit or ""):
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    resto = sum(int(d) * p for d, p in zip(cuit[:10], pesos)) % 11
    verificador = 0 if resto == 0 else 11 - resto
    return verificador != 10 and verificador == int(cuit[10])


def renglones_para_revisar(crudos: list[dict], propios: dict, bancos: list[dict]) -> list[dict]:
    """Lo leído (de la planilla o de la IA) como renglones del formulario:
    textos que se corrigen a mano. De quién es: el cliente de quien el CUIT
    del librador es PROPIO (`propios`: {CUIT: cliente_id}); si no, el nombre
    del librador a mano. El nombre solo no asigna un cliente (dueño, 14/10)."""
    renglones = []
    for crudo in crudos:
        librador = str(crudo.get("librador") or "").strip()
        cuit = cuit_de_la_celda(crudo.get("cuit_librador"))
        cliente_id = propios.get(cuit)
        renglones.append({
            "numero": numero_de_la_celda(crudo.get("numero")),
            "banco": _banco_de_la_lista(crudo.get("banco"), bancos) if crudo.get("banco") else "",
            "fecha_pago": fecha_de_la_celda(crudo.get("fecha_pago")),
            "importe": importe_de_la_celda(crudo.get("importe")),
            "cuit_librador": cuit,
            "tipo": tipo_de_la_celda(crudo.get("tipo")),
            "origen": "cliente" if cliente_id else ("a_mano" if librador else ""),
            "cliente_id": cliente_id,
            "nombre_a_mano": "" if cliente_id else librador,
        })
    return renglones


def _importe(texto) -> float | None:
    try:
        valor = float(str(texto or "").replace(",", "."))
    except ValueError:
        return None
    return valor if valor > 0 else None


def problemas_de_los_renglones(renglones: list[dict], bancos: list[dict], ya_cargados: set) -> list[list[str]]:
    """Por renglón, la lista de lo que tiene mal (vacía si está bien).

    `ya_cargados` son las claves de los cheques de la base: (banco,
    número sin ceros adelante, CUIT). Repetido es contra la base o contra
    otro renglón del mismo listado que no se sacó (se marcan los dos). El
    banco se compara por su `clave_de_banco`: "BANCO DE GALICIA" es "Galicia"."""
    claves_de_bancos = {clave_de_banco(b["nombre"]) for b in bancos}
    en_la_base = {(clave_de_banco(b), n, c) for b, n, c in ya_cargados}
    claves = []
    for r in renglones:
        claves.append((clave_de_banco(r.get("banco")), numero_normalizado(r.get("numero")),
                       str(r.get("cuit_librador") or "")))
    veces: dict = {}
    for r, clave in zip(renglones, claves):
        if not r.get("sacar"):
            veces[clave] = veces.get(clave, 0) + 1
    problemas = []
    for r, clave in zip(renglones, claves):
        mal = []
        if not str(r.get("numero") or "").strip():
            mal.append("falta el número")
        if not clave[0]:
            mal.append("falta el banco")
        elif clave[0] not in claves_de_bancos:
            mal.append("el banco no está en la lista")
        try:
            date.fromisoformat(str(r.get("fecha_pago") or ""))
        except ValueError:
            mal.append("falta la fecha de pago")
        if _importe(r.get("importe")) is None:
            mal.append("falta el importe")
        if not cuit_valido(clave[2]):
            mal.append("CUIT inválido")
        origen = r.get("origen")
        if origen == "cliente" and not r.get("cliente_id"):
            mal.append("elegí el cliente")
        elif origen == "a_mano" and not str(r.get("nombre_a_mano") or "").strip():
            mal.append("falta de quién es")
        elif origen not in ("cliente", "a_mano", "canje"):
            mal.append("decí de quién es")
        if clave[1] and clave[0] and clave in en_la_base:
            mal.append("ya está cargado")
        elif clave[1] and veces.get(clave, 0) > 1:
            mal.append("repetido en el listado")
        problemas.append(mal)
    return problemas


def bancos_que_faltan(renglones: list[dict], bancos: list[dict]) -> list[tuple[str, int]]:
    """Los bancos de los renglones que no están en la lista, UNA vez cada uno
    (el mismo banco con otro nombre es uno), con cuántos cheques lo traen. El
    nombre es el primero con que aparece."""
    en_la_lista = {clave_de_banco(b["nombre"]) for b in bancos}
    faltan: dict = {}
    for r in renglones:
        clave = clave_de_banco(r.get("banco"))
        if r.get("sacar") or not clave or clave in en_la_lista:
            continue
        nombre, cuantos = faltan.get(clave, (" ".join(str(r["banco"]).split()), 0))
        faltan[clave] = (nombre, cuantos + 1)
    return list(faltan.values())


# "Para todos": qué campos cambia y qué valores acepta.
CAMPOS_PARA_TODOS = ("origen", "cliente_id", "nombre_a_mano", "tipo", "banco")


def poner_a_todos(renglones: list[dict], cambios: dict) -> int:
    """Pone los `cambios` (solo los que vienen con valor) en los renglones
    TILDADOS, o en todos los que no se sacaron si no hay ninguno tildado.
    Elegir de quién es pone los tres datos juntos: el cliente solo si es un
    cliente, el nombre solo si es a mano. Devuelve a cuántos se les puso."""
    tildados = [r for r in renglones if r.get("tildado") and not r.get("sacar")]
    destino = tildados or [r for r in renglones if not r.get("sacar")]
    origen = cambios.get("origen")
    for r in destino:
        if origen in ("cliente", "a_mano", "canje"):
            r["origen"] = origen
            r["cliente_id"] = cambios.get("cliente_id") if origen == "cliente" else None
            r["nombre_a_mano"] = (cambios.get("nombre_a_mano") or "").strip() if origen == "a_mano" else ""
        if cambios.get("tipo") in ("fisico", "echeq"):
            r["tipo"] = cambios["tipo"]
        if (cambios.get("banco") or "").strip():
            r["banco"] = " ".join(cambios["banco"].split())
    return len(destino)


def asignar_por_cuit_propio(renglones: list[dict], propios: dict) -> int:
    """Los renglones cuyo CUIT es propio de un cliente pasan a ese cliente
    (después de decir "sí, es propio"). Devuelve cuántos cambiaron."""
    cambiados = 0
    for r in renglones:
        cliente_id = propios.get(r.get("cuit_librador") or "")
        if cliente_id and not r.get("sacar") and (r.get("origen"), r.get("cliente_id")) != ("cliente", cliente_id):
            r.update(origen="cliente", cliente_id=cliente_id, nombre_a_mano="")
            cambiados += 1
    return cambiados


def sugerencias(renglones: list[dict], propios: dict, ultimos: dict) -> list[int | None]:
    """Por renglón, el cliente de quien vino la ÚLTIMA vez un cheque con ese
    CUIT (`ultimos`: {CUIT: cliente_id}), para un cheque de TERCEROS (el CUIT
    no es propio de nadie) que todavía no tiene ese cliente. Si no, None."""
    resultado = []
    for r in renglones:
        cuit = r.get("cuit_librador") or ""
        sugerido = ultimos.get(cuit) if cuit_valido(cuit) and cuit not in propios else None
        if sugerido and (r.get("origen"), r.get("cliente_id")) == ("cliente", sugerido):
            sugerido = None
        resultado.append(None if r.get("sacar") else sugerido)
    return resultado


def cuits_para_preguntar(renglones: list[dict], propios: dict, ya_vinieron: set,
                         terceros: set) -> list[tuple[str, int]]:
    """(CUIT, cliente) a preguntar UNA vez cada uno: "¿es un CUIT propio de
    este cliente?". Se pregunta por un cheque con el cliente elegido a mano
    cuyo CUIT no es propio de nadie, nunca vino antes en un cheque de un
    cliente (`ya_vinieron`: entonces es de un tercero que ya se vio) y no se
    contestó "es de un tercero" en este listado (`terceros`)."""
    preguntas: dict = {}
    for r in renglones:
        cuit = r.get("cuit_librador") or ""
        if (r.get("sacar") or r.get("origen") != "cliente" or not r.get("cliente_id") or not cuit_valido(cuit)
                or cuit in propios or cuit in ya_vinieron or cuit in terceros):
            continue
        preguntas.setdefault(cuit, r["cliente_id"])
    return list(preguntas.items())


def planilla_modelo() -> bytes:
    """La planilla vacía para bajar: solo los títulos, que se reconocen solos.
    Sin renglón de ejemplo: si la suben sin borrarlo, entraría como un cheque."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Cheques"
    for columna, titulo in enumerate(COLUMNAS_DE_LA_PLANILLA, start=1):
        hoja.cell(row=1, column=columna, value=titulo).font = Font(bold=True)
    for letra, ancho in zip("ABCDEFG", (14, 18, 14, 14, 18, 26, 20)):
        hoja.column_dimensions[letra].width = ancho
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
