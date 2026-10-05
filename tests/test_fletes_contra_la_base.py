"""Fletes (dueño, 05/10), contra Postgres cargado con db/esquema_completo.sql.

Lo que pide el dueño para el armado: el empate, la flota que no alcanza, una
sola sucursal y los pallets en cero. Y lo que decide la base: las dos partes
suman el precio y un viaje pagado no se toca. Los nombres son de EJEMPLO.

  cliente 1  "Día %"  con VL Vicente López, BZ Burzaco y GR Garín
  cliente 2  EJ Otro  sin sucursales
  fletero 1  EJ Juan  Grande (12 pallets, tiene 1), Mediano (8, tiene 2), Chico (4, tiene 3)
  fletero 2  EJ Rival con su propio Grande: el RIVAL que no tiene que ganar
"""
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
DIA = date(2026, 3, 9)            # lunes, lejos de hoy

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'Día %'), (2, 'EJ Otro');
insert into clientes_sucursales (cliente_id, codigo, nombre) values
  (1, 'VL', 'Vicente López'), (1, 'BZ', 'Burzaco'), (1, 'GR', 'Garín');
insert into fleteros (id, nombre, telefono) overriding system value values (1, 'EJ Juan', '11 5555-0000'),
  (2, 'EJ Rival', null);
insert into fleteros_camiones (id, fletero_id, nombre, pallets, cantidad) overriding system value values
  (11, 1, 'Grande', 12, 1), (12, 1, 'Mediano', 8, 2), (13, 1, 'Chico', 4, 3), (21, 2, 'Grande', 12, 9);
insert into fleteros_camiones_precios (camion_id, precio, vigente_desde) values
  (11, 100000, '2026-01-01'), (12, 70000, '2026-01-01'), (13, 40000, '2026-01-01'),
  (11, 150000, '2026-03-10'),            -- el aumento del día SIGUIENTE no vale para DIA
  (21, 1, '2026-01-01');
select setval(pg_get_serial_sequence(t, 'id'), 100)
  from unnest(array['clientes', 'fleteros', 'fleteros_camiones']) as t;
