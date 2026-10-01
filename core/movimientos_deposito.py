"""MOVIMIENTOS DEL DEPÓSITO: textos, agrupado por proveedor y Excel — puro.

Las filas llegan de `movimientos_del_deposito` (app/db.py). Acá no se
recalcula nada: se agrupa por proveedor para conciliar su cuenta y se decide
cómo se DICE cada fila. La pantalla y el Excel usan las mismas palabras.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from core.exportar_vacios import VERDE_ENCABEZADO_HEX

TEXTO_DEL_TIPO = {
    "entrada": "Entrada de compra",
    "rechazo": "Devolución por rechazo",
    "deposito": "Devolución desde depósito",
    "segunda": "Segunda al puesto",
}

# El filtro de la pantalla: "" es todos.
OPCIONES_DE_TIPO = (("", "Todos"),) + tuple(TEXTO_DEL_TIPO.items())

# Desde qué sector se cargó una devolución desde depósito (dueño, 01/10). La
# misma pantalla se abre en Depósito y en Administración. Solo esa fila lo
# tiene: filtrar por sector deja únicamente esas devoluciones.
TEXTO_DEL_SECTOR = {"deposito": "Depósito", "administracion": "Administración"}
OPCIONES_DE_SECTOR = (("", "Todos"),) + tuple(TEXTO_DEL_SECTOR.items())


def texto_del_sector(m: dict) -> str:
    """"cargada desde Administración", o vacío si la fila no lo tiene."""
    sector = m.get("sector")
    return f"cargada desde {TEXTO_DEL_SECTOR[sector]}" if sector in TEXTO_DEL_SECTOR else ""


def texto_de_la_sena(m: dict) -> str:
    """Cómo se dice la seña de una fila, igual en la pantalla y en el Excel.

    Vacío si la fila no tiene seña. Los cajones son los bultos de la fila:
    "entró con seña" en una entrada, "volvió con seña" en una devolución.
    """
    if not m.get("sena"):
        return ""
    cajones = abs(m["bultos"])
    cajones_txt = f"{cajones:,.0f}".replace(",", ".") if cajones == int(cajones) else f"{cajones:g}"
    sena_txt = f"{m['sena']:,.0f}".replace(",", ".")
    verbo = "entró" if m["tipo"] == "entrada" else "volvió"
    return f"{verbo} con seña: {cajones_txt} cajones × ${sena_txt}"


def agrupar(movimientos: list[dict]) -> list[dict]:
    """Un grupo por proveedor, en el orden en que llegan, con lo que entró,
    lo que salió y el neto, en bultos y en plata.

    La segunda remitida no tiene proveedor: va en su propio grupo, al final.
    `valor_incompleto` dice que alguna fila no tiene valor (una compra sin
    precio): el total de plata de ese grupo le falta algo y la pantalla lo
    dice, en vez de mostrar un número que se lee cerrado.
    """
    grupos: dict = {}
    for m in movimientos:
        clave = m["proveedor_id"]
        grupo = grupos.setdefault(clave, {
            "proveedor_id": clave,
            "proveedor": m["proveedor"] or "Segunda remitida al puesto",
            "filas": [], "entraron": 0.0, "salieron": 0.0,
            "valor_entrado": 0.0, "valor_salido": 0.0, "valor_incompleto": False,
        })
        grupo["filas"].append(m)
        if m["bultos"] >= 0:
            grupo["entraron"] += m["bultos"]
        else:
            grupo["salieron"] += -m["bultos"]
        if m["valor"] is None:
            if m["tipo"] != "segunda":
                grupo["valor_incompleto"] = True
        elif m["valor"] >= 0:
            grupo["valor_entrado"] += m["valor"]
        else:
            grupo["valor_salido"] += -m["valor"]
    for grupo in grupos.values():
        grupo["neto"] = grupo["entraron"] - grupo["salieron"]
        grupo["valor_neto"] = grupo["valor_entrado"] - grupo["valor_salido"]
    return list(grupos.values())


def generar_excel_movimientos_deposito(desde, hasta, filtro: str, movimientos: list[dict]) -> bytes:
    """Lo filtrado, fila por fila, con las mismas palabras que la pantalla.

    Los bultos y la plata van con su signo y como NÚMERO, para poder sumarlos.
    """
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Movimientos del depósito"
    hoja.cell(row=1, column=1, value="Movimientos del depósito").font = Font(bold=True, size=14)
    hoja.cell(row=2, column=1,
              value=f"Del {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')} · {filtro}")
    relleno = PatternFill(start_color="DEEFE3", end_color="DEEFE3", fill_type="solid")
    encabezados = ("Fecha", "Tipo", "Proveedor", "Compra", "Artículo", "Bultos", "Valor", "Motivo",
                   "Seña por cajón", "Seña", "Cargada desde")
    for columna, encabezado in enumerate(encabezados, start=1):
        celda = hoja.cell(row=4, column=columna, value=encabezado)
        celda.font = Font(bold=True, color=VERDE_ENCABEZADO_HEX)
        celda.fill = relleno
    for fila, m in enumerate(movimientos, start=5):
        valores = (
            m["fecha"].strftime("%d/%m/%Y") if m["fecha"] else "",
            TEXTO_DEL_TIPO[m["tipo"]],
            m["proveedor"] or "",
            m["compra_id"],
            m["articulo"],
            m["bultos"],
            m["valor"],
            m["motivo"],
            m.get("sena"),
            texto_de_la_sena(m),
            TEXTO_DEL_SECTOR.get(m.get("sector"), ""),
        )
        for columna, valor in enumerate(valores, start=1):
            hoja.cell(row=fila, column=columna, value=valor)
    for letra, ancho in zip("ABCDEFGHIJK", (12, 24, 30, 10, 26, 10, 14, 30, 14, 34, 16)):
        hoja.column_dimensions[letra].width = ancho
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()
