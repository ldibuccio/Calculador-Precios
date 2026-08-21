import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.lector_comandas import (
    ANTHROPIC_API_KEY_ENV_VAR,
    MAX_TOKENS_LISTADO_CONSOLIDADO,
    MAX_TOKENS_LISTADO_PRECIOS,
    PROMPT_EXTRACCION,
    PROMPT_LISTADO_CONSOLIDADO,
    PROMPT_LISTADO_PRECIOS,
    _detectar_media_type,
    _extraer_texto_de_la_respuesta,
    _limpiar_respuesta_json,
    _llamar_api_claude,
    _llamar_api_claude_multi_imagen,
    _llamar_api_claude_texto,
    extraer_comanda,
    extraer_listado_consolidado,
    extraer_listado_precios_de_imagenes,
    extraer_listado_precios_de_texto,
    extraer_pedido_de_texto,
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
    assert "y P" in PROMPT_EXTRACCION


LISTADO_VALIDO = {
    "renglones": [
        {
            "es_idem": False,
            "proveedor_texto": "Saturno",
            "codigo": "",
            "articulo": "Kiwi",
            "cantidad": 10,
            "kg_x_bulto": 18,
            "importe": 5000,
            "nota_margen": "84",
            "confianza": "alta",
        },
        {
            "es_idem": True,
            "proveedor_texto": "",
            "codigo": "",
            "articulo": "Pera",
            "cantidad": 5,
            "kg_x_bulto": None,
            "importe": None,
            "nota_margen": "",
            "confianza": "alta",
        },
    ]
}


def test_extraer_listado_consolidado_devuelve_el_json_parseado():
    with patch("core.lector_comandas._llamar_api_claude", return_value=json.dumps(LISTADO_VALIDO)):
        resultado = extraer_listado_consolidado(IMAGEN_DE_PRUEBA)

    assert resultado == LISTADO_VALIDO


def test_extraer_listado_consolidado_usa_el_prompt_y_el_limite_de_tokens_propios():
    with patch("core.lector_comandas._llamar_api_claude", return_value=json.dumps(LISTADO_VALIDO)) as mock_llamar:
        extraer_listado_consolidado(IMAGEN_DE_PRUEBA)

    mock_llamar.assert_called_once_with(
        IMAGEN_DE_PRUEBA, None, prompt=PROMPT_LISTADO_CONSOLIDADO, max_tokens=MAX_TOKENS_LISTADO_CONSOLIDADO
    )


def test_extraer_listado_consolidado_json_invalido_lanza_error():
    with patch("core.lector_comandas._llamar_api_claude", return_value="esto no es JSON"):
        with pytest.raises(ValueError):
            extraer_listado_consolidado(IMAGEN_DE_PRUEBA)


def test_extraer_listado_consolidado_json_que_no_es_objeto_lanza_error():
    with patch("core.lector_comandas._llamar_api_claude", return_value=json.dumps([1, 2, 3])):
        with pytest.raises(ValueError):
            extraer_listado_consolidado(IMAGEN_DE_PRUEBA)


def test_extraer_listado_consolidado_respuesta_vacia_lanza_error():
    with patch("core.lector_comandas._llamar_api_claude", return_value=""):
        with pytest.raises(ValueError):
            extraer_listado_consolidado(IMAGEN_DE_PRUEBA)


def test_extraer_listado_consolidado_limpia_backticks_antes_de_parsear():
    respuesta_con_backticks = "```json\n" + json.dumps(LISTADO_VALIDO) + "\n```"
    with patch("core.lector_comandas._llamar_api_claude", return_value=respuesta_con_backticks):
        resultado = extraer_listado_consolidado(IMAGEN_DE_PRUEBA)

    assert resultado == LISTADO_VALIDO


def test_extraer_listado_consolidado_renglon_dudoso_pasa_confianza_baja():
    listado_con_dato_dudoso = {
        "renglones": [
            {
                "es_idem": False,
                "proveedor_texto": "completar proveedor",
                "codigo": "",
                "articulo": "completar articulo",
                "cantidad": 10,
                "kg_x_bulto": None,
                "importe": None,
                "nota_margen": "",
                "confianza": "baja",
            }
        ]
    }
    with patch("core.lector_comandas._llamar_api_claude", return_value=json.dumps(listado_con_dato_dudoso)):
        resultado = extraer_listado_consolidado(IMAGEN_DE_PRUEBA)

    assert resultado["renglones"][0]["articulo"] == "completar articulo"
    assert resultado["renglones"][0]["confianza"] == "baja"


def test_prompt_listado_consolidado_incluye_las_reglas_clave():
    # Test de regresión, mismo criterio que test_prompt_incluye_las_reglas_
    # clave_de_extraccion: si alguien edita el prompt sin querer, esto avisa
    # que se perdió alguna regla de negocio importante.
    assert "es_idem" in PROMPT_LISTADO_CONSOLIDADO
    assert "NUNCA copies vos el" in PROMPT_LISTADO_CONSOLIDADO
    assert "NUNCA adivinar" in PROMPT_LISTADO_CONSOLIDADO
    assert "kg_x_bulto" in PROMPT_LISTADO_CONSOLIDADO
    assert "nota_margen" in PROMPT_LISTADO_CONSOLIDADO
    assert "Granny" in PROMPT_LISTADO_CONSOLIDADO
    assert "completar proveedor" in PROMPT_LISTADO_CONSOLIDADO


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


def _respuesta_falsa(bloques, stop_reason="end_turn"):
    return SimpleNamespace(content=bloques, stop_reason=stop_reason)


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


def test_llamar_api_claude_cortada_por_max_tokens_da_error_claro(monkeypatch):
    # Regresión real: con una comanda con muchos artículos, la respuesta se
    # cortaba a mitad del JSON ("Unterminated string...") en vez de avisar
    # claramente que se quedó sin espacio.
    monkeypatch.setenv(ANTHROPIC_API_KEY_ENV_VAR, "clave-de-prueba")
    bloque_texto_cortado = SimpleNamespace(type="text", text='{"proveedor": {"nombre": "Sat')
    cliente_falso = Mock()
    cliente_falso.messages.create.return_value = _respuesta_falsa([bloque_texto_cortado], stop_reason="max_tokens")

    with patch("core.lector_comandas.anthropic.Anthropic", return_value=cliente_falso):
        with pytest.raises(RuntimeError, match="se cortó"):
            _llamar_api_claude(IMAGEN_PNG_DE_PRUEBA)


# --- extraer_listado_precios_de_imagenes / extraer_listado_precios_de_texto: "Cargar Foto Precios" ---

LISTADO_PRECIOS_VALIDO = {
    "items": [
        {"articulo": "Tomate Cherry", "precio": 500.0, "confianza": "alta"},
        {"articulo": "Mango", "precio": 350.0, "confianza": "alta"},
    ]
}


def test_extraer_listado_precios_de_imagenes_devuelve_el_json_parseado():
    with patch(
        "core.lector_comandas._llamar_api_claude_multi_imagen", return_value=json.dumps(LISTADO_PRECIOS_VALIDO)
    ):
        resultado = extraer_listado_precios_de_imagenes([IMAGEN_DE_PRUEBA])

    assert resultado == LISTADO_PRECIOS_VALIDO


def test_extraer_listado_precios_de_imagenes_usa_el_prompt_y_el_limite_de_tokens_propios():
    imagenes = [IMAGEN_JPEG_DE_PRUEBA, IMAGEN_PNG_DE_PRUEBA]
    with patch(
        "core.lector_comandas._llamar_api_claude_multi_imagen", return_value=json.dumps(LISTADO_PRECIOS_VALIDO)
    ) as mock_llamar:
        extraer_listado_precios_de_imagenes(imagenes)

    mock_llamar.assert_called_once_with(
        imagenes, prompt=PROMPT_LISTADO_PRECIOS, max_tokens=MAX_TOKENS_LISTADO_PRECIOS
    )


def test_extraer_listado_precios_de_imagenes_json_invalido_lanza_error():
    with patch("core.lector_comandas._llamar_api_claude_multi_imagen", return_value="esto no es JSON"):
        with pytest.raises(ValueError):
            extraer_listado_precios_de_imagenes([IMAGEN_DE_PRUEBA])


def test_extraer_listado_precios_de_texto_devuelve_el_json_parseado():
    with patch("core.lector_comandas._llamar_api_claude_texto", return_value=json.dumps(LISTADO_PRECIOS_VALIDO)):
        resultado = extraer_listado_precios_de_texto("Tomate Cherry | 500\nMango | 350")

    assert resultado == LISTADO_PRECIOS_VALIDO


def test_extraer_listado_precios_de_texto_usa_el_prompt_y_el_limite_de_tokens_propios():
    with patch(
        "core.lector_comandas._llamar_api_claude_texto", return_value=json.dumps(LISTADO_PRECIOS_VALIDO)
    ) as mock_llamar:
        extraer_listado_precios_de_texto("texto de la planilla")

    mock_llamar.assert_called_once_with(
        "texto de la planilla", prompt=PROMPT_LISTADO_PRECIOS, max_tokens=MAX_TOKENS_LISTADO_PRECIOS
    )


def test_extraer_listado_precios_de_texto_json_invalido_lanza_error():
    with patch("core.lector_comandas._llamar_api_claude_texto", return_value="esto no es JSON"):
        with pytest.raises(ValueError):
            extraer_listado_precios_de_texto("texto de la planilla")


def test_prompt_listado_precios_incluye_las_reglas_clave():
    assert "NUNCA adivinar" in PROMPT_LISTADO_PRECIOS
    assert "sin el símbolo $" in PROMPT_LISTADO_PRECIOS.lower() or "\"precio\"" in PROMPT_LISTADO_PRECIOS
    assert "confianza" in PROMPT_LISTADO_PRECIOS
    assert "varias páginas" in PROMPT_LISTADO_PRECIOS


def test_llamar_api_claude_multi_imagen_manda_todas_las_imagenes_en_un_solo_mensaje(monkeypatch):
    monkeypatch.setenv(ANTHROPIC_API_KEY_ENV_VAR, "clave-de-prueba")
    bloque_texto = SimpleNamespace(type="text", text=json.dumps(LISTADO_PRECIOS_VALIDO))
    cliente_falso = Mock()
    cliente_falso.messages.create.return_value = _respuesta_falsa([bloque_texto])

    with patch("core.lector_comandas.anthropic.Anthropic", return_value=cliente_falso):
        resultado = _llamar_api_claude_multi_imagen(
            [IMAGEN_JPEG_DE_PRUEBA, IMAGEN_PNG_DE_PRUEBA], prompt="prompt de prueba", max_tokens=1000
        )

    assert resultado == json.dumps(LISTADO_PRECIOS_VALIDO)
    contenido = cliente_falso.messages.create.call_args.kwargs["messages"][0]["content"]
    # 2 imágenes + el bloque de texto del prompt al final.
    assert len(contenido) == 3
    assert contenido[0]["type"] == "image"
    assert contenido[1]["type"] == "image"
    assert contenido[2] == {"type": "text", "text": "prompt de prueba"}


def test_llamar_api_claude_texto_manda_el_texto_y_el_prompt(monkeypatch):
    monkeypatch.setenv(ANTHROPIC_API_KEY_ENV_VAR, "clave-de-prueba")
    bloque_texto = SimpleNamespace(type="text", text=json.dumps(LISTADO_PRECIOS_VALIDO))
    cliente_falso = Mock()
    cliente_falso.messages.create.return_value = _respuesta_falsa([bloque_texto])

    with patch("core.lector_comandas.anthropic.Anthropic", return_value=cliente_falso):
        resultado = _llamar_api_claude_texto("contenido de la planilla", prompt="prompt de prueba", max_tokens=1000)

    assert resultado == json.dumps(LISTADO_PRECIOS_VALIDO)
    contenido = cliente_falso.messages.create.call_args.kwargs["messages"][0]["content"]
    assert contenido == [
        {"type": "text", "text": "contenido de la planilla"},
        {"type": "text", "text": "prompt de prueba"},
    ]


# --- extraer_pedido_de_texto: el mail de pedido de un cliente (Día) ---


PEDIDO_VALIDO = {
    "bloques": [
        {
            "empresa": "9582 FRUTAMAX",
            "sucursales": [{"sucursal": "VL", "orden_compra": "1257673", "total_bultos": 235}],
            "renglones": [
                {"codigo": "90101", "descripcion": "BANANA", "cantidades": {"VL": 225}, "confianza": "alta"}
            ],
        }
    ]
}


def test_extraer_pedido_de_texto_devuelve_el_json_parseado():
    with patch("core.lector_comandas._llamar_api_claude_texto", return_value=json.dumps(PEDIDO_VALIDO)):
        resultado = extraer_pedido_de_texto("9582 FRUTAMAX\nVL 1257673 235\n90101 BANANA 225")

    assert resultado == PEDIDO_VALIDO


def test_extraer_pedido_de_texto_usa_su_propio_prompt():
    from core.lector_comandas import MAX_TOKENS_PEDIDO_CLIENTE, PROMPT_PEDIDO_CLIENTE

    with patch("core.lector_comandas._llamar_api_claude_texto", return_value=json.dumps(PEDIDO_VALIDO)) as mock_llamada:
        extraer_pedido_de_texto("texto del mail")

    mock_llamada.assert_called_once_with("texto del mail", prompt=PROMPT_PEDIDO_CLIENTE, max_tokens=MAX_TOKENS_PEDIDO_CLIENTE)
    assert "bloques" in PROMPT_PEDIDO_CLIENTE
    assert "NUNCA adivinar" in PROMPT_PEDIDO_CLIENTE
