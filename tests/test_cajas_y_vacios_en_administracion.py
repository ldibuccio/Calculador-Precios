"""Cajas y Vacíos entran también por Administración, con el camino entero de allá.

Las pantallas son las MISMAS que Compras tiene en /compras/cajas y
/compras/vacios: los mismos handlers y las mismas consultas. Lo que se prueba
acá es el CAMINO, y sobre todo lo que no se ve entrando: la barra sale bien
porque la arma el server, y lo que se queda apuntando al otro sector es la
`action` de un formulario o el destino de un redirect, que recién muerde en
el primer submit (corolario 63).

Por eso se afirma que `/compras/` no aparece NI UNA VEZ en el marcado: cubre
la barra, el atrás, cada formulario y cada link sin enumerarlos, y también el
que alguien agregue mañana.
"""

import os
import re
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import PUERTA_ADMINISTRACION, PUERTA_COMPRAS, app

cliente = TestClient(app, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _las_dos_puertas_abiertas():
    """Las dos puertas con su clave y su cookie, como las cruza una persona.

    Las dos a la vez a propósito: con una sola, la ruta de la otra contesta
    la pantalla de la clave, y un test que pregunta por la barra la estaría
    buscando en la pantalla equivocada.
    """
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta",
                                 "CLAVE_ADMINISTRACION": "admin-secreta"}):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
        cliente.cookies.set(PUERTA_ADMINISTRACION.cookie,
                            PUERTA_ADMINISTRACION.firma("admin-secreta"))
        try:
            yield
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)
            cliente.cookies.delete(PUERTA_ADMINISTRACION.cookie)


# Nombres de ejemplo, y que se note (CLAUDE.md: capturas y fixtures).
UN_ENVASE = [{
    "id": 1, "nombre": "Caja EJEMPLO Grande", "umbral_reposicion": 50,
    "desde": date(2026, 9, 10), "contadas": 100, "declaradas": -70, "por_guias": -20,
    "stock": 10, "esperando_mov": 0, "esperando_guias": 0, "esperando_desde": None,
    "cajas_por_pallet": 4,
}, {
    # UNO SIN ARRANCAR, a propósito: el formulario del conteo inicial solo se
    # dibuja si hay alguno, y sin él la pantalla tiene tres formularios y el
    # cuarto no lo mira nadie (la séptima lectura del canario en cero).
    "id": 2, "nombre": "Caja EJEMPLO Chica", "umbral_reposicion": None,
    "desde": None, "contadas": None, "declaradas": 0, "por_guias": 0, "stock": None,
    "esperando_mov": 0, "esperando_guias": 0, "esperando_desde": None,
    "cajas_por_pallet": None,
}]
UNA_CUENTA = [{
    "colega_id": 3, "colega": "Colega EJEMPLO Uno", "movimientos": 1,
    "por_envase": [{"envase_id": 1, "envase": "Caja EJEMPLO Grande", "neto": 20,
                    "lado": "me debe", "cuantas": 20}],
}]
UN_MOVIMIENTO = [{
    "origen": "prestamo_a_colega", "cantidad": -20, "fecha": date(2026, 9, 12),
    "envase": "Caja EJEMPLO Grande", "motivo": None,
}]
UN_PROVEEDOR = [{
    "id": 7, "nombre": "Puesto EJEMPLO", "tipo_cajon": "Cajón de ejemplo",
    "desde": date(2026, 9, 17), "contados": 30, "recibidos": 10, "devueltos": 5,
    "stock": 35, "esperando_recepciones": 0, "esperando_devoluciones": 0,
    "esperando_desde": None,
}]
UNA_DEVOLUCION = [{
    "id": 11, "cantidad": 5, "fecha": date(2026, 9, 18), "importe": 1000.0,
    "articulo": "Artículo EJEMPLO", "fecha_compra": date(2026, 9, 17),
    "anulada": False, "foto_ruta": "2026-09-18/vale.jpg",
}]
UNA_COMPRA = [{"id": 40, "articulo": "Artículo EJEMPLO", "cajones": 10,
               "fecha": date(2026, 9, 17)}]


