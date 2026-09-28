"""El arranque de Vacíos del depósito desde el conteo físico del 28/09 (dueño).

Corren los seis .sql tal cual contra Postgres con el esquema real (corolario
89), en el orden en que los va a correr el dueño, y después la cuenta de la
APLICACIÓN (`stock_de_vacios_deposito`), que es lo que va a mostrar la
pantalla. La verificación no se contrasta contra sí misma: los números que se
esperan están escritos a mano acá, sacados de la tabla del dueño.

La base imita a Frutamax: FRUTAMAX S.R.L. con N09P39 de alternativo, los
proveedores del conteo con sus nombres como podrían estar cargados, y
HISTORIA de todo tipo antes del arranque —foto, recepciones con seña,
devoluciones, ajustes, asignaciones— que no puede mover el número.
"""
import io
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.matcheo_comanda import normalizar_texto  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
BLOQUES = ("vacios_conteo_2809_1_tablas.sql", "vacios_conteo_2809_2_datos.sql",
           "vacios_conteo_2809_3_buscadores.sql", "vacios_conteo_2809_4_revisar.sql",
           "vacios_conteo_2809_5_cargar.sql", "vacios_conteo_2809_6_verificacion.sql")

# LA TABLA DEL DUEÑO, copiada del pedido (28/09). Es el número que se espera,
# y por eso NO se lee de la función de datos del .sql: si las dos copias se
# separan, el test cae.
TABLA = [
    ("RIO URUGUAY", "Goloso", 493), ("Herederos N7", "La Unión", 154),
    ("Herederos N7", "Don Quijote", 30), ("Herederos N7", "Fortaleza", 12),
    ("Herederos N7", "Don Ibáñez", 3), ("Saturno", "Babilonia", 91),
    ("Patagonia Market", "Patagonia", 83), ("Roncaglia Alcides J.", "El Pato", 50),
    ("MRC", "Soto", 64), ("Sin Proveedor", "La Valentina", 35),
    ("Abra Chica", "Abra Chica", 24), ("Frutas J. Robol", "Canasto Negro", 24),
    ("FRUTAMAX S.R.L.", "Lisandro", 11), ("FRUTAMAX S.R.L.", "Tom Jug", 1),
    ("Deliverduras", "Crefu", 7), ("Kaizer", "1039", 3),
    ("Productos SAN MARCOS", "Ulises", 1),
]

# Cómo están cargados en la base de prueba. Algunos con otra forma a
# propósito: mayúsculas, puntos, y "KAIZER S.A." que solo CONTIENE el nombre.
# "FRUTAS J.ROBOL" es como está en Frutamax: el punto pegado, sin espacio.
# Con "FRUTAS J. ROBOL" el test pasaba y el bloque 4 real no lo encontraba.
CARGADOS = {
    "RIO URUGUAY": "RIO URUGUAY", "Herederos N7": "herederos n7", "Saturno": "SATURNO",
    "Patagonia Market": "PATAGONIA MARKET", "Roncaglia Alcides J.": "RONCAGLIA ALCIDES J",
    "MRC": "MRC", "Abra Chica": "ABRA CHICA", "Frutas J. Robol": "FRUTAS J.ROBOL",
    "FRUTAMAX S.R.L.": "FRUTAMAX S.R.L.", "Deliverduras": "DELIVERDURAS",
    "Kaizer": "KAIZER S.A.", "Productos SAN MARCOS": "PRODUCTOS SAN MARCOS",
}
ANTES = "2026-09-26 10:00-03"


