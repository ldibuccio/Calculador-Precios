"""PLAN B DE BACKUP (dueño, 02/10): la corrida diaria.

    python3 scripts/backup.py codigo     # git bundle --all
    python3 scripts/backup.py bases      # pg_dump de los tres proyectos, y RESTAURADOS
    python3 scripts/backup.py fotos      # todos los buckets, incremental

Cada parte va a los DOS destinos (los remotos `onedrive` y `gdrive` de rclone),
cifrada con rclone crypt, y al final graba en la base cómo le fue en cada
destino. Sale con 0 solo si los dos salieron bien. Las reglas (qué se
conserva, qué esquemas van, cuándo coinciden los conteos) viven en
core/backup.py; acá se habla con git, pg_dump, rclone y la base.

LO QUE NECESITA DEL ENTORNO (en el workflow, todo sale de los secrets):

    BACKUP_CLAVE              la clave del cifrado. SIN ELLA EL BACKUP NO SIRVE.
    RCLONE_CONFIG             el archivo con los remotos `onedrive` y `gdrive`
    <P>_DB_URL                la conexión de cada proyecto (P = FRUTAMAX,
                              PALMALA, GANADERIA). Frutamax y Palmala con
                              postgres; Ganadería con backup_lectura
    <P>_S3_KEY_ID, <P>_S3_SECRET, <P>_S3_REGION
                              las llaves S3 del Storage de cada proyecto
    BACKUP_PRUEBA_URL         un Postgres descartable donde se restaura
    ESTADO_FRUTAMAX_URL, ESTADO_PALMALA_URL
                              la conexión del rol que SOLO escribe el estado

Para los tests, BACKUP_CARPETA cambia la carpeta de los destinos,
<P>_FOTOS_ORIGEN reemplaza el Storage por un remoto cualquiera de rclone,
BACKUP_PROYECTOS achica la lista y BACKUP_HOY fija el día.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.backup import (  # noqa: E402
    DESTINOS, PROYECTOS, TEXTO_DEL_DESTINO, diferencias,
    esquemas_a_respaldar, nombre_del_bundle, que_se_borra, tablas_de_supabase_de,
)

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")
RCLONE_FLAGS = ["--retries", "3", "--low-level-retries", "10", "--transfers", "4"]
LEEME = "LEEME-RESTAURAR.md"


class Falla(Exception):
    """Algo de una parte en un destino no salió. El mensaje va a la pantalla
    de Gerencia, así que va en criollo y sin credenciales."""


# --- el entorno -------------------------------------------------------------------

def hoy() -> date:
    fijo = os.environ.get("BACKUP_HOY")
    return date.fromisoformat(fijo) if fijo else datetime.now(ARGENTINA).date()


def carpeta() -> str:
    return os.environ.get("BACKUP_CARPETA", "Backup-Sistema")


def proyectos() -> list[str]:
    lista = os.environ.get("BACKUP_PROYECTOS")
    return [p.strip() for p in lista.split(",") if p.strip()] if lista else list(PROYECTOS)


def _variable(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise Falla(f"falta el secret {nombre}")
    return valor


def _ejecutar(argumentos, *, entorno=None, entrada=None, cwd=None):
    r = subprocess.run(argumentos, capture_output=True, text=True, env=entorno, input=entrada, cwd=cwd)
    if r.returncode != 0:
        ultimas = (r.stderr or r.stdout).strip().splitlines()[-6:]
        raise Falla(f"{Path(argumentos[0]).name} {argumentos[1] if len(argumentos) > 1 else ''} "
                    f"salió con {r.returncode}: " + " | ".join(ultimas))
    return r.stdout


_ENTORNO = None


def entorno_rclone() -> dict:
    """Los dos remotos CIFRADOS se arman acá, con la clave, y no viven en
    ningún archivo: `cifrado_onedrive` y `cifrado_gdrive`, cada uno dentro de
    `<remoto>:<carpeta>/cifrado`. La clave es la contraseña de rclone crypt y
    la sal queda vacía (la de fábrica de rclone): para descifrar a mano alcanza
    con la clave, que es lo que dice RESTAURAR.md."""
    global _ENTORNO
    if _ENTORNO is None:
        entorno = dict(os.environ)
        oscura = _ejecutar(["rclone", "obscure", "-"], entrada=_variable("BACKUP_CLAVE") + "\n").strip()
        for destino in DESTINOS:
            prefijo = f"RCLONE_CONFIG_CIFRADO_{destino.upper()}_"
            entorno[prefijo + "TYPE"] = "crypt"
            entorno[prefijo + "REMOTE"] = f"{destino}:{carpeta()}/cifrado"
            entorno[prefijo + "PASSWORD"] = oscura
        _ENTORNO = entorno
    return _ENTORNO


def rclone(*argumentos) -> str:
    return _ejecutar(["rclone", *argumentos, *RCLONE_FLAGS], entorno=entorno_rclone())


def cifrado(destino: str, ruta: str = "") -> str:
    return f"cifrado_{destino}:{ruta}"


def subir(local: Path, destino: str, ruta: str) -> None:
    """Copia la carpeta y después COMPRUEBA cada archivo contra lo subido
    (cryptcheck descifra la cabecera y compara el checksum). Un `copy` que
    salió con 0 no es una prueba."""
    rclone("copy", str(local), cifrado(destino, ruta))
    rclone("cryptcheck", str(local), cifrado(destino, ruta), "--one-way")


def rotar(destino: str, ruta: str) -> list[str]:
    """Borra lo que la regla de rotación no conserva. Se llama SOLO después
    de un backup exitoso en ese destino: si los backups fallan un mes, no se
    borra nada viejo."""
    nombres = [n for n in rclone("lsf", cifrado(destino, ruta)).splitlines() if n.strip()]
    borrados = que_se_borra(nombres, hoy())
    for nombre in borrados:
        if nombre.endswith("/"):
            rclone("purge", cifrado(destino, f"{ruta}/{nombre.rstrip('/')}"))
        else:
            rclone("deletefile", cifrado(destino, f"{ruta}/{nombre}"))
    return borrados


def _por_destino(funcion) -> dict:
    """Corre `funcion(destino)` en cada destino: que falle uno no frena el otro."""
    resultados = {}
    for destino in DESTINOS:
        try:
            resultados[destino] = (True, funcion(destino) or "")
        except Falla as falla:
            resultados[destino] = (False, str(falla))
        except Exception as error:  # noqa: BLE001 - lo inesperado también es una falla del destino
            resultados[destino] = (False, f"error inesperado: {error}")
        print(f"  {TEXTO_DEL_DESTINO[destino]}: {'BIEN' if resultados[destino][0] else 'MAL'} "
              f"{resultados[destino][1]}", flush=True)
    return resultados


# --- CÓDIGO -----------------------------------------------------------------------

def parte_codigo(repo: Path) -> dict:
    fecha = hoy()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "subir").mkdir()
        bundle = tmp / "subir" / nombre_del_bundle(fecha)
        _ejecutar(["git", "-C", str(repo), "bundle", "create", str(bundle), "--all"])
        cabezas = _ejecutar(["git", "bundle", "list-heads", str(bundle)])
        if not cabezas.strip():
            raise Falla("el bundle salió sin ninguna rama")

        def a_un_destino(destino):
            subir(tmp / "subir", destino, "codigo")
            vuelta = tmp / f"vuelta_{destino}"
            rclone("copyto", cifrado(destino, f"codigo/{bundle.name}"), str(vuelta / bundle.name))
            if _ejecutar(["git", "bundle", "list-heads", str(vuelta / bundle.name)]) != cabezas:
                raise Falla("el bundle que se bajó no tiene las mismas ramas")
            clon = tmp / f"clon_{destino}"
            _ejecutar(["git", "clone", "-q", str(vuelta / bundle.name), str(clon)])
            leeme = RAIZ / "RESTAURAR.md"
            _ejecutar(["rclone", "copyto", str(leeme), f"{destino}:{carpeta()}/{LEEME}", *RCLONE_FLAGS],
                      entorno=entorno_rclone())
            borrados = rotar(destino, "codigo")
            return f"{len(cabezas.splitlines())} referencias" + (f", rotó {len(borrados)}" if borrados else "")

        return _por_destino(a_un_destino)


# --- BASES ------------------------------------------------------------------------

def _conectar(url):
    import psycopg2
    return psycopg2.connect(url)


def respaldar_base(proyecto: str, url: str, salida: Path) -> dict:
    """Saca el dump, los conteos y los CSV de Supabase de UNA base, todo en
    la MISMA foto (un snapshot exportado que pg_dump reusa). Así el manifiesto
    describe exactamente lo que el dump tiene, y la restauración se compara
    contra eso sin que una escritura de las 4 de la mañana mueva un número."""
    salida.mkdir(parents=True, exist_ok=True)
    conexion = _conectar(url)
    try:
        conexion.set_session(isolation_level="REPEATABLE READ", readonly=True)
        with conexion.cursor() as cursor:
            cursor.execute("SELECT pg_export_snapshot(), current_setting('server_version')")
            snapshot, version = cursor.fetchone()
            cursor.execute(
                "SELECT n.nspname FROM pg_namespace n WHERE NOT EXISTS ("
                "  SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_namespace'::regclass "
                "  AND d.objid = n.oid AND d.deptype = 'e')")
            esquemas = esquemas_a_respaldar([f[0] for f in cursor.fetchall()])
            if not esquemas:
                raise Falla(f"{proyecto}: no hay ningún esquema para respaldar")
            cursor.execute(
                "SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relkind IN ('r', 'p') AND n.nspname = ANY(%s) AND NOT EXISTS ("
                "  SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass "
                "  AND d.objid = c.oid AND d.deptype = 'e') ORDER BY 1, 2", (esquemas,))
            tablas = cursor.fetchall()
            filas = {}
            for esquema, tabla in tablas:
                cursor.execute(f'SELECT count(*) FROM "{esquema}"."{tabla}"')
                filas[f"{esquema}.{tabla}"] = cursor.fetchone()[0]
            cursor.execute(
                "SELECT e.extname, n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace "
                "WHERE n.nspname = ANY(%s) ORDER BY 1", (esquemas,))
            extensiones = [list(f) for f in cursor.fetchall()]
            # Los roles que nombran las POLÍTICAS: el dump no los trae (son
            # de todo el servidor) y sin ellos un CREATE POLICY no restaura.
            # En Ganadería son bot_lectura y bot_escritura (medido el 02/10).
            cursor.execute(
                "SELECT DISTINCT unnest(roles)::text FROM pg_policies WHERE schemaname = ANY(%s) ORDER BY 1",
                (esquemas,))
            roles = [f[0] for f in cursor.fetchall() if f[0] != "public"]

            argumentos = ["pg_dump", "--dbname", url, "--snapshot", snapshot, "--format", "custom",
                          "--file", str(salida / "base.dump")]
            for esquema in esquemas:
                argumentos += ["--schema", f'"{esquema}"']
            _ejecutar(argumentos)

            supabase = {}
            # Ganadería no las intenta: su usuario no las lee (core/backup.py).
            for tabla in tablas_de_supabase_de(proyecto):
                cursor.execute("SELECT to_regclass(%s) IS NOT NULL", (tabla,))
                if not cursor.fetchone()[0]:
                    supabase[tabla] = None
                    continue
                with open(salida / f"{tabla}.csv", "w", encoding="utf-8", newline="") as archivo:
                    cursor.copy_expert(f"COPY (SELECT * FROM {tabla}) TO STDOUT WITH CSV HEADER", archivo)
                cursor.execute(f"SELECT count(*) FROM {tabla}")
                supabase[tabla] = cursor.fetchone()[0]
        manifiesto = {"proyecto": proyecto, "fecha": hoy().isoformat(), "servidor": version,
                      "esquemas": esquemas, "extensiones": extensiones, "roles": roles,
                      "tablas": len(tablas), "filas": filas, "supabase": supabase}
    finally:
        conexion.rollback()
        conexion.close()
    (salida / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifiesto


# Lo mínimo de Supabase que un dump de `public` espera encontrar: los roles a
# los que les da permisos, `extensions` con las de siempre, y las funciones de
# `auth` que una política puede usar. Un proyecto nuevo de Supabase ya lo trae;
# un Postgres pelado no, y sin esto la restauración de prueba fallaría por algo
# que no es del backup.
PREPARACION_COMO_SUPABASE = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role NOLOGIN; END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA extensions;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS 'SELECT NULL::uuid';
CREATE OR REPLACE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS 'SELECT NULL::text';
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb LANGUAGE sql STABLE AS 'SELECT NULL::jsonb';
"""


