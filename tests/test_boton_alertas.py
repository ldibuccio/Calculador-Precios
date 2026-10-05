"""El botón de Alertas se pinta según el estado (dueño, 04/10).

En TODOS los hubs que lo tienen —la franja de Compras, Administración y
Gerencia, y el botón de Comercial—:
- con alertas: ROJO, y dice "Alertas (N)";
- sin alertas: VERDE, y dice "Sin alertas".
Y NO SE PONE VERDE si no se sabe (dueño, 05/10): una alerta que no se pudo
calcular, una sin calcular todavía, la foto vieja o la base que no contesta
también cuentan, porque son renglones del panel.
El de Tareas queda como estaba (lo cuida tests/test_tareas.py).

Auditoría, Depósito, Logística y Puesto no tienen botón de Alertas: Auditoría
ES el tablero de alertas, y los otros tres quedaron sin avisos arriba cuando
el dueño sacó la cinta corrida de todo el sistema (05/10).

El color lo decide el navegador (corolario 32): se mide con getComputedStyle.
"""
import os
import re
import sys
from datetime import datetime
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_administracion_reordenada import CLAVES, _cliente  # noqa: E402

ROJO, VERDE = "rgb(220, 38, 38)", "rgb(21, 128, 61)"
HUBS = {"/compras": "compras", "/administracion": "administracion", "/gerencia": "gerencia", "/comercial": None}
SELECTOR = {"/compras": "[data-franja-boton=alertas]", "/administracion": "[data-franja-boton=alertas]",
            "/gerencia": "[data-franja-boton=alertas]", "/comercial": 'a[href="/comercial/alertas"]'}


def _estado(casos, error=None, horas=0):
    """La foto ENTERA, como la de producción: todas calculadas hace `horas` y
    en cero, salvo UNA por hub con `casos` —vacíos para devolver en Compras,
    Administración y Gerencia; artículos incotizables en Comercial—. Con
    `error`, esas dos no se pudieron calcular."""
    from datetime import timedelta
    import app.main as m
    cuando = datetime.now(m.ARGENTINA) - timedelta(hours=horas)
    elegidas = ("vacios_para_devolver", "articulos_incotizables")
    return [{"codigo": d.codigo, "casos": casos if d.codigo in elegidas else 0, "mas_viejo": None,
             "calculada_el": cuando, "error": error if d.codigo in elegidas else None} for d in m.ALERTAS]


def _hub(url, casos, **foto):
    import app.main as m
    sector = HUBS[url]
    lectura = {"side_effect": RuntimeError("EJ la base no contesta")} if foto.pop("sin_base", False) \
        else {"return_value": _estado(casos, **foto)}
    with patch.dict(os.environ, CLAVES), patch("app.main.listar_estado_alertas", **lectura):
        cliente = _cliente(m, sector) if sector else _cliente(m)
        respuesta = cliente.get(url)
    assert respuesta.status_code == 200, url
    return respuesta.text


def _boton(url, html):
    marcado = " ".join(html.split("</style>")[-1].split())
    if url == "/comercial":
        (clase, texto), = re.findall(r'<a class="boton ([^"]+)" href="/comercial/alertas"><svg.*?</svg><span>([^<]*)</span>',
                                     marcado)
    else:
        (clase, texto), = re.findall(r'<button type="button" class="franja-boton ([^"]+)"[^>]*'
                                     r'data-franja-boton="alertas">([^<]*)</button>', marcado)
    return clase, texto


@pytest.mark.parametrize("url", list(HUBS))
def test_CON_alertas_el_boton_es_ROJO_y_dice_cuantas(url):
    # vacios_para_devolver: casos por encima del límite del galpón
    assert _boton(url, _hub(url, 1086)) == ("con-alertas", "Alertas (1)")


@pytest.mark.parametrize("url", list(HUBS))
def test_SIN_alertas_el_boton_es_VERDE_y_dice_Sin_alertas(url):
    assert _boton(url, _hub(url, 0)) == ("sin-alertas", "Sin alertas")


@pytest.mark.parametrize("url", list(HUBS))
@pytest.mark.parametrize("no_se_sabe", [{"error": "EJ no se pudo"}, {"horas": 40}, {"sin_base": True}],
                         ids=["no_se_pudo_calcular", "foto_vieja", "base_que_no_contesta"])
def test_lo_que_NO_SE_SABE_no_deja_el_boton_en_VERDE(url, no_se_sabe):
    """Cero casos, pero no se sabe: "Sin alertas" sería mentira."""
    assert _boton(url, _hub(url, 0, **no_se_sabe)) == ("con-alertas", "Alertas (1)")


def test_el_COLOR_lo_mide_el_navegador_en_los_dos_estados_y_en_los_cuatro_hubs():
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    paginas = {(url, casos): _hub(url, casos) for url in HUBS for casos in (1086, 0)}
    colores = {}
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            for (url, casos), html in paginas.items():
                pagina = navegador.new_page(viewport={"width": 313, "height": 700})
                pagina.set_content(html)
                colores[(url, casos)] = pagina.evaluate(
                    "(s) => getComputedStyle(document.querySelector(s)).backgroundColor", SELECTOR[url])
                pagina.close()
        finally:
            navegador.close()
    assert colores == {(url, casos): (ROJO if casos else VERDE) for url, casos in paginas}, colores


def test_los_hubs_SIN_boton_de_alertas_son_los_decididos():
    """Auditoría es el tablero; Depósito, Logística y Puesto tienen solo la
    cinta. Si mañana uno gana botón, este test pide decidir su color."""
    con_boton = set()
    for nombre in ("compras", "administracion", "gerencia", "comercial", "auditoria", "deposito",
                   "logistica", "puesto"):
        fuente = open(os.path.join(RAIZ, "templates", f"{nombre}.html"), encoding="utf-8").read()
        if re.search(r'href="/%s/alertas"|data-franja' % nombre, fuente) or "franja_hub.franja(" in fuente:
            con_boton.add(nombre)
    assert con_boton == {"compras", "administracion", "gerencia", "comercial"}
