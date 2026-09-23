"""La carga de compra: un cliente, una fecha, y el ancla del promedio.

POR QUÉ EXISTE. El rediseño del 22/09 partió "Qué comprar hoy" en dos pasos,
y con eso la carga se despegó del listado: un listado dejó de estar
identificado por una fecha y pasó a ser un ARMADO de cargas, que puede tomar
dos días de Día y uno de Tailem.

CORREN CONTRA POSTGRES DE VERDAD, con `db/esquema_completo.sql`. Son los
únicos que pueden ver que el SQL PARSEA y que los CHECK y las FK aceptan lo
que el código escribe: un assert de texto verifica la FORMA de una consulta,
nunca su VALIDEZ contra el esquema (corolario 89).

LO QUE MÁS SE PUEDE ROMPER SIN QUE NADA AVISE es el ancla del promedio. El
`ON CONFLICT` de `guardar_carga_de_compra` deja `promedio_anterior_a` AFUERA
del SET a propósito, y eso se lee como una omisión: el que "complete" ese SET
no rompe ninguna pantalla — hace que la ventana del promedio se corra sola
cada vez que alguien toca la carga, y el número que sale sigue siendo
plausible. Por eso hay un test que lo fija y un canario que lo demuestra.
"""
import os
import sys
from datetime import date, timedelta

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

# Igual que el humo: sin Postgres se saltea, y con HUMO_OBLIGATORIO=1 —que el
# workflow pone— dejar de poder correrlo FALLA en vez de saltear. Un test
# salteado se lee exactamente igual que uno verde.
OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

# EL DÍA EN QUE SE CARGÓ, y va a una fecha que NUNCA puede ser hoy.
#
# Se llamaba CARGADA_EL y valía 2026-09-22, que era el día de ayer. El canario que
# le cambia el ancla por `_hoy_argentina()` daba CERO: corrido a las 02:21
# UTC, `_hoy_argentina()` devuelve el 22 en Argentina, o sea el mismo valor
# — el test comparaba dos cosas iguales por la hora a la que se corría.
# Es un test que mide el ENTORNO: pasa donde se escribe y donde decide,
# calla (corolario 92). Con una fecha fija y lejana, los dos valores no
# pueden coincidir nunca.
CARGADA_EL = date(2026, 3, 5)
EL_27 = date(2026, 9, 27)


@pytest.fixture(scope="module")
def base_real():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def galpon(base_real, monkeypatch):
    """Un cliente y dos artículos nuevos por test, y DATABASE_URL restaurada al
    salir — la suite entera está mockeada y filtrársela sería dejar que
    cualquier otro test toque una base de verdad."""
    monkeypatch.setenv("DATABASE_URL", base_real)
    import app.db as d

    def sql(consulta, parametros=()):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()

    (sufijo,), = sql("SELECT nextval(pg_get_serial_sequence('clientes','id'))")
    (cliente,), = sql("INSERT INTO clientes (nombre) VALUES (%s) RETURNING id",
                      (f"EJEMPLO Cliente {sufijo}",))
    (tomate,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id",
                     (f"EJEMPLO Tomate {sufijo}",))
    (lima,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id",
                   (f"EJEMPLO Lima {sufijo}",))
    return d, sql, cliente, tomate, lima


def test_EDITAR_una_carga_NO_MUEVE_el_ancla_del_promedio(galpon):
    """La regla del dueño: editarla la deja donde está; el que la mueve es
    borrarla y empezar de cero. El canario está abajo."""
    d, _sql, cliente, _t, _l = galpon
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    # Se edita al día siguiente, con lo que el server pondría de ancla hoy.
    d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL + timedelta(days=1), 0)

    carga = d.carga_de_compra(cliente, EL_27)
    assert carga["modo"] == "manual", "el modo SÍ se actualiza al editar"
    assert carga["promedio_anterior_a"] == CARGADA_EL, (
        "editar movió el ancla: la ventana del promedio se corre sola"
    )


def test_EDITAR_una_carga_SI_MUEVE_el_margen(galpon):
    """EL ESPEJO DEL TEST DE ARRIBA, y hace falta: el `ON CONFLICT` pisa el
    margen y NO pisa el ancla, y las dos mitades se ven igual leyendo el SET.

    El margen es lo que el comprador acaba de tipear en la pantalla, así que
    guardarlo es el punto de guardar; el ancla es cuándo se abrió la carga y
    no cambia porque alguien la edite. Sin este test, sacar el margen del
    `SET` no rompe nada: la carga nueva lo guarda bien y solo la EDICIÓN lo
    pierde, en silencio.
    """
    d, _sql, cliente, _t, _l = galpon
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 10)
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 25)

    carga = d.carga_de_compra(cliente, EL_27)
    assert carga["margen"] == 25.0, "editar no guardó el margen nuevo"
    assert carga["promedio_anterior_a"] == CARGADA_EL, "y el ancla igual no se movió"


def test_BORRARLA_Y_EMPEZAR_DE_CERO_si_mueve_el_ancla(galpon):
    """La otra mitad, y es la que hace que la de arriba no sea una traba: sin
    esto, una carga vieja quedaría con su ancla para siempre."""
    d, _sql, cliente, _t, _l = galpon
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    assert d.borrar_carga_de_compra(cliente, EL_27) is True
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL + timedelta(days=1), 0)

    assert d.carga_de_compra(cliente, EL_27)["promedio_anterior_a"] == CARGADA_EL + timedelta(days=1)


def test_UNA_carga_por_cliente_y_fecha_y_la_segunda_EDITA_en_vez_de_sumar(galpon):
    """Lo que el dueño pidió: entrar de nuevo a Día para el mismo día abre la
    que ya existe. Que no pueda haber dos lo decide la BASE, no el código."""
    d, sql, cliente, _t, _l = galpon
    primera = d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    segunda = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL, 0)
    assert primera == segunda, "la segunda creó una carga nueva en vez de editar"
    (cuantas,), = sql("SELECT count(*) FROM cargas_compra WHERE cliente_id = %s", (cliente,))
    assert cuantas == 1


def test_una_carga_que_NO_EXISTE_devuelve_None_y_no_una_vacia(galpon):
    """`None` y "existe en automático" se ven igual mirando solo los
    renglones, y la pantalla necesita distinguirlas para poder preguntar."""
    d, _sql, cliente, _t, _l = galpon
    assert d.carga_de_compra(cliente, EL_27) is None
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    carga = d.carga_de_compra(cliente, EL_27)
    assert carga is not None and carga["renglones"] == {}


def test_los_renglones_SOBREVIVEN_un_cambio_de_modo(galpon):
    """Pasar un rato a automático no puede borrar lo que se tipeó o se leyó de
    un archivo: re-tipear molesta, releer un archivo cuesta una lectura con IA
    y otra revisión."""
    d, _sql, cliente, tomate, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL, 0)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500})

    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    assert d.carga_de_compra(cliente, EL_27)["renglones"] == {tomate: 500.0}


def test_guardar_renglones_REEMPLAZA_y_no_mezcla(galpon):
    """Es lo que quedó, no lo que cambió: sacarle un artículo a la carga tiene
    que llevárselo, y eso un upsert no lo puede expresar."""
    d, _sql, cliente, tomate, lima = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL, 0)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500, lima: 20})
    d.guardar_renglones_de_carga(carga_id, {tomate: 600})

    assert d.carga_de_compra(cliente, EL_27)["renglones"] == {tomate: 600.0}


