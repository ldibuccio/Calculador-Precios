"""Con fecha anterior desde Administración (dueño, 05/10), contra Postgres.

- Depósito: merma, pase a segunda y devolución al proveedor SOLO con la fecha
  de hoy.
- Administración: ingreso, devolución, merma y pase con fecha ANTERIOR, solo
  si esa mercadería no la tomó ya un armado o una guía R (la pantalla dice
  cuál y no deja), con una CONTRASEÑA ESPECIAL que fija Gerencia y se pide
  cada vez. Queda registrado quién y cuándo.

EL GALPÓN, con el RIVAL (el armado del 10/09, que no se puede quedar sin lo suyo):

  05/09  compra 11: 10 cajones de EJEMPLO Pera
  10/09  armado de 8 para la verdulería       -> quedan 2
  Hoy es el 20/09.

Una merma de 2 el 08/09 no le saca nada al armado (quedan 8 para él). Una de
3 sí: el armado se quedaría con 7. Y una de 3 el 12/09 no encuentra
mercadería: ese día quedaban 2.
"""
import io
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402
from tests.test_administracion_reordenada import CLAVES, _cliente  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 9, 20)
CLAVE = "galpon-2026"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Verduleria');
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Pera');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta)
  overriding system value values (1, 1, 1, 18, 'kilo');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (11, 1, 1, '2026-09-05', 10, 18, 180, 100, 'recepcionado', '2026-09-05 18:00-03', 10, 18);
insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 1, '2026-09-10', 'texto');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
                               cantidad_armada, armado_el)
  overriding system value
  values (1, 1, 'CENTRO', 1, 1, 8, 8, '2026-09-10 10:00-03');
