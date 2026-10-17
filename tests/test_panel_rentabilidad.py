"""PANEL, RENTABILIDAD POR CLIENTE (dueño, 16/10): mes anterior, mes en curso y
7 días; por cliente "Armado" (venta = lo enviado) y "Recibido" (venta = lo que
firmó el súper), contra el costo real de lo armado (mercadería + cartón) menos
la segunda cobrada, repartida por los bultos de segunda de las guías R de cada
cliente. Contra Postgres.

EL GALPÓN, con nombres inventados: el del pase de Rentabilidad Real (cliente 1
EJEMPLO Dia, Tomate a $100 el kilo) más octubre: una guía R del cliente 1 con
2 bultos de segunda y otra del cliente 2 (el RIVAL) con 6; un lote de segunda
al puesto cobrado $800; una venta del 06/10 con su remito recibido (24 kg
enviados, 18 recibidos) y una caja de esa venta que el súper rechazó y VOLVIÓ
AL STOCK ($300 más su caja de $50), y otra del 07/10 con el remito SIN recibir (6 kg). En
septiembre, una venta del 20/09 con su remito recibido, cargado en octubre.
"""
import os
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.panel_control import celda_de_rentabilidad, segunda_cobrada_por_cliente  # noqa: E402
from tests.test_panel_control_contra_la_base import _base_con, _cliente_gerencia, _sin_foto_del_panel  # noqa: E402,F401

HOY = date(2026, 10, 10)

OCTUBRE = """
insert into clientes (id, nombre) overriding system value values (2, 'EJEMPLO Coto');
insert into precios_venta_historial (articulo_id, cliente_id, ficha_id, precio, vigente_desde, creado_en)
  values (1, 1, 1, 100, '2026-09-01', '2026-09-01 08:00-03');
-- Una compra de octubre: la lista de precios de una fecha mira las compras recientes.
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value values
  (4, 1, 1, '2026-10-01', 10, 16, 160, 100, 'recepcionado', '2026-10-01 18:00-03', 10, 16);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra)
  overriding system value values
  (3, 1, '2026-10-02', 4, 6, 2, 0, 300, 1, 1, 1, true),
  (4, 1, '2026-10-02', 1, 1, 6, 0, 300, 2, null, null, false);
insert into remitos_segunda (id, articulo_id, bultos, fecha_operacion, destino) overriding system value
  values (91, 1, 8, '2026-10-05', 'puesto');
insert into segunda_cobros (salida_id, importe, fecha_cobro, sector) values (91, 800, '2026-10-06', 'gerencia');
insert into pedidos (id, cliente_id, fecha_operacion, origen, creado_en) overriding system value
  values (69, 1, '2026-09-20', 'mail', '2026-09-20 08:00-03'),
         (71, 1, '2026-10-06', 'mail', '2026-10-06 08:00-03'), (72, 1, '2026-10-07', 'mail', '2026-10-07 08:00-03');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad, cantidad_armada,
                               armado_el, kilos_enviados)
  overriding system value values (691, 69, 'VL', 1, 1, 1, 1, '2026-09-20 12:00-03', 6),
                                 (711, 71, 'VL', 1, 1, 4, 4, '2026-10-06 12:00-03', 24),
                                 (721, 72, 'VL', 1, 1, 1, 1, '2026-10-07 12:00-03', 6);
insert into pedidos_sucursales (id, pedido_id, sucursal) overriding system value
  values (69, 69, 'VL'), (71, 71, 'VL'), (72, 72, 'VL');
insert into remitos (id, pedido_sucursal_id, cliente_id, numero, emitido_el, recibido_el) overriding system value
  values (3, 69, 1, 'R-0003', '2026-10-02 15:00-03', '2026-10-02 16:00-03'),
         (1, 71, 1, 'R-0001', '2026-10-06 15:00-03', '2026-10-07 09:00-03'),
         (2, 72, 1, 'R-0002', '2026-10-07 15:00-03', null);
insert into remitos_renglones (remito_id, pedido_renglon_id, bultos_enviados, kilos_enviados,
                               bultos_recibidos, kilos_recibidos)
  values (3, 691, 1, 6, 1, 6), (1, 711, 4, 24, 3, 18), (2, 721, 1, 6, null, null);
-- La caja rechazada de la venta del 06/10 vuelve al stock con su costo congelado.
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo, stock_sistema,
                               pedido_renglon_id, destino_rechazo, costo_por_bulto, cliente_id)
  values (1, '2026-10-07', 'reingreso_rechazo', 1, 'volvio del super', 1, 711, 'stock', 300, 1);
"""


