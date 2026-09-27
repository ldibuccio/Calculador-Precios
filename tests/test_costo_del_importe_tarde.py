"""Un importe que se carga TARDE completa el costo de las guías R que ya consumieron la compra.

EL CASO (Frutamax, 26/09): la compra 776 recibió su importe el 25/09 a las
04:04, y las guías R 502 y 527 de Palta, del 23 y el 24/09, siguieron con el
consumo y el total en NULL. "Completar costo" existía como botón, guía por
guía, y el que carga el precio no sabe qué guías lo estaban esperando.

Corre contra Postgres con el esquema REAL: lo que se verifica es que el SQL
de la cascada parsea y hace lo que dice, y eso un cursor falso no lo puede ver
(corolario 89). El fixture siembra las guías R a mano, directo en las tablas,
porque es la forma de dejarlas en el estado exacto del caso: consumidas antes
de que exista el precio.
"""
import io
import os
import sys
from datetime import date

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

    (sufijo,), = sql("SELECT nextval(pg_get_serial_sequence('articulos','id'))")
    (articulo,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id",
                       (f"EJEMPLO Art {sufijo}",))
    (proveedor,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) RETURNING id",
                        (f"EJEMPLO Prov {sufijo}", f"L{sufijo % 100:02d}P{(sufijo // 100) % 100:02d}"))

    def compra(importe):
        (cid,), = sql(
            """INSERT INTO compras (fecha_operacion, articulo_id, proveedor_id, importe,
                   cantidad_cajones, contenido_por_cajon, cantidad_kilos, estado)
               VALUES (%s, %s, %s, %s, 10, 16, 160, 'recepcionado') RETURNING id""",
            (date(2026, 3, 5), articulo, proveedor, importe))
        return cid

    def guia(tomados, primera, consumos, costo_total=None, cpbp=None, anulada=False):
        (rid,), = sql(
            """INSERT INTO reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                   bultos_segunda, bultos_merma, costo_total, costo_por_bulto_primera, anulado_el)
               VALUES (%s, %s, %s, %s, 0, 0, %s, %s, %s) RETURNING id""",
            (articulo, date(2026, 3, 6), tomados, primera, costo_total, cpbp,
             date(2026, 3, 7) if anulada else None))
        for origen, origen_id, bultos, costo in consumos:
            sql("""INSERT INTO reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos, costo_por_bulto)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (rid, origen, origen_id if origen == "compra" else None, origen_id, bultos, costo))
        return rid

    def costo(rid):
        fila, = sql("SELECT costo_total, costo_por_bulto_primera FROM reprocesos WHERE id = %s", (rid,))
        return tuple(None if v is None else float(v) for v in fila)

    def consumos(rid):
        return sorted((None if v is None else float(v) for (v,) in
                      sql("SELECT costo_por_bulto FROM reprocesos_consumos WHERE reproceso_id = %s", (rid,))),
                      key=lambda v: (v is None, v or 0))

    return d, sql, compra, guia, costo, consumos


def _el_caso(galpon):
    """La compra sin precio, la guía que la consumió, y la guía que consumió
    la PRIMERA de esa guía — que es la mitad de "todo lo que dependa"."""
    _, _, compra, guia, _, _ = galpon
    sin_precio = compra(None)
    con_precio = compra(100)
    r1 = guia(10, 5, [("compra", sin_precio, 10, None)])
    r2 = guia(5, 4, [("reproceso", r1, 3, None), ("compra", con_precio, 2, 100)])
    anulada = guia(10, 5, [("compra", sin_precio, 10, None)], anulada=True)
    return sin_precio, r1, r2, anulada


def test_COMPRAS_SIN_PRECIO_completa_la_guia_y_la_que_consumio_su_primera(galpon):
    d, _, _, _, costo, consumos = galpon
    sin_precio, r1, r2, anulada = _el_caso(galpon)

    d.actualizar_importe_compra(sin_precio, 1000)

    # 10 bultos a 1000 = 10000, repartido en 5 de primera = 2000 por caja.
    assert consumos(r1) == [1000.0]
    assert costo(r1) == (10000.0, 2000.0)
    # La de abajo: 3 cajas de R1 a 2000 + 2 bultos a 100 = 6200, en 4 = 1550.
    assert consumos(r2) == [100.0, 2000.0]
    assert costo(r2) == (6200.0, 1550.0)
    # La anulada no entra: su primera no es un lote de nadie.
    assert costo(anulada) == (None, None)


def test_la_EDICION_tambien_completa(galpon):
    d, _, _, _, costo, _ = galpon
    sin_precio, r1, r2, _ = _el_caso(galpon)

    d.actualizar_precio_compra(sin_precio, 1000, None)

    assert costo(r1) == (10000.0, 2000.0)
    assert costo(r2) == (6200.0, 1550.0)


def test_una_RENEGOCIACION_no_recostea_lo_que_ya_estaba_congelado(galpon):
    """El control: sin éste, una versión que pisara todo pasa los de arriba.
    El costo de una guía R es un documento congelado a propósito."""
    d, _, compra, guia, costo, consumos = galpon
    cid = compra(500)
    rid = guia(10, 5, [("compra", cid, 10, 500)], costo_total=5000, cpbp=1000)

    d.actualizar_precio_compra(cid, 900, None)

    assert consumos(rid) == [500.0]
    assert costo(rid) == (5000.0, 1000.0)


def test_una_guia_con_un_consumo_SIN_PRECIO_POSIBLE_sigue_incompleta(galpon):
    """Completar un consumo no es cerrar la guía: si le queda uno que no
    puede tener precio, el total sigue en NULL. Mejor incompleto visible que
    un invento."""
    d, _, compra, guia, costo, consumos = galpon
    cid = compra(None)
    rid = guia(12, 6, [("compra", cid, 10, None), ("ajuste", 1, 2, None)])

    d.actualizar_importe_compra(cid, 1000)

    assert consumos(rid) == [1000.0, None]
    assert costo(rid) == (None, None)
    assert d.completar_costo_reproceso(rid) == {"completado": False, "sin_precio": 1}


def test_el_BOTON_completa_y_tambien_baja_la_cascada(galpon):
    d, sql, _, _, costo, _ = galpon
    sin_precio, r1, r2, _ = _el_caso(galpon)
    sql("UPDATE compras SET importe = 1000 WHERE id = %s", (sin_precio,))   # a mano, sin cascada

    assert d.completar_costo_reproceso(r1) == {"completado": True, "sin_precio": 0}
    assert costo(r2) == (6200.0, 1550.0)


def test_la_MIGRACION_completa_lo_que_ya_estaba_y_una_segunda_corrida_no_hace_nada(galpon):
    """El arreglo de las guías que ya existen. Se lo corre DOS veces: la
    segunda es Palmala, donde no hay nada que completar, y tiene que salir sin
    error y sin tocar nada."""
    _, sql, _, _, costo, _ = galpon
    sin_precio, r1, r2, anulada = _el_caso(galpon)
    sql("UPDATE compras SET importe = 1000 WHERE id = %s", (sin_precio,))   # el importe tarde, sin el código nuevo

    bloque = io.open(os.path.join(RAIZ, "db/costo_tarde_1_completar_lo_que_ya_esta.sql"),
                     encoding="utf-8").read()
    sql(bloque)
    assert costo(r1) == (10000.0, 2000.0)
    assert costo(r2) == (6200.0, 1550.0)
    assert costo(anulada) == (None, None)

    sql(bloque)
    assert costo(r2) == (6200.0, 1550.0)

    verificacion = io.open(os.path.join(RAIZ, "db/costo_tarde_1_verificacion.sql"),
                           encoding="utf-8").read()
    fila, = sql(verificacion)
    assert fila[0] == "costo_tarde_1_completar_lo_que_ya_esta"
    assert fila[1:4] == (0, 0, 0)
