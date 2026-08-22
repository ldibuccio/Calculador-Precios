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


class RespuestaCortada(RuntimeError):
    """La API cortó la respuesta por max_tokens: la salida no entró en el límite.

    Subclase de RuntimeError para que quien la trate como un error genérico
    siga andando; la distingue quien puede REINTENTAR con menos trabajo
    (la lectura de pedidos en tandas parte la tanda más chica y prueba de
    nuevo, sola).
    """

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

MAX_TOKENS_LISTADO_PRECIOS = 16384

PROMPT_LISTADO_PRECIOS = """
Estás leyendo un listado de precios de venta que un distribuidor mayorista
de frutas y verduras le pasa a un cliente puntual. Puede venir como foto,
página(s) de PDF, o el contenido de una planilla Excel ya convertido a
texto — no importa el formato ni el orden de las columnas, tu trabajo es
extraer cada artículo con su precio, tal como está escrito, sin hacer
ninguna cuenta ni interpretación.

Devolvé ÚNICAMENTE un JSON con este formato exacto:

{
  "items": [
    {"articulo": "...", "precio": ..., "confianza": "alta|baja"}
  ]
}

REGLAS DE EXTRACCIÓN:

- Un ítem por cada artículo con precio que aparezca, en el mismo orden en
  que aparecen.
- "articulo": el texto COMPLETO tal como está escrito, nunca una parte
  cortada de la palabra. Si está abreviado, transcribir la abreviatura tal
  cual, no acortarla más ni inventar el resto.
- "precio": el número tal como está, SIN el símbolo $ ni separadores de
  miles ni de decimales (ej. "$1.250,50" -> 1250.50, "1250" -> 1250). Si un
  renglón no tiene precio, no lo incluyas en la lista.
- NUNCA adivinar. Si el nombre o el precio de un renglón no se leen con
  seguridad, igual transcribí lo que se alcanza a leer y marcá
  "confianza": "baja" en ese ítem — mejor un dato marcado para revisar a
  mano que uno inventado.
- Si el archivo tiene varias páginas (PDF) u hojas (Excel), juntá todos
  los artículos encontrados en una sola lista "items".
- Ignorar encabezados, totales, fechas, subtítulos, o cualquier fila que
  no sea un artículo con su precio.

Respondé ÚNICAMENTE con el JSON, sin texto adicional antes ni después, y sin
comillas invertidas (backticks) ni bloques de código markdown.
"""

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

# Los textos que los prompts de arriba le ordenan a la IA devolver cuando NO
# pudo leer un campo, ya normalizados (minúsculas, sin acentos — la forma en
# que los deja normalizar_texto). NO son texto leído de ninguna comanda: no
# se aprende de ellos y tampoco sirven para sugerir un artículo. Si algún
# día se agrega un placeholder nuevo a los prompts, va también acá.
TEXTOS_PLACEHOLDER_LECTOR = frozenset(
    {
        "completar articulo",
        "completar cantidad",
        "completar importe",
        "completar proveedor",
    }
)


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


def _bloque_imagen(imagen: bytes, media_type: str | None = None) -> dict:
    """Arma un bloque de contenido "image" para el mensaje a la API, en base64."""
    media_type = media_type or _detectar_media_type(imagen)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(imagen).decode("utf-8"),
        },
    }


