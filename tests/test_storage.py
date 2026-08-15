import re
from unittest.mock import Mock, patch

import httpx
import pytest

from core.storage import (
    BUCKET_COMANDAS,
    SUPABASE_SERVICE_KEY_ENV_VAR,
    SUPABASE_URL_ENV_VAR,
    _armar_ruta_unica,
    _sanear_nombre,
    borrar_foto_comanda,
    obtener_url_foto,
    subir_foto_comanda,
)

IMAGEN_DE_PRUEBA = b"contenido falso de un jpeg"


def _respuesta(status_code=200, text="", json_data=None):
    mock = Mock()
    mock.status_code = status_code
    mock.text = text
    mock.json = Mock(return_value=json_data or {})
    return mock


# --- _sanear_nombre / _armar_ruta_unica: no dependen de red ni de credenciales ---


def test_sanear_nombre_saca_acentos_espacios_y_mayusculas():
    assert _sanear_nombre("Ñoño Frutería N07P41") == "nono-fruteria-n07p41"


def test_sanear_nombre_vacio_queda_vacio():
    assert _sanear_nombre("") == ""
    assert _sanear_nombre(None) == ""


def test_armar_ruta_unica_tiene_el_formato_fecha_base_timestamp_random():
    ruta = _armar_ruta_unica("Saturno")
    assert re.match(r"^\d{4}-\d{2}-\d{2}/saturno-\d+-[0-9a-f]{8}\.jpg$", ruta)


def test_armar_ruta_unica_dos_llamadas_seguidas_no_se_pisan():
    ruta1 = _armar_ruta_unica("comanda")
    ruta2 = _armar_ruta_unica("comanda")
    assert ruta1 != ruta2


def test_armar_ruta_unica_base_vacia_usa_comanda_como_default():
    ruta = _armar_ruta_unica("")
    assert "/comanda-" in ruta


# --- subir_foto_comanda ---


def test_subir_foto_comanda_sin_supabase_url_lanza_error_claro(monkeypatch):
    monkeypatch.delenv(SUPABASE_URL_ENV_VAR, raising=False)
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-de-prueba")

    with pytest.raises(RuntimeError, match=SUPABASE_URL_ENV_VAR):
        subir_foto_comanda(IMAGEN_DE_PRUEBA, "comanda")


