"""Plan B de backup (dueño, 02/10).

Dos clases de test. Las REGLAS puras (core/backup.py): qué se conserva al
rotar, cuándo una parte está vieja, cuándo dos conteos coinciden. Y el
SIMULACRO de punta a punta (scripts/backup.py) contra Postgres y rclone de
verdad: los dos destinos son carpetas locales con el MISMO cifrado (crypt) que
van a tener OneDrive y Google Drive, la base de origen es la del humo con
filas, y la restauración corre en una base nueva. Lo único que no se puede
correr acá es la red real (Supabase, las dos nubes): eso lo prueba la primera
corrida del workflow.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core import backup as regla  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
CLAVE = "EJEMPLO-CLAVE-QWERT-ASDFG-ZXCVB"
HOY = date(2026, 3, 18)   # lejos del reloj real (corolario 95)


# --- LAS REGLAS ---------------------------------------------------------------------

def test_la_ROTACION_deja_30_diarias_y_la_PRIMERA_de_cada_uno_de_12_meses():
    fechas = [HOY - timedelta(days=n) for n in range(0, 500)]
    quedan = regla.que_se_conserva(fechas, HOY)
    diarias = {f for f in quedan if f > HOY - timedelta(days=30)}
    assert diarias == {HOY - timedelta(days=n) for n in range(30)}
    # la del día 30 (17/02) ya no es diaria, y no es primera de su mes
    assert HOY - timedelta(days=30) not in quedan
    mensuales = sorted(quedan - diarias)
    assert mensuales == sorted({date(a, m, 1) for a, m in
                                [(2025, 4), (2025, 5), (2025, 6), (2025, 7), (2025, 8), (2025, 9),
                                 (2025, 10), (2025, 11), (2025, 12), (2026, 1), (2026, 2)]})
    # marzo 2026 tiene su primera adentro de las diarias; abril 2025 es el mes 12
    assert date(2026, 3, 1) in quedan and date(2025, 3, 1) not in quedan


def test_la_mensual_es_la_PRIMERA_que_HAY_aunque_no_sea_el_dia_1():
    fechas = [date(2025, 12, 9), date(2025, 12, 20), date(2025, 12, 31)]
    assert regla.que_se_conserva(fechas, HOY) == {date(2025, 12, 9)}


def test_la_rotacion_NO_toca_lo_que_no_lleva_fecha():
    nombres = ["calculador-precios_2025-01-02.bundle", "LEEME.md", "2026-03-18/", "raro/"]
    assert regla.que_se_borra(nombres, HOY) == ["calculador-precios_2025-01-02.bundle"]


def test_los_ESQUEMAS_que_van_son_los_que_NO_son_de_Supabase():
    medidos = ["auth", "extensions", "graphql", "graphql_public", "information_schema", "memoria",
               "public", "realtime", "storage", "vault", "pg_toast"]
    assert regla.esquemas_a_respaldar(medidos) == ["memoria", "public"]


def test_DIFERENCIAS_ve_una_fila_de_menos_una_tabla_de_mas_y_la_cantidad():
    origen = {"tablas": 2, "filas": {"public.a": 3, "public.b": 0}}
    assert regla.diferencias(origen, {"tablas": 2, "filas": {"public.a": 3, "public.b": 0}}) == []
    malas = regla.diferencias(origen, {"tablas": 3, "filas": {"public.a": 2, "public.b": 0, "public.c": 1}})
    assert len(malas) == 3 and any("public.a: 3" in m for m in malas) and any("public.c" in m for m in malas)


def _corrida(parte, horas_atras, onedrive=True, gdrive=True, detalle=None, ahora=None):
    return {"parte": parte, "onedrive_ok": onedrive, "gdrive_ok": gdrive, "detalle": detalle,
            "terminada_el": ahora - timedelta(hours=horas_atras)}


def test_el_ESTADO_dice_cual_destino_FALLO_y_la_buena_es_la_de_los_DOS():
    ahora = datetime(2026, 3, 18, 10, tzinfo=timezone.utc)
    corridas = [_corrida("codigo", 30, ahora=ahora),
                _corrida("codigo", 6, gdrive=False, detalle="Google Drive: sin token", ahora=ahora),
                _corrida("bases", 48, ahora=ahora),
                _corrida("fotos", 49, ahora=ahora)]
    estado = {e["parte"]: e for e in regla.estado_de_las_partes(corridas, ahora)}
    assert estado["codigo"]["ultima_exitosa"] == ahora - timedelta(hours=30)
    assert estado["codigo"]["texto_fallaron"] == ["Google Drive"] and not estado["codigo"]["vieja"]
    assert "sin token" in estado["codigo"]["detalle"]
    # "más de" 48 horas, no "igual"
    assert estado["bases"]["vieja"] is False and estado["fotos"]["vieja"] is True
    assert regla.partes_viejas(list(estado.values())) == 1


def test_una_parte_SIN_NINGUNA_corrida_buena_es_VIEJA():
    ahora = datetime(2026, 3, 18, tzinfo=timezone.utc)
    estado = regla.estado_de_las_partes([_corrida("fotos", 1, onedrive=False, ahora=ahora)], ahora)
    assert all(e["vieja"] for e in estado) and estado[2]["texto_fallaron"] == ["OneDrive"]


def test_la_lista_de_restaurar_saca_SOLO_la_creacion_de_public():
    from scripts.backup import lista_para_restaurar
    lista = ("4; 2615 2200 SCHEMA - public pg_database_owner\n"
             "5; 2615 16 SCHEMA - memoria postgres\n"
             "4692; 0 0 COMMENT - SCHEMA public pg_database_owner\n"
             "220; 1259 1 TABLE public compras postgres\n")
    assert lista_para_restaurar(lista) == ("5; 2615 16 SCHEMA - memoria postgres\n"
                                           "220; 1259 1 TABLE public compras postgres\n")


# --- EL SIMULACRO ---------------------------------------------------------------------

def _hace_falta(que):
    if OBLIGATORIO:
        pytest.fail(f"HUMO_OBLIGATORIO=1 y falta {que}: el backup no se verificó")
    pytest.skip(f"sin {que}")


@pytest.fixture
def simulacro(tmp_path, monkeypatch):
    if not hay_postgres():
        _hace_falta("Postgres")
    if not shutil.which("rclone"):
        _hace_falta("rclone")
    url = preparar_base()
    import psycopg2
    admin_url = url.rsplit("/", 1)[0] + "/postgres"

    def sql(base, consulta):
        conexion = psycopg2.connect(url.rsplit("/", 1)[0] + "/" + base)
        conexion.autocommit = True
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta)
                return cursor.fetchall() if cursor.description else None
        finally:
            conexion.close()

    for base in ("bk_origen", "bk_estado_a", "bk_estado_b"):
        sql("postgres", f"DROP DATABASE IF EXISTS {base}")
    sql("postgres", "CREATE DATABASE bk_origen TEMPLATE humo_calculador")
    # Lo que tiene Ganadería: otro esquema y una política con un rol propio.
    # Y lo que tiene todo Supabase: storage y auth, que NO van al dump.
    sql("bk_origen", """
        INSERT INTO clientes (nombre) VALUES ('EJEMPLO Cliente'), ('EJEMPLO Otro');
        CREATE SCHEMA memoria; CREATE TABLE memoria.notas (id serial PRIMARY KEY, texto text);
        INSERT INTO memoria.notas (texto) VALUES ('EJ a'), ('EJ b');
        DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bk_ej_lector')
          THEN CREATE ROLE bk_ej_lector NOLOGIN; END IF; END $$;
        ALTER TABLE memoria.notas ENABLE ROW LEVEL SECURITY;
        CREATE POLICY leer ON memoria.notas FOR SELECT TO bk_ej_lector USING (true);
        CREATE SCHEMA storage; CREATE TABLE storage.buckets (id text PRIMARY KEY);
        CREATE TABLE storage.objects (bucket_id text, name text, created_at timestamptz);
        INSERT INTO storage.objects VALUES ('comandas', 'a,"raro".jpg', '2025-01-02');
        CREATE SCHEMA auth; CREATE TABLE auth.users (id uuid PRIMARY KEY);
    """)
    clave_rol = "EjemploDeClaveDelRol0123456789abcdefXYZ"
    for base in ("bk_estado_a", "bk_estado_b"):
        sql("postgres", f"CREATE DATABASE {base} TEMPLATE humo_calculador")
        sql(base, (RAIZ / "db/backups_1_tabla.sql").read_text(encoding="utf-8"))
        sql(base, (RAIZ / "db/backups_2_rol.sql").read_text(encoding="utf-8")
            .replace("PEGAR_ACA_LA_CLAVE_DEL_ROL", clave_rol))

    destinos = tmp_path / "nubes"
    (destinos / "onedrive").mkdir(parents=True)
    (destinos / "gdrive").mkdir()
    conf = tmp_path / "rclone.conf"
    conf.write_text(f"[onedrive]\ntype = alias\nremote = {destinos / 'onedrive'}\n"
                    f"[gdrive]\ntype = alias\nremote = {destinos / 'gdrive'}\n", encoding="utf-8")
    storage = tmp_path / "storage"
    (storage / "comandas" / "2025-01-02").mkdir(parents=True)
    (storage / "comandas" / "2025-01-02" / "a.jpg").write_bytes(b"foto uno")
    (storage / "remitos").mkdir()
    (storage / "remitos" / "r.jpg").write_bytes(b"foto dos")

    base_url = url.rsplit("/", 1)[0]
    rol_url = f"postgresql://backup_estado:{clave_rol}@" + base_url.split("@", 1)[1]
    entorno = {
        "RCLONE_CONFIG": str(conf), "BACKUP_CLAVE": CLAVE, "BACKUP_PROYECTOS": "frutamax",
        "BACKUP_HOY": HOY.isoformat(), "FRUTAMAX_DB_URL": base_url + "/bk_origen",
        "BACKUP_PRUEBA_URL": admin_url, "FRUTAMAX_FOTOS_ORIGEN": str(storage) + "/",
        "ESTADO_FRUTAMAX_URL": rol_url + "/bk_estado_a", "ESTADO_PALMALA_URL": rol_url + "/bk_estado_b",
    }
    for nombre, valor in entorno.items():
        monkeypatch.setenv(nombre, valor)
    import scripts.backup as bk
    monkeypatch.setattr(bk, "_ENTORNO", None)
    return {"bk": bk, "sql": sql, "nubes": destinos, "storage": storage, "conf": conf, "tmp": tmp_path}


def _descifrar(s, destino, ruta, hacia):
    """Lo que hace RESTAURAR.md: una configuración NUEVA, con solo la clave."""
    conf = s["tmp"] / f"solo_la_clave_{destino}.conf"
    entorno = {**os.environ, "RCLONE_CONFIG": str(conf)}
    subprocess.run(["rclone", "config", "create", "descifrar", "crypt",
                    f"remote={s['nubes'] / destino / 'Backup-Sistema' / 'cifrado'}", f"password={CLAVE}",
                    "--obscure"], check=True, capture_output=True, env=entorno)
    subprocess.run(["rclone", "copy", f"descifrar:{ruta}", str(hacia)], check=True, capture_output=True, env=entorno)


def test_las_BASES_se_suben_CIFRADAS_a_los_dos_y_se_RESTAURAN_iguales(simulacro):
    s = simulacro
    resultado = s["bk"].parte_bases()
    assert resultado == {"onedrive": (True, "1 bases restauradas"), "gdrive": (True, "1 bases restauradas")}
    for destino in ("onedrive", "gdrive"):
        nube = s["nubes"] / destino / "Backup-Sistema" / "cifrado"
        nombres = [p.name for p in nube.rglob("*")]
        assert nombres and not any(n in ("bases", "base.dump", "manifiesto.json") for n in nombres)
    claro = s["tmp"] / "claro"
    _descifrar(s, "gdrive", f"bases/{HOY.isoformat()}/frutamax", claro)
    manifiesto = json.loads((claro / "manifiesto.json").read_text(encoding="utf-8"))
    assert manifiesto["esquemas"] == ["memoria", "public"]
    assert manifiesto["roles"] == ["bk_ej_lector"]
    assert manifiesto["filas"]["public.clientes"] == 2 and manifiesto["filas"]["memoria.notas"] == 2
    assert manifiesto["supabase"]["storage.objects"] == 1 and manifiesto["supabase"]["auth.users"] == 0
    assert not any(t.startswith(("storage.", "auth.")) for t in manifiesto["filas"])


def test_la_restauracion_CREA_el_rol_de_las_politicas_y_ve_una_FILA_que_FALTA(simulacro):
    s = simulacro
    carpeta = s["tmp"] / "dump"
    s["bk"].respaldar_base("frutamax", os.environ["FRUTAMAX_DB_URL"], carpeta)
    # el rol desaparece del servidor: la restauración tiene que crearlo sola
    s["sql"]("postgres", "DROP DATABASE bk_origen")
    s["sql"]("postgres", "DROP ROLE bk_ej_lector")
    assert s["bk"].probar_restauracion(carpeta, os.environ["BACKUP_PRUEBA_URL"], "bk_prueba") == []
    # canario: el manifiesto dice una fila más de las que tiene el dump
    manifiesto = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    manifiesto["filas"]["public.clientes"] += 1
    (carpeta / "manifiesto.json").write_text(json.dumps(manifiesto), encoding="utf-8")
    malas = s["bk"].probar_restauracion(carpeta, os.environ["BACKUP_PRUEBA_URL"], "bk_prueba")
    assert malas == ["public.clientes: 3 filas en el origen y 2 restauradas"]
    assert not s["sql"]("postgres", "SELECT 1 FROM pg_database WHERE datname = 'bk_prueba'")


def test_un_destino_que_FALLA_no_frena_al_otro_y_en_el_que_falla_NO_se_rota(simulacro):
    s = simulacro
    viejo = f"calculador-precios_{HOY - timedelta(days=400)}.bundle"   # más de 12 meses
    s["bk"].rclone("copyto", str(RAIZ / "RESTAURAR.md"), s["bk"].cifrado("onedrive", f"codigo/{viejo}"))
    s["bk"].rclone("copyto", str(RAIZ / "RESTAURAR.md"), s["bk"].cifrado("gdrive", f"codigo/{viejo}"))
    # Google Drive "se cae": su carpeta pasa a ser un archivo
    gdrive = s["nubes"] / "gdrive" / "Backup-Sistema" / "cifrado"
    nombres_antes = sorted(p.name for p in gdrive.rglob("*"))
    s["conf"].write_text(s["conf"].read_text(encoding="utf-8").replace(
        str(s["nubes"] / "gdrive"), str(s["tmp"] / "no-existe-y-es-archivo")), encoding="utf-8")
    (s["tmp"] / "no-existe-y-es-archivo").write_text("x")
    repo = s["tmp"] / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for n in range(3):
        (repo / "a.txt").write_text(str(n))
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=e@e", "-c", "user.name=EJ", "commit", "-qm",
                        f"EJ {n}"], check=True)
    resultado = s["bk"].parte_codigo(repo)
    assert resultado["onedrive"][0] is True and "rotó 1" in resultado["onedrive"][1]
    assert resultado["gdrive"][0] is False
    assert sorted(p.name for p in gdrive.rglob("*")) == nombres_antes   # lo viejo sigue
    # en OneDrive: el bundle de hoy, el viejo rotado, y el LEEME sin cifrar al lado
    claro = s["tmp"] / "claro"
    _descifrar(s, "onedrive", "codigo", claro)
    assert sorted(p.name for p in claro.iterdir()) == [f"calculador-precios_{HOY}.bundle"]
    assert (s["nubes"] / "onedrive" / "Backup-Sistema" / "LEEME-RESTAURAR.md").read_text(encoding="utf-8") \
        == (RAIZ / "RESTAURAR.md").read_text(encoding="utf-8")
    clon = s["tmp"] / "clon"
    subprocess.run(["git", "clone", "-q", str(claro / f"calculador-precios_{HOY}.bundle"), str(clon)], check=True)
    assert (clon / "a.txt").read_text() == "2"


def test_las_FOTOS_suben_solo_lo_NUEVO_y_NUNCA_se_borra_lo_que_el_origen_borro(simulacro):
    s = simulacro
    assert s["bk"].parte_fotos()["onedrive"] == (True, "2 fotos nuevas, 2 en el backup")
    (s["storage"] / "comandas" / "2025-01-02" / "a.jpg").unlink()            # el plazo la borró
    (s["storage"] / "remitos" / "nueva.jpg").write_bytes(b"foto tres")
    assert s["bk"].parte_fotos() == {"onedrive": (True, "1 fotos nuevas, 3 en el backup"),
                                     "gdrive": (True, "1 fotos nuevas, 3 en el backup")}
    claro = s["tmp"] / "claro"
    _descifrar(s, "onedrive", "fotos", claro)
    assert (claro / "frutamax" / "comandas" / "2025-01-02" / "a.jpg").read_bytes() == b"foto uno"


def test_una_foto_CAMBIADA_en_el_backup_se_ve_y_la_parte_FALLA(simulacro):
    s = simulacro
    s["bk"].parte_fotos()
    (s["storage"] / "remitos" / "r.jpg").write_bytes(b"otra cosa, otro largo")
    resultado = s["bk"].parte_fotos()
    assert resultado["onedrive"][0] is False and "remitos" in resultado["onedrive"][1]


def test_el_ESTADO_se_graba_en_LAS_DOS_bases_con_un_rol_que_SOLO_INSERTA(simulacro):
    s = simulacro
    no_grabo = s["bk"].registrar("bases", {"onedrive": (True, "bien"), "gdrive": (False, "sin token")})
    assert no_grabo == []
    for base in ("bk_estado_a", "bk_estado_b"):
        assert s["sql"](base, "SELECT parte, onedrive_ok, gdrive_ok, detalle FROM backups_corridas") == \
            [("bases", True, False, "Google Drive: sin token")]
    import psycopg2
    conexion = psycopg2.connect(os.environ["ESTADO_FRUTAMAX_URL"])
    try:
        for consulta in ("SELECT count(*) FROM backups_corridas", "UPDATE backups_corridas SET detalle = 'x'",
                         "DELETE FROM backups_corridas", "SELECT count(*) FROM proveedores",
                         "INSERT INTO clientes (nombre) VALUES ('EJ')"):
            with conexion.cursor() as cursor, pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cursor.execute(consulta)
            conexion.rollback()
    finally:
        conexion.close()


def test_si_NO_PUEDE_grabar_el_estado_en_una_base_igual_graba_en_la_otra_y_sale_en_ROJO(simulacro, monkeypatch):
    s = simulacro
    monkeypatch.setenv("ESTADO_FRUTAMAX_URL", os.environ["ESTADO_FRUTAMAX_URL"].replace("@", "x@", 1))
    monkeypatch.setattr(s["bk"], "parte_fotos", lambda: {"onedrive": (True, ""), "gdrive": (True, "")})
    assert s["bk"].main(["fotos"]) == 1
    assert s["sql"]("bk_estado_b", "SELECT count(*) FROM backups_corridas") == [(1,)]


def test_la_PANTALLA_y_la_ALERTA_leen_lo_que_grabo_el_workflow(simulacro, monkeypatch):
    s = simulacro
    s["sql"]("bk_estado_a", "INSERT INTO backups_corridas (parte, onedrive_ok, gdrive_ok, terminada_el) VALUES "
             "('codigo', true, true, now() - interval '3 days'), ('bases', true, true, now() - interval '1 hour'),"
             "('bases', false, true, now()), ('fotos', true, true, now())")
    monkeypatch.setenv("DATABASE_URL", os.environ["FRUTAMAX_DB_URL"].rsplit("/", 1)[0] + "/bk_estado_a")
    import app.db as d
    estado = {e["parte"]: e for e in d.estado_de_los_backups()}
    assert estado["codigo"]["vieja"] and not estado["bases"]["vieja"]
    assert estado["bases"]["texto_fallaron"] == ["OneDrive"]
    assert d.contar_backups_viejos()["casos"] == 1
    from fastapi.testclient import TestClient
    import app.main as m
    cliente = TestClient(m.app)
    monkeypatch.setattr(m, "_acceso_gerencia_valido", lambda request: True)
    texto = cliente.get("/gerencia/backups").text.split("</style>")[-1]
    assert texto.count('data-parte="') == 3
    assert "falló en\n      <strong>OneDrive</strong>" in texto
    assert texto.count('class="destino mal"') == 1


def test_la_ALERTA_de_backups_es_SOLO_de_Gerencia_y_va_a_su_pantalla():
    import app.main as m
    alerta = next(a for a in m.ALERTAS if a.codigo == "backups_viejos")
    assert alerta.modulos == ("gerencia",) and alerta.url == "/gerencia/backups"
    assert alerta.texto(1) == "1 parte del backup sin copia buena hace más de 2 días"
