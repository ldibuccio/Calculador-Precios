"""El panel de "el súper cambió el pedido", que vive en LAS DOS pantallas.

El que arma es el que atiende el teléfono. Hasta el 20/09 corregir un bulto
desde Armar era ir a la otra pantalla, corregir, y volver — y volver no
existía como botón. Lo que estos tests cuidan es que el panel sea UNO SOLO
(no dos copias que se separan) y que el POST devuelva al que lo usó a la
pantalla de la que salió.
"""

import io
import re
from datetime import date, datetime
from unittest.mock import patch

from tests.test_app import (
    CLIENTES_PARA_SELECTOR,
    FICHAS_ARMADO_CON_CONTENIDO,
    PEDIDO_VIGENTE_DE_PRUEBA,
    RENGLONES_ARMADO_DE_PRUEBA,
    SUCURSALES_PEDIDO_DE_PRUEBA,
    cliente,
)

PARTIAL = "templates/_cambio_el_pedido.html"
ARMAR = "templates/deposito_pedido_armar.html"
CORREGIR = "templates/deposito_pedido.html"


def _leer(ruta):
    return io.open(ruta, encoding="utf-8").read()


def _armar(renglones=None):
    """La pantalla de Armar, parada en una sucursal."""
    with (
        patch("app.main._hoy_argentina", return_value=date(2026, 8, 21)),
        patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR),
        patch("app.main.listar_pedidos_vigentes_con_armado", return_value=[]),
        patch("app.main.obtener_pedido_vigente", return_value=PEDIDO_VIGENTE_DE_PRUEBA),
        patch("app.main.listar_sucursales_pedido",
              return_value=[dict(s) for s in SUCURSALES_PEDIDO_DE_PRUEBA]),
        patch("app.main.listar_renglones_pedido",
              return_value=renglones if renglones is not None else RENGLONES_ARMADO_DE_PRUEBA),
        patch("app.main.fichas_con_cajas_armadas", return_value=set()),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_ARMADO_CON_CONTENIDO),
        patch("app.main.listar_mails_pedido_sin_procesar_de_cliente", return_value=[]),
    ):
        return cliente.get("/deposito/pedido/armar?cliente_id=1&fecha=2026-08-21&sucursal=VL")


def _marcado(respuesta):
    return respuesta.text.split("</style>")[-1]


# ----------------------------------------------------------------- el partial

def test_el_panel_sale_del_MISMO_partial_en_las_DOS_pantallas():
    """Una copia por pantalla se separa, y la que quede vieja ofrece otra cosa.

    Se pregunta por el IMPORT —que es lo que ata las dos a un solo archivo—
    y además por lo que NO puede estar: el `<form>` del alta escrito a mano
    en la pantalla. Afirmar solo el import pasa igual si alguien deja la
    copia vieja tres líneas más abajo.
    """
    for ruta in (ARMAR, CORREGIR):
        texto = _leer(ruta)
        assert '{% import "_cambio_el_pedido.html" as cambio %}' in texto, ruta
        assert "cambio.panel(" in texto, ruta
        assert 'class="alta-renglon"' not in texto, f"{ruta} tiene su propia copia del alta"
        assert "renglones/agregar" not in texto, f"{ruta} postea el alta por su cuenta"


def test_el_partial_es_el_UNICO_que_escribe_los_dos_POST_del_panel():
    """El conjunto ENCONTRADO contra el DECIDIDO: la tercera pantalla no la recuerda nadie."""
    import glob

    escriben = {
        ruta for ruta in glob.glob("templates/*.html")
        if "renglones/agregar" in _leer(ruta) or re.search(r"renglones/\{\{[^}]+\}\}/cantidad", _leer(ruta))
    }
    assert escriben == {PARTIAL}, escriben


def test_el_ESTILO_del_partial_va_ANTES_del_de_la_pantalla():
    """Si quedara último, `split("</style>")[-1]` se llevaría la pantalla entera.

    Es el corolario 50 en su forma silenciosa: los asserts por la negativa
    sobre un pedazo que ya no tiene la pantalla adentro pasan SIEMPRE, y un
    test apagado se ve igual que uno que mira.
    """
    for respuesta in (_armar(), _corregir()):
        bloques = re.findall(r"<style>(.*?)</style>", respuesta.text, re.S)
        assert len(bloques) >= 2, "no se emitieron los dos estilos"
        assert ".boton-tocar" in bloques[0], "el estilo del partial no es el primero"
        assert ".boton-tocar" not in bloques[-1], "el estilo del partial quedó último"


