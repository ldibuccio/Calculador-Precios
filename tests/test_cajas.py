"""El stock de CAJAS NUESTRAS: las reglas puras, la cuenta derivada y la pantalla."""

import ast
import io
import os
import re
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import (
    COMPARADOR_DESDE_EL_CONTEO,
    _SQL_MOVIMIENTOS_DE_COLEGAS,
    _SQL_STOCK_DE_ENVASES,
    crear_movimiento_envase,
    cuentas_de_colegas,
)
from app.main import PUERTA_COMPRAS, app
from core.envases import (
    ORIGENES_DE_COLEGA,
    SIGNO_POR_TIPO_DE_GUIA,
    como_queda_la_cuenta,
    efecto_en_la_cuenta,
    hay_que_reponer,
    cajas_que_mueve_la_guia,
    envase_derivado_de_la_ficha,
)

cliente = TestClient(app, base_url="https://testserver")

ESQUEMA = io.open("db/esquema_completo.sql", encoding="utf-8").read()

FICHA_FIJA = {"envase_id": 7, "envase_variable": False}
# CON OTRO ENVASE que la fija, a propósito: con las dos en 7, una regla que
# devolviera el envase de la fija para las dos pasaría el test igual y no se
# vería. El id es el que tiene que distinguirlas.
FICHA_VARIABLE = {"envase_id": 9, "envase_variable": True}
FICHA_SIN_ENVASE = {"envase_id": None, "envase_variable": False}


# ---------------------------------------------------------------------------
# Las reglas puras
# ---------------------------------------------------------------------------

def test_el_envase_SALE_DE_LA_FICHA_aunque_sea_VARIABLE():
    """`envase_variable` NO decide cuál caja: decide si se usa una.

    Entre el 17 y el 18/09 este test afirmaba lo contrario —variable pedía
    preguntar— y esa afirmación sostuvo un selector en Reproceso que dejaba
    elegir una caja DISTINTA de la que la ficha declara. Era el guardián de
    ese bug: el arreglo lo rompe, y la primera lectura de ese rojo es "me
    equivoqué yo" (corolario 22).

    Lo que lo cierra está en `envases_por_unidad_de_venta`, que es la única
    otra cuenta que lee el flag: para el caso variable devuelve 0 o
    `1/contenido_ficha` —LA CAJA DE LA FICHA a la tasa de la ficha—, y no
    tiene ninguna rama que busque otro envase.
    """
    assert envase_derivado_de_la_ficha(FICHA_FIJA) == (True, 7, False)
    assert envase_derivado_de_la_ficha(FICHA_VARIABLE) == (True, 9, False)
    # Y LA ÚNICA QUE SIGUE PREGUNTANDO ES LA SIN FICHA. Su arreglo tampoco es
    # un selector de cajas: es asignarle la ficha, que vuelve a derivar.
    assert envase_derivado_de_la_ficha(None) == (None, None, True)


def test_el_flag_VARIABLE_no_aparece_en_la_regla_de_la_caja():
    """Y se afirma sobre el CUERPO, no sobre los tres casos de arriba.

    Un test de valores lo pasa igual una regla que lea el flag y devuelva lo
    mismo por casualidad con estos fixtures. Que la palabra no esté es lo
    único que dice que el flag salió del camino.
    """
    fuente = io.open("core/envases.py", encoding="utf-8").read()
    cuerpo = fuente.split("def envase_derivado_de_la_ficha")[1].split("\ndef ")[0]
    codigo = cuerpo.split('"""', 2)[2]
    assert "envase_variable" not in codigo, (
        "la caja sale de la ficha: el flag decide si se usa una, no cuál"
    )


def test_una_ficha_SIN_ENVASE_no_es_un_hueco_es_envase_perdido():
    # Manzana, pera, arándano: salen en el cajón del proveedor y no hay caja
    # nuestra que contar. Eso es una respuesta, no un dato que falta — por eso
    # NO pide preguntar.
    assert envase_derivado_de_la_ficha(FICHA_SIN_ENVASE) == (False, None, False)


def test_la_guia_EN_ORIGEN_SUMA_donde_la_normal_resta():
    # La compra que llegó ya armada es una caja que ENTRA al depósito.
    assert cajas_que_mueve_la_guia("normal", 20, True) == -20
    assert cajas_que_mueve_la_guia("en_origen", 5, True) == 5
    # Las del corte ya estaban armadas antes de que esta cuenta empezara.
    assert cajas_que_mueve_la_guia("inicial", 77, True) == 0


def test_la_SEGUNDA_del_reproceso_NO_consume_caja_y_eso_es_una_DECISION():
    """Al reprocesar, la primera va en caja de Día y LA SEGUNDA QUEDA EN EL
    CAJÓN DEL PROVEEDOR. No lleva caja nuestra: no hay nada que descontar.

    ESTE TEST AFIRMABA LO CONTRARIO durante unas horas el 16/09, sobre un dato
    del galpón que el dueño dio vuelta el mismo día. Mientras tanto restaba
    80,97 bultos por trimestre de un stock del que nunca salieron —el stock
    BAJO y el aviso de reposición temprano— y era el guardián de ese bug.

    Se afirma POR LA FIRMA, como la merma: la función ni siquiera recibe
    `bultos_segunda`, así que el día que alguien la quiera volver a sumar
    tiene que cambiar la firma, y este test dice por qué no está. Un assert
    sobre el valor lo pasaría igual un parámetro ignorado.

    LA SEGUNDA QUE SÍ VA EN CAJA NUESTRA ES LA DEL RECHAZO —vuelve del súper
    en la caja en la que salió—, y ésa no pasa por esta función: vive en
    movimientos_stock y ya quedó descontada en la guía R que la armó.
    """
    import inspect

    parametros = inspect.signature(cajas_que_mueve_la_guia).parameters
    assert "bultos_segunda" not in parametros, (
        "volvió `bultos_segunda`: la segunda del reproceso sale en el cajón "
        "del proveedor, no en caja nuestra"
    )
    # Y el valor sigue saliendo solo de la primera, en las tres ramas.
    assert cajas_que_mueve_la_guia("normal", 30, True) == -30
    assert cajas_que_mueve_la_guia("en_origen", 30, True) == 30
    assert cajas_que_mueve_la_guia("inicial", 30, True) == 0


def test_la_MERMA_no_consume_caja_y_eso_es_una_DECISION():
    """Lo que se descarta se tira, no se pone en una caja para tirarlo.

    Se afirma en vez de dejarlo implícito: `cajas_que_mueve_la_guia` ni
    siquiera recibe la merma, así que el día que alguien decida que sí ocupa
    caja va a tener que cambiar la FIRMA — y este test dice por qué no está.
    """
    import inspect

    from core.envases import cajas_que_mueve_la_guia as fn

    assert "bultos_merma" not in inspect.signature(fn).parameters


def test_una_guia_SIN_DECLARAR_no_mueve_el_stock():
    # Y no es "no consumió": es "no sabemos", y se cuenta aparte.
    assert cajas_que_mueve_la_guia("normal", 20, None) == 0
    assert cajas_que_mueve_la_guia("normal", 20, False) == 0


def test_los_TRES_tipos_de_guia_del_CHECK_estan_nombrados_en_el_signo():
    """El conjunto ENCONTRADO contra el DECIDIDO, leído del esquema real.

    Un tipo nuevo tiene que hacer caer este test, no colarse valiendo cero
    por el `.get(tipo, 0)`.
    """
    check = re.search(r"reprocesos_tipo_check check \(tipo in \(([^)]+)\)\)", ESQUEMA)
    assert check, "no encontré el CHECK de reprocesos.tipo en el esquema"
    del_esquema = set(re.findall(r"'([a-z_]+)'", check.group(1)))
    assert del_esquema == set(SIGNO_POR_TIPO_DE_GUIA), (
        f"el esquema dice {sorted(del_esquema)} y core/envases.py {sorted(SIGNO_POR_TIPO_DE_GUIA)}"
    )


def test_los_CUATRO_origenes_declarados_del_CHECK_los_ofrece_la_pantalla():
    """Los que la base acepta son los que la pantalla puede mandar.

    Se lee del `.sql` y no se copia: copiada, la lista envejece en silencio.
    `conteo_inicial` no está en el select porque tiene su propio formulario,
    y por eso se lo descuenta acá a propósito en vez de aflojar el assert.

    MIRA LA PAGINA RENDERIZADA Y NO EL TEXTO DE LA PLANTILLA, desde el 17/09:
    las opciones de colega salen de un `{% for %}` sobre ORIGENES_DE_COLEGA,
    así que en el archivo dicen `{{ clave }}` y un regex sobre el texto no ve
    ninguna. Leída la respuesta, el test cubre además el camino entero —el
    mapa, el contexto de la ruta y la plantilla— en vez de solo lo que el
    archivo afirma. Es lo mismo que el `hidden` que el CSS desmiente: el
    archivo dice la intención y la página dice el efecto.
    """
    check = re.search(
        r"movimientos_envase_origen_check\s*\n?\s*check \(origen in \(([^)]+)\)\)", ESQUEMA)
    assert check, "no encontré el CHECK de movimientos_envase.origen"
    del_esquema = set(re.findall(r"'([a-z_]+)'", check.group(1)))
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    del_select = set(re.findall(r'<option value="([a-z_]+)"', marcado))
    assert del_select | {"conteo_inicial"} == del_esquema, (
        f"el esquema permite {sorted(del_esquema)} y la pantalla ofrece {sorted(del_select)}"
    )


# ---------------------------------------------------------------------------
# La cuenta derivada
# ---------------------------------------------------------------------------

def test_el_recorte_del_CONTEO_INICIAL_esta_escrito_UNA_sola_vez():
    """Las dos patas derivadas comparan contra la fecha del conteo inicial.

    ESCRITO A MANO EN CADA UNA SE SEPARAN, y el día que alguien pase a contar
    a la tarde va a corregir una y dejar dos: ahí las guías R de ese día se
    descuentan dos veces en una pata y una en las otras, sin descuadrar nada
    y sin que nada avise. Es la novena aparición de la asimetría del día del
    corte, y la única forma de que no haya una décima es que el criterio esté
    en UN lugar.

    Medido aparte, contra el esquema real con el caso plantado: con `>=` el
    stock da 226 y con `>` da 246 — la guía R del día del conteo. O sea que
    el recorte está puesto y no es decorativo.
    """
    assert COMPARADOR_DESDE_EL_CONTEO == ">="
    assert _SQL_STOCK_DE_ENVASES.count("{comp}") == 2
    # Y ninguna pata lo escribe a mano: el `{comp}` es el único comparador
    # contra `b.fecha_operacion` que hay en la consulta.
    assert not re.search(r"(>=|>)\s*b\.fecha_operacion", _SQL_STOCK_DE_ENVASES)


def test_la_cuenta_derivada_EXCLUYE_las_guias_INICIALES_y_las_sin_declarar():
    """Las columnas que la consulta PIDE, no el valor que devuelve un mock.

    Sin `lleva_caja_nuestra IS TRUE` la cuenta sumaría las guías sin declarar
    como si hubieran consumido cero, y el hueco desaparecería adentro del
    total. Sin el CASE por tipo, las 'inicial' —cajas que ya estaban armadas
    el día del corte— descontarían cajas que nunca se llenaron.
    """
    sql = _SQL_STOCK_DE_ENVASES
    assert "r.lleva_caja_nuestra IS TRUE" in sql
    assert "ELSE 0 END" in sql
    # Y NINGÚN RECHAZO SUMA. La pata `liberadas` le sumaba al stock las cajas
    # del rechazo a cajón grande; esa caja se tira (17/09), así que se fue con
    # la columna. El assert es del TEXTO por lo mismo que el de arriba: con un
    # mock la fila la entrega el fixture y el término de más llega igual, así
    # que ninguna pantalla puede ver que volvió.
    assert "destino_rechazo" not in sql and "reingreso_rechazo" not in sql