"""


@pytest.fixture
def galpon(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    monkeypatch.setenv("DATABASE_URL", url)
    for clave, valor in CLAVES.items():
        monkeypatch.setenv(clave, valor)
    import app.db as d
    import app.main as m

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
    with patch("app.main._hoy_argentina", return_value=HOY):
        yield d, m, sql


def _merma(cliente, fecha, cantidad, *, clave=CLAVE, quien="Marta"):
    return cliente.post("/administracion/retroactivo/merma", data={
        "articulo_id": "1", "que_merma": "sueltos", "cantidad": str(cantidad), "motivo": "podrido",
        "fecha": fecha, "sin_foto_confirmado": "1", "clave_especial": clave, "quien": quien,
    }, follow_redirects=False)


def _mermas(sql):
    return sql("SELECT fecha_operacion, -cantidad FROM movimientos_stock WHERE tipo = 'merma' ORDER BY id")


# --- la contraseña especial --------------------------------------------------

def test_la_CONTRASENA_la_fija_GERENCIA_se_guarda_sin_texto_y_se_pide_CADA_VEZ(galpon):
    d, m, sql = galpon
    adm = _cliente(m, "administracion")
    sin_clave = _merma(adm, "2026-09-08", 2)
    assert "Gerencia todavía no fijó la contraseña especial." in sin_clave.text

    # Administración sola no la puede fijar; Gerencia sí.
    adm.post("/gerencia/clave-retroactivo", data={"clave": CLAVE, "repetida": CLAVE})
    assert sql("SELECT count(*) FROM claves_especiales")[0][0] == 0
    gerencia = _cliente(m, "gerencia")
    distinta = gerencia.post("/gerencia/clave-retroactivo", data={"clave": CLAVE, "repetida": "otra-cosa"})
    assert "no son iguales" in distinta.text
    gerencia.post("/gerencia/clave-retroactivo", data={"clave": CLAVE, "repetida": CLAVE})
    (sal, guardado), = sql("SELECT sal, hash FROM claves_especiales WHERE nombre = 'retroactivo'")
    assert CLAVE not in guardado and CLAVE not in sal

    # Se pide cada vez: la mala rebota y no escribe; la buena entra.
    assert "La contraseña especial no es correcta." in _merma(adm, "2026-09-08", 2, clave="admin-secreta").text
    assert _mermas(sql) == []
    assert _merma(adm, "2026-09-08", 2).status_code == 303
    sin_escribirla = _merma(adm, "2026-09-08", 1, clave="")      # se pide de nuevo, cada vez
    assert sin_escribirla.status_code == 400 and _mermas(sql) == [(date(2026, 9, 8), 2)]


# --- solo si esa mercadería no se usó ----------------------------------------

def _con_clave(d):
    d.fijar_clave_especial(CLAVE)


def test_la_merma_que_NO_toca_al_armado_entra_con_su_fecha_y_queda_QUIEN(galpon):
    d, m, sql = galpon
    _con_clave(d)
    respuesta = _merma(_cliente(m, "administracion"), "2026-09-08", 2)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/administracion/retroactivo/merma?aviso=")
    assert _mermas(sql) == [(date(2026, 9, 8), 2)]
    registro = sql("SELECT tipo, fecha_del_hecho, quien, movimiento_id IS NOT NULL FROM retroactivos")
    assert registro == [("merma", date(2026, 9, 8), "Marta", True)]


def test_la_merma_que_le_SACA_al_armado_NO_entra_y_dice_CUAL(galpon):
    d, m, sql = galpon
    _con_clave(d)
    respuesta = _merma(_cliente(m, "administracion"), "2026-09-08", 3)

    assert respuesta.status_code == 400
    assert "El armado del pedido de EJEMPLO Verduleria del 10/09 se queda sin mercadería." in respuesta.text
    assert "Hasta que eso se elimine" in respuesta.text
    assert _mermas(sql) == [] and sql("SELECT count(*) FROM retroactivos")[0][0] == 0


# EL CONTROL FLOJO (dueño, 10/10): con una compra 12 del 06/09, la merma de 3
# del 08/09 le cambia la guía al armado (7 de la 11 y 1 de la 12) pero no lo
# deja sin mercadería: entra. Con el control estricto, esto frenaba.
COMPRA_12 = """insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real) overriding system value
  values (12, 1, 1, '2026-09-06', 10, 18, 180, 90, 'recepcionado', '2026-09-06 18:00-03', 10, 18)"""


def test_la_merma_que_solo_le_CAMBIA_la_guia_al_armado_ENTRA(galpon):
    d, m, sql = galpon
    _con_clave(d)
    sql(COMPRA_12)
    respuesta = _merma(_cliente(m, "administracion"), "2026-09-08", 3)
    assert respuesta.status_code == 303, respuesta.text[-600:]
    assert _mermas(sql) == [(date(2026, 9, 8), 3)]
    from core.costo_real import atribuir_costos_fifo
    entradas, salidas = d.entradas_y_salidas_stock_articulo(1)
    armado = next(s for s in atribuir_costos_fifo(entradas, salidas) if s["tipo"] == "armado")
    assert sorted((c["origen_id"], c["bultos"]) for c in armado["consumos_lotes"]) == [(11, 7), (12, 1)]


def test_el_PASE_que_solo_le_CAMBIA_la_guia_al_armado_ENTRA(galpon):
    d, m, sql = galpon
    _con_clave(d)
    sql(COMPRA_12)
    pase = _cliente(m, "administracion").post("/administracion/retroactivo/pase-a-segunda", data={
        "articulo_id": "1", "que_pasa": "sueltos", "cantidad": "3", "motivo": "podrido",
        "fecha": "2026-09-08", "clave_especial": CLAVE, "quien": "Juan"}, follow_redirects=False)
    assert pase.status_code == 303, pase.text[-600:]
    assert sql("SELECT tipo, quien FROM retroactivos") == [("pase_a_segunda", "Juan")]


def test_la_DEVOLUCION_no_pasa_de_lo_que_QUEDA_de_su_compra_y_lo_que_queda_ENTRA(galpon):
    """En la devolución el control casi no tiene qué frenar: la pantalla ya no
    deja devolver más de lo que queda de esa compra contando todo lo que salió
    después. Con la compra 12, lo que queda de la 11 (2) entra y el armado
    sigue entero de la 11."""
    d, m, sql = galpon
    _con_clave(d)
    sql(COMPRA_12)
    adm = _cliente(m, "administracion")
    datos = {"proveedor_id": "1", "compra_id": "11", "motivo": "fea", "fecha": "2026-09-08",
             "clave_especial": CLAVE, "quien": "Marta"}
    assert "quedan 2 bultos" in adm.post("/administracion/retroactivo/devolver",
                                         data={**datos, "cantidad": "3"}).text
    assert adm.post("/administracion/retroactivo/devolver", data={**datos, "cantidad": "2"},
                    follow_redirects=False).status_code == 303
    assert sql("SELECT tipo FROM retroactivos") == [("devolucion",)]


def test_DESPUES_del_armado_solo_hay_lo_que_quedo(galpon):
    d, m, sql = galpon
    _con_clave(d)
    adm = _cliente(m, "administracion")
    assert "El 12/09 no había esa mercadería en el depósito." in _merma(adm, "2026-09-12", 3).text
    assert _merma(adm, "2026-09-12", 2).status_code == 303


def test_la_GUIA_R_que_la_tomo_tambien_frena_y_se_nombra(galpon):
    d, m, sql = galpon
    _con_clave(d)
    sql("""insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
               bultos_segunda, bultos_merma, costo_por_bulto_primera) overriding system value
           values (7, 1, '2026-09-11', 2, 2, 0, 0, 100)""")
    sql("insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos) values (7, 'compra', 11, 2)")
    texto = _merma(_cliente(m, "administracion"), "2026-09-08", 1).text
    assert "La guía R7 del 11/09 se queda sin mercadería." in texto


def test_FECHA_de_hoy_futura_o_sin_quien_no_es_retroactivo(galpon):
    d, m, sql = galpon
    _con_clave(d)
    adm = _cliente(m, "administracion")
    assert "fecha ANTERIOR a hoy" in _merma(adm, HOY.isoformat(), 1).text
    assert "fecha ANTERIOR a hoy" in _merma(adm, "2026-12-01", 1).text
    assert "Poné quién lo carga." in _merma(adm, "2026-09-08", 1, quien="  ").text
    assert _mermas(sql) == []


# --- los otros tres --------------------------------------------------------

def test_DEVOLUCION_y_PASE_con_fecha_anterior_tambien_frenan_y_registran(galpon):
    d, m, sql = galpon
    _con_clave(d)
    adm = _cliente(m, "administracion")
    datos = {"proveedor_id": "1", "compra_id": "11", "motivo": "fea", "fecha": "2026-09-08",
             "clave_especial": CLAVE, "quien": "Marta"}
    # Devolver 3: de la compra quedan 2 (el resto lo tomó el armado). Y el
    # 04/09 la compra todavía no había llegado.
    assert "quedan 2 bultos" in adm.post("/administracion/retroactivo/devolver",
                                         data={**datos, "cantidad": "3"}).text
    antes = adm.post("/administracion/retroactivo/devolver", data={**datos, "cantidad": "1", "fecha": "2026-09-04"})
    assert "El 04/09 no había esa mercadería en el depósito." in antes.text
    entra = adm.post("/administracion/retroactivo/devolver", data={**datos, "cantidad": "2"},
                     follow_redirects=False)
    assert entra.status_code == 303
    devuelta = sql("SELECT fecha_operacion, -cantidad, cargada_desde FROM movimientos_stock "
                   "WHERE tipo = 'devolucion_deposito'")
    assert devuelta == [(date(2026, 9, 8), 2, "administracion")]

    pase = adm.post("/administracion/retroactivo/pase-a-segunda", data={
        "articulo_id": "1", "que_pasa": "sueltos", "cantidad": "1", "motivo": "podrido",
        "fecha": "2026-09-08", "clave_especial": CLAVE, "quien": "Juan"}, follow_redirects=False)
    assert pase.status_code == 400
    assert "El armado del pedido de EJEMPLO Verduleria del 10/09 se queda sin mercadería." in pase.text
    assert sql("SELECT tipo, quien FROM retroactivos ORDER BY id") == [("devolucion", "Marta")]


def test_el_INGRESO_con_fecha_anterior_desde_Administracion_dice_quien_en_la_compra(galpon):
    d, m, sql = galpon
    _con_clave(d)
    adm = _cliente(m, "administracion")
    respuesta = adm.post("/administracion/retroactivo/ingreso", data={
        "proveedor_id": "1", "articulo_id": "1", "cantidad_cajones": "4", "contenido_por_cajon": "18",
        "importe": "90", "fecha_recepcion": "2026-09-15", "clave_especial": CLAVE, "quien": "Marta"},
        follow_redirects=False)
    assert respuesta.status_code == 303
    (compra_id,), = sql("SELECT compra_id FROM retroactivos WHERE tipo = 'ingreso'")
    assert sql("SELECT (procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date FROM compras "
               "WHERE id = %s", (compra_id,)) == [(date(2026, 9, 15),)]
    detalle = _cliente(m, "compras").get(f"/compras/{compra_id}/detalle").text
    assert "desde Administración → Con fecha anterior, por Marta" in detalle


# --- Depósito: solo con la fecha de hoy --------------------------------------

def test_DEPOSITO_ya_no_elige_fecha_y_si_la_manda_igual_va_HOY(galpon):
    d, m, sql = galpon
    deposito = _cliente(m)
    for ruta in ("/deposito/stock/merma?articulo_id=1", "/deposito/stock/pase-a-segunda?articulo_id=1"):
        marcado = deposito.get(ruta).text.split("</style>")[-1]
        assert 'name="fecha"' not in marcado and 'name="clave_especial"' not in marcado, ruta
    deposito.post("/deposito/stock/merma", data={
        "articulo_id": "1", "que_merma": "sueltos", "cantidad": "1", "motivo": "podrido",
        "fecha": "2026-09-08", "sin_foto_confirmado": "1"})
    assert _mermas(sql) == [(HOY, 1)]
    assert sql("SELECT count(*) FROM retroactivos")[0][0] == 0


# --- las pantallas -----------------------------------------------------------

def test_las_PANTALLAS_de_Administracion_piden_dia_quien_y_contrasena(galpon):
    d, m, sql = galpon
    adm = _cliente(m, "administracion")
    for ruta in ("/administracion/retroactivo/merma?articulo_id=1",
                 "/administracion/retroactivo/pase-a-segunda?articulo_id=1",
                 "/administracion/retroactivo/devolver?proveedor_id=1",
                 "/administracion/retroactivo/ingreso"):
        marcado = adm.get(ruta).text.split("<body>")[-1]
        for campo in ('name="quien"', 'type="password" id="clave_especial" name="clave_especial"'):
            assert marcado.count(campo) == 1, (ruta, campo)
        assert re.search(r'<form method="post"[^>]*action="/administracion/retroactivo/', marcado), ruta
    hub = adm.get("/administracion/retroactivo").text
    assert "Gerencia todavía no fijó la contraseña especial" in hub
    for ruta in ("ingreso", "devolver", "merma", "pase-a-segunda"):
        assert hub.count(f'href="/administracion/retroactivo/{ruta}"') == 1


def test_el_REGISTRO_dice_que_de_que_dia_quien_y_cuando(galpon):
    d, m, sql = galpon
    _con_clave(d)
    adm = _cliente(m, "administracion")
    _merma(adm, "2026-09-08", 2)
    texto = " ".join(re.sub(r"<[^>]+>", " ", adm.get("/administracion/retroactivo").text).split())
    assert "Merma del 08/09/2026 · EJEMPLO Pera · 2 bultos" in texto
    assert "Cargado por Marta el" in texto


def test_a_313px_las_pantallas_nuevas_no_desbordan(galpon):
    from tests.test_remitos import _que_se_sale
    d, m, sql = galpon
    adm, gerencia = _cliente(m, "administracion"), _cliente(m, "gerencia")
    paginas = {"hub": adm.get("/administracion/retroactivo").text,
               "merma": adm.get("/administracion/retroactivo/merma?articulo_id=1").text,
               "clave": gerencia.get("/gerencia/clave-retroactivo").text}
    for nombre, html in paginas.items():
        assert html.count("<form") + html.count('class="boton"') >= 1, nombre   # identidad
        medicion = _que_se_sale(html, 313)
        assert medicion["pagina"] == 0 and medicion["salidos"] == [], (nombre, medicion)


# --- la migración ------------------------------------------------------------

def _leer(nombre):
    return io.open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


def test_la_MIGRACION_crea_las_dos_tablas_y_no_corre_dos_veces(galpon):
    import psycopg2
    d, m, sql = galpon
    sql("DROP TABLE retroactivos; DROP TABLE claves_especiales;")
    sql(_leer("retroactivo_1_clave_y_registro.sql"))
    fila, = sql(_leer("retroactivo_1_verificacion.sql"))
    assert fila[:5] == ("retroactivo_1_clave_y_registro", 2, 1, 0, 0)
    with pytest.raises(psycopg2.Error, match="retroactivo_1 ya corrio"):
        sql(_leer("retroactivo_1_clave_y_registro.sql"))
    with pytest.raises(psycopg2.Error, match="retroactivos_a_que_apunta"):
        sql("INSERT INTO retroactivos (tipo, fecha_del_hecho, quien, compra_id) VALUES ('merma', '2026-09-08', 'X', 11)")


def test_los_bloques_entran_en_el_editor_y_el_codigo_va_arriba():
    for nombre in ("retroactivo_1_clave_y_registro.sql", "retroactivo_1_verificacion.sql"):
        texto = _leer(nombre)
        assert len(texto) <= 2500 and not texto.lstrip().startswith("--"), nombre
    assert _leer("retroactivo_1_verificacion.sql").lstrip().startswith(
        "select 'retroactivo_1_clave_y_registro' as que_migracion")


def test_ELIMINAR_la_compra_cargada_con_fecha_anterior_se_lleva_su_registro(galpon):
    d, m, sql = galpon
    sql("INSERT INTO retroactivos (tipo, fecha_del_hecho, quien, compra_id) VALUES ('ingreso', '2026-09-05', 'Marta', 11)")
    sql("DELETE FROM pedidos_renglones; DELETE FROM compras WHERE id = 11")
    assert sql("SELECT count(*) FROM retroactivos")[0][0] == 0
