"""Qué comprar hoy, contra Postgres: el tilde que nadie puso y el "no se puede saber" (02/10).

Los dos, con los casos de Frutamax del 02/10 y nombres de EJEMPLO:

1. EL TILDE. El listado del 23/09 siguió abierto nueve días con la carga 28
   tildada, y cada vez que se entraba aparecía tildada. Regla del dueño:
   "al abrir no puede haber NADA tildado, ni por lo guardado ayer. Tilda solo
   Lionel". Un listado abierto OTRO DÍA no cuenta al entrar, y el próximo
   guardado lo cierra.

2. EL STOCK. "Hay cajones sueltos sin contenido declarado" con todas las
   compras completas. Lo que no cerraba era el REPARTO, no un dato:
     - Granny: el 17/09 se armaron 25 con 14 cargados (la compra que los
       cubría entró el 18/09), y las compras que quedan suman más que lo que
       hay. Acá: 15 armados con 10 cargados, y la compra siguiente queda con
       10 contra 5 reales.
     - Ombligo: queda una compra y un lote de guía R, que no es de compra.
   Desde el 02/10 los bultos son los de la resta y los kilos se ESTIMAN con
   la compra más cercana; nunca "no se puede saber" con bultos.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tests.test_cargas_compra import base_real, galpon  # noqa: F401  (fixtures)
from tests.test_salgo_a_comprar import _proveedor

# FIJO Y LEJOS DE HOY (corolario 95): el cierre del cálculo del stock.
CIERRE = date(2026, 9, 20)


def _compra(sql, articulo, proveedor, dia, cajones, contenido):
    procesada = datetime(dia.year, dia.month, dia.day, 15, 0, tzinfo=timezone.utc)
    (cid,), = sql(
        """INSERT INTO compras (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones,
               cantidad_cajones_real, contenido_por_cajon, contenido_por_cajon_real,
               cantidad_kilos, cantidad_kilos_real, estado, procesada_el)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'recepcionado', %s) RETURNING id""",
        (dia, articulo, proveedor, cajones, cajones, contenido, contenido,
         cajones * contenido, cajones * contenido, procesada))
    return cid


def _armado(sql, cliente, articulo, dia, bultos):
    """Un renglón armado en CAJÓN (ficha sin envase), como el de Granny."""
    (ficha,), = sql("INSERT INTO fichas_logistica (articulo_id, cliente_id, unidad_venta, contenido_caja)"
                    " VALUES (%s, %s, 'kilo', 18) RETURNING id", (articulo, cliente))
    (pedido,), = sql("INSERT INTO pedidos (cliente_id, fecha_operacion, origen)"
                     " VALUES (%s, %s, 'mail') RETURNING id", (cliente, dia))
    armado = datetime(dia.year, dia.month, dia.day, 21, 0, tzinfo=timezone.utc)
    sql("""INSERT INTO pedidos_renglones (pedido_id, sucursal, articulo_id, ficha_id, cantidad,
               cantidad_armada, armado_el)
           VALUES (%s, 'EJ', %s, %s, %s, %s, %s)""",
        (pedido, articulo, ficha, bultos, bultos, armado))


def test_GRANNY_el_reparto_no_cierra_y_los_kilos_se_ESTIMAN_con_los_bultos_REALES(galpon):
    """10 cargados el 10/09, 15 armados el 11/09 (5 salen sin lote), 10 más
    el 12/09. Hay 5 en el piso; el reparto deja la compra del 12 con 10.

    El RIVAL es la cuenta hasta el 02/10: 10 en lotes contra 5 de la resta
    daba None y "hay cajones sueltos sin contenido declarado". Y el otro
    rival, más tentador: pasar a kilos lo que dicen los lotes (10 × 18 = 180)
    en vez de los 5 que hay."""
    d, sql, cliente, granny, _l = galpon
    from app.main import _foto_del_stock, _piso_de_la_foto
    proveedor = _proveedor(sql)
    _compra(sql, granny, proveedor, date(2026, 9, 10), 10, 18.5)
    _armado(sql, cliente, granny, date(2026, 9, 11), 15)
    _compra(sql, granny, proveedor, date(2026, 9, 12), 10, 18.0)

    foto = _foto_del_stock([granny], CIERRE)
    piso = _piso_de_la_foto(foto, [granny])[granny]
    assert piso["sueltos"] == 5.0
    assert piso["magnitud"] == 90.0          # 5 bultos × 18 de la compra más nueva
    assert piso["estimado"] is True
    assert piso.get("por_que") is None


def test_OMBLIGO_un_lote_de_GUIA_R_se_estima_con_la_compra_mas_cercana(galpon):
    """10 de 16,3 el 10/09; una guía R sin ficha el 11/09 toma 4 y saca 3. Hay
    9: 6 de la compra y 3 de la guía R, que no es un lote de compra.

    El RIVAL (hasta el 02/10): None, "sin contenido declarado"."""
    d, sql, _cliente, ombligo, _l = galpon
    from app.main import _foto_del_stock, _piso_de_la_foto
    proveedor = _proveedor(sql)
    _compra(sql, ombligo, proveedor, date(2026, 9, 10), 10, 16.3)
    sql("""INSERT INTO reprocesos (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
               bultos_segunda, bultos_merma) VALUES (%s, %s, 4, 3, 0, 0)""",
        (ombligo, date(2026, 9, 11)))

    piso = _piso_de_la_foto(_foto_del_stock([ombligo], CIERRE), [ombligo])[ombligo]
    assert piso["sueltos"] == 9.0
    assert piso["magnitud"] == pytest.approx(9 * 16.3)
    assert piso["estimado"] is True


def test_cuando_CIERRA_los_kilos_son_EXACTOS_y_no_dicen_estimado(galpon):
    """El caso de siempre no cambia: dos compras, nada sin lote."""
    d, sql, _cliente, art, _l = galpon
    from app.main import _foto_del_stock, _piso_de_la_foto
    proveedor = _proveedor(sql)
    _compra(sql, art, proveedor, date(2026, 9, 10), 6, 16.3)
    _compra(sql, art, proveedor, date(2026, 9, 12), 30, 15.4)
    piso = _piso_de_la_foto(_foto_del_stock([art], CIERRE), [art])[art]
    assert piso["sueltos"] == 36.0
    assert piso["magnitud"] == pytest.approx(6 * 16.3 + 30 * 15.4)   # 559,8: Ombligo al 02/10
    assert piso["estimado"] is False


# --- EL TILDE -------------------------------------------------------------


@pytest.fixture
def pantalla(galpon, monkeypatch):
    import app.main as m
    monkeypatch.setenv("CLAVE_COMPRAS", "compras-secreta")
    cliente = TestClient(m.app)
    cliente.cookies.set(m.PUERTA_COMPRAS.cookie, m.PUERTA_COMPRAS.firma("compras-secreta"))
    return cliente


def _checkboxes(html):
    import re
    marcado = html.split("</style>")[-1]
    return re.findall(r'<input type="checkbox" name="carga" value="(\d+)"\s*(checked)?>', marcado)


def test_al_ENTRAR_no_hay_NADA_tildado_aunque_un_listado_de_OTRO_DIA_lo_tenga(galpon, pantalla):
    """Sembrado como Frutamax el 02/10: un listado abierto hace días, ya
    salido, con una carga tildada que se sigue ofreciendo hoy.

    El RIVAL es la regla del 23/09: con ésa la carga salía tildada y el stock
    era la foto de hace días. Después, tildar y guardar SÍ la deja tildada
    (la tildó el que compra), y el listado viejo queda cerrado."""
    d, sql, cliente, tomate, _l = galpon
    from app.main import ARGENTINA
    hoy = datetime.now(ARGENTINA).date()
    sql("UPDATE listados_compra SET estado = 'cerrado' WHERE estado = 'borrador'")
    d.guardar_carga_de_compra(cliente, hoy, "manual", hoy, 0)
    (carga,), = sql("SELECT id FROM cargas_compra WHERE cliente_id = %s", (cliente,))
    (viejo,), = sql("""INSERT INTO listados_compra (fecha, estado, generado_el)
                       VALUES (%s, 'borrador', now() - interval '3 days') RETURNING id""",
                    (hoy - timedelta(days=3),))
    sql("INSERT INTO listados_compra_cargas VALUES (%s, %s)", (viejo, carga))

    respuesta = pantalla.get("/compras/que-comprar")
    assert respuesta.status_code == 200
    cajas = _checkboxes(respuesta.text)
    assert (str(carga), "") in cajas, "la carga de hoy se ofrece"          # el denominador
    assert all(tilde == "" for _id, tilde in cajas), f"{sum(1 for c in cajas if c[1])} tildadas"
    assert "Stock congelado" not in respuesta.text
    assert 'autocomplete="off"' in respuesta.text

    # Lo tilda el que compra, y ahí sí queda.
    respuesta = pantalla.post("/compras/que-comprar", data={"accion": "guardar", "carga": str(carga)},
                              follow_redirects=True)
    assert (str(carga), "checked") in _checkboxes(respuesta.text)
    assert sql("SELECT estado FROM listados_compra WHERE id = %s", (viejo,)) == [("cerrado",)]
