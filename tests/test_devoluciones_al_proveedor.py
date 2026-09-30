"""Devoluciones de mercadería al proveedor (dueño, 30/09), contra Postgres.

Dos caminos, cada uno registrado por separado:

  · POR RECHAZO: lo que Día rechazó y se le devuelve al proveedor. Pide la
    compra, y cancela el costo al costo por bulto de ESA compra cuando lo que
    volvió iba en su cajón.
  · DESDE DEPÓSITO: lo que queda en el piso. Sale del lote de SU compra y de
    ningún otro, y nunca más de lo que queda.

En los dos, si la compra dejó seña, sus cajones vuelven llenos y salen de
Vacíos; y los dos aparecen en Movimientos del depósito.

Con la base mockeada el reparto lo decide el fixture, así que esto corre
contra el esquema real (corolario 89). Los nombres son de EJEMPLO.

EL GALPÓN QUE SE PLANTA, con el RIVAL puesto (corolario 11: el lote que no
tiene que ganar):

  compra 11  EJ Uno  05/09  10 cajones a $100, CON seña     <- la más vieja
  compra 12  EJ Uno  06/09   8 cajones a $120, sin seña
  compra 13  EJ Dos  07/09   5 cajones a $90

Una devolución de la 12 tiene que salir de la 12 aunque la 11 sea más vieja:
el FIFO puro la mandaría a la 11, que es exactamente lo que no pasó.
"""
import os
import re
import urllib.parse
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Dia');
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Fruta');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJ Uno', 'N91P01'), (2, 'EJ Dos', 'N91P02');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja Dia');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 16, 'kilo', null), (2, 1, 1, 6, 'kilo', 1);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, sena, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value values
  (11, 1, 1, '2026-09-05', 10, 16, 160, 100, 500, 'recepcionado', '2026-09-05 18:00-03', 10, 16),
  (12, 1, 1, '2026-09-06',  8, 16, 128, 120, null, 'recepcionado', '2026-09-06 18:00-03',  8, 16),
  (13, 2, 1, '2026-09-07',  5, 16,  80,  90, null, 'recepcionado', '2026-09-07 18:00-03',  5, 16);
insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 1, '2026-09-08', 'texto');
-- Un renglón SIN caja nuestra (ficha 1) y otro EN CAJA DE DÍA (ficha 2).
insert into pedidos_renglones (id, pedido_id, articulo_id, ficha_id, sucursal, cantidad,
                               cantidad_armada, armado_el, kilos_enviados)
  overriding system value values
  (1, 1, 1, 1, 'EJ Suc', 4, 4, '2026-09-08 10:00-03', 64),
  (2, 1, 1, 2, 'EJ Suc', 4, 4, '2026-09-08 10:00-03', 24);
