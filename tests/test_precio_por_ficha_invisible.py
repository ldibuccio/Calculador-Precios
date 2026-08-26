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
    return {FECHA_PEDIDO: {fila["ficha_id"]: fila for fila in _listado()}}


def test_rentabilidad_teorica_no_se_movio():
    renglones = [
        {"fecha_operacion": FECHA_PEDIDO, "ficha_id": 901, "articulo_id": 1,
         "articulo_nombre": "Banana", "articulo_grupo": "fruta", "bultos": 30},
        {"fecha_operacion": FECHA_PEDIDO, "ficha_id": 902, "articulo_id": 2,
         "articulo_nombre": "Mango", "articulo_grupo": "fruta", "bultos": 12},
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
                     "cantidad": 30, "unidades": 600.0, "cliente_id": CLIENTE_ID,
                     "ficha_id": 901}],
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


# --- Parte 2: el renglón del pedido guarda su ficha ---
#
# Mismo criterio que arriba: los números se capturaron corriendo este
# escenario contra el código ANTERIOR a la Parte 2 (cuando el renglón solo
# tenía artículo y los márgenes se anclaban por artículo) y comparando.
# Salieron idénticos. El escenario es más completo a propósito: dos fechas
# con precios distintos, dos grupos, una merma, y los dos motivos de "no
# calculable" — así el reporte entero queda clavado, no solo un total.

FICHAS_P2 = [
    {"id": 901, "articulo_id": 1, "articulo_nombre": "Banana", "articulo_grupo": "fruta",
     "contenido_caja": 20.0, "unidad_venta": "kilo"},
    {"id": 902, "articulo_id": 2, "articulo_nombre": "Batata", "articulo_grupo": "hortaliza",
     "contenido_caja": 18.0, "unidad_venta": "kilo"},
    {"id": 903, "articulo_id": 3, "articulo_nombre": "Rúcula", "articulo_grupo": "hoja",
     "contenido_caja": None, "unidad_venta": "unidad"},
]
FECHA_A, FECHA_B = date(2026, 8, 21), date(2026, 8, 22)


def _margen_p2(precio, costo, envase=0.0, denom=1.0):
    return {"precio_vigente": precio, "costo_actual": costo,
            "costo_envase_unidad_venta": envase, "denominador_tasas": denom}


def _renglon_p2(fecha, articulo_id, nombre, grupo, bultos):
    return {"fecha_operacion": fecha, "articulo_id": articulo_id,
            "ficha_id": 900 + articulo_id if articulo_id else None,
            "articulo_nombre": nombre, "articulo_grupo": grupo, "bultos": bultos}


# Los márgenes se anclan por FICHA: el precio del 21 y el del 22 son
# distintos, y cada pedido usa el suyo.
MARGENES_P2 = {
    FECHA_A: {901: _margen_p2(100.0, 80.0, envase=4.0, denom=0.9), 902: _margen_p2(50.0, 30.0)},
    FECHA_B: {901: _margen_p2(120.0, 80.0, envase=4.0, denom=0.9)},
}
RENGLONES_P2 = [
    _renglon_p2(FECHA_A, 1, "Banana", "fruta", 10),
    _renglon_p2(FECHA_B, 1, "Banana", "fruta", 5),
    _renglon_p2(FECHA_A, 2, "Batata", "hortaliza", 4),
    _renglon_p2(FECHA_A, 3, "Rúcula", "hoja", 6),   # ficha sin contenido_caja
    _renglon_p2(FECHA_A, None, None, None, 3),      # sin identificar
]


def test_teorica_anclada_por_ficha_no_movio_ningun_numero():
    resultado = calcular_rentabilidad_de_pedidos(RENGLONES_P2, FICHAS_P2, MARGENES_P2)

    filas = {f["articulo_nombre"]: f for g in resultado["grupos"] for f in g["filas"]}
    banana = filas["Banana"]
    assert banana["bultos"] == 15.0 and banana["unidades"] == 300.0
    assert banana["venta_neta"] == 28800.0   # 200×100×0.9 + 100×120×0.9
    assert banana["costo_mercaderia"] == 24000.0
    assert banana["costo_envase"] == 1200.0
    assert banana["renta_pesos"] == 3600.0
    batata = filas["Batata"]
    assert batata["venta_neta"] == 3600.0 and batata["renta_pesos"] == 1440.0

    totales = resultado["totales"]
    assert totales["bultos"] == 19.0
    assert totales["venta_neta"] == 32400.0
    assert totales["costo_total"] == 27360.0
    assert totales["renta_pesos"] == 5040.0
    assert round(totales["utilidad_pct"], 6) == 19.266055

    # Los dos motivos de "no calculable" siguen saliendo con su peso: lo
    # que no se puede calcular no suma como cero, ni antes ni ahora.
    assert sorted(
        (e["motivo"], e["articulo_nombre"], e["bultos"]) for e in resultado["no_calculables"]
    ) == [("sin_conversion", "Rúcula", 6.0), ("sin_identificar", "Sin identificar", 3.0)]


def test_real_anclada_por_ficha_no_movio_ningun_numero():
    # La fila del reporte sigue siendo por ARTÍCULO (ahí vive el stock y la
    # merma); lo que ancla por ficha es el precio de cada venta.
    articulos_datos = [{
        "articulo_id": 1, "nombre": "Banana", "grupo": "fruta",
        "entradas": [{"orden": (FECHA_A, 0), "cantidad": 50, "costo_bulto": 1500.0,
                      "tipo_lote": "guia"}],
        "salidas": [
            {"orden": (FECHA_A, 1), "tipo": "armado", "fecha": FECHA_A, "cantidad": 10,
             "unidades": 200.0, "cliente_id": 1, "ficha_id": 901},
            {"orden": (FECHA_A, 2), "tipo": "merma", "fecha": FECHA_A, "cantidad": 3},
            {"orden": (FECHA_B, 1), "tipo": "armado", "fecha": FECHA_B, "cantidad": 5,
             "unidades": 100.0, "cliente_id": 1, "ficha_id": 901},
        ],
    }]
    resultado = calcular_rentabilidad_real(articulos_datos, MARGENES_P2, 1, FECHA_A, FECHA_B)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["articulo_nombre"] == "Banana"
    assert fila["bultos"] == 15.0
    assert fila["venta_neta"] == 28800.0
    assert fila["costo_mercaderia"] == 22500.0
    assert fila["costo_envase"] == 1200.0
    assert fila["costo_mermas"] == 4500.0
    assert fila["renta_pesos"] == 600.0

    totales = resultado["totales"]
    assert totales["costo_total"] == 28200.0
    assert totales["renta_pesos"] == 600.0
    assert round(totales["utilidad_pct"], 6) == 2.666667
    assert totales["afuera_bultos"] == 0
