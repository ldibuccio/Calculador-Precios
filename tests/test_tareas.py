"""Tareas (dueño, 02/10), contra Postgres.

Gerencia carga tareas a Compras, Administración o Gerencia; el sector las ve
en un recuadro de su hub y las marca como hechas. Una repetitiva NO SE
ACUMULA: si llega la fecha de la siguiente y la anterior sigue pendiente, la
anterior queda "no hecha" y la nueva sale atrasada. Las ocurrencias se
generan al leer. La base decide (db/tareas_1 a _3), así que esto corre contra
el esquema real. Los nombres son de EJEMPLO.
"""
import os
import re
import sys
from datetime import date, timedelta

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
LUNES = date(2026, 3, 2)    # lejos del reloj real (corolario 95), y es lunes
assert LUNES.weekday() == 0


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: las tareas no se verificaron")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    monkeypatch.setenv("DATABASE_URL", url)
    import app.db as d

    def sql(consulta, parametros=None):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()
    return d, sql


def _semanal(d, sector="compras", desde=LUNES, titulo="EJ Contar cajas"):
    return d.crear_tarea(creada_por="gerencia", sector=sector, titulo=titulo, detalle="EJ en el galpón", tipo="semanal",
                         dia_semana=0, desde=desde, hoy=desde)


def _ocurrencias(sql, tarea_id):
    return sql("SELECT vence_el, estado, atrasada, no_hecha_el FROM tareas_ocurrencias "
               "WHERE tarea_id = %s ORDER BY vence_el", (tarea_id,))


def _cliente(monkeypatch, *sectores):
    from fastapi.testclient import TestClient
    from app.main import PUERTA_ADMINISTRACION, PUERTA_COMPRAS, PUERTA_GERENCIA, app
    cliente = TestClient(app, base_url="https://testserver")
    for puerta in (PUERTA_ADMINISTRACION, PUERTA_COMPRAS, PUERTA_GERENCIA):
        if puerta.sector in sectores:
            monkeypatch.setenv(puerta.env_var, f"clave-{puerta.sector}")
            cliente.cookies.set(puerta.cookie, puerta.firma(f"clave-{puerta.sector}"))
    return cliente


# --- las reglas, en la base ------------------------------------------------------

def test_una_de_UNA_VEZ_sale_al_crearla_y_la_marca_SU_sector_con_nota(base):
    d, sql = base
    d.crear_tarea(creada_por="gerencia", sector="administracion", titulo="EJ Pagar luz", detalle=None, tipo="una_vez",
                  vence_el=LUNES + timedelta(days=3), hoy=LUNES)
    (tarea,) = d.tareas_pendientes_del_sector("administracion", LUNES)
    assert d.tareas_pendientes_del_sector("compras", LUNES) == []
    with pytest.raises(ValueError, match="ya no está pendiente para este sector"):
        d.marcar_tarea_hecha(tarea["id"], sector="compras", nota=None)
    d.marcar_tarea_hecha(tarea["id"], sector="administracion", nota="  EJ pagada en el banco ")
    assert d.tareas_pendientes_del_sector("administracion", LUNES) == []
    (fila,) = sql("SELECT estado, hecha_por, nota, hecha_el IS NOT NULL FROM tareas_ocurrencias")
    assert fila == ("hecha", "administracion", "EJ pagada en el banco", True)
    with pytest.raises(ValueError, match="ya no está pendiente"):
        d.marcar_tarea_hecha(tarea["id"], sector="administracion", nota=None)


def test_la_base_exige_los_campos_de_CADA_tipo(base):
    import psycopg2
    d, sql = base
    with pytest.raises(ValueError, match="Faltan o sobran"):
        d.crear_tarea(creada_por="gerencia", sector="compras", titulo="EJ", detalle=None, tipo="semanal",
                      dia_semana=None, desde=LUNES, hoy=LUNES)
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO tareas (sector, creada_por, titulo, tipo, vence_el, cada_dias) "
            "VALUES ('compras', 'gerencia', 'EJ', 'una_vez', '2026-03-05', 3)")


def test_una_REPETITIVA_sale_el_dia_que_le_toca_y_NO_SE_ACUMULA(base):
    """La vez salteada queda NO HECHA en el registro, con el día en que llegó
    la siguiente, y en el recuadro hay UNA sola, marcada atrasada."""
    d, sql = base
    tarea_id = _semanal(d)
    assert d.tareas_pendientes_del_sector("compras", LUNES - timedelta(days=1)) == []   # todavía no tocaba
    assert len(d.tareas_pendientes_del_sector("compras", LUNES)) == 1
    d.generar_ocurrencias(LUNES)                                                       # idempotente
    assert _ocurrencias(sql, tarea_id) == [(LUNES, "pendiente", False, None)]
    siguiente = LUNES + timedelta(days=7)
    (recuadro,) = d.tareas_pendientes_del_sector("compras", siguiente)
    assert (recuadro["vence_el"], recuadro["atrasada"]) == (siguiente, True)
    assert _ocurrencias(sql, tarea_id) == [
        (LUNES, "no_hecha", False, siguiente),
        (siguiente, "pendiente", True, None)]


