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
import re
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


# --- EL AJUSTE DE SEGUNDA (28/09) ---------------------------------------------
#
# La migración `segunda_ajuste_1` corrió en las dos bases el 28/09. Todo esto
# va contra Postgres: lo que se afirma es que el pool SUMA la pata nueva, con
# su recorte, y eso solo lo puede ver una consulta que corre de verdad.


def _ajuste(d, art, bultos, dia, motivo="EJEMPLO segunda del piso al corte"):
    return d.crear_ajuste_segunda(art, bultos, motivo, dia)


def test_el_AJUSTE_suma_al_pool_y_deja_el_cierre_del_dia_en_lo_contado(galpon):
    """Palta en −2, se cuenta 0 el día 20 y se ajusta +2 ese día: el pool de
    ese cierre queda en 0, que es lo contado, y el stock congelado es −2."""
    d, m, sql, corte, articulo, remito, pase = galpon
    art = articulo("EJEMPLO Palta Ajuste")
    pase(art, 19)
    remito(art, 21)
    dia = corte + timedelta(days=20)
    assert _ajuste(d, art, 2, dia) == 0.0
    assert m._sistema_por_porcion_al_cierre(dia).get((art, None, True), 0.0) == 0.0
    (congelado, bultos, fecha), = sql(
        "SELECT stock_sistema, bultos, fecha_operacion FROM ajustes_segunda WHERE articulo_id = %s", (art,))
    assert (float(congelado), float(bultos), fecha) == (-2.0, 2.0, dia)
    # El día ANTERIOR no lo ve: el ajuste es del día del conteo.
    assert m._sistema_por_porcion_al_cierre(dia - timedelta(days=1)).get((art, None, True)) == -2.0


def test_el_AJUSTE_no_toca_la_PRIMERA(galpon):
    d, m, _sql, corte, articulo, remito, pase = galpon
    art = articulo("EJEMPLO Primera Quieta")
    pase(art, 5)
    dia = corte + timedelta(days=20)
    antes = [f for f in d.stock_deposito_por_articulo(dia) if f["articulo_id"] == art][0]["stock"]
    _ajuste(d, art, 3, dia)
    despues = [f for f in d.stock_deposito_por_articulo(dia) if f["articulo_id"] == art][0]
    assert despues["stock"] == antes
    assert despues["segunda"] == 8.0


def test_el_AJUSTE_del_MISMO_dia_del_corte_cuenta_y_el_de_antes_se_rechaza(galpon):
    """El `>=` a propósito: un ajuste corrige la cuenta, no es algo que pasó en
    el galpón esa tarde. El rival es el día anterior al corte, que la
    escritura rechaza porque ahí la segunda no se cuenta."""
    d, m, _sql, corte, articulo, _remito, _pase = galpon
    art = articulo("EJEMPLO Dia Del Corte")
    _ajuste(d, art, 4, corte)
    assert m._sistema_por_porcion_al_cierre(corte + timedelta(days=1)).get((art, None, True)) == 4.0
    with pytest.raises(ValueError, match="antes del corte"):
        _ajuste(d, art, 4, corte - timedelta(days=1))
    with pytest.raises(ValueError, match="todavía no pasó"):
        _ajuste(d, art, 4, date(2099, 1, 1))


def test_un_ajuste_ANULADO_deja_de_contar(galpon):
    d, m, sql, corte, articulo, _remito, _pase = galpon
    art = articulo("EJEMPLO Anulado")
    dia = corte + timedelta(days=20)
    _ajuste(d, art, 6, dia)
    (ajuste_id,), = sql("SELECT id FROM ajustes_segunda WHERE articulo_id = %s", (art,))
    assert d.anular_ajuste_segunda(ajuste_id) is True
    assert d.anular_ajuste_segunda(ajuste_id) is False
    assert m._sistema_por_porcion_al_cierre(dia).get((art, None, True), 0.0) == 0.0


def test_la_CONSULTA_de_db_da_el_MISMO_pool_que_el_sistema(galpon, base_real):
    """`db/segunda_negativa_1` es `_SQL_POOL_SEGUNDA` compactado para entrar en
    2500 caracteres. Lo que impide que se separe no es haberla copiado bien:
    es correrla al lado de la función, con un artículo por pata."""
    d, _m, sql, corte, articulo, remito, pase = galpon
    arts = [articulo("EJEMPLO Q Remito"), articulo("EJEMPLO Q Pase"), articulo("EJEMPLO Q Ajuste")]
    remito(arts[0], 5)
    pase(arts[1], 7)
    _ajuste(d, arts[2], -3, corte + timedelta(days=2))
    texto = open(os.path.join(RAIZ, "db", "segunda_negativa_1_por_articulo.sql"), encoding="utf-8").read()
    assert len(texto) <= 2500
    filas = {nombre: float(pool) for nombre, *_resto, pool, _corte in sql(texto)}
    conexion = d.obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            for art in arts:
                (nombre,), = sql("SELECT nombre FROM articulos WHERE id = %s", (art,))
                assert filas[nombre] == d._segunda_de_articulo(cursor, art), nombre
    finally:
        conexion.close()
    assert [filas[n] for n in sorted(filas) if n.startswith("EJEMPLO Q ")] == [-3.0, 7.0, -5.0]


