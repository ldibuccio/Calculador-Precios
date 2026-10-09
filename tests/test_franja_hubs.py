"""La franja de arriba de Compras, Administración y Gerencia (dueño, 04/10).

UNA línea con dos botones lado a lado, Tareas y Alertas, que despliegan lo
suyo abajo, a todo el ancho. Arranca plegada y entra en una línea a 313px.
Tareas: "Sin tareas pendientes" en verde, o "Tareas pendientes (N)" en rojo,
como Alertas (dueño, 09/10); adentro la lista y "Nueva tarea". Alertas: "Sin
alertas" o "Alertas (N)". Los nombres son de EJEMPLO.
"""
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

CLAVES = {"CLAVE_ADMINISTRACION": "admin-secreta", "CLAVE_GERENCIA": "gerencia-secreta",
          "CLAVE_COMPRAS": "compras-secreta"}


def _cliente(m, *puertas):
    from fastapi.testclient import TestClient
    cliente = TestClient(m.app, base_url="https://testserver")
    for puerta in puertas:
        clave = {"administracion": "admin-secreta", "gerencia": "gerencia-secreta",
                 "compras": "compras-secreta"}[puerta]
        objeto = getattr(m, f"PUERTA_{puerta.upper()}")
        cliente.cookies.set(objeto.cookie, objeto.firma(clave))
    return cliente


def _estado_con_una_alerta():
    """La foto ENTERA, como la de producción: todas calculadas recién y en
    cero, salvo la de los vacíos. Una que falta en la foto es "sin calcular
    todavía", y eso desde el 05/10 también va al panel."""
    from datetime import datetime
    from app.main import ALERTAS, ARGENTINA
    ahora = datetime.now(ARGENTINA)
    return [{"codigo": d.codigo, "casos": 1086 if d.codigo == "vacios_para_devolver" else 0, "mas_viejo": None,
             "calculada_el": ahora, "error": None} for d in ALERTAS]


def _tareas(sector, vencida):
    return {"sector": sector, "error": None, "vencidas": 1 if vencida else 0,
            "sectores": {"gerencia": "Gerencia", "compras": "Compras", "administracion": "Administración"},
            "tareas": [{"id": 1, "titulo": "EJ Contar cajas", "detalle": None, "vencida": vencida,
                        "atrasada": False, "creada_por": "gerencia", "vence_el": date(2026, 3, 9)}]}


@pytest.mark.parametrize("sector", ["compras", "administracion", "gerencia"])
def test_la_FRANJA_de_los_tres_hubs_lista_las_ALERTAS_con_su_link_y_el_detalle(sector):
    import app.main as m
    with patch.dict(os.environ, CLAVES), \
         patch("app.main.listar_estado_alertas", return_value=_estado_con_una_alerta()), \
         patch("app.main._recuadro_de_tareas", return_value=_tareas(sector, vencida=False)):
        marcado = _cliente(m, sector).get(f"/{sector}").text.split("</style>")[-1]
    assert marcado.count("data-franja>") == 1
    assert 'data-franja-boton="alertas">Alertas (1)</button>' in marcado
    panel = marcado.split('id="franja-alertas"')[1].split("</div>")[0]
    assert panel.startswith(' data-franja-panel="alertas" hidden>')
    assert re.search(r'<a class="franja-alerta" href="/[^"]+">Hay 1.086 cajones vacíos en el galpón: hay que '
                     r'devolver</a>', panel)
    assert f'<a class="franja-ver" href="/{sector}/alertas">Ver el detalle de las alertas</a>' in panel
    # el botón grande de Alertas de antes ya no está
    assert f'<a class="boton" href="/{sector}/alertas">' not in marcado
    assert f'boton-naranja" href="/{sector}/alertas"' not in marcado


