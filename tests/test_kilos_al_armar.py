"""KILOS POR CAJA AL ARMAR (dueño, 13/10), contra Postgres.

El kilaje por bulto se carga al armar, precargado con la ficha y editable
(`kilos_enviados` = bultos × lo cargado: lo que se factura), sin ningún aviso
(dueño, 13/10). Dos cosas nuevas:

- La PRIMERA de una guía R pesa lo que se mandó en los pedidos que salieron
  de sus cajas (`kilos_reales_de_la_primera`); las que no salieron, la ficha.
- El cuadro "Kilos al armar" del panel: los renglones de los últimos 7 días
  completos con kilos distintos de la ficha, por artículo.

EL GALPÓN, con nombres inventados y los RIVALES plantados (hoy es el 13/10):

  03/10  compra 11: 20 cajones de EJEMPLO Morrón, pesados de 10 kg
  04/10  guía R0: 1 cajón -> 1 caja de 8 kg (ficha 1)
  05/10  renglón 8: 1 bulto con 20 kg                   (fuera de la ventana)
  09/10  guía R1: 10 cajones -> 10 cajas de 8 kg
  11/10  renglón 1: 6 bultos con 9 kg  (54 kg)          +6 kg
         renglón 2: 2 bultos con 7 kg  (14 kg)          −2 kg
         renglón 3: 1 bulto con 8 kg                     igual a la ficha
         renglón 10: 1 bulto SIN kilos                   no se sabe cuánto
         rivales: renglón 4 anulado, renglón 5 de un pedido recargado (no
         vigente), renglón 6 de Mango (por unidad), renglón 7 de Cherry en
         su envase, renglón 13 de la verdulería (ficha sin envase: sale del
         cajón de la compra, no de una guía R).
"""
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.kilos_guia_r import kg_de_la_primera  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 13)

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'Día EJEMPLO'), (2, 'EJEMPLO Verduleria');
insert into articulos (id, nombre, unidad_compra) overriding system value
  values (1, 'EJEMPLO Morron', 'kilo'), (2, 'EJEMPLO Mango', null), (3, 'EJEMPLO Cherry', 'kilo');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id,
                              envase_variable)
  overriding system value
  values (1, 1, 1, 8, 'kilo', 1, false), (2, 1, 2, 10, 'unidad', 1, true), (3, 1, 3, 5, 'kilo', 1, true),
         (4, 2, 1, 8, 'kilo', null, false);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (11, 1, 1, '2026-10-03', 20, 10, 200, 50000, 'recepcionado', '2026-10-03 18:00-03', 20, 10);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra, creado_en)
  overriding system value
  values (100, 1, '2026-10-04', 1, 1, 0, 0, 50000, 1, 1, 1, true, '2026-10-04 09:00-03'),
         (101, 1, '2026-10-09', 10, 10, 0, 0, 50000, 1, 1, 1, true, '2026-10-09 09:00-03');
insert into reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos, costo_por_bulto)
  values (100, 'compra', 11, 11, 1, 50000), (101, 'compra', 11, 11, 10, 50000);
insert into pedidos (id, cliente_id, fecha_operacion, origen, creado_en) overriding system value
  values (1, 1, '2026-10-11', 'texto', '2026-10-11 08:00-03'),
         (2, 1, '2026-10-11', 'texto', '2026-10-11 07:00-03'),
         (5, 1, '2026-10-04', 'texto', '2026-10-04 07:00-03'),
         (6, 2, '2026-10-11', 'texto', '2026-10-11 07:00-03');
insert into pedidos_sucursales (pedido_id, sucursal) values (1, 'VL'), (2, 'VL'), (5, 'VL'), (6, 'CENTRO');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
                               cantidad_armada, armado_el, kilos_enviados, anulado_el, en_su_envase)
  overriding system value
  values (1, 1, 'VL', 1, 1, 6, 6, '2026-10-11 10:00-03', 54, null, false),
         (2, 1, 'VL', 1, 1, 2, 2, '2026-10-11 10:05-03', 14, null, false),
         (3, 1, 'VL', 1, 1, 1, 1, '2026-10-11 10:10-03', 8, null, false),
         (10, 1, 'VL', 1, 1, 1, 1, '2026-10-11 10:15-03', null, null, false),
         (4, 1, 'VL', 1, 1, 1, 1, '2026-10-11 10:20-03', 20, '2026-10-11 11:00-03', false),
         (5, 2, 'VL', 1, 1, 1, 1, '2026-10-11 10:25-03', 20, null, false),
         (6, 1, 'VL', 2, 2, 1, 1, '2026-10-11 10:30-03', 12, null, false),
         (7, 1, 'VL', 3, 3, 1, 1, '2026-10-11 10:35-03', 7, null, true),
         (8, 5, 'VL', 1, 1, 1, 1, '2026-10-05 10:00-03', 20, null, false),
         (13, 6, 'CENTRO', 1, 4, 1, 1, '2026-10-11 10:40-03', 8, null, false);
