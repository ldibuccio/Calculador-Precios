"""El caso que habilitó la Parte 3: DOS fichas del mismo artículo para un cliente.

Día compra "Banana Bolivia" y "Banana Ecuador": dos fichas distintas, con
su nombre, su código, su kilaje y su precio, del MISMO artículo de compra
(Banana). Se compra una sola banana, hay un solo stock de banana, y las dos
fichas salen de ahí.

Hasta la Parte 3 esto era imposible: fichas_logistica tenía unique
(articulo_id, cliente_id). Estos tests son la red de seguridad de lo que ese
drop destapó — todo lo que antes podía usar "cliente + artículo" como si
fuera único y ahora tiene que hablar de FICHA.

La convención de los ids es la de siempre: la ficha es 900 + algo, a
propósito distinta del artículo, para que confundir las dos claves rompa el
test en vez de pasar desapercibido.
"""

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import (
    _alias_de_fichas,
    _armar_renglones_pedido_desde_bloque,
    _ayudas_ficha_por_cliente_y_articulo,
    _nombre_de_ficha,
    app,
)

cliente = TestClient(app)

CLIENTE_DIA = [{"id": 1, "nombre": "Día", "utilidad_objetivo": 20.0}]

# Las dos fichas del artículo 1 (Banana). Kilajes distintos a propósito: es
# lo que hace que mostrar el de la otra sea armar la caja mal.
BANANA_BOLIVIA = {
    "id": 901, "cliente_id": 1, "articulo_id": 1, "articulo_nombre": "Banana", "articulo_grupo": "fruta",
    "envase_id": None, "envase_nombre": None, "contenido_caja": 6, "unidad_venta": "kilo",
    "envase_variable": False, "nombre_cliente": "BANANA BOLIVIA", "codigo_cliente": "90101",
}
BANANA_ECUADOR = {
    "id": 902, "cliente_id": 1, "articulo_id": 1, "articulo_nombre": "Banana", "articulo_grupo": "fruta",
    "envase_id": None, "envase_nombre": None, "contenido_caja": 10, "unidad_venta": "kilo",
    "envase_variable": False, "nombre_cliente": "BANANA ECUADOR", "codigo_cliente": "90102",
}
DOS_FICHAS = [BANANA_BOLIVIA, BANANA_ECUADOR]


def _renglones_de(bloque):
    por_codigo, por_nombre = _alias_de_fichas(DOS_FICHAS)
    return _armar_renglones_pedido_desde_bloque(bloque, DOS_FICHAS, por_codigo, por_nombre)


def _bloque(codigo="", descripcion="", cantidad=5):
    return {"renglones": [{"codigo": codigo, "descripcion": descripcion, "cantidades": {"VL": cantidad}}]}


# --- el matcheo del pedido cae en LA ficha, no en el artículo ---


def test_cada_codigo_cae_en_su_ficha_y_las_dos_comparten_el_articulo():
    bolivia = _renglones_de(_bloque(codigo="90101"))[0]
    ecuador = _renglones_de(_bloque(codigo="90102"))[0]

    assert bolivia["ficha_id"] == 901
    assert ecuador["ficha_id"] == 902
    # Misma clave de COMPRA: las dos descuentan del mismo stock de Banana.
    assert bolivia["articulo_id"] == ecuador["articulo_id"] == 1
    assert bolivia["match_por"] == ecuador["match_por"] == "codigo"


def test_el_nombre_exacto_tambien_distingue_las_dos_fichas():
    assert _renglones_de(_bloque(descripcion="BANANA ECUADOR"))[0]["ficha_id"] == 902
    assert _renglones_de(_bloque(descripcion="BANANA BOLIVIA"))[0]["ficha_id"] == 901


def test_la_sugerencia_difusa_compara_contra_el_nombre_del_cliente_no_el_del_catalogo():
    # Antes la sugerencia comparaba contra el catálogo ("Banana") y había que
    # traducir a ficha: con dos fichas del mismo artículo, esa traducción no
    # tenía forma de elegir. Ahora compara contra el nombre de cada ficha.
    renglon = _renglones_de(_bloque(descripcion="BANANA ECUADO"))[0]

    assert renglon["ficha_id"] == 902
    assert renglon["match_por"] == "sugerencia"


def test_un_codigo_desconocido_no_cae_en_ninguna_de_las_dos():
    renglon = _renglones_de(_bloque(codigo="77777", descripcion="COSA RARA"))[0]

    assert renglon["ficha_id"] is None
    assert renglon["articulo_id"] is None
    assert renglon["advertencia"] is True


# --- el nombre que se muestra ---


def test_el_nombre_visible_es_el_de_la_ficha_y_cae_al_del_articulo_si_esta_vacio():
    assert _nombre_de_ficha(BANANA_ECUADOR) == "BANANA ECUADOR"
    assert _nombre_de_ficha({**BANANA_ECUADOR, "nombre_cliente": None}) == "Banana"
    # Un nombre en blanco es como no tenerlo: no se muestra un renglón vacío.
    assert _nombre_de_ficha({**BANANA_ECUADOR, "nombre_cliente": "   "}) == "Banana"


