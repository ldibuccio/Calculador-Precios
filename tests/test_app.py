import base64
import io
from datetime import date, timedelta
from unittest.mock import patch

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import DATABASE_URL_ENV_VAR, obtener_conexion
from app.main import (
    SECTORES,
    _ICONO_INICIO,
    _fecha_de_corte_limpieza_fotos,
    _formatear_bytes,
    _formatear_fecha_corta,
    _formatear_kilos,
    _formatear_moneda,
    _formatear_numero,
    _generar_preview_foto,
    _sufijo_unidad,
    app,
    templates,
)

cliente = TestClient(app)


def test_formatear_numero_saca_decimales_de_sobra():
    assert _formatear_numero(16.0) == "16"
    assert _formatear_numero(16) == "16"
    assert _formatear_numero(16.5) == "16.5"
    assert _formatear_numero(16.25) == "16.25"
    assert _formatear_numero(None) == ""


def test_formatear_fecha_corta_muestra_dd_mm():
    assert _formatear_fecha_corta(date(2026, 8, 6)) == "06/08"
    assert _formatear_fecha_corta(None) == ""


def test_formatear_moneda_usa_signo_pesos_y_puntos_para_miles():
    assert _formatear_moneda(20000) == "$20.000"
    assert _formatear_moneda(50000) == "$50.000"
    assert _formatear_moneda(1500000) == "$1.500.000"
    assert _formatear_moneda(500) == "$500"
    assert _formatear_moneda(None) == ""


def test_formatear_moneda_redondea_al_peso_entero():
    assert _formatear_moneda(45000.4) == "$45.000"
    assert _formatear_moneda(45000.6) == "$45.001"


def test_formatear_kilos_muestra_entero_sin_decimales_ni_separador():
    assert _formatear_kilos(1500.5) == "1500"
    assert _formatear_kilos(16.0) == "16"
    assert _formatear_kilos(16) == "16"
    assert _formatear_kilos(1500) == "1500"
    assert _formatear_kilos(None) == ""


def test_sufijo_unidad_devuelve_la_letra_corta():
    assert _sufijo_unidad("kilo") == "k"
    assert _sufijo_unidad("unidad") == "u"
    assert _sufijo_unidad("cubeta") == "c"
    assert _sufijo_unidad(None) == ""
    assert _sufijo_unidad("otracosa") == ""


def test_formatear_bytes_elige_la_unidad_que_queda_natural():
    assert _formatear_bytes(0) == "0 bytes"
    assert _formatear_bytes(500) == "500 bytes"
    assert _formatear_bytes(907397) == "886 KB"  # caso real confirmado en producción
    assert _formatear_bytes(356000000) == "339,5 MB"
    assert _formatear_bytes(1288490188) == "1,2 GB"
    assert _formatear_bytes(None) == ""


def test_fecha_de_corte_limpieza_fotos_es_3_anios_atras():
    with patch("app.main._hoy_argentina", return_value=date(2026, 8, 15)):
        assert _fecha_de_corte_limpieza_fotos() == date(2023, 8, 15)


def test_fecha_de_corte_limpieza_fotos_29_de_febrero_bisiesto():
    # Regresión: hace 3 años (2024, bisiesto) no siempre hay un 29/2 — 2021 no lo es.
    with patch("app.main._hoy_argentina", return_value=date(2024, 2, 29)):
        assert _fecha_de_corte_limpieza_fotos() == date(2021, 2, 28)


def test_raiz_devuelve_estado_ok():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_salud_db_devuelve_la_cantidad_de_articulos():
    with patch("app.main.contar_articulos", return_value=29):
        respuesta = cliente.get("/salud/db")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"articulos": 29}


def test_salud_db_sin_database_url_devuelve_error_claro():
    with patch("app.main.contar_articulos", side_effect=RuntimeError(f"Falta configurar {DATABASE_URL_ENV_VAR}")):
        respuesta = cliente.get("/salud/db")

    assert respuesta.status_code == 500
    assert DATABASE_URL_ENV_VAR in respuesta.json()["detail"]


