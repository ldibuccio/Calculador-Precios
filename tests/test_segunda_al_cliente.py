# -*- coding: utf-8 -*-
"""Mandarle mercadería de SEGUNDA a un cliente que la acepta (dueño, 23/09).

LAS CUATRO DECISIONES que esto verifica, y ninguna se deduce de otra:

1. Misma ficha, mismo artículo, mismo precio: la segunda viaja ADENTRO del
   renglón (`pedidos_renglones.bultos_de_segunda`), no en un renglón aparte.
2. Parte y parte: 4 de segunda y 6 de primera en el mismo renglón.
3. Sale del POOL de segunda, no del stock de primera — y el stock de primera
   baja solo por la parte de primera.
4. Nunca se elige sola: sin tilde en el cliente no se puede, y retildar sin
   decirla la limpia.

POR QUÉ CONTRA LA BASE: las guardas del armado leen el pool con la MISMA
consulta que el Remanente, y la pared de la base (el CHECK
`pedidos_renglones_segunda_solo_armado`) solo se ve con el esquema real. Con
la base mockeada, desmarcar sin limpiar la segunda pasaría en verde y
reventaría en producción (corolario 75).

EL INTERRUPTOR ES EL DEL HUMO: sin Postgres se saltea, y con
HUMO_OBLIGATORIO=1 dejar de poder correrlo FALLA.
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

# EL GALPÓN, y cada número está para que una pata leída mal dé OTRO número:
#
#   compra        30 cajones recepcionados el 05/09
#   guía R        toma 10, produce 8 de primera y 6 de segunda
#                 -> stock de primera 30 - 10 + 8 = 28 · pool de segunda 6
#
#   CATERING  acepta segunda · renglón 1: pide 10
#   SUPER     NO la acepta   · renglón 2: pide 5
SIEMBRA = """
insert into clientes (id, nombre, acepta_segunda) overriding system value
  values (1, 'EJEMPLO Catering', true), (2, 'EJEMPLO Super', false);
insert into articulos (id, nombre, grupo) overriding system value
  values (1, 'EJEMPLO Tomate', 'hortaliza');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta)
  overriding system value values (1, 1, 1, 10, 'kilo'), (2, 2, 1, 10, 'kilo');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value values
  (1, 1, 1, '2026-09-05', 30, 16, 480, 100, 'recepcionado', '2026-09-05 18:00-03', 30, 16);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera)
  overriding system value values (1, 1, '2026-09-06', 10, 8, 6, 0, 150);
insert into pedidos (id, cliente_id, fecha_operacion, creado_en, origen) overriding system value
  values (1, 1, '2026-09-10', '2026-09-10 08:00-03', 'mail'),
         (2, 2, '2026-09-10', '2026-09-10 08:00-03', 'mail');
insert into pedidos_sucursales (pedido_id, sucursal) values (1, 'EJ'), (2, 'EJ');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad)
  overriding system value values (1, 1, 'EJ', 1, 1, 10), (2, 2, 'EJ', 1, 2, 5);
