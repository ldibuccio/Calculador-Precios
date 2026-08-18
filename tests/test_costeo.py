from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.costeo import (
    ARGENTINA,
    _envases_por_unidad_ponderado,
    agrupar_para_negociar,
    calcular_costo_por_unidad_venta_reciente,
    calcular_listado_para_negociar_precios,
    calcular_precio_sugerido_desglosado,
)

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

# Sin envase compartido (envase_id None): estos artículos no ejercitan el
# cálculo de precio_sugerido con envase, solo que no rompa (queda en None
# si falta descuento/utilidad, o se calcula sin costo de envase).
FICHAS_NEGOCIACION = [
    {
        "articulo_id": 1,
        "articulo_nombre": "Articulo A",
        "unidad_venta": "kilo",
        "envase_id": None,
        "contenido_caja": None,
        "envase_variable": False,
    },
    {
        "articulo_id": 2,
        "articulo_nombre": "Articulo B",
        "unidad_venta": "kilo",
        "envase_id": None,
        "contenido_caja": None,
        "envase_variable": False,
    },
    {
        "articulo_id": 3,
        "articulo_nombre": "Articulo C",
        "unidad_venta": "kilo",
        "envase_id": None,
        "contenido_caja": None,
        "envase_variable": False,
    },
    {
        "articulo_id": 4,
        "articulo_nombre": "Articulo D",
        "unidad_venta": "kilo",
        "envase_id": None,
        "contenido_caja": None,
        "envase_variable": False,
    },
    {
        "articulo_id": 5,
        "articulo_nombre": "Articulo E",
        "unidad_venta": "kilo",
        "envase_id": None,
        "contenido_caja": None,
        "envase_variable": False,
    },
]

# Día hoy: un solo concepto que resta (descuento 0.23) y la utilidad (0.20),
# sin ninguna tasa que sume — mismo caso que antes de abrir la lista de
# conceptos. listar_conceptos_vigentes_por_cliente ya devuelve fracciones
# (0.23), no porcentaje (a diferencia de la vieja obtener_cliente).
CONCEPTOS_NEGOCIACION = {"tasas_suman": [], "tasas_restan": [0.23], "utilidad": 0.20}

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
    conceptos=CONCEPTOS_NEGOCIACION,
    costos_envases=(),
):
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=compras) as mock_compras,
        patch("app.costeo.listar_fichas_por_cliente", return_value=fichas),
        patch("app.costeo.listar_precios_vigentes_por_cliente", return_value=precios_vigentes) as mock_vigentes,
        patch("app.costeo.listar_conceptos_vigentes_por_cliente", return_value=conceptos),
        patch("app.costeo.listar_costos_envases_vigentes", return_value=list(costos_envases)),
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


def test_negociacion_expone_costo_total_y_denominador_para_simulacion():
    # Sin envase (envase_id None): costo_total_unidad_venta = costo_actual.
    # Denominador = 1 - 0.23 (una sola tasa que resta, ninguna que suma) —
    # igual para TODOS los artículos del cliente, no solo para A.
    resultado, _, _ = _calcular_negociacion()
    por_id = {a["articulo_id"]: a for a in resultado}

    a = por_id[1]
    assert a["costo_total_unidad_venta"] == 200
    assert a["denominador_tasas"] == pytest.approx(0.77)

    b = por_id[2]
    assert b["costo_total_unidad_venta"] == 50
    assert b["denominador_tasas"] == pytest.approx(0.77)


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


# --- _envases_por_unidad_ponderado: decisión descartable vs. caja chica ---

def test_envases_ponderado_envase_fijo_siempre_uno_cada_contenido_de_ficha():
    compras = [{"importe": 100, "cantidad_cajones": 5, "contenido_por_cajon": 8}]
    resultado = _envases_por_unidad_ponderado(compras, contenido_ficha=8, envase_variable=False)
    assert resultado == pytest.approx(1 / 8)