def _corregir():
    """La pantalla de Corregir lo que pidieron, con el mismo pedido."""
    with (
        patch("app.main._hoy_argentina", return_value=date(2026, 8, 21)),
        patch("app.main.listar_clientes", return_value=CLIENTES_PARA_SELECTOR),
        patch("app.main.listar_pedidos_vigentes_con_armado", return_value=[]),
        patch("app.main.obtener_condiciones_pedido", return_value=None),
        patch("app.main.listar_mails_pedido_sin_procesar_de_cliente", return_value=[]),
        patch("app.main.obtener_pedido_vigente", return_value=PEDIDO_VIGENTE_DE_PRUEBA),
        patch("app.main.listar_sucursales_pedido",
              return_value=[dict(s) for s in SUCURSALES_PEDIDO_DE_PRUEBA]),
        patch("app.main.listar_renglones_pedido", return_value=RENGLONES_ARMADO_DE_PRUEBA),
        patch("app.main.fichas_con_cajas_armadas", return_value=set()),
        patch("app.main.listar_fotos_pedido", return_value=[]),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS_ARMADO_CON_CONTENIDO),
    ):
        return cliente.get("/deposito/pedido?cliente_id=1&fecha=2026-08-21")


# --------------------------------------------------------- la vuelta del POST

def _formularios_del_panel(marcado):
    """Los `<form>` de adentro del panel, uno por uno y con su denominador.

    UN `in` sobre el marcado entero no sirve, y el canario lo dijo: el panel
    tiene un formulario por renglón MÁS el del alta, así que con el hidden
    puesto en uno solo el assert pasa igual. Y el que se pierde es el de la
    cantidad —el que se usa todos los días— que sin `volver_a` devuelve al
    operario a la otra pantalla en el medio del armado.
    """
    panel = marcado[marcado.index('class="panel-tocar"'):]
    panel = panel[:panel.index("</div>", panel.index('class="alta-renglon"'))]
    formularios = [f"<form{f}" for f in panel.split("<form")[1:]]
    assert len(formularios) >= 2, "el panel quedó sin formularios que mirar"
    return formularios


def test_TODOS_los_formularios_del_panel_de_ARMAR_piden_volver_a_armar():
    formularios = _formularios_del_panel(_marcado(_armar()))
    conteo = sum('name="volver_a" value="armar"' in f for f in formularios)
    assert conteo == len(formularios), (
        f"solo {conteo} de {len(formularios)} formularios del panel vuelven a Armar")
    # Y el del alta es uno de ellos: sin este renglón, el conteo de arriba se
    # cumple igual el día que el panel deje de listar el alta.
    assert any("renglones/agregar" in f for f in formularios)
    assert any("/cantidad" in f for f in formularios)


def test_el_panel_de_CORREGIR_no_pide_volver_a_armar():
    formularios = _formularios_del_panel(_marcado(_corregir()))
    assert all('name="volver_a" value=""' in f for f in formularios)
    assert not any('value="armar"' in f for f in formularios)


def test_corregir_una_cantidad_DESDE_ARMAR_vuelve_a_armar_en_su_sucursal():
    with patch("app.main.corregir_cantidad_renglon", return_value=True):
        respuesta = cliente.post(
            "/deposito/pedido/7/renglones/11/cantidad",
            data={"cliente_id": "1", "fecha": "2026-08-21", "cantidad": "9",
                  "sucursal": "VL", "volver_a": "armar"},
            follow_redirects=False,
        )
    assert respuesta.status_code == 303
    destino = respuesta.headers["location"]
    assert destino.startswith("/deposito/pedido/armar?")
    assert "sucursal=VL" in destino, "vuelve a Armar pero no a la sucursal que estaba armando"


