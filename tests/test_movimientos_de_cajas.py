# -*- coding: utf-8 -*-
"""La lista de movimientos de cajas (dueño, 25/09: "hoy no tengo forma de verlos").

Junta las DOS fuentes que mueven el stock de cajas —lo que declara una persona
y lo que arma una guía R en caja nuestra— y cada una con el signo que ya usa el
stock. LA PRUEBA DE QUE NO ES UNA CUENTA NUEVA es la última de la primera
tanda: la lista, sumada desde el conteo inicial, da exactamente el stock que
devuelve `stock_de_envases`. Dos cuentas que se separaran dirían dos números.

Contra Postgres con el esquema real, con el interruptor del humo: sin Postgres
se saltea, y con HUMO_OBLIGATORIO=1 no poder correrlo FALLA.
"""
import datetime
import os
import re
import sys
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

# EL GALPÓN. Cada fila está para que una pata leída mal dé OTRO número:
#
#   01/09  conteo inicial 100                     (la foto: no suma ni resta)
#   02/09  compra +50
#   03/09  préstamo a un colega −20
#   04/09  guía R normal: 12 de primera en caja   −12
#   05/09  guía R EN ORIGEN: 8 llegaron armadas    +8
#   06/09  guía R INICIAL                           0  -> no aparece
#   07/09  un ajuste ANULADO −30                       -> no aparece
#   07/09  una guía R SIN caja nuestra                 -> no aparece
#   20/09  compra +40                                  -> afuera de la ventana
SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Súper');
insert into articulos (id, nombre, grupo) overriding system value values (1, 'EJEMPLO Tomate', 'hortaliza');
insert into proveedores (id, nombre, codigo_puesto) overriding system value values (1, 'EJEMPLO Puesto', 'N01P01');
insert into envases (id, nombre) overriding system value values (1, 'Caja EJEMPLO');
insert into colegas (id, nombre, nombre_normalizado) overriding system value values (1, 'Colega EJEMPLO', 'colega ejemplo');
insert into fichas_logistica (id, cliente_id, articulo_id, contenido_caja, unidad_venta, envase_id)
  overriding system value values (1, 1, 1, 10, 'kilo', 1);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, estado)
  overriding system value values (1, 1, 1, '2026-09-05', 8, 10, 80, 'recepcionado');
insert into movimientos_envase (envase_id, origen, cantidad, fecha_operacion, stock_sistema, colega_id, motivo, anulado_el) values
  (1, 'conteo_inicial', 100, '2026-09-01', 0, null, null, null),
  (1, 'compra', 50, '2026-09-02', 100, null, null, null),
  (1, 'colega_le_presto', -20, '2026-09-03', 150, 1, null, null),
  (1, 'ajuste', -30, '2026-09-07', 0, null, 'EJEMPLO anulado', now()),
  (1, 'compra', 40, '2026-09-20', 0, null, null, null);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, tipo, ficha_id, envase_id,
                        lleva_caja_nuestra, compra_origen_id)
  overriding system value values
  (10, 1, '2026-09-04', 15, 12, 0, 0, 'normal',    1, 1,    true, null),
  (11, 1, '2026-09-05',  8,  8, 0, 0, 'en_origen', 1, 1,    true, 1),
  (12, 1, '2026-09-06',  0,  5, 0, 0, 'inicial',   1, 1,    true, null),
  (13, 1, '2026-09-07',  4,  4, 0, 0, 'normal',    1, null, false, null);