# --- las ayudas de kilaje que ve el operario ---


def test_la_ayuda_de_kilaje_nombra_las_dos_fichas_con_el_suyo():
    # La guía R no guarda con qué ficha se armó, así que elegir una sería
    # adivinar — y mostrarle al operario el kilaje de la otra es armar mal.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTE_DIA),
        patch("app.main.listar_fichas_de_todos_los_clientes", return_value=DOS_FICHAS),
    ):
        ayudas = _ayudas_ficha_por_cliente_y_articulo()

    ayuda = ayudas["1:1"]
    assert "BANANA BOLIVIA: 6 kg" in ayuda
    assert "BANANA ECUADOR: 10 kg" in ayuda
    assert "fijate cuál estás armando" in ayuda


def test_con_una_sola_ficha_la_ayuda_queda_como_siempre():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTE_DIA),
        patch("app.main.listar_fichas_de_todos_los_clientes", return_value=[BANANA_BOLIVIA]),
    ):
        ayudas = _ayudas_ficha_por_cliente_y_articulo()

    assert ayudas["1:1"] == "6 kg por caja, según la ficha de Día."


# Acá vivían los dos tests de `_tamanos_de_caja_por_ficha` ("6 kg o 10 kg"
# cuando la guía R no decía con qué ficha se armó). La función se borró el
# 06/09 junto con Stock del Sistema, que era su único lector: la ambigüedad
# existía porque esa pantalla desglosaba POR GUÍA R, y una guía R no guarda la
# ficha. El Remanente lista POR FICHA —cada una es su propio renglón, con su
# nombre— así que no hay dos tamaños posibles que mostrar. No es una prueba
# que se perdió: es un caso que dejó de existir.


# --- las pantallas ---


PRECIOS_DE_LAS_DOS = [
    {"ficha_id": 901, "articulo_id": 1, "precio": 800.0, "vigente_desde": date(2026, 8, 26)},
    {"ficha_id": 902, "articulo_id": 1, "precio": 1200.0, "vigente_desde": date(2026, 8, 20)},
]


def test_la_carga_de_precios_ofrece_las_dos_fichas_con_su_propio_precio():
    # El agujero que cerró la Parte 1, visible por primera vez: dos fichas
    # del mismo artículo, cada una con su precio. Por artículo, las dos
    # habrían mostrado el mismo.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTE_DIA),
        patch("app.main.listar_fichas_por_cliente", return_value=DOS_FICHAS),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_DE_LAS_DOS),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
    ):
        respuesta = cliente.get("/precios/cargar?cliente_id=1")

    assert respuesta.status_code == 200
    assert 'id: 901,\n        nombre: "BANANA BOLIVIA",\n        precioVigente: 800.0,' in respuesta.text
    assert 'id: 902,\n        nombre: "BANANA ECUADOR",\n        precioVigente: 1200.0,' in respuesta.text


def test_la_consulta_de_precios_lista_las_dos_por_separado():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTE_DIA),
        patch("app.main._hoy_argentina", return_value=date(2026, 8, 26)),
        patch("app.main.listar_fichas_por_cliente", return_value=DOS_FICHAS),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=PRECIOS_DE_LAS_DOS),
    ):
        respuesta = cliente.get("/precios/consultar?cliente_id=1")

    assert "$800" in respuesta.text and "$1.200" in respuesta.text
    # Y con su propio nombre: dos renglones que dijeran "Banana" serían
    # indistinguibles justo en la pantalla que se usa para facturar.
    assert "BANANA BOLIVIA" in respuesta.text and "BANANA ECUADOR" in respuesta.text


RENGLONES_ARMADO = [
    {"id": 10, "sucursal": "VL", "articulo_id": 1, "articulo_nombre": "Banana",
     "ficha_id": 902, "nombre_venta": "BANANA ECUADOR", "texto_codigo": "90102",
     "texto_descripcion": "BANANA ECUADOR", "cantidad": 5.0, "armado_el": None,
     "cantidad_armada": None, "kilos_enviados": None, "anulado_el": None},
    {"id": 11, "sucursal": "VL", "articulo_id": 1, "articulo_nombre": "Banana",
     "ficha_id": 901, "nombre_venta": "BANANA BOLIVIA", "texto_codigo": "90101",
     "texto_descripcion": "BANANA BOLIVIA", "cantidad": 3.0, "armado_el": None,
     "cantidad_armada": None, "kilos_enviados": None, "anulado_el": None},
]

PEDIDO_DE_PRUEBA = {
    "id": 50, "cliente_id": 1, "fecha_operacion": date(2026, 8, 26), "origen": "texto",
    "recibido_el": None, "reemplaza_a_pedido_id": None, "creado_en": None,
    "armado_cerrado_el": None, "reemplazado_creado_en": None,
}


