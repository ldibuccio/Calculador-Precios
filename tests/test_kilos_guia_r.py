"""LOS KILOS NO DAN (dueño, 13/10): el cartel rojo al cargar una guía R.

Entraron = cajones tomados × lo que pesó un cajón de SU compra. Salieron =
cajas de primera × kilos de la ficha + cajones de segunda y merma × el cajón
promedio. Tolerancia: 0,8 kg por cajón tomado (era medio kilo; el dueño la
subió el mismo 13/10). Si no dan, cartel rojo con
"Revisar" y "Guardar igual"; si guardan igual, la guía anota la diferencia y
quién. Por unidad (Mango) o con un cajón sin pesada, no hay cartel.

EL GALPÓN, con nombres inventados y los RIVALES plantados:

  01/10  compra 21: 10 cajones de EJEMPLO Morrón pesados de 10 kg
  02/10  compra 22: 30 cajones de EJEMPLO Morrón declarados de 12, pesados de 12,7
         compra 23: 10 cajones de EJEMPLO Zapallo SIN PESADA (rival)
         compra 24: 10 cajones de EJEMPLO Mango, la ficha vende por unidad (rival)
  Fichas: Morrón 8 kg, Zapallo 10 kg, Mango 10 unidades. Hoy es el 13/10.

El caso de la R751 (09/10): 2 cajones de 10 kg y 21 de 12,7 = 286,7 kg; 20
cajas de 8 kg y 3 de segunda (a 12,47 kg el cajón promedio) = 197,4 kg. Faltan
89,3 kg contra una tolerancia de 18,4: salta. El cartel dice 287 − 197 = 90.
"""
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.kilos_guia_r import TOLERANCIA_KG_POR_CAJON, cuenta_de_kilos  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 13)
FECHA = date(2026, 10, 9)

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'Día EJEMPLO');
insert into articulos (id, nombre, unidad_compra) overriding system value
  values (1, 'EJEMPLO Morron', 'kilo'), (2, 'EJEMPLO Zapallo', 'kilo'), (3, 'EJEMPLO Mango', null);
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value
  values (1, 1, 1, 8, 'kilo', 1), (2, 1, 2, 10, 'kilo', 1), (3, 1, 3, 10, 'unidad', 1);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (21, 1, 1, '2026-10-01', 10, 10, 100, 70000, 'recepcionado', '2026-10-01 18:00-03', 10, 10),
         (22, 1, 1, '2026-10-02', 30, 12, 360, 80000, 'recepcionado', '2026-10-02 18:00-03', 30, 12.7),
         (23, 1, 2, '2026-10-02', 10, 10, 100, 30000, 'recepcionado', '2026-10-02 18:00-03', 10, null),
         (24, 1, 3, '2026-10-02', 10, 10, 100, 50000, 'recepcionado', '2026-10-02 18:00-03', 10, 10);
