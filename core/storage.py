"""Subida y lectura de fotos de comandas en Supabase Storage (bucket privado "comandas").

Habla directo con la API REST de Supabase Storage por HTTP, usando httpx
(que el proyecto ya trae como dependencia para otra cosa), en vez de sumar
la librería oficial supabase-py: para subir bytes y pedir una URL firmada
alcanza con dos llamadas HTTP simples, y supabase-py arrastra varios
paquetes más (postgrest, gotrue, realtime, storage3) para un caso de uso
que acá es chico. Mismo criterio que core/lector_comandas.py, que tampoco
usa un SDK propio para lo que puede resolver con una llamada HTTP directa.

Este módulo NO toca la base ni el flujo de compras: es la pieza de hablar
con el Storage, aislada, para poder probarla sola (ver /storage-prueba en
app/main.py) antes de conectarla a nada real.
"""

import os
import re
import time
import unicodedata
import uuid

import httpx

SUPABASE_URL_ENV_VAR = "SUPABASE_URL"
SUPABASE_SERVICE_KEY_ENV_VAR = "SUPABASE_SERVICE_KEY"

BUCKET_COMANDAS = "comandas"
EXPIRACION_URL_FIRMADA_SEGUNDOS = 3600  # 1 hora
TIMEOUT_HTTP_SEGUNDOS = 30


def _obtener_credenciales() -> tuple[str, str]:
    """Lee SUPABASE_URL y SUPABASE_SERVICE_KEY del entorno, o lanza RuntimeError con un mensaje claro."""
    url = os.environ.get(SUPABASE_URL_ENV_VAR)
    if not url:
        raise RuntimeError(f"Falta configurar la variable de entorno {SUPABASE_URL_ENV_VAR}")

    service_key = os.environ.get(SUPABASE_SERVICE_KEY_ENV_VAR)
    if not service_key:
        raise RuntimeError(f"Falta configurar la variable de entorno {SUPABASE_SERVICE_KEY_ENV_VAR}")

    return url.rstrip("/"), service_key


def _sanear_nombre(texto: str) -> str:
    """Minúsculas, sin acentos, sin nada que no sea letra/número — para que el path del archivo quede legible."""
    sin_acentos = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")


def _armar_ruta_unica(nombre_archivo: str) -> str:
    """Arma un path único dentro del bucket: "aaaa-mm-dd/base-timestampms-random.jpg".

    "base" es nombre_archivo saneado (ej. "comanda" o el código de puesto
    del proveedor) — solo para que el path se pueda leer a simple vista, no
    es lo que garantiza la unicidad. Lo que garantiza que nunca se pisen
    dos subidas (aunque lleguen con la misma base en el mismo milisegundo,
    ej. dos comandas del mismo proveedor casi en simultáneo) es el
    timestamp en milisegundos + 8 caracteres random. La carpeta por fecha
    es solo para que el bucket quede ordenado y sea fácil de recorrer a
    mano desde el panel de Supabase si hace falta.
    """
    base = _sanear_nombre(nombre_archivo) or "comanda"
    fecha = time.strftime("%Y-%m-%d")
    timestamp_ms = int(time.time() * 1000)
    sufijo_random = uuid.uuid4().hex[:8]
    return f"{fecha}/{base}-{timestamp_ms}-{sufijo_random}.jpg"