def test_la_FRANJA_a_313px_es_UNA_linea_arranca_plegada_y_abre_de_a_uno():
    """Lo que se ve lo decide el navegador: `hidden` y el color se miran con
    getComputedStyle, no leyendo el HTML (corolario 32)."""
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    import app.main as m
    from scripts.medir_layout import CHROMIUM, medir_sync
    with patch.dict(os.environ, CLAVES), \
         patch("app.main.listar_estado_alertas", return_value=_estado_con_una_alerta()), \
         patch("app.main._recuadro_de_tareas", return_value=_tareas("administracion", vencida=True)):
        respuesta = _cliente(m, "administracion").get("/administracion")
    # la identidad: el hub de verdad y no la pantalla de la clave
    assert respuesta.status_code == 200 and 'href="/administracion/stock/cotejo"' in respuesta.text
    html = respuesta.text
    medicion = medir_sync(html, ancho=313, selector_filas=".tarjeta")
    assert medicion["pares"] > 0, medicion
    assert medicion["desborde"] == 0, medicion             # con filas, es el de la página
    assert medicion["solapes"] == [], medicion

    def estado(pagina):
        return pagina.evaluate("""() => ({
          tareas: getComputedStyle(document.getElementById('franja-tareas')).display,
          alertas: getComputedStyle(document.getElementById('franja-alertas')).display,
          expandidos: [...document.querySelectorAll('[data-franja-boton]')].map(b => b.getAttribute('aria-expanded')),
        })""")

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            pagina = navegador.new_page(viewport={"width": 313, "height": 700})
            pagina.set_content(html)
            botones = pagina.locator("[data-franja-boton]")
            cajas = [botones.nth(i).bounding_box() for i in range(2)]
            # OVALADOS (dueño, 04/10): la punta llega a la mitad del alto; el
            # botón de acción del hub, el RIVAL, sigue con 8px
            puntas = pagina.evaluate("""() => ({
              franja: [...document.querySelectorAll('[data-franja-boton]')].map(b => [
                parseFloat(getComputedStyle(b).borderTopLeftRadius), b.getBoundingClientRect().height]),
              accion: getComputedStyle(document.querySelector('a.boton[href="/administracion/stock/cotejo"]'))
                .borderTopLeftRadius,
              renglones_alertas: (() => { const r = document.createRange();
                r.selectNodeContents(document.querySelector('[data-franja-boton=alertas]'));
                return new Set([...r.getClientRects()].map(c => Math.round(c.top))).size; })()})""")
            fondo_tareas = pagina.evaluate(
                "() => getComputedStyle(document.querySelector('[data-franja-boton=tareas]')).backgroundColor")
            al_llegar = estado(pagina)
            pagina.click("[data-franja-boton=tareas]")
            con_tareas = estado(pagina)
            nueva_visible = pagina.locator("#franja-tareas .tareas-nueva").is_visible()
            pagina.click("[data-franja-boton=alertas]")
            con_alertas = estado(pagina)
            pagina.click("[data-franja-boton=alertas]")
            cerrada = estado(pagina)
        finally:
            navegador.close()
    # una sola línea: los dos a la misma altura, uno al lado del otro, y de 44px
    assert cajas[0]["y"] == cajas[1]["y"] and cajas[0]["x"] + cajas[0]["width"] <= cajas[1]["x"]
    assert min(c["height"] for c in cajas) >= 44
    assert len(puntas["franja"]) == 2 and all(radio >= alto / 2 for radio, alto in puntas["franja"]), puntas
    assert puntas["accion"] == "8px", puntas
    assert puntas["renglones_alertas"] == 1, puntas            # "Alertas (1)" no se parte
    assert fondo_tareas == "rgb(220, 38, 38)"                     # una vencida: rojo
    assert al_llegar == {"tareas": "none", "alertas": "none", "expandidos": ["false", "false"]}
    assert con_tareas["tareas"] != "none" and con_tareas["alertas"] == "none"
    assert con_tareas["expandidos"] == ["true", "false"] and nueva_visible
    assert con_alertas["tareas"] == "none" and con_alertas["alertas"] != "none"
    assert cerrada == {"tareas": "none", "alertas": "none", "expandidos": ["false", "false"]}