def test_salud_db_error_de_conexion_devuelve_500():
    with patch("app.main.contar_articulos", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/salud/db")

    assert respuesta.status_code == 500


def test_obtener_conexion_sin_database_url_lanza_error_claro(monkeypatch):
    monkeypatch.delenv(DATABASE_URL_ENV_VAR, raising=False)

    with pytest.raises(RuntimeError, match=DATABASE_URL_ENV_VAR):
        obtener_conexion()


ARTICULOS_DE_PRUEBA = [
    {"id": 1, "nombre": "Frutilla", "unidad_compra": None, "contenido_referencia": None, "grupo": "fruta"},
    {"id": 2, "nombre": "Mango", "unidad_compra": None, "contenido_referencia": None, "grupo": None},
]


def test_ver_articulos_lista_vacia():
    with patch("app.main.listar_articulos", return_value=[]):
        respuesta = cliente.get("/articulos")

    assert respuesta.status_code == 200
    assert "No hay artículos cargados todavía." in respuesta.text


def test_ver_articulos_error_de_base_muestra_pagina_de_error_clara():
    with patch("app.main.listar_articulos", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/articulos")

    assert respuesta.status_code == 500
    assert "No se pudo leer el catálogo" in respuesta.text


def test_ver_articulos_muestra_solo_nombre():
    with patch("app.main.listar_articulos", return_value=ARTICULOS_DE_PRUEBA):
        respuesta = cliente.get("/articulos")

    assert respuesta.status_code == 200
    assert "Frutilla" in respuesta.text
    assert "Mango" in respuesta.text
    assert "/articulos/1/editar" in respuesta.text
    assert "/articulos/1/eliminar" in respuesta.text
    # codigo_interno es del cliente Día, no del artículo: no debe pedirse ni mostrarse acá
    assert "codigo_interno" not in respuesta.text
    # unidad_venta y envase ya no viven en articulos: no deben aparecer en la página
    assert "unidad_venta" not in respuesta.text
    assert "envase" not in respuesta.text.lower()
    # merma ya no se pide ni se muestra en esta pantalla
    assert "merma" not in respuesta.text.lower()


def test_ver_articulos_muestra_columna_grupo_con_sin_clasificar():
    with patch("app.main.listar_articulos", return_value=ARTICULOS_DE_PRUEBA):
        respuesta = cliente.get("/articulos")

    assert respuesta.status_code == 200
    assert "<th>Grupo</th>" in respuesta.text
    assert "Fruta" in respuesta.text
    assert "Sin clasificar" in respuesta.text


def test_ver_articulos_incluye_link_a_inicio():
    with patch("app.main.listar_articulos", return_value=[]):
        respuesta = cliente.get("/articulos")

    assert respuesta.status_code == 200
    assert 'href="/inicio"' in respuesta.text


def test_agregar_articulo_exitoso_redirige_a_articulos():
    with patch("app.main.crear_articulo") as mock_crear:
        respuesta = cliente.post(
            "/articulos/nuevo",
            data={"nombre": "Kiwi", "unidad_compra": "unidad", "contenido_referencia": "10"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/articulos"
    mock_crear.assert_called_once_with("Kiwi", "unidad", 10.0, None)


def test_agregar_articulo_sin_contenido_referencia_guarda_none():
    with patch("app.main.crear_articulo") as mock_crear:
        respuesta = cliente.post(
            "/articulos/nuevo",
            data={"nombre": "Kiwi", "unidad_compra": "kilo", "contenido_referencia": ""},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with("Kiwi", "kilo", None, None)


def test_agregar_articulo_con_grupo_valido_lo_guarda():
    with patch("app.main.crear_articulo") as mock_crear:
        respuesta = cliente.post(
            "/articulos/nuevo",
            data={"nombre": "Kiwi", "unidad_compra": "kilo", "contenido_referencia": "", "grupo": "fruta"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with("Kiwi", "kilo", None, "fruta")


def test_agregar_articulo_con_grupo_pesada_lo_guarda():
    with patch("app.main.crear_articulo") as mock_crear:
        respuesta = cliente.post(
            "/articulos/nuevo",
            data={"nombre": "Zapallo", "unidad_compra": "kilo", "contenido_referencia": "", "grupo": "pesada"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with("Zapallo", "kilo", None, "pesada")


def test_agregar_articulo_grupo_invalido_muestra_error():
    with patch("app.main.crear_articulo") as mock_crear, patch("app.main.listar_articulos", return_value=[]):
        respuesta = cliente.post(
            "/articulos/nuevo",
            data={"nombre": "Kiwi", "unidad_compra": "kilo", "grupo": "lacteo"},
        )

    assert respuesta.status_code == 400
    assert "grupo válido" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_articulo_nombre_vacio_muestra_error():
    with patch("app.main.crear_articulo") as mock_crear, patch("app.main.listar_articulos", return_value=[]):
        respuesta = cliente.post("/articulos/nuevo", data={"nombre": "   ", "unidad_compra": "kilo"})

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_articulo_nombre_string_vacio_muestra_error_prolijo_no_422():
    # Regresión: un campo de texto Form(...) vacío ("" y no solo espacios) hacía
    # que FastAPI devolviera un 422 crudo en vez de nuestro error prolijo.
    with patch("app.main.crear_articulo") as mock_crear, patch("app.main.listar_articulos", return_value=[]):
        respuesta = cliente.post("/articulos/nuevo", data={"nombre": "", "unidad_compra": "kilo"})

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_articulo_unidad_compra_invalida_muestra_error():
    with patch("app.main.crear_articulo") as mock_crear, patch("app.main.listar_articulos", return_value=[]):
        respuesta = cliente.post("/articulos/nuevo", data={"nombre": "Kiwi", "unidad_compra": "litro"})

    assert respuesta.status_code == 400
    assert "unidad de compra válida" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_articulo_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.crear_articulo", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_articulos", return_value=[]),
    ):
        respuesta = cliente.post("/articulos/nuevo", data={"nombre": "Kiwi", "unidad_compra": "kilo"})

    assert respuesta.status_code == 500
    assert "No se pudo guardar" in respuesta.text


ARTICULO_DE_PRUEBA = {
    "id": 1,
    "nombre": "Frutilla",
    "unidad_compra": "cubeta",
    "contenido_referencia": 12,
    "grupo": "fruta",
}


def test_ver_editar_articulo_muestra_datos_precargados():
    with patch("app.main.obtener_articulo", return_value=ARTICULO_DE_PRUEBA):
        respuesta = cliente.get("/articulos/1/editar")

    assert respuesta.status_code == 200
    assert "Frutilla" in respuesta.text
    assert 'action="/articulos/1/editar"' in respuesta.text
    assert "merma" not in respuesta.text.lower()
    assert '<option value="fruta" selected>Fruta</option>' in respuesta.text


def test_ver_editar_articulo_inexistente_da_404():
    with patch("app.main.obtener_articulo", return_value=None):
        respuesta = cliente.get("/articulos/999/editar")

    assert respuesta.status_code == 404


def test_ver_editar_articulo_error_de_base_da_500():
    with patch("app.main.obtener_articulo", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/articulos/1/editar")

    assert respuesta.status_code == 500


def test_editar_articulo_exitoso_redirige_a_articulos():
    with patch("app.main.actualizar_articulo") as mock_actualizar:
        respuesta = cliente.post(
            "/articulos/1/editar",
            data={"nombre": "Frutilla Premium", "unidad_compra": "cubeta", "contenido_referencia": "12"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/articulos"
    mock_actualizar.assert_called_once_with(1, "Frutilla Premium", "cubeta", 12.0, None)


def test_editar_articulo_con_grupo_valido_lo_guarda():
    with patch("app.main.actualizar_articulo") as mock_actualizar:
        respuesta = cliente.post(
            "/articulos/1/editar",
            data={"nombre": "Frutilla", "unidad_compra": "cubeta", "contenido_referencia": "12", "grupo": "hortaliza"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_actualizar.assert_called_once_with(1, "Frutilla", "cubeta", 12.0, "hortaliza")


def test_editar_articulo_grupo_invalido_muestra_error():
    with patch("app.main.actualizar_articulo") as mock_actualizar:
        respuesta = cliente.post(
            "/articulos/1/editar",
            data={"nombre": "Frutilla", "unidad_compra": "cubeta", "grupo": "lacteo"},
        )

    assert respuesta.status_code == 400
    assert "grupo válido" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_articulo_nombre_vacio_muestra_error():
    with patch("app.main.actualizar_articulo") as mock_actualizar:
        respuesta = cliente.post("/articulos/1/editar", data={"nombre": "   ", "unidad_compra": "kilo"})

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_articulo_unidad_compra_invalida_muestra_error():
    with patch("app.main.actualizar_articulo") as mock_actualizar:
        respuesta = cliente.post("/articulos/1/editar", data={"nombre": "Frutilla", "unidad_compra": "litro"})

    assert respuesta.status_code == 400
    assert "unidad de compra válida" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_articulo_error_de_base_muestra_mensaje_claro():
    with patch("app.main.actualizar_articulo", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/articulos/1/editar", data={"nombre": "Frutilla", "unidad_compra": "kilo"})

    assert respuesta.status_code == 500
    assert "No se pudo guardar" in respuesta.text


def test_eliminar_articulo_exitoso_redirige_a_articulos():
    with patch("app.main.desactivar_articulo") as mock_desactivar:
        respuesta = cliente.post("/articulos/1/eliminar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/articulos"
    mock_desactivar.assert_called_once_with(1)


def test_eliminar_articulo_no_borra_la_fila_solo_marca_inactivo():
    # desactivar_articulo (borrado lógico) hace UPDATE activo=false, no DELETE.
    # Este test confirma que la ruta llama a esa función y no a otra.
    with patch("app.main.desactivar_articulo") as mock_desactivar:
        cliente.post("/articulos/1/eliminar", follow_redirects=False)

    mock_desactivar.assert_called_once()


def test_eliminar_articulo_error_de_base_da_500():
    with patch("app.main.desactivar_articulo", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/articulos/1/eliminar")

    assert respuesta.status_code == 500


CLIENTES_DE_PRUEBA = [
    {"id": 1, "nombre": "Día", "descuento": 23.0, "adicionales": 0.0, "utilidad_objetivo": 20.0},
    {"id": 2, "nombre": "Otro cliente", "descuento": 15.0, "adicionales": 10.5, "utilidad_objetivo": 10.0},
]


def test_ver_clientes_lista_vacia():
    with patch("app.main.listar_clientes", return_value=[]):
        respuesta = cliente.get("/clientes")

    assert respuesta.status_code == 200
    assert "No hay clientes cargados todavía." in respuesta.text


def test_ver_clientes_error_de_base_muestra_pagina_de_error_clara():
    with patch("app.main.listar_clientes", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/clientes")

    assert respuesta.status_code == 500
    assert "No se pudo leer los clientes" in respuesta.text


def test_ver_clientes_muestra_nombre_descuentos_adicionales_y_utilidad_como_porcentaje():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/clientes")

    assert respuesta.status_code == 200
    assert "Día" in respuesta.text
    assert "Descuentos" in respuesta.text
    assert "Adicionales" in respuesta.text
    assert "23.0%" in respuesta.text
    assert "20.0%" in respuesta.text
    # "Otro cliente" tiene adicionales (10.5%, ej. IVA) además de descuentos.
    assert "10.5%" in respuesta.text
    assert "/clientes/1/editar" in respuesta.text
    assert "/clientes/1/eliminar" in respuesta.text


def test_ver_clientes_sin_adicionales_muestra_cero_por_ciento():
    # Regla explícita: si no tiene ninguna tasa de tipo suma, se muestra
    # "0%" (no una celda vacía ni un guión que confunda con "no se sabe").
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/clientes")

    assert respuesta.status_code == 200
    assert "0.0%" in respuesta.text


def test_ver_clientes_incluye_link_a_inicio():
    with patch("app.main.listar_clientes", return_value=[]):
        respuesta = cliente.get("/clientes")

    assert respuesta.status_code == 200
    assert 'href="/inicio"' in respuesta.text


def test_ver_agregar_cliente_muestra_formulario_vacio():
    respuesta = cliente.get("/clientes/nuevo")

    assert respuesta.status_code == 200
    assert 'action="/clientes/nuevo"' in respuesta.text
    # Regresión: los títulos y ejemplos de cada grupo de tasas, para que
    # quede claro qué va en cada uno.
    assert "Adicionales" in respuesta.text
    assert "IVA, premios" in respuesta.text
    assert "Descuentos" in respuesta.text
    assert "logística, flete" in respuesta.text
    assert 'id="utilidad_objetivo"' in respuesta.text
    assert '+ Agregar tasa Adicional' in respuesta.text
    assert '+ Agregar tasa de Descuento' in respuesta.text


def test_agregar_cliente_con_tasas_redirige_a_clientes():
    with patch("app.main.crear_cliente", return_value=5) as mock_crear:
        respuesta = cliente.post(
            "/clientes/nuevo",
            data={
                "nombre": "Vea",
                "utilidad_objetivo": "12",
                "cantidad_tasa_sumas": "1",
                "tasa_suma_0_nombre_original": "",
                "tasa_suma_0_valor_original": "",
                "tasa_suma_0_nombre": "IVA",
                "tasa_suma_0_valor": "21",
                "cantidad_tasa_restas": "1",
                "tasa_resta_0_nombre_original": "",
                "tasa_resta_0_valor_original": "",
                "tasa_resta_0_nombre": "Flete",
                "tasa_resta_0_valor": "4",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/clientes"
    mock_crear.assert_called_once_with(
        "Vea", [{"nombre": "IVA", "valor": 0.21}], [{"nombre": "Flete", "valor": 0.04}], 0.12
    )


def test_agregar_cliente_sin_tasas_redirige_a_clientes():
    # Las tasas son opcionales: un cliente se puede cargar solo con nombre
    # y utilidad, sin ninguna tasa todavía.
    with patch("app.main.crear_cliente", return_value=5) as mock_crear:
        respuesta = cliente.post(
            "/clientes/nuevo",
            data={"nombre": "Vea", "utilidad_objetivo": "12"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with("Vea", [], [], 0.12)


def test_agregar_cliente_nombre_vacio_muestra_error():
    with patch("app.main.crear_cliente") as mock_crear:
        respuesta = cliente.post("/clientes/nuevo", data={"nombre": "   ", "utilidad_objetivo": "12"})

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_cliente_utilidad_fuera_de_rango_muestra_error():
    with patch("app.main.crear_cliente") as mock_crear:
        respuesta = cliente.post("/clientes/nuevo", data={"nombre": "Vea", "utilidad_objetivo": "150"})

    assert respuesta.status_code == 400
    assert "entre 0 y 100" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_cliente_utilidad_no_numerica_muestra_error():
    with patch("app.main.crear_cliente") as mock_crear:
        respuesta = cliente.post("/clientes/nuevo", data={"nombre": "Vea", "utilidad_objetivo": "abc"})

    assert respuesta.status_code == 400
    assert "tiene que ser un número" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_cliente_tasa_con_nombre_sin_porcentaje_muestra_error():
    # Fila a medio completar (nombre sin %, o al revés): no se guarda nada
    # dudoso, se avisa para que la complete o la saque.
    with patch("app.main.crear_cliente") as mock_crear:
        respuesta = cliente.post(
            "/clientes/nuevo",
            data={
                "nombre": "Vea",
                "utilidad_objetivo": "12",
                "cantidad_tasa_sumas": "1",
                "tasa_suma_0_nombre": "IVA",
                "tasa_suma_0_valor": "",
            },
        )

    assert respuesta.status_code == 400
    assert "Completá el nombre y el porcentaje" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_cliente_fila_de_tasa_completamente_vacia_se_ignora():
    # El usuario tocó "+ Agregar tasa" pero no llegó a cargar nada — no
    # tiene que bloquear el guardado.
    with patch("app.main.crear_cliente", return_value=5) as mock_crear:
        respuesta = cliente.post(
            "/clientes/nuevo",
            data={
                "nombre": "Vea",
                "utilidad_objetivo": "12",
                "cantidad_tasa_sumas": "1",
                "tasa_suma_0_nombre": "",
                "tasa_suma_0_valor": "",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with("Vea", [], [], 0.12)


def test_agregar_cliente_error_de_base_muestra_mensaje_claro():
    with patch("app.main.crear_cliente", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/clientes/nuevo", data={"nombre": "Vea", "utilidad_objetivo": "12"})

    assert respuesta.status_code == 500
    assert "No se pudo guardar" in respuesta.text


CLIENTE_DE_PRUEBA = {"id": 1, "nombre": "Día"}

CONCEPTOS_EDITABLES_DE_PRUEBA = {
    "tasas_suma": [{"nombre": "IVA", "valor_pct": 21.0}],
    "tasas_resta": [{"nombre": "Flete", "valor_pct": 4.0}],
    "utilidad_pct": 20.0,
}


def test_ver_editar_cliente_muestra_datos_precargados():
    with (
        patch("app.main.obtener_cliente", return_value=CLIENTE_DE_PRUEBA),
        patch("app.main.listar_conceptos_editables_por_cliente", return_value=CONCEPTOS_EDITABLES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/clientes/1/editar")

    assert respuesta.status_code == 200
    assert "Día" in respuesta.text
    assert 'action="/clientes/1/editar"' in respuesta.text
    assert 'value="IVA"' in respuesta.text
    assert 'value="21.0"' in respuesta.text
    assert 'value="Flete"' in respuesta.text
    assert 'value="4.0"' in respuesta.text
    assert 'value="20.0"' in respuesta.text
    # Regresión: nombre_original/valor_original viajan ocultos, son el
    # punto de partida contra el que se compara al guardar.
    assert 'name="tasa_suma_0_nombre_original" value="IVA"' in respuesta.text
    assert 'name="tasa_resta_0_nombre_original" value="Flete"' in respuesta.text
    assert 'name="utilidad_original" value="20.0"' in respuesta.text
    assert "Dar de baja esta tasa" in respuesta.text


def test_ver_editar_cliente_inexistente_da_404():
    with patch("app.main.obtener_cliente", return_value=None):
        respuesta = cliente.get("/clientes/999/editar")

    assert respuesta.status_code == 404


def test_ver_editar_cliente_error_de_base_da_500():
    with patch("app.main.obtener_cliente", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/clientes/1/editar")

    assert respuesta.status_code == 500


def test_ver_editar_cliente_error_al_leer_conceptos_da_500():
    with (
        patch("app.main.obtener_cliente", return_value=CLIENTE_DE_PRUEBA),
        patch("app.main.listar_conceptos_editables_por_cliente", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.get("/clientes/1/editar")

    assert respuesta.status_code == 500


def _datos_editar_cliente(**overrides):
    datos = {
        "nombre": "Día",
        "utilidad_objetivo": "20",
        "utilidad_original": "20",
        "cantidad_tasa_sumas": "1",
        "tasa_suma_0_nombre_original": "IVA",
        "tasa_suma_0_valor_original": "21",
        "tasa_suma_0_nombre": "IVA",
        "tasa_suma_0_valor": "21",
        "cantidad_tasa_restas": "1",
        "tasa_resta_0_nombre_original": "Flete",
        "tasa_resta_0_valor_original": "4",
        "tasa_resta_0_nombre": "Flete",
        "tasa_resta_0_valor": "4",
    }
    datos.update(overrides)
    return datos


def test_editar_cliente_sin_ningun_cambio_no_genera_filas_nuevas():
    # Regresión explícita: si nada se tocó, no hay que agregar filas de
    # historial de más.
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post("/clientes/1/editar", data=_datos_editar_cliente(), follow_redirects=False)

    assert respuesta.status_code == 303
    mock_actualizar.assert_called_once_with(1, "Día", [])


def test_editar_cliente_tasa_editada_genera_fila_nueva_sin_pisar_la_vieja():
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post(
            "/clientes/1/editar",
            data=_datos_editar_cliente(tasa_resta_0_valor="5"),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_actualizar.assert_called_once_with(1, "Día", [{"nombre_parametro": "Flete", "tipo": "resta", "valor": 0.05}])


def test_editar_cliente_tasa_nueva_se_agrega():
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post(
            "/clientes/1/editar",
            data=_datos_editar_cliente(
                cantidad_tasa_sumas="2",
                tasa_suma_1_nombre_original="",
                tasa_suma_1_valor_original="",
                tasa_suma_1_nombre="Premio",
                tasa_suma_1_valor="2",
            ),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_actualizar.assert_called_once_with(1, "Día", [{"nombre_parametro": "Premio", "tipo": "suma", "valor": 0.02}])


def test_editar_cliente_tasa_dada_de_baja_genera_fila_en_cero():
    # Regla de oro: nunca se borra el historial, se agrega una fila en 0
    # vigente desde hoy — los cálculos pasados siguen viendo el valor viejo.
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post(
            "/clientes/1/editar",
            data=_datos_editar_cliente(tasa_resta_0_baja="on"),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_actualizar.assert_called_once_with(1, "Día", [{"nombre_parametro": "Flete", "tipo": "resta", "valor": 0.0}])


def test_editar_cliente_tasa_renombrada_da_de_baja_la_vieja_y_alta_la_nueva():
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post(
            "/clientes/1/editar",
            data=_datos_editar_cliente(tasa_resta_0_nombre="Flete y logística"),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_actualizar.assert_called_once_with(
        1,
        "Día",
        [
            {"nombre_parametro": "Flete", "tipo": "resta", "valor": 0.0},
            {"nombre_parametro": "Flete y logística", "tipo": "resta", "valor": 0.04},
        ],
    )


def test_editar_cliente_utilidad_editada_genera_fila_nueva():
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post(
            "/clientes/1/editar",
            data=_datos_editar_cliente(utilidad_objetivo="25"),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_actualizar.assert_called_once_with(
        1, "Día", [{"nombre_parametro": "utilidad_objetivo", "tipo": "utilidad", "valor": 0.25}]
    )


def test_editar_cliente_nombre_vacio_muestra_error():
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post("/clientes/1/editar", data=_datos_editar_cliente(nombre="   "))

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_cliente_error_de_base_muestra_mensaje_claro():
    with patch("app.main.actualizar_cliente", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/clientes/1/editar", data=_datos_editar_cliente())

    assert respuesta.status_code == 500
    assert "No se pudo guardar" in respuesta.text


def test_eliminar_cliente_exitoso_redirige_a_clientes():
    with patch("app.main.desactivar_cliente") as mock_desactivar:
        respuesta = cliente.post("/clientes/1/eliminar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/clientes"
    mock_desactivar.assert_called_once_with(1)


def test_eliminar_cliente_error_de_base_da_500():
    with patch("app.main.desactivar_cliente", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/clientes/1/eliminar")

    assert respuesta.status_code == 500


CLIENTES_PARA_SELECTOR = [{"id": 1, "nombre": "Día"}, {"id": 2, "nombre": "Vea"}]

FICHAS_DE_PRUEBA = [
    {
        "id": 10,
        "articulo_nombre": "Mango",
        "envase_nombre": "Caja Chica Día",
        "contenido_caja": 10,
        "unidad_venta": "unidad",
        "envase_variable": True,
        "nombre_cliente": "MANGO",
        "codigo_cliente": "225863",
    },
    {
        "id": 11,
        "articulo_nombre": "Sandía",
        "envase_nombre": None,
        "contenido_caja": 18,
        "unidad_venta": "kilo",
        "envase_variable": False,
        "nombre_cliente": None,
        "codigo_cliente": None,
    },
]


def test_ver_fichas_sin_cliente_elegido_pide_elegir_uno():
    with patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR):
        respuesta = cliente.get("/fichas")

    assert respuesta.status_code == 200
    assert "Elegí un cliente" in respuesta.text
    assert "Día" in respuesta.text  # aparece como opción del selector


def test_ver_fichas_error_al_leer_clientes_muestra_error_claro():
    with patch("app.main.listar_clientes", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/fichas")

    assert respuesta.status_code == 500
    assert "No se pudo leer los clientes" in respuesta.text


def test_ver_fichas_con_cliente_muestra_la_lista():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_DE_PRUEBA),
    ):
        respuesta = cliente.get("/fichas?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Mango" in respuesta.text
    assert "Caja Chica Día" in respuesta.text
    assert "Sandía" in respuesta.text
    assert "Sin envase" in respuesta.text
    assert "/fichas/10/editar" in respuesta.text
    assert "/fichas/nueva?cliente_id=1" in respuesta.text
    assert "Variable" in respuesta.text
    assert "Fijo" in respuesta.text
    # Alias fusionados desde la vieja /conversion: se muestran en la tabla.
    assert "<td>MANGO</td>" in respuesta.text
    assert "<td>225863</td>" in respuesta.text
    # Sandía no tiene alias cargado: se muestra "-", no vacío ni error.
    assert respuesta.text.count("<td>-</td>") >= 2


def test_ver_fichas_error_al_leer_fichas_muestra_error_claro():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR),
        patch("app.main.listar_fichas_por_cliente", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.get("/fichas?cliente_id=1")

    assert respuesta.status_code == 500
    assert "No se pudieron leer las fichas" in respuesta.text


ARTICULOS_SIN_FICHA = [{"id": 5, "nombre": "Kiwi"}]
ENVASES_DEL_CLIENTE = [{"id": 100, "nombre": "Caja Chica Día"}]


def test_ver_nueva_ficha_muestra_formulario():
    with (
        patch("app.main.listar_articulos_sin_ficha", return_value=ARTICULOS_SIN_FICHA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.get("/fichas/nueva?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Kiwi" in respuesta.text
    assert "Caja Chica Día" in respuesta.text
    assert 'id="nombre_cliente" name="nombre_cliente"' in respuesta.text
    assert 'id="codigo_cliente" name="codigo_cliente"' in respuesta.text


def test_ver_nueva_ficha_sin_cliente_id_da_422():
    respuesta = cliente.get("/fichas/nueva")
    assert respuesta.status_code == 422


def test_ver_nueva_ficha_sin_articulos_disponibles_muestra_mensaje():
    with (
        patch("app.main.listar_articulos_sin_ficha", return_value=[]),
        patch("app.main.listar_envases_por_cliente", return_value=[]),
    ):
        respuesta = cliente.get("/fichas/nueva?cliente_id=1")

    assert respuesta.status_code == 200
    assert "ya tienen ficha para este cliente" in respuesta.text


def test_ver_nueva_ficha_error_de_base_da_500():
    with patch("app.main.listar_articulos_sin_ficha", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/fichas/nueva?cliente_id=1")

    assert respuesta.status_code == 500


def test_agregar_ficha_exitosa_redirige_a_fichas_del_cliente():
    with patch("app.main.crear_ficha") as mock_crear:
        respuesta = cliente.post(
            "/fichas/nueva",
            data={
                "cliente_id": "1",
                "articulo_id": "5",
                "envase_id": "100",
                "contenido_caja": "10",
                "unidad_venta": "unidad",
                "envase_variable": "si",
                "nombre_cliente": "MANZ ROJ ELE",
                "codigo_cliente": "90039",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/fichas?cliente_id=1"
    mock_crear.assert_called_once_with(5, 1, 100, 10.0, "unidad", True, "MANZ ROJ ELE", "90039")


def test_agregar_ficha_sin_envase_con_contenido_caja_exitosa():
    with patch("app.main.crear_ficha") as mock_crear:
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "envase_id": "", "contenido_caja": "12", "unidad_venta": "cubeta"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    # Sin nombre_cliente/codigo_cliente en el form: quedan en None (son opcionales).
    mock_crear.assert_called_once_with(5, 1, None, 12.0, "cubeta", False, None, None)


def test_agregar_ficha_sin_envase_sin_contenido_caja_muestra_error():
    with (
        patch("app.main.crear_ficha") as mock_crear,
        patch("app.main.listar_articulos_sin_ficha", return_value=ARTICULOS_SIN_FICHA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "envase_id": "", "contenido_caja": "", "unidad_venta": "kilo"},
        )

    assert respuesta.status_code == 400
    assert "obligatorio" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_ficha_sin_articulo_muestra_error():
    with (
        patch("app.main.crear_ficha") as mock_crear,
        patch("app.main.listar_articulos_sin_ficha", return_value=ARTICULOS_SIN_FICHA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "", "envase_id": "", "contenido_caja": "", "unidad_venta": "kilo"},
        )

    assert respuesta.status_code == 400
    assert "Elegí un artículo" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_ficha_con_envase_sin_contenido_caja_muestra_error():
    with (
        patch("app.main.crear_ficha") as mock_crear,
        patch("app.main.listar_articulos_sin_ficha", return_value=ARTICULOS_SIN_FICHA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "envase_id": "100", "contenido_caja": "", "unidad_venta": "kilo"},
        )

    assert respuesta.status_code == 400
    assert "obligatorio" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_ficha_contenido_caja_no_numerico_muestra_error():
    with (
        patch("app.main.crear_ficha") as mock_crear,
        patch("app.main.listar_articulos_sin_ficha", return_value=ARTICULOS_SIN_FICHA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "envase_id": "100", "contenido_caja": "abc", "unidad_venta": "kilo"},
        )

    assert respuesta.status_code == 400
    assert "tiene que ser un número" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_ficha_contenido_caja_cero_muestra_error():
    with (
        patch("app.main.crear_ficha") as mock_crear,
        patch("app.main.listar_articulos_sin_ficha", return_value=ARTICULOS_SIN_FICHA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "envase_id": "100", "contenido_caja": "0", "unidad_venta": "kilo"},
        )

    assert respuesta.status_code == 400
    assert "mayor a cero" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_ficha_unidad_venta_invalida_muestra_error():
    with (
        patch("app.main.crear_ficha") as mock_crear,
        patch("app.main.listar_articulos_sin_ficha", return_value=ARTICULOS_SIN_FICHA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "envase_id": "", "contenido_caja": "", "unidad_venta": "litro"},
        )

    assert respuesta.status_code == 400
    assert "unidad de venta válida" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_ficha_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.crear_ficha", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_articulos_sin_ficha", return_value=ARTICULOS_SIN_FICHA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "envase_id": "", "contenido_caja": "10", "unidad_venta": "kilo"},
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar la ficha" in respuesta.text


FICHA_DE_PRUEBA = {
    "id": 10,
    "cliente_id": 1,
    "articulo_id": 5,
    "articulo_nombre": "Mango",
    "envase_id": 100,
    "contenido_caja": 10,
    "unidad_venta": "unidad",
    "envase_variable": True,
    "nombre_cliente": "MANGO",
    "codigo_cliente": "225863",
}


def test_ver_editar_ficha_muestra_datos_precargados():
    with (
        patch("app.main.obtener_ficha", return_value=FICHA_DE_PRUEBA),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.get("/fichas/10/editar")

    assert respuesta.status_code == 200
    assert "Mango" in respuesta.text
    assert 'action="/fichas/10/editar"' in respuesta.text
    assert "checked" in respuesta.text  # envase_variable=True precargado
    # Alias fusionados desde la vieja /conversion: editables en el mismo form.
    assert 'id="nombre_cliente" name="nombre_cliente"' in respuesta.text
    assert 'value="MANGO"' in respuesta.text
    assert 'id="codigo_cliente" name="codigo_cliente"' in respuesta.text
    assert 'value="225863"' in respuesta.text


def test_ver_editar_ficha_inexistente_da_404():
    with patch("app.main.obtener_ficha", return_value=None):
        respuesta = cliente.get("/fichas/999/editar")

    assert respuesta.status_code == 404


def test_ver_editar_ficha_error_de_base_da_500():
    with patch("app.main.obtener_ficha", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/fichas/10/editar")

    assert respuesta.status_code == 500


def test_editar_ficha_exitosa_redirige_a_fichas_del_cliente():
    with patch("app.main.actualizar_ficha") as mock_actualizar:
        respuesta = cliente.post(
            "/fichas/10/editar",
            data={
                "cliente_id": "1",
                "articulo_nombre": "Mango",
                "envase_id": "100",
                "contenido_caja": "12",
                "unidad_venta": "unidad",
                "envase_variable": "si",
                "nombre_cliente": "MANGO",
                "codigo_cliente": "225863",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/fichas?cliente_id=1"
    mock_actualizar.assert_called_once_with(10, 100, 12.0, "unidad", True, "MANGO", "225863")


def test_editar_ficha_sin_tildar_envase_variable_guarda_false():
    with patch("app.main.actualizar_ficha") as mock_actualizar:
        respuesta = cliente.post(
            "/fichas/10/editar",
            data={
                "cliente_id": "1",
                "articulo_nombre": "Mango",
                "envase_id": "100",
                "contenido_caja": "12",
                "unidad_venta": "unidad",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    # Sin nombre_cliente/codigo_cliente en el form: quedan en None (son opcionales).
    mock_actualizar.assert_called_once_with(10, 100, 12.0, "unidad", False, None, None)


def test_editar_ficha_sin_contenido_caja_muestra_error():
    with (
        patch("app.main.actualizar_ficha") as mock_actualizar,
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/10/editar",
            data={
                "cliente_id": "1",
                "articulo_nombre": "Mango",
                "envase_id": "100",
                "contenido_caja": "",
                "unidad_venta": "unidad",
            },
        )

    assert respuesta.status_code == 400
    assert "obligatorio" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_ficha_unidad_venta_invalida_muestra_error():
    with (
        patch("app.main.actualizar_ficha") as mock_actualizar,
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/10/editar",
            data={
                "cliente_id": "1",
                "articulo_nombre": "Mango",
                "envase_id": "100",
                "contenido_caja": "12",
                "unidad_venta": "litro",
            },
        )

    assert respuesta.status_code == 400
    assert "unidad de venta válida" in respuesta.text
    assert "Mango" in respuesta.text  # no se pierde el artículo al re-mostrar el error
    mock_actualizar.assert_not_called()


def test_editar_ficha_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.actualizar_ficha", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_envases_por_cliente", return_value=ENVASES_DEL_CLIENTE),
    ):
        respuesta = cliente.post(
            "/fichas/10/editar",
            data={
                "cliente_id": "1",
                "articulo_nombre": "Mango",
                "envase_id": "100",
                "contenido_caja": "12",
                "unidad_venta": "unidad",
            },
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar la ficha" in respuesta.text


def test_eliminar_ficha_exitosa_redirige_a_fichas_del_cliente():
    with patch("app.main.eliminar_ficha") as mock_eliminar:
        respuesta = cliente.post("/fichas/10/eliminar", data={"cliente_id": "1"}, follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/fichas?cliente_id=1"
    mock_eliminar.assert_called_once_with(10)


def test_eliminar_ficha_error_de_base_da_500():
    with patch("app.main.eliminar_ficha", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/fichas/10/eliminar", data={"cliente_id": "1"})

    assert respuesta.status_code == 500


def test_conversion_ya_no_existe_como_pantalla_propia():
    # Regresión: /conversion se fusionó dentro de las fichas de logística
    # del cliente (nombre_cliente/codigo_cliente ahora viven en la ficha).
    assert cliente.get("/conversion").status_code == 404
    assert cliente.get("/conversion/nueva?cliente_id=1").status_code == 404


HOY_DE_PRUEBA = date(2026, 8, 6)

COMPRAS_DE_PRUEBA = [
    {
        "id": 30,
        "fecha_operacion": HOY_DE_PRUEBA,
        "articulo_nombre": "Mzn Red",
        "proveedor_nombre": "Saturno",
        "proveedor_codigo_puesto": "N07P41",
        "cantidad_cajones": 10,
        "contenido_por_cajon": 18,
        "unidad_compra": "kilo",
        "cantidad_kilos": 180,
        "cantidad_fraccion": None,
        "importe": 50000,
        "sena": None,
        "tipo_retiro": "Clark",
    },
    {
        "id": 31,
        "fecha_operacion": HOY_DE_PRUEBA - timedelta(days=1),
        "articulo_nombre": "Mango",
        "proveedor_nombre": "Frutamax",
        "proveedor_codigo_puesto": "L03P38",
        "cantidad_cajones": 5,
        "contenido_por_cajon": 10,
        "unidad_compra": "unidad",
        "cantidad_kilos": None,
        "cantidad_fraccion": 50,
        "importe": 15000,
        "sena": 2000,
        "tipo_retiro": "Carro",
    },
]


def test_ver_compras_muestra_solo_la_botonera():
    # /compras es solo el título y las dos botoneras — el listado vive en
    # /compras/buscar (Últimas Compras ya no existe como pantalla propia).
    respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert '<div class="barra-titulo">Compras</div>' in respuesta.text
    assert ">Cargar<" in respuesta.text
    assert ">Operaciones<" in respuesta.text
    assert respuesta.text.index(">Cargar<") < respuesta.text.index(">Operaciones<")
    assert "Buscar Compras" in respuesta.text
    assert "Últimas Compras" not in respuesta.text
    assert "<table" not in respuesta.text
    assert 'id="boton-borrar-seleccionadas"' not in respuesta.text


def test_ver_compras_no_muestra_nada_de_sistema_ahi():
    # Regresión: el indicador de espacio y el botón de limpieza de fotos se
    # movieron a /sistema — /compras es operativa, no tiene que mostrar
    # nada de eso (ni siquiera si esas funciones responden bien).
    with (
        patch("app.main.obtener_uso_storage_bucket", return_value={"cantidad": 12, "bytes_totales": 907397}),
        patch("app.main.listar_fotos_para_limpiar", return_value=["2020-01-01/x.jpg"]),
    ):
        respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert "fotos guardadas" not in respuesta.text
    assert 'id="boton-limpiar-fotos-viejas"' not in respuesta.text
    assert 'href="/sistema"' in respuesta.text


def test_ver_compras_incluye_links_a_catalogo_y_a_inicio():
    respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert 'href="/articulos"' in respuesta.text
    assert 'href="/inicio"' in respuesta.text
    # Regresión: /conversion se fusionó dentro de las fichas de logística
    # del cliente, ya no existe como pantalla propia.
    assert 'href="/conversion"' not in respuesta.text


def test_ver_sistema_muestra_el_indicador_de_espacio_usado():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_uso_storage_bucket", return_value={"cantidad": 12, "bytes_totales": 907397}),
        patch("app.main.listar_fotos_para_limpiar", return_value=[]),
    ):
        respuesta = cliente.get("/sistema")

    assert respuesta.status_code == 200
    assert "Sistema" in respuesta.text
    assert "12 fotos guardadas" in respuesta.text
    assert "886 KB" in respuesta.text


def test_ver_sistema_indicador_en_singular_con_una_sola_foto():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_uso_storage_bucket", return_value={"cantidad": 1, "bytes_totales": 500}),
        patch("app.main.listar_fotos_para_limpiar", return_value=[]),
    ):
        respuesta = cliente.get("/sistema")

    assert respuesta.status_code == 200
    assert "1 foto guardada" in respuesta.text
    assert "fotos guardadas" not in respuesta.text


def test_ver_sistema_si_falla_el_uso_de_storage_no_muestra_el_indicador_ni_rompe():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_uso_storage_bucket", side_effect=Exception("permission denied for schema storage")),
        patch("app.main.listar_fotos_para_limpiar", side_effect=Exception("permission denied for schema storage")),
    ):
        respuesta = cliente.get("/sistema")

    assert respuesta.status_code == 200
    assert 'class="espacio-storage"' not in respuesta.text
    assert 'id="boton-limpiar-fotos-viejas"' not in respuesta.text


def test_ver_sistema_muestra_el_boton_de_limpieza_con_la_cantidad_real():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_uso_storage_bucket", return_value={"cantidad": 12, "bytes_totales": 907397}),
        patch("app.main.listar_fotos_para_limpiar", return_value=["2020-01-01/x.jpg", "2020-02-02/y.jpg"]),
    ):
        respuesta = cliente.get("/sistema")

    assert respuesta.status_code == 200
    assert 'action="/sistema/limpiar-fotos-viejas"' in respuesta.text
    assert 'id="boton-limpiar-fotos-viejas"' in respuesta.text
    assert 'data-cantidad="2"' in respuesta.text


def test_ver_sistema_incluye_link_a_inicio():
    respuesta = cliente.get("/sistema")

    assert respuesta.status_code == 200
    assert 'href="/inicio"' in respuesta.text


def test_limpiar_fotos_viejas_borra_las_encontradas_y_limpia_foto_ruta():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fotos_para_limpiar", return_value=["2020-01-01/a.jpg", "2020-02-02/b.jpg"]),
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
        patch("app.main.limpiar_foto_ruta_de_compras") as mock_limpiar_ruta,
        patch("app.main.obtener_uso_storage_bucket", return_value={"cantidad": 10, "bytes_totales": 500}),
    ):
        respuesta = cliente.post("/sistema/limpiar-fotos-viejas")

    assert respuesta.status_code == 200
    assert "Sistema" in respuesta.text
    assert "Se liberaron 2 fotos." in respuesta.text
    assert mock_borrar_foto.call_count == 2
    mock_borrar_foto.assert_any_call("2020-01-01/a.jpg")
    mock_borrar_foto.assert_any_call("2020-02-02/b.jpg")
    assert mock_limpiar_ruta.call_count == 2


def test_limpiar_fotos_viejas_sin_ninguna_para_borrar_no_rompe():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fotos_para_limpiar", return_value=[]),
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
    ):
        respuesta = cliente.post("/sistema/limpiar-fotos-viejas")

    assert respuesta.status_code == 200
    assert "No hay fotos de más de 3 años para borrar." in respuesta.text
    mock_borrar_foto.assert_not_called()


def test_limpiar_fotos_viejas_si_falla_una_sigue_con_las_demas():
    def borrar_side_effect(foto_ruta):
        if foto_ruta == "2020-01-01/a.jpg":
            raise Exception("Supabase Storage rechazó el borrado (404)")
        return None

    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch(
            "app.main.listar_fotos_para_limpiar",
            return_value=["2020-01-01/a.jpg", "2020-02-02/b.jpg"],
        ),
        patch("app.main.borrar_foto_comanda", side_effect=borrar_side_effect) as mock_borrar_foto,
        patch("app.main.limpiar_foto_ruta_de_compras") as mock_limpiar_ruta,
        patch("app.main.obtener_uso_storage_bucket", return_value={"cantidad": 10, "bytes_totales": 500}),
    ):
        respuesta = cliente.post("/sistema/limpiar-fotos-viejas")

    assert respuesta.status_code == 200
    assert mock_borrar_foto.call_count == 2
    # Solo la que no falló llega a limpiar foto_ruta en la base.
    mock_limpiar_ruta.assert_called_once_with("2020-02-02/b.jpg")
    assert "Se liberaron 1 de 2 fotos" in respuesta.text


def test_limpiar_fotos_viejas_error_al_buscar_candidatas_da_500():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fotos_para_limpiar", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.post("/sistema/limpiar-fotos-viejas")

    assert respuesta.status_code == 500
    assert "No se pudo revisar qué fotos limpiar" in respuesta.text


PROVEEDORES_DE_PRUEBA = [
    {"id": 200, "codigo_puesto": "N07P41", "nombre": "Saturno"},
    {"id": 201, "codigo_puesto": "L03P38", "nombre": "Frutamax"},
]

PROVEEDOR_DE_PRUEBA = {"id": 200, "codigo_puesto": "N07P41", "nombre": "Saturno"}

ARTICULOS_CON_UNIDAD_COMPRA = [
    {"id": 5, "nombre": "Kiwi", "unidad_compra": "kilo", "contenido_referencia": 18},
]

ARTICULO_KILO_DE_PRUEBA = {"id": 5, "nombre": "Kiwi", "unidad_compra": "kilo", "contenido_referencia": 18}
ARTICULO_UNIDAD_DE_PRUEBA = {"id": 6, "nombre": "Mango", "unidad_compra": "unidad", "contenido_referencia": 10}
ARTICULO_SIN_UNIDAD_COMPRA = {"id": 7, "nombre": "Kiwi", "unidad_compra": None, "contenido_referencia": None}


def test_ver_nueva_compra_sin_proveedor_muestra_formulario_de_proveedor():
    with patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA):
        respuesta = cliente.get("/compras/nueva")

    assert respuesta.status_code == 200
    assert "Código de puesto" in respuesta.text
    assert "N07P41" in respuesta.text
    # Regresión: sin este cartel, leer la foto con la IA puede tardar varios
    # segundos sin ningún cambio visible y el comprador aprieta de nuevo.
    assert 'id="form-leer-comanda"' in respuesta.text
    assert "Leyendo comanda..." in respuesta.text
    # Regresión: en Safari/iOS, deshabilitar el botón sincrónicamente dentro
    # del evento submit cancela el envío del formulario.
    assert "setTimeout" in respuesta.text


def test_ver_nueva_compra_sin_proveedor_botones_confirmar_verde_y_cancelar_rojo():
    with patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA):
        respuesta = cliente.get("/compras/nueva")

    assert respuesta.status_code == 200
    assert 'class="boton-exito" id="boton-confirmar-proveedor"' in respuesta.text
    assert 'class="boton boton-peligro" id="boton-cancelar"' in respuesta.text
    assert 'href="/compras"' in respuesta.text
    # Todavía no se cargó nada en esta pantalla: Cancelar no pide
    # confirmación, a diferencia del Cancelar de las pantallas siguientes.
    assert "confirm(" not in respuesta.text
    # Orden: Confirmar proveedor (verde) antes que Cancelar (rojo).
    assert respuesta.text.index('id="boton-confirmar-proveedor"') < respuesta.text.index('id="boton-cancelar"')


def test_ver_nueva_compra_muestra_autocompletado_en_los_dos_sentidos():
    with patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA):
        respuesta = cliente.get("/compras/nueva")

    assert respuesta.status_code == 200
    # Código -> nombre (ya existía): el datalist del código y el objeto JS.
    assert 'list="lista_proveedores"' in respuesta.text
    assert "PROVEEDORES_CONOCIDOS" in respuesta.text
    assert 'oninput="sugerirNombre()"' in respuesta.text
    # Nombre -> código (nuevo): datalist propio del campo nombre, con los
    # nombres conocidos, y la función que arma el mapeo inverso.
    assert 'list="lista_nombres_proveedores"' in respuesta.text
    assert 'id="lista_nombres_proveedores"' in respuesta.text
    assert "Saturno" in respuesta.text
    assert "Frutamax" in respuesta.text
    assert 'oninput="sugerirCodigo()"' in respuesta.text
    assert "NOMBRES_A_CODIGOS" in respuesta.text
    assert "function sugerirCodigo" in respuesta.text


def test_ver_nueva_compra_sin_proveedor_error_de_base_da_500():
    with patch("app.main.listar_proveedores", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/compras/nueva")

    assert respuesta.status_code == 500


def test_ver_nueva_compra_manual_muestra_solo_el_formulario_de_proveedor():
    with patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA):
        respuesta = cliente.get("/compras/nueva/manual")

    assert respuesta.status_code == 200
    assert "Código de puesto" in respuesta.text
    assert "N07P41" in respuesta.text
    assert 'action="/compras/nueva/proveedor"' in respuesta.text
    assert "PROVEEDORES_LISTA" in respuesta.text
    # No mezcla el flujo de foto: sin formulario de subida ni el link a
    # múltiples comandas.
    assert 'id="form-leer-comanda"' not in respuesta.text
    assert 'href="/compras/nueva/fotos"' not in respuesta.text


def test_ver_nueva_compra_manual_error_de_base_da_500():
    with patch("app.main.listar_proveedores", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/compras/nueva/manual")

    assert respuesta.status_code == 500


def test_ver_nueva_compra_foto_muestra_solo_el_formulario_de_una_foto():
    respuesta = cliente.get("/compras/nueva/foto-una")

    assert respuesta.status_code == 200
    assert 'id="form-leer-comanda"' in respuesta.text
    assert "Leer una comanda" in respuesta.text
    assert 'action="/compras/nueva/foto"' in respuesta.text
    # Sigue ofreciendo el atajo a múltiples fotos desde acá.
    assert 'href="/compras/nueva/fotos"' in respuesta.text
    # No mezcla el flujo manual: sin el formulario de proveedor a mano.
    assert "Código de puesto" not in respuesta.text
    assert 'action="/compras/nueva/proveedor"' not in respuesta.text


def test_ver_nueva_compra_foto_un_solo_toque_dispara_selector_y_lee_directo():
    # Regresión: el botón grande no es un submit — abre el input file oculto
    # (que sí tiene el required, por si algo falla) y la lectura arranca
    # sola al elegir la foto, sin un segundo toque en un botón "Leer".
    respuesta = cliente.get("/compras/nueva/foto-una")

    assert respuesta.status_code == 200
    assert 'class="input-foto-oculto"' in respuesta.text
    assert 'type="button" id="boton-leer-comanda"' in respuesta.text
    assert 'botonLeerComanda.addEventListener("click", function () {\n        inputFoto.click();' in respuesta.text
    assert 'inputFoto.addEventListener("change"' in respuesta.text
    assert "formLeerComanda.requestSubmit()" in respuesta.text


def test_cambiar_proveedor_en_carga_manual_apunta_a_la_pantalla_manual():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.get("/compras/nueva?proveedor_id=200")

    assert respuesta.status_code == 200
    assert 'href="/compras/nueva/manual"' in respuesta.text


def test_ver_cargar_listado_de_compras_muestra_la_pantalla():
    respuesta = cliente.get("/compras/nueva/listado")

    assert respuesta.status_code == 200
    assert "Cargar listado de compras" in respuesta.text
    # Un solo toque: el botón abre el selector nativo, no hace falta un
    # segundo botón "Leer" — mismo criterio que en Múltiples comandas.
    assert 'class="input-foto-oculto"' in respuesta.text
    assert 'id="input-foto-listado"' in respuesta.text
    assert '>Subir plantilla compras<' in respuesta.text
    assert "inputFotoListado.click();" in respuesta.text
    assert 'inputFotoListado.addEventListener("change"' in respuesta.text
    assert 'id="boton-guardar-siguiente"' in respuesta.text
    assert 'id="boton-descartar-siguiente"' in respuesta.text
    assert 'id="boton-cancelar-multiple"' in respuesta.text
    # Regresión: mientras la IA lee la planilla (puede tardar, es una foto
    # con varios proveedores), tiene que quedar clarísimo que el sistema
    # está trabajando — spinner + cartel, no un cartelito chico gris — y el
    # botón no se puede volver a tocar (queda tapado Y deshabilitado).
    assert 'id="seccion-leyendo"' in respuesta.text
    assert 'class="spinner"' in respuesta.text
    assert "Leyendo la planilla..." in respuesta.text
    assert 'document.getElementById("boton-elegir-foto-listado").disabled = true;' in respuesta.text
    assert 'document.getElementById("seccion-leyendo").style.display = "flex";' in respuesta.text


def test_ver_cargar_listado_de_compras_incluye_los_proveedores_conocidos_para_sugerir():
    with patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA):
        respuesta = cliente.get("/compras/nueva/listado")

    assert respuesta.status_code == 200
    assert '{ codigo: "N07P41", nombre: "Saturno" }' in respuesta.text
    assert '{ codigo: "L03P38", nombre: "Frutamax" }' in respuesta.text


# --- /compras/buscar: búsqueda de compras por rango de fechas, proveedor y artículo opcionales ---

COMPRAS_BUSQUEDA_DE_PRUEBA = [
    {
        "id": 1,
        "fecha_operacion": HOY_DE_PRUEBA,
        "articulo_nombre": "Tomate Cherry",
        "unidad_compra": "kilo",
        "proveedor_nombre": "Saturno",
        "proveedor_codigo_puesto": "N07P41",
        "cantidad_cajones": 40,
        "contenido_por_cajon": 20,
        "cantidad_kilos": 800,
        "cantidad_fraccion": None,
        "importe": 45000.0,
        "sena": None,
        "tipo_retiro": "Clark",
        "foto_ruta": None,
    },
    {
        "id": 2,
        "fecha_operacion": HOY_DE_PRUEBA - timedelta(days=1),
        "articulo_nombre": "Mango",
        "unidad_compra": "unidad",
        "proveedor_nombre": "Frutamax",
        "proveedor_codigo_puesto": "L03P38",
        "cantidad_cajones": 10,
        "contenido_por_cajon": 12,
        "cantidad_kilos": None,
        "cantidad_fraccion": 120,
        "importe": None,
        "sena": None,
        "tipo_retiro": "Carro",
        "foto_ruta": None,
    },
]


def test_ver_buscar_compras_sin_filtros_usa_las_ultimas_48hs():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=COMPRAS_BUSQUEDA_DE_PRUEBA) as mock_buscar,
    ):
        respuesta = cliente.get("/compras/buscar")

    assert respuesta.status_code == 200
    mock_buscar.assert_called_once_with(HOY_DE_PRUEBA - timedelta(days=1), HOY_DE_PRUEBA, None, None)
    assert f'value="{(HOY_DE_PRUEBA - timedelta(days=1)).isoformat()}"' in respuesta.text
    assert f'value="{HOY_DE_PRUEBA.isoformat()}"' in respuesta.text


def test_ver_buscar_compras_con_filtros_de_fecha_proveedor_y_articulo():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=COMPRAS_BUSQUEDA_DE_PRUEBA) as mock_buscar,
    ):
        respuesta = cliente.get(
            "/compras/buscar?fecha_desde=2026-08-01&fecha_hasta=2026-08-06&proveedor_id=200&articulo_id=5"
        )

    assert respuesta.status_code == 200
    mock_buscar.assert_called_once_with(date(2026, 8, 1), date(2026, 8, 6), 200, 5)
    # Los buscadores combinados quedan precargados con el nombre elegido.
    assert 'value="Saturno"' in respuesta.text
    assert 'value="Kiwi"' in respuesta.text
    assert "✕ Ver todos los proveedores" in respuesta.text
    assert "✕ Ver todos los artículos" in respuesta.text


def test_ver_buscar_compras_muestra_contador_y_tabla():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=COMPRAS_BUSQUEDA_DE_PRUEBA),
    ):
        respuesta = cliente.get("/compras/buscar")

    assert "2 compras encontradas" in respuesta.text
    assert "Tomate Cherry" in respuesta.text
    assert "Saturno (N07P41)" in respuesta.text
    assert "40 cajones × 20k" in respuesta.text
    assert "$45.000" in respuesta.text
    # Sin importe -> "SIN PRECIO" en rojo, mismo criterio que Últimas Compras.
    assert "SIN PRECIO" in respuesta.text


def test_ver_buscar_compras_sin_resultados_muestra_mensaje_y_no_boton_exportar():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=[]),
    ):
        respuesta = cliente.get("/compras/buscar")

    assert "0 compras encontradas" in respuesta.text
    assert "No se encontraron compras con estos filtros." in respuesta.text
    assert 'id="boton-exportar"' not in respuesta.text


def test_ver_buscar_compras_con_resultados_muestra_boton_exportar():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=COMPRAS_BUSQUEDA_DE_PRUEBA),
    ):
        respuesta = cliente.get("/compras/buscar?fecha_desde=2026-08-01&fecha_hasta=2026-08-06")

    assert 'id="boton-exportar"' in respuesta.text
    assert "/compras/buscar/exportar-pdf?fecha_desde=2026-08-01&fecha_hasta=2026-08-06" in respuesta.text
    assert "/compras/buscar/exportar-excel?fecha_desde=2026-08-01&fecha_hasta=2026-08-06" in respuesta.text


def test_ver_buscar_compras_fecha_invalida_muestra_error_y_usa_default():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=[]) as mock_buscar,
    ):
        respuesta = cliente.get("/compras/buscar?fecha_desde=no-es-una-fecha")

    assert respuesta.status_code == 200
    assert "La fecha desde no es válida." in respuesta.text
    mock_buscar.assert_called_once_with(HOY_DE_PRUEBA - timedelta(days=1), HOY_DE_PRUEBA, None, None)


def test_ver_buscar_compras_fecha_desde_posterior_a_hasta_muestra_error():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=[]),
    ):
        respuesta = cliente.get("/compras/buscar?fecha_desde=2026-08-10&fecha_hasta=2026-08-01")

    assert "La fecha desde no puede ser posterior a la fecha hasta." in respuesta.text


def test_ver_buscar_compras_incluye_buscadores_combinados():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=[]),
    ):
        respuesta = cliente.get("/compras/buscar")

    assert '{ id: 200, codigo: "N07P41", nombre: "Saturno" }' in respuesta.text
    assert '{ id: 5, nombre: "Kiwi" }' in respuesta.text
    assert "actualizarListaProveedores" in respuesta.text
    assert "actualizarListaArticulos" in respuesta.text


def test_ver_buscar_compras_error_de_base_da_500():
    with patch("app.main.listar_proveedores", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/compras/buscar")

    assert respuesta.status_code == 500


# --- /compras/buscar/exportar-pdf y exportar-excel ---


def test_exportar_listado_compras_pdf_devuelve_archivo_adjunto():
    with patch("app.main.buscar_compras", return_value=COMPRAS_BUSQUEDA_DE_PRUEBA) as mock_buscar:
        respuesta = cliente.get(
            "/compras/buscar/exportar-pdf?fecha_desde=2026-08-01&fecha_hasta=2026-08-06&proveedor_id=200&articulo_id=5"
        )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert "attachment" in respuesta.headers["content-disposition"]
    assert "Listado_Compras_2026-08-01_a_2026-08-06" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"%PDF")
    mock_buscar.assert_called_once_with(date(2026, 8, 1), date(2026, 8, 6), 200, 5)


def test_exportar_listado_compras_pdf_agrupa_por_fecha_y_proveedor():
    with patch("app.main.buscar_compras", return_value=COMPRAS_BUSQUEDA_DE_PRUEBA):
        respuesta = cliente.get("/compras/buscar/exportar-pdf?fecha_desde=2026-08-01&fecha_hasta=2026-08-06")

    texto = _texto_del_pdf_de_respuesta(respuesta.content)
    assert "Listado de Compras" in texto
    # La fecha más reciente (HOY_DE_PRUEBA) va antes que la del día anterior.
    assert texto.index(HOY_DE_PRUEBA.strftime("%d/%m/%Y")) < texto.index(
        (HOY_DE_PRUEBA - timedelta(days=1)).strftime("%d/%m/%Y")
    )
    assert "Saturno (N07P41)" in texto
    assert "Frutamax (L03P38)" in texto


def test_exportar_listado_compras_pdf_fecha_invalida_da_400():
    respuesta = cliente.get("/compras/buscar/exportar-pdf?fecha_desde=no-es-fecha&fecha_hasta=2026-08-06")

    assert respuesta.status_code == 400


def test_exportar_listado_compras_excel_devuelve_archivo_adjunto():
    with patch("app.main.buscar_compras", return_value=COMPRAS_BUSQUEDA_DE_PRUEBA):
        respuesta = cliente.get("/compras/buscar/exportar-excel?fecha_desde=2026-08-01&fecha_hasta=2026-08-06")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"PK")  # xlsx es un zip


def test_exportar_listado_compras_excel_fecha_invalida_da_400():
    respuesta = cliente.get("/compras/buscar/exportar-excel?fecha_desde=2026-08-01&fecha_hasta=no-es-fecha")

    assert respuesta.status_code == 400


def test_armar_listado_de_compras_muestra_en_construccion():
    respuesta = cliente.get("/compras/armar-listado")

    assert respuesta.status_code == 200
    assert "Armar listado de compras" in respuesta.text
    assert "En construcción" in respuesta.text


def test_ver_compras_muestra_la_botonera_de_cargar_y_operaciones():
    respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    # Grupo Cargar.
    assert 'href="/compras/nueva/manual"' in respuesta.text
    assert "Cargar Manual" in respuesta.text
    assert 'href="/compras/nueva/foto-una"' in respuesta.text
    assert "Cargar Foto" in respuesta.text
    assert 'href="/compras/nueva/fotos"' in respuesta.text
    assert "Cargar Múltiples Fotos" in respuesta.text
    assert 'href="/compras/nueva/listado"' in respuesta.text
    assert "Cargar Listado de Compras" in respuesta.text
    # Grupo Operaciones: Buscar Compras, Armar Listado, Compras sin precio,
    # Disponibles. "Últimas Compras" y "Enviar a Logística" ya no existen
    # (Buscar Compras + Logística los reemplazan).
    assert 'href="/compras/ultimas"' not in respuesta.text
    assert "Últimas Compras" not in respuesta.text
    assert 'href="/compras/buscar"' in respuesta.text
    assert 'href="/compras/armar-listado"' in respuesta.text
    assert 'href="/compras/pendientes"' in respuesta.text
    assert "Compras sin precio" in respuesta.text
    assert 'href="/compras/disponibles"' in respuesta.text
    assert "Disponibles" in respuesta.text
    assert 'href="/compras/enviar-logistica"' not in respuesta.text
    # El botón viejo "Agregar compra" queda retirado (lo cubre Cargar Manual).
    assert "Agregar compra" not in respuesta.text
    assert 'href="/compras/nueva"' not in respuesta.text


def test_ver_compras_botonera_diferencia_grupos_por_color():
    respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    # Cargar: azul, el color de acción normal (sin clase extra de color).
    assert 'class="boton" href="/compras/nueva/manual"' in respuesta.text
    # Operaciones: naranja — ni verde (=guardar) ni rojo (=borrar/cancelar).
    assert 'class="boton boton-naranja" href="/compras/buscar"' in respuesta.text
    assert 'class="boton boton-naranja" href="/compras/pendientes"' in respuesta.text
    assert ".boton-naranja { background: #ea580c; }" in respuesta.text
    # "Próximamente": color del grupo pero atenuado (mismo criterio en
    # Cargar y en Operaciones). Cargar Listado de Compras y Buscar Compras
    # ya no son "próximamente" — quedaron activos.
    assert 'class="boton" href="/compras/nueva/listado"' in respuesta.text
    assert 'class="boton boton-naranja boton-proximamente" href="/compras/disponibles"' in respuesta.text
    assert ".boton-proximamente { opacity: 0.6; }" in respuesta.text


def test_ver_buscar_compras_boton_borrar_seleccionadas_es_tamano_normal():
    # Regresión: el botón no puede depender solo de .boton-eliminar (que no
    # trae padding/ancho propios) — necesita la clase .boton para tener un
    # área de toque cómoda en celular, no quedar chico/finito.
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=COMPRAS_BUSQUEDA_DE_PRUEBA),
    ):
        respuesta = cliente.get("/compras/buscar")

    assert respuesta.status_code == 200
    assert 'class="boton boton-eliminar" id="boton-borrar-seleccionadas"' in respuesta.text


def test_ver_buscar_compras_muestra_editar_y_ver_foto_solo_con_foto():
    compras = [
        dict(COMPRAS_BUSQUEDA_DE_PRUEBA[0], foto_ruta="2026-08-06/n07p41-123-abcdef12.jpg"),
        dict(COMPRAS_BUSQUEDA_DE_PRUEBA[1], foto_ruta=None),
    ]
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=compras),
    ):
        respuesta = cliente.get("/compras/buscar")

    assert respuesta.text.count(">Editar<") == 2
    assert respuesta.text.count("Ver foto") == 1
    assert 'href="/compras/1/foto"' in respuesta.text
    assert 'href="/compras/2/foto"' not in respuesta.text
    assert 'href="/compras/1/editar"' in respuesta.text
    assert 'href="/compras/2/editar"' in respuesta.text


def test_ver_buscar_compras_muestra_el_aviso_cuando_viene_en_la_url():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=[]),
    ):
        respuesta = cliente.get("/compras/buscar?aviso=3+compras+canceladas.")

    assert '<div class="aviso">3 compras canceladas.</div>' in respuesta.text


def test_elegir_proveedor_compra_exitoso_redirige_con_proveedor_id():
    with patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=200) as mock_proveedor:
        respuesta = cliente.post(
            "/compras/nueva/proveedor",
            data={"codigo_puesto": "n07p41", "nombre": "Saturno"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/nueva?proveedor_id=200"
    mock_proveedor.assert_called_once_with("N07P41", "Saturno")


def test_elegir_proveedor_compra_codigo_invalido_muestra_error():
    with (
        patch("app.main.obtener_o_crear_proveedor_por_codigo") as mock_proveedor,
        patch("app.main.listar_proveedores", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/proveedor",
            data={"codigo_puesto": "puesto15", "nombre": "Saturno"},
        )

    assert respuesta.status_code == 400
    assert "formato NNNPNN" in respuesta.text
    mock_proveedor.assert_not_called()
    # Regresión: el error vuelve a la pantalla manual sola, no a la
    # combinada vieja con la carga de foto mezclada.
    assert 'id="form-leer-comanda"' not in respuesta.text


def test_elegir_proveedor_compra_sin_nombre_muestra_error():
    with (
        patch("app.main.obtener_o_crear_proveedor_por_codigo") as mock_proveedor,
        patch("app.main.listar_proveedores", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/proveedor",
            data={"codigo_puesto": "N07P41", "nombre": ""},
        )

    assert respuesta.status_code == 400
    assert "El nombre no puede estar vacío" in respuesta.text
    mock_proveedor.assert_not_called()


def test_elegir_proveedor_compra_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.obtener_o_crear_proveedor_por_codigo", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_proveedores", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/proveedor",
            data={"codigo_puesto": "N07P41", "nombre": "Saturno"},
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar el proveedor" in respuesta.text


def test_ver_nueva_compra_con_proveedor_muestra_formulario_de_renglon():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.get("/compras/nueva?proveedor_id=200")

    assert respuesta.status_code == 200
    assert "Saturno" in respuesta.text
    assert "N07P41" in respuesta.text
    assert "Kiwi" in respuesta.text
    assert "Cantidad de cajones" in respuesta.text
    assert "Contenido por cajón" in respuesta.text
    # Regresión: sin formnovalidate, el navegador bloquea "Terminar carga"
    # cuando el renglón está vacío (los campos "*" son required) y el POST
    # ni siquiera llega al servidor.
    assert 'name="accion" value="terminar" formnovalidate' in respuesta.text
    # Regresión: sin este cartel de "Guardando...", el comprador no ve
    # ningún cambio al apretar y termina cargando la compra duplicada.
    assert 'id="form-compra"' in respuesta.text
    assert "Guardando..." in respuesta.text
    # Regresión: en Safari/iOS, deshabilitar el botón sincrónicamente dentro
    # del evento submit cancela el envío del formulario.
    assert "setTimeout" in respuesta.text


def test_ver_nueva_compra_con_proveedor_botones_en_orden_guardar_agregar_cancelar():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.get("/compras/nueva?proveedor_id=200")

    assert respuesta.status_code == 200
    # Regresión: los 3 botones de abajo de todo, en este orden exacto y con
    # estos colores. Solo "Cancelar" pide confirmación. Se busca por id, no
    # por el texto visible "Agregar artículo", porque ese mismo texto
    # también aparece en el <title> de la página (título de la pestaña).
    orden = ['id="boton-terminar-carga"', 'id="boton-agregar-articulo"', 'id="boton-cancelar-carga"']
    posiciones = [respuesta.text.index(texto) for texto in orden]
    assert posiciones == sorted(posiciones)
    assert 'class="boton-exito" id="boton-terminar-carga"' in respuesta.text
    assert 'class="boton-peligro" id="boton-cancelar-carga"' in respuesta.text
    assert 'action="/compras/nueva/cancelar"' in respuesta.text
    assert "confirm('¿Seguro que querés cancelar? Se va a descartar todo lo cargado de este proveedor')" in respuesta.text
    assert 'name="proveedor_id" value="200"' in respuesta.text


def test_ver_nueva_compra_con_proveedor_muestra_cargado_hoy_con_formato_compacto():
    renglones_hoy = [
        {
            "id": 99,
            "articulo_nombre": "Kiwi",
            "cantidad_cajones": 10,
            "contenido_por_cajon": 18.6,
            "importe": 45000,
            "sena": None,
        },
    ]
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=renglones_hoy),
    ):
        respuesta = cliente.get("/compras/nueva?proveedor_id=200")

    assert respuesta.status_code == 200
    # Regresión: la tabla de "Cargado hoy" no tenía NINGÚN filtro aplicado
    # (mostraba los números pelados, e importe/seña en None literal texto
    # "None" cuando la compra no tenía precio todavía).
    assert "<td>19</td>" in respuesta.text  # contenido_por_cajon redondeado (18.6 -> 19)
    assert "$45.000" in respuesta.text
    assert "None" not in respuesta.text


def test_ver_nueva_compra_con_proveedor_inexistente_da_404():
    with patch("app.main.obtener_proveedor", return_value=None):
        respuesta = cliente.get("/compras/nueva?proveedor_id=999")

    assert respuesta.status_code == 404


def test_ver_nueva_compra_con_proveedor_error_de_base_da_500():
    with patch("app.main.obtener_proveedor", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/compras/nueva?proveedor_id=200")

    assert respuesta.status_code == 500


def test_agregar_compra_exitosa_redirige_al_mismo_proveedor_calcula_kilos():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/nueva?proveedor_id=200"
    # 10 cajones × 18 kg = 180 kg (unidad_compra del artículo = kilo)
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 50000.0, None, "Clark")


def test_agregar_compra_calcula_fraccion_para_articulo_por_unidad():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_UNIDAD_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "6",
                "cantidad_cajones": "5",
                "contenido_por_cajon": "10",
                "importe": "30000",
                "sena": "",
                "tipo_retiro": "Carro",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    # 5 cajones × 10 unidades = 50 unidades (unidad_compra del artículo = unidad)
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 6, 200, 5.0, 10.0, None, 50.0, 30000.0, None, "Carro")


def test_agregar_compra_proveedor_inexistente_da_404():
    with patch("app.main.obtener_proveedor", return_value=None):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "999",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 404


def test_agregar_compra_terminar_con_renglon_vacio_va_a_compras_sin_guardar():
    with (
        patch("app.main.obtener_proveedor") as mock_proveedor,
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "accion": "terminar",
                "articulo_id": "",
                "cantidad_cajones": "",
                "contenido_por_cajon": "",
                "importe": "",
                "sena": "",
                "tipo_retiro": "",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/buscar"
    mock_proveedor.assert_not_called()
    mock_crear.assert_not_called()


def test_agregar_compra_terminar_con_renglon_cargado_lo_guarda_y_va_a_compras():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "accion": "terminar",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/buscar"
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 50000.0, None, "Clark")


def test_agregar_compra_terminar_con_renglon_invalido_muestra_error_y_no_pierde_datos():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "accion": "terminar",
                "articulo_id": "",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 400
    assert "Elegí un artículo" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_compra_sin_articulo_muestra_error():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 400
    assert "Elegí un artículo" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_compra_sin_cantidad_cajones_muestra_error():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "5",
                "cantidad_cajones": "",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 400
    assert "La cantidad de cajones es obligatoria" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_compra_sin_contenido_por_cajon_muestra_error():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 400
    assert "El contenido por cajón es obligatorio" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_compra_sin_importe_queda_pendiente():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "",
                "sena": "",
                "tipo_retiro": "Clark",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, None, None, "Clark")


def test_agregar_compra_importe_negativo_muestra_error():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "-5",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 400
    assert "El importe tiene que ser mayor a cero" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_compra_tipo_retiro_invalido_muestra_error():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Camion",
            },
        )

    assert respuesta.status_code == 400
    assert "tipo de retiro válido" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_compra_tipo_retiro_pases_se_acepta():
    # "Pases" es el tercer tipo de retiro, junto con Clark/Carro.
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "accion": "terminar",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Pases",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 50000.0, None, "Pases")


def test_ver_nueva_compra_con_proveedor_muestra_las_tres_opciones_de_retiro():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.get("/compras/nueva?proveedor_id=200")

    assert respuesta.status_code == 200
    assert '<option value="Clark" selected>' in respuesta.text
    assert '<option value="Carro"' in respuesta.text
    assert '<option value="Pases"' in respuesta.text


def test_agregar_compra_articulo_sin_unidad_compra_configurada_muestra_error():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_SIN_UNIDAD_COMPRA),
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "7",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 400
    assert "no tiene la unidad de compra configurada" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_compra_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.crear_compra", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva",
            data={
                "proveedor_id": "200",
                "articulo_id": "5",
                "cantidad_cajones": "10",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar la compra" in respuesta.text


def test_cancelar_carga_proveedor_borra_todo_lo_de_hoy_y_va_a_compras():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.eliminar_compras_del_dia_por_proveedor", return_value={"borradas": 3, "protegidas": 0}) as mock_eliminar,
    ):
        respuesta = cliente.post(
            "/compras/nueva/cancelar",
            data={"proveedor_id": "200"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    location = respuesta.headers["location"]
    assert location.startswith("/compras/buscar?")
    assert f"fecha_desde={HOY_DE_PRUEBA.isoformat()}" in location
    assert f"fecha_hasta={HOY_DE_PRUEBA.isoformat()}" in location
    assert "proveedor_id=200" in location
    assert "aviso=3+compras+canceladas." in location
    # Se borra TODO lo del proveedor en el día, no un renglón puntual: no
    # hace falta que el comprador haya cargado nada en el formulario para
    # que se descarte lo que ya estaba guardado de "Agregar artículo".
    mock_eliminar.assert_called_once_with(HOY_DE_PRUEBA, 200)


def test_cancelar_carga_proveedor_con_protegidas_avisa_sin_tecnicismos():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.eliminar_compras_del_dia_por_proveedor", return_value={"borradas": 3, "protegidas": 2}),
    ):
        respuesta = cliente.post(
            "/compras/nueva/cancelar",
            data={"proveedor_id": "200"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    location = respuesta.headers["location"]
    assert "aviso=3+compras+canceladas.+2+no+se+pudieron+eliminar%3A+ya+fueron+retiradas+o+recepcionadas." in location


def test_cancelar_carga_proveedor_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.eliminar_compras_del_dia_por_proveedor", side_effect=Exception("no se pudo conectar")),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.post("/compras/nueva/cancelar", data={"proveedor_id": "200"})

    assert respuesta.status_code == 500
    assert "No se pudo cancelar" in respuesta.text
    # No pierde de vista al proveedor: sigue mostrando su formulario, no una
    # página de error genérica.
    assert "Saturno" in respuesta.text


COMPRA_DE_PRUEBA = {
    "id": 30,
    "fecha_operacion": HOY_DE_PRUEBA,
    "articulo_id": 5,
    "articulo_nombre": "Mzn Red",
    "proveedor_id": 200,
    "proveedor_nombre": "Saturno",
    "proveedor_codigo_puesto": "N07P41",
    "cantidad_cajones": 10,
    "contenido_por_cajon": 18,
    "cantidad_kilos": 180,
    "cantidad_fraccion": None,
    "importe": 50000,
    "sena": None,
    "tipo_retiro": "Clark",
    "estado": "pendiente",
    "estado_retiro": "pendiente",
}


def test_ver_editar_compra_muestra_datos_precargados():
    with (
        patch("app.main.obtener_compra", return_value=COMPRA_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.get("/compras/30/editar")

    assert respuesta.status_code == 200
    assert "Saturno" in respuesta.text
    assert "N07P41" in respuesta.text
    assert 'action="/compras/30/editar"' in respuesta.text
    # Regresión: mostrar cajones y contenido por cajón por separado (no el
    # kilaje total), para poder corregir uno solo de los dos sin recalcular.
    assert 'id="cantidad_cajones" name="cantidad_cajones"' in respuesta.text
    assert 'value="10"' in respuesta.text
    assert 'id="contenido_por_cajon" name="contenido_por_cajon"' in respuesta.text
    assert 'value="18"' in respuesta.text


def test_ver_editar_compra_inexistente_da_404():
    with patch("app.main.obtener_compra", return_value=None):
        respuesta = cliente.get("/compras/999/editar")

    assert respuesta.status_code == 404


def test_ver_editar_compra_error_de_base_da_500():
    with patch("app.main.obtener_compra", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/compras/30/editar")

    assert respuesta.status_code == 500


def test_editar_compra_exitosa_redirige_a_compras():
    with (
        patch("app.main.obtener_compra", return_value=COMPRA_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.actualizar_compra") as mock_actualizar,
    ):
        respuesta = cliente.post(
            "/compras/30/editar",
            data={
                "articulo_id": "5",
                "cantidad_cajones": "8",
                "contenido_por_cajon": "15",
                "importe": "55000",
                "sena": "1000",
                "tipo_retiro": "Carro",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/buscar"
    mock_actualizar.assert_called_once_with(30, 5, 8.0, 15.0, 120.0, None, 55000.0, 1000.0, "Carro")


def test_editar_compra_inexistente_da_404():
    with patch("app.main.obtener_compra", return_value=None):
        respuesta = cliente.post(
            "/compras/999/editar",
            data={
                "articulo_id": "5",
                "cantidad_cajones": "8",
                "contenido_por_cajon": "15",
                "importe": "55000",
                "sena": "",
                "tipo_retiro": "Carro",
            },
        )

    assert respuesta.status_code == 404


def test_editar_compra_sin_cantidad_de_cajones_muestra_error():
    with (
        patch("app.main.obtener_compra", return_value=COMPRA_DE_PRUEBA),
        patch("app.main.actualizar_compra") as mock_actualizar,
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.post(
            "/compras/30/editar",
            data={
                "articulo_id": "5",
                "cantidad_cajones": "",
                "contenido_por_cajon": "18",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 400
    assert "La cantidad de cajones es obligatoria" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_compra_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.obtener_compra", return_value=COMPRA_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.actualizar_compra", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.post(
            "/compras/30/editar",
            data={
                "articulo_id": "5",
                "cantidad_cajones": "8",
                "contenido_por_cajon": "12.5",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar la compra" in respuesta.text


def test_editar_compra_ya_retirada_da_400_con_el_mensaje():
    with (
        patch("app.main.obtener_compra", return_value=COMPRA_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch(
            "app.main.actualizar_compra",
            side_effect=ValueError("Esta compra ya fue retirada, no se puede editar."),
        ),
    ):
        respuesta = cliente.post(
            "/compras/30/editar",
            data={
                "articulo_id": "5",
                "cantidad_cajones": "8",
                "contenido_por_cajon": "12.5",
                "importe": "50000",
                "sena": "",
                "tipo_retiro": "Clark",
            },
        )

    assert respuesta.status_code == 400
    assert "Esta compra ya fue retirada, no se puede editar." in respuesta.text


def test_ver_editar_compra_recepcionada_muestra_aviso_y_deshabilita_el_form():
    compra_bloqueada = dict(COMPRA_DE_PRUEBA, estado="recepcionado", estado_retiro="retirado")
    with (
        patch("app.main.obtener_compra", return_value=compra_bloqueada),
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.get("/compras/30/editar")

    assert respuesta.status_code == 200
    assert "Esta compra ya fue recepcionada o retirada, no se puede editar." in respuesta.text
    assert "<fieldset disabled>" in respuesta.text


def test_ver_editar_compra_sin_procesar_no_muestra_aviso_ni_deshabilita():
    with (
        patch("app.main.obtener_compra", return_value=COMPRA_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.get("/compras/30/editar")

    assert respuesta.status_code == 200
    assert "no se puede editar" not in respuesta.text
    assert "<fieldset disabled>" not in respuesta.text


def test_eliminar_compra_exitosa_redirige_a_compras():
    with (
        patch("app.main.eliminar_compra", return_value=None) as mock_eliminar,
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
    ):
        respuesta = cliente.post("/compras/30/eliminar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/buscar"
    mock_eliminar.assert_called_once_with(30)
    # Esta compra no tenía foto (eliminar_compra devolvió None): no hay
    # nada que borrar del Storage.
    mock_borrar_foto.assert_not_called()


def test_eliminar_compra_con_foto_que_era_la_unica_referencia_la_borra_tambien_del_storage():
    with (
        patch("app.main.eliminar_compra", return_value="2026-08-13/n07p41-123-abcdef12.jpg"),
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
    ):
        respuesta = cliente.post("/compras/30/eliminar", follow_redirects=False)

    assert respuesta.status_code == 303
    mock_borrar_foto.assert_called_once_with("2026-08-13/n07p41-123-abcdef12.jpg")


def test_eliminar_compra_si_falla_el_borrado_de_la_foto_igual_redirige_bien():
    # Regresión: borrar la foto es un extra — si falla, la compra ya se
    # borró y no debe tumbar la respuesta al usuario.
    with (
        patch("app.main.eliminar_compra", return_value="2026-08-13/n07p41-123-abcdef12.jpg"),
        patch("app.main.borrar_foto_comanda", side_effect=Exception("sin conexión con Storage")),
    ):
        respuesta = cliente.post("/compras/30/eliminar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/buscar"


def test_eliminar_compra_error_de_base_da_500():
    with patch("app.main.eliminar_compra", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/compras/30/eliminar")

    assert respuesta.status_code == 500


def test_eliminar_compra_ya_recepcionada_da_400_con_el_mensaje():
    with patch(
        "app.main.eliminar_compra",
        side_effect=ValueError("Esta compra ya fue recepcionada, no se puede eliminar."),
    ):
        respuesta = cliente.post("/compras/30/eliminar")

    assert respuesta.status_code == 400
    assert "Esta compra ya fue recepcionada, no se puede eliminar." in respuesta.text


def test_eliminar_varias_compras_exitosa_muestra_aviso_y_conserva_filtros():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=COMPRAS_DE_PRUEBA),
        patch("app.main.eliminar_compra", return_value=None) as mock_eliminar,
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
    ):
        respuesta = cliente.post(
            "/compras/eliminar-varias",
            data={
                "compra_id": ["30", "31"],
                "fecha_desde": "2026-08-01",
                "fecha_hasta": "2026-08-06",
                "proveedor_id": "200",
                "articulo_id": "",
            },
        )

    assert respuesta.status_code == 200
    assert mock_eliminar.call_count == 2
    mock_eliminar.assert_any_call(30)
    mock_eliminar.assert_any_call(31)
    mock_borrar_foto.assert_not_called()
    assert '<div class="aviso">Se eliminaron 2 compras.</div>' in respuesta.text
    # Conserva los filtros que estaban activos cuando se apretó el borrado.
    assert 'value="2026-08-01"' in respuesta.text
    assert 'value="2026-08-06"' in respuesta.text


def test_eliminar_varias_compras_sin_ninguna_seleccionada_no_hace_nada():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=[]),
        patch("app.main.eliminar_compra") as mock_eliminar,
    ):
        respuesta = cliente.post("/compras/eliminar-varias", data={})

    assert respuesta.status_code == 200
    mock_eliminar.assert_not_called()


def test_eliminar_varias_compras_una_falla_no_corta_el_lote_y_avisa_sin_tecnicismos():
    # id 30 (Mzn Red, Saturno) se borra bien; id 31 (Mango, Frutamax) falla
    # (ej. porque ya fue retirada o recepcionada). El mensaje al usuario no
    # debe mostrar ids ni el error crudo de Postgres, y sí debe nombrar el
    # renglón que no se pudo borrar de forma reconocible (artículo + proveedor).
    def eliminar_side_effect(compra_id):
        if compra_id == 31:
            raise Exception('update or delete on table "compras" violates foreign key constraint')
        return None

    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=COMPRAS_DE_PRUEBA),
        patch("app.main.eliminar_compra", side_effect=eliminar_side_effect) as mock_eliminar,
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
    ):
        respuesta = cliente.post(
            "/compras/eliminar-varias",
            data={"compra_id": ["30", "31"], "fecha_desde": "2026-08-01", "fecha_hasta": "2026-08-06"},
        )

    assert respuesta.status_code == 200
    assert mock_eliminar.call_count == 2
    mock_borrar_foto.assert_not_called()
    assert "Se eliminaron 1 de 2 compras" in respuesta.text
    assert "1 no se pudieron eliminar" in respuesta.text
    assert "ya fueron retiradas o recepcionadas" in respuesta.text
    # Identifica el renglón fallido por artículo+proveedor, no por id ni con
    # el texto crudo de Postgres. (El "31" en la fila de la tabla es el
    # value del checkbox, no el mensaje de error — no cuenta como fuga.)
    assert "Mango (Frutamax)" in respuesta.text
    assert "id 31" not in respuesta.text
    assert "foreign key" not in respuesta.text
    assert "violates" not in respuesta.text


def test_eliminar_varias_compras_todas_fallan_informa_las_dos():
    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=COMPRAS_DE_PRUEBA),
        patch("app.main.eliminar_compra", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.post(
            "/compras/eliminar-varias",
            data={"compra_id": ["30", "31"], "fecha_desde": "2026-08-01", "fecha_hasta": "2026-08-06"},
        )

    assert respuesta.status_code == 200
    assert "Se eliminaron 0 de 2 compras" in respuesta.text
    assert "2 no se pudieron eliminar" in respuesta.text
    assert "Mzn Red (Saturno)" in respuesta.text
    assert "Mango (Frutamax)" in respuesta.text


COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA = [
    {
        "id": 1, "guia_id": 105, "guia_punto": 1, "articulo_nombre": "Tomate Cherry", "unidad_compra": "kilo",
        "proveedor_nombre": "Saturno", "proveedor_codigo_puesto": "N07P41",
        "cantidad_cajones": 40, "contenido_por_cajon": 20, "cantidad_kilos": 800, "cantidad_fraccion": None,
    },
    {
        "id": 2, "guia_id": 105, "guia_punto": 2, "articulo_nombre": "Mango", "unidad_compra": "unidad",
        "proveedor_nombre": "Saturno", "proveedor_codigo_puesto": "N07P41",
        "cantidad_cajones": 10, "contenido_por_cajon": 12, "cantidad_kilos": None, "cantidad_fraccion": 120,
    },
    {
        "id": 3, "guia_id": 106, "guia_punto": 1, "articulo_nombre": "Frutilla", "unidad_compra": "cubeta",
        "proveedor_nombre": "Don Pepe", "proveedor_codigo_puesto": "N01P02",
        "cantidad_cajones": 5, "contenido_por_cajon": 12, "cantidad_kilos": None, "cantidad_fraccion": 60,
    },
]


def test_ver_recepcion_agrupa_por_guia_y_muestra_estimado():
    with patch("app.main.listar_compras_pendientes_recepcion", return_value=COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA):
        respuesta = cliente.get("/deposito/recepcion")

    assert respuesta.status_code == 200
    assert "Guía 105" in respuesta.text
    assert "Guía 106" in respuesta.text
    assert "Saturno (N07P41)" in respuesta.text
    assert "Don Pepe (N01P02)" in respuesta.text
    assert "Tomate Cherry" in respuesta.text
    assert "Mango" in respuesta.text
    assert "Frutilla" in respuesta.text
    assert "40 cajones × 20k" in respuesta.text
    # Etiquetas según unidad_compra de cada artículo.
    assert "Kilos reales" in respuesta.text
    assert "Unidades reales" in respuesta.text
    assert "Cubetas reales" in respuesta.text


def test_ver_recepcion_prellena_los_inputs_con_el_estimado():
    with patch("app.main.listar_compras_pendientes_recepcion", return_value=COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA):
        respuesta = cliente.get("/deposito/recepcion")

    assert respuesta.status_code == 200
    assert 'id="cajones-real-1"' in respuesta.text
    assert 'value="40"' in respuesta.text
    assert 'id="total-real-1"' in respuesta.text
    assert 'value="800"' in respuesta.text


def test_ver_recepcion_sin_pendientes_muestra_mensaje_vacio():
    with patch("app.main.listar_compras_pendientes_recepcion", return_value=[]):
        respuesta = cliente.get("/deposito/recepcion")

    assert respuesta.status_code == 200
    assert "No hay compras pendientes de recepción." in respuesta.text


def test_ver_recepcion_error_de_base_da_500():
    with patch("app.main.listar_compras_pendientes_recepcion", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/deposito/recepcion")

    assert respuesta.status_code == 500


def test_recepcionar_compra_guarda_los_reales_y_redirige():
    with patch("app.main.recepcionar_compra", return_value=None) as mock_recepcionar:
        respuesta = cliente.post(
            "/deposito/recepcion/1/recepcionar",
            data={"cantidad_cajones_real": "38", "cantidad_total_real": "760"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/deposito/recepcion"
    mock_recepcionar.assert_called_once_with(1, 38.0, 760.0)


def test_recepcionar_compra_con_aviso_de_retiro_lo_pasa_por_la_url():
    # Si Depósito recepciona algo que Logística ya había marcado 'cancelado',
    # recepcionar_compra devuelve un aviso — no se pisa el cancelado, pero
    # tampoco puede pasar callado.
    with patch(
        "app.main.recepcionar_compra", return_value="Esta compra figuraba cancelada en Logística."
    ):
        respuesta = cliente.post(
            "/deposito/recepcion/1/recepcionar",
            data={"cantidad_cajones_real": "38", "cantidad_total_real": "760"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/deposito/recepcion?aviso=Esta+compra+figuraba+cancelada+en+Log%C3%ADstica."


def test_recepcionar_compra_sin_datos_muestra_error_sin_guardar():
    with (
        patch("app.main.recepcionar_compra") as mock_recepcionar,
        patch("app.main.listar_compras_pendientes_recepcion", return_value=COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA),
    ):
        respuesta = cliente.post(
            "/deposito/recepcion/1/recepcionar",
            data={"cantidad_cajones_real": "", "cantidad_total_real": "760"},
        )

    assert respuesta.status_code == 400
    assert "La cantidad de cajones real es obligatoria." in respuesta.text
    mock_recepcionar.assert_not_called()


def test_recepcionar_compra_con_numero_invalido_muestra_error_sin_guardar():
    with (
        patch("app.main.recepcionar_compra") as mock_recepcionar,
        patch("app.main.listar_compras_pendientes_recepcion", return_value=COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA),
    ):
        respuesta = cliente.post(
            "/deposito/recepcion/1/recepcionar",
            data={"cantidad_cajones_real": "abc", "cantidad_total_real": "760"},
        )

    assert respuesta.status_code == 400
    assert "tiene que ser un número" in respuesta.text
    mock_recepcionar.assert_not_called()


def test_recepcionar_compra_error_de_base_muestra_mensaje():
    with (
        patch("app.main.recepcionar_compra", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_compras_pendientes_recepcion", return_value=COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA),
    ):
        respuesta = cliente.post(
            "/deposito/recepcion/1/recepcionar",
            data={"cantidad_cajones_real": "38", "cantidad_total_real": "760"},
        )

    assert respuesta.status_code == 500
    assert "No se pudo recepcionar la compra" in respuesta.text


def test_rechazar_compra_redirige_y_no_pide_datos():
    with patch("app.main.rechazar_compra", return_value=None) as mock_rechazar:
        respuesta = cliente.post("/deposito/recepcion/2/rechazar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/deposito/recepcion"
    mock_rechazar.assert_called_once_with(2)


def test_rechazar_compra_con_aviso_de_retiro_lo_pasa_por_la_url():
    with patch(
        "app.main.rechazar_compra", return_value="Esta compra figuraba cancelada en Logística."
    ):
        respuesta = cliente.post("/deposito/recepcion/2/rechazar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/deposito/recepcion?aviso=Esta+compra+figuraba+cancelada+en+Log%C3%ADstica."


def test_ver_recepcion_muestra_el_aviso_cuando_viene_en_la_url():
    with patch("app.main.listar_compras_pendientes_recepcion", return_value=[]):
        respuesta = cliente.get("/deposito/recepcion?aviso=Esta+compra+figuraba+cancelada+en+Log%C3%ADstica.")

    assert respuesta.status_code == 200
    assert '<div class="aviso">Esta compra figuraba cancelada en Logística.</div>' in respuesta.text


def test_rechazar_compra_error_de_base_muestra_mensaje():
    with (
        patch("app.main.rechazar_compra", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_compras_pendientes_recepcion", return_value=COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA),
    ):
        respuesta = cliente.post("/deposito/recepcion/2/rechazar")

    assert respuesta.status_code == 500
    assert "No se pudo rechazar la compra" in respuesta.text


def test_ver_foto_compra_redirige_a_la_url_firmada():
    compra_con_foto = dict(COMPRA_DE_PRUEBA, foto_ruta="2026-08-06/n07p41-123-abcdef12.jpg")
    with (
        patch("app.main.obtener_compra", return_value=compra_con_foto),
        patch(
            "app.main.obtener_url_foto",
            return_value="https://proyecto.supabase.co/storage/v1/object/sign/comandas/x.jpg?token=abc",
        ) as mock_url,
    ):
        respuesta = cliente.get("/compras/30/foto", follow_redirects=False)

    assert respuesta.status_code == 307
    assert respuesta.headers["location"] == "https://proyecto.supabase.co/storage/v1/object/sign/comandas/x.jpg?token=abc"
    mock_url.assert_called_once_with("2026-08-06/n07p41-123-abcdef12.jpg")


def test_ver_foto_compra_sin_foto_ruta_da_404():
    compra_sin_foto = dict(COMPRA_DE_PRUEBA, foto_ruta=None)
    with patch("app.main.obtener_compra", return_value=compra_sin_foto):
        respuesta = cliente.get("/compras/30/foto")

    assert respuesta.status_code == 404


def test_ver_foto_compra_inexistente_da_404():
    with patch("app.main.obtener_compra", return_value=None):
        respuesta = cliente.get("/compras/999/foto")

    assert respuesta.status_code == 404


def test_ver_foto_compra_error_de_storage_da_500():
    compra_con_foto = dict(COMPRA_DE_PRUEBA, foto_ruta="2026-08-06/n07p41-123-abcdef12.jpg")
    with (
        patch("app.main.obtener_compra", return_value=compra_con_foto),
        patch("app.main.obtener_url_foto", side_effect=RuntimeError("Supabase Storage no pudo firmar la URL (404)")),
    ):
        respuesta = cliente.get("/compras/30/foto")

    assert respuesta.status_code == 500


COMPRAS_PENDIENTES_DE_PRUEBA = [
    {
        "id": 40,
        "fecha_operacion": HOY_DE_PRUEBA,
        "articulo_nombre": "Mzn Red",
        "proveedor_nombre": "Saturno",
        "proveedor_codigo_puesto": "N07P41",
        "cantidad_cajones": 10,
        "contenido_por_cajon": 18,
        "unidad_compra": "kilo",
    },
]


def test_ver_compras_pendientes_muestra_la_lista():
    with patch("app.main.listar_compras_sin_precio", return_value=COMPRAS_PENDIENTES_DE_PRUEBA) as mock_listar:
        respuesta = cliente.get("/compras/pendientes")

    assert respuesta.status_code == 200
    assert "Mzn Red" in respuesta.text
    assert "Saturno" in respuesta.text
    mock_listar.assert_called_once_with()
    # Regresión: misma pantalla compacta que /compras — fecha dd/mm y
    # números sin decimales de sobra.
    assert "06/08" in respuesta.text
    assert "2026" not in respuesta.text
    assert "<td>10</td>" in respuesta.text
    # Regresión: letra de unidad pegada al contenido por cajón.
    assert "<td>18k</td>" in respuesta.text
    # Regresión: mismos encabezados compactos que /compras.
    assert "<th>Cant</th>" in respuesta.text
    assert "<th>K/U</th>" in respuesta.text
    assert "<th>$</th>" in respuesta.text


def test_ver_compras_pendientes_sin_pendientes_muestra_mensaje():
    with patch("app.main.listar_compras_sin_precio", return_value=[]):
        respuesta = cliente.get("/compras/pendientes")

    assert respuesta.status_code == 200
    assert "No hay compras pendientes de precio" in respuesta.text


def test_ver_compras_pendientes_error_de_base_da_500():
    with patch("app.main.listar_compras_sin_precio", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/compras/pendientes")

    assert respuesta.status_code == 500
    assert "No se pudieron leer las compras pendientes" in respuesta.text


def test_completar_importe_compra_exitoso_redirige_a_pendientes():
    with patch("app.main.actualizar_importe_compra") as mock_actualizar:
        respuesta = cliente.post(
            "/compras/pendientes/40/importe",
            data={"importe": "50000"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/pendientes"
    mock_actualizar.assert_called_once_with(40, 50000.0)


def test_completar_importe_compra_vacio_muestra_error():
    with (
        patch("app.main.actualizar_importe_compra") as mock_actualizar,
        patch("app.main.listar_compras_sin_precio", return_value=COMPRAS_PENDIENTES_DE_PRUEBA),
    ):
        respuesta = cliente.post("/compras/pendientes/40/importe", data={"importe": ""})

    assert respuesta.status_code == 400
    assert "El importe es obligatorio" in respuesta.text
    mock_actualizar.assert_not_called()


def test_completar_importe_compra_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.actualizar_importe_compra", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_compras_sin_precio", return_value=COMPRAS_PENDIENTES_DE_PRUEBA),
    ):
        respuesta = cliente.post("/compras/pendientes/40/importe", data={"importe": "50000"})

    assert respuesta.status_code == 500
    assert "No se pudo guardar el importe" in respuesta.text


COMPRAS_PENDIENTES_MULTIPLES_DE_PRUEBA = [
    {
        "id": 40,
        "fecha_operacion": HOY_DE_PRUEBA,
        "articulo_nombre": "Mzn Red",
        "proveedor_nombre": "Saturno",
        "proveedor_codigo_puesto": "N07P41",
        "cantidad_cajones": 10,
        "contenido_por_cajon": 18,
    },
    {
        "id": 41,
        "fecha_operacion": HOY_DE_PRUEBA,
        "articulo_nombre": "Kiwi",
        "proveedor_nombre": "Frutamax",
        "proveedor_codigo_puesto": "L03P38",
        "cantidad_cajones": 5,
        "contenido_por_cajon": 16,
    },
]


def test_ver_compras_pendientes_muestra_boton_de_guardar_todos():
    with patch("app.main.listar_compras_sin_precio", return_value=COMPRAS_PENDIENTES_MULTIPLES_DE_PRUEBA):
        respuesta = cliente.get("/compras/pendientes")

    assert respuesta.status_code == 200
    assert 'id="boton-guardar-todos"' in respuesta.text
    assert "Guardar todos" in respuesta.text
    assert 'data-compra-id="40"' in respuesta.text
    assert 'data-compra-id="41"' in respuesta.text


def test_completar_importes_pendientes_guarda_solo_los_que_tienen_valor():
    with (
        patch("app.main.listar_compras_sin_precio", return_value=COMPRAS_PENDIENTES_MULTIPLES_DE_PRUEBA),
        patch("app.main.actualizar_importe_compra") as mock_actualizar,
    ):
        respuesta = cliente.post(
            "/compras/pendientes/guardar-todos",
            data={"importe_40": "50000", "importe_41": ""},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/pendientes"
    mock_actualizar.assert_called_once_with(40, 50000.0)


def test_completar_importes_pendientes_ninguno_cargado_muestra_error():
    with (
        patch("app.main.listar_compras_sin_precio", return_value=COMPRAS_PENDIENTES_MULTIPLES_DE_PRUEBA),
        patch("app.main.actualizar_importe_compra") as mock_actualizar,
    ):
        respuesta = cliente.post(
            "/compras/pendientes/guardar-todos",
            data={"importe_40": "", "importe_41": ""},
        )

    assert respuesta.status_code == 400
    assert "Cargá al menos un importe para guardar" in respuesta.text
    mock_actualizar.assert_not_called()


def test_completar_importes_pendientes_importe_invalido_muestra_error_con_el_articulo():
    with (
        patch("app.main.listar_compras_sin_precio", return_value=COMPRAS_PENDIENTES_MULTIPLES_DE_PRUEBA),
        patch("app.main.actualizar_importe_compra") as mock_actualizar,
    ):
        respuesta = cliente.post(
            "/compras/pendientes/guardar-todos",
            data={"importe_40": "50000", "importe_41": "no-es-un-numero"},
        )

    assert respuesta.status_code == 400
    assert "Kiwi" in respuesta.text
    assert "El importe tiene que ser un número" in respuesta.text
    mock_actualizar.assert_not_called()


def test_completar_importes_pendientes_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.listar_compras_sin_precio", return_value=COMPRAS_PENDIENTES_MULTIPLES_DE_PRUEBA),
        patch("app.main.actualizar_importe_compra", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.post(
            "/compras/pendientes/guardar-todos",
            data={"importe_40": "50000"},
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar el importe" in respuesta.text


COMANDA_LEIDA_DE_PRUEBA = {
    "proveedor": {"nombre": "Saturno", "tipo_pabellon": "nave", "numero_pabellon": "7", "puesto": "41"},
    "fecha": "2026-08-06",
    "items": [
        {
            "articulo": "Kiwi",
            "cantidad": 10,
            "importe": 5000,
            "sena": None,
            "nota_margen": "84",
            "confianza": "alta",
        },
        {
            "articulo": "completar artículo",
            "cantidad": 5,
            "importe": "completar importe",
            "sena": None,
            "nota_margen": "",
            "confianza": "baja",
        },
    ],
}


def test_subir_foto_compra_adivina_proveedor_y_articulo():
    with (
        patch("app.main.extraer_comanda", return_value=COMANDA_LEIDA_DE_PRUEBA),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]) as mock_aprendizaje,
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    assert "Saturno" in respuesta.text
    assert "N07P41" in respuesta.text
    assert "Kiwi" in respuesta.text
    assert "84" in respuesta.text  # nota al margen
    assert "⚠ revisar" in respuesta.text  # el segundo ítem, sin articulo ni importe
    mock_aprendizaje.assert_called_once_with(200)

    # Regresión: los 3 botones de abajo de todo, en este orden exacto y con
    # estos colores. Solo "Cancelar" pide confirmación.
    orden = ["Guardar", "Agregar Artículos", "Cancelar"]
    posiciones = [respuesta.text.index(texto) for texto in orden]
    assert posiciones == sorted(posiciones)
    assert 'value="agregar_articulos"' in respuesta.text
    assert 'class="boton-exito" id="boton-guardar"' in respuesta.text
    assert 'class="boton boton-peligro"' in respuesta.text
    assert "confirm('¿Seguro? Se pierde lo que cargaste de esta compra')" in respuesta.text
    # Tercer tipo de retiro (Pases), además de Clark/Carro. Clark viene
    # preseleccionado por defecto (mismo default que la carga manual).
    assert '<option value="Clark" selected>' in respuesta.text
    assert '<option value="Pases"' in respuesta.text
    # Regresión: la sugerencia puesto<->nombre de la carga manual también
    # está disponible acá (ayuda extra sobre lo que ya adivinó la IA).
    assert '{ codigo: "N07P41", nombre: "Saturno" }' in respuesta.text
    assert "oninput=\"actualizarListaProveedores('codigo_puesto')\"" in respuesta.text
    assert "oninput=\"actualizarListaProveedores('nombre')\"" in respuesta.text


def test_subir_foto_compra_proveedor_nuevo_sin_proveedores_existentes_igual_arma_el_codigo():
    # Regresión: antes, si no había NINGÚN proveedor cargado todavía (o
    # ninguno matcheaba), se perdía el código ya interpretado de la foto y
    # el campo quedaba vacío para un proveedor nuevo. Ahora se sugiere igual.
    with (
        patch("app.main.extraer_comanda", return_value=COMANDA_LEIDA_DE_PRUEBA),
        patch("app.main.listar_proveedores", return_value=[]),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor") as mock_aprendizaje,
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    assert 'value="N07P41"' in respuesta.text
    # El proveedor propuesto no existe todavía (id None): no tiene sentido
    # buscarle aprendizaje.
    mock_aprendizaje.assert_not_called()


def test_subir_foto_compra_sin_ningun_dato_de_proveedor_deja_codigo_vacio():
    comanda_sin_pabellon = {
        "proveedor": {"nombre": "", "tipo_pabellon": None, "numero_pabellon": "", "puesto": ""},
        "fecha": "2026-08-06",
        "items": [],
    }
    with (
        patch("app.main.extraer_comanda", return_value=comanda_sin_pabellon),
        patch("app.main.listar_proveedores", return_value=[]),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    assert 'value="" autocomplete="off"' in respuesta.text
    # Con un solo renglón (o ninguno) no tiene sentido ofrecer "aplicar a
    # todos los demás".
    assert 'id="aplicar_retiro_a_todos"' not in respuesta.text


def test_subir_foto_compra_adivina_articulo_por_conversion():
    comanda = {
        "proveedor": {"nombre": "Saturno", "tipo_pabellon": "nave", "numero_pabellon": "7", "puesto": "41"},
        "fecha": "2026-08-06",
        "items": [
            {"articulo": "PG", "cantidad": 10, "importe": 5000, "sena": None, "nota_margen": "", "confianza": "alta"},
        ],
    }
    conversiones = [{"articulo_id": 5, "nombre_cliente": "MANZANA PG"}]
    with (
        patch("app.main.extraer_comanda", return_value=comanda),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=conversiones),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    # El artículo 5 (Kiwi, en ARTICULOS_CON_UNIDAD_COMPRA) queda seleccionado en el combo.
    assert "selected>Kiwi" in respuesta.text


def test_subir_foto_compra_error_del_lector_muestra_mensaje_claro():
    with patch("app.main.extraer_comanda", side_effect=Exception("no se pudo conectar con la API")):
        respuesta = cliente.post(
            "/compras/nueva/foto",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 500
    assert "No se pudo leer la foto" in respuesta.text
    # Regresión: la pantalla de error vuelve a "cargar foto" (foco único),
    # no a la pantalla combinada vieja con el formulario manual mezclado.
    assert "Código de puesto" not in respuesta.text
    assert 'id="form-leer-comanda"' in respuesta.text


def _datos_confirmar_foto(descartar_item_1=True, codigo_puesto="N07P41", nombre="Saturno", foto_preview=None):
    datos = {
        "codigo_puesto": codigo_puesto,
        "nombre": nombre,
        "cantidad_renglones": "2",
        "item_0_texto_leido": "Kiwi",
        "item_0_articulo_id": "5",
        "item_0_cantidad_cajones": "10",
        "item_0_contenido_por_cajon": "18",
        "item_0_importe": "5000",
        "item_0_sena": "",
        "item_0_tipo_retiro": "Clark",
        "item_1_texto_leido": "completar artículo",
        "item_1_articulo_id": "",
        "item_1_cantidad_cajones": "5",
        "item_1_contenido_por_cajon": "",
        "item_1_importe": "",
        "item_1_sena": "",
        "item_1_tipo_retiro": "",
    }
    if descartar_item_1:
        datos["item_1_descartar"] = "on"
    if foto_preview is not None:
        datos["foto_preview"] = foto_preview
    return datos


def test_confirmar_compra_foto_exitosa_guarda_solo_los_confirmados():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=200) as mock_proveedor,
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.aprender_articulo") as mock_aprender,
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto/confirmar",
            data=_datos_confirmar_foto(),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/nueva?proveedor_id=200"
    mock_proveedor.assert_called_once_with("N07P41", "Saturno")
    # Sin foto_preview en el form (estos datos de prueba no la mandan), no
    # hay nada que subir a Storage: foto_ruta queda en None.
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 5000.0, None, "Clark", None)
    mock_aprender.assert_called_once_with(200, "kiwi", 5)


def test_confirmar_compra_foto_accion_guardar_va_directo_al_resumen_y_guarda_igual():
    # El botón verde "Guardar" tiene que guardar exactamente lo mismo que
    # "Agregar Artículos" (misma llamada a crear_compra/aprender_articulo),
    # la única diferencia es a dónde redirige después.
    datos = _datos_confirmar_foto()
    datos["accion"] = "guardar"
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=200) as mock_proveedor,
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.aprender_articulo") as mock_aprender,
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto/confirmar",
            data=datos,
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/buscar"
    mock_proveedor.assert_called_once_with("N07P41", "Saturno")
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 5000.0, None, "Clark", None)
    mock_aprender.assert_called_once_with(200, "kiwi", 5)


FOTO_PREVIEW_DE_PRUEBA = "data:image/jpeg;base64,aGVsbG8="  # decodifica a b"hello"


def test_confirmar_compra_foto_sube_la_foto_una_vez_y_guarda_la_ruta_en_todos_los_renglones():
    # Dos renglones válidos (no uno descartado como en _datos_confirmar_foto
    # por defecto), para poder confirmar que la MISMA ruta de foto queda en
    # los dos — una comanda = una foto = varios renglones de compra.
    datos = {
        "codigo_puesto": "N07P41",
        "nombre": "Saturno",
        "foto_preview": FOTO_PREVIEW_DE_PRUEBA,
        "cantidad_renglones": "2",
        "item_0_texto_leido": "Kiwi",
        "item_0_articulo_id": "5",
        "item_0_cantidad_cajones": "10",
        "item_0_contenido_por_cajon": "18",
        "item_0_importe": "5000",
        "item_0_sena": "",
        "item_0_tipo_retiro": "Clark",
        "item_1_texto_leido": "Kiwi",
        "item_1_articulo_id": "5",
        "item_1_cantidad_cajones": "3",
        "item_1_contenido_por_cajon": "18",
        "item_1_importe": "1500",
        "item_1_sena": "",
        "item_1_tipo_retiro": "Clark",
    }
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=200),
        patch("app.main.subir_foto_comanda", return_value="2026-08-06/n07p41-123-abcdef12.jpg") as mock_subir,
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.aprender_articulo"),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto/confirmar",
            data=datos,
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    # Se sube UNA sola vez (no una vez por renglón), con los bytes ya
    # decodificados del data URI y el código de puesto como base del nombre.
    mock_subir.assert_called_once_with(b"hello", "N07P41")
    assert mock_crear.call_count == 2
    for llamada in mock_crear.call_args_list:
        assert llamada.args[-1] == "2026-08-06/n07p41-123-abcdef12.jpg"


def test_confirmar_compra_foto_si_falla_la_subida_guarda_la_compra_igual_sin_foto():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=200),
        patch("app.main.subir_foto_comanda", side_effect=RuntimeError("Supabase Storage rechazó la subida (403)")),
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.aprender_articulo"),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto/confirmar",
            data=_datos_confirmar_foto(foto_preview=FOTO_PREVIEW_DE_PRUEBA),
            follow_redirects=False,
        )

    # NO es un error de "no se pudo guardar la compra": la foto es un
    # extra, la falla de Storage nunca puede bloquear la carga.
    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 5000.0, None, "Clark", None)


def test_confirmar_compra_foto_codigo_puesto_invalido_muestra_error():
    with (
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto/confirmar",
            data=_datos_confirmar_foto(codigo_puesto="puesto15"),
        )

    assert respuesta.status_code == 400
    assert "formato NNNPNN" in respuesta.text
    mock_crear.assert_not_called()


def test_confirmar_compra_foto_renglon_invalido_muestra_error_con_numero():
    datos = _datos_confirmar_foto(descartar_item_1=False)
    with (
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post("/compras/nueva/foto/confirmar", data=datos)

    assert respuesta.status_code == 400
    assert "Renglón 2" in respuesta.text
    assert "Elegí un artículo" in respuesta.text
    mock_crear.assert_not_called()


def test_confirmar_compra_foto_error_incluye_sugerencia_de_proveedor_para_reintentar():
    # Regresión: al reintentar después de un error, la pantalla de revisión
    # sigue teniendo disponible la sugerencia puesto<->nombre (no solo en la
    # primera carga de la foto).
    datos = _datos_confirmar_foto(descartar_item_1=False)
    with (
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.crear_compra"),
    ):
        respuesta = cliente.post("/compras/nueva/foto/confirmar", data=datos)

    assert respuesta.status_code == 400
    assert '{ codigo: "N07P41", nombre: "Saturno" }' in respuesta.text


def test_confirmar_compra_foto_conserva_el_retiro_ya_elegido_al_reintentar():
    # Regresión: si un renglón fallaba, el "Retiro" de los DEMÁS renglones se
    # perdía al re-mostrar el formulario (siempre volvía a "Elegí..."),
    # obligando a re-elegirlo en todos de nuevo en cada intento.
    datos = _datos_confirmar_foto(descartar_item_1=False)
    with (
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.crear_compra"),
    ):
        respuesta = cliente.post("/compras/nueva/foto/confirmar", data=datos)

    assert respuesta.status_code == 400
    assert "selected>Clark" in respuesta.text


def test_confirmar_compra_foto_todo_descartado_muestra_error():
    datos = _datos_confirmar_foto()
    datos["item_0_descartar"] = "on"
    with (
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.crear_compra") as mock_crear,
    ):
        respuesta = cliente.post("/compras/nueva/foto/confirmar", data=datos)

    assert respuesta.status_code == 400
    assert "No hay ningún renglón para guardar" in respuesta.text
    mock_crear.assert_not_called()


def test_confirmar_compra_foto_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.post("/compras/nueva/foto/confirmar", data=_datos_confirmar_foto())

    assert respuesta.status_code == 500
    assert "No se pudo guardar la compra" in respuesta.text


def _imagen_de_prueba() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color="red").save(buffer, format="JPEG")
    return buffer.getvalue()


def test_generar_preview_foto_devuelve_data_uri_para_una_imagen_valida():
    preview = _generar_preview_foto(_imagen_de_prueba())
    assert preview.startswith("data:image/jpeg;base64,")


def test_generar_preview_foto_devuelve_vacio_si_no_es_una_imagen():
    assert _generar_preview_foto(b"esto no es una imagen") == ""


def _imagen_apaisada_con_orientacion_exif(orientacion: int) -> bytes:
    """Imagen rectangular (30x10) con el tag EXIF Orientation seteado, como la que graba un celular."""
    imagen = Image.new("RGB", (30, 10), color="red")
    exif = imagen.getexif()
    exif[274] = orientacion  # 274 = Orientation
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", exif=exif.tobytes())
    return buffer.getvalue()


def test_generar_preview_foto_aplica_la_rotacion_del_exif():
    # Orientation 6 = hay que rotar 90° para verse derecha: una foto de
    # celular "vertical" que el sensor graba apaisada (30x10) tiene que
    # terminar parada (alto > ancho) en el preview, no apaisada.
    imagen_con_exif = _imagen_apaisada_con_orientacion_exif(6)
    preview = _generar_preview_foto(imagen_con_exif)

    assert preview.startswith("data:image/jpeg;base64,")
    _, base64_texto = preview.split(";base64,", 1)
    imagen_resultante = Image.open(io.BytesIO(base64.standard_b64decode(base64_texto)))
    ancho, alto = imagen_resultante.size
    assert alto > ancho


def test_subir_foto_compra_incluye_preview_de_la_foto_para_el_boton_ver_foto():
    with (
        patch("app.main.extraer_comanda", return_value=COMANDA_LEIDA_DE_PRUEBA),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto",
            files={"foto": ("comanda.jpg", _imagen_de_prueba(), "image/jpeg")},
        )

    assert respuesta.status_code == 200
    assert "data:image/jpeg;base64," in respuesta.text
    assert "Ver foto" in respuesta.text


def test_subir_foto_compra_muestra_cartel_de_guardando_para_evitar_duplicados():
    with (
        patch("app.main.extraer_comanda", return_value=COMANDA_LEIDA_DE_PRUEBA),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    assert 'id="form-confirmar-foto"' in respuesta.text
    assert "Guardando..." in respuesta.text
    # Regresión: en Safari/iOS, deshabilitar el botón sincrónicamente dentro
    # del evento submit cancela el envío del formulario — tiene que ir
    # diferido en un setTimeout.
    assert "setTimeout" in respuesta.text
    assert "b.elemento.disabled = true;" in respuesta.text
    # Regresión: checkbox para aplicar el retiro del primer artículo a todos
    # los demás, y así no elegirlo renglón por renglón.
    assert 'id="aplicar_retiro_a_todos"' in respuesta.text
    assert "Usar este retiro para todos los artículos" in respuesta.text


def test_confirmar_compra_foto_conserva_la_foto_al_reintentar_por_error():
    datos = _datos_confirmar_foto(descartar_item_1=False)
    datos["foto_preview"] = "data:image/jpeg;base64,ABC123"
    with (
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.crear_compra"),
    ):
        respuesta = cliente.post("/compras/nueva/foto/confirmar", data=datos)

    assert respuesta.status_code == 400
    assert "data:image/jpeg;base64,ABC123" in respuesta.text


def test_ver_carga_comandas_multiples_muestra_la_pantalla():
    respuesta = cliente.get("/compras/nueva/fotos")

    assert respuesta.status_code == 200
    assert "Cargar varias comandas por foto" in respuesta.text
    assert 'id="input-fotos"' in respuesta.text
    assert "multiple" in respuesta.text
    assert 'id="boton-guardar-siguiente"' in respuesta.text
    # Regresión: "Descartar y siguiente" saltea la comanda actual sin
    # guardarla, distinto de "Guardar y siguiente" y de "Cancelar" (que sale
    # de todo el lote).
    assert 'id="boton-descartar-siguiente"' in respuesta.text
    assert "Descartar y siguiente" in respuesta.text
    # Regresión: en la última comanda del lote, "Descartar y siguiente"
    # pasa a decir "Descartar y terminar", igual que ya hace "Guardar y
    # siguiente" -> "Guardar y terminar". Misma condición esUltima, en la
    # misma función (actualizarBotonGuardar) que actualiza los dos botones.
    assert '"Descartar y terminar" : "Descartar y siguiente"' in respuesta.text
    # Regresión: la lectura de todas las fotos arranca de entrada, con un
    # límite de concurrencia (no una por una al guardar).
    assert "LIMITE_CONCURRENCIA_LECTURA" in respuesta.text
    assert "Leídas" in respuesta.text
    # Regresión: al mostrar una comanda nueva (guardar/descartar y pasar a
    # la siguiente) la pantalla vuelve al tope.
    assert "window.scrollTo(0, 0)" in respuesta.text
    # Regresión: buscador combinado de proveedor también en modo múltiple,
    # reusando la misma lógica que la carga manual.
    assert "actualizarListaProveedores" in respuesta.text
    assert "elegirProveedor" in respuesta.text
    # Regresión: al agregar un renglón en blanco, si el tilde "usar este
    # retiro para todos" está tildado, el renglón nuevo se precarga con ese
    # retiro en vez de quedar en "Elegí...".
    assert "aplicar_retiro_a_todos" in respuesta.text
    assert 'checkboxAplicarATodos.checked' in respuesta.text
    assert "retiroActivo ? document.getElementById" in respuesta.text
    # Regresión: un solo toque — "Elegir fotos" no valida ni arranca nada
    # por sí solo, solo abre el input file oculto; el flujo arranca recién
    # en el "change" del input, cuando ya hay fotos elegidas.
    assert 'class="input-foto-oculto"' in respuesta.text
    assert '>Elegir fotos<' in respuesta.text
    assert "inputFotos.click();" in respuesta.text
    assert 'inputFotos.addEventListener("change"' in respuesta.text


def test_ver_carga_comandas_multiples_incluye_los_proveedores_conocidos_para_sugerir():
    with patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA):
        respuesta = cliente.get("/compras/nueva/fotos")

    assert respuesta.status_code == 200
    assert '{ codigo: "N07P41", nombre: "Saturno" }' in respuesta.text
    assert '{ codigo: "L03P38", nombre: "Frutamax" }' in respuesta.text


def test_link_multiples_comandas_en_pantalla_de_una_foto():
    with patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA):
        respuesta = cliente.get("/compras/nueva")

    assert respuesta.status_code == 200
    assert 'href="/compras/nueva/fotos"' in respuesta.text
    # Regresión: distinguir claramente "Leer una comanda" (una sola foto) de
    # "Múltiples comandas" (el flujo nuevo).
    assert "Leer una comanda" in respuesta.text


def test_leer_foto_comanda_multiple_adivina_proveedor_y_articulo():
    with (
        patch("app.main.extraer_comanda", return_value=COMANDA_LEIDA_DE_PRUEBA),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/fotos/leer",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is True
    assert datos["cantidad_renglones"] == 2
    assert "Saturno" in datos["html"]
    assert "N07P41" in datos["html"]
    assert "Kiwi" in datos["html"]
    assert 'id="renglones-comanda"' in datos["html"]


def test_leer_foto_comanda_multiple_si_falla_la_ia_devuelve_renglon_en_blanco_para_completar_a_mano():
    with (
        patch("app.main.extraer_comanda", side_effect=Exception("no se pudo leer")),
        patch("app.main.listar_proveedores", return_value=[]),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/fotos/leer",
            files={"foto": ("comanda.jpg", _imagen_de_prueba(), "image/jpeg")},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is True
    assert datos["cantidad_renglones"] == 1
    assert "⚠ revisar" in datos["html"]
    # No cortó la cola: la foto sigue disponible para el modal "Ver foto".
    assert "modal-foto" in datos["html"]


def test_leer_foto_comanda_multiple_sin_items_leidos_devuelve_renglon_en_blanco():
    comanda_sin_items = {
        "proveedor": {"nombre": "Saturno", "tipo_pabellon": "nave", "numero_pabellon": "7", "puesto": "41"},
        "fecha": "2026-08-06",
        "items": [],
    }
    with (
        patch("app.main.extraer_comanda", return_value=comanda_sin_items),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/fotos/leer",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is True
    assert datos["cantidad_renglones"] == 1
    assert "⚠ revisar" in datos["html"]


def test_leer_foto_comanda_multiple_error_de_base_devuelve_ok_false():
    with (
        patch("app.main.extraer_comanda", return_value=COMANDA_LEIDA_DE_PRUEBA),
        patch("app.main.listar_proveedores", side_effect=Exception("sin conexión")),
    ):
        respuesta = cliente.post(
            "/compras/nueva/fotos/leer",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is False
    assert "error" in datos


RENGLONES_LISTADO_DE_PRUEBA = [
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
        "articulo": "Kiwi",
        "cantidad": 5,
        "kg_x_bulto": 20,
        "importe": 3000,
        "nota_margen": "",
        "confianza": "alta",
    },
    {
        "es_idem": False,
        "proveedor_texto": "Frutamax",
        "codigo": "",
        "articulo": "completar articulo",
        "cantidad": 3,
        "kg_x_bulto": None,
        "importe": None,
        "nota_margen": "",
        "confianza": "baja",
    },
]


def test_leer_listado_consolidado_agrupa_por_proveedor_y_arma_un_grupo_revisable_por_cada_uno():
    with (
        patch("app.main.extraer_listado_consolidado", return_value={"renglones": RENGLONES_LISTADO_DE_PRUEBA}),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/listado/leer",
            files={"foto": ("planilla.jpg", _imagen_de_prueba(), "image/jpeg")},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is True
    # Saturno (2 renglones, el segundo es ídem) y Frutamax (1 renglón),
    # cada uno un grupo revisable aparte, en orden de primera aparición.
    assert len(datos["grupos"]) == 2
    assert datos["grupos"][0]["cantidad_renglones"] == 2
    assert "Saturno" in datos["grupos"][0]["html"]
    assert "N07P41" in datos["grupos"][0]["html"]
    assert datos["grupos"][1]["cantidad_renglones"] == 1
    assert "Frutamax" in datos["grupos"][1]["html"]
    # Opción A: renglón con articulo no reconocido queda marcado para
    # revisar a mano, nunca se guarda solo.
    assert "⚠ revisar" in datos["grupos"][1]["html"]
    # La foto de la planilla se manda en la respuesta para poder subirla
    # una sola vez desde el cliente (asegurarFotoSubida en el template).
    assert datos["foto_preview"].startswith("data:image/jpeg;base64,")


def test_leer_listado_consolidado_kg_x_bulto_de_la_planilla_pisa_el_de_catalogo():
    # Regresión: a diferencia de una comanda normal (contenido_por_cajon
    # sale del catálogo), en el listado cada renglón trae su propio
    # kg_x_bulto — el primer renglón de prueba trae 18 (coincide con el
    # catálogo) y el segundo (ídem) trae 20 (distinto al catálogo, 18):
    # tiene que quedar 20, no el del catálogo.
    with (
        patch("app.main.extraer_listado_consolidado", return_value={"renglones": RENGLONES_LISTADO_DE_PRUEBA}),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/listado/leer",
            files={"foto": ("planilla.jpg", _imagen_de_prueba(), "image/jpeg")},
        )

    datos = respuesta.json()
    assert 'value="20.0"' in datos["grupos"][0]["html"] or 'value="20"' in datos["grupos"][0]["html"]


def test_leer_listado_consolidado_proveedor_no_matcheado_queda_para_revisar():
    # Opción A también para proveedor no reconocido: el grupo queda armado
    # igual (con el nombre leído, id None), el comprador lo completa a mano
    # en el buscador combinado antes de guardar.
    renglones = [
        {
            "es_idem": False,
            "proveedor_texto": "Proveedor Desconocido SRL",
            "codigo": "",
            "articulo": "Kiwi",
            "cantidad": 10,
            "kg_x_bulto": 18,
            "importe": 5000,
            "nota_margen": "",
            "confianza": "alta",
        }
    ]
    with (
        patch("app.main.extraer_listado_consolidado", return_value={"renglones": renglones}),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_todas_las_conversiones", return_value=[]),
        patch("app.main.listar_aprendizaje_articulos_por_proveedor", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/listado/leer",
            files={"foto": ("planilla.jpg", _imagen_de_prueba(), "image/jpeg")},
        )

    datos = respuesta.json()
    assert datos["ok"] is True
    assert len(datos["grupos"]) == 1
    assert "Proveedor Desconocido SRL" in datos["grupos"][0]["html"]


def test_leer_listado_consolidado_si_falla_la_ia_devuelve_ok_false():
    with (
        patch("app.main.extraer_listado_consolidado", side_effect=Exception("no se pudo leer la planilla")),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
    ):
        respuesta = cliente.post(
            "/compras/nueva/listado/leer",
            files={"foto": ("planilla.jpg", _imagen_de_prueba(), "image/jpeg")},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is False
    assert "error" in datos


def test_leer_listado_consolidado_error_de_base_devuelve_ok_false():
    with (
        patch("app.main.extraer_listado_consolidado", return_value={"renglones": RENGLONES_LISTADO_DE_PRUEBA}),
        patch("app.main.listar_proveedores", side_effect=Exception("sin conexión")),
    ):
        respuesta = cliente.post(
            "/compras/nueva/listado/leer",
            files={"foto": ("planilla.jpg", _imagen_de_prueba(), "image/jpeg")},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is False
    assert "error" in datos


def test_leer_listado_consolidado_sin_renglones_leidos_devuelve_ok_false():
    with (
        patch("app.main.extraer_listado_consolidado", return_value={"renglones": []}),
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
    ):
        respuesta = cliente.post(
            "/compras/nueva/listado/leer",
            files={"foto": ("planilla.jpg", _imagen_de_prueba(), "image/jpeg")},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is False
    assert "error" in datos


def test_subir_foto_listado_sube_una_vez_y_devuelve_la_ruta():
    with patch("app.main.subir_foto_comanda", return_value="2026-08-15/listado-abc123.jpg") as mock_subir:
        respuesta = cliente.post(
            "/compras/nueva/listado/subir-foto",
            data={"foto_preview": FOTO_PREVIEW_DE_PRUEBA},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is True
    assert datos["foto_ruta"] == "2026-08-15/listado-abc123.jpg"
    mock_subir.assert_called_once_with(b"hello", "listado")


def test_subir_foto_listado_data_uri_invalida_devuelve_ok_false():
    respuesta = cliente.post(
        "/compras/nueva/listado/subir-foto",
        data={"foto_preview": "esto no es una data uri"},
    )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is False
    assert "error" in datos


def test_subir_foto_listado_si_falla_la_subida_devuelve_ok_false():
    with patch("app.main.subir_foto_comanda", side_effect=RuntimeError("Supabase Storage rechazó la subida (403)")):
        respuesta = cliente.post(
            "/compras/nueva/listado/subir-foto",
            data={"foto_preview": FOTO_PREVIEW_DE_PRUEBA},
        )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["ok"] is False
    assert "error" in datos


def test_confirmar_compra_foto_con_foto_ruta_ya_subida_no_vuelve_a_subir():
    # Regresión: en el listado consolidado, a partir del segundo proveedor
    # guardado el form manda foto_ruta_ya_subida — no hay que llamar a
    # subir_foto_comanda de nuevo, hay que usar esa ruta tal cual.
    datos = _datos_confirmar_foto()
    datos["foto_ruta_ya_subida"] = "2026-08-15/listado-abc123.jpg"
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=200),
        patch("app.main.subir_foto_comanda") as mock_subir,
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.aprender_articulo"),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto/confirmar",
            data=datos,
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_subir.assert_not_called()
    mock_crear.assert_called_once_with(
        HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 5000.0, None, "Clark", "2026-08-15/listado-abc123.jpg"
    )


def test_confirmar_compra_foto_sin_foto_ruta_ya_subida_sigue_igual_que_antes():
    # Regresión: sin ese campo (comanda única y múltiples fotos, que nunca
    # lo mandan), el comportamiento no cambia — sigue subiendo a partir de
    # foto_preview como siempre.
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=200),
        patch("app.main.subir_foto_comanda", return_value="2026-08-06/n07p41-123-abcdef12.jpg") as mock_subir,
        patch("app.main.crear_compra") as mock_crear,
        patch("app.main.aprender_articulo"),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto/confirmar",
            data=_datos_confirmar_foto(foto_preview=FOTO_PREVIEW_DE_PRUEBA),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_subir.assert_called_once_with(b"hello", "N07P41")
    assert mock_crear.call_args.args[-1] == "2026-08-06/n07p41-123-abcdef12.jpg"


# --- /negociar: cuadro para negociar precios (Bajas / Subas / Resumen bajo objetivo), por cliente elegido ---

ARTICULOS_NEGOCIAR_DE_PRUEBA = [
    {
        "articulo_nombre": "Tomate Cherry",
        "fresco": True,
        "variacion": "bajo",
        "costo_anterior": 600.0,
        "costo_actual": 500.0,
        "precio_sugerido": 900.0,
        "precio_vigente": 950.0,  # vigente >= sugerido -> ✓
        "utilidad_aproximada": 0.30,  # por encima del objetivo, no entra al resumen
    },
    {
        "articulo_nombre": "Mango",
        "fresco": True,
        "variacion": "subio",
        "costo_anterior": 300.0,
        "costo_actual": 400.0,
        "precio_sugerido": 800.0,
        "precio_vigente": 700.0,  # vigente < sugerido -> 🔴
        "utilidad_aproximada": 0.10,  # bajo el objetivo (0.20) -> resumen
    },
    {
        "articulo_nombre": "Palta",
        "fresco": False,  # no fresco: no entra en Bajas ni Subas
        "variacion": None,
        "costo_anterior": None,
        "costo_actual": 900.0,
        "precio_sugerido": 1300.0,
        "precio_vigente": 800.0,
        "utilidad_aproximada": -0.05,  # peor utilidad -> primero en el resumen
    },
]

FICHAS_NEGOCIAR_DE_PRUEBA = [{"id": 1, "articulo_id": 1, "articulo_nombre": "Tomate Cherry"}]


def test_ver_negociar_sin_cliente_muestra_selector():
    # Mismo patrón que /fichas: sin cliente_id en la URL, solo el
    # selector — no se calcula nada todavía.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA) as mock_listar,
        patch("app.main.calcular_listado_para_negociar_precios") as mock_calcular,
    ):
        respuesta = cliente.get("/negociar")

    assert respuesta.status_code == 200
    assert "Elegí un cliente para ver su cuadro de negociación." in respuesta.text
    assert '<option value="1"' in respuesta.text
    assert "Día" in respuesta.text
    assert "Otro cliente" in respuesta.text
    mock_listar.assert_called_once()
    mock_calcular.assert_not_called()


def test_ver_negociar_con_cliente_muestra_titulo_y_nombre_del_cliente():
    # La pantalla ya no es "de prueba": título fijo + nombre del cliente
    # elegido, sin ningún "(prueba)" en ningún lado.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Márgenes por Artículo" in respuesta.text
    assert "Cliente: <strong>Día</strong>" in respuesta.text
    assert "(prueba)" not in respuesta.text


def test_ver_negociar_bajas_incluye_fresco_que_bajo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA) as mock_calcular,
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    assert respuesta.status_code == 200
    # El motor genérico recibe el cliente_id elegido, no uno fijo.
    assert mock_calcular.call_args[0][0] == 1
    assert "Bajas" in respuesta.text
    assert "Tomate Cherry" in respuesta.text
    assert "$950" in respuesta.text
    assert "✓" in respuesta.text


def test_ver_negociar_subas_incluye_fresco_que_subio():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Mango" in respuesta.text
    assert "🔴" in respuesta.text


def test_ver_negociar_no_fresco_no_aparece_en_bajas_ni_subas():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    import re

    bloque_bajas = re.search(r"<h2>Bajas.*?</h2>(.*?)<h2>Subas", respuesta.text, re.S).group(1)
    bloque_subas = re.search(r"<h2>Subas.*?</h2>(.*?)<h2>\s*Resumen", respuesta.text, re.S).group(1)
    assert "Palta" not in bloque_bajas
    assert "Palta" not in bloque_subas


def test_ver_negociar_resumen_ordena_de_peor_a_mejor_y_filtra_bajo_objetivo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    import re

    bloque_resumen = re.search(r"<h2>\s*Resumen.*?(?=<h2>Todos los artículos)", respuesta.text, re.S).group(0)
    # Palta (-5%, peor) tiene que aparecer antes que Mango (10%).
    pos_palta = bloque_resumen.index("Palta")
    pos_mango = bloque_resumen.index("Mango")
    assert pos_palta < pos_mango
    # Tomate Cherry (30%, por encima del objetivo) no entra al resumen.
    assert "Tomate Cherry" not in bloque_resumen
    assert "utilidad-negativa" in bloque_resumen
    assert "utilidad-baja" in bloque_resumen
    # Regresión: el encabezado de la columna era un literal fijo "P. Día",
    # ahora es genérico (la pantalla puede ser de cualquier cliente).
    assert "P. Día" not in respuesta.text
    assert "<th>Precio vigente</th>" in respuesta.text


def test_ver_negociar_todos_los_articulos_lista_todos_ordenados_por_utilidad_descendente():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    import re

    bloque_todos = re.search(r"<h2>Todos los artículos.*", respuesta.text, re.S).group(0)
    # Tomate Cherry (30%) > Mango (10%) > Palta (-5%) — a diferencia del
    # resumen bajo objetivo, acá SÍ tienen que aparecer los 3, incluido el
    # que está bien (Tomate Cherry).
    pos_tomate = bloque_todos.index("Tomate Cherry")
    pos_mango = bloque_todos.index("Mango")
    pos_palta = bloque_todos.index("Palta")
    assert pos_tomate < pos_mango < pos_palta


def test_ver_negociar_todos_los_articulos_utilidad_ok_sin_color_de_alerta():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    import re

    bloque_todos = re.search(r"<h2>Todos los artículos.*", respuesta.text, re.S).group(0)
    fila_tomate = re.search(r"<tr>\s*<td>Tomate Cherry</td>.*?</tr>", bloque_todos, re.S).group(0)
    # Tomate Cherry (30%, por encima del objetivo de 20%) no lleva ninguna
    # de las clases de alerta — solo Mango y Palta, que sí están mal.
    assert "utilidad-negativa" not in fila_tomate
    assert "utilidad-baja" not in fila_tomate
    assert "30,0%" in fila_tomate


def test_ver_negociar_sin_fichas_muestra_aviso_y_link_para_cargarlas():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=[]),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "todavía no tiene fichas de logística cargadas" in respuesta.text
    assert 'href="/fichas?cliente_id=1"' in respuesta.text
    # Igual muestra la pantalla completa (secciones vacías, no en blanco).
    assert "Ningún artículo fresco bajó de costo" in respuesta.text


def test_ver_negociar_con_fichas_pero_sin_articulos_recientes_muestra_aviso_distinto():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "ningún artículo tuvo compra en los últimos 15 días" in respuesta.text
    assert "todavía no tiene fichas de logística cargadas" not in respuesta.text


def test_ver_negociar_sin_utilidad_objetivo_muestra_aviso():
    clientes_sin_utilidad = [{"id": 1, "nombre": "Cliente Nuevo", "descuento": 0.0, "adicionales": 0.0, "utilidad_objetivo": None}]
    with (
        patch("app.main.listar_clientes", return_value=clientes_sin_utilidad),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "no tiene utilidad objetivo cargada todavía" in respuesta.text
    assert 'href="/clientes/1/editar"' in respuesta.text


def test_ver_negociar_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/negociar?cliente_id=999")

    assert respuesta.status_code == 404


def test_ver_negociar_error_al_listar_clientes_da_500():
    with patch("app.main.listar_clientes", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/negociar")

    assert respuesta.status_code == 500


def test_ver_negociar_error_de_base_da_500():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.get("/negociar?cliente_id=1")

    assert respuesta.status_code == 500


def test_ver_negociar_otro_cliente_no_muestra_datos_de_dia():
    # Regresión explícita: elegir un cliente que no es "Día" tiene que
    # calcular para ESE cliente_id, no para el 1 fijo de antes.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_NEGOCIAR_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]) as mock_calcular,
    ):
        respuesta = cliente.get("/negociar?cliente_id=2")

    assert respuesta.status_code == 200
    assert mock_calcular.call_args[0][0] == 2
    assert "Cliente: <strong>Otro cliente</strong>" in respuesta.text


def test_costeo_prueba_ya_no_existe():
    # La pantalla de depuración se retiró: la negociación real ahora se
    # accede eligiendo cliente en /negociar.
    respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 404


# --- /precios: botonera de Lista de Precios ---


def test_ver_precios_muestra_la_botonera_con_los_seis_accesos_en_orden():
    respuesta = cliente.get("/precios")

    assert respuesta.status_code == 200
    assert 'href="/precios/cargar"' in respuesta.text
    assert 'href="/precios/cargar-foto"' in respuesta.text
    assert 'href="/precios/consultar"' in respuesta.text
    assert 'href="/negociar"' in respuesta.text
    assert 'href="/precios/resultado-negociacion"' in respuesta.text
    assert 'href="/precios/generar-listado"' in respuesta.text
    assert "Carga Manual de Precios" in respuesta.text
    assert "Carga Foto Precios" in respuesta.text
    assert "Consultar Precios" in respuesta.text
    assert "Márgenes por Artículo" in respuesta.text
    assert "Resultado Negociación" in respuesta.text
    assert "Cargar Precios Nuevos" not in respuesta.text
    assert "Próximamente" in respuesta.text

    orden = [
        "Carga Manual de Precios",
        "Carga Foto Precios",
        "Consultar Precios",
        "Márgenes por Artículo",
        "Resultado Negociación",
        "Generar Listado Actualizado",
    ]
    posiciones = [respuesta.text.index(texto) for texto in orden]
    assert posiciones == sorted(posiciones)


def test_ver_precios_guardado_muestra_mensaje_de_confirmacion():
    respuesta = cliente.get("/precios?guardado=3")

    assert respuesta.status_code == 200
    assert "Se cargaron 3 precios." in respuesta.text


def test_ver_precios_guardado_cero_muestra_mensaje_sin_cambios():
    respuesta = cliente.get("/precios?guardado=0")

    assert respuesta.status_code == 200
    assert "No se guardó ningún cambio" in respuesta.text


def test_ver_precios_sin_guardado_no_muestra_mensaje():
    respuesta = cliente.get("/precios")

    assert respuesta.status_code == 200
    assert "Se cargaron" not in respuesta.text
    assert "No se guardó ningún cambio" not in respuesta.text


def test_ver_precios_guardado_y_listado_muestra_mensaje_de_guardado_y_generado():
    respuesta = cliente.get("/precios?guardado=2&listado=1")

    assert respuesta.status_code == 200
    assert "Se guardaron 2 precios y se generó el listado." in respuesta.text


def test_ver_precios_guardado_cero_y_listado_muestra_mensaje_igual():
    respuesta = cliente.get("/precios?guardado=0&listado=1")

    assert respuesta.status_code == 200
    assert "Los precios ya estaban al día — se generó el listado igual." in respuesta.text


# --- /precios/consultar: consulta de precios vigentes (por cliente+fecha, o cliente+articulo+fecha) ---

FICHAS_PRECIOS_DE_PRUEBA = [
    {"id": 1, "articulo_id": 1, "articulo_nombre": "Tomate Cherry"},
    {"id": 2, "articulo_id": 2, "articulo_nombre": "Mango"},
]

PRECIOS_VIGENTES_DE_PRUEBA = [
    {"articulo_id": 1, "precio": 500.0},
    {"articulo_id": 2, "precio": 350.0},
]


def test_ver_precios_consultar_sin_cliente_muestra_selector():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente") as mock_precios,
    ):
        respuesta = cliente.get("/precios/consultar")

    assert respuesta.status_code == 200
    assert "Elegí un cliente para ver sus precios." in respuesta.text
    assert "Día" in respuesta.text
    mock_precios.assert_not_called()


def test_ver_precios_consultar_con_cliente_lista_todos_los_precios_vigentes():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA) as mock_precios,
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Tomate Cherry" in respuesta.text
    assert "$500" in respuesta.text
    assert "Mango" in respuesta.text
    assert "$350" in respuesta.text
    # Sin fecha en la URL, consulta a HOY.
    assert mock_precios.call_args[0] == (1, HOY_DE_PRUEBA)


def test_ver_precios_consultar_fecha_pasada_usa_esa_fecha():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]) as mock_precios,
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1&fecha=2026-01-15")

    assert respuesta.status_code == 200
    assert mock_precios.call_args[0][1] == date(2026, 1, 15)
    assert "15/01/2026" in respuesta.text


def test_ver_precios_consultar_fecha_invalida_muestra_error():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1&fecha=no-es-una-fecha")

    assert respuesta.status_code == 200
    assert "La fecha no es válida." in respuesta.text


def test_ver_precios_consultar_articulo_puntual_filtra_a_ese_solo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1&articulo_id=2")

    assert respuesta.status_code == 200
    # El selector de artículo sigue listando todos (para poder elegir
    # otro), pero el RESULTADO tiene que quedar filtrado a uno solo.
    import re

    bloque_resultado = re.search(r'<h2>Precios vigentes.*?</div>\s*</div>', respuesta.text, re.S).group(0)
    assert "Mango" in bloque_resultado
    assert "Tomate Cherry" not in bloque_resultado


def test_ver_precios_consultar_articulo_puntual_sin_precio_vigente_muestra_mensaje():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1&articulo_id=2")

    assert respuesta.status_code == 200
    assert "no tiene precio vigente" in respuesta.text


def test_ver_precios_consultar_cliente_sin_precios_muestra_mensaje():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "no tiene ningún precio vigente" in respuesta.text


def test_ver_precios_consultar_incluye_link_para_cargar():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1")

    assert 'href="/precios/cargar?cliente_id=1"' in respuesta.text


def test_ver_precios_consultar_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/consultar?cliente_id=999")

    assert respuesta.status_code == 404


def test_ver_precios_consultar_error_de_base_da_500():
    with patch("app.main.listar_clientes", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/precios/consultar")

    assert respuesta.status_code == 500


def test_ver_precios_consultar_articulo_id_vacio_trae_el_listado_completo():
    # Regresión: "Todos los artículos" manda articulo_id="" (el <select>
    # sin elegir nada puntual) — antes esto rompía con un 422 crudo de
    # FastAPI ("Input should be a valid integer") en vez de traer el
    # listado completo, que es lo que realmente significa un campo vacío.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1&fecha=2026-08-15&articulo_id=")

    assert respuesta.status_code == 200
    assert "Tomate Cherry" in respuesta.text
    assert "Mango" in respuesta.text


def test_ver_precios_consultar_articulo_id_no_numerico_no_rompe_trae_el_listado_completo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1&articulo_id=no-es-un-numero")

    assert respuesta.status_code == 200
    assert "Tomate Cherry" in respuesta.text
    assert "Mango" in respuesta.text


def test_ver_precios_consultar_cliente_id_vacio_muestra_el_selector_sin_romper():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/consultar?cliente_id=")

    assert respuesta.status_code == 200
    assert "Elegí un cliente para ver sus precios." in respuesta.text


def test_ver_precios_consultar_url_no_repite_cliente_id():
    # Regresión: el form tenía un input hidden "cliente_id" duplicando el
    # <select> del mismo nombre, generando ?cliente_id=1&...&cliente_id=1.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1")

    assert respuesta.text.count('name="cliente_id"') == 1


def test_ver_precios_consultar_incluye_buscador_de_articulo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1")

    assert 'id="articulo_texto"' in respuesta.text
    assert "actualizarListaArticulos" in respuesta.text
    assert '{ id: 1, nombre: "Tomate Cherry" }' in respuesta.text
    assert '{ id: 2, nombre: "Mango" }' in respuesta.text


def test_ver_precios_consultar_articulo_elegido_muestra_boton_para_limpiar():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1&articulo_id=2")

    assert "Ver todos los artículos" in respuesta.text
    assert 'value="Mango"' in respuesta.text


def test_ver_precios_consultar_con_resultados_muestra_boton_exportar():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1")

    assert 'id="boton-exportar"' in respuesta.text
    assert "/precios/consultar/exportar-pdf?cliente_id=1&fecha=" in respuesta.text
    assert "/precios/consultar/exportar-excel?cliente_id=1&fecha=" in respuesta.text


def test_ver_precios_consultar_sin_resultados_no_muestra_boton_exportar():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1")

    assert 'id="boton-exportar"' not in respuesta.text


# --- /precios/consultar/exportar-pdf y exportar-excel ---


def _texto_del_pdf_de_respuesta(pdf_bytes: bytes) -> str:
    documento = pdfium.PdfDocument(pdf_bytes)
    return "\n".join(pagina.get_textpage().get_text_range() for pagina in documento)


def _texto_sin_leyenda_de_respuesta(pdf_bytes: bytes) -> str:
    # La leyenda fija se repite en el encabezado de CADA página (para que
    # se vea aunque una sección se corte entre dos hojas) — se descarta acá
    # para contar los badges reales sin que la paginación lo altere.
    from core.exportar_precios import LEYENDA_PRECIO_NUEVO

    return _texto_del_pdf_de_respuesta(pdf_bytes).replace(LEYENDA_PRECIO_NUEVO, "")


FICHAS_EXPORTACION_DE_PRUEBA = [
    {"id": 1, "articulo_id": 1, "articulo_nombre": "Tomate Cherry", "unidad_venta": "kilo"},
    {"id": 2, "articulo_id": 2, "articulo_nombre": "Mango", "unidad_venta": "unidad"},
]

ARTICULOS_EXPORTACION_DE_PRUEBA = [
    {"id": 1, "nombre": "Tomate Cherry", "grupo": "hortaliza"},
    {"id": 2, "nombre": "Mango", "grupo": "fruta"},
]


def _precios_vigentes_exportacion(vigente_desde_articulo_1):
    return [
        {"articulo_id": 1, "precio": 500.0, "vigente_desde": vigente_desde_articulo_1},
        {"articulo_id": 2, "precio": 350.0, "vigente_desde": date(2026, 1, 1)},
    ]


def test_exportar_precios_pdf_devuelve_archivo_adjunto():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(HOY_DE_PRUEBA),
        ),
    ):
        respuesta = cliente.get(f"/precios/consultar/exportar-pdf?cliente_id=1&fecha={HOY_DE_PRUEBA.isoformat()}")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert "attachment" in respuesta.headers["content-disposition"]
    assert "Lista_Precios_D" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"%PDF")


def test_exportar_precios_pdf_hoy_resalta_el_que_cambio_hoy():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(HOY_DE_PRUEBA),
        ),
    ):
        respuesta = cliente.get(f"/precios/consultar/exportar-pdf?cliente_id=1&fecha={HOY_DE_PRUEBA.isoformat()}")

    texto = _texto_sin_leyenda_de_respuesta(respuesta.content)
    assert texto.count("Nuevo precio") == 1


def test_exportar_precios_pdf_fecha_pasada_no_resalta_nada():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(date(2026, 1, 15)),
        ),
    ):
        respuesta = cliente.get("/precios/consultar/exportar-pdf?cliente_id=1&fecha=2026-01-15")

    texto = _texto_sin_leyenda_de_respuesta(respuesta.content)
    assert "Nuevo precio" not in texto


def test_exportar_precios_pdf_separa_por_grupo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(date(2026, 1, 1)),
        ),
    ):
        respuesta = cliente.get("/precios/consultar/exportar-pdf?cliente_id=1&fecha=2026-01-01")

    texto = _texto_del_pdf_de_respuesta(respuesta.content)
    assert texto.index("FRUTA") < texto.index("HORTALIZA")
    assert "Mango" in texto[texto.index("FRUTA") : texto.index("HORTALIZA")]
    assert "Tomate Cherry" in texto[texto.index("HORTALIZA") :]


FICHAS_EXPORTACION_NOMBRE_CLIENTE_DE_PRUEBA = [
    # Con nombre_cliente cargado: la lista exportada tiene que usar ESE
    # nombre, no el interno del catálogo (articulo_nombre).
    {"id": 1, "articulo_id": 1, "articulo_nombre": "Mzn Red", "unidad_venta": "kilo", "nombre_cliente": "Manzana Red Elegida"},
    # Sin nombre_cliente cargado: se cae al nombre del catálogo.
    {"id": 2, "articulo_id": 2, "articulo_nombre": "Anana", "unidad_venta": "unidad", "nombre_cliente": None},
]


def test_exportar_precios_pdf_usa_nombre_cliente_de_la_ficha_no_el_interno():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_NOMBRE_CLIENTE_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(date(2026, 1, 1)),
        ),
    ):
        respuesta = cliente.get("/precios/consultar/exportar-pdf?cliente_id=1&fecha=2026-01-01")

    texto = _texto_del_pdf_de_respuesta(respuesta.content)
    assert "Manzana Red Elegida" in texto
    assert "Mzn Red" not in texto
    # Sin nombre_cliente cargado, se cae al nombre del catálogo.
    assert "Anana" in texto


def test_exportar_precios_pdf_cliente_invalido_da_400():
    respuesta = cliente.get("/precios/consultar/exportar-pdf?cliente_id=abc&fecha=2026-08-16")

    assert respuesta.status_code == 400


def test_exportar_precios_pdf_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/consultar/exportar-pdf?cliente_id=999&fecha=2026-08-16")

    assert respuesta.status_code == 404


def test_exportar_precios_pdf_fecha_invalida_da_400():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/consultar/exportar-pdf?cliente_id=1&fecha=no-es-una-fecha")

    assert respuesta.status_code == 400


def test_exportar_precios_excel_devuelve_archivo_adjunto():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(HOY_DE_PRUEBA),
        ),
    ):
        respuesta = cliente.get(f"/precios/consultar/exportar-excel?cliente_id=1&fecha={HOY_DE_PRUEBA.isoformat()}")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"PK")  # xlsx es un zip


def test_exportar_precios_excel_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/consultar/exportar-excel?cliente_id=999&fecha=2026-08-16")

    assert respuesta.status_code == 404


# --- /precios/cargar/guardar-y-exportar-pdf y guardar-y-exportar-excel: "Guardar y generar listado"
# de Carga Manual — guarda de verdad los pendientes y arma el PDF/Excel con lo recién guardado ---


def test_guardar_y_exportar_precios_cargar_manual_pdf_guarda_y_devuelve_archivo():
    precios_tras_guardar = [
        {"articulo_id": 1, "precio": 500.0, "vigente_desde": date(2026, 1, 1)},
        {"articulo_id": 2, "precio": 400.0, "vigente_desde": HOY_DE_PRUEBA},
    ]
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=precios_tras_guardar),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar/guardar-y-exportar-pdf",
            data={"cliente_id": "1", "pendiente_precio_2": "400", "pendiente_original_2": "350"},
        )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert "attachment" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"%PDF")
    assert respuesta.headers["x-cantidad-guardada"] == "1"
    mock_guardar.assert_called_once_with(1, [{"articulo_id": 2, "precio": 400.0}])

    # El archivo generado tiene que reflejar lo recién guardado: Mango
    # (el que se acaba de pactar) resaltado, Tomate Cherry (sin tocar) no.
    texto = _texto_sin_leyenda_de_respuesta(respuesta.content)
    bloque_frutas = texto[texto.index("FRUTA") : texto.index("HORTALIZA")]
    bloque_hortalizas = texto[texto.index("HORTALIZA") :]
    assert bloque_frutas.count("Nuevo precio") == 1
    assert "Nuevo precio" not in bloque_hortalizas


def test_guardar_y_exportar_precios_cargar_manual_excel_guarda_y_devuelve_archivo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(date(2026, 1, 1)),
        ),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar/guardar-y-exportar-excel",
            data={"cliente_id": "1", "pendiente_precio_2": "400", "pendiente_original_2": "350"},
        )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"PK")  # xlsx es un zip
    assert respuesta.headers["x-cantidad-guardada"] == "1"
    mock_guardar.assert_called_once()


def test_guardar_y_exportar_precios_cargar_manual_pdf_usa_nombre_cliente_de_la_ficha():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_NOMBRE_CLIENTE_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(date(2026, 1, 1)),
        ),
        patch("app.main.guardar_precios_cliente"),
    ):
        respuesta = cliente.post(
            "/precios/cargar/guardar-y-exportar-pdf",
            data={"cliente_id": "1", "pendiente_precio_1": "950", "pendiente_original_1": "890"},
        )

    texto = _texto_del_pdf_de_respuesta(respuesta.content)
    assert "Manzana Red Elegida" in texto
    assert "Mzn Red" not in texto
    assert "Anana" in texto


def test_guardar_y_exportar_precios_cargar_manual_pdf_cliente_invalido_da_400():
    respuesta = cliente.post("/precios/cargar/guardar-y-exportar-pdf", data={"cliente_id": "abc"})

    assert respuesta.status_code == 400


def test_guardar_y_exportar_precios_cargar_manual_pdf_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.post("/precios/cargar/guardar-y-exportar-pdf", data={"cliente_id": "999"})

    assert respuesta.status_code == 404


def test_guardar_y_exportar_precios_cargar_manual_pdf_precio_invalido_da_400_y_no_guarda():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar/guardar-y-exportar-pdf",
            data={"cliente_id": "1", "pendiente_precio_2": "no-es-un-numero"},
        )

    assert respuesta.status_code == 400
    mock_guardar.assert_not_called()


# --- /precios/cargar: carga de precios nuevos uno a la vez, con revisión antes de guardar ---


def test_ver_cargar_precios_sin_cliente_muestra_selector():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/cargar")

    assert respuesta.status_code == 200
    assert "Elegí un cliente para cargarle precios nuevos." in respuesta.text


def test_ver_cargar_precios_embebe_el_catalogo_con_precio_vigente():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/precios/cargar?cliente_id=1")

    assert respuesta.status_code == 200
    assert 'id="articulo_texto"' in respuesta.text
    assert "actualizarListaArticulos" in respuesta.text
    assert '{ id: 1, nombre: "Tomate Cherry", precioVigente: 500.0 }' in respuesta.text
    assert '{ id: 2, nombre: "Mango", precioVigente: 350.0 }' in respuesta.text


def test_ver_cargar_precios_articulo_sin_precio_previo_embebe_null():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/precios/cargar?cliente_id=1")

    assert respuesta.status_code == 200
    assert '{ id: 1, nombre: "Tomate Cherry", precioVigente: null }' in respuesta.text


def test_ver_cargar_precios_incluye_boton_guardar_y_generar_listado():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/precios/cargar?cliente_id=1")

    assert respuesta.status_code == 200
    assert 'id="boton-guardar-y-generar"' in respuesta.text
    assert "Guardar y generar listado" in respuesta.text
    assert "guardarYGenerarListado" in respuesta.text
    assert "/precios/cargar/guardar-y-exportar-pdf" in respuesta.text
    assert "/precios/cargar/guardar-y-exportar-excel" in respuesta.text
    # El botón "Exportar sin guardar" que había antes ya no va.
    assert 'id="boton-exportar"' not in respuesta.text


def test_ver_cargar_precios_boton_cargar_otro_precio_va_en_azul_y_hay_cancelar():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/precios/cargar?cliente_id=1")

    assert respuesta.status_code == 200
    # "Cargar otro Precio" en azul sólido (clase "boton" a secas), no el
    # outline blanco-y-azul de "boton-secundario".
    assert '<button type="button" class="boton" onclick="cargarOtroPrecio()">Cargar otro Precio</button>' in respuesta.text
    # "Cancelar" junto a "Guardar y terminar", mismo criterio de
    # visibilidad (solo si hay algo cargado o un artículo elegido).
    assert 'class="boton-peligro" id="boton-cancelar-carga"' in respuesta.text
    assert 'onclick="cancelarTodo()"' in respuesta.text
    assert '"boton-cancelar-carga").style.display' in respuesta.text


def test_ver_cargar_precios_cliente_sin_fichas_muestra_mensaje():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=[]),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/precios/cargar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "sin fichas no hay artículos a los que ponerle precio" in respuesta.text


# --- /precios/cargar: panel "Ver negociación" (estado oficial, con los precios ya vigentes) ---

ARTICULOS_NEGOCIACION_DE_PRUEBA = [
    {
        "articulo_nombre": "Tomate Cherry",
        "fresco": True,
        "variacion": "bajo",
        "costo_anterior": 300.0,
        "costo_actual": 280.0,
        "precio_sugerido": 420.0,
        "precio_vigente": 500.0,  # vigente >= sugerido -> ✓
        "utilidad_aproximada": 0.30,
    },
]


def test_ver_cargar_precios_incluye_boton_y_panel_de_negociacion():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIACION_DE_PRUEBA) as mock_negociar,
    ):
        respuesta = cliente.get("/precios/cargar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Ver negociación" in respuesta.text
    assert 'id="panel-negociacion"' in respuesta.text
    assert "abrirNegociacion" in respuesta.text
    assert "cerrarNegociacion" in respuesta.text
    # Reusa la misma función que /negociar, con el mismo cliente_id.
    assert mock_negociar.call_args[0][0] == 1
    # El cuadro embebido tiene que traer los datos reales de la negociación.
    assert "Bajas (frescos que bajaron de costo)" in respuesta.text
    assert "Tomate Cherry" in respuesta.text
    assert "$420" in respuesta.text
    # Mientras el panel está abierto, la barra de navegación (con el ícono
    # "Inicio") queda inhabilitada — evita que un toque se cuele por un
    # resquicio del overlay en Safari/iOS y navegue a /inicio en vez de
    # cerrar el panel.
    assert 'querySelector(".barra-navegacion").style.pointerEvents = "none"' in respuesta.text
    assert 'querySelector(".barra-navegacion").style.pointerEvents = ""' in respuesta.text


def test_ver_cargar_precios_panel_de_negociacion_no_usa_pendientes_sin_guardar():
    # El panel se arma UNA vez al cargar la pantalla, con lo que ya está
    # guardado — no hay forma de que use nada tipeado en el navegador
    # porque en ese momento todavía no se tipeó nada.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]) as mock_negociar,
    ):
        cliente.get("/precios/cargar?cliente_id=1")

    # Un solo cálculo, en el momento de armar la pantalla.
    mock_negociar.assert_called_once()


def test_ver_cargar_precios_sin_fichas_igual_muestra_boton_de_negociacion():
    # Aunque no haya fichas para cargar precios, el botón de negociación
    # sigue disponible (el panel tiene su propio aviso de "sin fichas").
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=[]),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/precios/cargar?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Ver negociación" in respuesta.text
    assert 'id="panel-negociacion"' in respuesta.text


def test_ver_cargar_precios_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/cargar?cliente_id=999")

    assert respuesta.status_code == 404


def test_ver_cargar_precios_error_de_base_da_500():
    with patch("app.main.listar_clientes", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/precios/cargar")

    assert respuesta.status_code == 500


def _datos_pendientes_cargar_precios(**overrides):
    datos = {
        "cliente_id": "1",
        "pendiente_precio_2": "380",
        "pendiente_original_2": "350.0",
    }
    datos.update(overrides)
    return datos


def test_cargar_precios_guarda_los_pendientes_y_redirige_con_cantidad():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar", data=_datos_pendientes_cargar_precios(), follow_redirects=False
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/precios?guardado=1"
    mock_guardar.assert_called_once_with(1, [{"articulo_id": 2, "precio": 380.0}])


def test_cargar_precios_varios_pendientes_se_guardan_todos_juntos():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar",
            data={
                "cliente_id": "1",
                "pendiente_precio_1": "520",
                "pendiente_original_1": "500.0",
                "pendiente_precio_2": "380",
                "pendiente_original_2": "350.0",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/precios?guardado=2"
    cambios_guardados = mock_guardar.call_args[0][1]
    assert {"articulo_id": 1, "precio": 520.0} in cambios_guardados
    assert {"articulo_id": 2, "precio": 380.0} in cambios_guardados


def test_cargar_precios_articulo_sin_precio_previo_genera_alta():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar",
            data=_datos_pendientes_cargar_precios(pendiente_original_2=""),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [{"articulo_id": 2, "precio": 380.0}])


def test_cargar_precios_pendiente_igual_al_vigente_no_genera_fila():
    # No se revalida contra la base al guardar, pero si lo que se cargó es
    # igual al vigente que se snapshoteó al elegir el artículo (viaja como
    # "original"), no hace falta una fila nueva en el historial.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar",
            data=_datos_pendientes_cargar_precios(pendiente_precio_2="350.0"),
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/precios?guardado=0"
    mock_guardar.assert_called_once_with(1, [])


def test_cargar_precios_sin_pendientes_no_guarda_nada():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post("/precios/cargar", data={"cliente_id": "1"}, follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/precios?guardado=0"
    mock_guardar.assert_called_once_with(1, [])


def test_cargar_precios_invalido_da_400():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar", data=_datos_pendientes_cargar_precios(pendiente_precio_2="abc")
        )

    assert respuesta.status_code == 400
    mock_guardar.assert_not_called()


def test_cargar_precios_cero_o_negativo_da_400():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar", data=_datos_pendientes_cargar_precios(pendiente_precio_2="0")
        )

    assert respuesta.status_code == 400
    mock_guardar.assert_not_called()


def test_cargar_precios_error_de_base_da_500():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.guardar_precios_cliente", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.post("/precios/cargar", data=_datos_pendientes_cargar_precios())

    assert respuesta.status_code == 500


def test_cargar_precios_cliente_invalido_da_400():
    respuesta = cliente.post("/precios/cargar", data={"cliente_id": "abc"})

    assert respuesta.status_code == 400


def test_cargar_precios_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.post("/precios/cargar", data={"cliente_id": "999"})

    assert respuesta.status_code == 404


# --- /precios/cargar-foto: carga de precios leyendo un archivo (foto, PDF o Excel) con IA ---

LISTADO_PRECIOS_LEIDO_DE_PRUEBA = {
    "items": [
        {"articulo": "Tomate Cherry", "precio": 520.0, "confianza": "alta"},
        {"articulo": "algo ilegible", "precio": 999.0, "confianza": "baja"},
    ]
}


def test_ver_cargar_foto_precios_sin_cliente_muestra_selector():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/cargar-foto")

    assert respuesta.status_code == 200
    assert "Elegí un cliente para subirle un listado de precios." in respuesta.text


def test_ver_cargar_foto_precios_con_cliente_muestra_boton_de_subir():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/cargar-foto?cliente_id=1")

    assert respuesta.status_code == 200
    assert 'id="archivo"' in respuesta.text
    assert 'accept="image/*,.pdf,.xlsx"' in respuesta.text


def test_ver_cargar_foto_precios_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/precios/cargar-foto?cliente_id=999")

    assert respuesta.status_code == 404


def test_leer_foto_precios_matchea_y_muestra_pantalla_de_revision():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=[]),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
        patch("app.main.extraer_listado_precios_de_imagenes", return_value=LISTADO_PRECIOS_LEIDO_DE_PRUEBA) as mock_extraer,
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto",
            data={"cliente_id": "1"},
            files={"archivo": ("lista.jpg", b"contenido falso de una foto", "image/jpeg")},
        )

    assert respuesta.status_code == 200
    assert "Tomate Cherry" in respuesta.text
    assert 'value="520.0"' in respuesta.text
    assert "Precio vigente: $500" in respuesta.text
    assert "⚠ revisar" in respuesta.text  # el segundo ítem, no matcheado
    mock_extraer.assert_called_once_with([b"contenido falso de una foto"])


def test_leer_foto_precios_pantalla_revision_incluye_boton_guardar_y_generar_listado():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=[]),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_VIGENTES_DE_PRUEBA),
        patch("app.main.extraer_listado_precios_de_imagenes", return_value=LISTADO_PRECIOS_LEIDO_DE_PRUEBA),
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto",
            data={"cliente_id": "1"},
            files={"archivo": ("lista.jpg", b"contenido falso de una foto", "image/jpeg")},
        )

    assert 'id="boton-guardar-y-generar"' in respuesta.text
    assert "Guardar y generar listado" in respuesta.text
    assert "guardarYGenerarListado" in respuesta.text
    assert "/precios/cargar-foto/guardar-y-exportar-pdf" in respuesta.text
    assert "/precios/cargar-foto/guardar-y-exportar-excel" in respuesta.text
    # El botón "Exportar sin guardar" que había antes ya no va.
    assert 'id="boton-exportar"' not in respuesta.text


def test_leer_foto_precios_pdf_convierte_paginas_a_imagenes():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=[]),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
        patch("app.main.imagenes_desde_pdf", return_value=[b"pagina1", b"pagina2"]) as mock_pdf,
        patch("app.main.extraer_listado_precios_de_imagenes", return_value=LISTADO_PRECIOS_LEIDO_DE_PRUEBA) as mock_extraer,
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto",
            data={"cliente_id": "1"},
            files={"archivo": ("lista.pdf", b"contenido falso de un pdf", "application/pdf")},
        )

    assert respuesta.status_code == 200
    mock_pdf.assert_called_once_with(b"contenido falso de un pdf")
    mock_extraer.assert_called_once_with([b"pagina1", b"pagina2"])