def lista_para_restaurar(lista: str) -> str:
    """La lista de pg_restore SIN la creación del esquema `public` ni su
    comentario: toda base nueva —un Postgres pelado o un proyecto nuevo de
    Supabase— ya lo trae, y `CREATE SCHEMA public` corta la restauración con
    "already exists". Todo lo demás del esquema se restaura igual. RESTAURAR.md
    hace exactamente esto a mano."""
    return "".join(linea for linea in lista.splitlines(keepends=True)
                   if " SCHEMA - public " not in linea and " COMMENT - SCHEMA public " not in linea)


def _url_de_base(url: str, base: str) -> str:
    from urllib.parse import urlsplit, urlunsplit
    partes = urlsplit(url)
    return urlunsplit((partes.scheme, partes.netloc, f"/{base}", partes.query, partes.fragment))


def probar_restauracion(carpeta_dump: Path, url_prueba: str, nombre: str) -> list[str]:
    """Restaura el dump en una base NUEVA del Postgres descartable y la cuenta.
    Devuelve las diferencias contra el manifiesto (vacío = coincide). Un
    pg_restore con un solo error ya es una falla: `--exit-on-error`."""
    manifiesto = json.loads((carpeta_dump / "manifiesto.json").read_text(encoding="utf-8"))
    admin = _conectar(url_prueba)
    admin.autocommit = True
    try:
        with admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{nombre}"')
            cursor.execute(f'CREATE DATABASE "{nombre}"')
        url = _url_de_base(url_prueba, nombre)
        _ejecutar(["psql", "-q", "-v", "ON_ERROR_STOP=1", "-d", url, "-c", PREPARACION_COMO_SUPABASE])
        for rol in manifiesto.get("roles", []):
            _ejecutar(["psql", "-q", "-v", "ON_ERROR_STOP=1", "-d", url, "-c",
                       "DO $r$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                       f"'{rol.replace(chr(39), chr(39) * 2)}') THEN CREATE ROLE \"{rol}\" NOLOGIN; END IF; END $r$"])
        for extension, esquema in manifiesto.get("extensiones", []):
            if esquema == "public":
                _ejecutar(["psql", "-q", "-v", "ON_ERROR_STOP=1", "-d", url, "-c",
                           f'CREATE EXTENSION IF NOT EXISTS "{extension}" SCHEMA public'])
        lista = carpeta_dump / "restaurar.lista"
        lista.write_text(lista_para_restaurar(_ejecutar(["pg_restore", "--list", str(carpeta_dump / "base.dump")])),
                         encoding="utf-8")
        _ejecutar(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error",
                   "--use-list", str(lista), "--dbname", url, str(carpeta_dump / "base.dump")])
        restaurada = {"filas": {}}
        conexion = _conectar(url)
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relkind IN ('r', 'p') AND n.nspname = ANY(%s) AND NOT EXISTS ("
                    "  SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass "
                    "  AND d.objid = c.oid AND d.deptype = 'e')", (manifiesto["esquemas"],))
                tablas = cursor.fetchall()
                for esquema, tabla in tablas:
                    cursor.execute(f'SELECT count(*) FROM "{esquema}"."{tabla}"')
                    restaurada["filas"][f"{esquema}.{tabla}"] = cursor.fetchone()[0]
            restaurada["tablas"] = len(tablas)
        finally:
            conexion.close()
        malas = diferencias(manifiesto, restaurada)
        for tabla, filas in manifiesto["supabase"].items():
            if filas is None:
                continue
            archivo = carpeta_dump / f"{tabla}.csv"
            if not archivo.exists():
                malas.append(f"falta el CSV de {tabla}")
                continue
            with open(archivo, encoding="utf-8", newline="") as abierto:
                registros = sum(1 for _ in csv.reader(abierto)) - 1
            if registros != filas:
                malas.append(f"{tabla}: {filas} filas en el origen y {registros} en el CSV")
        return malas
    finally:
        with admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{nombre}"')
        admin.close()


