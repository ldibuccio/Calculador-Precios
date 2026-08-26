"""El precio pasó a colgar de la FICHA: con una ficha por artículo, NADA se movió.

Este archivo es una red, no un test de una función: clava los números de
Márgenes, Objetivo de Compra y las DOS rentabilidades para un escenario
completo. Los valores esperados se capturaron corriendo el MISMO
escenario contra el código anterior al cambio (cuando el precio colgaba
del artículo) y comparando: salieron idénticos, uno por uno.

Si mañana alguien toca la cadena del precio y algún número de acá se
mueve, algo está mal — o el cambio no era invisible, o se rompió algo.

La convención de los fixtures: el id de la ficha es 900 + el del
artículo. A propósito distinto, para que confundir las dos claves rompa
el test en vez de pasar desapercibido.
"""

from datetime import date, datetime
from unittest.mock import patch

from app.costeo import calcular_listado_para_negociar_precios, calcular_objetivos_de_compra
from core.costo_real import calcular_rentabilidad_real
from core.rentabilidad import calcular_rentabilidad_de_pedidos

MOMENTO = datetime(2026, 8, 26, 12, 0)
FECHA_PEDIDO = date(2026, 8, 26)
CLIENTE_ID = 1

FICHAS = [
    {"id": 901, "articulo_id": 1, "articulo_nombre": "Banana", "unidad_venta": "kilo",
     "envase_id": 7, "contenido_caja": 20.0, "envase_variable": False,
     "nombre_cliente": "BANANA BOLIVIA", "codigo_cliente": "B-101"},
    {"id": 902, "articulo_id": 2, "articulo_nombre": "Mango", "unidad_venta": "unidad",
     "envase_id": 7, "contenido_caja": 12.0, "envase_variable": False,
     "nombre_cliente": None, "codigo_cliente": None},
]
COMPRAS = [
    {"articulo_id": 1, "articulo_nombre": "Banana", "fecha_operacion": date(2026, 8, 25),
     "cantidad_cajones": 10, "contenido_por_cajon": 20, "cantidad_kilos": 200, "importe": 4000,
     "cargado_el": datetime(2026, 8, 25, 9)},
    {"articulo_id": 1, "articulo_nombre": "Banana", "fecha_operacion": date(2026, 8, 20),
     "cantidad_cajones": 8, "contenido_por_cajon": 20, "cantidad_kilos": 160, "importe": 3600,
     "cargado_el": datetime(2026, 8, 20, 9)},
    {"articulo_id": 2, "articulo_nombre": "Mango", "fecha_operacion": date(2026, 8, 26),
     "cantidad_cajones": 5, "contenido_por_cajon": 12, "cantidad_kilos": None, "importe": 2400,
     "cargado_el": datetime(2026, 8, 26, 9)},
]
# Las filas de precio tal como salen de la base: la clave es ficha_id, y
# articulo_id viaja al lado (lo usan las pantallas para mostrar).
PRECIOS = [
    {"ficha_id": 901, "articulo_id": 1, "precio": 260.0, "vigente_desde": date(2026, 8, 24)},
    {"ficha_id": 902, "articulo_id": 2, "precio": 240.0, "vigente_desde": date(2026, 8, 20)},
]
CONCEPTOS = {"tasas_suman": [0.21], "tasas_restan": [0.06], "utilidad": 0.25}
ENVASES = [{"envase_id": 7, "costo": 480.0}]


def _listado():
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=COMPRAS),
        patch("app.costeo.listar_fichas_por_cliente", return_value=FICHAS),
        patch("app.costeo.listar_precios_vigentes_por_cliente", return_value=PRECIOS),
        patch("app.costeo.listar_costos_envases_vigentes", return_value=ENVASES),
        patch("app.costeo.listar_conceptos_vigentes_por_cliente", return_value=CONCEPTOS),
    ):
        return calcular_listado_para_negociar_precios(CLIENTE_ID, MOMENTO)


def test_margenes_por_articulo_no_se_movieron():
    filas = {fila["articulo_nombre"]: fila for fila in _listado()}

    banana = filas["Banana"]
    assert banana["ficha_id"] == 901
    assert banana["costo_actual"] == 200.0
    assert banana["costo_anterior"] == 180.0
    assert banana["variacion"] == "subio"
    assert banana["precio_vigente"] == 260.0
    assert round(banana["precio_sugerido"], 6) == 238.26087
    assert round(banana["utilidad_aproximada"], 6) == 0.375
    assert banana["costo_envase_unidad_venta"] == 24.0
    assert banana["denominador_tasas"] == 1.15

    mango = filas["Mango"]
    assert mango["ficha_id"] == 902
    assert mango["costo_actual"] == 200.0
    assert mango["costo_anterior"] is None
    assert mango["precio_vigente"] == 240.0
    assert round(mango["precio_sugerido"], 6) == 252.173913
    assert round(mango["utilidad_aproximada"], 6) == 0.18
    assert mango["costo_envase_unidad_venta"] == 40.0


