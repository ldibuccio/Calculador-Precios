import io
from datetime import date, timedelta
from unittest.mock import patch

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
    {"id": 1, "nombre": "Frutilla", "unidad_compra": None, "contenido_referencia": None},
    {"id": 2, "nombre": "Mango", "unidad_compra": None, "contenido_referencia": None},
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
    mock_crear.assert_called_once_with("Kiwi", "unidad", 10.0)


def test_agregar_articulo_sin_contenido_referencia_guarda_none():
    with patch("app.main.crear_articulo") as mock_crear:
        respuesta = cliente.post(
            "/articulos/nuevo",
            data={"nombre": "Kiwi", "unidad_compra": "kilo", "contenido_referencia": ""},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with("Kiwi", "kilo", None)


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


ARTICULO_DE_PRUEBA = {"id": 1, "nombre": "Frutilla", "unidad_compra": "cubeta", "contenido_referencia": 12}


def test_ver_editar_articulo_muestra_datos_precargados():
    with patch("app.main.obtener_articulo", return_value=ARTICULO_DE_PRUEBA):
        respuesta = cliente.get("/articulos/1/editar")

    assert respuesta.status_code == 200
    assert "Frutilla" in respuesta.text
    assert 'action="/articulos/1/editar"' in respuesta.text
    assert "merma" not in respuesta.text.lower()


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
    mock_actualizar.assert_called_once_with(1, "Frutilla Premium", "cubeta", 12.0)


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
    {"id": 1, "nombre": "Día", "descuento": 23.0, "utilidad_objetivo": 20.0},
    {"id": 2, "nombre": "Otro cliente", "descuento": 15.0, "utilidad_objetivo": 10.0},
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


def test_ver_clientes_muestra_nombre_descuento_y_utilidad_como_porcentaje():
    with patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA):
        respuesta = cliente.get("/clientes")

    assert respuesta.status_code == 200
    assert "Día" in respuesta.text
    assert "23.0%" in respuesta.text
    assert "20.0%" in respuesta.text
    assert "/clientes/1/editar" in respuesta.text
    assert "/clientes/1/eliminar" in respuesta.text


def test_ver_clientes_incluye_link_a_inicio():
    with patch("app.main.listar_clientes", return_value=[]):
        respuesta = cliente.get("/clientes")

    assert respuesta.status_code == 200
    assert 'href="/inicio"' in respuesta.text


