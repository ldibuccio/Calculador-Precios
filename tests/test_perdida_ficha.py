# -*- coding: utf-8 -*-
"""% DE PÉRDIDA POR FICHA (dueño, 13/10), contra Postgres.

El sugerido sale del costo de COMPRA, así que la pérdida no estaba en el
precio. Ahora cada ficha tiene su % de pérdida (0 por defecto), que rige desde
el día en que se carga, y el sugerido se calcula sobre el costo del kilo útil:

    costo útil = costo del kilo comprado / (1 − pérdida)

solo sobre la mercadería y antes de la utilidad; envase y tasas igual.
Ejemplo del dueño: $5.000 comprado, 18% → $6.098 útil; con 20% → $7.317.

EL GALPÓN, con nombres inventados:

  EJEMPLO Uno (cliente 1): utilidad 20%, sin tasas.
    ficha 1 Morrón: kilo, sin envase. 18% de pérdida desde el 10/10.
    ficha 2 Zapallo: kilo, sin envase, sin pérdida (rival).
  EJEMPLO Dos (cliente 2): utilidad 20%, IVA +10% y flete −10%.
    ficha 3 Morrón: kilo, caja de $120 cada 10 kg, 18% desde el 10/10.
  Compras del 08/10: Morrón 10 cajones de 10 kg a $50.000 ($5.000 el kilo),
  Zapallo 10 cajones de 20 kg a $40.000 ($2.000 el kilo).
"""
import os
import re
import sys
from datetime import date, datetime, time
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.motor_costeo import costo_del_kilo_util, precio_sugerido_multi_concepto  # noqa: E402
from core.zona import ARGENTINA  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Uno'), (2, 'EJEMPLO Dos');
insert into articulos (id, nombre, grupo) overriding system value
  values (1, 'EJEMPLO Morron', 'hortaliza'), (2, 'EJEMPLO Zapallo', 'hortaliza');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'EJEMPLO Caja');
insert into envases_costo_historial (envase_id, costo, vigente_desde) values (1, 120, '2026-01-01');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 10, 'kilo', null), (2, 1, 2, 10, 'kilo', null),
                                 (3, 2, 1, 10, 'kilo', 1);
insert into clientes_parametros_historial (cliente_id, nombre_parametro, valor, vigente_desde, tipo) values
  (1, 'utilidad_objetivo', 0.20, '2026-01-01', 'utilidad'),
  (2, 'utilidad_objetivo', 0.20, '2026-01-01', 'utilidad'),
  (2, 'IVA', 0.10, '2026-01-01', 'suma'),
  (2, 'flete', 0.10, '2026-01-01', 'resta');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado)
  overriding system value values
  (1, 1, 1, '2026-10-08', 10, 10, 100, 50000, 'recepcionado'),
  (2, 1, 2, '2026-10-08', 10, 20, 200, 40000, 'recepcionado');
"""
PERDIDAS = """
insert into fichas_perdida_historial (ficha_id, perdida, vigente_desde)
  values (1, 0.18, '2026-10-10'), (3, 0.18, '2026-10-10');
