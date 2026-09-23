"""Cambiar el proveedor de una compra desde Corregir Recepción (dueño, 23/09).

LOS CUATRO FRENOS son los lugares donde el proveedor viejo ya quedó escrito
en otro lado: una guía R consumió el lote, un vale de vacíos, una devolución
al proveedor, o la guía R en origen. Cada uno tiene su caso, y el caso que
TIENE QUE PASAR va al lado — sin él, una guarda que rebota siempre pasaría
los cuatro negativos (corolario 30).
"""
import ast
import io
import os
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


# ------------------------------------------------------------------ el código


def _llamadas_en(nombre):
    src = io.open(os.path.join(RAIZ, "app/db.py"), encoding="utf-8").read()
    for nodo in ast.walk(ast.parse(src)):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
            return {n.func.id for n in ast.walk(nodo)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    raise AssertionError(f"no existe {nombre}")


def test_la_PANTALLA_y_la_ESCRITURA_preguntan_por_LA_MISMA_funcion_de_frenos():
    """Una LLAMADA en el árbol y no el nombre en el texto: el docstring nombra
    la función para explicarla (corolario 59)."""
    for funcion in ("cambiar_proveedor_de_compra", "frenos_para_cambiar_proveedor"):
        assert "_frenos_para_cambiar_proveedor" in _llamadas_en(funcion), funcion


def test_los_frenos_reusan_los_helpers_que_YA_existen():
    llamadas = _llamadas_en("_frenos_para_cambiar_proveedor")
    assert {"_lote_de_la_compra_YA_SE_USO", "_guias_en_origen_vivas"} <= llamadas


def test_la_guia_se_muda_con_el_MISMO_helper_que_mover_la_fecha():
    assert "_guia_de_compra" in _llamadas_en("cambiar_proveedor_de_compra")


# --------------------------------------------------------- comportamiento


@pytest.fixture(scope="module")
def base_real():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def galpon(base_real, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", base_real)
    import app.db as d

    def sql(consulta, parametros=()):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()

    (n,), = sql("SELECT nextval(pg_get_serial_sequence('articulos','id'))")
    (art,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id", (f"EJEMPLO Art {n}",))
    (viejo,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s,%s) RETURNING id",
                    (f"EJEMPLO Viejo {n}", f"N02P{n % 100:02d}"))
    (nuevo,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s,%s) RETURNING id",
                    (f"EJEMPLO Nuevo {n}", f"N03P{n % 100:02d}"))

    def recepcionada():
        d.crear_compra(date.today(), art, viejo, 10, 16, 160, None, 50000, None,
                       "Clark", None, segunda_por_cajon=None)
        (cid,), = sql("SELECT max(id) FROM compras")
        sql("""UPDATE compras SET estado='recepcionado', cantidad_cajones_real=10,
               contenido_por_cajon_real=16, cantidad_kilos_real=160, procesada_el=now()
               WHERE id=%s""", (cid,))
        return cid

    return d, sql, recepcionada, art, viejo, nuevo


def _estado(sql, compra_id):
    fila, = sql("SELECT proveedor_id, guia_id FROM compras WHERE id=%s", (compra_id,))
    return fila


def test_sin_frenos_CAMBIA_el_proveedor_y_la_compra_pasa_a_la_GUIA_del_nuevo(galpon):
    """EL CASO QUE TIENE QUE PASAR."""
    d, sql, recepcionada, _, viejo, nuevo = galpon
    compra_id = recepcionada()
    _, guia_vieja = _estado(sql, compra_id)

    assert d.frenos_para_cambiar_proveedor(compra_id) == []
    d.cambiar_proveedor_de_compra(compra_id, nuevo)

    proveedor, guia = _estado(sql, compra_id)
    assert proveedor == nuevo
    assert guia != guia_vieja
    (proveedor_de_la_guia,), = sql("SELECT proveedor_id FROM guias_compra WHERE id=%s", (guia,))
    assert proveedor_de_la_guia == nuevo


def _rebota_sin_tocar(d, sql, compra_id, nuevo, palabra):
    antes = _estado(sql, compra_id)
    assert d.frenos_para_cambiar_proveedor(compra_id), "la pantalla ofrecería el botón"
    with pytest.raises(ValueError) as error:
        d.cambiar_proveedor_de_compra(compra_id, nuevo)
    assert palabra in str(error.value)
    assert _estado(sql, compra_id) == antes, "rebotó y además dejó algo escrito"


def test_FRENA_si_una_guia_R_CONSUMIO_el_lote(galpon):
    d, sql, recepcionada, art, _, nuevo = galpon
    compra_id = recepcionada()
    (rid,), = sql("""INSERT INTO reprocesos (articulo_id, fecha_operacion, bultos_tomados,
                     bultos_primera, bultos_segunda, bultos_merma, tipo)
                     VALUES (%s, current_date, 5, 5, 0, 0, 'normal') RETURNING id""", (art,))
    sql("""INSERT INTO reprocesos_consumos (reproceso_id, origen, compra_id, bultos)
           VALUES (%s,'compra',%s,5)""", (rid, compra_id))
    _rebota_sin_tocar(d, sql, compra_id, nuevo, "guía R tomó de su lote")

    # Y con la guía anulada vuelve a poder: el freno mira lo VIVO.
    sql("UPDATE reprocesos SET anulado_el = now() WHERE id=%s", (rid,))
    d.cambiar_proveedor_de_compra(compra_id, nuevo)
    assert _estado(sql, compra_id)[0] == nuevo


def test_FRENA_si_tiene_un_VALE_de_vacios(galpon):
    d, sql, recepcionada, _, viejo, nuevo = galpon
    compra_id = recepcionada()
    (vid,), = sql("""INSERT INTO vacios_deposito_devoluciones
                     (proveedor_id, compra_id, cantidad, stock_sistema)
                     VALUES (%s,%s,3,10) RETURNING id""", (viejo, compra_id))
    _rebota_sin_tocar(d, sql, compra_id, nuevo, "vale de vacíos")

    sql("UPDATE vacios_deposito_devoluciones SET anulado_el = now() WHERE id=%s", (vid,))
    assert d.frenos_para_cambiar_proveedor(compra_id) == []


def test_FRENA_si_tiene_una_DEVOLUCION_al_proveedor(galpon):
    d, sql, recepcionada, art, _, nuevo = galpon
    compra_id = recepcionada()
    (mid,), = sql("""INSERT INTO movimientos_stock
                     (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema,
                      destino_rechazo, compra_devolucion_id)
                     VALUES (%s,'reingreso_rechazo',2,'EJEMPLO rechazo',current_date,0,
                             'devolucion_proveedor',%s) RETURNING id""", (art, compra_id))
    _rebota_sin_tocar(d, sql, compra_id, nuevo, "devolución al proveedor")

    sql("UPDATE movimientos_stock SET anulado_el = now() WHERE id=%s", (mid,))
    assert d.frenos_para_cambiar_proveedor(compra_id) == []


def test_FRENA_si_genero_una_guia_R_EN_ORIGEN(galpon):
    d, sql, recepcionada, art, _, nuevo = galpon
    compra_id = recepcionada()
    (cliente,), = sql("INSERT INTO clientes (nombre) VALUES (%s) RETURNING id",
                      (f"EJEMPLO Cliente {compra_id}",))
    (ficha,), = sql("""INSERT INTO fichas_logistica (articulo_id, cliente_id, unidad_venta,
                       contenido_caja) VALUES (%s,%s,'kilo',6) RETURNING id""", (art, cliente))
    # 'en_origen' pide la ficha: una caja que llegó armada ya es de alguien.
    (rid,), = sql("""INSERT INTO reprocesos (articulo_id, fecha_operacion, bultos_tomados,
                     bultos_primera, bultos_segunda, bultos_merma, tipo, compra_origen_id,
                     ficha_id)
                     VALUES (%s, current_date, 5, 5, 0, 0, 'en_origen', %s, %s) RETURNING id""",
                  (art, compra_id, ficha))
    _rebota_sin_tocar(d, sql, compra_id, nuevo, f"R{rid}")


def test_el_MISMO_proveedor_y_uno_que_no_existe_rebotan(galpon):
    d, sql, recepcionada, _, viejo, _ = galpon
    compra_id = recepcionada()
    with pytest.raises(ValueError, match="ya es de ese proveedor"):
        d.cambiar_proveedor_de_compra(compra_id, viejo)
    with pytest.raises(ValueError, match="no existe"):
        d.cambiar_proveedor_de_compra(compra_id, 999_999_999)
    with pytest.raises(ValueError, match="no existe"):
        d.cambiar_proveedor_de_compra(999_999_999, viejo)


# -------------------------------------------------------------- la pantalla


PROVEEDORES = [
    {"id": 1, "nombre": "EJEMPLO Uno", "codigo_puesto": "N01P01"},
    {"id": 2, "nombre": "EJEMPLO Dos", "codigo_puesto": "N01P02"},
]
ACCION = 'action="/gerencia/compras/663/cambiar-proveedor"'


def _pantalla(**kw):
    from tests.test_cajas import _pantalla_corregir, NO_MARCADA
    return _pantalla_corregir(NO_MARCADA, **kw)


def test_el_SELECTOR_solo_aparece_donde_la_escritura_ACEPTA():
    """Los dos casos juntos: uno solo no distingue "ofrece cuando corresponde"
    de "ofrece siempre" ni de "no ofrece nunca". Sobre la respuesta ENTERA:
    esta pantalla incluye un partial con su propio <style> (corolario 50)."""
    libre = _pantalla(proveedores=PROVEEDORES)
    frenada = _pantalla(proveedores=PROVEEDORES,
                        frenos_proveedor=["tiene 1 vale de vacíos cargado"])

    assert libre.status_code == frenada.status_code == 200
    assert ACCION in libre.text
    assert ACCION not in frenada.text
    assert "tiene 1 vale de vacíos cargado" in frenada.text


def test_el_selector_NO_ofrece_el_proveedor_que_ya_tiene():
    """La compra de prueba es del proveedor 1: ofrecerlo sería un callejón,
    porque la escritura rechaza "ya es de ese proveedor"."""
    texto = _pantalla(proveedores=PROVEEDORES).text
    assert '<option value="1">' not in texto
    assert '<option value="2">EJEMPLO Dos (N01P02)</option>' in texto


def test_despues_de_cambiar_la_pantalla_lo_DICE():
    assert "el proveedor quedó cambiado" in _pantalla(url_extra="?proveedor_cambiado=1").text
    assert "el proveedor quedó cambiado" not in _pantalla().text


def _post(proveedor_id, *, con_clave=True, **parches):
    from fastapi.testclient import TestClient
    from app.main import app, _firma_acceso_gerencia
    from tests.test_cajas import _pantalla_corregir  # noqa: F401  (misma compra)
    compra = {"id": 663, "proveedor_id": 1, "proveedor_nombre": "Proveedor EJEMPLO",
              "proveedor_codigo_puesto": "N01P01", "articulo_nombre": "Pera EJEMPLO",
              "guia_id": 105, "guia_punto": 2, "estado": "recepcionado",
              "cantidad_cajones_real": 5.0, "contenido_por_cajon_real": 18.0,
              "cantidad_kilos_real": 90.0, "cantidad_cajones": 5.0,
              "contenido_por_cajon": 18.0, "cantidad_kilos": 90.0,
              "cantidad_fraccion": None, "cantidad_fraccion_real": None,
              "unidad_compra": "kilo", "unidad_conteo": None,
              "cantidad_cajones_rechazada": None, "motivo_rechazo": None,
              "importe": 40000.0, "articulo_id": 1}
    cliente = TestClient(app)
    with (
        patch.dict(os.environ, {"CLAVE_GERENCIA": "secreta"}),
        patch("app.main.cambiar_proveedor_de_compra", **parches) as cambiar,
        patch("app.main.obtener_detalle_compra", return_value=compra),
        patch("app.main.uso_del_lote_de_la_compra", return_value={"guias": 0, "armados": 0}),
        patch("app.main.frenos_para_cambiar_proveedor", return_value=[]),
        patch("app.main.listar_proveedores", return_value=[]),
        patch("app.main._dependencias_con_nombres", return_value=None),
        patch("app.main._fotos_de_la_guia_de", return_value=[]),
        patch("app.main.listar_fotos_de_recepcion", return_value=[]),
        patch("app.main.marca_en_origen_de_la_compra", return_value=None),
    ):
        if con_clave:
            cliente.cookies.set("acceso_gerencia", _firma_acceso_gerencia("secreta"))
        respuesta = cliente.post("/gerencia/compras/663/cambiar-proveedor",
                                 data={"proveedor_id": proveedor_id}, follow_redirects=False)
    return respuesta, cambiar


def test_el_POST_sin_la_clave_de_GERENCIA_no_escribe_y_la_PIDE():
    """Afirma lo que SÍ pasa —se pide la clave— y no un `!= 303`, que lo
    satisface también un 500 (corolario 91)."""
    respuesta, cambiar = _post("2", con_clave=False)
    cambiar.assert_not_called()
    assert "clave" in respuesta.text.lower()
    assert respuesta.status_code in (401, 403)


def test_el_POST_cambia_y_vuelve_a_la_pantalla_con_el_aviso():
    respuesta, cambiar = _post("2")
    cambiar.assert_called_once_with(663, 2)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].endswith("corregir-recepcion?proveedor_cambiado=1")


def test_un_FRENO_vuelve_como_400_con_el_motivo_en_la_pantalla():
    respuesta, _ = _post("2", side_effect=ValueError(
        "No se puede cambiar el proveedor: esta compra EJEMPLO."))
    assert respuesta.status_code == 400
    assert "No se puede cambiar el proveedor: esta compra EJEMPLO." in respuesta.text


def test_sin_elegir_proveedor_rebota_SIN_escribir():
    respuesta, cambiar = _post("")
    cambiar.assert_not_called()
    assert respuesta.status_code == 400
    assert "Elegí el proveedor nuevo." in respuesta.text
