"""En su envase o reprocesado a caja (dueño, 05/10), contra Postgres.

Mango y Cherry (fichas con `envase_variable`) pueden salir en el envase en que
vinieron, que NO consume cajas de Día, o reprocesados a caja, que sí. Se elige
por renglón al armar, sin default. El FIFO, el cotejo de cajas, la alerta de
guías R, las cajas perdidas y el costo de la caja respetan la elección.

EL GALPÓN, con el RIVAL (el renglón 2, que sí va en caja):

  05/09  compra 11: 10 cajones de Mango
  06/09  guía R: toma 4 de la 11 y arma 4 cajas de la ficha 1
  08/09  renglón 1: 3 bultos EN SU ENVASE      -> 3 de la compra, ninguna caja
         renglón 2: 2 bultos A CAJA            -> 2 de las 4 cajas
         renglón 3: 1 bulto de la verdulería (ficha sin envase) -> cajón

Si el renglón 1 se tomara las cajas (la regla vieja), se llevaría 3 de las 4
y el renglón 2 quedaría con 1 esperando una guía R.
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

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value
  values (1, 'Día EJEMPLO'), (2, 'EJEMPLO Verduleria');
insert into articulos (id, nombre) overriding system value
  values (1, 'EJEMPLO Mango'), (2, 'EJEMPLO Banana');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja Chica');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id,
                              envase_variable)
  overriding system value
  values (1, 1, 1, 10, 'unidad', 1, true), (2, 2, 1, 10, 'unidad', null, false),
         -- El rival de la pantalla: CON caja pero sin envase variable.
         (4, 1, 2, 18, 'kilo', 1, false);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (11, 1, 1, '2026-09-05', 10, 10, 100, 100, 'recepcionado', '2026-09-05 18:00-03', 10, 10);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra)
  overriding system value
  values (1, 1, '2026-09-06', 4, 4, 0, 0, 130, 1, 1, 1, true);
insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos)
  values (1, 'compra', 11, 4);
insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 1, '2026-09-08', 'texto'), (2, 2, '2026-09-08', 'texto');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad)
  overriding system value
  values (1, 1, 'VL', 1, 1, 3), (2, 1, 'VL', 1, 1, 2), (3, 2, 'CENTRO', 1, 2, 1),
         (4, 1, 'VL', 2, 4, 1);
insert into pedidos_sucursales (pedido_id, sucursal) values (1, 'VL'), (2, 'CENTRO');
"""


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    monkeypatch.setenv("DATABASE_URL", url)
    import app.db as d

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
    return d, sql


def _armar(d, sql, renglon_id, en_su_envase, hora):
    d.marcar_renglon_armado(renglon_id, None, None, en_su_envase=en_su_envase)
    sql("UPDATE pedidos_renglones SET armado_el = %s WHERE id = %s", (f"2026-09-08 {hora}-03", renglon_id))


def _armado_del_dia(d, sql, primero_en_su_envase=True):
    _armar(d, sql, 1, primero_en_su_envase, "09:00")
    _armar(d, sql, 2, False, "10:00")
    _armar(d, sql, 3, None, "11:00")


def _consumos(d):
    from core.costo_real import atribuir_costos_fifo
    entradas, salidas = d.entradas_y_salidas_stock_articulo(1)
    return {s["renglon_id"]: sorted((c["tipo_lote"], c["bultos"]) for c in s["consumos_lotes"])
            for s in atribuir_costos_fifo(entradas, salidas) if s["tipo"] == "armado"}


def test_EN_SU_ENVASE_sale_de_la_compra_y_A_CAJA_de_las_cajas(base):
    d, sql = base
    _armado_del_dia(d, sql)

    assert _consumos(d) == {1: [("guia", 3.0)], 2: [("reproceso", 2.0)], 3: [("guia", 1.0)]}
    assert d.cajas_armadas_por_ficha().get((1, 1)) == 2.0
    assert d.armados_esperando_guia_r(date(2026, 9, 30)) == []