def test_envases_ponderado_cherry_cajon_5kg_ficha_5kg_es_descartable():
    compras = [{"importe": 100, "cantidad_cajones": 10, "contenido_por_cajon": 5}]
    resultado = _envases_por_unidad_ponderado(compras, contenido_ficha=5, envase_variable=True)
    assert resultado == 0.0


def test_envases_ponderado_cherry_cajon_10kg_ficha_5kg_es_caja_chica_dos_cartones():
    # Cajón de 10kg, ficha 5kg -> 2 cartones por cajón -> 1 cartón cada 5kg.
    compras = [{"importe": 100, "cantidad_cajones": 4, "contenido_por_cajon": 10}]
    resultado = _envases_por_unidad_ponderado(compras, contenido_ficha=5, envase_variable=True)
    assert resultado == pytest.approx(1 / 5)
    # 40 kg comprados (4 cajones de 10kg) -> 8 cartones en total.
    assert resultado * (4 * 10) == pytest.approx(8)


def test_envases_ponderado_mango_cajon_10u_ficha_10u_es_descartable():
    compras = [{"importe": 100, "cantidad_cajones": 3, "contenido_por_cajon": 10}]
    resultado = _envases_por_unidad_ponderado(compras, contenido_ficha=10, envase_variable=True)
    assert resultado == 0.0


def test_envases_ponderado_mango_cajon_20u_ficha_10u_es_caja_chica_dos_cartones():
    compras = [{"importe": 100, "cantidad_cajones": 2, "contenido_por_cajon": 20}]
    resultado = _envases_por_unidad_ponderado(compras, contenido_ficha=10, envase_variable=True)
    assert resultado == pytest.approx(1 / 10)
    # 40 unidades compradas (2 cajones de 20u) -> 4 cartones en total.
    assert resultado * (2 * 20) == pytest.approx(4)


def test_envases_ponderado_el_corte_sigue_a_la_ficha_no_esta_hardcodeado():
    # Mismo cajón de 9 unidades: con ficha=10 es descartable (9<=10); con
    # ficha=8 pasa a ser caja chica (9>8). El corte y el "cada cuánto"
    # tienen que salir siempre de la ficha, nunca de un número fijo.
    compras = [{"importe": 100, "cantidad_cajones": 2, "contenido_por_cajon": 9}]

    con_ficha_10 = _envases_por_unidad_ponderado(compras, contenido_ficha=10, envase_variable=True)
    con_ficha_8 = _envases_por_unidad_ponderado(compras, contenido_ficha=8, envase_variable=True)

    assert con_ficha_10 == 0.0
    assert con_ficha_8 == pytest.approx(1 / 8)


def test_envases_ponderado_funciona_con_decimal_como_devuelve_psycopg2():
    # Regresión: contenido_caja (fichas_logistica, numeric) viene de la base
    # como Decimal, no float — sin castear, "1.0 / contenido_ficha" rompía
    # con "unsupported operand type(s) for /: 'float' and 'decimal.Decimal'".
    compras = [
        {
            "importe": Decimal("100"),
            "cantidad_cajones": Decimal("5"),
            "contenido_por_cajon": Decimal("8"),
        }
    ]
    resultado = _envases_por_unidad_ponderado(compras, contenido_ficha=Decimal("8"), envase_variable=False)
    assert resultado == pytest.approx(1 / 8)


# --- precio_sugerido de punta a punta, vía calcular_listado_para_negociar_precios ---

FICHA_MORRON_ROJO = {
    "articulo_id": 29,
    "articulo_nombre": "Morrón Rojo",
    "unidad_venta": "kilo",
    "envase_id": 100,
    "contenido_caja": 8,
    "envase_variable": False,
}

COSTOS_ENVASES_MORRON_ROJO = [{"envase_id": 100, "costo": 1600}]


def test_precio_sugerido_morron_rojo_envase_fijo_coincide_con_formula_del_excel():
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": 27000,
        },
    ]
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_MORRON_ROJO],
        precios_vigentes=[],
        costos_envases=COSTOS_ENVASES_MORRON_ROJO,
    )

    assert len(resultado) == 1
    morron = resultado[0]
    # costo_actual = 27000*10 / (10*8) = 3375.
    assert morron["costo_actual"] == 3375
    # Envase: 1/8 caja por kilo, a $1600 la caja => $200/kg de envase, sin
    # utilidad. Producto: 3375 * 1.20 = 4050. (4050+200) / 0.77 = 5519.48...
    assert morron["precio_sugerido"] == pytest.approx(5519.4805, abs=0.001)


