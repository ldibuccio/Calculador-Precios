import io
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import DATABASE_URL_ENV_VAR, obtener_conexion
from app.main import (
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


def test_ver_compras_muestra_las_de_los_ultimos_2_dias():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=COMPRAS_DE_PRUEBA) as mock_listar,
    ):
        respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert "Últimas compras" in respuesta.text
    assert "Mzn Red" in respuesta.text
    assert "Saturno" in respuesta.text
    assert "N07P41" in respuesta.text
    assert "Mango" in respuesta.text
    assert "Fecha" in respuesta.text
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


def test_ver_compras_sin_compras_muestra_mensaje():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", return_value=[]),
    ):
        respuesta = cliente.get("/compras")

    assert respuesta.status_code == 200
    assert "No hay compras cargadas en los últimos 2 días" in respuesta.text


def test_ver_compras_error_de_base_muestra_error_claro():
    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.listar_compras_por_rango_fechas", side_effect=Exception("no se pudo conectar")),
    ):
        respuesta = cliente.get("/compras")

    assert respuesta.status_code == 500
    assert "No se pudieron leer las compras" in respuesta.text


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


def test_ver_nueva_compra_sin_proveedor_error_de_base_da_500():
    with patch("app.main.listar_proveedores", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.get("/compras/nueva")

    assert respuesta.status_code == 500


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
    assert respuesta.headers["location"] == "/compras"
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
    assert respuesta.headers["location"] == "/compras"
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
    assert respuesta.headers["location"] == "/compras"
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
    with patch("app.main.eliminar_compra") as mock_eliminar:
        respuesta = cliente.post("/compras/30/eliminar", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras"
    mock_eliminar.assert_called_once_with(30)


def test_eliminar_compra_error_de_base_da_500():
    with patch("app.main.eliminar_compra", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/compras/30/eliminar")

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
    orden = ["Agregar Artículos", "Cancelar", "Guardar"]
    posiciones = [respuesta.text.index(texto) for texto in orden]
    assert posiciones == sorted(posiciones)
    assert 'value="agregar_articulos"' in respuesta.text
    assert 'class="boton-exito" id="boton-guardar"' in respuesta.text
    assert 'class="boton boton-peligro"' in respuesta.text
    assert "confirm('¿Seguro? Se pierde lo que cargaste de esta compra')" in respuesta.text


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
    assert 'value="" style="text-transform: uppercase;"' in respuesta.text
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
    with (
        patch("app.main.extraer_comanda", side_effect=Exception("no se pudo conectar con la API")),
        patch("app.main.listar_proveedores", return_value=[]),
    ):
        respuesta = cliente.post(
            "/compras/nueva/foto",
            files={"foto": ("comanda.jpg", b"contenido falso", "image/jpeg")},
        )

    assert respuesta.status_code == 500
    assert "No se pudo leer la foto" in respuesta.text


def _datos_confirmar_foto(descartar_item_1=True, codigo_puesto="N07P41", nombre="Saturno"):
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
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 5000.0, None, "Clark")
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
    assert respuesta.headers["location"] == "/compras"
    mock_proveedor.assert_called_once_with("N07P41", "Saturno")
    mock_crear.assert_called_once_with(HOY_DE_PRUEBA, 5, 200, 10.0, 18.0, 180.0, None, 5000.0, None, "Clark")
    mock_aprender.assert_called_once_with(200, "kiwi", 5)


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
    # Mango: sin costo anterior ni vigente -> "—", no "None".
    assert "None" not in respuesta.text
    assert "Fecha de referencia" in respuesta.text


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
        "descuento": 0.23,
        "envase_nombre": "Caja Grande",
        "envase_variable": False,
        "contenido_ficha": 8.0,
        "costo_envase_unitario": 1600.0,
        "envases_por_unidad": 0.125,
        "costo_envase_por_unidad": 200.0,
        "precio_sugerido": 5519.4805,
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
    assert "0.2300" in respuesta.text  # descuento
    assert "Caja Grande" in respuesta.text
    assert "1600.0000" in respuesta.text  # costo del envase
    assert "0.125000" in respuesta.text  # envases por unidad
    assert "200.0000" in respuesta.text  # costo de envase por unidad
    assert "5519.4805" in respuesta.text  # precio sugerido paso a paso
