"""Cobranzas de segunda (dueño, 02/10), contra Postgres.

Cada salida al puesto de segunda es un LOTE y nace pendiente. El puesto
liquida lote por lote; $0 es un cobro. Solo Gerencia corrige un importe o
vuelve un lote a pendiente, con historial. Una salida cobrada no se anula.
La base decide (db/cobranza_segunda_1 a _3): por eso esto corre contra el
esquema real (corolario 89). Los nombres son de EJEMPLO.

EL GALPÓN QUE SE PLANTA, con los rivales (lo que NO tiene que contar):

  lote 1  EJEMPLO Fruta    01/09  5 bultos   al puesto
  lote 2  EJEMPLO Fruta    10/09  3 bultos   al puesto
  lote 3  EJEMPLO Verdura  10/09  4 bultos   al puesto
  lote 4  EJEMPLO Fruta    10/09  2 bultos   MERMA de segunda   <- no es lote
  lote 5  EJEMPLO Fruta    10/09  9 bultos   al puesto ANULADO  <- no es lote
"""
import io
import os
import re
import sys
from datetime import date, timedelta

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 11)   # el lote 1 lleva 40 días: justo en el borde de la alerta

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Dia');
insert into articulos (id, nombre, grupo) overriding system value
  values (1, 'EJEMPLO Fruta', 'fruta'), (2, 'EJEMPLO Verdura', 'hortaliza');
insert into remitos_segunda (id, articulo_id, bultos, fecha_operacion, destino, motivo, anulado_el)
  overriding system value values
  (1, 1, 5, '2026-09-01', 'puesto', null, null),
  (2, 1, 3, '2026-09-10', 'puesto', null, null),
  (3, 2, 4, '2026-09-10', 'puesto', null, null),
  (4, 1, 2, '2026-09-10', 'merma', 'podrido', null),
  (5, 1, 9, '2026-09-10', 'puesto', null, now());
