"""Cajas por reponer en las Alertas de Gerencia y Administración (30/09, dueño).

Hasta ese día la alerta declaraba solo Compras: estaba calculada, con su caso,
y en las Alertas de Gerencia y de Administración no aparecía nunca. Ahora sale
en los tres sectores, con la caja, las que quedan y el umbral.

Los nombres de las cajas son de EJEMPLO.
"""

import os
import sys
from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import (  # noqa: E402
    ARGENTINA, PUERTA_ADMINISTRACION, PUERTA_COMPRAS, PUERTA_GERENCIA, app,
)

cliente = TestClient(app, base_url="https://testserver")

CLAVES = {"CLAVE_COMPRAS": "compras-secreta", "CLAVE_GERENCIA": "gerencia-secreta",
          "CLAVE_ADMINISTRACION": "admin-secreta"}


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


# Una abajo del umbral y otra arriba: la de arriba NO tiene que aparecer, así
# un detalle que listara todo el catálogo no pasa.
ENVASES = [
    {"id": 1, "nombre": "Caja EJEMPLO Chica", "umbral_reposicion": 3000, "stock": 10554,
     "desde": date(2026, 9, 17), "contadas": 5000, "declaradas": 9462, "por_guias": -3908},
    {"id": 2, "nombre": "Caja EJEMPLO Grande", "umbral_reposicion": 3000, "stock": 154,
     "desde": date(2026, 9, 17), "contadas": 5000, "declaradas": -2086, "por_guias": -2760},
]


def _estado():
    return [{"codigo": "cajas_a_reponer", "casos": 1, "mas_viejo": None,
             "calculada_el": datetime.now(ARGENTINA), "error": None}]


def _alertas(url):
    with patch("app.main.listar_estado_alertas", return_value=_estado()), \
         patch("app.db.stock_de_envases", return_value=ENVASES):
        return cliente.get(url)


@pytest.mark.parametrize("url", ["/gerencia/alertas", "/administracion/alertas", "/compras/alertas"])
def test_la_alerta_sale_con_la_CAJA_las_que_QUEDAN_y_el_UMBRAL(url):
    respuesta = _alertas(url)
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "Cajas nuestras debajo del aviso de reposición" in marcado
    assert 'data-rotulo="Envase">Caja EJEMPLO Grande<' in marcado
    assert 'data-rotulo="Quedan">154<' in marcado
    assert 'data-rotulo="Avisa debajo de">3000<' in marcado
    assert 'data-rotulo="Faltan">2846<' in marcado
    # La que está arriba de su aviso no es un caso.
    assert "Caja EJEMPLO Chica" not in marcado


def test_desde_ADMINISTRACION_lleva_a_SU_Cajas():
    marcado = _alertas("/administracion/alertas").text.split("</style>")[-1]
    assert 'href="/administracion/cajas">Ver en Cajas</a>' in marcado
    assert 'href="/compras/cajas"' not in marcado


def test_desde_GERENCIA_ningun_link_choca_contra_una_clave_ajena():
    marcado = _alertas("/gerencia/alertas").text.split("</style>")[-1]
    assert 'href="/compras/cajas"' not in marcado
    assert 'href="/administracion/cajas"' not in marcado
