from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from app.costeo import ARGENTINA, calcular_costo_por_unidad_venta_reciente, calcular_listado_para_negociar_precios

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


def test_calcular_costo_por_unidad_venta_funciona_con_decimal_como_devuelve_psycopg2():
    # Regresión: psycopg2 devuelve las columnas numeric como Decimal, no
    # float — con datos de prueba armados a mano con int/float esto no se
    # detectaba, pero en producción rompía con "unsupported operand
    # type(s) for +: 'float' and 'decimal.Decimal'".
    compras = [
        {
            "articulo_id": 21,
            "articulo_nombre": "Tomate Cherry",
            "cantidad_cajones": Decimal("10"),
            "contenido_por_cajon": Decimal("5"),
            "cantidad_kilos": Decimal("50"),
            "importe": Decimal("3000"),
        },
    ]
    resultado, _, _ = _calcular(compras=compras)

    # plata_total = 3000*10 = 30000; cantidad_total = 10*5 = 50; costo = 600.
    assert len(resultado["articulos"]) == 1
    assert resultado["articulos"][0]["cantidad_total"] == 50
    assert resultado["articulos"][0]["costo_por_unidad_de_venta"] == 600


def test_calcular_costo_por_unidad_venta_usa_ahora_si_no_le_pasan_momento():
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=[]) as mock_compras,
        patch("app.costeo.listar_fichas_por_cliente", return_value=[]),
    ):
        calcular_costo_por_unidad_venta_reciente(CLIENTE_ID_DE_PRUEBA)

    mock_compras.assert_called_once()
    fecha_desde, fecha_hasta = mock_compras.call_args[0]
    assert (fecha_hasta - fecha_desde).days == 2


# --- calcular_listado_para_negociar_precios ---
# "Hoy" = 2026-08-10. limite_aparicion = hoy-15 = 2026-07-26.
# limite_fresco = hoy-2 = 2026-08-08 (misma ventana de 48hs que ya usa
# calcular_costo_por_unidad_venta_reciente).

FICHAS_NEGOCIACION = [
    {"articulo_id": 1, "articulo_nombre": "Articulo A", "unidad_venta": "kilo"},
    {"articulo_id": 2, "articulo_nombre": "Articulo B", "unidad_venta": "kilo"},
    {"articulo_id": 3, "articulo_nombre": "Articulo C", "unidad_venta": "kilo"},
    {"articulo_id": 4, "articulo_nombre": "Articulo D", "unidad_venta": "kilo"},
    {"articulo_id": 5, "articulo_nombre": "Articulo E", "unidad_venta": "kilo"},
]

COMPRAS_NEGOCIACION = [
    # A: compra hoy y otra hace 4 días -> fresco, con costo anterior y variación.
    {
        "articulo_id": 1,
        "articulo_nombre": "Articulo A",
        "fecha_operacion": date(2026, 8, 10),
        "cantidad_cajones": 10,
        "contenido_por_cajon": 5,
        "cantidad_kilos": 50,
        "importe": 1000,
    },
    {
        "articulo_id": 1,
        "articulo_nombre": "Articulo A",
        "fecha_operacion": date(2026, 8, 6),
        "cantidad_cajones": 8,
        "contenido_por_cajon": 4,
        "cantidad_kilos": 32,
        "importe": 1200,
    },
    # B: compra hoy y la anterior hace 25 días -> fresco, sin costo anterior (tope 20 días).
    {
        "articulo_id": 2,
        "articulo_nombre": "Articulo B",
        "fecha_operacion": date(2026, 8, 10),
        "cantidad_cajones": 5,
        "contenido_por_cajon": 10,
        "cantidad_kilos": 50,
        "importe": 500,
    },
    {
        "articulo_id": 2,
        "articulo_nombre": "Articulo B",
        "fecha_operacion": date(2026, 7, 16),
        "cantidad_cajones": 5,
        "contenido_por_cajon": 10,
        "cantidad_kilos": 50,
        "importe": 400,
    },
    # C: compra hoy y ninguna anterior -> fresco, costo nuevo, variación None.
    {
        "articulo_id": 3,
        "articulo_nombre": "Articulo C",
        "fecha_operacion": date(2026, 8, 10),
        "cantidad_cajones": 3,
        "contenido_por_cajon": 6,
        "cantidad_kilos": 18,
        "importe": 900,
    },
    # D: última compra hace 6 días (fuera de 48hs, dentro de 15) -> no fresco.
    # Tiene una compra más vieja (hace 26 días) que NO debería usarse porque,
    # al no ser fresco, no se busca costo anterior.
    {
        "articulo_id": 4,
        "articulo_nombre": "Articulo D",
        "fecha_operacion": date(2026, 8, 4),
        "cantidad_cajones": 4,
        "contenido_por_cajon": 5,
        "cantidad_kilos": 20,
        "importe": 800,
    },
    {
        "articulo_id": 4,
        "articulo_nombre": "Articulo D",
        "fecha_operacion": date(2026, 7, 15),
        "cantidad_cajones": 4,
        "contenido_por_cajon": 5,
        "cantidad_kilos": 20,
        "importe": 600,
    },
    # E: última compra hace 20 días -> no debería aparecer en absoluto.
    {
        "articulo_id": 5,
        "articulo_nombre": "Articulo E",
        "fecha_operacion": date(2026, 7, 21),
        "cantidad_cajones": 2,
        "contenido_por_cajon": 3,
        "cantidad_kilos": 6,
        "importe": 300,
    },
]

