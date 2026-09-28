"""Los títulos de kilos y unidades, y la unidad al lado del número (28/09).

La compra 827 (palta, 27/09) se cargó en Ingreso por depósito con 18 "por
cajón" y 80 kilos por cajón, cuando eran 80 unidades y 18 kilos. Ahí el
primer campo decía "Contenido por cajón" sin unidad, y el segundo quedaba
SIN TÍTULO: su JS usaba una tabla que esa pantalla nunca definió, y al elegir
palta tiraba un error y cortaba.

Lo que estos tests miran es el EFECTO en el navegador (corolario 32) y no el
marcado: el título que se lee, el sufijo al lado del número, y que no haya
ningún error de JS. Con cuatro artículos, uno por cada caso de la regla:
contado (palta), por kilo solo (kiwi), por kilo y contado (limón), y el que
no tiene la unidad declarada, que es kilo.
"""
import io
import os
import re
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app.main as _main
from core.magnitudes import etiqueta_por_cajon, repartir_magnitudes, unidad_de_compra

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ARTICULOS = [
    {"id": 1, "nombre": "EJEMPLO Palta", "unidad_compra": "unidad", "unidad_conteo": "unidad",
     "contenido_referencia": None},
    {"id": 2, "nombre": "EJEMPLO Kiwi", "unidad_compra": "kilo", "unidad_conteo": None,
     "contenido_referencia": 18},
    {"id": 3, "nombre": "EJEMPLO Limon", "unidad_compra": "kilo", "unidad_conteo": "unidad",
     "contenido_referencia": 18},
    {"id": 4, "nombre": "EJEMPLO Sin unidad", "unidad_compra": None, "unidad_conteo": "cubeta",
     "contenido_referencia": None},
]
PROVEEDOR = {"id": 200, "codigo_puesto": "N07P41", "nombre": "EJEMPLO Puesto"}

# Por artículo: (título del primero, sufijo, título del segundo, sufijo).
ESPERADO = {
    "1": ("Unidades por cajón", "u", "Kilos por cajón", "kg"),
    "2": ("Kilos por cajón", "kg", "", ""),
    "3": ("Kilos por cajón", "kg", "Unidades por cajón", "u"),
    "4": ("Kilos por cajón", "kg", "Cubetas por cajón", "cub."),
}


# --- la regla, sin navegador ------------------------------------------------


def test_el_NULO_es_KILO_tambien_al_REPARTIR_las_magnitudes():
    """Con `== "kilo"` a secas, la recepción de un artículo sin la unidad
    declarada guardaba los kilos en la columna del conteo: la inversión de la
    827, hecha por el sistema. El rival es "unidad", que sí da vuelta."""
    assert repartir_magnitudes(None, 80.0, 18.0) == (80.0, 18.0)
    assert repartir_magnitudes("kilo", 80.0, 18.0) == (80.0, 18.0)
    assert repartir_magnitudes("unidad", 80.0, 18.0) == (18.0, 80.0)


def test_el_titulo_nombra_la_unidad_y_sin_articulo_no_inventa_una():
    assert unidad_de_compra({"unidad_compra": None}) == "kilo"
    assert unidad_de_compra(None) is None
    assert etiqueta_por_cajon("unidad") == "Unidades por cajón"
    assert etiqueta_por_cajon(None) == "Contenido por cajón"


def test_la_tabla_de_titulos_esta_escrita_UNA_vez():
    """Estaba en ocho lugares, y el que se olvidó de definirla es el que rompió
    el Ingreso por depósito. Ninguna plantilla puede volver a tener su copia:
    ni el diccionario de Jinja ni el del JS."""
    copias = {}
    carpeta = os.path.join(RAIZ, "templates")
    for nombre in os.listdir(carpeta):
        texto = io.open(os.path.join(carpeta, nombre), encoding="utf-8").read()
        if re.search(r"""["']?(kilo|unidad)["']?\s*:\s*["'](Kilos|Unidades) por cajón""", texto) \
                or re.search(r"ETIQUETAS_CONTENIDO|etiquetasContenido|segundaMagnitudDe", texto):
            copias[nombre] = True
    assert copias == {}


# --- en el navegador --------------------------------------------------------


def _html_de(pantalla):
    cliente = TestClient(_main.app, base_url="https://testserver")
    with patch.dict(os.environ, {"CLAVE_GERENCIA": "g", "CLAVE_COMPRAS": "c"}), \
         patch("app.main.listar_articulos", return_value=ARTICULOS), \
         patch("app.main.listar_proveedores", return_value=[PROVEEDOR]), \
         patch("app.main.obtener_proveedor", return_value=PROVEEDOR), \
         patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]), \
         patch("app.main._cajas_en_origen_por_articulo", return_value={}), \
         patch("app.main.fecha_corte", return_value=date(2026, 9, 5)):
        cliente.cookies.set(_main.PUERTA_GERENCIA.cookie, _main.PUERTA_GERENCIA.firma("g"))
        cliente.cookies.set(_main.PUERTA_COMPRAS.cookie, _main.PUERTA_COMPRAS.firma("c"))
        respuesta = cliente.get(pantalla["url"])
    assert respuesta.status_code == 200, respuesta.text[:300]
    return respuesta.text


PANTALLAS = [
    {"url": "/deposito/ingresar?proveedor_id=200", "select": "#articulo_id",
     "primero": "contenido_por_cajon", "segundo": "segunda_por_cajon"},
    {"url": "/compras/nueva/manual", "select": "#articulo_id",
     "primero": "contenido_por_cajon", "segundo": "segunda_por_cajon"},
    {"url": "/gerencia/compras/ingreso-retroactivo", "select": "#articulo",
     "primero": "contenido", "segundo": "segunda"},
]


