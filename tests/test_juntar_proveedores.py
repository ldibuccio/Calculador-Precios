"""Juntar dos proveedores desde Gerencia (dueño, 27/09).

Es la fusión que se hizo dos veces a mano —FRUTAMAX con db/codigos_3-4 y DON
LAZZARO con db/lazzaro_1-2—, escrita una vez en `app/db.py` para que el tercer
par no necesite una migración.

Los de Postgres corren contra `db/esquema_completo.sql`: el trigger de los
códigos, las FK compuestas de las marcas y el DELETE que rebota por una FK solo
existen ahí (corolario 89). Los de la pantalla parchean la base y miran qué se
ofrece.
"""
import contextlib
import io
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app.main import app  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


# ------------------------------------------------------------- contra la base


@pytest.fixture(scope="module")
def base_real():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def galpon(base_real, monkeypatch):
    """DOS proveedores que son el mismo, con algo de todo en el que se va.

    Los códigos salen de una secuencia para no chocar entre tests: la base es
    una sola para todo el módulo.
    """
    monkeypatch.setenv("DATABASE_URL", base_real)
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

    (n,), = sql("SELECT nextval(pg_get_serial_sequence('articulos','id'))")
    codigo = lambda k: f"L{(4 * n + k) % 100:02d}P{(4 * n + k) // 100 % 100:02d}"  # noqa: E731
    (articulo,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id", (f"EJEMPLO Art {n}",))
    (otro_articulo,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id", (f"EJEMPLO Otro {n}",))
    (queda,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) RETURNING id",
                    (f"EJEMPLO Queda {n}", codigo(0)))
    (va,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) RETURNING id",
                 (f"EJEMPLO Va {n}", codigo(1)))
    sql("INSERT INTO proveedores_codigos (proveedor_id, codigo) VALUES (%s, %s)", (va, codigo(2)))
    return {"d": d, "sql": sql, "n": n, "articulo": articulo, "otro_articulo": otro_articulo,
            "queda": queda, "va": va, "codigo_queda": codigo(0), "codigo_va": codigo(1),
            "alternativo_va": codigo(2)}


def _compra(g, proveedor, dia, codigo):
    g["d"].crear_compra(dia, g["articulo"], proveedor, 10, 16, 160, None,
                        1000, None, "Clark", None, segunda_por_cajon=None, codigo_llegada=codigo)
    (compra_id,), = g["sql"]("SELECT max(id) FROM compras")
    return compra_id


def _marca(g, proveedor, nombre):
    (marca,), = g["sql"](
        "INSERT INTO marcas_vacio (proveedor_id, nombre, nombre_normalizado) VALUES (%s, %s, %s) RETURNING id",
        (proveedor, nombre, nombre.lower()),
    )
    return marca


def _cuenta(g, tabla, columna, proveedor):
    (n,), = g["sql"](f"SELECT count(*) FROM {tabla} WHERE {columna} = %s", (proveedor,))
    return n