def test_precio_sugerido_con_descuento_y_flete_dos_tasas_que_restan():
    # Cliente con dos conceptos que restan (descuento 0.23 + flete 0.03),
    # sin ninguno que sume: las dos tienen que entrar juntas en tasas_restan.
    # Producto+envase: 3375*1.20 + 200 = 4250. (1 + 0 - 0.26) = 0.74.
    # 4250 / 0.74 = 5743.2432...
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": 27000,
        },
    ]
    conceptos = {"tasas_suman": [], "tasas_restan": [0.23, 0.03], "utilidad": 0.20}
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_MORRON_ROJO],
        precios_vigentes=[],
        conceptos=conceptos,
        costos_envases=COSTOS_ENVASES_MORRON_ROJO,
    )

    assert resultado[0]["costo_actual"] == 3375
    assert resultado[0]["precio_sugerido"] == pytest.approx(5743.2432, abs=0.001)


def test_precio_sugerido_con_iva_tasa_que_suma():
    # Cliente con descuento (resta) + IVA (suma) + utilidad.
    # 4250 / (1 + 0.105 - 0.23) = 4250 / 0.875 = 4857.1428...
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": 27000,
        },
    ]
    conceptos = {"tasas_suman": [0.105], "tasas_restan": [0.23], "utilidad": 0.20}
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_MORRON_ROJO],
        precios_vigentes=[],
        conceptos=conceptos,
        costos_envases=COSTOS_ENVASES_MORRON_ROJO,
    )

    assert resultado[0]["costo_actual"] == 3375
    assert resultado[0]["precio_sugerido"] == pytest.approx(4857.1428, abs=0.001)


FICHA_CHERRY_VARIABLE = {
    "articulo_id": 21,
    "articulo_nombre": "Tomate Cherry",
    "unidad_venta": "kilo",
    "envase_id": 200,
    "contenido_caja": 5,
    "envase_variable": True,
}

COSTOS_ENVASES_CHERRY = [{"envase_id": 200, "costo": 650}]


def test_precio_sugerido_cherry_envase_variable_caja_chica_de_punta_a_punta():
    # Cajón de 10kg con ficha de 5kg -> caja chica, 2 cartones cada cajón.
    compras = [
        {
            "articulo_id": 21,
            "articulo_nombre": "Tomate Cherry",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 4,
            "contenido_por_cajon": 10,
            "cantidad_kilos": 40,
            "importe": 3000,
        },
    ]
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_CHERRY_VARIABLE],
        precios_vigentes=[],
        costos_envases=COSTOS_ENVASES_CHERRY,
    )

    assert len(resultado) == 1
    cherry = resultado[0]
    # costo_actual = 3000*4 / (4*10) = 300/kg.
    assert cherry["costo_actual"] == 300
    # Envase: 1/5 caja por kilo (caja chica), a $650 => $130/kg, sin utilidad.
    # Producto: 300*1.20 = 360. (360+130)/0.77 = 636.36...
    assert cherry["precio_sugerido"] == pytest.approx(636.3636, abs=0.001)


def test_precio_sugerido_cherry_descartable_no_suma_costo_de_envase():
    # Mismo Cherry, pero comprado en cajón de 5kg (igual a la ficha) ->
    # descartable, sin cartón, aunque el envase esté configurado.
    compras = [
        {
            "articulo_id": 21,
            "articulo_nombre": "Tomate Cherry",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 4,
            "contenido_por_cajon": 5,
            "cantidad_kilos": 20,
            "importe": 1500,
        },
    ]
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_CHERRY_VARIABLE],
        precios_vigentes=[],
        costos_envases=COSTOS_ENVASES_CHERRY,
    )

    cherry = resultado[0]
    # costo_actual = 1500*4/(4*5) = 300/kg. Sin envase: 300*1.20/0.77.
    assert cherry["costo_actual"] == 300
    assert cherry["precio_sugerido"] == pytest.approx(300 * 1.20 / 0.77, abs=0.001)


