from datetime import datetime
from unittest.mock import patch

from app.costeo import ARGENTINA, calcular_costo_por_unidad_venta_reciente

MOMENTO_DE_PRUEBA = datetime(2026, 8, 10, 12, 0, tzinfo=ARGENTINA)
CLIENTE_ID_DE_PRUEBA = 1

# Cherry (articulo_id 21) y Mango (22) tienen ficha para este cliente.
# Morrón Rojo (29) NO tiene ficha — a propósito, para probar "sin ficha".
FICHAS_DE_PRUEBA = [
    {"articulo_id": 21, "articulo_nombre": "Tomate Cherry", "unidad_venta": "kilo"},
    {"articulo_id": 22, "articulo_nombre": "Mango", "unidad_venta": "unidad"},
]

COMPRAS_DE_PRUEBA = [
    # Cherry: 2 compras con distinto contenido_por_cajon (5kg y 8kg) y
    # distinto precio por cajón, más 1 sin precio.
    {
        "articulo_id": 21,
        "articulo_nombre": "Tomate Cherry",
        "cantidad_cajones": 10,
        "contenido_por_cajon": 5,
        "cantidad_kilos": 50,
        "importe": 3000,
    },
    {
        "articulo_id": 21,
        "articulo_nombre": "Tomate Cherry",
        "cantidad_cajones": 4,
        "contenido_por_cajon": 8,
        "cantidad_kilos": 32,
        "importe": 4000,
    },
    {
        "articulo_id": 21,
        "articulo_nombre": "Tomate Cherry",
        "cantidad_cajones": 2,
        "contenido_por_cajon": 6,
        "cantidad_kilos": 12,
        "importe": None,
    },
    # Mango: una sola compra por unidad.
    {
        "articulo_id": 22,
        "articulo_nombre": "Mango",
        "cantidad_cajones": 3,
        "contenido_por_cajon": 10,
        "cantidad_kilos": None,
        "importe": 4000,
    },
    # Morrón Rojo: tiene compra con precio, pero SIN ficha para este cliente.
    {
        "articulo_id": 29,
        "articulo_nombre": "Morrón Rojo",
        "cantidad_cajones": 40,
        "contenido_por_cajon": 8,
        "cantidad_kilos": 320,
        "importe": 27000,
    },
    # Palta: todas sus compras están sin precio, no debería aparecer en ningún lado.
    {
        "articulo_id": 23,
        "articulo_nombre": "Palta",
        "cantidad_cajones": 6,
        "contenido_por_cajon": 50,
        "cantidad_kilos": None,
        "importe": None,
    },
]


def _calcular(momento=MOMENTO_DE_PRUEBA, compras=COMPRAS_DE_PRUEBA, fichas=FICHAS_DE_PRUEBA):
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=compras) as mock_compras,
        patch("app.costeo.listar_fichas_por_cliente", return_value=fichas) as mock_fichas,
    ):
        resultado = calcular_costo_por_unidad_venta_reciente(CLIENTE_ID_DE_PRUEBA, momento)
    return resultado, mock_compras, mock_fichas


def test_calcular_costo_por_unidad_venta_pondera_por_cantidad_real_no_por_cajones():
    resultado, mock_compras, mock_fichas = _calcular()

    mock_compras.assert_called_once_with(datetime(2026, 8, 8).date(), datetime(2026, 8, 10).date())
    mock_fichas.assert_called_once_with(CLIENTE_ID_DE_PRUEBA)

    articulos_por_id = {a["articulo_id"]: a for a in resultado["articulos"]}

    # Cherry: plata_total = 3000*10 + 4000*4 = 46000
    #         cantidad_total = 10*5 + 4*8 = 82 kg
    #         costo_por_kilo = 46000 / 82 = 560.9756...
    # (Si el cálculo ponderara por cantidad de CAJONES en vez de por kilos
    # reales, daría (3000*10+4000*4)/(10+4) = 3285.71, bien distinto — esto
    # confirma que se está ponderando por la cantidad real.)
    cherry = articulos_por_id[21]
    assert cherry["articulo_nombre"] == "Tomate Cherry"
    assert cherry["unidad_venta"] == "kilo"
    assert cherry["cantidad_total"] == 82
    assert round(cherry["costo_por_unidad_de_venta"], 2) == 560.98
    assert cherry["compras_sin_precio_excluidas"] == 1

    # Mango: una sola compra, 3 cajones de 10 unidades a $4000 el cajón.
    # cantidad_total = 3*10 = 30 unidades; plata_total = 4000*3 = 12000
    # costo_por_unidad = 12000/30 = 400.
    mango = articulos_por_id[22]
    assert mango["unidad_venta"] == "unidad"
    assert mango["cantidad_total"] == 30
    assert mango["costo_por_unidad_de_venta"] == 400
    assert mango["compras_sin_precio_excluidas"] == 0

    # Palta: sin ninguna compra con precio, no aparece en ningún lado.
    ids_costeados = {a["articulo_id"] for a in resultado["articulos"]}
    ids_sin_ficha = {a["articulo_id"] for a in resultado["articulos_sin_ficha"]}
    assert 23 not in ids_costeados
    assert 23 not in ids_sin_ficha


def test_calcular_costo_por_unidad_venta_articulo_sin_ficha_no_se_costea():
    resultado, _, _ = _calcular()

    ids_costeados = {a["articulo_id"] for a in resultado["articulos"]}
    assert 29 not in ids_costeados

    sin_ficha = {a["articulo_id"]: a for a in resultado["articulos_sin_ficha"]}
    assert 29 in sin_ficha
    assert sin_ficha[29]["articulo_nombre"] == "Morrón Rojo"


def test_calcular_costo_por_unidad_venta_sin_compras_devuelve_listas_vacias():
    resultado, _, _ = _calcular(compras=[])

    assert resultado == {"articulos": [], "articulos_sin_ficha": []}


def test_calcular_costo_por_unidad_venta_usa_ahora_si_no_le_pasan_momento():
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=[]) as mock_compras,
        patch("app.costeo.listar_fichas_por_cliente", return_value=[]),
    ):
        calcular_costo_por_unidad_venta_reciente(CLIENTE_ID_DE_PRUEBA)

    mock_compras.assert_called_once()
    fecha_desde, fecha_hasta = mock_compras.call_args[0]
    assert (fecha_hasta - fecha_desde).days == 2
