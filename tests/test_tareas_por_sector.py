"""Tareas: cada sector carga las suyas, y la mensual en varios días (dueño, 02/10), contra Postgres.

- Compras, Administración y Gerencia crean tareas para su propio sector;
  Gerencia, para cualquiera. Cada tarea dice quién la CREÓ (`creada_por`).
- Un sector edita, pausa y da de baja SOLO las que creó él. Gerencia todas.
- El registro de Gerencia filtra por "creada por" y la exportación lo lleva.
- La alerta de vencidas de Gerencia sigue cubriendo todas.
- La mensual sale en varios días (1 y 15): cada fecha es una ocurrencia y no
  se acumula.
- La migración (db/tareas_5 antes del deploy, _6 después) no cambia la regla
  de ninguna tarea.

Los nombres son de EJEMPLO.
"""
import io
import os
import re
import sys
from datetime import date, timedelta

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_tareas import LUNES, _cliente, _ocurrencias, base  # noqa: E402,F401  (fixture)


def _mensual(d, dias, *, sector="compras", creada_por="compras", desde=LUNES, titulo="EJ Pagar luz"):
    return d.crear_tarea(sector=sector, creada_por=creada_por, titulo=titulo, detalle=None, tipo="mensual",
                         dias_mes=dias, desde=desde, hoy=desde)


# --- la mensual en varios días ---------------------------------------------------

def test_la_MENSUAL_sale_el_1_y_el_15_y_NO_SE_ACUMULA(base):
    """El 01/04 no se hace: el 15/04 queda NO HECHA y la del 15 sale atrasada.
    El RIVAL es la regla de un solo día: con ésa el 15 no salía nunca."""
    d, sql = base
    tarea = _mensual(d, [1, 15])
    d.generar_ocurrencias(date(2026, 3, 31))
    assert [(f[0], f[1]) for f in _ocurrencias(sql, tarea)] == [(date(2026, 3, 15), "pendiente")]
    d.generar_ocurrencias(date(2026, 4, 16))
    filas = _ocurrencias(sql, tarea)
    assert [f[0] for f in filas] == [date(2026, 3, 15), date(2026, 4, 1), date(2026, 4, 15)]
    assert [f[1] for f in filas] == ["no_hecha", "no_hecha", "pendiente"]
    assert filas[2][2] is True                                                      # atrasada
    assert sum(1 for f in filas if f[1] == "pendiente") == 1                        # una sola


def test_las_FECHAS_mensuales_con_varios_dias_y_el_31_y_el_30_en_febrero():
    from core.tareas import dias_del_mes, fechas_que_tocan, texto_de_la_regla
    tarea = {"tipo": "mensual", "dias_mes": [15, 1], "desde": date(2026, 1, 10)}
    assert fechas_que_tocan(tarea, date(2026, 1, 9), date(2026, 2, 28)) == [
        date(2026, 1, 15), date(2026, 2, 1), date(2026, 2, 15)]
    febrero = {"tipo": "mensual", "dias_mes": [30, 31], "desde": date(2026, 2, 1)}
    assert fechas_que_tocan(febrero, date(2026, 1, 31), date(2026, 3, 31)) == [
        date(2026, 2, 28), date(2026, 3, 30), date(2026, 3, 31)]                   # una sola en febrero
    assert texto_de_la_regla(tarea) == "los días 1 y 15 de cada mes"
    assert texto_de_la_regla({"tipo": "mensual", "dias_mes": [5]}) == "el día 5 de cada mes"
    assert dias_del_mes(" 15, 1 ,1") == [1, 15]
    assert dias_del_mes("1 15") == [1, 15]
    for malo in ("", "0", "32", "1, x", "-3"):
        assert dias_del_mes(malo) is None, malo


def test_la_BASE_no_deja_una_mensual_sin_dias_ni_con_un_dia_fuera_del_mes(base):
    import psycopg2
    d, sql = base
    for dias in ("{}", "{0}", "{32}"):
        with pytest.raises(psycopg2.errors.CheckViolation):
            sql("INSERT INTO tareas (sector, creada_por, titulo, tipo, desde, dias_mes) "
                "VALUES ('compras', 'gerencia', 'EJ', 'mensual', '2026-03-02', %s)", (dias,))
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO tareas (sector, creada_por, titulo, tipo, desde, cada_dias, dias_mes) "
            "VALUES ('compras', 'gerencia', 'EJ', 'cada_dias', '2026-03-02', 2, '{1}')")


