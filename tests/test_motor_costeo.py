import pytest

from core.clientes import buscar_cliente, buscar_envase
from core.motor_costeo import (
    SIN_ENVASE,
    calcular_costo_por_presentacion,
    calcular_costo_por_unidad_medida,
    calcular_costo_ponderado_por_cubeta,
    calcular_costo_ponderado_por_cubeta_arandano,
    calcular_costo_ponderado_por_cubeta_frutilla,
    calcular_costo_ponderado_por_kg_cherry,
    calcular_costo_ponderado_por_kg_mango_cc,
    calcular_costo_ponderado_por_unidad_mango_descartable,
    calcular_costo_promedio_ponderado,
    calcular_kilo_promedio_ponderado_cajon,
    calcular_promedio_ponderado,
    calcular_utilidad_combinada_ponderada_cherry,
    costo_por_kilo,
    costo_por_kilo_base,
    precio_sugerido,
    utilidad_real,
)

CLIENTE_DIA = buscar_cliente("Día")
DESCUENTO_DIA = CLIENTE_DIA["descuento"]
UTILIDAD_DIA = CLIENTE_DIA["utilidad_objetivo"]
COSTO_ENVASE_CHICO = buscar_envase("Caja Chica Día")["costo"]
COSTO_ENVASE_GRANDE = buscar_envase("Caja Grande Día")["costo"]


def test_calcular_costo_por_unidad_medida_por_kilo():
    # Compra de mango: importe $4000, cantidad_kilos = 4 => $1000/kg
    resultado = calcular_costo_por_unidad_medida(importe=4000, cantidad=4)
    assert resultado == 1000


def test_calcular_costo_por_unidad_medida_por_fraccion():
    # Misma compra de mango, cantidad_fraccion = 10 unidades => $400/unidad
    resultado = calcular_costo_por_unidad_medida(importe=4000, cantidad=10)
    assert resultado == 400


def test_calcular_costo_por_unidad_medida_cantidad_cero_lanza_error():
    with pytest.raises(ValueError):
        calcular_costo_por_unidad_medida(importe=4000, cantidad=0)


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


def test_costo_ponderado_por_unidad_mango_descartable_cajas_de_distinto_tamano():
    # Compra 1: 2 cajas de 9 unidades a $36 => costo/unidad = 4, unidades totales = 18
    # Compra 2: 3 cajas de 10 unidades a $150 => costo/unidad = 15, unidades totales = 30
    # Compra 3: 1 caja de 12 unidades a $72 => costo/unidad = 6, unidades totales = 12
    # (4*18 + 15*30 + 6*12) / (18+30+12) = (72 + 450 + 72) / 60 = 9.9
    resultado = calcular_costo_ponderado_por_unidad_mango_descartable(
        cantidad_cajas=[2, 3, 1],
        unidades_por_caja=[9, 10, 12],
        costo_por_caja=[36, 150, 72],
    )
    assert resultado == pytest.approx(9.9)


def test_costo_ponderado_por_unidad_mango_descartable_una_sola_compra():
    resultado = calcular_costo_ponderado_por_unidad_mango_descartable(
        cantidad_cajas=[5],
        unidades_por_caja=[10],
        costo_por_caja=[100],
    )
    assert resultado == 10


def test_costo_ponderado_por_unidad_mango_descartable_longitudes_distintas():
    with pytest.raises(ValueError):
        calcular_costo_ponderado_por_unidad_mango_descartable(
            cantidad_cajas=[1, 2],
            unidades_por_caja=[9],
            costo_por_caja=[36, 40],
        )


def test_costo_ponderado_por_kg_mango_cc_varias_compras():
    # Compra 1: 2 cajas de 40 kg a $400 => costo/kg = 10, kilos totales = 80
    # Compra 2: 3 cajas de 40 kg a $360 => costo/kg = 9, kilos totales = 120
    # (10*80 + 9*120) / (80+120) = (800 + 1080) / 200 = 9.4
    resultado = calcular_costo_ponderado_por_kg_mango_cc(
        cantidad_cajas=[2, 3],
        costo_por_caja=[400, 360],
    )
    assert resultado == 9.4


def test_costo_ponderado_por_kg_mango_cc_una_sola_compra():
    resultado = calcular_costo_ponderado_por_kg_mango_cc(
        cantidad_cajas=[1],
        costo_por_caja=[400],
    )
    assert resultado == 10


