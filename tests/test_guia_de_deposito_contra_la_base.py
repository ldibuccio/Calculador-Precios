"""La guía PROPIA del ingreso directo de Depósito (dueño, 25/09), contra Postgres.

"El ingreso directo de Depósito nunca es parte de la comanda del Puesto": desde
el 25/09 hay DOS guías por día y proveedor, la de Compras y la de Depósito
(`guias_compra.de_deposito`).

CONTRA LA BASE Y EN LOS DOS ESTADOS del esquema, porque el código tiene que
andar en los dos: con el unique viejo `(fecha, proveedor)` todavía puesto
—entre el deploy y `guia_deposito_2`— y sin él. Con la base mockeada, el
`ON CONFLICT` no lo arbitra nadie y lo que se afirma lo decide el fixture
(corolario 89).
"""
import os
import sys
from datetime import date, timedelta

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
DIA = date(2026, 9, 26)


@pytest.fixture
def galpon(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: la guía de depósito no se verificó")
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

    (art,), = sql("INSERT INTO articulos (nombre) VALUES ('EJEMPLO Fruta Guía') RETURNING id")
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES ('EJEMPLO Puesto Guía', 'N91P01') RETURNING id")
    (otro,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES ('EJEMPLO Otro Guía', 'N91P02') RETURNING id")

    def cargar(directo, dia=DIA, proveedor=None):
        d.crear_compra(dia, art, proveedor or prov, 10, 16, 160, None, 50000, None,
                       "Clark", None, ingreso_directo_deposito=directo,
                       segunda_por_cajon=None)
        fila, = sql("SELECT c.id, c.guia_id, c.guia_punto, g.de_deposito FROM compras c "
                       "JOIN guias_compra g ON g.id = c.guia_id "
                       "WHERE c.id = (SELECT max(id) FROM compras)")
        return fila

    return d, sql, cargar, prov, otro


def test_el_ingreso_directo_va_a_OTRA_guia_que_la_de_Compras_el_mismo_dia(galpon):
    _, _, cargar, _, _ = galpon
    _, guia_compras, punto_c1, dep_c = cargar(directo=False)
    _, guia_dep, punto_d1, dep_d = cargar(directo=True)
    _, guia_compras_2, punto_c2, _ = cargar(directo=False)
    _, guia_dep_2, punto_d2, _ = cargar(directo=True)

    assert guia_compras != guia_dep
    assert (dep_c, dep_d) == (False, True)
    # cada guía numera SUS renglones: el papel de Compras no salta un número
    # porque Depósito recibió algo en el medio
    assert (guia_compras_2, punto_c1, punto_c2) == (guia_compras, 1, 2)
    assert (guia_dep_2, punto_d1, punto_d2) == (guia_dep, 1, 2)


def test_la_comanda_de_la_carga_manual_NUNCA_se_cuelga_de_la_guia_de_deposito(galpon):
    d, sql, cargar, prov, _ = galpon
    cargar(directo=True)
    # Solo hay ingresos directos ese día: no hay dónde colgarla.
    assert d.agregar_foto_guia_del_dia(DIA, prov, "2026-09-26/comanda.jpg") is False
    _, guia_compras, _, _ = cargar(directo=False)
    assert d.agregar_foto_guia_del_dia(DIA, prov, "2026-09-26/comanda.jpg") is True
    (fotos,), = sql("SELECT array_agg(g.de_deposito) FROM fotos_guia f "
                    "JOIN guias_compra g ON g.id = f.guia_id")
    assert fotos == [False]


def test_mover_de_dia_un_ingreso_directo_lo_deja_en_la_guia_de_DEPOSITO(galpon):
    d, sql, cargar, _, _ = galpon
    compra_id, _, _, _ = cargar(directo=True)
    cargar(directo=False, dia=DIA + timedelta(days=1))   # la de Compras del día nuevo ya existe
    movida = d.mover_compra_de_fecha(compra_id, DIA + timedelta(days=1),
                                     DIA + timedelta(days=1))
    (de_deposito,), = sql("SELECT de_deposito FROM guias_compra WHERE id = %s",
                          (movida["guia_id"],))
    assert de_deposito is True


def test_cambiar_de_proveedor_un_ingreso_directo_lo_deja_en_la_guia_de_DEPOSITO(galpon):
    d, sql, cargar, _, otro = galpon
    compra_id, _, _, _ = cargar(directo=True)
    cargar(directo=False, proveedor=otro)                # la de Compras del otro ya existe
    cambio = d.cambiar_proveedor_de_compra(compra_id, otro)
    fila, = sql("SELECT proveedor_id, de_deposito FROM guias_compra WHERE id = %s",
                   (cambio["guia_id"],))
    assert fila == (otro, True)


def test_CON_el_unique_viejo_puesto_no_rebota_y_usa_la_guia_que_hay(galpon):
    """Entre el deploy y `guia_deposito_2` conviven los dos uniques.

    Con un `ON CONFLICT (fecha, proveedor, de_deposito)` el INSERT de la
    segunda guía del día viola el VIEJO y la carga entera rebota. Sin target
    no hace nada, y la compra va a la guía de ese día como antes del cambio.
    """
    _, sql, cargar, _, _ = galpon
    sql("ALTER TABLE guias_compra ADD CONSTRAINT guias_viejo_unico_de_prueba "
        "UNIQUE (fecha_operacion, proveedor_id)")
    _, guia_compras, _, _ = cargar(directo=False)
    _, guia_dep, punto, _ = cargar(directo=True)
    assert guia_dep == guia_compras
    assert punto == 2
