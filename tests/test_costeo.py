from datetime import datetime
from unittest.mock import patch

from app.costeo import ARGENTINA, calcular_costos_ponderados_recientes

MOMENTO_DE_PRUEBA = datetime(2026, 8, 10, 12, 0, tzinfo=ARGENTINA)

COMPRAS_DE_PRUEBA = [
    # Mzn Red: 2 compras con precio (importe = precio por cajón: $500 y $600) + 1 sin precio.
    {
        "articulo_id": 5,
        "articulo_nombre": "Mzn Red",
        "cantidad_cajones": 10,
        "contenido_por_cajon": 18,
        "cantidad_kilos": 180,
        "importe": 500,
    },
    {
        "articulo_id": 5,
        "articulo_nombre": "Mzn Red",
        "cantidad_cajones": 5,
        "contenido_por_cajon": 18,
        "cantidad_kilos": 90,
        "importe": 600,
    },
    {
        "articulo_id": 5,
        "articulo_nombre": "Mzn Red",
        "cantidad_cajones": 3,
        "contenido_por_cajon": 18,
        "cantidad_kilos": 54,
        "importe": None,
    },
    # Kiwi: una sola compra con precio.
    {
        "articulo_id": 35,
        "articulo_nombre": "Kiwi",
        "cantidad_cajones": 4,
        "contenido_por_cajon": 10,
        "cantidad_kilos": 40,
        "importe": 500,
    },
    # Palta: todas sus compras están sin precio, no debería aparecer en el resultado.
    {
        "articulo_id": 23,
        "articulo_nombre": "Palta",
        "cantidad_cajones": 6,
        "contenido_por_cajon": 50,
        "cantidad_kilos": None,
        "importe": None,
    },
]


def test_calcular_costos_ponderados_recientes_pondera_por_cajones():
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=COMPRAS_DE_PRUEBA) as mock_listar,
    ):
        resultado = calcular_costos_ponderados_recientes(MOMENTO_DE_PRUEBA)

    mock_listar.assert_called_once_with(datetime(2026, 8, 8).date(), datetime(2026, 8, 10).date())

    resultado_por_articulo = {fila["articulo_id"]: fila for fila in resultado}

    # Mzn Red: (500*10 + 600*5) / (10+5) = 8000/15 = 533.33...
    mzn_red = resultado_por_articulo[5]
    assert mzn_red["articulo_nombre"] == "Mzn Red"
    assert mzn_red["cantidad_cajones_total"] == 15
    assert round(mzn_red["costo_ponderado"], 2) == 533.33
    assert mzn_red["compras_sin_precio_excluidas"] == 1

    # Kiwi: una sola compra de 4 cajones a $500 el cajón => costo ponderado = 500
    # (NO 500/4 = 125: importe ya es el precio de un cajón, no el total).
    kiwi = resultado_por_articulo[35]
    assert kiwi["cantidad_cajones_total"] == 4
    assert kiwi["costo_ponderado"] == 500
    assert kiwi["compras_sin_precio_excluidas"] == 0


def test_calcular_costos_ponderados_recientes_importe_es_precio_por_cajon_no_total():
    # Regresión: caso real que detectó el bug. Morrón Rojo, una compra de 40
    # cajones a $27.000 el cajón. compras.importe YA es el precio de UN
    # cajón (no el total de la compra) — el costo ponderado tiene que dar
    # 27000, no 27000/40 = 675.
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "cantidad_cajones": 40,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 320,
            "importe": 27000,
        },
    ]
    with patch("app.costeo.listar_compras_para_costeo", return_value=compras):
        resultado = calcular_costos_ponderados_recientes(MOMENTO_DE_PRUEBA)

    assert len(resultado) == 1
    assert resultado[0]["articulo_nombre"] == "Morrón Rojo"
    assert resultado[0]["cantidad_cajones_total"] == 40
    assert resultado[0]["costo_ponderado"] == 27000


def test_calcular_costos_ponderados_recientes_excluye_articulo_sin_ninguna_compra_con_precio():
    with patch("app.costeo.listar_compras_para_costeo", return_value=COMPRAS_DE_PRUEBA):
        resultado = calcular_costos_ponderados_recientes(MOMENTO_DE_PRUEBA)

    ids_en_resultado = {fila["articulo_id"] for fila in resultado}
    assert 23 not in ids_en_resultado


def test_calcular_costos_ponderados_recientes_sin_compras_devuelve_lista_vacia():
    with patch("app.costeo.listar_compras_para_costeo", return_value=[]):
        resultado = calcular_costos_ponderados_recientes(MOMENTO_DE_PRUEBA)

    assert resultado == []


def test_calcular_costos_ponderados_recientes_usa_ahora_si_no_le_pasan_momento():
    with patch("app.costeo.listar_compras_para_costeo", return_value=[]) as mock_listar:
        calcular_costos_ponderados_recientes()

    mock_listar.assert_called_once()
    fecha_desde, fecha_hasta = mock_listar.call_args[0]
    assert (fecha_hasta - fecha_desde).days == 2