"""


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: las devoluciones no se verificaron")
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

    def rechazo(renglon_id, cantidad, compra_id=None, proveedor_id=None, costo=77):
        sql("""INSERT INTO movimientos_stock (articulo_id, tipo, cantidad, motivo, cliente_id,
                   fecha_operacion, stock_sistema, pedido_renglon_id, costo_por_bulto,
                   destino_rechazo, compra_devolucion_id, proveedor_devolucion_id)
               VALUES (1, 'reingreso_rechazo', %s, 'EJ rechazo', 1, '2026-09-09', 0, %s, %s,
                       'devolucion_proveedor', %s, %s)""",
            (cantidad, renglon_id, costo, compra_id, proveedor_id))
    return d, sql, rechazo


def _lotes(d):
    """{compra_id: restante} del reparto de ahora, y lo que quedó sin lote."""
    from core.stock import repartir_fifo, salidas_para_reparto
    entradas, salidas = d.entradas_y_salidas_stock_articulo(1)
    reparto = repartir_fifo(entradas, salidas_para_reparto(salidas))
    restos = {l["origen_id"]: l["restante"] for l in reparto["lotes"] if l["tipo_lote"] == "guia"}
    return restos, reparto["sin_lote"]


def _pila(d, proveedor_id):
    return next((p["stock"] for p in d.stock_de_vacios_deposito() if p["id"] == proveedor_id), 0)


# --- desde depósito: sale de SU compra --------------------------------------

def test_la_devolucion_desde_deposito_sale_de_SU_compra_y_no_de_la_mas_vieja(base):
    d, sql, _ = base
    antes, sin_lote_antes = _lotes(d)
    stock_antes = d.stock_deposito_de_articulo(1)
    d.crear_devolucion_deposito(12, 3, "EJ se puso fea", date(2026, 9, 10))
    despues, sin_lote = _lotes(d)
    # El armado en cajón consumió la 11 (FIFO); la devolución sale de la 12.
    # El de caja de Día ya estaba sin lote (espera su guía R): no se mueve.
    assert despues[12] == antes[12] - 3
    assert despues[11] == antes[11], "la compra más vieja no se toca"
    assert sin_lote == sin_lote_antes
    assert d.stock_deposito_de_articulo(1) == stock_antes - 3


def test_lo_que_su_compra_no_cubre_queda_SIN_LOTE_y_no_sale_de_otra(base):
    """La guarda de "no más de lo que queda" está en la ruta; si igual llega
    de más (un día cargado tarde), el sobrante queda a la vista sin lote en vez
    de llevarse mercadería de otra compra."""
    d, sql, _ = base
    antes, sin_lote_antes = _lotes(d)
    d.crear_devolucion_deposito(13, 7, "EJ de más", date(2026, 9, 10))
    despues, sin_lote = _lotes(d)
    assert despues.get(13, 0) == 0
    assert despues[11] == antes[11] and despues[12] == antes[12]
    assert sin_lote == sin_lote_antes + 2


def test_la_devolucion_lleva_sus_FOTOS_a_las_de_la_compra(base):
    d, sql, _ = base
    d.crear_devolucion_deposito(12, 1, "EJ", date(2026, 9, 10), fotos_pesada=["pesaje/x/a.jpg"])
    assert [f["foto_ruta"] for f in d.listar_fotos_de_recepcion(12)] == ["pesaje/x/a.jpg"]


def test_una_compra_que_NO_esta_recibida_no_se_puede_devolver(base):
    d, sql, _ = base
    sql("UPDATE compras SET estado = 'pendiente' WHERE id = 13")
    with pytest.raises(ValueError, match="no está recibida"):
        d.crear_devolucion_deposito(13, 1, "EJ", date(2026, 9, 10))
    assert sql("SELECT count(*) FROM movimientos_stock")[0][0] == 0


# --- vacíos: los cajones que vuelven llenos -----------------------------------

def test_con_SENA_los_cajones_que_vuelven_llenos_salen_de_Vacios(base):
    d, sql, rechazo = base
    assert _pila(d, 1) == 10, "la compra 11 dejó seña por 10 cajones"
    d.crear_devolucion_deposito(11, 3, "EJ", date(2026, 9, 10))
    assert _pila(d, 1) == 7
    # Sin seña (la 12) no hay cajón que devolver.
    d.crear_devolucion_deposito(12, 2, "EJ", date(2026, 9, 10))
    assert _pila(d, 1) == 7


def test_el_RECHAZO_en_cajon_resta_y_el_que_iba_en_CAJA_DE_DIA_no(base):
    d, sql, rechazo = base
    rechazo(1, 2, compra_id=11)        # ficha sin caja nuestra: vuelve el cajón
    assert _pila(d, 1) == 8
    rechazo(2, 2, compra_id=11)        # iba en caja de Día: su cajón quedó en el galpón
    assert _pila(d, 1) == 8
    rechazo(1, 1, proveedor_id=1)      # los viejos, sin compra: no se sabe la marca
    assert _pila(d, 1) == 8


def test_la_LISTA_de_vacios_y_la_PILA_dicen_lo_mismo_con_las_devoluciones(base):
    d, sql, rechazo = base
    d.crear_devolucion_deposito(11, 3, "EJ", date(2026, 9, 10))
    rechazo(1, 2, compra_id=11)
    movimientos = [m for m in d.movimientos_de_vacios(1, limite=1000) if not m["anulada"]]
    llenas = [m["cantidad"] for m in movimientos if m["tipo"] == "devolucion_llena"]
    assert sorted(llenas) == [-3, -2]
    assert sum(int(m["cantidad"]) for m in movimientos) == _pila(d, 1)


# --- el costo en la Rentabilidad Real ------------------------------------------

def test_el_RECHAZO_con_compra_cancela_al_costo_de_la_compra_si_iba_en_su_cajon(base):
    d, sql, rechazo = base
    rechazo(1, 2, compra_id=12)        # cajón: $120 de la compra 12
    rechazo(2, 2, compra_id=12)        # caja de Día: queda el congelado
    rechazo(1, 1, proveedor_id=1)      # viejo, sin compra: el congelado
    filas = d.devoluciones_vinculadas_por_rango(1, date(2026, 9, 1), date(2026, 9, 30))
    def clave(par):
        return (par[0], -1 if par[1] is None else float(par[1]))
    assert sorted(((f["ficha_id"], f["costo_bulto_compra"]) for f in filas), key=clave) == sorted(
        [(1, 120), (2, None), (1, None)], key=clave)


def test_la_Rentabilidad_usa_el_costo_de_la_compra_y_si_no_el_congelado():
    from core.costo_real import calcular_rentabilidad_real
    import inspect
    fuente = inspect.getsource(calcular_rentabilidad_real)
    assert 'costo = _numero(devolucion.get("costo_bulto_compra")) or costo' in fuente


# --- Movimientos del depósito --------------------------------------------------

def test_MOVIMIENTOS_del_deposito_trae_entradas_devoluciones_y_segunda(base):
    d, sql, rechazo = base
    d.crear_devolucion_deposito(12, 3, "EJ se puso fea", date(2026, 9, 10))
    rechazo(1, 2, compra_id=11)
    sql("INSERT INTO remitos_segunda (articulo_id, bultos, fecha_operacion) VALUES (1, 4, '2026-09-11')")
    sql("INSERT INTO remitos_segunda (articulo_id, bultos, fecha_operacion, anulado_el) "
        "VALUES (1, 9, '2026-09-11', now())")
    filas = d.movimientos_del_deposito(date(2026, 9, 1), date(2026, 9, 30))
    resumen = [(m["tipo"], m["proveedor"], m["compra_id"], m["bultos"], m["valor"]) for m in filas]
    assert resumen == [
        ("entrada", "EJ Dos", 13, 5.0, 450.0),
        ("entrada", "EJ Uno", 11, 10.0, 1000.0),
        ("entrada", "EJ Uno", 12, 8.0, 960.0),
        ("rechazo", "EJ Uno", 11, -2.0, -200.0),
        ("deposito", "EJ Uno", 12, -3.0, -360.0),
        ("segunda", None, None, -4.0, None),
    ]
    # Los filtros.
    assert {m["tipo"] for m in d.movimientos_del_deposito(
        date(2026, 9, 1), date(2026, 9, 30), tipo="deposito")} == {"deposito"}
    por_proveedor = d.movimientos_del_deposito(date(2026, 9, 1), date(2026, 9, 30), proveedor_id=2)
    assert [m["compra_id"] for m in por_proveedor] == [13]
    assert d.movimientos_del_deposito(date(2026, 9, 8), date(2026, 9, 9), tipo="entrada") == []


def test_la_CUENTA_de_un_proveedor_cierra_como_la_dice_el_duenio(base):
    """"El 01 entraron 50; el 02 salieron 10 por rechazo y 40 desde depósito."""
    from core.movimientos_deposito import agrupar
    d, sql, rechazo = base
    rechazo(1, 2, compra_id=11)
    d.crear_devolucion_deposito(12, 3, "EJ", date(2026, 9, 10))
    grupos = agrupar(d.movimientos_del_deposito(date(2026, 9, 1), date(2026, 9, 30), proveedor_id=1))
    uno, = grupos
    assert (uno["entraron"], uno["salieron"], uno["neto"]) == (18, 5, 13)
    assert (uno["valor_entrado"], uno["valor_salido"]) == (1960, 560)