def test_la_guia_R_consume_SOLO_LA_PRIMERA_y_la_segunda_NO_esta_en_el_SQL():
    """La segunda del reproceso queda en el cajón del proveedor.

    EL MODO DE FALLA NO SE VE EN NINGUNA PANTALLA, y por eso el assert es del
    TEXTO y no del valor (corolario 65): con un mock la fila la entrega el
    fixture y el término de más llega igual. Sumando la segunda, el stock
    queda BAJO por 80,97 bultos por trimestre en Frutamax, el aviso de
    reposición llega temprano, y ninguna cuenta se descuadra — lo único que
    lo delata es el conteo físico, que es justamente lo que este módulo viene
    a ahorrar.

    LAS DOS MITADES HACEN FALTA: afirmar `r.bultos_primera` pasa igual con
    `(r.bultos_primera + r.bultos_segunda)` puesto, porque el fragmento está
    adentro. Lo que niega el término es la segunda línea.
    """
    sql = _SQL_STOCK_DE_ENVASES
    assert "WHEN 'en_origen' THEN  r.bultos_primera" in sql
    assert "WHEN 'normal'    THEN -r.bultos_primera" in sql
    # El texto de la consulta SIN sus comentarios: el de arriba nombra a
    # `bultos_segunda` justamente para explicar por qué no está (corolario 59).
    consulta = "\n".join(
        linea for linea in sql.splitlines() if not linea.strip().startswith("--")
    )
    assert "bultos_segunda" not in consulta, (
        "volvió la segunda al descuento de cajas: sale en el cajón del "
        "proveedor, no en caja nuestra"
    )
    # Y la MERMA no: lo que se descarta se tira, no se pone en una caja para
    # tirarlo. Es una decisión, así que se afirma — si algún día cambia, que
    # este test caiga y no que aparezca sumada sin que nadie lo note.
    assert "bultos_merma" not in sql


def cuerpo_de_la_pata(anclaje: str) -> str:
    """El cuerpo de UNA pata de _SQL_STOCK_DE_ENVASES, anclada con su sangría.

    ANCLADA EN LA SANGRIA Y NO EN EL NOMBRE PELADO: `guias` es sufijo de
    `esperando_guias`, así que un split por "guias AS (" devuelve el cuerpo de
    la OTRA pata y el assert termina mirando lo que no quiso. Es el corolario
    4 —calificar el assert para que solo pueda matchear lo que se quiso
    probar— dentro de una misma consulta.
    """
    return _SQL_STOCK_DE_ENVASES.split(anclaje)[1].split("\n    )")[0]


def test_el_stock_NO_es_una_columna_que_alguien_actualiza():
    """Que anular una guía R corrija el stock solo sale de esto, no de un trigger.

    Si el stock viviera en una columna, anular sería un segundo lugar del que
    acordarse. Acá la fila deja de cumplir `anulado_el IS NULL` y ya no está
    en la suma.

    Verificado contra el esquema real: anulando una guía R de 30 cajas el
    stock pasó de 226 a 256 sin tocar nada más.
    """
    # EL FILTRO SE BUSCA ADENTRO DE CADA PATA (corolario 4). Esto decía
    # `assert "anulado_el IS NULL" in _SQL_STOCK_DE_ENVASES` a secas, y la
    # consulta tiene CINCO tablas que llaman igual a esa columna: sacarle el
    # filtro a la pata de las guías dejaba el assert pasando contra el de otra
    # tabla. Medido con un canario: caían CERO tests, y una guía R anulada
    # habría seguido consumiendo cajas para siempre — que es exactamente lo
    # contrario de lo que este test promete en su título.
    #
    # Y BUSCARLO POR ALIAS TAMPOCO ALCANZA DESDE EL 17/09: `m` y `r` se repiten
    # en las patas de "lo que espera al conteo", así que un `in` sobre la
    # consulta entera vuelve a poder matchear por la de al lado.
    patas = {
        "WITH base AS (": "anulado_el IS NULL",
        "\n    declarados AS (": "m.anulado_el IS NULL",
        "\n    guias AS (": "r.anulado_el IS NULL",
        "\n    esperando_mov AS (": "m.anulado_el IS NULL",
        "\n    esperando_guias AS (": "r.anulado_el IS NULL",
    }
    for anclaje, filtro in patas.items():
        assert filtro in cuerpo_de_la_pata(anclaje), anclaje
    assert "origen = 'conteo_inicial' AND anulado_el IS NULL" in _SQL_STOCK_DE_ENVASES
    # El denominador: sin él, cuatro filtros y cinco pasan igual.
    assert _SQL_STOCK_DE_ENVASES.count("anulado_el IS NULL") == len(patas)
    assert "UPDATE" not in _SQL_STOCK_DE_ENVASES.upper().replace("FOR UPDATE", "")
    esquema_sin_comentarios = "\n".join(
        l for l in ESQUEMA.splitlines() if not l.strip().startswith("--"))
    assert "stock_de_cajas" not in esquema_sin_comentarios


def test_la_guia_R_ESCRIBE_el_envase_en_su_UNICO_insert():
    """El que falta, por definición, no nombra la columna (corolario 3).

    Los dos caminos que crean una guía R —la normal y la de la compra que
    vino armada— pasan por `_crear_reproceso`, así que la columna se escribe
    en un solo lugar. Este test exige que ese lugar la nombre: si alguien
    agrega un segundo INSERT, el conteo de abajo lo delata.
    """
    fuente = io.open("app/db.py", encoding="utf-8").read()
    # `\b` Y NO un split a secas: "INSERT INTO reprocesos" también matchea
    # `reprocesos_consumos`, que es otra tabla. Calificar el ancla para que
    # solo pueda matchear lo que se quiso probar (corolario 4).
    partes = re.split(r"INSERT INTO reprocesos\b(?!_)", fuente)[1:]
    bloques = [b.split("RETURNING")[0] for b in partes]
    # SON DOS, y este test las enumera a las dos a propósito: la primera
    # versión afirmaba que era UNA y falló, que es exactamente para lo que
    # está. El conjunto ENCONTRADO contra el DECIDIDO — si aparece un tercer
    # INSERT, esto cae y hay que decidir qué hace con el envase.
    assert len(bloques) == 2, f"hay {len(bloques)} INSERT INTO reprocesos y estaban decididos 2"
    con_envase = [b for b in bloques if "lleva_caja_nuestra" in b and "envase_id" in b]
    sin_envase = [b for b in bloques if b not in con_envase]
    assert len(con_envase) == 1, "el INSERT de la guía R normal/en origen tiene que escribir el envase"
    # El otro es el del STOCK INICIAL, y no lo lleva a propósito: son las
    # cajas que ya estaban armadas el día del corte, y la cuenta las ignora
    # por su tipo ('inicial' vale 0 en SIGNO_POR_TIPO_DE_GUIA). Escribirle un
    # envase diría que consumieron una caja que nadie llenó.
    assert len(sin_envase) == 1 and "'inicial'" in sin_envase[0]


def test_asignar_la_ficha_DESPUES_completa_el_envase():
    """El hueco de una guía sin asignar se cierra cuando aparece la ficha.

    Si el UPDATE tocara solo `ficha_id`, el hueco quedaría abierto para
    siempre sin que nada lo señale.
    """
    fuente = io.open("app/db.py", encoding="utf-8").read()
    arbol = ast.parse(fuente)
    funcion = next(n for n in ast.walk(arbol)
                   if isinstance(n, ast.FunctionDef) and n.name == "asignar_ficha_a_reproceso")
    cuerpo = ast.unparse(funcion)
    assert "lleva_caja_nuestra = %s" in cuerpo and "envase_id = %s" in cuerpo
    # Y lo resuelve con el MISMO helper que el alta, no con una condición propia.
    llamadas = [n for n in ast.walk(funcion)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_envase_de_esta_guia"]
    assert llamadas, "usa una regla propia en vez del helper que usa el alta"


# ---------------------------------------------------------------------------
# La pantalla
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _puerta_de_compras_abierta():
    """Estos tests cruzan la puerta como la cruza una persona: con la clave.

    HACE FALTA PARA LOS POST Y NO PARA LOS GET, y esa asimetría es de la
    puerta, no de acá: bajo /compras un GET se abre igual cuando la variable
    no está cargada —para que un deploy no trabe la consulta— y un POST
    contesta 503 diciendo qué falta. Sin esta fixture los tres tests de
    escritura daban 503 y el rojo se leía como "la ruta está mal".

    Es el mismo molde que la fixture de test_app.py. Copiarlo es lo correcto
    acá: lo que se comparte es el gesto de abrir la puerta, no una regla.
    """
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
        try:
            yield
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)


# LOS FIXTURES LLEVAN LAS ONCE COLUMNAS, como las devuelve la consulta. Un
# fixture al que le falta el campo que el arreglo toca convierte al test en
# guardián de lo viejo: en Jinja una clave que no está es Undefined y es
# FALSA, así que el aviso no se dibuja y el test pasa igual con la pantalla
# sin aviso.
UN_ENVASE_SIN_ARRANCAR = [{
    "id": 1, "nombre": "Caja Grande", "umbral_reposicion": 50, "desde": None,
    "contadas": None, "declaradas": 0, "por_guias": 0, "stock": None,
    "esperando_mov": 0, "esperando_guias": 0, "esperando_desde": None,
}]
UN_ENVASE_SIN_ARRANCAR_CON_COSAS_ESPERANDO = [{
    "id": 1, "nombre": "Caja Grande", "umbral_reposicion": 50, "desde": None,
    "contadas": None, "declaradas": 0, "por_guias": 0, "stock": None,
    "esperando_mov": 2, "esperando_guias": 1,
    "esperando_desde": date(2026, 9, 5),
}]
UN_ENVASE_BAJO = [{
    "id": 1, "nombre": "Caja Grande", "umbral_reposicion": 50, "desde": date(2026, 9, 10),
    "contadas": 100, "declaradas": -70, "por_guias": -20, "stock": 10,
    "esperando_mov": 0, "esperando_guias": 0, "esperando_desde": None,
}]

# El gasto en cajas viaja SIEMPRE, así que todas las pruebas de pantalla lo
# parchean. Y ese parche hace, él solo, de aserción de que `app.main` importa
# `gasto_en_cajas`: si el nombre no está, `mock.patch` levanta AttributeError
# antes de ejercitar una línea (corolario 51).
SIN_GASTO = {"desde": date(2026, 6, 18), "por_envase": [], "cajas": 0,
             "gasto": 0.0, "sin_costo": 0, "ultima": None}
SIN_PERDIDAS = {"desde": date(2026, 6, 18), "renglones": [], "cajas": 0,
                "pesos": 0.0, "ultimo": None}
CON_PERDIDAS = {
    "desde": date(2026, 6, 18),
    "renglones": [
        {"cliente": "EJEMPLO Super", "articulo": "Fruta Uno", "envase": "Caja Grande",
         "cajas": 35.0, "pesos": 56000.0, "rechazos": 4, "ultimo": date(2026, 9, 12)},
        {"cliente": "EJEMPLO Super", "articulo": "Fruta Dos", "envase": "Caja Chica",
         "cajas": 5.0, "pesos": 3250.0, "rechazos": 1, "ultimo": date(2026, 9, 3)},
    ],
    "cajas": 40.0, "pesos": 59250.0, "ultimo": date(2026, 9, 12),
}
CON_GASTO = {
    "desde": date(2026, 6, 18),
    "por_envase": [
        {"nombre": "Caja Grande", "cajas": 150, "gasto": 200000.0,
         "sin_costo": 0, "ultima": date(2026, 9, 10)},
        {"nombre": "Caja Chica", "cajas": 90, "gasto": 52000.0,
         "sin_costo": 1, "ultima": date(2026, 9, 12)},
    ],
    "cajas": 240, "gasto": 252000.0, "sin_costo": 1, "ultima": date(2026, 9, 12),
}


def test_sin_conteo_inicial_la_pantalla_NO_dice_cero():
    """Un cero ahí se leería como "no quedan cajas", que es lo contrario."""
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_SIN_ARRANCAR), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "todavía sin conteo inicial" in marcado
    assert 'class="stock bajo"' not in marcado
    # Y ofrece arrancarla, que es lo único que se puede hacer con ese envase.
    assert 'action="/compras/cajas/conteo-inicial"' in marcado
    # SIN NADA ESPERANDO, EL AVISO NO SALE. Es la otra mitad del par: un aviso
    # que se dibuja siempre se ve igual de trabajador que uno que funciona, y
    # acá diría que hay movimientos invisibles donde no hay ninguno.
    assert "no se ven acá" not in marcado


