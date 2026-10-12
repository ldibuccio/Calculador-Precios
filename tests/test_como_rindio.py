# -*- coding: utf-8 -*-
"""El bloque "Cómo rindió" del detalle de la compra (dueño, 12/10), contra Postgres.

De lo que una compra mandó a guías R, cuántos kilos de primera salieron, con
números teóricos: cajas × kilos de la ficha (las cajas no se pesan), segunda y
merma en cajones de origen con el peso del cajón que entró a esa guía, y la
guía que mezcla compras repartida por los KILOS que puso cada una.

EL CASO, armado como el del Morrón del 08/10 con nombres inventados y con el
RIVAL plantado (la compra 12, de cajones más pesados):

  08/10  compra 11: 41 cajones declarados de 9 kg, pesados de 10, a $75.000
  09/10  compra 12: 64 cajones de 12 kg a $85.000 (rival)
  09/10  guía R1: 28 de la 11 y 2 de la 12 -> 36 cajas de 8 kg
         guía R2: 4 de la 11               -> 5 cajas y 3 de segunda
  12/10  guía R3: 13 de la 12              -> no es de la 11
         el 10/10 salen las 36 cajas de la R1 para Día

La 13 se recibió y no fue a ninguna guía: no tiene el bloque.
"""
import html
import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'Día EJEMPLO');
insert into articulos (id, nombre, unidad_compra) overriding system value
  values (1, 'EJEMPLO Morron', 'kilo');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01'), (2, 'EJEMPLO Quinta', 'N01P02');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 8, 'kilo', 1);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (11, 1, 1, '2026-10-08', 41, 9, 369, 75000, 'recepcionado', '2026-10-08 11:50-03', 41, 10),
         (12, 2, 1, '2026-10-09', 64, 12, 768, 85000, 'recepcionado', '2026-10-09 13:20-03', 64, 12),
         (13, 2, 1, '2026-10-09', 10, 12, 120, 80000, 'recepcionado', '2026-10-09 13:30-03', 10, 12);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra, creado_en)
  overriding system value
  values (1, 1, '2026-10-09', 30, 36, 0, 0, 63055.56, 1, 1, 1, true, '2026-10-09 17:00-03'),
         (2, 1, '2026-10-09', 4, 5, 3, 0, 60000, 1, 1, 1, true, '2026-10-09 17:30-03'),
         (3, 1, '2026-10-12', 13, 5, 5, 3, 221000, 1, 1, 1, true, '2026-10-12 09:00-03');
insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos, costo_por_bulto)
  values (1, 'compra', 11, 28, 75000), (1, 'compra', 12, 2, 85000),
         (2, 'compra', 11, 4, 75000), (3, 'compra', 12, 13, 85000);
-- LO QUE PIDE LA RENTABILIDAD DEL LOTE: el precio de la ficha (el del 10/10 es
-- el RIVAL: empieza después de las guías del 09/10), el descuento de Día y el
-- costo de la caja.
insert into precios_venta_historial (articulo_id, cliente_id, precio, vigente_desde, ficha_id)
  values (1, 1, 11000, '2026-10-01', 1), (1, 1, 15000, '2026-10-10', 1);
insert into clientes_parametros_historial (cliente_id, nombre_parametro, valor, vigente_desde, tipo)
  values (1, 'descuento', 0.2, '2020-01-01', 'resta');
insert into envases_costo_historial (envase_id, costo, vigente_desde) values (1, 1000, '2020-01-01');
insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 1, '2026-10-10', 'texto');
insert into pedidos_sucursales (pedido_id, sucursal) values (1, 'VL');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
                               cantidad_armada, armado_el, kilos_enviados)
  overriding system value
  values (1, 1, 'VL', 1, 1, 36, 36, '2026-10-10 10:00-03', 288);
