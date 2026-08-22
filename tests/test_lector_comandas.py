import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

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


def _cliente_falso_con_respuesta(respuesta):
    """El cliente de anthropic simulado: la llamada real va por STREAMING (para que el limite grande de salida no choque con el timeout HTTP) y la respuesta final sale de get_final_message."""
    cliente = MagicMock()
    cliente.messages.stream.return_value.__enter__.return_value.get_final_message.return_value = respuesta
    return cliente


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
    cliente_falso = _cliente_falso_con_respuesta(_respuesta_falsa([bloque_thinking, bloque_texto]))

    with patch("core.lector_comandas.anthropic.Anthropic", return_value=cliente_falso):
        resultado = _llamar_api_claude(IMAGEN_PNG_DE_PRUEBA)

    assert resultado == json.dumps(COMANDA_VALIDA)


def test_llamar_api_claude_cortada_por_max_tokens_da_error_claro(monkeypatch):
    # Regresión real: con una comanda con muchos artículos, la respuesta se
    # cortaba a mitad del JSON ("Unterminated string...") en vez de avisar
    # claramente que se quedó sin espacio.
    monkeypatch.setenv(ANTHROPIC_API_KEY_ENV_VAR, "clave-de-prueba")
    bloque_texto_cortado = SimpleNamespace(type="text", text='{"proveedor": {"nombre": "Sat')
    cliente_falso = _cliente_falso_con_respuesta(_respuesta_falsa([bloque_texto_cortado], stop_reason="max_tokens"))

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
    cliente_falso = _cliente_falso_con_respuesta(_respuesta_falsa([bloque_texto]))

    with patch("core.lector_comandas.anthropic.Anthropic", return_value=cliente_falso):
        resultado = _llamar_api_claude_multi_imagen(
            [IMAGEN_JPEG_DE_PRUEBA, IMAGEN_PNG_DE_PRUEBA], prompt="prompt de prueba", max_tokens=1000
        )

    assert resultado == json.dumps(LISTADO_PRECIOS_VALIDO)
    contenido = cliente_falso.messages.stream.call_args.kwargs["messages"][0]["content"]
    # 2 imágenes + el bloque de texto del prompt al final.
    assert len(contenido) == 3
    assert contenido[0]["type"] == "image"
    assert contenido[1]["type"] == "image"
    assert contenido[2] == {"type": "text", "text": "prompt de prueba"}


def test_llamar_api_claude_texto_manda_el_texto_y_el_prompt(monkeypatch):
    monkeypatch.setenv(ANTHROPIC_API_KEY_ENV_VAR, "clave-de-prueba")
    bloque_texto = SimpleNamespace(type="text", text=json.dumps(LISTADO_PRECIOS_VALIDO))
    cliente_falso = _cliente_falso_con_respuesta(_respuesta_falsa([bloque_texto]))

    with patch("core.lector_comandas.anthropic.Anthropic", return_value=cliente_falso):
        resultado = _llamar_api_claude_texto("contenido de la planilla", prompt="prompt de prueba", max_tokens=1000)

    assert resultado == json.dumps(LISTADO_PRECIOS_VALIDO)
    contenido = cliente_falso.messages.stream.call_args.kwargs["messages"][0]["content"]
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
    from core.lector_comandas import MAX_TOKENS_PEDIDO_CLIENTE, MENSAJE_CORTE_PEDIDO, PROMPT_PEDIDO_CLIENTE

    with patch("core.lector_comandas._llamar_api_claude_texto", return_value=json.dumps(PEDIDO_VALIDO)) as mock_llamada:
        extraer_pedido_de_texto("texto del mail")

    mock_llamada.assert_called_once_with(
        "texto del mail", prompt=PROMPT_PEDIDO_CLIENTE, max_tokens=MAX_TOKENS_PEDIDO_CLIENTE,
        mensaje_corte=MENSAJE_CORTE_PEDIDO,
    )
    assert "bloques" in PROMPT_PEDIDO_CLIENTE
    assert "NUNCA adivinar" in PROMPT_PEDIDO_CLIENTE


