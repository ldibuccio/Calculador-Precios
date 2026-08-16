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
- El campo "articulo" tiene que ser el texto COMPLETO tal como está escrito,
  nunca una parte cortada de la palabra. Si el nombre está abreviado en la
  comanda (fuera de las abreviaciones de la lista de abajo), transcribir la
  abreviatura completa tal cual, no acortarla más ni inventar el resto.
- El campo "Señor:" de la comanda es el COMPRADOR, no el proveedor.
  Ignorarlo siempre.
- El proveedor sale del membrete o encabezado. Si no hay nombre, igual
  capturar el pabellón y el número de puesto.
- Pabellón: suele estar impreso en el membrete, debajo del nombre del
  proveedor, con la forma "Nave N - Puesto M" o "Libre N - Puestos M". "Nave",
  "Pabellón", "Pabellon" o "Pab" + número = "tipo_pabellon": "nave". "Libre" +
  número = "tipo_pabellon": "libre". Si no se lee ninguno de los dos,
  "tipo_pabellon": null. "numero_pabellon" es solo el número (sin la palabra
  "Nave"/"Pabellón"/"Libre"), y "puesto" es solo el número de puesto. No
  agregar ceros ni armar ningún código: solo separar estos tres datos tal
  cual están escritos.
- Si el membrete dice "Puestos M y P" (varios puestos para el mismo
  proveedor, ej. "Puestos 4 y 6"), poner en "puesto" solo el PRIMER número
  (ej. "4"), nunca los dos juntos ni mezclados.
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

MAX_TOKENS_LISTADO_CONSOLIDADO = 16384

