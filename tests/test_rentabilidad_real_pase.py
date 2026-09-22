# -*- coding: utf-8 -*-
"""Lo pasado de primera a segunda, en Rentabilidad Real.

POR QUÉ ESTE ARCHIVO EXISTE. Hasta el 22/09 un pase consumía lotes en la
atribución del FIFO y **no sumaba en ninguna columna**: ni en `costo_mermas`,
ni en `segunda_bultos`, ni en "afuera del cálculo". La renta salía inflada por
el costo de lo que se pasó, y nadie lo veía.

Y HABÍA DOS COMPUERTAS, no una. La segunda —el filtro `filas_con_algo` de la
función pura— es la que se encuentra leyendo el código. La PRIMERA está en
`articulos_con_salidas_stock`, que decidía qué artículos mirar con
`tipo = 'merma'`: una berenjena que no se vendió y a la que solo se le pasaron
diez cajones **no llegaba nunca a la función pura**. Un test que solo
ejercitara la función pura habría pasado con ese agujero entero puesto, así
que este archivo entra por la BASE.

EL INTERRUPTOR ES EL DEL HUMO: sin Postgres esto se saltea, y un test salteado
se lee igual que uno verde. Con HUMO_OBLIGATORIO=1 dejar de poder correrlo
FALLA.
"""
import datetime
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

# EL GALPÓN. Los tres artículos están para tres preguntas distintas:
#
#   TOMATE     se vendió, se tiró y se pasó  -> el pase no puede pisar la merma
#   BERENJENA  SOLO se le pasaron 10 a segunda, sin una venta y sin una merma
#              -> es el rival del corolario 11: el que desaparecía
#   PALTA      solo se tiró, y sin precio    -> el control que NO tiene que
#              cambiar con este arreglo
SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Dia');
insert into articulos (id, nombre, grupo) overriding system value
  values (1, 'EJEMPLO Tomate', 'hortaliza'), (2, 'EJEMPLO Berenjena', 'hortaliza'),
         (3, 'EJEMPLO Palta', 'fruta');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja Dia');
insert into envases_costo_historial (envase_id, costo, vigente_desde) values (1, 50, '2026-01-01');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value
  values (1, 1, 1, 6, 'kilo', 1), (2, 1, 2, 6, 'kilo', 1);

insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value values
  (1, 1, 1, '2026-09-05', 10, 16, 160, 100, 'recepcionado', '2026-09-05 18:00-03', 10, 16),
  (2, 1, 2, '2026-09-05', 20, 16, 320, 200, 'recepcionado', '2026-09-05 18:00-03', 20, 16),
  (3, 1, 3, '2026-09-06',  5, 10,  50, null, 'recepcionado', '2026-09-06 18:00-03',  5, 10);

-- Las cajas armadas de cada uno: el pase de cajas armadas tiene que costearse
-- contra ESTAS y no contra el cajón de $100/$200.
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra)
  overriding system value values
  (1, 1, '2026-09-08', 5, 10, 0, 0, 300, 1, 1, 1, true),
  (2, 2, '2026-09-08', 8, 12, 0, 0, 400, 1, 2, 1, true);

insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema, bultos_segunda, ficha_id) values
  (1, '2026-09-11', 'pase_a_segunda', -3, 'se pusieron feas', 15, 3, 1),
  (2, '2026-09-11', 'pase_a_segunda', -10, 'se pusieron feas', 24, 10, 2);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema, ficha_id)
  values (1, '2026-09-12', 'merma', -2, 'se pudrio', 12, 1);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo,
                               stock_sistema)
  values (3, '2026-09-14', 'merma', -5, 'se pudrio y no tiene precio', 5);
