# -*- coding: utf-8 -*-
"""LA FOTO DEL PANEL DE CONTROL (dueño, 09/10).

El tablero se calcula a las 06:00 y a las 14:00 (hora Argentina) y al entrar
muestra lo último calculado. "Actualizar ahora" recalcula para todos. Si el
cálculo automático falla, se ve la última foto buena con el aviso "no se pudo
actualizar a las 14:00".

Lo puro (los turnos, el JSON con fechas, lo que se dice arriba) va sin base;
el circuito entero, contra Postgres con el esquema real.
"""
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.panel_foto import a_texto, de_texto, estado_de_la_foto, hay_que_calcular, turno_vigente  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

AR = ZoneInfo("America/Argentina/Buenos_Aires")
OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


def _ar(dia, hora, minuto=0):
    return datetime(2026, 10, dia, hora, minuto, tzinfo=AR)


# --- lo puro ---------------------------------------------------------------------

@pytest.mark.parametrize("ahora, turno", [
    (_ar(9, 5, 59), _ar(8, 14)),       # de madrugada todavía vale el de ayer a las 14
    (_ar(9, 6), _ar(9, 6)),
    (_ar(9, 13, 59), _ar(9, 6)),
    (_ar(9, 14), _ar(9, 14)),
    (_ar(9, 23, 30), _ar(9, 14)),
])
def test_el_TURNO_vigente_es_el_ultimo_de_las_06_o_las_14_que_ya_paso(ahora, turno):
    assert turno_vigente(ahora) == turno


def test_hay_que_calcular_solo_si_el_turno_vigente_NO_se_intento():
    # El rival: el de AYER a las 14 está intentado, y a las 06:30 de hoy igual toca.
    ayer_14 = _ar(8, 14).astimezone(ZoneInfo("UTC"))       # la base devuelve UTC
    assert hay_que_calcular([ayer_14], _ar(9, 6, 30)) is True
    assert hay_que_calcular([ayer_14, _ar(9, 6).astimezone(ZoneInfo("UTC"))], _ar(9, 6, 30)) is False
    assert hay_que_calcular([], _ar(9, 6, 30)) is True


def test_la_foto_vuelve_del_JSON_con_sus_FECHAS():
    datos = {"peso": {"anterior": {"desde": date(2026, 9, 1), "kilo": {"pct": Decimal("12.5")}}},
             "rentabilidad": [{"rangos": {"mes": (date(2026, 10, 1), date(2026, 10, 9))}}],
             "instante": datetime(2026, 10, 9, 14, 0, tzinfo=AR)}
    vuelta = de_texto(a_texto(datos))
    assert vuelta["peso"]["anterior"]["desde"] == date(2026, 9, 1)
    assert vuelta["peso"]["anterior"]["kilo"]["pct"] == 12.5
    assert vuelta["rentabilidad"][0]["rangos"]["mes"] == [date(2026, 10, 1), date(2026, 10, 9)]
    assert vuelta["instante"] == datetime(2026, 10, 9, 14, 0, tzinfo=AR)
    with pytest.raises(TypeError):
        a_texto({"raro": object()})


def test_ARRIBA_dice_cuando_y_avisa_SOLO_la_falla_posterior_a_la_foto_buena():
    utc = ZoneInfo("UTC")
    buena = {"calculada_el": _ar(9, 6, 1).astimezone(utc)}
    fallo = {"turno": _ar(9, 14).astimezone(utc), "calculada_el": _ar(9, 14, 2).astimezone(utc), "ok": False}
    assert estado_de_la_foto(buena, [fallo], _ar(9, 15)) == {
        "hay_foto": True, "actualizado": "Actualizado hoy a las 06:01",
        "fallo": "No se pudo actualizar a las 14:00."}
    # Después de la falla alguien tocó "Actualizar ahora": ya no se avisa.
    arreglada = {"calculada_el": _ar(9, 14, 30).astimezone(utc)}
    assert estado_de_la_foto(arreglada, [fallo], _ar(9, 15))["fallo"] is None
    assert estado_de_la_foto(buena, [], _ar(10, 9))["actualizado"] == "Actualizado ayer a las 06:01"
    assert estado_de_la_foto(buena, [], _ar(12, 9))["actualizado"] == "Actualizado el 09/10 a las 06:01"


# --- contra la base -------------------------------------------------------------

@pytest.fixture
def panel():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: la foto del panel no se verificó")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        import app.main as m
        from tests.test_administracion_reordenada import CLAVES, _cliente
        with patch.dict(os.environ, CLAVES):
            yield m, _cliente(m, "gerencia")


def _filas(m):
    import app.db as d
    conexion = d.obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT turno, ok, error IS NOT NULL FROM panel_fotos ORDER BY id")
            return cursor.fetchall()
    finally:
        conexion.close()


def _vales(total):
    """El panel con montos de mentira (los de test_panel_numeros_enteros) y
    Vales en `total`: lo que se mira es de CUÁNDO es el número, no la cuenta."""
    from tests.test_panel_numeros_enteros import _datos

    def calcular(hoy):
        datos = {cuadro: _datos(cuadro, hoy, {}) for cuadro in
                 ("rentabilidad", "cajas", "pedidos", "peso", "vacios", "rechazos", "mermas", "segunda")}
        return {**datos, "vales": {"total": total, "cantidad": 1, "vales": []}}
    return calcular


def _tablero(cliente):
    respuesta = cliente.get("/gerencia/panel")
    assert respuesta.status_code == 200, respuesta.text[:300]
    return respuesta.text.split("</style>")[-1]


