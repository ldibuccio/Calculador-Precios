"""La cinta corrida de avisos se sacó de TODO el sistema (dueño, 05/10).

- Ninguna pantalla la tiene: ni los hubs con botón de Alertas (Compras,
  Administración, Gerencia, Comercial) ni Depósito, Logística, Puesto y
  Fichas, que quedan sin avisos arriba (y sin botón en su lugar).
- Lo que solo decía la cinta —no se pudo calcular, sin calcular todavía, la
  foto vieja— va adentro del panel de Alertas de la franja, y en Comercial,
  que tiene botón sin panel, arriba de la pantalla a la que lleva el botón.
- El título de la barra no se corta a mitad de palabra en el celular
  ("Administrac / ión" a 313px con candado).
"""
import os
import re
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_administracion_reordenada import CLAVES, _cliente  # noqa: E402

HUBS_CON_FRANJA = ("compras", "administracion", "gerencia")
SIN_CINTA = ("/compras", "/administracion", "/gerencia", "/comercial", "/deposito", "/logistica", "/puesto",
             "/fichas")


def _foto(horas=0, con_error=(), faltan=(), casos=None):
    """La foto ENTERA, como la de producción, calculada hace `horas`: todas en
    cero salvo `casos`; las de `con_error` no se pudieron calcular y las de
    `faltan` no están (sin calcular todavía)."""
    import app.main as m
    cuando = datetime.now(m.ARGENTINA) - timedelta(hours=horas)
    casos = casos or {}
    return [{"codigo": d.codigo, "casos": casos.get(d.codigo, 0), "mas_viejo": None, "calculada_el": cuando,
             "error": "EJ no se pudo" if d.codigo in con_error else None}
            for d in m.ALERTAS if d.codigo not in faltan]


def _get(ruta, foto=None, sector=None, sin_base=False):
    import app.main as m
    lectura = {"side_effect": RuntimeError("EJ la base no contesta")} if sin_base else {"return_value": foto}
    with patch.dict(os.environ, CLAVES), patch("app.main.listar_estado_alertas", **lectura), \
         patch("app.main.listar_clientes", return_value=[]):
        respuesta = (_cliente(m, sector) if sector else _cliente(m)).get(ruta)
    assert respuesta.status_code == 200, (ruta, respuesta.text[:300])
    return respuesta.text


def _sector(ruta):
    nombre = ruta.strip("/").split("/")[0]
    return nombre if nombre in HUBS_CON_FRANJA else None


def test_NINGUNA_plantilla_tiene_la_cinta():
    encontradas = set()
    for nombre in os.listdir(os.path.join(RAIZ, "templates")):
        fuente = open(os.path.join(RAIZ, "templates", nombre), encoding="utf-8").read()
        if re.search(r'_banner_alertas\.html|class="banner-(avisos|cinta)"|@keyframes banner-correr', fuente):
            encontradas.add(nombre)
    assert encontradas == set()
    assert not os.path.exists(os.path.join(RAIZ, "templates", "_banner_alertas.html"))


@pytest.mark.parametrize("ruta", SIN_CINTA)
def test_ninguna_pantalla_muestra_la_cinta_ni_con_TODO_lo_que_la_hacia_aparecer(ruta):
    """Una alerta con casos de CADA alerta del registro, una con error, una
    sin calcular y la foto vieja: lo que antes llenaba la cinta."""
    import app.main as m
    todas = {d.codigo: 3 for d in m.ALERTAS}
    html = _get(ruta, _foto(horas=40, con_error=("compras_sin_precio",), faltan=("cajas_a_reponer",),
                            casos=todas), _sector(ruta))
    cuerpo = html.split("</style>")[-1]
    assert "banner-cinta" not in html and "banner-avisos" not in html
    assert '<span class="copia" aria-hidden="true">' not in cuerpo


@pytest.mark.parametrize("ruta", ["/deposito", "/logistica", "/puesto"])
def test_DEPOSITO_LOGISTICA_y_PUESTO_quedan_SIN_avisos_arriba_y_sin_boton(ruta):
    import app.main as m
    sector = ruta.strip("/")
    suyas = [d for d in m.ALERTAS if sector in d.modulos]
    assert suyas, sector                                 # el rival: tienen alertas propias
    cuerpo = _get(ruta, _foto(horas=40, con_error=(suyas[0].codigo,), casos={d.codigo: 3 for d in suyas}))
    cuerpo = cuerpo.split("</style>")[-1]
    assert "data-franja" not in cuerpo
    assert f'href="/{sector}/alertas"' not in cuerpo
    assert "No se pudo calcular" not in cuerpo and "Ojo: estas alertas" not in cuerpo