def _con_datos():
    """Los parches de las cuatro pantallas juntos: cada una lee un subconjunto."""
    from contextlib import ExitStack
    pila = ExitStack()
    for nombre, valor in {
        "stock_de_envases": UN_ENVASE,
        "cuentas_de_colegas": UNA_CUENTA,
        "listar_colegas": [{"id": 3, "nombre": "Colega EJEMPLO Uno"}],
        "movimientos_de_colegas": UN_MOVIMIENTO,
        "stock_de_vacios_deposito": UN_PROVEEDOR,
        "compras_para_vale_de_vacios": UNA_COMPRA,
        "listar_devoluciones_vacios": UNA_DEVOLUCION,
        "listar_tipos_cajon": [],
    }.items():
        pila.enter_context(patch(f"app.main.{nombre}", return_value=[dict(f) for f in valor]
                                 if isinstance(valor, list) else valor))
    return pila


# Las cuatro pantallas, con lo que cada una TIENE que tener para saber que es
# ella y no la de la clave (corolario 53: la identidad va pegada al resultado),
# y a dónde tiene que volver su atrás.
PANTALLAS = [
    ("/cajas", 'Caja EJEMPLO Grande', ""),
    ("/cajas/colega/3", 'Cuenta con Colega EJEMPLO Uno', "/cajas"),
    ("/vacios", 'Puesto EJEMPLO', ""),
    ("/vacios/7", 'Ver el vale', "/vacios"),
    ("/vacios/stock", '<span class="cantidad">35</span>', "/vacios"),
]


@pytest.mark.parametrize("ruta, propio, atras", PANTALLAS)
def test_entrando_por_ADMINISTRACION_todo_el_camino_es_de_ADMINISTRACION(ruta, propio, atras):
    """La barra, el atrás, cada formulario y cada link — sin una sola vuelta a Compras."""
    with _con_datos():
        respuesta = cliente.get(f"/administracion{ruta}")
    assert respuesta.status_code == 200
    marcado = respuesta.text
    assert propio in marcado, "no es la pantalla que se quiso abrir"

    assert 'aria-label="Ir a Administración"' in marcado
    # CON EL aria-label PEGADO: el href del ícono de sector y el del atrás
    # pueden ser el mismo, y suelto matchearía el ícono (corolario 57).
    assert f'href="/administracion{atras}" aria-label="Volver atrás"' in marcado
    assert 'aria-label="Ir a Compras"' not in marcado
    assert "/compras/" not in marcado
    assert 'href="/compras"' not in marcado


@pytest.mark.parametrize("ruta, propio, atras", PANTALLAS)
def test_entrando_por_COMPRAS_sigue_siendo_todo_de_COMPRAS(ruta, propio, atras):
    """El dueño de las pantallas no se movió: los botones de Compras quedan donde están."""
    with _con_datos():
        respuesta = cliente.get(f"/compras{ruta}")
    assert respuesta.status_code == 200
    marcado = respuesta.text
    assert propio in marcado
    assert 'aria-label="Ir a Compras"' in marcado
    assert f'href="/compras{atras}" aria-label="Volver atrás"' in marcado
    assert "/administracion" not in marcado


