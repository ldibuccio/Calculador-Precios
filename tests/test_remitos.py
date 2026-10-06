"""REMITOS Y FACTURACIÓN (dueño, 01/10), contra Postgres.

Un remito por ORDEN DE COMPRA (pedidos_sucursales). Se emite con el número
del remito oficial y congela lo que salió; vuelve en ESE MISMO remito con los
bultos y kilos que firmó el súper y la foto; se le anota la factura. NO SE
ANULA: Gerencia solo corrige el número, con registro. El remito no mueve
stock: enviados − recibidos se coteja contra los rechazos de Depósito. Corre contra el esquema real (corolario 89): los índices únicos y
los CHECK son la mitad de la regla. Los nombres son de EJEMPLO.

  cliente 1 EJ Súper   pedido 1 (05/09): VL renglones 11 y 12 armados, 14 sin armar;
                                         BZ renglón 13 armado (BZ SIN fila de orden)
                       pedido 3 (06/09): VL renglón 31 armado SIN kilos
                       pedido 4 (05/09): reemplazado por el 1 (más viejo)
  cliente 2 EJ Otro    pedido 2 (05/09): VL renglón 21 armado
  precios de la ficha 1: $90 desde 01/08, $100 desde 01/09, $120 desde 10/09
"""
import re
import os
import sys
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJ Súper'), (2, 'EJ Otro');
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Fruta'), (2, 'EJEMPLO Verdura');
insert into fichas_logistica (id, articulo_id, cliente_id, unidad_venta, contenido_caja) overriding system value
  values (1, 1, 1, 'kilo', 10), (2, 2, 1, 'kilo', 10), (3, 1, 2, 'kilo', 10);
insert into precios_venta_historial (articulo_id, cliente_id, ficha_id, precio, vigente_desde) values
  (1, 1, 1, 90, '2026-08-01'), (1, 1, 1, 100, '2026-09-01'), (1, 1, 1, 120, '2026-09-10'),
  (2, 1, 2, 50, '2026-09-01'), (1, 2, 3, 70, '2026-09-01');
insert into pedidos (id, cliente_id, fecha_operacion, origen, creado_en) overriding system value values
  (1, 1, '2026-09-05', 'mail', '2026-09-05 10:00-03'),
  (2, 2, '2026-09-05', 'mail', '2026-09-05 10:00-03'),
  (3, 1, '2026-09-06', 'mail', '2026-09-06 10:00-03'),
  (4, 1, '2026-09-05', 'mail', '2026-09-05 08:00-03');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad, cantidad_armada,
                               armado_el, kilos_enviados) overriding system value values
  (11, 1, 'VL', 1, 1, 5, 5, '2026-09-05 12:00-03', 50),
  (12, 1, 'VL', 2, 2, 3, 3, '2026-09-05 12:00-03', 30),
  (13, 1, 'BZ', 1, 1, 2, 2, '2026-09-05 12:00-03', 20),
  (14, 1, 'VL', 2, 2, 4, null, null, null),
  (21, 2, 'VL', 1, 3, 4, 4, '2026-09-05 12:00-03', 40),
  (31, 3, 'VL', 1, 1, 1, 1, '2026-09-06 12:00-03', null),
  (41, 4, 'VL', 1, 1, 1, 1, '2026-09-05 12:00-03', 10);
-- Sin ids a mano: emitir crea filas por la identidad (ids 1 a 4, en orden).
insert into pedidos_sucursales (pedido_id, sucursal, orden_compra) values
  (1, 'VL', 'OC-EJ-1'), (2, 'VL', 'OC-EJ-2'), (3, 'VL', null), (4, 'VL', null);
