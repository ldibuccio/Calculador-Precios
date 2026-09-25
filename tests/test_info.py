# -*- coding: utf-8 -*-
"""La "i" de información (25/09).

Criterio del dueño: si leerlo cambia lo que el operario hace EN ESE MOMENTO,
se ve; si explica CÓMO FUNCIONA, va a la "i". El texto queda en el DOM,
escondido, y lo abre un diálogo único que vive en la barra.

Lo que se mira en navegador y no en el marcado (corolario 32: el atributo es
la intención, el efecto lo decide el CSS): que el botón mida 44px, que el
texto NO se vea, y que el diálogo se abra, lo muestre y se cierre.
"""
import os
import sys

import pytest
from jinja2 import Environment, FileSystemLoader

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_app import (  # noqa: E402
    CASILLA_DE_PRUEBA, CLIENTES_PARA_SELECTOR, MAIL_PEDIDO_DE_PRUEBA,
    RESULTADO_REAL_DE_PRUEBA, TOTALES_TEORICA_DE_PRUEBA, cliente,
)
from datetime import date  # noqa: E402
from unittest.mock import patch  # noqa: E402


def _casilla():
    with (
        patch("app.main.listar_casillas_pedidos", return_value=[dict(CASILLA_DE_PRUEBA)]),
        patch("app.main.listar_mails_pedido", return_value=[dict(MAIL_PEDIDO_DE_PRUEBA)]),
        patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR),
        patch("app.main.clave_casilla_configurada", return_value="clave"),
    ):
        return cliente.get("/sistema/casilla-pedidos")


def _rentabilidad():
    teorica = {"grupos": [], "totales": dict(TOTALES_TEORICA_DE_PRUEBA), "no_calculables": [],
               "fechas_incluidas": []}
    with (
        patch("app.main._hoy_argentina", return_value=date(2026, 8, 25)),
        patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR),
        patch("app.main.listar_fichas_por_cliente", return_value=[]),
        patch("app.main._datos_rentabilidad_real", return_value=dict(RESULTADO_REAL_DE_PRUEBA)),
        patch("app.main._datos_rentabilidad", return_value=teorica),
    ):
        return cliente.get("/gerencia/rentabilidad-real?cliente_id=1")


def _cotejo():
    """La plantilla del Cotejo directo: su ruta arma las filas con cinco
    lecturas, y lo que se mira acá es solo la ayuda. Una fila de SEGUNDA con
    desvío y una de FICHA con desvío, que son las dos ramas con ayuda."""
    import app.main as m
    from datetime import datetime, timezone
    base = {"porcion_nombre": "EJEMPLO Uno", "creado_en": datetime(2026, 9, 1, tzinfo=timezone.utc),
            "cantidad": 5, "sistema_hoy": 8, "dif_hoy": 3, "deficit": 0, "opuestas": [],
            "query_ajuste": None, "ficha_id": None, "es_segunda": False}
    filas = [dict(base, es_segunda=True), dict(base, ficha_id=7)]
    return m.templates.env.get_template("deposito_stock_cotejo.html").render(filas=filas)


ENTORNO = Environment(loader=FileSystemLoader(os.path.join(RAIZ, "templates")))

PAGINA = """{% from "_info.html" import info %}<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body { margin: 0; padding: 1rem; }</style></head><body>
<p class="sub">Qué es {% call info("EJEMPLO título") %}Texto <strong>EJEMPLO</strong> largo.{% endcall %}</p>
</body></html>"""


def _pagina_con_barra():
    """La barra de verdad (con su CSS y su listener) más un uso de la macro."""
    import app.main as m
    barra = m.templates.env.get_template("_barra_navegacion.html").render(
        barra_sector="gerencia", barra_titulo="EJEMPLO", barra_atras="/gerencia",
        **{k: v for k, v in m.templates.env.globals.items()})
    uso = m.templates.env.from_string(PAGINA).render()
    return uso.replace("<body>", "<body>" + barra, 1)


def test_la_macro_deja_el_texto_en_el_DOM_al_lado_del_boton():
    html = ENTORNO.from_string(PAGINA).render()
    assert '<button type="button" class="info-boton" data-info' in html
    assert 'aria-label="Más información: EJEMPLO título"' in html
    # el texto va en el hermano de al lado, que es lo que el listener lee
    assert '</button><span class="info-texto">Texto <strong>EJEMPLO</strong> largo.</span>' in html
    # sin <style> propio: correría el último </style> del documento (corolario 50)
    import re
    fuente = re.sub(r"\{#.*?#\}", "", ENTORNO.loader.get_source(ENTORNO, "_info.html")[0], flags=re.S)
    assert "<style" not in fuente


