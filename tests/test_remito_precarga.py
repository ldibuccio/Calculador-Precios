"""Recibir remito: la precarga resta lo que Depósito ya cargó como rechazado (dueño, 02/10), contra Postgres.

El caso real fue el remito 20424 (Frutamax): Tomate Redondo salió 10 / 160 kg
y Depósito había cargado 10 rechazados, y la pantalla precargaba recibidos
10 / 160. La regla: bultos = enviados − rechazados, kilos proporcionales, y
con todo rechazado 0 y 0. Sin rechazos cargados, lo enviado como siempre.
Sigue editable, y el cotejo no cambia. Los nombres son de EJEMPLO.
"""
import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.remitos import precarga_de_lo_recibido  # noqa: E402
from tests.test_remitos import _cliente, _rechazo_de_deposito, base  # noqa: E402,F401  (fixture)


def _precarga(texto, renglon_id):
    """(bultos, kilos) que la pantalla dibuja en los campos de ESE renglón."""
    marcado = texto.split("</style>")[-1]
    bultos = re.search(rf'name="bultos_{renglon_id}" required\s+value="([^"]*)"', marcado)
    kilos = re.search(rf'name="kilos_{renglon_id}" required\s+value="([^"]*)"', marcado)
    return bultos.group(1), kilos.group(1)


def test_la_PANTALLA_precarga_lo_enviado_MENOS_lo_rechazado_total_parcial_y_sin(base, monkeypatch):
    """Renglón 11: 5 / 50 kg, Depósito rechazó los 5 → 0 / 0.
    Renglón 12: 3 / 30 kg, Depósito rechazó 1 (y otro ANULADO) → 2 / 20.
    Renglón 21, en otro remito, sin rechazos → 4 / 40, como hoy.

    El RIVAL es la precarga hasta el 02/10: lo enviado en los tres."""
    d, sql = base
    _rechazo_de_deposito(sql, 11, 5)
    _rechazo_de_deposito(sql, 12, 1)
    _rechazo_de_deposito(sql, 12, 1, anulado=True)
    remito = d.emitir_remito(1, "VL", "R-0001")
    otro = d.emitir_remito(2, "VL", "R-0002")
    ids = {r["pedido_renglon_id"]: r["id"] for r in d.remito_por_id(remito)["renglones"]}
    (id_21,) = [r["id"] for r in d.remito_por_id(otro)["renglones"]]
    cliente = _cliente(monkeypatch, "administracion")
    pagina = cliente.get(f"/administracion/facturacion/remito/{remito}/recibir")
    assert pagina.status_code == 200
    assert _precarga(pagina.text, ids[11]) == ("0", "0")
    assert _precarga(pagina.text, ids[12]) == ("2", "20")
    assert _precarga(cliente.get(f"/administracion/facturacion/remito/{otro}/recibir").text, id_21) == ("4", "40")
    # Lo que la pantalla propone se guarda tal cual, y el cotejo coincide.
    datos = {f"bultos_{ids[11]}": "0", f"kilos_{ids[11]}": "0", f"bultos_{ids[12]}": "2", f"kilos_{ids[12]}": "20"}
    from unittest.mock import patch
    from tests.test_remitos import _jpeg
    with patch("app.main.subir_foto_comanda", return_value="remitos/EJ.jpg"):
        respuesta = cliente.post(f"/administracion/facturacion/remito/{remito}/recibir", data=datos,
                                 files={"fotos": ("r.jpg", _jpeg(), "image/jpeg")}, follow_redirects=False)
    assert respuesta.status_code == 303
    assert d.contar_remitos_con_rechazo_distinto()["casos"] == 0
    guardado = {r["pedido_renglon_id"]: (float(r["bultos_recibidos"]), float(r["kilos_recibidos"]))
                for r in d.remito_por_id(remito)["renglones"]}
    assert guardado == {11: (0.0, 0.0), 12: (2.0, 20.0)}


def test_la_REGLA_proporcional_y_sus_bordes():
    def renglon(bultos, kilos, rechazo):
        return {"bultos_enviados": bultos, "kilos_enviados": kilos, "rechazo_deposito": rechazo}
    assert precarga_de_lo_recibido(renglon(10, 160, 0)) == (10.0, 160.0)          # sin rechazo
    assert precarga_de_lo_recibido(renglon(10, 160, None)) == (10.0, 160.0)
    assert precarga_de_lo_recibido(renglon(10, 160, 10)) == (0.0, 0.0)            # Tomate Redondo
    assert precarga_de_lo_recibido(renglon(20, 160, 20)) == (0.0, 0.0)            # Uva
    assert precarga_de_lo_recibido(renglon(3, 50, 1)) == (2.0, 33.33)             # proporcional
    assert precarga_de_lo_recibido(renglon(10, 160, 12)) == (0.0, 0.0)            # de más: tope
    assert precarga_de_lo_recibido(renglon(10, 160, -2)) == (10.0, 160.0)         # negativo: nada