def _sembrar_todo_en_el_que_se_va(g):
    """Una fila en CADA tabla que apunta al proveedor, así un UPDATE que falte
    hace rebotar el DELETE y el test lo ve (sin la fila, el canario da cero)."""
    compra = _compra(g, g["va"], date(2026, 8, 12), g["codigo_va"])
    marca = _marca(g, g["va"], f"Roja {g['n']}")
    g["sql"]("UPDATE compras SET marca_vacio_id = %s WHERE id = %s", (marca, compra))
    g["sql"]("INSERT INTO conteos_vacios_deposito (proveedor_id, cantidad, fecha, stock_sistema, marca_vacio_id)"
             " VALUES (%s, 5, %s, 5, %s)", (g["va"], date(2026, 9, 26), marca))
    g["sql"]("INSERT INTO vacios_deposito_asignaciones (proveedor_id, marca_desde_id, marca_hasta_id,"
             " cantidad, stock_sistema) VALUES (%s, NULL, %s, 3, 0)", (g["va"], marca))
    g["sql"]("INSERT INTO vacios_deposito_ajustes (proveedor_id, marca_vacio_id, cantidad, motivo, stock_sistema)"
             " VALUES (%s, %s, 2, 'EJEMPLO sobraron', 0)", (g["va"], marca))
    g["sql"]("INSERT INTO vacios_deposito_devoluciones (proveedor_id, marca_vacio_id, cantidad, foto_ruta,"
             " stock_sistema) VALUES (%s, %s, 1, '2026-09-26/vale.jpg', 5)", (g["va"], marca))
    g["sql"]("INSERT INTO vacios_deposito_foto (proveedor_id, cantidad, fecha) VALUES (%s, 40, %s)",
             (g["va"], date(2026, 9, 25)))
    g["sql"]("INSERT INTO vales_a_cobrar (origen, proveedor_id, fecha, importe) "
             "VALUES ('anterior_al_sistema', %s, %s, 1000)", (g["va"], date(2026, 8, 1)))
    g["sql"]("INSERT INTO movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema,"
             " destino_rechazo, proveedor_devolucion_id) VALUES (%s, 'reingreso_rechazo', 1, 'EJEMPLO',"
             " %s, 0, 'devolucion_proveedor', %s)", (g["articulo"], date(2026, 9, 20), g["va"]))
    # Aprendizaje: uno propio y uno REPETIDO, que en el que queda apunta a otro artículo.
    g["sql"]("INSERT INTO aprendizaje_articulos (proveedor_id, texto_leido, articulo_id) VALUES (%s, 'solo del va', %s)",
             (g["va"], g["articulo"]))
    g["sql"]("INSERT INTO aprendizaje_articulos (proveedor_id, texto_leido, articulo_id) VALUES (%s, 'limon', %s)",
             (g["va"], g["articulo"]))
    g["sql"]("INSERT INTO aprendizaje_articulos (proveedor_id, texto_leido, articulo_id) VALUES (%s, 'limon', %s)",
             (g["queda"], g["otro_articulo"]))
    return compra, marca


def test_juntar_pasa_TODO_al_que_queda_y_borra_el_que_se_va(galpon):
    g = galpon
    compra_queda = _compra(g, g["queda"], date(2026, 8, 13), g["codigo_queda"])
    compra_va, marca = _sembrar_todo_en_el_que_se_va(g)

    resumen = g["d"].juntar_proveedores(g["queda"], g["va"])

    assert resumen["mueve"]["compras"] == 1
    assert resumen["mueve"]["aprendizaje"] == 1 and resumen["mueve"]["aprendizaje_repetido"] == 1
    assert g["sql"]("SELECT count(*) FROM proveedores WHERE id = %s", (g["va"],)) == [(0,)]
    for tabla, columna in sorted(g["d"].TABLAS_QUE_APUNTAN_A_PROVEEDORES):
        assert _cuenta(g, tabla, columna, g["va"]) == 0, f"{tabla}.{columna} quedó apuntando al que se va"
    # Las dos compras son del que queda, y cada una sigue diciendo por qué puesto llegó.
    filas = g["sql"]("SELECT id, proveedor_id, codigo_llegada FROM compras WHERE id IN (%s, %s) ORDER BY id",
                     (compra_queda, compra_va))
    assert filas == sorted([(compra_queda, g["queda"], g["codigo_queda"]),
                            (compra_va, g["queda"], g["codigo_va"])])
    # La marca conserva su id, y lo que la nombra también se movió.
    assert g["sql"]("SELECT proveedor_id FROM marcas_vacio WHERE id = %s", (marca,)) == [(g["queda"],)]
    assert g["sql"]("SELECT marca_vacio_id FROM compras WHERE id = %s", (compra_va,)) == [(marca,)]
    # Los dos códigos del que se va, el principal y el alternativo, pasan a alternativos.
    codigos = g["sql"]("SELECT codigo FROM proveedores_codigos WHERE proveedor_id = %s ORDER BY codigo", (g["queda"],))
    assert [c for (c,) in codigos] == sorted([g["codigo_va"], g["alternativo_va"]])
    # Del aprendizaje repetido queda el del que se queda, y la foto se movió entera.
    assert g["sql"]("SELECT articulo_id FROM aprendizaje_articulos WHERE proveedor_id = %s AND texto_leido = 'limon'",
                    (g["queda"],)) == [(g["otro_articulo"],)]
    assert g["sql"]("SELECT cantidad FROM vacios_deposito_foto WHERE proveedor_id = %s", (g["queda"],)) == [(40,)]
    # El nombre del que queda no se toca.
    assert g["sql"]("SELECT nombre FROM proveedores WHERE id = %s", (g["queda"],)) == [(f"EJEMPLO Queda {g['n']}",)]


