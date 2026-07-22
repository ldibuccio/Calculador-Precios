import pytest

from core.motor_costeo import (
    calcular_costo_por_presentacion,
    calcular_costo_ponderado_por_kg_cherry,
    calcular_costo_promedio_ponderado,
    calcular_kilo_promedio_ponderado_cajon,
    calcular_promedio_ponderado,
    calcular_utilidad_combinada_ponderada_cherry,
)


def test_promedio_ponderado_pesos_iguales():
    resultado = calcular_promedio_ponderado([10, 20], [1, 1])
    assert resultado == 15


def test_promedio_ponderado_pesos_distintos():
    # 3 kg a $10 + 1 kg a $20 => (30 + 20) / 4 = 12.5
    resultado = calcular_promedio_ponderado([10, 20], [3, 1])
    assert resultado == 12.5


def test_promedio_ponderado_listas_de_distinta_longitud():
    with pytest.raises(ValueError):
        calcular_promedio_ponderado([10, 20], [1])


def test_promedio_ponderado_cantidades_en_cero():
    with pytest.raises(ValueError):
        calcular_promedio_ponderado([10, 20], [0, 0])


def test_costo_promedio_ponderado_varios_proveedores():
    # Proveedor A: 100 kg a $50 | Proveedor B: 50 kg a $65
    # (100*50 + 50*65) / 150 = (5000 + 3250) / 150 = 55
    resultado = calcular_costo_promedio_ponderado([100, 50], [50, 65])
    assert resultado == 55


def test_costo_promedio_ponderado_una_sola_compra():
    resultado = calcular_costo_promedio_ponderado([20], [40])
    assert resultado == 40


def test_kilo_promedio_ponderado_cajones_de_distinto_peso():
    # 5 cajones de 10 kg, 3 cajones de 12 kg, 2 cajones de 13 kg
    # (5*10 + 3*12 + 2*13) / (5+3+2) = (50 + 36 + 26) / 10 = 11.2
    resultado = calcular_kilo_promedio_ponderado_cajon([5, 3, 2], [10, 12, 13])
    assert resultado == 11.2


def test_kilo_promedio_ponderado_cajones_del_mismo_peso():
    resultado = calcular_kilo_promedio_ponderado_cajon([4, 6], [10, 10])
    assert resultado == 10


def test_costo_ponderado_por_kg_cherry_cajones_de_distinto_peso():
    # Compra 1: 2 cajones de 10 kg a $100 => costo/kg = 10, kilos totales = 20
    # Compra 2: 2 cajones de 5 kg a $20 => costo/kg = 4, kilos totales = 10
    # (10*20 + 4*10) / (20+10) = (200 + 40) / 30 = 8
    resultado = calcular_costo_ponderado_por_kg_cherry(
        cantidad_cajones=[2, 2],
        kg_por_cajon=[10, 5],
        precio_por_cajon=[100, 20],
    )
    assert resultado == 8


def test_costo_ponderado_por_kg_cherry_tres_tamanos_de_cajon():
    # Compra 1: 3 cajones de 5 kg a $30 => costo/kg = 6, kilos totales = 15
    # Compra 2: 2 cajones de 10 kg a $90 => costo/kg = 9, kilos totales = 20
    # Compra 3: 1 cajón de 14 kg a $84 => costo/kg = 6, kilos totales = 14
    # (6*15 + 9*20 + 6*14) / (15+20+14) = (90 + 180 + 84) / 49 = 354/49
    resultado = calcular_costo_ponderado_por_kg_cherry(
        cantidad_cajones=[3, 2, 1],
        kg_por_cajon=[5, 10, 14],
        precio_por_cajon=[30, 90, 84],
    )
    assert resultado == pytest.approx(354 / 49)


def test_costo_ponderado_por_kg_cherry_longitudes_distintas():
    with pytest.raises(ValueError):
        calcular_costo_ponderado_por_kg_cherry(
            cantidad_cajones=[1, 2],
            kg_por_cajon=[5],
            precio_por_cajon=[30, 60],
        )


def test_costo_por_presentacion():
    costo_por_kg = 8
    assert calcular_costo_por_presentacion(costo_por_kg, 5) == 40
    assert calcular_costo_por_presentacion(costo_por_kg, 10) == 80


def test_utilidad_combinada_ponderada_cherry():
    # Presentación de 5 kg: utilidad $1000 por los 15 kg comprados de esa presentación
    # Presentación de 10 kg: utilidad $1200 por los 35 kg comprados de esa presentación
    # (1000*15 + 1200*35) / (15+35) = (15000 + 42000) / 50 = 1140
    resultado = calcular_utilidad_combinada_ponderada_cherry([1000, 1200], [15, 35])
    assert resultado == 1140
