"""Tests del reparto FIFO del stock del depósito (core/stock.py) — puro, sin base."""

from core.stock import repartir_fifo


def _lote(orden, cantidad, **extra):
    return dict({"orden": orden, "cantidad": cantidad}, **extra)


def test_fifo_consume_del_lote_mas_viejo_primero():
    entradas = [_lote(2, 10, nombre="nueva"), _lote(1, 8, nombre="vieja")]
    reparto = repartir_fifo(entradas, [{"orden": 3, "cantidad": 5}])

    # Se ordena por fecha aunque las entradas vengan desordenadas.
    assert [l["nombre"] for l in reparto["lotes"]] == ["vieja", "nueva"]
    assert reparto["lotes"][0]["restante"] == 3
    assert reparto["lotes"][0]["consumido"] == 5
    assert reparto["lotes"][1]["restante"] == 10
    assert reparto["sin_lote"] == 0
    assert reparto["stock"] == 13


def test_fifo_una_salida_grande_cruza_varios_lotes():
    entradas = [_lote(1, 8), _lote(2, 10), _lote(3, 4)]
    reparto = repartir_fifo(entradas, [{"orden": 9, "cantidad": 15}])

    assert [l["restante"] for l in reparto["lotes"]] == [0, 3, 4]
    assert reparto["sin_lote"] == 0
    assert reparto["stock"] == 7


def test_fifo_salidas_de_mas_quedan_sin_lote_y_el_stock_negativo():
    # El armado nunca se traba por stock: el excedente NO se cuelga de
    # ninguna guía — queda como "sin lote" y el stock en negativo, que es
    # la señal de que falta un reproceso o un ajuste.
    entradas = [_lote(1, 8)]
    reparto = repartir_fifo(entradas, [{"orden": 2, "cantidad": 5}, {"orden": 3, "cantidad": 7}])

    assert reparto["lotes"][0]["restante"] == 0
    assert reparto["sin_lote"] == 4
    assert reparto["stock"] == -4


def test_fifo_sin_entradas_todo_queda_sin_lote():
    reparto = repartir_fifo([], [{"orden": 1, "cantidad": 6}])

    assert reparto["lotes"] == []
    assert reparto["sin_lote"] == 6
    assert reparto["stock"] == -6


def test_fifo_sin_salidas_no_toca_nada():
    reparto = repartir_fifo([_lote(1, 8)], [])

    assert reparto["lotes"][0]["restante"] == 8
    assert reparto["lotes"][0]["consumido"] == 0
    assert reparto["sin_lote"] == 0
    assert reparto["stock"] == 8


def test_fifo_un_reingreso_con_fecha_vieja_se_ordena_por_su_fecha_real():
    # El camión del rechazo volvió el 22 y se cargó el 23: la fecha de
    # operación (22) es la que ordena — por eso el orden es una tupla
    # (fecha del hecho, momento de carga) y no el momento de carga solo.
    from datetime import date, datetime

    entradas = [
        _lote((date(2026, 8, 23), datetime(2026, 8, 23, 10)), 10, nombre="guia_23"),
        _lote((date(2026, 8, 22), datetime(2026, 8, 23, 15)), 3, nombre="reingreso_del_22"),
    ]
    reparto = repartir_fifo(entradas, [{"orden": 0, "cantidad": 3}])

    assert [l["nombre"] for l in reparto["lotes"]] == ["reingreso_del_22", "guia_23"]
    assert reparto["lotes"][0]["restante"] == 0
    assert reparto["lotes"][1]["restante"] == 10


def test_fifo_redondea_a_dos_decimales():
    reparto = repartir_fifo([_lote(1, 0.1), _lote(2, 0.2)], [{"orden": 3, "cantidad": 0.4}])

    assert reparto["sin_lote"] == 0.1
    assert reparto["stock"] == -0.1
