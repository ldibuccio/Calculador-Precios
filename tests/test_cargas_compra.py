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

HOY = date(2026, 9, 22)
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
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY)
    # Se edita al día siguiente, con lo que el server pondría de ancla hoy.
    d.guardar_carga_de_compra(cliente, EL_27, "manual", HOY + timedelta(days=1))

    carga = d.carga_de_compra(cliente, EL_27)
    assert carga["modo"] == "manual", "el modo SÍ se actualiza al editar"
    assert carga["promedio_anterior_a"] == HOY, (
        "editar movió el ancla: la ventana del promedio se corre sola"
    )


def test_BORRARLA_Y_EMPEZAR_DE_CERO_si_mueve_el_ancla(galpon):
    """La otra mitad, y es la que hace que la de arriba no sea una traba: sin
    esto, una carga vieja quedaría con su ancla para siempre."""
    d, _sql, cliente, _t, _l = galpon
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY)
    assert d.borrar_carga_de_compra(cliente, EL_27) is True
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY + timedelta(days=1))

    assert d.carga_de_compra(cliente, EL_27)["promedio_anterior_a"] == HOY + timedelta(days=1)


def test_UNA_carga_por_cliente_y_fecha_y_la_segunda_EDITA_en_vez_de_sumar(galpon):
    """Lo que el dueño pidió: entrar de nuevo a Día para el mismo día abre la
    que ya existe. Que no pueda haber dos lo decide la BASE, no el código."""
    d, sql, cliente, _t, _l = galpon
    primera = d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY)
    segunda = d.guardar_carga_de_compra(cliente, EL_27, "manual", HOY)
    assert primera == segunda, "la segunda creó una carga nueva en vez de editar"
    (cuantas,), = sql("SELECT count(*) FROM cargas_compra WHERE cliente_id = %s", (cliente,))
    assert cuantas == 1


def test_una_carga_que_NO_EXISTE_devuelve_None_y_no_una_vacia(galpon):
    """`None` y "existe en automático" se ven igual mirando solo los
    renglones, y la pantalla necesita distinguirlas para poder preguntar."""
    d, _sql, cliente, _t, _l = galpon
    assert d.carga_de_compra(cliente, EL_27) is None
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY)
    carga = d.carga_de_compra(cliente, EL_27)
    assert carga is not None and carga["renglones"] == {}


def test_los_renglones_SOBREVIVEN_un_cambio_de_modo(galpon):
    """Pasar un rato a automático no puede borrar lo que se tipeó o se leyó de
    un archivo: re-tipear molesta, releer un archivo cuesta una lectura con IA
    y otra revisión."""
    d, _sql, cliente, tomate, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", HOY)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500})

    d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY)
    assert d.carga_de_compra(cliente, EL_27)["renglones"] == {tomate: 500.0}


def test_guardar_renglones_REEMPLAZA_y_no_mezcla(galpon):
    """Es lo que quedó, no lo que cambió: sacarle un artículo a la carga tiene
    que llevárselo, y eso un upsert no lo puede expresar."""
    d, _sql, cliente, tomate, lima = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", HOY)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500, lima: 20})
    d.guardar_renglones_de_carga(carga_id, {tomate: 600})

    assert d.carga_de_compra(cliente, EL_27)["renglones"] == {tomate: 600.0}


def test_borrar_la_carga_SE_LLEVA_sus_renglones(galpon):
    d, sql, cliente, tomate, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", HOY)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500})
    d.borrar_carga_de_compra(cliente, EL_27)

    (quedan,), = sql("SELECT count(*) FROM cargas_compra_renglones WHERE carga_id = %s",
                     (carga_id,))
    assert quedan == 0