"""


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: las cobranzas no se verificaron")
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


def _estado(d):
    return {l["id"]: l["importe"] for l in d.lotes_de_segunda()}


def _cliente(monkeypatch, *sectores):
    from fastapi.testclient import TestClient
    from app.main import PUERTA_ADMINISTRACION, PUERTA_GERENCIA, app
    cliente = TestClient(app, base_url="https://testserver")
    for puerta in (PUERTA_ADMINISTRACION, PUERTA_GERENCIA):
        if puerta.sector in sectores:
            monkeypatch.setenv(puerta.env_var, f"clave-{puerta.sector}")
            cliente.cookies.set(puerta.cookie, puerta.firma(f"clave-{puerta.sector}"))
    return cliente


def _marcado(respuesta):
    return respuesta.text.split("</style>")[-1]


# --- la regla, en la base --------------------------------------------------------

def test_los_LOTES_son_las_salidas_al_puesto_vigentes_y_nacen_PENDIENTES(base):
    d, _ = base
    assert _estado(d) == {1: None, 2: None, 3: None}       # ni la merma ni la anulada


def test_se_cobran_DE_A_MUCHOS_y_CERO_es_cobrado_no_pendiente(base):
    d, sql = base
    assert d.registrar_cobros_de_segunda([(1, 1500.0), (2, 0.0)], date(2026, 10, 1),
                                         sector="administracion", hoy=HOY) == 2
    assert _estado(d) == {1: 1500.0, 2: 0.0, 3: None}
    assert [l["id"] for l in d.lotes_de_segunda(estado="pendiente")] == [3]
    assert [l["id"] for l in d.lotes_de_segunda(estado="cobrado")] == [1, 2]
    assert sql("SELECT sector, fecha_cobro FROM segunda_cobros WHERE salida_id = 1") == [
        ("administracion", date(2026, 10, 1))]


@pytest.mark.parametrize("cobros, motivo", [
    ([(3, 100.0), (4, 50.0)], "no es una salida al puesto vigente"),    # la merma
    ([(3, 100.0), (5, 50.0)], "no es una salida al puesto vigente"),    # la anulada
])
def test_la_BASE_no_deja_cobrar_lo_que_no_es_un_lote_y_NO_graba_ninguno(base, cobros, motivo):
    d, _ = base
    with pytest.raises(ValueError, match=motivo):
        d.registrar_cobros_de_segunda(cobros, date(2026, 10, 1), sector="administracion", hoy=HOY)
    assert _estado(d) == {1: None, 2: None, 3: None}       # el 3 tampoco: todo o nada


def test_un_lote_NO_se_cobra_dos_veces_ni_con_fecha_futura_ni_negativo(base):
    d, _ = base
    d.registrar_cobros_de_segunda([(1, 100.0)], date(2026, 10, 1), sector="administracion", hoy=HOY)
    with pytest.raises(ValueError, match="ya estaba cobrado"):
        d.registrar_cobros_de_segunda([(2, 50.0), (1, 200.0)], date(2026, 10, 1),
                                      sector="administracion", hoy=HOY)
    with pytest.raises(ValueError, match="posterior a hoy"):
        d.registrar_cobros_de_segunda([(2, 50.0)], HOY + timedelta(days=1), sector="administracion", hoy=HOY)
    with pytest.raises(ValueError, match="negativo"):
        d.registrar_cobros_de_segunda([(2, -1.0)], HOY, sector="administracion", hoy=HOY)
    assert _estado(d) == {1: 100.0, 2: None, 3: None}


def test_GERENCIA_corrige_con_HISTORIAL_y_vuelve_a_pendiente_con_MOTIVO(base):
    d, sql = base
    d.registrar_cobros_de_segunda([(1, 1500.0)], date(2026, 10, 1), sector="administracion", hoy=HOY)
    with pytest.raises(ValueError, match="mismo importe"):
        d.corregir_cobro_de_segunda(1, 1500.0)
    d.corregir_cobro_de_segunda(1, 1800.0)
    assert _estado(d)[1] == 1800.0
    with pytest.raises(ValueError, match="motivo"):
        d.volver_a_pendiente_lote_de_segunda(1, "  ")
    d.volver_a_pendiente_lote_de_segunda(1, "EJ lo cargué en otro lote")
    assert _estado(d)[1] is None
    historial = d.historial_de_cobros_de_segunda([1])[1]
    assert [(h["tipo"], float(h["importe_anterior"]), h["importe_nuevo"] and float(h["importe_nuevo"]),
             h["motivo"], h["sector"]) for h in historial] == [
        ("correccion", 1500.0, 1800.0, None, "gerencia"),
        ("a_pendiente", 1800.0, None, "EJ lo cargué en otro lote", "gerencia"),
    ]
    with pytest.raises(ValueError, match="ya está pendiente"):
        d.volver_a_pendiente_lote_de_segunda(1, "EJ otra vez")
    # Y la base solo acepta el historial de Gerencia.
    import psycopg2
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO segunda_cobros_historial (salida_id, tipo, importe_anterior, importe_nuevo, "
            "fecha_cobro_anterior, sector) VALUES (1, 'correccion', 1, 2, '2026-10-01', 'administracion')")


def test_una_salida_COBRADA_no_se_anula_hasta_volverla_a_pendiente(base):
    d, sql = base
    d.registrar_cobros_de_segunda([(2, 0.0)], date(2026, 10, 1), sector="administracion", hoy=HOY)
    with pytest.raises(d.LoteDeSegundaCobrado, match="primero Gerencia"):
        d.anular_remito_segunda(2)
    assert sql("SELECT anulado_el FROM remitos_segunda WHERE id = 2") == [(None,)]
    d.volver_a_pendiente_lote_de_segunda(2, "EJ se cargó de más")
    d.anular_remito_segunda(2)
    assert 2 not in _estado(d)


def test_la_ALERTA_cuenta_los_lotes_pendientes_de_MAS_de_40_dias(base):
    d, _ = base
    from core.cobranzas_segunda import DIAS_SEGUNDA_SIN_COBRAR
    assert DIAS_SEGUNDA_SIN_COBRAR == 40
    assert d.contar_segunda_sin_cobrar(HOY)["casos"] == 0                      # el lote 1 lleva 40
    assert d.contar_segunda_sin_cobrar(HOY + timedelta(days=1)) == {"casos": 1, "mas_viejo": date(2026, 9, 1)}
    d.registrar_cobros_de_segunda([(1, 0.0)], date(2026, 10, 1), sector="administracion", hoy=HOY)
    assert d.contar_segunda_sin_cobrar(HOY + timedelta(days=1))["casos"] == 0  # $0 es cobrado


# --- la pantalla ---------------------------------------------------------------------

def test_ADMINISTRACION_carga_varios_cobros_con_UN_guardar(base, monkeypatch):
    from unittest.mock import patch
    d, sql = base
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main._hoy_argentina", return_value=HOY):
        pantalla = cliente.get("/administracion/cobranzas-segunda")
        marcado = _marcado(pantalla)
        assert pantalla.status_code == 200
        assert marcado.count('name="importe_') == 3 and 'name="importe_4"' not in marcado
        assert "Volver a pendiente" not in marcado
        respuesta = cliente.post("/administracion/cobranzas-segunda/cobrar", data={
            "fecha_cobro": "2026-10-05", "importe_1": "1.500,50", "importe_2": "0", "importe_3": "",
            "desde": "", "hasta": "", "articulo_id": "", "estado": "todos"}, follow_redirects=False)
    assert respuesta.status_code == 303 and "2+lotes+cobrados" in respuesta.headers["location"]
    assert _estado(d) == {1: 1500.5, 2: 0.0, 3: None}
    assert sql("SELECT DISTINCT sector, fecha_cobro FROM segunda_cobros") == [
        ("administracion", date(2026, 10, 5))]


def test_GERENCIA_tiene_la_misma_pantalla_y_ademas_CORRIGE(base, monkeypatch):
    from unittest.mock import patch
    d, _ = base
    d.registrar_cobros_de_segunda([(1, 1500.0)], date(2026, 10, 1), sector="administracion", hoy=HOY)
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=HOY):
        marcado = _marcado(cliente.get("/gerencia/cobranzas-segunda"))
        assert 'action="/gerencia/cobranzas-segunda/1/corregir"' in marcado
        assert 'action="/gerencia/cobranzas-segunda/1/pendiente"' in marcado
        respuesta = cliente.post("/gerencia/cobranzas-segunda/1/corregir", data={"importe": "1600"},
                                 follow_redirects=False)
        assert respuesta.status_code == 303
        marcado = _marcado(cliente.get("/gerencia/cobranzas-segunda"))
    assert _estado(d)[1] == 1600.0
    assert "corrigió $1.500 → $1.600" in marcado
    # Administración no tiene la puerta de corregir.
    admin = _cliente(monkeypatch, "administracion")
    assert admin.post("/administracion/cobranzas-segunda/1/corregir", data={"importe": "1"}).status_code in (404, 405)


def test_GERENCIA_sin_su_clave_no_corrige(base, monkeypatch):
    d, _ = base
    d.registrar_cobros_de_segunda([(1, 1500.0)], date(2026, 10, 1), sector="administracion", hoy=HOY)
    monkeypatch.setenv("CLAVE_GERENCIA", "clave-gerencia")
    from fastapi.testclient import TestClient
    from app.main import app
    TestClient(app, base_url="https://testserver").post("/gerencia/cobranzas-segunda/1/corregir",
                                                       data={"importe": "1"}, follow_redirects=False)
    assert _estado(d)[1] == 1500.0


def test_MOVIMIENTOS_no_ofrece_ANULAR_un_lote_cobrado(base, monkeypatch):
    d, _ = base
    d.registrar_cobros_de_segunda([(2, 100.0)], date(2026, 10, 1), sector="administracion", hoy=HOY)
    cliente = _cliente(monkeypatch, "administracion")
    marcado = _marcado(cliente.get("/administracion/stock/movimientos?fecha_desde=2026-09-01&fecha_hasta=2026-09-30"))
    assert 'action="/administracion/stock/movimientos/remitos/2/anular"' not in marcado
    assert 'action="/administracion/stock/movimientos/remitos/3/anular"' in marcado
    assert "Gerencia lo vuelve a pendiente" in marcado
    # Y si llega igual por un POST armado a mano, vuelve con el motivo.
    respuesta = cliente.post("/administracion/stock/movimientos/remitos/2/anular",
                             data={"fecha_desde": "2026-09-01", "fecha_hasta": "2026-09-30"})
    assert "ya está cobrado" in respuesta.text
    assert 2 in _estado(d)


@pytest.mark.parametrize("formato", ["exportar-pdf", "exportar-excel"])
def test_la_EXPORTACION_sigue_el_link_de_la_pantalla_con_TODOS_sus_filtros(base, monkeypatch, formato):
    """Se filtra por artículo y estado, se sigue el link QUE LA PANTALLA DIBUJA
    y se lee el archivo: el otro artículo no aparece y el filtro sí."""
    import html
    from unittest.mock import patch
    d, _ = base
    d.registrar_cobros_de_segunda([(2, 900.0)], date(2026, 10, 1), sector="administracion", hoy=HOY)
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=HOY):
        marcado = _marcado(cliente.get("/gerencia/cobranzas-segunda?articulo_id=1&estado=todos"
                                       "&desde=2026-09-01&hasta=2026-09-30"))
        link = html.unescape(re.search(rf'href="(/gerencia/cobranzas-segunda/{formato}\?[^"]*)"', marcado).group(1))
        archivo = cliente.get(link)
    from tests.test_exportaciones_filtradas import _texto_del_archivo
    texto = _texto_del_archivo(archivo)
    assert "EJEMPLO Fruta" in texto and "EJEMPLO Verdura" not in texto
    assert "artículo EJEMPLO Fruta" in texto
    assert "01/09/2026 al 30/09/2026" in texto


# --- la Rentabilidad Real ---------------------------------------------------------------

def test_la_RENTABILIDAD_suma_el_recupero_al_DIA_DE_LA_SALIDA_y_cuenta_los_pendientes(base):
    """Lo cobrado entra al día de la SALIDA (no al del cobro) y al artículo del
    lote; lo pendiente solo se cuenta por día, y el día NO queda provisorio."""
    from core.costo_real import calcular_rentabilidad_real
    d, _ = base
    d.registrar_cobros_de_segunda([(1, 1500.0), (3, 0.0)], date(2026, 10, 5), sector="administracion", hoy=HOY)
    lotes = d.lotes_de_segunda(desde=date(2026, 9, 1), hasta=date(2026, 9, 30))
    resultado = calcular_rentabilidad_real([], {}, 1, date(2026, 9, 1), date(2026, 9, 30), segunda=lotes)
    filas = {f["articulo_nombre"]: f for g in resultado["grupos"] for f in g["filas"]}
    assert filas["EJEMPLO Fruta"]["recupero_segunda"] == 1500.0
    assert filas["EJEMPLO Fruta"]["renta_pesos"] == 1500.0
    assert filas["EJEMPLO Verdura"]["recupero_segunda"] == 0.0           # cobrado en cero: se ve
    assert resultado["totales"]["recupero_segunda"] == 1500.0
    assert resultado["segunda_sin_cobrar"] == [{"fecha": date(2026, 9, 10), "lotes": 1}]
    assert resultado["fechas_provisorias"] == []
    # El cobro fue el 05/10: un rango de octubre no lo ve.
    octubre = calcular_rentabilidad_real([], {}, 1, date(2026, 10, 1), date(2026, 10, 31),
                                         segunda=d.lotes_de_segunda(desde=date(2026, 10, 1)))
    assert octubre["totales"]["recupero_segunda"] == 0.0 and octubre["grupos"] == []


def test_la_RENTABILIDAD_lo_muestra_en_PANTALLA_PDF_y_EXCEL(base, monkeypatch):
    from unittest.mock import patch
    from tests.test_exportaciones_filtradas import _texto_del_archivo
    d, _ = base
    d.registrar_cobros_de_segunda([(1, 1500.0)], date(2026, 10, 5), sector="administracion", hoy=HOY)
    cliente = _cliente(monkeypatch, "gerencia")
    filtros = "cliente_id=1&fecha_desde=2026-09-01&fecha_hasta=2026-09-30"
    with patch("app.main._hoy_argentina", return_value=HOY):
        marcado = _marcado(cliente.get(f"/gerencia/rentabilidad-real?{filtros}"))
        pdf = _texto_del_archivo(cliente.get(f"/gerencia/rentabilidad-real/exportar-pdf?{filtros}"))
        excel = _texto_del_archivo(cliente.get(f"/gerencia/rentabilidad-real/exportar-excel?{filtros}"))
    assert 'class="chip-recupero-segunda"' in marcado and "+$1.500" in marcado
    assert 'class="recupero-segunda"' in marcado
    # Los dos lotes del 10/09 siguen sin cobrar: se dice, y el día no es provisorio.
    assert "10/09 (2 lotes de segunda sin cobrar)" in marcado
    assert 'class="provisorio"' not in marcado
    pdf = " ".join(pdf.split())
    assert "recupero de segunda +$1.500" in pdf and "10/09 (2 lotes)" in pdf
    assert "Recupero de segunda $" in excel and "1500" in excel