# --- quién la creó y quién la maneja ---------------------------------------------

def test_un_SECTOR_crea_solo_para_si_mismo_y_lo_decide_la_BASE(base):
    import psycopg2
    d, sql = base
    with pytest.raises(ValueError, match="solo carga tareas para sí mismo"):
        d.crear_tarea(sector="administracion", creada_por="compras", titulo="EJ", detalle=None,
                      tipo="una_vez", vence_el=LUNES, hoy=LUNES)
    with pytest.raises(psycopg2.errors.NotNullViolation):
        sql("INSERT INTO tareas (sector, titulo, tipo, vence_el) VALUES ('compras', 'EJ', 'una_vez', '2026-03-02')")
    gerencia = d.crear_tarea(sector="compras", creada_por="gerencia", titulo="EJ", detalle=None,
                             tipo="una_vez", vence_el=LUNES, hoy=LUNES)
    assert sql("SELECT sector, creada_por FROM tareas WHERE id = %s", (gerencia,)) == [("compras", "gerencia")]


def test_un_SECTOR_maneja_SOLO_las_que_creo_y_Gerencia_todas(base):
    d, sql = base
    propia = _mensual(d, [1], titulo="EJ propia")
    de_gerencia = _mensual(d, [2], creada_por="gerencia", titulo="EJ de Gerencia")
    hoy = LUNES + timedelta(days=1)
    with pytest.raises(ValueError, match="este sector"):
        d.editar_tarea_repetitiva(de_gerencia, quien="compras", titulo="EJ tocada", detalle=None, tipo="mensual",
                                  cada_dias=None, dia_semana=None, dias_mes=[3])
    for estado in ("pausada", "baja"):
        with pytest.raises(ValueError, match="este sector"):
            d.cambiar_estado_de_tarea(de_gerencia, estado, hoy, quien="compras")
    with pytest.raises(ValueError, match="este sector"):
        d.cambiar_estado_de_tarea(propia, "pausada", hoy, quien="administracion")
    assert sql("SELECT titulo, estado, dias_mes FROM tareas WHERE id = %s", (de_gerencia,)) == [
        ("EJ de Gerencia", "activa", [2])]
    d.editar_tarea_repetitiva(propia, quien="compras", titulo="EJ propia 2", detalle=None, tipo="mensual",
                              cada_dias=None, dia_semana=None, dias_mes=[1, 15])
    d.cambiar_estado_de_tarea(propia, "pausada", hoy, quien="compras")
    d.cambiar_estado_de_tarea(de_gerencia, "baja", hoy, quien="gerencia")
    d.cambiar_estado_de_tarea(propia, "activa", hoy, quien="gerencia")              # Gerencia toca la del sector
    assert sql("SELECT id, titulo, estado, dias_mes FROM tareas ORDER BY id") == [
        (propia, "EJ propia 2", "activa", [1, 15]), (de_gerencia, "EJ de Gerencia", "baja", [2])]


def test_la_PANTALLA_de_un_sector_carga_para_si_y_no_ofrece_tocar_las_de_Gerencia(base, monkeypatch):
    from unittest.mock import patch
    d, sql = base
    de_gerencia = _mensual(d, [2], creada_por="gerencia", titulo="EJ de Gerencia")
    cliente = _cliente(monkeypatch, "compras")
    with patch("app.main._hoy_argentina", return_value=LUNES):
        # El formulario de un sector no pregunta el sector, y uno armado a
        # mano con otro igual queda para ESE sector.
        respuesta = cliente.post("/compras/tareas", follow_redirects=False, data={
            "sector": "administracion", "titulo": "EJ Llamar al puesto", "tipo": "mensual",
            "desde": LUNES.isoformat(), "dias_mes": "1, 15"})
        assert respuesta.status_code == 303 and respuesta.headers["location"].startswith("/compras/tareas?")
        marcado = cliente.get("/compras/tareas").text.split("</style>")[-1]
        tocar = cliente.post(f"/compras/tareas/{de_gerencia}/estado", data={"estado": "baja"})
    assert sql("SELECT sector, creada_por, dias_mes FROM tareas WHERE titulo = 'EJ Llamar al puesto'") == [
        ("compras", "compras", [1, 15])]
    assert 'name="sector"' not in marcado                                           # no pregunta el sector
    assert "Registro" not in marcado                                                # el registro es de Gerencia
    (propia,) = sql("SELECT id FROM tareas WHERE creada_por = 'compras'")[0]
    assert marcado.count('action="/compras/tareas/%d/estado?volver=' % propia) == 1
    assert 'action="/compras/tareas/%d/estado"' % de_gerencia not in marcado
    assert "La cargó Gerencia: solo Gerencia la cambia." in marcado
    assert tocar.status_code == 400
    assert sql("SELECT estado FROM tareas WHERE id = %s", (de_gerencia,)) == [("activa",)]