def test_agregar_cliente_exitoso_redirige_a_clientes():
    with patch("app.main.crear_cliente") as mock_crear:
        respuesta = cliente.post(
            "/clientes/nuevo",
            data={"nombre": "Vea", "descuento": "18", "utilidad_objetivo": "12"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/clientes"
    mock_crear.assert_called_once_with("Vea", 18.0, 12.0)


def test_agregar_cliente_nombre_vacio_muestra_error():
    with patch("app.main.crear_cliente") as mock_crear, patch("app.main.listar_clientes", return_value=[]):
        respuesta = cliente.post(
            "/clientes/nuevo", data={"nombre": "   ", "descuento": "18", "utilidad_objetivo": "12"}
        )

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_cliente_descuento_fuera_de_rango_muestra_error():
    with patch("app.main.crear_cliente") as mock_crear, patch("app.main.listar_clientes", return_value=[]):
        respuesta = cliente.post(
            "/clientes/nuevo", data={"nombre": "Vea", "descuento": "150", "utilidad_objetivo": "12"}
        )

    assert respuesta.status_code == 400
    assert "entre 0 y 100" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_cliente_utilidad_no_numerica_muestra_error():
    with patch("app.main.crear_cliente") as mock_crear, patch("app.main.listar_clientes", return_value=[]):
        respuesta = cliente.post(
            "/clientes/nuevo", data={"nombre": "Vea", "descuento": "18", "utilidad_objetivo": "abc"}
        )

    assert respuesta.status_code == 400
    assert "tiene que ser un número" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_cliente_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.crear_cliente", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_clientes", return_value=[]),
    ):
        respuesta = cliente.post(
            "/clientes/nuevo", data={"nombre": "Vea", "descuento": "18", "utilidad_objetivo": "12"}
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar" in respuesta.text


CLIENTE_DE_PRUEBA = {"id": 1, "nombre": "Día", "descuento": 23.0, "utilidad_objetivo": 20.0}


def test_ver_editar_cliente_muestra_datos_precargados():
    with patch("app.main.obtener_cliente", return_value=CLIENTE_DE_PRUEBA):
        respuesta = cliente.get("/clientes/1/editar")

    assert respuesta.status_code == 200
    assert "Día" in respuesta.text
    assert 'action="/clientes/1/editar"' in respuesta.text


def test_ver_editar_cliente_inexistente_da_404():
    with patch("app.main.obtener_cliente", return_value=None):
        respuesta = cliente.get("/clientes/999/editar")

    assert respuesta.status_code == 404


def test_ver_editar_cliente_error_de_base_da_500():
    with patch("app.main.obtener_cliente", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/clientes/1/editar")

    assert respuesta.status_code == 500


def test_editar_cliente_exitoso_redirige_a_clientes():
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post(
            "/clientes/1/editar",
            data={"nombre": "Día", "descuento": "25", "utilidad_objetivo": "22"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/clientes"
    # La ruta solo delega en actualizar_cliente; la lógica de historial
    # (agregar un registro nuevo con vigente_desde = hoy en vez de pisar el
    # anterior) vive en el SQL de app/db.py, que necesita una base real
    # para probarse — no se puede mockear sin perder la cobertura de esa lógica.
    mock_actualizar.assert_called_once_with(1, "Día", 25.0, 22.0)


def test_editar_cliente_nombre_vacio_muestra_error():
    with patch("app.main.actualizar_cliente") as mock_actualizar:
        respuesta = cliente.post(
            "/clientes/1/editar", data={"nombre": "   ", "descuento": "25", "utilidad_objetivo": "22"}
        )

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_cliente_error_de_base_muestra_mensaje_claro():
    with patch("app.main.actualizar_cliente", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post(
            "/clientes/1/editar", data={"nombre": "Día", "descuento": "25", "utilidad_objetivo": "22"}
        )

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
    },
    {
        "id": 11,
        "articulo_nombre": "Sandía",
        "envase_nombre": None,
        "contenido_caja": 18,
        "unidad_venta": "kilo",
        "envase_variable": False,
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
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/fichas?cliente_id=1"
    mock_crear.assert_called_once_with(5, 1, 100, 10.0, "unidad", True)


def test_agregar_ficha_sin_envase_con_contenido_caja_exitosa():
    with patch("app.main.crear_ficha") as mock_crear:
        respuesta = cliente.post(
            "/fichas/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "envase_id": "", "contenido_caja": "12", "unidad_venta": "cubeta"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with(5, 1, None, 12.0, "cubeta", False)


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
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/fichas?cliente_id=1"
    mock_actualizar.assert_called_once_with(10, 100, 12.0, "unidad", True)


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
    mock_actualizar.assert_called_once_with(10, 100, 12.0, "unidad", False)


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


CONVERSIONES_DE_PRUEBA = [
    {"id": 20, "articulo_nombre": "Mzn Red", "nombre_cliente": "MANZ ROJ ELE", "codigo_cliente": "90039"},
    {"id": 21, "articulo_nombre": "Pera", "nombre_cliente": "PERA WILL", "codigo_cliente": None},
]


def test_ver_conversion_sin_cliente_elegido_pide_elegir_uno():
    with patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR):
        respuesta = cliente.get("/conversion")

    assert respuesta.status_code == 200
    assert "Elegí un cliente" in respuesta.text
    assert "Día" in respuesta.text


def test_ver_conversion_error_al_leer_clientes_muestra_error_claro():
    with patch("app.main.listar_clientes", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/conversion")

    assert respuesta.status_code == 500
    assert "No se pudo leer los clientes" in respuesta.text


def test_ver_conversion_con_cliente_muestra_la_lista():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR),
        patch("app.main.listar_conversiones_por_cliente", return_value=CONVERSIONES_DE_PRUEBA),
    ):
        respuesta = cliente.get("/conversion?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Mzn Red" in respuesta.text
    assert "MANZ ROJ ELE" in respuesta.text
    assert "90039" in respuesta.text
    assert "Pera" in respuesta.text
    assert "/conversion/20/editar" in respuesta.text
    assert "/conversion/nueva?cliente_id=1" in respuesta.text


def test_ver_conversion_error_al_leer_conversiones_muestra_error_claro():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR),
        patch("app.main.listar_conversiones_por_cliente", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.get("/conversion?cliente_id=1")

    assert respuesta.status_code == 500
    assert "No se pudieron leer las conversiones" in respuesta.text


def test_ver_nueva_conversion_muestra_formulario():
    with patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA):
        respuesta = cliente.get("/conversion/nueva?cliente_id=1")

    assert respuesta.status_code == 200
    assert "Kiwi" in respuesta.text


def test_ver_nueva_conversion_sin_cliente_id_da_422():
    respuesta = cliente.get("/conversion/nueva")
    assert respuesta.status_code == 422


def test_ver_nueva_conversion_error_de_base_da_500():
    with patch("app.main.listar_articulos", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/conversion/nueva?cliente_id=1")

    assert respuesta.status_code == 500


def test_agregar_conversion_exitosa_redirige_a_conversion_del_cliente():
    with patch("app.main.crear_conversion") as mock_crear:
        respuesta = cliente.post(
            "/conversion/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "nombre_cliente": "MANZ ROJ ELE", "codigo_cliente": "90039"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/conversion?cliente_id=1"
    mock_crear.assert_called_once_with(5, 1, "MANZ ROJ ELE", "90039")


def test_agregar_conversion_sin_codigo_guarda_none():
    with patch("app.main.crear_conversion") as mock_crear:
        respuesta = cliente.post(
            "/conversion/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "nombre_cliente": "PERA WILL", "codigo_cliente": ""},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with(5, 1, "PERA WILL", None)


def test_agregar_conversion_sin_articulo_muestra_error():
    with (
        patch("app.main.crear_conversion") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.post(
            "/conversion/nueva",
            data={"cliente_id": "1", "articulo_id": "", "nombre_cliente": "PERA WILL", "codigo_cliente": ""},
        )

    assert respuesta.status_code == 400
    assert "Elegí un artículo" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_conversion_sin_nombre_cliente_muestra_error():
    with (
        patch("app.main.crear_conversion") as mock_crear,
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.post(
            "/conversion/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "nombre_cliente": "", "codigo_cliente": ""},
        )

    assert respuesta.status_code == 400
    assert "El nombre no puede estar vacío" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_conversion_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.crear_conversion", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.post(
            "/conversion/nueva",
            data={"cliente_id": "1", "articulo_id": "5", "nombre_cliente": "PERA WILL", "codigo_cliente": ""},
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar la conversión" in respuesta.text


CONVERSION_DE_PRUEBA = {
    "id": 20,
    "cliente_id": 1,
    "articulo_id": 5,
    "articulo_nombre": "Mzn Red",
    "nombre_cliente": "MANZ ROJ ELE",
    "codigo_cliente": "90039",
}


def test_ver_editar_conversion_muestra_datos_precargados():
    with (
        patch("app.main.obtener_conversion", return_value=CONVERSION_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.get("/conversion/20/editar")

    assert respuesta.status_code == 200
    assert "MANZ ROJ ELE" in respuesta.text
    assert "90039" in respuesta.text
    assert 'action="/conversion/20/editar"' in respuesta.text


def test_ver_editar_conversion_inexistente_da_404():
    with patch("app.main.obtener_conversion", return_value=None):
        respuesta = cliente.get("/conversion/999/editar")

    assert respuesta.status_code == 404


def test_ver_editar_conversion_error_de_base_da_500():
    with patch("app.main.obtener_conversion", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/conversion/20/editar")

    assert respuesta.status_code == 500


def test_editar_conversion_exitosa_redirige_a_conversion_del_cliente():
    with patch("app.main.actualizar_conversion") as mock_actualizar:
        respuesta = cliente.post(
            "/conversion/20/editar",
            data={"cliente_id": "1", "articulo_id": "5", "nombre_cliente": "MANZ ROJ ELE", "codigo_cliente": "90039"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/conversion?cliente_id=1"
    mock_actualizar.assert_called_once_with(20, 5, "MANZ ROJ ELE", "90039")


def test_editar_conversion_sin_nombre_cliente_muestra_error():
    with (
        patch("app.main.actualizar_conversion") as mock_actualizar,
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.post(
            "/conversion/20/editar",
            data={"cliente_id": "1", "articulo_id": "5", "nombre_cliente": "", "codigo_cliente": "90039"},
        )

    assert respuesta.status_code == 400
    assert "El nombre no puede estar vacío" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_conversion_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.actualizar_conversion", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_articulos", return_value=ARTICULOS_SIN_FICHA),
    ):
        respuesta = cliente.post(
            "/conversion/20/editar",
            data={"cliente_id": "1", "articulo_id": "5", "nombre_cliente": "MANZ ROJ ELE", "codigo_cliente": "90039"},
        )

    assert respuesta.status_code == 500
    assert "No se pudo guardar la conversión" in respuesta.text


def test_eliminar_conversion_exitosa_redirige_a_conversion_del_cliente():
    with patch("app.main.eliminar_conversion") as mock_eliminar:
        respuesta = cliente.post("/conversion/20/eliminar", data={"cliente_id": "1"}, follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/conversion?cliente_id=1"
    mock_eliminar.assert_called_once_with(20)


def test_eliminar_conversion_error_de_base_da_500():
    with patch("app.main.eliminar_conversion", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/conversion/20/eliminar", data={"cliente_id": "1"})

    assert respuesta.status_code == 500


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
        "tipo_retiro": "Granel",
    },
]


def test_ver_compras_muestra_solo_la_botonera():
    # /compras pasó a ser solo el título y las dos botoneras — el listado
    # se mudó a /compras/ultimas.
    respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert '<div class="barra-titulo">Compras</div>' in respuesta.text
    assert ">Cargar<" in respuesta.text
    assert ">Operaciones<" in respuesta.text
    assert respuesta.text.index(">Cargar<") < respuesta.text.index(">Operaciones<")
    assert "Últimas Compras" in respuesta.text  # el botón, no el listado
    assert "<table" not in respuesta.text
    assert 'id="boton-borrar-seleccionadas"' not in respuesta.text


def test_ver_ultimas_compras_muestra_las_de_los_ultimos_2_dias():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=COMPRAS_DE_PRUEBA) as mock_listar,
    ):
        respuesta = cliente.get("/compras/ultimas")

    assert respuesta.status_code == 200
    assert '<div class="barra-titulo">Últimas Compras</div>' in respuesta.text
    assert "Mzn Red" in respuesta.text
    assert "Saturno" in respuesta.text
    assert "N07P41" in respuesta.text
    assert "Mango" in respuesta.text
    assert "Fecha" in respuesta.text
    # Regresión: encabezado de la tabla con fondo propio, para
    # diferenciarlo de las filas.
    assert "thead tr {" in respuesta.text
    assert "background: #eef2f7" in respuesta.text
    # Regresión: "Enviar a Logística" vive acá adentro (Próximamente),
    # no en la botonera principal de /compras.
    assert 'id="boton-enviar-logistica"' in respuesta.text
    assert 'href="/compras/enviar-logistica"' in respuesta.text
    # Regresión: encabezados compactos para pantalla de celular.
    assert "<th>Cant</th>" in respuesta.text
    assert "<th>K/U</th>" in respuesta.text
    assert "<th>$</th>" in respuesta.text
    # sin totales calculados: no debe mostrarse la columna de fracción/kilos ya procesada
    assert "Fracción" not in respuesta.text
    mock_listar.assert_called_once_with(HOY_DE_PRUEBA - timedelta(days=1), HOY_DE_PRUEBA)
    # Regresión: pantalla compacta para celular — fecha dd/mm (sin año) y
    # números sin decimales de sobra (10 en vez de 10.0).
    assert "06/08" in respuesta.text
    assert "05/08" in respuesta.text
    assert "2026" not in respuesta.text
    assert "<td>10</td>" in respuesta.text
    assert "10.0" not in respuesta.text
    assert "18.0" not in respuesta.text
    # Regresión: letra de unidad pegada al contenido por cajón (18k, 10u).
    assert "<td>18k</td>" in respuesta.text
    assert "<td>10u</td>" in respuesta.text
    # Regresión: importe y seña con signo $ y "." cada tres cifras.
    assert "$50.000" in respuesta.text
    assert "$15.000" in respuesta.text
    assert "$2.000" in respuesta.text


def test_ver_ultimas_compras_muestra_ver_foto_solo_en_las_filas_con_foto():
    compras = [
        dict(COMPRAS_DE_PRUEBA[0], foto_ruta="2026-08-06/n07p41-123-abcdef12.jpg"),
        dict(COMPRAS_DE_PRUEBA[1], foto_ruta=None),
    ]
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=compras),
    ):
        respuesta = cliente.get("/compras/ultimas")

    assert respuesta.status_code == 200
    assert respuesta.text.count("Ver foto") == 1
    assert 'href="/compras/30/foto"' in respuesta.text
    assert 'href="/compras/31/foto"' not in respuesta.text


def test_ver_ultimas_compras_sin_compras_muestra_mensaje():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=[]),
    ):
        respuesta = cliente.get("/compras/ultimas")

    assert respuesta.status_code == 200
    assert "No hay compras cargadas en los últimos 2 días" in respuesta.text


def test_ver_ultimas_compras_error_de_base_muestra_error_claro():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.get("/compras/ultimas")

    assert respuesta.status_code == 500
    assert "No se pudieron leer las compras" in respuesta.text


def test_ver_compras_no_muestra_nada_de_sistema_ahi():
    # Regresión: el indicador de espacio y el botón de limpieza de fotos se
    # movieron a /sistema — /compras es operativa, no tiene que mostrar
    # nada de eso (ni siquiera si esas funciones responden bien).
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=COMPRAS_DE_PRUEBA),
        patch("app.main.obtener_uso_storage_bucket", return_value={"cantidad": 12, "bytes_totales": 907397}),
        patch("app.main.listar_fotos_para_limpiar", return_value=["2020-01-01/x.jpg"]),
    ):
        respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert "fotos guardadas" not in respuesta.text
    assert 'id="boton-limpiar-fotos-viejas"' not in respuesta.text
    assert 'href="/sistema"' in respuesta.text


def test_ver_compras_incluye_links_a_catalogo_y_a_inicio():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=COMPRAS_DE_PRUEBA),
    ):
        respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert 'href="/articulos"' in respuesta.text
    assert 'href="/conversion"' in respuesta.text
    assert 'href="/inicio"' in respuesta.text


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


def test_cambiar_proveedor_en_carga_manual_apunta_a_la_pantalla_manual():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.get("/compras/nueva?proveedor_id=200")

    assert respuesta.status_code == 200
    assert 'href="/compras/nueva/manual"' in respuesta.text


def test_cargar_listado_de_compras_muestra_en_construccion():
    respuesta = cliente.get("/compras/nueva/listado")

    assert respuesta.status_code == 200
    assert "Cargar listado de compras" in respuesta.text
    assert "En construcción" in respuesta.text
    assert 'href="/compras"' in respuesta.text


def test_buscar_compras_muestra_en_construccion():
    respuesta = cliente.get("/compras/buscar")

    assert respuesta.status_code == 200
    assert "Buscar compras" in respuesta.text
    assert "En construcción" in respuesta.text


def test_enviar_a_logistica_muestra_en_construccion():
    respuesta = cliente.get("/compras/enviar-logistica")

    assert respuesta.status_code == 200
    assert "Enviar a logística" in respuesta.text
    assert "En construcción" in respuesta.text


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
    # Grupo Operaciones: Últimas Compras, Buscar Compras, Armar Listado,
    # Compras sin precio, Disponibles. "Enviar a Logística" se retiró de
    # acá (ahora vive dentro de /compras/ultimas).
    assert 'href="/compras/ultimas"' in respuesta.text
    assert "Últimas Compras" in respuesta.text
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
    assert 'class="boton boton-naranja" href="/compras/ultimas"' in respuesta.text
    assert 'class="boton boton-naranja" href="/compras/pendientes"' in respuesta.text
    assert ".boton-naranja { background: #ea580c; }" in respuesta.text
    # "Próximamente": color del grupo pero atenuado (mismo criterio en
    # Cargar y en Operaciones).
    assert 'class="boton boton-proximamente" href="/compras/nueva/listado"' in respuesta.text
    assert 'class="boton boton-naranja boton-proximamente" href="/compras/buscar"' in respuesta.text
    assert 'class="boton boton-naranja boton-proximamente" href="/compras/disponibles"' in respuesta.text
    assert ".boton-proximamente { opacity: 0.6; }" in respuesta.text


def test_ver_ultimas_compras_boton_borrar_seleccionadas_es_tamano_normal():
    # Regresión: el botón no puede depender solo de .boton-eliminar (que no
    # trae padding/ancho propios) — necesita la clase .boton para tener un
    # área de toque cómoda en celular, no quedar chico/finito.
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=COMPRAS_DE_PRUEBA),
    ):
        respuesta = cliente.get("/compras/ultimas")

    assert respuesta.status_code == 200
    assert 'class="boton boton-eliminar" id="boton-borrar-seleccionadas"' in respuesta.text


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
                "tipo_retiro": "Granel",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    # 5 cajones × 10 unidades = 50 unidades (unidad_compra del artículo = unidad)
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 6, 200, 5.0, 10.0, None, 50.0, 30000.0, None, "Granel")


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
    assert respuesta.headers["location"] == "/compras/ultimas"
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
    assert respuesta.headers["location"] == "/compras/ultimas"
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


