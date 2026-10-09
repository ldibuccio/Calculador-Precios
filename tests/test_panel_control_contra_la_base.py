# -*- coding: utf-8 -*-
"""Panel de control de Gerencia (dueño, 08/10), contra Postgres.

Lo que el panel le cambió a las consultas que ya existían, y la pantalla:

  · la cruz cuenta como incompleto, y el panel y la alerta dan lo mismo;
  · las compras pesadas sin umbral, con el mismo recorte que la alerta;
  · los bultos al lado de la facturación de Márgenes;
  · la rentabilidad del panel es la Real sin mermas ni segunda, y Mermas y
    Segunda son la cuenta de Pérdidas (el galpón de
    tests/test_rentabilidad_real_pase.py, que tiene merma y pase);
  · el tablero y cada detalle, con el "hoy" del panel puesto a una fecha que
    no puede ser la real.

EL INTERRUPTOR ES EL DEL HUMO: sin Postgres se saltea; con HUMO_OBLIGATORIO=1
dejar de poder correrlo FALLA.
"""
import os
import re
import sys
from datetime import date, timedelta
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 8)
DESDE_7 = HOY - timedelta(days=7)

# EL GALPÓN DEL PANEL
#   Día (1) compra y tiene un pedido del 05/10 con un renglón completo, uno
#   armado de menos, uno con la cruz y uno sin armar en el pedido terminado.
#   Día tiene otro del 06/10, SIN TERMINAR, armado entero salvo un renglón con
#   la cruz: incompleto SOLO por la cruz.
#   RIVAL: un pedido incompleto del 20/09, fuera de los 7 días.
#   Pedidos Ya (2) tiene ficha y ninguna venta. "Sin ficha" (3) no aparece.
#   Compras pesadas (la foto de la balanza arranca el 02/09):
#     #1 02/10 10 cajones de 20 kg que pesaron 18 -> faltan 20
#     #2 03/10  5 cajones de 20 que pesaron 21    -> sobran 5, no compensa
#     #3 04/10 una compra en UNIDADES              -> fuera de los kilos
#     #4 15/09 10 de 20 que pesaron 19             -> septiembre: 10 de 200
#     #5 30/08 RIVAL: antes de la primera foto
#   Un rechazo de 1 bulto a $400 el 06/10 del renglón completo, que vuelve al
#   stock, y otro de 2 bultos a $400 el 07/10 que va a SEGUNDA: el puesto
#   pagó $300 por ese lote. Lo perdido en segunda: $800 − $300 = $500.
#   En septiembre el puesto pagó $900 por un lote de segunda de guía R (a $0 de
#   costo) y no fue nada más a segunda: se RECUPERARON $900.
SIEMBRA = """
insert into clientes (id, nombre) overriding system value
  values (1, 'EJEMPLO Día'), (2, 'EJEMPLO Pedidos Ya'), (3, 'EJEMPLO Sin ficha');
insert into articulos (id, nombre, grupo, unidad_compra, unidad_conteo) overriding system value
  values (1, 'EJEMPLO Tomate', 'hortaliza', 'kilo', null), (2, 'EJEMPLO Ananá', 'fruta', 'unidad', 'unidad');
insert into proveedores (id, nombre, codigo_puesto) overriding system value values (1, 'EJEMPLO Puesto', 'N01P01');
insert into fichas_logistica (id, articulo_id, cliente_id, unidad_venta, contenido_caja) overriding system value
  values (1, 1, 1, 'kilo', 10), (2, 1, 2, 'kilo', 10);
insert into precios_venta_historial (articulo_id, cliente_id, ficha_id, precio, vigente_desde) values
  (1, 1, 1, 100, '2026-09-01'), (1, 2, 2, 120, '2026-09-01');
insert into pedidos (id, cliente_id, fecha_operacion, origen, creado_en, armado_cerrado_el) overriding system value
  values (1, 1, '2026-10-05', 'mail', '2026-10-05 08:00-03', '2026-10-05 15:00-03'),
         (2, 1, '2026-09-20', 'mail', '2026-09-20 08:00-03', '2026-09-20 15:00-03'),
         (3, 1, '2026-10-06', 'mail', '2026-10-06 08:00-03', null);
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad, cantidad_armada,
                               armado_el, kilos_enviados, anulado_el) overriding system value values
  (11, 1, 'VL', 1, 1, 5, null, '2026-10-05 12:00-03', 50, null),
  (12, 1, 'BZ', 1, 1, 5, 3, '2026-10-05 12:00-03', 30, null),
  (13, 1, 'GR', 1, 1, 4, null, null, null, '2026-10-05 11:00-03'),
  (14, 1, 'LP', 1, 1, 2, null, null, null, null),
  (21, 2, 'VL', 1, 1, 5, 2, '2026-09-20 12:00-03', 20, null),
  (31, 3, 'VL', 1, 1, 2, null, '2026-10-06 12:00-03', 20, null),
  (32, 3, 'BZ', 1, 1, 3, null, null, null, '2026-10-06 11:00-03');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones, contenido_por_cajon,
                     cantidad_kilos, cantidad_fraccion, importe, estado, cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value values
  (1, 1, 1, '2026-10-02', 10, 20, 200, null, 1000, 'recepcionado', 10, 18),
  (2, 1, 1, '2026-10-03', 5, 20, 100, null, 1000, 'recepcionado', 5, 21),
  (3, 1, 2, '2026-10-04', 4, 8, 40, 32, 1000, 'recepcionado', 4, 6),
  (4, 1, 1, '2026-09-15', 10, 20, 200, null, 1000, 'recepcionado', 10, 19),
  (5, 1, 1, '2026-08-30', 10, 20, 200, null, 1000, 'recepcionado', 10, 10);
insert into fotos_recepcion (compra_id, foto_ruta, creado_en) values (4, 'pesaje/EJ-4.jpg', '2026-09-02 10:00-03');
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo, stock_sistema,
                               pedido_renglon_id, destino_rechazo, cliente_id, costo_por_bulto)
  values (1, '2026-10-06', 'reingreso_rechazo', 1, 'EJEMPLO volvió', 0, 11, 'stock', 1, 400);
insert into movimientos_stock (articulo_id, fecha_operacion, tipo, cantidad, motivo, stock_sistema,
                               pedido_renglon_id, destino_rechazo, bultos_segunda, cliente_id, costo_por_bulto)
  values (1, '2026-10-07', 'reingreso_rechazo', 2, 'EJEMPLO a segunda', 0, 11, 'segunda', 2, 1, 400);
insert into remitos_segunda (id, articulo_id, bultos, fecha_operacion, destino) overriding system value
  values (80, 1, 2, '2026-10-07', 'puesto');
insert into segunda_cobros (salida_id, importe, fecha_cobro, sector) values (80, 300, '2026-10-08', 'gerencia');
insert into remitos_segunda (id, articulo_id, bultos, fecha_operacion, destino) overriding system value
  values (81, 1, 6, '2026-09-25', 'puesto');
insert into segunda_cobros (salida_id, importe, fecha_cobro, sector) values (81, 900, '2026-09-26', 'gerencia');
"""


