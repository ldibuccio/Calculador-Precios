"""FOTOS DE MÁS DE 3 AÑOS (dueño, 30/09): el corte, los tipos y el resumen — puro.

Las fotos llegan de `fotos_de_respaldo` (app/db.py): una fila por ARCHIVO,
con su tipo y cuándo se subió. Los tamaños, de `subidas_al_storage`.
Acá no se lee la base: se decide qué es "más de 3 años", cómo se llama cada
tipo y cómo se suma, y la pantalla de Gerencia y el borrado usan lo mismo.

LA REGLA: una foto de respaldo no se borra antes de 3 años desde que se
SUBIÓ. Después se puede, a mano, desde Gerencia, y queda el registro. La
antigüedad se cuenta desde la subida y no desde la fecha de la compra o del
pedido: lo que vence es el archivo.
"""

from datetime import date, timedelta
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


# ============================================================================
# EL ESPACIO (dueño, 01/10): cuánto ocupa el Storage hoy, cómo creció mes a
# mes, a dónde va y cuánto del plan es.
#
# Las subidas llegan de `subidas_al_storage` (app/db.py): una fila por archivo
# que está en el Storage, más las fotos ya borradas por antigüedad, con su
# tamaño y cuándo se subieron. Las borradas NO suman al espacio de hoy, pero
# SÍ al mes en que se subieron: la pregunta del mes a mes es cuánto se subió,
# no cuánto queda. Lo que se borró por error de carga en el momento no está
# en ningún lado y no cuenta.
# ============================================================================

# El plan Pro de Supabase incluye 100 GB de Storage por ORGANIZACIÓN, no por
# base: Frutamax, Palmala y Ganadería suman contra la misma cuota (Supabase,
# "Variable Usage Fees and Quotas", medido el 01/10). Cada app ve solo su
# base, así que el porcentaje de acá es lo que pone ESTA base. Si cambia el
# plan, cambia este número y nada más.
PLAN_DE_SUPABASE = "Pro"
LIMITE_DEL_PLAN_BYTES = 100 * 1024 ** 3
UMBRAL_DEL_AVISO = 80          # %: más de esto, la alerta de Gerencia
DIAS_DEL_RITMO = 90            # "los últimos 3 meses" de la proyección

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def archivos_de_hoy(subidas: list[dict]) -> list[dict]:
    """Los archivos que están en el Storage ahora (las borradas no)."""
    return [s for s in subidas if not s["borrada"]]


def tamanos_del_bucket(subidas: list[dict], bucket: str) -> dict[str, int]:
    """{ruta: bytes} de los archivos de hoy de un bucket."""
    return {s["ruta"]: s["bytes"] for s in archivos_de_hoy(subidas) if s["bucket"] == bucket}


def porcentaje_del_plan(bytes_) -> float:
    return bytes_ * 100 / LIMITE_DEL_PLAN_BYTES


def pasa_el_aviso(bytes_) -> bool:
    return porcentaje_del_plan(bytes_) > UMBRAL_DEL_AVISO


def evolucion_por_mes(subidas: list[dict], hoy: date) -> list[dict]:
    """Un renglón por mes, desde el de la primera subida hasta el de hoy, con lo
    que se subió ese mes y el acumulado. Un mes sin subidas sale en cero:
    saltearlo haría parecer que el acumulado creció de golpe."""
    if not subidas:
        return []
    por_mes: dict[tuple[int, int], list[int]] = {}
    for s in subidas:
        dia = dia_de_subida(s["subida_el"])
        cuenta = por_mes.setdefault((dia.year, dia.month), [0, 0])
        cuenta[0] += 1
        cuenta[1] += s["bytes"]
    anio, mes = min(por_mes)
    fin = max(max(por_mes), (hoy.year, hoy.month))
    filas = []
    acumulado_cantidad = acumulado_bytes = 0
    while (anio, mes) <= fin:
        cantidad, bytes_ = por_mes.get((anio, mes), (0, 0))
        acumulado_cantidad += cantidad
        acumulado_bytes += bytes_
        filas.append({"mes": f"{MESES[mes - 1]} {anio}", "cantidad": cantidad, "bytes": bytes_,
                      "acumulado_cantidad": acumulado_cantidad, "acumulado_bytes": acumulado_bytes})
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    mayor = max(f["bytes"] for f in filas)
    for f in filas:
        f["ancho"] = round(f["bytes"] * 100 / mayor) if mayor else 0
    return filas


def proyeccion(subidas: list[dict], hoy: date) -> dict | None:
    """A dónde llega el espacio en 12 meses si se sigue subiendo al ritmo de
    los últimos 90 días. Si la primera foto es más nueva, el ritmo se mide
    desde ella y la pantalla dice sobre cuántos días: con 40 días de historia,
    dividir por 90 daría un ritmo de menos de la mitad.

    Supone que no se borra nada: lo de 3 años no empieza a vencer hasta 2029.
    """
    if not subidas:
        return None
    primer_dia = min(dia_de_subida(s["subida_el"]) for s in subidas)
    desde = max(primer_dia, hoy - timedelta(days=DIAS_DEL_RITMO - 1))
    dias = (hoy - desde).days + 1
    en_la_ventana = sum(s["bytes"] for s in subidas
                        if desde <= dia_de_subida(s["subida_el"]) <= hoy)
    por_dia = en_la_ventana / dias
    hoy_bytes = sum(s["bytes"] for s in archivos_de_hoy(subidas))
    en_12_meses = hoy_bytes + por_dia * 365
    return {"desde": desde, "dias": dias, "por_mes": por_dia * 365 / 12,
            "en_12_meses": en_12_meses, "porcentaje_en_12_meses": porcentaje_del_plan(en_12_meses)}


def archivos_sin_registro(fotos: list[dict], tamanos: dict[str, int] | None) -> dict | None:
    """Los archivos del bucket que ninguna fila nombra (dueño, 30/09): se
    muestran aparte, y NO se borran. None si el bucket no se pudo leer."""
    if tamanos is None:
        return None
    conocidas = {f["ruta"] for f in fotos}
    sueltos = sorted(ruta for ruta in tamanos if ruta not in conocidas)
    return {"cantidad": len(sueltos), "bytes": sum(tamanos[r] for r in sueltos), "rutas": sueltos}
