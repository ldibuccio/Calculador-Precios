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


def test_agregar_articulo_nombre_string_vacio_muestra_error_prolijo_no_422():
    # Regresión: un campo de texto Form(...) vacío ("" y no solo espacios) hacía
    # que FastAPI devolviera un 422 crudo en vez de nuestro error prolijo.
    with patch("app.main.crear_articulo") as mock_crear, patch("app.main.listar_articulos", return_value=[]):
        respuesta = cliente.post("/articulos/nuevo", data={"nombre": ""})

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