def test_leer_foto_precios_excel_convierte_a_texto():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=[]),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
        patch("app.main.texto_desde_excel", return_value="Tomate Cherry | 520") as mock_excel,
        patch("app.main.extraer_listado_precios_de_texto", return_value=LISTADO_PRECIOS_LEIDO_DE_PRUEBA) as mock_extraer,
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto",
            data={"cliente_id": "1"},
            files={
                "archivo": (
                    "lista.xlsx",
                    b"contenido falso de un excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert respuesta.status_code == 200
    mock_excel.assert_called_once_with(b"contenido falso de un excel")
    mock_extraer.assert_called_once_with("Tomate Cherry | 520")


def test_leer_foto_precios_extension_no_soportada_muestra_mensaje_claro():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.post(
            "/precios/cargar-foto",
            data={"cliente_id": "1"},
            files={"archivo": ("lista.docx", b"contenido falso", "application/msword")},
        )

    assert respuesta.status_code == 400
    assert "No se pudo reconocer el tipo de archivo" in respuesta.text


def test_leer_foto_precios_error_de_lectura_no_rompe_muestra_mensaje_claro():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.extraer_listado_precios_de_imagenes", side_effect=RuntimeError("la IA no pudo leer nada")),
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto",
            data={"cliente_id": "1"},
            files={"archivo": ("lista.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 500
    assert "No se pudo leer el archivo" in respuesta.text
    assert "la IA no pudo leer nada" in respuesta.text


def test_leer_foto_precios_sin_ningun_articulo_muestra_mensaje_claro():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=[]),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=[]),
        patch("app.main.extraer_listado_precios_de_imagenes", return_value={"items": []}),
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto",
            data={"cliente_id": "1"},
            files={"archivo": ("lista.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 400
    assert "No se encontró ningún artículo" in respuesta.text


def test_leer_foto_precios_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.post(
            "/precios/cargar-foto",
            data={"cliente_id": "999"},
            files={"archivo": ("lista.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 404


def test_confirmar_carga_foto_precios_guarda_y_sube_el_archivo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.subir_archivo_comanda", return_value="2026-08-16/dia-123-abc.jpg") as mock_subir,
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto/confirmar",
            data={
                "cliente_id": "1",
                "cantidad_renglones": "1",
                "tipo_archivo": "foto",
                "archivo_preview": "data:image/jpeg;base64,QUJD",
                "item_0_articulo_id": "1",
                "item_0_precio_original": "500.0",
                "item_0_precio_nuevo": "520",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/precios?guardado=1"
    mock_subir.assert_called_once_with(b"ABC", "Día", "jpg", "image/jpeg")
    mock_guardar.assert_called_once_with(1, [{"articulo_id": 1, "precio": 520.0}], foto_ruta="2026-08-16/dia-123-abc.jpg")


def test_confirmar_carga_foto_precios_renglon_descartado_no_se_guarda():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.subir_archivo_comanda") as mock_subir,
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto/confirmar",
            data={
                "cliente_id": "1",
                "cantidad_renglones": "1",
                "tipo_archivo": "foto",
                "archivo_preview": "",
                "item_0_articulo_id": "1",
                "item_0_precio_original": "500.0",
                "item_0_precio_nuevo": "520",
                "item_0_descartar": "on",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_subir.assert_not_called()
    mock_guardar.assert_called_once_with(1, [], foto_ruta=None)


def test_confirmar_carga_foto_precios_error_al_subir_archivo_guarda_igual_sin_archivo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.subir_archivo_comanda", side_effect=RuntimeError("Storage caído")),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto/confirmar",
            data={
                "cliente_id": "1",
                "cantidad_renglones": "1",
                "tipo_archivo": "foto",
                "archivo_preview": "data:image/jpeg;base64,QUJD",
                "item_0_articulo_id": "1",
                "item_0_precio_original": "500.0",
                "item_0_precio_nuevo": "520",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [{"articulo_id": 1, "precio": 520.0}], foto_ruta=None)


def test_confirmar_carga_foto_precios_pdf_sube_con_extension_y_content_type_correctos():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_PRECIOS_DE_PRUEBA),
        patch("app.main.subir_archivo_comanda", return_value="ruta.pdf") as mock_subir,
        patch("app.main.guardar_precios_cliente"),
    ):
        cliente.post(
            "/precios/cargar-foto/confirmar",
            data={
                "cliente_id": "1",
                "cantidad_renglones": "1",
                "tipo_archivo": "pdf",
                "archivo_preview": "data:application/pdf;base64,QUJD",
                "item_0_articulo_id": "1",
                "item_0_precio_original": "",
                "item_0_precio_nuevo": "520",
            },
            follow_redirects=False,
        )

    mock_subir.assert_called_once_with(b"ABC", "Día", "pdf", "application/pdf")


def test_confirmar_carga_foto_precios_cliente_invalido_da_400():
    respuesta = cliente.post("/precios/cargar-foto/confirmar", data={"cliente_id": "abc"})

    assert respuesta.status_code == 400


def test_confirmar_carga_foto_precios_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.post("/precios/cargar-foto/confirmar", data={"cliente_id": "999"})

    assert respuesta.status_code == 404


# --- /precios/cargar-foto/guardar-y-exportar-pdf y guardar-y-exportar-excel: "Guardar y generar
# listado" de Carga Foto — guarda de verdad los renglones (subiendo la foto si corresponde) y arma el
# PDF/Excel con lo recién guardado ---


def test_guardar_y_exportar_precios_cargar_foto_pdf_guarda_y_devuelve_archivo():
    precios_tras_guardar = [{"articulo_id": 1, "precio": 520.0, "vigente_desde": HOY_DE_PRUEBA}]
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=precios_tras_guardar),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto/guardar-y-exportar-pdf",
            data={
                "cliente_id": "1",
                "cantidad_renglones": "1",
                "tipo_archivo": "foto",
                "archivo_preview": "",
                "item_0_articulo_id": "1",
                "item_0_precio_original": "500.0",
                "item_0_precio_nuevo": "520",
            },
        )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert "attachment" in respuesta.headers["content-disposition"]
    assert respuesta.headers["x-cantidad-guardada"] == "1"
    mock_guardar.assert_called_once_with(1, [{"articulo_id": 1, "precio": 520.0}], foto_ruta=None)

    texto = _texto_sin_leyenda_de_respuesta(respuesta.content)
    assert "Tomate Cherry" in texto
    assert texto.count("Nuevo precio") == 1


def test_guardar_y_exportar_precios_cargar_foto_excel_sube_el_archivo_y_devuelve_excel():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_EXPORTACION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_EXPORTACION_DE_PRUEBA),
        patch(
            "app.main.listar_precios_vigentes_por_cliente",
            return_value=_precios_vigentes_exportacion(HOY_DE_PRUEBA),
        ),
        patch("app.main.subir_archivo_comanda", return_value="2026-08-16/dia-123-abc.jpg") as mock_subir,
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post(
            "/precios/cargar-foto/guardar-y-exportar-excel",
            data={
                "cliente_id": "1",
                "cantidad_renglones": "1",
                "tipo_archivo": "foto",
                "archivo_preview": "data:image/jpeg;base64,QUJD",
                "item_0_articulo_id": "1",
                "item_0_precio_original": "500.0",
                "item_0_precio_nuevo": "520",
            },
        )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in respuesta.headers["content-disposition"]
    assert respuesta.headers["x-cantidad-guardada"] == "1"
    mock_subir.assert_called_once_with(b"ABC", "Día", "jpg", "image/jpeg")
    mock_guardar.assert_called_once_with(1, [{"articulo_id": 1, "precio": 520.0}], foto_ruta="2026-08-16/dia-123-abc.jpg")


def test_guardar_y_exportar_precios_cargar_foto_pdf_cliente_invalido_da_400():
    respuesta = cliente.post("/precios/cargar-foto/guardar-y-exportar-pdf", data={"cliente_id": "abc"})

    assert respuesta.status_code == 400


def test_guardar_y_exportar_precios_cargar_foto_pdf_cliente_inexistente_da_404():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.post("/precios/cargar-foto/guardar-y-exportar-pdf", data={"cliente_id": "999"})

    assert respuesta.status_code == 404


# --- /precios/generar-listado: placeholder ---


def test_ver_generar_listado_precios_muestra_en_construccion_y_vuelve_a_precios():
    respuesta = cliente.get("/precios/generar-listado")

    assert respuesta.status_code == 200
    assert "En construcción" in respuesta.text
    assert 'href="/precios"' in respuesta.text


def test_ver_resultado_negociacion_muestra_en_construccion_y_vuelve_a_precios():
    respuesta = cliente.get("/precios/resultado-negociacion")

    assert respuesta.status_code == 200
    assert "En construcción" in respuesta.text
    assert 'href="/precios"' in respuesta.text


def test_ver_inicio_muestra_las_6_areas():
    respuesta = cliente.get("/inicio")

    assert respuesta.status_code == 200
    assert '<h1>Frutamax</h1>' in respuesta.text
    assert 'href="/compras"' in respuesta.text
    assert 'href="/comercial"' in respuesta.text
    assert 'href="/logistica"' in respuesta.text
    assert 'href="/deposito"' in respuesta.text
    assert 'href="/gerencia"' in respuesta.text
    assert 'href="/sistema"' in respuesta.text


def test_ver_inicio_usa_el_nombre_de_empresa_configurado():
    # Mismo código para varias empresas, cada una con su propia base: el
    # nombre que se ve en /inicio sale de la variable de entorno
    # NOMBRE_EMPRESA (ver app/main.py), no queda fijo en "Frutamax".
    with patch.dict(templates.env.globals, {"NOMBRE_EMPRESA": "Palmala"}):
        respuesta = cliente.get("/inicio")

    assert respuesta.status_code == 200
    assert "<h1>Palmala</h1>" in respuesta.text
    assert "<title>Palmala</title>" in respuesta.text
    assert "Frutamax" not in respuesta.text


def test_ver_inicio_deposito_y_logistica_ya_no_dicen_proximamente():
    # Depósito y Logística dejaron de ser "en construcción" (existen
    # Recepción y Retiro) — sus tarjetas en /inicio tienen que verse igual
    # de activas que Compras o Comercial, no atenuadas como Gerencia (que
    # sigue sin nada adentro).
    respuesta = cliente.get("/inicio")

    assert respuesta.status_code == 200
    assert "Depósito (Próximamente)" not in respuesta.text
    assert '<a class="boton-area" href="/deposito">' in respuesta.text
    assert "Logística (Próximamente)" not in respuesta.text
    assert '<a class="boton-area" href="/logistica">' in respuesta.text
    # Gerencia sigue siendo placeholder: no se tocó.
    assert "Gerencia (Próximamente)" in respuesta.text


def test_ver_inicio_usa_los_mismos_iconos_que_la_barra_de_navegacion():
    # Regresión: el mismo ícono que representa a cada sector en la barrita
    # de arriba tiene que estar en su tarjeta de la home, para un lenguaje
    # visual consistente.
    respuesta = cliente.get("/inicio")

    assert respuesta.status_code == 200
    for sector in ("compras", "comercial", "logistica", "deposito", "gerencia", "sistema"):
        assert SECTORES[sector]["icono"] in respuesta.text


def test_ver_comercial_muestra_los_tres_accesos():
    respuesta = cliente.get("/comercial")

    assert respuesta.status_code == 200
    assert 'href="/precios"' in respuesta.text
    assert 'href="/clientes"' in respuesta.text
    assert 'href="/fichas"' in respuesta.text
    assert "Precios" in respuesta.text
    assert "Clientes" in respuesta.text
    assert "Fichas logísticas" in respuesta.text
    # Negociar precios y Lista de Precios ya no están sueltos acá — viven
    # ordenados adentro de la botonera de Precios.
    assert 'href="/negociar"' not in respuesta.text
    assert 'href="/inicio"' in respuesta.text


def test_ver_logistica_muestra_los_tres_botones_de_retiro():
    respuesta = cliente.get("/logistica")

    assert respuesta.status_code == 200
    assert "Logística" in respuesta.text
    assert 'href="/logistica/retiro/Clark"' in respuesta.text
    assert 'href="/logistica/retiro/Carro"' in respuesta.text
    assert 'href="/logistica/retiro/Pases"' in respuesta.text
    assert "En construcción" not in respuesta.text
    assert 'href="/inicio"' in respuesta.text


# --- /logistica/retiro/{tipo_retiro}: retiro de mercadería en el Mercado Central ---

COMPRAS_PENDIENTES_RETIRO_DE_PRUEBA = [
    {
        "id": 1, "guia_id": 105, "guia_punto": 1, "articulo_nombre": "Tomate Cherry", "unidad_compra": "kilo",
        "proveedor_nombre": "Saturno", "proveedor_codigo_puesto": "N07P41",
        "cantidad_cajones": 40, "contenido_por_cajon": 20, "cantidad_kilos": 800, "cantidad_fraccion": None,
    },
    {
        "id": 2, "guia_id": 105, "guia_punto": 2, "articulo_nombre": "Mango", "unidad_compra": "unidad",
        "proveedor_nombre": "Saturno", "proveedor_codigo_puesto": "N07P41",
        "cantidad_cajones": 10, "contenido_por_cajon": 12, "cantidad_kilos": None, "cantidad_fraccion": 120,
    },
]


def test_ver_logistica_retiro_agrupa_por_guia():
    with patch("app.main.listar_compras_pendientes_retiro", return_value=COMPRAS_PENDIENTES_RETIRO_DE_PRUEBA) as mock_listar:
        respuesta = cliente.get("/logistica/retiro/Clark")

    assert respuesta.status_code == 200
    mock_listar.assert_called_once_with("Clark")
    assert "Guía 105" in respuesta.text
    assert "Saturno (N07P41)" in respuesta.text
    assert "Tomate Cherry" in respuesta.text
    assert "Mango" in respuesta.text
    assert 'action="/logistica/retiro/Clark/1/retirar"' in respuesta.text
    assert 'action="/logistica/retiro/Clark/1/cancelar"' in respuesta.text


def test_ver_logistica_retiro_tipo_invalido_da_404():
    respuesta = cliente.get("/logistica/retiro/Moto")

    assert respuesta.status_code == 404


def test_ver_logistica_retiro_sin_pendientes_muestra_mensaje():
    with patch("app.main.listar_compras_pendientes_retiro", return_value=[]):
        respuesta = cliente.get("/logistica/retiro/Pases")

    assert respuesta.status_code == 200
    assert "No hay compras pendientes de retiro por Pases." in respuesta.text


def test_retirar_compra_marca_retirada_y_redirige():
    with patch("app.main.marcar_compra_retirada", return_value=None) as mock_marcar:
        respuesta = cliente.post("/logistica/retiro/Clark/1/retirar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/logistica/retiro/Clark"
    mock_marcar.assert_called_once_with(1, "logistica")


def test_cancelar_retiro_compra_marca_cancelada_y_redirige():
    with patch("app.main.marcar_compra_cancelada", return_value=None) as mock_marcar:
        respuesta = cliente.post("/logistica/retiro/Carro/1/cancelar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/logistica/retiro/Carro"
    mock_marcar.assert_called_once_with(1, "logistica")


def test_retirar_compra_error_de_base_muestra_mensaje():
    with (
        patch("app.main.marcar_compra_retirada", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_compras_pendientes_retiro", return_value=[]),
    ):
        respuesta = cliente.post("/logistica/retiro/Clark/1/retirar")

    assert respuesta.status_code == 500
    assert "No se pudo marcar como retirada" in respuesta.text


def test_ver_deposito_muestra_el_acceso_a_recepcion():
    # /deposito dejó de ser "en construcción": ahora es un hub, como
    # /compras o /comercial, con Recepción como primer acceso real.
    respuesta = cliente.get("/deposito")

    assert respuesta.status_code == 200
    assert 'href="/deposito/recepcion"' in respuesta.text
    assert "Recepción" in respuesta.text
    assert "En construcción" not in respuesta.text


def test_ver_gerencia_muestra_en_construccion_y_vuelve_a_inicio():
    respuesta = cliente.get("/gerencia")

    assert respuesta.status_code == 200
    assert "Gerencia" in respuesta.text
    assert "En construcción" in respuesta.text
    assert 'href="/inicio"' in respuesta.text


def test_barra_navegacion_en_compras_apunta_a_compras_y_a_inicio():
    respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert '<header class="barra-navegacion">' in respuesta.text
    assert f'href="/inicio" aria-label="Ir a Inicio">{_ICONO_INICIO}</a>' in respuesta.text
    assert f'href="/compras" aria-label="Ir a Compras">{SECTORES["compras"]["icono"]}</a>' in respuesta.text
    assert '<div class="barra-titulo">Compras</div>' in respuesta.text


def test_barra_navegacion_en_comercial_usa_icono_distinto_de_compras():
    # Regresión: Compras y Comercial arrancan las dos con "C" — se
    # distinguen con íconos distintos, no con la inicial.
    with patch("app.main.listar_clientes", return_value=[]):
        respuesta = cliente.get("/clientes")

    assert respuesta.status_code == 200
    assert f'href="/comercial" aria-label="Ir a Comercial">{SECTORES["comercial"]["icono"]}</a>' in respuesta.text
    assert SECTORES["compras"]["icono"] not in respuesta.text


def test_barra_navegacion_en_sistema():
    respuesta = cliente.get("/sistema")

    assert respuesta.status_code == 200
    assert f'href="/sistema" aria-label="Ir a Sistema">{SECTORES["sistema"]["icono"]}</a>' in respuesta.text


def test_barra_navegacion_en_placeholders_logistica_gerencia():
    casos = [("/logistica", "logistica", "Logística"), ("/gerencia", "gerencia", "Gerencia")]
    for url, sector, nombre in casos:
        respuesta = cliente.get(url)
        assert respuesta.status_code == 200
        assert f'href="{url}" aria-label="Ir a {nombre}">{SECTORES[sector]["icono"]}</a>' in respuesta.text


def test_barra_navegacion_en_deposito_apunta_a_deposito_y_a_inicio():
    respuesta = cliente.get("/deposito")

    assert respuesta.status_code == 200
    assert f'href="/inicio" aria-label="Ir a Inicio">{_ICONO_INICIO}</a>' in respuesta.text
    assert f'href="/deposito" aria-label="Ir a Depósito">{SECTORES["deposito"]["icono"]}</a>' in respuesta.text
    assert '<div class="barra-titulo">Depósito</div>' in respuesta.text


def test_ver_inicio_no_tiene_barra_de_navegacion():
    # /inicio ya es el punto de partida de todo: no tiene adónde volver.
    respuesta = cliente.get("/inicio")

    assert respuesta.status_code == 200
    assert "barra-navegacion" not in respuesta.text


def test_emojis_de_colores_reemplazados_por_iconos_svg():
    # Regresión: los emojis de colores (🏠🛒💼📦🚚📊⚙️) se reemplazaron por
    # íconos SVG minimalistas de línea (heroicons), consistentes entre sí.
    emojis_viejos = ["🏠", "🛒", "💼", "📦", "🚚", "📊", "⚙️"]
    with patch("app.main.listar_clientes", return_value=[]):
        respuesta_clientes = cliente.get("/clientes")
    for url, respuesta in [("/inicio", cliente.get("/inicio")), ("/compras", cliente.get("/compras")), ("/clientes", respuesta_clientes)]:
        assert respuesta.status_code == 200
        for emoji in emojis_viejos:
            assert emoji not in respuesta.text, f"{emoji} todavía aparece en {url}"


def test_titulo_grande_del_cuerpo_ya_no_aparece_en_ninguna_pantalla():
    # Regresión: el título grande en el CUERPO de la pantalla (duplicado con
    # el de la barrita) se sacó por completo — ni la regla CSS .titulo-sector
    # ni el <h1> quedan en ningún lado.
    urls = [
        "/compras",
        "/comercial",
        "/sistema",
        "/logistica",
        "/deposito",
        "/gerencia",
        "/compras/nueva/listado",
    ]
    for url in urls:
        respuesta = cliente.get(url)
        assert respuesta.status_code == 200
        assert "titulo-sector" not in respuesta.text, f"'titulo-sector' todavía aparece en {url}"

    with patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA):
        respuesta = cliente.get("/compras/nueva/manual")
    assert respuesta.status_code == 200
    assert "titulo-sector" not in respuesta.text

    with patch("app.main.listar_compras_pendientes_recepcion", return_value=[]):
        respuesta = cliente.get("/deposito/recepcion")
    assert respuesta.status_code == 200
    assert "titulo-sector" not in respuesta.text

    with (
        patch("app.main.listar_proveedores", return_value=PROVEEDORES_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.buscar_compras", return_value=[]),
    ):
        respuesta = cliente.get("/compras/buscar")
    assert respuesta.status_code == 200
    assert "titulo-sector" not in respuesta.text


def test_barra_navegacion_muestra_el_titulo_del_sector_en_las_pantallas_principales():
    # El único título que queda es el de la barrita — se agrandó, pero
    # sigue siendo el mismo <div class="barra-titulo">.
    casos = [("/compras", "Compras"), ("/comercial", "Comercial"), ("/sistema", "Sistema")]
    for url, nombre in casos:
        respuesta = cliente.get(url)
        assert respuesta.status_code == 200
        assert f'<div class="barra-titulo">{nombre}</div>' in respuesta.text
