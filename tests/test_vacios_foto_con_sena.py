"""La foto de vacíos del 25/09 recalculada con la regla de la seña (dueño, 28/09).

EL CASO, con los números de Frutamax: 9 contados el 24/09, 279 cajones
recibidos ese día (solo los 10 de pomelo con seña) y 510 el 25/09, ninguno con
seña. La foto dio 798 = 9 + 279 + 510. Con la regla, 19 = 9 + 10.

Corren los tres .sql tal cual contra Postgres con el esquema real
(corolario 89): la revisión, la migración y la verificación. El 798 se pone a
mano, sacado de la cuenta de arriba y no de la consulta, para que la columna
de control choque contra un número que no salió de ella (corolario 19).
"""
import io
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
FOTO_EL = "2026-09-25 18:00-03"


def _leer(nombre):
    return io.open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: la foto no se verificó")
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

    (art,), = sql("INSERT INTO articulos (nombre) VALUES ('EJEMPLO Fruta Foto') RETURNING id")

    def proveedor(nombre, codigo, foto, conteo=None):
        (pid,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) RETURNING id",
                      (nombre, codigo))
        if conteo is not None:
            sql("INSERT INTO conteos_vacios_deposito (proveedor_id, cantidad, fecha, stock_sistema, creado_en) "
                "VALUES (%s, %s, '2026-09-24', 0, '2026-09-24 08:00-03')", (pid, conteo))
        sql("INSERT INTO vacios_deposito_foto (proveedor_id, cantidad, fecha, creado_en) "
            "VALUES (%s, %s, '2026-09-25', %s)", (pid, foto, FOTO_EL))
        return pid

    def compra(pid, cajones, sena, procesada):
        sql("""INSERT INTO compras (fecha_operacion, articulo_id, proveedor_id, importe,
                   cantidad_cajones, contenido_por_cajon, cantidad_kilos, estado, sena,
                   procesada_el, cantidad_cajones_real)
               VALUES ('2026-09-24', %s, %s, 1000, %s, 10, %s, 'recepcionado', %s, %s, %s)""",
            (art, pid, cajones, cajones * 10, sena, procesada, cajones))

    # EL CASO: la foto quedó en 798 = 9 + 279 + 510, contado a mano.
    frutamax = proveedor("EJEMPLO Frutamax", "N94P01", 9 + 279 + 510, conteo=9)
    compra(frutamax, 10, 500, "2026-09-24 10:00-03")      # pomelo, con seña
    compra(frutamax, 269, None, "2026-09-24 11:00-03")    # sin seña: NULL
    compra(frutamax, 300, None, "2026-09-25 09:00-03")    # sin seña
    compra(frutamax, 210, 0, "2026-09-25 10:00-03")       # sin seña: cero
    compra(frutamax, 7, 500, "2026-09-26 09:00-03")       # DESPUÉS de la foto, con seña
    compra(frutamax, 4, None, "2026-09-26 09:00-03")      # después y sin seña: no suma

    # Con una devolución antes de la foto: 5 + 6 con seña − 2 devueltos = 9.
    devuelve = proveedor("EJEMPLO Devuelve", "N94P02", 5 + 6 + 20 - 2, conteo=5)
    compra(devuelve, 6, 300, "2026-09-24 12:00-03")
    compra(devuelve, 20, None, "2026-09-24 12:00-03")
    sql("INSERT INTO vacios_deposito_devoluciones (proveedor_id, cantidad, stock_sistema, creado_en, foto_ruta) "
        "VALUES (%s, 2, 0, '2026-09-25 12:00-03', 'x.jpg')", (devuelve,))

    # Sin conteo la foto fue 0, y sigue en 0 aunque haya cajones con seña.
    sin_conteo = proveedor("EJEMPLO Sin Conteo", "N94P03", 0)
    compra(sin_conteo, 8, 500, "2026-09-24 12:00-03")

    def foto(pid):
        (cantidad,), = sql("SELECT cantidad FROM vacios_deposito_foto WHERE proveedor_id = %s", (pid,))
        return cantidad

    return d, sql, proveedor, compra, foto, {"frutamax": frutamax, "devuelve": devuelve,
                                             "sin_conteo": sin_conteo}