def _numero_de_vales(tablero):
    cuadro = tablero.split('data-cuadro="vales">', 1)[1].split("</a>", 1)[0]
    return cuadro.split('class="cuadro-numero">', 1)[1].split("<", 1)[0]


def test_al_ENTRAR_no_calcula_muestra_la_FOTO_y_el_BOTON_la_renueva_para_todos(panel):
    m, cliente = panel
    with patch.object(m, "calcular_el_panel", side_effect=_vales(111)) as calculo:
        primera = _tablero(cliente)           # no hay ninguna foto: la calcula una vez
        assert calculo.call_count == 1 and _numero_de_vales(primera) == "$111"
        assert '<span class="foto-cuando" data-actualizado>Actualizado hoy a las ' in primera
        assert '<form method="post" action="/gerencia/panel/actualizar"><button type="submit">' \
               'Actualizar ahora</button></form>' in primera
        assert "data-fallo" not in primera
        calculo.side_effect = _vales(222)     # los datos cambiaron...
        assert _numero_de_vales(_tablero(cliente)) == "$111" and calculo.call_count == 1   # ...y al entrar NO
        boton = cliente.post("/gerencia/panel/actualizar", follow_redirects=False)
        assert boton.status_code == 303 and boton.headers["location"] == "/gerencia/panel"
        assert calculo.call_count == 2 and _numero_de_vales(_tablero(cliente)) == "$222"
    assert _filas(m) == [(None, True, False), (None, True, False)]


def test_el_TURNO_se_calcula_una_vez_y_si_FALLA_se_ve_la_ultima_buena_con_el_aviso(panel):
    m, cliente = panel
    with patch.object(m, "calcular_el_panel", side_effect=_vales(500)):
        m._actualizar_panel_si_toca(_ar(9, 6, 0))
        m._actualizar_panel_si_toca(_ar(9, 6, 1))          # el mismo turno: no vuelve a calcular
        assert _filas(m) == [(_ar(9, 6), True, False)]
    with patch.object(m, "calcular_el_panel", side_effect=RuntimeError("la base no contestó")) as roto:
        m._actualizar_panel_si_toca(_ar(9, 14, 0))
        m._actualizar_panel_si_toca(_ar(9, 14, 1))         # un turno que falló NO se reintenta
        assert roto.call_count == 1
        tablero = _tablero(cliente)
    assert _filas(m) == [(_ar(9, 6), True, False), (_ar(9, 14), False, True)]
    assert _numero_de_vales(tablero) == "$500"
    assert '<div class="aviso-foto" data-fallo>No se pudo actualizar a las 14:00. ' in tablero


def test_la_BASE_no_deja_dos_intentos_del_mismo_turno_ni_una_foto_buena_sin_datos(panel):
    import psycopg2
    m, _ = panel
    import app.db as d
    d.guardar_foto_del_panel(turno=_ar(9, 6), datos_json="{}")
    for malo in (lambda: d.guardar_foto_del_panel(turno=_ar(9, 6), datos_json="{}"),):
        with pytest.raises(psycopg2.errors.UniqueViolation):
            malo()
    conexion = d.obtener_conexion()
    try:
        for consulta in ("INSERT INTO panel_fotos (ok, datos) VALUES (true, NULL)",
                         "INSERT INTO panel_fotos (ok, datos, error) VALUES (false, '{}', 'x')",
                         "INSERT INTO panel_fotos (ok) VALUES (false)"):
            with conexion.cursor() as cursor, pytest.raises(psycopg2.errors.CheckViolation):
                cursor.execute(consulta)
            conexion.rollback()
    finally:
        conexion.close()


def test_se_guardan_las_ULTIMAS_fotos_y_la_ultima_BUENA_no_se_borra_nunca(panel):
    m, _ = panel
    import app.db as d
    d.guardar_foto_del_panel(turno=None, datos_json='{"la": "buena"}')
    for n in range(d.FOTOS_DEL_PANEL_QUE_SE_GUARDAN + 5):
        d.guardar_foto_del_panel(turno=_ar(1, 6) + timedelta(days=n), datos_json=None, error="falló")
    filas = _filas(m)
    assert len(filas) == d.FOTOS_DEL_PANEL_QUE_SE_GUARDAN + 1
    assert d.foto_buena_del_panel()["datos_json"] == '{"la": "buena"}'


def test_el_BUCLE_de_las_alertas_es_el_que_dispara_el_panel_con_su_tope():
    """El mismo mecanismo automático que las Alertas: `_bucle_revision_casillas`
    llama a `_actualizar_panel_si_toca` en un hilo, con SEGUNDOS_TIMEOUT_PANEL."""
    import ast
    arbol = ast.parse(open(os.path.join(RAIZ, "app", "main.py"), encoding="utf-8").read())
    (bucle,) = [n for n in ast.walk(arbol) if isinstance(n, ast.AsyncFunctionDef) and n.name == "_bucle_revision_casillas"]
    llamadas = [n for n in ast.walk(bucle) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "wait_for"]
    del_panel = [c for c in llamadas
                 if any(isinstance(a, ast.Name) and a.id == "_actualizar_panel_si_toca" for a in ast.walk(c.args[0]))]
    assert len(del_panel) == 1
    assert [k.value.id for k in del_panel[0].keywords if k.arg == "timeout"] == ["SEGUNDOS_TIMEOUT_PANEL"]