def test_el_POR_BULTO_se_GUARDA_y_se_LEE_y_el_que_falta_queda_en_NULL(galpon):
    """Contra la base de verdad: el INSERT nombra la columna nueva y el SELECT
    la trae. Un mock no puede ver si ese SQL parsea (corolario 89).

    El que no se declaró queda en NULL y NO viaja en `por_bulto`: es "proponé
    el de la ficha", y un 0 o un valor inventado ahí lo taparía."""
    d, sql, cliente, tomate, lima = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL, 0)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500, lima: 20}, {tomate: 20})

    carga = d.carga_de_compra(cliente, EL_27)
    assert carga["renglones"] == {tomate: 500.0, lima: 20.0}
    assert carga["por_bulto"] == {tomate: 20.0}
    (nulos,), = sql("SELECT count(*) FROM cargas_compra_renglones"
                    " WHERE carga_id = %s AND contenido_por_bulto IS NULL", (carga_id,))
    assert nulos == 1


def test_borrar_la_carga_SE_LLEVA_sus_renglones(galpon):
    d, sql, cliente, tomate, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL, 0)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500})
    d.borrar_carga_de_compra(cliente, EL_27)

    (quedan,), = sql("SELECT count(*) FROM cargas_compra_renglones WHERE carga_id = %s",
                     (carga_id,))
    assert quedan == 0


def test_borrar_una_carga_QUE_UN_LISTADO_YA_USO_lo_RECHAZA_la_base(galpon):
    """Borrarla cambiaría en silencio lo que ese listado dice que se salió a
    comprar. Decide la BASE (la FK no va en cascada) y el código traduce."""
    d, sql, cliente, _t, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    # CERRADO y en otra fecha: el índice parcial deja UN borrador por día, y
    # el test de abajo abre el suyo para el 27. Para la FK da lo mismo.
    (listado,), = sql(
        "INSERT INTO listados_compra (fecha, estado)"
        " VALUES (%s, 'cerrado') RETURNING id", (date(2026, 9, 24),))
    sql("INSERT INTO listados_compra_cargas VALUES (%s, %s)", (listado, carga_id))

    with pytest.raises(Exception) as rebote:
        d.borrar_carga_de_compra(cliente, EL_27)
    assert "listados_compra_cargas" in str(rebote.value)
    assert d.carga_de_compra(cliente, EL_27) is not None, "la carga se borró igual"


def test_listar_cargas_RECORTA_por_fecha_y_el_recorte_lo_elige_QUIEN_LLAMA(galpon):
    """"Desde ayer en adelante" es del dueño y vive en la pantalla; acá lo que
    se fija es que el recorte exista y muerda."""
    d, _sql, cliente, _t, _l = galpon
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    d.guardar_carga_de_compra(cliente, EL_27 - timedelta(days=10), "automatico", CARGADA_EL, 0)

    desde_ayer = [c for c in d.listar_cargas_desde(EL_27 - timedelta(days=1))
                  if c["cliente_id"] == cliente]
    todas = [c for c in d.listar_cargas_desde(EL_27 - timedelta(days=30))
             if c["cliente_id"] == cliente]
    assert len(desde_ayer) == 1 and len(todas) == 2


def test_el_aviso_de_YA_SE_USO_excluye_el_listado_QUE_SE_ESTA_EDITANDO(galpon):
    """Sin eso, toda carga que se acaba de tildar diría "ya se usó" y el
    cartel pasaría a estar siempre puesto, que es como se aprende a no
    leerlo."""
    d, sql, cliente, _t, _l = galpon
    # UN SOLO ABIERTO en la base (índice del 23/09): uno que haya dejado otro
    # test haría rebotar el INSERT de abajo según el orden en que corran.
    sql("UPDATE listados_compra SET estado = 'cerrado' WHERE estado = 'borrador'")
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    (viejo,), = sql(
        "INSERT INTO listados_compra (fecha, estado)"
        " VALUES (%s, 'cerrado') RETURNING id", (date(2026, 9, 26),))
    (editando,), = sql(
        "INSERT INTO listados_compra (fecha, estado)"
        " VALUES (%s, 'borrador') RETURNING id", (EL_27,))
    sql("INSERT INTO listados_compra_cargas VALUES (%s, %s)", (viejo, carga_id))
    sql("INSERT INTO listados_compra_cargas VALUES (%s, %s)", (editando, carga_id))

    def la_carga(excepto):
        return next(c for c in d.listar_cargas_desde(EL_27 - timedelta(days=1), excepto)
                    if c["id"] == carga_id)

    editando_ahora = la_carga(editando)
    assert editando_ahora["usada_en_otros"] == 1, "cuenta el listado que se edita"
    assert editando_ahora["ultimo_listado"] == date(2026, 9, 26)
    # Sin excluir nada los ve a los dos: el parámetro hace algo.
    assert la_carga(None)["usada_en_otros"] == 2


def test_el_BORRADOR_guarda_CARGAS_y_KILAJES_y_al_volver_a_guardar_REEMPLAZA(galpon):
    """Contra la base de verdad: el INSERT sin margen tiene que entrar —la
    columna se va del listado— y destildar una carga tiene que sacarla."""
    d, _sql, cliente, tomate, _l = galpon
    uno = d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 0)
    dos = d.guardar_carga_de_compra(cliente, EL_27 + timedelta(days=1), "manual", CARGADA_EL, 0)
    fecha = date(2026, 3, 9)   # un día que ningún otro test usa para su borrador

    listado = d.guardar_borrador_de_compra(fecha, {uno, dos}, {tomate: 18.5})
    borrador = d.borrador_de_compra()
    assert borrador["id"] == listado
    assert borrador["cargas"] == {uno, dos}
    assert borrador["kilajes"] == {tomate: 18.5}
    assert "margen" not in borrador

    d.guardar_borrador_de_compra(fecha, {dos}, {})
    borrador = d.borrador_de_compra()
    assert borrador["id"] == listado, "guardar de nuevo abrió otro listado"
    assert borrador["cargas"] == {dos} and borrador["kilajes"] == {}


def test_una_carga_del_listado_MAS_VIEJA_que_ayer_se_sigue_ofreciendo(galpon):
    """La pantalla guarda lo que viene tildado: una carga del listado que no
    se dibuja se DESTILDA sola al primer Guardar."""
    d, _sql, cliente, _t, _l = galpon
    vieja = d.guardar_carga_de_compra(cliente, EL_27 - timedelta(days=10), "automatico",
                                      CARGADA_EL, 0)
    fecha = date(2026, 3, 10)
    listado = d.guardar_borrador_de_compra(fecha, {vieja}, {})
    desde = EL_27 - timedelta(days=1)

    con = [c["id"] for c in d.listar_cargas_desde(desde, listado)]
    sin = [c["id"] for c in d.listar_cargas_desde(desde, None)]
    assert vieja in con
    assert vieja not in sin, "sin listado el recorte por fecha tiene que seguir mordiendo"


def test_cargas_con_renglones_trae_lo_que_la_carga_GUARDO(galpon):
    d, _sql, cliente, tomate, lima = galpon
    carga = d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL, 15)
    d.guardar_renglones_de_carga(carga, {tomate: 40.0})
    otra = d.guardar_carga_de_compra(cliente, EL_27 + timedelta(days=1), "manual", CARGADA_EL, 0)
    d.guardar_renglones_de_carga(otra, {lima: 7.0})

    leidas = {c["id"]: c for c in d.cargas_con_renglones([carga, otra])}
    assert set(leidas) == {carga, otra}
    assert leidas[carga]["renglones"] == {tomate: 40.0}
    assert leidas[carga]["margen"] == 15.0
    assert leidas[carga]["promedio_anterior_a"] == CARGADA_EL
    assert leidas[otra]["renglones"] == {lima: 7.0} and leidas[otra]["modo"] == "manual"
    assert leidas[carga]["cliente_nombre"].startswith("EJEMPLO Cliente")
    assert d.cargas_con_renglones([]) == []


def test_la_carga_trae_CUANTOS_RENGLONES_tiene_al_lado(galpon):
    """El denominador: "Día, 27/09, a mano" sin el conteo no distingue una
    carga cargada de una que se abrió y quedó vacía."""
    d, _sql, cliente, tomate, lima = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL, 0)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500, lima: 20})

    fila = next(c for c in d.listar_cargas_desde(EL_27) if c["id"] == carga_id)
    assert fila["renglones"] == 2 and fila["cliente_nombre"].startswith("EJEMPLO")


