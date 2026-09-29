"""Fotos de la pesada cargadas DESPUÉS de recibir, desde el detalle de la compra.

Dueño, 29/09: la foto de la balanza se sube al recepcionar, y hacía falta
poder sumarla más tarde (la que no se sacó en el momento, o una más), y
borrar una subida por error. Van a `fotos_recepcion`, igual que las de la
recepción, y no tocan ningún número de la compra.

De yapa se cerró un bug viejo: las miniaturas pedían
`/deposito/recepcion/{compra}/foto-balanza/ver`, que devuelve siempre la
ÚLTIMA foto. Con dos o más, todas se veían iguales, en el detalle y en
Corregir recepción. Ahora cada una pide la suya por id.
"""

import os
import re
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import PUERTA_COMPRAS, PUERTA_GERENCIA, app  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402
from tests.test_app import COMPRA_DETALLE_DE_PRUEBA  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

cliente = TestClient(app, base_url="https://testserver")

DOS_FOTOS = [
    {"id": 3, "foto_ruta": "pesaje/2026-09-08/balanza-30-1.jpg",
     "creado_en": datetime(2026, 9, 8, 12, 5, tzinfo=timezone.utc)},
    {"id": 7, "foto_ruta": "pesaje/2026-09-10/balanza-30-2.jpg",
     "creado_en": datetime(2026, 9, 10, 18, 40, tzinfo=timezone.utc)},
]


@pytest.fixture(autouse=True)
def _puerta_de_compras_abierta():
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta",
                                 "CLAVE_GERENCIA": "gerencia-secreta"}):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
        cliente.cookies.set(PUERTA_GERENCIA.cookie, PUERTA_GERENCIA.firma("gerencia-secreta"))
        try:
            yield
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)
            cliente.cookies.delete(PUERTA_GERENCIA.cookie)


def _detalle(fotos=DOS_FOTOS, url="/compras/30/detalle"):
    with patch("app.main.obtener_detalle_compra", return_value=COMPRA_DETALLE_DE_PRUEBA), \
         patch("app.main.listar_fotos_de_guia", return_value=[]), \
         patch("app.main.devoluciones_de_la_compra", return_value=[]), \
         patch("app.main.listar_fotos_de_recepcion", return_value=list(fotos)):
        return cliente.get(url)


def _tarjeta_de_pesaje(marcado):
    return marcado[marcado.index('id="pesaje"'):]


def _foto(nombre="p.jpg"):
    return ("fotos", (nombre, b"x", "image/jpeg"))


# ---------------------------------------------------------------- la pantalla

def test_cada_miniatura_pide_SU_foto_con_su_FECHA_y_HORA():
    """Con la ruta vieja, las dos pedían la última y se veían iguales."""
    respuesta = _detalle()
    assert respuesta.status_code == 200
    tarjeta = _tarjeta_de_pesaje(respuesta.text.split("</style>")[-1])
    assert re.findall(r'<img src="([^"]+)"', tarjeta) == [
        "/deposito/recepcion/30/foto-balanza/3/ver", "/deposito/recepcion/30/foto-balanza/7/ver"]
    assert "/foto-balanza/ver" not in tarjeta
    # En hora argentina: 12:05 UTC son las 09:05.
    assert re.findall(r'<span class="foto-pesada-hora">([^<]+)</span>', tarjeta) == [
        "08/09/2026 09:05", "10/09/2026 15:40"]


def test_cada_foto_se_BORRA_por_su_id_y_pidiendo_confirmacion():
    tarjeta = _tarjeta_de_pesaje(_detalle().text.split("</style>")[-1])
    formularios = re.findall(r'<form method="post" action="([^"]+/borrar)"\s+onsubmit="([^"]+)"', tarjeta)
    assert [f[0] for f in formularios] == ["/compras/30/fotos-balanza/3/borrar",
                                           "/compras/30/fotos-balanza/7/borrar"]
    assert all("confirm(" in f[1] for f in formularios)


def test_el_boton_AGREGAR_acepta_VARIAS_fotos_de_camara_o_galeria():
    tarjeta = _tarjeta_de_pesaje(_detalle(fotos=[]).text.split("</style>")[-1])
    assert "Esta compra no tiene foto de la balanza." in tarjeta
    assert 'action="/compras/30/fotos-balanza"' in tarjeta
    campo = re.search(r'<input type="file" name="fotos"[^>]*>', tarjeta).group(0)
    assert 'accept="image/*"' in campo and "multiple" in campo
    # Con `capture`, el celular abre la cámara directo y no deja elegir de la galería.
    assert "capture" not in campo
    assert ">＋ Agregar foto de pesada<" in tarjeta


def test_el_ERROR_de_una_subida_se_VE_en_el_detalle():
    # El texto entero y no un corte por `</style>`: el parcial de las fotos
    # de la guía trae su propio <style> y el corte se lleva de más (corolario 50).
    assert '<div class="error">No es una foto</div>' in _detalle(
        url="/compras/30/detalle?error=No+es+una+foto").text


