"""EL TOPE POR COMPRA de la guía R (dueño, 13/10), contra Postgres.

Una compra no puede terminar con más cajones anotados por las guías R de los
que tenía. Pasaba por dos agujeros (114 compras de 421 desde el corte):

- EL MISMO DÍA: la propuesta y la validación del reparto veían los lotes
  ENTEROS, sin lo que otra guía del día ya se había llevado.
- ENTRE DÍAS: el FIFO se rejuega y no dirige la toma de una guía a los
  consumos que ella anotó, así que el lote que el stock da por consumido no
  es el que la guía anotó.

EL GALPÓN, con nombres inventados:

  01/10  compra 11: 30 cajones de EJEMPLO Morrón (la vieja)
  02/10  compra 12: 30 cajones de EJEMPLO Morrón (la nueva)
  Hoy es el 13/10.
"""
import json
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.stock import topar_por_lo_anotado  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 13)

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'Día EJEMPLO');
insert into articulos (id, nombre, unidad_compra) overriding system value
  values (1, 'EJEMPLO Morron', 'kilo');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 10, 'kilo', 1);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (11, 1, 1, '2026-10-01', 30, 10, 300, 70000, 'recepcionado', '2026-10-01 18:00-03', 30, 10),
         (12, 1, 1, '2026-10-02', 30, 10, 300, 80000, 'recepcionado', '2026-10-02 18:00-03', 30, 10);