def _leer(nombre):
    return io.open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: el arranque no se verificó")
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

    (art,), = sql("INSERT INTO articulos (nombre) VALUES ('EJEMPLO Fruta Arranque') RETURNING id")
    ids = {}
    for n, (clave, nombre) in enumerate(CARGADOS.items()):
        (ids[clave],), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) "
                             "RETURNING id", (nombre, f"N8{n // 10}P{n % 10:02d}"))
    # Un RIVAL de MRC que lo contiene: con el exacto presente, gana el exacto.
    sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES ('MRC FRUTAS', 'N79P01')")
    sql("INSERT INTO proveedores_codigos (proveedor_id, codigo) VALUES (%s, 'N09P39')",
        (ids["FRUTAMAX S.R.L."],))
    # Los que NO están en el conteo y hoy tienen cajones: van a cero.
    for nombre, codigo in (("INGUCA N5", "N79P02"), ("DIMIMAX", "N79P03")):
        (ids[nombre],), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) "
                              "RETURNING id", (nombre, codigo))

    def marca(prov, nombre):
        (mid,), = sql("INSERT INTO marcas_vacio (proveedor_id, nombre, nombre_normalizado) "
                      "VALUES (%s, %s, %s) RETURNING id", (ids[prov], nombre, normalizar_texto(nombre)))
        return mid

    marcas = {"la union": marca("Herederos N7", "La union"),
              "tomjug": marca("FRUTAMAX S.R.L.", "Tomjug"),
              "vieja": marca("Herederos N7", "Marca Vieja")}

    def compra(prov, cajones, procesada, marca_id=None, sena=500):
        sql("""INSERT INTO compras (fecha_operacion, articulo_id, proveedor_id, importe,
                   cantidad_cajones, contenido_por_cajon, cantidad_kilos, estado, sena,
                   procesada_el, cantidad_cajones_real, marca_vacio_id)
               VALUES ('2026-09-26', %s, %s, 1000, %s, 10, %s, 'recepcionado', %s, %s, %s, %s)""",
            (art, ids[prov], cajones, cajones * 10, sena, procesada, cajones, marca_id))

    # LA HISTORIA de antes del arranque, de todo tipo.
    sql("INSERT INTO vacios_deposito_foto (proveedor_id, cantidad, fecha, creado_en) "
        "VALUES (%s, 700, '2026-09-25', '2026-09-25 18:00-03')", (ids["RIO URUGUAY"],))
    sql("INSERT INTO vacios_deposito_foto (proveedor_id, cantidad, fecha, creado_en) "
        "VALUES (%s, 40, '2026-09-25', '2026-09-25 18:00-03')", (ids["INGUCA N5"],))
    compra("RIO URUGUAY", 25, ANTES)
    compra("Herederos N7", 60, ANTES, marcas["la union"])
    compra("DIMIMAX", 9, ANTES)
    sql("INSERT INTO vacios_deposito_devoluciones (proveedor_id, cantidad, stock_sistema, creado_en, "
        "foto_ruta) VALUES (%s, 30, 0, %s, 'x.jpg') RETURNING id", (ids["RIO URUGUAY"], ANTES))
    sql("INSERT INTO vacios_deposito_ajustes (proveedor_id, marca_vacio_id, cantidad, motivo, "
        "stock_sistema, creado_en) VALUES (%s, %s, 5, 'viejo', 0, %s)",
        (ids["Herederos N7"], marcas["vieja"], ANTES))
    sql("INSERT INTO vacios_deposito_asignaciones (proveedor_id, marca_desde_id, marca_hasta_id, "
        "cantidad, stock_sistema, creado_en) VALUES (%s, NULL, %s, 20, 0, %s)",
        (ids["Herederos N7"], marcas["vieja"], ANTES))

    def correr(hasta):
        salida = None
        for nombre in BLOQUES[:hasta]:
            salida = sql(_leer(nombre))
        return salida

    return d, sql, ids, marcas, compra, correr


def _stock_por_pila(d):
    return {(p["nombre"], pila["marca"]): pila["stock"]
            for p in d.stock_de_vacios_deposito() for pila in p["pilas"] if pila["stock"]}


def _esperado(ids_nombre):
    esperado = {}
    for prov, marca, cant in TABLA:
        nombre = ids_nombre.get(prov, prov)
        clave = (nombre, "La union" if marca == "La Unión" else marca)
        esperado[clave] = esperado.get(clave, 0) + cant
    return esperado