# --- las RUTAS, contra la misma base -------------------------------------------
# El tope de "lo que queda" se calcula en la ruta con el reparto de ahora. Con
# la base mockeada ese número lo pondría el fixture, así que va contra Postgres.

HOY = date(2026, 9, 10)


def _cliente():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app, base_url="https://testserver")


def test_la_pantalla_de_DEVOLVER_ofrece_solo_las_compras_con_lo_que_QUEDA(base):
    from unittest.mock import patch
    d, sql, _ = base
    with patch("app.main._hoy_argentina", return_value=HOY):
        respuesta = _cliente().get("/deposito/devolver?proveedor_id=1")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    # La 11 la consumió el armado en cajón (4 de 10: quedan 6); la 12 entera.
    assert re.search(r'value="11"[^>]*>.*?quedan <span class="resto">6</span> de 10', marcado, re.S)
    assert re.search(r'value="12"[^>]*>.*?quedan <span class="resto">8</span> de 8', marcado, re.S)
    # La 13 es de OTRO proveedor.
    assert 'value="13"' not in marcado


def test_DEVOLVER_mas_de_lo_que_queda_rebota_y_NO_escribe(base):
    from unittest.mock import patch
    d, sql, _ = base
    with patch("app.main._hoy_argentina", return_value=HOY):
        respuesta = _cliente().post("/deposito/devolver", data={
            "proveedor_id": "1", "compra_id": "11", "cantidad": "7", "motivo": "EJ fea"},
            follow_redirects=False)
    assert respuesta.status_code == 400
    assert "quedan 6 bultos" in respuesta.text
    assert sql("SELECT count(*) FROM movimientos_stock WHERE tipo = 'devolucion_deposito'") == [(0,)]