"""


@pytest.fixture(scope="module")
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay un Postgres usable.")
        pytest.skip("sin Postgres local: se corre con el humo antes de desplegar")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    return url


def _rindio(base, monkeypatch, compra_id):
    import app.db as db
    monkeypatch.setenv("DATABASE_URL", base)
    return db.como_rindio_la_compra(compra_id)


def test_PAGADO_COMPRADO_y_RECIBIDO(base, monkeypatch):
    cr = _rindio(base, monkeypatch, 11)
    assert (cr["pagado"], cr["importe_por_cajon"]) == (41 * 75000.0, 75000.0)
    assert (cr["kg_declarados"], cr["kg_pesados"]) == (369.0, 410.0)


def test_cada_GUIA_R_con_su_parte_por_KILOS_y_la_segunda_en_cajones_de_origen(base, monkeypatch):
    """La R1 mezcla: 28 cajones de 10 kg (280) y 2 de 12 (24). A la 11 le toca
    280 de 304 (92,1%), no 28 de 30 (93,3%). La R2 tiene 3 de segunda, que son
    cajones de 10 kg: 30 kg, y su cuenta no cierra (40 entraron, 70 salieron)."""
    guias = {g["numero"]: g for g in _rindio(base, monkeypatch, 11)["guias"]}
    assert sorted(guias) == [1, 2]                                   # la R3 no es de la 11
    r1, r2 = guias[1], guias[2]
    assert (r1["bultos"], r1["bultos_de_la_guia"], r1["kg_entraron"], r1["parte"]) == (28.0, 30.0, 280.0, 92.1)
    assert (r1["cajas_primera"], r1["kg_primera"], r1["kg_segunda"], r1["kg_merma"]) == (33.16, 265.26, 0.0, 0.0)
    assert r1["no_cierra_por"] == 14.74 and r1["mezcla"] is True
    assert (r2["bultos"], r2["kg_entraron"], r2["cajas_primera"], r2["kg_primera"], r2["kg_segunda"]) \
        == (4.0, 40.0, 5.0, 40.0, 30.0)
    assert r2["no_cierra_por"] == -30.0 and r2["mezcla"] is False


def test_los_TOTALES_y_los_dos_NUMEROS_CLAVE(base, monkeypatch):
    cr = _rindio(base, monkeypatch, 11)
    assert (cr["bultos_a_proceso"], cr["kg_entraron"], cr["kg_primera"], cr["pct_primera"]) \
        == (32.0, 320.0, 305.26, 95.4)
    assert cr["kg_primera_por_cajon"] == 9.54                       # 305,26 kg / 32 cajones
    assert cr["costo_por_kg_primera"] == 7862.15                    # 32 × $75.000 / 305,26 kg


def test_el_RIVAL_tiene_lo_suyo_y_la_compra_SIN_guia_no_tiene_bloque(base, monkeypatch):
    cr = _rindio(base, monkeypatch, 12)
    guias = {g["numero"]: g for g in cr["guias"]}
    assert sorted(guias) == [1, 3]
    assert (guias[1]["bultos"], guias[1]["kg_entraron"], guias[1]["parte"]) == (2.0, 24.0, 7.9)
    assert guias[3]["kg_segunda"] == 60.0 and guias[3]["kg_merma"] == 36.0
    assert _rindio(base, monkeypatch, 13) is None


def test_A_DONDE_FUE_reparte_la_guia_por_KILOS_igual_que_COMO_RINDIO(base, monkeypatch):
    """De las 36 cajas de la R1, a la 11 le tocan 36 × 280/304 = 33,16 (por
    bultos serían 33,6) y a la 12, 2,84."""
    import app.db as db
    monkeypatch.setenv("DATABASE_URL", base)
    de_la_11 = db.a_donde_fue_la_compra(11)["renglones"]
    de_la_12 = db.a_donde_fue_la_compra(12)["renglones"]
    assert [(r["id"], r["bultos"]) for r in de_la_11] == [(1, 33.16)]
    assert [(r["id"], r["bultos"]) for r in de_la_12] == [(1, 2.84)]


def _pagina(base, monkeypatch, url, puerta):
    from fastapi.testclient import TestClient

    import app.main as m
    monkeypatch.setenv("DATABASE_URL", base)
    objeto = getattr(m, f"PUERTA_{puerta.upper()}")
    monkeypatch.setenv(objeto.env_var, "secreta")
    cliente = TestClient(m.app, base_url="https://testserver")
    cliente.cookies.set(objeto.cookie, objeto.firma("secreta"))
    respuesta = cliente.get(url)
    assert respuesta.status_code == 200
    return respuesta.text


def _tarjeta(pagina):
    assert pagina.count('<div class="tarjeta" id="como-rindio">') == 1
    tarjeta = pagina.split('<div class="tarjeta" id="como-rindio">')[1].split('<div class="tarjeta" id="a-donde-fue">')[0]
    return tarjeta, " ".join(html.unescape(re.sub(r"<[^>]+>", " ", tarjeta)).split())


def test_la_PANTALLA_en_COMPRAS_y_en_GUIAS_MERCADERIA_dice_como_rindio(base, monkeypatch):
    for url, puerta in (("/compras/11/detalle", "compras"),
                        ("/administracion/guias-mercaderia/11/detalle", "administracion")):
        tarjeta, texto = _tarjeta(_pagina(base, monkeypatch, url, puerta))
        assert re.findall(r'<span class="clave-numero">([^<]*)</span>', tarjeta) == ["9.54 kg", "$7.862"], url
        assert "Pagado $3.075.000 ($75.000 por cajón)" in texto
        assert "Comprado 41 × 9 kg = 369 kg" in texto and "Recibido (pesado) 41 × 10 kg = 410 kg" in texto
        assert "Guía R1 del 09/10 28 cajones de esta compra (de 30) · entraron 280 kg" in texto
        assert "Primera: 33.16 cajas × 8 kg = 265.26 kg" in texto
        assert "Segunda: 30 kg · Merma: 0 kg" in texto
        assert "Entraron 320 kg · salieron 305.26 kg de primera 95.4% de primera" in texto
        assert tarjeta.count('class="nota-chica"') == 3              # la mezcla de la R1 y dos que no cierran
        assert "Las cajas armadas no se pesan" in tarjeta
        # Ni lo cobrado ni lo recibido por el súper (dueño, 12/10): la venta
        # es la teórica de la rentabilidad del lote. Ni la jerga del sistema.
        for ajeno in ("cobr", "recibido por", "FIFO", "consumo"):
            assert ajeno not in texto.replace("Recibido (pesado)", ""), (url, ajeno)
    assert 'id="como-rindio"' not in _pagina(base, monkeypatch, "/compras/13/detalle", "compras")


def test_la_RENTABILIDAD_DEL_LOTE_cuenta_como_RENTABILIDAD_REAL():
    """La cuenta pura: venta con las tasas del cliente, costo de los cajones y
    de la caja (la de Rentabilidad Real), % sobre la mercadería. La guía sin
    precio queda afuera y se cuenta; la de envase variable cobra la caja
    entera de reprocesado."""
    from core.costo_real import rentabilidad_del_lote
    guias = [{"numero": 1, "kg_primera": 100.0, "costo_mercaderia": 50000.0},
             {"numero": 2, "kg_primera": 40.0, "costo_mercaderia": 30000.0},
             {"numero": 3, "kg_primera": 10.0, "costo_mercaderia": 9000.0}]
    margenes = {1: {"precio_vigente": 1000, "denominador_tasas": 0.8, "costo_envase_unidad_venta": 125},
                2: {"precio_vigente": 1000, "denominador_tasas": 0.8, "envase_variable": True,
                    "costo_envase_unidad_venta": 0, "costo_envase_reprocesado_unidad_venta": 200}}
    rl = rentabilidad_del_lote(guias, margenes)
    assert rl["por_guia"][1] == {"precio": 1000.0, "venta_lista": 100000.0, "venta": 80000.0,
                                 "mercaderia": 50000.0, "cajas": 12500.0, "renta": 17500.0}
    assert rl["por_guia"][2]["cajas"] == 8000.0                     # la caja entera de reprocesado
    assert (rl["venta"], rl["mercaderia"], rl["cajas"], rl["renta"], rl["pct"]) \
        == (112000.0, 80000.0, 20500.0, 11500.0, 14.4)               # 11.500 / 80.000
    assert rl["guias_sin_precio"] == 1 and rl["tasas"] == -28000.0
    assert rentabilidad_del_lote(guias, {})["venta"] is None


def test_la_PANTALLA_trae_la_RENTABILIDAD_DEL_LOTE_con_el_precio_del_DIA_de_la_guia(base, monkeypatch):
    """Precio del 09/10: $11.000 (el de $15.000 empieza el 10/10). Venta
    305,26 kg × $11.000 × 0,8; costo 32 × $75.000 más la caja ($1.000 / 8 kg
    por kilo)."""
    tarjeta, texto = _tarjeta(_pagina(base, monkeypatch, "/compras/11/detalle", "compras"))
    renta = tarjeta.split("data-rentabilidad>")[1]
    assert "R1: 265.26 kg × $11.000 $2.917.860" in texto and "R2: 40 kg × $11.000 $440.000" in texto
    assert "Tasas del cliente $-671.572" in texto and "Venta $2.686.288" in texto
    assert "Costo: cajones de esta compra $2.400.000" in texto and "Costo: cajas de Día $38.158" in texto
    assert re.findall(r'<div class="dato rindio-total" data-renta>.*?</div>', renta, re.S)[0].count("$248.130") == 1
    assert "Rentabilidad $248.130 · 10.3%" in texto
    # Solo la rentabilidad real: ni el margen supuesto ni el sugerido.
    for ajeno in ("sugerid", "supuest", "objetivo"):
        assert ajeno not in texto.lower(), ajeno


def test_a_313px_el_bloque_no_DESBORDA(base, monkeypatch):
    pytest.importorskip("playwright")
    from tests.test_remitos import _que_se_sale
    pagina = _pagina(base, monkeypatch, "/compras/11/detalle", "compras")
    assert pagina.count('class="rindio-guia"') == 2                  # identidad: las dos guías de la 11
    medicion = _que_se_sale(pagina, 313)
    assert medicion["pagina"] == 0 and medicion["salidos"] == [], medicion