def test_el_promedio_recorta_ESTRICTO_y_el_dia_del_ancla_NO_entra(galpon):
    """EL RECORTE DE FECHA, contra Postgres de verdad.

    Sin él la consulta tomaba los últimos 6 por `fecha_operacion DESC`,
    FUTUROS INCLUIDOS: el pedido real del día que se va a comprar entraba al
    promedio y, con divisor 6, contaba como un sexto de sí mismo.

    Y EL CASO QUE DECIDE ES EL DEL DÍA DEL ANCLA, no el del futuro: el
    operador es `<` y no `<=`, así que el día en que se carga no entra. Con
    solo un pedido futuro plantado, un `<=` pasaría este test igual.
    """
    d, sql, cliente, tomate, _l = galpon
    (ficha,), = sql(
        "INSERT INTO fichas_logistica (articulo_id, cliente_id, unidad_venta, contenido_caja)"
        " VALUES (%s, %s, 'kilo', 10) RETURNING id", (tomate, cliente))

    def pedido(fecha, cantidad):
        (pedido_id,), = sql(
            "INSERT INTO pedidos (cliente_id, fecha_operacion, origen)"
            " VALUES (%s, %s, 'mail') RETURNING id", (cliente, fecha))
        sql("INSERT INTO pedidos_renglones (pedido_id, sucursal, articulo_id, ficha_id, cantidad)"
            " VALUES (%s, 'EJ', %s, %s, %s)", (pedido_id, tomate, ficha, cantidad))

    ancla = date(2026, 9, 22)
    pedido(ancla - timedelta(days=1), 10)   # ANTERIOR: entra
    pedido(ancla, 99)                       # EL DÍA DEL ANCLA: no entra
    pedido(ancla + timedelta(days=5), 99)   # FUTURO: no entra

    filas = d.renglones_de_los_ultimos_pedidos([cliente], ancla, 6)
    assert len(filas) == 1, f"entraron {len(filas)} de 1 renglón"
    assert float(filas[0]["bultos"]) == 10.0
    assert int(filas[0]["pedidos_del_cliente"]) == 1, (
        "el divisor cuenta pedidos de afuera de la ventana"
    )



# --- LAS PANTALLAS del Paso 1 -------------------------------------------------
#
# Mockeadas, como el resto de las rutas: acá lo que se mira es el CABLEADO
# —qué se guarda, a dónde redirige, qué dibuja— y no si el SQL parsea, que lo
# contestan los de arriba contra Postgres de verdad.

import os  # noqa: E402
import re  # noqa: E402
from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

import app.main as _main  # noqa: E402

_cliente = TestClient(_main.app)
_cliente.cookies.set(_main.PUERTA_COMPRAS.cookie, _main.PUERTA_COMPRAS.firma("compras-secreta"))

_CLIENTES = [{"id": 1, "nombre": "EJEMPLO Día"}]
_ARTICULOS = [
    {"id": 7, "nombre": "EJEMPLO Tomate", "unidad_conteo": None, "grupo": "hortalizas",
     "merma_porcentaje": 0, "unidad_compra": "kilo", "contenido_referencia": 16},
    {"id": 8, "nombre": "EJEMPLO Mango", "unidad_conteo": "unidad", "grupo": "frutas",
     "merma_porcentaje": 0, "unidad_compra": "unidad", "contenido_referencia": None},
    {"id": 9, "nombre": "EJEMPLO Sin magnitud", "unidad_conteo": "unidad", "grupo": None,
     "merma_porcentaje": 0, "unidad_compra": "unidad", "contenido_referencia": None},
    # EL RIVAL DE LOS BULTOS: mismo tipo de magnitud que el 7, pero el cliente
    # tiene ficha con contenido_caja. Sin él, "el número grande es bultos" no
    # se puede distinguir de "el número grande es la magnitud".
    {"id": 10, "nombre": "EJEMPLO Arándano", "unidad_conteo": None, "grupo": "frutas",
     "merma_porcentaje": 0, "unidad_compra": "kilo", "contenido_referencia": 4},
]
# El de magnitud imposible es el RIVAL: una ficha en 'cubeta' de un artículo
# cuyo conteo es 'unidad'. Sin él, "la pantalla dibuja un campo por artículo"
# pasa igual con la guarda sacada.
_FICHAS = [
    {"articulo_id": 7, "unidad_venta": "kilo", "unidad_conteo": None},
    {"articulo_id": 8, "unidad_venta": "unidad", "unidad_conteo": "unidad"},
    {"articulo_id": 9, "unidad_venta": "cubeta", "unidad_conteo": "unidad"},
    {"articulo_id": 10, "unidad_venta": "kilo", "unidad_conteo": None},
]
# LAS FICHAS DE ESTE CLIENTE, que son las que dicen cuánto entra en un bulto.
# Solo el 10 la tiene: el 7 se carga en su magnitud porque este cliente no
# tiene ficha suya, y ése es el par que hace legible la distinción.
_FICHAS_DEL_CLIENTE = [
    {"id": 40, "articulo_id": 10, "cliente_id": 1, "articulo_nombre": "EJEMPLO Arándano",
     "unidad_venta": "kilo", "unidad_conteo": None, "contenido_caja": 10,
     "nombre_cliente": None, "envase_id": None},
]


# Dos pedidos del mismo artículo, para que el divisor tenga algo que dividir:
# 3 pedidos en la historia del cliente, 300 bultos de 1 kilo -> 100 por día.
_RENGLONES_DE_PEDIDO = [
    {"cliente_id": 1, "articulo_id": 7, "bultos": 300, "contenido_caja": 1,
     "unidad_venta": "kilo", "unidad_conteo": None, "pedidos_del_cliente": 3},
    # Sin contenido_caja: no se puede pasar a la magnitud, así que NO se
    # propone. Es el rival — sin él, "un hueco deja el artículo afuera" pasa
    # igual con la guarda sacada.
    {"cliente_id": 1, "articulo_id": 8, "bultos": 60, "contenido_caja": None,
     "unidad_venta": "unidad", "unidad_conteo": "unidad", "pedidos_del_cliente": 3},
    # 30 bultos de 10 sobre 3 pedidos = 100 kilos por día = 10 bultos.
    {"cliente_id": 1, "articulo_id": 10, "bultos": 30, "contenido_caja": 10,
     "unidad_venta": "kilo", "unidad_conteo": None, "pedidos_del_cliente": 3},
]