@pytest.fixture(scope="module")
def galpon():
    from tests.test_rentabilidad_real_pase import SIEMBRA
    url = _base_con(SIEMBRA + OCTUBRE)
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        import app.main as m
        yield m


# --- LO PURO ----------------------------------------------------------------------

def test_la_SEGUNDA_se_reparte_por_los_bultos_de_segunda_de_las_guias_de_cada_cliente():
    lotes = [{"articulo_id": 1, "importe": 800}, {"articulo_id": 1, "importe": None},   # sin cobrar: nada
             {"articulo_id": 2, "importe": 100}]                                          # sin guía: sin repartir
    guias = [{"cliente_id": 1, "articulo_id": 1, "bultos_segunda": 2},
             {"cliente_id": 2, "articulo_id": 1, "bultos_segunda": 4},
             {"cliente_id": None, "articulo_id": 1, "bultos_segunda": 2},                  # sin cliente
             {"cliente_id": 1, "articulo_id": 2, "bultos_segunda": 0}]
    assert segunda_cobrada_por_cliente(lotes, guias) == {"por_cliente": {1: 200.0, 2: 400.0}, "sin_repartir": 300.0}


def test_la_CELDA_resta_la_segunda_del_costo_y_la_ganancia_va_sobre_la_mercaderia():
    celda = celda_de_rentabilidad({"venta_neta": 3000, "costo_mercaderia": 1500, "costo_envase": 250}, 200)
    assert (celda["costo"], celda["ganancia"], celda["pct"]) == (1550, 1450, pytest.approx(1450 / 1500 * 100))
    # Recibido: la venta sin lo que el motor descontó, y el costo con lo perdido en rechazos y
    # sin la diferencia de lo devuelto al proveedor.
    recibido = celda_de_rentabilidad({"venta_neta": 3000, "devoluciones_venta": 100, "costo_mercaderia": 1500,
                                      "costo_envase": 250, "rechazos_perdidos": 80,
                                      "diferencia_devolucion_proveedor": 30}, 200)
    assert (recibido["venta"], recibido["costo"]) == (2900, 1500 + 250 + 80 - 30 - 200)
    assert celda_de_rentabilidad({"venta_neta": 0, "costo_mercaderia": 0, "costo_envase": 0}, 0)["pct"] is None


# --- CONTRA LA BASE -----------------------------------------------------------------