def test_lo_que_YA_ESTA_CARGADO_y_no_se_ve_se_DICE_en_la_tarjeta_sin_conteo():
    """"Todavía sin conteo inicial" es verdadero y no alcanza.

    EL CASO: alguien da de alta un envase nuevo, compra doscientas cajas,
    entra a la pantalla y lee que la cuenta no arrancó. Sus doscientas están
    cargadas, bien cargadas, y no se ven en ningún lado — las tres patas del
    stock entran por `base`, así que sin conteo inicial no hay ni una fila.

    Es la pantalla vacía del backfill con otro disfraz: "no hay nada" y "hay
    cosas que no puedo mostrar" se dibujan exactamente igual. El aviso es lo
    único que las separa, y por eso dice el NÚMERO y la FECHA MÁS VIEJA — sin
    la fecha, "poné el conteo antes" no dice antes de qué.
    """
    with patch("app.main.stock_de_envases",
               return_value=UN_ENVASE_SIN_ARRANCAR_CON_COSAS_ESPERANDO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]

    assert "2 movimientos" in marcado
    # LAS GUIAS R VAN APARTE, y no sumadas a los movimientos: se cargan en
    # otra pantalla. Un solo "3 esperando" mandaría a buscar en la lista de
    # movimientos una guía R que nunca estuvo ahí.
    assert "1 guía R" in marcado
    assert "no se ven acá" in marcado
    assert "05/09/2026" in marcado
    # Y CERO ES UNA RESPUESTA VALIDA, dicho donde se decide qué tipear: sin
    # eso, el que tiene 200 esperando cuenta 200 y las suma dos veces.
    assert "Cero es una respuesta válida" in marcado


def test_la_REGLA_DE_LA_FECHA_esta_en_la_PANTALLA_y_no_solo_en_el_doc():
    """El error caro no se descuadra: el stock queda alto y nada avisa.

    Contar las 200 que ya llegaron Y fechar el conteo antes de esa compra las
    suma dos veces — el conteo las trae, y el recorte `>=` vuelve a traer la
    compra. No hay error, no hay hueco, y el aviso de reposición llega tarde
    para siempre.

    Un doc no lo ataja: el que arranca la cuenta está en esta pantalla y no
    va a ir a buscar nada. Por eso los tres casos van acá, y el que se
    equivoca va nombrado como lo que nunca va, no deducible de los otros dos.
    """
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_SIN_ARRANCAR), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]):
        respuesta = cliente.get("/compras/cajas")
    marcado = respuesta.text.split("</style>")[-1]

    assert 'class="regla-fecha"' in marcado
    assert "La fecha decide qué se suma y qué no" in marcado
    # Los TRES casos, y el tercero nombrado como el que nunca va.
    assert "quedan absorbidas" in marcado
    assert "contá cero" in marcado
    assert "Lo que nunca va" in marcado
    assert "se suman dos veces" in marcado
    # Y NO ESTA EN LETRA CHICA: es el texto que evita el error que no avisa.
    assert 'class="ayuda">La fecha decide' not in respuesta.text


def test_con_el_conteo_PUESTO_la_regla_de_la_fecha_YA_NO_ESTORBA():
    """La explicación vive en la rama que la necesita y en ninguna otra.

    Un envase con la cuenta andando no tiene nada que fechar, y dejarle la
    regla al lado sería repetir en cada tarjeta un párrafo que ya no aplica
    — que es cómo un texto útil se vuelve el que nadie lee.
    """
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]):
        respuesta = cliente.get("/compras/cajas")
    marcado = respuesta.text.split("</style>")[-1]

    assert 'class="regla-fecha"' not in marcado
    assert "no se ven acá" not in marcado


def test_la_pantalla_de_Cajas_es_SOLO_STOCK_y_no_cuelga_la_plata():
    """Contesta cuántas hay y con quién está la cuenta. Nada más (17/09).

    TRES BLOQUES SE FUERON y los tres por razones distintas: el aviso de las
    guías R sin caja declarada (una notificación va en Alertas), el gasto en
    cajas de los 90 días y lo que se llevaron los rechazos (los dos son plata
    y van en Gerencia).

    EL TEST PREGUNTA POR EL CONJUNTO, no por los tres de hoy: el `assert` de
    cada nombre es lo que impide que vuelvan de a uno, y lo que los junta es
    que ninguno contesta "cuántas cajas tengo". El día que alguien agregue un
    cuarto, este test no lo va a ver — pero el que lo agregue va a leer acá
    por qué los otros tres no están.

    Y VA CONTRA LOS NOMBRES DEL CONTEXTO además del texto visible: un `$` o un
    "gasto" pueden aparecer en prosa mañana; `perdidas.` y `gasto.` solo
    pueden ser un bloque cableado a esa cuenta.
    """
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]

    # 1. El aviso de las guías sin caja declarada.
    assert "no dicen en qué caja se armaron" not in marcado
    assert "no están descontadas" not in marcado
    # 2. El gasto en cajas.
    assert "Lo que se gastó en cajas" not in marcado
    # 3. Lo que se llevaron los rechazos.
    assert "Lo que se llevaron los rechazos" not in marcado
    # NI UN PESO EN TODA LA PANTALLA: es de existencias, no de plata.
    assert "$" not in marcado

    # Y LO QUE SI TIENE QUE ESTAR, porque un test que solo prohíbe lo pasa
    # igual una pantalla en blanco (el caso feliz del corolario 30).
    assert "Caja Grande" in marcado
    assert "Cuentas con colegas" in marcado


def test_la_RUTA_dejo_de_PEDIR_las_tres_cuentas_que_ya_no_muestra():
    """Sacar el bloque y dejar la consulta es pagar el viaje a la base de algo
    que nadie mira — y deja el cableado puesto, así que el próximo que lea la
    ruta va a creer que la pantalla todavía lo usa.

    SE PREGUNTA POR EL ARBOL Y NO POR EL TEXTO (corolario 59): los tres
    nombres están escritos en el docstring de la ruta, a propósito, para
    contar por qué no están. Un `in` sobre el fuente matchearía esa prosa y el
    test no podría fallar nunca — que es exactamente la forma que este archivo
    persigue.
    """
    import ast as _ast

    arbol = _ast.parse(io.open("app/main.py", encoding="utf-8").read())
    ruta = next(n for n in _ast.walk(arbol)
                if isinstance(n, _ast.FunctionDef) and n.name == "_renderizar_pantalla_cajas")
    llamadas = {n.func.id for n in _ast.walk(ruta)
                if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)}

    for nombre in ("gasto_en_cajas", "cajas_perdidas_por_rechazo",
                   "contar_guias_sin_declarar_el_envase"):
        assert nombre not in llamadas, f"la ruta sigue pidiendo {nombre}"
    # El control: las que SI tiene que pedir. Sin esto, un parseo que devuelva
    # el conjunto vacío pasa los tres asserts de arriba (corolario 47).
    assert {"stock_de_envases", "cuentas_de_colegas", "listar_colegas"} <= llamadas


def test_las_FUNCIONES_de_la_plata_siguen_ENTERAS_para_Gerencia():
    """Se sacaron de la PANTALLA, no del sistema.

    La diferencia decide el trabajo del día que Gerencia las pida: si además
    se hubieran borrado, mudarlas sería reescribir dos cuentas con sus
    ventanas, su valuación al costo del día de la compra y su orden por plata.
    Así es cablear una pantalla.

    Y ESTE TEST ES LA UNICA SEÑAL QUE QUEDA de que existen: sin ningún
    llamador, `gasto_en_cajas` y `cajas_perdidas_por_rechazo` son exactamente
    lo que el corolario 33 dice que se lee como "no se usa" y se borra.
    """
    from app.db import cajas_perdidas_por_rechazo, gasto_en_cajas

    assert callable(gasto_en_cajas)
    assert callable(cajas_perdidas_por_rechazo)


def test_debajo_del_umbral_la_pantalla_lo_MARCA():
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]):
        respuesta = cliente.get("/compras/cajas")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'class="stock bajo"' in marcado
    assert "hay que reponer" in marcado
    # Las TRES patas al lado del total: un número solo no se puede leer.
    assert "contadas el" in marcado and "declarado:" in marcado and "guías R" in marcado
    # Y NO HAY UNA CUARTA. Había una —"vueltas de un rechazo"— que mostraba la
    # pata `liberadas`: las cajas que devolvía un rechazo a cajón grande. Esa
    # caja se tira (17/09), así que la pata sumaba algo que no ocurre y se fue
    # con la columna. El assert de la ausencia vale acá y NO es del corolario
    # 68 —un test que defiende un hueco de pantalla—: esto no esconde un
    # camino que se pueda recorrer, dice que la cuenta tiene tres términos.
    assert "vueltas de un rechazo" not in marcado


def test_la_pantalla_vive_en_COMPRAS_y_la_barra_lo_dice():
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]):
        respuesta = cliente.get("/compras/cajas")
    # SOBRE EL DOCUMENTO ENTERO y no sobre `[-1]`: la barra se incluye desde
    # otra plantilla que trae su PROPIO `<style>`, así que el último
    # `</style>` del documento es el de ella y el corte se come la barra.
    # Es el corolario 50 —`split` falla por los dos lados— y el ancla es un
    # elemento que solo puede ser marcado, no una palabra suelta.
    assert 'href="/compras" aria-label="Volver atrás"' in respuesta.text


def test_una_cantidad_con_DECIMALES_no_entra():
    """Media caja no existe, y la regla sale de la misma función que la guía R."""
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.crear_movimiento_envase") as escribir:
        respuesta = cliente.post("/compras/cajas/movimiento",
                                 data={"envase_id": "1", "origen": "compra",
                                       "cantidad": "20.5", "fecha": "", "motivo": ""})
    assert respuesta.status_code == 400
    assert "decimales" in respuesta.text
    escribir.assert_not_called()


def test_el_PRESTAMO_lo_da_vuelta_el_SERVER_y_no_la_persona():
    """La pregunta es "cuántas le mandé", no "cuántas resto"."""
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.crear_movimiento_envase") as escribir:
        cliente.post("/compras/cajas/movimiento",
                     data={"envase_id": "1", "origen": "prestamo_al_puesto",
                           "cantidad": "30", "fecha": "2026-09-15", "motivo": ""},
                     follow_redirects=False)
    escribir.assert_called_once()
    assert escribir.call_args.args[2] == -30
    # Y la compra suma, con la misma pantalla y el mismo campo en positivo.
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.crear_movimiento_envase") as escribir:
        cliente.post("/compras/cajas/movimiento",
                     data={"envase_id": "1", "origen": "compra",
                           "cantidad": "200", "fecha": "2026-09-15", "motivo": ""},
                     follow_redirects=False)
    assert escribir.call_args.args[2] == 200


def test_el_umbral_VACIO_apaga_la_vigilancia_de_ese_envase():
    with patch("app.main.guardar_umbral_de_envase") as escribir:
        # `follow_redirects=False`: seguirlo llevaría de vuelta a la pantalla,
        # que sin parchear va a la base y devuelve 500 — un rojo que no habla
        # de lo que este test afirma.
        respuesta = cliente.post("/compras/cajas/umbral",
                                 data={"envase_id": "1", "umbral": ""},
                                 follow_redirects=False)
    assert respuesta.status_code == 303
    escribir.assert_called_once_with(1, None)


# ---------------------------------------------------------------------------
# La alerta de reposición: lo que convierte el umbral en una consecuencia
# ---------------------------------------------------------------------------