def test_extraer_pedido_de_imagenes_manda_todas_juntas_con_el_mismo_prompt():
    from core.lector_comandas import MAX_TOKENS_PEDIDO_CLIENTE, MENSAJE_CORTE_PEDIDO, PROMPT_PEDIDO_CLIENTE, extraer_pedido_de_imagenes

    with patch("core.lector_comandas._llamar_api_claude_multi_imagen", return_value=json.dumps(PEDIDO_VALIDO)) as mock_llamada:
        resultado = extraer_pedido_de_imagenes([b"captura-1", b"captura-2"])

    assert resultado == PEDIDO_VALIDO
    mock_llamada.assert_called_once_with(
        [b"captura-1", b"captura-2"], prompt=PROMPT_PEDIDO_CLIENTE, max_tokens=MAX_TOKENS_PEDIDO_CLIENTE,
        mensaje_corte=MENSAJE_CORTE_PEDIDO,
    )


def test_prompt_de_pedido_cuida_las_celdas_vacias_de_la_tabla():
    from core.lector_comandas import PROMPT_PEDIDO_CLIENTE

    # Lo que más fácil se lee mal en la tabla: celdas vacías y cantidades
    # corridas de columna. El prompt lo dice explícito.
    assert "celda vacía significa que esa sucursal NO pide ese artículo" in PROMPT_PEDIDO_CLIENTE
    assert "no corras cantidades de columna" in PROMPT_PEDIDO_CLIENTE
    assert "NUNCA un 0 inventado" in PROMPT_PEDIDO_CLIENTE
    # Varias capturas del mismo mail se juntan en un solo resultado.
    assert "capturas" in PROMPT_PEDIDO_CLIENTE


# --- recortar_bloque_de_empresa: mandar a la IA solo el bloque propio ---

from core.lector_comandas import MENSAJE_CORTE_PEDIDO, recortar_bloque_de_empresa  # noqa: E402

MAIL_DOS_BLOQUES = (
    "Buenas tardes, va el pedido del día:\n"
    "9582 FRUTAMAX\n"
    "Código\tProducto\tVL\tBZ\tGR\n"
    "90101\tBANANA\t225\t\t\n"
    "90102\tBATATA\t\t40\t\n"
    "\tTOTAL BULTOS\t225\t40\t\n"
    "11344 PALMALA\n"
    "Código\tProducto\tVL\tBZ\tGR\n"
    "555\tOTRA COSA\t10\t\t\n"
    "\tTOTAL BULTOS\t10\t\t\n"
    "Saludos"
)


def test_recortar_bloque_de_empresa_con_el_bloque_primero_corta_antes_del_otro():
    recortado = recortar_bloque_de_empresa(MAIL_DOS_BLOQUES, "Frutamax")

    assert recortado.startswith("9582 FRUTAMAX")
    assert "BANANA" in recortado and "BATATA" in recortado
    # El bloque ajeno (la mitad del trabajo de la IA) queda afuera.
    assert "PALMALA" not in recortado
    assert "OTRA COSA" not in recortado


def test_recortar_bloque_de_empresa_con_el_bloque_segundo_llega_hasta_el_final():
    recortado = recortar_bloque_de_empresa(MAIL_DOS_BLOQUES, "Palmala")

    assert recortado.startswith("11344 PALMALA")
    assert "OTRA COSA" in recortado
    assert "FRUTAMAX" not in recortado
    assert "BANANA" not in recortado


def test_recortar_bloque_de_empresa_sin_su_encabezado_devuelve_todo():
    # Ante la duda no se recorta: nada del mail se puede perder.
    recortado = recortar_bloque_de_empresa(MAIL_DOS_BLOQUES, "Empresa Inexistente")

    assert recortado == MAIL_DOS_BLOQUES


def test_recortar_bloque_de_empresa_sin_tabuladores_no_recorta():
    # Sin tabs (texto pegado que perdió la estructura) no hay cómo
    # distinguir una fila de producto de un encabezado: no se toca nada.
    texto_plano = "9582 FRUTAMAX\n90101 BANANA 225\n11344 PALMALA\n555 OTRA COSA 10"

    assert recortar_bloque_de_empresa(texto_plano, "Frutamax") == texto_plano


