from datetime import date
from io import BytesIO

import openpyxl

from core.exportar_rentabilidad_real import generar_excel_rentabilidad_real, generar_pdf_rentabilidad_real

RESULTADO_REAL = {
    "grupos": [
        {
            "grupo": "fruta",
            "etiqueta": "Fruta",
            "filas": [
                {
                    "articulo_id": 1, "articulo_nombre": "Banana", "grupo": "fruta",
                    "bultos": 10.0, "unidades": 160.0, "venta_neta": 14400.0,
                    "costo_mercaderia": 5000.0, "costo_envase": 320.0,
                    "costo_mermas": 1500.0, "bultos_mermados": 3.0, "segunda_bultos": 2.0,
                    "devoluciones_bultos": 5.0, "devoluciones_venta": 4500.0,
                    "rechazos_perdidos": 900.0, "rechazos_bultos": 2.0,
                    "costo_total": 6820.0, "renta_pesos": 3080.0, "utilidad_pct": 61.6,
                }
            ],
            "subtotal": {"bultos": 10.0, "venta_neta": 14400.0, "costo_mercaderia": 5000.0,
                         "costo_envase": 320.0, "costo_mermas": 1500.0, "costo_total": 6820.0,
                         "devoluciones_bultos": 5.0, "devoluciones_venta": 4500.0,
                         "rechazos_perdidos": 900.0, "rechazos_bultos": 2.0,
                         "renta_pesos": 3080.0, "utilidad_pct": 61.6},
        }
    ],
    "totales": {
        "bultos": 10.0, "venta_neta": 14400.0, "costo_mercaderia": 5000.0, "costo_envase": 320.0,
        "costo_mermas": 1500.0, "segunda_bultos": 2.0, "costo_total": 6820.0,
        "devoluciones_bultos": 5.0, "devoluciones_venta": 4500.0,
        "rechazos_perdidos": 900.0, "rechazos_bultos": 2.0,
        "renta_pesos": 3080.0, "utilidad_pct": 61.6, "afuera_bultos": 18.0, "afuera_motivos": 2,
    },
    "afuera_por_motivo": [
        {"motivo": "ajuste_sin_costo", "etiqueta": "Consumió stock inicial u otro ajuste (sin costo posible)",
         "bultos": 14.0, "articulos": [{"nombre": "Anco", "bultos": 14.0}]},
        {"motivo": "sin_kilaje", "etiqueta": "Renglón armado sin kilaje cargado",
         "bultos": 4.0, "articulos": [{"nombre": "Kiwi", "bultos": 4.0}]},
    ],
    "fechas_incluidas": [date(2026, 8, 25)],
}


def test_generar_pdf_rentabilidad_real_arma_un_pdf():
    pdf = generar_pdf_rentabilidad_real(date(2026, 8, 18), date(2026, 8, 25), ["cliente Día"], RESULTADO_REAL)
    assert pdf.startswith(b"%PDF")


def test_generar_excel_rentabilidad_real_lleva_la_cuenta_y_el_afuera():
    excel = generar_excel_rentabilidad_real(date(2026, 8, 18), date(2026, 8, 25), ["cliente Día"], RESULTADO_REAL)
    hoja = openpyxl.load_workbook(BytesIO(excel)).active

    assert hoja.title == "Rentabilidad Real"
    valores = [str(celda.value) for fila in hoja.iter_rows() for celda in fila if celda.value is not None]
    texto = "\n".join(valores)
    # El subtítulo lleva la regla de la cuenta REAL, para que el archivo
    # se explique solo.
    assert "venta = lo ENVIADO" in texto
    assert "costo FIFO" in texto
    assert "la segunda vale cero" in texto
    # El AFUERA va incluido, con bultos y artículos por motivo — en el
    # papel también es protagonista.
    assert "AFUERA DEL CÁLCULO" in texto
    assert "Consumió stock inicial u otro ajuste (sin costo posible)" in texto
    assert "Anco (14)" in texto
    # La cuenta: mermas, segunda y devoluciones con sus columnas.
    assert "Mermas $" in texto
    assert "Segunda bultos" in texto
    assert "Devol. bultos" in texto
    assert "Devoluciones $" in texto
    assert "Banana" in texto
    assert "Total REAL" in texto


def test_exports_reales_sin_datos_no_rompen():
    vacio = {"grupos": [], "totales": {"bultos": 0, "venta_neta": 0, "costo_mercaderia": 0,
                                       "costo_envase": 0, "costo_mermas": 0, "segunda_bultos": 0,
                                       "costo_total": 0, "renta_pesos": 0, "utilidad_pct": None,
                                       "afuera_bultos": 0, "afuera_motivos": 0},
             "afuera_por_motivo": [], "fechas_incluidas": []}
    assert generar_pdf_rentabilidad_real(date(2026, 8, 18), date(2026, 8, 25), [], vacio).startswith(b"%PDF")
    hoja = openpyxl.load_workbook(
        BytesIO(generar_excel_rentabilidad_real(date(2026, 8, 18), date(2026, 8, 25), [], vacio))
    ).active
    valores = [str(c.value) for f in hoja.iter_rows() for c in f if c.value is not None]
    assert any("Sin movimientos" in v for v in valores)
