"""Genera la Lista de Precios en PDF y Excel — puro, sin tocar la base ni la red.

Recibe los datos ya armados (ver "filas" en cada función) y devuelve los
bytes del archivo. No sabe nada de clientes, fichas ni de la base — eso lo
resuelve quien llama (app/main.py). Así se puede reusar tal cual desde
/precios/consultar y, más adelante, desde "Guardar y generar listado" en
la carga de precios, sin duplicar nada.

Los archivos son temporarios: esto solo arma bytes en memoria, nunca los
guarda en ningún lado.
"""

from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

VERDE_ENCABEZADO = colors.Color(0.18, 0.55, 0.34)
ROJO_PRECIO_NUEVO = colors.Color(0.80, 0.10, 0.10)
GRIS_TEXTO_AYUDA = colors.Color(0.35, 0.35, 0.35)
VERDE_ENCABEZADO_HEX = "2E8C57"  # equivalente aproximado de (0.18, 0.55, 0.34) en hex, para Excel
ROJO_PRECIO_NUEVO_HEX = "CC1A1A"
ROJO_FONDO_CLARO_HEX = "FCE4E4"

# Orden fijo de las secciones — "pesada" se suma a fruta/hortaliza; lo que
# no tiene ninguno de los 3 grupos válidos cae en "Sin clasificar", al
# final, para que se note en vez de perderse.
ORDEN_GRUPOS = [
    ("fruta", "FRUTA"),
    ("hortaliza", "HORTALIZA"),
    ("pesada", "PESADA"),
    (None, "SIN CLASIFICAR"),
]

TEXTO_UNIDAD = {"kilo": "por kilo", "unidad": "por unidad", "cubeta": "por cubeta"}


def _texto_unidad(unidad) -> str:
    return TEXTO_UNIDAD.get(unidad, "—")


def _formatear_moneda(valor) -> str:
    """"$45.000": símbolo $, "." cada tres cifras, redondeado al peso entero — mismo criterio que el resto de la app."""
    entero = round(float(valor))
    negativo = entero < 0
    texto = f"{abs(entero):,}".replace(",", ".")
    return f"${'-' if negativo else ''}{texto}"


def _agrupar_y_ordenar_filas(filas: list[dict]) -> dict:
    """Agrupa las filas por grupo (fruta/hortaliza/pesada/sin clasificar) y ordena cada sección por nombre."""
    grupos: dict = {"fruta": [], "hortaliza": [], "pesada": [], None: []}
    for fila in filas:
        clave = fila.get("grupo") if fila.get("grupo") in ("fruta", "hortaliza", "pesada") else None
        grupos[clave].append(fila)
    for lista_filas in grupos.values():
        lista_filas.sort(key=lambda f: f["articulo_nombre"])
    return grupos


LEYENDA_PRECIO_NUEVO = "Nuevo precio indica los productos cuyo precio fue actualizado."
PIE_PAGINA = "* Todos los precios están expresados en pesos y no incluyen IVA."


ALTURA_BANDA_ENCABEZADO = 24 * mm