def test_agregar_compra_tipo_retiro_propia_se_acepta():
    # "Propia" es el tercer tipo de retiro, agregado además de Clark/Granel.
    # OJO: hasta que el CHECK de la base también lo permita, esto pasa la
    # validación de la app pero el INSERT real fallaría — acá se mockea
    # crear_compra, así que no depende de que la base ya esté migrada.
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
                "tipo_retiro": "Propia",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 50000.0, None, "Propia")


def test_ver_nueva_compra_con_proveedor_muestra_las_tres_opciones_de_retiro():
    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        respuesta = cliente.get("/compras/nueva?proveedor_id=200")

    assert respuesta.status_code == 200
    assert '<option value="Clark"' in respuesta.text
    assert '<option value="Granel"' in respuesta.text
    assert '<option value="Propia"' in respuesta.text


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
        patch("app.main.eliminar_compras_del_dia_por_proveedor") as mock_eliminar,
    ):
        respuesta = cliente.post(
            "/compras/nueva/cancelar",
            data={"proveedor_id": "200"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/ultimas"
    # Se borra TODO lo del proveedor en el día, no un renglón puntual: no
    # hace falta que el comprador haya cargado nada en el formulario para
    # que se descarte lo que ya estaba guardado de "Agregar artículo".
    mock_eliminar.assert_called_once_with(HOY_DE_PRUEBA, 200)


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
                "tipo_retiro": "Granel",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/ultimas"
    mock_actualizar.assert_called_once_with(30, 5, 8.0, 15.0, 120.0, None, 55000.0, 1000.0, "Granel")


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
                "tipo_retiro": "Granel",
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


def test_eliminar_compra_exitosa_redirige_a_compras():
    with (
        patch("app.main.eliminar_compra", return_value=None) as mock_eliminar,
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
    ):
        respuesta = cliente.post("/compras/30/eliminar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/ultimas"
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
    assert respuesta.headers["location"] == "/compras/ultimas"


def test_eliminar_compra_error_de_base_da_500():
    with patch("app.main.eliminar_compra", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/compras/30/eliminar")

    assert respuesta.status_code == 500


def test_eliminar_varias_compras_exitosa_redirige_a_compras():
    with (
        patch("app.main.eliminar_compra", return_value=None) as mock_eliminar,
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
    ):
        respuesta = cliente.post(
            "/compras/eliminar-varias",
            data={"compra_id": ["30", "31"]},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/ultimas"
    assert mock_eliminar.call_count == 2
    mock_eliminar.assert_any_call(30)
    mock_eliminar.assert_any_call(31)
    mock_borrar_foto.assert_not_called()


def test_eliminar_varias_compras_sin_ninguna_seleccionada_redirige_sin_hacer_nada():
    with patch("app.main.eliminar_compra") as mock_eliminar:
        respuesta = cliente.post("/compras/eliminar-varias", data={}, follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/ultimas"
    mock_eliminar.assert_not_called()


def test_eliminar_varias_compras_una_falla_no_corta_el_lote_y_avisa_sin_tecnicismos():
    # id 30 (Mzn Red, Saturno) se borra bien; id 31 (Mango, Frutamax) falla
    # (ej. por la FK de recepciones). El mensaje al usuario no debe mostrar
    # ids ni el error crudo de Postgres, y sí debe nombrar el renglón que
    # no se pudo borrar de forma reconocible (artículo + proveedor).
    def eliminar_side_effect(compra_id):
        if compra_id == 31:
            raise Exception('update or delete on table "compras" violates foreign key constraint')
        return None

    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=COMPRAS_DE_PRUEBA),
        patch("app.main.eliminar_compra", side_effect=eliminar_side_effect) as mock_eliminar,
        patch("app.main.borrar_foto_comanda") as mock_borrar_foto,
    ):
        respuesta = cliente.post(
            "/compras/eliminar-varias",
            data={"compra_id": ["30", "31"]},
        )

    assert respuesta.status_code == 200
    assert mock_eliminar.call_count == 2
    mock_borrar_foto.assert_not_called()
    assert "Se borraron 1 de 2 compras" in respuesta.text
    assert "No se pudieron borrar 1" in respuesta.text
    assert "recepción asociada" in respuesta.text
    # Identifica el renglón fallido por artículo+proveedor, no por id ni con
    # el texto crudo de Postgres. (El "31" en la fila de la tabla es el
    # value del checkbox, no el mensaje de error — no cuenta como fuga.)
    assert "Mango (Frutamax)" in respuesta.text
    assert "id 31" not in respuesta.text
    assert "foreign key" not in respuesta.text
    assert "violates" not in respuesta.text


def test_eliminar_varias_compras_todas_fallan_informa_las_dos():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=COMPRAS_DE_PRUEBA),
        patch("app.main.eliminar_compra", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.post(
            "/compras/eliminar-varias",
            data={"compra_id": ["30", "31"]},
        )

    assert respuesta.status_code == 200
    assert "Se borraron 0 de 2 compras" in respuesta.text
    assert "No se pudieron borrar 2" in respuesta.text
    assert "Mzn Red (Saturno)" in respuesta.text
    assert "Mango (Frutamax)" in respuesta.text


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
    # Tercer tipo de retiro (Propia), además de Clark/Granel.
    assert '<option value="Propia"' in respuesta.text
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
    assert respuesta.headers["location"] == "/compras/ultimas"
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


def test_ver_costeo_prueba_muestra_tabla_con_formato():
    articulos = [
        {
            "articulo_id": 1,
            "articulo_nombre": "Tomate Cherry",
            "unidad_venta": "kilo",
            "fresco": True,
            "costo_actual": 560.98,
            "costo_anterior": 600.0,
            "variacion": "bajo",
            "fecha_ultima_compra": date(2026, 8, 10),
            "precio_vigente": 700.0,
            "precio_sugerido": 750.6,
            "utilidad_aproximada": 0.155,  # por debajo del objetivo del cliente (20%)
            "compras_sin_precio_excluidas": 1,
        },
        {
            "articulo_id": 2,
            "articulo_nombre": "Mango",
            "unidad_venta": "unidad",
            "fresco": False,
            "costo_actual": 400.0,
            "costo_anterior": None,
            "variacion": None,
            "fecha_ultima_compra": date(2026, 8, 4),
            "precio_vigente": None,
            "precio_sugerido": None,
            "utilidad_aproximada": None,  # sin precio vigente
            "compras_sin_precio_excluidas": 0,
        },
    ]
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=articulos) as mock_calcular,
        patch("app.main.calcular_precio_sugerido_desglosado", return_value=None),
    ):
        respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 200
    mock_calcular.assert_called_once()
    assert mock_calcular.call_args[0][0] == 1
    assert "Día" in respuesta.text
    assert "Tomate Cherry" in respuesta.text
    assert "<td>kilo</td>" in respuesta.text
    assert "$561" in respuesta.text  # 560.98 redondeado al peso entero
    assert "$600" in respuesta.text  # costo anterior
    assert "bajó" in respuesta.text
    assert "$700" in respuesta.text  # precio vigente
    assert "$751" in respuesta.text  # precio sugerido (750.5 redondeado)
    assert "10/08" in respuesta.text  # fecha última compra de Cherry
    # Cherry: utilidad 15.5%, por debajo del objetivo del cliente (20%) -> marcada.
    assert "15,5%" in respuesta.text
    assert "utilidad-baja" in respuesta.text
    # Mango: sin costo anterior, vigente ni utilidad -> "—", no "None".
    assert "None" not in respuesta.text
    assert "Fecha de referencia" in respuesta.text


def test_ver_costeo_prueba_utilidad_negativa_y_en_objetivo():
    articulos = [
        {
            "articulo_id": 1,
            "articulo_nombre": "Palta",
            "unidad_venta": "unidad",
            "fresco": True,
            "costo_actual": 900.0,
            "costo_anterior": None,
            "variacion": None,
            "fecha_ultima_compra": date(2026, 8, 10),
            "precio_vigente": 800.0,
            "precio_sugerido": 1200.0,
            "utilidad_aproximada": -0.10,  # precio vigente por debajo del costo
            "compras_sin_precio_excluidas": 0,
        },
        {
            "articulo_id": 2,
            "articulo_nombre": "Pera",
            "unidad_venta": "kilo",
            "fresco": True,
            "costo_actual": 1000.0,
            "costo_anterior": None,
            "variacion": None,
            "fecha_ultima_compra": date(2026, 8, 10),
            "precio_vigente": 2000.0,
            "precio_sugerido": 1900.0,
            "utilidad_aproximada": 0.25,  # por encima del objetivo (20%): normal, sin marcar
            "compras_sin_precio_excluidas": 0,
        },
    ]
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=articulos),
        patch("app.main.calcular_precio_sugerido_desglosado", return_value=None),
    ):
        respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 200
    assert "utilidad-negativa" in respuesta.text
    assert "-10,0%" in respuesta.text
    assert "25,0%" in respuesta.text
    # Pera está en 25%, por encima del objetivo (20%): no debería quedar
    # marcada como "baja" (buscamos la clase pegada al valor de Pera, no
    # simplemente que la clase exista en algún lado de la página).
    assert 'utilidad-baja">25,0%' not in respuesta.text