def test_el_RIVAL_con_la_regla_vieja_se_lleva_las_cajas_y_deja_esperando(base):
    """El mismo día con el renglón 1 a caja: así era antes del 05/10."""
    d, sql = base
    _armado_del_dia(d, sql, primero_en_su_envase=False)

    assert _consumos(d)[1] == [("reproceso", 3.0)]
    assert [(f["renglon_id"], f["esperan"]) for f in d.armados_esperando_guia_r(date(2026, 9, 30))] == [(2, 1.0)]


def test_la_eleccion_es_OBLIGATORIA_en_su_ficha_y_no_existe_en_las_demas(base):
    d, sql = base
    with pytest.raises(d.ComoSaleNoPermitido, match="Elegí cómo sale"):
        d.marcar_renglon_armado(1)
    with pytest.raises(d.ComoSaleNoPermitido, match="como dice su ficha"):
        d.marcar_renglon_armado(3, en_su_envase=True)
    assert sql("SELECT count(*) FROM pedidos_renglones WHERE armado_el IS NOT NULL")[0][0] == 0


def test_DESARMAR_y_ANULAR_limpian_la_eleccion(base):
    d, sql = base
    _armar(d, sql, 1, True, "09:00")
    d.desmarcar_renglon_armado(1)
    _armar(d, sql, 2, False, "09:00")
    sql("UPDATE pedidos_renglones SET en_su_envase = true WHERE id = 2")
    d.anular_renglon_pedido(2)
    assert sql("SELECT id, en_su_envase FROM pedidos_renglones WHERE id IN (1, 2) ORDER BY id") == [
        (1, False), (2, False)]
    import psycopg2
    with pytest.raises(psycopg2.Error, match="pedidos_renglones_en_su_envase_solo_armado"):
        sql("UPDATE pedidos_renglones SET en_su_envase = true WHERE id = 3")


def _rechazo(sql, renglon_id, destino, bultos=1):
    sql("""INSERT INTO movimientos_stock (articulo_id, tipo, cantidad, motivo, cliente_id, fecha_operacion,
               stock_sistema, pedido_renglon_id, costo_por_bulto, destino_rechazo, bultos_segunda)
           VALUES (1, 'reingreso_rechazo', %s, 'EJ rechazo', 1, '2026-09-09', 0, %s, 100, %s, %s)""",
        (bultos, renglon_id, destino, bultos if destino == "segunda" else None))


def test_el_RECHAZO_de_un_renglon_en_su_envase_vuelve_como_CAJON_y_no_pierde_caja(base):
    d, sql = base
    _armado_del_dia(d, sql)
    _rechazo(sql, 1, "stock")                          # vuelve en su envase: cajón
    _rechazo(sql, 1, "segunda")                        # no se pierde ninguna caja
    _rechazo(sql, 2, "segunda")                        # el rival: ésa sí se pierde

    entradas, _ = d.entradas_y_salidas_stock_articulo(1)
    rechazo, = [e for e in entradas if e["tipo_lote"] == "reingreso_rechazo"]
    assert (rechazo.get("en_cajon"), rechazo.get("de_una_ficha")) == (True, False)
    assert d.cajas_armadas_por_ficha().get((1, 1)) == 2.0
    perdidas = d.cajas_perdidas(date(2026, 9, 1), date(2026, 9, 30))
    assert perdidas["cajas"] == 1.0


def test_la_CAJA_se_cobra_segun_como_salio_el_renglon():
    from core.costo_real import envase_por_unidad_del_renglon
    variable = {"envase_variable": True, "costo_envase_unidad_venta": 0.4,
                "costo_envase_reprocesado_unidad_venta": 9.0}
    fija = {"envase_variable": False, "costo_envase_unidad_venta": 0.4,
            "costo_envase_reprocesado_unidad_venta": 9.0}
    assert envase_por_unidad_del_renglon(variable, True) == 0.0
    assert envase_por_unidad_del_renglon(variable, False) == 9.0
    assert envase_por_unidad_del_renglon(fija, False) == envase_por_unidad_del_renglon(fija, None) == 0.4
    # Una fila de margen armada por otro lado (sin las claves nuevas) sigue igual.
    assert envase_por_unidad_del_renglon({"costo_envase_unidad_venta": 0.4}, True) == 0.4