def test_una_compra_por_el_codigo_del_que_se_fue_va_al_que_queda(galpon):
    """Lo que se compra: que el puesto 44 siga cargando bien después."""
    g = galpon
    g["d"].juntar_proveedores(g["queda"], g["va"])
    proveedor_id, _ = g["d"].obtener_o_crear_proveedor_por_codigo(g["codigo_va"], "EJEMPLO Remito")
    assert proveedor_id == g["queda"]


def test_guias_del_MISMO_DIA_frenan_y_no_se_escribe_NADA(galpon):
    g = galpon
    _compra(g, g["queda"], date(2026, 8, 12), g["codigo_queda"])
    compra_va = _compra(g, g["va"], date(2026, 8, 12), g["codigo_va"])

    with pytest.raises(ValueError, match="mismo día: 12/08/2026"):
        g["d"].juntar_proveedores(g["queda"], g["va"])
    assert g["sql"]("SELECT proveedor_id FROM compras WHERE id = %s", (compra_va,)) == [(g["va"],)]
    assert g["sql"]("SELECT count(*) FROM proveedores WHERE id = %s", (g["va"],)) == [(1,)]


def test_la_guia_del_ingreso_directo_NO_cruza_con_la_de_compras_del_mismo_dia(galpon):
    """El control del cruce: son dos guías distintas por día (de_deposito)."""
    g = galpon
    _compra(g, g["queda"], date(2026, 8, 12), g["codigo_queda"])
    compra_va = _compra(g, g["va"], date(2026, 8, 12), g["codigo_va"])
    g["sql"]("UPDATE guias_compra SET de_deposito = true WHERE id = (SELECT guia_id FROM compras WHERE id = %s)",
             (compra_va,))
    g["d"].juntar_proveedores(g["queda"], g["va"])
    assert g["sql"]("SELECT proveedor_id FROM compras WHERE id = %s", (compra_va,)) == [(g["queda"],)]


def test_una_MARCA_con_el_mismo_nombre_en_los_dos_frena(galpon):
    g = galpon
    _marca(g, g["queda"], "Azul")
    _marca(g, g["va"], "Azul")
    with pytest.raises(ValueError, match="mismo nombre: Azul"):
        g["d"].juntar_proveedores(g["queda"], g["va"])


def test_FOTOS_DE_VACIOS_con_cajones_en_los_dos_frenan_y_en_cero_no(galpon):
    g = galpon
    g["sql"]("INSERT INTO vacios_deposito_foto (proveedor_id, cantidad, fecha) VALUES (%s, 10, %s), (%s, 7, %s)",
             (g["queda"], date(2026, 9, 25), g["va"], date(2026, 9, 25)))
    with pytest.raises(ValueError, match="foto de vacíos"):
        g["d"].juntar_proveedores(g["queda"], g["va"])

    # Con la del que se va en cero no hay nada que sumar: se descarta.
    g["sql"]("UPDATE vacios_deposito_foto SET cantidad = 0 WHERE proveedor_id = %s", (g["va"],))
    g["d"].juntar_proveedores(g["queda"], g["va"])
    assert g["sql"]("SELECT cantidad FROM vacios_deposito_foto WHERE proveedor_id = %s", (g["queda"],)) == [(10,)]


def test_el_MISMO_proveedor_dos_veces_no_se_junta(galpon):
    g = galpon
    with pytest.raises(ValueError, match="dos proveedores distintos"):
        g["d"].juntar_proveedores(g["queda"], g["queda"])


def test_si_algo_rebota_en_el_medio_NO_se_escribe_nada(galpon):
    """Todo o nada. Una tabla que nadie decidió cómo juntar hace rebotar el
    DELETE del final, y lo que ya se había movido vuelve atrás."""
    g = galpon
    compra_va = _compra(g, g["va"], date(2026, 8, 12), g["codigo_va"])
    g["sql"]("CREATE TABLE ejemplo_ajena (proveedor_id bigint REFERENCES proveedores (id))")
    try:
        g["sql"]("INSERT INTO ejemplo_ajena VALUES (%s)", (g["va"],))
        with pytest.raises(Exception, match="ejemplo_ajena"):
            g["d"].juntar_proveedores(g["queda"], g["va"])
        assert g["sql"]("SELECT proveedor_id FROM compras WHERE id = %s", (compra_va,)) == [(g["va"],)]
        assert g["sql"]("SELECT count(*) FROM proveedores_codigos WHERE proveedor_id = %s", (g["queda"],)) == [(0,)]
    finally:
        g["sql"]("DROP TABLE ejemplo_ajena")