def _con_catalogo(**extra):
    parches = {
        "app.main.listar_clientes": _CLIENTES,
        "app.main.listar_articulos": _ARTICULOS,
        "app.main.listar_fichas_de_todos_los_clientes": _FICHAS,
        "app.main.renglones_de_los_ultimos_pedidos": [],
        "app.main.listar_fichas_por_cliente": _FICHAS_DEL_CLIENTE,
        # Por default NO hay carga previa: el POST la lee para saber si lo
        # que llegó es un cambio de modo, y sin este parche se iría a la base
        # de verdad. El test que ejercita el cambio de modo la pone.
        "app.main.carga_de_compra": None,
    }
    parches.update(extra)
    contextos = [patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"})]
    contextos += [patch(nombre, return_value=valor) for nombre, valor in parches.items()]
    return contextos


def _entrar(contextos, metodo, ruta, **kwargs):
    """Devuelve la respuesta y los mocks POR NOMBRE.

    Por posición no: `abiertos[-1]` es el último que entró al diccionario de
    parches, y ese orden lo decide `dict.update` —una clave que ya estaba
    conserva su lugar— no el test. El test del ancla estaba leyendo el
    `call_args` de `carga_de_compra` creyendo mirar el del promedio, y pasó a
    fallar por un motivo que no era el suyo.
    """
    from contextlib import ExitStack
    with ExitStack() as pila:
        abiertos = [pila.enter_context(c) for c in contextos]
        respuesta = getattr(_cliente, metodo)(ruta, follow_redirects=False, **kwargs)
    # El primero es patch.dict(os.environ), que no tiene nombre de función.
    por_nombre = {}
    for contexto, mock in zip(contextos[1:], abiertos[1:]):
        por_nombre[getattr(contexto, "attribute", "") or str(contexto)] = mock
    return respuesta, por_nombre


def _carga(modo="manual", renglones=None, margen=0.0, por_bulto=None):
    # CON `por_bulto` COMO LO DEVUELVE LA BASE (un dict, vacío si nada se
    # declaró): un fixture sin la clave probaría una forma que producción no
    # tiene.
    return {"id": 3, "cliente_id": 1, "fecha": EL_27, "modo": modo, "margen": margen,
            "promedio_anterior_a": CARGADA_EL, "renglones": renglones or {},
            "por_bulto": por_bulto or {}}


def test_abrir_una_carga_QUE_YA_EXISTE_PREGUNTA_en_vez_de_crear_otra():
    """Lo pidió el dueño así: ni una segunda que sume doble ni abrir la vieja
    en silencio. Las dos salidas son legítimas y las dos borran trabajo."""
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga()})
    ctx.append(patch("app.main.guardar_carga_de_compra"))
    respuesta, abiertos = _entrar(ctx, "post", "/compras/carga",
                                  data={"cliente_id": "1", "fecha": EL_27.isoformat(),
                                        "modo": "manual"})
    guardar = abiertos["guardar_carga_de_compra"]
    assert respuesta.status_code == 200, "redirigió en vez de preguntar"
    marcado = respuesta.text.split("</style>")[-1]
    assert "Editar la que está" in marcado and "Borrar y empezar de cero" in marcado
    guardar.assert_not_called()


def test_abrir_una_carga_QUE_NO_EXISTE_la_crea_con_el_ancla_de_HOY():
    ctx = _con_catalogo(**{"app.main.carga_de_compra": None})
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    respuesta, abiertos = _entrar(ctx, "post", "/compras/carga",
                                  data={"cliente_id": "1", "fecha": EL_27.isoformat(),
                                        "modo": "automatico"})
    guardar = abiertos["guardar_carga_de_compra"]
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == f"/compras/carga/1/{EL_27.isoformat()}"
    cliente_id, fecha, modo, ancla, margen = guardar.call_args.args
    assert (cliente_id, fecha, modo) == (1, EL_27, "automatico")
    assert ancla == _main._hoy_argentina(), "el ancla no es el día en que se carga"
    assert margen == _main.MARGEN_SUGERIDO, "una carga nueva no nace con el sugerido"


def test_la_pantalla_dibuja_un_campo_POR_ARTICULO_con_SU_unidad():
    """El total va en la unidad del ARTÍCULO y el rótulo la nombra: la
    magnitud viaja con el número."""
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(renglones={7: 500.0})})
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    marcado = respuesta.text.split("</style>")[-1]
    assert respuesta.status_code == 200
    assert 'name="total_7"' in marcado and 'value="500"' in marcado
    assert 'name="total_8"' in marcado
    # El rival: sin magnitud no hay campo, porque cualquier número ahí estaría
    # en una unidad y se sumaría en otra.
    assert 'name="total_9"' not in marcado, "dibujó campo para el que no tiene magnitud"
    assert "no se puede cargar" in marcado


def test_lo_que_queda_IGUAL_A_LA_PROPUESTA_no_se_guarda():
    """SE DIO VUELTA EL 23/09, y el que estaba era el guardián de un hueco.

    Decía que en automático el guardado no tocaba los renglones — cierto
    mientras el modo no propusiera nada, que es justo lo que estaba mal: la
    pantalla salía idéntica a la de a mano y el modo no significaba nada.

    Ahora los dos modos escriben, y lo que los separa es ESTO: un artículo
    que quedó igual a lo que el promedio propuso NO se guarda, así que se
    vuelve a calcular al armar el listado; uno corregido queda fijo.
    """
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
        data={"modo": "automatico",
              "total_7": "500", "propuesto_7": "500",    # sin tocar
              "total_8": "120", "propuesto_8": "90"})    # corregido
    assert abiertos["guardar_renglones_de_carga"].call_args.args[1] == {8: 120.0}


def test_un_articulo_AGREGADO_a_una_carga_automatica_se_guarda():
    """El que el promedio no propuso no tiene `propuesto_`, así que no hay
    contra qué compararlo: cualquier número ahí lo puso una persona."""
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
        data={"modo": "automatico", "total_7": "500", "propuesto_7": "500",
              "total_8": "40"})
    assert abiertos["guardar_renglones_de_carga"].call_args.args[1] == {8: 40.0}


def test_en_modo_A_MANO_los_totales_llegan_y_el_VACIO_no_se_guarda_en_cero():
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    respuesta, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
        data={"modo": "manual", "total_7": "500", "total_8": "", "total_9": "0"})
    guardar_renglones = abiertos["guardar_renglones_de_carga"]
    assert respuesta.status_code == 303, "dibujó en vez de redirigir"
    assert guardar_renglones.call_args.args[1] == {7: 500.0}


def test_borrar_una_carga_QUE_UN_LISTADO_USO_avisa_en_vez_de_tirar_500():
    """La base la frena y el código traduce: un 500 le dice al comprador que
    el sistema se rompió, cuando lo que pasó es que la carga está en uso."""
    ctx = _con_catalogo()
    ctx.append(patch("app.main.borrar_carga_de_compra",
                     side_effect=Exception("listados_compra_cargas_carga_id_fkey")))
    respuesta, _ = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}/borrar")
    assert respuesta.status_code == 303
    assert "no+se+puede+borrar" in respuesta.headers["location"]


def test_la_lista_de_entrada_MARCA_la_carga_que_ya_se_uso():
    """El aviso, no una traba: se puede sumar de nuevo y decide el comprador."""
    usada = {"id": 3, "cliente_id": 1, "cliente_nombre": "EJEMPLO Día", "fecha": EL_27,
             "modo": "manual", "promedio_anterior_a": CARGADA_EL, "renglones": 2,
             "usada_en_otros": 1, "ultimo_listado": date(2026, 9, 26)}
    ctx = _con_catalogo(**{"app.main.listar_cargas_desde": [usada]})
    respuesta, _ = _entrar(ctx, "get", "/compras/carga")
    marcado = respuesta.text.split("</style>")[-1]
    assert respuesta.status_code == 200
    assert "ya se usó en el listado del 26/09" in marcado
    assert f'href="/compras/carga/1/{EL_27.isoformat()}"' in marcado


# --- EL LARGO DE LOS NOMBRES, que no lo controlamos --------------------------


def _medir(html):
    # pytest.importorskip y no un try: sin playwright estos dos se SALTEAN en
    # vez de fallar, y sus llamadores no tienen de qué acordarse.
    pytest.importorskip("playwright", reason="la medición de layout necesita un navegador")
    from scripts.medir_layout import medir_sync

    return medir_sync(html, ancho=390, selector_filas=".tarjeta")


def _pantalla_de_carga(nombre):
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(renglones={7: 500.0}),
        "app.main.listar_articulos": [dict(_ARTICULOS[0], nombre=nombre)],
        "app.main.listar_fichas_de_todos_los_clientes": [_FICHAS[0]],
        "app.main.listar_clientes": [{"id": 1, "nombre": nombre}],
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    return respuesta