def test_recortar_bloque_de_empresa_ignora_menciones_que_no_son_encabezado():
    # "pedido para Frutamax" en el saludo NO es el arranque del bloque: si
    # se arrancara ahí, un mail con los bloques en otro orden se cortaría mal.
    texto = (
        "Va el pedido para Frutamax y Palmala:\n"
        "11344 PALMALA\n555\tOTRA COSA\t10\n"
        "9582 FRUTAMAX\n90101\tBANANA\t225\n"
    )
    recortado = recortar_bloque_de_empresa(texto, "Frutamax")

    assert recortado.startswith("9582 FRUTAMAX")
    assert "BANANA" in recortado
    assert "OTRA COSA" not in recortado


def test_max_tokens_del_lector_de_pedidos_alcanza_para_el_pedido_diario():
    from core.lector_comandas import MAX_TOKENS_PEDIDO_CLIENTE

    # ~60 renglones TODOS los días: el JSON de salida es largo siempre, no
    # es un caso raro — 16K quedaba corto en producción.
    assert MAX_TOKENS_PEDIDO_CLIENTE >= 65536


def test_lectura_de_pedido_cortada_avisa_con_el_mensaje_del_pedido(monkeypatch):
    # El mensaje viejo ("probá sacar la foto en partes") es del lector de
    # comandas y no aplica cuando el pedido entra por texto.
    monkeypatch.setenv(ANTHROPIC_API_KEY_ENV_VAR, "clave-de-prueba")
    bloque_cortado = SimpleNamespace(type="text", text='{"bloques": [')
    cliente_falso = _cliente_falso_con_respuesta(_respuesta_falsa([bloque_cortado], stop_reason="max_tokens"))

    with patch("core.lector_comandas.anthropic.Anthropic", return_value=cliente_falso):
        with pytest.raises(RuntimeError, match="lector de pedidos"):
            extraer_pedido_de_texto("el mail")

    assert "foto" not in MENSAJE_CORTE_PEDIDO


# --- Lectura de pedidos en tandas: partir, combinar, reintentar solo ---

from core.lector_comandas import (  # noqa: E402
    MAX_RENGLONES_POR_TANDA,
    RespuestaCortada,
    _combinar_lecturas,
    _es_fila_de_titulos,
    _partir_en_tandas,
)


def _texto_pedido_largo(filas):
    lineas = ["9582 FRUTAMAX", "Código\tProducto\tVL\tBZ\tGR"]
    for i in range(filas):
        lineas.append(f"9{i:04d}\tPRODUCTO {i}\t{i % 9 + 1}\t\t")
    return "\n".join(lineas)


def test_partir_en_tandas_un_pedido_chico_va_entero():
    texto = _texto_pedido_largo(60)

    assert _partir_en_tandas(texto, MAX_RENGLONES_POR_TANDA) == [texto]


def test_partir_en_tandas_reparte_parejo_y_repite_el_encabezado():
    tandas = _partir_en_tandas(_texto_pedido_largo(250), 100)

    # 250 filas con tope 100: tres tandas de ~84, no dos de 100 y una de 50.
    assert len(tandas) == 3
    for tanda in tandas:
        # Cada tanda sabe de qué empresa es y qué sucursal es cada columna.
        assert tanda.startswith("9582 FRUTAMAX\nCódigo\tProducto\tVL\tBZ\tGR")
        filas = [l for l in tanda.split("\n") if "\t" in l and not _es_fila_de_titulos(l)]
        assert 82 <= len(filas) <= 84
    # Nada se pierde ni se duplica: la unión de las tandas es el original.
    todas = [l for t in tandas for l in t.split("\n") if "\t" in l and not _es_fila_de_titulos(l)]
    originales = [l for l in _texto_pedido_largo(250).split("\n") if "\t" in l and not _es_fila_de_titulos(l)]
    assert todas == originales


def test_partir_en_tandas_sin_fila_de_titulos_no_duplica_productos():
    # Si la tabla arranca directo con un producto (sin títulos de columna),
    # esa fila NO se puede repetir en cada tanda: sería un renglón duplicado.
    lineas = ["9582 FRUTAMAX"] + [f"9{i:04d}\tPRODUCTO {i}\t{i + 1}" for i in range(6)]
    tandas = _partir_en_tandas("\n".join(lineas), 3)

    assert len(tandas) == 2
    todas = [l for t in tandas for l in t.split("\n") if "\t" in l]
    assert len(todas) == 6  # cada producto una sola vez


