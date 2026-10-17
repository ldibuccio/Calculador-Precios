"""CONSULTAS POR TELEGRAM (dueño, 17/10): las llamadas a la API del bot.

Un bot por app (Frutamax y Palmala), con su token en TELEGRAM_BOT_TOKEN. Los
mensajes llegan por el webhook de la app, que Telegram firma con
TELEGRAM_WEBHOOK_SECRET (lo manda en un encabezado; si no coincide, no se
lee). Acá no se toca la base: solo se le habla a Telegram.
"""
import hmac
import os

import httpx

TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"
SECRETO_ENV_VAR = "TELEGRAM_WEBHOOK_SECRET"
ENCABEZADO_DEL_SECRETO = "X-Telegram-Bot-Api-Secret-Token"
LARGO_MAXIMO_DE_UN_MENSAJE = 4096
SEGUNDOS_POR_LLAMADA = 30


class TelegramNoAnda(RuntimeError):
    """Telegram no aceptó el pedido (o no se pudo llegar). El mensaje dice
    qué contestó, sin el token."""


def configurado() -> bool:
    return bool(os.environ.get(TOKEN_ENV_VAR)) and bool(os.environ.get(SECRETO_ENV_VAR))


def secreto_valido(recibido: str | None) -> bool:
    """El encabezado del webhook es el secreto de esta app. Sin secreto
    configurado no pasa nada."""
    esperado = os.environ.get(SECRETO_ENV_VAR) or ""
    return bool(esperado) and hmac.compare_digest(str(recibido or ""), esperado)


def _llamar(metodo: str, *, datos: dict | None = None, archivos: dict | None = None) -> dict:
    token = os.environ.get(TOKEN_ENV_VAR)
    if not token:
        raise TelegramNoAnda(f"falta la variable {TOKEN_ENV_VAR}")
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    try:
        if archivos:
            respuesta = httpx.post(url, data=datos or {}, files=archivos, timeout=SEGUNDOS_POR_LLAMADA)
        else:
            respuesta = httpx.post(url, json=datos or {}, timeout=SEGUNDOS_POR_LLAMADA)
    except httpx.HTTPError as error:
        raise TelegramNoAnda(f"no se pudo llegar a Telegram ({type(error).__name__})") from error
    try:
        cuerpo = respuesta.json()
    except ValueError:
        cuerpo = {}
    if respuesta.status_code >= 400 or not cuerpo.get("ok"):
        raise TelegramNoAnda(f"Telegram contestó {respuesta.status_code}: {cuerpo.get('description') or '?'}")
    return cuerpo.get("result") or {}


def cortar(texto: str, largo: int = LARGO_MAXIMO_DE_UN_MENSAJE) -> str:
    texto = texto or ""
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def enviar_mensaje(chat_id: int, texto: str, *, html: bool = False, boton: tuple[str, str] | None = None) -> dict:
    """Un mensaje; `boton` = (rótulo, dato que vuelve al apretarlo)."""
    datos = {"chat_id": chat_id, "text": cortar(texto) or "…"}
    if html:
        datos["parse_mode"] = "HTML"
    if boton:
        datos["reply_markup"] = {"inline_keyboard": [[{"text": boton[0], "callback_data": boton[1]}]]}
    return _llamar("sendMessage", datos=datos)


def enviar_escribiendo(chat_id: int) -> None:
    _llamar("sendChatAction", datos={"chat_id": chat_id, "action": "typing"})


def enviar_documento(chat_id: int, nombre: str, contenido: bytes, leyenda: str = "") -> dict:
    return _llamar("sendDocument", datos={"chat_id": str(chat_id), "caption": cortar(leyenda, 1024)},
                   archivos={"document": (nombre, contenido)})


def enviar_fotos(chat_id: int, fotos: list[dict]) -> None:
    """[{url, pdf, leyenda}]: las fotos juntas (hasta 10) y cada PDF aparte,
    como documento. Telegram las baja de la URL (firmada) por su cuenta."""
    imagenes = [f for f in fotos if not f.get("pdf")]
    for pdf in (f for f in fotos if f.get("pdf")):
        _llamar("sendDocument", datos={"chat_id": chat_id, "document": pdf["url"],
                                       "caption": cortar(pdf.get("leyenda") or "", 1024)})
    if len(imagenes) == 1:
        _llamar("sendPhoto", datos={"chat_id": chat_id, "photo": imagenes[0]["url"],
                                    "caption": cortar(imagenes[0].get("leyenda") or "", 1024)})
    elif imagenes:
        _llamar("sendMediaGroup", datos={"chat_id": chat_id, "media": [
            {"type": "photo", "media": f["url"], "caption": cortar(f.get("leyenda") or "", 1024)}
            for f in imagenes[:10]]})


def contestar_boton(callback_id: str, texto: str = "") -> None:
    _llamar("answerCallbackQuery", datos={"callback_query_id": callback_id, "text": cortar(texto, 200)})


def conectar_webhook(url: str) -> dict:
    """Le dice a Telegram a dónde mandar los mensajes, con el secreto. Solo
    mensajes y botones; los que esperaban se descartan."""
    secreto = os.environ.get(SECRETO_ENV_VAR)
    if not secreto:
        raise TelegramNoAnda(f"falta la variable {SECRETO_ENV_VAR}")
    return _llamar("setWebhook", datos={"url": url, "secret_token": secreto,
                                        "allowed_updates": ["message", "callback_query"],
                                        "drop_pending_updates": True})


def estado_del_webhook() -> dict:
    return _llamar("getWebhookInfo")


def datos_del_bot() -> dict:
    return _llamar("getMe")
