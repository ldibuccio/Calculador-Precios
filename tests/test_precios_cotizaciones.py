# -*- coding: utf-8 -*-
"""PRECIOS COTIZACIONES (dueño, 07/10): el precio de cada ficha de un cliente
NUEVO, sin ninguna operación, con el costo de lo que ya se compró.

LA CUENTA NO ES NUEVA. Es `calcular_listado_para_negociar_precios`, la de
Márgenes y Cargar precios manuales, que arranca de las fichas y de las
compras de todos (nunca de las ventas). Lo que agrega esta pantalla es la
ficha que esa cuenta deja afuera —sin compras en los últimos 15 días—, que
acá sale "sin costo" en vez de desaparecer.

Contra Postgres, como el humo. El GALPÓN:

  EJEMPLO Nuevo (cliente 1): utilidad 20%, IVA +10%, flete −10%, sin una venta.
    ficha 1 Tomate: kilo, caja de 10 kg ($120).
      compras del día -3: 10 cajones a $1600 (160 kg) y una SIN PRECIO;
      del día -4: 10 cajones a $2080 (160 kg) → entra (la ventana es F1 y el
      día anterior); del día -6: $9999 → RIVAL, fuera de la ventana.
      Costo = (16000 + 20800) / 320 = $115 por kilo; envase 120/10 = $12;
      sugerido = (115 × 1,20 + 12) / (1 + 0,10 − 0,10) = $150.
    ficha 2 Zapallo: su única compra es de hace 30 días → "sin costo".
  RIVAL cliente 2: utilidad 90% y una ficha de Tomate. No puede mezclarse.
  RIVAL de vigencia: una utilidad del 50% para el cliente 1 que rige en 5 días.

EL INTERRUPTOR ES EL DEL HUMO: sin Postgres se saltea; con
HUMO_OBLIGATORIO=1 dejar de poder correrlo FALLA.
"""
import io
import os
import re
import sys
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Nuevo'), (2, 'EJEMPLO Rival');
insert into articulos (id, nombre, grupo) overriding system value
  values (1, 'EJEMPLO Tomate', 'hortaliza'), (2, 'EJEMPLO Zapallo', 'hortaliza');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto Uno', 'N01P01'), (2, 'EJEMPLO Puesto Dos', 'N01P02');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
insert into envases_costo_historial (envase_id, costo, vigente_desde) values (1, 120, current_date - 60);
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 10, 'kilo', 1), (2, 1, 2, 10, 'kilo', 1), (3, 2, 1, 10, 'kilo', 1);
insert into clientes_parametros_historial (cliente_id, nombre_parametro, valor, vigente_desde, tipo) values
  (1, 'utilidad_objetivo', 0.20, current_date - 30, 'utilidad'),
  (1, 'IVA', 0.10, current_date - 30, 'suma'),
  (1, 'flete', 0.10, current_date - 30, 'resta'),
  (1, 'utilidad_objetivo', 0.50, current_date + 5, 'utilidad'),
  (2, 'utilidad_objetivo', 0.90, current_date - 30, 'utilidad');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado)
  overriding system value values
  (1, 1, 1, current_date - 3, 10, 16, 160, 1600, 'recepcionado'),
  (2, 2, 1, current_date - 4, 10, 16, 160, 2080, 'recepcionado'),
  (3, 1, 1, current_date - 6, 10, 16, 160, 9999, 'recepcionado'),
  (4, 2, 1, current_date - 3,  5, 16,  80, null, 'recepcionado'),
  (5, 1, 2, current_date - 30, 10, 20, 200, 3000, 'recepcionado');
