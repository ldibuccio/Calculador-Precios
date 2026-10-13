"""RENDIMIENTOS en Excel y PDF — puro, sin tocar la base (dueño, 13/10).

Recibe lo que ya armó `core.rendimientos.armar_rendimientos` para la pantalla,
con los MISMOS filtros (período y artículo), y el encabezado dice qué se
filtró. Acá no se recalcula nada.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.platypus import Paragraph, Spacer

from core.exportar_vacios import VERDE_ENCABEZADO_HEX, _documento_pdf, _estilos_pdf, _tabla_seccion_pdf
from core.rendimientos import texto_de_la_perdida

TITULO = "Rendimientos"
ENCABEZADOS_CON_GUIA = ("Artículo", "Kg que entraron", "% primera", "% segunda", "% merma",
                        "% falta sin registrar", "% pérdida total", "% pérdida en la ficha")
ENCABEZADOS_SIN_GUIA = ("Artículo", "Kg por cajón comprado", "Kg por bulto enviado", "Diferencia",
                        "Qué pasa", "% pérdida en la ficha")


def subtitulo(desde, hasta, articulo_nombre: str | None) -> str:
    """Lo que se filtró, como lo dice la pantalla."""
    texto = f"Del {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}"
    return texto + (f" · {articulo_nombre}" if articulo_nombre else " · todos los artículos")


def _pct(valor) -> str:
    return "—" if valor is None else f"{valor:.1f}%".replace(".", ",")


def _kg(valor) -> str:
    return "—" if valor is None else f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _filas_con_guia(datos: dict) -> list[list[str]]:
    return [[f["articulo"], _kg(f["entraron"]), _pct(f["primera_pct"]), _pct(f["segunda_pct"]),
             _pct(f["merma_pct"]), _pct(f["falta_pct"]), _pct(f["perdida_total_pct"]),
             texto_de_la_perdida(f["perdida_ficha"])] for f in datos["con_guia"]]


def _filas_sin_guia(datos: dict) -> list[list[str]]:
    return [[f["articulo"], _kg(f["kg_por_cajon"]), _kg(f["kg_por_bulto"]), _pct(f["diferencia_pct"]),
             f["que_pasa"] or "—", texto_de_la_perdida(f["perdida_ficha"])] for f in datos["sin_guia"]]


def generar_excel_rendimientos(datos: dict, desde, hasta, articulo_nombre: str | None) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Rendimientos"
    hoja.cell(row=1, column=1, value=TITULO).font = Font(bold=True, size=14)
    hoja.cell(row=2, column=1, value=subtitulo(desde, hasta, articulo_nombre))
    relleno = PatternFill(start_color="DEEFE3", end_color="DEEFE3", fill_type="solid")
    fila = 4
    for titulo, encabezados, filas in (
            ("Pasan por guía R", ENCABEZADOS_CON_GUIA, _filas_con_guia(datos)),
            ("No pasan por guía R", ENCABEZADOS_SIN_GUIA, _filas_sin_guia(datos))):
        hoja.cell(row=fila, column=1, value=titulo).font = Font(bold=True, size=12)
        fila += 1
        for columna, encabezado in enumerate(encabezados, start=1):
            celda = hoja.cell(row=fila, column=columna, value=encabezado)
            celda.font = Font(bold=True, color=VERDE_ENCABEZADO_HEX)
            celda.fill = relleno
        fila += 1
        for valores in filas:
            for columna, valor in enumerate(valores, start=1):
                hoja.cell(row=fila, column=columna, value=valor)
            fila += 1
        if not filas:
            hoja.cell(row=fila, column=1, value="Nada en el período.")
            fila += 1
        fila += 1
    hoja.column_dimensions["A"].width = 26
    for letra in "BCDEFGH":
        hoja.column_dimensions[letra].width = 16
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def generar_pdf_rendimientos(datos: dict, desde, hasta, articulo_nombre: str | None) -> bytes:
    buffer = BytesIO()
    documento, encabezado = _documento_pdf(buffer, TITULO, subtitulo(desde, hasta, articulo_nombre))
    estilos = _estilos_pdf()
    ancho = documento.width

    con = _filas_con_guia(datos)
    sin = _filas_sin_guia(datos)
    elementos = [
        _tabla_seccion_pdf("Pasan por guía R", list(ENCABEZADOS_CON_GUIA),
                           [[Paragraph(str(v), estilos["dato"] if i == 0 else estilos["numero"])
                             for i, v in enumerate(f)] for f in con]
                           or [[Paragraph("Nada en el período.", estilos["dato_gris"])] + [""] * 7],
                           [ancho * 0.19] + [ancho * 0.115] * 7, estilos),
        Spacer(1, 12),
        _tabla_seccion_pdf("No pasan por guía R", list(ENCABEZADOS_SIN_GUIA),
                           [[Paragraph(str(v), estilos["dato"] if i == 0 else estilos["numero"])
                             for i, v in enumerate(f)] for f in sin]
                           or [[Paragraph("Nada en el período.", estilos["dato_gris"])] + [""] * 5],
                           [ancho * 0.24, ancho * 0.15, ancho * 0.15, ancho * 0.13, ancho * 0.18, ancho * 0.15],
                           estilos),
    ]
    documento.build(elementos, onFirstPage=encabezado, onLaterPages=encabezado)
    return buffer.getvalue()
