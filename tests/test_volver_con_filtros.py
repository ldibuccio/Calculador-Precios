"""Volver a la lista CON SUS FILTROS (dueño, 05/10).

"Si listé 10 remitos de septiembre, entré en uno, lo cargué y vuelvo, tengo
que ver esos mismos 10 sin volver a filtrar." La lista manda su propia
dirección en `volver`; el detalle la usa para la barra, el "Volver" y las
redirecciones después de guardar. Los tests SIGUEN LOS LINKS QUE DIBUJA LA
PANTALLA, no arman la URL a mano: si la lista no manda `volver`, el camino se
corta y el test lo ve.
"""
import html as _html
import os
import re
import sys
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_remitos import _cliente, _jpeg, _recibido, base  # noqa: E402,F401


def _href(marcado: str, patron: str) -> str:
    """El href de un link de la pantalla cuyo destino empieza con `patron`."""
    hrefs = [_html.unescape(h) for h in re.findall(r'href="([^"]+)"', marcado)]
    elegidos = [h for h in hrefs if h.startswith(patron)]
    assert elegidos, f"la pantalla no tiene un link a {patron}"
    return elegidos[0]


def _accion(marcado: str, patron: str) -> str:
    acciones = [_html.unescape(a) for a in re.findall(r'<form[^>]*method="post"[^>]*action="([^"]+)"', marcado)]
    elegidas = [a for a in acciones if a.startswith(patron)]
    assert elegidas, f"la pantalla no tiene un formulario a {patron}"
    return elegidas[0]


def _barra(marcado: str) -> str:
    (atras,) = re.findall(r'<a class="barra-boton" href="([^"]+)" aria-label="Volver atrás">', marcado)
    return _html.unescape(atras)


def _volver_de(url: str) -> str:
    return parse_qs(urlsplit(url).query)["volver"][0]


# --- Armar remito → remito → atrás ------------------------------------------

ARMAR = "/administracion/pedidos/buscar?cliente_id=1&fecha_desde=2026-09-05&fecha_hasta=2026-09-06"


def test_ARMAR_REMITO_emitir_y_volver_deja_la_misma_lista(base, monkeypatch):
    """El caso del dueño: Armar remito con sus fechas → Emitir → el remito →
    atrás vuelve a Armar remito con esas fechas, no a Facturación."""
    d, sql = base
    cliente = _cliente(monkeypatch, "administracion")
    lista = cliente.get(ARMAR).text
    emitir = _href(lista, "/administracion/facturacion/emitir?pedido_id=1&sucursal=VL")
    assert _volver_de(emitir) == ARMAR

    pantalla = cliente.get(emitir).text
    assert _barra(pantalla) == ARMAR
    accion = _accion(pantalla, "/administracion/facturacion/emitir")
    campos = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', pantalla))
    emitido = cliente.post(accion, data={**campos, "numero": "R-EJ-1"}, follow_redirects=False)
    assert emitido.status_code == 303

    remito = cliente.get(emitido.headers["location"]).text
    assert _barra(remito) == ARMAR

    # Y desde la lista, el link al remito ya emitido también vuelve a ella.
    de_nuevo = cliente.get(_href(cliente.get(ARMAR).text, "/administracion/facturacion/remito/")).text
    assert _barra(de_nuevo) == ARMAR


