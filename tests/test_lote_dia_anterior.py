"""De qué lote salió un pedido de un DÍA ANTERIOR (dueño, 09/10), contra Postgres.

- Depósito: "Elegir el lote" solo el día del armado. Un renglón armado antes
  no ofrece el botón y el POST rebota.
- Administración → Con fecha anterior: se corrige con la contraseña especial
  y quién lo hace, SOLO si el control de "Con fecha anterior" no frena (un
  armado o una guía R que cambia de lote o queda sin lote), y queda el
  historial: quién, cuándo, antes, ahora y el costo de antes y de ahora.
- Anular una guía R pasa por el MISMO control.

EL GALPÓN, con el RIVAL (el armado del 04/10 de EJEMPLO Rival):

  01/10  compra 11: 10 cajones a $100
  02/10  compra 12: 10 cajones a $80
  03/10  armado 1, EJEMPLO Verduleria, 6   -> FIFO: 6 de la 11
  04/10  armado 2, EJEMPLO Rival, 6        -> FIFO: 4 de la 11 y 2 de la 12
  Hoy es el 06/10, y hay un armado de hoy de EJEMPLO Pera (otro artículo).

Pasar el armado 2 entero a la 12 no le cambia nada a nadie: entra. Pasar el
armado 1 a la 12 libera 6 de la 11, y el armado 2 —que tomaba 2 de la 12—
pasa a salir todo de la 11: el control frena y nombra al Rival.
"""
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402
from tests.test_administracion_reordenada import CLAVES, _cliente  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 6)
CLAVE = "galpon-2026"
BASE = "/administracion/retroactivo/lote-de-pedido"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value
  values (1, 'EJEMPLO Verduleria'), (2, 'EJEMPLO Rival');
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Tomate'), (2, 'EJEMPLO Pera');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01'), (2, 'EJEMPLO Quinta', 'N01P02');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta)
  overriding system value values (1, 1, 1, 18, 'kilo'), (2, 2, 1, 18, 'kilo'), (3, 1, 2, 18, 'kilo');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (11, 1, 1, '2026-10-01', 10, 18, 180, 100, 'recepcionado', '2026-10-01 18:00-03', 10, 18),
         (12, 2, 1, '2026-10-02', 10, 18, 180, 80, 'recepcionado', '2026-10-02 18:00-03', 10, 18),
         (13, 1, 2, '2026-10-02', 5, 18, 90, 50, 'recepcionado', '2026-10-02 18:00-03', 5, 18);
insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (1, 1, '2026-10-03', 'texto'), (2, 2, '2026-10-04', 'texto'), (3, 1, '2026-10-06', 'texto');
insert into pedidos_sucursales (pedido_id, sucursal) values (1, 'CENTRO'), (2, 'CENTRO'), (3, 'CENTRO');
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
                               cantidad_armada, armado_el)
  overriding system value
  values (1, 1, 'CENTRO', 1, 1, 6, 6, '2026-10-03 10:00-03'),
         (2, 2, 'CENTRO', 1, 2, 6, 6, '2026-10-04 10:00-03'),
         (3, 3, 'CENTRO', 2, 3, 1, 1, '2026-10-06 09:00-03');