def test_las_dos_tablas_VIEJAS_se_mueven_si_existen(galpon):
    """`recepciones` y `aprendizaje_proveedores` están solo en Frutamax, vacías,
    y no en el esquema del repo. Se crean acá desde db/schema.sql —leídas, no
    copiadas— para ejercitar esa rama."""
    g = galpon
    esquema = io.open(os.path.join(RAIZ, "db", "schema.sql"), encoding="utf-8").read()
    for tabla in g["d"].TABLAS_VIEJAS_QUE_APUNTAN_A_PROVEEDORES:
        g["sql"](re.search(rf"create table {tabla} \(.*?\);", esquema, re.S).group(0))
    try:
        g["sql"]("INSERT INTO recepciones (fecha_operacion, articulo_id, proveedor_id, cantidad_recibida)"
                 " VALUES (%s, %s, %s, 1)", (date(2026, 8, 1), g["articulo"], g["va"]))
        g["sql"]("INSERT INTO aprendizaje_proveedores (texto_leido, proveedor_id) VALUES (%s, %s)",
                 (f"EJEMPLO puesto {g['n']}", g["va"]))
        g["d"].juntar_proveedores(g["queda"], g["va"])
        assert _cuenta(g, "recepciones", "proveedor_id", g["queda"]) == 1
        assert _cuenta(g, "aprendizaje_proveedores", "proveedor_id", g["queda"]) == 1
    finally:
        for tabla in g["d"].TABLAS_VIEJAS_QUE_APUNTAN_A_PROVEEDORES:
            g["sql"](f"DROP TABLE IF EXISTS {tabla}")


def test_TODA_tabla_con_FK_a_proveedores_esta_DECIDIDA(galpon):
    """El conjunto ENCONTRADO en la base contra el DECIDIDO en el código
    (corolario 60). Falla cuando aparece una FK nueva que nadie decidió cómo
    juntar, y cuando una de la lista deja de existir."""
    g = galpon
    filas = g["sql"](
        """
        SELECT c.conrelid::regclass::text, a.attname
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
         WHERE c.contype = 'f' AND c.confrelid = 'proveedores'::regclass
        """
    )
    encontradas = set(filas)
    assert encontradas, "no encontró ninguna FK: la consulta no mira lo que dice"
    assert encontradas == g["d"].TABLAS_QUE_APUNTAN_A_PROVEEDORES


# ---------------------------------------------------------------- la pantalla

RESUMEN = {
    "queda": {"id": 10, "nombre": "EJEMPLO Queda", "codigo_puesto": "L02P42",
              "codigos_alternativos": [], "compras": 14},
    "va": {"id": 17, "nombre": "EJEMPLO Va", "codigo_puesto": "L02P44",
           "codigos_alternativos": [], "compras": 1},
    "mueve": {"compras": 1, "guias": 1, "marcas": 0, "vacios": 0, "devoluciones_al_proveedor": 0,
              "aprendizaje": 2, "aprendizaje_repetido": 0, "foto_vacios": None, "codigos": ["L02P44"]},
    "cruces": [],
}
PROVEEDORES = [
    {"id": 10, "codigo_puesto": "L02P42", "nombre": "EJEMPLO Queda", "activo": True, "compras": 14,
     "codigos_alternativos": []},
    {"id": 17, "codigo_puesto": "L02P44", "nombre": "EJEMPLO Va", "activo": True, "compras": 1,
     "codigos_alternativos": []},
]


@contextlib.contextmanager
def _gerencia(con_cookie=True):
    """La clave PUESTA: sin ella `PUERTA_GERENCIA` está abierta y el test de la
    puerta no prueba nada."""
    from app.main import _firma_acceso_gerencia

    with patch.dict(os.environ, {"CLAVE_GERENCIA": "secreta"}):
        c = TestClient(app, base_url="https://testserver")
        if con_cookie:
            c.cookies.set("acceso_gerencia", _firma_acceso_gerencia("secreta"))
        yield c