"""

ARG = timezone(timedelta(hours=-3))
HOY = date(2026, 12, 1)       # lejos de la fecha real (corolario 95)


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: los remitos no se verificaron")
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


def _cliente(monkeypatch, *sectores):
    from fastapi.testclient import TestClient
    from app.main import PUERTA_ADMINISTRACION, PUERTA_COMPRAS, PUERTA_GERENCIA, app
    cliente = TestClient(app, base_url="https://testserver")
    for puerta in (PUERTA_ADMINISTRACION, PUERTA_GERENCIA, PUERTA_COMPRAS):
        if puerta.sector in sectores:
            monkeypatch.setenv(puerta.env_var, f"clave-{puerta.sector}")
            cliente.cookies.set(puerta.cookie, puerta.firma(f"clave-{puerta.sector}"))
    return cliente


def _marcado(respuesta):
    return respuesta.text.split("</style>")[-1]


def _jpeg():
    import io
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color="red").save(buffer, format="JPEG")
    return buffer.getvalue()


def _rechazo_de_deposito(sql, renglon_id, bultos, anulado=False):
    """Un reingreso de rechazo cargado por Depósito contra el renglón."""
    sql("""INSERT INTO movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema,
                                          pedido_renglon_id, destino_rechazo, costo_por_bulto, anulado_el)
           SELECT articulo_id, 'reingreso_rechazo', %s, 'EJ', '2026-09-06', 0, id, 'stock', 10,
                  CASE WHEN %s THEN now() END
             FROM pedidos_renglones WHERE id = %s""", (bultos, anulado, renglon_id))


def _recibido(d, remito_id, kilos=None, bultos=None):
    """Recibe el remito: por renglón, (bultos, kilos) recibidos. Lo que no se
    nombra vuelve igual a lo enviado."""
    renglones = d.remito_por_id(remito_id)["renglones"]
    recepcion = {r["id"]: ((bultos or {}).get(r["pedido_renglon_id"], float(r["bultos_enviados"])),
                           (kilos or {}).get(r["pedido_renglon_id"], float(r["kilos_enviados"])))
                 for r in renglones}
    d.recibir_remito(remito_id, recepcion, ["remitos/EJ.jpg"])


# --- 1. emitir ----------------------------------------------------------------

def test_EMITIR_congela_lo_armado_de_ESA_orden_y_nada_mas(base):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "  R-0001 ")
    filas = sql("SELECT pedido_renglon_id, bultos_enviados, kilos_enviados FROM remitos_renglones "
                "WHERE remito_id = %s ORDER BY 1", (remito_id,))
    # El 14 no está armado y el 13 es de otra sucursal: no entran.
    assert [(r, float(b), float(k)) for r, b, k in filas] == [(11, 5.0, 50.0), (12, 3.0, 30.0)]
    assert sql("SELECT numero, cliente_id, pedido_sucursal_id FROM remitos") == [("R-0001", 1, 1)]
    # Congelado: corregir el armado después no mueve el remito.
    sql("UPDATE pedidos_renglones SET kilos_enviados = 99 WHERE id = 11")
    assert float(sql("SELECT kilos_enviados FROM remitos_renglones WHERE pedido_renglon_id = 11")[0][0]) == 50.0


def test_una_orden_SIN_fila_de_pedidos_sucursales_la_crea_al_emitir(base):
    d, sql = base
    assert sql("SELECT count(*) FROM pedidos_sucursales WHERE pedido_id = 1 AND sucursal = 'BZ'") == [(0,)]
    d.emitir_remito(1, "BZ", "R-BZ")
    assert sql("SELECT count(*) FROM pedidos_sucursales WHERE pedido_id = 1 AND sucursal = 'BZ'") == [(1,)]


def test_el_NUMERO_es_unico_POR_CLIENTE_y_lo_decide_la_base(base):
    d, sql = base
    from app.db import RemitoNoSePuede
    d.emitir_remito(1, "VL", "R-0001")
    with pytest.raises(RemitoNoSePuede, match="ya está cargado para EJ Súper"):
        d.emitir_remito(1, "BZ", "r-0001 ")          # mismo número plegado, mismo cliente
    d.emitir_remito(2, "VL", "R-0001")                # otro cliente: entra
    assert sql("SELECT count(*) FROM remitos") == [(2,)]


def test_UNA_orden_tiene_UN_remito(base):
    d, sql = base
    from app.db import RemitoNoSePuede
    d.emitir_remito(1, "VL", "R-0001")
    with pytest.raises(RemitoNoSePuede, match="ya tiene su remito"):
        d.emitir_remito(1, "VL", "R-0002")


def test_sin_KILOS_ENVIADOS_no_se_emite_y_dice_cual(base):
    d, sql = base
    from app.db import RemitoNoSePuede
    with pytest.raises(RemitoNoSePuede, match="Faltan los kilos enviados de EJEMPLO Fruta"):
        d.emitir_remito(3, "VL", "R-0003")
    assert sql("SELECT count(*) FROM remitos") == [(0,)]


def test_un_pedido_REEMPLAZADO_no_se_remite(base):
    d, sql = base
    from app.db import RemitoNoSePuede
    with pytest.raises(RemitoNoSePuede, match="reemplazado"):
        d.emitir_remito(4, "VL", "R-0004")


def test_sin_numero_no_se_emite(base):
    d, sql = base
    from app.db import RemitoNoSePuede
    with pytest.raises(RemitoNoSePuede, match="obligatorio"):
        d.emitir_remito(1, "VL", "   ")


# --- 2. recibir y el cotejo ---------------------------------------------------

def test_RECIBIR_guarda_en_el_MISMO_remito_bultos_y_kilos_y_NO_mueve_stock(base):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    movimientos = sql("SELECT count(*) FROM movimientos_stock")
    # El 11: de 5 se quedó 4 y menos kilos. El 12: todo, con menos kilos por cajón.
    _recibido(d, remito_id, bultos={11: 4}, kilos={11: 38, 12: 27})
    remito = d.remito_por_id(remito_id)
    assert remito["recibido_el"] is not None
    assert sql("SELECT count(*) FROM remitos") == [(1,)]                 # el mismo remito
    assert {r["pedido_renglon_id"]: (float(r["bultos_enviados"]), float(r["kilos_enviados"]),
                                     float(r["bultos_recibidos"]), float(r["kilos_recibidos"]))
            for r in remito["renglones"]} == {11: (5.0, 50.0, 4.0, 38.0), 12: (3.0, 30.0, 3.0, 27.0)}
    assert [f["ruta"] for f in remito["fotos"]] == ["remitos/EJ.jpg"]
    assert sql("SELECT count(*) FROM movimientos_stock") == movimientos


def test_QUE_RENGLONES_CAMBIARON_sale_de_enviado_contra_recibido():
    from core.remitos import rechazo_del_remito, renglon_cambio
    enviado = {"bultos_enviados": 10, "kilos_enviados": 100}
    assert not renglon_cambio({**enviado, "bultos_recibidos": None, "kilos_recibidos": None})
    assert not renglon_cambio({**enviado, "bultos_recibidos": 10, "kilos_recibidos": 100})
    assert renglon_cambio({**enviado, "bultos_recibidos": 8, "kilos_recibidos": 80})      # rechazó 2
    assert renglon_cambio({**enviado, "bultos_recibidos": 10, "kilos_recibidos": 95})     # menos kilos
    assert rechazo_del_remito({**enviado, "bultos_recibidos": 8, "kilos_recibidos": 80}) == 2.0
    assert rechazo_del_remito({**enviado, "bultos_recibidos": None, "kilos_recibidos": None}) is None


def test_RECIBIR_pide_foto_todos_los_renglones_y_una_sola_vez(base):
    d, sql = base
    from app.db import RemitoNoSePuede
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    ids = [r["id"] for r in d.remito_por_id(remito_id)["renglones"]]
    with pytest.raises(RemitoNoSePuede, match="foto"):
        d.recibir_remito(remito_id, {i: (1, 1) for i in ids}, [])
    with pytest.raises(RemitoNoSePuede, match="Falta cargar"):
        d.recibir_remito(remito_id, {ids[0]: (1, 1)}, ["remitos/EJ.jpg"])
    d.recibir_remito(remito_id, {i: (1, 1) for i in ids}, ["remitos/EJ.jpg"])
    with pytest.raises(RemitoNoSePuede, match="ya se recibió"):
        d.recibir_remito(remito_id, {i: (1, 1) for i in ids}, ["remitos/EJ.jpg"])


def test_los_RECIBIDOS_no_pasan_de_lo_que_salio():
    from core.remitos import leer_recepcion
    renglones = [{"id": 1, "articulo_nombre": "EJ", "bultos_enviados": 5}]
    assert leer_recepcion(renglones, {1: "4"}, {1: "40,5"}) == (None, {1: (4.0, 40.5)})
    error, _ = leer_recepcion(renglones, {1: "6"}, {1: "40"})
    assert "recibieron 6 bultos y salieron 5" in error
    error, _ = leer_recepcion(renglones, {1: ""}, {1: "40"})
    assert "Faltan los bultos recibidos" in error
    error, _ = leer_recepcion(renglones, {1: "5"}, {1: ""})
    assert "Faltan los kilos recibidos" in error


def test_el_CHECK_del_tope_rechaza_recibir_mas_bultos_que_los_enviados(base):
    d, sql = base
    import psycopg2
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("UPDATE remitos_renglones SET kilos_recibidos = 1, bultos_recibidos = 6 "
            "WHERE remito_id = %s AND pedido_renglon_id = 11", (remito_id,))
    with pytest.raises(psycopg2.errors.CheckViolation):          # los dos o ninguno
        sql("UPDATE remitos_renglones SET kilos_recibidos = 1 "
            "WHERE remito_id = %s AND pedido_renglon_id = 11", (remito_id,))


def test_el_COTEJO_compara_contra_lo_que_cargo_DEPOSITO_y_la_alerta_se_apaga_sola(base):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id, bultos={11: 3}, kilos={11: 30})    # de 5 se quedó 3: rechazo 2
    _rechazo_de_deposito(sql, 11, 1)
    _rechazo_de_deposito(sql, 11, 5, anulado=True)       # anulado: no cuenta
    renglon = next(r for r in d.remito_por_id(remito_id)["renglones"] if r["pedido_renglon_id"] == 11)
    assert float(renglon["rechazo_deposito"]) == 1.0
    from core.remitos import diferencia_de_rechazo
    assert diferencia_de_rechazo(renglon) == 1.0
    assert d.contar_remitos_con_rechazo_distinto()["casos"] == 1
    _rechazo_de_deposito(sql, 11, 1)                     # Depósito carga el que faltaba
    assert d.contar_remitos_con_rechazo_distinto()["casos"] == 0


def test_un_remito_EMITIDO_no_entra_al_cotejo_aunque_Deposito_tenga_rechazos(base):
    d, sql = base
    d.emitir_remito(1, "VL", "R-0001")
    _rechazo_de_deposito(sql, 11, 3)
    assert d.contar_remitos_con_rechazo_distinto()["casos"] == 0


# --- 3. el importe ------------------------------------------------------------

def test_el_IMPORTE_es_kilos_RECIBIDOS_por_el_precio_vigente_el_DIA_DEL_PEDIDO(base):
    d, sql = base
    from core.remitos import importe_del_remito
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id, kilos={11: 45})
    renglones = d.remito_por_id(remito_id)["renglones"]
    # El 11 a $100 (vigente el 05/09): ni el de agosto ni el del 10/09.
    assert {r["pedido_renglon_id"]: float(r["precio"]) for r in renglones} == {11: 100.0, 12: 50.0}
    assert importe_del_remito(renglones) == {"total": 45 * 100 + 30 * 50, "sin_precio": 0}


def test_un_renglon_SIN_PRECIO_no_suma_y_se_cuenta():
    from core.remitos import importe_del_remito
    renglones = [{"kilos_recibidos": 10, "precio": 5}, {"kilos_recibidos": 3, "precio": None},
                 {"kilos_recibidos": None, "precio": 7}]
    assert importe_del_remito(renglones) == {"total": 50.0, "sin_precio": 1}


# --- 4. facturar y corregir el número -----------------------------------------

def test_FACTURAR_una_factura_varios_remitos_del_mismo_cliente(base):
    d, sql = base
    from app.db import RemitoNoSePuede
    vl = d.emitir_remito(1, "VL", "R-VL")
    bz = d.emitir_remito(1, "BZ", "R-BZ")
    otro = d.emitir_remito(2, "VL", "R-OT")
    with pytest.raises(RemitoNoSePuede, match="recibido"):
        d.facturar_remitos([vl], "F-1")                  # todavía en viaje
    for r in (vl, bz, otro):
        _recibido(d, r)
    with pytest.raises(RemitoNoSePuede, match="un solo cliente"):
        d.facturar_remitos([vl, otro], "F-1")
    assert d.facturar_remitos([vl, bz], " F-0001 ") == 2
    assert sql("SELECT numero, factura_numero FROM remitos WHERE factura_numero IS NOT NULL ORDER BY 1") == [
        ("R-BZ", "F-0001"), ("R-VL", "F-0001")]
    with pytest.raises(RemitoNoSePuede):
        d.facturar_remitos([vl], "F-2")                  # un remito tiene UNA factura


def test_un_remito_NO_SE_ANULA_no_hay_funcion_ni_columna(base):
    d, sql = base
    assert not hasattr(d, "anular_remito")
    assert sql("SELECT count(*) FROM information_schema.columns "
               "WHERE table_name = 'remitos' AND column_name LIKE 'anulado%%'") == [(0,)]


def test_CORREGIR_EL_NUMERO_deja_registro_y_respeta_el_unico(base):
    d, sql = base
    from app.db import RemitoNoSePuede
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    d.emitir_remito(1, "BZ", "R-0002")
    with pytest.raises(RemitoNoSePuede, match="obligatorio"):
        d.corregir_numero_de_remito(remito_id, "  ")
    with pytest.raises(RemitoNoSePuede, match="mismo número"):
        d.corregir_numero_de_remito(remito_id, "r-0001")
    with pytest.raises(RemitoNoSePuede, match="ya está cargado"):
        d.corregir_numero_de_remito(remito_id, "R-0002")
    assert sql("SELECT count(*) FROM remitos_numeros") == [(0,)]      # el rebote no deja registro
    _recibido(d, remito_id)
    d.facturar_remitos([remito_id], "F-1")
    d.corregir_numero_de_remito(remito_id, " R-0010 ")                # también facturado
    d.corregir_numero_de_remito(remito_id, "R-0011")
    assert sql("SELECT numero FROM remitos WHERE id = %s", (remito_id,)) == [("R-0011",)]
    assert [(c["anterior"], c["nuevo"]) for c in d.correcciones_de_numero(remito_id)] == [
        ("R-0001", "R-0010"), ("R-0010", "R-0011")]
    assert all(c["corregido_el"] is not None for c in d.correcciones_de_numero(remito_id))
    import psycopg2
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO remitos_numeros (remito_id, numero_anterior, numero_nuevo) VALUES (%s, 'A', ' a ')",
            (remito_id,))


# --- 5. las alertas y las listas ------------------------------------------------

def test_SIN_VOLVER_es_MAS_de_4_dias_corridos(base):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    sql("UPDATE remitos SET emitido_el = '2026-11-27 23:30-03' WHERE id = %s", (remito_id,))
    assert d.contar_remitos_sin_volver(HOY)["casos"] == 0                    # 4 días: no
    assert d.contar_remitos_sin_volver(HOY + timedelta(days=1))["casos"] == 1  # 5: sí
    _recibido(d, remito_id)
    assert d.contar_remitos_sin_volver(HOY + timedelta(days=1))["casos"] == 0


def test_SIN_FACTURA_es_MAS_de_10_dias_corridos_desde_que_volvio(base):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id)
    sql("UPDATE remitos SET recibido_el = '2026-11-21 10:00-03' WHERE id = %s", (remito_id,))
    assert d.contar_remitos_sin_factura(HOY)["casos"] == 0                     # 10 días: no
    assert d.contar_remitos_sin_factura(HOY + timedelta(days=1))["casos"] == 1  # 11: sí
    d.facturar_remitos([remito_id], "F-1")
    assert d.contar_remitos_sin_factura(HOY + timedelta(days=1))["casos"] == 0


def test_PEDIDOS_SIN_REMITO_cuentan_desde_la_fecha_y_por_orden_de_compra(base):
    d, sql = base
    ordenes = d.ordenes_sin_remito(date(2026, 9, 5))
    # Vigentes: el 1 (VL y BZ), el 2 (VL) y el 3 (VL, sin kilos). El 4 está reemplazado.
    assert sorted((o["pedido_id"], o["sucursal"]) for o in ordenes) == [(1, "BZ"), (1, "VL"), (2, "VL"), (3, "VL")]
    assert next(o for o in ordenes if o["pedido_id"] == 3)["sin_kilos"] == 1
    assert d.contar_ordenes_sin_remito(date(2026, 9, 6))["casos"] == 1        # solo el del 06/09
    d.emitir_remito(1, "VL", "R-0001")
    assert d.contar_ordenes_sin_remito(date(2026, 9, 5))["casos"] == 3


def test_las_listas_de_cada_estado(base):
    d, sql = base
    en_viaje = d.emitir_remito(1, "VL", "R-1")
    recibido = d.emitir_remito(1, "BZ", "R-2")
    facturado = d.emitir_remito(2, "VL", "R-3")
    _recibido(d, recibido)
    _recibido(d, facturado)
    d.facturar_remitos([facturado], "F-1")
    sql("UPDATE remitos SET facturado_el = '2026-11-20 23:30-03' WHERE id = %s", (facturado,))
    assert [r["id"] for r in d.listar_remitos("emitido")] == [en_viaje]
    assert [r["id"] for r in d.listar_remitos("recibido")] == [recibido]
    # La fecha de la factura es la ARGENTINA: 20/11 a las 23:30 es el 20.
    assert [r["id"] for r in d.listar_remitos("facturado", date(2026, 11, 20), date(2026, 11, 20))] == [facturado]
    assert d.listar_remitos("facturado", date(2026, 11, 21), date(2026, 11, 30)) == []


def test_buscar_por_numero_pliega_como_el_indice(base):
    d, sql = base
    d.emitir_remito(1, "VL", "R-0001")
    assert [r["numero"] for r in d.buscar_remitos_por_numero(" r-0001")] == ["R-0001"]
    assert d.buscar_remitos_por_numero("R-9") == []


# --- 6. Rentabilidad: lo recibido -------------------------------------------------

def test_KILOS_RECIBIDOS_solo_de_remitos_RECIBIDOS(base):
    d, sql = base
    vl = d.emitir_remito(1, "VL", "R-VL")
    assert d.kilos_recibidos_por_renglon([11, 12, 13]) == {}
    _recibido(d, vl, kilos={11: 45})
    assert d.kilos_recibidos_por_renglon([11, 12, 13]) == {11: 45.0, 12: 30.0}


def test_la_RENTABILIDAD_cobra_lo_RECIBIDO_y_marca_el_dia_PROVISORIO():
    from core.costo_real import calcular_rentabilidad_real
    from core.remitos import REMITOS_DESDE
    dia = REMITOS_DESDE + timedelta(days=5)
    otro_dia = dia + timedelta(days=1)

    def salida(renglon, fecha):
        return {"tipo": "armado", "fecha": fecha, "cantidad": 5, "unidades": 50, "cliente_id": 1,
                "ficha_id": 1, "renglon_id": renglon, "orden": (fecha, renglon)}

    articulos = [{"articulo_id": 1, "nombre": "EJ", "grupo": "fruta",
                  "entradas": [{"orden": (dia - timedelta(days=4), 0), "cantidad": 20, "costo_bulto": 100,
                                "tipo_lote": "guia"}],
                  "salidas": [salida(11, dia), salida(12, otro_dia)]}]
    margenes = {f: {1: {"precio_vigente": 10, "denominador_tasas": 1, "costo_envase_unidad_venta": 0}}
                for f in (dia, otro_dia)}
    devoluciones = [{"bultos": 1, "fecha_pedido": dia, "kilos_enviados": 50, "bultos_armados": 5,
                     "costo_por_bulto": 100, "articulo_id": 1, "articulo_nombre": "EJ", "grupo": "fruta",
                     "ficha_id": 1, "destino_rechazo": "stock", "renglon_id": 11}]
    resultado = calcular_rentabilidad_real(articulos, margenes, 1, dia, otro_dia,
                                           devoluciones=devoluciones, kilos_recibidos={11: 40})
    totales = resultado["totales"]
    # El 11 se cobra por lo recibido (40) y su devolución NO resta venta otra vez;
    # el 12 sigue con lo enviado (50) y su día es provisorio.
    assert totales["venta_neta"] == 40 * 10 + 50 * 10
    assert totales["devoluciones_venta"] == 0
    assert resultado["fechas_provisorias"] == [otro_dia]
    # Sin saber nada de remitos (llamadores viejos): todo como antes, sin marcar.
    viejo = calcular_rentabilidad_real(articulos, margenes, 1, dia, otro_dia, devoluciones=devoluciones)
    assert viejo["totales"]["venta_neta"] == 100 * 10 and viejo["totales"]["devoluciones_venta"] == 100
    assert viejo["fechas_provisorias"] == []


def test_ANTES_de_REMITOS_DESDE_no_hay_provisorio_pero_un_remito_recibido_se_cobra():
    """Dueño, 01/10: los días anteriores siguen como siempre (enviados), salvo
    que tengan el remito recibido, y entonces cobran lo recibido."""
    from core.costo_real import calcular_rentabilidad_real
    from core.remitos import REMITOS_DESDE
    antes = REMITOS_DESDE - timedelta(days=10)
    justo = REMITOS_DESDE

    def salida(renglon, fecha):
        return {"tipo": "armado", "fecha": fecha, "cantidad": 5, "unidades": 50, "cliente_id": 1,
                "ficha_id": 1, "renglon_id": renglon, "orden": (fecha, renglon)}

    articulos = [{"articulo_id": 1, "nombre": "EJ", "grupo": "fruta",
                  "entradas": [{"orden": (antes - timedelta(days=1), 0), "cantidad": 30, "costo_bulto": 100,
                                "tipo_lote": "guia"}],
                  "salidas": [salida(11, antes), salida(12, antes), salida(13, justo)]}]
    margenes = {f: {1: {"precio_vigente": 10, "denominador_tasas": 1, "costo_envase_unidad_venta": 0}}
                for f in (antes, justo)}
    resultado = calcular_rentabilidad_real(articulos, margenes, 1, antes, justo, kilos_recibidos={12: 40})
    # El 11 (antes, sin remito) con lo enviado y SIN provisorio; el 12 (antes, con
    # remito recibido) con lo recibido; el 13 (desde la fecha) sin remito: provisorio.
    assert resultado["totales"]["venta_neta"] == 50 * 10 + 40 * 10 + 50 * 10
    assert resultado["fechas_provisorias"] == [justo]


# --- 7. las pantallas ------------------------------------------------------------

def test_EMITIR_desde_la_pantalla_y_volver_al_remito(base, monkeypatch):
    d, sql = base
    cliente = _cliente(monkeypatch, "administracion")
    pantalla = cliente.get("/administracion/facturacion/emitir", params={"pedido_id": 1, "sucursal": "VL"})
    assert pantalla.status_code == 200 and "OC-EJ-1" in pantalla.text
    respuesta = cliente.post("/administracion/facturacion/emitir",
                             data={"pedido_id": 1, "sucursal": "VL", "numero": "R-0001"}, follow_redirects=False)
    assert respuesta.status_code == 303 and "/administracion/facturacion/remito/" in respuesta.headers["location"]
    repetido = cliente.post("/administracion/facturacion/emitir",
                            data={"pedido_id": 1, "sucursal": "VL", "numero": "R-0002"})
    assert repetido.status_code == 400 and "ya tiene su remito" in repetido.text


def test_RECIBIR_por_la_pantalla_sube_la_foto_y_sin_foto_rebota(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    cliente = _cliente(monkeypatch, "administracion")
    busca = cliente.get("/administracion/facturacion/recibir", params={"numero": "r-0001"}, follow_redirects=False)
    assert busca.status_code == 303 and busca.headers["location"].split("?")[0].endswith(f"/remito/{remito_id}/recibir")
    formulario = cliente.get(f"/administracion/facturacion/remito/{remito_id}/recibir")
    assert 'value="50"' in formulario.text                  # precargado con lo enviado
    ids = {r["pedido_renglon_id"]: r["id"] for r in d.remito_por_id(remito_id)["renglones"]}
    assert f'name="bultos_{ids[11]}" required\n                     value="5"' in formulario.text
    datos = {f"bultos_{ids[11]}": "4", f"kilos_{ids[11]}": "40", f"bultos_{ids[12]}": "3", f"kilos_{ids[12]}": "30"}
    with patch("app.main.subir_foto_comanda", return_value="remitos/EJ-subida.jpg") as subir:
        sin_foto = cliente.post(f"/administracion/facturacion/remito/{remito_id}/recibir", data=datos)
        subir.assert_not_called()
        assert sin_foto.status_code == 400 and "foto del remito firmado" in sin_foto.text
        con_foto = cliente.post(f"/administracion/facturacion/remito/{remito_id}/recibir", data=datos,
                                files={"fotos": ("r.jpg", _jpeg(), "image/jpeg")}, follow_redirects=False)
    assert con_foto.status_code == 303
    remito = d.remito_por_id(remito_id)
    assert remito["recibido_el"] is not None and [f["ruta"] for f in remito["fotos"]] == ["remitos/EJ-subida.jpg"]
    assert {r["pedido_renglon_id"]: float(r["bultos_recibidos"]) for r in remito["renglones"]} == {11: 4.0, 12: 3.0}


def test_si_la_base_rebota_la_foto_subida_se_borra(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    cliente = _cliente(monkeypatch, "administracion")
    ids = [r["id"] for r in d.remito_por_id(remito_id)["renglones"]]
    datos = {**{f"bultos_{i}": "1" for i in ids}, **{f"kilos_{i}": "1" for i in ids}}
    _recibido(d, remito_id)                  # otro lo recibió mientras: la base rebota
    with patch("app.main.subir_foto_comanda", return_value="remitos/EJ-huerfana.jpg"), \
         patch("app.main.borrar_foto_comanda") as borrar:
        respuesta = cliente.post(f"/administracion/facturacion/remito/{remito_id}/recibir", data=datos,
                                 files={"fotos": ("r.jpg", _jpeg(), "image/jpeg")})
    assert respuesta.status_code == 400 and "ya se recibió" in respuesta.text
    borrar.assert_called_once_with("remitos/EJ-huerfana.jpg")


def test_FACTURACION_las_cuatro_listas_y_cada_puerta_lo_suyo(base, monkeypatch):
    d, sql = base
    recibido = d.emitir_remito(1, "VL", "R-REC")
    _recibido(d, recibido)
    d.emitir_remito(2, "VL", "R-VIAJE")
    with patch("app.main.REMITOS_DESDE", date(2026, 9, 1)), patch("app.main._hoy_argentina", return_value=HOY):
        admin = _marcado(_cliente(monkeypatch, "administracion").get("/administracion/facturacion"))
        gerencia = _marcado(_cliente(monkeypatch, "gerencia").get("/gerencia/facturacion"))
    for marcado in (admin, gerencia):
        for ancla in ('id="sin-remito"', 'id="en-viaje"', 'id="recibidos"', 'id="facturados"'):
            assert ancla in marcado
        assert "Remito R-REC" in marcado and "Remito R-VIAJE" in marcado
    # Administración emite, recibe y factura; Gerencia mira.
    assert 'action="/administracion/facturacion/facturar"' in admin and ">Emitir remito<" in admin
    # La búsqueda para recibir se abre desde ESTE formulario (no hay href):
    # el barrido de pantallas linkeadas la tiene decidida por eso.
    assert 'action="/administracion/facturacion/recibir"' in admin
    assert 'action="/administracion/facturacion/facturar"' not in gerencia and ">Emitir remito<" not in gerencia
    assert "/administracion/" not in gerencia.split('id="sin-remito"')[1]


def test_solo_GERENCIA_corrige_el_NUMERO_y_la_pantalla_muestra_el_registro(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    admin_cliente = _cliente(monkeypatch, "administracion")
    admin = _marcado(admin_cliente.get(f"/administracion/facturacion/remito/{remito_id}"))
    assert "/numero" not in admin and "lo corrige Gerencia" in admin
    assert "anular" not in admin.lower()
    gerencia = _cliente(monkeypatch, "gerencia")
    marcado = _marcado(gerencia.get(f"/gerencia/facturacion/remito/{remito_id}"))
    assert f'action="/gerencia/facturacion/remito/{remito_id}/numero"' in marcado
    assert "anular" not in marcado.lower()
    gerencia.post(f"/gerencia/facturacion/remito/{remito_id}/numero", data={"numero": "R-0010"})
    assert sql("SELECT numero FROM remitos") == [("R-0010",)]
    marcado = _marcado(gerencia.get(f"/gerencia/facturacion/remito/{remito_id}"))
    assert "R-0001 → <b>R-0010</b>, corregido el " in marcado
    # Sin la clave de Gerencia, el POST no corrige.
    admin_cliente.post(f"/gerencia/facturacion/remito/{remito_id}/numero", data={"numero": "R-0099"})
    assert sql("SELECT numero FROM remitos") == [("R-0010",)]


def test_el_remito_OBSERVADO_dice_que_renglones_cambiaron(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id, bultos={11: 4}, kilos={11: 40})
    marcado = _marcado(_cliente(monkeypatch, "administracion").get(f"/administracion/facturacion/remito/{remito_id}"))
    assert "Volvió observado: 1 renglón con cambios." in marcado
    assert marcado.count('class="cambio"') == 1 and " · cambió el " in marcado
    assert "Rechazados: remito <b>1</b>" in marcado


def test_ARMAR_REMITO_ofrece_emitir_o_muestra_el_remito_de_cada_sucursal(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    cliente = _cliente(monkeypatch, "administracion")
    marcado = _marcado(cliente.get("/administracion/pedidos/buscar", params={
        "cliente_id": 1, "fecha_desde": "2026-09-05", "fecha_hasta": "2026-09-05"}))
    assert re.search(rf'href="/administracion/facturacion/remito/{remito_id}\?volver=[^"]+">Remito R-0001', marcado)
    assert 'href="/administracion/facturacion/emitir?pedido_id=1&sucursal=BZ&amp;volver=' in marcado


def test_el_hub_de_Administracion_y_el_de_Gerencia_llevan_a_Facturacion(monkeypatch):
    from app.main import app  # noqa: F401
    import io as _io
    for plantilla, href in (("administracion.html", "/administracion/facturacion"),
                            ("gerencia.html", "/gerencia/facturacion")):
        texto = _io.open(os.path.join(RAIZ, "templates", plantilla), encoding="utf-8").read()
        assert f'href="{href}"' in texto


def _que_se_sale(html, ancho):
    """Cuánto se sale de su caja CADA elemento (corolario 53, sexto límite): el
    desborde de página puede dar cero con una tarjeta absorbiéndolo."""
    pytest.importorskip("playwright", reason="lo que desborda lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": ancho, "height": 800})
        pagina.set_content(html)
        resultado = pagina.evaluate("""() => {
            const raiz = document.documentElement;
            const salidos = [];
            for (const el of document.querySelectorAll('body *')) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.right > raiz.clientWidth + 0.5) {
                    salidos.push((el.className || el.tagName) + ' +' + Math.round(r.right - raiz.clientWidth));
                }
            }
            return {pagina: raiz.scrollWidth - raiz.clientWidth, salidos: salidos,
                    renglones: document.querySelectorAll('.fila-renglon').length};
        }""")
        navegador.close()
    return resultado


def test_ARMAR_REMITO_no_desborda_a_313px_con_un_nombre_que_no_se_puede_partir(base, monkeypatch):
    """Dueño, 01/10: a 313px se salía. El par: el nombre impartible y el normal."""
    d, sql = base
    sql("UPDATE articulos SET nombre = 'EJEMPLOARTICULOCONUNNOMBRESINESPACIOSQUENOENTRA' WHERE id = 1")
    d.emitir_remito(1, "VL", "R-0001-EJEMPLO-LARGO")
    cliente = _cliente(monkeypatch, "administracion")
    html = cliente.get("/administracion/pedidos/buscar", params={
        "cliente_id": 1, "fecha_desde": "2026-09-05", "fecha_hasta": "2026-09-05"}).text
    for ancho in (313, 390):
        medicion = _que_se_sale(html, ancho)
        assert medicion["renglones"] >= 3                     # se midió la pantalla con renglones
        assert medicion["pagina"] == 0 and medicion["salidos"] == [], (ancho, medicion)


def test_DETALLE_y_RECIBIR_no_desbordan_a_390px(base, monkeypatch):
    d, sql = base
    sql("UPDATE articulos SET nombre = 'EJEMPLOARTICULOCONUNNOMBRESINESPACIOSQUENOENTRA' WHERE id = 1")
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    gerencia = _cliente(monkeypatch, "gerencia", "administracion")
    recibir = gerencia.get(f"/administracion/facturacion/remito/{remito_id}/recibir").text
    _recibido(d, remito_id, bultos={11: 4}, kilos={11: 40})
    d.corregir_numero_de_remito(remito_id, "R-0001-EJEMPLO-CORREGIDO")
    detalle = gerencia.get(f"/gerencia/facturacion/remito/{remito_id}").text
    for nombre, html in (("recibir", recibir), ("detalle", detalle)):
        medicion = _que_se_sale(html, 390)
        assert medicion["pagina"] == 0 and medicion["salidos"] == [], (nombre, medicion)