def test_tres_semanas_sin_abrir_dejan_DOS_no_hechas_y_UNA_pendiente(base):
    d, sql = base
    tarea_id = _semanal(d)
    d.generar_ocurrencias(LUNES)
    assert len(d.tareas_pendientes_del_sector("compras", LUNES + timedelta(days=22))) == 1
    assert [(f[0], f[1]) for f in _ocurrencias(sql, tarea_id)] == [
        (LUNES, "no_hecha"), (LUNES + timedelta(days=7), "no_hecha"),
        (LUNES + timedelta(days=14), "no_hecha"), (LUNES + timedelta(days=21), "pendiente")]


def test_hecha_a_tiempo_la_siguiente_sale_SIN_atraso(base):
    d, sql = base
    tarea_id = _semanal(d)
    (t,) = d.tareas_pendientes_del_sector("compras", LUNES)
    d.marcar_tarea_hecha(t["id"], sector="compras", nota=None)
    (t2,) = d.tareas_pendientes_del_sector("compras", LUNES + timedelta(days=7))
    assert t2["atrasada"] is False
    assert [f[1] for f in _ocurrencias(sql, tarea_id)] == ["hecha", "pendiente"]


def test_PAUSADA_no_sale_y_al_REANUDAR_sigue_desde_hoy_sin_no_hechas(base):
    d, sql = base
    tarea_id = _semanal(d)
    (t,) = d.tareas_pendientes_del_sector("compras", LUNES)
    d.marcar_tarea_hecha(t["id"], sector="compras", nota=None)
    d.cambiar_estado_de_tarea(tarea_id, "pausada", LUNES + timedelta(days=1), quien="gerencia")
    assert d.tareas_pendientes_del_sector("compras", LUNES + timedelta(days=14)) == []
    d.cambiar_estado_de_tarea(tarea_id, "activa", LUNES + timedelta(days=15), quien="gerencia")
    assert d.tareas_pendientes_del_sector("compras", LUNES + timedelta(days=20)) == []
    assert len(d.tareas_pendientes_del_sector("compras", LUNES + timedelta(days=21))) == 1
    assert [f[1] for f in _ocurrencias(sql, tarea_id)] == ["hecha", "pendiente"]
    d.cambiar_estado_de_tarea(tarea_id, "baja", LUNES + timedelta(days=22), quien="gerencia")
    d.generar_ocurrencias(LUNES + timedelta(days=60))
    assert len(_ocurrencias(sql, tarea_id)) == 2                 # lo que ya salió queda
    with pytest.raises(ValueError):
        d.cambiar_estado_de_tarea(tarea_id, "activa", LUNES + timedelta(days=60), quien="gerencia")


def test_EDITAR_cambia_lo_que_viene_y_NO_lo_que_ya_salio(base):
    d, sql = base
    tarea_id = _semanal(d)
    d.generar_ocurrencias(LUNES)
    d.editar_tarea_repetitiva(tarea_id, quien="gerencia", titulo="EJ Contar pallets", detalle=None, tipo="cada_dias",
                              cada_dias=3, dia_semana=None, dias_mes=None)
    d.generar_ocurrencias(LUNES + timedelta(days=3))
    assert sql("SELECT vence_el, titulo FROM tareas_ocurrencias ORDER BY vence_el") == [
        (LUNES, "EJ Contar cajas"), (LUNES + timedelta(days=3), "EJ Contar pallets")]
    # Y el REGISTRO de Gerencia dice el de cada vez, no el de hoy.
    registro = d.listar_ocurrencias(sector=None, desde=None, hasta=None, estado=None, hoy=LUNES + timedelta(days=3))
    assert sorted((o["vence_el"], o["titulo"]) for o in registro) == [
        (LUNES, "EJ Contar cajas"), (LUNES + timedelta(days=3), "EJ Contar pallets")]