def _pantalla(query="", resumen=RESUMEN):
    with _gerencia() as c, \
         patch("app.main.listar_proveedores_para_abm", return_value=PROVEEDORES), \
         patch("app.main.resumen_para_juntar_proveedores", return_value=resumen) as consulta:
        respuesta = c.get("/gerencia/proveedores/juntar" + query)
    return respuesta, consulta


def test_juntar_PIDE_LA_CLAVE_de_gerencia():
    with _gerencia(con_cookie=False) as c, \
         patch("app.main.juntar_proveedores") as juntar:
        pantalla = c.get("/gerencia/proveedores/juntar")
        post = c.post("/gerencia/proveedores/juntar", data={"queda": "10", "va": "17"})
    assert "clave" in pantalla.text.lower() and "EJEMPLO" not in pantalla.text
    assert "clave" in post.text.lower()
    juntar.assert_not_called()


def test_sin_elegir_los_dos_no_hay_resumen_ni_boton():
    respuesta, consulta = _pantalla()
    assert respuesta.status_code == 200
    consulta.assert_not_called()
    assert 'class="boton-juntar"' not in respuesta.text
    assert respuesta.text.count('<option value="10"') == 2, "los dos selectores listan a todos"


def test_con_los_dos_elegidos_muestra_QUE_SE_MUEVE_y_el_boton():
    respuesta, consulta = _pantalla("?queda=10&va=17")
    assert consulta.call_args.args == (10, 17)
    marcado = respuesta.text.split('id="resumen"')[1]
    assert "Esto no se deshace." in marcado
    assert "Juntar, esto no se deshace" in marcado
    assert 'name="queda" value="10"' in marcado and 'name="va" value="17"' in marcado
    assert "Pasan a código alternativo: <strong>L02P44</strong>" in marcado


def test_con_un_CRUCE_lo_dice_y_NO_ofrece_el_boton():
    """El botón aparece solo donde la escritura acepta: ofrecer algo que el
    POST rechaza es un callejón."""
    con_cruce = {**RESUMEN, "cruces": ["EJEMPLO los dos tienen guía el mismo día: 12/08/2026."]}
    respuesta, _ = _pantalla("?queda=10&va=17", con_cruce)
    marcado = respuesta.text.split('id="resumen"')[1]
    assert 'class="cruce">EJEMPLO los dos tienen guía el mismo día' in marcado
    assert 'class="boton-juntar"' not in marcado
    assert 'method="post"' not in marcado


def test_el_mismo_dos_veces_lo_dice_con_400():
    with _gerencia() as c, \
         patch("app.main.listar_proveedores_para_abm", return_value=PROVEEDORES), \
         patch("app.main.resumen_para_juntar_proveedores", side_effect=ValueError("Elegí dos proveedores distintos.")):
        respuesta = c.get("/gerencia/proveedores/juntar?queda=10&va=10")
    assert respuesta.status_code == 400
    assert 'class="error">Elegí dos proveedores distintos.' in respuesta.text


def test_el_POST_junta_y_vuelve_con_el_aviso():
    with _gerencia() as c, \
         patch("app.main.juntar_proveedores", return_value=RESUMEN) as juntar:
        respuesta = c.post("/gerencia/proveedores/juntar", data={"queda": "10", "va": "17"},
                           follow_redirects=False)
    juntar.assert_called_once_with(10, 17)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/gerencia/proveedores/juntar?aviso=")
    assert "L02P44" in respuesta.headers["location"]


def test_el_POST_con_un_cruce_lo_muestra_y_no_redirige():
    """La guarda va donde se ESCRIBE: un POST armado a mano rebota igual."""
    with _gerencia() as c, \
         patch("app.main.listar_proveedores_para_abm", return_value=PROVEEDORES), \
         patch("app.main.juntar_proveedores", side_effect=ValueError("EJEMPLO cruce de marcas")):
        respuesta = c.post("/gerencia/proveedores/juntar", data={"queda": "10", "va": "17"},
                           follow_redirects=False)
    assert respuesta.status_code == 400
    assert 'class="error">EJEMPLO cruce de marcas' in respuesta.text


def test_la_pantalla_esta_en_el_hub_de_gerencia():
    with _gerencia() as c:
        respuesta = c.get("/gerencia")
    assert 'href="/gerencia/proveedores/juntar"' in respuesta.text
