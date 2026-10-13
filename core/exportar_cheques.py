"""CARTERA DE CHEQUES (dueño, 13/10): el listado en PDF y en Excel, con los
mismos filtros que la pantalla y el encabezado que dice cuáles."""
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph

from core.cheques import NOMBRES_DE_ESTADO, total_del_listado
from core.exportar_vacios import (
    VERDE_ENCABEZADO_HEX,
    _documento_pdf,
    _estilos_pdf,
    _tabla_seccion_pdf,
)


def _dia(fecha) -> str:
    return fecha.strftime("%d/%m/%Y") if fecha else ""


def _moneda(valor) -> str:
    if valor is None:
        return ""
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$" + (texto[:-3] if texto.endswith(",00") else texto)


def texto_del_filtro(partes: list[str]) -> str:
    """Las partes ya escritas por la pantalla ("pago del 01/10 al 31/10",
    "banco Galicia"...), o que no hay ninguna."""
    return " · ".join(partes) or "sin filtros: todos los cheques"


ENCABEZADOS = ("Número", "Banco", "Tipo", "De quién", "CUIT librador", "Carga", "Pago", "Importe",
               "Estado", "Concepto", "Proveedor", "Salida", "Acreditado")


def _fila(c: dict) -> tuple:
    return (c["numero"], c["banco"], "ECHEQ" if c["tipo"] == "echeq" else "Físico", c["de_quien"],
            c["cuit_librador"], _dia(c["fecha_carga"]), _dia(c["fecha_pago"]), float(c["importe"]),
            NOMBRES_DE_ESTADO.get(c["estado"], c["estado"]), c.get("concepto") or "",
            c.get("proveedor") or "", _dia(c.get("fecha_salida")), _dia(c.get("acreditado_el")))


def generar_excel_cheques(filtro: str, cheques: list[dict], hoy: date) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Cheques"
    hoja.cell(row=1, column=1, value="Cartera de cheques").font = Font(bold=True, size=14)
    hoja.cell(row=2, column=1, value=f"Al {hoy.strftime('%d/%m/%Y')} · Filtros: {filtro}")
    relleno = PatternFill(start_color="DEEFE3", end_color="DEEFE3", fill_type="solid")
    for columna, encabezado in enumerate(ENCABEZADOS, start=1):
        celda = hoja.cell(row=4, column=columna, value=encabezado)
        celda.font = Font(bold=True, color=VERDE_ENCABEZADO_HEX)
        celda.fill = relleno
    for numero_fila, cheque in enumerate(cheques, start=5):
        for columna, valor in enumerate(_fila(cheque), start=1):
            hoja.cell(row=numero_fila, column=columna, value=valor)
    fila_total = 5 + len(cheques)
    hoja.cell(row=fila_total, column=7, value="Total").font = Font(bold=True)
    hoja.cell(row=fila_total, column=8, value=total_del_listado(cheques)).font = Font(bold=True)
    for indice, ancho in enumerate((12, 18, 8, 26, 14, 11, 11, 14, 16, 18, 22, 11, 11)):
        hoja.column_dimensions[chr(ord("A") + indice)].width = ancho
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def generar_pdf_cheques(filtro: str, cheques: list[dict], hoy: date) -> bytes:
    buffer = BytesIO()
    documento, encabezado = _documento_pdf(buffer, "Cartera de cheques",
                                           f"Al {hoy.strftime('%d/%m/%Y')} · Filtros: {filtro}")
    documento.pagesize = landscape(A4)
    estilos = _estilos_pdf()

    def _p(texto, estilo="dato"):
        texto = str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(texto, estilos[estilo])

    filas = [[_p(c["numero"]), _p(c["banco"]), _p(c["de_quien"]), _p(_dia(c["fecha_carga"])),
              _p(_dia(c["fecha_pago"])), _p(_moneda(c["importe"]), "numero"),
              _p(NOMBRES_DE_ESTADO.get(c["estado"], c["estado"])), _p(c.get("proveedor") or c.get("concepto") or "")]
             for c in cheques] or [[_p("No hay cheques con estos filtros.", "vacio")] + [""] * 7]
    titulo = f"{len(cheques)} cheques · total {_moneda(total_del_listado(cheques))}"
    tabla = _tabla_seccion_pdf(titulo, ["Número", "Banco", "De quién", "Carga", "Pago", "Importe", "Estado",
                                        "Salió a"], filas,
                               [26 * mm, 32 * mm, 50 * mm, 22 * mm, 22 * mm, 30 * mm, 28 * mm, 50 * mm], estilos)
    documento.build([tabla], onFirstPage=encabezado, onLaterPages=encabezado)
    return buffer.getvalue()
