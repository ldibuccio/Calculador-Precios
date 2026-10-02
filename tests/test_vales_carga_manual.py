"""Vales: alta manual, sin movimiento de cajones (dueño, 02/10), contra Postgres.

Un vale en papel se da de alta desde la pantalla con origen 'carga_manual':
entra en cartera con quién y cuándo, y NO toca stock, cajones ni Vacíos. Si
ya hay uno parecido, se avisa y se pide confirmación. Un vale no se anula:
Gerencia lo corrige, con historial, mientras esté en cartera. La base decide
(db/vales_manual_1 a _3), así que esto corre contra el esquema real. Los
nombres son de EJEMPLO.
"""
import io
import os
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402
from tests.test_vales_a_cobrar import SIEMBRA, _cliente, _devolucion, _marcado  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 12, 1)

# Lo que una carga de vale NO puede mover: todas las tablas de stock, cajas y
# Vacíos que una devolución o un movimiento escribirían.
TABLAS_QUE_NO_SE_TOCAN = (
    "movimientos_stock", "remitos_segunda", "movimientos_envase", "vacios_deposito_devoluciones",
    "vacios_deposito_ajustes", "vacios_deposito_asignaciones", "conteos_vacios_deposito",
    "vacios_recibidos", "vacios_devueltos", "ajustes_vacios",
)


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: la carga de vales no se verificó")
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


def _cargar(d, proveedor=1, fecha=date(2026, 9, 1), importe=5000.0, numero=None, sector="administracion"):
    return d.cargar_vale_manual(proveedor, fecha, importe, numero=numero, foto_ruta=None,
                                nota="EJ nota", sector=sector, hoy=HOY)


def _conteos(sql):
    return {t: sql(f"SELECT count(*) FROM {t}")[0][0] for t in TABLAS_QUE_NO_SE_TOCAN}


def test_una_carga_manual_entra_en_CARTERA_con_quien_y_NO_mueve_NADA(base):
    d, sql = base
    antes, pilas_antes = _conteos(sql), d.stock_de_vacios_deposito()
    vale_id = _cargar(d, numero=" V-10 ")
    vale = d.vale_a_cobrar(vale_id, HOY)
    assert (vale["origen"], vale["estado"], vale["importe"], vale["numero"], vale["cargada_desde"],
            vale["nota"], vale["proveedor"]) == (
        "carga_manual", "en_cartera", 5000.0, "V-10", "administracion", "EJ nota", "EJ Uno")
    assert _conteos(sql) == antes
    assert d.stock_de_vacios_deposito() == pilas_antes
    assert d.resumen_de_la_cartera(HOY)["total"] == 5000.0


def test_la_BASE_exige_el_sector_en_la_carga_manual_y_solo_en_ella(base):
    import psycopg2
    d, sql = base
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO vales_a_cobrar (origen, proveedor_id, fecha, importe) "
            "VALUES ('carga_manual', 1, '2026-09-01', 10)")
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO vales_a_cobrar (origen, proveedor_id, fecha, importe, cargado_desde) "
            "VALUES ('anterior_al_sistema', 1, '2026-09-01', 10, 'gerencia')")
    with pytest.raises(ValueError, match="mayor que cero"):
        _cargar(d, importe=0)
    with pytest.raises(ValueError, match="posterior a hoy"):
        _cargar(d, fecha=date(2026, 12, 2))


def test_los_PARECIDOS_por_numero_o_por_fecha_e_importe(base):
    d, sql = base
    _cargar(d, numero="V-10")
    _cargar(d, fecha=date(2026, 9, 3), importe=700.0)
    assert [v["numero"] for v in d.vales_parecidos(1, " v-10", date(2026, 1, 1), 1.0)] == ["V-10"]
    assert d.vales_parecidos(2, "V-10", date(2026, 1, 1), 1.0) == []           # otro puesto
    assert len(d.vales_parecidos(1, None, date(2026, 9, 3), 700.0)) == 1        # sin número
    assert d.vales_parecidos(1, None, date(2026, 9, 3), 701.0) == []
    assert d.vales_parecidos(1, "V-99", date(2026, 9, 3), 700.0) == []          # con número manda el número