@pytest.mark.parametrize("nombre", [
    "Tomate Perita",                          # el caso cómodo
    "Zapallitoredondodeltronco" * 3,          # 75 caracteres SIN UN ESPACIO
])
def test_la_carga_no_se_ARRASTRA_de_costado_a_390px(nombre):
    """VA EL PAR COMPLETO —el nombre normal y el impartible— porque un arreglo
    que rompa el caso cómodo para aguantar el raro pasaría el primero sin que
    nada caiga.

    Y una palabra sin espacios NO ENVUELVE: se desborda. Por eso lo que se
    mira es el desborde y no el quiebre — un detector de quiebre solo la
    habría dado por buena.

    Y EL DESBORDE SE LEE COMO LO LEE `imprimir`, con las dos claves: cuando
    el selector de filas no encuentra ninguna, `medir` devuelve `desborde: 0`
    LITERAL y el número real viaja en `desborde_pagina`. O sea que leer una
    sola clave da un cero prolijo sobre una pantalla que nunca se midió
    (corolario 47, adentro del resultado). Por eso van también los dos
    denominadores: `filas` dice que el selector encontró algo y `pares` que
    hubo qué comparar.
    """
    respuesta = _pantalla_de_carga(nombre)
    assert respuesta.status_code == 200, "se midió otra pantalla"
    medicion = _medir(respuesta.text)
    # Los denominadores: sin esto, "no desborda" y "no se miró nada" se
    # imprimen igual (corolario 45).
    assert medicion["filas"] > 0 and medicion["pares"] > 0, "no se midió nada"
    desborde = medicion.get("desborde_pagina", medicion["desborde"])
    assert desborde == 0, (
        f"la pantalla se arrastra {desborde}px con el nombre «{nombre[:20]}…»"
    )
    assert medicion["solapes"] == [], f"hay cajas que se pisan: {medicion['solapes']}"


# --- EL PROMEDIO EN LA PANTALLA -----------------------------------------------
#
# Lo que faltaba y lo encontró el dueño usándola: "Del promedio" dibujaba la
# lista vacía, idéntica a la de a mano, así que el modo no significaba nada.
# El promedio se calculaba —en el Paso 2— y el Paso 1 nunca lo pedía.


def test_DEL_PROMEDIO_trae_los_numeros_a_la_pantalla():
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico"),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    marcado = respuesta.text.split("</style>")[-1]
    assert respuesta.status_code == 200
    # 300 bultos de 1 kilo sobre 3 pedidos = 100 por día.
    assert 'name="total_7"' in marcado and 'value="100"' in marcado
    assert 'name="propuesto_7"' in marcado, "sin esto no hay contra qué comparar al guardar"
    # CORRIDO: el wrap de la plantilla parte la frase, y chequear "por
    # partes" solo posterga el problema hasta que la frase crezca.
    corrido = " ".join(marcado.split())
    assert "Lo que no toques se vuelve a calcular" in corrido


def test_un_articulo_SIN_MAGNITUD_no_se_propone_a_medias():
    """Proponer la suma de los demás diría que ese cliente pide menos de lo
    que pide. El rival está en el fixture: el 8 viene sin contenido_caja."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico"),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'name="propuesto_8"' not in marcado


def test_el_promedio_se_pide_con_el_ANCLA_de_la_carga_y_no_con_hoy():
    """El ancla es el día en que se abrió la carga. Pedirlo con hoy correría
    la ventana sola cada vez que se abre la pantalla, que es exactamente lo
    que guardar la columna vino a impedir."""
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(modo="automatico")})
    _, abiertos = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    pedidos = abiertos["renglones_de_los_ultimos_pedidos"]
    assert pedidos.call_args.args[1] == CARGADA_EL, "el promedio se pidió con otra fecha"


def test_A_MANO_arranca_VACIA_y_los_demas_llegan_ESCONDIDOS():
    """38 artículos con un campo cada uno es lo que hace que la pantalla no se
    pueda usar con el pulgar. Están en el DOM para que el buscador los traiga
    sin ir al server, y arrancan `hidden`.

    SE MIRA EL ATRIBUTO EN SU FILA y no `"hidden" in marcado`: el atributo es
    la intención y hay que ver en cuál de las filas cayó.
    """
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(renglones={7: 500.0})})
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    marcado = respuesta.text.split("</style>")[-1]
    filas = re.findall(r'<div class="fila"[^>]*data-articulo="(\d+)"([^>]*)>', marcado)
    # El denominador: sin esto un regex roto deja la lista vacía y los dos
    # asserts de abajo pasan sobre nada (corolario 45).
    assert len(filas) == len(_ARTICULOS), f"se encontraron {len(filas)} de {len(_ARTICULOS)} filas"
    escondidas = {a for a, resto in filas if "hidden" in resto}
    assert escondidas == {"8", "9", "10"}, "la carga a mano no arrancó con solo lo cargado"


def test_el_buscador_AGREGA_en_vez_de_filtrar_una_lista_entera():
    """El botón que agrega lleva type="button": sin eso, tocarlo ENVÍA el
    formulario y la carga se guarda a medias en vez de sumar el artículo."""
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(renglones={7: 500.0})})
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    assert 'boton.type = "button"' in respuesta.text
    assert "f.hidden && f.dataset.nombre.indexOf(texto)" in respuesta.text, (
        "el buscador dejó de ofrecer SOLO las que no están puestas"
    )


def test_una_CORRECCION_dice_contra_que_se_corrigio():
    """Al reabrir, el campo muestra lo corregido. Sin el número del promedio
    al lado no hay forma de saber que se movió desde entonces."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico", renglones={7: 120.0}),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'value="120"' in marcado, "no mostró lo corregido"
    assert "el promedio dice 100 kg" in marcado, "no dijo contra qué se corrigió"


def test_lo_que_NO_se_corrigio_no_lleva_el_cartel():
    """El rival: si el cartel saliera siempre, no distinguiría una corrección
    de una propuesta aceptada — que es justo lo que viene a decir."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico"),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    # LA LEYENDA DE HOY, no la vieja: con "prom. " este assert pasaba siempre
    # desde que el texto cambió, que es el assert por la negativa que no
    # puede fallar.
    assert "el promedio dice" not in respuesta.text.split("</style>")[-1]


# --- BULTOS, que es como piensa el que compra --------------------------------


def _campo(corrido, nombre):
    """El `<input>` entero de ese nombre, para leer su value sin confundirlo con el de al lado."""
    return corrido.split(f'name="{nombre}"')[1].split(">")[0]


def test_la_fila_DIBUJA_LOS_TRES_numeros_y_de_donde_sale_el_por_bulto():
    """"Hoy no sé de dónde sale el número que veo ni en qué unidad está"
    (dueño, 23/09). Kilos en total, bultos y kilos por bulto, cada uno con su
    rótulo, y una línea que dice de dónde sale el por bulto.

    100 kilos por día sobre un bulto de 10 de la ficha = 10 bultos. La
    propuesta viaja en KILOS, que es lo que se guarda y lo que el listado suma.
    """
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico"),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    assert 'value="100"' in _campo(corrido, "total_10")
    assert 'value="10"' in _campo(corrido, "bultos_10")
    assert 'value="10"' in _campo(corrido, "por_bulto_10")
    assert 'name="propuesto_10" value="100"' in corrido, "la propuesta viaja en KILOS"
    assert "Kg en total" in corrido and "Kg por bulto" in corrido
    assert "Por bulto: el de la ficha de EJEMPLO Día" in corrido


def test_SIN_ficha_del_cliente_el_POR_BULTO_arranca_VACIO_y_lo_dice():
    """El rival. La carga va contra el catálogo de compra, así que un
    artículo que este cliente no tiene en ficha se carga igual — y ahí no hay
    con qué dividir. Los tres campos están, el por bulto vacío, y la pantalla
    dice qué falta en vez de inventar un bulto."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico"),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    assert 'value="100"' in _campo(corrido, "total_7")
    assert 'value=""' in _campo(corrido, "bultos_7")
    assert 'value=""' in _campo(corrido, "por_bulto_7")
    assert "Sin ficha de EJEMPLO Día: poné cuánto trae un bulto" in corrido


