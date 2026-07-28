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