def test_el_rojo_de_la_tarjeta_y_la_ALERTA_contestan_con_LA_MISMA_funcion():
    """Escrita dos veces se separan, y ahí no hay forma de saber cuál manda.

    El canario mueve `hay_que_reponer` y exige que la PANTALLA lo siga: con
    el predicado invertido, la tarjeta tiene que dejar de marcar el rojo. Una
    condición propia en la ruta pasa este test igual, y por eso además se
    mira que la ruta llame a la función.
    """
    fuente = io.open("app/main.py", encoding="utf-8").read()
    arbol = ast.parse(fuente)
    funcion = next(n for n in ast.walk(arbol)
                   if isinstance(n, ast.FunctionDef) and n.name == "_renderizar_pantalla_cajas")
    llamadas = [n for n in ast.walk(funcion)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "hay_que_reponer"]
    assert llamadas, "la pantalla usa una condición propia en vez de la función compartida"
    # Y la de la alerta también: las dos, o no sirve de nada que exista.
    fuente_db = io.open("app/db.py", encoding="utf-8").read()
    arbol_db = ast.parse(fuente_db)
    reponer = next(n for n in ast.walk(arbol_db)
                   if isinstance(n, ast.FunctionDef) and n.name == "_envases_a_reponer")
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "hay_que_reponer" for n in ast.walk(reponer))


def test_SIN_CONTEO_INICIAL_no_es_hay_que_reponer():
    """Si no, la alerta nace disparando por todo el catálogo.

    `stock` en None es "la cuenta no arrancó", no "no quedan cajas". Tratarlo
    como cero lo pone debajo de cualquier umbral.
    """
    assert hay_que_reponer({"stock": None, "umbral_reposicion": 50}) is False
    # Sin umbral tampoco: ese envase no se vigila, y es una decisión.
    assert hay_que_reponer({"stock": 3, "umbral_reposicion": None}) is False
    # Y el caso que SÍ tiene que encontrar, para que el par esté completo.
    assert hay_que_reponer({"stock": 16, "umbral_reposicion": 50}) is True
    # El borde: igual al umbral NO dispara — "avisame cuando queden MENOS de".
    assert hay_que_reponer({"stock": 50, "umbral_reposicion": 50}) is False


def test_la_alerta_de_CAJAS_se_registra_con_LAMBDA_y_no_con_la_referencia():
    """El registro se arma al importar: una referencia congela el objeto.

    Parchearla después no la toca, y el test que recorre las veinte se va a la
    base de verdad. Ya pasó una vez con `unidades_que_difieren`.
    """
    fuente = io.open("app/main.py", encoding="utf-8").read()
    bloque = fuente.split('codigo="cajas_a_reponer"')[1].split("DefinicionAlerta(")[0]
    assert "contar=lambda:" in bloque
    assert "detallar=lambda:" in bloque


def test_la_alerta_manda_a_CAJAS_que_es_donde_se_repone():
    from app.main import ALERTAS

    alerta = next(a for a in ALERTAS if a.codigo == "cajas_a_reponer")
    assert alerta.modulos == ("compras",)
    # UN SOLO SECTOR, así que no necesita destinos_por_sector: la acción
    # (comprar cajas) vive en Compras y no se mueve.
    assert alerta.destinos_por_sector == {}
    assert alerta.url == "/compras/cajas"


def test_el_detalle_dice_CUANTAS_FALTAN_y_no_solo_cuales():
    """"3 envases por reponer" manda a la pantalla a hacer la resta."""
    from app.db import detallar_envases_a_reponer

    bajos = [
        {"id": 1, "nombre": "Caja Grande", "umbral_reposicion": 50, "stock": 16,
         "desde": date(2026, 9, 10), "contadas": 100, "declaradas": 0,
         "por_guias": 0},
        {"id": 2, "nombre": "Caja Chica", "umbral_reposicion": 20, "stock": 300,
         "desde": date(2026, 9, 10), "contadas": 300, "declaradas": 0,
         "por_guias": 0},
        {"id": 3, "nombre": "Sin arrancar", "umbral_reposicion": 99, "stock": None,
         "desde": None, "contadas": None, "declaradas": 0,
         "por_guias": 0},
    ]
    with patch("app.db.stock_de_envases", return_value=bajos):
        detalle = detallar_envases_a_reponer()

    # Solo la primera: la segunda está por encima y la tercera no arrancó.
    assert detalle["filas"] == [["Caja Grande", 16, 50, 34]]
    assert detalle["resumen"] == "1 envase debajo de su aviso"
    assert "Faltan" in detalle["columnas"]


def test_el_conteo_de_la_alerta_sale_de_las_MISMAS_filas_que_el_detalle():
    """Si no, el banner y la pantalla pueden contradecirse sin explicación."""
    from app.db import contar_envases_a_reponer, detallar_envases_a_reponer

    bajos = [
        {"id": 1, "nombre": "A", "umbral_reposicion": 50, "stock": 16, "desde": date(2026, 9, 10)},
        {"id": 2, "nombre": "B", "umbral_reposicion": 50, "stock": 1, "desde": date(2026, 9, 10)},
    ]
    with patch("app.db.stock_de_envases", return_value=bajos):
        assert contar_envases_a_reponer() == {"casos": 2, "mas_viejo": None}
        assert len(detallar_envases_a_reponer()["filas"]) == 2


# --- El gasto en cajas -------------------------------------------------------
#
# Hasta el 16/09 la plata de las cajas no estaba en ninguna pantalla: el envase
# se cobra adentro del precio sugerido y la Rentabilidad Real no lo toca, así
# que comprar cajas era una sorpresa. Esto es lo único que junta las cajas de
# `movimientos_envase` con el precio de `envases_costo_historial`.


def _cuerpo(respuesta) -> str:
    """El marcado, sin el CSS ni el <script> (corolario 50)."""
    import re

    marcado = respuesta.text.split("</style>")[-1]
    return re.sub(r"<script>.*?</script>", "", marcado, flags=re.S)


def test_el_gasto_se_valua_al_costo_DEL_DIA_DE_LA_COMPRA_y_eso_sale_del_SQL():
    """El valor lo entrega el mock; QUÉ pide la consulta solo se ve en el texto.

    Es el corolario 65: con `h.vigente_desde <= current_date` la consulta
    revalúa las compras viejas al precio de hoy —medido contra el esquema
    real, Caja Grande pasa de $200.000 a $240.000— y ningún test de pantalla
    lo puede ver, porque el número lo pone el fixture.
    """
    from app.db import _SQL_GASTO_EN_CAJAS

    sql = "\n".join(
        linea for linea in _SQL_GASTO_EN_CAJAS.splitlines()
        if not linea.strip().startswith("--")
    )
    assert "h.vigente_desde <= m.fecha_operacion" in sql, (
        "el costo dejó de ser el vigente a la fecha de la compra"
    )
    assert "current_date" not in sql.lower()
    # Y los dos filtros que deciden qué ES una compra. Medido con canarios
    # contra el esquema real: sin el de origen, Caja Grande pasa de 150 a 320
    # cajas; sin el de anuladas, a 1149.
    assert "m.origen = 'compra'" in sql
    assert "m.anulado_el IS NULL" in sql


# --- Las cajas que se llevaron los rechazos ---------------------------------


def test_las_TRES_listas_de_destinos_que_se_llevan_la_caja_dicen_lo_MISMO():
    """La pantalla de Cajas, la de Rentabilidad Real y la consulta a mano.

    Son tres escrituras de la misma regla y no pueden compartir código —una
    es SQL de la app, otra Python, la tercera un `.sql` que se pega en
    Supabase—. El `.sql` se LEE, no se copia: copiado envejece en silencio y
    el número que el dueño corre a mano deja de ser el que la pantalla
    muestra, que son justo los dos que se ponen uno al lado del otro.
    """
    import io
    import re

    from app.db import _SQL_CAJAS_PERDIDAS_POR_RECHAZO
    from core.costo_real import DESTINOS_QUE_SE_LLEVAN_LA_CAJA

    def destinos(texto):
        sin_comentarios = "\n".join(
            l for l in texto.splitlines() if not l.strip().startswith("--")
        )
        adentro = re.search(r"destino_rechazo IN \(([^)]*)\)", sin_comentarios, re.I)
        assert adentro is not None, "dejó de filtrar por destino_rechazo"
        return tuple(sorted(re.findall(r"'([a-z_]+)'", adentro.group(1))))

    sql_del_repo = io.open(
        "db/cajas_7_las_que_se_pierden_contra_las_que_salen.sql", encoding="utf-8"
    ).read()
    esperado = tuple(sorted(DESTINOS_QUE_SE_LLEVAN_LA_CAJA))

    assert destinos(_SQL_CAJAS_PERDIDAS_POR_RECHAZO) == esperado
    assert destinos(sql_del_repo) == esperado


def test_lo_que_la_CONSULTA_de_las_perdidas_pide_solo_se_ve_en_su_TEXTO():
    """Tres propiedades que ningún test de pantalla puede ver.

    El valor lo entrega el mock, así que el orden, el reloj del costo y el
    tipo de JOIN llegan iguales con la consulta rota (corolario 65). Los tres
    canarios daban CERO antes de este test.

    Y el ancla va SIN los comentarios: el docstring de la función nombra las
    tres cosas para explicarlas, así que un `in` sobre el texto entero
    matchea la prosa (corolario 59).
    """
    from app.db import _SQL_CAJAS_PERDIDAS_POR_RECHAZO

    sql = "\n".join(
        l for l in _SQL_CAJAS_PERDIDAS_POR_RECHAZO.splitlines()
        if not l.strip().startswith("--")
    )

    # 1. ORDENADA POR PLATA: es lo que la vuelve una lista de trabajo. Con
    #    cuatro artículos llevándose el 80%, por nombre habría que leerla
    #    entera para encontrar los dos que importan.
    assert "ORDER BY SUM(m.cantidad * c.costo) DESC" in sql

    # 2. EL COSTO VIGENTE A LA FECHA DEL RECHAZO, no el de hoy: una caja
    #    perdida en julio no se revalúa sola. Es el mismo reloj que
    #    `gasto_en_cajas`, y las dos se leen juntas en la misma pantalla.
    assert "h.vigente_desde <= m.fecha_operacion" in sql
    assert "current_date" not in sql.lower()

    # 3. `JOIN envases` Y NO `LEFT JOIN`: una ficha sin envase es envase
    #    perdido de origen y ahí no hay caja nuestra que perder. Con LEFT
    #    JOIN esas devoluciones entran con cajas en positivo y pesos en NULL
    #    — se lee como una fuga sin precio en vez de como lo que es.
    assert "JOIN envases e" in sql and "LEFT JOIN envases" not in sql


def test_lo_que_ESPERA_AL_CONTEO_se_cuenta_SIN_PASAR_POR_base():
    """Las otras tres patas entran por `base`, y por eso no pueden contarlo.

    ESE ES EL BUG QUE EL AVISO VIENE A TAPAR: `declarados` y `guias` hacen
    `JOIN base`, así que un envase sin conteo inicial no produce ni una fila
    y sus movimientos son invisibles. Si estas dos CTE copiaran ese join
    —que es lo que sale solo, porque están escritas al lado— contarían CERO
    exactamente en el único caso que les importa, y el aviso no saldría
    nunca. Un cero que no puede dar otra cosa (corolario 47).

    Y LA OTRA MITAD: el SELECT las apaga cuando el conteo SÍ está, para que
    la columna signifique una sola cosa. Sin eso, un envase con la cuenta
    andando devolvería sus movimientos como "esperando" y habría que mirar
    `desde` para saber si el número quiere decir algo.
    """
    for nombre in ("esperando_mov", "esperando_guias"):
        cuerpo = cuerpo_de_la_pata("\n    " + nombre + " AS (")
        assert "base" not in cuerpo, (
            f"{nombre} pasa por `base`: cuenta cero justo donde tiene que contar"
        )
        assert "GROUP BY" in cuerpo and "MIN(" in cuerpo

    # Las TRES columnas se apagan con el conteo puesto, y se apagan por el
    # MISMO hecho: que `base` no tenga fila para ese envase.
    final = _SQL_STOCK_DE_ENVASES.split("FROM envases e")[0]
    assert final.count("CASE WHEN b.envase_id IS NULL") == 3
    # Y la fecha es la MAS VIEJA DE LAS DOS, no la de una sola: el aviso dice
    # "fechá el conteo antes de ese día", y antes de la segunda no alcanza.
    assert "LEAST(em.desde, eg.desde)" in final


