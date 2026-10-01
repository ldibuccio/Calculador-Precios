"""FOTOS: el plazo de cada tipo, los cortes, el resumen y el borrado — puro.

Las fotos llegan de `fotos_de_respaldo` (app/db.py): una fila por ARCHIVO,
con su tipo y cuándo se subió. Los tamaños, de `subidas_al_storage`.
Acá no se lee la base: se decide qué es "más de 3 años", cómo se llama cada
tipo y cómo se suma, y la pantalla de Gerencia y el borrado usan lo mismo.

LA REGLA (dueño, 30/09 y 01/10): cada TIPO de foto tiene un plazo en años
desde que se SUBIÓ (`fotos_plazos`, se edita en Gerencia; sin fila son 3).
Pasado el plazo la foto está VENCIDA y se puede borrar desde Gerencia. Además
Gerencia puede borrar A MANO un tipo "anterior a" una fecha. En los dos casos
se borra el ARCHIVO y queda el registro ("foto borrada el DD/MM/AAAA, por
plazo / a mano"), y cada borrado queda en un historial.

NUNCA se borran (se saltean y se dice cuántas): las fotos de un vale que no
está cobrado, cruzado ni anulado, ni las de un remito sin facturar. Eso lo
marca la consulta (`protegida`); acá se separan.

Las PESADAS DE COMPRAS BORRADAS siguen la regla de v1054 tal cual: 3 años
fijos, sin plazo editable y fuera del borrado a mano.
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
    "remito": "Remitos firmados",
}

# Los que no se tocan: la regla de v1054 (dueño, 01/10: "no la cambies").
TIPOS_CON_PLAZO_FIJO = ("compra_borrada",)

# Por qué una foto no se borra nunca, aunque esté vencida o se elija a mano.
TEXTO_DE_LA_PROTECCION = {
    "vale": "de un vale sin cobrar, cruzar ni anular",
    "remito": "de un remito sin facturar",
}

TEXTO_DE_COMO = {"plazo": "por plazo", "a_mano": "a mano"}

PLAZO_MAXIMO_ANIOS = 30


def corte_de_respaldo(hoy: date, anios: int = ANIOS_DE_RESPALDO) -> date:
    """`anios` antes de hoy. Una foto subida ANTES de este día está vencida y
    se puede borrar; la de este día, todavía no."""
    try:
        return hoy.replace(year=hoy.year - anios)
    except ValueError:
        # 29 de febrero: ese año no era bisiesto.
        return hoy.replace(month=2, day=28, year=hoy.year - anios)


def plazo_del_tipo(tipo: str, plazos: dict | None) -> int:
    """Los años que se guarda un tipo. Sin fila, los 3 de siempre; y los de
    plazo fijo no leen la tabla aunque alguien les haya cargado una fila."""
    if tipo in TIPOS_CON_PLAZO_FIJO:
        return ANIOS_DE_RESPALDO
    return int((plazos or {}).get(tipo) or ANIOS_DE_RESPALDO)


def cortes_por_tipo(hoy: date, plazos: dict | None) -> dict:
    """{tipo: corte} para todos los tipos conocidos."""
    return {tipo: corte_de_respaldo(hoy, plazo_del_tipo(tipo, plazos)) for tipo in TEXTO_DEL_TIPO}


def leer_plazo(texto) -> tuple[str | None, int | None]:
    """El plazo tipeado en Gerencia: años enteros, de 1 a 30."""
    texto = str(texto or "").strip()
    if not texto.isdigit() or not 1 <= int(texto) <= PLAZO_MAXIMO_ANIOS:
        return f"El plazo va en años enteros, de 1 a {PLAZO_MAXIMO_ANIOS}.", None
    return None, int(texto)


def dia_de_subida(subida_el) -> date:
    """El día argentino en que se subió. Lo hace el que compara, aunque llegue
    convertido (corolario 21)."""
    return subida_el.astimezone(ARGENTINA).date()


def es_de_mas_de_3_anios(foto: dict, corte: date) -> bool:
    return dia_de_subida(foto["subida_el"]) < corte


def _corte_de(foto: dict, corte) -> date | None:
    """`corte` puede ser una fecha (la misma para todos) o {tipo: fecha}. Un
    tipo que el mapa no conoce no vence (y un test exige que no exista)."""
    return corte.get(foto["tipo"]) if isinstance(corte, dict) else corte


def es_vencida(foto: dict, corte) -> bool:
    limite = _corte_de(foto, corte)
    return limite is not None and dia_de_subida(foto["subida_el"]) < limite


def fotos_para_borrar(fotos: list[dict], corte) -> list[dict]:
    """Las que se pueden borrar por PLAZO: vencidas, el archivo todavía está y
    no están protegidas. `corte` es una fecha o {tipo: fecha}."""
    return [f for f in fotos if not f["ya_borrada"] and not f.get("protegida") and es_vencida(f, corte)]


def vencidas_protegidas(fotos: list[dict], corte) -> list[dict]:
    """Las vencidas que NO se borran (vale en cartera, remito sin facturar)."""
    return [f for f in fotos if not f["ya_borrada"] and f.get("protegida") and es_vencida(f, corte)]


def seleccion_a_mano(fotos: list[dict], tipo: str, anteriores_a: date) -> tuple[list[dict], list[dict]]:
    """El borrado a mano: las de un tipo subidas ANTES de `anteriores_a`, con
    el archivo todavía. Devuelve (se borran, se saltean por protegidas). Los
    tipos de plazo fijo no entran: vuelven las dos listas vacías."""
    if tipo in TIPOS_CON_PLAZO_FIJO:
        return [], []
    elegidas = [f for f in fotos if f["tipo"] == tipo and not f["ya_borrada"]
                and dia_de_subida(f["subida_el"]) < anteriores_a]
    return ([f for f in elegidas if not f.get("protegida")],
            [f for f in elegidas if f.get("protegida")])


def motivos_de_las_salteadas(salteadas: list[dict]) -> list[str]:
    """"3 de un vale sin cobrar, cruzar ni anular", uno por motivo."""
    cuenta: dict = {}
    for f in salteadas:
        cuenta[f["protegida"]] = cuenta.get(f["protegida"], 0) + 1
    return [f"{n} {TEXTO_DE_LA_PROTECCION.get(motivo, motivo)}" for motivo, n in sorted(cuenta.items())]


def bytes_de(fotos: list[dict], tamanos: dict | None):
    """Lo que ocupan, o None si el bucket no se pudo leer."""
    if tamanos is None:
        return None
    return sum(tamanos.get(f["ruta"], 0) for f in fotos)


def resumen_por_tipo(fotos: list[dict], tamanos: dict[str, int] | None, corte) -> list[dict]:
    """Una fila por tipo: cuántas hay y cuánto ocupan, y cuántas están
    VENCIDAS según el plazo de su tipo (`corte` es una fecha o {tipo: fecha}).
    Las vencidas protegidas se cuentan aparte y no suman a "viejas", que es lo
    que se borra. Las ya borradas no suman acá (su archivo no está).

    `tamanos` None es que el bucket no se pudo leer: los bytes van en None y
    la pantalla dice "sin dato" en vez de un cero que se lea como "vacío".
    """
    def _nueva(tipo, texto):
        return {"tipo": tipo, "texto": texto, "cantidad": 0, "bytes": 0, "viejas": 0, "bytes_viejas": 0,
                "protegidas": 0, "corte": _corte_de({"tipo": tipo}, corte)}
    filas = {tipo: _nueva(tipo, texto) for tipo, texto in TEXTO_DEL_TIPO.items()}
    for foto in fotos:
        if foto["ya_borrada"]:
            continue
        fila = filas.setdefault(foto["tipo"], _nueva(foto["tipo"], foto["tipo"]))
        tamano = (tamanos or {}).get(foto["ruta"], 0)
        fila["cantidad"] += 1
        fila["bytes"] += tamano
        if es_vencida(foto, corte):
            if foto.get("protegida"):
                fila["protegidas"] += 1
            else:
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

# Plan Pro: 100 GB de almacenamiento incluido por ORGANIZACIÓN, no por base
# (dato del dueño, 01/10). Frutamax, Palmala y Ganadería suman contra la misma
# cuota. Cada app ve solo su base, así que el porcentaje de acá es lo que pone
# ESTA base. Si cambia el plan, cambia este número y nada más.
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
