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


def adivinar_articulo(texto_leido: str, aprendizaje: dict[str, int], articulos_existentes: list[dict]) -> int | None:
    """Sugiere el articulo_id para un texto leído, o None si no hay candidato.

    Primero busca en lo aprendido para este proveedor (aprendizaje: texto
    normalizado → articulo_id). Si no está, busca un nombre EXACTO (normalizado,
    sin acentos/mayúsculas) contra el catálogo — nada de parecido: un artículo
    mal sugerido puede terminar costeando mal, así que ante la duda queda vacío
    para que lo elija el comprador.
    """
    texto_normalizado = normalizar_texto(texto_leido)
    if not texto_normalizado:
        return None

    if texto_normalizado in aprendizaje:
        return aprendizaje[texto_normalizado]

    for articulo in articulos_existentes:
        if normalizar_texto(articulo["nombre"]) == texto_normalizado:
            return articulo["id"]

    return None