def test_costo_ponderado_por_kg_mango_cc_longitudes_distintas():
    with pytest.raises(ValueError):
        calcular_costo_ponderado_por_kg_mango_cc(
            cantidad_cajas=[1, 2],
            costo_por_caja=[400],
        )


def test_costo_ponderado_por_cubeta_frutilla_valor_por_defecto():
    # Compra 1: 3 cajas de 12 cubetas a $360 => costo/cubeta = 30, cubetas totales = 36
    # Compra 2: 2 cajas de 12 cubetas a $300 => costo/cubeta = 25, cubetas totales = 24
    # (30*36 + 25*24) / (36+24) = (1080 + 600) / 60 = 28
    resultado = calcular_costo_ponderado_por_cubeta_frutilla(
        cantidad_cajas=[3, 2],
        costo_por_caja=[360, 300],
    )
    assert resultado == 28


def test_costo_ponderado_por_cubeta_frutilla_con_aviso_de_cambio():
    # Si avisan que ahora la caja trae 10 cubetas, se puede pasar el valor explícito
    resultado = calcular_costo_ponderado_por_cubeta_frutilla(
        cantidad_cajas=[1],
        costo_por_caja=[100],
        cubetas_por_caja=10,
    )
    assert resultado == 10


def test_costo_ponderado_por_cubeta_arandano_valor_por_defecto():
    # Compra 1: 4 cajas de 12 cubetas a $240 => costo/cubeta = 20, cubetas totales = 48
    # Compra 2: 1 caja de 12 cubetas a $360 => costo/cubeta = 30, cubetas totales = 12
    # (20*48 + 30*12) / (48+12) = (960 + 360) / 60 = 22
    resultado = calcular_costo_ponderado_por_cubeta_arandano(
        cantidad_cajas=[4, 1],
        costo_por_caja=[240, 360],
    )
    assert resultado == 22


def test_costo_ponderado_por_cubeta_generica_longitudes_distintas():
    with pytest.raises(ValueError):
        calcular_costo_ponderado_por_cubeta(
            cantidad_cajas=[1, 2],
            costo_por_caja=[100],
            cubetas_por_caja=12,
        )


def test_costo_por_kilo_base_sin_envase():
    # (770 + 0) / 10 = 77
    resultado = costo_por_kilo_base(costo_bulto=770, kg_bulto=10, costo_envase=SIN_ENVASE, cantidad_envases=0)
    assert resultado == 77


def test_costo_por_kilo_base_con_envase_chico():
    # (1000 + 650*1) / 10 = 165
    resultado = costo_por_kilo_base(costo_bulto=1000, kg_bulto=10, costo_envase=COSTO_ENVASE_CHICO, cantidad_envases=1)
    assert resultado == 165


def test_costo_por_kilo_base_kg_bulto_cero():
    with pytest.raises(ValueError):
        costo_por_kilo_base(costo_bulto=100, kg_bulto=0, costo_envase=SIN_ENVASE, cantidad_envases=0)


def test_costo_por_kilo_sin_envase():
    # base = 77 => 77 / (1 - 0.23) = 100
    resultado = costo_por_kilo(
        costo_bulto=770, kg_bulto=10, costo_envase=SIN_ENVASE, cantidad_envases=0, descuento=DESCUENTO_DIA
    )
    assert resultado == 100


def test_costo_por_kilo_con_envase_grande():
    # base = (5000 + 1600*1) / 20 = 330 => 330 / 0.77
    resultado = costo_por_kilo(
        costo_bulto=5000, kg_bulto=20, costo_envase=COSTO_ENVASE_GRANDE, cantidad_envases=1, descuento=DESCUENTO_DIA
    )
    assert resultado == pytest.approx(330 / 0.77)


def test_precio_sugerido_sin_envase():
    # base = 77 => 77*1.2 / 0.77 = 120
    resultado = precio_sugerido(
        costo_bulto=770,
        kg_bulto=10,
        costo_envase=SIN_ENVASE,
        cantidad_envases=0,
        descuento=DESCUENTO_DIA,
        utilidad=UTILIDAD_DIA,
    )
    assert resultado == pytest.approx(120)


