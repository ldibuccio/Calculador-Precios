import pytest

from core.motor_costeo import calcular_promedio_ponderado


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
