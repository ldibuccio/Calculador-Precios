from datetime import date

from core.rentabilidad import calcular_rentabilidad_de_pedidos

FECHA_1 = date(2026, 8, 21)
FECHA_2 = date(2026, 8, 22)

FICHAS = [
    {"articulo_id": 1, "articulo_nombre": "Banana", "articulo_grupo": "fruta", "contenido_caja": 20.0, "unidad_venta": "kilo"},
    {"articulo_id": 2, "articulo_nombre": "Batata", "articulo_grupo": "hortaliza", "contenido_caja": 18.0, "unidad_venta": "kilo"},
    {"articulo_id": 3, "articulo_nombre": "Rúcula", "articulo_grupo": "hoja", "contenido_caja": None, "unidad_venta": "unidad"},
]


def _renglon(fecha, articulo_id, nombre, grupo, bultos):
    return {
        "fecha_operacion": fecha, "articulo_id": articulo_id,
        "articulo_nombre": nombre, "articulo_grupo": grupo, "bultos": bultos,
    }


def test_rentabilidad_camino_feliz_con_cambio_de_precio_entre_fechas():
    # Banana: 10 bultos el 21 a $100 y 5 el 22 a $120 — cada pedido con SU
    # precio vigente, nunca retroactivo. Contenido 20k por bulto, costo $80.
    renglones = [
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
        _renglon(FECHA_2, 1, "Banana", "fruta", 5),
    ]
    precios = {FECHA_1: {1: 100.0}, FECHA_2: {1: 120.0}}
    costos = {FECHA_1: {1: 80.0}, FECHA_2: {1: 80.0}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, precios, costos)

    assert len(resultado["grupos"]) == 1
    fila = resultado["grupos"][0]["filas"][0]
    assert fila["bultos"] == 15
    assert fila["unidades"] == 300  # 15 bultos × 20k
    assert fila["venta"] == 10 * 20 * 100 + 5 * 20 * 120  # 32.000
    assert fila["costo_total"] == 300 * 80  # 24.000
    assert fila["renta_pesos"] == 8000
    assert round(fila["renta_pct"], 2) == 25.0
    # Precio promedio PONDERADO por lo vendido, no el promedio simple.
    assert round(fila["precio_promedio"], 2) == round(32000 / 300, 2)
    assert resultado["totales"]["renta_pesos"] == 8000
    assert resultado["fechas_incluidas"] == [FECHA_1, FECHA_2]


def test_rentabilidad_agrupa_por_grupo_con_subtotales_y_orden_fijo():
    renglones = [
        _renglon(FECHA_1, 2, "Batata", "hortaliza", 4),
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
    ]
    precios = {FECHA_1: {1: 100.0, 2: 50.0}}
    costos = {FECHA_1: {1: 80.0, 2: 30.0}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, precios, costos)

    # Fruta primero, hortaliza después: el orden del reporte es fijo.
    assert [g["grupo"] for g in resultado["grupos"]] == ["fruta", "hortaliza"]
    fruta, hortaliza = resultado["grupos"]
    assert fruta["subtotal"]["renta_pesos"] == 10 * 20 * (100 - 80)  # 4.000
    assert hortaliza["subtotal"]["renta_pesos"] == 4 * 18 * (50 - 30)  # 1.440
    assert resultado["totales"]["renta_pesos"] == 5440
    assert resultado["totales"]["bultos"] == 14


def test_rentabilidad_los_no_calculables_van_aparte_con_su_motivo():
    # Los CUATRO motivos, cada uno aparte y con su peso en bultos — jamás
    # sumando como cero en silencio.
    renglones = [
        _renglon(FECHA_1, None, None, None, 3),          # sin identificar
        _renglon(FECHA_1, 3, "Rúcula", "hoja", 6),       # ficha sin contenido_caja
        _renglon(FECHA_1, 2, "Batata", "hortaliza", 4),  # sin precio vigente
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),     # sin costo (sin compras 48hs)
    ]
    precios = {FECHA_1: {1: 100.0}}  # Batata sin precio
    costos = {FECHA_1: {2: 30.0}}    # Banana sin costo

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, precios, costos)

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
    assert resultado["totales"]["venta"] == 0


def test_rentabilidad_filtro_por_grupo_y_por_articulo():
    renglones = [
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
        _renglon(FECHA_1, 2, "Batata", "hortaliza", 4),
        _renglon(FECHA_1, None, None, None, 3),
    ]
    precios = {FECHA_1: {1: 100.0, 2: 50.0}}
    costos = {FECHA_1: {1: 80.0, 2: 30.0}}

    por_grupo = calcular_rentabilidad_de_pedidos(renglones, FICHAS, precios, costos, grupo="fruta")
    assert [g["grupo"] for g in por_grupo["grupos"]] == ["fruta"]
    # El sin identificar NO se puede filtrar (no se sabe qué es): aparece
    # igual en los no calculables — ocultarlo sería descartarlo en silencio.
    assert [e["motivo"] for e in por_grupo["no_calculables"]] == ["sin_identificar"]

    por_articulo = calcular_rentabilidad_de_pedidos(renglones, FICHAS, precios, costos, articulo_id=2)
    assert [g["grupo"] for g in por_articulo["grupos"]] == ["hortaliza"]
    assert por_articulo["totales"]["bultos"] == 4


def test_rentabilidad_renglones_sin_bultos_no_aportan_nada():
    # Un renglón guardado con cantidad 0 (vino sin cantidades en el mail)
    # no mueve plata ni pesa: no aparece ni en calculables ni en afuera.
    renglones = [
        _renglon(FECHA_1, 1, "Banana", "fruta", 0),
        _renglon(FECHA_1, None, None, None, 0),
    ]
    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, {}, {})

    assert resultado["grupos"] == []
    assert resultado["no_calculables"] == []
    assert resultado["fechas_incluidas"] == []


def test_rentabilidad_renta_negativa_se_calcula_igual():
    # Vender abajo del costo no se esconde: renta en rojo, no un error.
    renglones = [_renglon(FECHA_1, 1, "Banana", "fruta", 10)]
    precios = {FECHA_1: {1: 70.0}}
    costos = {FECHA_1: {1: 80.0}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, precios, costos)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["renta_pesos"] == -2000
    assert round(fila["renta_pct"], 2) == round(-2000 / 14000 * 100, 2)


def test_rentabilidad_articulo_calculable_un_dia_y_no_el_otro_se_parte():
    # El 21 la Banana tiene precio; el 22 no. La parte calculable suma, la
    # otra queda AFUERA con su motivo — nunca promediada ni asumida.
    renglones = [
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
        _renglon(FECHA_2, 1, "Banana", "fruta", 5),
    ]
    precios = {FECHA_1: {1: 100.0}, FECHA_2: {}}
    costos = {FECHA_1: {1: 80.0}, FECHA_2: {1: 80.0}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, FICHAS, precios, costos)

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
        {"articulo_id": 9, "articulo_nombre": "Zapallo", "articulo_grupo": None, "contenido_caja": 10.0, "unidad_venta": "kilo"},
    ]
    renglones = [
        _renglon(FECHA_1, 9, "Zapallo", None, 2),
        _renglon(FECHA_1, 1, "Banana", "fruta", 10),
    ]
    precios = {FECHA_1: {1: 100.0, 9: 40.0}}
    costos = {FECHA_1: {1: 80.0, 9: 20.0}}

    resultado = calcular_rentabilidad_de_pedidos(renglones, fichas, precios, costos)

    assert [g["etiqueta"] for g in resultado["grupos"]] == ["Fruta", "Sin grupo"]
