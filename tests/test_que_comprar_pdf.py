"""Qué comprar hoy: el PDF del listado y el botón Actualizar arriba (dueño, 28/09).

Lo que cuidan estos tests, en orden de cuánto cuesta que se rompa:

1. EL PAPEL Y LA PANTALLA DICEN LO MISMO. Las filas son las mismas (salen de
   `_filas_de_que_comprar`), pero CÓMO SE DICE cada celda está escrito dos
   veces —Jinja y `textos_de_la_fila`— y el test las compara celda por celda.
2. EL PDF SALE DE LO TILDADO EN ESE MOMENTO: el botón guarda primero.
3. ACTUALIZAR ESTÁ ARRIBA, a la vista sin bajar en un celular, y el Guardar
   de abajo sigue.
"""
import os
import re
from datetime import date, datetime
from unittest.mock import patch

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient

import app.main as _main
from core.exportar_que_comprar import generar_pdf_que_comprar, para_el_papel, textos_de_la_fila

_cliente = TestClient(_main.app)
_cliente.cookies.set(_main.PUERTA_COMPRAS.cookie, _main.PUERTA_COMPRAS.firma("compras-secreta"))
_CLAVE = {"CLAVE_COMPRAS": "compras-secreta"}


def _fila(articulo_id, nombre, **cambios):
    fila = {"articulo_id": articulo_id, "nombre": nombre, "sufijo": "kg", "pide": 240.0,
            "de_quien": [("EJEMPLO Dia 26/09", 240.0)], "ya_tengo": 40.0, "en_piso": 40.0,
            "sueltos": 2, "cajas": 0, "comprado_cajones": 3.0, "comprado": 54.0,
            "kilaje": 18.0, "falta": 146.0, "cajones": 9,
            "a_comprar": 12, "pide_bultos": 13, "stock_bultos": 2, "palabra": "kg",
            "de_partida": 40.0, "en_camino": 0.0, "en_camino_cajones": 0.0,
            "a_comprar_magnitud": 200.0}
    fila.update(cambios)
    return fila


# UNA FILA POR RAMA de cada celda: si el fixture dibuja una sola, el test
# compara la rama cómoda y las otras se pueden separar sin que caiga nada.
FILAS = [
    _fila(1, "EJEMPLO Normal"),
    _fila(2, "EJEMPLO Ok", falta=0.0, cajones=None, a_comprar_magnitud=0.0, a_comprar=None),
    _fila(3, "EJEMPLO Sin bulto", kilaje=None, cajones=None, a_comprar=None,
          pide_bultos=None, stock_bultos=None),
    _fila(4, "EJEMPLO Sin unidad", pide=None, falta=None, cajones=None, a_comprar=None,
          a_comprar_magnitud=None, en_camino=None, pide_bultos=None),
    _fila(5, "EJEMPLO Sin piso", en_piso=None, de_partida=None, falta=None, cajones=None,
          a_comprar=None, a_comprar_magnitud=None, stock_bultos=None, en_camino_cajones=4.0),
]

CARGAS = [
    {"id": 11, "cliente_id": 7, "cliente_nombre": "EJEMPLO Dia", "fecha": date(2026, 9, 27),
     "modo": "automatico", "margen_porcentaje": 10, "usada_en_otros": 0},
    {"id": 12, "cliente_id": 7, "cliente_nombre": "EJEMPLO Dia", "fecha": date(2026, 9, 28),
     "modo": "manual", "margen_porcentaje": 0, "usada_en_otros": 0},
    {"id": 13, "cliente_id": 9, "cliente_nombre": "EJEMPLO Tailem", "fecha": date(2026, 9, 28),
     "modo": "manual", "margen_porcentaje": 0, "usada_en_otros": 0},
]


def _contexto(filas=FILAS, elegidas=(11, 13), salio_el=None, viejas=(), cargas=CARGAS, aviso=None):
    return {"barra_sector": "compras", "barra_titulo": "Qué comprar hoy",
            "clientes": _main._cargas_por_cliente([dict(c) for c in cargas]),
            "elegidas": set(elegidas), "filas": list(filas), "aviso": aviso,
            "hay_borrador": True, "salio_el": salio_el, "viejas": list(viejas)}


def _render(contexto):
    with patch.dict(os.environ, _CLAVE), \
         patch("app.main._contexto_de_que_comprar", return_value=contexto):
        return _cliente.get("/compras/que-comprar").text


def _pdf(contexto):
    with patch.dict(os.environ, _CLAVE), \
         patch("app.main._contexto_de_que_comprar", return_value=contexto):
        return _cliente.get("/compras/que-comprar/pdf")


