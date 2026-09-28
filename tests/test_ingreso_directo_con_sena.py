"""Ingreso directo con SEÑA y MARCA (dueño, 28/09).

El ingreso directo nace recibido y no pasa por Recepción. Con seña, sus
cajones suman a Vacíos y la marca se vincula a la del cajón (creándola si
falta), igual que al recibir. Sin seña queda la marca escrita y no suma.

La mitad de la base corre contra Postgres (corolario 89); la ruta, mockeada.
"""
import os
import sys
from datetime import date
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402
from tests.test_app import (  # noqa: E402
    ARTICULOS_CON_UNIDAD_COMPRA,
    HOY_DE_PRUEBA,
    PROVEEDORES_DE_PRUEBA,
    cliente,
)

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    monkeypatch.setenv("DATABASE_URL", preparar_base())
    import app.db as d

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

    (art,), = sql("INSERT INTO articulos (nombre) VALUES ('EJEMPLO Fruta Directa') RETURNING id")
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES ('EJEMPLO Puesto Directo', 'N95P01') RETURNING id")

    def ingresar(cajones, sena, marca):
        d.crear_compra(date.today(), art, prov, cajones, 10, cajones * 10, None, None, sena,
                       "Clark", ingreso_directo_deposito=True, segunda_por_cajon=None,
                       codigo_llegada=None, marca=marca)
        (cid,), = sql("SELECT max(id) FROM compras")
        fila, = sql("SELECT estado, sena, marca, marca_vacio_id FROM compras WHERE id = %s", (cid,))
        return fila

    return d, prov, ingresar


def _pilas(d, prov):
    proveedor = [p for p in d.stock_de_vacios_deposito() if p["id"] == prov]
    return {p["marca"]: p["stock"] for p in proveedor[0]["pilas"]} if proveedor else {}


def test_CON_SENA_los_cajones_suman_a_Vacios_en_la_pila_de_su_marca(base):
    d, prov, ingresar = base
    estado, sena, marca, marca_id = ingresar(12, 800, "  Río  Uruguay ")
    assert (estado, float(sena), marca) == ("recepcionado", 800.0, "Río Uruguay")
    assert [m["id"] for m in d.listar_marcas_vacio(prov)] == [marca_id]
    # Otra escrita distinto: la misma pila.
    ingresar(3, 800, "rio uruguay")
    assert _pilas(d, prov) == {"Río Uruguay": 15}


def test_SIN_SENA_la_marca_queda_escrita_y_no_suma(base):
    d, prov, ingresar = base
    assert ingresar(20, None, "Bandeja")[2:] == ("Bandeja", None)
    assert d.listar_marcas_vacio(prov) == []
    assert _pilas(d, prov) == {}


def test_CON_SENA_y_sin_marca_suma_a_sin_asignar(base):
    d, prov, ingresar = base
    assert ingresar(5, 300, "")[2:] == (None, None)
    assert _pilas(d, prov) == {None: 5}


# --- la ruta ------------------------------------------------------------

def _post(**datos):
    base_datos = {"proveedor_id": "200", "accion": "agregar", "articulo_id": "5",
                  "cantidad_cajones": "10", "contenido_por_cajon": "18", "tipo_retiro": "Clark",
                  "codigo_llegada": "N07P41"}
    base_datos.update(datos)
    with patch("app.main.obtener_proveedor", return_value=PROVEEDORES_DE_PRUEBA[0]), \
         patch("app.main.obtener_articulo", return_value=ARTICULOS_CON_UNIDAD_COMPRA[0]), \
         patch("app.main.listar_articulos", return_value=ARTICULOS_CON_UNIDAD_COMPRA), \
         patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]), \
         patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA), \
         patch("app.main.crear_compra") as crear:
        respuesta = cliente.post("/deposito/ingresar", data=base_datos, follow_redirects=False)
    return respuesta, crear


def test_la_ruta_pasa_la_SENA_y_la_MARCA_a_la_escritura():
    respuesta, crear = _post(sena="800", marca="Westfalia")
    assert respuesta.status_code == 303
    assert crear.call_args.args[8] == 800.0          # la seña, en su lugar
    assert crear.call_args.args[7] is None           # el importe sigue vacío
    assert crear.call_args.kwargs["marca"] == "Westfalia"


def test_si_REBOTA_la_seña_y_la_marca_vuelven_cargadas():
    """El que reintenta corrige lo que la pantalla le marcó y no revisa el
    resto (corolario 43): lo que se pierde en el re-render se pierde callado."""
    respuesta, crear = _post(sena="800", marca="Westfalia", cantidad_cajones="")
    assert respuesta.status_code == 400
    crear.assert_not_called()
    # Anclado en el CAMPO y no en un corte por </style>: el modal de "vino
    # armada" trae su propio <style> y el corte se lleva la pantalla (corolario 50).
    import re
    assert re.search(r'name="sena"[^>]*value="800"', respuesta.text)
    assert re.search(r'name="marca"[^>]*value="Westfalia"', respuesta.text)


def test_una_SENA_invalida_rebota():
    respuesta, crear = _post(sena="-5")
    assert respuesta.status_code == 400
    crear.assert_not_called()
    assert "La seña no puede ser negativa." in respuesta.text