def test_ver_costeo_prueba_sin_articulos_muestra_mensaje():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
        patch("app.main.calcular_precio_sugerido_desglosado", return_value=None),
    ):
        respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 200
    assert "No hay artículos con compra reciente" in respuesta.text


def test_ver_costeo_prueba_error_de_base_da_500():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 500
    assert "Error al calcular el costeo" in respuesta.text


def test_ver_costeo_prueba_sin_cliente_dia_da_404():
    with patch("app.main.listar_clientes", return_value=[{"id": 2, "nombre": "Otro cliente"}]):
        respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 404


def test_ver_costeo_prueba_desglose_falla_no_rompe_el_resto_de_la_pantalla_y_muestra_el_error():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
        patch("app.main.calcular_precio_sugerido_desglosado", side_effect=Exception("sin base")),
    ):
        respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 200
    assert "No hay artículos con compra reciente" in respuesta.text
    # El error ya no se traga en silencio: se muestra en pantalla.
    assert "Error al calcular el desglose" in respuesta.text
    assert "Exception: sin base" in respuesta.text


def test_ver_costeo_prueba_desglose_none_sin_error_muestra_explicacion():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
        patch("app.main.calcular_precio_sugerido_desglosado", return_value=None),
    ):
        respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 200
    assert "No hay desglose disponible" in respuesta.text
    assert "Morrón Verde" in respuesta.text
    assert "Error al calcular el desglose" not in respuesta.text


