"""Qué comprar hoy en PDF — puro, sin tocar la base.

Es el listado de la pantalla tal como está en ese momento, para imprimir en A4
o abrir en el celular. Las filas llegan ARMADAS de `_filas_de_que_comprar`, la
misma función que dibuja la pantalla: acá no se recalcula nada, así el papel
y la pantalla no pueden decir números distintos.

LO QUE SÍ ESTÁ ESCRITO DOS VECES es CÓMO SE DICE cada celda (OK, "poné el por
bulto", "no se sabe la unidad"): la pantalla lo dice en Jinja y el PDF acá.
Lo que impide que se separen no es que hoy coincidan: es
`test_el_PDF_dice_en_cada_celda_LO_MISMO_que_la_pantalla`, que renderiza la
pantalla y compara celda por celda contra `textos_de_la_fila`.

De `core/exportar_vacios.py` se reusa SOLO la forma del PDF (encabezado verde,
tabla con los rótulos repetidos en cada hoja), que es la de todos los PDF del
sistema.
"""

import re
from io import BytesIO

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer

from core.exportar_vacios import _documento_pdf, _estilos_pdf, _tabla_seccion_pdf

TITULO = "Qué comprar hoy"

# EN EL ORDEN DE LA PANTALLA (dueño, 23/09): de lo que piden a lo que falta.
COLUMNAS = (
    ("pide", "Piden"),
    ("kilaje", "Por bulto"),
    ("pide_bultos", "Piden bultos"),
    ("stock", "Stock"),
    ("en_camino", "En camino"),
    ("a_comprar", "A comprar hoy"),
    ("compre", "Compré"),
    ("falta", "Falta comprar"),
)

HUECO_UNIDAD = "no se sabe la unidad"
HUECO_KILAJE = "poné el por bulto"


def textos_de_la_fila(fila: dict, numero, sin_decimales) -> dict:
    """Lo que dice cada celda de una fila, con las MISMAS ramas que la pantalla.

    `numero` y `sin_decimales` son los filtros de la pantalla, que viven en
    `app/main.py` y `core` no puede importar: se pasan, para que el PDF no
    tenga su propio redondeo.
    """
    sufijo = fila.get("sufijo") or ""
    pide = fila.get("pide")
    en_piso = fila.get("en_piso")
    if en_piso is None:
        stock, stock_magnitud = "no se puede saber", ""
    elif fila.get("stock_bultos") is not None:
        stock = f"{numero(fila['stock_bultos'])} blt"
        stock_magnitud = f"{sin_decimales(en_piso)} {sufijo}".strip()
    else:
        stock, stock_magnitud = f"{sin_decimales(en_piso)} {sufijo}".strip(), ""

    a_comprar_magnitud = fila.get("a_comprar_magnitud")
    if a_comprar_magnitud is not None and a_comprar_magnitud == 0:
        a_comprar = "OK"
    elif pide is not None and fila.get("de_partida") is not None and fila.get("a_comprar") is not None:
        a_comprar = f"{fila['a_comprar']} cj"
    elif pide is not None and fila.get("de_partida") is not None:
        a_comprar = HUECO_KILAJE
    else:
        a_comprar = "—"

    falta_magnitud = fila.get("falta")
    if falta_magnitud is not None and falta_magnitud == 0:
        falta = "OK"
    elif fila.get("cajones") is not None:
        falta = f"{sin_decimales(fila['cajones'])} cj"
    elif falta_magnitud is not None:
        falta = HUECO_KILAJE
    else:
        falta = "—"

    kilaje = fila.get("kilaje")
    return {
        "pide": f"{sin_decimales(pide)} {sufijo}".strip() if pide is not None else HUECO_UNIDAD,
        # En la pantalla es un campo editable; en papel va el número que tiene.
        "kilaje": f"{sin_decimales(kilaje)} {sufijo}".strip() if kilaje is not None else "—",
        "pide_bultos": numero(fila["pide_bultos"]) if fila.get("pide_bultos") is not None else "—",
        "stock": stock,
        "stock_magnitud": stock_magnitud,
        "en_camino": (HUECO_UNIDAD if fila.get("en_camino") is None
                      else f"{sin_decimales(fila.get('en_camino_cajones') or 0)} cj"),
        "a_comprar": a_comprar,
        "compre": f"{sin_decimales(fila.get('comprado_cajones') or 0)} cj",
        "falta": falta,
        "de_quien": " · ".join(f"{e} {sin_decimales(t)}" for e, t in fila.get("de_quien") or []),
        # EL NEGATIVO DEL SISTEMA, con su número (dueño, 28/09). No es un
        # dato a completar a mano: en el papel va en rojo, no en blanco.
        "sueltos_negativos": (
            f"sistema {numero(fila['sueltos_negativos'])} blt sueltos"
            if fila.get("sueltos_negativos") is not None else ""),
    }