def test_solo_GERENCIA_vuelve_a_pendiente_con_MOTIVO_y_solo_la_ultima(base):
    d, sql = base
    tarea_id = _semanal(d)
    (t,) = d.tareas_pendientes_del_sector("compras", LUNES)
    d.marcar_tarea_hecha(t["id"], sector="compras", nota="EJ listo")
    with pytest.raises(ValueError, match="motivo"):
        d.volver_tarea_a_pendiente(t["id"], " ")
    d.volver_tarea_a_pendiente(t["id"], "EJ faltó contar el fondo")
    assert sql("SELECT estado, nota FROM tareas_ocurrencias WHERE id = %s", (t["id"],)) == [("pendiente", None)]
    (r,) = d.reaperturas_de_tareas([t["id"]])[t["id"]]
    assert (r["motivo"], r["hecha_por_anterior"], r["nota_anterior"]) == ("EJ faltó contar el fondo", "compras",
                                                                         "EJ listo")
    d.marcar_tarea_hecha(t["id"], sector="compras", nota=None)
    d.generar_ocurrencias(LUNES + timedelta(days=7))
    with pytest.raises(ValueError, match="Ya salió la siguiente"):
        d.volver_tarea_a_pendiente(t["id"], "EJ otra vez")
    assert len(_ocurrencias(sql, tarea_id)) == 2


def test_el_REGISTRO_filtra_por_estado_visible_y_la_ALERTA_cuenta_las_vencidas(base):
    from core.tareas import dias_de_atraso
    d, _ = base
    d.crear_tarea(creada_por="gerencia", sector="gerencia", titulo="EJ Vence hoy", detalle=None, tipo="una_vez", vence_el=LUNES, hoy=LUNES)
    _semanal(d, sector="administracion")
    hoy = LUNES + timedelta(days=9)
    estados = {e: [o["titulo"] for o in d.listar_ocurrencias(sector=None, desde=None, hasta=None, estado=e, hoy=hoy)]
               for e in ("pendiente", "vencida", "hecha", "no_hecha")}
    assert estados == {"pendiente": [], "vencida": ["EJ Contar cajas", "EJ Vence hoy"],
                       "hecha": [], "no_hecha": ["EJ Contar cajas"]}
    assert d.contar_tareas_vencidas(hoy) == {"casos": 2, "mas_viejo": LUNES}
    assert d.contar_tareas_vencidas(LUNES)["casos"] == 0               # el día que vence todavía no
    (vence_hoy,) = d.listar_ocurrencias(sector="gerencia", desde=None, hasta=None, estado=None, hoy=hoy)
    assert dias_de_atraso(vence_hoy, hoy) == 9


# --- las pantallas -------------------------------------------------------------------

def _boton_de_tareas(marcado):
    """El <button> de Tareas de la franja, entero: clase y texto."""
    (boton,) = re.findall(r'<button type="button" class="([^"]*)"[^>]*data-franja-boton="tareas">([^<]*)</button>',
                          " ".join(marcado.split()))
    return boton


def test_la_FRANJA_dice_las_tareas_en_gris_destacado_o_ROJO_y_arranca_plegada(base, monkeypatch):
    """Dueño, 04/10: "Sin tareas pendientes" en gris; "Tareas pendientes (N)"
    destacado; en rojo si alguna está vencida. "Nueva tarea" se despliega
    SIEMPRE, también sin pendientes."""
    from unittest.mock import patch
    d, _ = base
    cliente = _cliente(monkeypatch, "compras")
    with patch("app.main._hoy_argentina", return_value=LUNES + timedelta(days=2)):
        sin = cliente.get("/compras").text.split("</style>")[-1]
        d.crear_tarea(creada_por="gerencia", sector="compras", titulo="EJ Llamar al puesto", detalle=None,
                      tipo="una_vez", vence_el=LUNES + timedelta(days=5), hoy=LUNES)
        al_dia = cliente.get("/compras").text.split("</style>")[-1]
        _semanal(d)                                             # la semanal del LUNES ya pasó: vencida
        con_vencida = cliente.get("/compras").text.split("</style>")[-1]
    assert _boton_de_tareas(sin) == ("franja-boton", "Sin tareas pendientes")
    assert _boton_de_tareas(al_dia) == ("franja-boton destacada", "Tareas pendientes (1)")
    assert _boton_de_tareas(con_vencida) == ("franja-boton roja", "Tareas pendientes (2)")
    for marcado in (sin, al_dia, con_vencida):
        panel = marcado.split('id="franja-tareas"')[1].split('id="franja-alertas"')[0]
        assert panel.startswith(' data-franja-panel="tareas" hidden>')         # plegado al llegar
        assert panel.count('<a class="tareas-nueva" href="/compras/tareas">Nueva tarea</a>') == 1
        assert marcado.index("data-franja") < marcado.index('<div class="tarjeta">')   # arriba de los botones
    assert con_vencida.count('action="/compras/tareas/') == 2