"""

DESDE, HASTA = datetime.date(2026, 9, 1), datetime.date(2026, 9, 10)


@pytest.fixture
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay un Postgres usable: la lista de "
                        "movimientos de cajas no se verificó en esta corrida.")
        pytest.skip("sin Postgres local: se corre con el humo antes de desplegar")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        yield url


def test_la_lista_trae_las_DOS_fuentes_con_su_signo_y_deja_afuera_lo_que_no_mueve(base):
    from app.db import movimientos_de_cajas
    filas = [(m["fecha"].day, m["fuente"], m["origen"], m["cajas"], m["colega"], m["guia_id"])
             for m in movimientos_de_cajas(DESDE, HASTA)]
    assert filas == [
        (5, "guia", "en_origen", 8, None, 11),
        (4, "guia", "normal", -12, None, 10),
        (3, "declarado", "colega_le_presto", -20, "Colega EJEMPLO", None),
        (2, "declarado", "compra", 50, None, None),
        (1, "declarado", "conteo_inicial", 100, None, None),
    ]


def test_la_lista_SUMADA_desde_el_conteo_da_el_MISMO_stock_que_la_tarjeta(base):
    """El control que ata la lista al stock: si una de las dos leyera el signo
    de la guía distinto, o contara la inicial, los dos números se separan."""
    from app.db import movimientos_de_cajas, stock_de_envases
    lista = movimientos_de_cajas(DESDE, datetime.date(2030, 1, 1))
    contadas = sum(m["cajas"] for m in lista if m["origen"] == "conteo_inicial")
    movido = sum(m["cajas"] for m in lista if m["origen"] != "conteo_inicial")
    (envase,) = stock_de_envases()
    assert (contadas, movido) == (100, 50 - 20 - 12 + 8 + 40)
    assert envase["stock"] == contadas + movido


def test_la_ventana_de_fechas_recorta_en_los_DOS_extremos(base):
    from app.db import movimientos_de_cajas
    solo = movimientos_de_cajas(datetime.date(2026, 9, 3), datetime.date(2026, 9, 4))
    assert [m["fecha"].day for m in solo] == [4, 3]


# --- La pantalla, con la base mockeada ---------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.main import PUERTA_ADMINISTRACION, PUERTA_COMPRAS, app  # noqa: E402

cliente = TestClient(app)

UNA_LISTA = [
    {"fuente": "declarado", "fecha": datetime.date(2026, 9, 3), "origen": "colega_le_presto",
     "envase": "Caja EJEMPLO", "cajas": -20, "colega": "Colega EJEMPLO", "motivo": None,
     "guia_id": None, "articulo": None},
    {"fuente": "guia", "fecha": datetime.date(2026, 9, 4), "origen": "normal",
     "envase": "Caja EJEMPLO", "cajas": -12, "colega": None, "motivo": None,
     "guia_id": 10, "articulo": "EJEMPLO Tomate"},
    {"fuente": "declarado", "fecha": datetime.date(2026, 9, 1), "origen": "conteo_inicial",
     "envase": "Caja EJEMPLO", "cajas": 100, "colega": None, "motivo": None,
     "guia_id": None, "articulo": None},
]


def _get(url):
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "c", "CLAVE_ADMINISTRACION": "a"}), \
         patch("app.main.movimientos_de_cajas", return_value=[dict(m) for m in UNA_LISTA]) as leer:
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("c"))
        cliente.cookies.set(PUERTA_ADMINISTRACION.cookie, PUERTA_ADMINISTRACION.firma("a"))
        try:
            respuesta = cliente.get(url)
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)
            cliente.cookies.delete(PUERTA_ADMINISTRACION.cookie)
    return respuesta, leer


@pytest.mark.parametrize("prefijo, otro", [("/compras", "/administracion"),
                                           ("/administracion", "/compras")])
def test_la_pantalla_dice_QUE_PASO_cuantas_y_de_que_caja_y_se_queda_en_su_sector(prefijo, otro):
    respuesta, leer = _get(f"{prefijo}/cajas/movimientos?desde=2026-09-01&hasta=2026-09-10")
    assert respuesta.status_code == 200
    assert leer.call_args.args == (datetime.date(2026, 9, 1), datetime.date(2026, 9, 10))
    marcado = " ".join(respuesta.text.split("</style>")[-1].split())
    assert "3 movimientos del 01/09/2026 al 10/09/2026" in marcado
    assert "Le presté cajas a un colega" in marcado and "−20" not in marcado and "-20" in marcado
    assert "Se armaron en una guía R" in marcado and "guía R 10 (EJEMPLO Tomate)" in marcado
    assert "100 contadas" in marcado, "el conteo inicial no suma ni resta: va sin signo"
    assert f'action="{prefijo}/cajas/movimientos"' in marcado
    # La barra trae su propio <style>, así que el atrás vive ANTES del último
    # `</style>` (corolario 50): se mira sobre el texto entero.
    assert f'href="{prefijo}/cajas" aria-label="Volver atrás"' in respuesta.text
    assert otro + "/" not in respuesta.text


def test_SIN_fechas_mira_los_ULTIMOS_30_dias_hasta_hoy():
    with patch("app.main._hoy_argentina", return_value=datetime.date(2026, 9, 25)):
        _, leer = _get("/compras/cajas/movimientos")
    assert leer.call_args.args == (datetime.date(2026, 8, 26), datetime.date(2026, 9, 25))


def test_una_fecha_que_no_se_entiende_SE_DICE_en_vez_de_cambiarse_en_silencio():
    respuesta, _ = _get("/compras/cajas/movimientos?desde=ayer")
    assert "Alguna de las fechas no es válida" in respuesta.text


def test_fechas_DADAS_VUELTA_se_acomodan_y_se_avisa():
    respuesta, leer = _get("/compras/cajas/movimientos?desde=2026-09-10&hasta=2026-09-01")
    assert leer.call_args.args == (datetime.date(2026, 9, 1), datetime.date(2026, 9, 10))
    assert "se dieron vuelta" in respuesta.text


def test_la_pantalla_de_CAJAS_tiene_el_link_a_los_movimientos():
    from tests.test_cajas_y_vacios_en_administracion import _con_datos
    with _con_datos(), patch.dict(os.environ, {"CLAVE_ADMINISTRACION": "a"}):
        cliente.cookies.set(PUERTA_ADMINISTRACION.cookie, PUERTA_ADMINISTRACION.firma("a"))
        try:
            marcado = cliente.get("/administracion/cajas").text.split("</style>")[-1]
        finally:
            cliente.cookies.delete(PUERTA_ADMINISTRACION.cookie)
    assert 'class="accion ver-movimientos" href="/administracion/cajas/movimientos"' in marcado


def test_TODO_origen_de_la_base_tiene_su_rotulo_y_ningun_rotulo_sobra():
    """Lee los dos CHECK de `db/esquema_completo.sql` —no una copia— y compara
    en las DOS direcciones: un origen nuevo sin rótulo se mostraría crudo, y un
    rótulo sin origen protegería algo que ya no existe."""
    from core.envases import ROTULOS_DE_MOVIMIENTO_DE_CAJAS
    esquema = open(os.path.join(RAIZ, "db", "esquema_completo.sql"), encoding="utf-8").read()

    def lista(nombre):
        cuerpo = re.search(rf"constraint {nombre}\s+check \((?:\w+) in \((.*?)\)\)", esquema, re.S).group(1)
        return set(re.findall(r"'([a-z_]+)'", cuerpo))

    encontrado = lista("movimientos_envase_origen_check") | {
        f"guia_{t}" for t in lista("reprocesos_tipo_check") if t != "inicial"}
    assert set(ROTULOS_DE_MOVIMIENTO_DE_CAJAS) == encontrado
