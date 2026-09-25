"""Las DOS marcas que pone Depósito al recibir (dueño, 25/09).

- La de la MERCADERÍA: texto libre, opcional, en blanco = "sin asignar".
- La del VACÍO: solo si la compra dejó seña, elegida de las marcas cargadas
  en Vacíos para ESE proveedor, opcional.

Las dos se ven después en el Detalle de la compra, y la del vacío decide a
qué PILA van esos cajones en el stock de Vacíos.

La mitad que importa corre CONTRA POSTGRES: que la marca sea del proveedor
lo decide la FK compuesta de la base, y con la base mockeada eso no lo
arbitra nadie (corolario 89). Las pantallas van con la base mockeada.
"""
import os
import re
import sys
from copy import deepcopy
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402
from tests.test_app import (  # noqa: E402
    COMPRA_DETALLE_DE_PRUEBA,
    COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA,
    HOY_DE_PRUEBA,
    cliente,
)

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
DIA = date(2026, 3, 10)


# --- contra la base -------------------------------------------------------

@pytest.fixture
def galpon(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: las marcas de recepción no se verificaron")
        pytest.skip("sin Postgres local")
    monkeypatch.setenv("DATABASE_URL", preparar_base())
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

    (art,), = sql("INSERT INTO articulos (nombre) VALUES ('EJEMPLO Fruta Marca') RETURNING id")
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES ('EJEMPLO Puesto Marca', 'N92P01') RETURNING id")
    (otro,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES ('EJEMPLO Otro Marca', 'N92P02') RETURNING id")
    roja = d.crear_marca_vacio(prov, "EJ Roja")
    ajena = d.crear_marca_vacio(otro, "EJ Ajena")

    def compra(sena):
        d.crear_compra(DIA, art, prov, 10, 16, 160, None, 50000, sena, "Clark",
                       segunda_por_cajon=None)
        (compra_id,), = sql("SELECT max(id) FROM compras")
        return compra_id

    def estado(compra_id):
        fila, = sql("SELECT estado, marca, marca_vacio_id FROM compras WHERE id = %s", (compra_id,))
        return fila

    return d, compra, estado, prov, roja, ajena


def test_las_DOS_marcas_se_guardan_y_el_detalle_las_NOMBRA(galpon):
    d, compra, estado, _, roja, _ = galpon
    compra_id = compra(sena=500)

    d.recepcionar_compra(compra_id, 10, 16, marca="  EJ Granny  ", marca_vacio_id=roja)

    assert estado(compra_id) == ("recepcionado", "EJ Granny", roja)
    detalle = d.obtener_detalle_compra(compra_id)
    assert (detalle["marca"], detalle["marca_vacio"]) == ("EJ Granny", "EJ Roja")


def test_en_blanco_las_dos_quedan_SIN_ASIGNAR_y_no_en_texto_vacio(galpon):
    d, compra, estado, _, _, _ = galpon
    compra_id = compra(sena=500)

    d.recepcionar_compra(compra_id, 10, 16, marca="   ", marca_vacio_id=None)

    assert estado(compra_id) == ("recepcionado", None, None)


def test_una_marca_de_OTRO_proveedor_la_rechaza_la_base_y_no_se_recibe_nada(galpon):
    d, compra, estado, _, _, ajena = galpon
    compra_id = compra(sena=500)

    with pytest.raises(ValueError, match="no es de este proveedor"):
        d.recepcionar_compra(compra_id, 10, 16, marca="EJ Granny", marca_vacio_id=ajena)

    # La recepción entera se deshace: ni el estado ni la marca de la mercadería.
    assert estado(compra_id) == ("pendiente", None, None)


def test_SIN_SENA_no_hay_marca_de_vacio_que_poner(galpon):
    d, compra, estado, _, roja, _ = galpon
    compra_id = compra(sena=None)

    with pytest.raises(ValueError, match="no dejó seña"):
        d.recepcionar_compra(compra_id, 10, 16, marca_vacio_id=roja)
    assert estado(compra_id) == ("pendiente", None, None)

    # El control: la misma compra sin marca de vacío SÍ se recibe, con la de
    # la mercadería puesta. Sin este caso, una guarda que frenara siempre
    # pasaría el de arriba igual (corolario 30).
    d.recepcionar_compra(compra_id, 10, 16, marca="EJ Granny")
    assert estado(compra_id) == ("recepcionado", "EJ Granny", None)


def test_el_RECHAZO_PARCIAL_tambien_guarda_las_marcas(galpon):
    d, compra, estado, _, roja, _ = galpon
    compra_id = compra(sena=500)

    d.recepcionar_compra(compra_id, 8, 16, cantidad_cajones_rechazada=2,
                         motivo_rechazo="golpeado", marca="EJ Granny", marca_vacio_id=roja)

    assert estado(compra_id) == ("recepcionado", "EJ Granny", roja)


def test_los_cajones_recibidos_van_a_la_PILA_de_la_marca_elegida(galpon):
    """Es para lo que existe la marca del vacío: el remanente por proveedor y marca."""
    d, compra, _, prov, roja, _ = galpon
    con_marca = compra(sena=500)
    sin_marca = compra(sena=500)

    d.recepcionar_compra(con_marca, 10, 16, marca_vacio_id=roja)
    d.recepcionar_compra(sin_marca, 7, 16)

    proveedor, = [p for p in d.stock_de_vacios_deposito() if p["id"] == prov]
    pilas = {p["marca"]: p["stock"] for p in proveedor["pilas"]}
    assert pilas == {None: 7, "EJ Roja": 10}
    assert proveedor["stock"] == 17


# --- las pantallas --------------------------------------------------------

def _pendientes(**cambios):
    compras = deepcopy(COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA)
    # 1: con seña y el proveedor con marcas · 2: sin seña · 3: con seña y sin marcas
    compras[0].update(proveedor_id=501, sena=500)
    compras[1].update(proveedor_id=501, sena=None)
    compras[2].update(proveedor_id=502, sena=300)
    for compra_id, datos in cambios.items():
        compras[int(compra_id) - 1].update(datos)
    return compras


MARCAS = {501: [{"id": 7, "nombre": "EJ Roja"}, {"id": 8, "nombre": "EJ Azul"}],
          999: [{"id": 9, "nombre": "EJ De Otro"}]}


def _recepcion():
    with (
        patch("app.main.listar_compras_pendientes_recepcion", return_value=_pendientes()),
        patch("app.main.listar_compras_procesadas_hoy_recepcion", return_value=[]),
        patch("app.main.listar_marcas_vacio_por_proveedor", return_value=MARCAS),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
    ):
        respuesta = cliente.get("/deposito/recepcion")
    assert respuesta.status_code == 200
    return respuesta.text.split("</style>")[-1]


def _renglon(marcado, compra_id):
    """El pedazo de la pantalla de UNA compra: del form de recibir hasta el
    próximo renglón. Anclado en la `action`, que solo puede ser marcado."""
    inicio = marcado.index(f'action="/deposito/recepcion/{compra_id}/recepcionar"')
    siguiente = marcado.find('<div class="renglon">', inicio)
    return marcado[inicio: siguiente if siguiente != -1 else len(marcado)]


def test_la_marca_de_la_MERCADERIA_esta_en_las_DOS_puertas_de_cada_compra():
    marcado = _recepcion()
    for compra_id in (1, 2, 3):
        renglon = _renglon(marcado, compra_id)
        # Recibir y el rechazo parcial: las dos recepcionan, las dos la llevan.
        assert renglon.count('name="marca"') == 2, compra_id
        assert f'action="/deposito/recepcion/{compra_id}/rechazo-parcial"' in renglon


def test_la_marca_del_VACIO_solo_con_sena_y_solo_con_las_marcas_de_ESE_proveedor():
    marcado = _recepcion()
    con_marcas, sin_sena, sin_marcas = (_renglon(marcado, i) for i in (1, 2, 3))

    assert con_marcas.count('name="marca_vacio_id"') == 2
    opciones = re.findall(r'<option value="(\d*)">([^<]+)</option>', con_marcas)
    assert opciones[:3] == [("", "Sin asignar"), ("7", "EJ Roja"), ("8", "EJ Azul")]
    assert "EJ De Otro" not in con_marcas

    assert 'name="marca_vacio_id"' not in sin_sena
    assert "no tiene marcas cargadas" not in sin_sena

    assert 'name="marca_vacio_id"' not in sin_marcas
    assert "no tiene marcas cargadas en Vacíos" in sin_marcas


def test_la_ruta_pasa_las_marcas_a_la_recepcion():
    with patch("app.main.recepcionar_compra", return_value=(None, None)) as recibir:
        respuesta = cliente.post("/deposito/recepcion/1/recepcionar", data={
            "cantidad_cajones_real": "10", "cantidad_total_real": "16",
            "marca": "EJ Granny", "marca_vacio_id": "7",
        }, follow_redirects=False)
    assert respuesta.status_code == 303
    assert recibir.call_args.kwargs["marca"] == "EJ Granny"
    assert recibir.call_args.kwargs["marca_vacio_id"] == 7


def test_el_rechazo_parcial_pasa_las_marcas_a_la_recepcion():
    with patch("app.main.recepcionar_compra", return_value=(None, None)) as recibir:
        respuesta = cliente.post("/deposito/recepcion/1/rechazo-parcial", data={
            "cantidad_cajones_llegados": "10", "cantidad_cajones_rechazada": "2",
            "cantidad_total_real": "16", "marca": "EJ Granny", "marca_vacio_id": "8",
        }, follow_redirects=False)
    assert respuesta.status_code == 303
    assert (recibir.call_args.kwargs["marca"], recibir.call_args.kwargs["marca_vacio_id"]) == ("EJ Granny", 8)


def _post_con_error(**errores):
    with (
        patch("app.main.listar_compras_pendientes_recepcion", return_value=_pendientes()),
        patch("app.main.listar_compras_procesadas_hoy_recepcion", return_value=[]),
        patch("app.main.listar_marcas_vacio_por_proveedor", return_value=MARCAS),
        patch("app.main.recepcionar_compra", **errores) as recibir,
    ):
        respuesta = cliente.post("/deposito/recepcion/1/recepcionar", data={
            "cantidad_cajones_real": "10", "cantidad_total_real": "16",
            "marca_vacio_id": "7" if errores else "cualquiera",
        })
    return respuesta, recibir


def test_una_marca_de_vacio_que_no_es_un_id_rebota_SIN_recibir():
    respuesta, recibir = _post_con_error()
    assert respuesta.status_code == 400
    assert "elegila de la lista" in respuesta.text
    recibir.assert_not_called()


def test_lo_que_rechaza_la_recepcion_se_DICE_como_400_y_no_como_500():
    respuesta, _ = _post_con_error(side_effect=ValueError("Esa marca no es de este proveedor."))
    assert respuesta.status_code == 400
    assert "Esa marca no es de este proveedor." in respuesta.text


def _detalle(**cambios):
    compra = {**COMPRA_DETALLE_DE_PRUEBA, **cambios}
    with (
        patch("app.main.obtener_detalle_compra", return_value=compra),
        patch("app.main.listar_fotos_de_guia", return_value=[]),
        patch("app.main.listar_fotos_de_recepcion", return_value=[]),
        patch("app.main.devoluciones_de_la_compra", return_value=[]),
    ):
        respuesta = cliente.get("/compras/30/detalle")
    assert respuesta.status_code == 200
    # El texto ENTERO y no `split("</style>")[-1]`: el detalle incluye un
    # partial con su propio <style> al final y el corte se come la tarjeta
    # (corolario 50). Los asserts anclan en `etiqueta">`, que solo es marcado.
    return respuesta.text


def test_el_DETALLE_muestra_las_dos_marcas():
    marcado = _detalle(estado="recepcionado", sena=500, marca="EJ Granny", marca_vacio="EJ Roja")
    assert re.search(r"Marca de la mercadería</span>\s*<span class=\"valor\">EJ Granny<", marcado)
    assert re.search(r"Marca de los cajones</span>\s*<span class=\"valor\">EJ Roja<", marcado)


def test_el_DETALLE_dice_SIN_ASIGNAR_y_sin_sena_no_habla_de_cajones():
    marcado = _detalle(estado="recepcionado", sena=None, marca=None, marca_vacio=None)
    assert re.search(r"Marca de la mercadería</span>\s*<span class=\"valor\">Sin asignar<", marcado)
    assert 'etiqueta">Marca de los cajones' not in marcado


def test_el_DETALLE_de_una_PENDIENTE_no_dice_nada_de_marcas():
    marcado = _detalle(estado="pendiente", sena=500, marca=None, marca_vacio=None)
    assert 'etiqueta">Marca de la mercadería' not in marcado
    assert 'etiqueta">Marca de los cajones' not in marcado


@pytest.mark.parametrize("proveedor, marca", [
    ("EJEMPLOPROVEEDORCONUNNOMBRESINESPACIOSMUYLARGO", "EJ Roja"),
    ("Saturno", "EJEMPLOMARCACONUNNOMBRESINESPACIOSMUYLARGO"),
    ("Saturno", "EJ Roja"),
])
def test_la_pantalla_NO_se_arrastra_de_costado_con_nombres_sin_espacios(proveedor, marca):
    """El largo de un nombre no lo controlamos: el proveedor y la marca se
    miden con uno que no se puede partir, y el par cómodo va al lado."""
    pytest.importorskip("playwright", reason="el desborde lo mide el navegador")
    from scripts.medir_layout import medir_sync

    compras = _pendientes()
    compras[0]["proveedor_nombre"] = proveedor
    with (
        patch("app.main.listar_compras_pendientes_recepcion", return_value=compras),
        patch("app.main.listar_compras_procesadas_hoy_recepcion", return_value=[]),
        patch("app.main.listar_marcas_vacio_por_proveedor",
              return_value={501: [{"id": 7, "nombre": marca}]}),
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
    ):
        respuesta = cliente.get("/deposito/recepcion")
    assert respuesta.status_code == 200
    assert respuesta.text.count('name="marca_vacio_id"') == 2   # la pantalla con el selector
    medicion = medir_sync(respuesta.text, ancho=390)
    assert medicion["pares"] > 0
    # De PÁGINA: en una pantalla de tarjetas `desborde` viene en 0 (corolario 53).
    assert medicion["desborde_pagina"] == 0, medicion