def _base_con(siembra):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay un Postgres usable: el Panel de control no se verificó.")
        pytest.skip("sin Postgres local: se corre con el humo antes de desplegar")
    url = preparar_base()
    if url is None:
        pytest.fail("no se pudo preparar la base con db/esquema_completo.sql")
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(siembra)
    conexion.commit()
    conexion.close()
    return url


@pytest.fixture(autouse=True)
def _sin_foto_del_panel():
    """El tablero muestra la ÚLTIMA FOTO (dueño, 09/10): cada test arranca sin
    ninguna, así su primera entrada la calcula con SU día y SUS datos."""
    yield
    if os.environ.get("DATABASE_URL"):
        import app.db as d
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("DELETE FROM panel_fotos")
            conexion.commit()
        finally:
            conexion.close()


@pytest.fixture(scope="module")
def base():
    url = _base_con(SIEMBRA)
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        import app.main as m
        yield m


def test_la_CRUZ_cuenta_como_incompleto_y_el_PANEL_da_lo_MISMO_que_la_ALERTA(base):
    from app.db import contar_pedidos_incompletos, listar_pedidos_incompletos
    renglones = listar_pedidos_incompletos(DESDE_7)
    assert sorted((r["pedido_id"], r["sucursal"], r["motivo"]) for r in renglones) == [
        (1, "BZ", "de_menos"), (1, "GR", "cruz"), (1, "LP", "sin_armar"), (3, "BZ", "cruz")]
    # El pedido 3 es incompleto SOLO por la cruz, y la alerta lo cuenta. El
    # RIVAL del 20/09 queda fuera de los 7 días.
    assert contar_pedidos_incompletos(DESDE_7)["casos"] == 2
    # El MISMO número: el del cuadro del panel y el de la alerta registrada.
    m = base
    with patch.object(m, "_hoy_argentina", return_value=HOY):
        alerta = next(a for a in m.ALERTAS if a.codigo == "pedidos_incompletos")
        assert m._panel_pedidos(HOY)["pedidos"] == alerta.contar()["casos"] == 2


