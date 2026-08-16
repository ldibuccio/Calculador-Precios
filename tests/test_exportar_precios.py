from datetime import date
from io import BytesIO

import openpyxl
import pypdfium2 as pdfium

from core.exportar_precios import generar_excel_lista_precios, generar_pdf_lista_precios

FILAS_DE_PRUEBA = [
    {"articulo_nombre": "Mango", "grupo": "fruta", "precio": 350.0, "unidad": "unidad", "es_nuevo": False},
    {"articulo_nombre": "Manzana Red", "grupo": "fruta", "precio": 890.0, "unidad": "kilo", "es_nuevo": True},
    {"articulo_nombre": "Morrón Rojo", "grupo": "hortaliza", "precio": 1200.0, "unidad": "kilo", "es_nuevo": False},
    {"articulo_nombre": "Tomate Cherry", "grupo": "hortaliza", "precio": 500.0, "unidad": "kilo", "es_nuevo": True},
    {"articulo_nombre": "Cubeta X", "grupo": "pesada", "precio": 15000.0, "unidad": "cubeta", "es_nuevo": False},
    {"articulo_nombre": "Articulo Raro", "grupo": None, "precio": 100.0, "unidad": None, "es_nuevo": False},
]


def _texto_del_pdf(pdf_bytes: bytes) -> str:
    documento = pdfium.PdfDocument(pdf_bytes)
    textos = []
    for pagina in documento:
        textos.append(pagina.get_textpage().get_text_range())
    return "\n".join(textos)


# --- generar_pdf_lista_precios ---


def test_generar_pdf_incluye_encabezado_y_pie():
    pdf_bytes = generar_pdf_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    texto = _texto_del_pdf(pdf_bytes)

    assert "Lista de Precios" in texto
    assert "Cliente: Día" in texto
    assert "Vigencia: 16/08/2026 · Precios + IVA" in texto
    assert "Nuevo precio indica los productos cuyo precio fue actualizado." in texto
    assert "Todos los precios están expresados en pesos y no incluyen IVA." in texto


def test_generar_pdf_secciones_en_el_orden_fruta_hortaliza_pesada_sin_clasificar():
    pdf_bytes = generar_pdf_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    texto = _texto_del_pdf(pdf_bytes)

    posiciones = [texto.index(titulo) for titulo in ("FRUTA", "HORTALIZA", "PESADA", "SIN CLASIFICAR")]
    assert posiciones == sorted(posiciones)


def test_generar_pdf_articulo_sin_grupo_cae_en_sin_clasificar():
    pdf_bytes = generar_pdf_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    texto = _texto_del_pdf(pdf_bytes)

    bloque_sin_clasificar = texto[texto.index("SIN CLASIFICAR") :]
    assert "Articulo Raro" in bloque_sin_clasificar


def test_generar_pdf_precios_formateados_con_signo_pesos_y_separador_de_miles():
    pdf_bytes = generar_pdf_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    texto = _texto_del_pdf(pdf_bytes)

    assert "$1.200" in texto
    assert "$15.000" in texto


def test_generar_pdf_unidad_segun_la_ficha():
    pdf_bytes = generar_pdf_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    texto = _texto_del_pdf(pdf_bytes)

    assert "por kilo" in texto
    assert "por unidad" in texto
    assert "por cubeta" in texto


def test_generar_pdf_hoy_muestra_badge_nuevo_precio_solo_en_los_nuevos():
    pdf_bytes = generar_pdf_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    texto = _texto_del_pdf(pdf_bytes)

    # La leyenda de arriba también dice "Nuevo precio" — se cuenta solo a
    # partir de las tablas (después de la primera sección) para no
    # confundir esa frase con los badges de las filas.
    bloque_tablas = texto[texto.index("FRUTA") :]
    # Solo Manzana Red y Tomate Cherry vinieron con es_nuevo=True.
    assert bloque_tablas.count("Nuevo precio") == 2


def test_generar_pdf_fecha_pasada_no_resalta_nada_aunque_venga_es_nuevo():
    # Regresión explícita: si es_hoy=False (se está exportando una fecha
    # pasada), TODOS los precios van en negro — el badge no debe aparecer
    # aunque las filas traigan es_nuevo=True (eso pasaría si vigente_desde
    # coincidiera con la fecha exportada, pero esa fecha no es HOY).
    pdf_bytes = generar_pdf_lista_precios("Día", date(2026, 1, 15), FILAS_DE_PRUEBA, es_hoy=False)
    texto = _texto_del_pdf(pdf_bytes)

    # La leyenda fija sigue apareciendo (no depende de es_hoy); lo que no
    # tiene que aparecer es el badge en ninguna fila de las tablas.
    bloque_tablas = texto[texto.index("FRUTA") :]
    assert "Nuevo precio" not in bloque_tablas


def test_generar_pdf_sin_filas_no_rompe():
    pdf_bytes = generar_pdf_lista_precios("Día", date(2026, 8, 16), [], es_hoy=True)
    texto = _texto_del_pdf(pdf_bytes)

    assert "Lista de Precios" in texto
    assert "FRUTA" not in texto


# --- generar_excel_lista_precios ---


def _cargar_excel(excel_bytes: bytes):
    return openpyxl.load_workbook(BytesIO(excel_bytes))


def test_generar_excel_incluye_encabezado_y_secciones():
    excel_bytes = generar_excel_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    libro = _cargar_excel(excel_bytes)
    hoja = libro.active

    valores = [celda.value for fila in hoja.iter_rows() for celda in fila if celda.value is not None]
    assert "Lista de Precios" in valores
    assert "FRUTA" in valores
    assert "HORTALIZA" in valores
    assert "PESADA" in valores
    assert "SIN CLASIFICAR" in valores
    assert "Mango" in valores
    assert "Articulo Raro" in valores


def _nombres_con_precio_resaltado_en_rojo(hoja):
    from core.exportar_precios import ROJO_FONDO_CLARO_HEX

    return [
        fila[0].value
        for fila in hoja.iter_rows()
        if fila[1].fill
        and fila[1].fill.start_color
        and fila[1].fill.start_color.rgb == f"00{ROJO_FONDO_CLARO_HEX}"
    ]


def test_generar_excel_precio_nuevo_resaltado_solo_si_es_hoy():
    excel_bytes = generar_excel_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    libro = _cargar_excel(excel_bytes)
    hoja = libro.active

    celdas_resaltadas = _nombres_con_precio_resaltado_en_rojo(hoja)
    assert "Manzana Red" in celdas_resaltadas
    assert "Tomate Cherry" in celdas_resaltadas
    assert "Mango" not in celdas_resaltadas


def test_generar_excel_fecha_pasada_no_resalta_nada():
    excel_bytes = generar_excel_lista_precios("Día", date(2026, 1, 15), FILAS_DE_PRUEBA, es_hoy=False)
    libro = _cargar_excel(excel_bytes)
    hoja = libro.active

    assert _nombres_con_precio_resaltado_en_rojo(hoja) == []


def test_generar_excel_precio_guardado_como_numero_no_como_texto():
    # Guardar el precio como número (con number_format de moneda) en vez de
    # como texto "$1.200" deja la planilla usable (sumar, filtrar, ordenar).
    excel_bytes = generar_excel_lista_precios("Día", date(2026, 8, 16), FILAS_DE_PRUEBA, es_hoy=True)
    libro = _cargar_excel(excel_bytes)
    hoja = libro.active

    valores_precio = [fila[1].value for fila in hoja.iter_rows() if fila[0].value == "Mango"]
    assert valores_precio == [350.0]
