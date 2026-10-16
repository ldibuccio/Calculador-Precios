"""LA CARGA EN DOS PASOS (dueño, 16/10): Palmala Cruces, Caja, Banco e
Inversiones cargan igual que "Aplicar cheques".

Paso 1, elegir: archivos (fotos de cheques, comprobantes, Excel, PDF) y/o
filas a mano, que se pueden usar juntos. Paso 2, revisar: un renglón por
movimiento, todo editable, agrupado por archivo (los a mano, en su grupo),
con el encabezado del grupo y "Para todos" para cambiar varios de una vez, y
"Confirmar todos" guarda los que están bien.

Lo que es de cada cuenta (qué campos tiene un renglón, qué le falta) está en
`core/palmala_cruces.py` y `core/cuentas.py`; acá va lo que comparten. Nada
de acá toca la base.
"""

# El grupo de las filas cargadas a mano (los archivos son 0, 1, 2...).
A_MANO = -1

# Cuántas filas vacías puede pedir el paso 1 de una vez.
MAX_FILAS_A_MANO = 50

REPETIDO_EN_LA_CARGA = "repetido: ya está más arriba en esta carga"


def cuantas_a_mano(texto) -> int:
    """Las filas a mano que se pidieron, entre 0 y MAX_FILAS_A_MANO."""
    try:
        return max(0, min(MAX_FILAS_A_MANO, int(str(texto or "0").strip() or 0)))
    except ValueError:
        return 0


def tipo_de_archivo(nombre: str) -> str | None:
    """"excel" (se lee por sus columnas), "foto" (la lee la IA: una foto o un
    PDF) o None si no es ninguno de los dos."""
    nombre = (nombre or "").lower()
    if nombre.endswith((".xlsx", ".xls", ".csv")):
        return "excel"
    if nombre.endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif")):
        return "foto"
    return None


def como_se_cargo(renglon: dict, tipos: list[str]) -> str:
    """Lo que la base guarda de cada movimiento: "a_mano", "foto" o "excel"."""
    archivo = renglon.get("archivo", A_MANO)
    return tipos[archivo] if 0 <= archivo < len(tipos) and tipos[archivo] in ("foto", "excel") else "a_mano"


def poner(renglon: dict, cambios: dict) -> None:
    """Pone en el renglón lo que viene con valor; lo que quedó en "No
    cambiar" (vacío) no se toca."""
    for campo, valor in cambios.items():
        if valor not in (None, ""):
            renglon[campo] = valor


def poner_a_los_tildados(renglones: list[dict], cambios: dict, *, sin_tildar_tambien: bool = False) -> int | None:
    """"Para todos": a los tildados. Sin ninguno tildado devuelve None (la
    pantalla pregunta si va a TODOS) salvo que ya se dijo que sí. Devuelve a
    cuántos se puso."""
    vivos = [r for r in renglones if not r.get("sacar")]
    destino = [r for r in vivos if r.get("tildado")]
    if not destino:
        if not sin_tildar_tambien:
            return None
        destino = vivos
    for r in destino:
        poner(r, cambios)
        r["tildado"] = False
    return len(destino)


def poner_en_el_grupo(renglones: list[dict], archivo: int, cambios: dict) -> int:
    """El encabezado de un grupo: lo elegido va a todos los del grupo."""
    destino = [r for r in renglones if r.get("archivo", A_MANO) == archivo and not r.get("sacar")]
    for r in destino:
        poner(r, cambios)
    return len(destino)


def repetidos(renglones: list[dict], clave, ya_cargados: dict) -> list[str | None]:
    """Por renglón, por qué parece repetido (None si no). `clave(r)` dice
    qué lo identifica (None: no se compara); `ya_cargados` son las claves que
    ya están en la base, con cómo se las nombra. Dentro de la carga se marca
    el SEGUNDO, no el primero. El que se tildó "No es repetido" no se marca:
    dos pagos iguales el mismo día pueden existir."""
    vistas: set = set()
    motivos: list[str | None] = []
    for r in renglones:
        if r.get("sacar"):
            motivos.append(None)
            continue
        k = clave(r)
        if k is None or r.get("no_es_repetido"):
            motivos.append(None)
        elif k in ya_cargados:
            motivos.append(f"repetido: ya está cargado ({ya_cargados[k]})")
        elif k in vistas:
            motivos.append(REPETIDO_EN_LA_CARGA)
        else:
            motivos.append(None)
        if k is not None:
            vistas.add(k)
    return motivos


def vivos(renglones: list[dict]) -> list[dict]:
    return [r for r in renglones if not r.get("sacar")]


def grupos(renglones: list[dict], problemas: list[list[str]], nombres: list[str], total) -> list[dict]:
    """Un grupo por archivo, en el orden en que se subieron, y al final los
    cargados a mano. `total(renglones)` dice cuánto suman (como texto: en
    Palmala hay pesos y dólares)."""
    por_archivo: dict[int, list[int]] = {}
    for i, r in enumerate(renglones):
        por_archivo.setdefault(r.get("archivo", A_MANO), []).append(i)
    salida = []
    for archivo in sorted(por_archivo, key=lambda a: (a == A_MANO, a)):
        indices = por_archivo[archivo]
        de_este = [i for i in indices if not renglones[i].get("sacar")]
        salida.append({
            "archivo": archivo,
            "titulo": "Cargados a mano" if archivo == A_MANO else (
                nombres[archivo] if 0 <= archivo < len(nombres) and nombres[archivo] else f"Archivo {archivo + 1}"),
            "indices": indices, "cuantos": len(de_este),
            "con_problema": sum(1 for i in de_este if problemas[i]),
            "total_texto": total([renglones[i] for i in de_este]),
        })
    return salida


def resumen(renglones: list[dict], problemas: list[list[str]]) -> dict:
    """La línea de arriba: X movimientos · $Y · Z bien · W con problema."""
    de_la_carga = [p for r, p in zip(renglones, problemas) if not r.get("sacar")]
    return {"cuantos": len(de_la_carga), "bien": sum(1 for p in de_la_carga if not p),
            "con_problema": sum(1 for p in de_la_carga if p)}
