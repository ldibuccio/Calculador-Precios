"""La migración que vincula la marca ESCRITA al recibir con su marca de cajón (28/09).

Corre el .sql tal cual contra Postgres con el esquema real (corolario 89): lo
que se verifica es que el bloque parsea, que pliega los nombres IGUAL que
`normalizar_texto` —si no, la marca creada acá y la que busca el código al
recibir serían dos— y que una segunda corrida no hace nada.
"""
import io
import os
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.matcheo_comanda import normalizar_texto  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


def _leer(nombre):
    return io.open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: la migración no se verificó")
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

    (art,), = sql("INSERT INTO articulos (nombre) VALUES ('EJEMPLO Fruta Texto') RETURNING id")
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) "
                   "VALUES ('EJEMPLO Puesto Texto', 'N93P01') RETURNING id")
    # La foto a las 12: lo recibido antes no lo suma el stock y no se toca.
    sql("INSERT INTO vacios_deposito_foto (proveedor_id, cantidad, fecha, creado_en) "
        "VALUES (%s, 40, '2026-09-25', '2026-09-25 12:00-03')", (prov,))
    # Una marca ya cargada: se REUSA, no se duplica.
    ya = d.crear_marca_vacio(prov, "Westfalia")

    def compra(marca, sena, procesada):
        (cid,), = sql(
            """INSERT INTO compras (fecha_operacion, articulo_id, proveedor_id, importe,
                   cantidad_cajones, contenido_por_cajon, cantidad_kilos, estado, sena,
                   marca, procesada_el, cantidad_cajones_real)
               VALUES (%s, %s, %s, 1000, 10, 16, 160, 'recepcionado', %s, %s, %s, 10)
               RETURNING id""",
            (date(2026, 9, 25), art, prov, sena, marca, procesada))
        return cid

    despues = "2026-09-26 09:00-03"
    compras = {
        "rio": compra("Río  Uruguay", 500, despues),
        "rio_bis": compra(" rio uruguay ", 500, despues),
        "westfalia": compra("WESTFALIA", 500, despues),
        "bandeja": compra("Bandeja", None, despues),       # sin seña: no se vincula
        "vieja": compra("Citrus", 500, "2026-09-25 10:00-03"),  # antes de la foto
        "sin_marca": compra(None, 500, despues),
    }

    def marca_de(cid):
        (mid,), = sql("SELECT marca_vacio_id FROM compras WHERE id = %s", (cid,))
        return mid

    return d, sql, prov, ya, compras, marca_de


def test_la_migracion_crea_las_marcas_plegadas_como_PYTHON_y_vincula(base):
    d, sql, prov, ya, compras, marca_de = base

    sql(_leer("vacios_marca_texto_1_vincular.sql"))

    marcas = sql("SELECT id, nombre, nombre_normalizado FROM marcas_vacio "
                 "WHERE proveedor_id = %s ORDER BY id", (prov,))
    # Una marca nueva (Río Uruguay, escrita de dos formas) más la que ya estaba.
    assert [m[1] for m in marcas] == ["Westfalia", "Río Uruguay"]
    for _id, nombre, plegado in marcas:
        assert plegado == normalizar_texto(nombre)
    rio = marcas[1][0]
    assert marca_de(compras["rio"]) == rio and marca_de(compras["rio_bis"]) == rio
    assert marca_de(compras["westfalia"]) == ya
    assert marca_de(compras["bandeja"]) is None
    assert marca_de(compras["vieja"]) is None
    assert marca_de(compras["sin_marca"]) is None

    # El stock de vacíos las ve en su pila: 40 de la foto sin asignar, 20 y 10.
    proveedor, = [p for p in d.stock_de_vacios_deposito() if p["id"] == prov]
    assert {p["marca"]: p["stock"] for p in proveedor["pilas"]} == {
        None: 50, "Río Uruguay": 20, "Westfalia": 10}