def test_las_COMPRAS_PESADAS_traen_todas_y_la_ALERTA_sigue_con_su_umbral(base):
    from app.db import listar_compras_pesadas, listar_diferencia_de_kilos
    assert [c["id"] for c in listar_compras_pesadas(date(2026, 10, 1), HOY)] == [3, 2, 1]
    assert [c["id"] for c in listar_compras_pesadas(date(2026, 8, 1), date(2026, 9, 30))] == [4]   # #5: antes de la foto
    # La alerta, igual que antes: con su umbral y el cajón en SU unidad (a la
    # de unidades le faltaron 2 por cajón y entra; la que pesó de más no).
    assert [c["id"] for c in listar_diferencia_de_kilos(date(2026, 10, 1), HOY, 1)] == [3, 1]


def test_la_FACTURACION_de_Margenes_trae_los_BULTOS_de_las_mismas_entregas(base):
    from app.db import facturacion_por_ficha
    facturado = facturacion_por_ficha(1, date(2026, 10, 1), HOY)
    # Renglones 11 (5 bultos, 50 kg), 12 (3 armados de 5, 30 kg) y 31 (2, 20 kg):
    # ni las cruces ni el sin armar.
    assert facturado["por_ficha"] == {1: 10000.0}
    assert facturado["bultos_por_ficha"] == {1: 10.0}


def _cliente_gerencia(m):
    from fastapi.testclient import TestClient
    from tests.test_administracion_reordenada import CLAVES, _cliente
    with patch.dict(os.environ, CLAVES):
        return _cliente(m, "gerencia"), CLAVES


def test_el_TABLERO_dice_un_numero_por_cuadro_en_el_orden_del_dueno(base):
    m = base
    cliente, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves), patch.object(m, "_hoy_argentina", return_value=HOY):
        pagina = cliente.get("/gerencia/panel")
    assert pagina.status_code == 200, pagina.text[:300]
    marcado = pagina.text.split("</style>")[-1]
    assert re.findall(r'data-cuadro="([a-z]+)"', marcado) == list(m.CUADROS_DEL_PANEL)
    assert m.CUADROS_DEL_PANEL == ("rentabilidad", "cajas", "pedidos", "peso", "vales", "vacios", "rechazos",
                                   "mermas", "segunda")
    for cuadro in m.CUADROS_DEL_PANEL:
        assert marcado.count(f'href="/gerencia/panel/{cuadro}"') == 1, cuadro

    def cuadro(nombre):
        return marcado.split(f'data-cuadro="{nombre}"')[1].split("</a>")[0]

    rentabilidad = cuadro("rentabilidad")
    assert "EJEMPLO Día" in rentabilidad and "EJEMPLO Pedidos Ya" in rentabilidad
    assert "EJEMPLO Sin ficha" not in rentabilidad
    ya = rentabilidad.split("EJEMPLO Pedidos Ya")[1]
    assert ya.count("sin ventas") == 1
    assert "Ganancia sobre el costo de la mercadería" in rentabilidad
    assert "sin mermas ni segunda (ver sus cuadros)" in rentabilidad
    assert re.search(r'cuadro-numero rojo">2</div>', cuadro("pedidos"))
    peso = cuadro("peso")
    assert "Septiembre" in peso and "Octubre (a hoy)" in peso
    assert ">5,0%<" in peso                          # septiembre: 10 de 200
    assert ">6,7%<" in peso                          # octubre: 20 de 300 kilos
    # Las unidades, solas: 4 cajones de 8 que trajeron 6 -> faltan 8 de 32.
    assert 'data-unidad="unidad">Unidades: 25,0%<' in peso
    assert peso.count('data-unidad="cubeta">Cubetas: —<') == 2
    rechazos = cuadro("rechazos")
    # Octubre: 3 bultos a $400 = $1.200 de $10.000 facturados = 12,0%; 3 de 10 = 30,0%.
    assert "12,0%" in rechazos and "30,0%" in rechazos and "$1.200" in rechazos and "3 bultos" in rechazos


