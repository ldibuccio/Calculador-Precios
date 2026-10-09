# -*- coding: utf-8 -*-
"""GUÍAS MERCADERÍA (dueño, 09/10): Buscar compras desde Administración.

La misma pantalla de Compras —buscar cualquier guía, entrar al detalle y ver
todo lo que pasó con ella— y SUMAR fotos de la comanda y de la pesada. Nada
que cambie un dato: ni Editar, ni Vino armada, ni Eliminar, ni borrar fotos,
ni lo de Gerencia.

EL BLOQUEO ESTÁ EN EL SERVIDOR, no solo en el botón:
  · bajo /administracion/guias-mercaderia existen SOLO las rutas decididas
    (el conjunto ENCONTRADO contra el DECIDIDO, en las dos direcciones);
  · con la cookie de Administración, las rutas que escriben de /compras y de
    /gerencia piden su clave, y la función que guarda NO SE LLAMA;
  · una ruta de editar armada a mano bajo el prefijo de Administración no
    existe.
"""
import os
import re
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import PUERTA_ADMINISTRACION, PUERTA_COMPRAS, app  # noqa: E402
from tests.test_app import (  # noqa: E402
    ARTICULOS_CON_UNIDAD_COMPRA,
    COMPRA_DETALLE_DE_PRUEBA,
    COMPRAS_BUSQUEDA_DE_PRUEBA,
    PROVEEDORES_DE_PRUEBA,
)

CLAVES = {"CLAVE_ADMINISTRACION": "admin-secreta", "CLAVE_COMPRAS": "compras-secreta",
          "CLAVE_GERENCIA": "gerencia-secreta"}
BASE = "/administracion/guias-mercaderia"
FOTO_GUIA = [{"id": 11, "foto_ruta": "comanda/2026-10-01/guia-5-1.jpg"}]
FOTO_PESADA = [{"id": 3, "foto_ruta": "pesaje/2026-10-01/balanza-30-1.jpg", "movimiento_id": None,
                "creado_en": datetime(2026, 10, 1, 12, 5, tzinfo=timezone.utc)}]


def _cliente(*sectores):
    cliente = TestClient(app, base_url="https://testserver")
    for puerta, clave in ((PUERTA_ADMINISTRACION, "admin-secreta"), (PUERTA_COMPRAS, "compras-secreta")):
        if puerta.sector in sectores:
            cliente.cookies.set(puerta.cookie, puerta.firma(clave))
    return cliente


def _lista(cliente, url):
    compras = [dict(COMPRAS_BUSQUEDA_DE_PRUEBA[0], id=1, tiene_comanda=True, tiene_pesaje=True)]
    with patch.dict(os.environ, CLAVES), \
            patch("app.main.listar_todos_los_proveedores", return_value=PROVEEDORES_DE_PRUEBA), \
            patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA), \
            patch("app.main.buscar_compras", return_value=compras):
        return cliente.get(url)


def _detalle(cliente, url):
    compra = dict(COMPRA_DETALLE_DE_PRUEBA, guia_id=5)
    with patch.dict(os.environ, CLAVES), \
            patch("app.main.obtener_detalle_compra", return_value=compra), \
            patch("app.main.listar_fotos_de_guia", return_value=FOTO_GUIA), \
            patch("app.main.devoluciones_de_la_compra", return_value=[]), \
            patch("app.main.a_donde_fue_la_compra", return_value=None), \
            patch("app.main.listar_fotos_de_recepcion", return_value=FOTO_PESADA):
        return cliente.get(url)


def _cuerpo(respuesta):
    return respuesta.text.split("<body", 1)[1]


def _formularios(html):
    """Los formularios de la pantalla, sin el candado de la barra (cerrar la sesión no escribe datos)."""
    return [f for f in re.findall(r'<form\b[^>]*\bmethod="(get|post)"[^>]*\baction="([^"]*)"', html)
            if not f[1].endswith("/bloquear")]


def _links(html):
    return re.findall(r'<a\b[^>]*\bhref="([^"]*)"', html)


def test_la_LISTA_de_Administracion_busca_y_lleva_al_detalle_sin_nada_que_escriba():
    respuesta = _lista(_cliente("administracion"), BASE)
    assert respuesta.status_code == 200
    html = _cuerpo(respuesta)
    assert _formularios(html) == [("get", BASE)]                      # solo el de los filtros
    assert f'href="{BASE}/1/detalle?' in html and f'href="{BASE}/1/foto"' in html
    assert f'href="{BASE}/exportar-pdf?' in html and f'href="{BASE}/exportar-excel?' in html
    assert [l for l in _links(html) if l.startswith(("/compras", "/gerencia"))] == []
    assert 'class="check-fila"' not in html and "Vino armada" not in html and ">Eliminar<" not in html
    # El RIVAL: la misma pantalla en Compras sí escribe.
    compras = _cuerpo(_lista(_cliente("compras"), "/compras/buscar"))
    assert ("post", "/compras/1/eliminar") in _formularios(compras) and 'class="check-fila"' in compras


