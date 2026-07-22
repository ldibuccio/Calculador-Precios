import pytest

from core.motor_costeo import (
    calcular_costo_promedio_ponderado,
    calcular_kilo_promedio_ponderado_cajon,
    calcular_promedio_ponderado,
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
