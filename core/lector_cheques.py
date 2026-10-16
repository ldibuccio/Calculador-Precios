"""CARTERA DE CHEQUES (dueño, 13/10): leer cheques de una foto o un archivo.

Igual que la carga de compras con foto: la IA LEE y la pantalla muestra lo
leído para corregir antes de guardar. Nada de lo leído se guarda solo.

Un archivo puede traer uno o varios cheques (la foto de un cheque físico, el
PDF de un ECHEQ, la boleta de un depósito con varios). El mismo lector sirve
para cargar (todos los datos) y para aplicar (con el número y el banco
alcanza para encontrarlos entre los que están en cartera).
"""
from core.lector_comandas import (
    _llamar_api_claude_multi_imagen,
    _llamar_api_claude_texto,
    _parsear_json_de_la_respuesta,
)

MAX_TOKENS_CHEQUES = 8192

PROMPT_CHEQUES = """
Estás leyendo uno o varios CHEQUES argentinos: la foto de un cheque físico
(frente o dorso), la captura o el PDF de un ECHEQ, o un comprobante (boleta
de depósito, listado de cheques) que trae varios.

Devolvé ÚNICAMENTE un JSON con este formato exacto:
{"fecha": "AAAA-MM-DD o null",
 "cheques": [{"numero": "texto", "banco": "texto", "fecha_pago": "AAAA-MM-DD o null",
              "importe": número o null, "cuit_librador": "11 dígitos o null",
              "tipo": "fisico" o "echeq", "librador": "texto o null"}]}

- "fecha" es la fecha del comprobante (el depósito, la entrega), si la hay.
- "numero" es el número del cheque tal como está impreso, sin espacios.
- "banco" es el nombre del banco que lo emite (ej. "Galicia", "Nación").
- "fecha_pago" es la fecha de pago o de cobro del cheque (la de pago
  diferido si es diferido, si no la de emisión).
- "importe" en pesos, con punto decimal y sin separador de miles.
- "cuit_librador" son los 11 números del CUIT de quien firma, sin guiones.
- "tipo" es "fisico" SOLO si se ve claramente un cheque de PAPEL (la foto de
  un cheque impreso, con su talón o su firma en tinta). Si no se puede saber,
  o es una captura, un PDF de home banking o un listado, va "echeq".
- Si un dato no se lee, va null. No inventes.
"""


def extraer_cheques_de_imagenes(imagenes: list[bytes]) -> dict:
    """{"fecha", "cheques": [...]} de una foto o de las páginas de un PDF."""
    respuesta = _llamar_api_claude_multi_imagen(imagenes, prompt=PROMPT_CHEQUES, max_tokens=MAX_TOKENS_CHEQUES)
    return _parsear_json_de_la_respuesta(respuesta)


def extraer_cheques_de_texto(texto: str) -> dict:
    """Mismo contrato, desde el texto de un Excel."""
    respuesta = _llamar_api_claude_texto(texto, prompt=PROMPT_CHEQUES, max_tokens=MAX_TOKENS_CHEQUES)
    return _parsear_json_de_la_respuesta(respuesta)


# ENDOSOS DE ECHEQ (dueño, 13/10): la captura de "Operación pendiente de
# firma" del home banking, con el proveedor a quien se endosa y sus cheques.
PROMPT_SALIDA = """
Estás leyendo un comprobante de cheques que SALIERON de una cartera. Puede
ser: la captura de un HOME BANKING argentino con una operación de ECHEQ
("Operación pendiente de firma" o parecida: un ENDOSO o un DEPÓSITO), una
BOLETA DE DEPÓSITO del banco, o un RECIBO de entrega de cheques. Puede tener
una o varias páginas: es UN solo comprobante.

Devolvé ÚNICAMENTE un JSON con este formato exacto:
{"tipo": "endoso", "deposito" o null, "cuenta_deposito": "texto o null",
 "proveedor_cuit": "11 dígitos o null", "proveedor_nombre": "texto o null",
 "cheques": [{"numero": "texto", "fecha_pago": "AAAA-MM-DD o null",
              "importe": número o null, "emisor": "texto o null"}]}

- Es un DEPÓSITO si dice en qué cuenta propia se depositan ("Cuenta de
  Depósito", una boleta de depósito): "tipo" va "deposito",
  "cuenta_deposito" la cuenta tal como aparece si se lee (por ejemplo
  "CC$ 191-220-000247/7") y el proveedor va null.
- Es un ENDOSO si los cheques se le dan a otro (un endoso, un recibo de
  entrega): "tipo" va "endoso", "cuenta_deposito" null, y "proveedor_cuit"
  y "proveedor_nombre" son los de QUIEN RECIBE los cheques (el beneficiario
  del endoso, el que firma el recibo), no los del que firma la operación.
- Si el comprobante no dice a dónde van los cheques, "tipo",
  "cuenta_deposito" y el proveedor van null.
- Un objeto por cheque. "numero" tal como aparece (el número o el ID del
  ECHEQ), sin espacios. "emisor" es quien libró el cheque (razón social).
- "importe" en pesos, con punto decimal y sin separador de miles.
- Si un dato no se lee, va null. No inventes.
"""


def extraer_salida_de_cheques(imagenes: list[bytes]) -> dict:
    """{"tipo", "cuenta_deposito", "proveedor_cuit", "proveedor_nombre",
    "cheques": [...]} de UN comprobante (sus páginas): endoso, depósito,
    boleta o recibo. "tipo" None si no dice a dónde van."""
    respuesta = _llamar_api_claude_multi_imagen(imagenes, prompt=PROMPT_SALIDA, max_tokens=MAX_TOKENS_CHEQUES)
    return _parsear_json_de_la_respuesta(respuesta)
