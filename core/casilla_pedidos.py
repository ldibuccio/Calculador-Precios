"""Lectura de la casilla de pedidos de la empresa, en SOLO LECTURA ESTRICTA.

La casilla es la cuenta Gmail VIVA de la empresa (años de correos): el
sistema nunca borra, nunca mueve, nunca marca como leído, nunca responde.
Las garantías van en capas:

- EXAMINE en vez de SELECT (``readonly=True``): el servidor rechaza
  cualquier intento de escritura sobre el buzón.
- ``BODY.PEEK`` en todos los FETCH: ni siquiera se marcaría ``\\Seen``
  aunque el buzón no estuviera abierto en solo lectura.
- Búsqueda SERVER-SIDE (``SINCE`` + ``FROM``): jamás se enumera ni se
  descarga el buzón entero — solo se bajan los mails de los remitentes
  permitidos posteriores a la fecha de activación.
- Sin estado en el mailbox: la idempotencia es por Message-ID contra la
  base (``mails_pedido``), nunca por flags del buzón.

La clave viene de la variable de entorno CLAVE_CASILLA_PEDIDOS (una por
servicio de Railway). Nunca de la base.
"""

import email
import email.policy
import email.utils
import imaplib
import os
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

CLAVE_CASILLA_ENV_VAR = "CLAVE_CASILLA_PEDIDOS"

ARGENTINA = timezone(timedelta(hours=-3))

# Abreviaturas de mes del criterio SINCE de IMAP (RFC 3501): van EN INGLÉS
# siempre, independientes del locale — no usar strftime("%b").
_MESES_IMAP = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ErrorCasilla(Exception):
    """Falló la conversación con la casilla (conexión, login, búsqueda o lectura)."""


def clave_casilla_configurada() -> str | None:
    """La clave IMAP desde la variable de Railway, o None si no está configurada."""
    clave = os.environ.get(CLAVE_CASILLA_ENV_VAR, "").strip()
    return clave or None


def separar_remitentes(remitentes_permitidos: str) -> list[str]:
    """La lista de direcciones permitidas desde el texto separado por comas de la config."""
    return [parte.strip().lower() for parte in (remitentes_permitidos or "").split(",") if parte.strip()]