def parte_bases() -> dict:
    fecha = hoy().isoformat()
    url_prueba = _variable("BACKUP_PRUEBA_URL")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        salida = tmp / "subir"
        respaldadas, fallas = [], []
        for proyecto in proyectos():
            try:
                respaldar_base(proyecto, _variable(f"{proyecto.upper()}_DB_URL"), salida / fecha / proyecto)
                respaldadas.append(proyecto)
                print(f"  {proyecto}: dump hecho", flush=True)
            except Exception as error:  # noqa: BLE001 - una base que no se pudo leer es una falla, no un corte
                fallas.append(f"{proyecto} no se pudo respaldar: {error}")
                print(f"  {proyecto}: NO SE PUDO RESPALDAR: {error}", flush=True)
        if not respaldadas:
            return {d: (False, "; ".join(fallas)) for d in DESTINOS}

        def a_un_destino(destino):
            subir(salida, destino, "bases")
            malas = list(fallas)
            for proyecto in respaldadas:
                vuelta = tmp / f"vuelta_{destino}" / proyecto
                rclone("copy", cifrado(destino, f"bases/{fecha}/{proyecto}"), str(vuelta))
                diferentes = probar_restauracion(vuelta, url_prueba, f"prueba_{proyecto}_{destino}")
                malas += [f"{proyecto}: {d}" for d in diferentes[:3]]
            if malas:
                raise Falla("; ".join(malas))
            borrados = rotar(destino, "bases")
            return f"{len(respaldadas)} bases restauradas" + (f", rotó {len(borrados)}" if borrados else "")

        return _por_destino(a_un_destino)