def test_cada_DETALLE_abre_y_PEDIDOS_distingue_armado_de_menos_de_la_cruz(base):
    m = base
    cliente, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves), patch.object(m, "_hoy_argentina", return_value=HOY):
        paginas = {c: cliente.get(f"/gerencia/panel/{c}") for c in m.CUADROS_DEL_PANEL}
        inexistente = cliente.get("/gerencia/panel/otro")
    assert {c: p.status_code for c, p in paginas.items()} == {c: 200 for c in m.CUADROS_DEL_PANEL}
    assert inexistente.status_code == 404
    # Una dirección escrita por cuadro: las ENCONTRADAS contra las DECIDIDAS.
    import ast
    import io as _io
    arbol = ast.parse(_io.open("app/main.py", encoding="utf-8").read())
    rutas = {d.args[0].value for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)
             and n.name == "ver_detalle_del_panel" for d in n.decorator_list}
    assert rutas == {f"/gerencia/panel/{c}" for c in m.CUADROS_DEL_PANEL}
    pedidos = paginas["pedidos"].text.split("</style>")[-1]
    motivos = dict(re.findall(r'data-motivo="([a-z_]+)">.*?<span class="rojo">([^<]+)</span>', pedidos, re.S))
    assert motivos == {"de_menos": "Armado de menos", "cruz": "No se armó (cruz)", "sin_armar": "No se armó"}
    peso = paginas["peso"].text.split("</style>")[-1]
    # Ninguna compra queda afuera: la de unidades está, con su unidad.
    assert peso.count('data-compra="1"') == 1 and peso.count('data-compra="3"') == 1
    assert "Compra #1 · 02/10 · EJEMPLO Puesto" in peso
    assert "declarados 32 u" in peso and "-8 u" in peso


def test_la_MISMA_PANTALLA_de_Gerencia_tiene_el_boton_del_panel(base):
    m = base
    cliente, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves):
        hub = cliente.get("/gerencia").text.split("</style>")[-1]
    assert hub.count('href="/gerencia/panel"') == 1


def test_un_RECHAZO_que_va_a_SEGUNDA_y_se_cobra_da_costo_MENOS_cobrado_y_no_negativo(base):
    """Del pedido del dueño (08/10): lo cobrado incluía la segunda de los
    rechazos y el costo no. Con un rechazo de 2 bultos a $400 a segunda y $300
    cobrados por ese lote, lo perdido es $500 —antes salía −$300."""
    m = base
    with patch.object(m, "_hoy_argentina", return_value=HOY):
        octubre = m._panel_segunda(HOY, {})["actual"]
    assert octubre["por_origen"] == {"pase": 0.0, "rechazo": 800.0, "reproceso": 0.0}
    assert (octubre["costo"], octubre["cobrado"], octubre["perdida"]) == (800.0, 300.0, 500.0)
    assert octubre["perdida"] >= 0
    (tomate,) = octubre["filas"]
    assert (tomate["articulo"], tomate["rechazo"], tomate["cobrado"], tomate["perdida"]) == (
        "EJEMPLO Tomate", 800.0, 300.0, 500.0)
    cliente, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves), patch.object(m, "_hoy_argentina", return_value=HOY):
        cuadro = cliente.get("/gerencia/panel").text.split('data-cuadro="segunda"')[1].split("</a>")[0]
    actual = cuadro.split("Octubre")[1]
    assert '<div data-ajustar class="cuadro-numero rojo" data-resultado="perdido">$500</div>' in actual
    assert 'data-origen="rechazo">rechazos $800<' in actual and "cobrado $300" in actual