def test_ver_costeo_prueba_muestra_desglose_con_valores_intermedios():
    desglose = {
        "articulo_id": 29,
        "articulo_nombre": "Morrón Verde",
        "unidad_venta": "kilo",
        "fecha_ultima_compra": date(2026, 8, 10),
        "cantidad_total": 80.0,
        "compras_sin_precio_excluidas": 0,
        "costo_actual": 3375.0,
        "utilidad": 0.20,
        "tasas_suman": [0.105],
        "tasas_restan": [0.23],
        "envase_nombre": "Caja Grande",
        "envase_variable": False,
        "contenido_ficha": 8.0,
        "costo_envase_unitario": 1600.0,
        "envases_por_unidad": 0.125,
        "costo_envase_por_unidad": 200.0,
        "precio_sugerido": 4857.1428,
        "precio_vigente": 4400.0,
        "costo_producto_bulto": 27000.0,
        "costo_envase_bulto": 1600.0,
        "costo_total_bulto": 28600.0,
        "precio_vigente_bulto": 35200.0,
        "entra_bulto": 30800.0,
        "utilidad_aproximada": 0.0769230769,
    }
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
        patch("app.main.calcular_precio_sugerido_desglosado", return_value=desglose) as mock_desglose,
    ):
        respuesta = cliente.get("/costeo-prueba")

    assert respuesta.status_code == 200
    mock_desglose.assert_called_once()
    assert mock_desglose.call_args[0][0] == 1
    assert mock_desglose.call_args[0][1] == "Morrón Verde"
    assert "Desglose de depuración" in respuesta.text
    assert "3375.0000" in respuesta.text  # costo actual, sin redondear
    assert "0.2000" in respuesta.text  # utilidad
    assert "0.105" in respuesta.text  # tasa que suma (IVA)
    assert "0.23" in respuesta.text  # tasa que resta (descuento)
    assert "Caja Grande" in respuesta.text
    assert "1600.0000" in respuesta.text  # costo del envase
    assert "0.125000" in respuesta.text  # envases por unidad
    assert "200.0000" in respuesta.text  # costo de envase por unidad
    assert "4857.1428" in respuesta.text  # precio sugerido paso a paso
    # Desglose de utilidad aproximada (paso a paso, por bulto).
    assert "27000.0000" in respuesta.text  # costo_producto_bulto
    assert "28600.0000" in respuesta.text  # costo_total_bulto
    assert "35200.0000" in respuesta.text  # precio_vigente_bulto
    assert "30800.0000" in respuesta.text  # entra_bulto
    assert "7,7%" in respuesta.text  # utilidad_aproximada