def _texto_pdf(contenido):
    documento = pdfium.PdfDocument(contenido)
    texto = "\n".join(pagina.get_textpage().get_text_range() for pagina in documento)
    return " ".join(texto.split()), len(documento)


def _visible(fragmento):
    return " ".join(re.sub(r"<[^>]+>", " ", fragmento).split())


# --- 1. EL PAPEL Y LA PANTALLA DICEN LO MISMO -------------------------------

CELDAS = {"dato-pide": "pide", "dato-bultos": "pide_bultos", "dato-stock": "stock",
          "dato-en-camino": "en_camino", "dato-a-comprar": "a_comprar",
          "dato-compre": "compre", "dato-falta": "falta"}


def test_el_PDF_dice_en_cada_celda_LO_MISMO_que_la_pantalla():
    """Renderiza la pantalla y compara el <b> de cada celda contra
    `textos_de_la_fila`. El kilaje queda afuera: en la pantalla es un campo.

    Con el denominador al lado: cinco filas por siete celdas, y cada rama de
    cada celda (OK, "poné el por bulto", "no se sabe la unidad", el hueco del
    stock) aparece en al menos una."""
    marcado = _render(_contexto()).split("</style>")[-1]
    tarjetas = re.findall(r'data-articulo="(\d+)"(.*?)(?=data-articulo="|<button class="guardar")',
                          marcado, re.S)
    assert len(tarjetas) == len(FILAS)
    por_id = {f["articulo_id"]: f for f in FILAS}
    comparadas = 0
    vistos = set()
    for articulo_id, tarjeta in tarjetas:
        textos = textos_de_la_fila(por_id[int(articulo_id)], _main._formatear_numero,
                                   _main._formatear_sin_decimales)
        for clase, clave in CELDAS.items():
            celda = re.search(rf'class="dato {clase}".*?<b[^>]*>(.*?)</b>', tarjeta, re.S).group(1)
            assert _visible(celda) == textos[clave], (articulo_id, clase)
            vistos.add(textos[clave])
            comparadas += 1
        magnitud = re.search(r'class="stock-magnitud">(.*?)</small>', tarjeta)
        assert (_visible(magnitud.group(1)) if magnitud else "") == textos["stock_magnitud"]
    assert comparadas == len(FILAS) * len(CELDAS)
    assert {"OK", "poné el por bulto", "no se sabe la unidad", "no se puede saber", "—"} <= vistos


def test_el_PDF_trae_cada_ARTICULO_con_su_FALTA_y_de_quien_sale():
    texto, _paginas = _texto_pdf(generar_pdf_que_comprar(
        "28/09/2026 · stock de ahora", ["EJEMPLO Dia 27/09"], FILAS,
        _main._formatear_numero, _main._formatear_sin_decimales))
    for fila in FILAS:
        assert fila["nombre"] in texto
    # LOS RÓTULOS ENTEROS: con nueve columnas en A4, "Compré" se partía en
    # "Compr é" y "A comprar" en "A comp rar". Partir entre palabras se lee;
    # al medio de una, no.
    for rotulo in ("Artículo Piden Por bulto Piden bultos Stock En camino A comprar hoy "
                   "Compré Falta comprar",):
        assert rotulo in texto
    assert "EJEMPLO Dia 26/09 240" in texto
    assert "9 cj" in texto and "12 cj" in texto
    # Los carteles de la pantalla NO van al papel: ahí quedan en blanco.
    for cartel in ("poné el por bulto", "no se sabe la unidad", "no se puede saber", "OK", "—"):
        assert cartel not in texto, cartel


def test_un_listado_LARGO_sigue_en_la_hoja_siguiente_con_los_rotulos_repetidos():
    """A4: sesenta artículos no entran en una hoja, y la segunda sin rótulos
    no se entiende impresa."""
    filas = [_fila(i, f"EJEMPLO Art{i:02d}") for i in range(60)]
    contenido = generar_pdf_que_comprar("x", ["EJEMPLO Dia 27/09"], filas,
                                        _main._formatear_numero, _main._formatear_sin_decimales)
    documento = pdfium.PdfDocument(contenido)
    assert len(documento) >= 2
    ancho, alto = documento[0].get_size()
    assert (round(ancho), round(alto)) == (595, 842)          # A4 vertical, en puntos
    segunda = documento[1].get_textpage().get_text_range()
    assert "Falta" in segunda and "Artículo" in segunda


def test_un_nombre_con_MENOR_QUE_no_rompe_el_PDF():
    """Paragraph lee marcado: un "<" sin escapar tira el PDF entero."""
    texto, _p = _texto_pdf(generar_pdf_que_comprar(
        "x", ["EJEMPLO <raro> & cia"], [_fila(1, "EJEMPLO <b>Tomate")],
        _main._formatear_numero, _main._formatear_sin_decimales))
    assert "EJEMPLO <b>Tomate" in texto and "EJEMPLO <raro> & cia" in texto


