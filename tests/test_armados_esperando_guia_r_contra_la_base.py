# -*- coding: utf-8 -*-
"""El detalle de "Armados esperando una guía R", contra Postgres.

POR QUÉ CONTRA LA BASE: el detalle no es una consulta, es el REJUEGO del FIFO
(`atribuir_costos_fifo`). Con la base mockeada el reparto lo decide el
fixture, y lo que se quiere ver es qué armado se queda sin caja cuando pasan
cosas en orden (corolario 91).

EL CASO, que es el del 30/09 (Limón de Día con rechazo y reenvío):

  10/09  guía R arma 60 cajas de Día
  10/09  se arman 60 para Día                 -> se llevan las 60 cajas
  11/09  vuelven 60 rechazadas, destino stock -> lote de cajas, con su costo
  11/09  se arman 20 para OTRO cliente, en cajón (ficha SIN envase)
  12/09  se reenvían 60 a Día                 -> las 60 del rechazo
  12/09  10 más para Día, sin caja que las cubra -> esperan 10

El armado en cajón sale del CAJÓN (la compra) y no toca las cajas: el
pedido se arma según la ficha del cliente (dueño, 30/09). Hasta ese día se
llevaba 20 cajas del rechazo y dejaba al reenvío esperando 20.

Mismo interruptor que el humo: sin Postgres se saltea, y con
HUMO_OBLIGATORIO=1 falla.
"""
import datetime
import os
import sys
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Super'), (2, 'EJEMPLO Catering');
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Citrico');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
-- ficha 1 CON caja (la del super) y ficha 2 SIN caja (el catering, en cajon)
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 16, 'kilo', 1), (2, 2, 1, 16, 'kilo', null);

insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (1, 1, 1, '2026-09-05', 200, 16, 3200, 100, 'recepcionado',
          '2026-09-05 18:00-03', 200, 16);

insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra)
  overriding system value
  values (1, 1, '2026-09-10', 60, 60, 0, 0, 150, 1, 1, 1, true);

insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 1, '2026-09-10', 'texto'), (2, 2, '2026-09-11', 'texto'),
         (3, 1, '2026-09-12', 'texto');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
                               cantidad_armada, armado_el)
  overriding system value
  values (1, 1, 'EJEMPLO Suc A', 1, 1, 60, 60, '2026-09-10 13:00-03'),
         (2, 2, 'EJEMPLO Suc B', 1, 2, 20, 20, '2026-09-11 14:00-03'),
         (3, 3, 'EJEMPLO Suc A', 1, 1, 60, 60, '2026-09-12 10:00-03'),
         (4, 3, 'EJEMPLO Suc B', 1, 1, 10, 10, '2026-09-12 11:00-03');

insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema, cliente_id, pedido_renglon_id,
                               destino_rechazo, costo_por_bulto)
  values (1, '2026-09-11', 'reingreso_rechazo', 60, 'rechazo del super', 0, 1, 1,
          'stock', 150);
