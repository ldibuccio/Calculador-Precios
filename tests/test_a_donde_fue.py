# -*- coding: utf-8 -*-
"""El cuadro "A dónde fue" del detalle de la compra (dueño, 05/10), contra Postgres.

POR QUÉ CONTRA LA BASE: lo que sale de una compra no es una consulta, es el
rejuego del FIFO (`atribuir_costos_fifo`). Con la base mockeada el reparto lo
decidiría el fixture (corolario 91).

EL CASO, con el RIVAL plantado (la compra 12, que no tiene que contar en la 11):

  05/09  compra 11: 10 cajones          06/09  compra 12: 10 cajones (rival)
  07/09  se arman 7 en cajón para la verdulería         -> 7 de la 11
  08/09  guía R toma 6: 3 de la 11 y 3 de la 12         -> la mitad es de la 11
  09/09  se arman 6 cajas para Día, Vicente López      -> de la guía: 3 son de la 11
  10/09  se arman 4 en cajón para la verdulería         -> de la 12: no es de la 11

La 13 no se recibió y la 15 (otro artículo) se recibió y no salió nada.

Mismo interruptor que el humo: sin Postgres se saltea, y con
HUMO_OBLIGATORIO=1 falla.
"""
import html
import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value
  values (1, 'Día EJEMPLO'), (2, 'EJEMPLO Verduleria');
insert into clientes_sucursales (cliente_id, codigo, nombre) values (1, 'VL', 'Vicente López');
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Limon'), (2, 'EJEMPLO Pera');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 18, 'kilo', 1), (2, 2, 1, 20, 'kilo', null);

insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (11, 1, 1, '2026-09-05', 10, 20, 200, 100, 'recepcionado', '2026-09-05 18:00-03', 10, 20),
         (12, 1, 1, '2026-09-06', 10, 20, 200, 100, 'recepcionado', '2026-09-06 18:00-03', 10, 20),
         (13, 1, 1, '2026-09-07', 10, 20, 200, 100, 'pendiente', null, null, null),
         (15, 1, 2, '2026-09-05', 10, 20, 200, 100, 'recepcionado', '2026-09-05 18:00-03', 10, 20);

insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra)
  overriding system value
  values (1, 1, '2026-09-08', 6, 6, 0, 0, 150, 1, 1, 1, true);
insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos)
  values (1, 'compra', 11, 3), (1, 'compra', 12, 3);

insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 2, '2026-09-07', 'texto'), (2, 1, '2026-09-09', 'texto'),
         (3, 2, '2026-09-10', 'texto');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
                               cantidad_armada, armado_el, kilos_enviados)
  overriding system value
  values (1, 1, 'CENTRO', 1, 2, 7, 7, '2026-09-07 13:00-03', 140),
         (2, 2, 'VL', 1, 1, 6, 6, '2026-09-09 10:00-03', 108),
         (3, 3, 'CENTRO', 1, 2, 4, 4, '2026-09-10 10:00-03', 80);
insert into pedidos_sucursales (id, pedido_id, sucursal, orden_compra) overriding system value
  values (1, 1, 'CENTRO', null), (2, 2, 'VL', 'OC-77'), (3, 3, 'CENTRO', null);
insert into remitos (id, pedido_sucursal_id, cliente_id, numero, emitido_el, recibido_el)
  overriding system value
  values (1, 1, 2, 'R-0001', '2026-09-07 15:00-03', '2026-09-08 09:00-03'),
         (2, 2, 1, 'R-0002', '2026-09-09 15:00-03', null);
insert into remitos_renglones (remito_id, pedido_renglon_id, bultos_enviados, kilos_enviados,
                               bultos_recibidos, kilos_recibidos)
  values (1, 1, 7, 140, 6, 120), (2, 2, 6, 108, null, null);
