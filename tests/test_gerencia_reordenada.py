"""El reorden de Gerencia y el fin de Sistema (dueño, 04/10).

- Gerencia: diez botones en tres grupos (Mirar, Corregir, Mantenimiento); once
  desde el 05/10, con la contraseña especial de "Con fecha anterior"; doce
  desde el 08/10, con el Panel de control primero en Mirar.
  Rentabilidad (De pedidos · Real), Pérdidas (Mercadería · Cajas) y
  Facturación y cobranzas (Remitos y facturas · Vales · Segunda) llevan
  pestañas. Las de Facturación y cobranzas salen SOLO entrando por Gerencia:
  en Administración son tres botones.
- Sistema desaparece: la Casilla de pedidos se fue ENTERA a Administración →
  Pedidos, con la clave de Administración y sus tres alertas (dueño, 04/10:
  "Todo a Administración"). Las direcciones viejas llevan allá.
- El circuito del mail (revisar y confirmar) es de Depósito, sin clave: sus
  errores vuelven a Pedidos de Depósito y no a la Casilla.
"""
import os
import re
import sys
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_administracion_reordenada import CLAVES, _cliente, _grupos_con_color  # noqa: E402
from tests.test_segunda_negativa import base_real, galpon  # noqa: E402,F401

GRUPOS_DECIDIDOS = {
    "Mirar": [("1", "/gerencia/panel", "Panel de control"),
              ("1", "/gerencia/rentabilidad", "Rentabilidad"), ("1", "/gerencia/perdidas", "Pérdidas"),
              ("1", "/gerencia/costos-fijos", "Costos fijos"),
              ("1", "/gerencia/facturacion", "Facturación y cobranzas")],
    "Corregir": [("2", "/gerencia/compras/ingreso-retroactivo", "Ingreso con fecha anterior"),
                 # La contraseña especial de "Con fecha anterior" de
                 # Administración (dueño, 05/10): la fija Gerencia.
                 ("2", "/gerencia/clave-retroactivo", "Contraseña de fecha anterior"),
                 ("2", "/gerencia/proveedores/juntar", "Juntar dos proveedores"),
                 ("2", "/gerencia/stock/inicial", "Stock inicial del corte")],
    "Mantenimiento": [("3", "/gerencia/tareas", "Tareas"), ("3", "/gerencia/backups", "Backups"),
                      ("3", "/gerencia/fotos", "Fotos y espacio")],
}

# LOS BOTONES QUE TENÍA EL HUB hasta el 04/10 (sin Alertas, que está en la
# franja) y dónde quedó cada uno que salió.
BOTONES_VIEJOS = (
    "/gerencia/tareas", "/gerencia/backups", "/gerencia/rentabilidad", "/gerencia/rentabilidad-real",
    "/gerencia/cajas-perdidas", "/gerencia/perdidas", "/gerencia/vales", "/gerencia/cobranzas-segunda",
    "/gerencia/facturacion", "/gerencia/costos-fijos", "/gerencia/compras/ingreso-retroactivo",
    "/gerencia/proveedores/juntar", "/gerencia/fotos", "/gerencia/stock/inicial",
)
SE_MUDARON = {
    "/gerencia/rentabilidad-real": "/gerencia/rentabilidad",
    "/gerencia/cajas-perdidas": "/gerencia/perdidas",
    "/gerencia/vales": "/gerencia/facturacion",
    "/gerencia/cobranzas-segunda": "/gerencia/facturacion",
}

PESTANAS = {
    "/gerencia/rentabilidad": ("Rentabilidad", ["/gerencia/rentabilidad", "/gerencia/rentabilidad-real"]),
    "/gerencia/rentabilidad-real": ("Rentabilidad", ["/gerencia/rentabilidad", "/gerencia/rentabilidad-real"]),
    "/gerencia/perdidas": ("Pérdidas", ["/gerencia/perdidas", "/gerencia/cajas-perdidas"]),
    "/gerencia/cajas-perdidas": ("Pérdidas", ["/gerencia/perdidas", "/gerencia/cajas-perdidas"]),
    "/gerencia/facturacion": ("Facturación y cobranzas",
                              ["/gerencia/facturacion", "/gerencia/vales", "/gerencia/cobranzas-segunda"]),
    "/gerencia/vales": ("Facturación y cobranzas",
                        ["/gerencia/facturacion", "/gerencia/vales", "/gerencia/cobranzas-segunda"]),
    "/gerencia/cobranzas-segunda": ("Facturación y cobranzas",
                                    ["/gerencia/facturacion", "/gerencia/vales", "/gerencia/cobranzas-segunda"]),
}