class _ExtractorTextoMail(HTMLParser):
    """HTML del mail -> texto plano conservando la ESTRUCTURA de las tablas.

    Cada fila de tabla queda en una línea con las celdas separadas por
    tabulador, y una celda vacía queda como campo vacío entre tabuladores:
    "celda vacía = esa sucursal no pide ese artículo" sobrevive a la
    conversión, que es exactamente lo que el lector necesita para no
    inventar ceros ni correr columnas.
    """

    _IGNORADOS = {"style", "script", "head", "title"}
    _BLOQUES = {"p", "div", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._partes: list[str] = []
        self._ignorando = 0
        self._celdas_en_fila = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._IGNORADOS:
            self._ignorando += 1
        elif tag == "br":
            self._partes.append("\n")
        elif tag == "tr":
            self._partes.append("\n")
            self._celdas_en_fila = 0
        elif tag in ("td", "th"):
            if self._celdas_en_fila:
                self._partes.append("\t")
            self._celdas_en_fila += 1
        elif tag in self._BLOQUES:
            self._partes.append("\n")

    def handle_endtag(self, tag):
        if tag in self._IGNORADOS:
            if self._ignorando:
                self._ignorando -= 1
        elif tag == "tr" or tag in self._BLOQUES:
            self._partes.append("\n")

    def handle_data(self, data):
        if self._ignorando:
            return
        limpio = re.sub(r"[ \xa0\r\n\t]+", " ", data)
        if limpio.strip():
            self._partes.append(limpio)

    def texto(self) -> str:
        lineas = "".join(self._partes).split("\n")
        # Espacios sueltos afuera, pero los tabuladores del final se
        # CONSERVAN: una fila que termina en celdas vacías tiene que seguir
        # mostrando esas celdas (si no, el lector vería menos columnas).
        lineas = [linea.strip(" ").replace(" \t", "\t").replace("\t ", "\t") for linea in lineas]
        texto = "\n".join(lineas)
        return re.sub(r"\n{3,}", "\n\n", texto).strip("\n")


def html_a_texto(html: str) -> str:
    """El cuerpo HTML del mail pasado a texto plano, tablas incluidas (ver _ExtractorTextoMail)."""
    extractor = _ExtractorTextoMail()
    extractor.feed(html or "")
    extractor.close()
    return extractor.texto()


def _contenido_de_parte(parte) -> str:
    try:
        contenido = parte.get_content()
        if isinstance(contenido, str):
            return contenido
    except Exception:
        pass
    crudo = parte.get_payload(decode=True)
    if crudo is None:
        return ""
    charset = parte.get_content_charset() or "utf-8"
    try:
        return crudo.decode(charset, errors="replace")
    except LookupError:
        return crudo.decode("utf-8", errors="replace")


def _cuerpo_de_mensaje(mensaje) -> tuple[str, str | None]:
    """(cuerpo_crudo, cuerpo_texto) del mail.

    Se prefiere la parte HTML (la tabla del pedido de Día viaja ahí, y la
    conversión conserva las celdas vacías); si no hay, text/plain tal cual.
    El crudo se devuelve SIEMPRE entero, sin limpiar: es el respaldo.
    """
    parte_html = None
    parte_texto = None
    partes = mensaje.walk() if mensaje.is_multipart() else [mensaje]
    for parte in partes:
        tipo = parte.get_content_type()
        if tipo == "text/html" and parte_html is None:
            parte_html = parte
        elif tipo == "text/plain" and parte_texto is None:
            parte_texto = parte

    if parte_html is not None:
        crudo = _contenido_de_parte(parte_html)
        return crudo, html_a_texto(crudo)
    if parte_texto is not None:
        crudo = _contenido_de_parte(parte_texto)
        return crudo, (crudo.strip() or None)
    return "", None


def _fecha_de_mensaje(mensaje) -> datetime | None:
    try:
        fecha = email.utils.parsedate_to_datetime(mensaje["Date"])
    except (TypeError, ValueError):
        return None
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha


def _criterio_since(fecha_desde: datetime) -> str:
    """La fecha de activación como criterio SINCE (día calendario argentino, formato IMAP)."""
    dia = fecha_desde.astimezone(ARGENTINA).date()
    return f"{dia.day:02d}-{_MESES_IMAP[dia.month - 1]}-{dia.year}"


def _buscar_uids(conexion, criterio: str) -> list[bytes]:
    estado, datos = conexion.uid("SEARCH", None, criterio)
    if estado != "OK":
        raise ErrorCasilla(f"La búsqueda en el buzón falló ({criterio}).")
    if not datos or not datos[0]:
        return []
    return datos[0].split()


def _bytes_de_fetch(datos) -> bytes | None:
    for item in datos or []:
        if isinstance(item, tuple) and len(item) >= 2:
            return item[1]
    return None


def revisar_casilla(direccion: str, clave: str, servidor: str, fecha_desde: datetime, remitentes: list[str]) -> dict:
    """Revisa el buzón en solo lectura y devuelve qué hay, con el detalle para el reporte.

    Devuelve ``{"total_desde": n, "mails": [...]}``: ``total_desde`` es
    cuántos mails (de CUALQUIER remitente) hay desde la fecha de
    activación — sirve para ver de una si el filtro de remitente está mal
    escrito ("hay 12 mails pero ninguno pasa el filtro") — y ``mails`` son
    los de remitentes permitidos, ya descargados y con el cuerpo extraído:
    {"message_id", "remitente", "asunto", "recibido_el", "cuerpo_crudo",
    "cuerpo_texto"}. Los ajenos al filtro NI SE DESCARGAN.
    """
    try:
        conexion = imaplib.IMAP4_SSL(servidor)
    except Exception as error:
        raise ErrorCasilla(f"No se pudo conectar a {servidor}: {error}") from error

    try:
        try:
            conexion.login(direccion, clave)
        except imaplib.IMAP4.error as error:
            raise ErrorCasilla(
                f"El login de {direccion} falló: {error}. Si la cuenta es de Google Workspace, "
                "puede que el administrador tenga IMAP deshabilitado, o que haga falta una "
                "clave de aplicación nueva."
            ) from error

        # EXAMINE, no SELECT: el buzón queda abierto en modo solo lectura y
        # el servidor mismo rechaza cualquier escritura.
        estado, _ = conexion.select("INBOX", readonly=True)
        if estado != "OK":
            raise ErrorCasilla("No se pudo abrir la bandeja de entrada en modo solo lectura.")

        criterio_desde = _criterio_since(fecha_desde)
        total_desde = len(_buscar_uids(conexion, f"(SINCE {criterio_desde})"))

        uids: list[bytes] = []
        for remitente in remitentes:
            for uid in _buscar_uids(conexion, f'(SINCE {criterio_desde} FROM "{remitente}")'):
                if uid not in uids:
                    uids.append(uid)

        mails = []
        for uid in uids:
            estado, datos = conexion.uid("FETCH", uid, "(BODY.PEEK[])")
            crudo_bytes = _bytes_de_fetch(datos)
            if estado != "OK" or crudo_bytes is None:
                raise ErrorCasilla("No se pudo descargar un mail del buzón.")
            mensaje = email.message_from_bytes(crudo_bytes, policy=email.policy.default)

            recibido_el = _fecha_de_mensaje(mensaje)
            # SINCE tiene granularidad de DÍA y usa la fecha interna del
            # servidor: el corte fino contra la fecha de activación se hace
            # acá, con la fecha real del mail.
            if recibido_el is not None and recibido_el < fecha_desde:
                continue

            # Sin Message-ID (no debería pasar con un remitente real), un
            # identificador estable por buzón: el UID no cambia mientras no
            # cambie la UIDVALIDITY de la casilla.
            message_id = (mensaje["Message-ID"] or "").strip() or f"<uid-{uid.decode()}@{direccion}>"
            cuerpo_crudo, cuerpo_texto = _cuerpo_de_mensaje(mensaje)
            remitente_mail = email.utils.parseaddr(mensaje["From"] or "")[1] or (mensaje["From"] or "")

            mails.append(
                {
                    "message_id": message_id,
                    "remitente": remitente_mail,
                    "asunto": str(mensaje["Subject"] or "").strip() or None,
                    "recibido_el": recibido_el or datetime.now(timezone.utc),
                    "cuerpo_crudo": cuerpo_crudo,
                    "cuerpo_texto": cuerpo_texto,
                }
            )
        return {"total_desde": total_desde, "mails": mails}
    finally:
        try:
            conexion.logout()
        except Exception:
            pass
