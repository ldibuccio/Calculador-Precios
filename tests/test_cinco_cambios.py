"""Los cambios del 02/10 sin migración (dueño), contra Postgres y en navegador.

- Reingreso por rechazo: el motivo viene escrito con "Rechazo por calidad",
  editable o borrable; vacío se comporta como siempre (es obligatorio).
- Recibir remito y Reingreso: el texto explicativo va a la "i", cerrada al
  abrir, y a 313px no desborda.
- Movimientos del depósito: "Planilla para pagar" se llama "Resumen
  proveedores" en todos lados.

Los nombres son de EJEMPLO.
"""
import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_remitos import _cliente, base  # noqa: E402,F401  (fixture)


def _cliente_deposito():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app, base_url="https://testserver")


def _valor_del_motivo(html):
    marcado = html.split("</style>")[-1]
    return re.search(r'<input type="text" id="motivo" name="motivo"[^>]*value="([^"]*)"', marcado, re.S).group(1)


def test_el_MOTIVO_del_rechazo_viene_escrito_y_vacio_sigue_siendo_obligatorio(base):
    """El RIVAL es el campo vacío de hasta el 02/10."""
    cliente = _cliente_deposito()
    pagina = cliente.get("/deposito/stock/reingreso", params={"renglon_id": 11})
    assert pagina.status_code == 200
    assert _valor_del_motivo(pagina.text) == "Rechazo por calidad"
    # Borrado: el server lo rechaza como siempre, y el reintento vuelve VACÍO,
    # no con la sugerencia otra vez (lo borró a propósito).
    rebote = cliente.post("/deposito/stock/reingreso", data={
        "renglon_id": "11", "cantidad": "1", "motivo": "", "fecha": "2026-09-06", "destino": "stock"})
    assert rebote.status_code == 400
    assert _valor_del_motivo(rebote.text) == ""
    # Editado: vuelve lo que se escribió.
    rebote = cliente.post("/deposito/stock/reingreso", data={
        "renglon_id": "11", "cantidad": "999", "motivo": "EJ golpeado", "fecha": "2026-09-06", "destino": "stock"})
    assert rebote.status_code == 400 and _valor_del_motivo(rebote.text) == "EJ golpeado"


def _medir_la_i(html):
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 313, "height": 800})
        pagina.set_content(html)
        antes = pagina.evaluate("""() => {
            const botones = [...document.querySelectorAll('[data-info]')];
            return {botones: botones.length,
                    alto: botones.map(b => Math.round(b.getBoundingClientRect().height)),
                    textos_visibles: [...document.querySelectorAll('.info-texto')]
                        .filter(t => getComputedStyle(t).display !== 'none').length,
                    desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth};
        }""")
        pagina.click("[data-info]")
        abierto = pagina.evaluate("""() => {
            const d = document.querySelector('dialog.info-dialogo');
            return {open: d.open, cuerpo: d.querySelector('.info-cuerpo').textContent,
                    desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth};
        }""")
        navegador.close()
    return antes, abierto


def test_RECIBIR_REMITO_la_explicacion_va_a_la_i_cerrada_y_entra_en_313(base, monkeypatch):
    d, _sql = base
    remito = d.emitir_remito(1, "VL", "R-0001")
    html = _cliente(monkeypatch, "administracion").get(f"/administracion/facturacion/remito/{remito}/recibir").text
    assert "cambiá solo lo que el súper anotó distinto" in html            # en el DOM, escondido
    antes, abierto = _medir_la_i(html)
    assert antes == {"botones": 1, "alto": [44], "textos_visibles": 0, "desborde": 0}, antes
    assert abierto["open"] and "cambiá solo lo que el súper anotó distinto" in abierto["cuerpo"]
    assert abierto["desborde"] == 0


def test_REINGRESO_las_explicaciones_van_a_la_i_cerradas_y_entra_en_313(base):
    html = _cliente_deposito().get("/deposito/stock/reingreso", params={"renglon_id": 11}).text
    antes, abierto = _medir_la_i(html)
    # Las dos nuevas (qué es un reingreso, la fecha) más la de los cajones,
    # que ya estaba: su campo arranca escondido, por eso mide 0. (La de "una
    # sola compra" solo sale con compras para elegir.)
    assert antes["botones"] == 3 and antes["textos_visibles"] == 0 and antes["desborde"] == 0, antes
    assert antes["alto"] == [44, 44, 0], antes
    assert abierto["open"] and "volvió del cliente" not in abierto["cuerpo"]
    assert "Entra al stock marcada como rechazo" in abierto["cuerpo"]
    assert "Si el camión volvió ayer" in html.split("</style>")[-1]          # en el DOM, en la i
    # Lo que cambia lo que se hace sigue a la vista: la fecha del pedido.
    assert re.search(r'<p class="ayuda">El pedido es del \d\d/\d\d\. Esta fecha es la de la vuelta', html)


def test_el_RESUMEN_PROVEEDORES_se_llama_asi_en_todos_lados():
    """Ni en las pantallas, ni en el PDF/Excel, ni en CLAUDE.md ni en docs/ queda el nombre viejo."""
    import glob
    archivos = (glob.glob(os.path.join(RAIZ, "app", "*.py")) + glob.glob(os.path.join(RAIZ, "core", "*.py"))
                + glob.glob(os.path.join(RAIZ, "templates", "*.html")) + [os.path.join(RAIZ, "CLAUDE.md")]
                + [a for d in ("reglas", "corolarios", "modulos")       # lo que era CLAUDE.md hasta el 03/10
                   for a in glob.glob(os.path.join(RAIZ, "docs", d, "*.md"))])
    assert len(archivos) > 100
    viejos = [(os.path.basename(a), n) for a in archivos for n in ("Planilla para pagar", "planilla para pagar",
                                                                   "Ingresos a Depósito", "Ingresos_Deposito")
              if n in open(a, encoding="utf-8").read()]
    assert viejos == []
    marcado = open(os.path.join(RAIZ, "templates", "administracion_movimientos_deposito.html"), encoding="utf-8").read()
    assert ">Resumen proveedores</a>" in marcado