# --- FOTOS ------------------------------------------------------------------------

def origen_de_fotos(proyecto: str) -> str:
    """El Storage de un proyecto, por su API S3. En los tests,
    <P>_FOTOS_ORIGEN lo reemplaza por cualquier remoto de rclone."""
    propio = os.environ.get(f"{proyecto.upper()}_FOTOS_ORIGEN")
    if propio:
        return propio
    entorno = entorno_rclone()
    prefijo = f"RCLONE_CONFIG_S3_{proyecto.upper()}_"
    entorno[prefijo + "TYPE"] = "s3"
    entorno[prefijo + "PROVIDER"] = "Other"
    entorno[prefijo + "ACCESS_KEY_ID"] = _variable(f"{proyecto.upper()}_S3_KEY_ID")
    entorno[prefijo + "SECRET_ACCESS_KEY"] = _variable(f"{proyecto.upper()}_S3_SECRET")
    entorno[prefijo + "REGION"] = _variable(f"{proyecto.upper()}_S3_REGION")
    entorno[prefijo + "ENDPOINT"] = f"https://{PROYECTOS[proyecto]}.supabase.co/storage/v1/s3"
    entorno[prefijo + "FORCE_PATH_STYLE"] = "true"
    return f"s3_{proyecto}:"


def _contar_archivos(remoto: str) -> int:
    return len([n for n in rclone("lsf", "-R", "--files-only", remoto).splitlines() if n.strip()])


