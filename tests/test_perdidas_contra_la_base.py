# -*- coding: utf-8 -*-
"""Lo que Pérdidas CONTESTA, no lo que pregunta.

POR QUÉ ESTE ARCHIVO EXISTE. `perdidas_por_periodo` no es una consulta: es
un REJUEGO. Le pide al FIFO que reparta todo desde el corte y después suma
lo que cayó adentro de la ventana. Con la base mockeada, el reparto lo
decide el fixture —o sea el andamio— así que ningún test de `tests/test_*`
puede ver si el costo que sale es el del lote correcto (corolario 91).

Y acá el número no es para mirar: **va a un estado de resultados.** Un
total plausible y mal es exactamente lo que no se puede permitir.

LOS CUATRO CANARIOS QUE ESTE ARCHIVO MUERDE, y ninguno lo ve un assert de
texto:

  · la merma de caja armada pierde la preferencia por el lote trabajado y
    se costea contra el cajón más viejo: $200 donde van $600;
  · el rejuego se recorta a la ventana en vez de al corte: las entradas
    quedan afuera y **todo sale sin costear** —cero pesos, prolijo—;
  · la caja deja de sumarse en la rama de la merma: $2000 donde van $2100,
    que es la mitad de la regla del dueño (los kilos MÁS la caja);
  · la ventana no se aplica: entra la merma de octubre.

EL INTERRUPTOR ES EL DEL HUMO, y por la misma razón: sin Postgres esto se
saltea, y un test salteado se lee exactamente igual que uno verde. Con
HUMO_OBLIGATORIO=1 —que el workflow pone— dejar de poder correrlo FALLA.

Y LA BASE ES LA DEL HUMO, compartida con los otros dos módulos que corren
contra Postgres. No se pisan porque el fixture es de MÓDULO: pytest
finaliza los de un módulo al pasar a otro, así que volver a este re-siembra.
Medido barajando con `SEMILLA_ORDEN=7`, que los interleava de verdad. Un
fixture de SESIÓN acá sí se los llevaría puestos.
"""
import datetime
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

# EL GALPÓN QUE SE PLANTA. Los números están elegidos para que el ORDEN del
# reparto decida el resultado: si el rejuego se recortara a la ventana, o si
# la merma armada perdiera su preferencia, el total CAMBIA en vez de quedar
# igual por casualidad (corolario 11 — plantar el rival que no tiene que
# ganar).
#
#   corte 31/08 · ventana 10/09 al 30/09
#
#   05/09  entran 10 cajones a $100 el bulto        <- ANTES de la ventana
#   08/09  una guía R toma 5 y arma 10 cajas a $300 <- ANTES de la ventana
#   11/09  3 cajas ARMADAS pasan a segunda          -> $900 + 3 cajas
#   12/09  2 cajas ARMADAS se tiran                 -> $600 + 2 cajas
#   13/09  8 bultos SUELTOS se tiran                -> 5 del cajón + 3 de la
#                                                      primera = $1400, SIN caja
#   05/10  1 caja armada se tira                    <- DESPUÉS de la ventana
#
# El suelto del 13/09 es el que hace que el orden importe: le quedan 5 del
# cajón porque la guía R se llevó los otros 5, así que se desborda a la
# primera. Con el rejuego recortado a la ventana el cajón tendría 10 y el
# número sería otro.
SIEMBRA = """
-- EL CORTE YA VIENE EN EL ESQUEMA (31/08) y no se toca: es el mismo dato
-- que `_fecha_corte` lee en produccion, y re-escribirlo aca seria una segunda
-- version del parametro contra el que se mide.
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Dia');
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Tomate');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja Dia');
insert into envases_costo_historial (envase_id, costo, vigente_desde) values (1, 50, '2026-01-01');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 6, 'kilo', 1);

-- EL CAJON: 10 bultos a $100. `importe` es POR BULTO, no el total.
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (1, 1, 1, '2026-09-05', 10, 16, 160, 100, 'recepcionado',
          '2026-09-05 18:00-03', 10, 16);

-- LA GUIA R: toma 5 cajones y arma 10 cajas de Dia a $300 el bulto.
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra)
  overriding system value
  values (1, 1, '2026-09-08', 5, 10, 0, 0, 300, 1, 1, 1, true);

insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema, bultos_segunda, ficha_id)
  values (1, '2026-09-11', 'pase_a_segunda', -3, 'se pusieron feas', 15, 3, 1);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema, ficha_id)
  values (1, '2026-09-12', 'merma', -2, 'se pudrio', 12, 1);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema)
  values (1, '2026-09-13', 'merma', -8, 'se pudrio', 10);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema, ficha_id)
  values (1, '2026-10-05', 'merma', -1, 'fuera de la ventana', 2, 1);

-- EL ARTICULO SIN COSTO, y es el unico que hace que `bultos_sin_costo` pueda
-- valer algo. Sin el, la linea que lo acumula se puede BORRAR entera y el
-- total sigue dando 0, que es exactamente lo que ya habia (quinta lectura del
-- canario en cero: el fixture ejercita el caso donde el campo perdido estaba
-- vacio). La compra entra SIN importe, que es como queda una que se recibio y
-- todavia no se le cargo el precio.
insert into articulos (id, nombre) overriding system value values (2, 'EJEMPLO Palta');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (2, 1, 2, '2026-09-06', 5, 10, 50, null, 'recepcionado',
          '2026-09-06 18:00-03', 5, 10);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema)
  values (2, '2026-09-14', 'merma', -5, 'se pudrio y no tiene precio', 5);
"""


