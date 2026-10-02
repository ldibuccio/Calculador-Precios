"""PLAN B DE BACKUP (dueño, 02/10): las reglas puras.

Tres partes, cada una con su copia, en DOS lugares independientes (el
OneDrive y el Google Drive de Lionel), todo cifrado con rclone crypt:

- CÓDIGO: un `git bundle --all` diario.
- BASES: un `pg_dump` diario de los tres proyectos de Supabase, que se
  RESTAURA todos los días para contar que sirve.
- FOTOS: todos los buckets, incremental, y nunca se borra nada.

Acá no se habla con nada: se decide qué se conserva al rotar, cómo se llama
cada copia, qué esquemas van al dump, cuándo dos conteos coinciden y qué
quiere decir "el último backup exitoso". La corrida vive en
`scripts/backup.py` y la pantalla de Gerencia en app/.

UN BACKUP DE UNA PARTE ES EXITOSO SI LLEGÓ A LOS DOS DESTINOS (y, en las
bases, si lo que se bajó de cada destino se restauró y dio los mismos
conteos). Con uno solo, la parte se ve como fallada y la pantalla dice cuál.
"""

import re
from datetime import date, datetime, timedelta

PARTES = ("codigo", "bases", "fotos")
TEXTO_DE_LA_PARTE = {"codigo": "Código", "bases": "Bases", "fotos": "Fotos"}

DESTINOS = ("onedrive", "gdrive")
TEXTO_DEL_DESTINO = {"onedrive": "OneDrive", "gdrive": "Google Drive"}

# Rotación de código y bases (dueño, 02/10): las diarias de los últimos 30
# días, más una por mes de los últimos 12. Las fotos NO rotan.
DIAS_DE_DIARIAS = 30
MESES_DE_MENSUALES = 12

# Una parte cuyo último backup exitoso tiene más de esto sale en las alertas
# de Gerencia. "Más de", no "igual".
HORAS_PARA_LA_ALERTA = 48

# Los tres proyectos de Supabase y su referencia. Ganadería no es de este
# sistema, pero entra igual (dueño, 02/10).
PROYECTOS = {
    "frutamax": "opivgeqpjgtlduxcozqz",
    "palmala": "uygzmbqwharuhtnzqwpp",
    "ganaderia": "rhmrjguqtjsaoykhogln",
}

# LOS ESQUEMAS QUE MANEJA SUPABASE, y por eso NO van al pg_dump: los crea y
# los actualiza la plataforma, y un proyecto nuevo ya los trae. Restaurarlos
# encima pisaría su versión. Lo que sí hace falta de dos de ellos va aparte,
# como DATOS (ver TABLAS_DE_SUPABASE). Todo esquema que NO esté acá (public,
# y cualquiera que una app haya creado) va entero al dump: es lo que la app
# escribió y no se puede volver a fabricar.
ESQUEMAS_DE_SUPABASE = frozenset({
    "auth", "storage", "realtime", "_realtime", "extensions", "graphql", "graphql_public",
    "pgbouncer", "pgsodium", "pgsodium_masks", "vault", "supabase_functions",
    "supabase_migrations", "net", "cron", "_analytics", "pgtle", "information_schema",
})

# Lo que hace falta de los esquemas de Supabase para reconstruir de verdad,
# como DATOS en CSV (no se restaura encima del de la plataforma: se usa para
# volver a poner lo que importa):
# - storage.buckets y storage.objects: qué buckets había y CUÁNDO se subió
#   cada foto. Esta app lee `storage.objects.created_at` (el mes a mes, el
#   plazo de 3 años desde la subida) y volver a subir los archivos le pondría
#   la fecha de hoy a todos.
# - auth.users y auth.identities: los usuarios de login. Este sistema no usa
#   el login de Supabase, pero Ganadería puede: sin estas dos, nadie entra.
TABLAS_DE_SUPABASE = ("storage.buckets", "storage.objects", "auth.users", "auth.identities")

_FECHA = re.compile(r"(\d{4}-\d{2}-\d{2})")


def esquemas_a_respaldar(esquemas: list[str]) -> list[str]:
    """Los esquemas que van al dump: todos menos los de Postgres y los de
    Supabase. Ordenados, para que dos corridas digan lo mismo."""
    return sorted(e for e in esquemas
                  if e not in ESQUEMAS_DE_SUPABASE and not e.startswith("pg_"))


def nombre_del_bundle(fecha: date) -> str:
    return f"calculador-precios_{fecha.isoformat()}.bundle"


