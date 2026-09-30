# -*- coding: utf-8 -*-
"""Administración → Alertas: los armados adentro del margen van APARTE y no suman.

La cuenta se prueba contra Postgres en
`test_armados_esperando_guia_r_contra_la_base.py`. Acá, la pantalla: que los
del margen se dibujen abajo, en gris y con su título, y que el número del
bloque sea solo el de los que pasaron el margen (dueño, 30/09).
"""
import os
import sys
from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import ARGENTINA, PUERTA_ADMINISTRACION, app  # noqa: E402

cliente = TestClient(app, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _puerta_abierta():
    with patch.dict(os.environ, {"CLAVE_ADMINISTRACION": "admin-secreta"}):
        cliente.cookies.set(PUERTA_ADMINISTRACION.cookie,
                            PUERTA_ADMINISTRACION.firma("admin-secreta"))
        try:
            yield
        finally:
            cliente.cookies.delete(PUERTA_ADMINISTRACION.cookie)


def _fila(renglon, articulo, fecha, esperan, fuera):
    return {"articulo_id": renglon, "articulo": articulo, "fecha_armado": fecha,
            "fecha_pedido": fecha, "renglon_id": renglon, "esperan": esperan,
            "cajas_a_armados_sin_ficha": 0.0, "fuera_del_margen": fuera,
            "pedido_id": 38, "cliente": "EJEMPLO Super", "sucursal": "EJEMPLO Suc"}


def _pantalla(filas):
    estado = [{"codigo": "armado_esperando_guia_r", "casos": 5, "mas_viejo": None,
               "calculada_el": datetime.now(ARGENTINA), "error": None}]
    with patch("app.main.listar_estado_alertas", return_value=estado), \
            patch("app.main.armados_esperando_guia_r", return_value=filas) as lista, \
            patch("app.main._hoy_argentina", return_value=date(2026, 9, 30)):
        respuesta = cliente.get("/administracion/alertas")
    lista.assert_called_once_with(date(2026, 9, 30))
    assert respuesta.status_code == 200
    return respuesta.text.split("</style>")[-1]


def test_los_del_margen_van_ABAJO_en_gris_y_el_numero_es_solo_el_de_los_viejos():
    marcado = _pantalla([
        _fila(1, "EJEMPLO Viejo", date(2026, 9, 25), 5.0, True),
        _fila(2, "EJEMPLO Ayer", date(2026, 9, 29), 57.0, False),
    ])

    assert "5 bultos en 1 renglón de 1 artículo" in marcado
    assert "cuenta solo lo armado hace más de 3 días" in marcado
    aparte = marcado.index('class="aparte"')
    assert "Esperando guía R (normal): 57 bultos armados en los últimos 3 días. No suman." \
        in marcado[aparte:]
    # El viejo arriba, en la tabla que cuenta; el de ayer, abajo y aparte.
    assert marcado.index("EJEMPLO Viejo") < aparte < marcado.index("EJEMPLO Ayer")


def test_SOLO_del_margen_dice_que_no_hay_casos_y_los_muestra_igual():
    marcado = _pantalla([_fila(2, "EJEMPLO Ayer", date(2026, 9, 29), 57.0, False)])

    assert "0 bultos en 0 renglones" in marcado
    assert "✓ Ninguno ahora mismo." in marcado
    assert marcado.index("✓ Ninguno ahora mismo.") < marcado.index('class="aparte"') \
        < marcado.index("EJEMPLO Ayer")


def test_sin_nada_en_el_margen_NO_hay_bloque_aparte():
    marcado = _pantalla([_fila(1, "EJEMPLO Viejo", date(2026, 9, 25), 5.0, True)])

    assert 'class="aparte"' not in marcado
    assert "No suman" not in marcado