def test_la_REVISION_muestra_hoy_y_como_queda_sin_escribir_nada(base):
    d, sql, ids, marcas, _, correr = base
    antes = _stock_por_pila(d)
    filas = correr(4)
    assert _stock_por_pila(d) == antes                      # solo lee
    columnas = ("que", "proveedor", "marca", "stock_hoy", "queda", "que_pasa")
    por_pila = {(f[1], f[2]): dict(zip(columnas, f)) for f in filas}
    assert filas[0][0] == "vacios_conteo_2809_4_revisar"
    # Las 17 del conteo, en su orden, y cada una con su cantidad.
    assert [f[4] for f in filas[:17]] == [c for _, _, c in TABLA]
    assert por_pila[("RIO URUGUAY", "Goloso")]["que_pasa"] == "marca nueva"
    assert por_pila[("herederos n7", "La Unión")]["que_pasa"] == 'reusa "La union"'
    assert por_pila[("FRUTAMAX S.R.L.", "Tom Jug")]["que_pasa"] == 'reusa "Tomjug"'
    assert por_pila[("KAIZER S.A.", "1039")]["queda"] == 3
    assert por_pila[("Sin Proveedor (nuevo)", "La Valentina")]["queda"] == 35
    # Lo que hoy tiene cajones y no está en el conteo: va a cero, con el
    # número de hoy al lado (la pantalla vieja: foto 700 + 25 − 30).
    assert por_pila[("RIO URUGUAY", "sin asignar")] == {
        "que": "vacios_conteo_2809_4_revisar", "proveedor": "RIO URUGUAY", "marca": "sin asignar",
        "stock_hoy": 695, "queda": 0, "que_pasa": "va a cero"}
    assert por_pila[("INGUCA N5", "sin asignar")]["stock_hoy"] == 40
    assert por_pila[("DIMIMAX", "sin asignar")]["stock_hoy"] == 9
    # El stock_hoy de la revisión es la cuenta de la pantalla: mismo total, y
    # las pilas de Herederos con los números de la historia.
    assert sum(f[3] for f in filas) == sum(antes.values())
    assert por_pila[("herederos n7", "La Unión")]["stock_hoy"] == 60
    assert por_pila[("herederos n7", "Marca Vieja")]["stock_hoy"] == 25
    assert por_pila[("herederos n7", "sin asignar")]["stock_hoy"] == -20


def test_la_CARGA_deja_la_tabla_del_duenio_y_nada_mas(base):
    d, sql, ids, marcas, _, correr = base
    correr(5)
    stock = _stock_por_pila(d)
    nombres = {k: v for k, v in CARGADOS.items()}
    assert stock == _esperado(nombres)
    assert sum(stock.values()) == 1086
    # Los que no están en el conteo desaparecen de la pantalla: cero y sin movimiento después.
    assert not [p for p in d.stock_de_vacios_deposito() if p["id"] in (ids["INGUCA N5"], ids["DIMIMAX"])]
    # "La union" se reusó con su nombre; "Tomjug" pasó a "Tom Jug", el mismo id.
    assert sql("SELECT nombre FROM marcas_vacio WHERE id = %s", (marcas["la union"],)) == [("La union",)]
    assert sql("SELECT nombre, nombre_normalizado FROM marcas_vacio WHERE id = %s",
               (marcas["tomjug"],)) == [("Tom Jug", "tom jug")]
    # Sin Proveedor nació con el código que no choca con ningún puesto real.
    assert sql("SELECT codigo_puesto, activo FROM proveedores WHERE nombre = 'Sin Proveedor'") == [
        ("N00P00", True)]
    # Las marcas nuevas quedan plegadas como las pliega Python al recibir.
    for (nombre, plegado) in sql("SELECT nombre, nombre_normalizado FROM marcas_vacio"):
        assert plegado == normalizar_texto(nombre), nombre


def test_la_VERIFICACION_da_la_fila_buena_y_ANTES_de_cargar_no(base):
    _, sql, _, _, _, correr = base
    correr(4)
    antes, = sql(_leer(BLOQUES[5]))
    assert antes[:7] == ("vacios_conteo_2809_5_cargar", 0, 0, 0, 0, 0, None)   # canario
    sql(_leer(BLOQUES[4]))
    fila, = sql(_leer(BLOQUES[5]))
    assert fila[:7] == ("vacios_conteo_2809_5_cargar", 1, 17, 1086, 17, 1, 1086)
    assert fila[7] is not None and fila[8] is not None