def test_precio_sugerido_sin_costo_actual_es_none():
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": None,
        },
    ]
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_MORRON_ROJO],
        precios_vigentes=[],
        costos_envases=COSTOS_ENVASES_MORRON_ROJO,
    )

    assert resultado[0]["costo_actual"] is None
    assert resultado[0]["precio_sugerido"] is None


# --- utilidad_aproximada, vía calcular_listado_para_negociar_precios ---

def test_utilidad_aproximada_morron_rojo():
    # Caso del enunciado: precio vigente 4400/kg, costo 2500/kg, 8 kg,
    # caja grande 1600, descuento 0.23, sin tasas que suman -> ~25,48%.
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": 20000,  # costo_actual = 20000*10/(10*8) = 2500
        },
    ]
    precios_vigentes = [{"articulo_id": 29, "precio": 4400}]
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_MORRON_ROJO],
        precios_vigentes=precios_vigentes,
        costos_envases=COSTOS_ENVASES_MORRON_ROJO,
    )

    morron = resultado[0]
    assert morron["costo_actual"] == 2500
    assert morron["precio_vigente"] == 4400
    assert morron["utilidad_aproximada"] == pytest.approx(0.254815, abs=0.000001)
    assert round(morron["utilidad_aproximada"] * 100, 2) == 25.48


def test_utilidad_aproximada_sin_precio_vigente_es_none():
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": 27000,
        },
    ]
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_MORRON_ROJO],
        precios_vigentes=[],  # sin precio vigente para articulo_id 29
        costos_envases=COSTOS_ENVASES_MORRON_ROJO,
    )

    assert resultado[0]["precio_vigente"] is None
    assert resultado[0]["utilidad_aproximada"] is None


def test_utilidad_aproximada_precio_vigente_por_debajo_del_costo_da_negativa():
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": 20000,  # costo_actual = 2500/kg
        },
    ]
    # Precio vigente desactualizado, muy por debajo del costo.
    precios_vigentes = [{"articulo_id": 29, "precio": 1875}]  # 1875/kg
    resultado, _, _ = _calcular_negociacion(
        compras=compras,
        fichas=[FICHA_MORRON_ROJO],
        precios_vigentes=precios_vigentes,
        costos_envases=COSTOS_ENVASES_MORRON_ROJO,
    )

    morron = resultado[0]
    assert morron["precio_vigente"] == 1875
    assert morron["utilidad_aproximada"] < 0


# --- calcular_precio_sugerido_desglosado ---

FICHA_MORRON_ROJO_CON_NOMBRE = {
    "articulo_id": 29,
    "articulo_nombre": "Morrón Rojo",
    "unidad_venta": "kilo",
    "envase_id": 100,
    "envase_nombre": "Caja Grande",
    "contenido_caja": 8,
    "envase_variable": False,
}

COMPRAS_MORRON_ROJO_DESGLOSE = [
    {
        "articulo_id": 29,
        "articulo_nombre": "Morrón Rojo",
        "fecha_operacion": date(2026, 8, 10),
        "cantidad_cajones": 10,
        "contenido_por_cajon": 8,
        "cantidad_kilos": 80,
        "importe": 27000,
    },
]


def _calcular_desglose(
    momento=MOMENTO_DE_PRUEBA,
    articulo_nombre="Morrón Rojo",
    compras=COMPRAS_MORRON_ROJO_DESGLOSE,
    fichas=(FICHA_MORRON_ROJO_CON_NOMBRE,),
    conceptos=CONCEPTOS_NEGOCIACION,
    costos_envases=COSTOS_ENVASES_MORRON_ROJO,
    precios_vigentes=(),
):
    with (
        patch("app.costeo.listar_compras_para_costeo", return_value=compras),
        patch("app.costeo.listar_fichas_por_cliente", return_value=list(fichas)),
        patch("app.costeo.listar_conceptos_vigentes_por_cliente", return_value=conceptos),
        patch("app.costeo.listar_costos_envases_vigentes", return_value=list(costos_envases)),
        patch("app.costeo.listar_precios_vigentes_por_cliente", return_value=list(precios_vigentes)),
    ):
        return calcular_precio_sugerido_desglosado(CLIENTE_ID_DE_PRUEBA, articulo_nombre, momento)


