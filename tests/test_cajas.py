"""El stock de CAJAS NUESTRAS: las reglas puras, la cuenta derivada y la pantalla."""

import ast
import io
import os
import re
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import COMPARADOR_DESDE_EL_CONTEO, _SQL_STOCK_DE_ENVASES
from app.main import PUERTA_COMPRAS, app
from core.envases import (
    SIGNO_POR_TIPO_DE_GUIA,
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
    """
    check = re.search(
        r"movimientos_envase_origen_check\s*\n?\s*check \(origen in \(([^)]+)\)\)", ESQUEMA)
    assert check, "no encontré el CHECK de movimientos_envase.origen"
    del_esquema = set(re.findall(r"'([a-z_]+)'", check.group(1)))
    marcado = io.open("templates/compras_cajas.html", encoding="utf-8").read().split("</style>")[-1]
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
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}), \
         patch("app.main.crear_movimiento_envase") as escribir:
        cliente.post("/compras/cajas/movimiento",
                     data={"envase_id": "1", "origen": "prestamo_salida",
                           "cantidad": "30", "fecha": "2026-09-15", "motivo": ""},
                     follow_redirects=False)
    escribir.assert_called_once()
    assert escribir.call_args.args[2] == -30
    # Y la compra suma, con la misma pantalla y el mismo campo en positivo.
    with patch("app.main.cajas_perdidas_por_rechazo", return_value=SIN_PERDIDAS), \
         patch("app.main.gasto_en_cajas", return_value=SIN_GASTO), \
         patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
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