def test_los_FORMULARIOS_de_cada_pantalla_mandan_a_SU_sector():
    """TODOS los formularios, y el conjunto de destinos ENCONTRADO contra el DECIDIDO.

    Un `in` contesta por el más suertudo (corolario 57, tercera causa): con la
    `action` arreglada en uno solo de los formularios de Cajas, el assert
    suelto pasaría igual. Y comparar conjuntos falla en las dos direcciones
    (corolario 60): si un formulario vuelve a Compras y si uno desaparece.
    """
    decididos = {
        "/cajas": {"/administracion/cajas/umbral", "/administracion/cajas/pallet",
                   "/administracion/cajas/conteo-inicial",
                   "/administracion/cajas/movimiento", "/administracion/cajas/colegas"},
        "/vacios": {"/administracion/vacios/conteo"},
        "/vacios/7": {"/administracion/vacios/7/cajon", "/administracion/vacios/7/devolucion",
                      "/administracion/vacios/devolucion/11/anular"},
    }
    for ruta, esperados in decididos.items():
        with _con_datos():
            marcado = cliente.get(f"/administracion{ruta}").text
        # La ETIQUETA entera y no un corte por `</style>`: la barra trae su
        # propio <style> y el último del documento corta de más (corolario 50).
        formularios = re.findall(r"<form\b[^>]*>", marcado)
        # El de BLOQUEAR es de la barra y va a /administracion/bloquear: entra
        # en la pregunta del sector, pero no en el conjunto de la pantalla.
        acciones = {re.search(r'action="([^"]*)"', f).group(1)
                    for f in formularios if "barra-bloquear" not in f}
        assert acciones == esperados, ruta
        sin_su_sector = [f for f in formularios if 'action="/administracion/' not in f]
        assert sin_su_sector == [], (ruta, sin_su_sector)


@pytest.mark.parametrize("url, datos, parche, destino", [
    ("/cajas/movimiento", {"envase_id": "1", "origen": "compra", "cantidad": "10",
                           "fecha": "2026-09-20"}, "crear_movimiento_envase", "/cajas?"),
    ("/cajas/conteo-inicial", {"envase_id": "1", "cantidad": "10", "fecha": "2026-09-20"},
     "crear_movimiento_envase", "/cajas?"),
    ("/cajas/colegas", {"nombre": "Colega EJEMPLO Dos"}, "obtener_o_crear_colega", "/cajas?"),
    ("/cajas/umbral", {"envase_id": "1", "umbral": "30"}, "guardar_umbral_de_envase", "/cajas?"),
    ("/cajas/pallet", {"envase_id": "1", "cajas": "60"}, "guardar_cajas_por_pallet", "/cajas?"),
    ("/vacios/conteo", {"proveedor_id": "7", "cantidad": "0", "fecha": "2026-09-20"},
     "crear_conteo_vacios_deposito", "/vacios?"),
    ("/vacios/7/cajon", {"tipo_cajon_id": "4"}, "asignar_tipo_cajon", "/vacios/7?"),
    ("/vacios/7/devolucion", {"compra_id": "40", "cantidad": "5"},
     "crear_devolucion_vacios", "/vacios/7?"),
    ("/vacios/devolucion/11/anular", {"proveedor_id": "7"}, "anular_devolucion_vacios",
     "/vacios/7?"),
])
def test_despues_de_GUARDAR_vuelve_al_sector_por_el_que_ENTRO(url, datos, parche, destino):
    """Las dos puertas, cada una a la suya. El redirect es el camino que no se ve al abrir."""
    for sector in ("/administracion", "/compras"):
        with patch(f"app.main.{parche}") as escritor:
            respuesta = cliente.post(f"{sector}{url}", data=datos, follow_redirects=False)
        assert respuesta.status_code == 303, (sector, respuesta.text[:300])
        assert escritor.called
        assert respuesta.headers["location"].startswith(f"{sector}{destino}"), \
            respuesta.headers["location"]


@pytest.mark.parametrize("cantidad, importe", [("0", ""), ("5", "no-es-numero"), ("5", "-3")])
def test_un_vale_mal_cargado_REBOTA_con_400_y_no_revienta(cantidad, importe):
    """Tres de las guardas del vale llamaban a la RUTA con un `status_code` que no acepta.

    `ver_vacios_de_proveedor` no tiene ese parámetro, así que el TypeError
    salía como 500 en vez del cartel. Estaba así antes de este cambio y se
    arregla acá porque es el mismo handler que gana la segunda puerta.
    """
    with _con_datos(), patch("app.main.crear_devolucion_vacios") as escritor:
        respuesta = cliente.post("/administracion/vacios/7/devolucion",
                                 data={"compra_id": "40", "cantidad": cantidad,
                                       "importe": importe})
    assert respuesta.status_code == 400
    assert not escritor.called
    assert "/compras/" not in respuesta.text