def test_partir_en_tandas_texto_sin_tabuladores_va_entero():
    texto = "pedido en texto plano sin estructura"

    assert _partir_en_tandas(texto, 2) == [texto]


def test_combinar_lecturas_concatena_renglones_y_completa_sucursales():
    primera = {"bloques": [{
        "empresa": "9582 FRUTAMAX",
        "sucursales": [{"sucursal": "VL", "orden_compra": "1257673", "total_bultos": None}],
        "renglones": [{"codigo": "1", "descripcion": "A", "cantidades": {"VL": 5}, "confianza": "alta"}],
    }]}
    segunda = {"bloques": [{
        "empresa": "9582 FRUTAMAX",
        "sucursales": [
            {"sucursal": "VL", "orden_compra": None, "total_bultos": 235},
            {"sucursal": "BZ", "orden_compra": "1257642", "total_bultos": 40},
        ],
        "renglones": [{"codigo": "2", "descripcion": "B", "cantidades": {"BZ": 3}, "confianza": "alta"}],
    }]}

    resultado = _combinar_lecturas([primera, segunda])

    assert len(resultado["bloques"]) == 1
    bloque = resultado["bloques"][0]
    # Renglones en el orden del mail; la OC de una tanda y el total de la
    # otra se completan entre sí.
    assert [r["codigo"] for r in bloque["renglones"]] == ["1", "2"]
    assert bloque["sucursales"][0] == {"sucursal": "VL", "orden_compra": "1257673", "total_bultos": 235}
    assert bloque["sucursales"][1]["sucursal"] == "BZ"


def _lector_falso_por_tanda(texto, prompt, max_tokens, mensaje_corte=None):
    """Simula la IA: devuelve un renglón por cada fila de producto del texto recibido."""
    filas = [l for l in texto.split("\n") if "\t" in l and not _es_fila_de_titulos(l)]
    bloque = {
        "empresa": "9582 FRUTAMAX",
        "sucursales": [{"sucursal": "VL", "orden_compra": None, "total_bultos": None}],
        "renglones": [
            {"codigo": l.split("\t")[0], "descripcion": l.split("\t")[1], "cantidades": {"VL": 1}, "confianza": "alta"}
            for l in filas
        ],
    }
    return json.dumps({"bloques": [bloque]})


def test_extraer_pedido_de_texto_largo_lee_en_tandas_y_junta_todo():
    with patch("core.lector_comandas._llamar_api_claude_texto", side_effect=_lector_falso_por_tanda) as mock_llamada:
        resultado = extraer_pedido_de_texto(_texto_pedido_largo(250))

    # Tres llamadas (una por tanda) y NINGÚN renglón perdido ni duplicado.
    assert mock_llamada.call_count == 3
    assert len(resultado["bloques"]) == 1
    codigos = [r["codigo"] for r in resultado["bloques"][0]["renglones"]]
    assert len(codigos) == 250
    assert codigos == [f"9{i:04d}" for i in range(250)]


def test_extraer_pedido_de_texto_reintenta_solo_partiendo_mas_chico():
    # La primera llamada (el pedido entero) se corta: el sistema parte en
    # tandas más chicas y reintenta SOLO, sin que nadie toque nada.
    llamadas = []

    def _falso_con_corte(texto, prompt, max_tokens, mensaje_corte=None):
        llamadas.append(texto)
        if len(llamadas) == 1:
            raise RespuestaCortada("se cortó")
        return _lector_falso_por_tanda(texto, prompt, max_tokens, mensaje_corte)

    with patch("core.lector_comandas._llamar_api_claude_texto", side_effect=_falso_con_corte):
        resultado = extraer_pedido_de_texto(_texto_pedido_largo(80))

    # 1 corte + 2 mitades leídas.
    assert len(llamadas) == 3
    assert len(resultado["bloques"][0]["renglones"]) == 80


def test_extraer_pedido_de_texto_si_ni_la_tanda_minima_entra_recien_ahi_error():
    with patch("core.lector_comandas._llamar_api_claude_texto", side_effect=RespuestaCortada("se cortó")):
        with pytest.raises(RespuestaCortada):
            extraer_pedido_de_texto(_texto_pedido_largo(8))