def test_cada_ficha_toma_SU_precio_y_no_el_de_otra():
    # El corazón del cambio: el precio se busca por ficha. Si el código
    # volviera a buscarlo por artículo, con estos ids (901/902 contra 1/2)
    # no encontraría ninguno y los dos precios darían None.
    filas = {fila["articulo_nombre"]: fila for fila in _listado()}
    assert filas["Banana"]["precio_vigente"] == 260.0
    assert filas["Mango"]["precio_vigente"] == 240.0


def test_objetivo_de_compra_no_se_movio():
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=COMPRAS),
        patch("app.costeo.listar_fichas_por_cliente", return_value=FICHAS),
        patch("app.costeo.listar_precios_vigentes_por_cliente", return_value=PRECIOS),
        patch("app.costeo.listar_costos_envases_vigentes", return_value=ENVASES),
        patch("app.costeo.listar_conceptos_vigentes_por_cliente", return_value=CONCEPTOS),
    ):
        objetivos = calcular_objetivos_de_compra(CLIENTE_ID, MOMENTO)

    # Solo el Mango queda bajo el objetivo de utilidad (18% contra 25%).
    assert [a["articulo_nombre"] for a in objetivos["articulos"]] == ["Mango"]
    mango = objetivos["articulos"][0]
    assert mango["precio_vigente"] == 240.0
    assert round(mango["utilidad_actual"], 6) == 0.18
    assert mango["entra_por_unidad"] == 276.0
    assert mango["objetivo_por_unidad"] == 188.8
    assert round(mango["objetivo_bulto_ultima"], 6) == 2265.6
    assert objetivos["sin_precio_vigente"] == []


def _margenes_por_fecha():
    return {FECHA_PEDIDO: {fila["articulo_id"]: fila for fila in _listado()}}


def test_rentabilidad_teorica_no_se_movio():
    renglones = [
        {"fecha_operacion": FECHA_PEDIDO, "articulo_id": 1, "articulo_nombre": "Banana",
         "articulo_grupo": "fruta", "bultos": 30},
        {"fecha_operacion": FECHA_PEDIDO, "articulo_id": 2, "articulo_nombre": "Mango",
         "articulo_grupo": "fruta", "bultos": 12},
    ]
    totales = calcular_rentabilidad_de_pedidos(renglones, FICHAS, _margenes_por_fecha())["totales"]

    assert totales["bultos"] == 42.0
    assert totales["venta_neta"] == 219144.0
    assert totales["costo_mercaderia"] == 148800.0
    assert totales["costo_envase"] == 20160.0
    assert totales["costo_total"] == 168960.0
    assert totales["renta_pesos"] == 50184.0
    assert round(totales["utilidad_pct"], 6) == 33.725806
    assert totales["no_calculables_casos"] == 0


def test_rentabilidad_real_no_se_movio():
    articulos_datos = [{
        "articulo_id": 1, "nombre": "Banana", "grupo": "fruta",
        "entradas": [{"orden": (FECHA_PEDIDO, 1), "cantidad": 100, "costo_bulto": 3800.0,
                      "tipo_lote": "guia"}],
        "salidas": [{"orden": (FECHA_PEDIDO, 2), "tipo": "armado", "fecha": FECHA_PEDIDO,
                     "cantidad": 30, "unidades": 600.0, "cliente_id": CLIENTE_ID}],
    }]
    totales = calcular_rentabilidad_real(
        articulos_datos, _margenes_por_fecha(), CLIENTE_ID, FECHA_PEDIDO, FECHA_PEDIDO
    )["totales"]

    assert totales["bultos"] == 30.0
    assert totales["venta_neta"] == 179400.0
    assert totales["costo_mercaderia"] == 114000.0
    assert totales["costo_envase"] == 14400.0
    assert totales["costo_total"] == 128400.0
    assert totales["renta_pesos"] == 51000.0
    assert round(totales["utilidad_pct"], 6) == 44.736842
    assert totales["afuera_bultos"] == 0
