"""FOTOS DE MÁS DE 3 AÑOS (dueño, 30/09): el corte, los tipos y el resumen — puro.

Las fotos llegan de `fotos_de_respaldo` (app/db.py): una fila por ARCHIVO,
con su tipo y cuándo se subió. Los tamaños, del bucket (`tamanos_del_bucket`).
Acá no se lee la base: se decide qué es "más de 3 años", cómo se llama cada
tipo y cómo se suma, y la pantalla de Gerencia y el borrado usan lo mismo.

LA REGLA: una foto de respaldo no se borra antes de 3 años desde que se
SUBIÓ. Después se puede, a mano, desde Gerencia, y queda el registro. La
antigüedad se cuenta desde la subida y no desde la fecha de la compra o del
pedido: lo que vence es el archivo.
"""

from datetime import date
from zoneinfo import ZoneInfo

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")

ANIOS_DE_RESPALDO = 3

# De dónde es cada foto, en el orden en que se muestran. La clave es la que
# escribe `_SQL_FOTOS_DE_RESPALDO`; un tipo que la consulta devuelva y no esté
# acá se muestra con su clave tal cual (un test exige que no pase).
TEXTO_DEL_TIPO = {
    "pesada": "Pesadas de recepción",
    "devolucion_mercaderia": "Devoluciones de mercadería",
    "compra_borrada": "Pesadas de compras borradas",
    "comanda": "Comandas del proveedor",
    "pedido": "Capturas de pedidos",
    "precios": "Archivos de precios",
    "merma": "Mermas",
    "vacios": "Devoluciones de vacíos",
    "vale": "Vales a cobrar",
}


def corte_de_respaldo(hoy: date) -> date:
    """3 años antes de hoy. Una foto subida ANTES de este día tiene más de 3
    años y se puede borrar; la de este día, todavía no."""
    try:
        return hoy.replace(year=hoy.year - ANIOS_DE_RESPALDO)
    except ValueError:
        # 29 de febrero: hace 3 años no era bisiesto.
        return hoy.replace(month=2, day=28, year=hoy.year - ANIOS_DE_RESPALDO)


def dia_de_subida(subida_el) -> date:
    """El día argentino en que se subió. Lo hace el que compara, aunque llegue
    convertido (corolario 21)."""
    return subida_el.astimezone(ARGENTINA).date()


def es_de_mas_de_3_anios(foto: dict, corte: date) -> bool:
    return dia_de_subida(foto["subida_el"]) < corte


def fotos_para_borrar(fotos: list[dict], corte: date) -> list[dict]:
    """Las que se pueden borrar: más de 3 años y el archivo todavía está."""
    return [f for f in fotos if not f["ya_borrada"] and es_de_mas_de_3_anios(f, corte)]


def resumen_por_tipo(fotos: list[dict], tamanos: dict[str, int] | None, corte: date) -> list[dict]:
    """Una fila por tipo: cuántas hay y cuánto ocupan, y cuántas tienen más de
    3 años. Las ya borradas no suman acá (su archivo no está): van aparte.

    `tamanos` None es que el bucket no se pudo leer: los bytes van en None y
    la pantalla dice "sin dato" en vez de un cero que se lea como "vacío".
    """
    filas = {tipo: {"tipo": tipo, "texto": texto, "cantidad": 0, "bytes": 0,
                    "viejas": 0, "bytes_viejas": 0}
             for tipo, texto in TEXTO_DEL_TIPO.items()}
    for foto in fotos:
        if foto["ya_borrada"]:
            continue
        fila = filas.setdefault(foto["tipo"], {"tipo": foto["tipo"], "texto": foto["tipo"], "cantidad": 0,
                                               "bytes": 0, "viejas": 0, "bytes_viejas": 0})
        tamano = (tamanos or {}).get(foto["ruta"], 0)
        fila["cantidad"] += 1
        fila["bytes"] += tamano
        if es_de_mas_de_3_anios(foto, corte):
            fila["viejas"] += 1
            fila["bytes_viejas"] += tamano
    resultado = list(filas.values())
    if tamanos is None:
        for fila in resultado:
            fila["bytes"] = fila["bytes_viejas"] = None
    return resultado


def total_de(filas: list[dict], campo: str):
    valores = [f[campo] for f in filas]
    return None if any(v is None for v in valores) else sum(valores)


def archivos_sin_registro(fotos: list[dict], tamanos: dict[str, int] | None) -> dict | None:
    """Los archivos del bucket que ninguna fila nombra (dueño, 30/09): se
    muestran aparte, y NO se borran. None si el bucket no se pudo leer."""
    if tamanos is None:
        return None
    conocidas = {f["ruta"] for f in fotos}
    sueltos = sorted(ruta for ruta in tamanos if ruta not in conocidas)
    return {"cantidad": len(sueltos), "bytes": sum(tamanos[r] for r in sueltos), "rutas": sueltos}