def test_un_POR_BULTO_GUARDADO_le_gana_a_la_ficha_y_la_pantalla_lo_dice():
    """Si el que cargó puso 20 donde la ficha dice 10, al reabrir ve SUS
    bultos: 200 kilos son 10 bultos de 20, no 20 de 10."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(renglones={10: 200.0}, por_bulto={10: 20.0}),
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    assert 'value="20"' in _campo(corrido, "por_bulto_10")
    assert 'value="10"' in _campo(corrido, "bultos_10")
    assert "Por bulto: lo pusiste vos (la ficha dice 10)" in corrido


def test_los_BULTOS_tipeados_se_guardan_en_la_MAGNITUD():
    """La columna guarda UNA unidad. Lo que se tipea son bultos y lo que se
    guarda es la magnitud, y la conversión la hace el SERVER con la ficha —
    no un campo escondido, que un POST armado a mano podría cambiar."""
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
                          data={"modo": "manual", "bultos_10": "12"})
    assert abiertos["guardar_renglones_de_carga"].call_args.args[1] == {10: 120.0}


def test_un_bultos_de_un_articulo_SIN_contenido_no_entra():
    """Bultos solos, sin ficha y sin por bulto tipeado, no dicen cuántos kilos
    son: no se guarda con una conversión inventada."""
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
                          data={"modo": "manual", "bultos_7": "12", "total_10": "99"})
    assert abiertos["guardar_renglones_de_carga"].call_args.args[1] == {10: 99.0}


# --- "Apreto Guardar y no pasa nada" -----------------------------------------


def test_GUARDAR_lleva_a_LA_LISTA_y_no_deja_la_pantalla_igual():
    """Guardaba bien; lo que no pasaba es que se viera. El aviso es una
    tarjeta ARRIBA y el botón está abajo, así que en una carga larga la
    pantalla vuelve a dibujarse igual y el cartel queda fuera de la vista.
    Otra pantalla es la única señal que no se puede perder de vista."""
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    respuesta, _ = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
                           data={"modo": "manual", "total_7": "500"})
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/carga?aviso=Carga+guardada"


def test_CAMBIAR_DE_MODO_no_toca_los_renglones_y_vuelve_a_la_carga():
    """Los campos que llegan son los que la pantalla dibujó para el modo
    VIEJO: pasando de a mano a del promedio no traen su `propuesto_` al lado,
    así que se leerían como correcciones y quedarían TODOS fijos — el
    promedio no volvería a proponer nada nunca."""
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(modo="manual")})
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    respuesta, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
        data={"modo": "automatico", "total_7": "500", "bultos_10": "12"})
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].endswith("?aviso=Pasada+a+Del+promedio")
    abiertos["guardar_renglones_de_carga"].assert_not_called()
    assert abiertos["guardar_carga_de_compra"].call_args.args[2] == "automatico"


# --- EL MARGEN, uno solo y por carga -----------------------------------------
#
# Del dueño (23/09): "si los dos se multiplican, termino comprando 32% de más
# sin darme cuenta". Por eso vive acá y no en el listado: 1,20 × 1,10 = 1,32 y
# nadie hace esa cuenta con el pulgar.


def test_el_margen_INFLA_lo_que_propone_el_promedio():
    """Con `con_margen`, que es la misma función del Paso 2 —sobre LO QUE
    PIDEN y no sobre el faltante—. Escrita a mano serían dos márgenes, y la
    copia que se separe infla distinto y los dos números son plausibles."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico", margen=20.0),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    # 100 kilos de promedio, 20% más = 120.
    assert 'name="propuesto_10" value="120"' in corrido
    assert 'name="margen" type="number"' in corrido


def test_la_fila_lleva_la_BASE_SIN_margen_para_recalcular_sin_ir_al_server():
    """"Recalcula los bultos al toque" (dueño, 23/09). Sin la base, mover el
    porcentaje tendría que pasar por un guardado."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico", margen=20.0),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    assert 'data-base="100"' in corrido, "la fila no trae el promedio crudo"
    # Y el JS solo mueve lo que TODAVÍA muestra lo propuesto: sin eso, subir
    # el porcentaje pisaría las correcciones.
    assert "campo.value !== espejo.value" in respuesta.text


def test_el_margen_SE_GUARDA():
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
                          data={"modo": "automatico", "margen": "25"})
    assert abiertos["guardar_carga_de_compra"].call_args.args[4] == 25.0


def test_CAMBIAR_DE_MODO_conserva_el_margen():
    """El modo se cambia sin tocar nada más: el margen que llega en el
    formulario es el del modo viejo y no hay por qué creerle más que a la
    fila guardada."""
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(modo="manual", margen=20.0)})
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
                          data={"modo": "automatico", "margen": "99"})
    assert abiertos["guardar_carga_de_compra"].call_args.args[4] == 20.0


def test_A_MANO_no_muestra_el_margen_y_DEL_PROMEDIO_si():
    """El margen va solo sobre lo que el promedio propone (dueño, 23/09): en
    "a mano" no movería nada, y un campo sin consecuencia invita a creer que
    hizo algo."""
    def campo(modo):
        ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(modo=modo, margen=20.0)})
        respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
        # El input ENTERO y no el nombre suelto: el JS dice getElementById("margen").
        return 'id="margen" name="margen"' in respuesta.text.split("</style>")[-1]
    assert campo("automatico") is True
    assert campo("manual") is False


def test_guardar_A_MANO_sin_el_campo_CONSERVA_el_margen_que_tenia():
    """El campo no se dibuja en "a mano", así que no llega. El rival es leerlo
    igual con `margen_valido`: lo pisaría con el sugerido, y al volver a "del
    promedio" la carga aparecería con un margen que nadie eligió."""
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(modo="manual", margen=20.0)})
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
                          data={"modo": "manual", "total_7": "40"})
    assert abiertos["guardar_carga_de_compra"].call_args.args[4] == 20.0


def test_una_CORRECCION_no_lleva_el_margen_encima():
    """Lo corregido se corrige MIRANDO la propuesta que ya tiene el margen:
    inflarlo de nuevo le cobra el margen dos veces. Con 20%: el 7 guardado se
    muestra 7, no 8,4."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico", margen=20.0, renglones={7: 7.0}),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    assert 'name="total_7"' in corrido
    campo = corrido.split('name="total_7"')[1].split(">")[0]
    assert 'value="7"' in campo, campo


def test_la_CARGA_y_el_LISTADO_calculan_lo_que_se_pide_con_la_MISMA_funcion():
    """La regla está escrita una vez (`lo_que_pide_la_carga`) y las dos
    pantallas la LLAMAN. Si una la reescribe, el listado compra otra cosa que
    la que el comprador vio en la carga — y los dos números son plausibles.

    Pregunta por la LLAMADA en el árbol y no por el nombre en el texto: el
    docstring de cada una nombra la regla para explicarla (corolario 59).
    """
    import ast
    import inspect
    import textwrap
    import app.main as m

    def llama(funcion, nombre):
        arbol = ast.parse(textwrap.dedent(inspect.getsource(funcion)))
        return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == nombre for n in ast.walk(arbol))

    for funcion in (m._articulos_para_cargar, m._contexto_de_que_comprar):
        assert llama(funcion, "lo_que_pide_la_carga"), funcion.__name__
    # Y el modo se decide en UN lugar: el listado no puede llamar al promedio
    # directo, o le sumaría el promedio a una carga "a mano".
    assert llama(m._contexto_de_que_comprar, "_propuesto_de_la_carga")
    assert not llama(m._contexto_de_que_comprar, "_promedio_por_articulo")
    assert llama(m._contexto_de_carga, "_propuesto_de_la_carga")


def test_A_MANO_no_pide_el_promedio():
    from app.main import _propuesto_de_la_carga
    with patch("app.main._promedio_por_articulo", return_value={1: 99.0}) as promedio:
        assert _propuesto_de_la_carga(_carga(modo="manual")) == {}
        assert not promedio.called
        assert _propuesto_de_la_carga(_carga(modo="automatico")) == {1: 99.0}


def test_un_margen_en_CERO_deja_la_propuesta_como_esta():
    """0 significa sin margen y es distinto de vacío — el rival del sugerido:
    un `or MARGEN_SUGERIDO` le pondría 10 a quien pidió ninguno."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico", margen=0.0),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    assert 'name="propuesto_10" value="100"' in corrido