def test_el_hub_de_ADMINISTRACION_tiene_el_recuadro_y_los_otros_TRES_intactos():
    respuesta = cliente.get("/administracion")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    titulos = [t.split("</h2>")[0] for t in marcado.split("<h2>")[1:]]
    assert titulos == ["Control de stock", "Pedidos", "Facturación", "Cajas y vacíos"]
    recuadro = marcado.split("<h2>Cajas y vacíos</h2>")[1].split("</div>")[0]
    assert 'href="/administracion/cajas"' in recuadro
    assert 'href="/administracion/vacios"' in recuadro


# EL STOCK DE VACÍOS (23/09): la lista simple con sus dos exportes.
SIN_CONTEO = dict(UN_PROVEEDOR[0], id=8, nombre="Otro EJEMPLO", desde=None, contados=None,
                  stock=None, esperando_recepciones=3)


def test_el_STOCK_de_vacios_lista_proveedor_tipo_y_cantidad_y_CUENTA_los_sin_conteo():
    """El que no tiene conteo no sale en CERO: se cuenta al pie. Un cero diría
    que no hay cajones, y lo que pasa es que nadie los contó."""
    with patch("app.main.stock_de_vacios_deposito",
               return_value=[dict(UN_PROVEEDOR[0]), dict(SIN_CONTEO)]):
        respuesta = cliente.get("/administracion/vacios/stock")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert marcado.count('<div class="fila">') == 1
    assert '<span class="nombre">Puesto EJEMPLO</span>' in marcado
    assert '<span class="tipo">Cajón de ejemplo</span>' in marcado
    assert '<span class="cantidad">35</span>' in marcado
    assert "Otro EJEMPLO" not in marcado
    assert "1 proveedor con cajones cargados pero sin conteo" in marcado
    assert 'href="/administracion/vacios/stock/excel"' in marcado
    assert 'href="/administracion/vacios/stock/pdf"' in marcado


def test_el_indice_de_vacios_tiene_el_BOTON_del_stock():
    with _con_datos():
        marcado = cliente.get("/administracion/vacios").text.split("</style>")[-1]
    assert 'class="boton-stock" href="/administracion/vacios/stock"' in marcado


def test_los_EXPORTES_del_stock_de_vacios_dicen_lo_MISMO_que_la_pantalla():
    import io as _io
    from openpyxl import load_workbook
    datos = [dict(UN_PROVEEDOR[0]), dict(SIN_CONTEO)]
    with patch("app.main.stock_de_vacios_deposito", return_value=datos):
        excel = cliente.get("/administracion/vacios/stock/excel")
        pdf = cliente.get("/compras/vacios/stock/pdf")
    assert excel.status_code == 200 and pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    hoja = load_workbook(_io.BytesIO(excel.content)).active
    filas = [tuple(c.value for c in f[:3]) for f in hoja.iter_rows(min_row=5)]
    assert filas[0] == ("Puesto EJEMPLO", "Cajón de ejemplo", 35)
    assert filas[1] == (None, "Total", 35)
    assert any("1 proveedor(es) con cajones sin conteo" in str(f[0]) for f in filas)


# CAJAS POR PALLET (23/09): el mismo stock partido en pallets y sueltas.
def test_en_pallets_parte_el_stock_y_NO_parte_lo_que_no_puede():
    from core.envases import en_pallets
    assert en_pallets(130, 60) == (2, 10)
    assert en_pallets(120, 60) == (2, 0)
    # Sin el número, sin stock, o NEGATIVO: no hay pallets que decir.
    assert en_pallets(130, None) is None
    assert en_pallets(None, 60) is None
    assert en_pallets(-20, 60) is None