"""


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: los fletes no se verificaron")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
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


def _propuesta(d, pallets, fletero=1, fecha=DIA, excepto=None):
    """Lo mismo que hace la pantalla: los camiones y su precio de ESE día y
    los ya asignados, de la base; la decisión, de core/fletes."""
    from core.fletes import armar_flete
    camiones = d.camiones_del_fletero(fletero, fecha)
    usados = d.camiones_usados_el_dia(fletero, fecha, excepto)
    return armar_flete([{"codigo": c, "pallets": p} for c, p in pallets if p > 0], camiones, usados)


def _guardar(d, propuesta, pallets_fm_pm, fletero=1, fecha=DIA, cliente=1, flete_id=None, sector="administracion"):
    sucursales = [{"codigo": c, "pallets_frutamax": fm, "pallets_palmala": pm,
                   "camiones": propuesta["asignacion"].get(c, {})} for c, fm, pm in pallets_fm_pm]
    return d.guardar_flete(fecha, cliente, fletero, sucursales, sector, flete_id=flete_id)


# --- el armado, con la flota y el precio de la base --------------------------

def test_dos_sucursales_la_mas_barata_con_el_precio_DE_ESE_DIA(base):
    d, _ = base
    p = _propuesta(d, [("VL", 18), ("BZ", 8)])
    assert p["alcanza"] and p["asignacion"] == {"VL": {11: 1, 12: 1}, "BZ": {12: 1}}
    assert p["costo"] == Decimal("240000")          # 100.000 + 70.000 + 70.000: no el aumento del 10/03


def test_EMPATE_de_precio_gana_el_de_MENOS_camiones(base):
    d, sql = base
    # 8 pallets: 1 Mediano a 70.000 o 2 Chicos a 35.000 cada uno. Empatan.
    sql("insert into fleteros_camiones_precios (camion_id, precio, vigente_desde) values (13, 35000, '2026-03-01')")
    p = _propuesta(d, [("BZ", 8)])
    assert p["asignacion"] == {"BZ": {12: 1}} and p["costo"] == Decimal("70000") and p["camiones"] == 1
    # el rival del empate: un peso menos y ganan los dos chicos
    sql("insert into fleteros_camiones_precios (camion_id, precio, vigente_desde) values (13, 34999, '2026-03-02')")
    assert _propuesta(d, [("BZ", 8)])["asignacion"] == {"BZ": {13: 2}}


def test_UNA_SOLA_sucursal(base):
    d, _ = base
    p = _propuesta(d, [("VL", 0), ("BZ", 0), ("GR", 5)])
    assert p["alcanza"] and p["asignacion"] == {"GR": {12: 1}}     # 5 pallets: Mediano 70.000 < 2 Chicos 80.000
    flete = d.obtener_flete(_guardar(d, p, [("VL", 0, 0), ("BZ", 0, 0), ("GR", 3, 2)]))
    assert [s["codigo"] for s in flete["sucursales"]] == ["GR"]
    assert flete["sucursales"][0]["nombre"] == "Garín"


def test_PALLETS_EN_CERO_la_sucursal_no_lleva_camion_y_todo_en_cero_no_se_confirma(base):
    d, sql = base
    p = _propuesta(d, [("VL", 0), ("BZ", 0)])
    assert p["alcanza"] and p["asignacion"] == {} and p["camiones"] == 0
    with pytest.raises(d.FleteNoSePuede, match="No hay pallets"):
        _guardar(d, p, [("VL", 0, 0), ("BZ", 0, 0)])
    assert sql("select count(*) from fletes") == [(0,)]


def test_FLOTA_INSUFICIENTE_se_dice_propone_sin_tope_y_se_puede_confirmar_a_mano(base):
    d, _ = base
    # toda la flota lleva 12 + 16 + 12 = 40 pallets
    p = _propuesta(d, [("VL", 30), ("BZ", 20)])
    assert p["alcanza"] is False
    usa = {}
    for camiones in p["asignacion"].values():
        for cid, n in camiones.items():
            usa[cid] = usa.get(cid, 0) + n
    assert sum(n * {11: 12, 12: 8, 13: 4}[c] for c, n in usa.items()) >= 50
    # A mano se puede pasar de la flota (es lo que la pantalla deja elegir)
    flete = d.obtener_flete(_guardar(d, p, [("VL", 30, 0), ("BZ", 20, 0)]))
    assert sum(len(s["viajes"]) for s in flete["sucursales"]) == p["camiones"]


def test_cuenta_los_camiones_YA_ASIGNADOS_ese_dia_y_no_los_de_otro_dia_ni_los_del_RIVAL(base):
    d, _ = base
    _guardar(d, _propuesta(d, [("VL", 12)]), [("VL", 12, 0)])
    # el único Grande ya salió hoy: 12 pallets más van en Mediano + Chico (110.000), no en el Grande
    assert d.camiones_usados_el_dia(1, DIA) == {11: 1}
    assert _propuesta(d, [("BZ", 12)])["asignacion"] == {"BZ": {12: 1, 13: 1}}
    # otro día está libre, y el fletero rival no se entera
    assert _propuesta(d, [("BZ", 12)], fecha=date(2026, 3, 8))["asignacion"] == {"BZ": {11: 1}}
    assert d.camiones_usados_el_dia(2, DIA) == {}


def test_un_camion_SIN_PRECIO_ese_dia_no_se_propone_y_no_se_guarda(base):
    d, sql = base
    sql("insert into fleteros_camiones (id, fletero_id, nombre, pallets, cantidad) overriding system value "
        "values (14, 1, 'Nuevo', 30, 5)")
    p = _propuesta(d, [("VL", 30)])
    assert p["sin_precio"] == ["Nuevo"] and 14 not in p["asignacion"]["VL"]
    with pytest.raises(d.FleteNoSePuede, match="no tiene precio"):
        d.guardar_flete(DIA, 1, 1, [{"codigo": "VL", "pallets_frutamax": 30, "pallets_palmala": 0,
                                     "camiones": {14: 1}}], "administracion")


def test_NO_ENTRAN_y_sin_camion_no_se_confirma(base):
    d, sql = base
    with pytest.raises(d.FleteNoSePuede, match="no le entran: son 20 pallets"):
        d.guardar_flete(DIA, 1, 1, [{"codigo": "VL", "pallets_frutamax": 20, "pallets_palmala": 0,
                                     "camiones": {12: 1}}], "administracion")
    with pytest.raises(d.FleteNoSePuede, match="ningún camión"):
        d.guardar_flete(DIA, 1, 1, [{"codigo": "BZ", "pallets_frutamax": 2, "pallets_palmala": 0,
                                     "camiones": {}}], "administracion")
    with pytest.raises(d.FleteNoSePuede, match="no es de ese fletero"):
        d.guardar_flete(DIA, 1, 1, [{"codigo": "BZ", "pallets_frutamax": 2, "pallets_palmala": 0,
                                     "camiones": {21: 1}}], "administracion")
    assert sql("select count(*) from fletes") == [(0,)]


# --- lo que se guarda --------------------------------------------------------

def test_cada_viaje_guarda_el_precio_y_la_parte_de_cada_empresa_POR_PALLETS(base):
    d, sql = base
    p = _propuesta(d, [("VL", 18), ("BZ", 8)])
    flete = d.obtener_flete(_guardar(d, p, [("VL", 10, 8), ("BZ", 8, 0)]))
    vl, bz = flete["sucursales"]
    assert (vl["nombre"], vl["pallets"]) == ("Vicente López", 18)
    assert [(v["camion"], v["precio"], v["parte_frutamax"], v["parte_palmala"]) for v in vl["viajes"]] == [
        ("Grande", Decimal("100000.00"), Decimal("55555.56"), Decimal("44444.44")),
        ("Mediano", Decimal("70000.00"), Decimal("38888.89"), Decimal("31111.11"))]
    assert [(v["parte_frutamax"], v["parte_palmala"]) for v in bz["viajes"]] == [(Decimal("70000.00"), 0)]
    assert flete["costo"] == Decimal("240000") == flete["parte_frutamax"] + flete["parte_palmala"]
    # el aumento del catálogo NO toca lo guardado
    d.cargar_precio_camion(12, 99999, DIA)
    assert d.obtener_flete(flete["id"])["costo"] == Decimal("240000")


def test_LA_BASE_rechaza_partes_que_no_suman_el_precio(base):
    d, sql = base
    import psycopg2
    fid = _guardar(d, _propuesta(d, [("BZ", 8)]), [("BZ", 8, 0)])
    (sid,), = sql("select id from fletes_sucursales where flete_id = %s", (fid,))
    with pytest.raises(psycopg2.errors.CheckViolation, match="fletes_viajes_partes_suman"):
        sql("insert into fletes_viajes (flete_sucursal_id, camion_id, precio, parte_frutamax, parte_palmala) "
            "values (%s, 12, 100, 60, 30)", (sid,))


def test_un_SEGUNDO_flete_del_mismo_fletero_cliente_y_dia_rebota(base):
    d, _ = base
    _guardar(d, _propuesta(d, [("BZ", 8)]), [("BZ", 8, 0)])
    with pytest.raises(d.FleteNoSePuede, match="corregilo"):
        _guardar(d, _propuesta(d, [("GR", 4)]), [("GR", 4, 0)])


# --- corregir ----------------------------------------------------------------

def test_CORREGIR_reemplaza_y_deja_el_HISTORIAL_y_no_cuenta_sus_propios_camiones(base):
    d, sql = base
    fid = _guardar(d, _propuesta(d, [("VL", 12)]), [("VL", 12, 0)])
    # corrigiendo el mismo flete, su Grande no cuenta como "ya asignado"
    p = _propuesta(d, [("VL", 12), ("BZ", 4)], excepto=fid)
    assert p["asignacion"] == {"VL": {11: 1}, "BZ": {13: 1}}
    _guardar(d, p, [("VL", 6, 6), ("BZ", 4, 0)], flete_id=fid, sector="gerencia")
    flete = d.obtener_flete(fid)
    assert [s["codigo"] for s in flete["sucursales"]] == ["VL", "BZ"]
    (correccion,) = flete["correcciones"]
    assert correccion["sector"] == "gerencia"
    assert [s["codigo"] for s in correccion["antes"]["sucursales"]] == ["VL"]
    assert [s["codigo"] for s in correccion["despues"]["sucursales"]] == ["VL", "BZ"]
    assert sql("select count(*) from fletes") == [(1,)]


def test_un_viaje_PAGADO_no_se_corrige_y_no_se_vuelve_a_pagar(base):
    d, sql = base
    fid = _guardar(d, _propuesta(d, [("VL", 18)]), [("VL", 18, 0)])
    filas = d.cuenta_del_fletero(1, DIA, DIA)
    assert d.marcar_viajes_pagados([filas[0]["id"]], date(2026, 3, 20)) == 1
    assert d.marcar_viajes_pagados([f["id"] for f in filas], date(2026, 3, 25)) == 1   # solo el que faltaba
    assert [f["pagado_el"] for f in d.cuenta_del_fletero(1, DIA, DIA)] == [date(2026, 3, 20), date(2026, 3, 25)]
    with pytest.raises(d.FleteNoSePuede, match="ya se pagó"):
        _guardar(d, _propuesta(d, [("VL", 4)], excepto=fid), [("VL", 4, 0)], flete_id=fid)
    assert len(d.obtener_flete(fid)["sucursales"][0]["viajes"]) == 2
    assert sql("select count(*) from fletes_correcciones") == [(0,)]


# --- la cuenta y la Rentabilidad Real ----------------------------------------

def test_la_CUENTA_filtra_por_fletero_y_fechas_con_el_nombre_de_la_sucursal(base):
    d, sql = base
    _guardar(d, _propuesta(d, [("BZ", 8)]), [("BZ", 5, 3)])
    _guardar(d, _propuesta(d, [("GR", 4)], fecha=date(2026, 3, 20)), [("GR", 4, 0)], fecha=date(2026, 3, 20))
    sql("insert into fletes (id, fecha, cliente_id, fletero_id) overriding system value values (90, %s, 1, 2)", (DIA,))
    filas = d.cuenta_del_fletero(1, DIA, DIA)
    assert [(f["fecha"], f["sucursal"], f["camion"]) for f in filas] == [(DIA, "Burzaco", "Mediano")]
    assert len(d.cuenta_del_fletero(None, DIA, date(2026, 3, 31))) == 2
    assert d.cuenta_del_fletero(2, DIA, DIA) == []


def test_la_parte_de_CADA_EMPRESA_por_dia_y_sucursal_para_rentabilidad_real(base):
    d, _ = base
    _guardar(d, _propuesta(d, [("VL", 18), ("BZ", 8)]), [("VL", 10, 8), ("BZ", 8, 0)])
    assert d.flete_por_dia_y_sucursal(1, DIA, DIA, "frutamax") == [
        {"fecha": DIA, "sucursal": "Vicente López", "pesos": Decimal("94444.45")},
        {"fecha": DIA, "sucursal": "Burzaco", "pesos": Decimal("70000.00")}]
    assert [f["pesos"] for f in d.flete_por_dia_y_sucursal(1, DIA, DIA, "palmala")] == [
        Decimal("75555.55"), Decimal("0.00")]
    assert d.flete_por_dia_y_sucursal(2, DIA, DIA, "frutamax") == []
    assert d.flete_por_dia_y_sucursal(1, date(2026, 3, 10), date(2026, 3, 31), "frutamax") == []
