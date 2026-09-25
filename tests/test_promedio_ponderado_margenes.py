"""El promedio ponderado de utilidad arriba de Márgenes por Artículo (dueño, 25/09).

Σ(utilidad × facturado) / Σ(facturado), sobre las filas de "Todos" A LA VISTA.
Lo calcula el script del cuadro —una sola vez, para el primer dibujo y para
el buscador—, así que se mide EN UN NAVEGADOR: un assert sobre el HTML
servido leería el "—" con el que la caja nace.

EL CASO, con nombres de ejemplo y números elegidos para que cada lectura mala
dé OTRO número:

    EJ Tomate   utilidad 30%   facturó 600
    EJ Banana   utilidad 10%   facturó 300
    EJ Palta    utilidad −5%   facturó 100
    EJ Kiwi     utilidad 50%   facturó   0   -> no pesa
    EJ Mango    sin utilidad   facturó 200   -> afuera, y se dice

    bien:                          (180 + 30 − 5) / 1000 = 20,5%
    promedio simple de los 4:      21,3%
    Mango en el denominador en 0:  205 / 1200 = 17,1%
    Kiwi pesando igual que el resto (sin facturación): cualquier otro número
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app, base_url="https://testserver")

CLIENTES = [{"id": 1, "nombre": "Cliente EJEMPLO", "utilidad_objetivo": 20.0}]
FICHAS = [{"id": i, "articulo_id": i, "articulo_nombre": f"EJ {i}"} for i in range(1, 6)]


def _articulo(ficha_id, nombre, utilidad):
    return {"ficha_id": ficha_id, "articulo_nombre": nombre, "fresco": False,
            "variacion": None, "costo_anterior": None, "costo_actual": 1000.0,
            "precio_sugerido": 1300.0, "precio_vigente": 1300.0 if utilidad is not None else None,
            "utilidad_aproximada": utilidad, "compras_sin_precio_excluidas": 0}


ARTICULOS = [_articulo(1, "EJ Tomate", 0.30), _articulo(2, "EJ Banana", 0.10),
             _articulo(3, "EJ Palta", -0.05), _articulo(4, "EJ Kiwi", 0.50),
             _articulo(5, "EJ Mango", None)]
FACTURACION = {"por_ficha": {1: 600.0, 2: 300.0, 3: 100.0, 5: 200.0}, "dias": 22}


def _pantalla(facturacion=FACTURACION):
    parche_fact = (patch("app.main.facturacion_por_ficha", side_effect=RuntimeError("caída"))
                   if facturacion is None else
                   patch("app.main.facturacion_por_ficha", return_value=facturacion))
    with patch("app.main.listar_clientes", return_value=CLIENTES), \
         patch("app.main.listar_fichas_por_cliente", return_value=FICHAS), \
         patch("app.main.calcular_listado_para_negociar_precios",
               return_value=[dict(a) for a in ARTICULOS]), parche_fact:
        respuesta = cliente.get("/negociar?cliente_id=1")
    assert respuesta.status_code == 200
    return respuesta.text


def _leer(html, buscar=None):
    pytest.importorskip("playwright", reason="el promedio lo calcula el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        pagina.set_content(html)
        if buscar is not None:
            pagina.fill("#buscar-todos-articulos", buscar)
        leido = pagina.evaluate("""() => {
          const caja = document.getElementById('promedio-ponderado');
          const t = s => { const e = caja.querySelector(s); return e ? e.textContent.trim() : null; };
          return {valor: t('.promedio-valor') || t('.promedio-valor-fijo'),
                  detalle: t('.promedio-detalle'),
                  visibles: [...document.querySelectorAll('#tbody-todos-articulos tr')]
                              .filter(f => f.style.display !== 'none').length,
                  desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth};
        }""")
        navegador.close()
    assert errores == [], errores
    return leido


def test_el_promedio_pesa_por_lo_FACTURADO_y_deja_afuera_lo_que_no_se_puede_pesar():
    leido = _leer(_pantalla())
    # el denominador al lado: las cinco filas estaban a la vista
    assert leido["visibles"] == 5
    assert leido["valor"] == "20,5%", leido
    assert "3 artículos" in leido["detalle"]
    assert "$1.000" in leido["detalle"]
    # el que facturó sin utilidad no se esconde en el número: se nombra
    assert "Quedan afuera 1 que facturó $200" in leido["detalle"]
    assert leido["desborde"] == 0


def test_el_BUSCADOR_recalcula_con_lo_que_quedo_a_la_vista():
    leido = _leer(_pantalla(), buscar="tomate")
    assert leido["visibles"] == 1
    assert leido["valor"] == "30,0%"
    assert "solo los que coinciden con la búsqueda" in leido["detalle"]


def test_si_nada_de_lo_visible_facturo_con_utilidad_dice_que_no_hay_numero():
    leido = _leer(_pantalla(), buscar="kiwi")
    assert leido["visibles"] == 1
    assert leido["valor"] == "—"
    assert "Ningún artículo de los que coinciden" in leido["detalle"]


def test_sin_facturacion_LEGIBLE_no_se_inventa_un_promedio():
    """Sin pesos no hay promedio ponderado. Un cero, o el promedio simple, se
    leerían como un número calculado."""
    leido = _leer(_pantalla(facturacion=None))
    assert leido["valor"] == "—"
    assert leido["detalle"] is None


def test_la_caja_va_ARRIBA_de_todo_antes_de_las_Bajas():
    marcado = _pantalla().split("</style>")[-1]
    assert marcado.index('id="promedio-ponderado"') < marcado.index("<h2>Bajas")
