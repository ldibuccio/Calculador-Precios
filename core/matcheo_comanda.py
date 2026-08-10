"""Interpreta lo que leyó el lector de comandas contra los datos reales.

Todo acá es Python puro, sin tocar la base ni la API: recibe los datos ya
leídos de la foto y las listas de proveedores/artículos ya existentes (las
trae quien llame a estas funciones), y devuelve sugerencias. Nunca decide
por sí solo: todo lo que sugiere queda editable para que el comprador lo
confirme o corrija antes de guardar.
"""

import re
import unicodedata
from difflib import SequenceMatcher

UMBRAL_SIMILITUD_PROVEEDOR = 0.75
UMBRAL_SIMILITUD_ARTICULO = 0.7


def normalizar_texto(texto: str | None) -> str:
    """Minúsculas, sin acentos, sin espacios de más. Para comparar texto leído contra la base."""
    if not texto:
        return ""

    texto = texto.strip().lower()
    texto = "".join(
        caracter for caracter in unicodedata.normalize("NFD", texto) if unicodedata.category(caracter) != "Mn"
    )
    return re.sub(r"\s+", " ", texto)


def construir_codigo_puesto(tipo_pabellon: str | None, numero_pabellon, puesto) -> str | None:
    """Arma el código NNPNN (ej. N07P41) a partir de lo leído en la comanda.

    tipo_pabellon tiene que ser "nave" o "libre" (ya normalizado por el lector). Se
    quedan solo los dígitos de numero_pabellon y puesto (ignora "Pab.", espacios,
    etc.). Si falta algún dato, no entran en 2 dígitos, o el tipo no es válido,
    devuelve None: no hay candidato de código para este caso.
    """
    if tipo_pabellon not in ("nave", "libre"):
        return None

    digitos_pabellon = re.sub(r"\D", "", str(numero_pabellon or ""))
    digitos_puesto = re.sub(r"\D", "", str(puesto or ""))
    if not digitos_pabellon or not digitos_puesto:
        return None

    numero_pabellon_int = int(digitos_pabellon)
    puesto_int = int(digitos_puesto)
    if numero_pabellon_int > 99 or puesto_int > 99:
        return None

    letra = "N" if tipo_pabellon == "nave" else "L"
    return f"{letra}{numero_pabellon_int:02d}P{puesto_int:02d}"


def adivinar_proveedor(proveedor_leido: dict, proveedores_existentes: list[dict]) -> dict | None:
    """Sugiere un proveedor existente a partir de lo leído en la comanda, o None si no hay candidato.

    Primero intenta por código de puesto (nave/pabellón + puesto → NNPNN, match
    exacto). Si no arma un código o no encuentra ese código, intenta por
    parecido de nombre contra los proveedores existentes.
    """
    codigo_candidato = construir_codigo_puesto(
        proveedor_leido.get("tipo_pabellon"),
        proveedor_leido.get("numero_pabellon"),
        proveedor_leido.get("puesto"),
    )
    if codigo_candidato:
        for proveedor in proveedores_existentes:
            if proveedor["codigo_puesto"] == codigo_candidato:
                return proveedor

    nombre_leido = normalizar_texto(proveedor_leido.get("nombre"))
    if not nombre_leido:
        return None

    mejor_proveedor = None
    mejor_similitud = 0.0
    for proveedor in proveedores_existentes:
        similitud = SequenceMatcher(None, nombre_leido, normalizar_texto(proveedor["nombre"])).ratio()
        if similitud > mejor_similitud:
            mejor_similitud = similitud
            mejor_proveedor = proveedor

    if mejor_proveedor is not None and mejor_similitud >= UMBRAL_SIMILITUD_PROVEEDOR:
        return mejor_proveedor

    return None


def _mejor_candidato(texto_normalizado: str, candidatos: list[tuple[str, int]], umbral: float) -> int | None:
    """Busca el mejor candidato en (texto_candidato_normalizado, valor): exacto, por palabra completa, o por parecido.

    "Por palabra completa" cubre casos como "PG" adentro de "manzana pg": el
    texto leído es exactamente una de las palabras del candidato — pero solo
    si es una palabra que aparece en un único artículo (si "tomate" es
    palabra de "tomate redondo" Y de "tomate perita", es ambiguo y no
    adivina). El parecido (difflib) cubre abreviaturas parciales como
    "Manzana Granny" vs "Mzn Granny". Nunca devuelve nada por debajo del
    umbral: mejor dejarlo para que lo elija el comprador que sugerir un
    artículo equivocado.
    """
    for texto_candidato, valor in candidatos:
        if texto_candidato == texto_normalizado:
            return valor

    coincidencias_por_palabra = {
        valor for texto_candidato, valor in candidatos if texto_normalizado in texto_candidato.split()
    }
    if len(coincidencias_por_palabra) == 1:
        return next(iter(coincidencias_por_palabra))

    mejor_valor = None
    mejor_similitud = 0.0
    for texto_candidato, valor in candidatos:
        similitud = SequenceMatcher(None, texto_normalizado, texto_candidato).ratio()
        if similitud > mejor_similitud:
            mejor_similitud = similitud
            mejor_valor = valor

    if mejor_valor is not None and mejor_similitud >= umbral:
        return mejor_valor

    return None


def adivinar_articulo(
    texto_leido: str,
    aprendizaje: dict[str, int],
    articulos_existentes: list[dict],
    conversiones: list[dict],
) -> int | None:
    """Sugiere el articulo_id para un texto leído, o None si no hay candidato.

    Orden de prioridad:
    1. Lo aprendido para este proveedor puntual (match exacto: ya fue
       confirmado a mano una vez para este texto y este proveedor).
    2. Los alias ya cargados en conversion_articulos_cliente (ej. "MANZANA PG"
       para Man Gob) — de cualquier cliente, exacto o parecido.
    3. El nombre real del artículo en el catálogo — exacto o parecido.
    """
    texto_normalizado = normalizar_texto(texto_leido)
    if not texto_normalizado:
        return None

    if texto_normalizado in aprendizaje:
        return aprendizaje[texto_normalizado]

    candidatos_conversion = [
        (normalizar_texto(conversion["nombre_cliente"]), conversion["articulo_id"]) for conversion in conversiones
    ]
    resultado = _mejor_candidato(texto_normalizado, candidatos_conversion, UMBRAL_SIMILITUD_ARTICULO)
    if resultado is not None:
        return resultado

    candidatos_articulos = [(normalizar_texto(articulo["nombre"]), articulo["id"]) for articulo in articulos_existentes]
    return _mejor_candidato(texto_normalizado, candidatos_articulos, UMBRAL_SIMILITUD_ARTICULO)
