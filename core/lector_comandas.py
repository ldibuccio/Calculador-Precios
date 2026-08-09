"""Lectura de comandas: extrae datos crudos de una foto usando la API de Claude.

Este módulo NO hace cálculos de costeo. Solo extrae y valida el JSON crudo
que devuelve la API; los cálculos siguen viviendo en motor_costeo.py.
"""

import base64
import json
import os
import re

import anthropic

MODELO_LECTOR_COMANDAS = "claude-sonnet-5"
ANTHROPIC_API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"

FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
FIRMA_JPEG = b"\xff\xd8\xff"

PROMPT_EXTRACCION = """
Estás leyendo la foto de una comanda de compra de un distribuidor mayorista
de frutas y verduras. Tu trabajo es extraer los datos crudos tal como están
escritos, sin hacer ninguna cuenta ni interpretación de costos.

Devolvé ÚNICAMENTE un JSON con este formato exacto:

{
  "proveedor": {"nombre": "...", "tipo_pabellon": "nave|libre|null", "numero_pabellon": "...", "puesto": "..."},
  "fecha": "...",
  "items": [
    {"articulo": "...", "cantidad": ..., "importe": ..., "sena": null, "nota_margen": "...", "confianza": "alta|baja"}
  ]
}

REGLAS DE EXTRACCIÓN:

- NUNCA adivinar. Si un dato no se lee con seguridad, poner el texto
  "completar artículo", "completar cantidad" o "completar importe" según
  corresponda, y marcar "confianza": "baja" en ese ítem.
- El campo "Señor:" de la comanda es el COMPRADOR, no el proveedor.
  Ignorarlo siempre.
- El proveedor sale del membrete o encabezado. Si no hay nombre, igual
  capturar el pabellón y el número de puesto.
- Pabellón: "Nave", "Pabellón", "Pabellon" o "Pab" + número = "tipo_pabellon":
  "nave". "Libre" + número = "tipo_pabellon": "libre". Si no se lee ninguno
  de los dos, "tipo_pabellon": null. "numero_pabellon" es solo el número
  (sin la palabra "Nave"/"Pabellón"/"Libre"), y "puesto" es solo el número
  de puesto. No agregar ceros ni armar ningún código: solo separar estos
  tres datos tal cual están escritos.
- Seña: por defecto null. Solo cargar si está escrita. La seña es por
  artículo, no por comanda.
- Ignorar la seña escrita al pie tipo "20 x 1000".
- Capturar SIEMPRE las anotaciones al margen junto al artículo (ej. "84",
  "x5", "4 kg"), en el campo "nota_margen". Son datos de unidades o kilaje.
- Hay tres formatos de comanda: en blanco, con lista pre-impresa donde se
  marca el renglón, y con membrete. En las de lista pre-impresa, solo
  extraer los renglones que tienen algo escrito.
- Abreviaciones: "M rojo"/"M.Rojo" = Morrón Rojo, "M verde" = Morrón Verde,
  "Red" = Manzana Red, "Granny" = Manzana Granny, "Pg" = Manzana PG.

Respondé ÚNICAMENTE con el JSON, sin texto adicional antes ni después, y sin
comillas invertidas (backticks) ni bloques de código markdown.
"""


def _detectar_media_type(imagen: bytes) -> str:
    """Detecta el media_type de una imagen (JPEG o PNG) a partir de su firma de bytes."""
    if imagen.startswith(FIRMA_PNG):
        return "image/png"
    if imagen.startswith(FIRMA_JPEG):
        return "image/jpeg"
    raise ValueError("No se pudo detectar el formato de la imagen: debe ser JPEG o PNG")


def _obtener_api_key() -> str:
    api_key = os.environ.get(ANTHROPIC_API_KEY_ENV_VAR)
    if not api_key:
        raise RuntimeError(
            f"Falta configurar la variable de entorno {ANTHROPIC_API_KEY_ENV_VAR} con la API key de Anthropic"
        )
    return api_key


def _limpiar_respuesta_json(texto: str) -> str:
    """Saca comillas invertidas o bloques de código markdown, por si la API los agrega igual."""
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*", "", texto)
    texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()


def _llamar_api_claude(imagen: bytes, media_type: str | None = None) -> str:
    """Envía la imagen y el prompt de extracción a la API de Claude y devuelve el texto de la respuesta."""
    media_type = media_type or _detectar_media_type(imagen)
    api_key = _obtener_api_key()
    imagen_base64 = base64.standard_b64encode(imagen).decode("utf-8")

    cliente = anthropic.Anthropic(api_key=api_key)

    try:
        respuesta = cliente.messages.create(
            model=MODELO_LECTOR_COMANDAS,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": imagen_base64,
                            },
                        },
                        {"type": "text", "text": PROMPT_EXTRACCION},
                    ],
                }
            ],
        )
    except anthropic.APIConnectionError as error:
        raise RuntimeError(f"No se pudo conectar con la API de Claude: {error}") from error
    except anthropic.APIStatusError as error:
        raise RuntimeError(f"La API de Claude devolvió un error ({error.status_code}): {error.message}") from error

    return respuesta.content[0].text


def extraer_comanda(imagen: bytes, media_type: str | None = None) -> dict:
    """Extrae los datos crudos de una comanda a partir de una foto.

    Devuelve el JSON estructurado ya parseado (dict). Lanza ValueError si la
    respuesta de la API no es un JSON válido o no tiene forma de objeto.
    """
    respuesta_texto = _llamar_api_claude(imagen, media_type)
    respuesta_limpia = _limpiar_respuesta_json(respuesta_texto)

    try:
        datos = json.loads(respuesta_limpia)
    except json.JSONDecodeError as error:
        raise ValueError(f"La respuesta de la API no es un JSON válido: {error}") from error

    if not isinstance(datos, dict):
        raise ValueError("La respuesta de la API debe ser un objeto JSON (dict)")

    return datos