def test_CORREGIR_RECEPCION_tambien_pide_cada_foto_por_su_id():
    """La otra copia del mismo loop (corolario 2)."""
    compra = dict(COMPRA_DETALLE_DE_PRUEBA, unidad_compra="kilo")
    with patch("app.main.obtener_detalle_compra", return_value=compra), \
         patch("app.main.uso_del_lote_de_la_compra", return_value={"guias": 0, "armados": 0}), \
         patch("app.main.listar_fotos_de_guia", return_value=[]), \
         patch("app.main.frenos_para_cambiar_proveedor", return_value=[]), \
         patch("app.main.listar_proveedores", return_value=[]), \
         patch("app.main.listar_fotos_de_recepcion", return_value=list(DOS_FOTOS)), \
         patch("app.main.dependencias_del_lote_de_compra", return_value=None), \
         patch("app.main.listar_clientes", return_value=[]), \
         patch("app.main.marca_en_origen_de_la_compra",
               return_value={"ficha_id": None, "codigo_cliente": None, "envase_nombre": None,
                             "cliente_nombre": None, "guias_vivas": []}):
        respuesta = cliente.get("/gerencia/compras/30/corregir-recepcion")
    # El 200 va primero: sin la cookie, la pantalla de la clave también da un
    # `[]` prolijo y el test mediría otra pantalla (corolario 53).
    assert respuesta.status_code == 200
    texto = respuesta.text
    assert re.findall(r'<img src="(/deposito/recepcion/30/foto-balanza/[^"]+)"', texto) == [
        "/deposito/recepcion/30/foto-balanza/3/ver", "/deposito/recepcion/30/foto-balanza/7/ver"]


# ---------------------------------------------------------------- las rutas