def _llamar_api_claude_con_contenido(contenido: list[dict], max_tokens: int, mensaje_corte: str | None = None) -> str:
    """Manda un bloque de contenido ya armado (imágenes y/o texto) a la API de Claude y devuelve el texto de la respuesta.

    Pieza compartida por las tres formas de leer un listado (una imagen,
    varias imágenes de un PDF página por página, o texto plano de un
    Excel) — todo lo que no depende de CÓMO se armó el contenido (llamar a
    la API, manejar errores de conexión/status, revisar que no se haya
    cortado por max_tokens, extraer el texto de la respuesta) vive acá una
    sola vez.
    """
    api_key = _obtener_api_key()
    cliente = anthropic.Anthropic(api_key=api_key)

    try:
        # Streaming, no porque haga falta mostrar nada en vivo, sino porque
        # con límites de salida grandes (el lector de pedidos usa 64K) una
        # llamada sin streaming choca contra el timeout HTTP del SDK. La
        # respuesta final es idéntica.
        with cliente.messages.stream(
            model=MODELO_LECTOR_COMANDAS,
            # Generoso a propósito: con el thinking activado y una comanda con
            # varios artículos, un límite chico corta la respuesta a mitad del
            # JSON (quedaba un "Unterminated string" al parsearlo).
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": contenido}],
        ) as stream:
            respuesta = stream.get_final_message()
    except anthropic.APIConnectionError as error:
        raise RuntimeError(f"No se pudo conectar con la API de Claude: {error}") from error
    except anthropic.APIStatusError as error:
        raise RuntimeError(f"La API de Claude devolvió un error ({error.status_code}): {error.message}") from error

    if respuesta.stop_reason == "max_tokens":
        raise RespuestaCortada(
            mensaje_corte
            or "La respuesta de la API se cortó por quedarse sin espacio (debe tener muchos artículos). "
            "Probá sacar la foto en partes, o avisale a Lionel para subir el límite."
        )

    return _extraer_texto_de_la_respuesta(respuesta.content)


def _llamar_api_claude(
    imagen: bytes, media_type: str | None = None, prompt: str = PROMPT_EXTRACCION, max_tokens: int = 8192
) -> str:
    """Envía UNA imagen y un prompt de extracción a la API de Claude y devuelve el texto de la respuesta.

    prompt y max_tokens son configurables para reusar esta misma llamada
    con el prompt de listado consolidado (más renglones esperados, por eso
    necesita más espacio de respuesta que una comanda de un solo proveedor).
    """
    contenido = [_bloque_imagen(imagen, media_type), {"type": "text", "text": prompt}]
    return _llamar_api_claude_con_contenido(contenido, max_tokens)


def _llamar_api_claude_multi_imagen(imagenes: list[bytes], prompt: str, max_tokens: int, mensaje_corte: str | None = None) -> str:
    """Envía VARIAS imágenes (ej. las páginas de un PDF) en un solo mensaje, con un único prompt.

    El media_type de cada imagen se detecta solo (todas se renderizan como
    JPEG, ver core/lector_archivos.py). Manda todas las páginas juntas para
    que la IA pueda ver el listado completo de una — no hay que juntar
    varias respuestas JSON parciales después.
    """
    contenido = [_bloque_imagen(imagen) for imagen in imagenes]
    contenido.append({"type": "text", "text": prompt})
    return _llamar_api_claude_con_contenido(contenido, max_tokens, mensaje_corte)


def _llamar_api_claude_texto(texto: str, prompt: str, max_tokens: int, mensaje_corte: str | None = None) -> str:
    """Envía texto plano (ej. el contenido de un Excel ya extraído) en vez de una imagen.

    Mismo contrato de salida que la lectura por imagen, pero sin tokens de
    imagen — más rápido y más barato para lo que ya viene como texto
    estructurado (no hace falta "ver" nada, solo interpretar).
    """
    contenido = [{"type": "text", "text": texto}, {"type": "text", "text": prompt}]
    return _llamar_api_claude_con_contenido(contenido, max_tokens, mensaje_corte)


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


def extraer_listado_precios_de_imagenes(imagenes: list[bytes]) -> dict:
    """Extrae {"items": [{"articulo", "precio", "confianza"}, ...]} a partir de una o varias imágenes.

    Usado para "Cargar Foto Precios" con una foto (una sola imagen) o un
    PDF (una imagen por página, todas juntas en el mismo pedido — ver
    core/lector_archivos.py para el renderizado de páginas).
    """
    respuesta_texto = _llamar_api_claude_multi_imagen(
        imagenes, prompt=PROMPT_LISTADO_PRECIOS, max_tokens=MAX_TOKENS_LISTADO_PRECIOS
    )
    return _parsear_json_de_la_respuesta(respuesta_texto)