"""


@pytest.fixture(scope="module")
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay un Postgres usable.")
        pytest.skip("sin Postgres local: se corre con el humo antes de desplegar")
    url = preparar_base()
    if url is None:
        pytest.fail("no se pudo preparar la base con db/esquema_completo.sql")
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    return url


def _con(url, funcion):
    import app.db as db
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        return getattr(db, funcion)()


def test_el_RECHAZO_que_vuelve_entra_como_CAJA_y_cubre_el_reenvio(base):
    """El rechazo del 11 es un lote de cajas con su costo congelado.

    El reenvío del 12 sale entero de ahí. Lo único que espera es el renglón
    de 10 que no tiene ninguna caja que lo cubra.
    """
    filas = _con(base, "armados_esperando_guia_r")

    assert [(f["renglon_id"], f["esperan"]) for f in filas] == [(4, 10.0)]


def test_el_armado_EN_CAJON_sale_del_cajon_y_no_toca_las_cajas(base):
    """El pedido se arma según la ficha: el catering (sin envase) sale de la compra."""
    import app.db as db

    with patch.dict(os.environ, {"DATABASE_URL": base}):
        _nombres, rejuego = db._rejuego_de_armados_con_caja()
    catering = next(s for s in rejuego[1] if s.get("renglon_id") == 2)

    assert [(c["tipo_lote"], c["bultos"]) for c in catering["consumos_lotes"]] == [("guia", 20.0)]


def test_el_detalle_SUMA_lo_mismo_que_el_numero_de_la_alerta(base):
    """Dos lectores del mismo rejuego: la lista y el conteo no pueden diferir."""
    filas = _con(base, "armados_esperando_guia_r")
    total = _con(base, "contar_bultos_esperando_guia_r")["casos"]

    assert len(filas) >= 1
    assert round(sum(f["esperan"] for f in filas), 2) == total


def test_cada_fila_dice_ARMADO_PEDIDO_CLIENTE_y_SUCURSAL(base):
    fila = _con(base, "armados_esperando_guia_r")[0]

    assert fila["articulo"] == "EJEMPLO Citrico"
    assert fila["fecha_armado"] == datetime.date(2026, 9, 12)
    assert fila["fecha_pedido"] == datetime.date(2026, 9, 12)
    assert fila["pedido_id"] == 3
    assert fila["cliente"] == "EJEMPLO Super"
    assert fila["sucursal"] == "EJEMPLO Suc B"


def test_la_columna_cuenta_las_cajas_que_se_llevan_renglones_SIN_FICHA(base):
    """El catering en cajón no cuenta (no toma cajas); un renglón sin ficha sí.

    Se agrega un renglón sin ficha de 5 el 11/09, antes del reenvío: se lleva
    5 cajas del rechazo, que le faltan al reenvío (renglón 3); el de 10 sigue
    esperando 10.
    """
    import psycopg2
    import app.db as db

    conexion = psycopg2.connect(base)
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, cantidad,"
                " cantidad_armada, armado_el) overriding system value values"
                " (5, 2, 'EJEMPLO Suc B', 1, 5, 5, '2026-09-11 15:00-03')")
        with patch.object(db, "obtener_conexion", return_value=_SinCerrar(conexion)):
            filas = db.armados_esperando_guia_r()
    finally:
        conexion.rollback()
        conexion.close()

    assert [(f["renglon_id"], f["esperan"], f["cajas_a_armados_sin_ficha"]) for f in filas] \
        == [(3, 5.0, 5.0), (4, 10.0, 5.0)]
    assert _con(base, "armados_esperando_guia_r")[0]["cajas_a_armados_sin_ficha"] == 0.0


def test_CONTROL_sin_el_renglon_de_10_no_espera_nada(base):
    """El control: sacado el único faltante, la lista queda vacía.

    Se anula adentro de una transacción que se deshace, así la siembra del
    módulo queda como estaba para los demás tests.
    """
    import psycopg2
    import app.db as db

    conexion = psycopg2.connect(base)
    try:
        with conexion.cursor() as cursor:
            cursor.execute("update pedidos_renglones set anulado_el = now() where id = 4")
        with patch.object(db, "obtener_conexion", return_value=_SinCerrar(conexion)):
            filas = db.armados_esperando_guia_r()
    finally:
        conexion.rollback()
        conexion.close()

    assert filas == []


def test_el_lote_del_rechazo_dice_EN_CAJON_segun_la_ficha_del_renglon(base):
    """El rechazo del súper (ficha con caja) es caja; uno del catering, cajón."""
    import psycopg2
    import app.db as db

    conexion = psycopg2.connect(base)
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad,"
                " motivo, stock_sistema, cliente_id, pedido_renglon_id, destino_rechazo,"
                " costo_por_bulto) values (1, '2026-09-11', 'reingreso_rechazo', 5,"
                " 'rechazo del catering', 0, 2, 2, 'stock', 100)")
            entradas, _salidas = db._entradas_y_salidas_stock(cursor, 1)
    finally:
        conexion.rollback()
        conexion.close()

    rechazos = sorted((float(e["cantidad"]), e["en_cajon"])
                      for e in entradas if e["tipo_lote"] == "reingreso_rechazo")
    assert rechazos == [(5.0, True), (60.0, False)]
    assert all(e["en_cajon"] is False for e in entradas if e["tipo_lote"] != "reingreso_rechazo")


class _SinCerrar:
    """La conexión de la transacción abierta, sin que `close()` la corte."""

    def __init__(self, conexion):
        self._conexion = conexion

    def cursor(self):
        return self._conexion.cursor()

    def close(self):
        pass