"""


@pytest.fixture
def galpon(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    monkeypatch.setenv("DATABASE_URL", url)
    for clave, valor in CLAVES.items():
        monkeypatch.setenv(clave, valor)
    import app.db as d
    import app.main as m

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
    d.fijar_clave_especial(CLAVE)
    with patch("app.main._hoy_argentina", return_value=HOY):
        yield d, m, sql


def _corregir(cliente, renglon_id, reparto, *, clave=CLAVE, quien="Marta", volver=None):
    datos = {"lote": [f"guia:{c}" for c in reparto], "bultos": [str(b) for b in reparto.values()],
             "quien": quien, "clave_especial": clave}
    url = f"{BASE}/{renglon_id}" + (f"?volver={volver}" if volver else "")
    return cliente.post(url, data=datos, follow_redirects=False)


def _elegidos(sql):
    return sql("SELECT renglon_id, lote_tipo, lote_origen_id, bultos::float FROM pedidos_renglones_lotes_elegidos "
               "ORDER BY renglon_id, lote_origen_id")


def _texto(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html.split("<body", 1)[-1]).split())


def test_la_correccion_que_no_le_cambia_nada_a_NADIE_entra_con_su_HISTORIAL(galpon):
    d, m, sql = galpon
    adm = _cliente(m, "administracion")
    respuesta = _corregir(adm, 2, {11: 0, 12: 6})

    assert respuesta.status_code == 303, re.findall(r"data-error>([^<]*)", respuesta.text)
    assert respuesta.headers["location"].startswith(f"{BASE}/2?aviso=")
    assert _elegidos(sql) == [(2, "guia", 12, 6.0)]
    (quien, antes, ahora, costo_antes, costo_ahora), = sql(
        "SELECT quien, antes, ahora, costo_antes::float, costo_ahora::float FROM pedidos_renglones_lotes_correcciones")
    assert quien == "Marta"
    assert [(p["lote"], p["bultos"]) for p in antes] == [("Guía de EJEMPLO Puesto del 01/10", 4),
                                                         ("Guía de EJEMPLO Quinta del 02/10", 2)]
    assert [(p["lote"], p["bultos"]) for p in ahora] == [("Guía de EJEMPLO Quinta del 02/10", 6)]
    assert (costo_antes, costo_ahora) == (560.0, 480.0)
    # El rival (el armado 1) sigue saliendo de la 11.
    pantalla = _texto(adm.get(f"{BASE}/2").text)
    assert "6 de Guía de EJEMPLO Quinta del 02/10" in pantalla
    assert "Marta ·" in pantalla and "Costo: $560 → $480 ($-80)" in pantalla
    # La fecha del armado NO se toca.
    assert sql("SELECT armado_el = '2026-10-04 10:00-03' FROM pedidos_renglones WHERE id = 2") == [(True,)]


# EL EJEMPLO DEL DUEÑO, con guías R (dueño, 09/10): Tomate Perita de una ficha
# con caja. R683 del 04/10 a $20.689 la caja y R711 del 05/10 a $16.057.
PERITA = """
insert into articulos (id, nombre) overriding system value values (3, 'EJEMPLO Tomate Perita');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja Chica');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (4, 1, 3, 18, 'kilo', 1);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (21, 1, 3, '2026-10-02', 80, 18, 1440, 10000, 'recepcionado', '2026-10-02 18:00-03', 80, 18);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera, bultos_segunda,
                        bultos_merma, costo_por_bulto_primera, cliente_id, ficha_id, envase_id,
                        lleva_caja_nuestra, creado_en)
  overriding system value
  values (683, 3, '2026-10-04', 30, 30, 0, 0, 20689, 1, 4, 1, true, '2026-10-04 18:00-03'),
         (711, 3, '2026-10-05', 30, 30, 0, 0, 16057, 1, 4, 1, true, '2026-10-05 08:00-03');
insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos)
  values (683, 'compra', 21, 30), (711, 'compra', 21, 30);
insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value
  values (10, 1, '2026-10-05', 'texto'), (12, 1, '2026-10-07', 'texto');
insert into pedidos_sucursales (pedido_id, sucursal) values (10, 'VL'), (12, 'VL');
-- El 05/10 a las 17:28, 30 cajas: el sistema las pone en la R683 (la más vieja).
-- El 06/10 a las 10:00, el armado siguiente: el sistema lo pone en la R711.
insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
                               cantidad_armada, armado_el)
  overriding system value
  values (31, 10, 'VL', 3, 4, 30, 30, '2026-10-05 17:28-03'),
         (32, 3, 'CENTRO', 3, 4, %(siguiente)s, %(siguiente)s, '2026-10-06 10:00-03');