ALERTAS_DE_LA_CASILLA = ("mails_sin_confirmar", "mails_leidos_con_ia", "casilla_sin_revisar")


def test_el_hub_de_GERENCIA_tiene_DIEZ_botones_en_tres_grupos_con_su_color():
    import app.main as m
    with patch.dict(os.environ, CLAVES):
        marcado = _cliente(m, "gerencia").get("/gerencia").text.split("</style>")[-1]
    assert {t: [tuple(b) for b in botones] for t, botones in _grupos_con_color(marcado).items()} == GRUPOS_DECIDIDOS
    assert marcado.count('<a class="boton ') == 12


def test_NINGUN_boton_viejo_de_Gerencia_desaparece_y_cada_pantalla_VIEJA_abre(galpon):
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "gerencia")
        hub = cliente.get("/gerencia").text.split("</style>")[-1]
        en_el_hub = set(re.findall(r'href="(/[^"?#]*)"', hub))
        donde = {v: cliente.get(SE_MUDARON[v]).text.split("</style>")[-1].count(f'href="{v}"')
                 for v in BOTONES_VIEJOS if v not in en_el_hub}
        abren = {r: cliente.get(r).status_code for r in BOTONES_VIEJOS}
    assert set(donde) == set(SE_MUDARON) and all(n >= 1 for n in donde.values()), donde
    assert abren == {r: 200 for r in BOTONES_VIEJOS}, {r: c for r, c in abren.items() if c != 200}


def test_las_PESTANAS_de_Gerencia_y_las_de_cobranzas_SOLO_entrando_por_Gerencia(galpon):
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        gerencia = _cliente(m, "gerencia")
        paginas = {ruta: gerencia.get(ruta) for ruta in PESTANAS}
        admin = _cliente(m, "administracion")
        por_admin = {r: admin.get(r) for r in ("/administracion/facturacion", "/administracion/vales",
                                                "/administracion/cobranzas-segunda")}
    for ruta, respuesta in paginas.items():
        assert respuesta.status_code == 200, ruta
        etiqueta, hrefs = PESTANAS[ruta]
        marcado = respuesta.text.split("</style>")[-1]
        (nav,) = re.findall(r'<nav class="pestanas" aria-label="%s">(.*?)</nav>' % etiqueta, marcado, re.S)
        links = re.findall(r'<a href="([^"]+)"( aria-current="page")?>', nav)
        assert [h for h, _a in links] == hrefs, ruta
        assert [h for h, a in links if a] == [ruta], ruta
    for ruta, respuesta in por_admin.items():
        assert respuesta.status_code == 200, ruta
        assert '<nav class="pestanas"' not in respuesta.text.split("</style>")[-1], ruta


def test_SISTEMA_desaparece_y_la_CASILLA_vive_en_Administracion_con_su_clave():
    import app.main as m
    with patch.dict(os.environ, CLAVES):
        sin_clave = _cliente(m, "compras")
        viejas = {r: sin_clave.get(r, follow_redirects=False) for r in
                  ("/sistema", "/sistema/casilla-pedidos", "/sistema/casilla-pedidos?mensaje=EJ")}
        pared = sin_clave.get("/administracion/casilla-pedidos")
        hub = _cliente(m, "administracion").get("/administracion").text.split("</style>")[-1]
        inicio = sin_clave.get("/inicio").text
    assert {r: (x.status_code, x.headers["location"]) for r, x in viejas.items()} == {
        "/sistema": (301, "/administracion/casilla-pedidos"),
        "/sistema/casilla-pedidos": (301, "/administracion/casilla-pedidos"),
        "/sistema/casilla-pedidos?mensaje=EJ": (301, "/administracion/casilla-pedidos?mensaje=EJ"),
    }
    assert pared.status_code == 401                       # la de Compras no abre Administración
    pedidos = hub.split("<h2>Pedidos</h2>")[1].split("</div>")[0]
    assert re.search(r'<a class="boton color-2" href="/administracion/casilla-pedidos">.*?'
                     r'<span>Casilla de pedidos</span></a>', pedidos, re.S)
    assert 'href="/sistema"' not in inicio
    # y nada del sistema sigue mandando a /sistema
    plantillas = "".join(open(os.path.join(RAIZ, "templates", n), encoding="utf-8").read()
                         for n in os.listdir(os.path.join(RAIZ, "templates")) if n.endswith(".html"))
    assert re.findall(r'(?:href|action)="/sistema[/"]', plantillas) == []


