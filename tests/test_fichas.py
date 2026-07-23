import pytest

from core.fichas import (
    TIPO_ENVASE_CAJA_CHICA,
    TIPO_ENVASE_CAJA_GRANDE,
    TIPO_ENVASE_PERDIDO,
    UNIDAD_VENTA_CUBETA,
    UNIDAD_VENTA_KILO,
    UNIDAD_VENTA_UNIDAD,
    buscar_ficha,
    calcular_cantidad_cajas,
    calcular_palets,
)
from core.motor_costeo import COSTO_ENVASE_CHICO, COSTO_ENVASE_GRANDE, SIN_ENVASE


def test_buscar_ficha_envase_perdido_por_kilo():
    ficha = buscar_ficha("Sandía")
    assert ficha["tipo_envase"] == TIPO_ENVASE_PERDIDO
    assert ficha["unidad_venta"] == UNIDAD_VENTA_KILO
    assert ficha["costo_envase"] == SIN_ENVASE
    assert "contenido_caja" not in ficha


def test_buscar_ficha_envase_perdido_por_cubeta():
    for nombre in ("Frutilla", "Arándano"):
        ficha = buscar_ficha(nombre)
        assert ficha["tipo_envase"] == TIPO_ENVASE_PERDIDO
        assert ficha["unidad_venta"] == UNIDAD_VENTA_CUBETA
        assert ficha["cubetas_por_caja"] == 12


def test_buscar_ficha_caja_chica():
    ficha = buscar_ficha("Zapallito")
    assert ficha["tipo_envase"] == TIPO_ENVASE_CAJA_CHICA
    assert ficha["unidad_venta"] == UNIDAD_VENTA_KILO
    assert ficha["costo_envase"] == COSTO_ENVASE_CHICO
    assert ficha["contenido_caja"] == 6


def test_buscar_ficha_caja_grande():
    ficha = buscar_ficha("Morrón Rojo")
    assert ficha["tipo_envase"] == TIPO_ENVASE_CAJA_GRANDE
    assert ficha["unidad_venta"] == UNIDAD_VENTA_KILO
    assert ficha["costo_envase"] == COSTO_ENVASE_GRANDE
    assert ficha["contenido_caja"] == 8


def test_buscar_ficha_mango_incluye_datos_de_palet():
    ficha = buscar_ficha("Mango")
    assert ficha["unidad_venta"] == UNIDAD_VENTA_UNIDAD
    assert ficha["contenido_caja"] == 10
    assert ficha["datos_palet"] == {"unidades_por_cajon": 40, "kg_por_cajon": 16}


def test_buscar_ficha_palta_incluye_datos_de_palet():
    ficha = buscar_ficha("Palta")
    assert ficha["unidad_venta"] == UNIDAD_VENTA_UNIDAD
    assert ficha["contenido_caja"] == 50
    assert ficha["datos_palet"] == {"unidades_por_cajon": 80, "kg_por_cajon": 10}


def test_buscar_ficha_articulo_inexistente_lanza_error():
    with pytest.raises(ValueError):
        buscar_ficha("Articulo que no existe")


def test_calcular_cantidad_cajas_ejemplo_zapallito():
    # 20 kg de zapallito / 6 = 3.33..., sin redondear
    resultado = calcular_cantidad_cajas(20, buscar_ficha("Zapallito")["contenido_caja"])
    assert resultado == pytest.approx(20 / 6)


def test_calcular_cantidad_cajas_division_exacta():
    resultado = calcular_cantidad_cajas(18, buscar_ficha("Morrón Verde")["contenido_caja"])
    assert resultado == 4.5


def test_calcular_cantidad_cajas_contenido_caja_cero_lanza_error():
    with pytest.raises(ValueError):
        calcular_cantidad_cajas(20, 0)


def test_calcular_palets_redondea_siempre_hacia_arriba():
    # 960 kg / 800 = 1.2 => se pagan 2 palets
    assert calcular_palets(960) == 2


def test_calcular_palets_division_exacta_no_redondea_de_mas():
    assert calcular_palets(800) == 1
    assert calcular_palets(1600) == 2


def test_calcular_palets_con_kg_por_palet_personalizado():
    assert calcular_palets(100, kg_por_palet=50) == 2
    assert calcular_palets(101, kg_por_palet=50) == 3


def test_calcular_palets_kg_por_palet_cero_lanza_error():
    with pytest.raises(ValueError):
        calcular_palets(100, kg_por_palet=0)


def test_palets_de_mango_usando_datos_de_la_ficha():
    # Se compran 200 unidades de mango; la ficha dice 40 unidades = 16 kg por cajón
    datos_palet = buscar_ficha("Mango")["datos_palet"]
    cajones_comprados = 200 / datos_palet["unidades_por_cajon"]
    kg_totales = cajones_comprados * datos_palet["kg_por_cajon"]
    assert calcular_palets(kg_totales) == 1
