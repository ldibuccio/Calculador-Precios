"""Vacíos del depósito, 29/09 (dueño): el total del galpón, la alerta de
devolver y las cuatro acciones del detalle en azul.

- El índice dice el TOTAL al lado de "Cajones en el galpón".
- Con más de LIMITE_CAJONES_VACIOS_EN_GALPON cajones (el total, no por
  proveedor) salta "Hay N cajones vacíos en el galpón: hay que devolver", en
  Compras, Gerencia y Administración. Gerencia y Administración estrenan su
  botón y su pantalla de Alertas, y los botones dicen cuántas hay.
- Los nombres de los proveedores son de EJEMPLO.
"""

import io
import re
import os
import sys
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.db as db  # noqa: E402
from app.alertas import para_mostrar  # noqa: E402
from app.main import (  # noqa: E402
    ALERTAS, ARGENTINA, PUERTA_ADMINISTRACION, PUERTA_COMPRAS, PUERTA_GERENCIA, app,
)

cliente = TestClient(app, base_url="https://testserver")

CLAVES = {"CLAVE_COMPRAS": "compras-secreta", "CLAVE_GERENCIA": "gerencia-secreta",
          "CLAVE_ADMINISTRACION": "admin-secreta"}


@pytest.fixture(autouse=True)
def _puertas_abiertas():
    with patch.dict(os.environ, CLAVES), patch("app.main.arranque_de_vacios", return_value=None):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
        cliente.cookies.set(PUERTA_GERENCIA.cookie, PUERTA_GERENCIA.firma("gerencia-secreta"))
        cliente.cookies.set(PUERTA_ADMINISTRACION.cookie,
                            PUERTA_ADMINISTRACION.firma("admin-secreta"))
        try:
            yield
        finally:
            for puerta in (PUERTA_COMPRAS, PUERTA_GERENCIA, PUERTA_ADMINISTRACION):
                cliente.cookies.delete(puerta.cookie)


def _prov(id, nombre, stock):
    return {"id": id, "nombre": nombre, "stock": stock,
            "pilas": [{"proveedor_id": id, "proveedor": nombre, "marca_id": None,
                       "marca": None, "arranque": 0, "recibidos": 0, "devueltos": 0,
                       "ajustes": 0, "asignados": 0, "stock": stock}]}


# 1.086, como el galpón el día que se pidió. Un negativo resta.
GALPON = [_prov(1, "Puesto EJEMPLO Uno", 700), _prov(2, "Puesto EJEMPLO Dos", 390),
          _prov(3, "Puesto EJEMPLO Tres", -4)]


# ---------------------------------------------------------------------------
# La cuenta y el límite
# ---------------------------------------------------------------------------

def test_el_total_SUMA_todos_los_proveedores_y_un_negativo_RESTA():
    assert db.total_de_vacios_en_galpon(GALPON) == 1086


@pytest.mark.parametrize("stock, casos", [(501, 501), (500, 0), (499, 0), (1086, 1086)])
def test_la_alerta_cuenta_los_cajones_SOLO_si_PASAN_del_limite(stock, casos):
    """500 justos no avisa: "cuando el total pasa de 500". 501 sí."""
    assert db.LIMITE_CAJONES_VACIOS_EN_GALPON == 500
    with patch("app.db.stock_de_vacios_deposito", return_value=[_prov(1, "EJ", stock)]):
        assert db.contar_vacios_para_devolver() == casos


def test_el_limite_vive_en_UN_lugar_y_moverlo_mueve_la_alerta_y_su_detalle():
    """Moverlo a 2.000 apaga el conteo y cambia la nota del detalle.

    Es el control del "un solo lugar": si la alerta o el detalle tuvieran su
    propio 500, este test lo encuentra."""
    from app import main
    with patch("app.db.stock_de_vacios_deposito", return_value=GALPON), \
         patch("app.main.stock_de_vacios_deposito", return_value=GALPON), \
         patch("app.db.LIMITE_CAJONES_VACIOS_EN_GALPON", 2000), \
         patch("app.main.LIMITE_CAJONES_VACIOS_EN_GALPON", 2000):
        assert db.contar_vacios_para_devolver() == 0
        detalle = main._detalle_vacios_para_devolver()
    assert detalle["resumen"] == "Hay 1.086 cajones vacíos en el galpón"
    assert "2.000" in detalle["nota"]
    fuentes = io.open("app/main.py", encoding="utf-8").read() + io.open("app/db.py", encoding="utf-8").read()
    assert fuentes.count("LIMITE_CAJONES_VACIOS_EN_GALPON = ") == 1
    assert "> 500" not in fuentes and ">500" not in fuentes


def _alerta():
    return next(a for a in ALERTAS if a.codigo == "vacios_para_devolver")


def test_la_alerta_sale_en_COMPRAS_GERENCIA_y_ADMINISTRACION():
    assert set(_alerta().modulos) == {"compras", "gerencia", "administracion"}