@pytest.fixture(scope="module")
def base():
    """La base REAL, con `db/esquema_completo.sql` y la siembra de este caso."""
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail(
                "HUMO_OBLIGATORIO=1 y no hay un Postgres usable: lo que "
                "Pérdidas CONTESTA no se verificó en esta corrida. Revisá el "
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


def _perdidas(url, desde, hasta):
    """Corre `perdidas_por_periodo` contra ESA base y nada más.

    `obtener_conexion` lee DATABASE_URL en CADA llamada, así que alcanza con
    ponerla en el entorno del bloque — sin subproceso y sin que quede puesta
    para el resto de la suite.
    """
    from unittest.mock import patch
    import app.db as db
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        return db.perdidas_por_periodo(desde, hasta)


DESDE, HASTA = datetime.date(2026, 9, 10), datetime.date(2026, 9, 30)


def test_la_caja_ARMADA_se_costea_al_costo_de_SU_CAJA_y_no_del_cajon_mas_viejo(base):
    """Los 3 bultos del pase son cajas armadas a $300, no cajones a $100.

    Es la regla del dueño (21/09): *"la pérdida de mercadería es al costo de
    esa caja armada"*. El cajón de $100 es MÁS VIEJO y está ahí a propósito:
    sin la preferencia por el lote trabajado, el FIFO lo elegiría y la cuenta
    daría $300 — un número plausible, un tercio del real.
    """
    r = _perdidas(base, DESDE, HASTA)
    segunda = r["renglones"]["segunda"]

    assert segunda["bultos"] == 3.0
    assert segunda["mercaderia"] == 900.0, "se costeó contra el cajón, no contra la caja"


def test_la_MERMA_de_caja_armada_pierde_los_kilos_MAS_la_caja(base):
    """2 cajas armadas tiradas = $600 de tomate + 2 cajas a $50 = $700.

    Las dos mitades de la regla en un solo assert del total: un canario que
    saque la caja de la rama de la merma deja $600, que se lee igual de
    prolijo.
    """
    r = _perdidas(base, DESDE, HASTA)
    merma = r["renglones"]["merma"]

    # 2 armadas a $300 + 8 sueltos (5 del cajón a $100 + 3 de la primera a
    # $300) + los 5 de Palta, que no tienen precio y por eso no suman pesos.
    assert merma["bultos"] == 15.0
    assert merma["mercaderia"] == 2000.0
    assert merma["cajas"] == 2.0, "las sueltas no llevan caja nuestra"
    assert merma["caja_pesos"] == 100.0
    assert merma["total"] == 2100.0


def test_los_SUELTOS_se_costean_por_FIFO_PURO_y_se_desbordan_al_lote_siguiente(base):
    """8 sueltos contra un cajón al que le quedan 5: 5×$100 + 3×$300 = $1400.

    Éste es el que necesita el REJUEGO COMPLETO. Al cajón le quedan 5 porque
    la guía R del 08/09 —anterior a la ventana— se llevó los otros 5. Con el
    rejuego recortado a la ventana el cajón tendría los 10 puestos y los 8
    saldrían a $800, o directamente sin costear.
    """
    r = _perdidas(base, DESDE, HASTA)
    merma = r["renglones"]["merma"]

    # $2000 en total − los $600 de las dos armadas = $1400 de los ocho sueltos
    assert merma["mercaderia"] - 600.0 == 1400.0

    # Y LOS OCHO SE COSTEARON ENTEROS: los únicos sin costo son los 5 de
    # Palta. Sin esta mitad, un rejuego que arrancara tarde dejaría los ocho
    # sin lote y el `- 600 == 1400` de arriba fallaría por otro motivo.
    detalle = {(d["destino"], d["articulo"]): d for d in r["detalle"]}
    assert detalle[("merma", "EJEMPLO Tomate")]["bultos_sin_costo"] == 0.0


def test_la_VENTANA_deja_afuera_la_merma_de_OCTUBRE(base):
    """La del 05/10 es del mismo artículo, así que entra al rejuego igual.

    Lo que la deja afuera es el recorte de DESPUÉS, y son dos recortes
    distintos a propósito. Sin él la merma daría 11 bultos.
    """
    r = _perdidas(base, DESDE, HASTA)
    assert r["renglones"]["merma"]["bultos"] == 15.0, "entró la del 05/10"

    ancha = _perdidas(base, DESDE, datetime.date(2026, 10, 31))
    assert ancha["renglones"]["merma"]["bultos"] == 16.0, (
        "con la ventana abierta hasta octubre la del 05/10 TIENE que entrar: "
        "si no, el recorte no está donde dice")


def test_el_DETALLE_por_articulo_suma_lo_mismo_que_los_dos_RENGLONES(base):
    """Dos cuentas del mismo hecho que no se comparan se separan sin que nada
    avise (corolario 74). Acá salen del mismo bucle y por eso se pueden atar.
    """
    r = _perdidas(base, DESDE, HASTA)

    assert sum(d["total"] for d in r["detalle"]) == r["total"] == 3150.0
    assert {(d["destino"], d["articulo"]) for d in r["detalle"]} == {
        ("merma", "EJEMPLO Tomate"), ("segunda", "EJEMPLO Tomate"),
        ("merma", "EJEMPLO Palta")}
    # ORDENADO POR PLATA, y Palta va ÚLTIMA aunque tenga bultos: no se pudo
    # costear, así que su total es cero. Es el orden que vuelve la lista una
    # lista de trabajo — y de paso deja a la vista que un renglón con bultos
    # y sin plata existe.
    assert [(d["destino"], d["articulo"]) for d in r["detalle"]] == [
        ("merma", "EJEMPLO Tomate"), ("segunda", "EJEMPLO Tomate"),
        ("merma", "EJEMPLO Palta")]


def test_los_BULTOS_SIN_COSTEAR_llegan_del_FIFO_al_renglon_y_no_suman_pesos(base):
    """Los 5 de Palta salieron de una compra sin importe.

    LAS DOS MITADES, y hacen falta las dos: que el número LLEGUE —la línea que
    lo acumula se puede borrar entera y, con todo costeado, el total sigue
    dando el mismo cero— y que NO sume pesos, que es lo que distingue un total
    que cubre todo de uno que se comió bultos en silencio.

    Este número va a un estado de resultados: un total más chico y prolijo es
    peor que uno con un hueco declarado al lado.
    """
    r = _perdidas(base, DESDE, HASTA)

    assert r["bultos_sin_costo"] == 5.0
    assert r["renglones"]["merma"]["bultos_sin_costo"] == 5.0
    assert r["renglones"]["segunda"]["bultos_sin_costo"] == 0.0

    palta = [d for d in r["detalle"] if d["articulo"] == "EJEMPLO Palta"]
    assert len(palta) == 1
    assert palta[0]["bultos"] == 5.0
    assert palta[0]["mercaderia"] == 0.0, "se costeó algo que no tiene precio"
    assert palta[0]["total"] == 0.0

    # Y EL TOTAL NO SE MOVIÓ: los 5 aportan bultos y cero pesos.
    assert r["total"] == 3150.0