"""

DESDE, HASTA = datetime.date(2026, 9, 10), datetime.date(2026, 9, 30)


@pytest.fixture(scope="module")
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail(
                "HUMO_OBLIGATORIO=1 y no hay un Postgres usable: lo que "
                "Rentabilidad Real hace con un pase no se verificó en esta "
                "corrida. Revisá el servicio de Postgres del runner.")
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


def _resultado(url):
    """El resultado de la pantalla, por el MISMO camino que la ruta.

    `_datos_rentabilidad_real` es lo que la ruta llama, así que esto ejercita
    las DOS compuertas: la de `articulos_con_salidas_stock` y la del filtro de
    la función pura. Llamar al motor puro con artículos elegidos a mano
    saltearía justamente la primera.
    """
    from unittest.mock import patch
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        from app.main import _datos_rentabilidad_real
        return _datos_rentabilidad_real(1, DESDE, HASTA, None, None)


def _filas(resultado):
    return {f["articulo_nombre"]: f for g in resultado["grupos"] for f in g["filas"]}


def test_el_articulo_que_SOLO_tuvo_un_pase_APARECE(base):
    """La berenjena no se vendió, no se le tiró nada, y se pasaron 10 a segunda.

    Antes del 22/09 no aparecía — no en cero: ausente, que es peor, porque un
    cero se ve y una fila que no está no. Y el agujero era de la PRIMERA
    compuerta: no llegaba ni a la función pura.
    """
    filas = _filas(_resultado(base))

    assert "EJEMPLO Berenjena" in filas, (
        "el artículo con un pase como único movimiento desapareció de la pantalla")
    f = filas["EJEMPLO Berenjena"]
    assert f["bultos"] == 0.0, "no se vendió nada: la fila existe por la pérdida"
    assert f["bultos_pasados_a_segunda"] == 10.0


def test_lo_pasado_a_segunda_se_costea_contra_LA_CAJA_ARMADA_y_suma_la_caja(base):
    """10 cajas armadas a $400 + 10 cajas a $50 = $4.500.

    El cajón de la berenjena es de $200 y es MÁS VIEJO: sin la preferencia por
    el lote trabajado el FIFO lo elegiría y la cuenta daría $2.000 + caja, la
    mitad. Y sin la caja daría $4.000, que se lee igual de prolijo.
    """
    f = _filas(_resultado(base))["EJEMPLO Berenjena"]

    assert f["costo_segunda"] == 4500.0
    assert f["cajas_perdidas"] == 10.0
    assert f["cajas_perdidas_pesos"] == 500.0
    # La caja va ADENTRO del costo y además NOMBRADA, igual que en el rechazo:
    # no es una cuenta nueva, es el mismo dinero con nombre.
    assert f["costo_segunda"] - f["cajas_perdidas_pesos"] == 4000.0


def test_el_pase_SUMA_AL_COSTO_TOTAL_y_baja_la_renta(base):
    """Es lo que estaba inflando la rentabilidad: consumía y no costaba."""
    f = _filas(_resultado(base))["EJEMPLO Berenjena"]

    assert f["costo_total"] == 4500.0, "el pase no entró en el costo total"
    assert f["renta_pesos"] == -4500.0, "sin venta, la pérdida ES la renta"


def test_el_pase_NO_SE_MEZCLA_con_las_mermas(base):
    """Se costean igual y se muestran separados: son dos hechos del galpón.

    El tomate tiene las dos cosas el mismo mes, que es lo único que puede
    mostrar que una no se comió a la otra.
    """
    f = _filas(_resultado(base))["EJEMPLO Tomate"]

    assert f["bultos_mermados"] == 2.0 and f["costo_mermas"] == 600.0
    assert f["bultos_pasados_a_segunda"] == 3.0
    assert f["costo_segunda"] == 1050.0      # 3 × $300 + 3 cajas × $50
    # Y NO están sumados uno adentro del otro, en ninguna dirección.
    assert f["costo_mermas"] != f["costo_segunda"]
    assert f["costo_total"] == 600.0 + 1050.0


def test_lo_que_NO_cambio_este_arreglo(base):
    """La palta solo se tiró y su compra no tiene precio: sigue afuera.

    El control que tiene que quedarse quieto. Sin él, un arreglo que hiciera
    entrar cualquier cosa pasaría los cuatro tests de arriba.
    """
    r = _resultado(base)
    filas = _filas(r)

    assert "EJEMPLO Palta" not in filas, "entró un artículo sin nada costeable"
    motivos = {a["motivo"] for a in r["afuera_por_motivo"]}
    assert "compra_sin_precio" in motivos
    assert r["totales"]["segunda_bultos"] == 0.0, (
        "`segunda_bultos` es la segunda que PRODUCE un reproceso: el pase no "
        "va ahí, y confundirlas sería dos cosas con el mismo nombre")


def test_la_caja_de_la_MERMA_no_entra_en_Rentabilidad_Real(base):
    """El control que faltaba, y lo pidió un canario en CERO.

    El tomate tiene una merma de 2 CAJAS ARMADAS (ficha 1), así que su caja
    vale 2 × $50 = $100 y se perdió igual de verdad que la del pase. Hoy NO
    se cuenta acá, y es una decisión del dueño y no un olvido: meterla movería
    `costo_mermas`, que es un número que ya se lee todos los días.

    Sin este test, sacarle a `cajas_de_pases_por_articulo` el filtro de
    `destino == "segunda"` no hacía caer nada — o sea que la decisión podía
    darse vuelta sola sin que nada se pusiera rojo.
    """
    f = _filas(_resultado(base))["EJEMPLO Tomate"]

    # 3 del pase y NO 5: las 2 de la merma quedan afuera.
    assert f["cajas_perdidas"] == 3.0
    assert f["cajas_perdidas_pesos"] == 150.0
    # Y `costo_mermas` es mercadería pelada: 2 bultos a $300, sin la caja.
    assert f["costo_mermas"] == 600.0


def test_la_PANTALLA_dibuja_lo_pasado_a_segunda(base):
    """Los tres canarios en CERO de la plantilla.

    Se podía borrar el chip, el renglón del total y la corrección del párrafo
    de las cajas sin que nada cayera: la cuenta estaba cubierta y lo que el
    dueño VE, no. Es la diferencia entre "¿se puede llegar?" y "¿se ve?".
    """
    import os as _os
    from unittest.mock import patch
    from fastapi.testclient import TestClient

    with patch.dict(_os.environ, {"DATABASE_URL": base, "CLAVE_GERENCIA": "secreta"}):
        from app.main import app, _firma_acceso_gerencia
        cliente = TestClient(app, base_url="https://testserver")
        cliente.cookies.set("acceso_gerencia", _firma_acceso_gerencia("secreta"))
        respuesta = cliente.get(
            f"/gerencia/rentabilidad-real?cliente_id=1"
            f"&fecha_desde={DESDE}&fecha_hasta={HASTA}")

    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    # EL ANCLA POSITIVA PRIMERO: un `not in` sobre un recorte que se llevó la
    # pantalla entera pasa siempre (corolario 50).
    assert "EJEMPLO Berenjena" in marcado

    # El chip, por artículo. Se cuenta: son DOS los artículos con pase, así
    # que un `in` lo satisface el más suertudo.
    assert marcado.count('class="chip-pasado-segunda"') == 2
    assert "pasado a segunda 10 bultos" in marcado
    assert "pasado a segunda 3 bultos" in marcado

    # El renglón del total.
    assert "pasado a segunda $5.550" in marcado
    assert "de primera que dejaron de serlo" in marcado

    # Y EL PÁRRAFO DE LAS CAJAS DEJÓ DE DECIR SOLO "LOS RECHAZOS", que es lo
    # que se volvió falso en el mismo commit que le sumó la caja de los pases:
    # este número tiene dos orígenes y uno no es del cliente.
    assert "Los rechazos se llevaron" not in marcado
    assert "PASES A SEGUNDA" in marcado