def test_los_NOMBRES_de_las_columnas_son_los_que_la_consulta_DEVUELVE():
    """El conjunto ENCONTRADO contra el DECIDIDO, leído del SELECT de verdad.

    EXISTE PORQUE HAY DOS LECTORES y uno direccionaba por índice. Al sacar la
    pata `liberadas` el 17/09 la consulta pasó de nueve columnas a ocho:
    `stock_de_envases` se actualizó y `crear_movimiento_envase` quedó leyendo
    `fila[8]`, así que TODO guardado reventaba con "tuple index out of range"
    — el conteo inicial incluido.

    Ningún grep lo habría encontrado: un lector por índice NO NOMBRA NINGUNA
    COLUMNA, así que buscar la que se saca no lo cruza nunca. Es el corolario
    3 y es la misma forma que el CSS que ubica por `nth-child`.

    Que este test caiga el día que alguien agregue o saque una columna sin
    tocar la tupla de nombres ES SU FUNCION, no una molestia.
    """
    from app.db import COLUMNAS_STOCK_DE_ENVASES

    select = _SQL_STOCK_DE_ENVASES.split("SELECT e.id")[1].split("FROM envases")[0]
    crudas = [c.strip() for c in re.split(r",(?![^()]*\))", "e.id" + select) if c.strip()]
    nombres = []
    for cruda in crudas:
        plana = " ".join(cruda.split())
        if " AS " in plana:
            nombres.append(plana.split(" AS ")[-1].strip())
        else:
            nombres.append(plana.split(".")[-1].strip())

    assert tuple(nombres) == COLUMNAS_STOCK_DE_ENVASES, (
        f"la consulta devuelve {nombres} y la tupla de nombres dice "
        f"{list(COLUMNAS_STOCK_DE_ENVASES)}"
    )


def test_guardar_un_movimiento_LEE_EL_STOCK_y_NO_revienta():
    """La foto de antes sale de la MISMA consulta, y hay que poder leerla.

    ES EL CASO QUE TENIA QUE PASAR, y por eso encontró lo que ninguna batería
    de rechazos podía: los tests del formulario parchean
    `crear_movimiento_envase`, así que nadie ejercitaba su cuerpo — la función
    estuvo rota en main sin un solo test en rojo.

    La fila que se le da tiene EXACTAMENTE las columnas que devuelve la
    consulta de hoy. Una fila inventada con una de más lo dejaría pasar, que
    es el fixture que no se parece a producción.
    """
    conexion = MagicMock()
    cursor = conexion.cursor.return_value.__enter__.return_value
    fila = (1, "Caja EJEMPLO Grande", 100, date(2026, 9, 10), 500, 0, 0, 500,
            0, 0, None)
    assert len(fila) == len(
        __import__("app.db", fromlist=["x"]).COLUMNAS_STOCK_DE_ENVASES
    ), "el fixture tiene que tener las columnas que la consulta devuelve, ni una más"
    cursor.fetchall.return_value = [fila]
    cursor.fetchone.return_value = (77,)

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert crear_movimiento_envase(1, "compra", 200, date(2026, 9, 17)) == 77

    insert = next(ll for ll in cursor.execute.call_args_list
                  if "INSERT INTO movimientos_envase" in ll.args[0])
    # 500 es la foto de ANTES, leída de la fila: si el lector se desalinea, acá
    # entra un 0 y el ajuste de mañana no se puede reconstruir contra nada.
    assert insert.args[1][5] == 500


# ---------------------------------------------------------------------------
# La cuenta con un colega
# ---------------------------------------------------------------------------

UN_ENVASE_BAJO_CON_DEUDA = [
    {"id": 1, "nombre": "Caja EJEMPLO Grande", "umbral_reposicion": 100,
     "desde": date(2026, 9, 10), "contadas": 500, "declaradas": -420,
     "por_guias": 0, "stock": 80},
]
CUENTA_CON_DOSCIENTAS = [
    {"colega_id": 3, "colega": "Colega EJEMPLO Uno", "movimientos": 2,
     "por_envase": [{"envase": "Caja EJEMPLO Grande", "neto": 200,
                     "lado": "me debe", "cuantas": 200}]},
]


def test_la_alerta_de_reposicion_MIRA_SOLO_EL_PISO_aunque_le_deban_doscientas():
    """El consolidado es información; el físico es el que dispara.

    Si te deben doscientas cajas NO LAS TENES: no podés salir a comprar menos
    porque alguien te las debe. El detonante de salir corriendo es lo que hay
    en el piso y nada más.

    SE CUMPLE POR CONSTRUCCION y no por acordarse: `cantidad` significa el
    efecto sobre EL PISO, así que una caja prestada ya está restada del stock
    y la cuenta se lee de otras columnas. Este test existe para que el día que
    alguien quiera "mejorar" el stock sumándole lo que le deben, se entere de
    que estaba decidido.
    """
    assert hay_que_reponer(UN_ENVASE_BAJO_CON_DEUDA[0]), (
        "80 cajas contra un umbral de 100 es reponer, le deban lo que le deban"
    )
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO_CON_DEUDA), \
         patch("app.main.cuentas_de_colegas", return_value=CUENTA_CON_DOSCIENTAS), \
         patch("app.main.listar_colegas", return_value=[{"id": 3, "nombre": "Colega EJEMPLO Uno", "activo": True}]):
        respuesta = cliente.get("/compras/cajas")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'class="stock bajo"' in marcado, (
        "con 200 en la cuenta a favor, el piso sigue estando bajo y tiene que marcarse"
    )
    # Y las 200 SE VEN, porque son información: lo que no hacen es apagar el rojo.
    assert "me debe" in marcado


def test_la_cuenta_del_colega_NO_lleva_el_recorte_del_conteo_inicial():
    """El físico lleva el recorte y la cuenta NO, y eso se afirma en los dos.

    La foto del piso ya refleja lo que se prestó antes de contarla, así que el
    físico tiene que saltear esos movimientos. La cuenta no: si le presté 200
    el mes pasado y conté el galpón hoy, el piso está bien sin esas 200 y el
    colega me las sigue debiendo.

    COPIAR ACA EL FILTRO DE LA PATA DE AL LADO ES LO NATURAL —está tres líneas
    más arriba— y borraría las deudas viejas EN SILENCIO. Sería la novena
    aparición de la asimetría del corte.

    EL CONTROL ES LA MITAD QUE IMPORTA: sin afirmar que el físico SI lo lleva,
    este test pasaría igual el día que alguien saque el recorte de los dos
    lados, que es el otro modo de romperlo.
    """
    cuenta = " ".join(_SQL_MOVIMIENTOS_DE_COLEGAS.split())
    assert "conteo_inicial" not in cuenta, (
        "la cuenta con el colega no mira el conteo inicial del piso"
    )
    assert "fecha_operacion >=" not in cuenta and "fecha_operacion >" not in cuenta

    fisico = " ".join(_SQL_STOCK_DE_ENVASES.split())
    assert "conteo_inicial" in fisico
    assert "fecha_operacion {comp} b.fecha_operacion" in fisico, (
        "el físico SI recorta por el conteo inicial: si esto deja de ser cierto, "
        "la asimetría se fue de los dos lados y este test dejó de significar algo"
    )


def test_una_caja_prestada_ANTES_del_conteo_sigue_en_la_cuenta():
    """El canario del corte, sobre la cuenta armada de verdad.

    El texto de la consulta dice que el recorte no está; esto mide que su
    ausencia CAMBIA EL NUMERO. Un piso que no mueve nada al romperlo es un
    piso que no está puesto.
    """
    viejo = {"colega_id": 3, "colega": "Colega EJEMPLO Uno", "envase_id": 1,
             "envase": "Caja EJEMPLO Grande", "origen": "colega_le_presto",
             "cantidad": -200, "fecha": date(2026, 8, 15), "motivo": None}
    nuevos = [
        {"colega_id": 3, "colega": "Colega EJEMPLO Uno", "envase_id": 1,
         "envase": "Caja EJEMPLO Grande", "origen": "colega_le_presto",
         "cantidad": -50, "fecha": date(2026, 9, 12), "motivo": None},
        {"colega_id": 3, "colega": "Colega EJEMPLO Uno", "envase_id": 1,
         "envase": "Caja EJEMPLO Grande", "origen": "colega_me_devuelve",
         "cantidad": 30, "fecha": date(2026, 9, 14), "motivo": None},
    ]
    colegas = [{"id": 3, "nombre": "Colega EJEMPLO Uno", "activo": True}]

    with patch("app.db.listar_colegas", return_value=colegas), \
         patch("app.db.movimientos_de_colegas", return_value=[viejo] + nuevos):
        con_el_viejo = cuentas_de_colegas()[0]["por_envase"][0]
    # El CANARIO: los mismos movimientos con el recorte del conteo puesto, o sea
    # sin el préstamo anterior al 10/09.
    with patch("app.db.listar_colegas", return_value=colegas), \
         patch("app.db.movimientos_de_colegas", return_value=nuevos):
        con_recorte = cuentas_de_colegas()[0]["por_envase"][0]

    assert con_el_viejo["neto"] == 220 and con_el_viejo["lado"] == "me debe"
    assert con_recorte["neto"] == 20, "el recorte se come las 200 de agosto"
    assert con_el_viejo["neto"] != con_recorte["neto"], (
        "si el número no se mueve, este test no está midiendo el recorte"
    )


def test_el_neto_NO_se_suma_entre_TIPOS_de_caja():
    """Te puede deber Grandes mientras vos le debés Chicas, y no se cancelan.

    Netear entre tipos diría que están a mano cuando hay dos conversaciones
    pendientes. Adentro de un tipo el neto sí es lo que se quiere ver.
    """
    movimientos = [
        {"colega_id": 3, "colega": "Colega EJEMPLO Uno", "envase_id": 1,
         "envase": "Caja EJEMPLO Grande", "origen": "colega_le_presto",
         "cantidad": -40, "fecha": date(2026, 9, 12), "motivo": None},
        {"colega_id": 3, "colega": "Colega EJEMPLO Uno", "envase_id": 2,
         "envase": "Caja EJEMPLO Chica", "origen": "colega_me_presta",
         "cantidad": 40, "fecha": date(2026, 9, 13), "motivo": None},
    ]
    with patch("app.db.listar_colegas",
               return_value=[{"id": 3, "nombre": "Colega EJEMPLO Uno", "activo": True}]), \
         patch("app.db.movimientos_de_colegas", return_value=movimientos):
        cuenta = cuentas_de_colegas()[0]

    assert len(cuenta["por_envase"]) == 2, "un renglón por tipo de caja, no uno solo"
    por_nombre = {p["envase"]: p for p in cuenta["por_envase"]}
    assert por_nombre["Caja EJEMPLO Grande"]["lado"] == "me debe"
    assert por_nombre["Caja EJEMPLO Chica"]["lado"] == "le debo"


def test_el_INSERT_de_un_movimiento_escribe_LAS_DOS_columnas_que_el_CHECK_ata():
    """La forma exacta del corolario 75, y por eso se mira el INSERT y no la firma.

    `movimientos_envase_colega_segun_origen` ata `colega_id` con `origen` en
    las DOS direcciones. Una guarda de coherencia con UNA SOLA MITAD escrita
    por el código no protege: RECHAZA TODO, y de un camino frío que nadie
    recorre hasta que alguien lo recorre. El 17/09 una así estuvo enterrada un
    día entero en las dos bases y la desactivó un drop en vez del uso.

    Y SE COMPARA LA TUPLA ENTERA, no los campos que este cambio tocó: que
    falle el día que alguien agregue una columna es su función. Un test de
    tres campos de siete no protege los que no mira.
    """
    conexion = MagicMock()
    cursor = conexion.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        (1, "Caja EJEMPLO Grande", 100, date(2026, 9, 10), 500, 0, 0, 500,
         0, 0, None)]
    cursor.fetchone.return_value = (77,)

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_envase(1, "colega_le_presto", -50, date(2026, 9, 17),
                                colega_id=3)

    insert = next(ll for ll in cursor.execute.call_args_list
                  if "INSERT INTO movimientos_envase" in ll.args[0])
    assert "colega_id" in insert.args[0], "la columna tiene que estar en el INSERT"
    assert insert.args[1] == (1, "colega_le_presto", -50, None,
                              date(2026, 9, 17), 500, 3)

    # Y el caso de al lado: sin colega, la columna viaja en NULL. Con solo el
    # caso de arriba, un INSERT que escribiera un 3 fijo pasaría igual.
    cursor.execute.reset_mock()
    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_envase(1, "compra", 200, date(2026, 9, 17))
    insert = next(ll for ll in cursor.execute.call_args_list
                  if "INSERT INTO movimientos_envase" in ll.args[0])
    assert insert.args[1][-1] is None


