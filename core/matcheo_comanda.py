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

    tipo_pabellon tiene que ser "nave" o "libre" (ya normalizado por el lector).
    Se queda con el PRIMER número de numero_pabellon y de puesto (ignora "Pab.",
    espacios, etc.) — si el membrete dice "Puestos 4 y 6" (varios puestos para
    el mismo proveedor), toma solo el primero en vez de mezclar los dígitos.
    Si falta algún dato, no entran en 2 dígitos, o el tipo no es válido,
    devuelve None: no hay candidato de código para este caso.
    """
    if tipo_pabellon not in ("nave", "libre"):
        return None

    match_pabellon = re.search(r"\d+", str(numero_pabellon or ""))
    match_puesto = re.search(r"\d+", str(puesto or ""))
    if not match_pabellon or not match_puesto:
        return None

    digitos_pabellon = match_pabellon.group()
    digitos_puesto = match_puesto.group()

    numero_pabellon_int = int(digitos_pabellon)
    puesto_int = int(digitos_puesto)
    if numero_pabellon_int > 99 or puesto_int > 99:
        return None

    letra = "N" if tipo_pabellon == "nave" else "L"
    return f"{letra}{numero_pabellon_int:02d}P{puesto_int:02d}"


def adivinar_proveedor(proveedor_leido: dict, proveedores_existentes: list[dict]) -> dict | None:
    """Sugiere un proveedor a partir de lo leído en la comanda, o None si no hay ningún candidato.

    Orden de prioridad:
    1. Un proveedor YA EXISTENTE cuyo código de puesto matchea exacto con el
       que se arma a partir de nave/pabellón + puesto leídos.
    2. Un proveedor YA EXISTENTE con nombre parecido (por si el puesto no se
       leyó o cambió).
    3. Si nada de lo anterior encontró un proveedor existente, pero SÍ se
       pudo armar un código de puesto válido a partir de lo leído (proveedor
       nuevo, primera vez que se le compra), se sugiere ese código recién
       armado igual — "id": None marca que todavía no existe en la base,
       queda como propuesta editable, no una confirmación.
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

    nombre_leido_normalizado = normalizar_texto(proveedor_leido.get("nombre"))
    if nombre_leido_normalizado:
        mejor_proveedor = None
        mejor_similitud = 0.0
        for proveedor in proveedores_existentes:
            similitud = SequenceMatcher(None, nombre_leido_normalizado, normalizar_texto(proveedor["nombre"])).ratio()
            if similitud > mejor_similitud:
                mejor_similitud = similitud
                mejor_proveedor = proveedor

        if mejor_proveedor is not None and mejor_similitud >= UMBRAL_SIMILITUD_PROVEEDOR:
            return mejor_proveedor

    if codigo_candidato:
        return {"id": None, "codigo_puesto": codigo_candidato, "nombre": proveedor_leido.get("nombre") or ""}

    return None


def agrupar_renglones_por_proveedor(renglones: list[dict], proveedores_existentes: list[dict]) -> list[dict]:
    """Agrupa los renglones planos de un listado consolidado (varios proveedores en una sola foto) por proveedor.

    Cada renglón trae "proveedor_texto" (puede venir vacío) y "es_idem"
    (True si la fila usaba comillas/guiones/"ídem" para decir "mismo
    proveedor que la fila de arriba" — ver PROMPT_LISTADO_CONSOLIDADO en
    core/lector_comandas.py). Recorre en orden: si es_idem, el renglón se
    suma al grupo del proveedor_texto vigente (el de la última fila que sí
    traía nombre propio); si no, actualiza cuál es el proveedor vigente.

    Después funde entre sí los grupos que no quedaron contiguos pero son en
    realidad el mismo proveedor: por id (si ambos matchean, vía
    adivinar_proveedor, al mismo proveedor ya existente) o, si ninguno
    matchea nada existente, por texto normalizado idéntico (mismo
    proveedor nuevo mencionado dos veces en la planilla, en bloques
    separados, sin ídem entre medio).

    Devuelve una lista de {"proveedor_texto": str, "renglones": [...]}, en
    el orden de primera aparición de cada proveedor.
    """
    grupos_en_orden = []
    proveedor_vigente = ""

    for renglon in renglones:
        if not renglon.get("es_idem"):
            proveedor_vigente = (renglon.get("proveedor_texto") or "").strip()

        if grupos_en_orden and grupos_en_orden[-1]["proveedor_texto"] == proveedor_vigente:
            grupo = grupos_en_orden[-1]
        else:
            grupo = {"proveedor_texto": proveedor_vigente, "renglones": []}
            grupos_en_orden.append(grupo)

        grupo["renglones"].append(renglon)

    grupos_fundidos = []
    indice_por_proveedor_id = {}
    indice_por_texto_normalizado = {}
    for grupo in grupos_en_orden:
        proveedor_texto = grupo["proveedor_texto"]
        proveedor_sugerido = adivinar_proveedor({"nombre": proveedor_texto}, proveedores_existentes)
        proveedor_id = proveedor_sugerido["id"] if proveedor_sugerido else None
        texto_normalizado = normalizar_texto(proveedor_texto)

        indice_existente = indice_por_proveedor_id.get(proveedor_id) if proveedor_id is not None else None
        if indice_existente is None and texto_normalizado:
            indice_existente = indice_por_texto_normalizado.get(texto_normalizado)

        if indice_existente is not None:
            grupos_fundidos[indice_existente]["renglones"].extend(grupo["renglones"])
            continue

        grupos_fundidos.append({"proveedor_texto": proveedor_texto, "renglones": grupo["renglones"]})
        nuevo_indice = len(grupos_fundidos) - 1
        if proveedor_id is not None:
            indice_por_proveedor_id[proveedor_id] = nuevo_indice
        if texto_normalizado:
            indice_por_texto_normalizado[texto_normalizado] = nuevo_indice

    return grupos_fundidos


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