def test_agregar_un_renglon_DESDE_ARMAR_vuelve_a_armar():
    with patch("app.main.agregar_renglon_a_pedido"):
        respuesta = cliente.post(
            "/deposito/pedido/7/renglones/agregar",
            data={"cliente_id": "1", "fecha": "2026-08-21", "ficha_id": "1",
                  "sucursal": "VL", "cantidad": "4", "volver_a": "armar"},
            follow_redirects=False,
        )
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/deposito/pedido/armar?")


def test_SIN_volver_a_los_dos_POST_siguen_yendo_a_corregir():
    """El caso que tiene que PASAR: sin él, un helper que mandara siempre a
    Armar pasaría los dos tests de arriba y rompería la pantalla vieja."""
    with patch("app.main.corregir_cantidad_renglon", return_value=True):
        uno = cliente.post(
            "/deposito/pedido/7/renglones/11/cantidad",
            data={"cliente_id": "1", "fecha": "2026-08-21", "cantidad": "9"},
            follow_redirects=False,
        )
    with patch("app.main.agregar_renglon_a_pedido"):
        dos = cliente.post(
            "/deposito/pedido/7/renglones/agregar",
            data={"cliente_id": "1", "fecha": "2026-08-21", "ficha_id": "1",
                  "sucursal": "VL", "cantidad": "4"},
            follow_redirects=False,
        )
    for respuesta in (uno, dos):
        assert respuesta.status_code == 303
        assert respuesta.headers["location"].startswith("/deposito/pedido?")


def test_la_url_de_vuelta_la_arma_el_SERVER_y_no_el_formulario():
    """`volver_a` es un valor CERRADO. Con la url adentro del hidden, un
    formulario armado a mano elige a dónde mandar al operario DESPUÉS de
    escribir en la base — y eso lo decide el sistema, no el que postea."""
    from app.main import VUELTAS_DEL_CAMBIO_DE_PEDIDO, _vuelta_del_cambio_de_pedido

    assert set(VUELTAS_DEL_CAMBIO_DE_PEDIDO) == {"", "armar"}
    for intruso in ("https://otro.example/ea", "/administracion/stock", "armar/../x"):
        destino = _vuelta_del_cambio_de_pedido(intruso, 1, "2026-08-21", "VL", "ok")
        assert destino.startswith("/deposito/pedido?"), destino


# --------------------------------------------------------------- qué se lista

def test_el_panel_de_ARMAR_no_ofrece_los_ANULADOS():
    """`corregir_cantidad_renglon` los rechaza: ofrecerlos es un callejón.

    El anulado lleva un nombre PROPIO a propósito — con el mismo nombre que
    un pendiente, el assert no podría distinguirlos y pasaría siempre.
    """
    renglones = [dict(r) for r in RENGLONES_ARMADO_DE_PRUEBA] + [
        {"id": 99, "sucursal": "VL", "articulo_id": 3, "articulo_nombre": "Zapallo",
         "ficha_id": 903, "nombre_venta": "ZAPALLO ANULADO", "texto_codigo": "90103",
         "texto_descripcion": "ZAPALLO", "cantidad": 7.0, "armado_el": None,
         "cantidad_armada": None, "kilos_enviados": None,
         "anulado_el": datetime(2026, 8, 21, 10, 0),
         "agregado_a_mano_el": None, "cantidad_original": None},
    ]
    marcado = _marcado(_armar(renglones))
    panel = marcado[marcado.index('class="panel-tocar"'):marcado.index('class="alta-renglon"')]
    assert "Banana" in panel and "Batata" in panel, "el panel quedó sin renglones que mirar"
    assert "ZAPALLO ANULADO" not in panel


def test_la_IDA_y_la_VUELTA_entre_las_dos_pantallas_existen_las_dos():
    ida = _marcado(_corregir())
    assert 'href="/deposito/pedido/armar?cliente_id=1&fecha=2026-08-21"' in ida
    vuelta = _marcado(_armar())
    assert 'href="/deposito/pedido?cliente_id=1&fecha=2026-08-21"' in vuelta


# -------------------------------------------------------- los tres del menú