def test_el_DETALLE_de_Administracion_solo_SUMA_fotos():
    respuesta = _detalle(_cliente("administracion"), f"{BASE}/30/detalle?fecha_desde=2026-10-01")
    assert respuesta.status_code == 200
    html = _cuerpo(respuesta)
    assert sorted(_formularios(html)) == [
        ("post", f"{BASE}/30/fotos"), ("post", f"{BASE}/30/fotos-balanza?fecha_desde=2026-10-01")]
    assert f'src="{BASE}/30/fotos/11/ver"' in html                       # la comanda se ve
    assert 'src="/deposito/recepcion/30/foto-balanza/3/ver"' in html     # y la pesada
    assert [l for l in _links(html) if l.startswith(("/compras", "/gerencia"))] == []
    assert ">Editar<" not in html and ">Borrar<" not in html
    assert f'href="{BASE}?fecha_desde=2026-10-01">Volver a Guías mercadería<' in html
    # El RIVAL: el detalle de Compras tiene Editar y los dos Borrar.
    compras = _cuerpo(_detalle(_cliente("compras"), "/compras/30/detalle"))
    acciones = [a for _, a in _formularios(compras)]
    assert "/compras/30/fotos/11/borrar" in acciones and "/compras/30/fotos-balanza/3/borrar" in acciones
    assert ">Editar<" in compras


# Lo único que existe bajo el prefijo de Administración. Una ruta nueva acá
# tiene que entrar en esta lista A PROPÓSITO.
RUTAS_DECIDIDAS = {
    ("GET", BASE), ("GET", f"{BASE}/exportar-pdf"), ("GET", f"{BASE}/exportar-excel"),
    ("GET", BASE + "/{compra_id}/detalle"), ("GET", BASE + "/{compra_id}/foto"),
    ("GET", BASE + "/{compra_id}/fotos/{foto_id}/ver"),
    ("POST", BASE + "/{compra_id}/fotos"), ("POST", BASE + "/{compra_id}/fotos-balanza"),
}


def test_bajo_el_prefijo_existen_SOLO_las_rutas_DECIDIDAS():
    encontradas = {(metodo, ruta.path) for ruta in app.routes if getattr(ruta, "path", "").startswith(BASE)
                   for metodo in getattr(ruta, "methods", set()) if metodo != "HEAD"}
    assert encontradas - RUTAS_DECIDIDAS == set(), "ruta nueva en Guías mercadería sin decidir"
    assert RUTAS_DECIDIDAS - encontradas == set()


def test_con_la_cookie_de_ADMINISTRACION_editar_DEVUELVE_ERROR_y_no_toca_nada():
    """Aunque alguien arme la llamada a mano."""
    cliente = _cliente("administracion")
    # `obtener_compra` es lo PRIMERO que hace Editar: si el pedido llegara a
    # la función, se llamaría. Que no se llame dice que el servidor lo frenó antes.
    guardar, eliminar, borrar_foto = MagicMock(), MagicMock(), MagicMock()
    with patch.dict(os.environ, CLAVES), patch("app.main.obtener_compra", guardar), \
            patch("app.main.eliminar_compra", eliminar), patch("app.main.borrar_foto_guia", borrar_foto):
        respuestas = {
            "editar en Compras": cliente.post("/compras/30/editar", data={"importe": "1"}, follow_redirects=False),
            "eliminar en Compras": cliente.post("/compras/30/eliminar", follow_redirects=False),
            "borrar foto en Compras": cliente.post("/compras/30/fotos/11/borrar", follow_redirects=False),
            "editar en Gerencia": cliente.post("/gerencia/compras/30/editar", follow_redirects=False),
            "editar armado a mano": cliente.post(f"{BASE}/30/editar", data={"importe": "1"}, follow_redirects=False),
            "borrar foto armado a mano": cliente.post(f"{BASE}/30/fotos/11/borrar", follow_redirects=False),
        }
    estados = {que: r.status_code for que, r in respuestas.items()}
    assert estados["editar en Compras"] == estados["eliminar en Compras"] == estados["borrar foto en Compras"] == 401
    assert estados["editar en Gerencia"] in (401, 404, 405)
    assert estados["editar armado a mano"] in (404, 405) and estados["borrar foto armado a mano"] in (404, 405)
    assert not guardar.called and not eliminar.called and not borrar_foto.called


def test_desde_ADMINISTRACION_se_SUMAN_las_fotos_y_vuelve_a_su_detalle():
    cliente = _cliente("administracion")
    compra = dict(COMPRA_DETALLE_DE_PRUEBA, guia_id=5)
    with patch.dict(os.environ, CLAVES), patch("app.main.obtener_compra", return_value=compra), \
            patch("app.main._comprimir_foto_jpeg", return_value=b"jpg"), \
            patch("app.main.subir_foto_comanda", return_value="ruta.jpg") as subir, \
            patch("app.main.agregar_foto_guia") as a_la_guia, \
            patch("app.main.agregar_foto_recepcion") as a_la_pesada:
        comanda = cliente.post(f"{BASE}/30/fotos", files={"archivo": ("c.jpg", b"x", "image/jpeg")},
                               data={"query_filtros": "fecha_desde=2026-10-01"}, follow_redirects=False)
        pesada = cliente.post(f"{BASE}/30/fotos-balanza?fecha_desde=2026-10-01",
                              files=[("fotos", ("p.jpg", b"x", "image/jpeg"))], follow_redirects=False)
    assert comanda.status_code == pesada.status_code == 303
    assert comanda.headers["location"] == f"{BASE}/30/detalle?fecha_desde=2026-10-01"
    assert pesada.headers["location"].startswith(f"{BASE}/30/detalle?fecha_desde=2026-10-01")
    a_la_guia.assert_called_once_with(5, "ruta.jpg")
    a_la_pesada.assert_called_once_with(30, "ruta.jpg")
    assert subir.call_count == 2


def test_sin_la_cookie_de_ADMINISTRACION_Guias_mercaderia_pide_la_clave():
    with patch.dict(os.environ, CLAVES):
        sin = TestClient(app, base_url="https://testserver")
        assert sin.get(BASE, follow_redirects=False).status_code == 401
        assert sin.post(f"{BASE}/30/fotos-balanza", follow_redirects=False).status_code == 401