def test_el_SECTOR_marca_desde_su_hub_y_NO_puede_desmarcar(base, monkeypatch):
    from unittest.mock import patch
    d, sql = base
    d.crear_tarea(creada_por="gerencia", sector="administracion", titulo="EJ", detalle=None, tipo="una_vez", vence_el=LUNES, hoy=LUNES)
    (t,) = d.tareas_pendientes_del_sector("administracion", LUNES)
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main._hoy_argentina", return_value=LUNES):
        respuesta = cliente.post(f"/administracion/tareas/{t['id']}/hecha", data={"nota": "EJ ok"},
                                 follow_redirects=False)
        assert respuesta.status_code == 303 and respuesta.headers["location"] == "/administracion"
        assert cliente.post(f"/administracion/tareas/{t['id']}/hecha", data={}).status_code == 409
        assert cliente.post(f"/administracion/tareas/ocurrencias/{t['id']}/pendiente",
                            data={"motivo": "x"}).status_code in (404, 405)
    assert sql("SELECT estado, hecha_por FROM tareas_ocurrencias") == [("hecha", "administracion")]


def test_GERENCIA_crea_desde_su_pantalla_y_EXPORTA_con_los_filtros(base, monkeypatch):
    import html
    from unittest.mock import patch
    from tests.test_exportaciones_filtradas import _texto_del_archivo
    d, sql = base
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=LUNES):
        assert cliente.post("/gerencia/tareas", data={
            "sector": "compras", "titulo": "EJ Revisar balanza", "detalle": "", "tipo": "mensual",
            "desde": LUNES.isoformat(), "dias_mes": "2", "cada_dias": "4", "dia_semana": "3"},
            follow_redirects=False).status_code == 303
        assert cliente.post("/gerencia/tareas", data={
            "sector": "administracion", "titulo": "EJ Otra", "tipo": "una_vez",
            "vence_el": LUNES.isoformat()}, follow_redirects=False).status_code == 303
        marcado = cliente.get("/gerencia/tareas?sector=compras&estado=pendiente").text.split("</style>")[-1]
        links = [html.unescape(l) for l in re.findall(r'href="(/gerencia/tareas/exportar-[a-z]+\?[^"]*)"', marcado)]
        archivos = [_texto_del_archivo(cliente.get(l)) for l in links]
    assert sql("SELECT tipo, dias_mes, cada_dias, dia_semana, creada_por FROM tareas WHERE sector = 'compras'") == [
        ("mensual", [2], None, None, "gerencia")]
    assert "EJ Revisar balanza" in marcado and "EJ Otra" not in marcado
    assert len(archivos) == 2
    for texto in archivos:
        assert "EJ Revisar balanza" in texto and "EJ Otra" not in texto
        assert "sector Compras" in texto and "estado pendiente" in texto


def test_la_ALERTA_de_tareas_es_SOLO_de_Gerencia():
    from app.main import ALERTAS
    (alerta,) = [a for a in ALERTAS if a.codigo == "tareas_vencidas"]
    assert alerta.modulos == ("gerencia",)


def test_el_RECUADRO_abierto_se_ve_bien_a_313px(base, monkeypatch):
    """Desplegado, con un título y un detalle largos: nada se sale de la página
    y nada se pisa."""
    pytest.importorskip("playwright")
    from unittest.mock import patch
    from scripts.medir_layout import medir_sync
    d, _ = base
    d.crear_tarea(creada_por="gerencia", sector="gerencia", titulo="EJEMPLO tarea con un título bastante largo para un celular",
                  detalle="EJEMPLOSINESPACIOSQUENOSEPUEDEPARTIRPORNINGUNLADO y algo más",
                  tipo="una_vez", vence_el=LUNES, hoy=LUNES)
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=LUNES + timedelta(days=1)):
        pagina = cliente.get("/gerencia").text
    pagina = pagina.replace('<details class="tareas-plegable">', '<details class="tareas-plegable" open>')
    pagina = pagina.replace('<details class="tarea-hecha">', '<details class="tarea-hecha" open>')
    medicion = medir_sync(pagina, ancho=313)
    assert medicion["pares"] > 0
    assert medicion["desborde_pagina"] == 0, medicion["desborde_pagina"]
    assert medicion["solapes"] == [], medicion["solapes"]


def test_las_FECHAS_de_cada_regla_mensual_31_cae_al_ultimo_dia():
    from core.tareas import fechas_que_tocan
    mensual = {"tipo": "mensual", "dias_mes": [31], "desde": date(2026, 1, 15)}
    assert fechas_que_tocan(mensual, date(2026, 1, 14), date(2026, 4, 30)) == [
        date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
    cada = {"tipo": "cada_dias", "cada_dias": 3, "desde": date(2026, 3, 2)}
    assert fechas_que_tocan(cada, date(2026, 3, 3), date(2026, 3, 12)) == [
        date(2026, 3, 5), date(2026, 3, 8), date(2026, 3, 11)]
    semanal = {"tipo": "semanal", "dia_semana": 4, "desde": date(2026, 3, 2)}
    assert fechas_que_tocan(semanal, date(2026, 3, 1), date(2026, 3, 13)) == [date(2026, 3, 6), date(2026, 3, 13)]
