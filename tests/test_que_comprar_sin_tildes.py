"""Qué comprar hoy: AL ENTRAR NUNCA HAY NADA TILDADO (dueño, 05/10), contra Postgres.

"Ni aunque sea el mismo día y ya se haya guardado. Se tilda, se aprieta
Actualizar, y recién ahí calcula." Hasta v1098 la pantalla abría con lo
guardado hoy ("se abre como se dejó"): el tilde volvía por el LISTADO DEL DÍA,
no por el autocompletado del navegador (que ya estaba apagado). El test abre
la pantalla DESPUÉS de guardar el mismo día y exige cero tildes, mirando el
`checked` que el navegador ve; el RIVAL es la vuelta de Actualizar, que sí
muestra lo tildado. Los nombres son de EJEMPLO.
"""
import os
from datetime import datetime
from unittest.mock import patch

import pytest

from tests.test_cargas_compra import base_real, galpon  # noqa: F401  (fixtures)

CLAVE = {"CLAVE_COMPRAS": "compras-secreta"}


def _cliente_de_compras():
    from fastapi.testclient import TestClient
    import app.main as m
    cliente = TestClient(m.app)
    cliente.cookies.set(m.PUERTA_COMPRAS.cookie, m.PUERTA_COMPRAS.firma("compras-secreta"))
    return cliente


def _tildes(html):
    """Cuántas cargas tiene tildadas la pantalla, para el navegador."""
    pytest.importorskip("playwright", reason="lo tildado lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            pagina = navegador.new_page()
            pagina.set_content(html)
            return pagina.evaluate(
                "() => [...document.querySelectorAll('input[name=carga]')].filter(c => c.checked).length")
        finally:
            navegador.close()


def test_despues_de_GUARDAR_el_mismo_dia_la_pantalla_abre_con_CERO_tildes(galpon):
    import app.main as m
    d, sql, cliente_id, tomate, _lima = galpon
    sql("UPDATE listados_compra SET estado = 'cerrado' WHERE estado = 'borrador'")
    hoy = datetime.now(m.ARGENTINA).date()
    carga = d.guardar_carga_de_compra(cliente_id, hoy, "manual", datetime.now(m.ARGENTINA), 0)
    sql("INSERT INTO cargas_compra_renglones (carga_id, articulo_id, total) VALUES (%s, %s, 160)", (carga, tomate))
    cliente = _cliente_de_compras()
    with patch.dict(os.environ, CLAVE):
        guardado = cliente.post("/compras/que-comprar", data={"accion": "guardar", "carga": [str(carga)]},
                                follow_redirects=False)
        assert guardado.status_code == 303
        assert sql("SELECT c.carga_id FROM listados_compra_cargas c JOIN listados_compra l ON l.id = c.listado_id "
                   "WHERE l.estado = 'borrador'") == [(carga,)]
        vuelta = cliente.get(guardado.headers["location"])        # la vuelta de Actualizar
        entrar = cliente.get("/compras/que-comprar")              # entrar de nuevo, el mismo día
    assert vuelta.status_code == entrar.status_code == 200
    # la identidad: es la pantalla, con la carga de este test ofrecida
    assert entrar.text.count(f'name="carga" value="{carga}"') == 1
    assert _tildes(vuelta.text) == 1                              # el RIVAL: al volver de Actualizar, sí
    assert _tildes(entrar.text) == 0
    # y sin cálculo: no hay filas del listado hasta Actualizar
    assert vuelta.text.count('data-articulo="') == 1 and entrar.text.count('data-articulo="') == 0
    # el "atrás" del navegador no restaura una pantalla vieja con tildes
    assert entrar.headers["cache-control"] == "no-store"


def test_el_PDF_sale_de_lo_GUARDADO_aunque_al_entrar_no_haya_tildes(galpon):
    """El PDF no se toca: "Exportar" guarda primero y saca lo tildado."""
    import app.main as m
    d, sql, cliente_id, tomate, _lima = galpon
    sql("UPDATE listados_compra SET estado = 'cerrado' WHERE estado = 'borrador'")
    hoy = datetime.now(m.ARGENTINA).date()
    carga = d.guardar_carga_de_compra(cliente_id, hoy, "manual", datetime.now(m.ARGENTINA), 0)
    sql("INSERT INTO cargas_compra_renglones (carga_id, articulo_id, total) VALUES (%s, %s, 160)", (carga, tomate))
    cliente = _cliente_de_compras()
    with patch.dict(os.environ, CLAVE):
        pdf = cliente.post("/compras/que-comprar", data={"accion": "pdf", "carga": [str(carga)]})
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    import pypdfium2 as pdfium
    texto = "\n".join(p.get_textpage().get_text_range() for p in pdfium.PdfDocument(pdf.content))
    assert "EJEMPLO Tomate" in texto