def test_cada_sector_va_a_una_pantalla_de_SU_prefijo():
    """Corolario 56: Vacíos está detrás de la clave de Administración, así que
    el link de Compras y el de Gerencia no pueden ir ahí."""
    estado = [{"codigo": "vacios_para_devolver", "casos": 1086, "mas_viejo": None,
               "calculada_el": datetime.now(ARGENTINA), "error": None}]
    for sector in ("compras", "gerencia", "administracion"):
        alerta = next(a for a in para_mostrar(ALERTAS, estado, sector)
                      if a["codigo"] == "vacios_para_devolver")
        assert alerta["url"].startswith(f"/{sector}/"), (sector, alerta["url"])


def test_la_frase_lleva_el_numero_con_punto_de_miles():
    estado = [{"codigo": "vacios_para_devolver", "casos": 1086, "mas_viejo": None,
               "calculada_el": datetime.now(ARGENTINA), "error": None}]
    alerta = next(a for a in para_mostrar(ALERTAS, estado, "compras")
                  if a["codigo"] == "vacios_para_devolver")
    assert alerta["texto"] == "Hay 1.086 cajones vacíos en el galpón: hay que devolver"


def test_sin_casos_la_alerta_NO_sale():
    estado = [{"codigo": "vacios_para_devolver", "casos": 0, "mas_viejo": None,
               "calculada_el": datetime.now(ARGENTINA), "error": None}]
    assert not [a for a in para_mostrar(ALERTAS, estado, "gerencia")
                if a["codigo"] == "vacios_para_devolver"]


# ---------------------------------------------------------------------------
# Los hubs: el banner y el botón con la cantidad
# ---------------------------------------------------------------------------

def _estado(casos_vacios=1086, otra_de_compras=0):
    ahora = datetime.now(ARGENTINA)
    filas = [{"codigo": "vacios_para_devolver", "casos": casos_vacios, "mas_viejo": None,
              "calculada_el": ahora, "error": None}]
    if otra_de_compras:
        filas.append({"codigo": "compras_sin_precio", "casos": otra_de_compras,
                      "mas_viejo": None, "calculada_el": ahora, "error": None})
    return filas


def _hub(url, estado):
    with patch("app.main.listar_estado_alertas", return_value=estado):
        return cliente.get(url)


@pytest.mark.parametrize("url", ["/compras", "/gerencia", "/administracion"])
def test_el_hub_muestra_la_frase_y_el_boton_ALERTAS_con_la_cantidad(url):
    respuesta = _hub(url, _estado())
    assert respuesta.status_code == 200
    # Sobre el texto ENTERO: el banner trae su propio <style>, y cortar por
    # el último "</style>" se lo lleva (corolario 50). El ancla es el <a>.
    marcado = respuesta.text
    assert '">Hay 1.086 cajones vacíos en el galpón: hay que devolver</a>' in marcado
    # Desde el 04/10 el botón es el de la FRANJA de arriba (dueño), y el
    # detalle de todas sigue linkeado desde su panel.
    assert 'data-franja-boton="alertas">Alertas (1)</button>' in marcado
    assert f'href="{url}/alertas">Ver el detalle de las alertas</a>' in marcado


def test_el_boton_cuenta_ALERTAS_y_no_casos():
    """Dos alertas activas en Compras: el botón dice 2, no 1.086 + 3."""
    marcado = _hub("/compras", _estado(otra_de_compras=3)).text
    assert 'data-franja-boton="alertas">Alertas (2)</button>' in marcado


@pytest.mark.parametrize("url", ["/compras", "/gerencia", "/administracion", "/comercial"])
def test_sin_alertas_el_boton_dice_solo_ALERTAS(url):
    marcado = _hub(url, _estado(casos_vacios=0)).text
    if url == "/comercial":     # Comercial no tiene franja: su botón, verde y "Sin alertas" (04/10)
        assert re.search(r'<a class="boton sin-alertas" href="/comercial/alertas">[^<]*<svg.*?</svg>'
                         r'<span>Sin alertas</span></a>', marcado, re.S)
    else:
        assert 'data-franja-boton="alertas">Sin alertas</button>' in marcado
    assert "hay que devolver" not in marcado


def test_una_alerta_SIN_CALCULAR_no_suma_al_boton():
    estado = [{"codigo": "vacios_para_devolver", "casos": None, "mas_viejo": None,
               "calculada_el": None, "error": None}]
    marcado = _hub("/gerencia", estado).text
    assert 'data-franja-boton="alertas">Sin alertas</button>' in marcado


# ---------------------------------------------------------------------------
# Las pantallas de Alertas nuevas
# ---------------------------------------------------------------------------

def _alertas(url):
    with patch("app.main.listar_estado_alertas", return_value=_estado()), \
         patch("app.main.stock_de_vacios_deposito", return_value=GALPON):
        return cliente.get(url)


@pytest.mark.parametrize("url", ["/compras/alertas", "/gerencia/alertas", "/administracion/alertas"])
def test_la_pantalla_de_alertas_lista_los_proveedores_y_la_frase(url):
    respuesta = _alertas(url)
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "Hay 1.086 cajones vacíos en el galpón: hay que devolver" in marcado
    assert "Puesto EJEMPLO Uno" in marcado and ">700<" in marcado
    # el negativo se lista: sin él, la lista no suma el total de arriba
    assert "Puesto EJEMPLO Tres" in marcado and ">-4<" in marcado