def test_desglose_morron_rojo_expone_los_valores_intermedios():
    resultado = _calcular_desglose()

    assert resultado is not None
    # costo_actual = 27000*10 / (10*8) = 3375 (mismo valor que el listado completo).
    assert resultado["costo_actual"] == 3375
    assert resultado["utilidad"] == pytest.approx(0.20)
    assert resultado["tasas_restan"] == [0.23]
    assert resultado["tasas_suman"] == []
    assert resultado["envase_nombre"] == "Caja Grande"
    assert resultado["envase_variable"] is False
    assert resultado["contenido_ficha"] == 8
    assert resultado["costo_envase_unitario"] == 1600
    # Envase fijo: 1/8 caja por kilo.
    assert resultado["envases_por_unidad"] == pytest.approx(1 / 8)
    # 1600 * 1/8 = 200/kg de envase.
    assert resultado["costo_envase_por_unidad"] == pytest.approx(200)
    # Mismo resultado que calcular_listado_para_negociar_precios para este artículo.
    assert resultado["precio_sugerido"] == pytest.approx(5519.4805, abs=0.001)
    assert resultado["fecha_ultima_compra"] == date(2026, 8, 10)
    assert resultado["compras_sin_precio_excluidas"] == 0
    # Sin precio vigente cargado (precios_vigentes=() por defecto): no hay
    # nada que medir, todo el desglose de utilidad_aproximada queda en None.
    assert resultado["precio_vigente"] is None
    assert resultado["utilidad_aproximada"] is None
    assert resultado["costo_total_bulto"] is None


def test_desglose_utilidad_aproximada_morron_rojo():
    # Caso del enunciado: precio vigente 4400/kg, costo 2500/kg, 8 kg,
    # caja grande 1600, descuento 0.23, sin tasas que suman -> ~25,48%.
    # costo_actual = 2500 con importe=20000, cantidad_cajones=10,
    # contenido_por_cajon=8 -> 20000*10/(10*8) = 2500.
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": 20000,
        },
    ]
    precios_vigentes = [{"articulo_id": 29, "precio": 4400}]

    resultado = _calcular_desglose(compras=compras, precios_vigentes=precios_vigentes)

    assert resultado is not None
    assert resultado["costo_actual"] == 2500
    assert resultado["precio_vigente"] == 4400
    # costo_producto_bulto = 2500*8 = 20000; costo_envase_bulto = 200*8 = 1600
    # (1600 = 1/8 caja/kg * 8kg * 1600/caja); costo_total_bulto = 21600.
    assert resultado["costo_producto_bulto"] == pytest.approx(20000)
    assert resultado["costo_envase_bulto"] == pytest.approx(1600)
    assert resultado["costo_total_bulto"] == pytest.approx(21600)
    # precio_vigente_bulto = 4400*8 = 35200; entra = 35200*0.77 = 27104.
    assert resultado["precio_vigente_bulto"] == pytest.approx(35200)
    assert resultado["entra_bulto"] == pytest.approx(27104)
    # utilidad = (27104-21600)/21600 ≈ 0,254815 (~25,48%).
    assert resultado["utilidad_aproximada"] == pytest.approx(0.254815, abs=0.000001)
    assert round(resultado["utilidad_aproximada"] * 100, 2) == 25.48


def test_desglose_articulo_sin_ficha_devuelve_none():
    resultado = _calcular_desglose(articulo_nombre="Artículo Inexistente")

    assert resultado is None


