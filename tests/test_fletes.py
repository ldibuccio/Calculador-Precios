"""Fletes (dueño, 05/10): el motor puro de core/fletes.py. Nombres de EJEMPLO."""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.fletes import armar_flete, repartir, texto_whatsapp  # noqa: E402


def _camion(id_, pallets, cantidad, precio, nombre=None):
    return {"id": id_, "nombre": nombre or f"EJ {id_}", "pallets": pallets, "cantidad": cantidad, "precio": precio}


def test_la_FLOTA_se_reparte_entre_las_sucursales_A_LA_VEZ():
    """De a una, la primera se queda con el Grande (le sale más barato) y la
    segunda se queda sin camión que le alcance. Juntas, alcanza."""
    camiones = [_camion(1, 12, 1, 60000), _camion(2, 8, 1, 70000)]
    p = armar_flete([{"codigo": "BZ", "pallets": 8}, {"codigo": "VL", "pallets": 12}], camiones)
    assert p["alcanza"] and p["asignacion"] == {"BZ": {2: 1}, "VL": {1: 1}}
    assert p["costo"] == Decimal("130000")


def test_lo_mas_barato_en_TOTAL_aunque_tenga_mas_camiones():
    camiones = [_camion(1, 10, 5, 100000), _camion(2, 4, 5, 30000)]
    p = armar_flete([{"codigo": "VL", "pallets": 10}], camiones)
    assert p["asignacion"] == {"VL": {2: 3}} and p["costo"] == Decimal("90000")


def test_no_propone_camiones_DE_MAS():
    camiones = [_camion(1, 10, 5, 100000), _camion(2, 4, 5, 300000)]
    assert armar_flete([{"codigo": "VL", "pallets": 9}], camiones)["asignacion"] == {"VL": {1: 1}}


def test_SIN_FLOTA_que_alcance_ni_sin_tope_devuelve_vacio_y_lo_dice():
    p = armar_flete([{"codigo": "VL", "pallets": 9}], [_camion(1, 10, 0, None, "Grande")])
    assert p["alcanza"] is False and p["asignacion"] == {} and p["sin_precio"] == ["Grande"]


def test_REPARTO_por_pallets_suma_el_precio_al_centavo():
    assert repartir(100, 1, 2) == (Decimal("33.33"), Decimal("66.67"))
    assert sum(repartir(Decimal("99999.99"), 7, 3)) == Decimal("99999.99")
    assert repartir(5000, 3, 0) == (Decimal("5000.00"), Decimal("0.00"))
    assert repartir(5000, 0, 3) == (Decimal("0.00"), Decimal("5000.00"))
    with pytest.raises(ValueError):
        repartir(5000, 0, 0)


def test_el_MENSAJE_de_WhatsApp_es_el_del_duenio():
    texto = texto_whatsapp("Juan", date(2026, 10, 6), [
        {"nombre": "Vicente López", "pallets": 18, "camiones": [("Grande", 1), ("Mediano", 1)]},
        {"nombre": "Burzaco", "pallets": 8, "camiones": [("Mediano", 1), ("Chico", 0)]}])
    assert texto == ("Hola Juan, para el martes 06/10 necesito: Vicente López: 1 Grande + 1 Mediano "
                     "(18 pallets). Burzaco: 1 Mediano (8 pallets). Gracias.")