def subir_foto_comanda(bytes_jpeg: bytes, nombre_archivo: str) -> str:
    """Sube una foto (ya comprimida a JPEG) al bucket privado "comandas" y devuelve la ruta con la que quedó guardada.

    nombre_archivo es una base descriptiva (ej. "comanda", o el código de
    puesto del proveedor) — la ruta final siempre es única, ver
    _armar_ruta_unica. Guardá la ruta devuelta (no hace falta guardar nada
    más) para poder pedir después una URL con obtener_url_foto(ruta).

    Lanza RuntimeError con un mensaje claro si:
    - Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en el entorno.
    - No se pudo conectar (sin internet, DNS, timeout, etc.).
    - Supabase Storage rechazó la subida (credencial inválida, bucket
      inexistente, etc.) — se incluye el status code y el mensaje que
      devolvió Supabase, para poder diagnosticar sin adivinar.
    """
    url_base, service_key = _obtener_credenciales()
    ruta = _armar_ruta_unica(nombre_archivo)

    try:
        respuesta = httpx.post(
            f"{url_base}/storage/v1/object/{BUCKET_COMANDAS}/{ruta}",
            content=bytes_jpeg,
            headers={
                "Authorization": f"Bearer {service_key}",
                "apikey": service_key,
                "Content-Type": "image/jpeg",
            },
            timeout=TIMEOUT_HTTP_SEGUNDOS,
        )
    except httpx.HTTPError as error:
        raise RuntimeError(f"No se pudo conectar con Supabase Storage: {error}") from error

    if respuesta.status_code >= 400:
        raise RuntimeError(f"Supabase Storage rechazó la subida ({respuesta.status_code}): {respuesta.text}")

    return ruta


def borrar_foto_comanda(ruta: str) -> None:
    """Borra un archivo del bucket privado "comandas" en Supabase Storage.

    Lanza RuntimeError con un mensaje claro en los mismos casos que
    subir_foto_comanda (faltan credenciales, sin conexión, Supabase
    rechaza el borrado). No decide si un fallo acá debe bloquear algo
    más — eso lo decide quien llama (ver app/main.py: borrar una foto
    nunca debe tumbar el borrado de la compra que la usaba).
    """
    url_base, service_key = _obtener_credenciales()

    try:
        respuesta = httpx.delete(
            f"{url_base}/storage/v1/object/{BUCKET_COMANDAS}/{ruta}",
            headers={
                "Authorization": f"Bearer {service_key}",
                "apikey": service_key,
            },
            timeout=TIMEOUT_HTTP_SEGUNDOS,
        )
    except httpx.HTTPError as error:
        raise RuntimeError(f"No se pudo conectar con Supabase Storage: {error}") from error

    if respuesta.status_code >= 400:
        raise RuntimeError(f"Supabase Storage rechazó el borrado ({respuesta.status_code}): {respuesta.text}")


def obtener_url_foto(ruta: str, expiracion_segundos: int = EXPIRACION_URL_FIRMADA_SEGUNDOS) -> str:
    """Genera una URL firmada temporal para ver una foto del bucket privado "comandas".

    El bucket es privado: no existe una URL pública fija para sus archivos.
    Hay que pedirle a Supabase que firme una de acceso por un rato
    (expiracion_segundos, por defecto 3600 = 1 hora). Pasado ese tiempo la
    URL deja de servir; para volver a ver la foto hace falta llamar de
    nuevo a esta función con la misma ruta (no hace falta re-subir nada).

    Lanza RuntimeError con un mensaje claro si faltan las credenciales, si
    no se pudo conectar, si Supabase no pudo firmar la URL (ruta
    inexistente, credencial inválida, etc.), o si la respuesta no vino con
    el campo de URL firmada esperado.
    """
    url_base, service_key = _obtener_credenciales()

    try:
        respuesta = httpx.post(
            f"{url_base}/storage/v1/object/sign/{BUCKET_COMANDAS}/{ruta}",
            json={"expiresIn": expiracion_segundos},
            headers={
                "Authorization": f"Bearer {service_key}",
                "apikey": service_key,
            },
            timeout=TIMEOUT_HTTP_SEGUNDOS,
        )
    except httpx.HTTPError as error:
        raise RuntimeError(f"No se pudo conectar con Supabase Storage: {error}") from error

    if respuesta.status_code >= 400:
        raise RuntimeError(f"Supabase Storage no pudo firmar la URL ({respuesta.status_code}): {respuesta.text}")

    datos = respuesta.json()
    ruta_firmada = datos.get("signedURL") or datos.get("signedUrl")
    if not ruta_firmada:
        raise RuntimeError(f"Supabase Storage no devolvió una URL firmada en la respuesta: {datos}")

    return f"{url_base}/storage/v1{ruta_firmada}"
