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