def _leer_en_el_navegador(html, pantalla):
    pytest.importorskip("playwright", reason="los títulos se leen en un navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    leido = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        pagina.set_content(html)
        for articulo_id in ESPERADO:
            pagina.select_option(pantalla["select"], articulo_id)
            leido[articulo_id] = pagina.evaluate("""([uno, dos]) => {
              const titulo = id => {
                const l = document.querySelector('label[for="' + id + '"]');
                const campo = document.getElementById(id);
                const visible = campo && campo.offsetParent !== null;
                return visible ? l.textContent.replace('*', '').trim() : '';
              };
              const sufijo = id => {
                const campo = document.getElementById(id);
                const s = campo && campo.parentNode.querySelector('.unidad-al-lado');
                return (s && campo.offsetParent !== null) ? s.textContent : '';
              };
              return [titulo(uno), sufijo(uno), titulo(dos), sufijo(dos),
                      document.documentElement.scrollWidth - document.documentElement.clientWidth];
            }""", [pantalla["primero"], pantalla["segundo"]])
        navegador.close()
    return leido, errores


@pytest.mark.parametrize("pantalla", PANTALLAS, ids=lambda p: p["url"].split("?")[0])
def test_cada_campo_DICE_LA_UNIDAD_en_el_titulo_y_al_lado_del_numero(pantalla):
    leido, errores = _leer_en_el_navegador(_html_de(pantalla), pantalla)
    assert errores == [], "un error de JS corta el resto del cableado: así quedó sin título la 827"
    assert len(leido) == len(ESPERADO)
    for articulo_id, (t1, s1, t2, s2) in ESPERADO.items():
        titulo1, sufijo1, titulo2, sufijo2, desborde = leido[articulo_id]
        assert (titulo1, sufijo1) == (t1, s1), (articulo_id, leido[articulo_id])
        if pantalla["segundo"] == "segunda" and not t2:
            # En Gerencia el segundo campo se ve siempre, y lo dice.
            assert titulo2 == "La otra magnitud (este artículo no la lleva)"
            assert sufijo2 == ""
        else:
            assert (titulo2, sufijo2) == (t2, s2), (articulo_id, leido[articulo_id])
        assert desborde <= 0


# --- Corregir recepción: la segunda magnitud (28/09) -------------------------


def test_CORREGIR_RECEPCION_de_una_compra_con_LAS_DOS_magnitudes_anda_contra_la_base():
    """La 827 hubo que borrarla porque Corregir recepción mandaba UNA sola
    magnitud y la escritura exige las dos. Contra Postgres: la palta cargada
    cruzada (18 u y 80 kg) se da vuelta desde la pantalla, y el RIVAL es la
    pantalla sin el campo, que rebota."""
    from scripts.humo import hay_postgres, preparar_base
    if not hay_postgres():
        if os.environ.get("HUMO_OBLIGATORIO") == "1":
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    os.environ["DATABASE_URL"] = preparar_base()
    import app.db as d

    def sql(q, p=()):
        c = d.obtener_conexion()
        try:
            with c.cursor() as cur:
                cur.execute(q, p)
                f = cur.fetchall() if cur.description else None
            c.commit()
            return f
        finally:
            c.close()

    (art,), = sql("INSERT INTO articulos (nombre, unidad_compra, unidad_conteo) "
                  "VALUES ('EJEMPLO Palta Corregir', 'unidad', 'unidad') RETURNING id")
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES (%s, %s) RETURNING id", (f"EJEMPLO Prov {art}", f"N95P{art % 100:02d}"))
    d.crear_compra(date(2026, 9, 27), art, prov, 10, 18, 800, 180, 1000, None, "Clark", None,
                   segunda_por_cajon=80, codigo_llegada=None)
    (cid,), = sql("SELECT max(id) FROM compras")
    sql("""UPDATE compras SET estado='recepcionado', cantidad_cajones_real=10,
           contenido_por_cajon_real=18, cantidad_fraccion_real=180, cantidad_kilos_real=800,
           segunda_por_cajon_real=80, procesada_el=now() WHERE id=%s""", (cid,))

    cliente = TestClient(_main.app, base_url="https://testserver")
    cliente.cookies.set(_main.PUERTA_GERENCIA.cookie, _main.PUERTA_GERENCIA.firma("g"))
    with patch.dict(os.environ, {"CLAVE_GERENCIA": "g"}):
        pantalla = cliente.get(f"/gerencia/compras/{cid}/corregir-recepcion").text
        assert 'name="segunda_real"' in pantalla
        assert "Kilos por cajón/bulto (real)" in pantalla
        # Sin la segunda: la escritura rebota y la pantalla lo dice.
        sin = cliente.post(f"/gerencia/compras/{cid}/corregir-recepcion",
                           data={"cantidad_cajones_real": "10", "cantidad_total_real": "80",
                                 "confirmado": "1"}, follow_redirects=False)
        assert sin.status_code == 400
        con = cliente.post(f"/gerencia/compras/{cid}/corregir-recepcion",
                           data={"cantidad_cajones_real": "10", "cantidad_total_real": "80",
                                 "segunda_real": "18", "confirmado": "1"}, follow_redirects=False)
    assert con.status_code == 303, con.text[:300]
    fila, = sql("SELECT contenido_por_cajon_real, cantidad_fraccion_real, cantidad_kilos_real "
                "FROM compras WHERE id=%s", (cid,))
    assert [float(x) for x in fila] == [80.0, 800.0, 180.0]
