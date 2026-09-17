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
FICHA_VARIABLE = {"envase_id": 7, "envase_variable": True}
FICHA_SIN_ENVASE = {"envase_id": None, "envase_variable": False}


# ---------------------------------------------------------------------------
# Las reglas puras
# ---------------------------------------------------------------------------

def test_el_envase_se_DERIVA_de_la_ficha_fija_y_se_PREGUNTA_cuando_no_se_puede():
    assert envase_derivado_de_la_ficha(FICHA_FIJA) == (True, 7, False)
    # Variable: el envase lo decide el cajón de ESA compra, no la ficha.
    assert envase_derivado_de_la_ficha(FICHA_VARIABLE) == (None, None, True)
    # Sin ficha no hay de dónde derivarlo. No estaba en el pedido y sale de
    # la misma regla: si no se puede derivar, se pregunta.
    assert envase_derivado_de_la_ficha(None) == (None, None, True)


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
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase",
               return_value={"casos": 0, "poblacion": 0}):
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


def test_el_stock_NO_es_una_columna_que_alguien_actualiza():
    """Que anular una guía R corrija el stock solo sale de esto, no de un trigger.

    Si el stock viviera en una columna, anular sería un segundo lugar del que
    acordarse. Acá la fila deja de cumplir `anulado_el IS NULL` y ya no está
    en la suma.

    Verificado contra el esquema real: anulando una guía R de 30 cajas el
    stock pasó de 226 a 256 sin tocar nada más.
    """
    # CALIFICADO POR ALIAS Y EN LAS CUATRO PATAS (corolario 4). Esto decía
    # `assert "anulado_el IS NULL" in _SQL_STOCK_DE_ENVASES` a secas, y la
    # consulta tiene CUATRO tablas que se llaman igual esa columna: sacarle el
    # filtro a la pata de las guías dejaba el assert pasando contra el de otra
    # tabla. Medido con un canario: caían CERO tests, y una guía R anulada
    # habría seguido consumiendo cajas para siempre — que es exactamente lo
    # contrario de lo que este test promete en su título.
    for alias, pata in (("m", "declarados"), ("r", "guias")):
        assert f"{alias}.anulado_el IS NULL" in _SQL_STOCK_DE_ENVASES, pata
    assert "origen = 'conteo_inicial' AND anulado_el IS NULL" in _SQL_STOCK_DE_ENVASES
    assert _SQL_STOCK_DE_ENVASES.count("anulado_el IS NULL") == 3
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


UN_ENVASE_SIN_ARRANCAR = [{
    "id": 1, "nombre": "Caja Grande", "umbral_reposicion": 50, "desde": None,
    "contadas": None, "declaradas": 0, "por_guias": 0, "stock": None,
}]
UN_ENVASE_BAJO = [{
    "id": 1, "nombre": "Caja Grande", "umbral_reposicion": 50, "desde": date(2026, 9, 10),
    "contadas": 100, "declaradas": -70, "por_guias": -20, "stock": 10,
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
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_SIN_ARRANCAR), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "todavía sin conteo inicial" in marcado
    assert 'class="stock bajo"' not in marcado
    # Y ofrece arrancarla, que es lo único que se puede hacer con ese envase.
    assert 'action="/compras/cajas/conteo-inicial"' in marcado


def test_debajo_del_umbral_la_pantalla_lo_MARCA():
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
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


def test_el_HUECO_de_las_guias_sin_declarar_se_muestra_CON_su_poblacion():
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase",
               return_value={"casos": 3, "poblacion": 314}):
        respuesta = cliente.get("/compras/cajas")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'class="hueco"' in marcado
    # `casos 3` solo se puede leer contra `de 314`.
    assert "3" in marcado and "314" in marcado


def test_la_pantalla_vive_en_COMPRAS_y_la_barra_lo_dice():
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    # SOBRE EL DOCUMENTO ENTERO y no sobre `[-1]`: la barra se incluye desde
    # otra plantilla que trae su PROPIO `<style>`, así que el último
    # `</style>` del documento es el de ella y el corte se come la barra.
    # Es el corolario 50 —`split` falla por los dos lados— y el ancla es un
    # elemento que solo puede ser marcado, no una palabra suelta.
    assert 'href="/compras" aria-label="Volver atrás"' in respuesta.text


def test_una_cantidad_con_DECIMALES_no_entra():
    """Media caja no existe, y la regla sale de la misma función que la guía R."""
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}), \
         patch("app.main.crear_movimiento_envase") as escribir:
        respuesta = cliente.post("/compras/cajas/movimiento",
                                 data={"envase_id": "1", "origen": "compra",
                                       "cantidad": "20.5", "fecha": "", "motivo": ""})
    assert respuesta.status_code == 400
    assert "decimales" in respuesta.text
    escribir.assert_not_called()


def test_el_PRESTAMO_lo_da_vuelta_el_SERVER_y_no_la_persona():
    """La pregunta es "cuántas le mandé", no "cuántas resto"."""
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}), \
         patch("app.main.crear_movimiento_envase") as escribir:
        cliente.post("/compras/cajas/movimiento",
                     data={"envase_id": "1", "origen": "prestamo_al_puesto",
                           "cantidad": "30", "fecha": "2026-09-15", "motivo": ""},
                     follow_redirects=False)
    escribir.assert_called_once()
    assert escribir.call_args.args[2] == -30
    # Y la compra suma, con la misma pantalla y el mismo campo en positivo.
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}), \
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