"""


def _a_la_guia(cliente, renglon_id, reparto):
    return cliente.post(f"{BASE}/{renglon_id}", data={
        "lote": [f"reproceso:{g}" for g in reparto], "bultos": [str(b) for b in reparto.values()],
        "quien": "Marta", "clave_especial": CLAVE}, follow_redirects=False)


def test_R683_a_R711_ENTRA_aunque_el_armado_siguiente_cambie_de_guia(galpon):
    """Lo liberado de la R683 lo toma el armado del 06/10, que el sistema había
    puesto en la R711. A la R711 le sobra: nadie queda sin mercadería y nadie
    eligió a mano. Con el control estricto esto frenaba (dueño, 09/10)."""
    d, m, sql = galpon
    sql(PERITA, {"siguiente": 10})
    respuesta = _a_la_guia(_cliente(m, "administracion"), 31, {683: 0, 711: 30})

    assert respuesta.status_code == 303, re.findall(r"data-error>([^<]*)", respuesta.text)
    assert sql("SELECT costo_antes::float, costo_ahora::float FROM pedidos_renglones_lotes_correcciones") \
        == [(30 * 20689.0, 30 * 16057.0)]                     # 138.960 menos
    from core.costo_real import atribuir_costos_fifo
    entradas, salidas = d.entradas_y_salidas_stock_articulo(3)
    siguiente = next(s for s in atribuir_costos_fifo(entradas, salidas) if s.get("renglon_id") == 32)
    assert [(c["tipo_lote"], c["origen_id"], c["bultos"]) for c in siguiente["consumos_lotes"]] \
        == [("reproceso", 683, 10)]                           # lo liberado lo tomó el siguiente


def test_la_que_deja_a_un_pedido_SIN_MERCADERIA_no_entra_y_dice_CUAL(galpon):
    """El 06/10 (pedido del 07/10) alguien eligió a mano la R711 para 30 cajas.
    Si el del 05/10 pasa a la R711, ese armado se queda sin las suyas y la R683
    liberada ya la tomó el de las 10:00: queda sin mercadería. El rival: el
    de las 10:00, que estaba sin lote y pasa a tener, no frena."""
    d, m, sql = galpon
    sql(PERITA, {"siguiente": 30})
    sql("""insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
               cantidad_armada, armado_el) overriding system value
           values (33, 12, 'VL', 3, 4, 30, 30, '2026-10-06 12:00-03')""")
    sql("insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos) "
        "values (33, 'reproceso', 711, 30)")
    respuesta = _a_la_guia(_cliente(m, "administracion"), 31, {683: 0, 711: 30})

    assert respuesta.status_code == 400
    texto = _texto(respuesta.text)
    assert "El armado del pedido de EJEMPLO Verduleria del 07/10 se queda sin mercadería." in texto
    assert "del 06/10" not in re.findall(r"data-error>([^<]*)", respuesta.text)[0]
    assert sql("SELECT renglon_id FROM pedidos_renglones_lotes_elegidos") == [(33,)]
    assert sql("SELECT count(*) FROM pedidos_renglones_lotes_correcciones") == [(0,)]


def test_la_que_le_SACA_a_otro_la_guia_ELEGIDA_A_MANO_no_entra_aunque_alcance(galpon):
    """El del 06/10 a las 12:00 eligió a mano 20 de la R711. Si el del 05/10
    pasa a la R711, a él le toca la R683 liberada: no queda sin mercadería,
    pero pierde lo que alguien eligió, y eso también frena (dueño, 09/10)."""
    d, m, sql = galpon
    sql(PERITA, {"siguiente": 10})
    sql("""insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
               cantidad_armada, armado_el) overriding system value
           values (33, 12, 'VL', 3, 4, 20, 20, '2026-10-06 12:00-03')""")
    sql("insert into pedidos_renglones_lotes_elegidos (renglon_id, lote_tipo, lote_origen_id, bultos) "
        "values (33, 'reproceso', 711, 20)")
    respuesta = _a_la_guia(_cliente(m, "administracion"), 31, {683: 0, 711: 30})

    assert respuesta.status_code == 400
    assert re.findall(r"data-error>([^<]*)", respuesta.text) == [
        "El armado del pedido de EJEMPLO Verduleria del 07/10 pierde la guía que eligieron a mano. "
        "Hasta que eso se corrija, no se puede cambiar de dónde salió."]
    assert sql("SELECT count(*) FROM pedidos_renglones_lotes_correcciones") == [(0,)]


def test_sin_CONTRASENA_o_sin_QUIEN_no_escribe_nada(galpon):
    d, m, sql = galpon
    adm = _cliente(m, "administracion")
    mala = _corregir(adm, 2, {12: 6}, clave="admin-secreta")
    assert mala.status_code == 400 and "La contraseña especial no es correcta." in mala.text
    assert "Poné quién lo carga." in _corregir(adm, 2, {12: 6}, quien="  ").text
    # Lo que escribió vuelve escrito (menos la contraseña).
    assert 'value="6"' in mala.text and 'value="Marta"' in mala.text
    assert _elegidos(sql) == [] and sql("SELECT count(*) FROM pedidos_renglones_lotes_correcciones") == [(0,)]
    sin_cookie = _cliente(m).post(f"{BASE}/2", data={"lote": "guia:12", "bultos": "6", "quien": "X",
                                                      "clave_especial": CLAVE}, follow_redirects=False)
    assert sin_cookie.status_code == 401 and _elegidos(sql) == []


def test_lo_IMPOSIBLE_rebota_con_el_motivo(galpon):
    d, m, sql = galpon
    adm = _cliente(m, "administracion")
    assert "cuando se armó quedaban 10, no 11" in _texto(_corregir(adm, 2, {12: 11}).text)
    assert "no hay nada que corregir" in _texto(_corregir(adm, 2, {11: 4, 12: 2}).text)
    assert "Repartiste más bultos de los 6 que se armaron." in _texto(_corregir(adm, 2, {11: 4, 12: 3}).text)
    # El de HOY es de Depósito.
    assert "Ese renglón se armó hoy" in _texto(_corregir(adm, 3, {13: 1}).text)
    assert _elegidos(sql) == []


def test_DEPOSITO_corrige_solo_el_DIA_del_armado(galpon):
    d, m, sql = galpon
    deposito = _cliente(m)
    del_dia_anterior = deposito.post("/deposito/pedido/2/renglones/2/lotes", data={
        "cliente_id": "2", "fecha": "2026-10-04", "sucursal": "CENTRO",
        "reparto": '[{"tipo_lote": "guia", "origen_id": 12, "bultos": 6}]'}, follow_redirects=False)
    assert del_dia_anterior.status_code == 400
    assert "Administración → Con fecha anterior" in del_dia_anterior.json()["detail"]
    # El rival: el de hoy sí entra.
    de_hoy = deposito.post("/deposito/pedido/3/renglones/3/lotes", data={
        "cliente_id": "1", "fecha": "2026-10-06", "sucursal": "CENTRO",
        "reparto": '[{"tipo_lote": "guia", "origen_id": 13, "bultos": 1}]'}, follow_redirects=False)
    assert de_hoy.status_code == 303
    assert _elegidos(sql) == [(3, "guia", 13, 1.0)]


def test_DEPOSITO_no_ofrece_Elegir_el_lote_en_un_armado_de_OTRO_DIA(galpon):
    d, m, sql = galpon
    deposito = _cliente(m)
    sql("UPDATE pedidos_renglones SET armado_el = '2026-10-05 20:00-03' WHERE id = 3")
    viejo = deposito.get("/deposito/pedido/armar?cliente_id=1&fecha=2026-10-06&sucursal=CENTRO").text
    assert viejo.count('id="ver-lotes-3"') == 0 and 'action="/deposito/pedido/3/renglones/3/lotes"' not in viejo
    assert viejo.count('<p class="lote-otro-dia">') == 1
    sql("UPDATE pedidos_renglones SET armado_el = '2026-10-06 09:00-03' WHERE id = 3")
    hoy = deposito.get("/deposito/pedido/armar?cliente_id=1&fecha=2026-10-06&sucursal=CENTRO").text
    assert hoy.count('id="ver-lotes-3"') == 1 and '<p class="lote-otro-dia">' not in hoy


def test_la_LISTA_lleva_al_renglon_y_el_renglon_VUELVE_con_sus_filtros(galpon):
    d, m, sql = galpon
    adm = _cliente(m, "administracion")
    lista = adm.get(f"{BASE}?fecha=2026-10-04&cliente_id=2")
    assert lista.status_code == 200
    links = re.findall(r'<a class="renglon" href="([^"]*)"', lista.text)
    assert len(links) == 1 and links[0].startswith(f"{BASE}/2?volver=")
    detalle = adm.get(links[0].replace("&amp;", "&"))
    assert re.search(r'<a class="barra-boton" href="/administracion/retroactivo/lote-de-pedido\?fecha=2026-10-04'
                     r'&amp;cliente_id=2"', detalle.text)
    # Después de guardar sigue sabiendo a qué lista volver.
    guardado = _corregir(adm, 2, {12: 6}, volver="/administracion/retroactivo/lote-de-pedido%3Ffecha%3D2026-10-04")
    assert "volver=" in guardado.headers["location"]
    marcada = adm.get(f"{BASE}?fecha=2026-10-04").text
    assert marcada.count('<span class="marca">Corregido</span>') == 1
    hub = adm.get("/administracion/retroactivo").text
    assert hub.count(f'href="{BASE}"') == 1


def test_ANULAR_una_guia_R_cuyas_cajas_las_cubre_lo_que_LIBERA_se_anula(galpon):
    """El 05/10 la guía R7 toma 2 cajones (de la 12) y da 2 de primera, y el
    armado 4 de 9 sale de la 12 y de las 2 de la R7. Sin la guía, los 2
    cajones que libera le alcanzan al armado: le cambia la guía, pero no queda
    sin mercadería. Con el control flojo (dueño, 10/10) se anula; con el
    estricto, esto frenaba."""
    d, m, sql = galpon
    sql("""insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
               bultos_segunda, bultos_merma, costo_por_bulto_primera, creado_en) overriding system value
           values (7, 1, '2026-10-05', 2, 2, 0, 0, 80, '2026-10-05 08:00-03')""")
    sql("insert into reprocesos_consumos (reproceso_id, origen, compra_id, bultos) values (7, 'compra', 12, 2)")
    sql("""insert into pedidos_renglones (id, pedido_id, sucursal, articulo_id, ficha_id, cantidad,
               cantidad_armada, armado_el) overriding system value
           values (4, 2, 'CENTRO', 1, 2, 9, 9, '2026-10-05 12:00-03')""")
    respuesta = _cliente(m, "administracion").post("/administracion/stock/guias-r/7/anular",
                                                   follow_redirects=False)
    assert respuesta.status_code == 303 and "error=" not in respuesta.headers["location"]
    assert sql("SELECT anulado_el IS NOT NULL FROM reprocesos WHERE id = 7") == [(True,)]


def test_ANULAR_una_guia_R_que_deja_un_pedido_SIN_MERCADERIA_no_anula_y_dice_cual(galpon):
    """Con la Perita: el 05/10 salen 30 cajas de la R683 y el 06/10 10 de la
    R711. Sin la R683, las 30 del 05/10 pasan a la R711 y las 10 del 06/10
    quedan sin cajas. El rival: anular la R711 sin el armado del 06/10 deja
    a todos cubiertos y se anula."""
    d, m, sql = galpon
    sql(PERITA, {"siguiente": 10})
    adm = _cliente(m, "administracion")
    respuesta = adm.post("/administracion/stock/guias-r/683/anular", follow_redirects=False)
    from urllib.parse import parse_qs, urlparse
    error = parse_qs(urlparse(respuesta.headers["location"]).query)["error"][0]
    assert error == ("La guía R683 no se anuló: El armado del pedido de EJEMPLO Verduleria del 06/10 "
                     "se queda sin mercadería. Hasta que eso se corrija, no se puede anular.")
    assert sql("SELECT anulado_el IS NULL FROM reprocesos WHERE id = 683") == [(True,)]
    sql("UPDATE pedidos_renglones SET anulado_el = now(), armado_el = NULL, cantidad_armada = NULL WHERE id = 32")
    assert "error=" not in adm.post("/administracion/stock/guias-r/711/anular",
                                    follow_redirects=False).headers["location"]
    assert sql("SELECT anulado_el IS NOT NULL FROM reprocesos WHERE id = 711") == [(True,)]


def test_a_313px_las_dos_pantallas_no_desbordan(galpon):
    from tests.test_remitos import _que_se_sale
    d, m, sql = galpon
    adm = _cliente(m, "administracion")
    _corregir(adm, 2, {12: 6})
    paginas = {"lista": adm.get(f"{BASE}?fecha=2026-10-04").text, "renglon": adm.get(f"{BASE}/2").text}
    assert paginas["lista"].count('<a class="renglon"') == 1                      # identidad
    assert paginas["renglon"].count('data-cambio') == 1
    for nombre, html in paginas.items():
        medicion = _que_se_sale(html, 313)
        assert medicion["pagina"] == 0 and medicion["salidos"] == [], (nombre, medicion)


def _leer(nombre):
    return open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


def test_la_MIGRACION_crea_la_tabla_con_candado_y_no_corre_dos_veces(galpon):
    import psycopg2
    d, m, sql = galpon
    sql("DROP TABLE pedidos_renglones_lotes_correcciones")
    sql(_leer("lote_dia_anterior_1_historial.sql"))
    with pytest.raises(psycopg2.errors.RaiseException):
        sql(_leer("lote_dia_anterior_1_historial.sql"))
    (fila,) = sql(_leer("lote_dia_anterior_1_verificacion.sql"))
    assert fila[:6] == ("lote_dia_anterior_1_historial", 1, 1, 1, 1, 0)
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("INSERT INTO pedidos_renglones_lotes_correcciones (renglon_id, quien, antes, ahora) "
            "VALUES (1, '  ', '[]', '[]')")
    for nombre in ("lote_dia_anterior_1_historial.sql", "lote_dia_anterior_1_verificacion.sql"):
        texto = _leer(nombre)
        assert len(texto) <= 2500, nombre
