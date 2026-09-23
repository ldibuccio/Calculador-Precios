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
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL)
    # Se edita al día siguiente, con lo que el server pondría de ancla hoy.
    d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL + timedelta(days=1))

    carga = d.carga_de_compra(cliente, EL_27)
    assert carga["modo"] == "manual", "el modo SÍ se actualiza al editar"
    assert carga["promedio_anterior_a"] == CARGADA_EL, (
        "editar movió el ancla: la ventana del promedio se corre sola"
    )


def test_BORRARLA_Y_EMPEZAR_DE_CERO_si_mueve_el_ancla(galpon):
    """La otra mitad, y es la que hace que la de arriba no sea una traba: sin
    esto, una carga vieja quedaría con su ancla para siempre."""
    d, _sql, cliente, _t, _l = galpon
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL)
    assert d.borrar_carga_de_compra(cliente, EL_27) is True
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL + timedelta(days=1))

    assert d.carga_de_compra(cliente, EL_27)["promedio_anterior_a"] == CARGADA_EL + timedelta(days=1)


def test_UNA_carga_por_cliente_y_fecha_y_la_segunda_EDITA_en_vez_de_sumar(galpon):
    """Lo que el dueño pidió: entrar de nuevo a Día para el mismo día abre la
    que ya existe. Que no pueda haber dos lo decide la BASE, no el código."""
    d, sql, cliente, _t, _l = galpon
    primera = d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL)
    segunda = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL)
    assert primera == segunda, "la segunda creó una carga nueva en vez de editar"
    (cuantas,), = sql("SELECT count(*) FROM cargas_compra WHERE cliente_id = %s", (cliente,))
    assert cuantas == 1


def test_una_carga_que_NO_EXISTE_devuelve_None_y_no_una_vacia(galpon):
    """`None` y "existe en automático" se ven igual mirando solo los
    renglones, y la pantalla necesita distinguirlas para poder preguntar."""
    d, _sql, cliente, _t, _l = galpon
    assert d.carga_de_compra(cliente, EL_27) is None
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL)
    carga = d.carga_de_compra(cliente, EL_27)
    assert carga is not None and carga["renglones"] == {}


def test_los_renglones_SOBREVIVEN_un_cambio_de_modo(galpon):
    """Pasar un rato a automático no puede borrar lo que se tipeó o se leyó de
    un archivo: re-tipear molesta, releer un archivo cuesta una lectura con IA
    y otra revisión."""
    d, _sql, cliente, tomate, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500})

    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL)
    assert d.carga_de_compra(cliente, EL_27)["renglones"] == {tomate: 500.0}


def test_guardar_renglones_REEMPLAZA_y_no_mezcla(galpon):
    """Es lo que quedó, no lo que cambió: sacarle un artículo a la carga tiene
    que llevárselo, y eso un upsert no lo puede expresar."""
    d, _sql, cliente, tomate, lima = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500, lima: 20})
    d.guardar_renglones_de_carga(carga_id, {tomate: 600})

    assert d.carga_de_compra(cliente, EL_27)["renglones"] == {tomate: 600.0}


def test_borrar_la_carga_SE_LLEVA_sus_renglones(galpon):
    d, sql, cliente, tomate, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500})
    d.borrar_carga_de_compra(cliente, EL_27)

    (quedan,), = sql("SELECT count(*) FROM cargas_compra_renglones WHERE carga_id = %s",
                     (carga_id,))
    assert quedan == 0


def test_borrar_una_carga_QUE_UN_LISTADO_YA_USO_lo_RECHAZA_la_base(galpon):
    """Borrarla cambiaría en silencio lo que ese listado dice que se salió a
    comprar. Decide la BASE (la FK no va en cascada) y el código traduce."""
    d, sql, cliente, _t, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL)
    # CERRADO y en otra fecha: el índice parcial deja UN borrador por día, y
    # el test de abajo abre el suyo para el 27. Para la FK da lo mismo.
    (listado,), = sql(
        "INSERT INTO listados_compra (fecha, estado, margen_porcentaje)"
        " VALUES (%s, 'cerrado', 10) RETURNING id", (date(2026, 9, 24),))
    sql("INSERT INTO listados_compra_cargas VALUES (%s, %s)", (listado, carga_id))

    with pytest.raises(Exception) as rebote:
        d.borrar_carga_de_compra(cliente, EL_27)
    assert "listados_compra_cargas" in str(rebote.value)
    assert d.carga_de_compra(cliente, EL_27) is not None, "la carga se borró igual"


