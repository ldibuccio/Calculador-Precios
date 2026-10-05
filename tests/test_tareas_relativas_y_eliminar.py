"""Tareas, segunda vuelta (dueño, 05/10), contra Postgres.

- "Las repetitivas desde los sectores no funcionan": cada forma de repetir
  se carga DESDE EL FORMULARIO DE VERDAD, en un navegador, desde cada sector.
  La mensual va con casillas: el teclado numérico del iPhone no tiene coma.
- Dos formas de repetir: a fecha fija (cada X días, semanal, mensual con
  varios días, ANUAL) o RELATIVA: vuelve a salir X días después de hecha.
- Se puede ELIMINAR una tarea (el sector las que cargó, Gerencia todas); lo
  eliminado queda en el registro de Gerencia.
- Una tarea es pendiente RECIÉN el día de su vencimiento; antes, programada.
- La pantalla de Tareas del sector: para hacer, programadas y hechas.
Los nombres son de EJEMPLO.
"""
import os
import re
import sys
from datetime import date, timedelta
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_tareas import LUNES, _cliente, _ocurrencias, base  # noqa: E402,F401  (fixture)


# --- el formulario de verdad, en un navegador ----------------------------------

def _navegador_contra(cliente):
    """Un Chromium cuyos pedidos los contesta el cliente de pruebas: el
    formulario lo arma y lo manda el navegador, tal cual lo haría el celular."""
    pytest.importorskip("playwright", reason="lo que se manda lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    def contestar(ruta):
        pedido = ruta.request
        camino = pedido.url.split("://testserver", 1)[1]
        respuesta = cliente.request(pedido.method, camino, content=pedido.post_data_buffer,
                                    headers={"content-type": pedido.headers.get("content-type", "")},
                                    follow_redirects=True)
        # La redirección la sigue el cliente: Chromium no sigue un 303 contestado a mano.
        ruta.fulfill(status=respuesta.status_code, body=respuesta.content,
                     headers={"content-type": respuesta.headers.get("content-type", "text/html")})
    pw = sync_playwright().start()
    navegador = pw.chromium.launch(executable_path=CHROMIUM)
    pagina = navegador.new_page(viewport={"width": 390, "height": 800})
    pagina.route("https://testserver/**", contestar)
    return pw, navegador, pagina


CARGAS = [
    ("cada_dias", {"input[name=cada_dias]": "3"}),
    ("semanal", {"select[name=dia_semana]": "2"}),
    ("mensual", {"checkbox": ["1", "15"]}),
    ("anual", {"input[name=anual_dia]": "29", "select[name=anual_mes]": "2"}),
    ("despues_de_hecha", {"input[name=dias_despues]": "15"}),
    ("una_vez", {"input[name=vence_el]": "2026-03-20"}),
]


@pytest.mark.parametrize("sector", ["compras", "administracion", "gerencia"])
def test_CADA_FORMA_de_repetir_se_carga_desde_el_FORMULARIO_del_sector(base, monkeypatch, sector):
    pytest.importorskip("playwright", reason="lo que se manda lo decide el navegador")
    d, sql = base
    cliente = _cliente(monkeypatch, sector)
    pw, navegador, pagina = _navegador_contra(cliente)
    try:
        with patch("app.main._hoy_argentina", return_value=LUNES):
            for tipo, campos in CARGAS:
                pagina.goto(f"https://testserver/{sector}/tareas#nueva")
                assert pagina.evaluate("() => document.getElementById('nueva').open") is True
                if sector == "gerencia":
                    pagina.select_option("select[name=sector]", "gerencia")
                pagina.fill("input[name=titulo]", f"EJ {tipo}")
                pagina.select_option("#tipo-nueva", tipo)
                for selector, valor in campos.items():
                    if selector == "checkbox":
                        for dia in valor:
                            pagina.check(f"input[name=dias_mes][value='{dia}']")
                    elif selector.startswith("select"):
                        pagina.select_option(selector, valor)
                    else:
                        pagina.fill(selector, valor)
                with pagina.expect_navigation():
                    pagina.click("button:has-text('Crear tarea')")
                texto = pagina.inner_text("body")
                assert "Tarea creada." in texto, (tipo, pagina.url, texto[:800])
    finally:
        navegador.close()
        pw.stop()
    filas = sql("SELECT tipo, cada_dias, dia_semana, dias_mes, anual_dia, anual_mes, vence_el, creada_por, sector "
                "FROM tareas ORDER BY id")
    assert filas == [
        ("cada_dias", 3, None, None, None, None, None, sector, sector),
        ("semanal", None, 2, None, None, None, None, sector, sector),
        ("mensual", None, None, [1, 15], None, None, None, sector, sector),
        ("anual", None, None, None, 29, 2, None, sector, sector),
        ("despues_de_hecha", 15, None, None, None, None, None, sector, sector),
        ("una_vez", None, None, None, None, None, date(2026, 3, 20), sector, sector),
    ]


# --- las reglas ------------------------------------------------------------------

def test_la_ANUAL_sale_una_vez_por_año_y_el_29_de_febrero_cae_el_28():
    from core.tareas import fechas_que_tocan, texto_de_la_regla
    tarea = {"tipo": "anual", "anual_dia": 29, "anual_mes": 2, "desde": date(2026, 1, 1)}
    assert fechas_que_tocan(tarea, date(2025, 12, 31), date(2028, 12, 31)) == [
        date(2026, 2, 28), date(2027, 2, 28), date(2028, 2, 29)]
    assert texto_de_la_regla(tarea) == "todos los años, el 29 de febrero"


def test_la_RELATIVA_vuelve_a_salir_X_dias_DESPUES_DE_HECHA_y_no_por_calendario(base):
    d, sql = base
    tid = d.crear_tarea(creada_por="compras", sector="compras", titulo="EJ Limpiar la cámara", detalle=None,
                        tipo="despues_de_hecha", cada_dias=5, desde=LUNES, hoy=LUNES)
    (o,) = d.tareas_pendientes_del_sector("compras", LUNES)
    # sin hacer, pasan los días y NO sale otra: no tiene calendario
    assert len(d.tareas_pendientes_del_sector("compras", LUNES + timedelta(days=20))) == 1
    hecha = LUNES + timedelta(days=2)
    d.marcar_tarea_hecha(o["id"], sector="compras", nota=None, hoy=hecha)
    siguiente = hecha + timedelta(days=5)
    assert d.tareas_pendientes_del_sector("compras", siguiente - timedelta(days=1)) == []      # programada
    (nueva,) = d.tareas_pendientes_del_sector("compras", siguiente)
    assert nueva["vence_el"] == siguiente and nueva["tarea_id"] == tid
    assert _ocurrencias(sql, tid) == [(LUNES, "hecha", False, None), (siguiente, "pendiente", False, None)]


def test_una_FIJA_no_pasa_a_RELATIVA_al_editarla(base):
    d, _ = base
    tid = d.crear_tarea(creada_por="compras", sector="compras", titulo="EJ", detalle=None, tipo="cada_dias",
                        cada_dias=3, desde=LUNES, hoy=LUNES)
    with pytest.raises(ValueError, match="eliminala y cargala de nuevo"):
        d.editar_tarea_repetitiva(tid, quien="compras", titulo="EJ", detalle=None, tipo="despues_de_hecha",
                                  cada_dias=3, dia_semana=None, dias_mes=None)
    d.editar_tarea_repetitiva(tid, quien="compras", titulo="EJ", detalle=None, tipo="anual", cada_dias=None,
                              dia_semana=None, dias_mes=None, anual_dia=1, anual_mes=5)


def test_ELIMINAR_el_sector_las_suyas_Gerencia_todas_y_queda_en_el_REGISTRO(base):
    d, sql = base
    propia = d.crear_tarea(creada_por="compras", sector="compras", titulo="EJ Propia", detalle=None, tipo="una_vez",
                           vence_el=LUNES + timedelta(days=4), hoy=LUNES)
    de_gerencia = d.crear_tarea(creada_por="gerencia", sector="compras", titulo="EJ De Gerencia", detalle=None,
                                tipo="semanal", dia_semana=0, desde=LUNES, hoy=LUNES)
    d.tareas_pendientes_del_sector("compras", LUNES)                     # sale la semanal de hoy
    with pytest.raises(ValueError, match="no se puede eliminar"):
        d.eliminar_tarea(de_gerencia, quien="compras")
    d.eliminar_tarea(propia, quien="compras")
    d.eliminar_tarea(de_gerencia, quien="gerencia")
    with pytest.raises(ValueError, match="no se puede eliminar"):
        d.eliminar_tarea(propia, quien="compras")                       # ya está eliminada
    assert sql("SELECT titulo, estado, eliminada_por FROM tareas ORDER BY id") == [
        ("EJ Propia", "baja", "compras"), ("EJ De Gerencia", "baja", "gerencia")]
    assert d.tareas_pendientes_del_sector("compras", LUNES + timedelta(days=30)) == []      # ni sale más
    registro = d.listar_ocurrencias(sector=None, desde=None, hasta=None, estado="eliminada", hoy=LUNES)
    assert {(o["titulo"], o["eliminada_por"]) for o in registro} == {("EJ Propia", "compras"),
                                                                     ("EJ De Gerencia", "gerencia")}


def test_lo_HECHO_no_cambia_al_eliminar(base):
    d, sql = base
    tid = d.crear_tarea(creada_por="compras", sector="compras", titulo="EJ", detalle=None, tipo="una_vez",
                        vence_el=LUNES, hoy=LUNES)
    (o,) = d.tareas_pendientes_del_sector("compras", LUNES)
    d.marcar_tarea_hecha(o["id"], sector="compras", nota=None, hoy=LUNES)
    d.eliminar_tarea(tid, quien="compras")
    assert sql("SELECT estado FROM tareas_ocurrencias") == [("hecha",)]


# --- las pantallas ----------------------------------------------------------------

def test_la_PANTALLA_del_sector_tiene_PARA_HACER_PROGRAMADAS_y_HECHAS_y_ELIMINAR_solo_lo_suyo(base, monkeypatch):
    d, _ = base
    hoy_ = d.crear_tarea(creada_por="compras", sector="compras", titulo="EJ Para hoy", detalle=None,
                         tipo="una_vez", vence_el=LUNES, hoy=LUNES)
    d.crear_tarea(creada_por="gerencia", sector="compras", titulo="EJ Programada de Gerencia", detalle=None,
                  tipo="una_vez", vence_el=LUNES + timedelta(days=9), hoy=LUNES)
    d.crear_tarea(creada_por="compras", sector="compras", titulo="EJ Hecha", detalle=None, tipo="una_vez",
                  vence_el=LUNES, hoy=LUNES)
    d.crear_tarea(creada_por="administracion", sector="administracion", titulo="EJ RIVAL de otro sector",
                  detalle=None, tipo="una_vez", vence_el=LUNES, hoy=LUNES)
    hecha = next(o for o in d.tareas_pendientes_del_sector("compras", LUNES) if o["titulo"] == "EJ Hecha")
    d.marcar_tarea_hecha(hecha["id"], sector="compras", nota="EJ listo", hoy=LUNES)
    with patch("app.main._hoy_argentina", return_value=LUNES), \
         patch("app.db._hoy_en_argentina", return_value=LUNES):
        pagina = _cliente(monkeypatch, "compras").get("/compras/tareas").text.split("</style>")[-1]
        hub = _cliente(monkeypatch, "compras").get("/compras").text.split("</style>")[-1]

    def lista(nombre):
        return pagina.split(f'data-lista="{nombre}"')[1].split('<div class="tarjeta"')[0]
    para_hacer, programadas, hechas = lista("Para hacer"), lista("Programadas"), lista("Hechas en los últimos 30 días")
    assert "EJ Para hoy" in para_hacer and "EJ Programada" not in para_hacer
    assert "EJ Programada de Gerencia" in programadas and "sale el 11/03/2026" in programadas
    assert "EJ Hecha" in hechas and "«EJ listo»" in hechas
    assert "EJ RIVAL" not in pagina
    # eliminar: la suya sí, la de Gerencia no
    assert para_hacer.count(f'action="/compras/tareas/{hoy_}/eliminar"') == 1
    assert "/eliminar" not in programadas
    # el recuadro del hub: solo lo de hoy
    panel = hub.split('id="franja-tareas"')[1].split('id="franja-alertas"')[0]
    assert "EJ Para hoy" in panel and "EJ Programada" not in panel


def test_ELIMINAR_desde_la_pantalla_y_lo_ve_el_REGISTRO_de_Gerencia(base, monkeypatch):
    d, sql = base
    tid = d.crear_tarea(creada_por="compras", sector="compras", titulo="EJ A eliminar", detalle=None,
                        tipo="una_vez", vence_el=LUNES, hoy=LUNES)
    respuesta = _cliente(monkeypatch, "compras").post(f"/compras/tareas/{tid}/eliminar", follow_redirects=False)
    assert respuesta.status_code == 303 and "Tarea+eliminada" in respuesta.headers["location"]
    with patch("app.main._hoy_argentina", return_value=LUNES):
        registro = _cliente(monkeypatch, "gerencia").get("/gerencia/tareas?estado=eliminada").text.split("</style>")[-1]
    assert "EJ A eliminar" in registro and re.search(r"Tarea eliminada el [^<]+ por Compras", registro)