PRECIOS_VIGENTES_NEGOCIACION = [
    {"articulo_id": 1, "precio": 250},
]


def _calcular_negociacion(
    momento=MOMENTO_DE_PRUEBA,
    compras=COMPRAS_NEGOCIACION,
    fichas=FICHAS_NEGOCIACION,
    precios_vigentes=PRECIOS_VIGENTES_NEGOCIACION,
):
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=compras) as mock_compras,
        patch("app.costeo.listar_fichas_por_cliente", return_value=fichas),
        patch("app.costeo.listar_precios_vigentes_por_cliente", return_value=precios_vigentes) as mock_vigentes,
    ):
        resultado = calcular_listado_para_negociar_precios(CLIENTE_ID_DE_PRUEBA, momento)
    return resultado, mock_compras, mock_vigentes


def test_negociacion_articulo_fresco_con_costo_anterior_y_variacion():
    resultado, _, _ = _calcular_negociacion()
    por_id = {a["articulo_id"]: a for a in resultado}

    # A: costo_actual = 1000*10/(10*5) = 200; costo_anterior = 1200*8/(8*4) = 300 -> bajó.
    a = por_id[1]
    assert a["fresco"] is True
    assert a["costo_actual"] == 200
    assert a["costo_anterior"] == 300
    assert a["variacion"] == "bajo"
    assert a["fecha_ultima_compra"] == date(2026, 8, 10)
    assert a["precio_vigente"] == 250


def test_negociacion_costo_anterior_se_descarta_a_mas_de_20_dias():
    resultado, _, _ = _calcular_negociacion()
    por_id = {a["articulo_id"]: a for a in resultado}

    b = por_id[2]
    assert b["fresco"] is True
    assert b["costo_actual"] == 50  # 500*5/(5*10)
    assert b["costo_anterior"] is None
    assert b["variacion"] is None
    assert b["precio_vigente"] is None


def test_negociacion_articulo_nuevo_sin_compra_anterior():
    resultado, _, _ = _calcular_negociacion()
    por_id = {a["articulo_id"]: a for a in resultado}

    c = por_id[3]
    assert c["fresco"] is True
    assert c["costo_actual"] == 150  # 900*3/(3*6)
    assert c["costo_anterior"] is None
    assert c["variacion"] is None


def test_negociacion_articulo_no_fresco_no_calcula_costo_anterior():
    resultado, _, _ = _calcular_negociacion()
    por_id = {a["articulo_id"]: a for a in resultado}

    d = por_id[4]
    assert d["fresco"] is False
    assert d["costo_actual"] == 160  # 800*4/(4*5)
    assert d["costo_anterior"] is None
    assert d["variacion"] is None
    assert d["fecha_ultima_compra"] == date(2026, 8, 4)


def test_negociacion_articulo_sin_compra_reciente_no_aparece():
    resultado, _, _ = _calcular_negociacion()
    ids = {a["articulo_id"] for a in resultado}

    assert 5 not in ids


def test_negociacion_ordena_frescos_primero():
    resultado, _, _ = _calcular_negociacion()

    frescos = [a["fresco"] for a in resultado]
    # Todos los frescos (True) antes que los viejos (False).
    assert frescos == sorted(frescos, key=lambda f: not f)


def test_negociacion_llama_precios_vigentes_con_fecha_de_hoy():
    _, _, mock_vigentes = _calcular_negociacion()

    mock_vigentes.assert_called_once_with(CLIENTE_ID_DE_PRUEBA, date(2026, 8, 10))


def test_negociacion_sin_fichas_devuelve_lista_vacia():
    resultado, _, _ = _calcular_negociacion(fichas=[])

    assert resultado == []