def test_el_pallet_REDONDEA_PARA_ABAJO_siempre_y_a_ENTERO():
    """Del dueño (25/09): 13 pallets y 283 sueltas son 13 pallets, nunca 14 ni
    13,5 — un pallet incompleto no es un pallet. El caso pegado a la raya es el
    que distingue el piso del redondeo: 599 de 300 es 1 y no 2."""
    from core.envases import en_pallets
    assert en_pallets(13 * 300 + 283, 300) == (13, 283)
    assert en_pallets(599, 300) == (1, 299)
    assert en_pallets(299, 300) == (0, 299)
    # Llegan como Decimal/float de la base: el pallet sigue siendo un ENTERO.
    pallets, sueltas = en_pallets(599.0, 300.0)
    assert (pallets, sueltas) == (1, 299) and isinstance(pallets, int)


def test_la_tarjeta_dice_PALLETS_Y_SUELTAS_y_la_que_no_tiene_el_numero_NO():
    """10 cajas de 4 por pallet = 2 pallets y 2 sueltas, cada una su número, y
    el total en cajas abajo. La chica no tiene el número cargado, así que se
    lee solo en cajas."""
    with _con_datos():
        marcado = cliente.get("/administracion/cajas").text.split("</style>")[-1]
    assert marcado.count('class="piso con-pallets"') == 1
    texto = " ".join(marcado.split())
    import re
    par = re.search(r'<div class="par">(.*?)</div> </div>', texto).group(1)
    numeros = re.findall(r'<span class="n[^"]*">([^<]*)</span> <span class="r">(\w+)</span>', par)
    assert numeros == [("2", "pallets"), ("2", "sueltas")]
    assert "10 cajas en el piso · 4 por pallet" in texto
    assert 'action="/administracion/cajas/pallet"' in marcado


def test_PALLETS_y_SUELTAS_se_ven_del_MISMO_tamano_y_el_total_mas_chico():
    """Lo que se mira en el depósito es el pallet: no puede ser el número chico.
    Medido con el CSS corrido (el atributo es la intención, no el efecto)."""
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    with _con_datos():
        html = cliente.get("/administracion/cajas").text
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        medido = pagina.evaluate("""() => {
            const piso = document.querySelector('.piso.con-pallets');
            const tam = el => parseFloat(getComputedStyle(el).fontSize);
            const [pallets, sueltas] = piso.querySelectorAll('.par .n');
            const fila = el => Math.round(el.getBoundingClientRect().top);
            return {pallets: tam(pallets), sueltas: tam(sueltas),
                    total: tam(piso.querySelector('.total-cajas')),
                    misma_fila: fila(pallets) === fila(sueltas),
                    desborde: document.documentElement.scrollWidth
                              - document.documentElement.clientWidth};
        }""")
        navegador.close()
    assert medido["pallets"] == medido["sueltas"], medido
    assert medido["pallets"] >= 20, medido
    assert medido["total"] < medido["pallets"], medido
    assert medido["misma_fila"], medido
    assert medido["desborde"] == 0, medido


@pytest.mark.parametrize("valor", ["0", "abc", "-3"])
def test_cajas_por_pallet_que_no_son_un_entero_positivo_REBOTAN(valor):
    with _con_datos(), patch("app.main.guardar_cajas_por_pallet") as guardar:
        respuesta = cliente.post("/administracion/cajas/pallet",
                                 data={"envase_id": "1", "cajas": valor},
                                 follow_redirects=False)
    assert respuesta.status_code == 400
    guardar.assert_not_called()


def test_cajas_por_pallet_VACIO_borra_el_numero():
    with _con_datos(), patch("app.main.guardar_cajas_por_pallet") as guardar:
        respuesta = cliente.post("/administracion/cajas/pallet",
                                 data={"envase_id": "1", "cajas": ""},
                                 follow_redirects=False)
    assert respuesta.status_code == 303
    guardar.assert_called_once_with(1, None)

