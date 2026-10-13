"""RINDE DE GUÍAS R (dueño, 13/10): el cuadro del panel, contra Postgres.

Los últimos 7 días COMPLETOS (de hoy − 7 a ayer). Por artículo que pasó por
guías R y se vende por kilo: Falta % = (entraron − primera − segunda − merma)
/ entraron, con la cuenta del cartel, POR GUÍA. El número grande: cuántos
artículos pasan el 5%.

EL GALPÓN, con nombres inventados y los RIVALES plantados (hoy es el 13/10):

  compra 21: EJEMPLO Morrón, cajones pesados de 10 kg
  compra 22: EJEMPLO Zapallo, cajones pesados de 20 kg
  compra 23: EJEMPLO Mango (la ficha vende por unidad)
  compra 24: EJEMPLO Zapallo SIN PESADA

  R1 06/10 Morrón: 10 cajones (100 kg) → 7 cajas de 10 kg y 1 de segunda   falta 20 kg
  R2 12/10 Morrón: 10 cajones (100 kg) → 9 cajas, guardada con "Guardar igual"   falta 10 kg
  R3 09/10 Zapallo: 5 cajones (100 kg) → 9 cajas de 10 y 1 de merma (20 kg)   sobran 10 kg
  rivales: R4 del 05/10 (fuera, 8 días), R5 de HOY, R6 anulada, R7 de Mango,
           R8 de Zapallo sin pesada.
"""
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.kilos_guia_r import UMBRAL_FALTA_PCT, resumen_del_rinde, rinde_por_articulo  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 13)

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'Día EJEMPLO');
insert into articulos (id, nombre, unidad_compra) overriding system value
  values (1, 'EJEMPLO Morron', 'kilo'), (2, 'EJEMPLO Zapallo', 'kilo'), (3, 'EJEMPLO Mango', null);
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value
  values (1, 1, 1, 10, 'kilo', 1), (2, 1, 2, 10, 'kilo', 1), (3, 1, 3, 10, 'unidad', 1);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (21, 1, 1, '2026-10-01', 100, 10, 1000, 1, 'recepcionado', '2026-10-01 18:00-03', 100, 10),
         (22, 1, 2, '2026-10-01', 100, 20, 2000, 1, 'recepcionado', '2026-10-01 18:00-03', 100, 20),
         (23, 1, 3, '2026-10-01', 100, 10, 1000, 1, 'recepcionado', '2026-10-01 18:00-03', 100, 10),
         (24, 1, 2, '2026-10-01', 100, 20, 2000, 1, 'recepcionado', '2026-10-01 18:00-03', 100, null);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, cliente_id, ficha_id, envase_id,
                        lleva_caja_nuestra, anulado_el, kilos_diferencia, kilos_guardo_igual,
                        kilos_guardo_igual_el)
  overriding system value
  values (1, 1, '2026-10-06', 10, 7, 1, 0, 1, 1, 1, true, null, null, null, null),
         (2, 1, '2026-10-12', 10, 9, 0, 0, 1, 1, 1, true, null, 10, 'Juan', '2026-10-12 10:00-03'),
         (3, 2, '2026-10-09', 5, 9, 0, 1, 1, 2, 1, true, null, null, null, null),
         (4, 1, '2026-10-05', 10, 1, 0, 0, 1, 1, 1, true, null, null, null, null),
         (5, 1, '2026-10-13', 10, 1, 0, 0, 1, 1, 1, true, null, null, null, null),
         (6, 1, '2026-10-08', 10, 1, 0, 0, 1, 1, 1, true, '2026-10-08 12:00-03', null, null, null),
         (7, 3, '2026-10-08', 10, 1, 0, 0, 1, 3, 1, true, null, null, null, null),
         (8, 2, '2026-10-08', 10, 1, 0, 0, 1, 2, 1, true, null, null, null, null);
insert into reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos)
  values (1, 'compra', 21, 21, 10), (2, 'compra', 21, 21, 10), (3, 'compra', 22, 22, 5),
         (4, 'compra', 21, 21, 10), (5, 'compra', 21, 21, 10), (6, 'compra', 21, 21, 10),
         (7, 'compra', 23, 23, 10), (8, 'compra', 24, 24, 10);