def test_en_el_NAVEGADOR_el_boton_mide_44_el_texto_no_se_ve_y_el_dialogo_abre_y_cierra():
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    html = _pagina_con_barra()
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        antes = pagina.evaluate("""() => {
            const b = document.querySelector('[data-info]').getBoundingClientRect();
            const t = document.querySelector('.info-texto');
            return {ancho: b.width, alto: b.height, texto_display: getComputedStyle(t).display,
                    dialogos: document.querySelectorAll('dialog').length};
        }""")
        pagina.click("[data-info]")
        abierto = pagina.evaluate("""() => {
            const d = document.querySelector('dialog.info-dialogo');
            const c = d.querySelector('button.info-cerrar').getBoundingClientRect();
            return {open: d.open, titulo: d.querySelector('h2').textContent,
                    cuerpo: d.querySelector('.info-cuerpo').innerHTML, cerrar_alto: c.height,
                    desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth};
        }""")
        pagina.click("button.info-cerrar")
        cerrado_boton = pagina.evaluate("() => document.querySelector('dialog.info-dialogo').open")
        # tocar AFUERA también cierra (el fondo le pega al <dialog> mismo)
        pagina.click("[data-info]")
        pagina.mouse.click(5, 5)
        cerrado_afuera = pagina.evaluate("() => document.querySelector('dialog.info-dialogo').open")
        # y tocar ADENTRO del texto NO cierra
        pagina.click("[data-info]")
        pagina.click("dialog.info-dialogo .info-cuerpo")
        sigue_abierto = pagina.evaluate("() => document.querySelector('dialog.info-dialogo').open")
        navegador.close()

    assert antes == {"ancho": 44, "alto": 44, "texto_display": "none", "dialogos": 0}, antes
    assert abierto["open"] and abierto["titulo"] == "EJEMPLO título", abierto
    assert abierto["cuerpo"] == "Texto <strong>EJEMPLO</strong> largo.", abierto
    assert abierto["cerrar_alto"] >= 44 and abierto["desborde"] == 0, abierto
    assert cerrado_boton is False and cerrado_afuera is False
    assert sigue_abierto is True


def _infos(marcado):
    """(título, texto) de cada "i" de la pantalla, anclado en el marcado."""
    import re
    return re.findall(r'data-info-titulo="([^"]*)">i</button><span class="info-texto">(.*?)</span>(?=\S|\s)',
                      marcado, re.S)


def test_RENTABILIDAD_REAL_la_cuenta_y_la_diferencia_van_a_la_i():
    marcado = _rentabilidad().text.split("</style>")[-1]
    titulos = [t for t, _ in _infos(marcado)]
    assert titulos == ["Cómo se calcula la rentabilidad real", "Qué es la diferencia"], titulos
    # el texto sigue estando, adentro de la "i" y en ningún otro lado
    assert marcado.count("la lista de cosas a explicar") == 1
    assert 'class="nota"' not in marcado
    # las aclaraciones de una línea de las mermas quedan como están
    assert "Cajones como vinieron de la compra." not in "".join(x for _, x in _infos(marcado))


def test_CASILLA_las_tres_explicaciones_van_a_la_i_y_el_aviso_queda_a_la_vista():
    marcado = _casilla().text.split("</style>")[-1]
    titulos = [t for t, _ in _infos(marcado)]
    assert titulos == ["Qué correos mira el sistema", "Auto-confirmar", "Los mails registrados"], titulos
    assert marcado.count("solo lectura estricta") == 1
    assert '<p class="sub" style="margin-bottom: 0.25rem;">' not in marcado
    # lo que cambia qué hace el que lo lee queda A LA VISTA
    assert "La casilla queda guardada DESACTIVADA" not in "".join(x for _, x in _infos(marcado))


def test_COTEJO_el_signo_y_que_hacer_se_ven_el_porque_va_a_la_i():
    marcado = _cotejo()
    infos = _infos(marcado)
    assert [t for t, _ in infos] == ["Cómo se compara", "Por qué no se ajusta la segunda"], infos
    escondido = "".join(x for _, x in infos)
    # A LA VISTA: cómo leer el número, y qué NO hacer con un desvío
    assert "positivo es mercadería que falta" in marcado
    assert "positivo es mercadería que falta" not in escondido
    assert "No se corrige ajustando el stock" not in escondido
    assert "Revisá la guía R en Guías R, no ajustes el stock." in marcado
    assert "Revisá la guía R" not in escondido


def test_MIRAR_PANTALLA_no_imprime_como_visible_el_texto_de_la_i():
    """El paso 6 del push lee la pantalla con este script, que no corre CSS:
    sin esto imprimía el texto escondido como si estuviera a la vista."""
    from scripts.mirar_pantalla import texto_visible
    html = ENTORNO.from_string(PAGINA).render()
    assert texto_visible(html) == ["Qué es [i]"]


@pytest.mark.parametrize("pantalla", ["rentabilidad", "casilla", "cotejo"])
def test_las_TRES_pantallas_no_desbordan_ni_se_pisan_a_390(pantalla):
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from scripts.medir_layout import medir_sync
    html = {"rentabilidad": lambda: _rentabilidad().text, "casilla": lambda: _casilla().text,
            "cotejo": _cotejo}[pantalla]()
    medicion = medir_sync(html, ancho=390)
    assert medicion["pares"] > 0, medicion
    assert medicion["desborde_pagina"] == 0, medicion
    assert medicion["solapes"] == [], medicion
