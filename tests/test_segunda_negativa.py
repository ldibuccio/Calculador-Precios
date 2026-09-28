"""La segunda en NEGATIVO se ve, con su número real (dueño, 28/09), contra Postgres.

La palta de segunda está en −2 desde el 15/09: salieron 21 en remitos al
Puesto y entraron 19, porque el 05/09 había segunda en el piso que no se
cargó como stock inicial. El Remanente no mostraba la fila —la segunda salía
solo con `> 0`— y el Cotejo leía "sistema 0", porque busca la porción en esa
lista y la que no está vale cero.

Y una segunda mitad que no estaba en el pedido y salió de mirar la consulta:
un artículo cuyo ÚNICO movimiento es un remito al Puesto desaparecía de la
consulta del stock entera, porque su filtro no miraba los remitos.

Contra la base y no con mocks: lo que se afirma sale de la consulta real, y
cada caso lleva su rival —la segunda en cero, que no tiene que salir—.
"""
import os
import sys
from datetime import date, timedelta
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


@pytest.fixture(scope="module")
def base_real():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def galpon(base_real, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", base_real)
    import app.db as d
    import app.main as m

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

    (corte,), = sql("SELECT fecha FROM corte_modelo WHERE id = 1")
    (n,), = sql("SELECT nextval(pg_get_serial_sequence('articulos','id'))")

    def articulo(nombre):
        (art,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id", (f"{nombre} {n}",))
        return art

    def remito(art, bultos, dias=10):
        sql("INSERT INTO remitos_segunda (articulo_id, bultos, fecha_operacion) VALUES (%s,%s,%s)",
            (art, bultos, corte + timedelta(days=dias)))

    def pase(art, bultos, dias=5):
        sql("""INSERT INTO movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion,
               stock_sistema, bultos_segunda) VALUES (%s,'pase_a_segunda',%s,'EJEMPLO',%s,0,%s)""",
            (art, -bultos, corte + timedelta(days=dias), bultos))

    return d, m, sql, corte, articulo, remito, pase


def _porcion_de_segunda(m, articulo_id, hasta):
    return [p for p in m._remanente_a_fecha(hasta)["porciones"]
            if p["articulo_id"] == articulo_id and p.get("es_segunda")]


def test_la_segunda_NEGATIVA_sale_en_el_remanente_con_su_numero(galpon):
    """Entraron 19 por pases y salieron 21 al Puesto: −2, marcada."""
    _d, m, _sql, corte, articulo, remito, pase = galpon
    art = articulo("EJEMPLO Palta")
    pase(art, 19)
    remito(art, 21)
    hasta = corte + timedelta(days=20)
    segunda, = _porcion_de_segunda(m, art, hasta)
    assert segunda["bultos"] == -2.0
    assert segunda["negativo"] is True and segunda["faltan"] == 2.0


def test_el_COTEJO_lee_menos_dos_y_no_cero(galpon):
    """El Cotejo busca la porción en la lista del Remanente: sin la fila, la
    segunda de la palta decía "sistema 0"."""
    _d, m, _sql, corte, articulo, remito, pase = galpon
    art = articulo("EJEMPLO Palta Cotejo")
    pase(art, 19)
    remito(art, 21)
    sistema = m._sistema_por_porcion_al_cierre(corte + timedelta(days=20))
    assert sistema.get((art, None, True)) == -2.0


def test_un_articulo_cuyo_UNICO_movimiento_es_un_REMITO_no_desaparece(galpon):
    """El filtro de la consulta no miraba los remitos: con solo un remito, el
    artículo no estaba en la lista y su −5 no existía para nadie."""
    d, m, _sql, corte, articulo, remito, _pase = galpon
    art = articulo("EJEMPLO Solo remito")
    remito(art, 5)
    hasta = corte + timedelta(days=20)
    filas = [f for f in d.stock_deposito_por_articulo(hasta) if f["articulo_id"] == art]
    assert len(filas) == 1
    segunda, = _porcion_de_segunda(m, art, hasta)
    assert segunda["bultos"] == -5.0


def test_la_segunda_en_CERO_sigue_sin_salir_y_la_positiva_sin_marca(galpon):
    """El rival: con `!= 0` una segunda que cierra justo no es una pila, y una
    positiva no lleva la marca de negativo."""
    _d, m, _sql, corte, articulo, remito, pase = galpon
    cero, positiva = articulo("EJEMPLO Cero"), articulo("EJEMPLO Positiva")
    pase(cero, 7)
    remito(cero, 7)
    pase(positiva, 7)
    remito(positiva, 3)
    hasta = corte + timedelta(days=20)
    assert _porcion_de_segunda(m, cero, hasta) == []
    segunda, = _porcion_de_segunda(m, positiva, hasta)
    assert segunda["bultos"] == 4.0 and segunda["negativo"] is False


def test_la_pantalla_del_REMANENTE_la_muestra_en_ROJO(galpon):
    from fastapi.testclient import TestClient
    _d, m, _sql, corte, articulo, remito, pase = galpon
    art = articulo("EJEMPLO Palta Pantalla")
    pase(art, 19)
    remito(art, 21)
    cliente = TestClient(m.app, base_url="https://testserver")
    cliente.cookies.set(m.PUERTA_ADMINISTRACION.cookie, m.PUERTA_ADMINISTRACION.firma("a"))
    with patch.dict(os.environ, {"CLAVE_ADMINISTRACION": "a"}):
        respuesta = cliente.get(f"/administracion/stock/remanente?fecha={(corte + timedelta(days=20)).isoformat()}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.text.split("</style>")[-1]
    # EL RENGLÓN DE LA SEGUNDA, no el primero con el nombre: el pase le sacó
    # 19 a la primera, así que ese renglón también está en negativo (−19) y
    # un test que tomara el primero con el nombre miraría el equivocado.
    renglones = [r[:r.index("</a>")] for r in cuerpo.split("<a class=\"porcion")[1:]
                 if f"articulo_id={art}&" in r[:r.index("</a>")] and "segunda=1" in r[:r.index("</a>")]]
    assert len(renglones) == 1
    assert '<span class="numero-negativo">-2</span>' in renglones[0]