def _dibujar_banda_encabezado(canvas, documento):
    """Pinta la banda verde con "Lista de Precios" directo en el canvas, de punta a punta de la hoja.

    Se dibuja así (no como Table/Paragraph dentro del flujo normal) porque
    un flowable queda acotado por los márgenes del documento — para que el
    color llegue de borde a borde de la página hay que pintarlo antes, en
    el canvas crudo, en cada página (onFirstPage/onLaterPages).
    """
    ancho_pagina, alto_pagina = A4
    canvas.saveState()
    canvas.setFillColor(VERDE_ENCABEZADO)
    canvas.rect(0, alto_pagina - ALTURA_BANDA_ENCABEZADO, ancho_pagina, ALTURA_BANDA_ENCABEZADO, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawCentredString(ancho_pagina / 2, alto_pagina - ALTURA_BANDA_ENCABEZADO / 2 - 7, "Lista de Precios")
    canvas.restoreState()


def generar_pdf_lista_precios(cliente_nombre: str, fecha: date, filas: list[dict], es_hoy: bool) -> bytes:
    """Arma el PDF de la Lista de Precios de un cliente a una fecha, con el formato ya definido.

    filas: [{"articulo_nombre", "grupo", "precio", "unidad", "es_nuevo"}, ...]. es_hoy indica si la
    fecha exportada es HOY — si no lo es, ningún precio se resalta como nuevo aunque
    fila["es_nuevo"] venga en True (quien arma "filas" ya debería respetar esto, pero se vuelve a
    chequear acá para no depender de que el llamador no se equivoque).
    """
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=ALTURA_BANDA_ENCABEZADO + 8 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    ancho_util = documento.width

    estilo_normal = ParagraphStyle("normal", fontName="Helvetica", fontSize=10, textColor=colors.black, leading=13)
    estilo_ayuda = ParagraphStyle("ayuda", fontName="Helvetica-Oblique", fontSize=9, textColor=GRIS_TEXTO_AYUDA)
    estilo_seccion = ParagraphStyle(
        "seccion", fontName="Helvetica-Bold", fontSize=13, textColor=VERDE_ENCABEZADO, spaceBefore=14, spaceAfter=6
    )
    estilo_encabezado_tabla = ParagraphStyle(
        "encabezado_tabla", fontName="Helvetica-Bold", fontSize=9.5, textColor=colors.white
    )
    estilo_producto = ParagraphStyle("producto", fontName="Helvetica", fontSize=9.5, textColor=colors.black)
    estilo_precio = ParagraphStyle("precio", fontName="Helvetica-Bold", fontSize=9.5, textColor=colors.black)
    estilo_precio_nuevo = ParagraphStyle(
        "precio_nuevo", fontName="Helvetica-Bold", fontSize=9.5, textColor=ROJO_PRECIO_NUEVO
    )
    estilo_badge_nuevo = ParagraphStyle(
        "badge_nuevo", fontName="Helvetica-Bold", fontSize=7, textColor=ROJO_PRECIO_NUEVO, spaceBefore=1
    )
    estilo_unidad = ParagraphStyle("unidad", fontName="Helvetica", fontSize=9.5, textColor=GRIS_TEXTO_AYUDA)

    elementos = []

    fecha_texto = fecha.strftime("%d/%m/%Y")
    elementos.append(Paragraph(f"Cliente: {cliente_nombre}", estilo_normal))
    elementos.append(Paragraph(f"Vigencia: {fecha_texto} · Precios + IVA", estilo_normal))
    elementos.append(Spacer(1, 6))
    elementos.append(Paragraph(LEYENDA_PRECIO_NUEVO, estilo_ayuda))

    grupos = _agrupar_y_ordenar_filas(filas)
    for clave, titulo in ORDEN_GRUPOS:
        filas_grupo = grupos[clave]
        if not filas_grupo:
            continue

        elementos.append(Paragraph(titulo, estilo_seccion))

        datos_tabla = [
            [
                Paragraph("Producto", estilo_encabezado_tabla),
                Paragraph("Precio", estilo_encabezado_tabla),
                Paragraph("Unidad", estilo_encabezado_tabla),
            ]
        ]
        for fila in filas_grupo:
            es_nueva = es_hoy and bool(fila.get("es_nuevo"))
            precio_texto = _formatear_moneda(fila["precio"])
            if es_nueva:
                celda_precio = [
                    Paragraph(precio_texto, estilo_precio_nuevo),
                    Paragraph("Nuevo precio", estilo_badge_nuevo),
                ]
            else:
                celda_precio = Paragraph(precio_texto, estilo_precio)
            datos_tabla.append(
                [
                    Paragraph(fila["articulo_nombre"], estilo_producto),
                    celda_precio,
                    Paragraph(_texto_unidad(fila.get("unidad")), estilo_unidad),
                ]
            )

        tabla = Table(datos_tabla, colWidths=[ancho_util * 0.5, ancho_util * 0.25, ancho_util * 0.25], repeatRows=1)
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), VERDE_ENCABEZADO),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.Color(0.85, 0.85, 0.85)),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elementos.append(tabla)

    elementos.append(Spacer(1, 16))
    elementos.append(Paragraph(PIE_PAGINA, estilo_ayuda))

    documento.build(elementos, onFirstPage=_dibujar_banda_encabezado, onLaterPages=_dibujar_banda_encabezado)
    return buffer.getvalue()