def test_los_CUATRO_origenes_de_colega_del_CHECK_estan_en_el_MAPA():
    """El conjunto ENCONTRADO contra el DECIDIDO, en los dos sentidos.

    La lista de orígenes de colega está escrita en TRES lugares del esquema
    —la lista de valores, el signo y la coherencia con `colega_id`— y en el
    mapa de `core/envases.py`. Recorrer solo el mapa confirmaría lo que ya
    sabíamos; comparar los conjuntos falla también cuando aparece uno que
    nadie decidió.

    LO QUE NO ENTRA ACA ES EL NETO, y es la mejor protección que tiene esta
    cuenta: `efecto_en_la_cuenta` es `-cantidad` y NO LEE EL ORIGEN, así que
    no puede separarse de ninguna de estas listas.
    """
    check = re.search(
        r"movimientos_envase_origen_check\s*\n?\s*check \(origen in \(([^)]+)\)\)", ESQUEMA)
    assert check, "no encontré el CHECK de movimientos_envase.origen"
    del_esquema = {v for v in re.findall(r"'([a-z_]+)'", check.group(1))
                   if v.startswith("colega_")}
    assert del_esquema == set(ORIGENES_DE_COLEGA), (
        f"el esquema dice {sorted(del_esquema)} y el mapa {sorted(ORIGENES_DE_COLEGA)}"
    )
    assert len(del_esquema) == 4, "son cuatro: prestar y devolver, para los dos lados"

    signo = re.search(r"movimientos_envase_signo_segun_origen(.{0,600}?)\),\n", ESQUEMA, re.S)
    coherencia = re.search(r"movimientos_envase_colega_segun_origen(.{0,400}?)\),\n", ESQUEMA, re.S)
    assert signo and coherencia
    for origen in del_esquema:
        assert origen in signo.group(1), f"{origen} no tiene signo declarado"
        assert origen in coherencia.group(1), f"{origen} no está en la guarda de colega_id"

    # Y cada uno lleva sus DOS rótulos y su signo del piso: repartidos en tres
    # mapas, el día que se agregue un origen alguno se va a olvidar.
    for origen, datos in ORIGENES_DE_COLEGA.items():
        assert datos["corto"] and datos["largo"], origen
        assert datos["piso"] in (-1, 1), origen


def test_la_pantalla_lista_UN_RENGLON_por_colega_y_SE_VE_que_se_puede_entrar():
    """Un camino que anda y no se ve es un camino que no existe.

    El corolario 68 salió de un link del color exacto del texto de al lado y
    sin subrayar: el marcado decía que se podía llegar y nadie llegaba. Acá el
    renglón del colega lleva borde, fondo propio y chevron, y eso se afirma —
    aunque lo único que lo prueba de verdad sea abrir el navegador.
    """
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=CUENTA_CON_DOSCIENTAS), \
         patch("app.main.listar_colegas", return_value=[{"id": 3, "nombre": "Colega EJEMPLO Uno", "activo": True}]):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert 'href="/compras/cajas/colega/3"' in marcado
    assert "Colega EJEMPLO Uno" in marcado
    assert "me debe" in marcado and "200" in marcado
    # Y el colega se puede elegir al cargar el movimiento.
    assert 'name="colega"' in marcado
    estilos = respuesta.text.split("</style>")[0]
    assert ".colega-fila" in estilos and "chevron" in estilos, (
        "el renglón tiene que verse tocable, no solo serlo"
    )
    # El `hidden` del campo del colega necesita SU regla: `.campo` es flex y le
    # gana al [hidden] del navegador. Sin esto el campo se ve siempre.
    assert ".campo[hidden]" in estilos


def test_el_detalle_de_la_cuenta_MUESTRA_lo_que_le_di_y_lo_que_me_dio_con_fechas():
    """Y sale de la MISMA consulta que el renglón, no de una propia."""
    movimientos = [
        {"id": 9, "colega_id": 3, "colega": "Colega EJEMPLO Uno", "envase_id": 1,
         "envase": "Caja EJEMPLO Grande", "origen": "colega_le_presto",
         "cantidad": -50, "fecha": date(2026, 9, 12), "motivo": None},
        {"id": 8, "colega_id": 3, "colega": "Colega EJEMPLO Uno", "envase_id": 1,
         "envase": "Caja EJEMPLO Grande", "origen": "colega_me_devuelve",
         "cantidad": 30, "fecha": date(2026, 9, 14), "motivo": None},
    ]
    with patch("app.main.movimientos_de_colegas", return_value=movimientos), \
         patch("app.main.cuentas_de_colegas", return_value=CUENTA_CON_DOSCIENTAS):
        respuesta = cliente.get("/compras/cajas/colega/3")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "Le presté" in marcado and "Me devolvió" in marcado
    assert "12/09/2026" in marcado and "14/09/2026" in marcado
    # SOBRE LA RESPUESTA ENTERA Y CON EL ATRIBUTO DE AL LADO: la barra se
    # incluye con su propio <style>, así que split("</style>")[-1] corta DE MAS
    # y se come la barra. Y el href solo aparece dos veces en la barra por
    # diseño (el ícono del sector y el botón de atrás), así que un assert del
    # href pelado no puede fallar — hay que anclar en el elemento.
    assert 'href="/compras/cajas" aria-label="Volver atrás"' in respuesta.text, (
        "tiene que poder volver a Cajas"
    )

    # Un colega que no existe no es un 500.
    with patch("app.main.movimientos_de_colegas", return_value=[]), \
         patch("app.main.cuentas_de_colegas", return_value=[]):
        assert cliente.get("/compras/cajas/colega/999").status_code == 404


# ---------------------------------------------------------------------------
# EL SELECTOR DE "¿VIENE YA ARMADA EN CAJA NUESTRA?" NO OFRECE ENVASE PERDIDO
# ---------------------------------------------------------------------------
#
# Manzana, pera y arándano salen en el cajón del proveedor. Marcar ahí "viene
# en nuestra caja" es una contradicción que no falla ruidosamente: la guía R
# en origen deriva (False, None), el conteo de cajas no se mueve, y la compra
# queda afirmando algo que no pasó. Un hueco se ve; una marca que no hace nada
# se lee como un dato declarado.

FICHAS_DE_LOS_TRES_CASOS = [
    {"id": 1, "cliente_id": 10, "articulo_id": 7, "articulo_nombre": "EJEMPLO Uno",
     "articulo_grupo": None, "envase_id": 4, "envase_nombre": "Caja EJEMPLO Fija",
     "contenido_caja": 16, "unidad_venta": "kilo", "envase_variable": False,
     "nombre_cliente": None, "codigo_cliente": None},
    {"id": 2, "cliente_id": 10, "articulo_id": 7, "articulo_nombre": "EJEMPLO Uno",
     "articulo_grupo": None, "envase_id": 5, "envase_nombre": "Caja EJEMPLO Variable",
     "contenido_caja": 10, "unidad_venta": "kilo", "envase_variable": True,
     "nombre_cliente": None, "codigo_cliente": None},
    {"id": 3, "cliente_id": 10, "articulo_id": 7, "articulo_nombre": "EJEMPLO Uno",
     "articulo_grupo": None, "envase_id": None, "envase_nombre": None,
     "contenido_caja": 18, "unidad_venta": "kilo", "envase_variable": False,
     "nombre_cliente": "EJEMPLO Perdido", "codigo_cliente": None},
]


def _catalogo_de_los_tres_casos():
    from app.main import _cajas_en_origen_por_articulo
    with patch("app.main.listar_clientes",
               return_value=[{"id": 10, "nombre": "Cliente EJEMPLO"}]), \
         patch("app.main.listar_fichas_de_todos_los_clientes",
               return_value=FICHAS_DE_LOS_TRES_CASOS):
        return _cajas_en_origen_por_articulo()


def test_el_selector_de_EN_ORIGEN_no_ofrece_la_ficha_de_ENVASE_PERDIDO():
    """Se ofrecen la FIJA y la VARIABLE; la de envase perdido no.

    Los tres casos van juntos a propósito: un test que solo plantara la
    perdida lo pasaría igual un filtro que no ofreciera ninguna (corolario
    53 — hay que poder dar las dos respuestas).
    """
    ofrecidas = {caja["id"] for caja in _catalogo_de_los_tres_casos()[7]}
    assert ofrecidas == {1, 2}, (
        "la fija se deriva y la variable se pregunta: las dos tienen caja "
        f"nuestra. La de envase perdido no. Ofrecidas: {ofrecidas}"
    )


def test_un_articulo_que_SOLO_tiene_fichas_de_envase_perdido_no_aparece():
    """Y no aparece con la lista vacía: el artículo se va entero.

    Una entrada con `[]` deja el bloque dibujado y vacío, que es lo que el
    macro dice que se lee como "este artículo no tiene cajas" — cierto acá,
    y aun así peor que no ofrecerlo: un selector con una sola opción que
    dice "No" invita a buscar la que falta.
    """
    solo_perdida = [FICHAS_DE_LOS_TRES_CASOS[2]]
    from app.main import _cajas_en_origen_por_articulo
    with patch("app.main.listar_clientes",
               return_value=[{"id": 10, "nombre": "Cliente EJEMPLO"}]), \
         patch("app.main.listar_fichas_de_todos_los_clientes", return_value=solo_perdida):
        assert _cajas_en_origen_por_articulo() == {}


def test_el_filtro_PREGUNTA_por_envase_derivado_y_no_por_su_propia_condicion():
    """Se mueve la pared y el filtro tiene que seguirla.

    Con `envase_derivado_de_la_ficha` parcheada para decir que TODA ficha
    lleva caja, la de envase perdido tiene que entrar. Un filtro con un
    `envase_id is None` propio pasa este test en verde con la regla de
    verdad cambiada, y ese es exactamente el día que las dos se separan.
    """
    from app.main import _cajas_en_origen_por_articulo
    with patch("app.main.listar_clientes",
               return_value=[{"id": 10, "nombre": "Cliente EJEMPLO"}]), \
         patch("app.main.listar_fichas_de_todos_los_clientes",
               return_value=FICHAS_DE_LOS_TRES_CASOS), \
         patch("app.main.envase_derivado_de_la_ficha", return_value=(True, 99, False)):
        ofrecidas = {caja["id"] for caja in _cajas_en_origen_por_articulo()[7]}
    assert ofrecidas == {1, 2, 3}, (
        "el filtro tiene que salir de envase_derivado_de_la_ficha, no de una "
        f"condición escrita al lado. Ofrecidas: {ofrecidas}"
    )


def test_las_pantallas_que_eligen_la_PORCION_siguen_viendo_la_de_envase_perdido():
    """El filtro es del selector de en origen, NO del catálogo del que sale.

    Stock Físico, Stock Inicial y el asignar ficha de una guía R eligen de
    qué porción del artículo se está hablando, y una ficha de envase perdido
    es una porción legítima. Filtrarla allá la haría incontable.
    """
    from app.main import _cajas_para_elegir_por_articulo
    with patch("app.main.listar_clientes",
               return_value=[{"id": 10, "nombre": "Cliente EJEMPLO"}]), \
         patch("app.main.listar_fichas_de_todos_los_clientes",
               return_value=FICHAS_DE_LOS_TRES_CASOS):
        todas = {caja["id"] for caja in _cajas_para_elegir_por_articulo()[7]}
    assert todas == {1, 2, 3}


# ---------------------------------------------------------------------------
# Y LA GUARDA VA DONDE SE ESCRIBE
# ---------------------------------------------------------------------------
#
# Que la pantalla no la ofrezca no alcanza: un POST armado a mano entra igual.
# Es el mismo hallazgo del tilde de la fecha y el del cajón en el armado.

def _cursor_con_ficha(articulo_id, envase_id, envase_variable):
    cursor = MagicMock()
    cursor.fetchone.return_value = (articulo_id, envase_id, envase_variable)
    return cursor


