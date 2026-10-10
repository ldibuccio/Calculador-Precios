"""Cómo salió un renglón de un DÍA ANTERIOR (dueño, 09/10), contra Postgres.

El caso real: Cherry cargado como caja de Día que salió en el descartable del
proveedor (5 o 7 kg), o al revés. Al corregir se liberan las cajas de la guía
R, se descuentan los cajones de la compra, deja de cobrarse la caja de Día,
se corrigen los kilos y queda el historial. En Mango igual, sin kilos: sale
siempre por 10 unidades. Administración, contraseña de fecha anterior, el
control de la corrección de lote; la fecha del armado y el remito emitido no
se tocan.

EL GALPÓN, con el RIVAL (el renglón 3, que sí salió en su envase):

  01/10  compra 11: 30 cajones de EJEMPLO Cherry de 7 kg a $20.000
         compra 12: 30 cajones de EJEMPLO Mango a $5.000
  02/10  guía R5: toma 10 de la 11 y arma 10 cajas de Cherry a $30.000
         guía R6: toma 10 de la 12 y arma 10 cajas de Mango a $6.000
  05/10  renglón 1: Cherry, 10 A CAJA, 50 kg        -> las 10 cajas de la R5
         renglón 2: Mango, 10 A CAJA, 100 unidades   -> las 10 cajas de la R6
         renglón 3: Cherry, 10 EN SU ENVASE, 70 kg   -> 10 cajones de la 11
  Hoy es el 08/10.
"""
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402
from tests.test_administracion_reordenada import CLAVES, _cliente  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 8)
CLAVE = "galpon-2026"
BASE = "/administracion/retroactivo/lote-de-pedido"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'Día EJEMPLO');
insert into articulos (id, nombre) overriding system value
  values (1, 'EJEMPLO Cherry'), (2, 'EJEMPLO Mango');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja Chica Día');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id,
                              envase_variable)
  overriding system value
  values (1, 1, 1, 5, 'kilo', 1, true), (2, 1, 2, 10, 'unidad', 1, true);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (11, 1, 1, '2026-10-01', 30, 7, 210, 20000, 'recepcionado', '2026-10-01 18:00-03', 30, 7),
         (12, 1, 2, '2026-10-01', 30, 10, 300, 5000, 'recepcionado', '2026-10-01 18:00-03', 30, 10);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera, bultos_segunda,
                        bultos_merma, costo_por_bulto_primera, cliente_id, ficha_id, envase_id,
                        lleva_caja_nuestra, creado_en)
  overriding system value
  values (5, 1, '2026-10-02', 10, 10, 0, 0, 30000, 1, 1, 1, true, '2026-10-02 18:00-03'),
         (6, 2, '2026-10-02', 10, 10, 0, 0, 6000, 1, 2, 1, true, '2026-10-02 18:00-03');
insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos)
  values (5, 'compra', 11, 10), (6, 'compra', 12, 10);
insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 1, '2026-10-05', 'texto');
insert into pedidos_sucursales (id, pedido_id, sucursal) overriding system value values (1, 1, 'VL');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
                               cantidad_armada, armado_el, kilos_enviados, en_su_envase)
  overriding system value
  values (1, 1, 'VL', 1, 1, 10, 10, '2026-10-05 10:00-03', 50, false),
         (2, 1, 'VL', 2, 2, 10, 10, '2026-10-05 11:00-03', 100, false),
         (3, 1, 'VL', 1, 1, %(rival)s, %(rival)s, '2026-10-05 12:00-03', 70, true);
