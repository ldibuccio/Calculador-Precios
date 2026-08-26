from datetime import date

import pytest

from core.motor_costeo import utilidad_real_multi_concepto
from core.rentabilidad import calcular_rentabilidad_de_pedidos

FECHA_1 = date(2026, 8, 21)
FECHA_2 = date(2026, 8, 22)

FICHAS = [
    {"id": 901, "articulo_id": 1, "articulo_nombre": "Banana", "articulo_grupo": "fruta", "contenido_caja": 20.0, "unidad_venta": "kilo"},
    {"id": 902, "articulo_id": 2, "articulo_nombre": "Batata", "articulo_grupo": "hortaliza", "contenido_caja": 18.0, "unidad_venta": "kilo"},
    {"id": 903, "articulo_id": 3, "articulo_nombre": "Rúcula", "articulo_grupo": "hoja", "contenido_caja": None, "unidad_venta": "unidad"},
]


def _renglon(fecha, articulo_id, nombre, grupo, bultos, ficha_id=None):
    """Un renglón agrupado por fecha y FICHA. Sin ficha_id explícito, la de
    su artículo (900 + articulo_id, la convención de los fixtures); con
    articulo_id None es un renglón sin identificar, que tampoco tiene ficha."""
    if ficha_id is None and articulo_id is not None:
        ficha_id = 900 + articulo_id
    return {
        "fecha_operacion": fecha, "articulo_id": articulo_id, "ficha_id": ficha_id,
        "articulo_nombre": nombre, "articulo_grupo": grupo, "bultos": bultos,
    }


def _margen(precio_vigente, costo_actual, envase=0.0, denominador=1.0):
    """Una fila de calcular_listado_para_negociar_precios, reducida a lo que usa rentabilidad."""
    return {
        "precio_vigente": precio_vigente,
        "costo_actual": costo_actual,
        "costo_envase_unidad_venta": envase,
        "denominador_tasas": denominador,
    }


def test_rentabilidad_aplica_tasas_y_envase_no_el_precio_de_lista_crudo():
    # Cliente con tasas: denominador 0.8 (resta neta 20%). Lista $100 →
    # neta $80. Costo $60 + $4 de envase. La venta NUNCA es la lista cruda
    # (estaría sobrevaluada) y el envase SIEMPRE suma al costo.
    renglones = [_renglon(FECHA_1, 1, "Banana", "fruta", 10)]
    margenes = {FECHA_1: {901: _margen(100.0, 60.0, envase=4.0, denominador=0.8)}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["unidades"] == 200  # 10 bultos × 20k
    assert fila["venta_neta"] == 200 * 80.0  # 16.000 — no 20.000 de lista
    assert fila["costo_mercaderia"] == 200 * 60.0
    assert fila["costo_envase"] == 200 * 4.0
    assert fila["costo_total"] == 200 * 64.0
    assert fila["renta_pesos"] == 16000 - 12800  # 3.200
    assert fila["precio_lista_promedio"] == 100.0
    assert fila["precio_neto_promedio"] == 80.0


def test_rentabilidad_da_exactamente_lo_mismo_que_margenes_por_articulo():
    # EL CONTROL DEL DUEÑO: mismo artículo, misma fecha → la utilidad de
    # Rentabilidad tiene que ser idéntica a la utilidad_aproximada de
    # Márgenes por Artículo (utilidad_real_multi_concepto del motor).
    tasas_suman = [0.105]
    tasas_restan = [0.28]
    denominador = 1 + sum(tasas_suman) - sum(tasas_restan)
    precio, costo, envase = 500.0, 250.0, 12.5

    renglones = [_renglon(FECHA_1, 1, "Banana", "fruta", 7)]
    margenes = {FECHA_1: {901: _margen(precio, costo, envase=envase, denominador=denominador)}}
    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes)

    utilidad_margenes = utilidad_real_multi_concepto(
        precio_vigente=precio, costo_producto=costo, costo_envase=envase,
        tasas_suman=tasas_suman, tasas_restan=tasas_restan,
    )
    fila = resultado["grupos"][0]["filas"][0]
    assert fila["utilidad_pct"] == pytest.approx(utilidad_margenes * 100)
    # Y la utilidad se gana SOLO sobre la mercadería, nunca sobre el envase.
    assert fila["utilidad_pct"] == pytest.approx(fila["renta_pesos"] / fila["costo_mercaderia"] * 100)


def test_rentabilidad_cada_fecha_usa_su_propio_margen():
    # Precio $100 el 21 y $120 el 22 (denominador 1): cada pedido con SU
    # margen anclado a la fecha, nunca el de hoy retroactivo.
    renglones = [
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
        _renglon(FECHA_2, 1, "Banana", "fruta", 5),
    ]
    margenes = {
        FECHA_1: {901: _margen(100.0, 80.0)},
        FECHA_2: {901: _margen(120.0, 80.0)},
    }

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["bultos"] == 15
    assert fila["venta_neta"] == 10 * 20 * 100 + 5 * 20 * 120  # 32.000
    assert fila["costo_total"] == 300 * 80.0
    assert fila["renta_pesos"] == 8000
    assert resultado["fechas_incluidas"] == [FECHA_1, FECHA_2]