def parte_fotos() -> dict:
    """Incremental y sin borrar nunca: `copy --ignore-existing` sube solo lo
    nuevo y no pisa nada (una foto no cambia), y no hay `sync`, así que lo
    que el sistema borra por plazo sigue en el backup. Después, cryptcheck
    compara el checksum de cada archivo del origen contra el subido.

    LA LISTA SE TOMA AL ARRANCAR (dueño, 09/10): el 07/10 y el 08/10 el
    control dio rojo por UNA foto que se subió al Storage mientras corría la
    copia (no estaba en la copia y sí en el control). Así que antes de
    copiar se anota qué fotos hay en cada bucket, y la copia y el control
    trabajan SOLO sobre esa lista (`--files-from`), en los dos destinos. Las
    que entran después van en la copia siguiente."""
    origenes, fallas = {}, []
    listas = Path(tempfile.mkdtemp(prefix="fotos_al_arrancar_"))
    for proyecto in proyectos():
        try:
            origen = origen_de_fotos(proyecto)
            buckets = [b.rstrip("/") for b in rclone("lsf", "--dirs-only", origen).splitlines() if b.strip()]
            for bucket in buckets:
                (listas / f"{proyecto}__{bucket}.txt").write_text(
                    rclone("lsf", "-R", "--files-only", f"{origen}{bucket}"), encoding="utf-8")
            origenes[proyecto] = (origen, buckets)
        except Exception as error:  # noqa: BLE001
            fallas.append(f"{proyecto}: no se pudo leer el Storage: {error}")

    def a_un_destino(destino):
        malas, nuevos, total, sin_checksum = list(fallas), 0, 0, set()
        for proyecto, (origen, buckets) in origenes.items():
            for bucket in buckets:
                desde, hacia = f"{origen}{bucket}", cifrado(destino, f"fotos/{proyecto}/{bucket}")
                lista = str(listas / f"{proyecto}__{bucket}.txt")
                try:
                    antes = _contar_archivos(hacia) if _existe(hacia) else 0
                    rclone("copy", desde, hacia, "--ignore-existing", "--files-from-raw", lista)
                    if not _comprobar_fotos(desde, hacia, lista):
                        sin_checksum.add(f"{proyecto}/{bucket}")
                    despues = _contar_archivos(hacia)
                    nuevos += despues - antes
                    total += despues
                except Falla as falla:
                    malas.append(f"{proyecto}/{bucket}: {falla}")
        if malas:
            raise Falla("; ".join(malas)[:600])
        return (f"{nuevos} fotos nuevas, {total} en el backup"
                + (f" (comprobado por tamaño: {', '.join(sorted(sin_checksum))})" if sin_checksum else ""))

    return _por_destino(a_un_destino)


