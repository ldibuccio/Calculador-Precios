"""Lectura de comandas: extrae datos crudos de una foto usando la API de Claude.

Este módulo NO hace cálculos de costeo. Solo extrae y valida el JSON crudo
que devuelve la API; los cálculos siguen viviendo en motor_costeo.py.
"""

import json

PROMPT_EXTRACCION = """
Estás leyendo la foto de una comanda de compra de un distribuidor mayorista
de frutas y verduras. Tu trabajo es extraer los datos crudos tal como están
escritos, sin hacer ninguna cuenta ni interpretación de costos.

Devolvé ÚNICAMENTE un JSON con este formato exacto:

{
  "proveedor": {"nombre": "...", "nave": "...", "puesto": "..."},
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
  capturar nave y número de puesto.
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

No agregues texto antes ni después del JSON.
"""


def _llamar_api_claude(imagen: bytes) -> str:
    """Punto de integración con la API de Claude (sin conectar todavía).

    Reemplazar esta función por la llamada real (envío de `imagen` junto con
    PROMPT_EXTRACCION a la API) cuando se conecte la API de verdad. Debe
    devolver el texto de la respuesta.
    """
    raise NotImplementedError("Todavía no está conectada la llamada real a la API de Claude")


def extraer_comanda(imagen: bytes) -> dict:
    """Extrae los datos crudos de una comanda a partir de una foto.

    Devuelve el JSON estructurado ya parseado (dict). Lanza ValueError si la
    respuesta de la API no es un JSON válido o no tiene forma de objeto.
    """
    respuesta_texto = _llamar_api_claude(imagen)

    try:
        datos = json.loads(respuesta_texto)
    except json.JSONDecodeError as error:
        raise ValueError(f"La respuesta de la API no es un JSON válido: {error}") from error

    if not isinstance(datos, dict):
        raise ValueError("La respuesta de la API debe ser un objeto JSON (dict)")

    return datos
