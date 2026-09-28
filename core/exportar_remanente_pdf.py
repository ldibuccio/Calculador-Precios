"""El Stock del Depósito en PDF, filtrado por tipo — puro, sin tocar la base.

Es EL PAPEL PARA BAJAR AL DEPÓSITO (dueño, 28/09): "el listado de segunda lo
voy a usar para bajar a controlar o para armar un remito al Puesto". Por eso:

- A4 VERTICAL, tres columnas: se lee igual impreso que abierto en el celular.
- Una columna "Contado" VACÍA, con recuadro, para anotar con la lapicera.
- El filtro en el TÍTULO: una hoja de solo Segunda con el título de siempre
  se lee, impresa, como el depósito entero.
- Una sección por tipo con su total ARRIBA ("Segunda: 25 bultos en total"),
  que es lo que se controla primero.
- Los negativos con su número real y en rojo, igual que la pantalla.

Las porciones y las secciones llegan armadas: el filtro vive en
core/remanente_por_tipo.py y lo usan la pantalla, el Excel y esto. Acá no se
decide qué es "segunda".
"""

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from core.exportar_vacios import _documento_pdf, _estilos_pdf, _tabla_seccion_pdf

ROJO_NEGATIVO_HEX = "#B91C1C"
TITULO = "Stock del Depósito"
ENCABEZADOS = ("Producto", "Sistema", "Contado")


def _escapar(texto) -> str:
    """Paragraph de reportlab lee marcado: un "<" en un nombre rompería el PDF."""
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _en_rojo_si_negativo(texto: str, valor: float) -> str:
    if valor < 0:
        return f"<font color='{ROJO_NEGATIVO_HEX}'><b>{texto}</b></font>"
    return texto


def titulo_del_pdf(filtro: str) -> str:
    return f"{TITULO} — {filtro}"


def generar_pdf_remanente(fecha: date, secciones: list[dict], filtro: str, numero,
                          *, es_hoy: bool = True) -> bytes:
    """secciones: [{"rotulo", "total", "porciones": [{"nombre", "bultos"}]}], ya filtradas.

    `numero` es el formateador de la pantalla (_formatear_numero): el papel
    escribe los números igual que se leen en el celular.
    """
    buffer = BytesIO()
    documento, encabezado = _documento_pdf(buffer, titulo_del_pdf(filtro),
                                           f"Al {fecha.strftime('%d/%m/%Y')} · Filtro: {filtro}")
    estilos = _estilos_pdf()
    estilos["total"] = ParagraphStyle("total", parent=estilos["titulo_tabla"], fontSize=12.5)
    ancho = documento.width
    anchos = [ancho * 0.60, ancho * 0.17, ancho * 0.23]
    elementos = []

    if not es_hoy:
        elementos += [Paragraph(
            f"Así estaba el depósito al cierre del {fecha.strftime('%d/%m/%Y')}. "
            "No es el stock de ahora.", estilos["aviso"]), Spacer(1, 3 * mm)]

    for seccion in secciones:
        total = _en_rojo_si_negativo(numero(seccion["total"]), float(seccion["total"]))
        titulo = f"{_escapar(seccion['rotulo'])}: {total} bultos en total"
        if not seccion["porciones"]:
            elementos += [Paragraph(titulo, estilos["total"]), Spacer(1, 2 * mm),
                          Paragraph("No hay bultos de este tipo.", estilos["vacio"]),
                          Spacer(1, 6 * mm)]
            continue
        filas = []
        for porcion in seccion["porciones"]:
            bultos = float(porcion["bultos"])
            filas.append([
                Paragraph(_escapar(porcion["nombre"]), estilos["dato"]),
                Paragraph(_en_rojo_si_negativo(numero(bultos), bultos), estilos["numero"]),
                "",  # CONTADO: vacío a propósito, para la lapicera.
            ])
        tabla = _tabla_seccion_pdf(titulo, list(ENCABEZADOS), filas, anchos,
                                   {**estilos, "titulo_tabla": estilos["total"]})
        # El recuadro de la columna Contado: una línea sola abajo no alcanza
        # para escribir derecho con el papel apoyado en un cajón.
        tabla.setStyle([
            ("BOX", (2, 2), (2, -1), 0.8, colors.black),
            ("INNERGRID", (2, 2), (2, -1), 0.8, colors.black),
            ("TOPPADDING", (0, 2), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 2), (-1, -1), 9),
        ])
        elementos += [tabla, Spacer(1, 6 * mm)]

    documento.build(elementos, onFirstPage=encabezado, onLaterPages=encabezado)
    return buffer.getvalue()