def _comprobar_fotos(desde: str, hacia: str, lista: str) -> bool:
    """Compara cada foto de la LISTA DEL ARRANQUE contra la subida. Primero
    por CHECKSUM (cryptcheck); si el origen no da checksums —un objeto S3
    subido en partes no trae MD5—, por TAMAÑO, que es lo que el dueño aceptó
    ("tamaño o checksum"). Devuelve True si fue por checksum. Una diferencia
    de verdad falla por los dos caminos."""
    try:
        rclone("cryptcheck", desde, hacia, "--one-way", "--files-from-raw", lista)
        return True
    except Falla as falla:
        if "hash" not in str(falla).lower():
            raise
    rclone("check", desde, hacia, "--one-way", "--size-only", "--files-from-raw", lista)
    return False


def _existe(remoto: str) -> bool:
    try:
        rclone("lsf", "--max-depth", "1", remoto)
        return True
    except Falla:
        return False


# --- EL ESTADO --------------------------------------------------------------------

def registrar(parte: str, resultados: dict) -> list[str]:
    """Graba cómo le fue a la parte en cada destino, en las DOS bases (la
    pantalla de Gerencia de cada una lee la suya). El rol solo puede INSERTAR
    en esta tabla: no hay RETURNING porque eso pide permiso de lectura."""
    detalle = "; ".join(f"{TEXTO_DEL_DESTINO[d]}: {msg}" for d, (ok, msg) in resultados.items() if not ok)
    no_grabo = []
    for variable in ("ESTADO_FRUTAMAX_URL", "ESTADO_PALMALA_URL"):
        try:
            conexion = _conectar(_variable(variable))
            try:
                with conexion.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO backups_corridas (parte, onedrive_ok, gdrive_ok, detalle) "
                        "VALUES (%s, %s, %s, %s)",
                        (parte, resultados["onedrive"][0], resultados["gdrive"][0], detalle[:1000] or None))
                conexion.commit()
            finally:
                conexion.close()
        except Exception as error:  # noqa: BLE001 - que no grabe en una no impide grabar en la otra
            no_grabo.append(f"{variable}: {error}")
            print(f"  NO SE PUDO GRABAR EL ESTADO en {variable}: {error}", flush=True)
    return no_grabo


def main(argumentos=None) -> int:
    lector = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lector.add_argument("parte", choices=["codigo", "bases", "fotos"])
    lector.add_argument("--repo", default=str(RAIZ), help="el repo a empaquetar (solo para codigo)")
    leido = lector.parse_args(argumentos)
    print(f"Backup de {leido.parte}, {hoy().isoformat()}", flush=True)
    try:
        if leido.parte == "codigo":
            resultados = parte_codigo(Path(leido.repo))
        elif leido.parte == "bases":
            resultados = parte_bases()
        else:
            resultados = parte_fotos()
    except Exception as error:  # noqa: BLE001 - lo que corta antes de llegar a los destinos falla en los dos
        print(f"  NO SE PUDO EMPEZAR: {error}", flush=True)
        resultados = {d: (False, str(error)) for d in DESTINOS}
    no_grabo = registrar(leido.parte, resultados)
    # Sin el estado grabado, Gerencia no se entera: eso también pone el CI en rojo.
    return 0 if all(ok for ok, _ in resultados.values()) and not no_grabo else 1


if __name__ == "__main__":
    sys.exit(main())