# --- 2. EL PDF SALE DE LO TILDADO EN ESE MOMENTO ---------------------------


def test_el_boton_PDF_GUARDA_PRIMERO_y_redirige_al_PDF():
    """El RIVAL es un link directo al PDF: imprimiría lo último guardado, y
    no lo que el que aprieta tiene tildado."""
    with patch.dict(os.environ, _CLAVE), \
         patch("app.main.guardar_borrador_de_compra", return_value=5) as guardar, \
         patch("app.main.salir_a_comprar") as salir:
        respuesta = _cliente.post("/compras/que-comprar",
                                  data={"accion": "pdf", "carga": ["11", "13"], "kilaje_1": "18"},
                                  follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/que-comprar/pdf"
    _hoy, cargas, kilajes = guardar.call_args.args
    assert cargas == {11, 13} and kilajes == {1: 18.0}
    salir.assert_not_called()                     # sacar el PDF no es salir a comprar


def test_si_GUARDAR_FALLA_el_PDF_no_sale_con_lo_viejo():
    with patch.dict(os.environ, _CLAVE), \
         patch("app.main.guardar_borrador_de_compra", side_effect=RuntimeError("caida")):
        respuesta = _cliente.post("/compras/que-comprar", data={"accion": "pdf"},
                                  follow_redirects=False)
    assert respuesta.headers["location"] == "/compras/que-comprar?error=guardar"


def test_el_PDF_nombra_SOLO_las_cargas_TILDADAS_y_de_cuando_es_el_stock():
    respuesta = _pdf(_contexto(elegidas=(11, 13)))
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    # INLINE: en el celular se abre para leer o imprimir.
    assert respuesta.headers["content-disposition"].startswith("inline;")
    texto, _p = _texto_pdf(respuesta.content)
    assert "EJEMPLO Dia 27/09 (del promedio, 10% más)" in texto
    assert "EJEMPLO Tailem 28/09 (a mano)" in texto
    assert "EJEMPLO Dia 28/09" not in texto        # la carga NO tildada no va
    assert "todavía no saliste" in texto


def test_despues_de_SALIR_el_PDF_dice_la_hora_de_la_foto():
    salio = datetime(2026, 9, 28, 7, 40, tzinfo=_main.ARGENTINA)
    texto, _p = _texto_pdf(_pdf(_contexto(salio_el=salio)).content)
    assert "stock al salir, 28/09 07:40" in texto
    assert "todavía no saliste" not in texto


def test_las_compras_VIEJAS_van_al_papel_igual_que_a_la_pantalla():
    viejas = [{"nombre": "EJEMPLO Pera", "compras": 1, "cajones": 5.0, "desde": date(2026, 9, 20)}]
    texto, _p = _texto_pdf(_pdf(_contexto(viejas=viejas)).content)
    assert "NO se cuentan" in texto and "EJEMPLO Pera (5 cj, desde el 20/09)" in texto


def test_sin_filas_el_PDF_lo_DICE_en_vez_de_salir_en_blanco():
    texto, _p = _texto_pdf(_pdf(_contexto(filas=[], elegidas=())).content)
    assert "No hay cargas tildadas." in texto and "ninguna tildada" in texto
    texto, _p = _texto_pdf(_pdf(_contexto(filas=[])).content)
    assert "Esas cargas no piden nada." in texto


# --- 3. ACTUALIZAR ARRIBA, Y EL GUARDAR DE ABAJO SIGUE ----------------------


def test_ACTUALIZAR_y_PDF_van_ARRIBA_de_los_tildes_y_el_GUARDAR_de_abajo_sigue():
    """Por la posición en el marcado: los dos antes del primer tilde, y el
    Guardar después de la última tarjeta. Los tres con su `accion`: sin el
    name, el POST no sabe qué hacer y cae en guardar."""
    marcado = _render(_contexto()).split("</style>")[-1]
    arriba = marcado.index('<div class="arriba">')
    primer_tilde = marcado.index('name="carga"')
    actualizar = marcado.index('class="actualizar" type="submit" name="accion" value="guardar"')
    pdf = marcado.index('class="pdf" type="submit" name="accion" value="pdf"')
    guardar = marcado.index('class="guardar" type="submit" name="accion" value="guardar"')
    ultima_tarjeta = marcado.rindex("data-articulo=")
    assert arriba < actualizar < primer_tilde and arriba < pdf < primer_tilde
    assert ultima_tarjeta < guardar
    assert marcado.count('value="pdf"') == 1 and marcado.count('value="guardar"') == 2


def _medir_arriba(html):
    pytest.importorskip("playwright", reason="la posición en pantalla necesita un navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        leido = pagina.evaluate("""() => {
          const caja = s => { const e = document.querySelector(s); const r = e.getBoundingClientRect();
                              return {abajo: r.bottom, alto: r.height, ancho: r.width,
                                      visible: getComputedStyle(e).display !== 'none'}; };
          return {actualizar: caja('.actualizar'), pdf: caja('.pdf'),
                  tildes: document.querySelectorAll('input[name="carga"]').length,
                  desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth};
        }""")
        navegador.close()
    return leido


def test_a_390px_ACTUALIZAR_se_ve_SIN_BAJAR_aunque_haya_muchas_cargas():
    """Medido en el navegador y no en el marcado (corolario 32): el efecto, no
    la intención. Con diez clientes de tres fechas —treinta tildes— el botón
    tiene que estar en la primera pantalla de un celular, y los dos botones
    tocables (44px como mínimo) sin desbordar de costado."""
    cargas = [{"id": 100 + i * 3 + d, "cliente_id": i, "cliente_nombre": f"EJEMPLO Cliente{i}",
               "fecha": date(2026, 9, 26 + d), "modo": "manual", "margen_porcentaje": 0,
               "usada_en_otros": 0} for i in range(10) for d in range(3)]
    leido = _medir_arriba(_render(_contexto(cargas=cargas, elegidas=())))
    assert leido["tildes"] == 30                 # el denominador: la pantalla larga de verdad
    for boton in ("actualizar", "pdf"):
        assert leido[boton]["visible"] and leido[boton]["abajo"] <= 844, boton
        assert leido[boton]["alto"] >= 44, boton
    assert leido["desborde"] == 0


# --- 4. EN EL PAPEL, CERO Y "NO SE SABE" QUEDAN EN BLANCO (dueño, 28/09) -----


@pytest.mark.parametrize("pantalla, papel", [
    ("OK", ""), ("—", ""), ("no se puede saber", ""), ("no se sabe la unidad", ""),
    ("poné el por bulto", ""), ("0 cj", ""), ("0 kg", ""), ("0", ""),
    # Los RIVALES: parecen cero y no lo son.
    ("0.5 kg", "0.5 kg"), ("10 cj", "10 cj"), ("3 cj", "3 cj"), ("2.2 blt", "2.2 blt"),
])
def test_el_papel_deja_en_BLANCO_el_cero_y_lo_que_no_se_sabe(pantalla, papel):
    """"Un espacio vacío se puede llenar con la lapicera; un cero impreso no." """
    assert para_el_papel(pantalla) == papel


def test_una_fila_SIN_NADA_QUE_DECIR_sale_con_las_celdas_VACIAS():
    """Todo en cero o sin saber: lo único impreso es el nombre, de quién sale,
    y lo pedido. El RIVAL es la fila normal de al lado, que sí imprime sus
    números: sin ella, un PDF que blanqueara todo pasaría igual."""
    vacia = _fila(1, "EJEMPLO Vacia", en_piso=None, de_partida=None, falta=None, cajones=None,
                  a_comprar=None, a_comprar_magnitud=None, stock_bultos=None, kilaje=None,
                  pide_bultos=None, comprado_cajones=0.0, en_camino_cajones=0.0)
    normal = _fila(2, "EJEMPLO Normal")
    texto, _p = _texto_pdf(generar_pdf_que_comprar(
        "x", ["EJEMPLO Dia 27/09"], [vacia, normal], _main._formatear_numero,
        _main._formatear_sin_decimales))
    fila_vacia = texto[texto.index("EJEMPLO Vacia"):texto.index("EJEMPLO Normal")]
    assert fila_vacia.split() == ["EJEMPLO", "Vacia", "EJEMPLO", "Dia", "26/09", "240", "240", "kg"]
    fila_normal = texto[texto.index("EJEMPLO Normal"):]
    for dato in ("18 kg", "13", "2 blt", "40 kg", "12 cj", "3 cj", "9 cj"):
        assert dato in fila_normal, dato
    # "En camino" de la normal es cero: también en blanco.
    assert "0 cj" not in fila_normal


def test_el_boton_dice_EXPORTAR_y_no_Sacar_PDF():
    """"Sacar PDF" no se entendía (dueño, 28/09). La jerga que no puede
    aparecer se pregunta también, no solo el texto bueno."""
    marcado = _render(_contexto()).split("</style>")[-1]
    assert '<button class="pdf" type="submit" name="accion" value="pdf">Exportar</button>' in marcado
    assert "Sacar PDF" not in marcado
