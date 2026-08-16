"""Conversión de archivos (PDF, Excel) a algo que la IA de core/lector_comandas.py pueda leer.

Este módulo NO habla con la API de Claude ni interpreta nada: solo
convierte el archivo tal como llegó a imágenes (PDF, una por página) o a
texto plano (Excel, celda por celda). La lectura con IA — que es la que
decide qué es un artículo y qué un precio — vive en core/lector_comandas.py.
"""

import io

import openpyxl
import pypdfium2 as pdfium

ESCALA_RENDER_PDF = 2.0  # 72 * 2 ≈ 144 DPI: legible sin generar imágenes gigantes.
CALIDAD_JPEG_PDF = 85


def imagenes_desde_pdf(bytes_pdf: bytes) -> list[bytes]:
    """Convierte cada página de un PDF en una imagen JPEG (bytes), en el mismo orden.

    Sirve tanto para un PDF con texto real como para uno escaneado (fotos
    metidas en un PDF): en los dos casos la página se renderiza tal cual se
    ve, y es la IA (en modo imagen) la que la lee — no hace falta distinguir
    de antemano cuál es cuál.

    Lanza ValueError con un mensaje claro si el archivo no es un PDF válido
    o no se pudo abrir, para que quien llame pueda mostrar un error
    entendible en vez de un stack trace de la librería.
    """
    try:
        documento = pdfium.PdfDocument(bytes_pdf)
    except Exception as error:
        raise ValueError(f"No se pudo abrir el PDF: {error}") from error

    try:
        imagenes = []
        for pagina in documento:
            bitmap = pagina.render(scale=ESCALA_RENDER_PDF)
            try:
                imagen_pil = bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
            buffer = io.BytesIO()
            imagen_pil.save(buffer, format="JPEG", quality=CALIDAD_JPEG_PDF)
            imagenes.append(buffer.getvalue())
            pagina.close()
        return imagenes
    finally:
        documento.close()


def texto_desde_excel(bytes_excel: bytes) -> str:
    """Vuelca el contenido de todas las hojas de un Excel a texto plano, fila por fila.

    Cada fila se representa como sus valores separados por " | ", una fila
    por línea — no hace falta más estructura que esa: la IA es la que
    interpreta cuál columna es el artículo y cuál el precio (ver
    PROMPT_LISTADO_PRECIOS en core/lector_comandas.py). Filas y celdas
    vacías no aportan nada, se saltean. Si el archivo tiene varias hojas,
    se vuelcan todas juntas, una atrás de la otra.

    Lanza ValueError con un mensaje claro si el archivo no es un Excel
    válido (.xlsx) o no se pudo abrir.
    """
    try:
        libro = openpyxl.load_workbook(io.BytesIO(bytes_excel), data_only=True, read_only=True)
    except Exception as error:
        raise ValueError(f"No se pudo abrir el Excel: {error}") from error

    try:
        lineas = []
        for hoja in libro.worksheets:
            for fila in hoja.iter_rows(values_only=True):
                valores = [str(valor).strip() for valor in fila if valor is not None and str(valor).strip()]
                if valores:
                    lineas.append(" | ".join(valores))
        return "\n".join(lineas)
    finally:
        libro.close()