def test_armar_pedido_muestra_el_nombre_de_la_ficha_no_el_del_articulo():
    # El punto crítico: el que arma tiene que saber qué caja usar. Las dos
    # filas son del artículo Banana; si las dos dijeran "Banana", no habría
    # forma de distinguirlas.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTE_DIA),
        patch("app.main._hoy_argentina", return_value=date(2026, 8, 26)),
        patch("app.main.obtener_pedido_vigente", return_value=PEDIDO_DE_PRUEBA),
        patch("app.main.listar_sucursales_pedido", return_value=[
            {"id": 1, "sucursal": "VL", "orden_compra": "123", "total_bultos_declarado": 8},
        ]),
        patch("app.main.listar_renglones_pedido", return_value=RENGLONES_ARMADO),
        patch("app.main.fichas_con_cajas_armadas", return_value=set()),
        patch("app.main.listar_mails_pedido_sin_procesar_de_cliente", return_value=[]),
        patch("app.main.listar_fichas_por_cliente", return_value=DOS_FICHAS),
    ):
        respuesta = cliente.get("/deposito/pedido/armar?cliente_id=1&fecha=2026-08-26&sucursal=VL")

    assert respuesta.status_code == 200
    assert "BANANA ECUADOR" in respuesta.text
    assert "BANANA BOLIVIA" in respuesta.text


def test_armar_pedido_sugiere_los_kilos_de_SU_ficha_no_los_de_la_otra():
    # Los kilos sugeridos se facturan: 5 bultos de Banana Ecuador son 50 kg
    # (caja de 10), y 3 de Banana Bolivia son 18 (caja de 6). Buscando el
    # kilaje por artículo, las dos habrían salido con el mismo número.
    with (
        patch("app.main.listar_clientes", return_value=CLIENTE_DIA),
        patch("app.main._hoy_argentina", return_value=date(2026, 8, 26)),
        patch("app.main.obtener_pedido_vigente", return_value=PEDIDO_DE_PRUEBA),
        patch("app.main.listar_sucursales_pedido", return_value=[
            {"id": 1, "sucursal": "VL", "orden_compra": "123", "total_bultos_declarado": 8},
        ]),
        patch("app.main.listar_renglones_pedido", return_value=RENGLONES_ARMADO),
        patch("app.main.fichas_con_cajas_armadas", return_value=set()),
        patch("app.main.listar_mails_pedido_sin_procesar_de_cliente", return_value=[]),
        patch("app.main.listar_fichas_por_cliente", return_value=DOS_FICHAS),
    ):
        respuesta = cliente.get("/deposito/pedido/armar?cliente_id=1&fecha=2026-08-26&sucursal=VL")

    assert "Manda 5 bultos × 10 kg = 50 kg." in respuesta.text   # Ecuador
    assert "Manda 3 bultos × 6 kg = 18 kg." in respuesta.text    # Bolivia


def test_confirmar_pedido_guarda_las_dos_fichas_como_renglones_distintos():
    # Dos renglones del MISMO artículo con FICHAS distintas: es lo que antes
    # quedaba idéntico en la base y nada río abajo podía distinguir.
    with (
        patch("app.main._hoy_argentina", return_value=date(2026, 8, 26)),
        patch("app.main.obtener_pedido_vigente", return_value=None),
        patch("app.main.listar_fichas_por_cliente", return_value=DOS_FICHAS),
        patch("app.main.crear_pedido", return_value=50) as mock_crear,
    ):
        respuesta = cliente.post(
            "/deposito/pedido/cargar/confirmar",
            data={
                "cliente_id": "1", "fecha": "2026-08-26", "cantidad_sucursales": "1",
                "sucursal_0_nombre": "VL", "sucursal_0_oc": "123", "sucursal_0_total": "8",
                "cantidad_renglones": "2",
                "renglon_0_codigo": "90101", "renglon_0_descripcion": "BANANA BOLIVIA",
                "renglon_0_ficha_id": "901", "renglon_0_cant_0": "3",
                "renglon_1_codigo": "90102", "renglon_1_descripcion": "BANANA ECUADOR",
                "renglon_1_ficha_id": "902", "renglon_1_cant_0": "5",
            },
            follow_redirects=False,
        )

    assert respuesta.status_code == 303
    renglones = mock_crear.call_args[0][5]  # (cliente, fecha, origen, texto, sucursales, renglones)
    assert {"sucursal": "VL", "articulo_id": 1, "ficha_id": 901, "texto_codigo": "90101",
            "texto_descripcion": "BANANA BOLIVIA", "cantidad": 3.0} in renglones
    assert {"sucursal": "VL", "articulo_id": 1, "ficha_id": 902, "texto_codigo": "90102",
            "texto_descripcion": "BANANA ECUADOR", "cantidad": 5.0} in renglones