def test_la_PANTALLA_pide_como_sale_solo_en_su_ficha_y_el_tilde_sin_elegir_rebota(base):
    from fastapi.testclient import TestClient

    from app.main import app
    d, sql = base
    cliente = TestClient(app, base_url="https://testserver")
    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 8)):
        pagina = cliente.get("/deposito/pedido/armar?cliente_id=1&fecha=2026-09-08&sucursal=VL")
    assert pagina.status_code == 200
    marcado = pagina.text.split("</style>")[-1]
    # Identidad: los tres renglones de Día; la pregunta solo en los dos del Mango.
    assert len(re.findall(r'<form method="post" action="/deposito/pedido/1/renglones/\d+/armar"', marcado)) == 3
    assert marcado.count("<legend>¿Cómo sale?</legend>") == 2
    assert marcado.count('name="como_sale" value="su_envase" required') == 2
    assert marcado.count('name="como_sale" value="caja" required') == 2

    datos = {"cliente_id": "1", "fecha": "2026-09-08", "sucursal": "VL", "cantidad_pedida": "3"}
    sin_elegir = cliente.post("/deposito/pedido/1/renglones/1/armar", data=datos)
    assert sin_elegir.status_code == 400 and "Elegí cómo sale" in sin_elegir.text
    elegido = cliente.post("/deposito/pedido/1/renglones/1/armar", data={**datos, "como_sale": "su_envase"},
                           follow_redirects=False)
    assert elegido.status_code == 303
    assert sql("SELECT en_su_envase FROM pedidos_renglones WHERE id = 1") == [(True,)]

    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 8)):
        verduleria = cliente.get("/deposito/pedido/armar?cliente_id=2&fecha=2026-09-08&sucursal=CENTRO")
    assert verduleria.status_code == 200
    assert "¿Cómo sale?" not in verduleria.text.split("</style>")[-1]


def _leer(nombre):
    import io
    return io.open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


def test_la_MIGRACION_deja_lo_de_antes_como_estaba_y_no_corre_dos_veces(base):
    import psycopg2
    d, sql = base
    _armar(d, sql, 2, False, "10:00")
    sql("ALTER TABLE pedidos_renglones DROP COLUMN en_su_envase")
    sql(_leer("en_su_envase_1_renglon.sql"))
    fila, = sql(_leer("en_su_envase_1_verificacion.sql"))
    assert fila[:5] == ("en_su_envase_1_renglon", 1, 1, 0, 1)
    with pytest.raises(psycopg2.Error, match="en_su_envase_1 ya corrio"):
        sql(_leer("en_su_envase_1_renglon.sql"))


def test_los_bloques_entran_en_el_editor_y_el_codigo_va_arriba():
    for nombre in ("en_su_envase_1_renglon.sql", "en_su_envase_1_verificacion.sql"):
        texto = _leer(nombre)
        assert len(texto) <= 2500 and not texto.lstrip().startswith("--"), nombre
    assert _leer("en_su_envase_1_verificacion.sql").lstrip().startswith(
        "select 'en_su_envase_1_renglon' as que_migracion")


def test_el_COSTEO_trae_la_caja_ENTERA_para_el_renglon_que_se_reprocesa():
    """Cherry comprado en cajón de 5 (igual a la ficha): el ponderado da 0
    —descartable— pero el renglón que se reprocesó usó una caja cada 5."""
    from tests.test_costeo import COSTOS_ENVASES_CHERRY, FICHA_CHERRY_VARIABLE, _calcular_negociacion
    compras = [{"articulo_id": 21, "articulo_nombre": "Tomate Cherry", "fecha_operacion": date(2026, 8, 10),
                "cantidad_cajones": 4, "contenido_por_cajon": 5, "cantidad_kilos": 20, "importe": 1500}]
    cherry, = _calcular_negociacion(compras=compras, fichas=[FICHA_CHERRY_VARIABLE], precios_vigentes=[],
                                    costos_envases=COSTOS_ENVASES_CHERRY)[0]
    assert cherry["envase_variable"] is True
    assert cherry["costo_envase_unidad_venta"] == 0
    assert cherry["costo_envase_reprocesado_unidad_venta"] == pytest.approx(650 / 5)