def test_los_TRES_bloques_del_menu_tienen_TRES_colores_DISTINTOS():
    """Y el violeta NO entra: ya significa EL LOTE en las pantallas a las que
    el propio menú lleva (`.boton-guardar-lotes`, `.boton-lotes`, el número de
    guía R). El mismo color diciendo dos cosas según la pantalla es justo lo
    que la decisión del dueño venía a evitar."""
    css = _leer("templates/deposito.html").split("</style>")[0]
    colores = {
        bloque: re.search(rf"\.boton\.{bloque}\s*{{[^}}]*background:\s*(#[0-9a-f]{{6}})", css).group(1)
        for bloque in ("ingresos", "pedidos", "stock")
    }
    assert len(set(colores.values())) == 3, colores
    assert "#7c3aed" not in colores.values() and "#6d28d9" not in colores.values(), colores


def test_cada_boton_del_menu_LLEVA_la_clase_de_su_bloque():
    """Sin la clase, el botón cae al `.boton` pelado y se pinta de otro color
    — o de ninguno. Se cuentan los once contra su denominador: un assert de
    "aparece la clase" pasa con uno solo puesto."""
    marcado = _leer("templates/deposito.html").split("</style>")[-1]
    botones = re.findall(r'<a class="boton ([a-z]+)"', marcado)
    assert len(botones) == len(re.findall(r'<a class="boton', marcado)), \
        "hay botones del menú sin clase de bloque"
    assert botones.count("ingresos") == 4
    assert botones.count("pedidos") == 1
    assert botones.count("stock") == 5


# ------------------------------------------- el pie, que cambia en cada commit

def test_ningun_assert_NUMERICO_por_la_negativa_mira_la_pagina_CON_EL_PIE():
    """El pie dice `v938` hoy y `v939` mañana, en TODAS las pantallas.

    Un `assert "38" not in texto` sobre la página entera no pregunta por el
    38 del artículo: matchea el número de versión, que es el vecino
    (corolario 4). Y el modo de falla es el peor — **pasa donde se escribe y
    se cae donde decide**: el sello corre después de la suite local, así que
    acá la página dice v937 y en el runner v938. Costó una corrida roja el
    20/09.

    Se compara el conjunto ENCONTRADO contra el DECIDIDO (corolario 60), así
    que falla en las dos direcciones: cuando aparece un assert nuevo sin
    `sin_pie`, y cuando uno de la lista deja de necesitarlo.
    """
    import ast as _ast

    fuente = io.open("tests/test_app.py", encoding="utf-8").read()
    encontrados = set()
    for nodo in _ast.walk(_ast.parse(fuente)):
        if not isinstance(nodo, _ast.FunctionDef):
            continue
        cuerpo = _ast.unparse(nodo)
        for m in re.finditer(r"assert\s+'(\d{1,4})'\s+not in\s+(\w+)(\.lower\(\))?\b", cuerpo):
            variable = m.group(2)
            # La variable sale DERECHO de la respuesta (sin filtrar por regex
            # ni recortar): ahí adentro viaja el pie.
            if re.search(rf"\b{variable}\s*=\s*[\w.()\[\]]*\.text\b", cuerpo):
                encontrados.add((nodo.name, m.group(1)))

    # NINGUNO: el del remanente pasó a `sin_pie(texto)`, que es la forma. Si
    # mañana hace falta uno, entra acá CON SU RAZÓN — no se afloja el test.
    DECIDIDOS = set()
    assert encontrados == DECIDIDOS, (
        f"asserts numéricos por la negativa sobre la página CON el pie: {encontrados}. "
        f"Van con `sin_pie(...)`, o el día que la versión contenga ese número "
        f"el CI se cae y acá sale verde."
    )


def test_sin_pie_SACA_el_pie_y_DEJA_la_pantalla():
    """El par completo (corolario 53): lo que tiene que sacar y lo que no.

    Con solo lo primero, un helper que devuelva la cadena vacía pasa igual.
    """
    from tests.test_app import sin_pie

    pagina = '<body><p>EL-CONTENIDO 38</p><footer ...>v938 · sin commit</footer></body>'
    recortado = sin_pie(pagina)
    assert "v938" not in recortado
    assert "EL-CONTENIDO 38" in recortado