# --- LOS TRES NÚMEROS AL GUARDAR (dueño, 23/09) ------------------------------


def _guardar(datos, carga=None):
    ctx = _con_catalogo(**({"app.main.carga_de_compra": carga} if carga else {}))
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}", data=datos)
    llamada = abiertos["guardar_renglones_de_carga"].call_args
    return llamada.args[1], llamada.args[2]


def test_el_TOTAL_manda_y_un_POR_BULTO_distinto_de_la_ficha_se_GUARDA():
    """500 kilos de a 20 donde la ficha dice 10: se guardan los 500 y el 20."""
    renglones, por_bulto = _guardar({"modo": "manual", "total_10": "500",
                                     "bultos_10": "25", "por_bulto_10": "20"})
    assert renglones == {10: 500.0}
    assert por_bulto == {10: 20.0}


def test_un_POR_BULTO_IGUAL_al_de_la_ficha_NO_se_guarda():
    """Igual al de la ficha es "no lo toqué". Guardarlo lo dejaría fijo el día
    que la ficha cambie; NULL es exactamente "proponé el de la ficha"."""
    renglones, por_bulto = _guardar({"modo": "manual", "total_10": "500",
                                     "por_bulto_10": "10"})
    assert renglones == {10: 500.0}
    assert por_bulto == {}


def test_SIN_TOTAL_se_saca_de_BULTOS_por_el_POR_BULTO_tipeado():
    """El camino sin JavaScript: 25 bultos de 20 son 500 kilos, aunque la
    ficha diga 10. El rival —multiplicar por la ficha— daría 250."""
    renglones, por_bulto = _guardar({"modo": "manual", "bultos_10": "25",
                                     "por_bulto_10": "20"})
    assert renglones == {10: 500.0}
    assert por_bulto == {10: 20.0}


def test_un_articulo_SIN_ficha_con_POR_BULTO_tipeado_se_guarda_con_el():
    """Sin ficha, cualquier por bulto es declarado: no hay contra qué comparar."""
    renglones, por_bulto = _guardar({"modo": "manual", "bultos_7": "5",
                                     "por_bulto_7": "18"})
    assert renglones == {7: 90.0}
    assert por_bulto == {7: 18.0}


def test_en_DEL_PROMEDIO_cambiar_SOLO_el_por_bulto_es_una_CORRECCION():
    """El total quedó igual a la propuesta pero el por bulto no: el que cargó
    decidió algo, y eso se guarda. El rival —mirar solo el total— lo tiraría."""
    renglones, por_bulto = _guardar(
        {"modo": "automatico", "total_10": "100", "propuesto_10": "100",
         "por_bulto_10": "20"},
        carga=_carga(modo="automatico"))
    assert renglones == {10: 100.0}
    assert por_bulto == {10: 20.0}


def test_en_DEL_PROMEDIO_lo_que_quedo_IGUAL_no_se_guarda_ni_el_por_bulto():
    """El caso que no tiene que guardar nada, sin el cual una regla que
    guarda todo pasaría los tres de arriba."""
    renglones, por_bulto = _guardar(
        {"modo": "automatico", "total_10": "100", "propuesto_10": "100",
         "bultos_10": "10", "por_bulto_10": "10"},
        carga=_carga(modo="automatico"))
    assert renglones == {} and por_bulto == {}


def _en_el_navegador(html, pasos):
    """Tipea en la primera fila visible y devuelve lo que quedó en los tres campos."""
    pytest.importorskip("playwright", reason="el recálculo en vivo necesita un navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        for selector, valor in pasos:
            pagina.fill(selector, valor)
        leido = pagina.evaluate("""() => ({
            total: document.querySelector('[name="total_10"]').value,
            bultos: document.querySelector('[name="bultos_10"]').value,
            por_bulto: document.querySelector('[name="por_bulto_10"]').value,
            ancho: document.documentElement.scrollWidth - document.documentElement.clientWidth})""")
        navegador.close()
    return leido


def _pantalla_con_arandano():
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(renglones={10: 100.0})})
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    assert respuesta.status_code == 200
    return respuesta.text


@pytest.mark.parametrize("pasos, esperado", [
    # "Pongo 500 kilos y 20 kilos por bulto -> me muestra 25 bultos."
    ([('[name="por_bulto_10"]', "20"), ('[name="total_10"]', "500")],
     {"total": "500", "bultos": "25", "por_bulto": "20"}),
    # "O pongo 25 bultos y 20 por bulto -> me muestra 500 kilos."
    ([('[name="por_bulto_10"]', "20"), ('[name="bultos_10"]', "25")],
     {"total": "500", "bultos": "25", "por_bulto": "20"}),
    # Cambiar el por bulto deja los bultos y rehace el total: 10 bultos de 25.
    ([('[name="por_bulto_10"]', "25")],
     {"total": "250", "bultos": "10", "por_bulto": "25"}),
])
def test_los_TRES_campos_se_AJUSTAN_solos_al_tipear(pasos, esperado):
    """Los dos ejemplos del dueño, al pie de la letra, más el tercer campo.
    Arranca con 100 kilos de a 10 = 10 bultos (la ficha del arándano)."""
    leido = _en_el_navegador(_pantalla_con_arandano(), pasos)
    assert {k: leido[k] for k in esperado} == esperado
    assert leido["ancho"] <= 0, "la fila arrastra la pantalla de costado"


# --- SUBIR ARCHIVO: se lee, se revisa, se corrige, y recién ahí se guarda ----
#
# LAS RUTAS SON POST, así que el humo no las abre: estos tests son lo único
# que mira que la revisión se dibuje. El archivo NO SE GUARDA (dueño, 22/09):
# es una herramienta para tipear más rápido y lo que vale es lo revisado.

_LEIDO = {"items": [
    {"articulo": "EJEMPLO Arandano", "cantidad": 12, "confianza": "alta"},
    {"articulo": "Algo que no existe", "cantidad": 5, "confianza": "baja"},
]}


def _subir(ctx, datos_leidos=None, archivo=("listado.xlsx", b"x")):
    ctx = list(ctx)
    ctx.append(patch("app.main._extraer_carga_de_archivo",
                     return_value=datos_leidos if datos_leidos is not None else _LEIDO))
    from contextlib import ExitStack
    with ExitStack() as pila:
        abiertos = [pila.enter_context(c) for c in ctx]
        respuesta = _cliente.post(
            f"/compras/carga/1/{EL_27.isoformat()}/archivo",
            files={"archivo": (archivo[0], archivo[1], "application/octet-stream")},
            follow_redirects=False)
    return respuesta, abiertos


def test_el_archivo_se_LEE_y_abre_la_REVISION_sin_guardar_nada():
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    respuesta, abiertos = _subir(ctx)
    marcado = respuesta.text.split("</style>")[-1]
    assert respuesta.status_code == 200, "redirigió en vez de mostrar la revisión"
    assert "Todavía no se guardó" in " ".join(marcado.split())
    assert abiertos[-2].call_count == 0, "guardó antes de que nadie revisara"
    # El que matcheó llega con su artículo elegido.
    assert 'value="10" data-unidad="blt" selected' in " ".join(marcado.split())