PROMPT_LISTADO_CONSOLIDADO = """
Estás leyendo la foto de una planilla de compras CONSOLIDADA de un
distribuidor mayorista de frutas y verduras: una sola hoja con muchos
artículos de VARIOS proveedores mezclados (a diferencia de una comanda
normal, que es de un solo proveedor). Tu trabajo es extraer los datos
crudos tal como están escritos, renglón por renglón, sin hacer ninguna
cuenta ni interpretación de costos, y SIN agrupar vos por proveedor — eso
lo hace el sistema después.

Devolvé ÚNICAMENTE un JSON con este formato exacto:

{
  "renglones": [
    {
      "es_idem": true|false,
      "proveedor_texto": "...",
      "codigo": "...",
      "articulo": "...",
      "cantidad": ...,
      "kg_x_bulto": ...,
      "importe": ...,
      "nota_margen": "...",
      "confianza": "alta|baja"
    }
  ]
}

REGLAS DE EXTRACCIÓN:

- Un renglón del JSON por cada FILA de la planilla, en el mismo orden en
  que aparecen.
- COLUMNA PROVEEDOR: si la fila tiene el nombre del proveedor escrito,
  ponelo tal cual en "proveedor_texto" y "es_idem": false. Si la fila usa
  comillas ("), guiones (—, -), la palabra "ídem"/"idem", o cualquier otra
  marca que signifique "mismo proveedor que la fila de arriba", poné
  "es_idem": true y dejá "proveedor_texto" vacío (""). NUNCA copies vos el
  nombre del proveedor de la fila anterior — eso lo resuelve el sistema
  después con el flag "es_idem", no adivines ni arrastres el texto.
- "codigo": el código de producto de la fila si la planilla tiene esa
  columna, tal cual está escrito. Si no hay columna de código, dejalo
  vacío.
- "articulo": el texto COMPLETO tal como está escrito, nunca una parte
  cortada de la palabra. Si está abreviado (fuera de las abreviaciones de
  la lista de abajo), transcribí la abreviatura completa tal cual, no la
  acortes más ni inventes el resto.
- "kg_x_bulto": el contenido por bulto/cajón si la planilla lo tiene en su
  propia columna (ej. "18", "10kg"). Si la fila no tiene ese dato, null.
- "importe": el precio de la fila, si está. Si no está, null.
- NUNCA adivinar. Si un dato no se lee con seguridad, poner el texto
  "completar articulo", "completar cantidad" o "completar proveedor" según
  corresponda (en el campo que no se pudo leer), y marcar
  "confianza": "baja" en ese renglón. Mejor un campo marcado para revisar
  a mano que un dato inventado.
- Capturar SIEMPRE las anotaciones al margen junto al artículo (ej. "84",
  "x5", "4 kg"), en el campo "nota_margen".
- Abreviaciones conocidas: "M rojo"/"M.Rojo" = Morrón Rojo, "M verde" =
  Morrón Verde, "Red" = Manzana Red, "Granny" = Manzana Granny, "Pg" =
  Manzana PG.
- Si una fila está completamente vacía o es un encabezado/subtítulo de
  sección (no un artículo), no la incluyas en "renglones".

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


def _llamar_api_claude(
    imagen: bytes, media_type: str | None = None, prompt: str = PROMPT_EXTRACCION, max_tokens: int = 8192
) -> str:
    """Envía la imagen y un prompt de extracción a la API de Claude y devuelve el texto de la respuesta.

    prompt y max_tokens son configurables para reusar esta misma llamada
    con el prompt de listado consolidado (más renglones esperados, por eso
    necesita más espacio de respuesta que una comanda de un solo proveedor).
    """
    media_type = media_type or _detectar_media_type(imagen)
    api_key = _obtener_api_key()
    imagen_base64 = base64.standard_b64encode(imagen).decode("utf-8")

    cliente = anthropic.Anthropic(api_key=api_key)

    try:
        respuesta = cliente.messages.create(
            model=MODELO_LECTOR_COMANDAS,
            # Generoso a propósito: con el thinking activado y una comanda con
            # varios artículos, un límite chico corta la respuesta a mitad del
            # JSON (quedaba un "Unterminated string" al parsearlo).
            max_tokens=max_tokens,
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
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
    except anthropic.APIConnectionError as error:
        raise RuntimeError(f"No se pudo conectar con la API de Claude: {error}") from error
    except anthropic.APIStatusError as error:
        raise RuntimeError(f"La API de Claude devolvió un error ({error.status_code}): {error.message}") from error

    if respuesta.stop_reason == "max_tokens":
        raise RuntimeError(
            "La respuesta de la API se cortó por quedarse sin espacio (debe tener muchos artículos). "
            "Probá sacar la foto en partes, o avisale a Lionel para subir el límite."
        )

    return _extraer_texto_de_la_respuesta(respuesta.content)


def _extraer_texto_de_la_respuesta(bloques) -> str:
    """Concatena solo los bloques de texto de la respuesta, ignorando los de "thinking" u otro tipo.

    Cuando el thinking está activado, la API devuelve varios bloques de
    contenido (ThinkingBlock, TextBlock, ...) y no siempre en el mismo orden;
    solo los de texto tienen atributo .text.
    """
    textos = [bloque.text for bloque in bloques if getattr(bloque, "type", None) == "text"]

    if not textos:
        raise ValueError("La respuesta de la API no tiene ningún bloque de texto (¿solo vino texto de razonamiento?)")

    return "".join(textos)


def _parsear_json_de_la_respuesta(respuesta_texto: str) -> dict:
    """Limpia backticks si los hubiera y parsea el JSON de una respuesta de la API.

    Devuelve el JSON estructurado ya parseado (dict). Lanza ValueError si la
    respuesta no es un JSON válido o no tiene forma de objeto.
    """
    respuesta_limpia = _limpiar_respuesta_json(respuesta_texto)

    try:
        datos = json.loads(respuesta_limpia)
    except json.JSONDecodeError as error:
        raise ValueError(f"La respuesta de la API no es un JSON válido: {error}") from error

    if not isinstance(datos, dict):
        raise ValueError("La respuesta de la API debe ser un objeto JSON (dict)")

    return datos


def extraer_comanda(imagen: bytes, media_type: str | None = None) -> dict:
    """Extrae los datos crudos de una comanda (un solo proveedor) a partir de una foto."""
    respuesta_texto = _llamar_api_claude(imagen, media_type)
    return _parsear_json_de_la_respuesta(respuesta_texto)


def extraer_listado_consolidado(imagen: bytes, media_type: str | None = None) -> dict:
    """Extrae los renglones crudos de una planilla de compras consolidada (varios proveedores en una sola foto).

    Devuelve {"renglones": [...]}, todavía SIN agrupar por proveedor — eso
    lo hace agrupar_renglones_por_proveedor en core/matcheo_comanda.py, a
    partir del flag "es_idem" de cada renglón.
    """
    respuesta_texto = _llamar_api_claude(
        imagen, media_type, prompt=PROMPT_LISTADO_CONSOLIDADO, max_tokens=MAX_TOKENS_LISTADO_CONSOLIDADO
    )
    return _parsear_json_de_la_respuesta(respuesta_texto)
