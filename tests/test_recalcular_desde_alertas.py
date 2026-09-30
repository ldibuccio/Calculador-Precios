"""El botón "Recalcular ahora" en las Alertas de cada sector (30/09, dueño).

Estaba solo en Auditoría. Desde que Gerencia y Administración tienen su
pantalla de Alertas, el que las mira ahí no tenía cómo recalcular sin salir.
Ahora las cuatro pantallas de Alertas lo traen, recalculan con la MISMA
función que Auditoría y vuelven a la pantalla desde la que se apretó.
"""

import os
import sys
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import (  # noqa: E402
    PUERTA_ADMINISTRACION, PUERTA_COMPRAS, PUERTA_GERENCIA, app,
)

cliente = TestClient(app, base_url="https://testserver")

CLAVES = {"CLAVE_COMPRAS": "compras-secreta", "CLAVE_GERENCIA": "gerencia-secreta",
          "CLAVE_ADMINISTRACION": "admin-secreta"}

SECTORES = ["compras", "comercial", "gerencia", "administracion"]


@pytest.fixture(autouse=True)
def _puertas_abiertas():
    with patch.dict(os.environ, CLAVES):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
        cliente.cookies.set(PUERTA_GERENCIA.cookie, PUERTA_GERENCIA.firma("gerencia-secreta"))
        cliente.cookies.set(PUERTA_ADMINISTRACION.cookie,
                            PUERTA_ADMINISTRACION.firma("admin-secreta"))
        try:
            yield
        finally:
            for puerta in (PUERTA_COMPRAS, PUERTA_GERENCIA, PUERTA_ADMINISTRACION):
                cliente.cookies.delete(puerta.cookie)


def _pantalla(url):
    with patch("app.main.listar_estado_alertas", return_value=[]):
        return cliente.get(url)


@pytest.mark.parametrize("sector", SECTORES)
def test_la_pantalla_de_alertas_trae_el_boton_que_postea_a_SU_sector(sector):
    respuesta = _pantalla(f"/{sector}/alertas")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert (f'<form method="post" action="/{sector}/alertas/recalcular">\n'
            '    <button class="recalcular" type="submit">Recalcular ahora</button>') in marcado


@pytest.mark.parametrize("sector", SECTORES)
def test_recalcular_corre_TODAS_y_vuelve_a_las_alertas_del_sector(sector):
    with patch("app.main.recalcular", return_value={"corrio": True, "ok": 22, "fallaron": 0}) as mock:
        respuesta = cliente.post(f"/{sector}/alertas/recalcular", follow_redirects=False)
    mock.assert_called_once()
    assert respuesta.status_code == 303
    destino = urlparse(respuesta.headers["location"])
    assert destino.path == f"/{sector}/alertas"
    assert parse_qs(destino.query) == {"aviso": ["Listo: 22 controles recalculados."]}


@pytest.mark.parametrize("resumen, clave, texto", [
    ({"corrio": False, "ok": 0, "fallaron": 0}, "aviso",
     "Ya se estaban recalculando en este momento. Probá de nuevo en un rato."),
    ({"corrio": True, "ok": 20, "fallaron": 2}, "error",
     "Se recalcularon 20, pero 2 no se pudieron calcular (quedaron con su valor viejo)."),
])
def test_los_OTROS_resultados_son_los_mismos_que_en_Auditoria(resumen, clave, texto):
    with patch("app.main.recalcular", return_value=resumen):
        desde_gerencia = cliente.post("/gerencia/alertas/recalcular", follow_redirects=False)
        desde_auditoria = cliente.post("/auditoria/recalcular", follow_redirects=False)
    assert parse_qs(urlparse(desde_gerencia.headers["location"]).query) == {clave: [texto]}
    assert parse_qs(urlparse(desde_auditoria.headers["location"]).query) == {clave: [texto]}


@pytest.mark.parametrize("clave, clase", [("aviso", "mensaje ok"), ("error", "mensaje mal")])
def test_la_pantalla_MUESTRA_lo_que_dejo_el_boton(clave, clase):
    """Un `?error=` que el GET no lee es un error mudo."""
    marcado = _pantalla(f"/gerencia/alertas?{clave}=EJEMPLO+de+resultado").text.split("</style>")[-1]
    assert f'<div class="{clase}">EJEMPLO de resultado</div>' in marcado


def test_sin_la_clave_de_GERENCIA_no_recalcula():
    cliente.cookies.delete(PUERTA_GERENCIA.cookie)
    with patch("app.main.recalcular") as mock:
        respuesta = cliente.post("/gerencia/alertas/recalcular", follow_redirects=False)
    mock.assert_not_called()
    assert 'type="password"' in respuesta.text


@pytest.mark.parametrize("url, puerta", [
    ("/compras/alertas/recalcular", PUERTA_COMPRAS),
    ("/administracion/alertas/recalcular", PUERTA_ADMINISTRACION),
])
def test_sin_la_clave_de_su_prefijo_no_recalcula(url, puerta):
    cliente.cookies.delete(puerta.cookie)
    with patch("app.main.recalcular") as mock:
        respuesta = cliente.post(url, follow_redirects=False)
    mock.assert_not_called()
    # Lo que SÍ tiene que pasar: la clave del prefijo, no un 500 cualquiera.
    assert respuesta.status_code == 401
    assert 'type="password"' in respuesta.text