def extraer_listado_precios_de_texto(texto: str) -> dict:
    """Extrae {"items": [{"articulo", "precio", "confianza"}, ...]} a partir de texto plano (ej. celdas de un Excel).

    Mismo contrato que extraer_listado_precios_de_imagenes — la pantalla de
    revisión no necesita saber de qué formato salió cada ítem.
    """
    respuesta_texto = _llamar_api_claude_texto(
        texto, prompt=PROMPT_LISTADO_PRECIOS, max_tokens=MAX_TOKENS_LISTADO_PRECIOS
    )
    return _parsear_json_de_la_respuesta(respuesta_texto)


# El pedido diario de Día son ~60 renglones con cantidades por 3
# sucursales — el JSON de salida es largo TODOS los días, no es un caso
# raro. 64K deja lugar de sobra (el modelo admite hasta 128K); la llamada
# va por streaming para que el límite grande no choque con el timeout HTTP.
MAX_TOKENS_PEDIDO_CLIENTE = 65536

MENSAJE_CORTE_PEDIDO = (
    "La lectura del pedido quedó cortada por el límite de espacio de la respuesta: "
    "el pedido es más largo de lo previsto. Avisale a Lionel para subir el límite del lector de pedidos."
)

PROMPT_PEDIDO_CLIENTE = """
Estás leyendo un MAIL DE PEDIDO que un cliente (un supermercado) le
manda a un distribuidor mayorista de frutas y verduras. Puede venir como
texto pegado o como una o varias capturas de pantalla del MISMO mail (el
mail es largo y no entra en una sola pantalla: las capturas son partes
consecutivas de la misma tabla — juntalas en un solo resultado, sin
repetir renglones si dos capturas se solapan).
El mail puede traer UNO o VARIOS bloques de empresa (el cliente a veces
le pide a más de una empresa en el mismo mail, con un encabezado por
bloque, ej. "9582 FRUTAMAX" y "11344 PALMALA"). Cada bloque tiene
columnas por sucursal/depósito (ej. VL, BZ, GR): cada sucursal trae
arriba su número de orden de compra y un total de bultos, y después un
renglón por artículo con el código del cliente, el nombre y la cantidad
pedida para cada sucursal (muchas celdas vienen vacías).

Devolvé ÚNICAMENTE un JSON con este formato exacto:

{
  "bloques": [
    {
      "empresa": "...",
      "sucursales": [
        {"sucursal": "...", "orden_compra": "...", "total_bultos": ...}
      ],
      "renglones": [
        {"codigo": "...", "descripcion": "...", "cantidades": {"VL": ..., "BZ": ...}, "confianza": "alta|baja"}
      ]
    }
  ]
}

REGLAS DE EXTRACCIÓN:

- Un bloque del JSON por cada bloque de empresa del mail. Si el mail no
  separa por empresa, devolvé un solo bloque con "empresa": "".
- "empresa": el encabezado del bloque tal cual está escrito (ej.
  "9582 FRUTAMAX"). Si no hay encabezado, "".
- "sucursales": una por columna de sucursal del bloque, con el nombre tal
  cual aparece (ej. "VL"), su número de orden de compra como TEXTO tal
  cual está escrito (puede tener ceros a la izquierda) y el total de
  bultos declarado como número. Si a una sucursal le falta la orden o el
  total, poné null en lo que falte.
- "renglones": uno por cada FILA de artículo, en el mismo orden en que
  aparecen. "codigo" y "descripcion" tal cual están escritos, completos,
  sin acortar ni inventar. "cantidades": un valor por sucursal usando los
  MISMOS nombres de sucursal que declaraste en "sucursales".
- OJO CON LAS CELDAS VACÍAS — es lo que más fácil se lee mal en la tabla:
  una celda vacía, o con un guion solo ("-"), significa que esa sucursal
  NO pide ese artículo. Va null, NUNCA un 0 inventado (y no transcribas el
  guion como si fuera un dato: "-" en cualquier celda es celda VACÍA). En
  el texto pegado las celdas vacías pueden venir marcadas así con "-",
  justamente para que cada fila traiga TODAS sus columnas y no haya que
  inferir posiciones. Y cuidá la alineación: cada cantidad
  pertenece a la columna de SU sucursal — si una fila tiene vacía la
  primera columna y número en la segunda, ese número es de la segunda
  sucursal, no corras cantidades de columna para llenar huecos.
- NUNCA adivinar. Si un dato no se lee con seguridad, transcribí lo que
  se alcanza a leer y marcá "confianza": "baja" en ese renglón.
- Ignorar saludos, firmas y texto que no sea parte del pedido — pero
  NUNCA saltees una fila de artículo, aunque esté rara: mejor un renglón
  con confianza baja que un renglón perdido.

Respondé ÚNICAMENTE con el JSON, sin texto adicional antes ni después, y sin
comillas invertidas (backticks) ni bloques de código markdown.
"""