"""


@pytest.fixture(scope="module")
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay un Postgres usable: Precios Cotizaciones no se verificó.")
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

    def sql(consulta, parametros=None):
        con = psycopg2.connect(url)
        try:
            with con.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            con.commit()
            return filas
        finally:
            con.close()

    with patch.dict(os.environ, {"DATABASE_URL": url}):
        import app.main as m
        yield m, sql


def _filas(m):
    from app.costeo import calcular_precios_sugeridos
    return {f["ficha_id"]: f for f in calcular_precios_sugeridos(1)}


def test_la_CUENTA_es_la_de_MARGENES_y_sale_de_las_compras_de_la_ventana(base):
    m, _ = base
    from app.costeo import calcular_listado_para_negociar_precios
    tomate = _filas(m)[1]
    assert tomate["costo_actual"] == pytest.approx(115)
    assert tomate["costo_envase_unidad_venta"] == pytest.approx(12)
    assert tomate["precio_sugerido"] == pytest.approx(150)
    # La MISMA cuenta que Márgenes, no otra que da lo mismo hoy.
    de_margenes = {f["ficha_id"]: f for f in calcular_listado_para_negociar_precios(1)}
    assert tomate["precio_sugerido"] == de_margenes[1]["precio_sugerido"]
    # De qué compras sale: las de la ventana, con la que no entra marcada; el
    # RIVAL del día -6 no aparece.
    compras = [(c["compra_id"], c["entra"], c["motivo"], c["proveedor_nombre"]) for c in tomate["compras_del_costo"]]
    assert compras == [(2, True, None, "EJEMPLO Puesto Dos"), (1, True, None, "EJEMPLO Puesto Uno"),
                       (4, False, "sin precio de compra", "EJEMPLO Puesto Dos")]


def test_una_ficha_SIN_COMPRAS_RECIENTES_sale_SIN_COSTO_en_vez_de_desaparecer(base):
    m, _ = base
    from app.costeo import calcular_listado_para_negociar_precios
    filas = _filas(m)
    assert set(filas) == {1, 2}                                   # el RIVAL cliente 2 no entra
    zapallo = filas[2]
    assert (zapallo["costo_actual"], zapallo["precio_sugerido"]) == (None, None)
    assert zapallo["sin_costo"] == "sin compras en los últimos 15 días"
    # Es justo lo que Márgenes deja afuera: por eso esta pantalla lo agrega.
    assert 2 not in {f["ficha_id"] for f in calcular_listado_para_negociar_precios(1)}


def test_la_PANTALLA_muestra_costo_compras_envase_condiciones_y_sugerido(base):
    from fastapi.testclient import TestClient
    m, _ = base
    pagina = TestClient(m.app).get("/precios/cotizaciones", params={"cliente_id": 1})
    assert pagina.status_code == 200
    # El botón, la pestaña y la barra se llaman igual (dueño, 07/10).
    assert pagina.text.count('<div class="barra-titulo">Precios Cotizaciones</div>') == 1
    assert pagina.text.count('<title>Precios Cotizaciones</title>') == 1
    marcado = pagina.text.split("</style>")[-1]
    assert "Utilidad 20% sobre la mercadería · IVA +10% · flete −10%" in marcado
    tomate = marcado.split('data-ficha="1"')[1].split('data-ficha="2"')[0]
    assert "Costo de compra: <strong>$115</strong> por kilo" in tomate
    assert "Envase: $12 por kilo" in tomate
    assert "Precio sugerido: $150 por kilo" in tomate
    assert re.search(r'name="pendiente_precio_1"[^>]*value="150"', tomate)
    assert "EJEMPLO Puesto Dos (no entra: sin precio de compra)" in tomate
    assert "$9.999" not in marcado
    zapallo = marcado.split('data-ficha="2"')[1]
    assert "Sin costo: sin compras en los últimos 15 días" in zapallo
    assert re.search(r'name="pendiente_precio_2"[^>]*value=""', zapallo)
    for jerga in ("ficha_id", "costo_actual", "utilidad_objetivo", "None"):
        assert jerga not in re.sub(r"<[^>]+>", " ", marcado), jerga


def _texto_del_pdf(contenido: bytes) -> str:
    import pypdfium2 as pdfium
    return "\n".join(p.get_textpage().get_text_range() for p in pdfium.PdfDocument(contenido))


def test_PDF_y_EXCEL_salen_con_LO_DE_LA_PANTALLA_y_lo_corregido_a_mano(base):
    from fastapi.testclient import TestClient
    from openpyxl import load_workbook
    m, _ = base
    cliente = TestClient(m.app)
    formulario = {"cliente_id": "1", "pendiente_precio_1": "165", "pendiente_precio_2": "300"}
    excel = cliente.post("/precios/cotizaciones/exportar-excel", data=formulario)
    assert excel.status_code == 200
    hoja = load_workbook(io.BytesIO(excel.content)).active
    celdas = [[c for c in fila] for fila in hoja.iter_rows(values_only=True)]
    assert celdas[0][0] == "Precios Cotizaciones" and hoja.title == "Precios Cotizaciones"
    assert celdas[1][0].startswith("Cliente: EJEMPLO Nuevo · ") and celdas[1][0].endswith("2 precios corregidos a mano")
    assert celdas[2][0] == "Utilidad 20% sobre la mercadería · IVA +10% · flete −10%"
    filas = {fila[0]: fila for fila in celdas[5:]}
    assert set(filas) == {"EJEMPLO Tomate", "EJEMPLO Zapallo"}
    tomate = filas["EJEMPLO Tomate"]
    assert (tomate[1], tomate[3], tomate[4], tomate[5]) == ("$115 por kilo", "$12", "$150", "$165 (a mano)")
    assert re.fullmatch(r"\d\d/\d\d EJEMPLO Puesto Dos \$2\.080 × 10 · \d\d/\d\d EJEMPLO Puesto Uno \$1\.600 × 10 · "
                        r"\d\d/\d\d EJEMPLO Puesto Dos \(no entra: sin precio de compra\)", tomate[2])
    zapallo = filas["EJEMPLO Zapallo"]
    assert (zapallo[1], zapallo[4], zapallo[5]) == (
        "sin costo (sin compras en los últimos 15 días)", "sin costo", "$300 (a mano)")
    pdf = cliente.post("/precios/cotizaciones/exportar-pdf", data=formulario)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    texto = " ".join(_texto_del_pdf(pdf.content).split())
    assert texto.startswith("Precios Cotizaciones"), texto[:60]
    for esperado in ("Cliente: EJEMPLO Nuevo", "2 precios corregidos a mano", "IVA +10%",
                     "EJEMPLO Tomate", "$150", "$165 (a mano)", "$300 (a mano)"):
        assert esperado in texto, esperado


def test_GUARDAR_los_deja_como_precios_vigentes_DESDE_HOY_y_solo_los_del_cliente(base):
    from fastapi.testclient import TestClient
    m, sql = base
    respuesta = TestClient(m.app).post(
        "/precios/cotizaciones/guardar",
        data={"cliente_id": "1", "pendiente_precio_1": "150", "pendiente_precio_2": ""},
        follow_redirects=False)
    try:
        assert respuesta.status_code == 303
        assert respuesta.headers["location"].startswith("/precios/cotizaciones?cliente_id=1&aviso=Se+guardaron+1+precio+de")
        hoy = m._hoy_argentina()
        assert sql("select cliente_id, ficha_id, articulo_id, precio::float, vigente_desde "
                   "from precios_venta_historial") == [(1, 1, 1, 150.0, hoy)]
        from app.db import listar_precios_vigentes_por_cliente
        assert [(p["ficha_id"], float(p["precio"])) for p in listar_precios_vigentes_por_cliente(1, hoy)] == [(1, 150.0)]
    finally:
        sql("delete from precios_venta_historial")