def test_desglose_sin_compras_con_precio_devuelve_none():
    compras = [
        {
            "articulo_id": 29,
            "articulo_nombre": "Morrón Rojo",
            "fecha_operacion": date(2026, 8, 10),
            "cantidad_cajones": 10,
            "contenido_por_cajon": 8,
            "cantidad_kilos": 80,
            "importe": None,
        },
    ]
    resultado = _calcular_desglose(compras=compras)

    assert resultado is None


def test_desglose_sin_utilidad_del_cliente_devuelve_none():
    conceptos_sin_utilidad = {"tasas_suman": [], "tasas_restan": [0.23], "utilidad": None}
    resultado = _calcular_desglose(conceptos=conceptos_sin_utilidad)

    assert resultado is None


def test_desglose_sin_ninguna_tasa_extra_no_es_falta_de_datos():
    # tasas_suman y tasas_restan vacías NO son "faltan datos": un cliente
    # puede legítimamente no tener ninguna tasa de esos tipos cargada. Solo
    # la utilidad ausente corta el cálculo.
    conceptos_solo_utilidad = {"tasas_suman": [], "tasas_restan": [], "utilidad": 0.20}
    resultado = _calcular_desglose(conceptos=conceptos_solo_utilidad)

    assert resultado is not None
    # Sin ninguna tasa: precio = (3375*1.20 + 200) / 1 = 4250.
    assert resultado["precio_sugerido"] == pytest.approx(4250)


def test_desglose_encuentra_la_ficha_aunque_el_nombre_en_la_base_no_tenga_tilde():
    # Regresión real: en producción el nombre del artículo está cargado como
    # "Morron Rojo" (sin tilde), y la búsqueda comparaba con == exacto contra
    # "Morrón Rojo" (con tilde) — no encontraba la ficha y devolvía None en
    # silencio, aunque el artículo sí tenía ficha, compra con precio y
    # descuento/utilidad vigentes (confirmado porque el listado principal sí
    # lo mostraba con precio sugerido calculado).
    ficha_sin_tilde = dict(FICHA_MORRON_ROJO_CON_NOMBRE, articulo_nombre="Morron Rojo")
    compras = [dict(c, articulo_nombre="Morron Rojo") for c in COMPRAS_MORRON_ROJO_DESGLOSE]

    resultado = _calcular_desglose(articulo_nombre="Morrón Rojo", compras=compras, fichas=(ficha_sin_tilde,))

    assert resultado is not None
    assert resultado["articulo_nombre"] == "Morron Rojo"
    assert resultado["costo_actual"] == 3375


# --- agrupar_para_negociar: cuadro simplificado (Bajas / Subas / bajo objetivo) ---
# No recalcula nada: son los mismos dicts que devolvería
# calcular_listado_para_negociar_precios, armados a mano acá para no
# depender de mocks de base — solo se prueba el filtrado/orden.

UTILIDAD_OBJETIVO_DE_PRUEBA = 0.20

ARTICULOS_PARA_AGRUPAR = [
    # A: fresco, bajó, utilidad floja (0.10 < 0.20) -> Bajas + bajo_objetivo.
    {"articulo_nombre": "A", "fresco": True, "variacion": "bajo", "utilidad_aproximada": 0.10},
    # B: fresco, subió, utilidad por encima del objetivo -> Subas, no bajo_objetivo.
    {"articulo_nombre": "B", "fresco": True, "variacion": "subio", "utilidad_aproximada": 0.30},
    # C: NO fresco (variacion None), utilidad muy negativa -> ni Bajas ni
    # Subas, pero sí en bajo_objetivo (peor de todos, tiene que ir primero).
    {"articulo_nombre": "C", "fresco": False, "variacion": None, "utilidad_aproximada": -0.05},
    # D: fresco pero sin variación (artículo nuevo, sin comparación previa),
    # utilidad floja -> ni Bajas ni Subas, pero sí en bajo_objetivo.
    {"articulo_nombre": "D", "fresco": True, "variacion": None, "utilidad_aproximada": 0.15},
    # E: no fresco, sin precio vigente (utilidad_aproximada None) -> no
    # entra en ningún lado, ni siquiera en bajo_objetivo.
    {"articulo_nombre": "E", "fresco": False, "variacion": None, "utilidad_aproximada": None},
    # F: fresco, variación "igual", utilidad por encima del objetivo -> no
    # entra en ningún lado.
    {"articulo_nombre": "F", "fresco": True, "variacion": "igual", "utilidad_aproximada": 0.25},
]


