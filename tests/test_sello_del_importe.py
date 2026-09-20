"""El par que dice CUÁNDO y POR DÓNDE entró el importe que una compra tiene hoy.

POR QUÉ EXISTE. `compras.importe` es un número solo: el día que un precio no
cierre contra lo que el proveedor dice, no hay con qué reconstruir si se cargó
al recibir la mercadería o si se renegoció una semana después. `cargado_el` no
sirve —es de la COMPRA, y una que nació sin precio y se completó tres días más
tarde lo lleva igual con la fecha del alta—.

LOS TRES CAMINOS, enumerados con `ast` y no de memoria:

    el ALTA       _insertar_compra_con_guia   INSERT   -> 'alta'
    la EDICIÓN    actualizar_precio_compra    UPDATE   -> 'edicion'
    el PENDIENTE  actualizar_importe_compra   UPDATE   -> 'pendiente'

QUÉ MIRA CADA MITAD DE ESTE ARCHIVO, y hacen falta las dos:

  · Los de ABAJO corren las tres funciones de verdad contra
    `db/esquema_completo.sql`. Son los únicos que pueden ver que el SQL
    PARSEA y que el CHECK de la base acepta lo que el código escribe — un
    assert de texto verifica la FORMA de una consulta, nunca su VALIDEZ
    contra el esquema (corolario 89).
  · Los ESTRUCTURALES de arriba miran lo que ninguna corrida puede ver: que
    un CUARTO escritor que aparezca mañana también selle. El que falta, por
    definición, no nombra la columna nueva — así que se enumera el conjunto
    ENCONTRADO y se lo compara contra el DECIDIDO (corolario 60), no contra
    una lista escrita a mano que solo confirma lo que ya sabíamos.
"""
import ast
import io
import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app.db import ORIGENES_DEL_IMPORTE, _sello_del_importe  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402


# Igual que el humo: sin Postgres se saltea, y con HUMO_OBLIGATORIO=1 —que el
# workflow pone— dejar de poder correrlo FALLA en vez de saltear. Un test
# salteado se lee exactamente igual que uno verde.
OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

ESCRITORES_DECIDIDOS = {
    "_insertar_compra_con_guia": "alta",
    "actualizar_precio_compra": "edicion",
    "actualizar_importe_compra": "pendiente",
}


# ---------------------------------------------------------------- estructura


def _funciones_que_escriben(columna):
    """Las funciones de app/db.py cuyo SQL ESCRIBE esa columna de `compras`.

    Lee los literales del árbol —f-strings incluidas, que es donde vive la
    mitad del SQL de este archivo— y pregunta por la POSICIÓN: un INSERT INTO
    compras o un UPDATE compras que nombre la columna. Buscar el nombre suelto
    matchearía el docstring que explica para qué está (corolario 59).
    """
    src = io.open(os.path.join(RAIZ, "app/db.py"), encoding="utf-8").read()
    escribe = re.compile(r"(insert\s+into\s+compras\b|update\s+compras\b)", re.I)
    encontradas = set()
    for nodo in ast.walk(ast.parse(src)):
        if not isinstance(nodo, ast.FunctionDef):
            continue
        for pedazo in ast.walk(nodo):
            texto = None
            if isinstance(pedazo, ast.Constant) and isinstance(pedazo.value, str):
                texto = pedazo.value
            elif isinstance(pedazo, ast.JoinedStr):
                texto = "".join(p.value for p in pedazo.values
                                if isinstance(p, ast.Constant) and isinstance(p.value, str))
            if texto and escribe.search(texto) and re.search(rf"\b{columna}\b", texto):
                encontradas.add(nodo.name)
                break
    return encontradas


def _funciones_que_llaman(nombre):
    """Las funciones de app/db.py que LLAMAN a esa función.

    Una llamada en posición de llamada, no el nombre adentro de una cadena: el
    docstring de una guarda SIEMPRE la nombra para explicar por qué está, así
    que preguntar por el texto la encuentra con la llamada sacada (corolario 59).
    """
    src = io.open(os.path.join(RAIZ, "app/db.py"), encoding="utf-8").read()
    encontradas = set()
    for nodo in ast.walk(ast.parse(src)):
        if not isinstance(nodo, ast.FunctionDef):
            continue
        for pedazo in ast.walk(nodo):
            if isinstance(pedazo, ast.Call) and isinstance(pedazo.func, ast.Name) and pedazo.func.id == nombre:
                encontradas.add(nodo.name)
                break
    return encontradas


def _veces_en_el_SQL(fragmento):
    """Cuántas veces aparece ese texto en los literales de app/db.py, SIN contar
    los docstrings — que es donde vive la explicación de por qué está."""
    src = io.open(os.path.join(RAIZ, "app/db.py"), encoding="utf-8").read()
    arbol = ast.parse(src)
    prosa = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(nodo, clean=False)
            if doc is not None:
                prosa.add(doc)
    veces = 0
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and nodo.value not in prosa:
            veces += nodo.value.count(fragmento)
    return veces