def test_desde_ADMINISTRACION_la_alerta_lleva_a_VACIOS():
    marcado = _alertas("/administracion/alertas").text
    assert 'href="/administracion/vacios">Ver Vacíos del depósito</a>' in marcado


@pytest.mark.parametrize("url", ["/compras/alertas", "/gerencia/alertas"])
def test_desde_COMPRAS_y_GERENCIA_ningun_link_va_a_ADMINISTRACION(url):
    marcado = _alertas(url).text.split("</style>")[-1]
    assert 'href="/administracion' not in marcado


@pytest.mark.parametrize("url", ["/gerencia/alertas", "/administracion/alertas"])
def test_las_pantallas_nuevas_piden_su_CLAVE(url):
    cliente.cookies.delete(PUERTA_GERENCIA.cookie)
    cliente.cookies.delete(PUERTA_ADMINISTRACION.cookie)
    respuesta = _alertas(url)
    assert "Hay 1.086" not in respuesta.text
    assert 'type="password"' in respuesta.text


# ---------------------------------------------------------------------------
# El índice de Vacíos: el total al lado del título
# ---------------------------------------------------------------------------

def _indice(proveedores):
    with patch("app.main.stock_de_vacios_deposito", return_value=proveedores):
        return cliente.get("/administracion/vacios")


def test_el_indice_dice_el_TOTAL_al_lado_del_titulo_en_ROJO_si_pasa_del_limite():
    respuesta = _indice(GALPON)
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert '<span class="total total-alto">1.086</span></h2>' in marcado


def test_debajo_del_limite_el_total_NO_va_en_rojo():
    marcado = _indice([_prov(1, "EJ", 35)]).text.split("</style>")[-1]
    assert '<span class="total">35</span></h2>' in marcado


def test_el_total_con_numero_negativo_lleva_el_signo_BIEN_puesto():
    """_agrupar_miles solo sabe de dígitos: el "-" cuenta como una cifra más.
    Con -1086 sale bien por casualidad ("-1" queda solo); con -100 da "-.100"."""
    from app.main import _entero_con_miles
    assert _entero_con_miles(-100) == "-100"
    assert _entero_con_miles(-1086) == "-1.086"
    assert _entero_con_miles(1086) == "1.086"
    assert _entero_con_miles(0) == "0"


# ---------------------------------------------------------------------------
# En el navegador: el total entra en 390px y las cuatro acciones son azules
# ---------------------------------------------------------------------------

def _navegador():
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    return sync_playwright, CHROMIUM


def _detalle():
    with patch("app.main.stock_de_vacios_deposito", return_value=GALPON[:1]), \
         patch("app.main.proveedor_para_vacios", return_value=None), \
         patch("app.main.listar_marcas_vacio", return_value=[]), \
         patch("app.main.movimientos_de_vacios", return_value=[]), \
         patch("app.main.sena_por_cajon_de_la_ultima_recepcion", return_value={}):
        return cliente.get("/administracion/vacios/1")


def test_las_CUATRO_acciones_son_AZULES_y_el_historial_NO():
    """El efecto y no la clase (corolario 32): el color que calcula el navegador."""
    sync_playwright, chromium = _navegador()
    respuesta = _detalle()
    assert respuesta.status_code == 200
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=chromium)
        pagina = navegador.new_page(viewport={"width": 390, "height": 900})
        pagina.set_content(respuesta.text)
        colores = pagina.evaluate("""() => [...document.querySelectorAll('details > summary')]
            .map(s => [s.parentElement.id, getComputedStyle(s).backgroundColor,
                       getComputedStyle(s.querySelector('strong')).color,
                       s.getBoundingClientRect().height])""")
        navegador.close()
    por_id = {c[0]: c for c in colores}
    assert set(por_id) == {"devolver", "pasar", "corregir", "ajustar", "movimientos"}
    for accion in ("devolver", "pasar", "corregir", "ajustar"):
        _, fondo, letra, alto = por_id[accion]
        assert fondo == "rgb(37, 99, 235)", (accion, fondo)
        assert letra == "rgb(255, 255, 255)", (accion, letra)
        assert alto >= 44, (accion, alto)
    assert por_id["movimientos"][1] != "rgb(37, 99, 235)"


def test_el_total_ENTRA_en_390px_con_un_numero_grande():
    sync_playwright, chromium = _navegador()
    marcado = _indice([_prov(1, "PUESTODEEJEMPLOSINUNSOLOESPACIOPARAPARTIRLO", 123456)]).text
    assert "123.456" in marcado
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=chromium)
        pagina = navegador.new_page(viewport={"width": 390, "height": 900})
        pagina.set_content(marcado)
        medida = pagina.evaluate("""() => {
            const t = document.querySelector('.total');
            const r = t.getBoundingClientRect();
            return {derecha: r.right, ancho: document.documentElement.clientWidth,
                    desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth};
        }""")
        navegador.close()
    assert medida["desborde"] == 0, medida
    assert medida["derecha"] <= medida["ancho"], medida