def generar_excel_lista_precios(cliente_nombre: str, fecha: date, filas: list[dict], es_hoy: bool) -> bytes:
    """Arma el Excel de la Lista de Precios de un cliente a una fecha, mismas secciones y columnas que el PDF."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Lista de Precios"

    relleno_verde = PatternFill(start_color=VERDE_ENCABEZADO_HEX, end_color=VERDE_ENCABEZADO_HEX, fill_type="solid")
    fuente_blanca_titulo = Font(color="FFFFFF", bold=True, size=16)
    fuente_normal = Font(size=10)
    fuente_ayuda = Font(size=9, italic=True, color="595959")
    fuente_seccion = Font(bold=True, size=12, color=VERDE_ENCABEZADO_HEX)
    fuente_encabezado_tabla = Font(bold=True, color="FFFFFF")
    relleno_rojo_claro = PatternFill(start_color=ROJO_FONDO_CLARO_HEX, end_color=ROJO_FONDO_CLARO_HEX, fill_type="solid")
    fuente_precio_nuevo = Font(bold=True, color=ROJO_PRECIO_NUEVO_HEX)

    fila_actual = 1
    hoja.cell(row=fila_actual, column=1, value="Lista de Precios")
    for columna in range(1, 4):
        celda = hoja.cell(row=fila_actual, column=columna)
        celda.fill = relleno_verde
        if columna == 1:
            celda.font = fuente_blanca_titulo
    fila_actual += 1

    hoja.cell(row=fila_actual, column=1, value=f"Cliente: {cliente_nombre}").font = fuente_normal
    fila_actual += 1
    fecha_texto = fecha.strftime("%d/%m/%Y")
    hoja.cell(row=fila_actual, column=1, value=f"Vigencia: {fecha_texto} · Precios + IVA").font = fuente_normal
    fila_actual += 1
    hoja.cell(row=fila_actual, column=1, value=LEYENDA_PRECIO_NUEVO).font = fuente_ayuda
    fila_actual += 2

    grupos = _agrupar_y_ordenar_filas(filas)
    for clave, titulo in ORDEN_GRUPOS:
        filas_grupo = grupos[clave]
        if not filas_grupo:
            continue

        hoja.cell(row=fila_actual, column=1, value=titulo).font = fuente_seccion
        fila_actual += 1

        for columna, encabezado in enumerate(("Producto", "Precio", "Unidad"), start=1):
            celda = hoja.cell(row=fila_actual, column=columna, value=encabezado)
            celda.font = fuente_encabezado_tabla
            celda.fill = relleno_verde
        fila_actual += 1

        for fila in filas_grupo:
            es_nueva = es_hoy and bool(fila.get("es_nuevo"))

            hoja.cell(row=fila_actual, column=1, value=fila["articulo_nombre"])

            celda_precio = hoja.cell(row=fila_actual, column=2, value=float(fila["precio"]))
            celda_precio.number_format = '"$"#,##0'
            if es_nueva:
                celda_precio.font = fuente_precio_nuevo
                celda_precio.fill = relleno_rojo_claro

            celda_unidad = hoja.cell(row=fila_actual, column=3, value=_texto_unidad(fila.get("unidad")))
            if es_nueva:
                celda_unidad.fill = relleno_rojo_claro

            fila_actual += 1

        fila_actual += 1  # renglón en blanco entre secciones

    fila_actual += 1
    hoja.cell(row=fila_actual, column=1, value=PIE_PAGINA).font = fuente_ayuda

    hoja.column_dimensions[get_column_letter(1)].width = 32
    hoja.column_dimensions[get_column_letter(2)].width = 14
    hoja.column_dimensions[get_column_letter(3)].width = 14

    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