def test_TODO_el_que_escribe_compras_importe_SELLA_tambien_el_par():
    """El conjunto ENCONTRADO contra el DECIDIDO, y falla en las DOS direcciones.

    Un cuarto camino que escriba un importe y no lo selle deja una compra que
    dice tener precio y no dice de dónde salió — y eso no falla en ninguna
    pantalla: se ve igual que las 625 viejas, que tampoco lo tienen.
    """
    escriben_importe = _funciones_que_escriben("importe")
    assert escriben_importe == set(ESCRITORES_DECIDIDOS), (
        f"cambió quién escribe compras.importe: {escriben_importe}. "
        f"Si es un camino nuevo, tiene que sellar y entrar acá con su origen."
    )
    # Sella el que lo escribe en su propio SQL (el alta, que es una fila recién
    # insertada y no tiene un valor viejo contra el cual comparar) o el que usa
    # el helper compartido.
    sellan = _funciones_que_escriben("importe_origen") | _funciones_que_llaman("_sello_del_importe")
    assert escriben_importe <= sellan, f"escriben el importe y NO lo sellan: {escriben_importe - sellan}"


def test_el_CASE_del_sello_esta_escrito_UNA_sola_vez():
    """Lo que demuestra que la regla no está copiada no es que hoy coincidan: es
    que haya UN solo lugar donde esté escrita. Dos copias del `IS DISTINCT FROM`
    se separan sin fallar —una re-fecha un importe que no cambió y la otra no—,
    y eso no se ve en ninguna pantalla."""
    # SOBRE LOS LITERALES DE SQL Y NO SOBRE EL ARCHIVO: el docstring de
    # _sello_del_importe nombra el `IS NOT DISTINCT FROM` para explicar por qué
    # está, así que un `src.count(...)` cuenta la prosa junto con el código. Es
    # la colisión de siempre —un comentario explica algo, así que NOMBRA la
    # cosa que el test busca— y acá mordió adentro del test escrito contra ella.
    assert _veces_en_el_SQL("importe IS NOT DISTINCT FROM") == 2, (
        "las dos apariciones son los dos CASE del MISMO fragmento, adentro de "
        "_sello_del_importe. Una tercera es una copia."
    )
    de_su_propio_sql = _funciones_que_escriben("importe_origen")
    assert de_su_propio_sql == {"_insertar_compra_con_guia"}, (
        f"además del alta, {de_su_propio_sql - {'_insertar_compra_con_guia'}} arma el sello "
        f"por su cuenta en vez de pedírselo a _sello_del_importe."
    )


def test_la_lista_de_ORIGENES_y_la_del_CHECK_de_la_base_son_LA_MISMA_regla():
    """LEE el `.sql`, no lo copia: una lista copiada envejece en silencio.

    Se compara en los dos sentidos porque cada dirección falla distinto. Si el
    código tiene un origen que el CHECK no acepta, la escritura revienta el día
    que alguien use ese camino. Si el CHECK acepta uno que el código no escribe
    nunca, el que lea la base va a buscar filas que no existen.
    """
    esquema = io.open(os.path.join(RAIZ, "db/esquema_completo.sql"), encoding="utf-8").read()
    cuerpo = re.search(r"compras_importe_origen_check\s+check\s*\((.*?)\)\s*,", esquema, re.S)
    assert cuerpo, "no se encontró el CHECK de importe_origen en db/esquema_completo.sql"
    del_check = set(re.findall(r"'([a-z_]+)'", cuerpo.group(1)))

    assert del_check == set(ORIGENES_DEL_IMPORTE), (
        f"el CHECK dice {sorted(del_check)} y el código {sorted(ORIGENES_DEL_IMPORTE)}"
    )


def test_el_sello_RECHAZA_un_origen_que_el_CHECK_no_acepta():
    """La guarda va donde se ESCRIBE. Sin esto el valor llega hasta la base y
    revienta ahí, con un error de constraint que no dice de qué camino salió."""
    with pytest.raises(ValueError) as error:
        _sello_del_importe("inventado", 100.0)
    assert "inventado" in str(error.value)


def test_el_sello_solo_FECHA_si_el_numero_CAMBIO():
    """El `IS NOT DISTINCT FROM` no es prolijidad: es lo que hace que la columna
    signifique algo. Editar Compra llama a actualizar_precio_compra en CADA
    guardado, aunque lo único tocado sea la cantidad."""
    fragmento, parametros = _sello_del_importe("edicion", 500.0)
    assert "importe IS NOT DISTINCT FROM %s" in fragmento
    assert fragmento.count("%s") == len(parametros) == 4
    assert parametros == (500.0, 500.0, 500.0, 500.0)


# ------------------------------------------------------------ comportamiento


