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


# ---------------------------------------------------------------------------
# EL BARRIDO de todas las pantallas (25/09). El conjunto ENCONTRADO contra el
# DECIDIDO (corolario 60): falla cuando aparece una pantalla con "i" que nadie
# decidió y cuando una de la lista la pierde.
# ---------------------------------------------------------------------------

PANTALLAS_CON_I = {
    "_cuadro_negociacion.html", "administracion_extracto_porcion.html",
    "administracion_ingresos.html", "administracion_stock_evolucion.html",
    "administracion_stock_remanente.html", "alertas_sector.html",
    "cliente_formulario.html", "compra_detalle.html", "compra_editar_gerencia.html",
    "compra_form.html", "compra_fotos_multiples.html", "compra_leer_foto.html",
    "compra_listado.html", "compra_manual.html", "compra_proveedor_form.html",
    "compras_cajas.html", "compras_cajas_colega.html", "compras_cajas_movimientos.html",
    "compras_carga.html", "compras_proveedores.html", "compras_vacios_cotejo.html",
    "compras_vacios_proveedor.html", "deposito_ingresar.html", "deposito_pedido_buscar.html",
    "deposito_pedido_cargar.html", "deposito_stock_ajustar.html",
    "deposito_stock_articulo.html", "deposito_stock_cotejo.html",
    "deposito_stock_guias_r.html", "deposito_stock_merma.html",
    "deposito_stock_movimientos.html", "deposito_stock_reingreso.html",
    "deposito_stock_reproceso.html", "envases.html", "ficha_form.html",
    "fichas_historial.html", "gerencia_costos_fijos_cargar.html",
    "gerencia_costos_fijos_indices.html", "gerencia_costos_fijos_plan.html",
    "gerencia_ingreso_retroactivo.html", "gerencia_perdidas.html",
    "gerencia_rentabilidad.html", "gerencia_rentabilidad_real.html", "negociar.html",
    "precios_cargar_foto.html", "precios_consulta.html", "precios_vigencias.html",
    "sistema_casilla_pedidos.html", "vacios_ajustar.html", "vacios_clientes.html",
    "vacios_cotejo.html", "vacios_movimientos.html", "vacios_pendientes.html",
    "vacios_proveedores.html", "vacios_stock.html", "vacios_tipos.html",
}

# Los que SE VEN aunque estén en una pantalla que ganó la "i": avisos que
# cambian lo que el operario hace (la lista del dueño, en CLAUDE.md). Si uno
# termina adentro de un `call info`, deja de verse, y eso es lo que se prohíbe.
QUEDAN_A_LA_VISTA = [
    ("ficha_form.html", "esto cierra la ficha y abre una nueva"),
    ("ficha_form.html", "probablemente haya que cambiar este alias"),
    ("compra_editar_gerencia.html", "primero: con una compra recepcionada"),
    ("compra_editar_gerencia.html", "Tiene que ser posterior al corte"),
    ("vacios_tipos.html", "La fecha que elegiste es anterior"),
    ("administracion_stock_inicial.html", "queda sin costear para siempre"),
    ("administracion_stock_inicial.html", "Una caja armada siempre es de alguna ficha"),
    ("deposito_stock_reingreso.html", "Si el camión volvió ayer"),
    ("deposito_stock_reingreso.html", "El pedido es del"),
    ("deposito_stock_fisico.html", "aunque te parezca que está mal"),
    ("vacios_stock_fisico.html", "Contá los cajones que hay físicamente"),
    ("compras_cajas.html", "Contalas a la mañana"),
    ("compra_vino_armada.html", "Se carga la guía R de una vez"),
    ("deposito_stock_cotejo.html", "no ajustes el stock"),
    # y los dos "no se suma" que son reglas del dueño
    ("gerencia_perdidas.html", "<strong>no se suma</strong> con la de"),
    ("gerencia_cajas_perdidas.html", "<strong>ya se cobra</strong>"),
]


def _fuente(nombre):
    import re
    texto = ENTORNO.loader.get_source(ENTORNO, nombre)[0]
    return re.sub(r"\{#.*?#\}", "", texto, flags=re.S)


def _cuerpos_de_la_i(fuente):
    import re
    return re.findall(r'\{% call info\("[^"]*"\) %\}(.*?)\{% endcall %\}', fuente, re.S)


def test_las_pantallas_con_i_son_EXACTAMENTE_las_decididas():
    encontradas = {
        n for n in os.listdir(os.path.join(RAIZ, "templates"))
        if n.endswith(".html") and n != "_info.html" and "call info(" in _fuente(n)
    }
    assert encontradas - PANTALLAS_CON_I == set(), "con i y sin decidir"
    assert PANTALLAS_CON_I - encontradas == set(), "decididas y sin i"


@pytest.mark.parametrize("nombre", sorted(PANTALLAS_CON_I))
def test_cada_pantalla_importa_la_i_UNA_vez_y_su_texto_es_de_LINEA(nombre):
    import re
    fuente = _fuente(nombre)
    assert fuente.count('{% from "_info.html" import info %}') == 1
    # el import va antes del primer uso: si no, la plantilla no compila
    assert fuente.index("import info") < fuente.index("call info(")
    for cuerpo in _cuerpos_de_la_i(fuente):
        # el texto vive en un <span>: un bloque adentro lo rompe el navegador
        assert not re.search(r"<(p|div|ul|ol|li|table|h\d|form|section)\b", cuerpo), cuerpo[:80]
    # y nunca adentro de un <script>, donde la macro no se ejecuta
    for script in re.findall(r"<script.*?</script>", fuente, re.S):
        assert "call info(" not in script


@pytest.mark.parametrize("nombre,frase", QUEDAN_A_LA_VISTA)
def test_los_AVISOS_que_cambian_lo_que_se_hace_siguen_a_la_vista(nombre, frase):
    fuente = _fuente(nombre)
    assert frase in fuente, "el aviso ya no está en la pantalla"
    assert all(frase not in cuerpo for cuerpo in _cuerpos_de_la_i(fuente)), \
        "el aviso quedó escondido en la i"


def test_la_i_adentro_de_un_LABEL_no_toca_el_campo():
    """Siete pantallas cuelgan la i de un <label>. Tocarla no puede tildar el
    campo que el label envuelve: un botón es contenido interactivo y el label
    no se activa, y el listener además hace preventDefault. Se mide, no se lee."""
    pytest.importorskip("playwright", reason="lo que pasa al tocar lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    html = _pagina_con_barra().replace(
        "</body>",
        '<label id="rot"><input type="checkbox" id="tilde"> Tildar '
        '<button type="button" class="info-boton" data-info data-info-titulo="EJEMPLO">i</button>'
        '<span class="info-texto">EJEMPLO</span></label></body>', 1)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        pagina.click("#rot [data-info]")
        tras_la_i = pagina.evaluate("""() => ({tilde: document.getElementById('tilde').checked,
            abierto: document.querySelector('dialog.info-dialogo').open})""")
        pagina.click("button.info-cerrar")
        pagina.click("#rot", position={"x": 5, "y": 5})
        tras_el_rotulo = pagina.evaluate("() => document.getElementById('tilde').checked")
        navegador.close()
    assert tras_la_i == {"tilde": False, "abierto": True}, tras_la_i
    # el control: el rótulo mismo sí tilda, o el caso de arriba no probaba nada
    assert tras_el_rotulo is True