# Un encabezado de bloque de empresa en el mail de Día: código y nombre en
# mayúsculas ("9582 FRUTAMAX", "11344 PALMALA"), sin tabuladores (las filas
# de productos vienen con las celdas separadas por tab).
_PATRON_ENCABEZADO_BLOQUE = re.compile(r"^\d{2,6}\s*[-–]?\s*[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s.\-]*$")


def recortar_bloque_de_empresa(texto: str, nombre_empresa: str) -> str:
    """Recorta del texto del mail SOLO el bloque de esta empresa, si se puede delimitar con confianza.

    El mail de Día trae los bloques de las dos empresas juntos: mandar a la
    IA solo el propio reduce la salida (y el tiempo de lectura) a la mitad.
    El corte es CONSERVADOR — arranca en la línea que nombra a esta empresa
    y termina en el próximo encabezado de bloque de OTRA empresa; si el
    nombre no aparece, ante la duda se devuelve el texto entero (nada del
    mail se puede perder por un recorte agresivo). La selección de bloque
    de siempre sigue corriendo después, como red de seguridad.
    """
    # Import local: matcheo_comanda importa de este módulo (los placeholders
    # del lector), así que importarlo arriba armaría un ciclo.
    from core.matcheo_comanda import normalizar_texto

    empresa = normalizar_texto(nombre_empresa)
    # Sin tabuladores no hay cómo distinguir una fila de producto de un
    # encabezado de bloque (en el texto tabulado los productos SIEMPRE
    # traen tabs): ante esa duda, no se recorta.
    if not empresa or "\t" not in texto:
        return texto

    lineas = texto.split("\n")
    inicio = None
    for indice, linea in enumerate(lineas):
        linea_limpia = linea.strip()
        # El arranque tiene que ser un encabezado de bloque DE VERDAD
        # ("9582 FRUTAMAX"), no una mención suelta de la empresa en el
        # saludo — arrancar en una mención cortaría cualquier cosa.
        if "\t" not in linea and _PATRON_ENCABEZADO_BLOQUE.match(linea_limpia) and empresa in normalizar_texto(linea_limpia):
            inicio = indice
            break
    if inicio is None:
        return texto

    fin = len(lineas)
    for indice in range(inicio + 1, len(lineas)):
        linea = lineas[indice].strip()
        if "\t" in lineas[indice] or not linea:
            continue
        if _PATRON_ENCABEZADO_BLOQUE.match(linea) and empresa not in normalizar_texto(linea):
            fin = indice
            break

    return "\n".join(lineas[inicio:fin]).strip("\n")


# Tope de filas de producto por llamada a la IA. La restricción real es la
# SALIDA (el JSON de cada renglón más el thinking): con el pedido real de
# ~60 renglones la salida pasó los 16K tokens (~270 por renglón), así que
# 100 renglones entran holgados en el límite de 64K. La cantidad de tandas
# sale del tamaño real del texto, no de un número fijo de tandas.
MAX_RENGLONES_POR_TANDA = 100


def _es_numero_de_celda(celda: str) -> bool:
    try:
        float(celda.replace(",", "."))
        return True
    except ValueError:
        return False


