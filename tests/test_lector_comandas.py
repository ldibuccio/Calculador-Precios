import json
from unittest.mock import patch

import pytest

from core.lector_comandas import PROMPT_EXTRACCION, extraer_comanda

IMAGEN_DE_PRUEBA = b"contenido falso de una imagen"

COMANDA_VALIDA = {
    "proveedor": {"nombre": "Frutas del Sol", "nave": "3", "puesto": "12"},
    "fecha": "2026-07-23",
    "items": [
        {
            "articulo": "Tomate Redondo",
            "cantidad": 10,
            "importe": 28000,
            "sena": None,
            "nota_margen": "84",
            "confianza": "alta",
        }
    ],
}


def test_extraer_comanda_devuelve_el_json_parseado():
    with patch("core.lector_comandas._llamar_api_claude", return_value=json.dumps(COMANDA_VALIDA)):
        resultado = extraer_comanda(IMAGEN_DE_PRUEBA)

    assert resultado == COMANDA_VALIDA


def test_extraer_comanda_json_invalido_lanza_error():
    with patch("core.lector_comandas._llamar_api_claude", return_value="esto no es JSON"):
        with pytest.raises(ValueError):
            extraer_comanda(IMAGEN_DE_PRUEBA)


def test_extraer_comanda_json_que_no_es_objeto_lanza_error():
    with patch("core.lector_comandas._llamar_api_claude", return_value=json.dumps([1, 2, 3])):
        with pytest.raises(ValueError):
            extraer_comanda(IMAGEN_DE_PRUEBA)


def test_extraer_comanda_respuesta_vacia_lanza_error():
    with patch("core.lector_comandas._llamar_api_claude", return_value=""):
        with pytest.raises(ValueError):
            extraer_comanda(IMAGEN_DE_PRUEBA)


def test_extraer_comanda_con_dato_no_leido_marca_confianza_baja():
    comanda_con_dato_dudoso = {
        "proveedor": {"nombre": "", "nave": "5", "puesto": "8"},
        "fecha": "2026-07-23",
        "items": [
            {
                "articulo": "completar artículo",
                "cantidad": 10,
                "importe": 5000,
                "sena": None,
                "nota_margen": "",
                "confianza": "baja",
            }
        ],
    }
    with patch("core.lector_comandas._llamar_api_claude", return_value=json.dumps(comanda_con_dato_dudoso)):
        resultado = extraer_comanda(IMAGEN_DE_PRUEBA)

    assert resultado["items"][0]["articulo"] == "completar artículo"
    assert resultado["items"][0]["confianza"] == "baja"


def test_prompt_incluye_las_reglas_clave_de_extraccion():
    # Test de regresión: si alguien edita el prompt sin querer, esto avisa
    # que se perdió alguna regla de negocio importante.
    assert "NUNCA adivinar" in PROMPT_EXTRACCION
    assert "Señor" in PROMPT_EXTRACCION
    assert "nota_margen" in PROMPT_EXTRACCION
    assert "Morrón Rojo" in PROMPT_EXTRACCION
    assert "Granny" in PROMPT_EXTRACCION


def test_llamar_api_claude_sin_conectar_lanza_not_implemented():
    from core.lector_comandas import _llamar_api_claude

    with pytest.raises(NotImplementedError):
        _llamar_api_claude(IMAGEN_DE_PRUEBA)
