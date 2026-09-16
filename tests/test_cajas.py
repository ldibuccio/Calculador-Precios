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
    envase_de_la_guia,
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
    assert envase_de_la_guia(FICHA_FIJA) == (True, 7, False)
    # Variable: el envase lo decide el cajón de ESA compra, no la ficha.
    assert envase_de_la_guia(FICHA_VARIABLE) == (None, None, True)
    # Sin ficha no hay de dónde derivarlo. No estaba en el pedido y sale de
    # la misma regla: si no se puede derivar, se pregunta.
    assert envase_de_la_guia(None) == (None, None, True)


def test_una_ficha_SIN_ENVASE_no_es_un_hueco_es_envase_perdido():
    # Manzana, pera, arándano: salen en el cajón del proveedor y no hay caja
    # nuestra que contar. Eso es una respuesta, no un dato que falta — por eso
    # NO pide preguntar.
    assert envase_de_la_guia(FICHA_SIN_ENVASE) == (False, None, False)


def test_la_guia_EN_ORIGEN_SUMA_donde_la_normal_resta():
    # La compra que llegó ya armada es una caja que ENTRA al depósito.
    assert cajas_que_mueve_la_guia("normal", 20, True) == -20
    assert cajas_que_mueve_la_guia("en_origen", 5, True) == 5
    # Las del corte ya estaban armadas antes de que esta cuenta empezara.
    assert cajas_que_mueve_la_guia("inicial", 77, True) == 0


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
    """Las tres patas derivadas comparan contra la fecha del conteo inicial.

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
    assert _SQL_STOCK_DE_ENVASES.count("{comp}") == 3
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
    assert "WHEN 'en_origen' THEN r.bultos_primera" in sql
    assert "WHEN 'normal'    THEN -r.bultos_primera" in sql
    assert "ELSE 0 END" in sql
    # El rechazo que vacía la caja es el ÚNICO destino que suma.
    assert "m.destino_rechazo = 'reproceso'" in sql


def test_el_stock_NO_es_una_columna_que_alguien_actualiza():
    """Que anular una guía R corrija el stock solo sale de esto, no de un trigger.

    Si el stock viviera en una columna, anular sería un segundo lugar del que
    acordarse. Acá la fila deja de cumplir `anulado_el IS NULL` y ya no está
    en la suma.

    Verificado contra el esquema real: anulando una guía R de 30 cajas el
    stock pasó de 226 a 256 sin tocar nada más.
    """
    assert "anulado_el IS NULL" in _SQL_STOCK_DE_ENVASES
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
    "contadas": None, "declaradas": 0, "por_guias": 0, "liberadas": 0, "stock": None,
}]
UN_ENVASE_BAJO = [{
    "id": 1, "nombre": "Caja Grande", "umbral_reposicion": 50, "desde": date(2026, 9, 10),
    "contadas": 100, "declaradas": -70, "por_guias": -20, "liberadas": 6, "stock": 16,
}]


def test_sin_conteo_inicial_la_pantalla_NO_dice_cero():
    """Un cero ahí se leería como "no quedan cajas", que es lo contrario."""
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_SIN_ARRANCAR), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "todavía sin conteo inicial" in marcado
    assert 'class="stock bajo"' not in marcado
    # Y ofrece arrancarla, que es lo único que se puede hacer con ese envase.
    assert 'action="/compras/cajas/conteo-inicial"' in marcado


def test_debajo_del_umbral_la_pantalla_lo_MARCA():
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}):
        respuesta = cliente.get("/compras/cajas")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'class="stock bajo"' in marcado
    assert "hay que reponer" in marcado
    # Las cuatro patas al lado del total: un número solo no se puede leer.
    assert "guías R" in marcado and "vueltas de un rechazo" in marcado


def test_el_HUECO_de_las_guias_sin_declarar_se_muestra_CON_su_poblacion():
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.contar_guias_sin_declarar_el_envase",
               return_value={"casos": 3, "poblacion": 314}):
        respuesta = cliente.get("/compras/cajas")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'class="hueco"' in marcado
    # `casos 3` solo se puede leer contra `de 314`.
    assert "3" in marcado and "314" in marcado


def test_la_pantalla_vive_en_COMPRAS_y_la_barra_lo_dice():
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
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
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
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
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
         patch("app.main.contar_guias_sin_declarar_el_envase", return_value={"casos": 0, "poblacion": 0}), \
         patch("app.main.crear_movimiento_envase") as escribir:
        cliente.post("/compras/cajas/movimiento",
                     data={"envase_id": "1", "origen": "prestamo_salida",
                           "cantidad": "30", "fecha": "2026-09-15", "motivo": ""},
                     follow_redirects=False)
    escribir.assert_called_once()
    assert escribir.call_args.args[2] == -30
    # Y la compra suma, con la misma pantalla y el mismo campo en positivo.
    with patch("app.main.stock_de_envases", return_value=UN_ENVASE_BAJO), \
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
         "por_guias": 0, "liberadas": 0},
        {"id": 2, "nombre": "Caja Chica", "umbral_reposicion": 20, "stock": 300,
         "desde": date(2026, 9, 10), "contadas": 300, "declaradas": 0,
         "por_guias": 0, "liberadas": 0},
        {"id": 3, "nombre": "Sin arrancar", "umbral_reposicion": 99, "stock": None,
         "desde": None, "contadas": None, "declaradas": 0,
         "por_guias": 0, "liberadas": 0},
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