def test_si_el_puesto_pago_MAS_que_el_costo_se_ve_RECUPERADO_en_verde_y_no_una_perdida_negativa(base):
    """Septiembre: $900 cobrados por segunda de guía R, a $0 de costo (dueño,
    08/10: su costo ya está en las cajas armadas)."""
    m = base
    septiembre = m._panel_segunda(HOY, {})["anterior"]
    assert septiembre["por_origen"] == {"pase": 0.0, "rechazo": 0.0, "reproceso": 0.0}
    assert (septiembre["cobrado"], septiembre["perdida"]) == (900.0, -900.0)
    cliente, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves), patch.object(m, "_hoy_argentina", return_value=HOY):
        tablero = cliente.get("/gerencia/panel").text.split("</style>")[-1]
        detalle = cliente.get("/gerencia/panel/segunda").text.split("</style>")[-1]
    cuadro = tablero.split('data-cuadro="segunda"')[1].split("</a>")[0]
    anterior, actual = cuadro.split("Septiembre")[1].split("Octubre")
    assert anterior.count('<div data-ajustar class="cuadro-numero verde" data-resultado="recuperado">$900</div>') == 1
    assert '<div class="cuadro-pie">recuperado</div>' in anterior
    assert 'data-resultado="perdido">$500<' in actual and '<div class="cuadro-pie">perdido</div>' in actual
    assert "-$" not in cuadro and "$-" not in cuadro
    assert cuadro.count("reprocesos a $0: su costo ya está en las cajas armadas") == 1
    septiembre_detalle = detalle.split('data-mes="anterior"')[1].split('data-mes="actual"')[0]
    assert '<p data-ajustar class="grande verde" data-resultado="recuperado">$900 recuperado</p>' in septiembre_detalle
    assert '<span class="verde">$900 recuperado</span>' in septiembre_detalle
    assert "-$" not in septiembre_detalle and "$-" not in septiembre_detalle

# ---- El galpón de un solo cliente, con merma, pase y segunda cobrada. OJO:
# `preparar_base` recrea LA MISMA base, así que desde acá la de arriba ya no
# existe: los tests de `base` van todos antes de esta línea. ----

@pytest.fixture(scope="module")
def galpon_de_un_cliente():
    from tests.test_rentabilidad_real_pase import SIEMBRA as SIEMBRA_DEL_PASE
    # Más un lote de segunda al puesto, cobrado $250, del 15/09, y una VENTA
    # del 15/09 (5 cajas de Tomate a $100 el kilo) para que haya rentabilidad.
    url = _base_con(SIEMBRA_DEL_PASE + """
insert into precios_venta_historial (articulo_id, cliente_id, ficha_id, precio, vigente_desde)
  values (1, 1, 1, 100, '2026-09-01');
insert into pedidos (id, cliente_id, fecha_operacion, origen, creado_en) overriding system value
  values (70, 1, '2026-09-15', 'mail', '2026-09-15 08:00-03');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad, armado_el, kilos_enviados)
  overriding system value values (701, 70, 'VL', 1, 1, 5, '2026-09-15 12:00-03', 30);
insert into remitos_segunda (id, articulo_id, bultos, fecha_operacion, destino) overriding system value
  values (90, 1, 3, '2026-09-15', 'puesto');
insert into segunda_cobros (salida_id, importe, fecha_cobro, sector) values (90, 250, '2026-09-20', 'gerencia');
""")
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        import app.main as m
        yield m


