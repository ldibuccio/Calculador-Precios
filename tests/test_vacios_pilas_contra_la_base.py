# -*- coding: utf-8 -*-
"""El stock de VACÍOS DEL DEPÓSITO por PILA (proveedor y marca), contra la base.

CONTRA POSTGRES, porque la cuenta no vive en ninguna columna: se deriva en
cada lectura de cinco tablas, y con la base mockeada el número lo decidiría
el fixture (corolario 91).

EL GALPÓN, armado para que cada pata leída mal dé OTRO número. LA FOTO VA EN
MARZO y no el 25/09 como en producción, a propósito: el corte compara contra
el INSTANTE de la foto, y los movimientos que el test crea con `now()` tienen
que caer después de ella pase lo que pase con el reloj (corolario 95). Con la
foto el 25/09, el 25/09 mismo el test medía el día y no la regla.

  Proveedor EJ Con Foto — foto 10, marcas EJ Roja y EJ Azul
    01/03  recibido CON seña 20 (Roja) 10hs     -> ANTES de la foto de las 12hs: ya está en ella
    26/09  recibido CON seña 5  (Roja)          -> +5 Roja
    26/09  recibido SIN seña 7  (Roja)          -> no suma: sin seña no hay cajón que devolver
    26/09  recibido CON seña 4, estado pendiente-> no suma: no llegó
    20/02  devuelto 6 (sin asignar)             -> ya está en la foto
    27/09  devuelto 3 (sin asignar)             -> −3 sin asignar
    27/09  devuelto 2 (sin asignar), ANULADO    -> no cuenta
    ajuste +2 (Roja)                            -> +2 Roja
    ajuste −1 (Azul), ANULADO                   -> no cuenta
    asignación 4 de sin asignar a Roja          -> −4 sin asignar, +4 Roja

      sin asignar = 10 − 3 − 4 = 3
      Roja        = 5 + 2 + 4  = 11
      Azul        = sin movimientos vivos, cero -> NO se muestra

  Proveedor EJ Sin Foto (dado de alta después del corte)
    27/09  recibido CON seña 6 (sin marca)      -> 6: sin foto suma todo

  Proveedor EJ Mismo Dia — foto 5 el 05/03 a las 12hs
    05/03  recibido 3 a las 10hs                -> ya está en la foto
    05/03  recibido 2 a las 16hs                -> +2: EL MISMO DÍA, después de la foto
      = 7. Comparando por FECHA daba 5: lo del resto del día del corte se perdía.
"""
import os
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into articulos (id, nombre) overriding system value values (901, 'EJEMPLO Fruta');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (901, 'EJ Con Foto', 'N90P01'), (902, 'EJ Sin Foto', 'N90P02'), (903, 'EJ Otro', 'N90P03'),
         (904, 'EJ Mismo Dia', 'N90P04');
insert into marcas_vacio (id, proveedor_id, nombre, nombre_normalizado) overriding system value
  values (911, 901, 'EJ Roja', 'ej roja'), (912, 901, 'EJ Azul', 'ej azul'), (913, 903, 'EJ Ajena', 'ej ajena');
insert into vacios_deposito_foto (proveedor_id, cantidad, fecha, creado_en)
  values (901, 10, '2026-03-01', '2026-03-01 12:00-03'), (903, 0, '2026-03-01', '2026-03-01 12:00-03'),
         (904, 5, '2026-03-05', '2026-03-05 12:00-03');
insert into compras (fecha_operacion, articulo_id, proveedor_id, cantidad_kilos, cantidad_cajones,
                     contenido_por_cajon, estado, procesada_el, sena, marca_vacio_id) values
  ('2026-03-01', 901, 901, 200, 20, 10, 'recepcionado', '2026-03-01 10:00-03', 500, 911),
  ('2026-09-26', 901, 901, 50,  5, 10, 'recepcionado', '2026-09-26 09:00-03', 800, 911),
  ('2026-09-26', 901, 901, 70,  7, 10, 'recepcionado', '2026-09-26 09:00-03', null, 911),
  ('2026-09-26', 901, 901, 40,  4, 10, 'pendiente',    null,                   800, 911),
  ('2026-09-27', 901, 902, 60,  6, 10, 'recepcionado', '2026-09-27 09:00-03', 300, null),
  ('2026-03-05', 901, 904, 30,  3, 10, 'recepcionado', '2026-03-05 10:00-03', 100, null),
  ('2026-03-05', 901, 904, 20,  2, 10, 'recepcionado', '2026-03-05 16:00-03', 100, null);