def test_ADMINISTRACION_tambien_carga_y_el_RECUADRO_tiene_Nueva_tarea_y_dice_quien(base, monkeypatch):
    from unittest.mock import patch
    d, sql = base
    cliente = _cliente(monkeypatch, "administracion", "compras", "gerencia")
    with patch("app.main._hoy_argentina", return_value=LUNES):
        assert cliente.post("/administracion/tareas", follow_redirects=False, data={
            "titulo": "EJ Cobrar vale", "tipo": "una_vez", "vence_el": LUNES.isoformat()}).status_code == 303
        hubs = {s: cliente.get(f"/{s}").text.split("</style>")[-1] for s in ("compras", "administracion", "gerencia")}
    for sector, marcado in hubs.items():
        assert marcado.count(f'<a class="tareas-nueva" href="/{sector}/tareas#nueva">Nueva tarea</a>') == 1, sector
    assert "la cargó Administración" in hubs["administracion"]
    assert sql("SELECT sector, creada_por FROM tareas") == [("administracion", "administracion")]


def test_el_REGISTRO_de_Gerencia_filtra_por_CREADA_POR_y_la_exportacion_lo_dice(base, monkeypatch):
    import html
    from unittest.mock import patch
    from tests.test_exportaciones_filtradas import _texto_del_archivo
    d, sql = base
    d.crear_tarea(sector="compras", creada_por="compras", titulo="EJ de Compras", detalle=None, tipo="una_vez",
                  vence_el=LUNES, hoy=LUNES)
    d.crear_tarea(sector="compras", creada_por="gerencia", titulo="EJ de Gerencia", detalle=None, tipo="una_vez",
                  vence_el=LUNES, hoy=LUNES)
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=LUNES):
        marcado = cliente.get("/gerencia/tareas?creada_por=compras").text.split("</style>")[-1]
        links = [html.unescape(l) for l in re.findall(r'href="(/gerencia/tareas/exportar-[a-z]+\?[^"]*)"', marcado)]
        archivos = [_texto_del_archivo(cliente.get(l)) for l in links]
    assert "EJ de Compras" in marcado and "EJ de Gerencia" not in marcado
    assert "la cargó Compras" in marcado
    assert len(archivos) == 2
    for texto in archivos:
        texto = " ".join(texto.split())             # el PDF parte los rótulos en dos renglones
        assert "EJ de Compras" in texto and "EJ de Gerencia" not in texto
        assert "creadas por Compras" in texto and "Creada por" in texto
        assert "02/03/2026" in texto                # la fecha entera, sin partir


def test_la_ALERTA_de_Gerencia_cuenta_tambien_las_que_cargo_un_sector(base):
    d, _ = base
    d.crear_tarea(sector="compras", creada_por="compras", titulo="EJ", detalle=None, tipo="una_vez",
                  vence_el=LUNES, hoy=LUNES)
    d.crear_tarea(sector="administracion", creada_por="gerencia", titulo="EJ", detalle=None, tipo="una_vez",
                  vence_el=LUNES, hoy=LUNES)
    assert d.contar_tareas_vencidas(LUNES + timedelta(days=1))["casos"] == 2


# --- la migración ---------------------------------------------------------------