def test_un_renglon_SIN_ARTICULO_llega_marcado_y_no_elegido():
    """El rival del test de arriba: sin un renglón que NO matchee, "la
    pantalla marca los que faltan" pasa igual con la marca sacada."""
    ctx = _con_catalogo()
    respuesta, _ = _subir(ctx)
    marcado = respuesta.text.split("</style>")[-1]
    assert "No hay artículo que le corresponda" in marcado
    assert "no se leyó bien, mirala" in marcado, "no marcó la confianza baja"


def test_el_ALIAS_del_cliente_es_lo_que_matchea_su_listado():
    """El nombre con que ÉL llama al artículo es el alias más preciso que
    existe, y el único que puede reconocer su listado."""
    fichas = [dict(_FICHAS_DEL_CLIENTE[0], nombre_cliente="ARAND. BANDEJA")]
    ctx = _con_catalogo(**{"app.main.listar_fichas_por_cliente": fichas})
    respuesta, _ = _subir(ctx, {"items": [
        {"articulo": "ARAND. BANDEJA", "cantidad": 7, "confianza": "alta"}]})
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    assert 'value="10" data-unidad="blt" selected' in corrido


def test_un_archivo_que_NO_se_reconoce_avisa_en_vez_de_romper():
    ctx = _con_catalogo()
    respuesta, _ = _subir(ctx, archivo=("listado.docx", b"x"))
    assert respuesta.status_code == 303
    assert "No+se+reconoci" in respuesta.headers["location"]


def test_CONFIRMAR_guarda_en_la_MAGNITUD_y_deja_la_carga_A_MANO():
    """Lo que se tipea son bultos cuando la ficha dice cuánto entra en uno; la
    conversión la hace el server. Y subir un archivo es DECLARAR lo que pide,
    así que la carga queda a mano."""
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    respuesta, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}/archivo/confirmar",
        data={"cantidad_renglones": "2",
              "articulo_10": "x",            # ruido: no es un campo del form
              "articulo_0": "10", "cantidad_0": "12", "texto_0": "Arandano",
              "articulo_1": "7", "cantidad_1": "50", "texto_1": "Tomate"})
    assert respuesta.status_code == 303
    # El 10 tiene bulto de 10 -> 120 en magnitud; el 7 no tiene ficha -> tal cual.
    assert abiertos["guardar_renglones_de_carga"].call_args.args[1] == {10: 120.0, 7: 50.0}
    assert abiertos["guardar_carga_de_compra"].call_args.args[2] == "manual"


def test_DOS_renglones_del_mismo_articulo_se_SUMAN():
    """Un listado que nombra el tomate dos veces. Un diccionario por artículo
    se quedaría con uno solo, en silencio — y los dos están a la vista con su
    número en la pantalla."""
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}/archivo/confirmar",
        data={"cantidad_renglones": "2",
              "articulo_0": "7", "cantidad_0": "30", "texto_0": "Tomate",
              "articulo_1": "7", "cantidad_1": "20", "texto_1": "Tomate perita"})
    assert abiertos["guardar_renglones_de_carga"].call_args.args[1] == {7: 50.0}


def test_un_renglon_TIRADO_no_entra():
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}/archivo/confirmar",
        data={"cantidad_renglones": "2",
              "articulo_0": "7", "cantidad_0": "30", "texto_0": "Tomate",
              "articulo_1": "8", "cantidad_1": "20", "descartar_1": "on", "texto_1": "Mango"})
    assert abiertos["guardar_renglones_de_carga"].call_args.args[1] == {7: 30.0}


def test_DAR_DE_ALTA_crea_el_articulo_y_NO_PIERDE_la_revision():
    """Mandarlo a /compras/articulos y volver significaría SUBIR EL ARCHIVO DE
    NUEVO — la revisión costó una lectura con IA."""
    nuevo = dict(_ARTICULOS[0], id=77, nombre="EJEMPLO Radicheta")
    ctx = _con_catalogo(**{"app.main.listar_articulos": _ARTICULOS + [nuevo]})
    ctx.append(patch("app.main.crear_articulo", return_value=77))
    respuesta, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}/archivo/articulo",
        data={"cantidad_renglones": "2", "fila_del_alta": "1",
              "articulo_nuevo": "EJEMPLO Radicheta",
              "articulo_0": "7", "cantidad_0": "30", "texto_0": "Tomate",
              "articulo_1": "", "cantidad_1": "5", "texto_1": "Radicheta"})
    corrido = " ".join(respuesta.text.split("</style>")[-1].split())
    assert respuesta.status_code == 200, "salió de la revisión"
    assert abiertos["crear_articulo"].call_args.args[0] == "EJEMPLO Radicheta"
    # SIN contenido_referencia: un artículo nuevo no tiene valor dominante.
    assert abiertos["crear_articulo"].call_args.args[1] is None
    assert "quedó dado de alta" in corrido
    # Y la revisión vuelve ENTERA, con el nuevo elegido en SU renglón.
    assert 'value="30"' in corrido and 'value="5"' in corrido
    assert 'value="77" data-unidad="kg" selected' in corrido


# --- LO QUE SE VE, y no lo que dice el atributo -------------------------------
#
# Del 23/09, y lo encontró el dueño usándola: "no me muestres los artículos en
# cero, son decenas de filas vacías". Las filas llevaban `hidden` bien puesto
# —el test de arriba lo confirma y pasaba— y se veían igual, en los DOS modos:
# `.fila { display: flex }` le gana al `[hidden]` del navegador. Es el
# corolario 32 al pie de la letra, así que esto se mide en un navegador.


def _filas_que_se_ven(html, buscar=None):
    pytest.importorskip("playwright", reason="lo que se ve necesita un navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        if buscar:
            pagina.fill("#buscar", buscar)
            pagina.click("#hallazgos button")
        resultado = pagina.evaluate("""() => {
          const f = [...document.querySelectorAll('.fila[data-articulo]')];
          return {total: f.length,
                  visibles: f.filter(x => getComputedStyle(x).display !== 'none')
                             .map(x => x.dataset.articulo)};
        }""")
        navegador.close()
    return resultado


def _pantalla(modo, renglones_de_pedido=_RENGLONES_DE_PEDIDO):
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga(modo=modo),
                           "app.main.renglones_de_los_ultimos_pedidos": renglones_de_pedido})
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    assert respuesta.status_code == 200, "se midió otra pantalla"
    return respuesta.text


def test_DEL_PROMEDIO_se_ven_SOLO_los_que_encontro_en_los_6_pedidos():
    """El 7 y el 10 salen del promedio; el 8 no tiene magnitud y el 9 nadie
    lo pidió. Con el CSS roto se ven los cuatro."""
    medicion = _filas_que_se_ven(_pantalla("automatico"))
    # El denominador: cuatro filas en el DOM, así el buscador tiene qué traer.
    assert medicion["total"] == len(_ARTICULOS)
    assert sorted(medicion["visibles"]) == ["10", "7"]


def test_A_MANO_arranca_sin_ninguna_fila_a_la_vista():
    medicion = _filas_que_se_ven(_pantalla("manual"))
    assert medicion["total"] == len(_ARTICULOS)
    assert medicion["visibles"] == []


def test_un_articulo_que_el_promedio_da_en_CERO_no_se_muestra_y_se_puede_AGREGAR():
    """El pedido del dueño son las dos mitades: el cero no aparece, y si hace
    falta se trae con el buscador. La segunda es la que hace que esconderlo no
    sea perderlo."""
    en_cero = [dict(_RENGLONES_DE_PEDIDO[0], bultos=0)] + _RENGLONES_DE_PEDIDO[1:]
    html = _pantalla("automatico", en_cero)
    assert sorted(_filas_que_se_ven(html)["visibles"]) == ["10"]
    agregado = _filas_que_se_ven(html, buscar="tomate")
    assert sorted(agregado["visibles"]) == ["10", "7"], "el buscador no lo trajo"