"""


def test_TOPAR_deja_cada_compra_en_lo_que_le_queda_y_no_toca_lo_demas():
    lotes = [{"tipo_lote": "guia", "origen_id": 11, "restante": 10.0},
             {"tipo_lote": "guia", "origen_id": 12, "restante": 30.0},
             {"tipo_lote": "ajuste", "origen_id": 11, "restante": 5.0}]   # rival: mismo id, otro tipo
    topados = topar_por_lo_anotado(lotes, {11: 30.0, 12: 10.0})
    assert [l["restante"] for l in topados] == [10.0, 10.0, 5.0]
    assert topar_por_lo_anotado(lotes, {11: -2.0})[0]["restante"] == 0.0   # pasada: cero, no negativo
    assert lotes[1]["restante"] == 30.0                                      # devuelve copias


@pytest.fixture
def galpon(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    monkeypatch.setenv("DATABASE_URL", url)
    from tests.test_administracion_reordenada import CLAVES
    for clave, valor in CLAVES.items():
        monkeypatch.setenv(clave, valor)
    import app.db as d
    import app.main as m

    def sql(consulta, parametros=None):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()

    sql(SIEMBRA)
    with patch("app.main._hoy_argentina", return_value=HOY):
        yield d, m, sql


def _guia(d, bultos, fecha, reparto=None):
    return d.crear_reproceso(1, bultos, bultos, 0, 0, fecha, cliente_id=1, ficha_id=1, reparto=reparto)


def _anotado(sql, compra):
    return float(sql("select coalesce(sum(rc.bultos), 0) from reprocesos_consumos rc "
                     "join reprocesos rp on rp.id = rc.reproceso_id "
                     "where rc.compra_id = %s and rp.anulado_el is null", (compra,))[0][0])


def test_EL_MISMO_DIA_la_segunda_guia_no_vuelve_a_tomar_lo_de_la_primera(galpon):
    """R1 toma 25 de la 11 el 05/10. R2 del MISMO día pide 20: antes la
    propuesta veía la 11 entera (30) y anotaba 20 más (45 de 30). Ahora salen
    5 de la 11 y 15 de la 12."""
    d, m, sql = galpon
    _guia(d, 25, date(2026, 10, 5))
    _guia(d, 20, date(2026, 10, 5))
    assert (_anotado(sql, 11), _anotado(sql, 12)) == (30.0, 15.0)


def test_EL_MISMO_DIA_un_reparto_a_mano_que_se_pasa_lo_rebota(galpon):
    d, m, sql = galpon
    _guia(d, 25, date(2026, 10, 5))
    with pytest.raises(d.RepartoDesactualizado):
        _guia(d, 10, date(2026, 10, 5), reparto=[{"tipo_lote": "guia", "origen_id": 11, "bultos": 10}])
    assert _anotado(sql, 11) == 25.0


def test_ENTRE_DIAS_cuenta_lo_ANOTADO_y_no_lo_que_dice_el_rejuego(galpon):
    """R1 (05/10) anotó 20 de la 12 elegidos a mano; el rejuego del stock le
    atribuye esos 20 a la 11, la más vieja. El 06/10 el rejuego dice 11 → 10
    y 12 → 30, pero la 12 solo tiene 10 libres. R2 pide 25: antes pasaba (40
    disponibles) y la 12 terminaba con 35 de 30. Ahora hay 20: frena."""
    d, m, sql = galpon
    _guia(d, 20, date(2026, 10, 5), reparto=[{"tipo_lote": "guia", "origen_id": 12, "bultos": 20}])
    with pytest.raises(d.StockInsuficienteParaReproceso) as freno:
        _guia(d, 25, date(2026, 10, 6))
    assert freno.value.disponible == 20.0
    # Y el control: 20 sí entran, 10 de cada una.
    _guia(d, 20, date(2026, 10, 6))
    assert (_anotado(sql, 11), _anotado(sql, 12)) == (10.0, 30.0)


def test_LA_BASE_rechaza_por_su_cuenta_una_guia_nueva_que_se_pasa(galpon):
    d, m, sql = galpon
    _guia(d, 25, date(2026, 10, 5))
    guia = sql("select id from reprocesos")[0][0]
    import psycopg2
    with pytest.raises(psycopg2.errors.CheckViolation) as error:
        sql("insert into reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos) "
            "values (%s, 'compra', 11, 11, 6)", (guia,))
    assert error.value.diag.constraint_name == "guia_r_no_pasa_la_compra"
    # El borde entra: le quedan 5 y pide 5.
    sql("insert into reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos) "
        "values (%s, 'compra', 11, 11, 5)", (guia,))
    # Una guía ANULADA no retiene nada: ni se cuenta ni se frena lo que se le anote.
    sql("update reprocesos set anulado_el = now() where id = %s", (guia,))
    sql("insert into reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos) "
        "values (%s, 'compra', 11, 11, 50)", (guia,))
    _guia(d, 30, date(2026, 10, 6), reparto=[{"tipo_lote": "guia", "origen_id": 11, "bultos": 30}])


def test_LA_PANTALLA_ofrece_lo_mismo_que_el_freno(galpon):
    d, m, sql = galpon
    _guia(d, 25, date(2026, 10, 5))
    from tests.test_administracion_reordenada import _cliente
    datos = _cliente(m).get("/deposito/stock/reproceso/desglose",
                            params={"articulo_id": 1, "fecha": "2026-10-05", "bultos": 20}).json()
    assert datos["disponible"] == 35.0
    assert datos["propuesta"] == {"guia:11": 5.0, "guia:12": 15.0}


def test_COMO_RINDIO_dice_cuando_las_guias_anotaron_de_mas_y_solo_entonces(galpon):
    """La compra vieja pasada (como las 114) se plantó con el trigger apagado,
    como quedó en producción. La 12 es el rival: anotada justo."""
    d, m, sql = galpon
    sql("alter table reprocesos_consumos disable trigger guia_r_no_pasa_la_compra")
    sql("insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera, "
        "bultos_segunda, bultos_merma, cliente_id, ficha_id, envase_id, lleva_caja_nuestra) "
        "overriding system value values (7, 1, '2026-10-05', 32, 32, 0, 0, 1, 1, 1, true), "
        "(8, 1, '2026-10-05', 30, 30, 0, 0, 1, 1, 1, true)")
    sql("insert into reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos) "
        "values (7, 'compra', 11, 11, 32), (8, 'compra', 12, 12, 30)")
    sql("alter table reprocesos_consumos enable trigger guia_r_no_pasa_la_compra")
    from tests.test_administracion_reordenada import _cliente
    nota = re.compile(r"<span class=\"nota-chica\" data-anotadas-de-mas>([^<]*)</span>")
    vieja = _cliente(m, "compras").get("/compras/11/detalle").text
    assert nota.findall(vieja) == ["Las guías anotaron 32 cajones de una compra de 30."]
    assert nota.findall(_cliente(m, "compras").get("/compras/12/detalle").text) == []


def test_LA_PANTALLA_entre_dias_tambien_topa_por_lo_anotado(galpon):
    d, m, sql = galpon
    _guia(d, 20, date(2026, 10, 5), reparto=[{"tipo_lote": "guia", "origen_id": 12, "bultos": 20}])
    from tests.test_administracion_reordenada import _cliente
    datos = _cliente(m).get("/deposito/stock/reproceso/desglose",
                            params={"articulo_id": 1, "fecha": "2026-10-06", "bultos": 20}).json()
    assert datos["disponible"] == 20.0
    assert datos["propuesta"] == {"guia:11": 10.0, "guia:12": 10.0}


def test_si_igual_llega_a_la_base_el_error_se_TRADUCE_y_no_queda_nada(galpon, monkeypatch):
    """La carrera: otra guía anotó de la misma compra entre la lista y el
    INSERT. Se simula apagando el tope de la lista (no el de la base, que es lo
    que se prueba): la base rechaza y la pantalla recibe el motivo."""
    d, m, sql = galpon
    _guia(d, 20, date(2026, 10, 5), reparto=[{"tipo_lote": "guia", "origen_id": 12, "bultos": 20}])
    monkeypatch.setattr(d, "_cajones_libres_por_compra", lambda *a, **k: {})
    with pytest.raises(d.RepartoDesactualizado) as error:
        _guia(d, 25, date(2026, 10, 6), reparto=[{"tipo_lote": "guia", "origen_id": 12, "bultos": 25}])
    assert "más cajones de los que le quedan" in str(error.value)
    assert sql("select count(*) from reprocesos")[0][0] == 1