def test_ARMADO_es_lo_enviado_RECIBIDO_lo_firmado_y_lo_que_vuelve_al_stock_cuenta_una_vez(galpon):
    m = galpon
    datos = m._panel_rentabilidad(HOY)
    (fila,) = [f for f in datos["filas"] if f["cliente_id"] == 1]
    armado, recibido = fila["armado"]["actual"], fila["recibido"]["actual"]
    assert armado["mercaderia"] > 0                                            # el testigo: hubo costo
    assert armado["venta"] == pytest.approx(3000)                             # (24 + 6) kg × $100
    assert recibido["venta"] == pytest.approx(2400)                           # 18 recibidos + 6 sin recibir
    # La caja que volvió al stock no es costo de lo recibido: se cuenta cuando salga de nuevo.
    # $300 de mercadería y $50 de la caja de Día, que vuelve con ella (dueño, 09/10).
    assert recibido["costo"] == pytest.approx(armado["costo"] - 300 - 50)
    assert armado["carton"] > 0                                               # el cartón está en el costo
    assert armado["segunda"] == pytest.approx(200)                            # $800 × 2 / (2 + 6)
    assert armado["costo"] == pytest.approx(armado["mercaderia"] + armado["carton"] - 200)
    assert (recibido["sin_remitos"], recibido["sin_recibir"]) == (False, 1)
    # Septiembre: su remito se cargó en octubre y cuenta igual; sin segunda que repartir.
    septiembre = fila["recibido"]["anterior"]
    assert (septiembre["sin_remitos"], septiembre["sin_recibir"]) == (False, 0)
    assert septiembre["venta"] == pytest.approx(600) and septiembre["pct"] is not None
    # Los 7 días (03/10 a hoy) no tienen la guía R del 02/10: lo cobrado queda sin repartir.
    assert fila["armado"]["semana"]["segunda"] == 0
    assert datos["segunda_sin_repartir"] == {"anterior": 0, "actual": 0, "semana": pytest.approx(800)}


def test_sin_NINGUN_remito_del_rango_el_recibido_es_una_raya(galpon):
    """El rival: un rango sin remitos (agosto) no se confunde con uno parcial."""
    m = galpon
    datos = m._panel_rentabilidad(date(2026, 9, 10))
    (fila,) = [f for f in datos["filas"] if f["cliente_id"] == 1]
    assert fila["recibido"]["anterior"]["sin_remitos"] is True                # agosto
    assert fila["recibido"]["actual"]["sin_remitos"] is True                  # 01 al 10/09: el remito es del 20/09


def test_el_TABLERO_dice_parcial_y_sin_remitos_y_una_foto_vieja_espera(galpon):
    m = galpon
    cliente, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves), patch.object(m, "_hoy_argentina", return_value=HOY):
        tablero = cliente.get("/gerencia/panel").text.split("</style>")[-1]
        detalle = cliente.get("/gerencia/panel/rentabilidad").text.split("</style>")[-1]
    cuadro = tablero.split('data-cuadro="rentabilidad"')[1].split("</a>")[0]
    assert "<th>Sep</th><th>Oct</th><th>7 días</th>" in cuadro
    assert cuadro.count('data-renglon="armado"') == cuadro.count('data-renglon="recibido"') == 1
    recibido = cuadro.split('data-renglon="recibido"')[1].split("</tr>")[0]
    assert '<span class="marca">sin remitos</span>' not in recibido                      # septiembre tiene su remito
    assert recibido.count('<span class="marca">parcial · <span class="n">1</span> sin recibir</span>') == 2   # octubre y 7 días
    assert ">Ahora<" not in cuadro
    assert detalle.count('data-rango="') == 3 and detalle.count("data-costo-recibido") == 3
    # Una foto calculada antes de este cambio (con "Ahora") no se rompe: espera la próxima.
    vieja = {"rentabilidad": [{"cliente_id": 1, "cliente": "EJEMPLO Dia", "mes": 1.0, "semana": 1.0,
                               "ahora": {"pct": 1.0, "sin_ventas": False, "fichas": 1}}]}
    m.guardar_foto_del_panel(turno=None, datos_json=m.foto_a_texto(dict(m.calcular_el_panel(HOY), **vieja)),
                             duracion_ms=1)
    with patch.dict(os.environ, claves), patch.object(m, "_hoy_argentina", return_value=HOY):
        con_foto_vieja = cliente.get("/gerencia/panel").text.split("</style>")[-1]
    cuadro_viejo = con_foto_vieja.split('data-cuadro="rentabilidad"')[1].split("</a>")[0]
    assert "data-sin-foto" in cuadro_viejo and "data-rentabilidad" not in cuadro_viejo
