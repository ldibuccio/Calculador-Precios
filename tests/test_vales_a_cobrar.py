"""Vales a cobrar (dueño, 30/09), contra Postgres.

Un vale nace de una devolución de vacíos con importe, o se carga por SQL
(anterior al sistema). Sale de la cartera cobrado o cruzado (Administración),
anulado (Gerencia), o porque se anuló su devolución. NADA DE ESTO TOCA EL
STOCK. Corre contra el esquema real (corolario 89): el CHECK de las salidas y
el del origen son la mitad de la regla. Los nombres son de EJEMPLO.

  proveedor 1  EJ Uno  N92P01, marca "EJ Roja" con 100 cajones en el arranque
  compra 21    EJ Uno  recepcionada, seña $500 por cajón, marca "EJ Roja"
"""
import io
import os
import re
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Fruta');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJ Uno', 'N92P01'), (2, 'EJ Dos', 'N92P02');
insert into marcas_vacio (id, proveedor_id, nombre, nombre_normalizado) overriding system value
  values (1, 1, 'EJ Roja', 'ej roja');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, sena, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real, marca_vacio_id)
  overriding system value values
  (21, 1, 1, '2026-09-05', 10, 16, 160, 100, 500, 'recepcionado', '2026-09-05 18:00-03', 10, 16, 1);
insert into vacios_deposito_arranques (id, motivo, creado_en) overriding system value
  values (1, 'EJEMPLO conteo', '2026-09-06 12:00-03');
insert into vacios_deposito_arranque_pilas (arranque_id, proveedor_id, marca_vacio_id, cantidad)
  values (1, 1, 1, 100), (1, 1, null, 50);