def test_subir_foto_comanda_sin_service_key_lanza_error_claro(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.delenv(SUPABASE_SERVICE_KEY_ENV_VAR, raising=False)

    with pytest.raises(RuntimeError, match=SUPABASE_SERVICE_KEY_ENV_VAR):
        subir_foto_comanda(IMAGEN_DE_PRUEBA, "comanda")


def test_subir_foto_comanda_exitosa_devuelve_la_ruta_y_manda_las_credenciales(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-secreta")

    with patch("core.storage.httpx.post", return_value=_respuesta(200)) as mock_post:
        ruta = subir_foto_comanda(IMAGEN_DE_PRUEBA, "Saturno")

    assert re.match(r"^\d{4}-\d{2}-\d{2}/saturno-\d+-[0-9a-f]{8}\.jpg$", ruta)

    url_llamada, kwargs = mock_post.call_args[0], mock_post.call_args[1]
    assert url_llamada[0] == f"https://proyecto.supabase.co/storage/v1/object/{BUCKET_COMANDAS}/{ruta}"
    assert kwargs["content"] == IMAGEN_DE_PRUEBA
    assert kwargs["headers"]["Authorization"] == "Bearer clave-secreta"
    assert kwargs["headers"]["apikey"] == "clave-secreta"
    assert kwargs["headers"]["Content-Type"] == "image/jpeg"


def test_subir_foto_comanda_recorta_barra_final_de_supabase_url(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co/")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-secreta")

    with patch("core.storage.httpx.post", return_value=_respuesta(200)) as mock_post:
        subir_foto_comanda(IMAGEN_DE_PRUEBA, "comanda")

    url_llamada = mock_post.call_args[0][0]
    assert "//storage" not in url_llamada
    assert url_llamada.startswith("https://proyecto.supabase.co/storage/v1/object/")


def test_subir_foto_comanda_error_de_supabase_lanza_error_con_detalle(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-mala")

    with patch("core.storage.httpx.post", return_value=_respuesta(403, text="Invalid JWT")):
        with pytest.raises(RuntimeError, match="403"):
            subir_foto_comanda(IMAGEN_DE_PRUEBA, "comanda")


def test_subir_foto_comanda_error_de_conexion_lanza_error_claro(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-de-prueba")

    with patch("core.storage.httpx.post", side_effect=httpx.ConnectError("sin conexión")):
        with pytest.raises(RuntimeError, match="No se pudo conectar"):
            subir_foto_comanda(IMAGEN_DE_PRUEBA, "comanda")


# --- obtener_url_foto ---


def test_obtener_url_foto_sin_supabase_url_lanza_error_claro(monkeypatch):
    monkeypatch.delenv(SUPABASE_URL_ENV_VAR, raising=False)
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-de-prueba")

    with pytest.raises(RuntimeError, match=SUPABASE_URL_ENV_VAR):
        obtener_url_foto("2026-08-13/comanda-123-abcdef12.jpg")


def test_obtener_url_foto_exitosa_arma_la_url_completa(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-secreta")

    ruta = "2026-08-13/comanda-123-abcdef12.jpg"
    respuesta = _respuesta(200, json_data={"signedURL": f"/object/sign/{BUCKET_COMANDAS}/{ruta}?token=xyz"})

    with patch("core.storage.httpx.post", return_value=respuesta) as mock_post:
        url = obtener_url_foto(ruta)

    assert url == f"https://proyecto.supabase.co/storage/v1/object/sign/{BUCKET_COMANDAS}/{ruta}?token=xyz"

    url_llamada, kwargs = mock_post.call_args[0], mock_post.call_args[1]
    assert url_llamada[0] == f"https://proyecto.supabase.co/storage/v1/object/sign/{BUCKET_COMANDAS}/{ruta}"
    assert kwargs["json"] == {"expiresIn": 3600}
    assert kwargs["headers"]["Authorization"] == "Bearer clave-secreta"


def test_obtener_url_foto_usa_la_expiracion_pasada_por_parametro(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-secreta")

    respuesta = _respuesta(200, json_data={"signedURL": "/object/sign/comandas/x.jpg?token=xyz"})
    with patch("core.storage.httpx.post", return_value=respuesta) as mock_post:
        obtener_url_foto("x.jpg", expiracion_segundos=120)

    assert mock_post.call_args[1]["json"] == {"expiresIn": 120}


def test_obtener_url_foto_sin_campo_signedurl_lanza_error(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-secreta")

    respuesta = _respuesta(200, json_data={"algo_inesperado": True})
    with patch("core.storage.httpx.post", return_value=respuesta):
        with pytest.raises(RuntimeError, match="URL firmada"):
            obtener_url_foto("x.jpg")


def test_obtener_url_foto_error_de_supabase_lanza_error_con_detalle(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-secreta")

    with patch("core.storage.httpx.post", return_value=_respuesta(404, text="Object not found")):
        with pytest.raises(RuntimeError, match="404"):
            obtener_url_foto("no-existe.jpg")


def test_obtener_url_foto_error_de_conexion_lanza_error_claro(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-secreta")

    with patch("core.storage.httpx.post", side_effect=httpx.ConnectError("sin conexión")):
        with pytest.raises(RuntimeError, match="No se pudo conectar"):
            obtener_url_foto("x.jpg")


# --- borrar_foto_comanda ---


def test_borrar_foto_comanda_sin_supabase_url_lanza_error_claro(monkeypatch):
    monkeypatch.delenv(SUPABASE_URL_ENV_VAR, raising=False)
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-de-prueba")

    with pytest.raises(RuntimeError, match=SUPABASE_URL_ENV_VAR):
        borrar_foto_comanda("2026-08-13/comanda-123-abcdef12.jpg")


def test_borrar_foto_comanda_exitosa_manda_las_credenciales(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-secreta")

    ruta = "2026-08-13/comanda-123-abcdef12.jpg"
    with patch("core.storage.httpx.delete", return_value=_respuesta(200)) as mock_delete:
        borrar_foto_comanda(ruta)

    url_llamada, kwargs = mock_delete.call_args[0], mock_delete.call_args[1]
    assert url_llamada[0] == f"https://proyecto.supabase.co/storage/v1/object/{BUCKET_COMANDAS}/{ruta}"
    assert kwargs["headers"]["Authorization"] == "Bearer clave-secreta"
    assert kwargs["headers"]["apikey"] == "clave-secreta"


def test_borrar_foto_comanda_error_de_supabase_lanza_error_con_detalle(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-mala")

    with patch("core.storage.httpx.delete", return_value=_respuesta(403, text="Invalid JWT")):
        with pytest.raises(RuntimeError, match="403"):
            borrar_foto_comanda("2026-08-13/comanda-123-abcdef12.jpg")


def test_borrar_foto_comanda_error_de_conexion_lanza_error_claro(monkeypatch):
    monkeypatch.setenv(SUPABASE_URL_ENV_VAR, "https://proyecto.supabase.co")
    monkeypatch.setenv(SUPABASE_SERVICE_KEY_ENV_VAR, "clave-de-prueba")

    with patch("core.storage.httpx.delete", side_effect=httpx.ConnectError("sin conexión")):
        with pytest.raises(RuntimeError, match="No se pudo conectar"):
            borrar_foto_comanda("2026-08-13/comanda-123-abcdef12.jpg")