def test_la_RENTABILIDAD_del_panel_es_la_Real_SIN_mermas_ni_segunda(galpon_de_un_cliente):
    m = galpon_de_un_cliente
    from tests.test_rentabilidad_real_pase import DESDE, HASTA
    pantalla = m._datos_rentabilidad_real(1, DESDE, HASTA, None, None)["totales"]
    panel = m._datos_rentabilidad_real(1, DESDE, HASTA, None, None, solo_lo_vendido=True)["totales"]
    assert pantalla["costo_mermas"] > 0 and pantalla["costo_segunda"] > 0      # el testigo: hay de las dos
    assert (panel["costo_mermas"], panel["costo_segunda"], panel["recupero_segunda"]) == (0, 0, 0)
    assert panel["venta_neta"] == pytest.approx(pantalla["venta_neta"])
    assert panel["costo_mercaderia"] == pytest.approx(pantalla["costo_mercaderia"])
    assert panel["renta_pesos"] == pytest.approx(
        pantalla["renta_pesos"] + pantalla["costo_mermas"] + pantalla["costo_segunda"] - pantalla["recupero_segunda"])


def test_MERMAS_y_SEGUNDA_son_la_cuenta_de_PERDIDAS_y_lo_cobrado_al_puesto(galpon_de_un_cliente):
    m = galpon_de_un_cliente
    from app.db import perdidas_por_periodo
    septiembre = perdidas_por_periodo(date(2026, 9, 1), date(2026, 9, 30))
    merma, segunda = septiembre["renglones"]["merma"]["total"], septiembre["renglones"]["segunda"]["total"]
    assert merma > 0 and segunda > 250                                          # el testigo
    cliente, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves), patch.object(m, "_hoy_argentina", return_value=HOY):
        tablero = cliente.get("/gerencia/panel").text.split("</style>")[-1]
        detalle_segunda = cliente.get("/gerencia/panel/segunda").text.split("</style>")[-1]
        detalle_mermas = cliente.get("/gerencia/panel/mermas").text.split("</style>")[-1]
    assert re.findall(r'data-cuadro="([a-z]+)"', tablero)[-3:] == ["rechazos", "mermas", "segunda"]
    moneda = m._formatear_moneda
    cuadro_mermas = tablero.split('data-cuadro="mermas"')[1].split("</a>")[0]
    assert f'cuadro-numero rojo">{moneda(merma)}<' in cuadro_mermas
    cuadro_segunda = tablero.split('data-cuadro="segunda"')[1].split("</a>")[0]
    assert f">{moneda(segunda - 250)}<" in cuadro_segunda
    assert f'data-origen="pase">pases {moneda(segunda)}<' in cuadro_segunda
    assert 'data-origen="rechazo">rechazos $0<' in cuadro_segunda
    assert "cobrado $250" in cuadro_segunda
    septiembre_segunda = detalle_segunda.split('data-mes="anterior"')[1].split('data-mes="actual"')[0]
    assert "EJEMPLO Tomate" in septiembre_segunda and "cobrado $250" in septiembre_segunda
    assert detalle_mermas.split('data-mes="anterior"')[1].count('class="fila"') == len(
        [f for f in septiembre["detalle"] if f["destino"] == "merma"])


def test_el_CUADRO_de_rentabilidad_usa_la_Real_SIN_mermas_y_no_la_entera(galpon_de_un_cliente):
    """El cableado: lo que el cuadro muestra para el mes es la cuenta sin
    mermas, y en este galpón es DISTINTA de la de la pantalla de la Real."""
    m = galpon_de_un_cliente
    fin_de_mes = date(2026, 9, 30)
    (fila,) = [f for f in m._panel_rentabilidad(fin_de_mes) if f["cliente_id"] == 1]
    sin_mermas = m._datos_rentabilidad_real(1, date(2026, 9, 1), fin_de_mes, None, None, solo_lo_vendido=True)
    entera = m._datos_rentabilidad_real(1, date(2026, 9, 1), fin_de_mes, None, None)
    assert sin_mermas["totales"]["venta_neta"] > 0                              # el testigo: hubo venta
    assert fila["mes"] == pytest.approx(sin_mermas["totales"]["utilidad_pct"])
    assert fila["mes"] != pytest.approx(entera["totales"]["utilidad_pct"])
