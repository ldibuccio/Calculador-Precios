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
PROMPT_ENDOSO = """
Estás leyendo la captura de pantalla de un HOME BANKING argentino con una
operación de ECHEQ ("Operación pendiente de firma" o parecida). Puede ser un
ENDOSO (a quién se le endosan los cheques y cuáles) o un DEPÓSITO (en qué
cuenta propia se depositan: dice "Cuenta de Depósito").

Devolvé ÚNICAMENTE un JSON con este formato exacto:
{"tipo": "endoso" o "deposito", "cuenta_deposito": "texto o null",
 "proveedor_cuit": "11 dígitos o null", "proveedor_nombre": "texto o null",
 "cheques": [{"numero": "texto", "fecha_pago": "AAAA-MM-DD o null",
              "importe": número o null, "emisor": "texto o null"}]}

- Si la captura dice "Cuenta de Depósito", es un DEPÓSITO: "tipo" va
  "deposito", "cuenta_deposito" la cuenta tal como aparece (por ejemplo
  "CC$ 191-220-000247/7") y el proveedor va null.
- Si es un endoso, "cuenta_deposito" va null y "proveedor_cuit" y
  "proveedor_nombre" son los del BENEFICIARIO del endoso (a quien se le
  entregan los cheques), no los del que firma la operación.
- Un objeto por cheque endosado. "numero" tal como aparece (el número o el ID
  del ECHEQ), sin espacios. "emisor" es quien libró el cheque (razón social).
- "importe" en pesos, con punto decimal y sin separador de miles.
- Si un dato no se lee, va null. No inventes.
"""


def extraer_endoso(imagen: bytes) -> dict:
    """{"tipo", "cuenta_deposito", "proveedor_cuit", "proveedor_nombre",
    "cheques": [...]} de UNA captura (endoso o depósito)."""
    respuesta = _llamar_api_claude_multi_imagen([imagen], prompt=PROMPT_ENDOSO, max_tokens=MAX_TOKENS_CHEQUES)
    return _parsear_json_de_la_respuesta(respuesta)