"""


@pytest.fixture
def galpon(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    monkeypatch.setenv("DATABASE_URL", url)
    for clave, valor in CLAVES.items():
        monkeypatch.setenv(clave, valor)
    import app.db as d
    import app.main as m

    def sql(consulta, parametros=None):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()

    def sembrar(rival=10):
        sql(SIEMBRA, {"rival": rival})
        d.fijar_clave_especial(CLAVE)
    with patch("app.main._hoy_argentina", return_value=HOY):
        yield d, m, sql, sembrar


def _corregir(m, renglon_id, como, kilos="", *, clave=CLAVE, quien="Marta"):
    return _cliente(m, "administracion").post(f"{BASE}/{renglon_id}/como-salio", data={
        "como_sale": como, "kilos_por_bulto": kilos, "quien": quien, "clave_especial": clave},
        follow_redirects=False)


def _consumos(d, articulo_id):
    from core.costo_real import atribuir_costos_fifo
    entradas, salidas = d.entradas_y_salidas_stock_articulo(articulo_id)
    return {s["renglon_id"]: sorted((c["tipo_lote"], c["origen_id"], c["bultos"]) for c in s["consumos_lotes"])
            for s in atribuir_costos_fifo(entradas, salidas) if s["tipo"] == "armado"}


def _error(respuesta):
    return re.findall(r"data-error>([^<]*)", respuesta.text)


def test_CHERRY_de_caja_a_SU_ENVASE_de_7_libera_las_cajas_toma_cajones_y_corrige_los_kilos(galpon):
    d, m, sql, sembrar = galpon
    sembrar()
    # Lo que se había elegido a mano era de la otra forma: se va.
    sql("insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos) "
        "values (1, 'reproceso', 5, 10)")
    assert _consumos(d, 1)[1] == [("reproceso", 5, 10)]

    respuesta = _corregir(m, 1, "su_envase", "7")

    assert respuesta.status_code == 303, _error(respuesta)
    assert sql("SELECT en_su_envase, kilos_enviados::float, armado_el = '2026-10-05 10:00-03' "
               "FROM pedidos_renglones WHERE id = 1") == [(True, 70.0, True)]
    consumos = _consumos(d, 1)
    assert consumos[1] == [("guia", 11, 10)]                # cajones de la compra
    assert consumos[3] == [("guia", 11, 10)]                # el rival, igual que antes
    assert sql("SELECT count(*) FROM pedidos_renglones_lotes_elegidos") == [(0,)]
    (que, envase_antes, envase_ahora, kilos_antes, kilos_ahora, antes, ahora, costo_antes, costo_ahora), = sql(
        "SELECT que, en_su_envase_antes, en_su_envase_ahora, kilos_antes::float, kilos_ahora::float, "
        "antes, ahora, costo_antes::float, costo_ahora::float FROM pedidos_renglones_lotes_correcciones")
    assert (que, envase_antes, envase_ahora, kilos_antes, kilos_ahora) == ("como_salio", False, True, 50.0, 70.0)
    assert [p["lote"] for p in antes] == ["Guía R5 del 02/10"]
    assert [p["lote"] for p in ahora] == ["Guía de EJEMPLO Puesto del 01/10"]
    assert (costo_antes, costo_ahora) == (300000.0, 200000.0)
    pantalla = " ".join(re.sub(r"<[^>]+>", " ", _cliente(m, "administracion").get(f"{BASE}/1").text).split())
    assert "Cómo salió: en caja de Día → en su envase" in pantalla and "Kilos: 50 → 70" in pantalla
    assert "Hoy figura: en su envase · 7 kg por bulto" in pantalla


def test_al_REVES_de_su_envase_a_CAJA_toma_las_cajas_y_vuelve_al_kilaje_de_la_ficha(galpon):
    """Con una guía R7 del 03/10 con 10 cajas libres. Sin ella, las cajas de
    la R5 son del renglón 1 y el control frena (que es lo que tiene que hacer)."""
    d, m, sql, sembrar = galpon
    sembrar()
    assert "no había cajas armadas de esta ficha" in _error(_corregir(m, 3, "caja"))[0]
    sql("""insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
               bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id, ficha_id, envase_id,
               lleva_caja_nuestra, creado_en) overriding system value
           values (7, 1, '2026-10-03', 10, 10, 0, 0, 30000, 1, 1, 1, true, '2026-10-03 18:00-03')""")
    sql("insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos) values (7, 'compra', 11, 10)")
    respuesta = _corregir(m, 3, "caja")                     # sin kilos: los de la ficha (5)
    assert respuesta.status_code == 303, _error(respuesta)
    assert sql("SELECT en_su_envase, kilos_enviados::float FROM pedidos_renglones WHERE id = 3") == [(False, 50.0)]
    assert _consumos(d, 1)[3] == [("reproceso", 7, 10)]


def test_si_otro_queda_SIN_MERCADERIA_no_deja_y_dice_cual(galpon):
    """El rival lleva 15 en su envase: a la compra 11 le quedan 20 cajones. Si
    el renglón 1 también pasa a su envase, se lleva 10 antes y el rival queda
    con 5 sin lote."""
    d, m, sql, sembrar = galpon
    sembrar(rival=15)
    respuesta = _corregir(m, 1, "su_envase", "5")
    assert respuesta.status_code == 400
    assert _error(respuesta) == ["El armado del pedido de Día EJEMPLO del 05/10 se queda sin mercadería. "
                                 "Hasta que eso se corrija, no se puede cambiar cómo salió."]
    assert sql("SELECT en_su_envase, kilos_enviados::float FROM pedidos_renglones WHERE id = 1") == [(False, 50.0)]
    assert sql("SELECT count(*) FROM pedidos_renglones_lotes_correcciones") == [(0,)]


def test_el_MANGO_cambia_el_envase_y_NUNCA_la_cantidad(galpon):
    d, m, sql, sembrar = galpon
    sembrar()
    pagina = _cliente(m, "administracion").get(f"{BASE}/2").text
    assert pagina.count("data-como-salio") == 1 and 'name="kilos_por_bulto"' not in pagina
    respuesta = _corregir(m, 2, "su_envase")
    assert respuesta.status_code == 303, _error(respuesta)
    assert sql("SELECT en_su_envase, kilos_enviados::float FROM pedidos_renglones WHERE id = 2") == [(True, 100.0)]
    assert sql("SELECT kilos_antes, kilos_ahora FROM pedidos_renglones_lotes_correcciones") == [(None, None)]
    assert _consumos(d, 2)[2] == [("guia", 12, 10)]


def test_lo_que_NO_se_puede_rebota_sin_escribir(galpon):
    d, m, sql, sembrar = galpon
    sembrar()
    assert "En su envase hay que poner cuántos kilos va cada bulto." in _error(_corregir(m, 1, "su_envase"))[0]
    assert "La contraseña especial no es correcta." in _error(_corregir(m, 1, "su_envase", "7", clave="x"))[0]
    assert "Ya figura así" in _error(_corregir(m, 3, "su_envase", "7"))[0]
    assert "Elegí cómo salió" in _error(_corregir(m, 1, ""))[0]
    sql("UPDATE pedidos_renglones SET armado_el = '2026-10-08 09:00-03' WHERE id = 1")
    assert "Ese renglón se armó hoy" in _error(_corregir(m, 1, "su_envase", "7"))[0]
    assert sql("SELECT count(*) FROM pedidos_renglones_lotes_correcciones") == [(0,)]
    assert sql("SELECT en_su_envase FROM pedidos_renglones WHERE id = 1") == [(False,)]


def test_el_REMITO_ya_emitido_se_avisa_y_NO_se_toca(galpon):
    d, m, sql, sembrar = galpon
    sembrar()
    sql("insert into remitos (id, pedido_sucursal_id, cliente_id, numero) overriding system value "
        "values (1, 1, 1, '20440')")
    sql("insert into remitos_renglones (remito_id, pedido_renglon_id, bultos_enviados, kilos_enviados) "
        "values (1, 1, 10, 50)")
    pagina = _cliente(m, "administracion").get(f"{BASE}/1").text
    assert re.findall(r"<p class=\"ojo\" data-remito>([^<]*)</p>", pagina) == [
        "El remito 20440 ya salió con 50 kg: no se toca. Se cobra lo que firme el súper."]
    assert _corregir(m, 1, "su_envase", "7").status_code == 303
    assert sql("SELECT bultos_enviados::float, kilos_enviados::float FROM remitos_renglones") == [(10.0, 50.0)]


def test_una_ficha_que_NO_elige_no_ofrece_la_pregunta_ni_la_acepta(galpon):
    d, m, sql, sembrar = galpon
    sembrar()
    sql("UPDATE fichas_logistica SET envase_variable = false WHERE id = 1")
    assert "data-como-salio" not in _cliente(m, "administracion").get(f"{BASE}/1").text
    assert "sale como dice su ficha" in _error(_corregir(m, 1, "su_envase", "7"))[0]


def test_a_313px_el_renglon_con_la_pregunta_no_desborda(galpon):
    from tests.test_remitos import _que_se_sale
    d, m, sql, sembrar = galpon
    sembrar()
    _corregir(m, 1, "su_envase", "7")
    html = _cliente(m, "administracion").get(f"{BASE}/1").text
    assert html.count("data-como-salio") == 1 and html.count("data-cambio") == 1       # identidad
    medicion = _que_se_sale(html, 313)
    assert medicion["pagina"] == 0 and medicion["salidos"] == [], medicion


def _leer(nombre):
    return open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


def test_la_MIGRACION_suma_las_columnas_y_no_corre_dos_veces(galpon):
    import psycopg2
    d, m, sql, sembrar = galpon
    sql("DROP TABLE pedidos_renglones_lotes_correcciones")
    sql(_leer("lote_dia_anterior_1_historial.sql"))
    sql("INSERT INTO pedidos_renglones_lotes_correcciones (renglon_id, quien, antes, ahora) "
        "SELECT id, 'Marta', '[]', '[]' FROM pedidos_renglones LIMIT 0")
    sql(_leer("lote_dia_anterior_2_como_salio.sql"))
    with pytest.raises(psycopg2.errors.RaiseException):
        sql(_leer("lote_dia_anterior_2_como_salio.sql"))
    (fila,) = sql(_leer("lote_dia_anterior_2_verificacion.sql"))
    assert fila[:4] == ("lote_dia_anterior_2_como_salio", 5, 3, fila[4]) and fila[6] == 0
    sembrar()
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO pedidos_renglones_lotes_correcciones (renglon_id, quien, antes, ahora, que) "
            "VALUES (1, 'Marta', '[]', '[]', 'como_salio')")
    for nombre in ("lote_dia_anterior_2_como_salio.sql", "lote_dia_anterior_2_verificacion.sql"):
        assert len(_leer(nombre)) <= 2500, nombre
