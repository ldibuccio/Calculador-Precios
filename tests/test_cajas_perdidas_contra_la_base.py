# -*- coding: utf-8 -*-
"""Lo que Cajas perdidas CONTESTA, no lo que pregunta.

POR QUÉ ESTE ARCHIVO EXISTE. Los tests de `cajas_perdidas` son de TEXTO:
miran que el SQL pida el pase, que filtre los sueltos, que dé vuelta el
signo. Eso verifica que la consulta PREGUNTE lo correcto — y con la base
mockeada el valor lo entrega el fixture, así que nada verifica que
CONTESTE.

Lo encontraron dos canarios en CERO el 21/09, y los dos son realistas:

  · agregarle un `AND false` a la rama del pase: el texto queda intacto,
    los tres asserts pasan, y la consulta no trae un solo pase;
  · dejar `cajas_por_pase` devolviendo `0` con el alias puesto: el assert
    `"cajas_por_pase" in sql` pasa igual y la columna miente para siempre.

Ninguno de los dos es un `AND false` escrito a mano en la vida real; la
CLASE sí lo es —un join mal puesto, un filtro que se cuela, una columna
renombrada— y ninguna cantidad de asserts de texto los puede ver.

EL INTERRUPTOR ES EL DEL HUMO, y por la misma razón: sin Postgres esto se
saltea, y un test salteado se lee exactamente igual que uno verde. Con
HUMO_OBLIGATORIO=1 —que el workflow pone— dejar de poder correrlo FALLA.
"""
import datetime
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

# EL GALPÓN QUE SE PLANTA, y los tres casos están a propósito:
#
#   · 3 cajas ARMADAS que pasan a segunda      -> pierden caja  (lo nuevo)
#   · 4 que volvieron del súper y se remiten   -> pierden caja  (lo de antes)
#   · 9 bultos SUELTOS que pasan a segunda     -> NO pierden caja
#
# El tercero es el que distingue una consulta que filtra de una que suma
# todo: sin él, contar los sueltos daría 16 y se leería igual de prolijo.
SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Dia');
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Berenjena');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja Dia');
insert into envases_costo_historial (envase_id, costo, vigente_desde) values (1, 100, '2026-01-01');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 6, 'kilo', 1);
insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 1, '2026-09-10', 'texto');
insert into pedidos_renglones (id, pedido_id, articulo_id, ficha_id, sucursal, cantidad, armado_el)
  overriding system value values (1, 1, 1, 1, 'BZ', 4, '2026-09-10 10:00-03');

insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema, bultos_segunda, ficha_id)
  values (1, '2026-09-11', 'pase_a_segunda', -3, 'se pusieron feas', 10, 3, 1);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo, stock_sistema,
                               pedido_renglon_id, destino_rechazo, bultos_segunda, cliente_id)
  values (1, '2026-09-12', 'reingreso_rechazo', 4, 'volvio del super', 5, 1, 'segunda', 4, 1);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema, bultos_segunda)
  values (1, '2026-09-12', 'pase_a_segunda', -9, 'se pusieron feas', 5, 9);
"""


@pytest.fixture(scope="module")
def base():
    """La base REAL, con `db/esquema_completo.sql` y la siembra de este caso."""
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail(
                "HUMO_OBLIGATORIO=1 y no hay un Postgres usable: lo que Cajas "
                "perdidas CONTESTA no se verificó en esta corrida. Revisá el "
                "servicio de Postgres del runner.")
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


def _con(url, funcion, *args):
    """Corre una función de app.db contra ESA base y nada más.

    `obtener_conexion` lee DATABASE_URL en CADA llamada, así que alcanza con
    ponerla en el entorno del bloque — sin subproceso y sin que quede puesta
    para el resto de la suite.
    """
    from unittest.mock import patch
    import app.db as db
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        return getattr(db, funcion)(*args)


DESDE, HASTA = datetime.date(2026, 9, 1), datetime.date(2026, 9, 30)


def test_la_consulta_TRAE_el_pase_de_cajas_armadas(base):
    """3 del pase + 4 del rechazo = 7 cajas a $100 = $700.

    El canario del `AND false` daba CERO contra el texto y acá da 4 y $400.
    """
    r = _con(base, "cajas_perdidas", DESDE, HASTA)

    assert len(r["renglones"]) == 1, r["renglones"]
    fila = r["renglones"][0]
    assert fila["cajas"] == 7.0
    assert fila["pesos"] == 700.0
    assert fila["veces"] == 2
    assert (fila["cliente"], fila["articulo"], fila["envase"]) == (
        "EJEMPLO Dia", "EJEMPLO Berenjena", "EJEMPLO Caja Dia")


def test_los_SUELTOS_no_entran_aunque_pasen_a_segunda(base):
    """9 bultos sueltos pasaron a segunda y no llevan caja nuestra.

    Sin el filtro el total daría 16 y se leería igual de prolijo — y los
    sueltos son el caso NORMAL del pase, así que el número sería casi todo
    invento.
    """
    r = _con(base, "cajas_perdidas", DESDE, HASTA)
    assert r["cajas"] == 7.0, "entraron los 9 sueltos"


def test_la_columna_que_separa_los_dos_origenes_CONTESTA_y_no_solo_existe(base):
    """3 de las 7 son del pase. El canario que la deja en `0` con el alias
    puesto pasaba todos los asserts de texto.
    """
    fila = _con(base, "cajas_perdidas", DESDE, HASTA)["renglones"][0]
    assert fila["cajas_por_pase"] == 3.0
    assert fila["cajas_por_pase"] < fila["cajas"], (
        "si fueran iguales, el rechazo no estaría entrando")


def test_el_SIGNO_del_pase_suma_en_vez_de_restar(base):
    """La cantidad del pase es NEGATIVA y la del reingreso positiva. Sumadas
    crudas se restan entre sí: 4 − 3 = 1, que es un número plausible.
    """
    fila = _con(base, "cajas_perdidas", DESDE, HASTA)["renglones"][0]
    assert fila["cajas"] != 1.0, "el pase se está restando del rechazo"
    assert fila["cajas"] == 7.0