def fecha_de(nombre: str) -> date | None:
    """La fecha que lleva el nombre de una copia (archivo o carpeta), o None
    si no lleva ninguna: lo que no tiene fecha no lo toca la rotación."""
    hallada = _FECHA.search(nombre)
    if not hallada:
        return None
    try:
        return date.fromisoformat(hallada.group(1))
    except ValueError:
        return None


def que_se_conserva(fechas, hoy: date) -> set[date]:
    """Las fechas que la rotación deja: las de los últimos DIAS_DE_DIARIAS
    días (hoy incluido) y, de cada uno de los últimos MESES_DE_MENSUALES
    meses (el de hoy incluido), la PRIMERA copia de ese mes.

    La primera y no la última: la última del mes en curso cambia todos los
    días, y la mensual tiene que ser una foto quieta del mes.
    """
    fechas = sorted(set(fechas))
    desde_diarias = hoy - timedelta(days=DIAS_DE_DIARIAS - 1)
    conservar = {f for f in fechas if desde_diarias <= f <= hoy}
    meses = set()
    anio, mes = hoy.year, hoy.month
    for _ in range(MESES_DE_MENSUALES):
        meses.add((anio, mes))
        anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    primeras = {}
    for f in fechas:
        if (f.year, f.month) in meses and f <= hoy:
            primeras.setdefault((f.year, f.month), f)
    return conservar | set(primeras.values())


def que_se_borra(nombres, hoy: date) -> list[str]:
    """Los nombres que la rotación borra. Lo que no lleva fecha se deja."""
    con_fecha = {n: fecha_de(n) for n in nombres}
    se_quedan = que_se_conserva([f for f in con_fecha.values() if f], hoy)
    return sorted(n for n, f in con_fecha.items() if f and f not in se_quedan)


def diferencias(manifiesto: dict, restaurada: dict) -> list[str]:
    """Qué no coincide entre lo que tenía el origen (el manifiesto, sacado en
    la MISMA foto que el dump) y lo que dio la restauración. Vacío = coincide.

    Se compara la cantidad de tablas y las filas de TODAS (no de unas pocas
    elegidas): contar es barato en estas bases, y "las principales" sería una
    lista escrita a mano que envejece.
    """
    malas = []
    if manifiesto["tablas"] != restaurada["tablas"]:
        malas.append(f"tablas {manifiesto['tablas']} en el origen y {restaurada['tablas']} restauradas")
    for tabla, filas in sorted(manifiesto["filas"].items()):
        otra = restaurada["filas"].get(tabla)
        if otra != filas:
            malas.append(f"{tabla}: {filas} filas en el origen y {otra} restauradas")
    for tabla in sorted(set(restaurada["filas"]) - set(manifiesto["filas"])):
        malas.append(f"{tabla}: restaurada y no estaba en el origen")
    return malas


def estado_de_las_partes(corridas: list[dict], ahora: datetime) -> list[dict]:
    """Para Gerencia: por parte, el último backup EXITOSO (los dos destinos
    bien) y, si la última corrida no fue exitosa, qué destino falló.

    `corridas`: {parte, onedrive_ok, gdrive_ok, detalle, terminada_el}, de
    cualquier orden. Una parte sin ninguna corrida exitosa es VIEJA: no hay
    backup, y eso es lo peor que puede pasar.
    """
    salida = []
    for parte in PARTES:
        de_la_parte = sorted((c for c in corridas if c["parte"] == parte), key=lambda c: c["terminada_el"])
        exitosas = [c for c in de_la_parte if c["onedrive_ok"] and c["gdrive_ok"]]
        ultima_exitosa = exitosas[-1]["terminada_el"] if exitosas else None
        ultima = de_la_parte[-1] if de_la_parte else None
        fallaron = []
        if ultima and not (ultima["onedrive_ok"] and ultima["gdrive_ok"]):
            fallaron = [d for d in DESTINOS if not ultima[f"{d}_ok"]]
        vieja = ultima_exitosa is None or (ahora - ultima_exitosa) > timedelta(hours=HORAS_PARA_LA_ALERTA)
        salida.append({
            "parte": parte, "texto": TEXTO_DE_LA_PARTE[parte],
            "ultima_exitosa": ultima_exitosa, "vieja": vieja,
            "ultima_corrida": ultima["terminada_el"] if ultima else None,
            "fallaron": fallaron, "texto_fallaron": [TEXTO_DEL_DESTINO[d] for d in fallaron],
            "detalle": ultima["detalle"] if ultima and fallaron else None,
        })
    return salida


def partes_viejas(estado: list[dict]) -> int:
    return sum(1 for e in estado if e["vieja"])
