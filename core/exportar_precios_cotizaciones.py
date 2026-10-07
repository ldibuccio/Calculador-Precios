"""PRECIOS COTIZACIONES en Excel y PDF (dueño, 07/10) — puro, sin base.

Las filas llegan armadas desde la pantalla (`calcular_precios_sugeridos` más
el precio que quedó en cada casillero, corregido o no): el archivo y la
pantalla no pueden decir números distintos. El encabezado dice el cliente,
la fecha y las condiciones con que se calculó.
"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.platypus import Paragraph

from core.exportar_vacios import VERDE_ENCABEZADO_HEX, _documento_pdf, _estilos_pdf, _tabla_seccion_pdf

TITULO = "Precios Cotizaciones"
ENCABEZADOS = ("Ficha", "Costo de compra", "De qué compras", "Envase", "Sugerido", "Precio")


def _pesos(valor) -> str:
    if valor is None:
        return ""
    entero = round(float(valor))
    return ("-" if entero < 0 else "") + "$" + f"{abs(entero):,}".replace(",", ".")


def texto_de_las_compras(fila: dict) -> str:
    """Las compras de las que sale el costo, en una línea. Las que no entraron, con su motivo."""
    if fila["sin_costo"] and not fila["compras_del_costo"]:
        return fila["sin_costo"]
    partes = []
    for compra in fila["compras_del_costo"]:
        texto = f"{compra['fecha_operacion'].strftime('%d/%m')} {compra['proveedor_nombre'] or ''}".strip()
        if compra["entra"]:
            texto += f" {_pesos(compra['importe'])} × {compra['cantidad_cajones']:g}"
        else:
            texto += f" (no entra: {compra['motivo']})"
        partes.append(texto)
    return " · ".join(partes)


def _costo(fila: dict) -> str:
    if fila["costo_actual"] is None:
        return f"sin costo ({fila['sin_costo']})"
    return f"{_pesos(fila['costo_actual'])} por {fila['unidad_venta']}"


def _sugerido(fila: dict) -> str:
    if fila["precio_sugerido"] is None:
        return fila["sin_sugerido"] or "sin costo"
    return _pesos(fila["precio_sugerido"])


def _precio(fila: dict) -> str:
    if fila["precio"] is None:
        return ""
    return _pesos(fila["precio"]) + (" (a mano)" if fila["corregido"] else "")


def _valores(fila: dict) -> tuple:
    return (fila["ficha_nombre"], _costo(fila), texto_de_las_compras(fila),
            _pesos(fila["costo_envase_unidad_venta"]), _sugerido(fila), _precio(fila))


def generar_excel_precios_cotizaciones(encabezado: str, condiciones: str, filas: list[dict]) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Precios Cotizaciones"
    hoja.cell(row=1, column=1, value=TITULO).font = Font(bold=True, size=14)
    hoja.cell(row=2, column=1, value=encabezado)
    hoja.cell(row=3, column=1, value=condiciones)
    relleno = PatternFill(start_color="DEEFE3", end_color="DEEFE3", fill_type="solid")
    for columna, titulo in enumerate(ENCABEZADOS, start=1):
        celda = hoja.cell(row=5, column=columna, value=titulo)
        celda.font = Font(bold=True, color=VERDE_ENCABEZADO_HEX)
        celda.fill = relleno
    for renglon, fila in enumerate(filas, start=6):
        for columna, valor in enumerate(_valores(fila), start=1):
            hoja.cell(row=renglon, column=columna, value=valor)
    for letra, ancho in zip("ABCDEF", (26, 26, 50, 12, 26, 18)):
        hoja.column_dimensions[letra].width = ancho
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def generar_pdf_precios_cotizaciones(encabezado: str, condiciones: str, filas: list[dict]) -> bytes:
    buffer = BytesIO()
    documento, dibujar_encabezado = _documento_pdf(buffer, TITULO, f"{encabezado} · {condiciones}")
    estilos = _estilos_pdf()
    ancho = documento.width
    datos = [[Paragraph(_escapar(texto), estilos["dato"]) for texto in _valores(fila)] for fila in filas]
    anchos = [ancho * p for p in (0.18, 0.17, 0.30, 0.09, 0.13, 0.13)]
    elementos = [_tabla_seccion_pdf("Fichas del cliente", list(ENCABEZADOS), datos, anchos, estilos)]
    documento.build(elementos, onFirstPage=dibujar_encabezado, onLaterPages=dibujar_encabezado)
    return buffer.getvalue()


def _escapar(texto) -> str:
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
