"""PALMALA CRUCES (dueño, 16/10): leer movimientos de una foto o un PDF.

Igual que Cuentas y la Cartera de cheques: la IA LEE y la pantalla muestra lo
leído para corregir antes de guardar. Nada se guarda solo.

Un archivo puede ser la foto de un cheque o un ECHEQ con que Palmala paga,
un comprobante (una transferencia, un recibo) o una hoja con varios
movimientos. Cada movimiento trae su cheque si es un pago con cheque. El
concepto que sugiere la IA tiene que ser uno de la lista: si no encaja
ninguno va null y se elige en la revisión.
"""
from core.lector_comandas import _llamar_api_claude_multi_imagen, _parsear_json_de_la_respuesta

MAX_TOKENS_PALMALA = 8192

PROMPT_PALMALA = """
Estás leyendo comprobantes de la cuenta corriente entre Frutamax y Palmala:
cheques o ECHEQ con que Palmala paga, transferencias, recibos, o una hoja
con movimientos escrita a mano.

Devolvé ÚNICAMENTE un JSON con este formato exacto:
{{"movimientos": [{{"fecha": "AAAA-MM-DD o null", "sentido": "debe" o "pago" o null,
                   "importe": número o null, "concepto": "uno de la lista o null",
                   "detalle": "texto o null",
                   "cheque": {{"numero": "texto", "banco": "texto", "fecha_pago": "AAAA-MM-DD o null",
                              "tipo": "fisico" o "echeq"}} o null}}]}}

- Un objeto por movimiento. Cada cheque es un movimiento.
- "sentido": "pago" si es un pago de Palmala (un cheque, una transferencia
  que hace Palmala); "debe" si es algo que Palmala queda debiendo. Si no se
  puede saber, null.
- "importe" positivo, con punto decimal y sin separador de miles.
- "concepto" tiene que ser EXACTAMENTE uno de esta lista, o null si ninguno
  encaja: {conceptos}
- "detalle" es lo que sirva para reconocerlo (quién firma el cheque, el
  número de operación).
- "cheque" va solo si es un cheque o un ECHEQ: "numero" tal como está
  impreso, sin espacios; "banco" el que lo emite (ej. "Galicia");
  "fecha_pago" la de pago o cobro; "tipo" es "fisico" SOLO si se ve
  claramente un cheque de PAPEL, si no "echeq".
- Si un dato no se lee, va null. No inventes.
"""


def extraer_movimientos_de_palmala(imagenes: list[bytes], *, conceptos: list[str]) -> dict:
    """{"movimientos": [...]} de una foto o de las páginas de un PDF."""
    prompt = PROMPT_PALMALA.format(conceptos="; ".join(conceptos) or "(ninguno)")
    respuesta = _llamar_api_claude_multi_imagen(imagenes, prompt=prompt, max_tokens=MAX_TOKENS_PALMALA)
    return _parsear_json_de_la_respuesta(respuesta)
