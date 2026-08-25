"""Tests del motor de Costos Fijos (core/costos_fijos.py) — puro, sin base.

Las tres reglas del dueño: el valor es un CÁLCULO (jamás guardado), la
corrección vale de ahí en adelante, y un índice faltante AVISA — nunca se
inventa ni se arrastra el anterior.
"""

from datetime import date, datetime

from core.costos_fijos import calcular_costos_fijos, valor_subcuenta_en_mes

AGO = date(2026, 8, 1)
SEP = date(2026, 9, 1)
OCT = date(2026, 10, 1)
NOV = date(2026, 11, 1)

INDICES = {SEP: 10.0, OCT: 5.0, NOV: 2.0}


def _foto(mes, importe, alcance="en_adelante", creado_en=None, anulado_el=None, subcuenta_id=1):
    return {
        "subcuenta_id": subcuenta_id,
        "mes_desde": mes,
        "importe": importe,
        "alcance": alcance,
        "creado_en": creado_en or datetime(2026, 8, 1, 12, 0),
        "anulado_el": anulado_el,
    }


# --- valor_subcuenta_en_mes ---


def test_la_foto_vale_tal_cual_en_su_propio_mes():
    # Sin meses posteriores no hace falta ningún índice.
    resultado = valor_subcuenta_en_mes([_foto(AGO, 1000.0)], {}, AGO)
    assert resultado["valor"] == 1000.0
    assert resultado["mes_foto"] == AGO


def test_el_inflado_es_compuesto_mes_a_mes():
    # Foto de agosto en octubre: ×(1 + 10%) por septiembre y ×(1 + 5%)
    # por octubre — el % de un mes es la inflación DE ese mes.
    resultado = valor_subcuenta_en_mes([_foto(AGO, 1000.0)], INDICES, OCT)
    assert resultado["valor"] == 1155.0


def test_el_indice_puede_ser_negativo():
    resultado = valor_subcuenta_en_mes([_foto(AGO, 1000.0)], {SEP: -10.0}, SEP)
    assert resultado["valor"] == 900.0


def test_indice_faltante_no_calcula_y_dice_que_mes_falta():
    # Falta septiembre: NO se usa el índice anterior ni se asume cero —
    # se avisa y el valor queda sin calcular (regla 3).
    resultado = valor_subcuenta_en_mes([_foto(AGO, 1000.0)], {OCT: 5.0}, OCT)
    assert resultado["valor"] is None
    assert resultado["indices_faltantes"] == [SEP]


def test_la_correccion_vale_de_ahi_en_adelante():
    fotos = [_foto(AGO, 1000.0), _foto(OCT, 2000.0, creado_en=datetime(2026, 10, 5, 12, 0))]
    # Septiembre sigue con la foto vieja y el índice de entonces.
    assert valor_subcuenta_en_mes(fotos, INDICES, SEP)["valor"] == 1100.0
    # Octubre arranca de la corrección, tal cual.
    assert valor_subcuenta_en_mes(fotos, INDICES, OCT)["valor"] == 2000.0
    # Noviembre infla desde la corrección.
    assert valor_subcuenta_en_mes(fotos, INDICES, NOV)["valor"] == 2040.0


def test_la_correccion_puntual_pisa_solo_su_mes():
    fotos = [
        _foto(AGO, 1000.0),
        _foto(SEP, 1234.0, alcance="solo_este_mes", creado_en=datetime(2026, 9, 10, 12, 0)),
    ]
    # Septiembre: el valor puntual, tal cual, sin inflar.
    septiembre = valor_subcuenta_en_mes(fotos, INDICES, SEP)
    assert septiembre["valor"] == 1234.0
    assert septiembre["puntual"] is True
    # Octubre NO arrastra el puntual: sigue la foto de agosto inflada.
    assert valor_subcuenta_en_mes(fotos, INDICES, OCT)["valor"] == 1155.0


def test_una_foto_anulada_no_cuenta():
    fotos = [
        _foto(AGO, 9999.0, anulado_el=datetime(2026, 8, 2, 12, 0)),
        _foto(AGO, 1000.0, creado_en=datetime(2026, 8, 3, 12, 0)),
    ]
    assert valor_subcuenta_en_mes(fotos, INDICES, AGO)["valor"] == 1000.0


def test_dos_fotos_del_mismo_mes_gana_la_ultima_cargada():
    fotos = [
        _foto(AGO, 1000.0, creado_en=datetime(2026, 8, 1, 12, 0)),
        _foto(AGO, 1200.0, creado_en=datetime(2026, 8, 20, 12, 0)),
    ]
    assert valor_subcuenta_en_mes(fotos, INDICES, AGO)["valor"] == 1200.0


