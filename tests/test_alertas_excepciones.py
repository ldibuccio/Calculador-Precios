"""EXCEPCIONES DE ALERTAS (dueño, 16/10): lo que una alerta NO cuenta.

El remito 20344 de Día % arrastraba un rechazo distinto ya corregido por
otro lado: sin tocar el remito ni el stock, una fila en `alertas_excepciones`
lo saca de "remitos_rechazo_distinto". El aviso amarillo del remito queda,
con el motivo.

El galpón es el de tests/test_remitos.py (siembra real, esquema_completo).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_remitos import _cliente, _marcado, _recibido, _rechazo_de_deposito, base  # noqa: E402,F401

ALERTA = "remitos_rechazo_distinto"


def _con_rechazo_distinto(d, sql):
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id, bultos={11: 3}, kilos={11: 30})     # el remito dice rechazo 2
    _rechazo_de_deposito(sql, 11, 1)                            # Depósito cargó 1
    return remito_id


def _excepcion(sql, alerta, apunta_a, motivo="Arrastre ya corregido"):
    sql("INSERT INTO alertas_excepciones (alerta, apunta_a, motivo) VALUES (%s, %s, %s)", (alerta, apunta_a, motivo))


def test_CON_la_excepcion_la_alerta_da_0_y_SIN_ella_da_1(base):
    d, sql = base
    remito_id = _con_rechazo_distinto(d, sql)
    assert d.contar_remitos_con_rechazo_distinto()["casos"] == 1          # sin excepción
    # Los RIVALES: la misma alerta para otro id, y otra alerta para el mismo id.
    _excepcion(sql, ALERTA, remito_id + 1000)
    _excepcion(sql, "remitos_sin_factura", remito_id)
    assert d.contar_remitos_con_rechazo_distinto()["casos"] == 1
    _excepcion(sql, ALERTA, remito_id)
    assert d.contar_remitos_con_rechazo_distinto() == {"casos": 0, "mas_viejo": None}
    assert d.remitos_con_rechazo_distinto() == []                         # y el detalle tampoco
    sql("DELETE FROM alertas_excepciones WHERE alerta = %s AND apunta_a = %s", (ALERTA, remito_id))
    assert d.contar_remitos_con_rechazo_distinto()["casos"] == 1


def test_el_REMITO_sigue_avisando_pero_con_el_MOTIVO(base, monkeypatch):
    d, sql = base
    remito_id = _con_rechazo_distinto(d, sql)
    url = f"/administracion/facturacion/remito/{remito_id}"
    sin = _marcado(_cliente(monkeypatch, "administracion").get(url))
    assert "Revisá el reingreso en Depósito" in sin and "data-excepcion" not in sin
    _excepcion(sql, ALERTA, remito_id)
    con = _marcado(_cliente(monkeypatch, "administracion").get(url))
    assert 'class="ojo"' in con                                           # el aviso amarillo queda
    assert re.findall(r"<span data-excepcion>([^<]*)</span>", con) == [
        f"No cuenta en Alertas: Arrastre ya corregido (desde el {d.remito_por_id(remito_id)['excepcion_rechazo']['fecha'].strftime('%d/%m/%Y')})."]
    assert "Revisá el reingreso en Depósito" not in con


def test_la_BASE_no_deja_dos_veces_lo_mismo_ni_un_motivo_vacio(base):
    import psycopg2
    d, sql = base
    _excepcion(sql, ALERTA, 5)
    for fila in ((ALERTA, 5, "otro"), (ALERTA, 6, "  "), (" ", 7, "x")):
        try:
            _excepcion(sql, *fila)
        except (psycopg2.errors.UniqueViolation, psycopg2.errors.CheckViolation):
            continue
        raise AssertionError(f"entró {fila}")