def test_precio_sugerido_con_envase_chico():
    # el envase no lleva utilidad: (100*1.2 + 65) / 0.77 = 185 / 0.77
    resultado = precio_sugerido(
        costo_bulto=1000,
        kg_bulto=10,
        costo_envase=COSTO_ENVASE_CHICO,
        cantidad_envases=1,
        descuento=DESCUENTO_DIA,
        utilidad=UTILIDAD_DIA,
    )
    assert resultado == pytest.approx(185 / 0.77)


def test_utilidad_real_vendiendo_al_costo_por_kilo_da_cero():
    # Si vendo justo al costo_por_kilo, la utilidad real tiene que dar 0
    resultado = utilidad_real(
        precio_dia=100,
        kg_bulto=10,
        costo_bulto=770,
        costo_envase=SIN_ENVASE,
        cantidad_envases=0,
        descuento=DESCUENTO_DIA,
    )
    assert resultado == 0


def test_utilidad_real_costo_total_cero():
    with pytest.raises(ValueError):
        utilidad_real(
            precio_dia=100,
            kg_bulto=10,
            costo_bulto=0,
            costo_envase=SIN_ENVASE,
            cantidad_envases=0,
            descuento=DESCUENTO_DIA,
        )


def test_tomate_redondo_envase_chico():
    resultado_costo = costo_por_kilo(
        costo_bulto=28000, kg_bulto=16, costo_envase=COSTO_ENVASE_CHICO, cantidad_envases=3, descuento=DESCUENTO_DIA
    )
    resultado_precio = precio_sugerido(
        costo_bulto=28000,
        kg_bulto=16,
        costo_envase=COSTO_ENVASE_CHICO,
        cantidad_envases=3,
        descuento=DESCUENTO_DIA,
        utilidad=UTILIDAD_DIA,
    )
    resultado_utilidad = utilidad_real(
        precio_dia=4200,
        kg_bulto=16,
        costo_bulto=28000,
        costo_envase=COSTO_ENVASE_CHICO,
        cantidad_envases=3,
        descuento=DESCUENTO_DIA,
    )
    assert resultado_costo == pytest.approx(2431.01, abs=0.01)
    assert resultado_precio == pytest.approx(2885.55, abs=0.01)
    assert resultado_utilidad == pytest.approx(0.7277, abs=0.0001)


def test_mandarina_envase_grande():
    resultado_costo = costo_por_kilo(
        costo_bulto=7000, kg_bulto=17, costo_envase=COSTO_ENVASE_GRANDE, cantidad_envases=1, descuento=DESCUENTO_DIA
    )
    resultado_precio = precio_sugerido(
        costo_bulto=7000,
        kg_bulto=17,
        costo_envase=COSTO_ENVASE_GRANDE,
        cantidad_envases=1,
        descuento=DESCUENTO_DIA,
        utilidad=UTILIDAD_DIA,
    )
    resultado_utilidad = utilidad_real(
        precio_dia=900,
        kg_bulto=17,
        costo_bulto=7000,
        costo_envase=COSTO_ENVASE_GRANDE,
        cantidad_envases=1,
        descuento=DESCUENTO_DIA,
    )
    assert resultado_costo == pytest.approx(656.99, abs=0.01)
    assert resultado_precio == pytest.approx(763.94, abs=0.01)
    assert resultado_utilidad == pytest.approx(0.3699, abs=0.0001)


def test_manzana_granny_sin_envase():
    resultado_costo = costo_por_kilo(
        costo_bulto=60000, kg_bulto=18, costo_envase=SIN_ENVASE, cantidad_envases=0, descuento=DESCUENTO_DIA
    )
    resultado_precio = precio_sugerido(
        costo_bulto=60000,
        kg_bulto=18,
        costo_envase=SIN_ENVASE,
        cantidad_envases=0,
        descuento=DESCUENTO_DIA,
        utilidad=UTILIDAD_DIA,
    )
    resultado_utilidad = utilidad_real(
        precio_dia=5500,
        kg_bulto=18,
        costo_bulto=60000,
        costo_envase=SIN_ENVASE,
        cantidad_envases=0,
        descuento=DESCUENTO_DIA,
    )
    assert resultado_costo == pytest.approx(4329.00, abs=0.01)
    assert resultado_precio == pytest.approx(5194.81, abs=0.01)
    assert resultado_utilidad == pytest.approx(0.2705, abs=0.0001)