@pytest.fixture(scope="module")
def base_real():
    """Una base de verdad, cargada con el esquema REAL. Nunca un `create table`
    escrito para la ocasión: ése confirma que la consulta es consistente
    CONSIGO MISMA y no con la base."""
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def galpon(base_real, monkeypatch):
    """Un artículo y un proveedor nuevos por test, y DATABASE_URL restaurada al
    salir — la suite entera está mockeada y filtrársela sería dejar que
    cualquier otro test toque una base de verdad."""
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

    (sufijo,), = sql("SELECT nextval(pg_get_serial_sequence('articulos','id'))")
    (articulo,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id",
                       (f"EJEMPLO Art {sufijo}",))
    (proveedor,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) RETURNING id",
                        (f"EJEMPLO Prov {sufijo}", f"N01P{sufijo % 100:02d}"))
    return d, sql, articulo, proveedor


def _alta(galpon, importe):
    from datetime import date
    d, sql, articulo, proveedor = galpon
    d.crear_compra(date.today(), articulo, proveedor, 10, 16, 160, None,
                   importe, None, "Carro", None, segunda_por_cajon=None)
    (compra_id,), = sql("SELECT max(id) FROM compras")
    return compra_id


def _par(sql, compra_id):
    fila, = sql("SELECT importe_puesto_el, importe_origen, importe FROM compras WHERE id = %s",
                (compra_id,))
    return fila


def test_el_ALTA_con_precio_sella_alta(galpon):
    _, sql, _, _ = galpon
    puesto_el, origen, importe = _par(sql, _alta(galpon, 50000))
    assert origen == "alta"
    assert puesto_el is not None
    assert importe == 50000


def test_la_que_nace_SIN_PRECIO_deja_el_par_en_NULL(galpon):
    """Y no es un hueco a tapar: es la verdad. No hay importe que fechar, y ese
    par en NULL es el que Compras sin precio va a completar como 'pendiente'."""
    _, sql, _, _ = galpon
    puesto_el, origen, importe = _par(sql, _alta(galpon, None))
    assert (puesto_el, origen, importe) == (None, None, None)


def test_COMPRAS_SIN_PRECIO_sella_pendiente(galpon):
    d, sql, _, _ = galpon
    compra_id = _alta(galpon, None)
    d.actualizar_importe_compra(compra_id, 33000)
    puesto_el, origen, importe = _par(sql, compra_id)
    assert origen == "pendiente"
    assert puesto_el is not None
    assert importe == 33000


def test_editar_la_CANTIDAD_no_le_RE_FECHA_el_precio(galpon):
    """EL CASO QUE DECIDE TODO. La pantalla de Editar Compra llama a
    actualizar_precio_compra en cada guardado, toque el precio o no. Sin la
    guarda, corregir los cajones de una compra le fecharía el precio como
    renegociado hoy: la columna mentiría justo en el caso para el que existe, y
    sin que nada se vea raro en ninguna pantalla.
    """
    d, sql, _, _ = galpon
    compra_id = _alta(galpon, 50000)
    sql("UPDATE compras SET importe_puesto_el = now() - interval '5 days' WHERE id = %s", (compra_id,))
    (antes,), = sql("SELECT importe_puesto_el FROM compras WHERE id = %s", (compra_id,))

    d.actualizar_precio_compra(compra_id, 50000, None)   # el MISMO número

    despues, origen, _ = _par(sql, compra_id)
    assert despues == antes, "se re-fechó un importe que no cambió"
    assert origen == "alta", "y encima quedó diciendo que lo puso la edición"


def test_una_renegociacion_DE_VERDAD_si_sella_edicion(galpon):
    """El control del test de arriba: sin éste, una guarda que no sellara NUNCA
    los pasaría a los dos (corolario 30 — el caso que tiene que pasar es el que
    distingue la guarda que funciona de la que frena siempre)."""
    d, sql, _, _ = galpon
    compra_id = _alta(galpon, 50000)
    sql("UPDATE compras SET importe_puesto_el = now() - interval '5 days' WHERE id = %s", (compra_id,))
    (antes,), = sql("SELECT importe_puesto_el FROM compras WHERE id = %s", (compra_id,))

    d.actualizar_precio_compra(compra_id, 61000, None)   # OTRO número

    despues, origen, importe = _par(sql, compra_id)
    assert despues != antes
    assert origen == "edicion"
    assert importe == 61000


def test_BORRAR_el_precio_devuelve_el_par_a_NULL(galpon):
    """Un "puesto el 19/09 por edición" sobre una fila sin precio afirma algo
    que no pasó — es el `{% else %}` que dice de más, en una columna."""
    d, sql, _, _ = galpon
    compra_id = _alta(galpon, 50000)
    d.actualizar_precio_compra(compra_id, None, None)
    assert _par(sql, compra_id) == (None, None, None)
