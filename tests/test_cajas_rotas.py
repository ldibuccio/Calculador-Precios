# -*- coding: utf-8 -*-
"""Las cajas ROTAS: una merma de cajas vacías que es plata perdida (dueño, 25/09).

Se cargan en Cajas como un movimiento más (origen `merma`, siempre resta) y
van a Gerencia → Pérdidas como un renglón propio que SUMA AL TOTAL.

CONTRA LA BASE, porque la plata no vive en ninguna columna: se valúa al costo
de la caja vigente EL DÍA de la rotura, con el mismo fragmento SQL que las
otras cuentas de plata de cajas. Con la base mockeada el costo lo decidiría el
fixture (corolario 91).

EL GALPÓN, y cada fila está para que una pata leída mal dé OTRO número:

  costo de la caja EJEMPLO: $50 desde el 01/01, $80 desde el 20/09
  ventana 10/09 al 30/09

  15/09  se rompen 4 cajas EJEMPLO            -> 4 x $50  = $200
  21/09  se rompe 1 caja EJEMPLO              -> 1 x $80  = $80   (el costo de ESE día)
  16/09  se rompen 3, pero la merma se ANULÓ  -> no cuenta
  05/10  se rompe 1                           -> afuera de la ventana
  17/09  se compran 10                        -> no es una rotura
  18/09  se rompen 2 cajas SIN COSTO cargado  -> 2 cajas, $0, y se dicen

  total esperado: 7 cajas · $280 · 2 sin costo
"""
import datetime
import os
import sys
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into envases (id, nombre) overriding system value
  values (1, 'Caja EJEMPLO'), (2, 'Caja EJEMPLO sin costo');
insert into envases_costo_historial (envase_id, costo, vigente_desde)
  values (1, 50, '2026-01-01'), (1, 80, '2026-09-20');
insert into movimientos_envase (envase_id, origen, cantidad, fecha_operacion, stock_sistema, anulado_el)
  values (1, 'merma', -4, '2026-09-15', 0, null),
         (1, 'merma', -1, '2026-09-21', 0, null),
         (1, 'merma', -3, '2026-09-16', 0, now()),
         (1, 'merma', -1, '2026-10-05', 0, null),
         (1, 'compra', 10, '2026-09-17', 0, null),
         (2, 'merma', -2, '2026-09-18', 0, null);
"""

DESDE, HASTA = datetime.date(2026, 9, 10), datetime.date(2026, 9, 30)


@pytest.fixture(scope="module")
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay un Postgres usable: las cajas "
                        "rotas no se verificaron en esta corrida.")
        pytest.skip("sin Postgres local: se corre con el humo antes de desplegar")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    return url


def _perdidas(url):
    import app.db as db
    with patch.dict(os.environ, {"DATABASE_URL": url}):
        return db.perdidas_por_periodo(DESDE, HASTA)


def test_las_cajas_ROTAS_se_valuan_al_costo_del_DIA_y_dejan_afuera_lo_que_no_es_rotura(base):
    rotas = _perdidas(base)["cajas_rotas"]
    assert (rotas["cajas"], rotas["total"], rotas["sin_costo"]) == (7, 280.0, 2)
    assert [(r["envase"], r["cajas"], r["pesos"], r["sin_costo"]) for r in rotas["por_envase"]] == [
        ("Caja EJEMPLO", 5, 280.0, 0),
        ("Caja EJEMPLO sin costo", 2, 0.0, 2),
    ]


def test_las_cajas_rotas_SUMAN_AL_TOTAL_de_Perdidas(base):
    """Son plata perdida igual que la mercadería (dueño, 25/09). Acá no hay
    ninguna merma de mercadería plantada, así que el total entero son ellas:
    si no sumaran, daría cero."""
    resultado = _perdidas(base)
    assert resultado["total"] == 280.0
    assert resultado["total"] == resultado["cajas_rotas"]["total"] + sum(
        r["total"] for r in resultado["renglones"].values())


# --- La carga en Cajas y la pantalla, con la base mockeada --------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.main import PUERTA_COMPRAS, app  # noqa: E402

cliente = TestClient(app)


def test_cargar_cajas_rotas_RESTA_aunque_se_tipee_en_positivo():
    """El signo lo pone el server: la pregunta es cuántas se rompieron."""
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "c"}), \
         patch("app.main.crear_movimiento_envase") as crear:
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("c"))
        try:
            respuesta = cliente.post("/compras/cajas/movimiento", follow_redirects=False,
                                     data={"envase_id": "1", "origen": "merma",
                                           "cantidad": "4", "fecha": "2026-09-15"})
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)
    assert respuesta.status_code == 303
    assert crear.call_args.args[:3] == (1, "merma", -4)


def test_la_pantalla_de_Cajas_OFRECE_las_cajas_rotas():
    from tests.test_cajas_y_vacios_en_administracion import _con_datos
    with _con_datos(), patch.dict(os.environ, {"CLAVE_COMPRAS": "c"}):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("c"))
        try:
            marcado = cliente.get("/compras/cajas").text.split("</style>")[-1]
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)
    assert '<option value="merma">Se rompieron cajas</option>' in marcado


def test_Perdidas_DIBUJA_el_renglon_de_cajas_rotas_con_su_desglose():
    from tests.test_perdidas import PERDIDAS, _marcado
    resultado = dict(PERDIDAS, cajas_rotas={
        "cajas": 7, "total": 280.0, "sin_costo": 2,
        "por_envase": [{"envase": "Caja EJEMPLO", "cajas": 5, "pesos": 280.0, "sin_costo": 0},
                       {"envase": "Caja EJEMPLO sin costo", "cajas": 2, "pesos": 0.0, "sin_costo": 2}]})
    marcado = _marcado(resultado=resultado)
    renglon = marcado.split('data-destino="cajas_rotas"')[1].split('data-destino=')[0]
    texto = " ".join(renglon.split())
    assert "Cajas rotas" in texto and "7 cajas" in texto
    assert "Caja EJEMPLO: 5" in texto
    assert "2 cajas rotas no tienen" in texto


def test_Perdidas_dibuja_el_renglon_de_cajas_rotas_AUNQUE_este_en_cero():
    """Como los otros dos: un renglón que desaparece en cero no distingue
    "no se rompió ninguna" de "esta pantalla no las cuenta"."""
    from tests.test_perdidas import PERDIDAS, _marcado
    assert 'data-destino="cajas_rotas"' in _marcado(resultado=PERDIDAS)