def test_rentabilidad_agrupa_por_grupo_con_subtotales_y_orden_fijo():
    renglones = [
        _renglon(FECHA_1, 2, "Batata", "hortaliza", 4),
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
    ]
    margenes = {FECHA_1: {901: _margen(100.0, 80.0), 902: _margen(50.0, 30.0)}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes)

    # Fruta primero, hortaliza después: el orden del reporte es fijo.
    assert [g["grupo"] for g in resultado["grupos"]] == ["fruta", "hortaliza"]
    fruta, hortaliza = resultado["grupos"]
    assert fruta["subtotal"]["renta_pesos"] == 10 * 20 * (100 - 80)  # 4.000
    assert hortaliza["subtotal"]["renta_pesos"] == 4 * 18 * (50 - 30)  # 1.440
    assert resultado["totales"]["renta_pesos"] == 5440
    assert resultado["totales"]["bultos"] == 14
    # Utilidad del total: renta sobre la mercadería de TODO lo calculable.
    assert resultado["totales"]["utilidad_pct"] == pytest.approx(
        5440 / (200 * 80.0 + 72 * 30.0) * 100
    )


def test_rentabilidad_los_no_calculables_van_aparte_con_su_motivo():
    # Los CUATRO motivos, cada uno aparte y con su peso en bultos — jamás
    # sumando como cero en silencio.
    renglones = [
        _renglon(FECHA_1, None, None, None, 3),          # sin identificar
        _renglon(FECHA_1, 3, "Rúcula", "hoja", 6),       # ficha sin contenido_caja
        _renglon(FECHA_1, 2, "Batata", "hortaliza", 4),  # con costo pero sin precio vigente
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),     # sin fila de Márgenes (sin compras)
    ]
    margenes = {FECHA_1: {902: _margen(None, 30.0)}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes)

    assert resultado["grupos"] == []
    motivos = {(e["motivo"], e["articulo_nombre"]): e["bultos"] for e in resultado["no_calculables"]}
    assert motivos == {
        ("sin_identificar", "Sin identificar"): 3,
        ("sin_conversion", "Rúcula"): 6,
        ("sin_precio", "Batata"): 4,
        ("sin_costo", "Banana"): 10,
    }
    assert resultado["totales"]["no_calculables_casos"] == 4
    assert resultado["totales"]["no_calculables_bultos"] == 23
    assert resultado["totales"]["venta_neta"] == 0


def test_rentabilidad_filtro_por_grupo_y_por_articulo():
    renglones = [
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
        _renglon(FECHA_1, 2, "Batata", "hortaliza", 4),
        _renglon(FECHA_1, None, None, None, 3),
    ]
    margenes = {FECHA_1: {901: _margen(100.0, 80.0), 902: _margen(50.0, 30.0)}}

    por_grupo = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes, grupo="fruta")
    assert [g["grupo"] for g in por_grupo["grupos"]] == ["fruta"]
    # El sin identificar NO se puede filtrar (no se sabe qué es): aparece
    # igual en los no calculables — ocultarlo sería descartarlo en silencio.
    assert [e["motivo"] for e in por_grupo["no_calculables"]] == ["sin_identificar"]

    por_articulo = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes, articulo_id=2)
    assert [g["grupo"] for g in por_articulo["grupos"]] == ["hortaliza"]
    assert por_articulo["totales"]["bultos"] == 4


def test_rentabilidad_renglones_sin_bultos_no_aportan_nada():
    # Un renglón guardado con cantidad 0 (vino sin cantidades en el mail)
    # no mueve plata ni pesa: no aparece ni en calculables ni en afuera.
    renglones = [
        _renglon(FECHA_1, 1, "Banana", "fruta", 0),
        _renglon(FECHA_1, None, None, None, 0),
    ]
    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, {})

    assert resultado["grupos"] == []
    assert resultado["no_calculables"] == []
    assert resultado["fechas_incluidas"] == []


def test_rentabilidad_renta_negativa_se_calcula_igual():
    # Vender abajo del costo no se esconde: renta en rojo, no un error.
    renglones = [_renglon(FECHA_1, 1, "Banana", "fruta", 10)]
    margenes = {FECHA_1: {901: _margen(70.0, 80.0)}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["renta_pesos"] == -2000
    assert fila["utilidad_pct"] == pytest.approx(-2000 / 16000 * 100)


def test_rentabilidad_articulo_calculable_un_dia_y_no_el_otro_se_parte():
    # El 21 la Banana tiene margen; el 22 no hay precio. La parte
    # calculable suma, la otra queda AFUERA con su motivo — nunca
    # promediada ni asumida.
    renglones = [
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
        _renglon(FECHA_2, 1, "Banana", "fruta", 5),
    ]
    margenes = {
        FECHA_1: {901: _margen(100.0, 80.0)},
        FECHA_2: {901: _margen(None, 80.0)},
    }

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, margenes)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["bultos"] == 10  # solo el día calculable
    assert resultado["no_calculables"] == [
        {
            "motivo": "sin_precio",
            "motivo_etiqueta": "Sin precio de venta vigente a la fecha del pedido",
            "articulo_id": 1, "articulo_nombre": "Banana", "bultos": 5.0, "dias": 1,
        }
    ]


def test_rentabilidad_articulo_sin_grupo_va_en_su_seccion_al_final():
    fichas = FICHAS + [
        {"id": 909, "articulo_id": 9, "articulo_nombre": "Zapallo", "articulo_grupo": None, "contenido_caja": 10.0, "unidad_venta": "kilo"},
    ]
    renglones = [
        _renglon(FECHA_1, 9, "Zapallo", None, 2),
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
    ]
    margenes = {FECHA_1: {901: _margen(100.0, 80.0), 909: _margen(40.0, 20.0)}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, fichas, margenes)

    assert [g["etiqueta"] for g in resultado["grupos"]] == ["Fruta", "Sin grupo"]