"""
ANTES = datetime.combine(date(2026, 10, 9), time(12), tzinfo=ARGENTINA)
DESPUES = datetime.combine(date(2026, 10, 12), time(12), tzinfo=ARGENTINA)


def test_el_EJEMPLO_del_duenio():
    assert round(costo_del_kilo_util(5000, 0.18)) == 6098
    assert round(precio_sugerido_multi_concepto(costo_del_kilo_util(5000, 0.18), 0, [], [], 0.20)) == 7317
    assert costo_del_kilo_util(5000, 0.0) == 5000                     # con 0 no cambia nada
    with pytest.raises(ValueError):
        costo_del_kilo_util(5000, 1.0)


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    monkeypatch.setenv("DATABASE_URL", url)
    from tests.test_administracion_reordenada import CLAVES
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

    sql(SIEMBRA)
    yield d, m, sql


def _listado(cliente, momento):
    from app.costeo import calcular_listado_para_negociar_precios
    return {f["ficha_id"]: f for f in calcular_listado_para_negociar_precios(cliente, momento)}


def test_con_PERDIDA_CERO_todo_da_EXACTAMENTE_igual_en_todos_los_clientes(base):
    """Sin filas y con la pérdida cargada en 0 para todas las fichas, el
    listado entero (sugerido, utilidad, costo) es el mismo, número por número."""
    d, m, sql = base
    sin_filas = {c: _listado(c, DESPUES) for c in (1, 2)}
    sql("insert into fichas_perdida_historial (ficha_id, perdida, vigente_desde) "
        "values (1, 0, '2026-10-01'), (2, 0, '2026-10-01'), (3, 0, '2026-10-01')")
    en_cero = {c: _listado(c, DESPUES) for c in (1, 2)}
    assert en_cero == sin_filas
    assert sorted((c, f) for c in sin_filas for f in sin_filas[c]) == [(1, 1), (1, 2), (2, 3)]
    assert sin_filas[1][1]["precio_sugerido"] == pytest.approx(6000)          # 5.000 × 1,20


def test_con_18_por_ciento_da_el_ejemplo_y_solo_desde_que_RIGE(base):
    d, m, sql = base
    sql(PERDIDAS)
    despues, antes = _listado(1, DESPUES), _listado(1, ANTES)
    morron = despues[1]
    assert (morron["perdida"], round(morron["costo_util"]), round(morron["precio_sugerido"])) == (0.18, 6098, 7317)
    assert morron["costo_actual"] == pytest.approx(5000)            # el comprado no cambia
    assert antes[1]["precio_sugerido"] == pytest.approx(6000)       # el 09/10 todavía no regía
    assert despues[2]["precio_sugerido"] == pytest.approx(2400)     # el rival sin pérdida


def test_la_perdida_va_SOLO_sobre_la_mercaderia(base):
    """Cliente 2: caja de $120 cada 10 kg ($12 por kilo) y tasas que se
    anulan. (6.097,56 × 1,20 + 12) / 1 = 7.329,07: la caja no se infla."""
    d, m, sql = base
    sql(PERDIDAS)
    morron = _listado(2, DESPUES)[3]
    assert morron["precio_sugerido"] == pytest.approx(5000 / 0.82 * 1.2 + 12)
    # La utilidad del precio vigente también mira el costo útil (el "ahora" del panel).
    sql("insert into precios_venta_historial (articulo_id, cliente_id, ficha_id, precio, vigente_desde) "
        "values (1, 2, 3, 7329.07, '2026-10-01')")
    assert _listado(2, DESPUES)[3]["utilidad_aproximada"] == pytest.approx(0.20, abs=1e-5)


def test_COTIZACIONES_y_el_cajon_tipeado_usan_la_perdida(base):
    d, m, sql = base
    sql(PERDIDAS)
    from app.costeo import precio_de_la_cotizacion_del_cliente
    with patch("app.costeo.datetime") as reloj:
        reloj.now.return_value = DESPUES
        cajon = precio_de_la_cotizacion_del_cliente(1, 1, 50000, 10)
    assert (round(cajon["costo_unidad"]), round(cajon["precio_sugerido"])) == (5000, 7317)


def test_las_PANTALLAS_dicen_la_perdida_al_lado_del_costo_y_solo_donde_hay(base):
    d, m, sql = base
    sql("insert into fichas_perdida_historial (ficha_id, perdida, vigente_desde) values (1, 0.18, '2026-01-01')")
    from tests.test_administracion_reordenada import _cliente
    cotizaciones = _cliente(m).get("/precios/cotizaciones", params={"cliente_id": 1}).text
    marca = re.compile(r'<span class="perdida-chica" data-perdida>pérdida ([^<]*)</span>')
    assert marca.findall(cotizaciones) == ["18%"]                   # el Zapallo no lleva
    # Márgenes: al lado del sugerido en la tabla de todos (no hubo variación de costo).
    margenes = _cliente(m).get("/negociar", params={"cliente_id": 1}).text
    assert marca.findall(margenes) == ["18%"]
    # Cargar precios: la simulación calcula con el costo ÚTIL, por ficha.
    cargar = _cliente(m).get("/precios/cargar", params={"cliente_id": 1}).text
    costos = re.findall(r"costoProductoUnidadVenta: ([0-9.]+|null)", cargar)
    assert sorted(round(float(c)) for c in costos) == [2000, 6098]


def test_la_FICHA_se_edita_rige_desde_HOY_y_queda_en_la_bitacora(base):
    d, m, sql = base
    from tests.test_administracion_reordenada import _cliente
    datos = {"cliente_id": "1", "articulo_nombre": "EJEMPLO Morron", "envase_id": "", "contenido_caja": "10",
             "unidad_venta": "kilo", "envase_variable": "", "nombre_cliente": "", "codigo_cliente": ""}
    with patch.object(m, "_hoy_argentina", return_value=date(2026, 10, 12)):
        cliente = _cliente(m)
        assert cliente.post("/fichas/1/editar", data={**datos, "perdida": "18"},
                            follow_redirects=False).status_code == 303
        # El mismo día, el último valor pisa al anterior: una fila por día.
        cliente.post("/fichas/1/editar", data={**datos, "perdida": "12,5"}, follow_redirects=False)
        # Sin cambiar la pérdida no se escribe otra fila.
        cliente.post("/fichas/1/editar", data={**datos, "perdida": "12.5"}, follow_redirects=False)
        rechazo = cliente.post("/fichas/1/editar", data={**datos, "perdida": "95"}, follow_redirects=False)
        formulario = cliente.get("/fichas/1/editar").text
    assert sql("select perdida, vigente_desde from fichas_perdida_historial") == [
        (pytest.approx(0.125), date(2026, 10, 12))]
    assert rechazo.status_code == 400 and "La pérdida va de 0 a 90 %." in rechazo.text
    assert re.findall(r'<input type="number" id="perdida" name="perdida"[^>]*value="([^"]*)"', formulario) == ["12.5"]
    assert "Desde el 12/10/2026: 12,5%" in formulario
    bitacora = [float(p) if p is not None else None
                for (p,) in sql("select perdida from fichas_logistica_historial order by id")]
    assert bitacora == [0.18, 0.125, 0.125]