def test_una_SEGUNDA_corrida_no_cambia_nada(base):
    d, sql, _, _, _, correr = base
    correr(5)
    antes = (_stock_por_pila(d), sql("SELECT count(*) FROM marcas_vacio"),
             sql("SELECT count(*) FROM proveedores"), sql("SELECT count(*) FROM vacios_deposito_arranque_pilas"))
    correr(5)
    assert (_stock_por_pila(d), sql("SELECT count(*) FROM marcas_vacio"),
            sql("SELECT count(*) FROM proveedores"),
            sql("SELECT count(*) FROM vacios_deposito_arranque_pilas")) == antes


def test_lo_de_DESPUES_suma_y_lo_de_ANTES_no_se_puede_anular(base):
    d, sql, ids, marcas, compra, correr = base
    correr(5)
    # Una recepción con seña de un proveedor que NO estaba en el conteo, y
    # una de uno que sí: las dos suman.
    compra("DIMIMAX", 4, "2099-01-01 10:00-03")
    compra("Saturno", 6, "2099-01-01 10:00-03")
    stock = _stock_por_pila(d)
    assert stock[("DIMIMAX", None)] == 4
    assert stock[("SATURNO", "Babilonia")] == 91
    assert stock[("SATURNO", None)] == 6
    # Lo de antes queda como historia: el listado lo marca y anularlo rebota.
    dev, = d.listar_devoluciones_vacios(ids["RIO URUGUAY"])
    assert dev["antes_del_arranque"] is True
    with pytest.raises(ValueError, match="anterior al Conteo físico 28/09"):
        d.anular_devolucion_vacios(dev["id"])
    movs = d.listar_ajustes_y_asignaciones_vacios(ids["Herederos N7"])
    assert movs and all(m["antes_del_arranque"] for m in movs)
    ajuste, = [m for m in movs if m["tipo"] == "ajuste"]
    with pytest.raises(ValueError, match="anularlo no cambiaría nada"):
        d.anular_ajuste_vacios_deposito(ajuste["id"])
    # Uno de DESPUÉS sí se anula, y el stock vuelve.
    nuevo = d.crear_ajuste_vacios_deposito(ids["MRC"], None, 2, "apareció uno")
    assert _stock_por_pila(d)[("MRC", None)] == 2
    d.anular_ajuste_vacios_deposito(nuevo)
    assert ("MRC", None) not in _stock_por_pila(d)


def test_en_PALMALA_no_hace_nada(base):
    d, sql, _, _, _, correr = base
    sql("DELETE FROM proveedores_codigos WHERE codigo = 'N09P39'")
    antes = _stock_por_pila(d)
    correr(5)
    assert _stock_por_pila(d) == antes
    assert sql("SELECT count(*) FROM vacios_deposito_arranques") == [(0,)]
    assert sql("SELECT count(*) FROM proveedores WHERE codigo_puesto = 'N00P00'") == [(0,)]
    fila, = sql(_leer(BLOQUES[5]))
    assert fila[1:7] == (0, 0, 0, 0, 0, None)


def test_un_proveedor_que_NO_se_encuentra_aborta_sin_escribir(base):
    _, sql, ids, _, _, correr = base
    sql("UPDATE proveedores SET nombre = 'ALGO QUE NO ES' WHERE id = %s", (ids["Saturno"],))
    correr(3)
    with pytest.raises(Exception, match='proveedor "saturno": 0 con ese nombre'):
        sql(_leer(BLOQUES[4]))
    # El do es una sola sentencia: no quedó ni el arranque, ni Sin Proveedor, ni marcas nuevas.
    assert sql("SELECT count(*) FROM vacios_deposito_arranques") == [(0,)]
    assert sql("SELECT count(*) FROM proveedores WHERE codigo_puesto = 'N00P00'") == [(0,)]
    assert sql("SELECT count(*) FROM marcas_vacio WHERE nombre = 'Goloso'") == [(0,)]