"""


def _guia(articulo, consumos, primera, segunda=0, merma=0, kg_caja=10.0, igual=False):
    return {"articulo_id": articulo, "articulo": f"EJEMPLO {articulo}", "consumos": consumos,
            "primera": primera, "segunda": segunda, "merma": merma, "kg_caja": kg_caja,
            "guardada_igual": igual}


def test_la_cuenta_es_POR_GUIA_y_suma_los_kilos_de_cada_una():
    """Dos guías del mismo artículo con cajones distintos: 10 de 10 kg y 10 de
    12 kg. Cada una usa SU cajón promedio para la segunda: 1 de segunda en la
    segunda guía son 12 kg, no 11."""
    filas = rinde_por_articulo([_guia(1, [(10, 10.0)], 9), _guia(1, [(10, 12.0)], 10, segunda=1)])
    assert len(filas) == 1
    f = filas[0]
    assert (f["entraron"], f["primera"], f["segunda"], f["merma"], f["falta"]) == (220.0, 190.0, 12.0, 0.0, 18.0)
    assert (f["falta_pct"], f["perdida_total_pct"], f["guias"]) == (8.2, 13.6, 2)


def test_SIN_PESADA_o_POR_UNIDAD_no_entra_y_se_cuenta():
    filas = rinde_por_articulo([_guia(1, [(10, 10.0)], 9), _guia(1, [(10, None)], 9),
                                _guia(3, [(10, 10.0)], 9, kg_caja=None)])
    assert [(f["articulo_id"], f["guias"], f["guias_sin_cuenta"]) for f in filas] == [(1, 1, 1)]


def test_el_numero_cuenta_los_que_PASAN_el_5_y_el_borde_no():
    """5% justo no cuenta; 5,1% sí. Ordenado de mayor a menor falta."""
    resumen = resumen_del_rinde([_guia(1, [(100, 10.0)], 95), _guia(2, [(1000, 10.0)], 949),
                                 _guia(3, [(10, 10.0)], 11)])
    assert UMBRAL_FALTA_PCT == 5.0
    assert [(f["articulo_id"], f["falta_pct"]) for f in resumen["filas"]] == [(2, 5.1), (1, 5.0), (3, -10.0)]
    assert resumen["con_falta"] == 1


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
    conexion = d.obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    with patch("app.main._hoy_argentina", return_value=HOY):
        yield d, m


def test_el_CUADRO_mira_los_7_dias_completos_y_deja_afuera_a_los_rivales(galpon):
    d, m = galpon
    dato = m._panel_rinde(HOY)
    assert (dato["desde"], dato["hasta"]) == (date(2026, 10, 6), date(2026, 10, 12))
    filas = {f["articulo"]: f for f in dato["filas"]}
    assert sorted(filas) == ["EJEMPLO Morron", "EJEMPLO Zapallo"]       # Mango no
    morron, zapallo = filas["EJEMPLO Morron"], filas["EJEMPLO Zapallo"]
    # R1 y R2: 200 kg; primera 160; segunda 1 cajón de 10 kg. Faltan 30 (15%).
    assert (morron["entraron"], morron["primera"], morron["segunda_y_merma"], morron["falta"]) \
        == (200.0, 160.0, 10.0, 30.0)
    assert (morron["falta_pct"], morron["guias"], morron["guardadas_igual"]) == (15.0, 2, 1)
    # R3: 100 kg; primera 90; merma 1 cajón de 20 kg: sobran 10. La R8 sin pesada se cuenta aparte.
    assert (zapallo["falta"], zapallo["falta_pct"], zapallo["guias_sin_cuenta"]) == (-10.0, -10.0, 1)
    assert dato["con_falta"] == 1
    assert [f["articulo"] for f in dato["filas"]] == ["EJEMPLO Morron", "EJEMPLO Zapallo"]


def test_el_TABLERO_y_el_DETALLE_lo_muestran(galpon):
    d, m = galpon
    from tests.test_administracion_reordenada import _cliente
    cliente = _cliente(m, "gerencia")
    cliente.post("/gerencia/panel/actualizar")
    tablero = cliente.get("/gerencia/panel").text.split("</style>")[-1]
    cuadro = tablero.split('data-cuadro="rinde"')[1].split("</a>")[0]
    assert re.findall(r'<div data-ajustar class="cuadro-numero ([a-z]+)">(\d+)</div>', cuadro) == [("rojo", "1")]
    assert "artículo con más de 5% de falta, de 2" in cuadro
    detalle = cliente.get("/gerencia/panel/rinde").text.split("</style>")[-1]
    tarjetas = re.findall(r'data-articulo="(\d+)"', detalle)
    assert tarjetas == ["1", "2"]
    morron = detalle.split('data-articulo="1"')[1].split('data-articulo="2"')[0]
    assert "15,0% falta" in morron and "Faltan <strong data-ajustar class=\"rojo\">30 kg</strong>" in morron
    assert "1 guardada con \"Guardar igual\"" in morron


def test_una_FOTO_VIEJA_sin_el_cuadro_no_rompe_el_tablero(galpon):
    """La foto de antes del 13/10 no trae "rinde": el tablero dice que aparece
    en la próxima, en vez de caerse."""
    d, m = galpon
    from core.panel_foto import a_texto
    from datetime import datetime, timezone
    from tests.test_administracion_reordenada import _cliente
    vieja = {c: m._datos_del_cuadro(c, HOY, {}) for c in m.CUADROS_DEL_PANEL if c != "rinde"}
    buena = {"calculada_el": datetime(2026, 10, 13, 9, 1, tzinfo=timezone.utc), "datos_json": a_texto(vieja)}
    with patch.object(m, "foto_buena_del_panel", return_value=buena), \
            patch.object(m, "intentos_automaticos_del_panel", return_value=[]):
        pagina = _cliente(m, "gerencia").get("/gerencia/panel")
    assert pagina.status_code == 200
    cuadro = pagina.text.split('data-cuadro="rinde"')[1].split("</a>")[0]
    assert '<div class="cuadro-pie" data-sin-foto>Aparece en la próxima actualización.</div>' in cuadro