def _es_fila_de_titulos(linea: str) -> bool:
    """Una fila tabulada SIN ninguna celda numérica: los títulos de columna ("Código  Producto  VL  BZ  GR").

    Las filas de producto siempre traen algún número (el código o una
    cantidad) — por eso esto no confunde un producto con los títulos.
    """
    celdas = [celda.strip() for celda in linea.split("\t")]
    return not any(_es_numero_de_celda(celda) for celda in celdas if celda)


def _partir_en_tandas(texto: str, max_renglones: int) -> list[str]:
    """Parte el texto tabulado en tandas de tamaño parejo, repitiendo el encabezado en cada una.

    Cada tanda arranca con las líneas previas a la tabla (el encabezado del
    bloque de empresa) y la fila de títulos de columna si la hay — sin eso
    la IA no sabría de qué empresa es la tanda ni qué sucursal es cada
    columna. Un texto sin tabuladores no se puede partir con confianza:
    va entero en una sola tanda.
    """
    lineas = texto.split("\n")
    indice_primera_tab = next((i for i, linea in enumerate(lineas) if "\t" in linea), None)
    if indice_primera_tab is None:
        return [texto]

    fin_encabezado = indice_primera_tab
    if _es_fila_de_titulos(lineas[indice_primera_tab]):
        fin_encabezado += 1
    encabezado = lineas[:fin_encabezado]
    cuerpo = lineas[fin_encabezado:]

    filas = sum(1 for linea in cuerpo if "\t" in linea)
    if filas <= max_renglones:
        return [texto]

    # Tandas parejas: 250 filas con tope 100 son 3 tandas de ~84, no dos
    # de 100 y una colita de 50.
    cantidad_tandas = -(-filas // max_renglones)
    filas_por_tanda = -(-filas // cantidad_tandas)

    tandas: list[list[str]] = []
    actual: list[str] = []
    contadas = 0
    for linea in cuerpo:
        actual.append(linea)
        if "\t" in linea:
            contadas += 1
            if contadas == filas_por_tanda:
                tandas.append(actual)
                actual = []
                contadas = 0
    if actual:
        if any("\t" in linea for linea in actual) or not tandas:
            tandas.append(actual)
        else:
            # Las líneas sueltas del final (un saludo, una aclaración) van
            # con la última tanda: nada del mail queda sin mandar.
            tandas[-1].extend(actual)

    return ["\n".join(encabezado + tanda).strip("\n") for tanda in tandas]


def _combinar_lecturas(lecturas: list[dict]) -> dict:
    """Junta los resultados de varias tandas en un solo {"bloques": [...]}.

    Los bloques se combinan por empresa (todas las tandas llevan el mismo
    encabezado, así que el nombre coincide); los renglones se concatenan en
    el orden del mail y las sucursales se completan entre tandas (la OC y
    el total declarado suelen venir en una sola).
    """
    from core.matcheo_comanda import normalizar_texto

    combinados: dict = {}
    orden: list[str] = []
    for lectura in lecturas:
        for bloque in lectura.get("bloques") or []:
            clave = normalizar_texto(bloque.get("empresa") or "")
            if clave not in combinados:
                combinados[clave] = {"empresa": bloque.get("empresa"), "sucursales": [], "renglones": []}
                orden.append(clave)
            combinado = combinados[clave]

            por_sucursal = {normalizar_texto(s.get("sucursal") or ""): s for s in combinado["sucursales"]}
            for sucursal in bloque.get("sucursales") or []:
                clave_sucursal = normalizar_texto(sucursal.get("sucursal") or "")
                existente = por_sucursal.get(clave_sucursal)
                if existente is None:
                    copia = dict(sucursal)
                    combinado["sucursales"].append(copia)
                    por_sucursal[clave_sucursal] = copia
                else:
                    for campo in ("orden_compra", "total_bultos"):
                        if existente.get(campo) is None and sucursal.get(campo) is not None:
                            existente[campo] = sucursal[campo]

            combinado["renglones"].extend(bloque.get("renglones") or [])

    return {"bloques": [combinados[clave] for clave in orden]}


MARCADOR_CELDA_VACIA = "-"


def _marcar_celdas_vacias(texto: str) -> str:
    """Pone el marcador en cada celda vacía de las filas tabuladas.

    Refuerzo para el camino IA: con el marcador, toda fila trae TODAS sus
    columnas con un valor visible y no queda nada que inferir contando
    tabuladores consecutivos — que es exactamente donde una cantidad se
    cruza de sucursal. El prompt explica que "-" es celda vacía (null).
    """
    lineas = []
    for linea in texto.split("\n"):
        if "\t" in linea:
            celdas = [celda if celda.strip() else MARCADOR_CELDA_VACIA for celda in linea.split("\t")]
            lineas.append("\t".join(celdas))
        else:
            lineas.append(linea)
    return "\n".join(lineas)


def _leer_pedido_de_texto_directo(texto: str) -> dict:
    respuesta_texto = _llamar_api_claude_texto(
        texto, prompt=PROMPT_PEDIDO_CLIENTE, max_tokens=MAX_TOKENS_PEDIDO_CLIENTE,
        mensaje_corte=MENSAJE_CORTE_PEDIDO,
    )
    return _parsear_json_de_la_respuesta(respuesta_texto)


def _leer_tanda_con_reintento(texto_tanda: str, max_renglones: int) -> list[dict]:
    """Lee una tanda; si la respuesta se corta igual, la parte más chica y reintenta SOLA.

    Error recién cuando ni la tanda mínima (o un texto que no se puede
    partir) entra en el límite — ahí sí no hay nada más que probar solo.
    """
    try:
        return [_leer_pedido_de_texto_directo(texto_tanda)]
    except RespuestaCortada:
        mitad = max(1, max_renglones // 2)
        tandas_mas_chicas = _partir_en_tandas(texto_tanda, mitad)
        if len(tandas_mas_chicas) <= 1:
            raise
        lecturas: list[dict] = []
        for tanda in tandas_mas_chicas:
            lecturas.extend(_leer_tanda_con_reintento(tanda, mitad))
        return lecturas


def extraer_pedido_de_texto(texto: str) -> dict:
    """Extrae {"bloques": [...]} del texto pegado de un mail de pedido de un cliente.

    Cada bloque trae empresa (el encabezado, si hay), sucursales (con
    orden de compra y total de bultos declarado) y renglones con las
    cantidades por sucursal. Elegir QUÉ bloque es de esta empresa lo hace
    quien llama (app/main.py) — el desempate real es determinista, contra
    las fichas del cliente.

    Un pedido largo se lee en TANDAS (el tamaño sale de la cantidad real de
    renglones del texto) y los resultados se combinan; si una tanda se
    corta igual, se reintenta sola partiéndola más chica. 60 o 300
    renglones se leen igual, sin tocar nada.

    Este es el camino de RESPALDO: el principal es el parser por
    estructura (core/pedido_estructura.py), que no usa IA. Acá las celdas
    vacías van con marcador para que la IA no tenga que inferir columnas.
    """
    tandas = _partir_en_tandas(_marcar_celdas_vacias(texto), MAX_RENGLONES_POR_TANDA)
    lecturas: list[dict] = []
    for tanda in tandas:
        lecturas.extend(_leer_tanda_con_reintento(tanda, MAX_RENGLONES_POR_TANDA))
    if len(lecturas) == 1:
        return lecturas[0]
    return _combinar_lecturas(lecturas)


def extraer_pedido_de_imagenes(imagenes: list[bytes]) -> dict:
    """Extrae {"bloques": [...]} de una o varias capturas del MISMO mail de pedido.

    Mismo contrato que extraer_pedido_de_texto — la revisión no necesita
    saber de qué formato salió. Varias imágenes son partes consecutivas
    del mismo mail (no entra en una pantalla): van todas juntas en la
    misma llamada para que la IA las junte en un solo resultado.
    """
    respuesta_texto = _llamar_api_claude_multi_imagen(
        imagenes, prompt=PROMPT_PEDIDO_CLIENTE, max_tokens=MAX_TOKENS_PEDIDO_CLIENTE,
        mensaje_corte=MENSAJE_CORTE_PEDIDO,
    )
    return _parsear_json_de_la_respuesta(respuesta_texto)