def test_sin_foto_anterior_no_existia():
    resultado = valor_subcuenta_en_mes([_foto(OCT, 500.0)], INDICES, SEP)
    assert resultado["valor"] is None
    assert resultado["mes_foto"] is None
    assert resultado["indices_faltantes"] == []


# --- calcular_costos_fijos ---

GRUPOS = [
    {"id": 1, "numero": 10, "nombre": "Sueldos", "baja_el": None},
    {"id": 2, "numero": 20, "nombre": "Cargas sociales", "baja_el": None},
]
SUBCUENTAS = [
    {"id": 1, "grupo_id": 1, "numero": 1, "nombre": "Sdo Christian", "baja_desde": None},
    {"id": 2, "grupo_id": 1, "numero": 2, "nombre": "Sdo Camila", "baja_desde": None},
    {"id": 3, "grupo_id": 2, "numero": 2, "nombre": "Aguinaldos", "baja_desde": None},
]


def test_total_con_desglose_por_grupo_y_codigo():
    importes = [
        _foto(SEP, 1000.0, subcuenta_id=1),
        _foto(SEP, 800.0, subcuenta_id=2),
        _foto(SEP, 300.0, subcuenta_id=3),
    ]
    resultado = calcular_costos_fijos(GRUPOS, SUBCUENTAS, importes, INDICES, SEP)

    assert resultado["total"] == 2100.0
    assert resultado["incompleto"] is False
    sueldos = resultado["grupos"][0]
    assert sueldos["numero"] == 10 and sueldos["subtotal"] == 1800.0
    assert sueldos["filas"][0]["codigo"] == "10.1"
    assert resultado["grupos"][1]["filas"][0]["codigo"] == "20.2"


def test_indice_faltante_marca_el_total_incompleto_y_lista_la_subcuenta():
    importes = [_foto(AGO, 1000.0, subcuenta_id=1), _foto(SEP, 800.0, subcuenta_id=2)]
    resultado = calcular_costos_fijos(GRUPOS, SUBCUENTAS, importes, {}, SEP)

    # La foto de agosto necesita el índice de septiembre y no está: NO
    # entra al total, y el total queda marcado INCOMPLETO.
    assert resultado["total"] == 800.0
    assert resultado["incompleto"] is True
    assert resultado["sin_calcular"][0]["codigo"] == "10.1"
    assert resultado["sin_calcular"][0]["faltan"] == [SEP]
    assert resultado["indices_faltantes"] == [SEP]


def test_la_baja_con_mes_deja_de_contar_desde_su_mes():
    subcuentas = [dict(SUBCUENTAS[0], baja_desde=OCT), SUBCUENTAS[1], SUBCUENTAS[2]]
    importes = [
        _foto(SEP, 1000.0, subcuenta_id=1),
        _foto(SEP, 800.0, subcuenta_id=2),
        _foto(SEP, 300.0, subcuenta_id=3),
    ]
    # Septiembre lo cuenta (la baja es desde octubre)...
    septiembre = calcular_costos_fijos(GRUPOS, subcuentas, importes, INDICES, SEP)
    assert septiembre["total"] == 2100.0
    # ...y octubre ya no — pero las otras siguen inflando.
    octubre = calcular_costos_fijos(GRUPOS, subcuentas, importes, INDICES, OCT)
    assert octubre["total"] == round(800 * 1.05 + 300 * 1.05, 2)


def test_filtro_por_grupo_puntual():
    importes = [_foto(SEP, 1000.0, subcuenta_id=1), _foto(SEP, 300.0, subcuenta_id=3)]
    resultado = calcular_costos_fijos(GRUPOS, SUBCUENTAS, importes, INDICES, SEP, grupo_numero=20)

    assert [g["numero"] for g in resultado["grupos"]] == [20]
    assert resultado["total"] == 300.0


def test_subcuenta_sin_foto_queda_informada_sin_sumar():
    importes = [_foto(SEP, 1000.0, subcuenta_id=1)]
    resultado = calcular_costos_fijos(GRUPOS, SUBCUENTAS, importes, INDICES, SEP)

    assert resultado["total"] == 1000.0
    codigos_sin_importe = {s["codigo"] for s in resultado["sin_importe"]}
    assert codigos_sin_importe == {"10.2", "20.2"}