insert into vacios_deposito_devoluciones (proveedor_id, cantidad, stock_sistema, creado_en, foto_ruta, anulado_el) values
  (901, 6, 0, '2026-02-20 12:00-03', 'x.jpg', null),
  (901, 3, 0, '2026-09-27 12:00-03', 'x.jpg', null),
  (901, 2, 0, '2026-09-27 12:00-03', 'x.jpg', now());
insert into vacios_deposito_ajustes (proveedor_id, marca_vacio_id, cantidad, motivo, stock_sistema, anulado_el) values
  (901, 911, 2, 'EJ aparecieron', 0, null),
  (901, 912, -1, 'EJ anulado', 0, now());
insert into vacios_deposito_asignaciones (proveedor_id, marca_desde_id, marca_hasta_id, cantidad, stock_sistema)
  values (901, null, 911, 4, 0);
"""


@pytest.fixture()
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay un Postgres usable: el stock de "
                        "vacíos por pila no se verificó en esta corrida.")
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


def _pilas(proveedor_id):
    import app.db as db
    proveedor = next(p for p in db.stock_de_vacios_deposito() if p["id"] == proveedor_id)
    return {pila["marca"]: pila["stock"] for pila in proveedor["pilas"]}, proveedor["stock"]


def test_cada_PATA_del_stock_cae_en_su_PILA(base):
    assert _pilas(901) == ({None: 3, "EJ Roja": 11}, 14)


def test_un_proveedor_SIN_FOTO_suma_todo_lo_suyo(base):
    assert _pilas(902) == ({None: 6}, 6)


def test_lo_recibido_el_MISMO_DIA_de_la_foto_cuenta_segun_la_HORA(base):
    """El bug que salió corriendo la cuenta, no leyéndola: el corte es un INSTANTE."""
    assert _pilas(904) == ({None: 7}, 7)


def test_un_proveedor_en_cero_y_sin_movimientos_NO_se_muestra(base):
    import app.db as db
    assert 903 not in {p["id"] for p in db.stock_de_vacios_deposito()}


def test_no_se_DEVUELVE_mas_de_lo_que_dice_el_sistema_y_no_se_escribe_nada(base):
    import app.db as db
    with pytest.raises(ValueError, match="hay 3 cajones"):
        db.crear_devolucion_vacios(901, None, 4, foto_ruta="vale.jpg")
    assert _pilas(901)[0][None] == 3
    db.crear_devolucion_vacios(901, None, 3, foto_ruta="vale.jpg", importe=2400)
    pilas, total = _pilas(901)
    assert pilas[None] == 0 and total == 11
    # la pila que llegó a cero porque se devolvió todo SIGUE a la vista
    assert None in pilas


def test_sin_FOTO_no_es_una_devolucion(base):
    import app.db as db
    with pytest.raises(ValueError, match="ajuste"):
        db.crear_devolucion_vacios(901, 911, 1, foto_ruta="  ")
    assert _pilas(901)[0]["EJ Roja"] == 11


def test_la_BASE_rechaza_el_vale_sin_foto_por_INSERT_y_por_UPDATE(base):
    """vacios_dev_con_foto, sin pasar por la guarda de la escritura (solo lo nuevo, sin compra).

    El UPDATE es el caso que importa: olvidar_foto_borrada ponía la ruta en
    NULL, y con el CHECK puesto eso rebota y tira la limpieza de fotos entera.
    Por eso el vale salió de la retención (25/09)."""
    import psycopg2
    conexion = psycopg2.connect(base)
    try:
        with conexion.cursor() as cursor:
            for sentencia in (
                "INSERT INTO vacios_deposito_devoluciones (proveedor_id, cantidad, stock_sistema) "
                "VALUES (901, 1, 0)",
                "UPDATE vacios_deposito_devoluciones SET foto_ruta = NULL WHERE proveedor_id = 901",
                "UPDATE vacios_deposito_devoluciones SET foto_ruta = '  ' WHERE proveedor_id = 901",
            ):
                with pytest.raises(psycopg2.errors.CheckViolation, match="vacios_dev_con_foto"):
                    cursor.execute(sentencia)
                conexion.rollback()
            # el caso que tiene que PASAR (corolario 30)
            cursor.execute("UPDATE vacios_deposito_devoluciones SET foto_ruta = 'otra.jpg' "
                           "WHERE proveedor_id = 901")
            assert cursor.rowcount == 3
            # Y LA VIEJA, contra una compra y sin foto, se puede ANULAR. Con el
            # CHECK de vacios_marcas_5 (NOT VALID, sin eximir) rebotaba: NOT
            # VALID no exime a lo viejo de los UPDATE (vacios_marcas_7).
            cursor.execute("SELECT id FROM compras WHERE proveedor_id = 901 LIMIT 1")
            (compra_id,), = cursor.fetchall()
            cursor.execute("INSERT INTO vacios_deposito_devoluciones "
                           "(proveedor_id, compra_id, cantidad, stock_sistema) "
                           "VALUES (901, %s, 1, 0) RETURNING id", (compra_id,))
            vieja = cursor.fetchone()[0]
            cursor.execute("UPDATE vacios_deposito_devoluciones SET anulado_el = now() "
                           "WHERE id = %s", (vieja,))
            assert cursor.rowcount == 1
    finally:
        conexion.rollback()
        conexion.close()


def test_la_base_RECHAZA_una_marca_de_OTRO_proveedor(base):
    import app.db as db
    with pytest.raises(ValueError, match="no es de este proveedor"):
        db.crear_ajuste_vacios_deposito(901, 913, 5, "EJ marca ajena")


def test_un_ajuste_sin_MOTIVO_lo_rechaza_la_base(base):
    import app.db as db
    with pytest.raises(ValueError, match="motivo"):
        db.crear_ajuste_vacios_deposito(901, None, 5, "  ")


def test_la_ASIGNACION_mueve_entre_pilas_sin_cambiar_el_total_y_frena_de_mas(base):
    import app.db as db
    with pytest.raises(ValueError, match="hay 11 cajones"):
        db.crear_asignacion_vacios(901, 911, 912, 12)
    db.crear_asignacion_vacios(901, 911, 912, 5)
    assert _pilas(901) == ({None: 3, "EJ Roja": 6, "EJ Azul": 5}, 14)


def test_ANULAR_corrige_el_stock_solo(base):
    import app.db as db
    asignacion = db.crear_asignacion_vacios(901, 911, 912, 5)
    db.anular_asignacion_vacios(asignacion)
    assert _pilas(901) == ({None: 3, "EJ Roja": 11}, 14)
    with pytest.raises(ValueError, match="ya estaba anulada"):
        db.anular_asignacion_vacios(asignacion)


def test_las_MARCAS_no_se_repiten_por_proveedor_pero_si_entre_proveedores(base):
    import app.db as db
    with pytest.raises(ValueError, match="EJ Roja"):
        db.crear_marca_vacio(901, "  ej   ROJA ")
    assert db.crear_marca_vacio(903, "EJ Roja")


def test_el_COTEJO_compara_el_ultimo_conteo_contra_el_stock_de_AHORA(base):
    import app.db as db
    db.crear_conteo_vacios_deposito(901, 911, 20, date(2026, 9, 26))
    db.crear_conteo_vacios_deposito(901, 911, 9, date(2026, 9, 27))
    db.crear_conteo_vacios_deposito(901, None, 3, date(2026, 9, 27))
    filas = {(f["marca"], f["contado"]): f["diferencia"] for f in db.cotejo_de_vacios_deposito()}
    assert filas == {("EJ Roja", 9): 2, (None, 3): 0}


def test_la_SENA_por_cajon_de_la_ultima_recepcion_por_pila(base):
    import app.db as db
    assert db.sena_por_cajon_de_la_ultima_recepcion(901) == {911: 800.0}
    assert db.sena_por_cajon_de_la_ultima_recepcion(902) == {None: 300.0}
