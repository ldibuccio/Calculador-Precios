"""La seña cargada DESPUÉS de recibir (dueño, 05/10): los cajones van a la pila de su marca.

Hasta el 05/10, Recepción pegaba la marca escrita a su marca de cajón solo si
la compra ya tenía seña. Una seña cargada después desde Editar dejaba los
cajones en "sin asignar" con la marca escrita. Dos mitades:

- el CÓDIGO: `actualizar_precio_compra` la pega con la misma regla;
- la MIGRACIÓN `vacios_marca_texto_2_sena_tarde.sql` corrige las que ya
  quedaron (en Frutamax, la 921), y aborta si esos cajones ya salieron de
  "sin asignar": se contarían dos veces.

Contra Postgres con el esquema real (corolario 89).
"""
import io
import os
import re
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
MIGRACION = "vacios_marca_texto_2_sena_tarde.sql"
VERIFICACION = "vacios_marca_texto_2_verificacion.sql"


def _leer(nombre):
    return io.open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    monkeypatch.setenv("DATABASE_URL", preparar_base())
    import app.db as d

    def sql(consulta, parametros=()):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros or None)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()

    (art,), = sql("INSERT INTO articulos (nombre) VALUES ('EJEMPLO Fruta Seña') RETURNING id")
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES ('EJEMPLO Puesto Seña', 'N94P01') RETURNING id")
    westfalia = d.crear_marca_vacio(prov, "Westfalia")

    def compra(marca, sena, marca_vacio_id=None, cajones=10):
        (cid,), = sql(
            """INSERT INTO compras (fecha_operacion, articulo_id, proveedor_id, importe,
                   cantidad_cajones, contenido_por_cajon, cantidad_kilos, estado, sena,
                   marca, marca_vacio_id, procesada_el, cantidad_cajones_real)
               VALUES (%s, %s, %s, 1000, %s, 16, 160, 'recepcionado', %s, %s, %s,
                       '2026-10-02 12:00-03', %s)
               RETURNING id""",
            (date(2026, 10, 2), art, prov, cajones, sena, marca, marca_vacio_id, cajones))
        return cid

    def marca_de(cid):
        (mid,), = sql("SELECT marca_vacio_id FROM compras WHERE id = %s", (cid,))
        return mid

    def pilas():
        proveedor = [p for p in d.stock_de_vacios_deposito() if p["id"] == prov]
        return {p["marca"]: p["stock"] for p in proveedor[0]["pilas"]} if proveedor else {}

    return d, sql, prov, westfalia, compra, marca_de, pilas


# --- el CÓDIGO ----------------------------------------------------------------

def test_la_SENA_cargada_DESPUES_manda_los_cajones_a_la_pila_de_su_MARCA(base):
    d, _, _, _, compra, marca_de, pilas = base
    cid = compra(" camila ", None)
    assert pilas() == {}  # sin seña no entra a Vacíos

    d.actualizar_precio_compra(cid, 1000, 500)

    assert marca_de(cid) is not None
    assert pilas() == {"camila": 10}


def test_la_marca_ya_PUESTA_no_se_pisa_y_sin_marca_escrita_no_se_inventa(base):
    """El rival: una compra con su marca de cajón ya elegida queda con ésa."""
    d, _, _, westfalia, compra, marca_de, pilas = base
    con_marca = compra("Otra", None, marca_vacio_id=westfalia)
    sin_marca = compra(None, None, cajones=4)

    d.actualizar_precio_compra(con_marca, 1000, 500)
    d.actualizar_precio_compra(sin_marca, 1000, 500)

    assert marca_de(con_marca) == westfalia
    assert marca_de(sin_marca) is None
    assert pilas() == {"Westfalia": 10, None: 4}


def test_la_misma_marca_escrita_distinto_cae_en_la_MISMA_pila(base):
    d, _, _, _, compra, marca_de, _ = base
    una, otra = compra("Río Uruguay", None), compra("rio  uruguay", None)
    d.actualizar_precio_compra(una, 1000, 500)
    d.actualizar_precio_compra(otra, 1000, 500)
    assert marca_de(una) == marca_de(otra) is not None


# --- la MIGRACIÓN -------------------------------------------------------------

def test_la_migracion_VINCULA_las_que_quedaron_y_una_segunda_corrida_no_hace_nada(base):
    _, sql, prov, westfalia, compra, marca_de, pilas = base
    camila = compra("Camila", 1000)                   # la 921 de Frutamax
    ya = compra("Otra", 1000, marca_vacio_id=westfalia)
    sin_sena = compra("Bandeja", None)
    assert pilas() == {None: 10, "Westfalia": 10}
    antes = sql(_leer(VERIFICACION))[0][1]
    assert antes >= 1                                 # canario de la verificación

    sql(_leer(MIGRACION))
    marcas = sql("SELECT count(*) FROM marcas_vacio")[0][0]
    sql(_leer(MIGRACION))

    assert sql("SELECT count(*) FROM marcas_vacio")[0][0] == marcas
    assert marca_de(ya) == westfalia and marca_de(sin_sena) is None
    assert pilas() == {"Camila": 10, "Westfalia": 10}
    fila, = sql(_leer(VERIFICACION))
    assert (fila[0], fila[1]) == ("vacios_marca_texto_2_sena_tarde", 0)
    assert marca_de(camila) is not None


def test_la_migracion_ABORTA_si_los_cajones_ya_salieron_de_sin_asignar(base):
    """Una asignación desde "sin asignar" ya los movió: vincular los contaría dos veces."""
    _, sql, prov, westfalia, compra, marca_de, pilas = base
    camila = compra("Camila", 1000)
    sql("INSERT INTO vacios_deposito_asignaciones (proveedor_id, marca_desde_id, marca_hasta_id, "
        "cantidad, stock_sistema, creado_en) VALUES (%s, NULL, %s, 10, 10, '2026-10-03 10:00-03')",
        (prov, westfalia))
    import psycopg2
    with pytest.raises(psycopg2.Error, match="ABORTA: 1 compras"):
        sql(_leer(MIGRACION))
    assert marca_de(camila) is None
    assert pilas() == {None: 0, "Westfalia": 10}


def test_los_bloques_entran_en_el_editor_y_el_codigo_va_arriba():
    for nombre in (MIGRACION, VERIFICACION):
        texto = _leer(nombre)
        assert len(texto) <= 2500, nombre
        assert not texto.lstrip().startswith("--"), nombre
    assert _leer(VERIFICACION).lstrip().lower().startswith(
        "select 'vacios_marca_texto_2_sena_tarde' as que_migracion")


def test_el_plegado_es_EL_MISMO_de_la_migracion_del_28_09():
    patron = r"translate\(btrim\(%s\),\s*'([^']+)',\s*'([^']+)'\)"
    assert (re.search(patron, _leer(MIGRACION), re.S).groups()
            == re.search(patron, _leer("vacios_marca_texto_1_vincular.sql"), re.S).groups())