# --- /negociar: cuadro simplificado (Bajas / Subas / Resumen bajo objetivo) ---

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


def test_ver_negociar_bajas_incluye_fresco_que_bajo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar")

    assert respuesta.status_code == 200
    assert "Bajas" in respuesta.text
    assert "Tomate Cherry" in respuesta.text
    assert "$950" in respuesta.text
    assert "✓" in respuesta.text


def test_ver_negociar_subas_incluye_fresco_que_subio():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar")

    assert respuesta.status_code == 200
    assert "Mango" in respuesta.text
    assert "🔴" in respuesta.text


def test_ver_negociar_no_fresco_no_aparece_en_bajas_ni_subas():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar")

    import re

    bloque_bajas = re.search(r"<h2>Bajas.*?</h2>(.*?)<h2>Subas", respuesta.text, re.S).group(1)
    bloque_subas = re.search(r"<h2>Subas.*?</h2>(.*?)<h2>\s*Resumen", respuesta.text, re.S).group(1)
    assert "Palta" not in bloque_bajas
    assert "Palta" not in bloque_subas


def test_ver_negociar_resumen_ordena_de_peor_a_mejor_y_filtra_bajo_objetivo():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=ARTICULOS_NEGOCIAR_DE_PRUEBA),
    ):
        respuesta = cliente.get("/negociar")

    import re

    bloque_resumen = re.search(r"<h2>\s*Resumen.*", respuesta.text, re.S).group(0)
    # Palta (-5%, peor) tiene que aparecer antes que Mango (10%).
    pos_palta = bloque_resumen.index("Palta")
    pos_mango = bloque_resumen.index("Mango")
    assert pos_palta < pos_mango
    # Tomate Cherry (30%, por encima del objetivo) no entra al resumen.
    assert "Tomate Cherry" not in bloque_resumen
    assert "utilidad-negativa" in bloque_resumen
    assert "utilidad-baja" in bloque_resumen


