import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.lector_comandas import (
    ANTHROPIC_API_KEY_ENV_VAR,
    PROMPT_EXTRACCION,
    _detectar_media_type,
    _extraer_texto_de_la_respuesta,
    _limpiar_respuesta_json,
    _llamar_api_claude,
    extraer_comanda,
)

IMAGEN_DE_PRUEBA = b"contenido falso de una imagen"
IMAGEN_PNG_DE_PRUEBA = b"\x89PNG\r\n\x1a\n" + b"resto de bytes falsos"
IMAGEN_JPEG_DE_PRUEBA = b"\xff\xd8\xff" + b"resto de bytes falsos"

COMANDA_VALIDA = {
    "proveedor": {"nombre": "Frutas del Sol", "tipo_pabellon": "nave", "numero_pabellon": "3", "puesto": "12"},
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
        "proveedor": {"nombre": "", "tipo_pabellon": "nave", "numero_pabellon": "5", "puesto": "8"},
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
    assert "tipo_pabellon" in PROMPT_EXTRACCION
    assert "Libre" in PROMPT_EXTRACCION
    assert "COMPLETO" in PROMPT_EXTRACCION


def test_detectar_media_type_png():
    assert _detectar_media_type(IMAGEN_PNG_DE_PRUEBA) == "image/png"


def test_detectar_media_type_jpeg():
    assert _detectar_media_type(IMAGEN_JPEG_DE_PRUEBA) == "image/jpeg"


def test_detectar_media_type_formato_desconocido_lanza_error():
    with pytest.raises(ValueError):
        _detectar_media_type(b"esto no es ni jpeg ni png")


def test_limpiar_respuesta_json_sin_backticks_no_cambia():
    texto = '{"a": 1}'
    assert _limpiar_respuesta_json(texto) == '{"a": 1}'


def test_limpiar_respuesta_json_con_backticks_y_json():
    texto = '```json\n{"a": 1}\n```'
    assert _limpiar_respuesta_json(texto) == '{"a": 1}'


def test_limpiar_respuesta_json_con_backticks_simples():
    texto = '```\n{"a": 1}\n```'
    assert _limpiar_respuesta_json(texto) == '{"a": 1}'


def test_extraer_comanda_limpia_backticks_antes_de_parsear():
    respuesta_con_backticks = '```json\n' + json.dumps(COMANDA_VALIDA) + '\n```'
    with patch("core.lector_comandas._llamar_api_claude", return_value=respuesta_con_backticks):
        resultado = extraer_comanda(IMAGEN_DE_PRUEBA)

    assert resultado == COMANDA_VALIDA


def test_llamar_api_claude_sin_api_key_lanza_error_claro(monkeypatch):
    monkeypatch.delenv(ANTHROPIC_API_KEY_ENV_VAR, raising=False)

    with pytest.raises(RuntimeError, match=ANTHROPIC_API_KEY_ENV_VAR):
        _llamar_api_claude(IMAGEN_PNG_DE_PRUEBA)


def _respuesta_falsa(bloques):
    return SimpleNamespace(content=bloques)


def test_extraer_texto_de_la_respuesta_ignora_bloques_de_thinking():
    # ThinkingBlock real: tiene "type" == "thinking" y ".thinking", pero NO ".text".
    bloque_thinking = SimpleNamespace(type="thinking", thinking="razonando sobre la comanda...")
    bloque_texto = SimpleNamespace(type="text", text="hola")

    resultado = _extraer_texto_de_la_respuesta([bloque_thinking, bloque_texto])

    assert resultado == "hola"


def test_extraer_texto_de_la_respuesta_concatena_varios_bloques_de_texto():
    bloques = [SimpleNamespace(type="text", text='{"a": '), SimpleNamespace(type="text", text="1}")]

    resultado = _extraer_texto_de_la_respuesta(bloques)

    assert resultado == '{"a": 1}'


def test_extraer_texto_de_la_respuesta_sin_bloques_de_texto_lanza_error():
    bloques = [SimpleNamespace(type="thinking", thinking="solo pensó, no contestó")]

    with pytest.raises(ValueError):
        _extraer_texto_de_la_respuesta(bloques)


def test_llamar_api_claude_con_thinking_activado_usa_solo_el_bloque_de_texto(monkeypatch):
    # Regresión: con el thinking activado, la respuesta trae un ThinkingBlock
    # (sin .text) antes del bloque de texto real; no hay que asumir que
    # content[0] es siempre el texto.
    monkeypatch.setenv(ANTHROPIC_API_KEY_ENV_VAR, "clave-de-prueba")
    bloque_thinking = SimpleNamespace(type="thinking", thinking="pensando en la comanda...")
    bloque_texto = SimpleNamespace(type="text", text=json.dumps(COMANDA_VALIDA))
    cliente_falso = Mock()
    cliente_falso.messages.create.return_value = _respuesta_falsa([bloque_thinking, bloque_texto])

    with patch("core.lector_comandas.anthropic.Anthropic", return_value=cliente_falso):
        resultado = _llamar_api_claude(IMAGEN_PNG_DE_PRUEBA)

    assert resultado == json.dumps(COMANDA_VALIDA)