@pytest.mark.parametrize("datos, error", [
    ({"proveedor_id": "1", "compra_id": "13", "cantidad": "1", "motivo": "EJ"}, "Elegí de qué compra"),
    ({"proveedor_id": "1", "compra_id": "12", "cantidad": "1", "motivo": "  "}, "El motivo es obligatorio"),
    ({"proveedor_id": "1", "compra_id": "12", "cantidad": "0", "motivo": "EJ"}, ""),
])
def test_DEVOLVER_una_compra_AJENA_sin_motivo_o_en_cero_rebota(base, datos, error):
    from unittest.mock import patch
    d, sql, _ = base
    with patch("app.main._hoy_argentina", return_value=HOY):
        respuesta = _cliente().post("/deposito/devolver", data=datos, follow_redirects=False)
    assert respuesta.status_code == 400
    assert error in respuesta.text
    assert sql("SELECT count(*) FROM movimientos_stock WHERE tipo = 'devolucion_deposito'") == [(0,)]


def test_DEVOLVER_lo_que_queda_guarda_con_su_FOTO_y_avisa_la_sena(base):
    import io
    from unittest.mock import patch
    from PIL import Image
    d, sql, _ = base
    jpeg = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 100, 50)).save(jpeg, format="JPEG")
    with patch("app.main._hoy_argentina", return_value=HOY), \
         patch("app.main.subir_foto_comanda", return_value="pesaje/2026-09-10/ej.jpg") as subir:
        respuesta = _cliente().post(
            "/deposito/devolver",
            data={"proveedor_id": "1", "compra_id": "11", "cantidad": "6", "motivo": "EJ fea"},
            files=[("fotos", ("a.jpg", jpeg.getvalue(), "image/jpeg"))],
            follow_redirects=False)
    assert respuesta.status_code == 303, respuesta.text[-400:]
    assert subir.call_count == 1
    assert "esos cajones salen de Vacíos" in urllib.parse.unquote_plus(respuesta.headers["location"])
    assert sql("""SELECT compra_devolucion_id, cantidad, motivo, fecha_operacion FROM movimientos_stock
                  WHERE tipo = 'devolucion_deposito'""") == [(11, -6, "EJ fea", HOY)]
    assert sql("SELECT foto_ruta FROM fotos_recepcion WHERE compra_id = 11") == [("pesaje/2026-09-10/ej.jpg",)]


