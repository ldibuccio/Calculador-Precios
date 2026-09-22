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
                    # Los $1.800 de merma, abiertos: 2 bultos crudos a $350
                    # y 1 ya trabajado a $800 — el trabajado sale más caro,
                    # que es justo lo que el desglose tiene que dejar ver.
                    "costo_mermas": 1800.0, "bultos_mermados": 3.0,
                    "costo_mermas_cruda": 700.0, "bultos_mermados_cruda": 2.0,
                    "costo_mermas_trabajada": 800.0, "bultos_mermados_trabajada": 1.0, "costo_segunda": 2100.0, "bultos_pasados_a_segunda": 4.0,
                     "cajas_mermadas": 2.0, "cajas_mermadas_pesos": 300.0,
                    "segunda_bultos": 2.0,
                    "devoluciones_bultos": 5.0, "devoluciones_venta": 4500.0,
                    "rechazos_perdidos": 900.0, "rechazos_bultos": 2.0,
                    "costo_total": 9220.0, "renta_pesos": 5180.0, "utilidad_pct": 103.6,
                }
            ],
            "subtotal": {"bultos": 10.0, "venta_neta": 14400.0, "costo_mercaderia": 5000.0,
                         "costo_envase": 320.0, "costo_mermas": 1800.0, "costo_total": 9220.0, "bultos_mermados": 3.0,
                         "costo_mermas_cruda": 700.0, "bultos_mermados_cruda": 2.0,
                         "costo_mermas_trabajada": 800.0, "bultos_mermados_trabajada": 1.0, "costo_segunda": 2100.0, "bultos_pasados_a_segunda": 4.0,
                     "cajas_mermadas": 2.0, "cajas_mermadas_pesos": 300.0,
                         "devoluciones_bultos": 5.0, "devoluciones_venta": 4500.0,
                         "rechazos_perdidos": 900.0, "rechazos_bultos": 2.0,
                         "renta_pesos": 5180.0, "utilidad_pct": 103.6},
        }
    ],
    "totales": {
        "bultos": 10.0, "venta_neta": 14400.0, "costo_mercaderia": 5000.0, "costo_envase": 320.0,
        "costo_mermas": 1800.0, "segunda_bultos": 2.0, "costo_total": 9220.0, "bultos_mermados": 3.0,
        "costo_mermas_cruda": 700.0, "bultos_mermados_cruda": 2.0,
        "costo_mermas_trabajada": 800.0, "bultos_mermados_trabajada": 1.0, "costo_segunda": 2100.0, "bultos_pasados_a_segunda": 4.0,
                     "cajas_mermadas": 2.0, "cajas_mermadas_pesos": 300.0,
        "devoluciones_bultos": 5.0, "devoluciones_venta": 4500.0,
        "rechazos_perdidos": 900.0, "rechazos_bultos": 2.0,
        "renta_pesos": 5180.0, "utilidad_pct": 103.6, "afuera_bultos": 18.0, "afuera_motivos": 2,
    },
    "afuera_por_motivo": [
        {"motivo": "ajuste_sin_costo", "etiqueta": "Consumió un ajuste (sin costo posible)",
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
    assert "Consumió un ajuste (sin costo posible)" in texto
    assert "Anco (14)" in texto
    # La cuenta: mermas, segunda y devoluciones con sus columnas.
    assert "Mermas $" in texto
    assert "Segunda bultos" in texto
    assert "Devol. bultos" in texto
    assert "Devoluciones $" in texto
    assert "Banana" in texto
    assert "Total REAL" in texto


def test_generar_excel_rentabilidad_real_abre_la_merma_al_lado_del_total_de_mermas():
    excel = generar_excel_rentabilidad_real(date(2026, 8, 18), date(2026, 8, 25), ["cliente Día"], RESULTADO_REAL)
    hoja = openpyxl.load_workbook(BytesIO(excel)).active

    encabezados = [c.value for f in hoja.iter_rows() for c in f if c.value == "Mermas $"]
    assert encabezados, "falta la columna Mermas $"
    fila_encabezado = next(f for f in hoja.iter_rows() if f[0].value == "Artículo")
    nombres = [c.value for c in fila_encabezado]
    # El desglose va PEGADO al total de mermas (columnas 7 a 12), para poder
    # sumar o filtrar por "lo trabajado" sin ir a buscarlo al final.
    assert nombres[6:12] == [
        "Mermas $", "Mermas bultos",
        "Mermas crudas $", "Mermas crudas bultos", "Mermas trabajadas $", "Mermas trabajadas bultos",
    ]

    fila_banana = next(f for f in hoja.iter_rows() if f[0].value == "Banana")
    assert fila_banana[6].value == 1800.0   # total de mermas, CON la caja adentro
    assert fila_banana[8].value == 700.0    # crudas $
    assert fila_banana[9].value == 2.0      # crudas bultos
    assert fila_banana[10].value == 800.0   # trabajadas $
    assert fila_banana[11].value == 1.0     # trabajadas bultos
    # LAS PARTES CIERRAN CONTRA EL TOTAL, también en la planilla, y desde el
    # 22/09 son TRES: "Mermas $" lleva la caja adentro, así que sin su columna
    # la resta no se puede hacer y el que abre la planilla ve un total que su
    # desglose contradice.
    assert fila_banana[21].value == 300.0   # la caja de la merma, $
    assert fila_banana[22].value == 2.0     # la caja de la merma, cajas
    assert (fila_banana[8].value + fila_banana[10].value
            + fila_banana[21].value) == fila_banana[6].value
    # Y la mercadería SOLA no alcanza: si alcanzara, la caja no estaría
    # adentro del total y la suma de arriba cerraría sin mirar la columna.
    assert fila_banana[8].value + fila_banana[10].value == 1500.0

    fila_total = next(f for f in hoja.iter_rows() if f[0].value == "Total REAL")
    assert fila_total[8].value == 700.0 and fila_total[10].value == 800.0
    # El total de bultos mermados también va en el total, no solo el
    # desglose: la columna no puede quedar vacía al lado de dos que suman.
    assert fila_total[7].value == 3.0
    # La caja también en el total y en el subtotal, no solo en la fila: un
    # canario que movía SOLO el `column=22` de la fila del artículo pasaba
    # todo lo de arriba (corolario 57, los N hermanos).
    fila_subtotal = next(f for f in hoja.iter_rows() if f[0].value == "Subtotal")
    assert fila_subtotal[21].value == 300.0 and fila_subtotal[22].value == 2.0
    assert fila_total[21].value == 300.0 and fila_total[22].value == 2.0
    # Y las columnas que estaban después de las mermas siguieron corriéndose
    # enteras: la renta no quedó pisada por el desglose.
    assert fila_total[17].value == 5180.0


def test_generar_pdf_rentabilidad_real_dice_si_lo_tirado_era_crudo_o_trabajado():
    import pypdfium2 as pdfium

    pdf = generar_pdf_rentabilidad_real(date(2026, 8, 18), date(2026, 8, 25), ["cliente Día"], RESULTADO_REAL)
    documento = pdfium.PdfDocument(pdf)
    texto = "\n".join(pagina.get_textpage().get_text_range() for pagina in documento)

    # Va en su propio párrafo, no adentro de la columna angosta "Mermas".
    assert "Mermas — ¿materia prima o trabajo?" in texto
    assert "cruda $700" in texto
    assert "ya trabajada $800" in texto
    # EL PÁRRAFO HACE WRAP y dónde corta lo decide el largo del texto, así que
    # se afirma sobre el renglón corrido y no sobre el extraído: la versión
    # vieja chequeaba "por partes" para esquivarlo, y el día que la frase
    # creció el corte se movió al medio de una de esas partes igual.
    corrido = " ".join(texto.split())
    assert "Es el mismo total de $1.800, abierto por lo que se tiró." in corrido
    assert "(1 bulto, guías R" in corrido  # un solo bulto no lleva la s
    # EL TERCER TÉRMINO: sin él la frase "es el mismo total" manda a sumar dos
    # números que no dan ese total.
    assert "la caja de Día $300 (2 cajas nuestras que se fueron con la fruta adentro)" in corrido


def test_exports_reales_sin_datos_no_rompen():
    vacio = {"grupos": [], "totales": {"bultos": 0, "venta_neta": 0, "costo_mercaderia": 0,
                                       "costo_envase": 0, "costo_mermas": 0, "bultos_mermados": 0,
                                       "costo_mermas_cruda": 0, "bultos_mermados_cruda": 0,
                                       "costo_mermas_trabajada": 0, "bultos_mermados_trabajada": 0,
                                       "costo_segunda": 0, "bultos_pasados_a_segunda": 0,
                                       "cajas_mermadas": 0, "cajas_mermadas_pesos": 0,
                                       "segunda_bultos": 0,
                                       "costo_total": 0, "renta_pesos": 0, "utilidad_pct": None,
                                       "afuera_bultos": 0, "afuera_motivos": 0},
             "afuera_por_motivo": [], "fechas_incluidas": []}
    assert generar_pdf_rentabilidad_real(date(2026, 8, 18), date(2026, 8, 25), [], vacio).startswith(b"%PDF")
    hoja = openpyxl.load_workbook(
        BytesIO(generar_excel_rentabilidad_real(date(2026, 8, 18), date(2026, 8, 25), [], vacio))
    ).active
    valores = [str(c.value) for f in hoja.iter_rows() for c in f if c.value is not None]
    assert any("Sin movimientos" in v for v in valores)


def test_el_PDF_y_el_EXCEL_NOMBRAN_lo_pasado_a_segunda():
    """Los dos canarios que dieron CERO: se podían borrar las dos columnas del
    Excel y el párrafo del PDF sin que nada cayera.

    El fixture tiene $2.100 en 4 bultos a propósito: con todo en cero los dos
    exportables se saltean el renglón y ningún assert puede distinguir "no lo
    escribe" de "no había nada que escribir" (corolario 30).
    """
    import pypdfium2 as pdfium

    pdf = generar_pdf_rentabilidad_real(
        date(2026, 8, 18), date(2026, 8, 25), ["cliente Día"], RESULTADO_REAL)
    documento = pdfium.PdfDocument(pdf)
    texto = "\n".join(p.get_textpage().get_text_range() for p in documento)
    assert "Pasado a segunda" in texto
    assert "$2.100" in texto

    hoja = openpyxl.load_workbook(BytesIO(generar_excel_rentabilidad_real(
        date(2026, 8, 18), date(2026, 8, 25), ["cliente Día"], RESULTADO_REAL))).active
    encabezados = [str(c.value) for f in hoja.iter_rows() for c in f if c.value is not None]
    assert "Pasado a segunda $" in encabezados
    assert "Pasado a segunda bultos" in encabezados

    # Y EL VALOR, no solo el encabezado: una columna con título y sin número
    # pasa el assert de arriba y no dice nada. Tres veces —la fila, el
    # subtotal y el total— que es el denominador de esta hoja.
    valores = [c.value for f in hoja.iter_rows() for c in f if c.value is not None]
    assert valores.count(2100.0) == 3, valores.count(2100.0)
    assert valores.count(4.0) >= 3


def test_el_Excel_agrega_las_columnas_AL_FINAL_y_no_corre_las_que_ya_estaban():
    """Esta hoja ubica cada valor por ÍNDICE.

    Meter las dos nuevas en el medio correría todo lo que está a la derecha
    —renta, utilidad, rechazos— sin que ningún test que mire un número lo
    pueda ver. Es el mismo mecanismo que el `nth-child` del catálogo de
    Artículos, en openpyxl.
    """
    hoja = openpyxl.load_workbook(BytesIO(generar_excel_rentabilidad_real(
        date(2026, 8, 18), date(2026, 8, 25), ["cliente Día"], RESULTADO_REAL))).active
    fila_encabezado = next(
        f for f in hoja.iter_rows() if f[0].value == "Artículo")
    titulos = [c.value for c in fila_encabezado]

    assert titulos[-4:] == ["Pasado a segunda $", "Pasado a segunda bultos",
                            "Caja de la merma $", "Caja de la merma cajas"]
    # Las que ya estaban, en su lugar de siempre.
    assert titulos[17] == "Renta $" and titulos[18] == "Utilidad %"

    # Y LOS VALORES, en LAS TRES FILAS. El encabezado no alcanza: un canario
    # que movía SOLO el `column=20` de la fila del artículo —dejando el título
    # al final y el subtotal y el total en su lugar— pasaba los asserts de
    # arriba y el `count(2100.0) == 3` de más abajo, porque el valor seguía
    # existiendo tres veces. Lo único que lo ve es DÓNDE está en cada fila, y
    # las tres van juntas: con una sola, mover las otras dos no rompe nada
    # (corolario 57, los N hermanos).
    filas = {f[0].value: f for f in hoja.iter_rows()
             if f[0].value in ("Banana", "Subtotal", "Total REAL")}
    assert len(filas) == 3, sorted(filas)
    for nombre, fila in filas.items():
        assert fila[19].value == 2100.0, (nombre, fila[19].value)
        assert fila[20].value == 4.0, (nombre, fila[20].value)
        assert fila[21].value == 300.0, (nombre, fila[21].value)
        assert fila[22].value == 2.0, (nombre, fila[22].value)

    # Y EL VECINO QUE LA INSERCIÓN EN EL MEDIO PISA: "Mermas bultos" es la
    # columna 8, que es adonde el canario mandaba el costo de la segunda.
    assert titulos[7] == "Mermas bultos"
    assert filas["Banana"][7].value == 3.0