def test_SUBIR_dos_fotos_las_guarda_a_las_DOS_en_esta_compra():
    with patch("app.main.obtener_compra", return_value={"id": 30}), \
         patch("app.main._comprimir_foto_jpeg", return_value=b"jpg"), \
         patch("app.main.subir_foto_comanda", side_effect=["pesaje/a.jpg", "pesaje/b.jpg"]) as subir, \
         patch("app.main.agregar_foto_recepcion") as agregar:
        respuesta = cliente.post("/compras/30/fotos-balanza",
                                 files=[_foto("a.jpg"), _foto("b.jpg")], follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/compras/30/detalle?")
    assert "2+fotos+de+pesada+agregadas" in respuesta.headers["location"]
    assert [c.kwargs["prefijo"] for c in subir.call_args_list] == ["pesaje", "pesaje"]
    assert [c.args for c in agregar.call_args_list] == [(30, "pesaje/a.jpg"), (30, "pesaje/b.jpg")]


def test_si_UNA_no_es_foto_no_se_sube_NINGUNA():
    """Se valida todo antes de subir la primera: una tanda a medias es peor que
    ninguna, porque el que la cargó cree que entraron todas."""
    with patch("app.main.obtener_compra", return_value={"id": 30}), \
         patch("app.main._comprimir_foto_jpeg", side_effect=[b"jpg", None]), \
         patch("app.main.subir_foto_comanda") as subir, \
         patch("app.main.agregar_foto_recepcion") as agregar:
        respuesta = cliente.post("/compras/30/fotos-balanza",
                                 files=[_foto("a.jpg"), _foto("planilla.xlsx")], follow_redirects=False)
    assert respuesta.status_code == 303
    assert "error=" in respuesta.headers["location"] and "planilla.xlsx" in respuesta.headers["location"]
    assert not subir.called and not agregar.called


def test_una_compra_que_NO_EXISTE_da_404_y_no_sube_nada():
    with patch("app.main.obtener_compra", return_value=None), \
         patch("app.main.subir_foto_comanda") as subir:
        respuesta = cliente.post("/compras/999/fotos-balanza", files=[_foto()])
    assert respuesta.status_code == 404
    assert not subir.called


def test_VER_una_foto_de_OTRA_compra_es_404():
    with patch("app.main.listar_fotos_de_recepcion", return_value=list(DOS_FOTOS)), \
         patch("app.main.obtener_url_foto", return_value="https://firmada/x") as firmar:
        buena = cliente.get("/deposito/recepcion/30/foto-balanza/7/ver", follow_redirects=False)
        ajena = cliente.get("/deposito/recepcion/30/foto-balanza/99/ver", follow_redirects=False)
    assert buena.status_code == 307 and buena.headers["location"] == "https://firmada/x"
    assert firmar.call_args.args == ("pesaje/2026-09-10/balanza-30-2.jpg",)
    assert ajena.status_code == 404


def test_BORRAR_saca_la_fila_y_despues_el_archivo():
    with patch("app.main.borrar_foto_recepcion", return_value="pesaje/b.jpg") as borrar, \
         patch("app.main.borrar_foto_comanda") as del_storage:
        respuesta = cliente.post("/compras/30/fotos-balanza/7/borrar", follow_redirects=False)
    assert respuesta.status_code == 303
    assert borrar.call_args.args == (30, 7)
    assert del_storage.call_args.args == ("pesaje/b.jpg",)


def test_BORRAR_una_foto_que_no_es_de_esta_compra_es_404_y_no_toca_el_storage():
    with patch("app.main.borrar_foto_recepcion", return_value=None), \
         patch("app.main.borrar_foto_comanda") as del_storage:
        respuesta = cliente.post("/compras/30/fotos-balanza/99/borrar", follow_redirects=False)
    assert respuesta.status_code == 404
    assert not del_storage.called


def test_las_rutas_que_ESCRIBEN_estan_detras_de_la_clave_de_COMPRAS():
    cliente.cookies.delete(PUERTA_COMPRAS.cookie)
    with patch("app.main.borrar_foto_recepcion") as borrar, \
         patch("app.main.agregar_foto_recepcion") as agregar:
        subir = cliente.post("/compras/30/fotos-balanza", files=[_foto()], follow_redirects=False)
        sacar = cliente.post("/compras/30/fotos-balanza/7/borrar", follow_redirects=False)
    assert subir.status_code != 303 and sacar.status_code != 303
    assert "clave" in subir.text.lower() and "clave" in sacar.text.lower()
    assert not borrar.called and not agregar.called


# ---------------------------------------------------------------- contra la base

@pytest.fixture(scope="module")
def base_real():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def dos_compras(base_real, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", base_real)
    from datetime import date
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

    (sufijo,), = sql("SELECT nextval(pg_get_serial_sequence('articulos','id'))")
    (articulo,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id",
                       (f"EJEMPLO Art {sufijo}",))
    (proveedor,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) RETURNING id",
                        (f"EJEMPLO Prov {sufijo}", f"N02P{sufijo % 100:02d}"))
    ids = []
    for _ in range(2):
        d.crear_compra(date.today(), articulo, proveedor, 10, 16, 160, None, 5000, None,
                       "Carro", None, segunda_por_cajon=None, codigo_llegada=None)
        (compra_id,), = sql("SELECT max(id) FROM compras")
        ids.append(compra_id)
    sql("UPDATE compras SET estado = 'recepcionado', procesada_el = now(), "
        "cantidad_cajones_real = 10 WHERE id = ANY(%s)", (ids,))
    return d, sql, ids


def test_contra_la_BASE_sumar_y_borrar_no_cambia_NINGUN_numero_de_la_compra(dos_compras):
    """Con la compra YA recepcionada, que es el caso del pedido. La fila entera
    de `compras` antes y después tiene que ser la misma."""
    d, sql, (compra, otra) = dos_compras
    fila_antes = sql("SELECT * FROM compras WHERE id = %s", (compra,))
    with patch("app.main._comprimir_foto_jpeg", return_value=b"jpg"), \
         patch("app.main.subir_foto_comanda", side_effect=[f"pesaje/{compra}-a.jpg",
                                                            f"pesaje/{compra}-b.jpg"]), \
         patch("app.main.borrar_foto_comanda") as del_storage:
        subir = cliente.post(f"/compras/{compra}/fotos-balanza",
                             files=[_foto("a.jpg"), _foto("b.jpg")], follow_redirects=False)
        assert subir.status_code == 303, subir.text[:300]
        fotos = d.listar_fotos_de_recepcion(compra)
        assert [f["foto_ruta"] for f in fotos] == [f"pesaje/{compra}-a.jpg", f"pesaje/{compra}-b.jpg"]

        # Un id de OTRA compra no borra nada, ni del storage.
        ajena = cliente.post(f"/compras/{otra}/fotos-balanza/{fotos[0]['id']}/borrar",
                             follow_redirects=False)
        assert ajena.status_code == 404
        assert len(d.listar_fotos_de_recepcion(compra)) == 2
        assert not del_storage.called

        sacar = cliente.post(f"/compras/{compra}/fotos-balanza/{fotos[0]['id']}/borrar",
                             follow_redirects=False)
        assert sacar.status_code == 303
    assert [f["foto_ruta"] for f in d.listar_fotos_de_recepcion(compra)] == [f"pesaje/{compra}-b.jpg"]
    assert del_storage.call_args.args == (f"pesaje/{compra}-a.jpg",)
    assert sql("SELECT * FROM compras WHERE id = %s", (compra,)) == fila_antes


def test_en_el_NAVEGADOR_a_390px_tres_fotos_ENVUELVEN_y_no_scrollean_de_costado():
    """El efecto y no la clase (corolario 32): la tira de la guía scrollea de
    costado a propósito, y la de la pesada envuelve porque cada foto lleva su
    hora y su botón. Con el CSS de la guía ganando, esto desborda 37px."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    tres = DOS_FOTOS + [dict(DOS_FOTOS[0], id=9)]
    html = _detalle(fotos=tres).text
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        dibujadas = pagina.eval_on_selector_all(".foto-pesada", "es => es.length")
        sobrante = pagina.eval_on_selector(".tira-pesada", "e => e.scrollWidth - e.clientWidth")
        alturas = pagina.eval_on_selector_all(
            ".borrar-pesada", "es => es.map(e => e.getBoundingClientRect().height)")
        navegador.close()
    assert dibujadas == 3
    assert sobrante <= 1
    assert alturas and min(alturas) >= 44