def test_una_SEGUNDA_corrida_no_hace_nada_y_la_verificacion_da_cero(base):
    _, sql, prov, _, compras, marca_de = base
    bloque = _leer("vacios_marca_texto_1_vincular.sql")
    sql(bloque)
    antes = (sql("SELECT count(*) FROM marcas_vacio")[0][0], marca_de(compras["rio"]))
    sql(bloque)
    assert (sql("SELECT count(*) FROM marcas_vacio")[0][0], marca_de(compras["rio"])) == antes

    fila, = sql(_leer("vacios_marca_texto_1_verificacion.sql"))
    assert fila[0] == "vacios_marca_texto_1_vincular"
    assert fila[1] == 0             # faltan_vincular
    assert fila[2] >= 3             # vinculadas
    assert fila[3] >= 1             # con marca y sin seña: no se toca


def test_ANTES_de_correrla_la_verificacion_ve_lo_que_falta(base):
    """Canario de la verificación: sin el bloque, faltan_vincular NO es cero."""
    _, sql, _, _, _, _ = base
    fila, = sql(_leer("vacios_marca_texto_1_verificacion.sql"))
    assert fila[1] >= 3


def test_los_bloques_entran_en_el_editor_y_el_codigo_va_arriba():
    for nombre in ("vacios_marca_texto_1_vincular.sql", "vacios_marca_texto_1_verificacion.sql"):
        texto = _leer(nombre)
        assert len(texto) <= 2500, nombre
        assert not texto.lstrip().startswith("--"), nombre


def test_el_plegado_de_la_migracion_es_el_del_indice_de_codigos():
    """La tabla de tildes se copió de plegar_tildes_en_codigo_cliente.sql, que ya
    tiene su test contra Python. Copiada envejece: ésta tiene que ser la misma."""
    import re
    origen = _leer("plegar_tildes_en_codigo_cliente.sql")
    tabla = re.search(r"translate\(btrim\(codigo_cliente\),\s*'([^']+)',\s*'([^']+)'\)", origen, re.S)
    aca = re.search(r"translate\(btrim\(%s\),\s*'([^']+)',\s*'([^']+)'\)",
                    _leer("vacios_marca_texto_1_vincular.sql"), re.S)
    assert aca.groups() == tabla.groups()


def test_la_consulta_de_RIO_URUGUAY_separa_lo_que_suma_de_lo_que_no(base):
    """Solo lee. Se corre acá para que parsee contra el esquema real y para ver
    que lo que dice que suma es lo mismo que suma el stock de la pantalla."""
    d, sql, prov, _, compras, _ = base
    sql("UPDATE proveedores SET nombre = 'EJEMPLO Río Uruguay SA' WHERE id = %s", (prov,))
    sql("UPDATE compras SET retiro_origen = 'logistica' WHERE id = %s", (compras["rio"],))
    sql("UPDATE compras SET retiro_origen = 'ingreso_directo' WHERE id = %s", (compras["bandeja"],))

    fila, = [f for f in sql(_leer("vacios_rio_uruguay_1_de_donde_sale.sql")) if f[1].startswith("EJEMPLO")]
    columnas = ("que", "proveedor", "foto", "foto_el", "todos", "con_sena", "sin_sena",
                "logistica", "deposito", "ingreso_directo", "otra", "id_con_sena",
                "devueltos", "ajustes", "compras")
    f = dict(zip(columnas, fila))
    # 5 después de la foto: rio, rio_bis, westfalia, sin_marca con seña; bandeja sin seña.
    assert (f["foto"], f["todos"], f["con_sena"], f["sin_sena"]) == (40, 50, 40, 10)
    assert (f["logistica"], f["ingreso_directo"], f["id_con_sena"]) == (10, 10, 0)
    proveedor, = [p for p in d.stock_de_vacios_deposito() if p["id"] == prov]
    assert proveedor["stock"] == f["foto"] + f["con_sena"] - f["devueltos"] + f["ajustes"]
