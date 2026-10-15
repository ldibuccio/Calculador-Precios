"""CUENTAS (dueño, 15/10): leer movimientos de una foto o un PDF.

Igual que Palmala Cruces y la Cartera de cheques: la IA LEE y la pantalla
muestra lo leído para corregir antes de guardar. Nada se guarda solo.

Un comprobante (un recibo, una transferencia, un ticket, una hoja de la caja
escrita a mano) puede traer uno o varios movimientos. El concepto que
sugiere la IA tiene que ser uno de los de la cuenta: se le pasa la lista, y
si no encaja ninguno va null y se elige en la revisión.
"""
from core.lector_comandas import _llamar_api_claude_multi_imagen, _parsear_json_de_la_respuesta

MAX_TOKENS_CUENTAS = 8192

PROMPT_COMPROBANTES = """
Estás leyendo uno o varios comprobantes de plata de una empresa argentina
para cargarlos en la cuenta "{cuenta}" ({tipo}): recibos, transferencias,
tickets, depósitos, o una hoja con movimientos escrita a mano.

Devolvé ÚNICAMENTE un JSON con este formato exacto:
{{"movimientos": [{{"fecha": "AAAA-MM-DD o null", "tipo": "ingreso" o "egreso" o null,
                   "importe": número o null, "quien": "texto o null",
                   "concepto": "uno de la lista o null", "detalle": "texto o null"}}]}}

- Un objeto por movimiento. "tipo": "ingreso" si la plata ENTRA a esta
  cuenta, "egreso" si SALE. Si no se puede saber, null.
- "importe" en pesos, positivo, con punto decimal y sin separador de miles.
- "quien" es la persona o empresa que paga o cobra (ej. "Mecafront").
- "concepto" tiene que ser EXACTAMENTE uno de esta lista, o null si ninguno
  encaja: {conceptos}
- "detalle" es lo que sirva para reconocerlo (número de factura, de
  operación). Si un dato no se lee, va null. No inventes.
"""


def extraer_movimientos_de_imagenes(imagenes: list[bytes], *, cuenta: str, tipo: str,
                                    conceptos: list[str]) -> dict:
    """{"movimientos": [...]} de una foto o de las páginas de un PDF."""
    prompt = PROMPT_COMPROBANTES.format(cuenta=cuenta, tipo=tipo, conceptos="; ".join(conceptos) or "(ninguno)")
    respuesta = _llamar_api_claude_multi_imagen(imagenes, prompt=prompt, max_tokens=MAX_TOKENS_CUENTAS)
    return _parsear_json_de_la_respuesta(respuesta)
