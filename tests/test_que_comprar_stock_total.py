"""Qué comprar hoy: el stock es del ARTÍCULO, provisorio hasta salir (dueño, 28/09).

- El stock son los sueltos más TODAS las cajas armadas, de cualquier ficha y
  cualquier cliente. Hasta el 28/09 contaban solo las cajas de los clientes
  de las cargas tildadas.
- Antes de salir se muestra el de ahora, en gris y con "provisorio, se
  congela al salir"; la cuenta ya lo usa.
- "Salgo a comprar" va arriba de todo. Después de salir, arriba dice de
  cuándo es la foto.
- Un stock que no se puede saber dice por qué.
"""
import re
from datetime import datetime, timezone

import tests.test_que_comprar as tq
from app.main import _piso_de_la_foto

# Tomate (1): 2 sueltos de 20 kg = 40; cajas de DOS clientes: 3 de Día (ficha 11,
# 10 kg) y 4 de Coto (ficha 12, 5 kg). Zapallito (2): una caja sin contenido.
FOTO = {"sueltos": {1: (2.0, 40.0), 2: (1.0, 20.0)},
        "cajas": {11: (1, 3.0, 30.0), 12: (1, 4.0, 20.0), 13: (2, 2.0, None)}}


def test_el_stock_suma_las_cajas_de_TODOS_los_clientes():
    piso = _piso_de_la_foto(FOTO, [1])
    # 40 sueltos + 30 de Día + 20 de Coto. El rival de antes: solo Día daba 70.
    assert piso[1]["magnitud"] == 90.0
    assert piso[1]["cajas"] == 7.0
    assert piso[1].get("por_que") is None


def test_un_stock_que_no_se_puede_saber_dice_POR_QUE():
    piso = _piso_de_la_foto(FOTO, [2, 3])
    assert piso[2]["magnitud"] is None
    assert piso[2]["por_que"] == "hay cajas armadas de una ficha sin contenido por caja"
    assert piso[3]["por_que"] == "el artículo se cargó después de la foto"
    sin_contenido = _piso_de_la_foto({"sueltos": {4: (3.0, None)}, "cajas": {}}, [4])
    assert sin_contenido[4]["por_que"] == "hay cajones sueltos sin contenido declarado"


def test_la_cuenta_real_usa_el_stock_TOTAL_sin_pedir_las_fichas_del_cliente():
    """Por el contexto de verdad: la foto trae una caja de OTRO cliente."""
    from unittest.mock import patch
    foto = {"sueltos": {1: (2.0, 40.0)}, "cajas": {99: (1, 5.0, 100.0)}}
    borrador = {"id": 3, "fecha": tq.date(2026, 9, 23), "cargas": [1], "kilajes": {},
                "generado_el": datetime(2026, 9, 23, 1, 5, tzinfo=timezone.utc)}
    contexto, _ = tq._contexto_real(borrador, foto_guardada=foto)
    assert contexto["filas"][0]["en_piso"] == 140.0


def _tarjetas(html):
    marcado = html.split("</style>")[-1]
    return re.findall(r'data-articulo="\d+"(.*?)(?=data-articulo="|<button class="guardar")',
                      marcado, re.S)


def test_ANTES_de_salir_el_stock_va_en_gris_y_dice_provisorio():
    html = tq._render(tq._contexto([tq._fila(3, "TOMATE"), tq._fila(8, "ZAPALLITO")]))
    tarjetas = _tarjetas(html)
    assert len(tarjetas) == 2
    for tarjeta in tarjetas:
        assert '<span class="dato dato-stock" data-provisorio>' in tarjeta
        assert "provisorio, se congela al salir" in tarjeta
    assert ".dato-stock[data-provisorio]" in html.split("</style>")[0]


def test_DESPUES_de_salir_el_stock_no_es_provisorio_y_arriba_dice_de_cuando():
    salida = datetime(2026, 9, 28, 13, 5, tzinfo=timezone.utc)
    from app.main import ARGENTINA
    html = tq._render(tq._contexto([tq._fila(3, "TOMATE")], salio_el=salida.astimezone(ARGENTINA)))
    marcado = html.split("</style>")[-1]
    assert "data-provisorio" not in marcado
    assert "provisorio, se congela al salir" not in marcado
    arriba = marcado[marcado.index('<div class="arriba">'):marcado.index('<div class="tarjeta">')]
    assert "Stock congelado el <b>28/09 a las 10:05</b>" in arriba
    assert 'value="salgo"' not in marcado


def test_SALGO_A_COMPRAR_va_ARRIBA_de_todo_y_una_sola_vez():
    marcado = tq._render(tq._contexto([tq._fila(3, "TOMATE")])).split("</style>")[-1]
    assert marcado.count('value="salgo"') == 1
    arriba = marcado[marcado.index('<div class="arriba">'):marcado.index('<div class="tarjeta">')]
    # Antes que Actualizar y Exportar, y antes que la elección de cargas.
    assert arriba.index('value="salgo"') < arriba.index('value="guardar"') < arriba.index('value="pdf"')


def test_en_el_NAVEGADOR_a_390_Salgo_se_ve_sin_bajar_y_mide_44():
    import pytest
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    html = tq._render(tq._contexto([tq._fila(3, "TOMATE")]))
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        caja = pagina.evaluate("""() => {
            const b = document.querySelector('button.salgo').getBoundingClientRect();
            const s = getComputedStyle(document.querySelector('.dato-stock b'));
            return {abajo: b.bottom, alto: b.height, color: s.color,
                    desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth};
        }""")
        navegador.close()
    assert caja["abajo"] <= 844 and caja["alto"] >= 44
    assert caja["color"] == "rgb(107, 114, 128)"       # el gris del provisorio
    assert caja["desborde"] == 0


def _pdf(salio_el):
    import os
    from unittest.mock import patch
    import pypdfium2 as pdfium
    contexto = tq._contexto([tq._fila(3, "TOMATE")], salio_el=salio_el)
    contexto["elegidas"] = set()
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}), \
         patch("app.main._contexto_de_que_comprar", return_value=contexto):
        contenido = tq._cliente.get("/compras/que-comprar/pdf").content
    return "\n".join(p.get_textpage().get_text_range() for p in pdfium.PdfDocument(contenido))


def test_el_PDF_antes_de_salir_dice_STOCK_PROVISORIO_y_despues_no():
    from app.main import ARGENTINA
    assert "stock provisorio" in _pdf(None)
    despues = _pdf(datetime(2026, 9, 28, 13, 5, tzinfo=timezone.utc).astimezone(ARGENTINA))
    assert "stock provisorio" not in despues and "stock al salir, 28/09 10:05" in despues


def test_la_PANTALLA_dice_por_que_no_se_puede_saber_el_stock():
    fila = {**tq._fila(3, "TOMATE"), "en_piso": None, "stock_bultos": None,
            "stock_por_que": "hay cajas armadas de una ficha sin contenido por caja"}
    tarjeta, = _tarjetas(tq._render(tq._contexto([fila])))
    celda = tarjeta[tarjeta.index('class="dato dato-stock"'):tarjeta.index('class="dato dato-en-camino"')]
    assert "no se puede saber" in celda
    assert '<small class="por-que">hay cajas armadas de una ficha sin contenido por caja</small>' in celda
