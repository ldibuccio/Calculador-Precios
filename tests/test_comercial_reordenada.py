"""El reorden de Comercial (dueño, 04/10).

- Comercial: cuatro botones (Alertas, Precios, Clientes, Fichas logísticas).
  Envases se fue a Administración → Cajas → Tipos de caja y su costo: el
  precio de las cajas lo carga Administración. Su dirección vieja lleva allá
  y sus formularios viejos ya no escriben.
- Precios: de siete botones a cuatro. Modificar y Carga foto quedaron detrás
  de "Cargar precios"; los dos "Próximamente" salieron (no hacían nada). El
  07/10 se sumó un quinto, "Precios Cotizaciones".
- El estilo de Depósito: un dibujo en cada botón y un color por recuadro.
"""
import os
import re
import sys
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_administracion_reordenada import CLAVES, _cliente  # noqa: E402

_BOTON = re.compile(r'<a class="boton color-(\d)" href="([^"]*)"><svg [^>]*>.*?</svg><span>([^<]*)</span></a>', re.S)

# El de Alertas va aparte: su color es el del estado (rojo o verde), y lo
# cuida tests/test_boton_alertas.py.
COMERCIAL = [("1", "/precios", "Precios"), ("1", "/clientes", "Clientes"), ("1", "/fichas", "Fichas logísticas")]
PRECIOS = [("1", "/precios/cargar-precios", "Cargar precios"), ("1", "/precios/consultar", "Consultar Precios"),
           ("1", "/precios/vigencias", "Precios por Período"), ("1", "/negociar", "Márgenes por Artículo"),
           # Dueño, 07/10: el precio de cada ficha de un cliente nuevo.
           ("1", "/precios/cotizaciones", "Precios Cotizaciones")]
# Dueño, 07/10: Cargar precios primero; adentro, manuales y después por foto.
CARGAR_PRECIOS = [("1", "/precios/cargar", "Cargar precios manuales"),
                  ("1", "/precios/cargar-foto", "Cargar precios por foto")]

# LOS SIETE DE PRECIOS hasta el 04/10: dónde quedó cada uno.
PRECIOS_VIEJOS = {
    "/precios/cargar": "/precios/cargar-precios",
    "/precios/cargar-foto": "/precios/cargar-precios",
    "/precios/consultar": "/precios",
    "/precios/vigencias": "/precios",
    "/negociar": "/precios",
    # Los "Próximamente": sin botón, pero su dirección sigue abriendo.
    "/precios/resultado-negociacion": None,
    "/precios/generar-listado": None,
}


def _botones(html):
    return [tuple(b) for b in _BOTON.findall(html.split("</style>")[-1])]


def test_COMERCIAL_tiene_cuatro_botones_y_ya_no_Envases():
    from fastapi.testclient import TestClient
    import app.main as m
    marcado = TestClient(m.app).get("/comercial").text
    assert _botones(marcado) == COMERCIAL
    assert re.search(r'<a class="boton (con|sin)-alertas" href="/comercial/alertas">', marcado)
    assert marcado.split("</style>")[-1].count('<a class="boton ') == 4
    assert 'href="/envases"' not in marcado


def test_PRECIOS_tiene_cinco_botones_y_CARGAR_PRECIOS_las_dos_formas():
    from fastapi.testclient import TestClient
    import app.main as m
    cliente = TestClient(m.app)
    precios, cargar = cliente.get("/precios"), cliente.get("/precios/cargar-precios")
    assert precios.status_code == cargar.status_code == 200
    assert _botones(precios.text) == PRECIOS
    assert _botones(cargar.text) == CARGAR_PRECIOS
    assert "Próximamente" not in precios.text
    assert '<a class="barra-boton" href="/precios" aria-label="Volver atrás">' in cargar.text


def test_cada_forma_de_CARGAR_PRECIOS_se_titula_como_su_boton():
    """Dueño, 07/10: el botón y el título de la pantalla dicen lo mismo."""
    from fastapi.testclient import TestClient
    import app.main as m
    cliente = TestClient(m.app)
    for _, ruta, nombre in CARGAR_PRECIOS:
        with patch("app.main.listar_clientes", return_value=[{"id": 1, "nombre": "EJ Cliente"}]):
            pagina = cliente.get(ruta)
        assert pagina.status_code == 200, ruta
        assert pagina.text.count(f"<title>{nombre}</title>") == 1, ruta
        assert pagina.text.count(f'<div class="barra-titulo">{nombre}</div>') == 1, ruta

def test_NINGUN_boton_viejo_de_Precios_desaparece_y_cada_pantalla_VIEJA_abre():
    from fastapi.testclient import TestClient
    import app.main as m
    cliente = TestClient(m.app)
    for viejo, donde in PRECIOS_VIEJOS.items():
        if donde:
            assert f'href="{viejo}"' in cliente.get(donde).text.split("</style>")[-1], viejo
    for viejo in ("/precios/resultado-negociacion", "/precios/generar-listado", "/precios/cargar-precios"):
        assert cliente.get(viejo).status_code == 200, viejo


def test_ENVASES_lleva_a_TIPOS_DE_CAJA_de_Administracion_y_sus_formularios_viejos_no_escriben():
    import app.main as m
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "compras")       # cualquiera sin la clave de Administración
        vieja = cliente.get("/envases?aviso=EJ", follow_redirects=False)
        with patch("app.main.registrar_costo_envase") as registrar, patch("app.main.crear_envase") as crear:
            escrituras = [cliente.post("/envases/7/costo", data={"costo": "800"}, follow_redirects=False),
                          cliente.post("/envases/7/baja", follow_redirects=False),
                          cliente.post("/envases/nuevo", data={"nombre": "EJ Caja", "costo": "700"},
                                       follow_redirects=False)]
    assert (vieja.status_code, vieja.headers["location"]) == (301, "/administracion/cajas/tipos?aviso=EJ")
    assert all(r.status_code in (404, 405) for r in escrituras), [r.status_code for r in escrituras]
    assert not registrar.called and not crear.called


def test_a_313px_PRECIOS_y_CARGAR_PRECIOS_no_se_salen():
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright
    import app.main as m
    from scripts.medir_layout import CHROMIUM
    cliente = TestClient(m.app)
    paginas = {r: cliente.get(r) for r in ("/comercial", "/precios", "/precios/cargar-precios")}
    assert all(x.status_code == 200 for x in paginas.values())
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            medidas = {}
            for ruta, respuesta in paginas.items():
                pagina = navegador.new_page(viewport={"width": 313, "height": 700})
                pagina.set_content(respuesta.text)
                medidas[ruta] = pagina.evaluate("""() => ({
                  desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                  altos: [...document.querySelectorAll('a.boton')].map(b => Math.round(b.getBoundingClientRect().height))})""")
                pagina.close()
        finally:
            navegador.close()
    for ruta, medida in medidas.items():
        assert medida["desborde"] == 0, (ruta, medida)
        assert medida["altos"] and min(medida["altos"]) >= 44, (ruta, medida)