def _devolucion_al_proveedor(sql, renglon_id):
    sql("""INSERT INTO movimientos_stock (articulo_id, tipo, cantidad, motivo, cliente_id, fecha_operacion,
               stock_sistema, pedido_renglon_id, costo_por_bulto, destino_rechazo, compra_devolucion_id)
           VALUES (1, 'reingreso_rechazo', 1, 'EJ rechazo', 1, '2026-09-09', 0, %s, 100,
                   'devolucion_proveedor', 11)""", (renglon_id,))


def test_la_DEVOLUCION_al_proveedor_de_un_renglon_en_su_envase_lleva_su_cajon_y_su_sena(base):
    """En su envase vuelve en el cajón del proveedor: se lleva la seña y sale
    de Vacíos. El rival en caja de Día no devuelve ningún cajón."""
    d, sql = base
    sql("UPDATE compras SET sena = 500 WHERE id = 11")
    _armado_del_dia(d, sql)
    _devolucion_al_proveedor(sql, 1)
    _devolucion_al_proveedor(sql, 2)

    movimientos = [m for m in d.movimientos_del_deposito(date(2026, 9, 1), date(2026, 9, 30))
                   if m["tipo"] == "rechazo"]
    assert sorted(m["sena"] is not None for m in movimientos) == [False, True]
    proveedor, = [p for p in d.stock_de_vacios_deposito() if p["id"] == 1]
    assert sum(p["devueltos"] for p in proveedor["pilas"]) == 1

    devoluciones = d.devoluciones_vinculadas_por_rango(1, date(2026, 9, 1), date(2026, 9, 30))
    assert sorted((x["renglon_id"], x["en_su_envase"]) for x in devoluciones) == [(1, True), (2, False)]


def test_RENTABILIDAD_REAL_cobra_la_caja_solo_al_renglon_que_fue_a_caja(base):
    from core.costo_real import calcular_rentabilidad_real
    d, sql = base
    _armado_del_dia(d, sql)
    sql("UPDATE pedidos_renglones SET kilos_enviados = 10 * cantidad WHERE id IN (1, 2)")
    entradas, salidas = d.entradas_y_salidas_stock_articulo(1)
    margen = {"precio_vigente": 50, "denominador_tasas": 1, "costo_envase_unidad_venta": 0.0,
              "envase_variable": True, "costo_envase_reprocesado_unidad_venta": 13.0}
    reporte = calcular_rentabilidad_real(
        [{"articulo_id": 1, "nombre": "EJEMPLO Mango", "grupo": None, "entradas": entradas, "salidas": salidas}],
        {date(2026, 9, 8): {1: margen}}, 1, date(2026, 9, 1), date(2026, 9, 30))
    # 2 bultos × 10 unidades a caja × $13; los 3 en su envase no llevan caja.
    assert reporte["totales"]["costo_envase"] == pytest.approx(260.0)


def test_ARMAR_con_la_pregunta_no_desborda_a_313px(base):
    from fastapi.testclient import TestClient

    from app.main import app
    from tests.test_remitos import _que_se_sale
    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 8)):
        html = TestClient(app, base_url="https://testserver").get(
            "/deposito/pedido/armar?cliente_id=1&fecha=2026-09-08&sucursal=VL").text
    assert html.count("<legend>¿Cómo sale?</legend>") == 2       # identidad: la pantalla con la pregunta
    medicion = _que_se_sale(html, 313)
    assert medicion["pagina"] == 0 and medicion["salidos"] == [], medicion