def test_la_pantalla_MUESTRA_lo_que_se_gasto_en_cajas():
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=CON_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = _cuerpo(respuesta)

    # El ancla es la CLASE, no el texto: el comentario del <style> explica por
    # qué el gasto se apila sin tabla y nombra el gasto (corolario 38).
    assert 'class="gasto-total"' in marcado
    assert marcado.count('class="gasto-fila"') == 2, "un renglón por envase"
    # Y el total está, con las dos mitades: cuántas cajas y cuánta plata.
    assert "252.000" in marcado
    assert "240 cajas" in marcado


def test_SIN_compras_la_pantalla_lo_DICE_en_vez_de_mostrar_un_cero():
    """La otra respuesta del detector (corolario 53): la que NO tiene que marcar.

    Un `$0` prolijo se lee como "no gastamos nada en cajas", que es lo mismo
    que se vería si nadie declarara las compras. Son cosas distintas y la
    pantalla las separa con palabras.
    """
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    marcado = _cuerpo(respuesta)

    assert 'class="gasto-total"' not in marcado, "sin compras no hay total que mostrar"
    assert "No hay ninguna compra de cajas declarada" in marcado


def test_las_compras_SIN_COSTO_a_su_fecha_se_dicen_y_no_se_esconden():
    """`cajas` y `gasto` no tienen la misma población, y eso se ve.

    Una compra anterior al primer costo cargado de su envase suma cajas y no
    suma pesos. Sin este renglón el total se leería como si las cubriera.
    """
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=CON_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    # Una sola frase, con los saltos de línea del HTML colapsados: partida en
    # dos asserts unidos por un `or` el test lo pasa cualquiera de las mitades.
    marcado = " ".join(_cuerpo(respuesta).split())
    assert "<strong>1 de esas compras no tienen costo cargado a su fecha</strong>" in marcado
    assert "el total está corto por ésas" in marcado


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


def test_la_pantalla_LISTA_las_cajas_perdidas_ORDENADAS_POR_PLATA():
    """Ordenada por plata es lo que la vuelve una lista de trabajo.

    En Frutamax cuatro artículos se llevan el 80% de los $158.600: por cajas
    o por nombre habría que leerla entera para encontrar los dos que
    importan. El orden lo hace el SQL; acá se afirma que la pantalla lo
    respeta y no lo vuelve a ordenar por su cuenta.
    """
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=CON_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = _cuerpo(respuesta)

    assert marcado.count('class="perdida-fila"') == 2
    assert 'class="perdida-total"' in marcado
    assert marcado.index("Fruta Uno") < marcado.index("Fruta Dos"), (
        "la de más plata tiene que ir primero"
    )
    # Cliente y artículo juntos: el número se negocia con alguien.
    assert "Fruta Uno · EJEMPLO Super" in " ".join(marcado.split())
    assert "59.250" in marcado


def test_la_lista_dice_DE_CUANTOS_RECHAZOS_sale_cada_numero():
    """Sin esa columna un porcentaje sobre números chicos no se puede leer.

    Cinco cajas perdidas en UN rechazo es un camión que volvió; las mismas
    cinco en CINCO es algo que pasa siempre, y son dos conversaciones
    distintas. Es el denominador del corolario 45 puesto por renglón.
    """
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=CON_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    marcado = " ".join(_cuerpo(respuesta).split())

    assert "4 rechazos" in marcado
    assert "1 rechazo ·" in marcado, "singular con uno solo, o se lee como un error"


def test_SIN_cajas_perdidas_la_pantalla_lo_DICE_en_vez_de_mostrar_una_lista_vacia():
    """La otra respuesta del par (corolario 53).

    Y acá el vacío es la respuesta normal: la mayoría de las semanas no se
    pierde ninguna caja. Una tarjeta vacía se aprende a saltear y el día que
    tenga algo ya nadie la mira.
    """
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    marcado = _cuerpo(respuesta)

    assert 'class="perdida-total"' not in marcado
    assert "Ningún rechazo se llevó una caja nuestra" in marcado


def test_las_dos_cuentas_de_la_pantalla_usan_LA_MISMA_VENTANA():
    """Lo comprado y lo perdido se leen juntos: con dos recortes no se restan.

    Se afirma sobre la LLAMADA y no sobre el texto: las dos fechas viajan a
    la pantalla adentro de sus dicts, así que un assert sobre el marcado
    compararía lo que el fixture trajo (corolario 40).
    """
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS) as perdidas, \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO) as gasto, \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=[]), \
         patch("app.main.listar_colegas", return_value=[]), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        cliente.get("/compras/cajas")

    assert perdidas.call_args.args == gasto.call_args.args


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
    fila = (1, "Caja EJEMPLO Grande", 100, date(2026, 9, 10), 500, 0, 0, 500)
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
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO_CON_DEUDA), \
         patch("app.main.cuentas_de_colegas", return_value=CUENTA_CON_DOSCIENTAS), \
         patch("app.main.listar_colegas", return_value=[{"id": 3, "nombre": "Colega EJEMPLO Uno", "activo": True}]), \
         patch("app.main.contar_guias_sin_declarar_el_envase",
               return_value={"casos": 0, "poblacion": 0}):
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
        (1, "Caja EJEMPLO Grande", 100, date(2026, 9, 10), 500, 0, 0, 500)]
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
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.cuentas_de_colegas", return_value=CUENTA_CON_DOSCIENTAS), \
         patch("app.main.listar_colegas", return_value=[{"id": 3, "nombre": "Colega EJEMPLO Uno", "activo": True}]), \
         patch("app.main.contar_guias_sin_declarar_el_envase",
               return_value={"casos": 0, "poblacion": 0}):
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