VIEJO = """
  alter table tareas drop constraint tareas_campos_de_su_tipo;
  alter table tareas drop constraint tareas_creada_por;
  alter table tareas drop column creada_por;
  alter table tareas drop column dias_mes;
  alter table tareas add column dia_mes integer;
  alter table tareas add constraint tareas_campos_de_su_tipo check (
    (tipo = 'una_vez' and vence_el is not null and cada_dias is null
      and dia_semana is null and dia_mes is null and desde is null)
    or (tipo <> 'una_vez' and vence_el is null and desde is not null
      and (tipo = 'cada_dias') = coalesce(cada_dias >= 1, false)
      and (tipo = 'semanal') = coalesce(dia_semana between 0 and 6, false)
      and (tipo = 'mensual') = coalesce(dia_mes between 1 and 31, false)));
  insert into tareas (sector, titulo, tipo, vence_el) values ('compras', 'EJ una', 'una_vez', '2026-03-02');
  insert into tareas (sector, titulo, tipo, desde, dia_mes) values ('gerencia', 'EJ mes', 'mensual', '2026-03-02', 31);
  insert into tareas (sector, titulo, tipo, desde, dia_semana) values ('compras', 'EJ sem', 'semanal', '2026-03-02', 3);
"""


def _bloque(archivo):
    texto = io.open(os.path.join(RAIZ, "db", archivo), encoding="utf-8").read()
    return texto[: texto.index("end $$;") + len("end $$;")]


def _verificacion(sql):
    texto = io.open(os.path.join(RAIZ, "db", "tareas_7_verificacion.sql"), encoding="utf-8").read()
    (fila,) = sql(texto[: texto.index(";") + 1])
    return fila[1:9]


def test_la_MIGRACION_en_dos_bloques_no_cambia_la_regla_de_ninguna_tarea(base):
    from core.tareas import fechas_que_tocan
    d, sql = base
    sql(VIEJO)
    sql(_bloque("tareas_5_creada_por_y_dias.sql"))
    assert _verificacion(sql) == (2, 1, 1, 1, 1, 0, 0, 3)
    # En la ventana el código viejo inserta sin creada_por y con dia_mes.
    sql("insert into tareas (sector, titulo, tipo, desde, dia_mes) values ('compras', 'EJ ventana', 'mensual', "
        "'2026-03-02', 15)")
    sql(_bloque("tareas_6_sin_dia_mes.sql"))
    assert _verificacion(sql) == (2, 0, 0, 1, 1, 0, 0, 4)
    filas = sql("SELECT titulo, tipo, dias_mes, dia_semana, creada_por FROM tareas ORDER BY id")
    assert filas == [("EJ una", "una_vez", None, None, "gerencia"), ("EJ mes", "mensual", [31], None, "gerencia"),
                     ("EJ sem", "semanal", None, 3, "gerencia"), ("EJ ventana", "mensual", [15], None, "gerencia")]
    # La regla del 31 sigue siendo la misma: cae al último día del mes.
    assert fechas_que_tocan({"tipo": "mensual", "dias_mes": [31], "desde": date(2026, 3, 2)},
                            date(2026, 3, 1), date(2026, 4, 30)) == [date(2026, 3, 31), date(2026, 4, 30)]


def test_los_bloques_entran_en_el_EDITOR_y_tienen_el_CODIGO_ARRIBA():
    for archivo in ("tareas_5_creada_por_y_dias.sql", "tareas_6_sin_dia_mes.sql", "tareas_7_verificacion.sql"):
        texto = io.open(os.path.join(RAIZ, "db", archivo), encoding="utf-8").read()
        assert len(texto) <= 2500, archivo
        assert not texto.lstrip().startswith("--"), archivo


def test_la_PANTALLA_de_un_sector_se_ve_bien_a_313px(base, monkeypatch):
    """Con el formulario y una repetitiva abiertos: nada se sale ni se pisa."""
    pytest.importorskip("playwright")
    from unittest.mock import patch
    from scripts.medir_layout import medir_sync
    d, _ = base
    _mensual(d, [1, 15], titulo="EJEMPLO tarea con un título bastante largo para un celular")
    _mensual(d, [2], creada_por="gerencia", titulo="EJEMPLOSINESPACIOSQUENOSEPUEDEPARTIRPORNINGUNLADO")
    with patch("app.main._hoy_argentina", return_value=LUNES):
        pagina = _cliente(monkeypatch, "compras").get("/compras/tareas").text
    assert pagina.count("<details") >= 2
    pagina = re.sub(r"<details(?=[ >])", "<details open", pagina)
    medicion = medir_sync(pagina, ancho=313)
    assert medicion["pares"] > 0
    assert medicion["desborde_pagina"] == 0, medicion["desborde_pagina"]
    assert medicion["solapes"] == [], medicion["solapes"]