def test_DOS_que_lo_contienen_y_ninguno_igual_aborta(base):
    _, sql, ids, _, _, correr = base
    sql("UPDATE proveedores SET nombre = 'KAIZER HNOS' WHERE id = %s", (ids["MRC"],))
    sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES ('MRC SRL', 'N79P09')")
    correr(3)
    # MRC ya no está igual, y "MRC FRUTAS" y "MRC SRL" lo contienen: ¿cuál?
    with pytest.raises(Exception, match='proveedor "mrc": 0 con ese nombre y 2'):
        sql(_leer(BLOQUES[4]))


def test_la_TABLA_del_duenio_y_la_funcion_de_datos_son_la_MISMA(base):
    """Lo escrito en el .sql contra lo copiado del pedido, fila por fila."""
    _, sql, ids, _, _, correr = base
    correr(3)
    filas = sql("SELECT pn, marca, cant FROM vacios_conteo_2809() ORDER BY orden")
    assert [(m, c) for _, m, c in filas] == [(m, c) for _, m, c in TABLA]
    # El nombre del .sql lo resuelve el MISMO buscador de la carga contra el
    # proveedor TAL COMO ESTÁ CARGADO. Antes se comparaba contra el rótulo del
    # pedido plegado ("Frutas J. Robol" -> "frutas j robol"), y eso pasaba con
    # un nombre que en Frutamax ("FRUTAS J.ROBOL") no se encuentra.
    for (pn, _, _), (prov, _, _) in zip(filas, TABLA):
        if prov == "Sin Proveedor":
            continue
        (encontrado, _, _), = sql("SELECT * FROM vacios_conteo_2809_proveedor(%s)", (pn,))
        assert encontrado == ids[prov], (prov, pn)
    assert sum(c for _, _, c in TABLA) == 1086


def test_el_buscador_de_la_carga_pliega_IGUAL_que_el_del_test():
    """El plegado del test de arriba es una copia: ésta la ata al .sql."""
    texto = _leer(BLOQUES[2])
    assert ("btrim(regexp_replace(replace(translate(lower(nombre), 'áéíóúüñ', 'aeiouun'),\n"
            "             '.', ''), '[^a-z0-9]+', ' ', 'g'))") in texto


def test_los_bloques_entran_en_el_editor_y_el_codigo_va_arriba():
    for nombre in BLOQUES:
        texto = _leer(nombre)
        assert len(texto) <= 2500, (nombre, len(texto))
        assert not texto.lstrip().startswith("--"), nombre
        assert "temp" not in texto.lower().split("\n-- ")[0], nombre
    # La verificación va APARTE del do: ningún bloque con un do trae un select final.
    carga = _leer(BLOQUES[4])
    assert carga.lstrip().startswith("do $$")
    assert "select 'vacios" not in carga


def test_la_pantalla_sabe_de_que_conteo_arranca(base):
    d, _, _, _, _, correr = base
    assert d.arranque_de_vacios() is None
    correr(5)
    arranque = d.arranque_de_vacios()
    assert (arranque["motivo"], arranque["total"]) == ("Conteo físico 28/09", 1086)


def test_JUNTAR_dos_proveedores_lleva_lo_contado_y_el_total_no_se_mueve(base):
    """Sin mover la tabla del arranque, el DELETE del proveedor rebota por la FK."""
    d, sql, ids, _, _, correr = base
    correr(5)
    antes = sum(_stock_por_pila(d).values())
    d.juntar_proveedores(ids["Saturno"], ids["Kaizer"])
    stock = _stock_por_pila(d)
    assert sum(stock.values()) == antes == 1086
    assert stock[("SATURNO", "1039")] == 3 and stock[("SATURNO", "Babilonia")] == 91


def test_JUNTAR_dos_marcas_suma_lo_contado_de_las_dos(base):
    d, sql, ids, _, _, correr = base
    correr(5)
    (quijote,), = sql("SELECT id FROM marcas_vacio WHERE nombre = 'Don Quijote'")
    (fortaleza,), = sql("SELECT id FROM marcas_vacio WHERE nombre = 'Fortaleza'")
    d.juntar_marcas_vacio(ids["Herederos N7"], fortaleza, quijote)
    stock = _stock_por_pila(d)
    assert stock[("herederos n7", "Don Quijote")] == 42
    assert sum(stock.values()) == 1086