def test_MOVIMIENTOS_en_la_pantalla_y_el_EXCEL_de_Administracion(base, monkeypatch):
    import io
    import openpyxl
    from unittest.mock import patch
    from app.main import PUERTA_ADMINISTRACION
    d, sql, rechazo = base
    d.crear_devolucion_deposito(12, 3, "EJ se puso fea", date(2026, 9, 10))
    monkeypatch.setenv("CLAVE_ADMINISTRACION", "admin-secreta")
    cliente = _cliente()
    cliente.cookies.set(PUERTA_ADMINISTRACION.cookie, PUERTA_ADMINISTRACION.firma("admin-secreta"))
    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 12)):
        pantalla = cliente.get("/administracion/ingresos?proveedor_id=1")
        excel = cliente.get("/administracion/ingresos/movimientos-excel?proveedor_id=1&tipo=deposito")
    assert pantalla.status_code == 200
    marcado = pantalla.text.split("</style>")[-1]
    assert "Entraron 18 · se devolvieron 3 · neto 15 bultos" in marcado
    assert marcado.count('<div class="fila">') == 3
    assert "Devolución desde depósito · EJEMPLO Fruta" in marcado
    assert 'href="/administracion/ingresos/pagar?' in marcado
    assert excel.status_code == 200
    hoja = openpyxl.load_workbook(io.BytesIO(excel.content)).active
    filas = [tuple(c.value for c in fila) for fila in hoja.iter_rows(min_row=5)]
    assert filas == [("10/09/2026", "Devolución desde depósito", "EJ Uno", 12, "EJEMPLO Fruta",
                      -3, -360, "EJ se puso fea", None, None)]


def test_MOVIMIENTOS_dicen_que_ENTRO_con_sena_y_VOLVIO_con_sena(base, monkeypatch):
    """Dueño, 30/09: la devolución de mercadería con seña no genera un vale,
    pero Movimientos tiene que mostrar los cajones y la seña en la entrada y
    en la devolución. En un rechazo, solo si iba en el cajón."""
    import io
    import openpyxl
    from unittest.mock import patch
    from app.main import PUERTA_ADMINISTRACION
    d, sql, rechazo = base
    d.crear_devolucion_deposito(11, 2, "EJ se puso fea", date(2026, 9, 10))
    rechazo(1, 1, compra_id=11)          # iba en el cajón: vuelve con seña
    rechazo(2, 1, compra_id=11)          # iba en caja de Día: no
    movs = {(m["tipo"], m["bultos"], m["sena"]) for m in d.movimientos_del_deposito(
        date(2026, 9, 1), date(2026, 9, 30), proveedor_id=1)
        if m["compra_id"] == 11}
    assert movs == {("entrada", 10.0, 500.0), ("deposito", -2.0, 500.0),
                    ("rechazo", -1.0, 500.0), ("rechazo", -1.0, None)}
    # Nada de esto crea un vale.
    assert sql("SELECT count(*) FROM vales_a_cobrar") == [(0,)]
    monkeypatch.setenv("CLAVE_ADMINISTRACION", "admin-secreta")
    cliente = _cliente()
    cliente.cookies.set(PUERTA_ADMINISTRACION.cookie, PUERTA_ADMINISTRACION.firma("admin-secreta"))
    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 12)):
        pantalla = cliente.get("/administracion/ingresos?proveedor_id=1")
        excel = cliente.get("/administracion/ingresos/movimientos-excel?proveedor_id=1&tipo=deposito")
    marcado = pantalla.text.split("</style>")[-1]
    assert "entró con seña: 10 cajones × $500" in marcado
    assert "volvió con seña: 2 cajones × $500" in marcado
    assert marcado.count("con seña:") == 3
    hoja = openpyxl.load_workbook(io.BytesIO(excel.content)).active
    filas = [tuple(c.value for c in fila) for fila in hoja.iter_rows(min_row=5)]
    assert [f[8:] for f in filas] == [(500, "volvió con seña: 2 cajones × $500")]