"""


@pytest.fixture
def base():
    """Una base NUEVA por test: las guardas dependen del pool, y un test que
    deja segunda gastada le cambia el número al siguiente."""
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail(
                "HUMO_OBLIGATORIO=1 y no hay un Postgres usable: la segunda al "
                "cliente no se verificó en esta corrida.")
        pytest.skip("sin Postgres local: se corre con el humo antes de desplegar")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        yield url


def _renglon(url, renglon_id):
    import psycopg2
    conexion = psycopg2.connect(url)
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT armado_el IS NOT NULL, cantidad_armada, bultos_de_segunda "
                "FROM pedidos_renglones WHERE id = %s", (renglon_id,))
            armado, cantidad_armada, segunda = cursor.fetchone()
        return armado, (float(cantidad_armada) if cantidad_armada is not None else None), (
            float(segunda) if segunda is not None else None)
    finally:
        conexion.close()


def _tomate():
    from app.db import stock_deposito_por_articulo
    filas = stock_deposito_por_articulo(datetime.date(2030, 1, 1), articulo_id=1)
    assert len(filas) == 1, "el artículo sembrado no apareció: la medición no miró nada"
    return filas[0]


def test_el_punto_de_partida_es_28_de_primera_y_6_de_segunda(base):
    """El control: sin él, los números de abajo no se pueden leer."""
    fila = _tomate()
    assert (fila["stock"], fila["segunda"]) == (28, 6)


def test_4_de_segunda_y_6_de_primera_bajan_CADA_UNO_de_su_lado(base):
    """La decisión B: parte y parte. El stock de primera baja 6, no 10; el pool
    baja 4. Con la segunda leída como primera, el stock daría 18 y el pool 6."""
    from app.db import marcar_renglon_armado

    marcar_renglon_armado(1, None, 100.0, bultos_de_segunda=4)

    # cantidad_armada EXPLÍCITA aunque sea completa: si quedara NULL, corregir
    # lo pedido después movería lo armado por debajo de la segunda.
    assert _renglon(base, 1) == (True, 10.0, 4.0)
    fila = _tomate()
    assert (fila["stock"], fila["segunda"]) == (28 - 6, 6 - 4)


def test_TODO_de_segunda_no_saca_nada_de_la_primera(base):
    from app.db import marcar_renglon_armado

    marcar_renglon_armado(1, 6.0, None, bultos_de_segunda=6)

    fila = _tomate()
    assert (fila["stock"], fila["segunda"]) == (28, 0)


def test_un_cliente_SIN_el_tilde_no_puede_llevar_segunda_y_NO_se_escribe_nada(base):
    """Día no acepta. La guarda va donde se escribe: un POST armado a mano no
    ve que la pantalla no le ofreció el campo."""
    from app.db import SegundaNoPermitida, marcar_renglon_armado

    with pytest.raises(SegundaNoPermitida, match="no acepta mercadería de segunda"):
        marcar_renglon_armado(2, None, None, bultos_de_segunda=1)

    assert _renglon(base, 2) == (False, None, None)


def test_la_segunda_no_puede_ser_MAS_que_lo_armado(base):
    from app.db import SegundaNoPermitida, marcar_renglon_armado

    with pytest.raises(SegundaNoPermitida, match="no puede ser más"):
        marcar_renglon_armado(1, 3.0, None, bultos_de_segunda=4)
    assert _renglon(base, 1) == (False, None, None)


def test_no_se_puede_mandar_MAS_segunda_de_la_que_hay(base):
    """El pool dice 6: pedir 7 rebota nombrando cuánto hay."""
    from app.db import SegundaNoPermitida, marcar_renglon_armado

    with pytest.raises(SegundaNoPermitida, match="hay 6 de segunda"):
        marcar_renglon_armado(1, None, None, bultos_de_segunda=7)
    assert _renglon(base, 1) == (False, None, None)


def test_RETILDAR_no_rebota_contra_la_segunda_que_el_mismo_renglon_ya_tenia(base):
    """Con 4 ya puestos el pool dice 2. Retildar con 6 tiene que entrar: los 4
    son del propio renglón y vuelven al pool al retildar. Sin sumarle lo que ya
    tenía, el pool diría 2 y rebotaría contra sí mismo."""
    from app.db import marcar_renglon_armado

    marcar_renglon_armado(1, None, None, bultos_de_segunda=4)
    marcar_renglon_armado(1, None, None, bultos_de_segunda=6)

    assert _renglon(base, 1) == (True, 10.0, 6.0)
    assert _tomate()["segunda"] == 0


def test_retildar_SIN_decirla_la_limpia_porque_nunca_se_elige_sola(base):
    from app.db import marcar_renglon_armado

    marcar_renglon_armado(1, None, None, bultos_de_segunda=4)
    marcar_renglon_armado(1, None, None)

    assert _renglon(base, 1) == (True, None, None)
    assert (_tomate()["stock"], _tomate()["segunda"]) == (18, 6)


def test_DESTILDAR_y_ANULAR_pasan_la_pared_de_la_base(base):
    """Los dos escritores que sacan el armado tienen que sacar la segunda: sin
    eso el CHECK los rechaza. Un test mockeado no puede ver esto."""
    from app.db import anular_renglon_pedido, desmarcar_renglon_armado, marcar_renglon_armado

    marcar_renglon_armado(1, None, None, bultos_de_segunda=4)
    desmarcar_renglon_armado(1)
    assert _renglon(base, 1) == (False, None, None)

    marcar_renglon_armado(1, None, None, bultos_de_segunda=4)
    anular_renglon_pedido(1)
    assert _renglon(base, 1) == (False, None, None)
    assert _tomate()["segunda"] == 6


def test_la_PARED_de_la_base_existe_en_el_esquema(base):
    """El control del test de arriba: si el CHECK no estuviera en
    `db/esquema_completo.sql`, desmarcar sin limpiar pasaría igual."""
    import psycopg2
    conexion = psycopg2.connect(base)
    try:
        with conexion.cursor() as cursor:
            with pytest.raises(psycopg2.errors.CheckViolation):
                cursor.execute("UPDATE pedidos_renglones SET bultos_de_segunda = 1 WHERE id = 1")
    finally:
        conexion.close()


def test_el_FIFO_costea_SOLO_la_primera_y_la_venta_cuenta_los_10(base):
    """La decisión C: la segunda se vende a precio lleno y no cuesta nada. El
    FIFO recibe 6 (la primera), y la fila de la rentabilidad dice 10 bultos."""
    from app.db import entradas_y_salidas_stock_articulo, marcar_renglon_armado
    from core.costo_real import atribuir_costos_fifo

    marcar_renglon_armado(1, None, 100.0, bultos_de_segunda=4)
    entradas, salidas = entradas_y_salidas_stock_articulo(1)
    armados = [s for s in salidas if s["tipo"] == "armado"]

    assert [(float(s["cantidad"]), float(s["de_segunda"])) for s in armados] == [(6.0, 4.0)]
    costeadas = [s for s in atribuir_costos_fifo(entradas, salidas) if s["tipo"] == "armado"]
    # 6 bultos de la primera de la guía R, a $150 (un armado prefiere lo
    # trabajado). Con los 10 costeados daría 8 x 150 + 2 x 100 = 1400.
    assert costeadas[0]["costo"] == pytest.approx(900.0)