def test_ver_negociar_sin_articulos_muestra_mensajes_vacios():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/negociar")

    assert respuesta.status_code == 200
    assert "Ningún artículo fresco bajó de costo" in respuesta.text
    assert "Ningún artículo fresco subió de costo" in respuesta.text
    assert "Ningún artículo con precio vigente está por debajo del objetivo" in respuesta.text


def test_ver_negociar_sin_cliente_dia_da_404():
    with patch("app.main.listar_clientes", return_value=[{"id": 2, "nombre": "Otro cliente"}]):
        respuesta = cliente.get("/negociar")

    assert respuesta.status_code == 404


def test_ver_negociar_error_de_base_da_500():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.get("/negociar")

    assert respuesta.status_code == 500


def test_ver_negociar_tiene_link_de_ida_y_vuelta_con_costeo_prueba():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES_DE_PRUEBA),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta_negociar = cliente.get("/negociar")
        respuesta_costeo = cliente.get("/costeo-prueba")

    assert 'href="/costeo-prueba"' in respuesta_negociar.text
    assert 'href="/negociar"' in respuesta_costeo.text


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
    assert 'href="/clientes"' in respuesta.text
    assert 'href="/fichas"' in respuesta.text
    assert 'href="/negociar"' in respuesta.text
    assert 'href="/inicio"' in respuesta.text