def _revision(sql):
    columnas = ("que", "proveedor", "conteo_el", "contado", "con_sena", "sin_sena", "devueltos",
                "foto_actual", "control", "foto_nueva", "baja")
    return {f[1]: dict(zip(columnas, f)) for f in sql(_leer("vacios_foto_3_revisar_con_sena.sql"))
            if f[1].startswith("EJEMPLO")}


def test_la_REVISION_reproduce_la_foto_vieja_y_da_la_nueva(base):
    _, sql, _, _, _, _ = base
    filas = _revision(sql)
    f = filas["EJEMPLO Frutamax"]
    # El control rehace la foto vieja con TODOS los cajones: 798, igual al actual.
    assert (f["foto_actual"], f["control"]) == (798, 798)
    assert (f["contado"], f["con_sena"], f["sin_sena"]) == (9, 10, 779)
    assert (f["foto_nueva"], f["baja"]) == (19, 779)
    d = filas["EJEMPLO Devuelve"]
    assert (d["control"], d["foto_nueva"]) == (d["foto_actual"], 9)
    s = filas["EJEMPLO Sin Conteo"]
    assert (s["foto_actual"], s["foto_nueva"]) == (0, 0)


def test_la_MIGRACION_deja_19_la_verificacion_da_cero_y_se_puede_repetir(base):
    d, sql, _, _, foto, ids = base
    bloque = _leer("vacios_foto_4_corregir_con_sena.sql")

    antes, = sql(_leer("vacios_foto_5_verificacion.sql"))
    assert antes[1] >= 2                       # canario: antes de corregir, hay fuera de la regla

    sql(bloque)
    assert (foto(ids["frutamax"]), foto(ids["devuelve"]), foto(ids["sin_conteo"])) == (19, 9, 0)
    sql(bloque)                                # la segunda no cambia nada
    assert foto(ids["frutamax"]) == 19

    despues, = sql(_leer("vacios_foto_5_verificacion.sql"))
    assert despues[0] == "vacios_foto_4_corregir_con_sena"
    assert despues[1] == 0

    # Y el stock de la pantalla: 19 de la foto + 7 con seña después. Los 4 sin
    # seña de después no suman, porque la cuenta ya filtraba.
    proveedor, = [p for p in d.stock_de_vacios_deposito() if p["id"] == ids["frutamax"]]
    assert proveedor["stock"] == 26


def test_una_foto_que_no_sale_de_NINGUNA_regla_aborta_sin_escribir(base):
    _, sql, proveedor, compra, foto, ids = base
    raro = proveedor("EJEMPLO Raro", "N94P09", 50, conteo=3)
    compra(raro, 10, 500, "2026-09-24 12:00-03")      # vieja 13, nueva 13: 50 no sale de ninguna

    with pytest.raises(Exception, match="no salen ni de la regla vieja ni de la nueva"):
        sql(_leer("vacios_foto_4_corregir_con_sena.sql"))
    # El do es una sola sentencia: no quedó nada escrito, tampoco en los que sí cerraban.
    assert (foto(ids["frutamax"]), foto(raro)) == (798, 50)


def test_los_bloques_entran_en_el_editor_y_el_codigo_va_arriba():
    for nombre in ("vacios_foto_3_revisar_con_sena.sql", "vacios_foto_4_corregir_con_sena.sql",
                   "vacios_foto_5_verificacion.sql"):
        texto = _leer(nombre)
        assert len(texto) <= 2500, nombre
        assert not texto.lstrip().startswith("--"), nombre
        assert "temp" not in texto.lower().split("--")[0], nombre