"""


# ---------------------------------------------------------------- la cuenta


def test_la_cuenta_de_la_R751_SALTA():
    cuenta = cuenta_de_kilos([(2, 10), (21, 12.7)], 20, 3, 0, 8)
    assert (cuenta["entraron"], cuenta["salieron"], cuenta["diferencia"], cuenta["tolerancia"]) \
        == (286.7, 197.4, 89.3, 18.4)
    assert cuenta["no_dan"] is True
    # El cartel: 287 − 197 = 90, y es lo que queda anotado.
    assert (cuenta["kg_entraron"], cuenta["kg_salieron"], cuenta["kg_diferencia"]) == (287, 197, 90)


def test_la_cuenta_de_la_R788_NO_salta():
    """28 cajones de 10 y 2 de 12 = 304 kg; 36 cajas de 8 = 288 kg. Faltan 16 kg
    contra 24 de tolerancia (30 × 0,8): no salta, que es lo que el dueño
    pidió. Con medio kilo por cajón saltaba por 1 kg, y por eso la subió."""
    cuenta = cuenta_de_kilos([(28, 10), (2, 12)], 36, 0, 0, 8)
    assert (cuenta["entraron"], cuenta["salieron"], cuenta["diferencia"], cuenta["tolerancia"]) \
        == (304.0, 288.0, 16.0, 24.0)
    assert TOLERANCIA_KG_POR_CAJON == 0.8
    assert cuenta["no_dan"] is False


def test_dentro_de_la_tolerancia_NO_salta_y_justo_en_el_borde_tampoco():
    assert cuenta_de_kilos([(10, 10)], 12, 0, 0, 8)["no_dan"] is False      # 100 vs 96: 4 ≤ 8
    assert cuenta_de_kilos([(10, 10)], 13, 0, 0, 8)["no_dan"] is False      # sobran 4 ≤ 8
    assert cuenta_de_kilos([(10, 10)], 10, 0, 0, 9.2)["no_dan"] is False    # 8 = 8: el borde no salta
    assert cuenta_de_kilos([(10, 10)], 10, 0, 0, 9.1)["no_dan"] is True     # 9 > 8


def test_SOBRAN_tambien_salta():
    cuenta = cuenta_de_kilos([(4, 10)], 8, 0, 0, 8)                          # 40 vs 64
    assert (cuenta["diferencia"], cuenta["no_dan"]) == (-24.0, True)


def test_sin_cuenta_por_UNIDAD_SIN_PESADA_o_SIN_FICHA():
    assert cuenta_de_kilos([(10, 10)], 10, 0, 0, None) is None              # ficha por unidad / sin ficha
    assert cuenta_de_kilos([(5, 10), (5, None)], 10, 0, 0, 8) is None       # un cajón sin pesada
    assert cuenta_de_kilos([], 10, 0, 0, 8) is None


def test_el_TEXTO_del_cartel_con_las_palabras_del_duenio():
    from app.main import texto_kilos_no_dan
    falta = cuenta_de_kilos([(2, 10), (21, 12.7)], 20, 3, 0, 8)
    assert texto_kilos_no_dan(falta) == (
        "LOS KILOS NO DAN. Entraron 287 kg (23 cajones). Salieron 197 kg. Faltan 90 kg. "
        "Revisá antes de seguir: ¿falta cargar segunda o merma?")
    from core.kilos_guia_r import kg_entero
    assert (kg_entero(286.5), kg_entero(287.5)) == (287, 288)             # medio, para arriba
    sobra = cuenta_de_kilos([(4, 10)], 8, 0, 0, 8)
    assert texto_kilos_no_dan(sobra) == (
        "LOS KILOS NO DAN. Entraron 40 kg y salieron 64 kg. Sobran 24 kg. Revisá los cajones tomados.")


# ---------------------------------------------------------------- contra Postgres


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


REPARTO_R751 = [{"tipo_lote": "guia", "origen_id": 21, "bultos": 2},
                {"tipo_lote": "guia", "origen_id": 22, "bultos": 21}]


def _r751(d, **extra):
    return d.crear_reproceso(1, 23, 20, 3, 0, FECHA, cliente_id=1, ficha_id=1,
                             reparto=REPARTO_R751, **extra)


def _anotado(sql, guia):
    return sql("select kilos_diferencia, kilos_guardo_igual, kilos_guardo_igual_el is not null "
               "from reprocesos where id = %s", (guia,))[0]


def test_la_R751_NO_DAN_y_no_escribe_nada(galpon):
    d, m, sql = galpon
    with pytest.raises(d.KilosNoDan) as no_dan:
        _r751(d)
    assert (no_dan.value.cuenta["diferencia"], no_dan.value.cuenta["kg_diferencia"]) == (89.3, 90)
    assert sql("select count(*) from reprocesos")[0][0] == 0
    assert sql("select count(*) from reprocesos_consumos")[0][0] == 0


def test_GUARDAR_IGUAL_anota_la_diferencia_quien_y_cuando(galpon):
    d, m, sql = galpon
    guia = _r751(d, kilos_guardo_igual="  Juan   Pérez ")
    assert _anotado(sql, guia) == (90, "Juan Pérez", True)


def test_un_nombre_en_BLANCO_no_alcanza_para_guardar_igual(galpon):
    d, m, sql = galpon
    with pytest.raises(d.KilosNoDan):
        _r751(d, kilos_guardo_igual="   ")
    assert sql("select count(*) from reprocesos")[0][0] == 0


def test_si_los_kilos_DAN_no_se_anota_nada_aunque_venga_un_nombre(galpon):
    """El RIVAL de la anotación: 10 cajones de 12,7 (127 kg) en 16 cajas de 8
    (128 kg): sobra 1 kg contra 8 de tolerancia."""
    d, m, sql = galpon
    guia = d.crear_reproceso(1, 10, 16, 0, 0, FECHA, cliente_id=1, ficha_id=1,
                             reparto=[{"tipo_lote": "guia", "origen_id": 22, "bultos": 10}],
                             kilos_guardo_igual="Juan")
    assert _anotado(sql, guia) == (None, None, False)


def test_MANGO_por_unidad_y_ZAPALLO_sin_pesada_no_tienen_cartel(galpon):
    d, m, sql = galpon
    mango = d.crear_reproceso(3, 10, 30, 0, 0, FECHA, cliente_id=1, ficha_id=3)
    zapallo = d.crear_reproceso(2, 10, 30, 0, 0, FECHA, cliente_id=1, ficha_id=2)
    assert _anotado(sql, mango) == (None, None, False)
    assert _anotado(sql, zapallo) == (None, None, False)


def test_la_base_no_acepta_la_diferencia_SIN_QUIEN(galpon):
    d, m, sql = galpon
    guia = d.crear_reproceso(1, 10, 16, 0, 0, FECHA, cliente_id=1, ficha_id=1,
                             reparto=[{"tipo_lote": "guia", "origen_id": 22, "bultos": 10}])
    import psycopg2
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("update reprocesos set kilos_diferencia = 5, kilos_guardo_igual_el = now() where id = %s",
            (guia,))


# ---------------------------------------------------------------- la pantalla


def _cargar(m, **extra):
    from tests.test_administracion_reordenada import _cliente
    import json
    datos = {"cliente_id": "1", "articulo_id": "1", "ficha_id": "1", "bultos_tomados": "23",
             "bultos_primera": "20", "bultos_segunda": "3", "bultos_merma": "0",
             "fecha": FECHA.isoformat(), "confirmado": "1", "reparto": json.dumps(REPARTO_R751)}
    datos.update(extra)
    # Depósito no tiene clave: el cliente sin ninguna puerta abierta.
    return _cliente(m).post("/deposito/stock/reproceso", data=datos, follow_redirects=False)


def _cartel(respuesta):
    return re.findall(r'<p class="kilos-no-dan-texto">([^<]*)</p>', respuesta.text)


def test_la_pantalla_muestra_el_CARTEL_con_REVISAR_y_GUARDAR_IGUAL(galpon):
    d, m, sql = galpon
    respuesta = _cargar(m)
    assert respuesta.status_code == 200
    import html
    assert [html.unescape(t) for t in _cartel(respuesta)] == [
        "LOS KILOS NO DAN. Entraron 287 kg (23 cajones). Salieron 197 kg. Faltan 90 kg. "
        "Revisá antes de seguir: ¿falta cargar segunda o merma?"]
    assert respuesta.text.count('<a class="boton-revisar" href="#bultos_tomados"') == 1
    assert respuesta.text.count('<button type="submit" class="boton-guardar-igual">Guardar igual</button>') == 1
    # Guardar igual reenvía lo mismo que se mandó, el reparto incluido.
    assert respuesta.text.count('<input type="hidden" name="guardar_igual" value="1">') == 1
    assert [html.unescape(v) for v in
            re.findall(r'<input type="hidden" name="reparto" value="([^"]*)">', respuesta.text)] \
        == ['[{"tipo_lote": "guia", "origen_id": 21, "bultos": 2}, '
            '{"tipo_lote": "guia", "origen_id": 22, "bultos": 21}]']
    assert sql("select count(*) from reprocesos")[0][0] == 0


def test_GUARDAR_IGUAL_sin_nombre_vuelve_a_pedirlo_y_con_nombre_guarda(galpon):
    d, m, sql = galpon
    sin_nombre = _cargar(m, guardar_igual="1", kilos_guardo_igual="")
    assert _cartel(sin_nombre) and '<p class="kilos-no-dan-falta">Poné quién la guarda.</p>' in sin_nombre.text
    assert sql("select count(*) from reprocesos")[0][0] == 0
    con_nombre = _cargar(m, guardar_igual="1", kilos_guardo_igual="Juan")
    assert con_nombre.status_code == 303
    guia = sql("select id from reprocesos")[0][0]
    assert _anotado(sql, guia)[:2] == (90, "Juan")


def test_un_nombre_SIN_guardar_igual_no_pasa_el_cartel(galpon):
    """El nombre solo vale con el botón: un POST con el campo y sin el botón
    vuelve a mostrar el cartel."""
    d, m, sql = galpon
    assert _cartel(_cargar(m, kilos_guardo_igual="Juan"))
    assert sql("select count(*) from reprocesos")[0][0] == 0


def test_la_diferencia_se_ve_en_GUIAS_R_y_en_COMO_RINDIO(galpon):
    d, m, sql = galpon
    guia = _r751(d, kilos_guardo_igual="Juan")
    from tests.test_administracion_reordenada import _cliente
    linea = re.compile(r'<span class="kilos-guardada-igual" data-kilos-guardada-igual[^>]*>([^<]*)</span>')
    esperado = "Los kilos no daban: faltaban 90 kg. La guardó igual Juan."
    import html
    lista = _cliente(m, "administracion").get(f"/administracion/stock/guias-r?guia=R{guia}")
    assert [html.unescape(t) for t in linea.findall(lista.text)] == [esperado]
    detalle = _cliente(m, "compras").get("/compras/22/detalle")
    assert [html.unescape(t) for t in linea.findall(detalle.text)] == [esperado]
    # El rival: una compra cuya guía no tiene diferencia no muestra la línea.
    otra = d.crear_reproceso(1, 4, 5, 0, 0, FECHA, cliente_id=1, ficha_id=1,
                             reparto=[{"tipo_lote": "guia", "origen_id": 21, "bultos": 4}])
    assert _anotado(sql, otra)[0] is None
    lista = _cliente(m, "administracion").get(f"/administracion/stock/guias-r?guia=R{otra}")
    assert linea.findall(lista.text) == []