def test_borrar_una_carga_QUE_UN_LISTADO_YA_USO_lo_RECHAZA_la_base(galpon):
    """Borrarla cambiaría en silencio lo que ese listado dice que se salió a
    comprar. Decide la BASE (la FK no va en cascada) y el código traduce."""
    d, sql, cliente, _t, _l = galpon
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY)
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
    d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY)
    d.guardar_carga_de_compra(cliente, EL_27 - timedelta(days=10), "automatico", HOY)

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
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "automatico", HOY)
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
    carga_id = d.guardar_carga_de_compra(cliente, EL_27, "manual", HOY)
    d.guardar_renglones_de_carga(carga_id, {tomate: 500, lima: 20})

    fila = next(c for c in d.listar_cargas_desde(EL_27) if c["id"] == carga_id)
    assert fila["renglones"] == 2 and fila["cliente_nombre"].startswith("EJEMPLO")


# --- LAS PANTALLAS del Paso 1 -------------------------------------------------
#
# Mockeadas, como el resto de las rutas: acá lo que se mira es el CABLEADO
# —qué se guarda, a dónde redirige, qué dibuja— y no si el SQL parsea, que lo
# contestan los de arriba contra Postgres de verdad.

import os  # noqa: E402
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
]
# El de magnitud imposible es el RIVAL: una ficha en 'cubeta' de un artículo
# cuyo conteo es 'unidad'. Sin él, "la pantalla dibuja un campo por artículo"
# pasa igual con la guarda sacada.
_FICHAS = [
    {"articulo_id": 7, "unidad_venta": "kilo", "unidad_conteo": None},
    {"articulo_id": 8, "unidad_venta": "unidad", "unidad_conteo": "unidad"},
    {"articulo_id": 9, "unidad_venta": "cubeta", "unidad_conteo": "unidad"},
]


def _con_catalogo(**extra):
    parches = {
        "app.main.listar_clientes": _CLIENTES,
        "app.main.listar_articulos": _ARTICULOS,
        "app.main.listar_fichas_de_todos_los_clientes": _FICHAS,
    }
    parches.update(extra)
    contextos = [patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"})]
    contextos += [patch(nombre, return_value=valor) for nombre, valor in parches.items()]
    return contextos


def _entrar(contextos, metodo, ruta, **kwargs):
    from contextlib import ExitStack
    with ExitStack() as pila:
        abiertos = [pila.enter_context(c) for c in contextos]
        respuesta = getattr(_cliente, metodo)(ruta, follow_redirects=False, **kwargs)
    return respuesta, abiertos


def _carga(modo="manual", renglones=None):
    return {"id": 3, "cliente_id": 1, "fecha": EL_27, "modo": modo,
            "promedio_anterior_a": HOY, "renglones": renglones or {}}


def test_abrir_una_carga_QUE_YA_EXISTE_PREGUNTA_en_vez_de_crear_otra():
    """Lo pidió el dueño así: ni una segunda que sume doble ni abrir la vieja
    en silencio. Las dos salidas son legítimas y las dos borran trabajo."""
    ctx = _con_catalogo(**{"app.main.carga_de_compra": _carga()})
    ctx.append(patch("app.main.guardar_carga_de_compra"))
    respuesta, abiertos = _entrar(ctx, "post", "/compras/carga",
                                  data={"cliente_id": "1", "fecha": EL_27.isoformat(),
                                        "modo": "manual"})
    guardar = abiertos[-1]
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
    guardar = abiertos[-1]
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


def test_en_modo_AUTOMATICO_el_guardado_NO_TOCA_los_renglones():
    """Pasar un rato a automático no puede borrar lo que se tipeó o se leyó de
    un archivo: re-tipear molesta, releer un archivo cuesta una lectura con IA
    y otra revisión."""
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    _, abiertos = _entrar(ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
                          data={"modo": "automatico", "total_7": "500"})
    assert abiertos[-1].call_count == 0


def test_en_modo_A_MANO_los_totales_llegan_y_el_VACIO_no_se_guarda_en_cero():
    ctx = _con_catalogo()
    ctx.append(patch("app.main.guardar_carga_de_compra", return_value=3))
    ctx.append(patch("app.main.guardar_renglones_de_carga"))
    respuesta, abiertos = _entrar(
        ctx, "post", f"/compras/carga/1/{EL_27.isoformat()}",
        data={"modo": "manual", "total_7": "500", "total_8": "", "total_9": "0"})
    guardar_renglones = abiertos[-1]
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
             "modo": "manual", "promedio_anterior_a": HOY, "renglones": 2,
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