def test_marcar_EN_ORIGEN_una_ficha_de_ENVASE_PERDIDO_se_RECHAZA():
    from app.db import _validar_caja_en_origen
    with pytest.raises(ValueError) as error:
        _validar_caja_en_origen(_cursor_con_ficha(7, None, False), 3, 7)
    assert "cajón del proveedor" in str(error.value)


def test_la_FIJA_y_la_VARIABLE_pasan_la_guarda():
    """El caso feliz, que es el único que distingue "rechaza lo que tiene que
    rechazar" de "rechaza siempre" (corolario 30)."""
    from app.db import _validar_caja_en_origen
    _validar_caja_en_origen(_cursor_con_ficha(7, 4, False), 1, 7)
    _validar_caja_en_origen(_cursor_con_ficha(7, 5, True), 2, 7)


def test_la_guarda_del_ENVASE_PERDIDO_pregunta_por_envase_derivado():
    """Movida la pared, la de envase perdido tiene que entrar."""
    from app.db import _validar_caja_en_origen
    with patch("app.db.envase_derivado_de_la_ficha", return_value=(True, 99, False)):
        _validar_caja_en_origen(_cursor_con_ficha(7, None, False), 3, 7)


def _columnas_que_pide(fuente_de_la_funcion: str) -> str:
    """Lo que hay ENTRE el SELECT y el FROM, que es la única parte que decide
    qué columnas vuelven.

    Preguntar si el nombre "está en la consulta" no sirve y los dos canarios
    lo midieron: con `fl.envase_id` sacado del SELECT, el nombre seguía ahí
    en el `LEFT JOIN envases e ON e.id = fl.envase_id`; y con `envase_id`
    sacado de la guarda, seguía en el dict que la guarda arma dos líneas más
    abajo. Los dos asserts pasaban en verde con la columna afuera.

    Es el corolario 59: el ancla es la POSICIÓN GRAMATICAL —una columna en
    posición de columna— y no que la palabra aparezca.
    """
    arriba = fuente_de_la_funcion.upper()
    desde = arriba.index("SELECT") + len("SELECT")
    return fuente_de_la_funcion[desde:desde + arriba[desde:].index("FROM")]


def test_la_consulta_de_la_guarda_TRAE_las_dos_columnas_que_la_regla_lee():
    """Corolario 65: con el mock, el valor lo entrega el fixture y el test no
    ve QUÉ columna pidió la consulta. Sin `envase_id` en el SELECT la regla
    contesta "esta ficha no lleva caja" para TODAS y la marca se rechaza
    siempre — en producción, sin un test en rojo."""
    fuente = io.open("app/db.py", encoding="utf-8").read()
    cuerpo = fuente.split("def _validar_caja_en_origen")[1].split("\ndef ")[0]
    pedidas = _columnas_que_pide(cuerpo.split('"""')[2])
    assert "envase_id" in pedidas and "envase_variable" in pedidas, (
        f"lo que pide la consulta es: {pedidas.strip()!r}. "
        "la guarda lee las dos de la ficha: la consulta las tiene que traer"
    )


def test_la_consulta_del_CATALOGO_trae_las_dos_columnas_del_filtro():
    """Corolario 65, y acá el modo de falla es MUDO en las dos direcciones.

    El filtro las lee con `.get()` sobre un dict que viene de la base. Sin
    `envase_id` en el SELECT, `envase_derivado_de_la_ficha` contesta "envase
    perdido" para TODAS y el selector de "viene ya armada" queda vacío en las
    cinco pantallas de carga — que es exactamente lo que el macro dice que se
    lee como "este artículo no tiene cajas". Sin `envase_variable`, la
    variable se toma por fija y se ofrece igual, que no rompe nada hoy y deja
    el filtro decidiendo con media regla.

    Con el mock, el valor lo entrega el fixture: lo único que ve QUÉ columna
    pidió la consulta es el texto del SQL.
    """
    fuente = io.open("app/db.py", encoding="utf-8").read()
    cuerpo = fuente.split("def listar_fichas_de_todos_los_clientes")[1].split("\ndef ")[0]
    # Después del docstring, no "entre las dos primeras comillas triples": esa
    # función tiene DOS bloques de `\"\"\"` —el docstring y el SQL— así que un
    # corte fijo cae en el hueco de en medio y el assert falla sin razón.
    pedidas = _columnas_que_pide(cuerpo.split('"""', 2)[2])
    assert "fl.envase_id" in pedidas and "fl.envase_variable" in pedidas, (
        f"lo que pide la consulta es: {pedidas.strip()!r}. "
        "el catálogo de cajas por artículo filtra las de envase perdido con "
        "estas dos: la consulta las tiene que traer"
    )


# ---------------------------------------------------------------------------
# DESMARCAR UNA COMPRA MAL MARCADA COMO "VINO ARMADA"
# ---------------------------------------------------------------------------
#
# El 18/09 aparecio una compra de Pera marcada contra una ficha de envase
# perdido. El filtro de 2770e7c impide que vuelva a pasar; esta es la puerta
# para la que ya estaba, y para la proxima que se marque mal por otro motivo.
#
# Vive en Corregir Recepcion y no en Buscar Compras —que es donde se MARCA—
# porque desmarcar exige que la guia R este anulada, y anular vive detras de
# la clave de Administracion.

def _pantalla_corregir(marca, estado="recepcionado"):
    compra = {"id": 663, "proveedor_nombre": "Proveedor EJEMPLO",
              "proveedor_codigo_puesto": "N01P01", "articulo_nombre": "Pera EJEMPLO",
              "guia_id": 105, "guia_punto": 2, "estado": estado,
              "cantidad_cajones_real": 5.0, "contenido_por_cajon_real": 18.0,
              "cantidad_kilos_real": 90.0, "cantidad_cajones": 5.0,
              "contenido_por_cajon": 18.0, "cantidad_kilos": 90.0,
              "cantidad_fraccion": None, "cantidad_fraccion_real": None,
              "unidad_compra": "kilo", "unidad_conteo": None,
              "cantidad_cajones_rechazada": None, "motivo_rechazo": None,
              "importe": 40000.0, "articulo_id": 1}
    from app.main import _firma_acceso_gerencia
    with (
        patch.dict(os.environ, {"CLAVE_GERENCIA": "secreta"}),
        patch("app.main.obtener_detalle_compra", return_value=compra),
        patch("app.main._dependencias_con_nombres", return_value=None),
        patch("app.main._fotos_de_la_guia_de", return_value=[]),
        patch("app.main.listar_fotos_de_recepcion", return_value=[]),
        # El parche ES, el solo, la asercion de que `app.main` importa el
        # nombre (corolario 51).
        patch("app.main.marca_en_origen_de_la_compra", return_value=marca),
    ):
        cliente.cookies.set("acceso_gerencia", _firma_acceso_gerencia("secreta"))
        try:
            return cliente.get("/gerencia/compras/663/corregir-recepcion")
        finally:
            cliente.cookies.clear()


SIN_GUIA_VIVA = {"ficha_id": 21, "codigo_cliente": "PERA COMERCI",
                 "envase_nombre": None, "cliente_nombre": "Cliente EJEMPLO",
                 "guias_vivas": []}
CON_GUIA_VIVA = dict(SIN_GUIA_VIVA, guias_vivas=["R354"])
NO_MARCADA = {"ficha_id": None, "codigo_cliente": None, "envase_nombre": None,
              "cliente_nombre": None, "guias_vivas": []}


def test_la_compra_MARCADA_y_sin_guia_viva_OFRECE_sacarle_la_marca():
    """SOBRE LA RESPUESTA ENTERA y anclado en atributos, no con
    split("</style>")[-1]: esta pantalla incluye `_fotos_guia.html`, que trae
    su propio <style>, asi que el ultimo corte se come el bloque entero y el
    assert falla diciendo que no esta cuando esta (corolario 50)."""
    texto = _pantalla_corregir(SIN_GUIA_VIVA).text
    assert 'action="/gerencia/compras/663/desmarcar-armada"' in texto
    assert "<h3>Esta compra dice que vino armada en caja nuestra</h3>" in texto
    # Y dice de que ficha, porque "sacar la marca" sin decir cual invita a
    # sacarla de la compra equivocada.
    assert "PERA COMERCI" in texto


def test_con_la_GUIA_VIVA_no_hay_boton_y_dice_CUAL_anular():
    """El callejon: ofrecer algo que la escritura despues rechaza es peor que
    no ofrecer nada — el que lo aprieta se come un error por algo que la
    pantalla le propuso."""
    texto = _pantalla_corregir(CON_GUIA_VIVA).text
    assert 'action="/gerencia/compras/663/desmarcar-armada"' not in texto
    assert "<strong>Primero anulá R354</strong>" in texto


def test_una_compra_SIN_marca_no_muestra_nada_de_esto():
    """El caso normal, y el unico que distingue "ofrece cuando corresponde"
    de "ofrece siempre" (corolario 30)."""
    texto = _pantalla_corregir(NO_MARCADA).text
    assert "desmarcar-armada" not in texto
    assert "<h3>Esta compra dice que vino armada en caja nuestra</h3>" not in texto


def _cursor_desmarcar(ficha, guias_vivas):
    """El orden de los fetchone/fetchall es el orden en que la funcion pregunta."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = [(ficha,)]
    cursor.fetchall.side_effect = [[(g,) for g in guias_vivas]]
    conexion = MagicMock()
    conexion.cursor.return_value.__enter__.return_value = cursor
    return conexion, cursor


def _desmarcar(ficha=21, guias_vivas=()):
    from app.db import desmarcar_compra_armada_en_origen
    conexion, cursor = _cursor_desmarcar(ficha, guias_vivas)
    with patch("app.db.obtener_conexion", return_value=conexion):
        desmarcar_compra_armada_en_origen(663)
    return conexion, cursor


def test_desmarcar_pone_la_marca_en_NULL_y_COMMITEA():
    """El caso FELIZ, que es el unico que distingue una guarda que funciona de
    una que siempre frena (corolario 30)."""
    conexion, cursor = _desmarcar()
    consulta, parametros = next(
        c.args for c in cursor.execute.call_args_list
        if "UPDATE compras" in c.args[0]
    )
    assert "ficha_en_origen_id = NULL" in consulta
    assert parametros == (663,)
    conexion.commit.assert_called_once()


def test_desmarcar_con_la_GUIA_VIVA_rebota_NOMBRANDOLA_y_no_escribe():
    from app.db import desmarcar_compra_armada_en_origen
    conexion, cursor = _cursor_desmarcar(21, [354])
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as rebote:
            desmarcar_compra_armada_en_origen(663)
    # NOMBRA la guia: un "no se puede" que no dice que lo retiene manda a
    # adivinar, y es la misma frase que ya da corregir_recepcion_compra.
    assert "R354" in str(rebote.value)
    assert not [c for c in cursor.execute.call_args_list if "UPDATE compras" in c.args[0]]
    conexion.commit.assert_not_called()


def test_desmarcar_una_que_NO_esta_marcada_rebota():
    from app.db import desmarcar_compra_armada_en_origen
    conexion, cursor = _cursor_desmarcar(None, [])
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="no está marcada"):
            desmarcar_compra_armada_en_origen(663)
    conexion.commit.assert_not_called()


def test_desmarcar_NO_anula_la_guia_y_eso_es_una_DECISION():
    """Anular tiene su propia pantalla en Guias R. Hacerlo tambien aca seria
    la misma operacion escrita dos veces, y la copia que se separe anularia
    guias que la otra puerta no anula.

    Se afirma sobre el TEXTO de la funcion, no sobre el resultado: con la
    guia viva rebota antes de llegar a ningun UPDATE, asi que un test de
    comportamiento pasa igual con un `anulado_el = now()` escrito adentro."""
    fuente = io.open("app/db.py", encoding="utf-8").read()
    cuerpo = fuente.split("def desmarcar_compra_armada_en_origen")[1].split("\ndef ")[0]
    codigo = cuerpo.split('"""', 2)[2]
    assert "anulado_el = " not in codigo and "anular" not in codigo.lower()


