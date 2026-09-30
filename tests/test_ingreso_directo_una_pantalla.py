"""Ingreso directo en UNA pantalla, con las fotos de la pesada (dueño, 30/09).

Hasta ese día eran dos pantallas: "Ingresar Mercadería" para elegir el
proveedor (`POST /deposito/ingresar/proveedor`) y otra para cargar la
mercadería. Ahora es una sola, como la carga manual de Compras: proveedor
arriba, mercadería abajo, las fotos de la pesada y un Guardar.

Las fotos son LAS MISMAS que las del detalle de la compra y de Recepción
(`fotos_recepcion`): lo que sube Depósito se ve desde Compras y al revés.

La ruta va mockeada; la escritura corre contra Postgres (corolario 89), y
la pantalla, en un navegador (el atributo es la intención, no el efecto).
Los nombres son de EJEMPLO.
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
from tests.test_app import (  # noqa: E402
    ARTICULO_KILO_DE_PRUEBA,
    ARTICULOS_CON_UNIDAD_COMPRA,
    HOY_DE_PRUEBA,
    cliente,
)

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

PROVEEDOR = {"id": 200, "codigo_puesto": "N07P41", "nombre": "EJEMPLO Saturno", "activo": True}
PARECIDO = {"id": 300, "codigo_puesto": "N09P41", "nombre": "EJEMPLO FRUTAS S.R.L.", "activo": True}
DATOS = {"codigo_puesto": "N07P41", "nombre": "EJEMPLO Saturno", "accion": "agregar",
         "articulo_id": "5", "cantidad_cajones": "10", "contenido_por_cajon": "18",
         "tipo_retiro": "Clark"}


def _jpeg():
    from PIL import Image
    salida = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 100, 50)).save(salida, format="JPEG")
    return salida.getvalue()


def _post(datos=None, fotos=None, *, existente=PROVEEDOR, abm=(PROVEEDOR,), crear=None):
    """El POST con lo que la ruta lee de la base mockeado. `existente` es lo
    que contesta la búsqueda por código: None es un código que no es de nadie."""
    rutas = iter(f"pesaje/2026-09-30/foto-{i}.jpg" for i in range(1, 10))
    with patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA), \
         patch("app.main.buscar_proveedor_por_codigo", return_value=existente), \
         patch("app.main.listar_proveedores_para_abm", return_value=list(abm)), \
         patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(200, False)) as ocrear, \
         patch("app.main.asociar_codigo_a_proveedor", return_value="EJEMPLO FRUTAS S.R.L.") as asociar, \
         patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA), \
         patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA), \
         patch("app.main.listar_proveedores", return_value=[PROVEEDOR]), \
         patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]), \
         patch("app.main.subir_foto_comanda", side_effect=lambda *a, **k: next(rutas)) as subir, \
         patch("app.main.borrar_foto_comanda") as borrar, \
         patch("app.main.crear_compra", side_effect=crear) as crear_compra:
        respuesta = cliente.post("/deposito/ingresar", data=dict(DATOS, **(datos or {})),
                                 files=fotos or None, follow_redirects=False)
    return respuesta, {"crear_compra": crear_compra, "subir": subir, "borrar": borrar,
                       "obtener_o_crear": ocrear, "asociar": asociar}


# --- las fotos de la pesada --------------------------------------------------

def test_las_FOTOS_se_suben_y_viajan_con_la_compra_en_UNA_escritura():
    fotos = [("fotos", ("uno.jpg", _jpeg(), "image/jpeg")), ("fotos", ("dos.jpg", _jpeg(), "image/jpeg"))]
    respuesta, m = _post(fotos=fotos)
    assert respuesta.status_code == 303
    assert m["subir"].call_count == 2
    assert m["crear_compra"].call_args.kwargs["fotos_pesada"] == [
        "pesaje/2026-09-30/foto-1.jpg", "pesaje/2026-09-30/foto-2.jpg"]
    assert "Con+2+fotos+de+la+pesada" in respuesta.headers["location"]


def test_SIN_fotos_se_guarda_igual_porque_no_son_obligatorias():
    respuesta, m = _post()
    assert respuesta.status_code == 303
    assert m["crear_compra"].call_args.kwargs["fotos_pesada"] == []
    m["subir"].assert_not_called()
    assert "pesada" not in respuesta.headers["location"]


def test_un_campo_de_archivo_VACIO_no_es_una_foto():
    """El navegador manda el campo aunque nadie haya elegido nada."""
    respuesta, m = _post(fotos=[("fotos", ("", b"", "application/octet-stream"))])
    assert respuesta.status_code == 303
    assert m["crear_compra"].call_args.kwargs["fotos_pesada"] == []


def test_un_archivo_que_NO_es_foto_frena_todo_antes_de_escribir():
    fotos = [("fotos", ("uno.jpg", _jpeg(), "image/jpeg")),
             ("fotos", ("planilla.pdf", b"%PDF-1.4 no es foto", "application/pdf"))]
    respuesta, m = _post(fotos=fotos)
    assert respuesta.status_code == 400
    assert "«planilla.pdf» no es una foto" in respuesta.text
    m["subir"].assert_not_called()
    m["obtener_o_crear"].assert_not_called()
    m["crear_compra"].assert_not_called()


def test_si_la_compra_REBOTA_las_fotos_ya_subidas_se_borran_del_Storage():
    fotos = [("fotos", ("uno.jpg", _jpeg(), "image/jpeg")), ("fotos", ("dos.jpg", _jpeg(), "image/jpeg"))]
    respuesta, m = _post(fotos=fotos, crear=Exception("se cayó la base"))
    assert respuesta.status_code == 500
    assert "No se pudo guardar la compra" in respuesta.text
    assert [c.args[0] for c in m["borrar"].call_args_list] == [
        "pesaje/2026-09-30/foto-1.jpg", "pesaje/2026-09-30/foto-2.jpg"]
    # Y lo dice: el que corrige no puede creer que las fotos siguen ahí.
    assert "Las fotos de la pesada no se guardaron: agregalas de nuevo." in respuesta.text


def test_un_rebote_por_un_campo_AVISA_que_las_fotos_hay_que_volver_a_agregarlas():
    fotos = [("fotos", ("uno.jpg", _jpeg(), "image/jpeg"))]
    respuesta, m = _post({"cantidad_cajones": ""}, fotos=fotos)
    assert respuesta.status_code == 400
    assert "Las fotos de la pesada no se guardaron: agregalas de nuevo." in respuesta.text
    # Y lo demás vuelve cargado (corolario 43), el proveedor incluido.
    assert re.search(r'id="codigo_puesto" name="codigo_puesto"[^>]*value="N07P41"', respuesta.text, re.S)
    assert re.search(r'id="nombre" name="nombre"[^>]*value="EJEMPLO Saturno"', respuesta.text, re.S)
    assert re.search(r'name="contenido_por_cajon"[^>]*value="18"', respuesta.text, re.S)


# --- el modal de nombres parecidos --------------------------------------------

def test_un_codigo_NUEVO_con_un_nombre_PARECIDO_frena_y_pregunta():
    """La misma guarda que Compras → Proveedores, en el POST: un formulario
    armado a mano sin decidir pasa por el modal igual."""
    respuesta, m = _post({"codigo_puesto": "N07P50", "nombre": "EJEMPLO Frutas"},
                         existente=None, abm=(PARECIDO,))
    assert respuesta.status_code == 409
    marcado = re.sub(r"<style>.*?</style>|<script>.*?</script>", " ", respuesta.text, flags=re.S)
    assert '<div class="modal-fondo visible" id="modal-parecidos">' in marcado
    assert 'data-mismo="300">Es EJEMPLO FRUTAS S.R.L. (N09P41): sumarle el puesto N07P50<' in marcado
    m["obtener_o_crear"].assert_not_called()
    m["crear_compra"].assert_not_called()


def test_sin_parecidos_el_modal_NO_sale():
    respuesta, _ = _post({"cantidad_cajones": ""}, existente=None, abm=(PROVEEDOR,))
    assert respuesta.status_code == 400
    assert '<div class="modal-fondo" id="modal-parecidos">' in respuesta.text


def test_un_codigo_que_YA_ES_de_alguien_no_pregunta_aunque_el_nombre_se_parezca():
    respuesta, m = _post({"nombre": "EJEMPLO Frutas"}, existente=PROVEEDOR, abm=(PARECIDO,))
    assert respuesta.status_code == 303
    m["asociar"].assert_not_called()
    m["crear_compra"].assert_called_once()


def test_ES_OTRO_carga_el_proveedor_nuevo_sin_asociar_nada():
    respuesta, m = _post({"codigo_puesto": "N07P50", "nombre": "EJEMPLO Frutas", "es_otro": "1"},
                         existente=None, abm=(PARECIDO,))
    assert respuesta.status_code == 303
    m["asociar"].assert_not_called()
    m["obtener_o_crear"].assert_called_once_with("N07P50", "EJEMPLO Frutas")
    assert m["crear_compra"].call_args.kwargs["codigo_llegada"] == "N07P50"


def test_ES_EL_MISMO_le_suma_el_puesto_y_la_compra_llega_por_ese_puesto():
    respuesta, m = _post({"codigo_puesto": "N07P50", "nombre": "EJEMPLO Frutas", "mismo_que": "300"},
                         existente=None, abm=(PARECIDO,))
    assert respuesta.status_code == 303
    m["asociar"].assert_called_once_with(300, "N07P50")
    assert m["crear_compra"].call_args.kwargs["codigo_llegada"] == "N07P50"


def test_la_consulta_de_PARECIDOS_de_la_pantalla_contesta_lo_mismo_que_el_POST():
    with patch("app.main.buscar_proveedor_por_codigo", return_value=None), \
         patch("app.main.listar_proveedores_para_abm", return_value=[PARECIDO, PROVEEDOR]):
        nuevo = cliente.get("/deposito/ingresar/parecidos",
                            params={"codigo": "n07p50", "nombre": "EJEMPLO Frutas"}).json()
    assert nuevo == {"parecidos": [{"id": 300, "nombre": "EJEMPLO FRUTAS S.R.L.", "codigo_puesto": "N09P41"}]}
    with patch("app.main.buscar_proveedor_por_codigo", return_value=PARECIDO), \
         patch("app.main.listar_proveedores_para_abm", return_value=[PARECIDO]):
        ya_existe = cliente.get("/deposito/ingresar/parecidos",
                                params={"codigo": "N09P41", "nombre": "EJEMPLO Frutas"}).json()
    assert ya_existe == {"parecidos": []}
    assert cliente.get("/deposito/ingresar/parecidos").json() == {"parecidos": []}


# --- lo cargado hoy muestra las fotos, vengan de donde vengan -----------------

def test_lo_CARGADO_HOY_muestra_las_fotos_de_cada_renglon():
    """Las que se subieron acá y las que Compras sumó desde el detalle: es la
    misma tabla, así que se ven igual."""
    renglones = [{"id": 71, "articulo_nombre": "EJEMPLO Kiwi", "cantidad_cajones": 10, "contenido_por_cajon": 18},
                 {"id": 72, "articulo_nombre": "EJEMPLO Pera", "cantidad_cajones": 4, "contenido_por_cajon": 20}]
    with patch("app.main.obtener_proveedor", return_value=PROVEEDOR), \
         patch("app.main.listar_proveedores", return_value=[PROVEEDOR]), \
         patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA), \
         patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=renglones), \
         patch("app.main.fotos_de_recepcion_por_compra",
               return_value={71: [{"id": 5, "creado_en": None}, {"id": 6, "creado_en": None}]}) as fotos:
        respuesta = cliente.get("/deposito/ingresar?proveedor_id=200")
    assert respuesta.status_code == 200
    fotos.assert_called_once_with([71, 72])
    assert respuesta.text.count('<img src="/deposito/recepcion/71/foto-balanza/') == 2
    assert '<img src="/deposito/recepcion/71/foto-balanza/6/ver"' in respuesta.text
    assert "/deposito/recepcion/72/foto-balanza/" not in respuesta.text
    assert respuesta.text.count("sin foto de la pesada") == 1


# --- contra Postgres: la compra y sus fotos, en la tabla de siempre ------------

@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    monkeypatch.setenv("DATABASE_URL", preparar_base())
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

    (art,), = sql("INSERT INTO articulos (nombre) VALUES ('EJEMPLO Fruta Pesada') RETURNING id")
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES ('EJEMPLO Puesto Pesada', 'N95P02') RETURNING id")

    def ingresar(fotos, **extra):
        return d.crear_compra(date.today(), art, prov, 5, 10, 50, None, None, None, "Clark",
                              ingreso_directo_deposito=True, segunda_por_cajon=None,
                              codigo_llegada=None, fotos_pesada=fotos, **extra)
    return d, sql, ingresar


def test_las_fotos_del_INGRESO_son_las_que_lee_el_DETALLE_de_la_compra(base):
    d, sql, ingresar = base
    compra = ingresar(["pesaje/2026-09-30/a.jpg", "pesaje/2026-09-30/b.jpg"])
    sin_fotos = ingresar([])
    # `listar_fotos_de_recepcion` es la que usa el detalle de la compra.
    assert [f["foto_ruta"] for f in d.listar_fotos_de_recepcion(compra)] == [
        "pesaje/2026-09-30/a.jpg", "pesaje/2026-09-30/b.jpg"]
    assert d.listar_fotos_de_recepcion(sin_fotos) == []
    juntas = d.fotos_de_recepcion_por_compra([compra, sin_fotos])
    assert list(juntas) == [compra] and len(juntas[compra]) == 2
    assert d.fotos_de_recepcion_por_compra([]) == {}


def test_si_la_compra_REBOTA_no_queda_ninguna_foto_colgando(base):
    d, sql, ingresar = base
    (antes,), = sql("SELECT count(*) FROM fotos_recepcion")
    with pytest.raises(Exception):
        # Un artículo y un proveedor que no existen: la FK hace rebotar el INSERT.
        d.crear_compra(date.today(), 999999, 999999, 5, 10, 50, None, None, None, "Clark",
                       ingreso_directo_deposito=True, segunda_por_cajon=None,
                       codigo_llegada=None, fotos_pesada=["pesaje/2026-09-30/c.jpg"])
    (despues,), = sql("SELECT count(*) FROM fotos_recepcion")
    assert despues == antes


# --- en el navegador: miniatura, borrar con confirmación, y el modal -----------

def _html_de_la_pantalla(parecidos=False):
    if parecidos:
        respuesta, _ = _post({"codigo_puesto": "N07P50", "nombre": "EJEMPLO Frutas"},
                             existente=None, abm=(PARECIDO,))
        return respuesta.text
    with patch("app.main.listar_proveedores", return_value=[PROVEEDOR]), \
         patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA):
        return cliente.get("/deposito/ingresar").text


def _navegador():
    pytest.importorskip("playwright", reason="la pantalla se mira en un navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    return sync_playwright, CHROMIUM


def test_en_el_NAVEGADOR_las_fotos_se_ven_en_miniatura_y_se_borran_con_confirmacion(tmp_path):
    sync_playwright, chromium = _navegador()
    for nombre in ("uno.jpg", "dos.jpg", "tres.jpg"):
        (tmp_path / nombre).write_bytes(_jpeg())
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=chromium)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        pagina.set_content(_html_de_la_pantalla())

        def miniaturas():
            return pagina.evaluate("""() => Array.from(document.querySelectorAll('#fotos-elegidas .foto-elegida'))
                .filter(e => getComputedStyle(e).display !== 'none').length""")

        assert miniaturas() == 0
        with pagina.expect_file_chooser() as elegir:
            pagina.click("#boton-agregar-foto")
        elegir.value.set_files([str(tmp_path / "uno.jpg"), str(tmp_path / "dos.jpg")])
        with pagina.expect_file_chooser() as elegir:
            pagina.click("#boton-agregar-foto")
        elegir.value.set_files(str(tmp_path / "tres.jpg"))
        assert miniaturas() == 3
        # El input no se ve: lo abre el botón.
        assert pagina.evaluate("""() => Array.from(document.querySelectorAll('#campos-fotos-pesada input'))
            .every(i => getComputedStyle(i).display === 'none')""")

        # Cancelar la confirmación no borra.
        pagina.once("dialog", lambda d: d.dismiss())
        pagina.click("#fotos-elegidas .foto-elegida:nth-child(1) button")
        assert miniaturas() == 3
        # Aceptarla sí: una de las dos elegidas juntas, y la otra queda.
        pagina.once("dialog", lambda d: d.accept())
        pagina.click("#fotos-elegidas .foto-elegida:nth-child(1) button")
        assert miniaturas() == 2
        cuantos = pagina.evaluate("""() => Array.from(document.querySelectorAll('#campos-fotos-pesada input'))
            .map(i => i.files.length)""")
        assert cuantos == [1, 1]
        # Y el botón se toca con el pulgar.
        alto = pagina.evaluate("() => document.getElementById('boton-agregar-foto').getBoundingClientRect().height")
        assert alto >= 44
        desborde = pagina.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert desborde == 0
        navegador.close()
    assert errores == []


def test_en_el_NAVEGADOR_el_modal_se_VE_solo_cuando_hay_parecidos():
    sync_playwright, chromium = _navegador()
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=chromium)
        visible = "() => getComputedStyle(document.getElementById('modal-parecidos')).display"
        # Una página por pantalla: dos set_content en la misma comparten los
        # `const` globales y el segundo script no corre.
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(_html_de_la_pantalla())
        assert pagina.evaluate(visible) == "none"
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        pagina.set_content(_html_de_la_pantalla(parecidos=True))
        assert pagina.evaluate(visible) == "flex"
        # Volver al formulario lo cierra sin mandar nada.
        pagina.click("#boton-cerrar-parecidos")
        assert pagina.evaluate(visible) == "none"
        navegador.close()
    assert errores == []