"""


@pytest.fixture(scope="module")
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay un Postgres usable.")
        pytest.skip("sin Postgres local: se corre con el humo antes de desplegar")
    url = preparar_base()
    if url is None:
        pytest.fail("no se pudo preparar la base con db/esquema_completo.sql")
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    return url


def _a_donde(base, monkeypatch, compra_id):
    import app.db as db
    monkeypatch.setenv("DATABASE_URL", base)
    return db.a_donde_fue_la_compra(compra_id)


def _resumen(resultado):
    return [(r["id"], r["bultos"], r["de_un_renglon_de"], r["kilos_enviados"]) for r in resultado["renglones"]]


def test_la_compra_sale_DIRECTO_y_POR_LA_GUIA_R_en_su_proporcion(base, monkeypatch):
    """7 directo a la verdulería; de las 6 cajas de Día, la mitad es de la 11."""
    resultado = _a_donde(base, monkeypatch, 11)

    assert _resumen(resultado) == [(1, 7.0, None, 140.0), (2, 3.0, 6.0, 54.0)]
    assert resultado["bultos"] == 10.0


def test_el_RIVAL_no_cuenta_en_la_11_y_tiene_lo_suyo(base, monkeypatch):
    """La 12 pone la otra mitad de la guía y el armado del 10/09 entero."""
    resultado = _a_donde(base, monkeypatch, 12)

    assert _resumen(resultado) == [(2, 3.0, 6.0, 54.0), (3, 4.0, None, 80.0)]


def test_cada_renglon_trae_ORDEN_REMITO_SUCURSAL_y_lo_RECIBIDO(base, monkeypatch):
    por_id = {r["id"]: r for r in _a_donde(base, monkeypatch, 11)["renglones"]}

    verduleria, dia = por_id[1], por_id[2]
    assert (verduleria["remito"], verduleria["remito_volvio"],
            verduleria["bultos_recibidos"], verduleria["kilos_recibidos"]) == ("R-0001", True, 6.0, 120.0)
    assert (dia["sucursal_nombre"], dia["orden_compra"], dia["remito"], dia["remito_volvio"],
            dia["bultos_recibidos"]) == ("Vicente López", "OC-77", "R-0002", False, None)


def test_sin_recepcion_y_sin_salidas_lo_DICE(base, monkeypatch):
    assert _a_donde(base, monkeypatch, 13) == {"recepcionada": False, "renglones": [], "bultos": 0.0}
    assert _a_donde(base, monkeypatch, 15) == {"recepcionada": True, "renglones": [], "bultos": 0.0}


def _pagina(base, monkeypatch, compra_id):
    from fastapi.testclient import TestClient

    from app.main import PUERTA_COMPRAS, app
    monkeypatch.setenv("DATABASE_URL", base)
    monkeypatch.setenv(PUERTA_COMPRAS.env_var, "compras-secreta")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
    respuesta = cliente.get(f"/compras/{compra_id}/detalle")
    assert respuesta.status_code == 200
    # La tarjeta va desde su apertura hasta el botón Editar, que la sigue.
    pagina = respuesta.text
    assert pagina.count('<div class="tarjeta" id="a-donde-fue">') == 1
    tarjeta = pagina.split('<div class="tarjeta" id="a-donde-fue">')[1].split('<a class="boton-editar-detalle"')[0]
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", tarjeta)).split())


def test_la_PANTALLA_dice_a_donde_fue(base, monkeypatch):
    texto = _pagina(base, monkeypatch, 11)

    assert "Salieron al cliente 10 bultos" in texto
    assert "Día EJEMPLO · Vicente López" in texto
    assert "Orden de compra OC-77 · remito R-0002" in texto
    assert "Enviados: 3 bultos · 54 kg (de un renglón de 6)" in texto
    assert "Recibidos por el cliente: 6 bultos · 120 kg" in texto
    assert texto.count("El remito todavía no volvió") == 1
    # La jerga del FIFO no aparece en la pantalla.
    for jerga in ("lote", "FIFO", "reproceso", "consumo"):
        assert jerga not in texto


def test_la_PANTALLA_dice_que_todavia_no_salio(base, monkeypatch):
    assert "Todavía no salió nada de esta compra a un cliente." in _pagina(base, monkeypatch, 15)
    assert "Todavía no se recibió: no salió nada." in _pagina(base, monkeypatch, 13)


def test_a_313px_el_cuadro_no_DESBORDA_ni_se_PISA(base, monkeypatch):
    pytest.importorskip("playwright")
    from fastapi.testclient import TestClient

    from app.main import PUERTA_COMPRAS, app
    from scripts.medir_layout import imprimir, medir_sync
    monkeypatch.setenv("DATABASE_URL", base)
    monkeypatch.setenv(PUERTA_COMPRAS.env_var, "compras-secreta")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
    respuesta = cliente.get("/compras/11/detalle")
    # La identidad: el status y los renglones del cuadro (2, los de la siembra).
    assert respuesta.status_code == 200
    medicion = medir_sync(respuesta.text, ancho=313, selector_filas=".a-donde li",
                          captura=os.environ.get("CAPTURA_A_DONDE_FUE"))
    imprimir("A dónde fue a 313px", medicion)

    assert medicion["filas"] == 2
    assert medicion.get("desborde_pagina", medicion.get("desborde")) == 0
    assert medicion.get("solapes", []) == []