def test_la_PANTALLA_carga_por_codigo_de_puesto_y_pide_CONFIRMAR_si_hay_parecido(base, monkeypatch):
    from unittest.mock import patch
    d, sql = base
    for sector in ("administracion", "gerencia"):
        assert _cliente(monkeypatch, sector).get(f"/{sector}/vales/cargar").status_code == 200
    cliente = _cliente(monkeypatch, "administracion")
    datos = {"codigo_puesto": "N92P02", "fecha": "2026-09-01", "importe": "1.500", "numero": "P-7", "nota": ""}
    with patch("app.main._hoy_argentina", return_value=HOY):
        respuesta = cliente.post("/administracion/vales/cargar", data=datos, follow_redirects=False)
        assert respuesta.status_code == 303
        assert sql("SELECT proveedor_id, importe, numero, cargado_desde FROM vales_a_cobrar") == [
            (2, 1500, "P-7", "administracion")]
        # El mismo número otra vez: avisa y NO graba.
        assert cliente.get("/administracion/vales/cargar/parecidos", params=datos).json()["parecidos"]
        repetido = cliente.post("/administracion/vales/cargar", data=datos, follow_redirects=False)
        assert repetido.status_code == 409 and "puede ser el mismo" in _marcado(repetido)
        assert sql("SELECT count(*) FROM vales_a_cobrar") == [(1,)]
        # Confirmado: entra.
        confirmado = cliente.post("/administracion/vales/cargar", data=dict(datos, confirmar_parecido="si"),
                                  follow_redirects=False)
        assert confirmado.status_code == 303
        assert sql("SELECT count(*) FROM vales_a_cobrar") == [(2,)]
        malo = cliente.post("/administracion/vales/cargar", data=dict(datos, codigo_puesto="X00"))
        assert malo.status_code == 400 and "ningún proveedor con el código" in malo.text


def test_GERENCIA_corrige_con_HISTORIAL_y_un_vale_que_SALIO_no_se_corrige(base):
    import psycopg2
    d, sql = base
    vale_id = _cargar(d, numero="V-1")
    assert d.corregir_vale(vale_id, importe=5500.0, numero=None, fecha=date(2026, 9, 2), proveedor_id=2,
                           hoy=HOY) == 4
    vale = d.vale_a_cobrar(vale_id, HOY)
    assert (vale["importe"], vale["numero"], vale["fecha"], vale["proveedor"]) == (
        5500.0, None, date(2026, 9, 2), "EJ Dos")
    assert [(c["campo"], c["valor_anterior"], c["valor_nuevo"], c["sector"])
            for c in d.correcciones_del_vale(vale_id)] == [
        ("importe", "5000.00", "5500.00", "gerencia"), ("numero", "V-1", None, "gerencia"),
        ("fecha", "2026-09-01", "2026-09-02", "gerencia"),
        ("proveedor", "N92P01 · EJ Uno", "N92P02 · EJ Dos", "gerencia")]
    with pytest.raises(ValueError, match="No cambió nada"):
        d.corregir_vale(vale_id, importe=5500.0, numero=None, fecha=date(2026, 9, 2), proveedor_id=2, hoy=HOY)
    # Cobrado: ni por la función ni por un UPDATE a mano.
    d.registrar_salida_de_vale(vale_id, "cobrado", date(2026, 9, 10), sector="administracion", hoy=HOY,
                               importe_cobrado=5500.0, ingreso_a_caja=None)
    with pytest.raises(d.ValeNoSeCorrige, match="ya salió"):
        d.corregir_vale(vale_id, importe=1.0, numero=None, fecha=date(2026, 9, 2), proveedor_id=2, hoy=HOY)
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("UPDATE vales_a_cobrar SET importe = 1 WHERE id = %s", (vale_id,))


