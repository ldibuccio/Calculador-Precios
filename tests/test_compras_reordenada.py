"""El reorden de Compras (dueño, 04/10): de 14 botones a 7, en tres grupos.

- Cargar compra: las cuatro formas (a mano, una foto, varias fotos, listado)
  en una pantalla propia.
- Buscar compras con pestañas Todas · Sin precio.
- Qué comprar hoy con pestañas 1. Lo que pide cada cliente · 2. Qué comprar hoy.
- Analizar artículo con pestañas Qué pasa si · Objetivo de compra.
- Cajas se fue a Administración: sus direcciones viejas llevan allá, y la
  alerta de pocas cajas de Compras lleva a las Alertas de Compras.

Ningún botón desaparece del sistema y cada pantalla vieja sigue abriendo o
lleva a la nueva. Contra Postgres donde lo que se afirma sale de una consulta.
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
    "Cargar": [("1", "/compras/cargar-compra", "Cargar compra")],
    "Operaciones": [("2", "/compras/buscar", "Buscar compras"), ("2", "/compras/que-comprar", "Qué comprar hoy"),
                    ("2", "/compras/analizar", "Analizar artículo"), ("2", "/compras/disponibles", "Disponibles")],
    "Catálogo": [("3", "/compras/articulos", "Artículos"), ("3", "/compras/proveedores", "Proveedores")],
}

# LOS 14 BOTONES QUE TENÍA EL HUB hasta el 04/10 (más Alertas, que ya está en
# la franja) y dónde quedó cada uno que salió: (pantalla, lo que lo lleva).
BOTONES_VIEJOS = (
    "/compras/nueva/manual", "/compras/nueva/foto-una", "/compras/nueva/fotos", "/compras/nueva/listado",
    "/compras/buscar", "/compras/analizar", "/compras/objetivo", "/compras/carga", "/compras/que-comprar",
    "/compras/pendientes", "/compras/disponibles", "/compras/cajas", "/compras/articulos", "/compras/proveedores",
)
SE_MUDARON = {
    "/compras/nueva/manual": "/compras/cargar-compra",
    "/compras/nueva/foto-una": "/compras/cargar-compra",
    "/compras/nueva/fotos": "/compras/cargar-compra",
    "/compras/nueva/listado": "/compras/cargar-compra",
    "/compras/pendientes": "/compras/buscar",
    "/compras/objetivo": "/compras/analizar",
    "/compras/carga": "/compras/que-comprar",
}
# Cajas no se muda adentro de Compras: se fue a Administración (dueño, 04/10).
SE_FUERON = {"/compras/cajas": "/administracion/cajas"}

PESTANAS = {
    "/compras/buscar": ("Buscar compras", ["/compras/buscar", "/compras/pendientes"]),
    "/compras/pendientes": ("Buscar compras", ["/compras/buscar", "/compras/pendientes"]),
    "/compras/carga": ("Qué comprar hoy", ["/compras/carga", "/compras/que-comprar"]),
    "/compras/que-comprar": ("Qué comprar hoy", ["/compras/carga", "/compras/que-comprar"]),
    "/compras/analizar": ("Analizar artículo", ["/compras/analizar", "/compras/objetivo"]),
    "/compras/objetivo": ("Analizar artículo", ["/compras/analizar", "/compras/objetivo"]),
}


def test_el_hub_de_COMPRAS_tiene_SIETE_botones_en_tres_grupos_con_su_color():
    import app.main as m
    with patch.dict(os.environ, CLAVES):
        marcado = _cliente(m, "compras").get("/compras").text.split("</style>")[-1]
    assert {t: [tuple(b) for b in botones] for t, botones in _grupos_con_color(marcado).items()} == GRUPOS_DECIDIDOS
    assert marcado.count('<a class="boton ') == 7
    assert 'href="/compras/cajas"' not in marcado


def test_NINGUN_boton_viejo_de_Compras_desaparece_y_cada_pantalla_VIEJA_abre_o_lleva_a_la_nueva(galpon):
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "compras", "administracion")
        hub = cliente.get("/compras").text.split("</style>")[-1]
        en_el_hub = set(re.findall(r'href="(/[^"?#]*)"', hub))
        donde = {viejo: cliente.get(SE_MUDARON[viejo]).text.split("</style>")[-1].count(f'href="{viejo}"')
                 for viejo in BOTONES_VIEJOS if viejo not in en_el_hub and viejo in SE_MUDARON}
        sueltos = {v for v in BOTONES_VIEJOS if v not in en_el_hub and v not in SE_MUDARON}
        abren = {r: cliente.get(r, follow_redirects=False) for r in BOTONES_VIEJOS + ("/compras/cargar-compra",)}
    assert set(donde) == set(SE_MUDARON) and all(n >= 1 for n in donde.values()), donde
    assert sueltos == set(SE_FUERON)
    for ruta, respuesta in abren.items():
        if ruta in SE_FUERON:
            assert respuesta.status_code == 301 and respuesta.headers["location"] == SE_FUERON[ruta], ruta
        else:
            assert respuesta.status_code == 200, (ruta, respuesta.status_code)


def test_las_direcciones_viejas_de_CAJAS_de_Compras_llevan_a_las_de_Administracion():
    import app.main as m
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "compras")
        destinos = {r: cliente.get(r, follow_redirects=False) for r in
                    ("/compras/cajas", "/compras/cajas/movimientos?desde=2026-09-01", "/compras/cajas/colega/7")}
    assert {r: (x.status_code, x.headers.get("location")) for r, x in destinos.items()} == {
        "/compras/cajas": (301, "/administracion/cajas"),
        "/compras/cajas/movimientos?desde=2026-09-01": (301, "/administracion/cajas/movimientos?desde=2026-09-01"),
        "/compras/cajas/colega/7": (301, "/administracion/cajas/colega/7"),
    }


def test_la_alerta_de_POCAS_CAJAS_en_Compras_lleva_a_las_Alertas_de_Compras():
    """Compras se quedó sin Cajas: el link no puede chocar contra la clave de
    Administración (corolario 56)."""
    from datetime import datetime
    import app.main as m
    alerta = next(a for a in m.ALERTAS if a.codigo == "cajas_a_reponer")
    assert alerta.destinos_por_sector["compras"] == ("/compras/alertas", "Ver cuál es")
    assert "compras" in alerta.modulos
    estado = [{"codigo": "cajas_a_reponer", "casos": 2, "mas_viejo": None,
               "calculada_el": datetime.now(m.ARGENTINA), "error": None}]
    with patch.dict(os.environ, CLAVES), patch("app.main.listar_estado_alertas", return_value=estado):
        marcado = _cliente(m, "compras").get("/compras").text
    panel = marcado.split('id="franja-alertas"')[1].split("</div>")[0]
    links = re.findall(r'<a class="franja-alerta" href="([^"]+)">', panel)
    assert links == ["/compras/alertas"]
    assert "/administracion/" not in panel


def test_las_PESTANAS_de_Compras_estan_en_sus_seis_pantallas_con_UNA_activa(galpon):
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "compras")
        paginas = {ruta: cliente.get(ruta) for ruta in PESTANAS}
    for ruta, respuesta in paginas.items():
        assert respuesta.status_code == 200, ruta
        etiqueta, hrefs = PESTANAS[ruta]
        marcado = respuesta.text.split("</style>")[-1]
        (nav,) = re.findall(r'<nav class="pestanas" aria-label="%s">(.*?)</nav>' % etiqueta, marcado, re.S)
        links = re.findall(r'<a href="([^"]+)"( aria-current="page")?>', nav)
        assert [h for h, _a in links] == hrefs, ruta
        assert [h for h, a in links if a] == [ruta], ruta


def test_a_313px_CARGAR_COMPRA_y_las_pestanas_de_QUE_COMPRAR_no_se_salen_ni_parten_palabras(galpon):
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "compras")
        cargar = cliente.get("/compras/cargar-compra")
        carga = cliente.get("/compras/carga")
    assert cargar.status_code == carga.status_code == 200
    assert cargar.text.count('<a class="boton color-1"') == 4
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            medidas = {}
            for nombre, html in (("cargar", cargar.text), ("carga", carga.text)):
                pagina = navegador.new_page(viewport={"width": 313, "height": 700})
                pagina.set_content(html)
                medidas[nombre] = pagina.evaluate("""() => ({
                  desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                  botones: [...document.querySelectorAll('a.boton')].map(b => Math.round(b.getBoundingClientRect().height)),
                  pestanas: [...document.querySelectorAll('.pestanas a')].map(a => ({
                    alto: Math.round(a.getBoundingClientRect().height), desborda: a.scrollWidth > a.clientWidth}))})""")
                pagina.close()
        finally:
            navegador.close()
    assert medidas["cargar"]["desborde"] == 0 and medidas["carga"]["desborde"] == 0, medidas
    assert len(medidas["cargar"]["botones"]) == 4 and min(medidas["cargar"]["botones"]) >= 44
    # cada pestaña en UNA línea (44px) y sin salirse: si no entran, bajan enteras
    assert len(medidas["carga"]["pestanas"]) == 2
    assert all(p["alto"] == 44 and not p["desborda"] for p in medidas["carga"]["pestanas"]), medidas