# --- La pantalla -------------------------------------------------------------


def _cliente(m):
    from fastapi.testclient import TestClient
    cliente = TestClient(m.app, base_url="https://testserver")
    cliente.cookies.set(m.PUERTA_ADMINISTRACION.cookie, m.PUERTA_ADMINISTRACION.firma("a"))
    return cliente


def test_la_tarjeta_de_segunda_del_COTEJO_lleva_el_boton_y_la_pantalla_propone_la_diferencia(galpon):
    d, m, sql, corte, articulo, remito, pase = galpon
    art = articulo("EJEMPLO Palta Cotejo Boton")
    pase(art, 19)
    remito(art, 21)
    dia = corte + timedelta(days=20)
    sql("INSERT INTO conteos_stock (articulo_id, es_segunda, cantidad, stock_sistema, creado_en) "
        "VALUES (%s, true, 0, 0, %s)", (art, f"{dia.isoformat()} 16:00-03"))
    cliente = _cliente(m)
    with patch.dict(os.environ, {"CLAVE_ADMINISTRACION": "a"}):
        cotejo = cliente.get("/administracion/stock/cotejo").text.split("</style>")[-1]
        # por el ENCABEZADO: el artículo también está en la lista del ajuste sin conteo
        tarjeta = [t for t in cotejo.split('<div class="tarjeta') if 'encabezado">EJEMPLO Palta Cotejo Boton' in t]
        assert len(tarjeta) == 1
        # COTEJO Y AJUSTE (04/10): el formulario de la segunda va adentro de
        # la tarjeta, con la diferencia de ese día y SIN motivo escrito
        assert tarjeta[0].count('action="/administracion/stock/ajustar-segunda"') == 1
        assert f'<input type="hidden" name="fecha_conteo" value="{dia.isoformat()}">' in tarjeta[0]
        assert re.search(r'name="cantidad" step="0.01" required[^>]*value="2.0"', tarjeta[0])
        assert re.search(r'<input type="text" name="motivo" required\s+placeholder="[^"]*"></label>', tarjeta[0])
        # la de PRIMERA no: ese botón mueve el total y la segunda no está ahí
        assert 'action="/administracion/stock/ajustar"' not in tarjeta[0]
        pantalla = cliente.get(
            f"/administracion/stock/ajustar-segunda?articulo_id={art}&contado=0&fecha_conteo={dia.isoformat()}"
        ).text.split("</style>")[-1]
    assert 'name="cantidad" step="0.01" required' in pantalla
    assert 'value="2.0"' in pantalla  # 0 contados − (−2) del sistema
    # el MOTIVO no viene escrito: es lo único que dice por qué
    assert re.search(r'name="motivo" required\s+placeholder="[^"]*"\s+value=""', pantalla)


def test_guardar_el_ajuste_exige_MOTIVO_y_despues_se_puede_ANULAR(galpon):
    d, m, sql, corte, articulo, _remito, _pase = galpon
    art = articulo("EJEMPLO Guardar Ajuste")
    dia = (corte + timedelta(days=20)).isoformat()
    cliente = _cliente(m)
    with patch.dict(os.environ, {"CLAVE_ADMINISTRACION": "a"}):
        sin = cliente.post("/administracion/stock/ajustar-segunda",
                           data={"articulo_id": art, "fecha_conteo": dia, "cantidad": "3", "motivo": "  "},
                           follow_redirects=False)
        assert sin.status_code == 400 and "El motivo es obligatorio" in sin.text
        assert sql("SELECT count(*) FROM ajustes_segunda WHERE articulo_id = %s", (art,)) == [(0,)]
        con = cliente.post("/administracion/stock/ajustar-segunda",
                           data={"articulo_id": art, "fecha_conteo": dia, "cantidad": "3",
                                 "motivo": "EJEMPLO segunda del piso"}, follow_redirects=False)
        assert con.status_code == 303
        (ajuste_id,), = sql("SELECT id FROM ajustes_segunda WHERE articulo_id = %s", (art,))
        lista = cliente.get(con.headers["location"]).text
        assert "EJEMPLO Guardar Ajuste" in lista and "quedó en 3" in lista
        anular = cliente.post(f"/administracion/stock/ajustar-segunda/{ajuste_id}/anular",
                              follow_redirects=False)
        assert anular.status_code == 303
    (anulado,), = sql("SELECT anulado_el FROM ajustes_segunda WHERE id = %s", (ajuste_id,))
    assert anulado is not None


def test_el_ajuste_de_segunda_esta_detras_de_la_clave_de_ADMINISTRACION(galpon):
    _d, m, _sql, _corte, _articulo, _remito, _pase = galpon
    from fastapi.testclient import TestClient
    sin_cookie = TestClient(m.app, base_url="https://testserver")
    with patch.dict(os.environ, {"CLAVE_ADMINISTRACION": "a"}):
        assert sin_cookie.get("/administracion/stock/ajustar-segunda").status_code == 401
        assert sin_cookie.post("/administracion/stock/ajustar-segunda", data={}).status_code == 401