def test_ver_logistica_muestra_en_construccion_y_vuelve_a_inicio():
    respuesta = cliente.get("/logistica")

    assert respuesta.status_code == 200
    assert "Logística" in respuesta.text
    assert "En construcción" in respuesta.text
    assert 'href="/inicio"' in respuesta.text


def test_ver_deposito_muestra_en_construccion_y_vuelve_a_inicio():
    respuesta = cliente.get("/deposito")

    assert respuesta.status_code == 200
    assert "Depósito" in respuesta.text
    assert "En construcción" in respuesta.text
    assert 'href="/inicio"' in respuesta.text


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


def test_barra_navegacion_en_placeholders_logistica_deposito_gerencia():
    casos = [("/logistica", "logistica", "Logística"), ("/deposito", "deposito", "Depósito"), ("/gerencia", "gerencia", "Gerencia")]
    for url, sector, nombre in casos:
        respuesta = cliente.get(url)
        assert respuesta.status_code == 200
        assert f'href="{url}" aria-label="Ir a {nombre}">{SECTORES[sector]["icono"]}</a>' in respuesta.text


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
        "/compras/buscar",
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


def test_barra_navegacion_muestra_el_titulo_del_sector_en_las_pantallas_principales():
    # El único título que queda es el de la barrita — se agrandó, pero
    # sigue siendo el mismo <div class="barra-titulo">.
    casos = [("/compras", "Compras"), ("/comercial", "Comercial"), ("/sistema", "Sistema")]
    for url, nombre in casos:
        respuesta = cliente.get(url)
        assert respuesta.status_code == 200
        assert f'<div class="barra-titulo">{nombre}</div>' in respuesta.text