def test_agrupar_bajas_incluye_solo_frescos_que_bajaron():
    resultado = agrupar_para_negociar(ARTICULOS_PARA_AGRUPAR, UTILIDAD_OBJETIVO_DE_PRUEBA)

    nombres_bajas = [a["articulo_nombre"] for a in resultado["bajas"]]
    assert nombres_bajas == ["A"]


def test_agrupar_subas_incluye_solo_frescos_que_subieron():
    resultado = agrupar_para_negociar(ARTICULOS_PARA_AGRUPAR, UTILIDAD_OBJETIVO_DE_PRUEBA)

    nombres_subas = [a["articulo_nombre"] for a in resultado["subas"]]
    assert nombres_subas == ["B"]


def test_agrupar_no_fresco_no_aparece_en_bajas_ni_subas():
    resultado = agrupar_para_negociar(ARTICULOS_PARA_AGRUPAR, UTILIDAD_OBJETIVO_DE_PRUEBA)

    nombres_bajas = {a["articulo_nombre"] for a in resultado["bajas"]}
    nombres_subas = {a["articulo_nombre"] for a in resultado["subas"]}
    assert "C" not in nombres_bajas
    assert "C" not in nombres_subas


def test_agrupar_bajo_objetivo_ordena_de_peor_a_mejor_y_filtra():
    resultado = agrupar_para_negociar(ARTICULOS_PARA_AGRUPAR, UTILIDAD_OBJETIVO_DE_PRUEBA)

    nombres_bajo_objetivo = [a["articulo_nombre"] for a in resultado["bajo_objetivo"]]
    # C (-0.05) peor que A (0.10) peor que D (0.15); B, E y F quedan afuera.
    assert nombres_bajo_objetivo == ["C", "A", "D"]


def test_agrupar_sin_precio_vigente_no_entra_en_bajo_objetivo():
    resultado = agrupar_para_negociar(ARTICULOS_PARA_AGRUPAR, UTILIDAD_OBJETIVO_DE_PRUEBA)

    nombres_bajo_objetivo = {a["articulo_nombre"] for a in resultado["bajo_objetivo"]}
    assert "E" not in nombres_bajo_objetivo


def test_agrupar_sin_utilidad_objetivo_del_cliente_bajo_objetivo_vacio():
    resultado = agrupar_para_negociar(ARTICULOS_PARA_AGRUPAR, utilidad_objetivo=None)

    assert resultado["bajo_objetivo"] == []
    # Bajas/Subas no dependen de la utilidad objetivo del cliente.
    assert [a["articulo_nombre"] for a in resultado["bajas"]] == ["A"]
    assert [a["articulo_nombre"] for a in resultado["subas"]] == ["B"]


def test_agrupar_todos_incluye_todos_los_articulos_ordenados_de_mejor_a_peor_utilidad():
    resultado = agrupar_para_negociar(ARTICULOS_PARA_AGRUPAR, UTILIDAD_OBJETIVO_DE_PRUEBA)

    nombres_todos = [a["articulo_nombre"] for a in resultado["todos"]]
    # B (0.30) > F (0.25) > D (0.15) > A (0.10) > C (-0.05); E (sin
    # utilidad, no comparable) va al final.
    assert nombres_todos == ["B", "F", "D", "A", "C", "E"]


def test_agrupar_todos_no_depende_de_la_utilidad_objetivo_del_cliente():
    # A diferencia de bajo_objetivo, "todos" siempre trae los 6 aunque el
    # cliente no tenga utilidad objetivo cargada.
    resultado = agrupar_para_negociar(ARTICULOS_PARA_AGRUPAR, utilidad_objetivo=None)

    assert len(resultado["todos"]) == 6
