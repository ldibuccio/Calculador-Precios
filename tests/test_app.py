from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import DATABASE_URL_ENV_VAR, obtener_conexion
from app.main import app

cliente = TestClient(app)


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
    {"id": 1, "nombre": "Frutilla"},
    {"id": 2, "nombre": "Mango"},
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
            data={"nombre": "Kiwi"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/articulos"
    mock_crear.assert_called_once_with("Kiwi")


def test_agregar_articulo_nombre_vacio_muestra_error():
    with patch("app.main.crear_articulo") as mock_crear, patch("app.main.listar_articulos", return_value=[]):
        respuesta = cliente.post("/articulos/nuevo", data={"nombre": "   "})

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_crear.assert_not_called()


def test_agregar_articulo_error_de_base_muestra_mensaje_claro():
    with (
        patch("app.main.crear_articulo", side_effect=Exception("no se pudo conectar")),
        patch("app.main.listar_articulos", return_value=[]),
    ):
        respuesta = cliente.post("/articulos/nuevo", data={"nombre": "Kiwi"})

    assert respuesta.status_code == 500
    assert "No se pudo guardar" in respuesta.text


ARTICULO_DE_PRUEBA = {"id": 1, "nombre": "Frutilla"}


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
            data={"nombre": "Frutilla Premium"},
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/articulos"
    mock_actualizar.assert_called_once_with(1, "Frutilla Premium")


def test_editar_articulo_nombre_vacio_muestra_error():
    with patch("app.main.actualizar_articulo") as mock_actualizar:
        respuesta = cliente.post("/articulos/1/editar", data={"nombre": "   "})

    assert respuesta.status_code == 400
    assert "no puede estar vacío" in respuesta.text
    mock_actualizar.assert_not_called()


def test_editar_articulo_error_de_base_muestra_mensaje_claro():
    with patch("app.main.actualizar_articulo", side_effect=Exception("no se pudo conectar")):
        respuesta = cliente.post("/articulos/1/editar", data={"nombre": "Frutilla"})

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