"""

HOY = date(2026, 12, 1)   # lejos de la fecha real, para que los días no dependan del reloj


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: los vales no se verificaron")
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


def _devolucion(d, cajones=4, importe=2000.0, numero=None, marca=1):
    return d.crear_devolucion_vacios(1, marca, cajones, foto_ruta="2026-09-30/vale.jpg", importe=importe,
                                     cargada_desde="administracion", numero_vale=numero)


def _anterior(sql, importe, fecha, proveedor=1, numero=None):
    (vid,), = sql("INSERT INTO vales_a_cobrar (origen, proveedor_id, fecha, importe, numero) "
                  "VALUES ('anterior_al_sistema', %s, %s, %s, %s) RETURNING id",
                  (proveedor, fecha, importe, numero))
    return vid


# --- el vale nace con la devolución -----------------------------------------

def test_una_devolucion_CON_importe_deja_un_vale_EN_CARTERA_leido_de_ella(base):
    d, sql = base
    dev = _devolucion(d, cajones=4, importe=2100.0, numero="  V-77 ")
    (vale,) = d.listar_vales(hoy=HOY)
    assert vale["devolucion_id"] == dev and vale["estado"] == "en_cartera"
    assert vale["proveedor"] == "EJ Uno" and vale["marca"] == "EJ Roja" and vale["cajones"] == 4
    assert vale["importe"] == 2100.0 and vale["numero"] == "V-77"
    # Lo calculado lo hace el server: seña de la pila por cajones, y se ve la diferencia.
    assert vale["importe_calculado"] == 2000.0 and vale["diferencia"] == 100.0
    # El importe vive UNA vez: en la devolución, no en el vale.
    assert sql("SELECT importe, proveedor_id, fecha FROM vales_a_cobrar") == [(None, None, None)]


def test_SIN_importe_no_hay_vale_y_un_NUMERO_sin_importe_rebota_sin_escribir(base):
    d, sql = base
    _devolucion(d, importe=None)
    assert d.listar_vales(hoy=HOY) == []
    antes = sql("SELECT count(*) FROM vacios_deposito_devoluciones")
    with pytest.raises(ValueError, match="número de vale va con el importe"):
        _devolucion(d, importe=None, numero="V-1")
    assert sql("SELECT count(*) FROM vacios_deposito_devoluciones") == antes


def test_sin_SENA_de_esa_pila_el_calculado_queda_vacio_y_no_inventa_diferencia(base):
    d, _ = base
    _devolucion(d, cajones=3, importe=900.0, marca=None)     # "sin asignar": ninguna compra con seña
    (vale,) = d.listar_vales(hoy=HOY)
    assert vale["importe_calculado"] is None and vale["diferencia"] is None


def test_las_devoluciones_VIEJAS_no_entran_a_la_cartera(base):
    """Las del 25/09 son pruebas (dueño): el vale nace al guardar, no se backfillea."""
    d, sql = base
    sql("INSERT INTO vacios_deposito_devoluciones (proveedor_id, compra_id, cantidad, importe, stock_sistema,"
        " creado_en) VALUES (1, 21, 5, 1000, 50, '2026-09-25 10:00-03')")
    assert d.listar_vales(estado=None, hoy=HOY) == []


# --- las salidas --------------------------------------------------------------

def test_COBRADO_saca_el_vale_del_total_y_no_se_puede_salir_dos_veces(base):
    d, _ = base
    _devolucion(d, importe=2000.0)
    (vale,) = d.listar_vales(hoy=HOY)
    assert d.resumen_de_la_cartera(HOY)["total"] == 2000.0
    d.registrar_salida_de_vale(vale["id"], "cobrado", date(2026, 11, 30), sector="administracion", hoy=HOY,
                               importe_cobrado=1950.0, ingreso_a_caja=" Caja chica ")
    resumen = d.resumen_de_la_cartera(HOY)
    assert resumen["total"] == 0 and resumen["cantidad"] == 0
    (cobrado,) = d.listar_vales(estado="cobrado", hoy=HOY)
    assert cobrado["importe_cobrado"] == 1950.0 and cobrado["ingreso_a_caja"] == "Caja chica"
    assert cobrado["salida_sector"] == "administracion" and cobrado["salida_creado_en"] is not None
    with pytest.raises(ValueError, match="ya salió de la cartera"):
        d.registrar_salida_de_vale(vale["id"], "cruzado", date(2026, 11, 30), sector="administracion",
                                   hoy=HOY, referencia="L-1")


def test_ANULAR_es_solo_de_GERENCIA_y_con_motivo_en_el_codigo_Y_en_la_base(base):
    d, sql = base
    vid = _anterior(sql, 1000, date(2026, 8, 1))
    with pytest.raises(ValueError, match="no se carga desde este sector"):
        d.registrar_salida_de_vale(vid, "anulado", date(2026, 11, 30), sector="administracion", hoy=HOY,
                                   motivo="EJ")
    with pytest.raises(ValueError, match="motivo"):
        d.registrar_salida_de_vale(vid, "anulado", date(2026, 11, 30), sector="gerencia", hoy=HOY, motivo=" ")
    # La pared de la base, sin pasar por el código.
    import psycopg2
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO vales_a_cobrar_salidas (vale_id, tipo, fecha, motivo, sector) "
            "VALUES (%s, 'anulado', '2026-11-30', 'EJ', 'administracion')", (vid,))
    # Un cobrado SIN importe: `importe_cobrado > 0` da NULL, y sin el coalesce el CHECK lo dejaba pasar.
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO vales_a_cobrar_salidas (vale_id, tipo, fecha, sector) "
            "VALUES (%s, 'cobrado', '2026-11-30', 'administracion')", (vid,))
    # El de PAPEL no se anula (dueño, 01/10): el de una devolución sí.
    with pytest.raises(ValueError, match="en papel no se anula"):
        d.registrar_salida_de_vale(vid, "anulado", date(2026, 11, 30), sector="gerencia", hoy=HOY,
                                   motivo="EJ perdido")
    assert sql("SELECT count(*) FROM vales_a_cobrar_salidas") == [(0,)]
    _devolucion(d)
    (de_devolucion,) = [v["id"] for v in d.listar_vales(hoy=HOY) if v["origen"] == "devolucion"]
    d.registrar_salida_de_vale(de_devolucion, "anulado", date(2026, 11, 30), sector="gerencia", hoy=HOY,
                               motivo="EJ perdido")
    assert d.listar_vales(estado="anulado", hoy=HOY)[0]["motivo"] == "EJ perdido"


def test_el_vale_en_PAPEL_sale_cobrado_o_cruzado_y_nunca_anulado():
    import app.db as d
    assert d.salidas_del_vale("anterior_al_sistema", "gerencia") == []
    assert d.salidas_del_vale("anterior_al_sistema", "administracion") == ["cobrado", "cruzado"]
    assert d.salidas_del_vale("devolucion", "gerencia") == ["anulado"]


def test_CRUZADO_pide_referencia_y_la_fecha_no_puede_ser_futura(base):
    d, sql = base
    vid = _anterior(sql, 1000, date(2026, 8, 1))
    with pytest.raises(ValueError, match="referencia"):
        d.registrar_salida_de_vale(vid, "cruzado", date(2026, 11, 30), sector="administracion", hoy=HOY)
    with pytest.raises(ValueError, match="posterior a hoy"):
        d.registrar_salida_de_vale(vid, "cruzado", date(2026, 12, 2), sector="administracion", hoy=HOY,
                                   referencia="L-9")
    d.registrar_salida_de_vale(vid, "cruzado", date(2026, 11, 30), sector="administracion", hoy=HOY,
                               referencia="L-9")
    assert d.listar_vales(estado="cruzado", hoy=HOY)[0]["referencia"] == "L-9"


def test_el_SECTOR_de_cada_salida_es_el_MISMO_en_el_codigo_y_en_el_sql():
    """La pantalla ofrece lo que dice SECTOR_DE_LA_SALIDA; la base rechaza lo
    que dicen los CHECK. Si se separan, hay un botón que el POST rebota."""
    import app.db as d
    texto = io.open(os.path.join(RAIZ, "db", "vales_2_salidas.sql"), encoding="utf-8").read()
    encontrado = dict(re.findall(r"tipo <> '(\w+)'\s*or \(.*?sector = '(\w+)'\)", texto, re.S))
    assert encontrado == d.SECTOR_DE_LA_SALIDA


# --- anular la devolución -----------------------------------------------------

def test_anular_la_DEVOLUCION_saca_el_vale_EN_CARTERA_y_rebota_si_ya_se_COBRO(base):
    d, _ = base
    uno = _devolucion(d, importe=1000.0)
    dos = _devolucion(d, importe=3000.0)
    d.anular_devolucion_vacios(uno)
    vales = {v["devolucion_id"]: v for v in d.listar_vales(estado=None, hoy=HOY)}
    assert vales[uno]["estado"] == "devolucion_anulada"
    assert d.resumen_de_la_cartera(HOY)["total"] == 3000.0
    with pytest.raises(ValueError, match="está anulada"):
        d.registrar_salida_de_vale(vales[uno]["id"], "cobrado", date(2026, 11, 30), sector="administracion",
                                   hoy=HOY, importe_cobrado=1000)
    d.registrar_salida_de_vale(vales[dos]["id"], "cobrado", date(2026, 11, 30), sector="administracion",
                               hoy=HOY, importe_cobrado=3000)
    with pytest.raises(ValueError, match="ya se cobró"):
        d.anular_devolucion_vacios(dos)
    assert d.listar_vales(estado="cobrado", hoy=HOY)[0]["devolucion_anulada_el"] is None


# --- los anteriores al sistema ------------------------------------------------

def test_un_vale_ANTERIOR_AL_SISTEMA_suma_al_MISMO_total_y_el_CHECK_no_deja_mezclar(base):
    d, sql = base
    _anterior(sql, 1500, date(2026, 8, 1), numero="P-1")
    _devolucion(d, importe=2000.0)
    resumen = d.resumen_de_la_cartera(HOY)
    assert resumen["total"] == 3500.0 and resumen["cantidad"] == 2
    import psycopg2
    for malo in (
        "INSERT INTO vales_a_cobrar (origen, proveedor_id, fecha) VALUES ('anterior_al_sistema', 1, '2026-08-01')",
        "INSERT INTO vales_a_cobrar (origen, proveedor_id, fecha, importe, importe_calculado)"
        " VALUES ('anterior_al_sistema', 1, '2026-08-01', 10, 10)",
        "INSERT INTO vales_a_cobrar (origen, devolucion_id, proveedor_id)"
        " VALUES ('devolucion', (SELECT max(id) FROM vacios_deposito_devoluciones), 1)",
    ):
        with pytest.raises(psycopg2.errors.CheckViolation):
            sql(malo)


# --- las dos alertas y los límites --------------------------------------------

def test_las_ALERTAS_cuentan_la_misma_cartera_y_los_LIMITES_las_mueven(base):
    d, sql = base
    assert d.limites_de_vales() == {"monto": 500000.0, "dias": 14}
    _anterior(sql, 400000, date(2026, 11, 1))        # 30 días
    _anterior(sql, 150000, date(2026, 11, 25))       # 6 días
    assert d.contar_vales_plata_sin_aplicar(HOY)["casos"] == 550000
    assert d.contar_vales_viejos(HOY)["casos"] == 1
    d.guardar_limites_de_vales(600000, 5)
    assert d.contar_vales_plata_sin_aplicar(HOY)["casos"] == 0
    assert d.contar_vales_viejos(HOY)["casos"] == 2
    with pytest.raises(ValueError):
        d.guardar_limites_de_vales(0, 5)


def test_la_alerta_de_DIAS_mide_mas_de_y_no_igual(base):
    d, sql = base
    _anterior(sql, 100, date(2026, 11, 17))     # exactamente 14 días: no salta
    assert d.contar_vales_viejos(HOY)["casos"] == 0
    _anterior(sql, 100, date(2026, 11, 16))     # 15
    assert d.contar_vales_viejos(HOY)["casos"] == 1


# --- los movimientos ----------------------------------------------------------

def test_los_MOVIMIENTOS_traen_la_entrada_y_la_salida_por_su_fecha(base):
    d, sql = base
    vid = _anterior(sql, 1000, date(2026, 11, 10))
    _anterior(sql, 2000, date(2026, 10, 1))                      # fuera de la ventana
    d.registrar_salida_de_vale(vid, "cobrado", date(2026, 11, 20), sector="administracion", hoy=HOY,
                               importe_cobrado=900)
    movs = d.movimientos_de_vales(date(2026, 11, 1), date(2026, 11, 30), proveedor_id=None, hoy=HOY)
    assert [(m["que"], m["fecha"], m["importe"]) for m in movs] == [
        ("entrada", date(2026, 11, 10), 1000.0), ("cobrado", date(2026, 11, 20), 900.0)]


# --- las pantallas ------------------------------------------------------------

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


def test_ADMINISTRACION_ve_el_total_y_cobra_desde_el_detalle(base, monkeypatch):
    from unittest.mock import patch
    d, sql = base
    vid = _anterior(sql, 12345, date(2026, 11, 1), numero="P-7")
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main._hoy_argentina", return_value=HOY):
        listado = cliente.get("/administracion/vales")
        detalle = cliente.get(f"/administracion/vales/{vid}")
        cobro = cliente.post(f"/administracion/vales/{vid}/cobrar",
                             data={"fecha": "2026-11-30", "importe_cobrado": "12.000", "ingreso_a_caja": ""},
                             follow_redirects=False)
    assert listado.status_code == 200
    marcado = _marcado(listado)
    assert "$12.345 en cartera" in marcado and "1 vale sin aplicar" in marcado
    assert f'href="/administracion/vales/{vid}"' in marcado and "30 días en cartera" in marcado
    marcado = _marcado(detalle)
    assert f'action="/administracion/vales/{vid}/cobrar"' in marcado
    assert f'action="/administracion/vales/{vid}/cruzar"' in marcado
    assert "/anular" not in marcado          # anular es de Gerencia: acá no se ofrece
    assert cobro.status_code == 303
    assert d.listar_vales(estado="cobrado", hoy=HOY)[0]["importe_cobrado"] == 12000.0


def test_GERENCIA_pide_su_clave_anula_y_fija_los_limites(base, monkeypatch):
    from unittest.mock import patch
    d, sql = base
    papel = _anterior(sql, 1000, date(2026, 11, 1))
    _devolucion(d)
    (vid,) = [v["id"] for v in d.listar_vales(hoy=HOY) if v["origen"] == "devolucion"]
    sin_clave = _cliente(monkeypatch, "administracion")
    monkeypatch.setenv("CLAVE_GERENCIA", "clave-gerencia")     # con la clave puesta y sin la cookie
    with patch("app.main._hoy_argentina", return_value=HOY):
        sin = sin_clave.get("/gerencia/vales")
        assert "en cartera" not in sin.text and "type=\"password\"" in sin.text
        cliente = _cliente(monkeypatch, "gerencia")
        detalle = cliente.get(f"/gerencia/vales/{vid}")
        detalle_papel = cliente.get(f"/gerencia/vales/{papel}")
        anulado = cliente.post(f"/gerencia/vales/{vid}/anular", data={"fecha": "2026-11-30", "motivo": "EJ"},
                               follow_redirects=False)
        limites = cliente.post("/gerencia/vales/limites", data={"monto": "700.000", "dias": "20"},
                               follow_redirects=False)
        listado = cliente.get("/gerencia/vales")
    marcado = _marcado(detalle)
    assert f'action="/gerencia/vales/{vid}/anular"' in marcado and "/cobrar" not in marcado
    assert "/anular" not in _marcado(detalle_papel)          # el de papel no se anula
    assert anulado.status_code == 303 and limites.status_code == 303
    assert d.listar_vales(estado="anulado", hoy=HOY)[0]["salida_sector"] == "gerencia"
    assert d.limites_de_vales() == {"monto": 700000.0, "dias": 20}
    assert 'action="/gerencia/vales/limites"' in _marcado(listado)


def test_el_listado_de_ADMINISTRACION_no_ofrece_cambiar_los_limites(base, monkeypatch):
    from unittest.mock import patch
    _cliente_admin = _cliente(monkeypatch, "administracion")
    with patch("app.main._hoy_argentina", return_value=HOY):
        marcado = _marcado(_cliente_admin.get("/administracion/vales"))
    assert "/gerencia/vales/limites" not in marcado and "/gerencia/" not in marcado


def test_el_EXCEL_de_movimientos_baja_lo_filtrado(base, monkeypatch):
    import openpyxl
    from unittest.mock import patch
    d, sql = base
    _anterior(sql, 1000, date(2026, 11, 10), numero="P-3")
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main._hoy_argentina", return_value=HOY):
        pantalla = cliente.get("/administracion/vales/movimientos?desde=2026-11-01&hasta=2026-11-30")
        excel = cliente.get("/administracion/vales/movimientos-excel?desde=2026-11-01&hasta=2026-11-30")
    assert pantalla.status_code == 200 and "Entró a cartera · EJ Uno" in _marcado(pantalla)
    hoja = openpyxl.load_workbook(io.BytesIO(excel.content)).active
    filas = [tuple(c.value for c in fila) for fila in hoja.iter_rows(min_row=5)]
    assert len(filas) == 1 and filas[0][1] == "Entró a cartera" and filas[0][3] == "P-3" and filas[0][6] == 1000


def test_la_DEVOLUCION_desde_la_pantalla_guarda_el_numero_del_vale(base, monkeypatch):
    from unittest.mock import patch
    d, _ = base
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main.subir_foto_comanda", return_value="2026-09-30/vale.jpg"), \
            patch("app.main._comprimir_foto_jpeg", return_value=b"jpg"):
        respuesta = cliente.post("/deposito/vacios/devolucion", data={
            "proveedor_id": "1", "marca_vacio_id": "1", "cantidad": "2", "importe": "1.000",
            "numero_vale": "D-5"}, files={"foto": ("vale.jpg", b"x", "image/jpeg")}, follow_redirects=False)
    assert respuesta.status_code == 303
    (vale,) = d.listar_vales(hoy=HOY)
    assert vale["numero"] == "D-5" and vale["importe"] == 1000.0 and vale["importe_calculado"] == 1000.0


# --- la carga de los vales en papel -------------------------------------------

def _correr(sql, archivo):
    sql(io.open(os.path.join(RAIZ, "db", archivo), encoding="utf-8").read())


def test_la_carga_en_PAPEL_revisa_carga_TODO_o_NADA_y_no_duplica(base):
    import psycopg2
    d, sql = base
    _correr(sql, "vales_papel_1_pegar.sql")                     # las dos filas de EJEMPLO
    with pytest.raises(psycopg2.errors.RaiseException, match="fila 1: el codigo no es de un puesto"):
        _correr(sql, "vales_papel_3_cargar.sql")
    assert sql("SELECT count(*) FROM vales_a_cobrar") == [(0,)]
    sql("DELETE FROM vales_papel_listado")
    sql("INSERT INTO vales_papel_listado VALUES (1, 'n92p01', '31/08/2026', 15000, 'P-1', null),"
        " (2, 'N92P02', '30/02/2026', 10, null, null)")
    problemas = sql("SELECT fila, problema FROM vales_papel_revision WHERE problema IS NOT NULL")
    assert problemas == [(2, "esa fecha no existe")]
    with pytest.raises(psycopg2.errors.RaiseException, match="fila 2"):
        _correr(sql, "vales_papel_3_cargar.sql")
    sql("UPDATE vales_papel_listado SET fecha = '28/02/2026' WHERE fila = 2")
    _correr(sql, "vales_papel_3_cargar.sql")
    vales = d.listar_vales(hoy=HOY)
    assert [(v["proveedor"], v["fecha"], v["importe"], v["numero"], v["origen"]) for v in vales] == [
        ("EJ Dos", date(2026, 2, 28), 10.0, None, "anterior_al_sistema"),
        ("EJ Uno", date(2026, 8, 31), 15000.0, "P-1", "anterior_al_sistema")]
    assert sql("SELECT count(*) FROM vales_papel_listado") == [(0,)]
    sql("INSERT INTO vales_papel_listado VALUES (1, 'N92P01', '31/08/2026', 15000, 'P-1', null)")
    assert sql("SELECT problema FROM vales_papel_revision") == [("ya estaba cargado",)]


def test_la_REVISION_del_esquema_es_la_MISMA_que_la_de_la_migracion():
    """La vista vive en dos archivos: la migración y db/esquema_completo.sql.
    Si se separan, una base nueva revisa con otra regla."""
    def cuerpo(texto):
        a = texto.index("create view vales_papel_revision")
        b = texto.index("limit 1) pr on true", a)
        return " ".join(texto[a:b].split())
    migracion = io.open(os.path.join(RAIZ, "db", "vales_4_listado_en_papel.sql"), encoding="utf-8").read()
    esquema = io.open(os.path.join(RAIZ, "db", "esquema_completo.sql"), encoding="utf-8").read()
    assert cuerpo(migracion) == cuerpo(esquema)