@pytest.mark.parametrize("sector", HUBS_CON_FRANJA)
def test_el_PANEL_de_la_franja_dice_lo_que_NO_SE_SABE_despues_de_las_alertas_con_casos(sector):
    import app.main as m
    suya_con_casos = next(d for d in m.ALERTAS if sector in d.modulos)
    otras = [d for d in m.ALERTAS if sector in d.modulos and d is not suya_con_casos]
    con_error, sin_calcular = otras[0], otras[1]
    html = _get(f"/{sector}", _foto(horas=40, con_error=(con_error.codigo,), faltan=(sin_calcular.codigo,),
                                    casos={suya_con_casos.codigo: 3}), sector)
    marcado = " ".join(html.split("</style>")[-1].split())
    panel = marcado.split('id="franja-alertas"')[1].split('class="franja-ver"')[0]
    renglones = re.findall(r'<a class="franja-alerta( franja-problema)?" href="([^"]+)">([^<]*)</a>', panel)
    # la de casos primero, con SU link (que es por sector); después lo que no se sabe, a Auditoría
    assert [bool(p) for p, _, _ in renglones] == [False, True, True, True]
    assert renglones[0][1] != "/auditoria" and {url for _, url, _ in renglones[1:]} == {"/auditoria"}
    textos = [t for _, _, t in renglones[1:]]
    assert textos[0] == f"No se pudo calcular: {con_error.titulo}"
    assert textos[1] == f"Sin calcular todavía: {sin_calcular.titulo}"
    assert re.fullmatch(r"Ojo: estas alertas se calcularon .+ y no se actualizaron desde entonces", textos[2])
    assert 'data-franja-boton="alertas">Alertas (4)</button>' in marcado


@pytest.mark.parametrize("sector", HUBS_CON_FRANJA)
def test_si_la_base_no_contesta_el_panel_lo_dice(sector):
    marcado = _get(f"/{sector}", sector=sector, sin_base=True).split("</style>")[-1]
    panel = marcado.split('id="franja-alertas"')[1]
    assert '<a class="franja-alerta franja-problema" href="/auditoria">No se pudieron leer las alertas</a>' in panel
    assert "No hay alertas con casos." not in panel


def test_en_COMERCIAL_lo_que_no_se_sabe_aparece_al_tocar_el_boton():
    """El botón no tiene panel: lleva a su pantalla de Alertas, y ahí va arriba."""
    hub = _get("/comercial", _foto(con_error=("articulos_incotizables",)))
    assert re.search(r'<a class="boton con-alertas" href="/comercial/alertas"><svg.*?</svg><span>Alertas \(1\)</span>',
                     hub, re.S)
    import app.main as m
    titulo = next(d for d in m.ALERTAS if d.codigo == "articulos_incotizables").titulo
    with patch("app.main._bloques_de_alertas", return_value=[]):
        pantalla = _get("/comercial/alertas", _foto(con_error=("articulos_incotizables",)))
    cuerpo = pantalla.split("</style>")[-1]
    aviso = f'<a class="problema" href="/auditoria">No se pudo calcular: {titulo}</a>'
    assert cuerpo.count(aviso) == 1
    assert cuerpo.index(aviso) < cuerpo.index('action="/comercial/alertas/recalcular"')
    assert "Todo en orden" not in cuerpo                 # no se sabe: no está todo en orden
    # y sin nada que no se sepa, no hay ninguno
    with patch("app.main._bloques_de_alertas", return_value=[]):
        limpia = _get("/comercial/alertas", _foto()).split("</style>")[-1]
    assert 'class="problema"' not in limpia
    assert "✓ Todo en orden" in limpia


def test_a_313px_el_TITULO_de_la_barra_no_se_corta_a_mitad_de_palabra():
    """Cada palabra del título queda en UN renglón (un rectángulo). El rival:
    un nombre sin espacios, que no entra de ninguna forma, se sigue cortando
    para no estirar la página."""
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    paginas = {r: _get(r, _foto(), _sector(r)) for r in ("/administracion", "/gerencia", "/compras")}
    assert 'aria-label="Bloquear Administración"' in paginas["/administracion"]   # con candado
    sin_espacios = paginas["/administracion"].replace('<div class="barra-titulo">Administración</div>',
                                                      '<div class="barra-titulo">EJDistribuidoraFrutihorticola</div>')
    medir = """() => { const t = document.querySelector('.barra-titulo'); const texto = t.firstChild;
      const palabras = []; let i = 0;
      for (const p of texto.textContent.split(' ')) { const r = document.createRange();
        r.setStart(texto, i); r.setEnd(texto, i + p.length); i += p.length + 1;
        palabras.push([p, new Set([...r.getClientRects()].map(c => Math.round(c.top))).size]); }
      return {palabras, tam: parseFloat(getComputedStyle(t).fontSize),
              desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            medidas = {}
            for nombre, html in list(paginas.items()) + [("sin_espacios", sin_espacios)]:
                pagina = navegador.new_page(viewport={"width": 313, "height": 600})
                pagina.set_content(html)
                medidas[nombre] = pagina.evaluate(medir)
                pagina.close()
        finally:
            navegador.close()
    for ruta in paginas:
        assert all(renglones == 1 for _, renglones in medidas[ruta]["palabras"]), (ruta, medidas[ruta])
        assert medidas[ruta]["tam"] >= 12 and medidas[ruta]["desborde"] == 0, (ruta, medidas[ruta])
    assert medidas["sin_espacios"]["palabras"][0][1] > 1 and medidas["sin_espacios"]["desborde"] == 0, medidas