# LO QUE EL PAPEL DEJA EN BLANCO (dueño, 28/09): "imprimo el listado y lo
# completo a mano en el Mercado. Un espacio vacío se puede llenar con la
# lapicera; un cero impreso no". Los carteles de la pantalla ("no se puede
# saber", "poné el por bulto") y el OK, que es cero para comprar, también.
# En la PANTALLA siguen: ahí dicen qué hacer, y el test que compara las dos
# mira `textos_de_la_fila`, que no cambia.
EN_BLANCO_EN_EL_PAPEL = {"OK", "—", "no se puede saber", HUECO_UNIDAD, HUECO_KILAJE}


def para_el_papel(texto: str) -> str:
    """El texto de la celda para imprimir: vacío si es cero, un cartel o no se sabe.

    Cero es el número que empieza con "0" y sigue con un espacio o nada
    ("0", "0 cj", "0 kg"). "0.5 kg" NO es cero y se imprime.
    """
    texto = (texto or "").strip()
    if texto in EN_BLANCO_EN_EL_PAPEL or re.match(r"^0(\s|$)", texto):
        return ""
    return texto


def _escapar(texto) -> str:
    """Paragraph de reportlab lee marcado: un "<" en un nombre rompería el PDF."""
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generar_pdf_que_comprar(
    subtitulo: str, cargas: list[str], filas: list[dict], numero, sin_decimales,
    *, viejas: list[dict] | None = None, aviso: str | None = None,
) -> bytes:
    """El listado en A4 vertical: una fila por artículo, con de quién sale abajo del nombre.

    VERTICAL Y NO APAISADO: se abre en el celular, que se lee parado. Las
    nueve columnas entran con los rótulos partidos en dos renglones.
    """
    buffer = BytesIO()
    documento, encabezado = _documento_pdf(buffer, TITULO, subtitulo)
    estilos = _estilos_pdf()
    ancho = documento.width
    elementos = []

    if aviso:
        elementos += [Paragraph(_escapar(aviso), estilos["aviso"]), Spacer(1, 3 * mm)]
    texto_cargas = ", ".join(_escapar(c) for c in cargas) if cargas else "ninguna tildada"
    elementos += [Paragraph(f"<b>Cargas:</b> {texto_cargas}", estilos["dato"]), Spacer(1, 3 * mm)]

    # LAS VIEJAS VAN EN EL PAPEL IGUAL QUE EN LA PANTALLA: no se suman, y el
    # que compra con el papel en la mano tiene que saber que existen.
    if viejas:
        lista = "; ".join(
            f"{_escapar(v['nombre'])} ({sin_decimales(v['cajones'])} cj"
            + (f", desde el {v['desde'].strftime('%d/%m')}" if v.get("desde") else "") + ")"
            for v in viejas
        )
        elementos += [Paragraph(
            "Hay compras cargadas hace más de 3 días que no llegaron y NO se cuentan: " + lista,
            estilos["aviso"]), Spacer(1, 3 * mm)]

    if not filas:
        elementos.append(Paragraph(
            "Esas cargas no piden nada." if cargas else "No hay cargas tildadas.", estilos["vacio"]))
    else:
        datos = []
        for fila in filas:
            textos = textos_de_la_fila(fila, numero, sin_decimales)
            nombre = f"<b>{_escapar(fila.get('nombre', ''))}</b>"
            if textos["de_quien"]:
                nombre += f"<br/><font size='8' color='#595959'>{_escapar(textos['de_quien'])}</font>"
            celdas = [Paragraph(nombre, estilos["dato"])]
            for clave, _rotulo in COLUMNAS:
                texto = _escapar(para_el_papel(textos[clave]))
                magnitud = para_el_papel(textos["stock_magnitud"])
                if clave == "stock" and texto and magnitud:
                    texto += f"<br/><font size='8' color='#595959'>{_escapar(magnitud)}</font>"
                if clave == "stock" and textos["sueltos_negativos"]:
                    texto += (("<br/>" if texto else "")
                              + f"<font size='8' color='#B91C1C'><b>{_escapar(textos['sueltos_negativos'])}</b></font>")
                estilo = estilos["numero"] if clave in ("a_comprar", "falta") else estilos["dato"]
                celdas.append(Paragraph(texto, estilo))
            datos.append(celdas)
        anchos = [ancho * 0.22] + [ancho * 0.0975] * len(COLUMNAS)
        # NUEVE COLUMNAS EN A4 VERTICAL: con el rótulo de 9,5 de las otras
        # tablas, "Compré" y "A comprar" se partían al medio de la palabra. Con
        # 8 parten entre palabras, que es lo que se lee impreso.
        estilos["encabezado_tabla"] = ParagraphStyle(
            "encabezado_chico", parent=estilos["encabezado_tabla"], fontSize=8, leading=9.5)
        elementos.append(_tabla_seccion_pdf(
            "Una fila por artículo", ["Artículo"] + [r for _c, r in COLUMNAS], datos, anchos, estilos))

    documento.build(elementos, onFirstPage=encabezado, onLaterPages=encabezado)
    return buffer.getvalue()