def test_la_pantalla_de_la_CASILLA_es_de_Administracion_y_sus_formularios_tambien(galpon):
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        respuesta = _cliente(m, "administracion").get("/administracion/casilla-pedidos")
    assert respuesta.status_code == 200
    assert '<a class="barra-boton" href="/administracion" aria-label="Volver atrás">' in respuesta.text
    marcado = respuesta.text.split("</style>")[-1]
    acciones = set(re.findall(r'action="([^"]+)"', marcado))
    assert acciones and all(a.startswith("/administracion/casilla-pedidos/") for a in acciones), acciones
    assert "/sistema" not in marcado


def test_las_TRES_ALERTAS_de_la_casilla_son_de_Administracion():
    import app.main as m
    alertas = {a.codigo: a for a in m.ALERTAS if a.codigo in ALERTAS_DE_LA_CASILLA}
    assert set(alertas) == set(ALERTAS_DE_LA_CASILLA)
    assert {c: (a.modulos, a.url) for c, a in alertas.items()} == {
        c: (("administracion",), "/administracion/casilla-pedidos") for c in ALERTAS_DE_LA_CASILLA}


def test_el_MAIL_que_ya_se_proceso_vuelve_a_PEDIDOS_DE_DEPOSITO_y_no_a_la_casilla():
    """El circuito del mail es de Depósito, sin clave: mandarlo a la Casilla
    sería una pared desde el 04/10 (corolario 56)."""
    from fastapi.testclient import TestClient
    import app.main as m
    cliente = TestClient(m.app, base_url="https://testserver")
    with patch("app.main.obtener_mail_pedido", return_value={"id": 9, "estado": "confirmado"}):
        respuesta = cliente.get("/deposito/pedido/mails/9/revisar", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/deposito/pedido?aviso=")
    revision = open(os.path.join(RAIZ, "templates", "deposito_pedido_revision.html"), encoding="utf-8").read()
    # Sin `volver` (dueño, 05/10: si vino de una lista, vuelve a ESA), el
    # defecto sigue siendo Pedidos de Depósito y nunca la Casilla.
    assert '{% set barra_atras = (volver or "/deposito/pedido") if mail else' in revision
    assert "<a class=\"volver\" href=\"{{ volver or '/deposito/pedido' }}\">" in revision
    assert "Volver a Pedidos (sin guardar)" in revision


def test_a_313px_el_hub_de_GERENCIA_y_las_pestanas_de_COBRANZAS_no_se_salen(galpon):
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "gerencia")
        paginas = {"hub": cliente.get("/gerencia"), "vales": cliente.get("/gerencia/vales")}
    assert all(r.status_code == 200 for r in paginas.values())
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            medidas = {}
            for nombre, respuesta in paginas.items():
                pagina = navegador.new_page(viewport={"width": 313, "height": 700})
                pagina.set_content(respuesta.text)
                medidas[nombre] = pagina.evaluate("""() => ({
                  desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                  botones: [...document.querySelectorAll('a.boton')].length,
                  pestanas: [...document.querySelectorAll('.pestanas a')].map(a => ({
                    alto: Math.round(a.getBoundingClientRect().height), desborda: a.scrollWidth > a.clientWidth}))})""")
                pagina.close()
        finally:
            navegador.close()
    assert medidas["hub"]["desborde"] == 0 and medidas["hub"]["botones"] == 12, medidas["hub"]
    assert medidas["vales"]["desborde"] == 0 and len(medidas["vales"]["pestanas"]) == 3
    assert all(p["alto"] == 44 and not p["desborda"] for p in medidas["vales"]["pestanas"]), medidas["vales"]