def test_un_vale_de_DEVOLUCION_no_se_corrige_aca(base):
    """Lee proveedor, fecha e importe de la devolución: se corrige allá."""
    d, _ = base
    dev = _devolucion(d, cajones=4, importe=2000.0)
    (vale_id,) = [v["id"] for v in d.listar_vales(hoy=HOY) if v["devolucion_id"] == dev]
    with pytest.raises(d.ValeNoSeCorrige, match="devolución"):
        d.corregir_vale(vale_id, importe=1.0, numero=None, fecha=date(2026, 9, 2), proveedor_id=1, hoy=HOY)


def test_la_PANTALLA_de_un_vale_ofrece_corregir_SOLO_a_Gerencia_y_en_cartera(base, monkeypatch):
    from unittest.mock import patch
    d, _ = base
    vale_id = _cargar(d)
    with patch("app.main._hoy_argentina", return_value=HOY):
        assert 'action="/gerencia/vales/%d/corregir"' % vale_id in _marcado(
            _cliente(monkeypatch, "gerencia").get(f"/gerencia/vales/{vale_id}"))
        assert "/corregir" not in _marcado(_cliente(monkeypatch, "administracion").get(f"/administracion/vales/{vale_id}"))
        respuesta = _cliente(monkeypatch, "gerencia").post(
            f"/gerencia/vales/{vale_id}/corregir",
            data={"proveedor_id": "1", "fecha": "2026-09-01", "importe": "6.000", "numero": ""},
            follow_redirects=False)
        assert respuesta.status_code == 303
        marcado = _marcado(_cliente(monkeypatch, "gerencia").get(f"/gerencia/vales/{vale_id}"))
    assert d.vale_a_cobrar(vale_id, HOY)["importe"] == 6000.0
    assert "Corrigió importe" in marcado and "$5.000 → $6.000" in marcado
    assert _cliente(monkeypatch, "administracion").post(
        f"/administracion/vales/{vale_id}/corregir", data={"importe": "1"}).status_code in (404, 405)


def test_juntar_proveedores_MUEVE_tambien_el_vale_que_ya_salio(base):
    """La pared de "un vale que salió no se corrige" deja pasar a juntar: no
    es corregir, es el mismo proveedor con dos fichas."""
    d, sql = base
    vale_id = _cargar(d, proveedor=2)
    d.registrar_salida_de_vale(vale_id, "cobrado", date(2026, 9, 10), sector="administracion", hoy=HOY,
                               importe_cobrado=5000.0, ingreso_a_caja=None)
    d.juntar_proveedores(1, 2)
    assert sql("SELECT proveedor_id FROM vales_a_cobrar WHERE id = %s", (vale_id,)) == [(1,)]


def test_el_LISTADO_y_MOVIMIENTOS_filtran_por_ORIGEN_y_el_Excel_lo_dice(base, monkeypatch):
    from unittest.mock import patch
    import openpyxl
    d, sql = base
    _cargar(d, numero="MANUAL-1")
    sql("INSERT INTO vales_a_cobrar (origen, proveedor_id, fecha, importe, numero) "
        "VALUES ('anterior_al_sistema', 1, '2026-09-01', 900, 'PAPEL-1')")
    assert [v["numero"] for v in d.listar_vales(hoy=HOY, origen="carga_manual")] == ["MANUAL-1"]
    assert [v["numero"] for v in d.listar_vales(hoy=HOY, origen="anterior_al_sistema")] == ["PAPEL-1"]
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 20)):
        marcado = _marcado(cliente.get("/gerencia/vales?origen=carga_manual"))
        assert "MANUAL-1" in marcado and "PAPEL-1" not in marcado
        assert 'href="/gerencia/vales/cargar"' in marcado
        pantalla = _marcado(cliente.get("/gerencia/vales/movimientos?origen=carga_manual"))
        import html
        import re
        link = html.unescape(re.search(r'href="(/gerencia/vales/movimientos-excel\?[^"]*)"', pantalla).group(1))
        assert "origen=carga_manual" in link
        excel = cliente.get(link)
    hoja = openpyxl.load_workbook(io.BytesIO(excel.content)).active
    texto = " ".join(str(c.value) for fila in hoja.iter_rows() for c in fila if c.value is not None)
    assert "MANUAL-1" in texto and "PAPEL-1" not in texto
    assert "origen Carga manual" in texto and "Administración" in texto