def test_la_pantalla_pregunta_por_LA_MISMA_guarda_que_la_escritura():
    """Las dos leen las guias vivas de `reprocesos` con el mismo filtro. Si se
    separan, la pantalla ofrece un boton que el POST despues rechaza — el
    callejon que este bloque vino a evitar."""
    fuente = io.open("app/db.py", encoding="utf-8").read()
    filtro = "WHERE compra_origen_id = %s AND anulado_el IS NULL"
    for nombre in ("marca_en_origen_de_la_compra", "desmarcar_compra_armada_en_origen",
                   "corregir_recepcion_compra"):
        cuerpo = fuente.split(f"def {nombre}")[1].split("\ndef ")[0]
        assert filtro in cuerpo, f"{nombre} dejo de preguntar por la guia viva igual"


# ---------------------------------------------------------------------------
# EL REMITO CON DOS MAGNITUDES (B5)
# ---------------------------------------------------------------------------
#
# `pedidos_renglones.kilos_enviados` se llama kilos y guarda LA MAGNITUD DE LA
# FICHA: kilos, unidades o cubetas. Armar Remito los sumaba todos en un solo
# numero — un remito de 160 kg + 400 u + 40 cubetas daba "600", que no es de
# nada, y sin nada que se viera raro.

def _renglon_remito(id, articulo, kilos, unidad, sucursal="VL"):
    from datetime import date as _date, datetime as _dt
    return {"fecha_operacion": _date(2026, 9, 18), "pedido_id": 90, "id": id,
            "sucursal": sucursal, "articulo_id": id, "articulo_nombre": articulo,
            "cantidad": 10.0, "cantidad_armada": None, "kilos_enviados": kilos,
            "armado_el": _dt(2026, 9, 18, 10, 0), "anulado_el": None,
            "controlado_el": None, "orden_compra": "OC-1", "unidad_venta": unidad}


MEZCLADO = [
    _renglon_remito(1, "Tomate EJEMPLO", 160.0, "kilo"),
    _renglon_remito(2, "Mango EJEMPLO", 400.0, "unidad"),
    _renglon_remito(3, "Frutilla EJEMPLO", 40.0, "cubeta"),
]


def test_el_total_del_remito_se_PARTE_por_unidad_en_vez_de_sumar_las_tres():
    from app.main import _grupos_buscar_pedidos
    _, totales = _grupos_buscar_pedidos(MEZCLADO)
    assert [(f["total"], f["sufijo"]) for f in totales["por_unidad"]] == [
        (160.0, "kg"), (400.0, "u"), (40.0, "cub.")
    ]


def test_el_ORDEN_de_las_pilas_es_FIJO_y_no_por_tamano():
    """Ordenadas por total, dos remitos del mismo cliente salen con las filas
    en distinto orden segun lo que se mando ese dia, y comparar dos remitos
    pasa a ser leerlos enteros."""
    from app.main import _grupos_buscar_pedidos
    # La cubeta pesa MAS que los kilos: por tamaño saldria primera.
    al_reves = [_renglon_remito(1, "Tomate EJEMPLO", 5.0, "kilo"),
                _renglon_remito(3, "Frutilla EJEMPLO", 900.0, "cubeta")]
    _, totales = _grupos_buscar_pedidos(al_reves)
    assert [f["sufijo"] for f in totales["por_unidad"]] == ["kg", "cub."]


def test_con_UNA_SOLA_unidad_devuelve_UNA_pila_y_se_ve_como_antes():
    """El caso normal, y el unico que distingue "parte cuando hay que partir"
    de "parte siempre" (corolario 30)."""
    from app.main import _grupos_buscar_pedidos
    _, totales = _grupos_buscar_pedidos([
        _renglon_remito(1, "Tomate EJEMPLO", 160.0, "kilo"),
        _renglon_remito(2, "Pera EJEMPLO", 90.0, "kilo"),
    ])
    assert [(f["total"], f["sufijo"]) for f in totales["por_unidad"]] == [(250.0, "kg")]


def test_un_renglon_SIN_FICHA_va_en_su_propia_pila_y_DICE_que_no_tiene_unidad():
    """Y no cae al primer subtotal, que es lo que haria un `or "kilo"`: un
    numero sin rotulo al lado de otros que dicen "kg" se lee como kilos."""
    from app.main import _grupos_buscar_pedidos
    _, totales = _grupos_buscar_pedidos([
        _renglon_remito(1, "Tomate EJEMPLO", 160.0, "kilo"),
        _renglon_remito(9, "Sin ficha EJEMPLO", 12.0, None),
    ])
    pilas = {f["sufijo"]: f["total"] for f in totales["por_unidad"]}
    assert pilas == {"kg": 160.0, "sin unidad": 12.0}


def test_LOS_TRES_NIVELES_se_parten_igual_y_por_la_MISMA_funcion():
    """Sucursal, fecha y el total de arriba. Convertidos cada uno por su lado,
    el dia que cambie el rotulo cambia en uno y el remito dice "u" arriba y
    "unidad" abajo."""
    from app.main import _grupos_buscar_pedidos
    grupos, totales = _grupos_buscar_pedidos(MEZCLADO)
    del_grupo = [(f["total"], f["sufijo"]) for f in grupos[0]["por_unidad"]]
    de_la_sucursal = [(f["total"], f["sufijo"]) for f in grupos[0]["sucursales"][0]["por_unidad"]]
    de_arriba = [(f["total"], f["sufijo"]) for f in totales["por_unidad"]]
    assert del_grupo == de_la_sucursal == de_arriba


def test_el_SUFIJO_sale_del_MISMO_mapa_que_usa_Armar_Pedido():
    """Escrito dos veces, un dia la pantalla que arma dice "u" y la que
    factura dice "un.", y el que compara las dos tiene que decidir si son la
    misma cosa. Se afirma por REFERENCIA y no copiando la tabla."""
    fuente = io.open("app/main.py", encoding="utf-8").read()
    cuerpo = fuente.split("def _grupos_buscar_pedidos")[1].split("\ndef ")[0]
    assert "SUFIJOS_FICHA_REPROCESO" in cuerpo
    cuerpo_helper = fuente.split("def _totales_por_unidad")[1].split("\ndef ")[0]
    assert "SUFIJOS_FICHA_REPROCESO" in cuerpo_helper


def test_la_consulta_del_remito_TRAE_la_unidad_de_la_ficha():
    """Corolario 65: con el mock la fila la entrega el fixture, asi que lo
    unico que ve QUE columna pidio la consulta es el texto del SQL. Y el modo
    de falla es mudo — sin la columna, todas las pilas caen en "sin unidad" y
    el remito deja de decir kilos donde decia kilos."""
    fuente = io.open("app/db.py", encoding="utf-8").read()
    cuerpo = fuente.split("def buscar_renglones_pedidos")[1].split("\ndef ")[0]
    sql = cuerpo.split('"""', 2)[2]
    sin_comentarios = "\n".join(l for l in sql.split("\n") if "--" not in l)
    assert "fl.unidad_venta" in sin_comentarios
    # Y el JOIN es LEFT: un renglon sin ficha tiene que VOLVER, con la unidad
    # en NULL. Con un JOIN normal desapareceria del remito y el total
    # cerraria contra menos de lo que se mando.
    assert "LEFT JOIN fichas_logistica fl ON fl.id = r.ficha_id" in sin_comentarios


def _exportables_del_remito(renglones):
    with (
        patch("app.main._hoy_argentina", return_value=date(2026, 9, 18)),
        patch("app.main.obtener_cliente", return_value={"id": 1, "nombre": "Cliente EJEMPLO"}),
        patch("app.main.buscar_renglones_pedidos", return_value=list(renglones)),
        patch("app.main.listar_clientes", return_value=[{"id": 1, "nombre": "Cliente EJEMPLO"}]),
    ):
        filtros = "cliente_id=1&fecha_desde=2026-09-15&fecha_hasta=2026-09-18"
        return (cliente.get(f"/administracion/pedidos/buscar?{filtros}"),
                cliente.get(f"/administracion/pedidos/buscar/exportar-pdf?{filtros}"),
                cliente.get(f"/administracion/pedidos/buscar/exportar-excel?{filtros}"))


def test_la_PANTALLA_del_remito_dice_la_unidad_en_cada_renglon_y_parte_el_total():
    pantalla, _, _ = _exportables_del_remito(MEZCLADO)
    assert pantalla.status_code == 200
    marcado = pantalla.text.split("</style>")[-1]
    # Cada renglon con SU unidad, no todos con "kg".
    assert "160 kg" in marcado and "400 u" in marcado and "40 cub." in marcado
    # Y el total de arriba NO es un solo numero que sume las tres.
    assert "600 kg" not in marcado


def test_el_EXCEL_del_remito_pone_la_unidad_en_COLUMNA_y_una_fila_de_total_por_unidad():
    from openpyxl import load_workbook
    _, _, excel = _exportables_del_remito(MEZCLADO)
    assert excel.status_code == 200
    hoja = load_workbook(io.BytesIO(excel.content)).active
    filas = [[c.value for c in f] for f in hoja.iter_rows(max_col=7)]

    mango = next(f for f in filas if f[1] == "Mango EJEMPLO")
    # El numero SIGUE SIENDO NUMERO: pegarle "400 u" adentro lo vuelve texto
    # y deja de poder sumarse, que es para lo que existe una planilla.
    # NUMERO y no texto. `float` a secas no sirve: openpyxl devuelve 400.0
    # como int, asi que el assert caia por el TIPO y no por lo que importa.
    assert mango[4] == 400.0 and not isinstance(mango[4], str)
    assert mango[5] == "u"

    totales = [f for f in filas if f[0] == "Total"]
    assert [(f[4], f[5]) for f in totales] == [(160.0, "kg"), (400.0, "u"), (40.0, "cub.")]
    # Los BULTOS van SOLO en la primera: son comparables entre unidades, asi
    # que repetirlos en cada fila los contaria tres veces.
    assert totales[0][2] == 30.0
    assert [f[2] for f in totales[1:]] == [None, None]


def test_el_PDF_del_remito_sale_y_no_es_el_de_una_sola_unidad():
    """El PDF se verifica por que SALE y por su largo, no por su texto: es un
    binario y extraerle el texto seria una segunda implementacion del
    generador adentro del test. Lo que decide el contenido es el test de
    `_texto_por_unidad`, que es la funcion que los dos comparten."""
    _, pdf, _ = _exportables_del_remito(MEZCLADO)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
    assert len(pdf.content) > 1000


def test_las_DOS_exportables_y_la_pantalla_dicen_el_MISMO_sufijo():
    """Tres superficies, un solo mapa. Si el PDF dice "u" y el Excel
    "unidad", el que compara los dos archivos tiene que decidir si son la
    misma cosa."""
    from core.exportar_pedidos import _texto_por_unidad
    from app.main import _grupos_buscar_pedidos
    _, totales = _grupos_buscar_pedidos(MEZCLADO)
    assert _texto_por_unidad(totales, sufijo_sin_kilaje=False) == "160 kg + 400 u + 40 cub."


def test_el_RENGLON_del_PDF_dice_su_unidad_y_no_kg_para_todos():
    """El agujero que encontro el canario: el test del PDF verificaba que
    SALIERA —status 200, %PDF, largo— y eso no ve el texto de una celda.
    Devolverle el "kg" fijo a cada renglon no hacia caer nada.

    Se afirma sobre `_texto_kilos`, que es la funcion que arma esa celda: el
    PDF es un binario y extraerle el texto seria una segunda implementacion
    del generador adentro del test."""
    from core.exportar_pedidos import _texto_kilos
    assert _texto_kilos({"kilos": 160.0, "sufijo_unidad": "kg"}) == "160 kg"
    assert _texto_kilos({"kilos": 400.0, "sufijo_unidad": "u"}) == "400 u"
    assert _texto_kilos({"kilos": 40.0, "sufijo_unidad": "cub."}) == "40 cub."
    # Sin ficha lo DICE: un numero sin rotulo al lado de otros que dicen "kg"
    # se lee como kilos.
    assert _texto_kilos({"kilos": 12.0, "sufijo_unidad": None}) == "12 sin unidad"
    # Y el caso sin kilaje no gana una unidad de la nada.
    assert _texto_kilos({"kilos": None, "sufijo_unidad": "kg"}) == "SIN KILAJE"