def test_listar_cargas_RECORTA_por_fecha_y_el_recorte_lo_elige_QUIEN_LLAMA(galpon):
    """"Desde ayer en adelante" es del dueño y vive en la pantalla; acá lo que
    se fija es que el recorte exista y muerda."""
    d, _sql, cliente, _t, _l = galpon
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL)
    d.guardar_carga_de_compra(cliente, EL_27 - timedelta(days=10), "automatico", CARGADA_EL)

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
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "automatico", CARGADA_EL)
    (viejo,), = sql(
        "INSERT INTO listados_compra (fecha, estado, margen_porcentaje)"
        " VALUES (%s, 'cerrado', 10) RETURNING id", (date(2026, 9, 26),))
    (editando,), = sql(
        "INSERT INTO listados_compra (fecha, estado, margen_porcentaje)"
        " VALUES (%s, 'borrador', 10) RETURNING id", (EL_27,))
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


def test_la_carga_trae_CUANTOS_RENGLONES_tiene_al_lado(galpon):
    """El denominador: "Día, 27/09, a mano" sin el conteo no distingue una
    carga cargada de una que se abrió y quedó vacía."""
    d, _sql, cliente, tomate, lima = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", CARGADA_EL)
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


def _carga(modo="manual", renglones=None):
    return {"id": 3, "cliente_id": 1, "fecha": EL_27, "modo": modo,
            "promedio_anterior_a": CARGADA_EL, "renglones": renglones or {}}


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
    cliente_id, fecha, modo, ancla = guardar.call_args.args
    assert (cliente_id, fecha, modo) == (1, EL_27, "automatico")
    assert ancla == _main._hoy_argentina(), "el ancla no es el día en que se carga"


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
    filas = re.findall(r'<label class="fila"[^>]*data-articulo="(\d+)"([^>]*)>', marcado)
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
    assert "prom. 100" in marcado, "no dijo contra qué se corrigió"


def test_lo_que_NO_se_corrigio_no_lleva_el_cartel():
    """El rival: si el cartel saliera siempre, no distinguiría una corrección
    de una propuesta aceptada — que es justo lo que viene a decir."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico"),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    assert "prom. " not in respuesta.text.split("</style>")[-1]


# --- BULTOS, que es como piensa el que compra --------------------------------


def test_el_numero_GRANDE_es_BULTOS_cuando_la_ficha_dice_cuanto_entra():
    """370 kilos de arándano no le dicen nada al comprador; 370 cubetas sí.
    El bulto sale de `fichas_logistica.contenido_caja` DEL CLIENTE — no del
    kilaje del Mercado, que es otro número y vive en el Paso 2."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico"),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    marcado = respuesta.text.split("</style>")[-1]
    # 100 kilos por día sobre un bulto de 10 = 10 bultos.
    assert 'name="bultos_10"' in marcado and 'value="10"' in marcado
    # CORRIDO: el atributo cae en la línea siguiente del template, así que
    # el par name/value no es contiguo en el texto.
    corrido = " ".join(marcado.split())
    assert 'name="propuesto_10" value="10"' in corrido, "la propuesta viaja en BULTOS"
    # Y la magnitud al lado, chica.
    assert "100 kg" in marcado, "no mostró los kilos al lado"


def test_SIN_ficha_del_cliente_el_campo_sigue_siendo_LA_MAGNITUD():
    """El rival. La carga va contra el catálogo de compra, así que un
    artículo que este cliente no tiene en ficha se carga igual — y ahí no hay
    con qué dividir. El campo se llama por lo que es."""
    ctx = _con_catalogo(**{
        "app.main.carga_de_compra": _carga(modo="automatico"),
        "app.main.renglones_de_los_ultimos_pedidos": _RENGLONES_DE_PEDIDO,
    })
    respuesta, _ = _entrar(ctx, "get", f"/compras/carga/1/{EL_27.isoformat()}")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'name="total_7"' in marcado and 'name="bultos_7"' not in marcado


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
    """La pantalla no pudo haber dibujado ese campo: sin contenido el campo
    se llama `total_`. Si llega igual, vino por otro lado y no se guarda con
    una conversión inventada."""
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