def test_FACTURACION_recibir_y_agregar_fotos_vuelve_a_Facturacion_con_su_rango(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    cliente = _cliente(monkeypatch, "administracion")
    facturacion = "/administracion/facturacion?desde=2026-09-01&hasta=2026-09-30"
    recibir = _href(cliente.get(facturacion).text, f"/administracion/facturacion/remito/{remito_id}/recibir")
    assert _volver_de(recibir) == facturacion

    pantalla = cliente.get(recibir).text
    assert _barra(pantalla) == facturacion
    ids = {r["pedido_renglon_id"]: r["id"] for r in d.remito_por_id(remito_id)["renglones"]}
    datos = {f"bultos_{ids[11]}": "5", f"kilos_{ids[11]}": "50", f"bultos_{ids[12]}": "3", f"kilos_{ids[12]}": "30"}
    with patch("app.main.subir_foto_comanda", return_value="remitos/EJ-1.jpg"):
        recibido = cliente.post(_accion(pantalla, f"/administracion/facturacion/remito/{remito_id}/recibir"),
                                data=datos, files={"fotos": ("r.jpg", _jpeg(), "image/jpeg")},
                                follow_redirects=False)
    remito = cliente.get(recibido.headers["location"]).text
    assert _barra(remito) == facturacion

    # Agregar una foto después: la redirección sigue sabiendo a dónde volver.
    with patch("app.main.subir_foto_comanda", return_value="remitos/EJ-2.jpg"):
        agregada = cliente.post(_accion(remito, f"/administracion/facturacion/remito/{remito_id}/fotos"),
                                files={"fotos": ("r.jpg", _jpeg(), "image/jpeg")}, follow_redirects=False)
    assert _barra(cliente.get(agregada.headers["location"].split("#")[0]).text) == facturacion


def test_SIN_volver_cada_pantalla_vuelve_a_su_lista_de_siempre_y_NO_sale_del_sitio(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    cliente = _cliente(monkeypatch, "administracion")
    assert _barra(cliente.get(f"/administracion/facturacion/remito/{remito_id}").text) == "/administracion/facturacion"
    for malo in ("https://otro.sitio/x", "//otro.sitio/x", "/\\otro.sitio"):
        pagina = cliente.get(f"/administracion/facturacion/remito/{remito_id}", params={"volver": malo}).text
        assert _barra(pagina) == "/administracion/facturacion", malo


# --- vales y vacíos (el galpón de los vales) ---------------------------------

from tests import test_vales_a_cobrar as _vales  # noqa: E402

galpon_de_vales = _vales.base


def _vale_anterior(sql):
    (vid,), = sql("INSERT INTO vales_a_cobrar (origen, proveedor_id, fecha, importe, numero) "
                  "VALUES ('anterior_al_sistema', 1, '2026-09-10', 3000, 'V-EJ') RETURNING id")
    return vid


def test_VALE_desde_dos_listas_vuelve_a_la_suya_y_cobrarlo_no_la_pierde(galpon_de_vales, monkeypatch):
    d, sql = galpon_de_vales
    vid = _vale_anterior(sql)
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main._hoy_argentina", return_value=_vales.HOY):
        cartera = "/administracion/vales?estado=en_cartera&proveedor_id=1"
        vale = _href(cliente.get(cartera).text, f"/administracion/vales/{vid}?")
        assert _volver_de(vale) == cartera
        pantalla = cliente.get(vale).text
        assert _barra(pantalla) == cartera
        # Cobrarlo no pierde la lista: la redirección sigue sabiendo a dónde volver.
        cobrado = cliente.post(_accion(pantalla, f"/administracion/vales/{vid}/cobrar"),
                               data={"fecha": "2026-11-30", "importe_cobrado": "3000"}, follow_redirects=False)
        assert cobrado.status_code == 303
        assert _volver_de(cobrado.headers["location"].split("#")[0]) == cartera
        # Ya cobrado, sale en Movimientos de vales, y desde ahí vuelve a Movimientos.
        movimientos = "/administracion/vales/movimientos?desde=2026-11-01&hasta=2026-12-01&proveedor_id=1"
        vale = _href(cliente.get(movimientos).text, f"/administracion/vales/{vid}?")
        assert _barra(cliente.get(vale).text) == movimientos


def test_VACIOS_desde_Movimientos_vuelve_a_Movimientos_con_sus_filtros(galpon_de_vales, monkeypatch):
    d, sql = galpon_de_vales
    sql("INSERT INTO vacios_deposito_ajustes (proveedor_id, cantidad, motivo, stock_sistema) "
        "VALUES (1, -3, 'EJ rotos', 150)")
    cliente = _cliente(monkeypatch, "administracion")
    lista = "/administracion/vacios/movimientos?desde=2026-09-15&hasta=2026-12-01&proveedor_id=1"
    proveedor = _href(cliente.get(lista).text, "/administracion/vacios/1?abrir=movimientos")
    assert _volver_de(proveedor) == lista
    pantalla = cliente.get(proveedor).text
    assert _barra(pantalla) == lista
    # Y sin venir de Movimientos, sigue volviendo a Vacíos.
    assert _barra(cliente.get("/administracion/vacios/1").text) == "/administracion/vacios"


# --- stock, movimientos, pedidos, guías R, fichas, compras, tareas ------------

from tests import test_devoluciones_al_proveedor as _devol  # noqa: E402

galpon_de_stock = _devol.base


def test_STOCK_REMANENTE_el_articulo_y_la_porcion_vuelven_con_fecha_Y_tipo(galpon_de_stock, monkeypatch):
    d, sql, _ = galpon_de_stock
    cliente = _cliente(monkeypatch, "administracion")
    lista = "/administracion/stock/remanente?fecha=2026-09-20&tipo=sueltos"
    with patch("app.main._hoy_argentina", return_value=_devol.HOY):
        pagina = cliente.get(lista).text
        porcion = _href(pagina, "/administracion/stock/remanente/porcion")
        assert _volver_de(porcion) == lista
        extracto = cliente.get(porcion).text
        volver = [_html.unescape(h) for h in re.findall(r'href="([^"]+)"', extracto) if "tipo=sueltos" in _html.unescape(h)]
        assert lista in volver, "el extracto perdió el tipo"


def test_MOVIMIENTOS_del_deposito_el_Resumen_proveedores_vuelve_con_todos_los_filtros(galpon_de_stock, monkeypatch):
    d, sql, _ = galpon_de_stock
    cliente = _cliente(monkeypatch, "administracion")
    lista = "/administracion/ingresos?desde=2026-09-01&hasta=2026-09-30&tipo=entrada&sector=deposito"
    resumen = _href(cliente.get(lista).text, "/administracion/ingresos/pagar")
    assert _volver_de(resumen) == lista
    assert _barra(cliente.get(resumen).text) == lista


def test_GUIAS_R_volver_a_la_lista_conserva_el_rango(galpon_de_stock, monkeypatch):
    d, sql, _ = galpon_de_stock
    sql("""insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
               bultos_segunda, bultos_merma, costo_por_bulto_primera) overriding system value
           values (5, 1, '2026-09-08', 2, 2, 0, 0, 100)""")
    sql("insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos) values (5, 'compra', 11, 2)")
    cliente = _cliente(monkeypatch, "administracion")
    una = cliente.get("/administracion/stock/guias-r?fecha_desde=2026-09-01&fecha_hasta=2026-09-30&guia=5").text
    assert _href(una, "/administracion/stock/guias-r?") == "/administracion/stock/guias-r?fecha_desde=2026-09-01&fecha_hasta=2026-09-30"


def test_TAREAS_al_guardar_vuelve_a_la_lista_FILTRADA(galpon_de_stock, monkeypatch):
    d, sql, _ = galpon_de_stock
    cliente = _cliente(monkeypatch, "gerencia")
    lista = "/gerencia/tareas?desde=2026-09-01&hasta=2026-09-30&estado=pendiente"
    pantalla = cliente.get(lista).text
    accion = _accion(pantalla, "/gerencia/tareas")
    creada = cliente.post(accion, data={"titulo": "EJ tarea", "tipo": "una_vez", "sector": "gerencia",
                                        "vence_el": "2027-01-15"}, follow_redirects=False)
    assert creada.status_code == 303
    destino = creada.headers["location"]
    assert destino.startswith(lista + "&aviso=") or destino.startswith(lista + "&error="), destino


def test_COMPRA_la_barra_y_las_fotos_de_la_balanza_conservan_la_busqueda(galpon_de_stock, monkeypatch):
    d, sql, _ = galpon_de_stock
    cliente = _cliente(monkeypatch, "compras")
    filtros = "fecha_desde=2026-09-01&fecha_hasta=2026-09-30&proveedor_id=1"
    detalle = cliente.get(f"/compras/11/detalle?{filtros}").text
    assert _barra(detalle) == f"/compras/buscar?{filtros}"
    with patch("app.main.subir_foto_comanda", return_value="pesaje/EJ.jpg"):
        subida = cliente.post(_accion(detalle, "/compras/11/fotos-balanza"),
                              files={"fotos": ("b.jpg", _jpeg(), "image/jpeg")}, follow_redirects=False)
    assert subida.headers["location"].startswith(f"/compras/11/detalle?{filtros}&aviso=")


def test_FICHA_la_barra_vuelve_a_las_fichas_de_ESE_cliente(galpon_de_stock, monkeypatch):
    d, sql, _ = galpon_de_stock
    cliente = _cliente(monkeypatch, "compras")
    assert _barra(cliente.get("/fichas/1/editar").text) == "/fichas?cliente_id=1"