"""


def test_KG_DE_LA_PRIMERA_pesa_lo_mandado_y_completa_con_la_ficha():
    assert kg_de_la_primera(10, 8.0) == 80.0                                   # sin armados: ficha
    assert kg_de_la_primera(10, 8.0, {"bultos": 0, "kg": 0}) == 80.0
    assert kg_de_la_primera(10, 8.0, {"bultos": 6, "kg": 54}) == 54 + 4 * 8.0   # 6 mandadas, 4 en el piso
    # Más salidas atribuidas que primera (un rejuego): nunca pasa la primera.
    assert kg_de_la_primera(10, 8.0, {"bultos": 12, "kg": 108}) == 90.0


@pytest.fixture(scope="module")
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    return url


@pytest.fixture
def d(base, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", base)
    import app.db as modulo
    return modulo


def test_KILOS_REALES_cada_guia_con_lo_que_se_mando_de_sus_cajas(d):
    """R0: el renglón 8 (1 caja con 20 kg). R1: los renglones 1, 2 y 3 (9
    cajas, 76 kg); la del renglón 10 salió de la R1 pero sin kilos: no
    cuenta, y esa caja pesa la ficha. El 13 sale de la compra: no es de
    ninguna guía."""
    assert d.kilos_reales_de_la_primera([1]) == {100: {"bultos": 1.0, "kg": 20.0},
                                                 101: {"bultos": 9.0, "kg": 76.0}}
    assert d.kilos_reales_de_la_primera([2, None]) == {}


def test_el_RINDE_del_panel_usa_la_primera_REAL(d):
    """La ventana es del 06/10 al 12/10: entra la R1, no la R0. Entraron 100
    kg; la primera son 76 kg mandados + 1 caja de 8 de la ficha = 84."""
    import app.main as m
    rinde = m._panel_rinde(HOY)
    fila, = rinde["filas"]
    assert (fila["articulo_id"], fila["entraron"], fila["primera"], fila["falta"]) == (1, 100.0, 84.0, 16.0)


def test_COMO_RINDIO_suma_la_primera_REAL_de_sus_guias(d):
    cr = d.como_rindio_la_compra(11)
    guias = {g["numero"]: g for g in cr["guias"]}
    assert (guias[100]["kg_primera"], guias[101]["kg_primera"]) == (20.0, 84.0)
    assert cr["kg_primera"] == 104.0


def test_KILOS_DISTINTOS_cuenta_solo_lo_suyo(d):
    """Los renglones 1 (+6) y 2 (−2). Ni el igual a la ficha, ni el sin kilos,
    ni los rivales: anulado, no vigente, por unidad, en su envase, fuera de
    la ventana."""
    assert d.kilos_distintos_de_la_ficha(date(2026, 10, 6), date(2026, 10, 12)) == [
        {"articulo_id": 1, "articulo": "EJEMPLO Morron", "renglones": 2, "kg_diferencia": 4.0}]
    # El de fuera de la ventana existe: con la ventana corrida, aparece.
    assert d.kilos_distintos_de_la_ficha(date(2026, 10, 5), date(2026, 10, 5)) == [
        {"articulo_id": 1, "articulo": "EJEMPLO Morron", "renglones": 1, "kg_diferencia": 12.0}]


def _gerencia(m):
    from tests.test_administracion_reordenada import CLAVES, _cliente
    return _cliente(m, "gerencia"), CLAVES


def test_el_CUADRO_y_su_DETALLE(d):
    import app.main as m
    cliente, claves = _gerencia(m)
    with patch.dict(os.environ, claves), patch.object(m, "_hoy_argentina", return_value=HOY):
        datos = m._panel_kilos(HOY)
        detalle = cliente.get("/gerencia/panel/kilos")
    assert (datos["renglones"], datos["kg_diferencia"], datos["desde"], datos["hasta"]) \
        == (2, 4.0, date(2026, 10, 6), date(2026, 10, 12))
    assert detalle.status_code == 200, detalle.text[:300]
    marcado = detalle.text.split("</style>")[-1]
    tarjetas = re.findall(r'<div data-ajustar-contenedor class="tarjeta" data-articulo="(\d+)">', marcado)
    assert tarjetas == ["1"]
    tarjeta = marcado.split('data-articulo="1">')[1].split("</div>")[0]
    assert "<h2>EJEMPLO Morron</h2>" in tarjeta
    assert "<strong data-ajustar>2</strong> renglones" in tarjeta
    assert "<strong data-ajustar>4 kg</strong> de más" in tarjeta

