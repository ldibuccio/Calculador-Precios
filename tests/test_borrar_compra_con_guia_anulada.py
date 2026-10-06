"""Borrar una compra que costeó una guía R ya ANULADA (28/09), contra Postgres.

El caso real: la compra 827 (Palta, 27/09) se cargó cruzada y había que
borrarla. "Corregir o eliminar compra" la frenaba con "R556 se costeó contra
este lote", y la R556 estaba anulada desde el 28/09. El consumo congelado de
la guía anulada seguía apuntando a la compra, y `reprocesos_consumos.compra_id`
es una FK sin cascade: aunque la guarda la dejara pasar, el DELETE rebotaba.

CONTRA LA BASE Y NO CON MOCKS: lo que decide es la FK, y con la base mockeada
el rebote no lo arbitra nadie (corolario 89). Y cada caso lleva su RIVAL: la
guía viva, que tiene que seguir frenando, y la consumida por OTRA compra, que
no se puede llevar puesta.
"""
import os
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


@pytest.fixture(scope="module")
def base_real():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def galpon(base_real, monkeypatch):
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
    (art,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id", (f"EJEMPLO Palta {n}",))
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s,%s) RETURNING id",
                   (f"EJEMPLO Puesto {n}", f"N07P{n % 100:02d}"))

    def recepcionada():
        d.crear_compra(date(2026, 9, 27), art, prov, 10, 16, 160, None, 50000, None,
                       "Clark", None, segunda_por_cajon=None, codigo_llegada=None)
        (cid,), = sql("SELECT max(id) FROM compras")
        sql("""UPDATE compras SET estado='recepcionado', cantidad_cajones_real=10,
               contenido_por_cajon_real=16, cantidad_kilos_real=160, procesada_el=now()
               WHERE id=%s""", (cid,))
        return cid

    def guia_r(*consumos, anulada=False):
        """Una guía R normal que consumió `bultos` de cada compra."""
        (rid,), = sql("""INSERT INTO reprocesos (articulo_id, fecha_operacion, bultos_tomados,
                         bultos_primera, bultos_segunda, bultos_merma, tipo)
                         VALUES (%s, date '2026-09-27', %s, %s, 0, 0, 'normal') RETURNING id""",
                      (art, sum(b for _c, b in consumos), sum(b for _c, b in consumos)))
        for compra_id, bultos in consumos:
            sql("""INSERT INTO reprocesos_consumos (reproceso_id, origen, compra_id, bultos,
                   costo_por_bulto) VALUES (%s,'compra',%s,%s,50000)""", (rid, compra_id, bultos))
        if anulada:
            sql("UPDATE reprocesos SET anulado_el = now() WHERE id=%s", (rid,))
        return rid

    def consumos(compra_id):
        (n,), = sql("SELECT count(*) FROM reprocesos_consumos WHERE compra_id=%s", (compra_id,))
        return n

    def existe(compra_id):
        (n,), = sql("SELECT count(*) FROM compras WHERE id=%s", (compra_id,))
        return n == 1

    return d, sql, recepcionada, guia_r, consumos, existe, art


def test_la_compra_costeada_por_una_guia_ANULADA_SE_BORRA_y_su_consumo_se_va(galpon):
    """El caso de la 827: la pantalla no lo nombra, el borrado anda, y queda
    archivada como cualquier otra."""
    d, sql, recepcionada, guia_r, consumos, existe, _ = galpon
    compra = recepcionada()
    guia_r((compra, 8), anulada=True)

    assert d.lo_que_cuelga_de_la_compra(compra) == [], "la pantalla no ofrecería el botón"
    d.eliminar_compra(compra, forzar=True, origen="gerencia")

    assert not existe(compra)
    assert consumos(compra) == 0
    (archivadas,), = sql("SELECT count(*) FROM compras_eliminadas WHERE compra_id=%s", (compra,))
    assert archivadas == 1


def test_con_la_guia_VIVA_sigue_FRENANDO_y_no_toca_nada(galpon):
    """El rival: una guía que todavía cuenta no se puede llevar puesta."""
    d, _sql, recepcionada, guia_r, consumos, existe, _ = galpon
    compra = recepcionada()
    viva = guia_r((compra, 8))

    assert [c["detalle"] for c in d.lo_que_cuelga_de_la_compra(compra)] == [
        f"R{viva} se costeó contra este lote"]
    with pytest.raises(ValueError, match=f"R{viva}"):
        d.eliminar_compra(compra, forzar=True, origen="gerencia")
    assert existe(compra) and consumos(compra) == 1


def test_una_VIVA_y_una_ANULADA_juntas_frenan_y_la_anulada_NO_SE_BORRA_a_medias(galpon):
    """El DELETE de los consumos anulados va antes del freno. Si el freno
    rebota, se tiene que deshacer con todo lo demás: la misma transacción."""
    d, _sql, recepcionada, guia_r, consumos, existe, _ = galpon
    compra = recepcionada()
    guia_r((compra, 3), anulada=True)
    viva = guia_r((compra, 5))

    with pytest.raises(ValueError, match=f"R{viva}"):
        d.eliminar_compra(compra, forzar=True, origen="gerencia")
    assert existe(compra) and consumos(compra) == 2


def test_SIN_FORZAR_tambien_se_deshace_si_la_compra_no_se_puede_borrar(galpon):
    """Sin forzar, la recepcionada rebota por estado: el borrado de los
    consumos anulados tiene que volver atrás igual."""
    d, _sql, recepcionada, guia_r, consumos, existe, _ = galpon
    compra = recepcionada()
    guia_r((compra, 8), anulada=True)

    with pytest.raises(ValueError, match="recepcionada"):
        d.eliminar_compra(compra, origen="compras")
    assert existe(compra) and consumos(compra) == 1


def test_la_guia_anulada_que_consumio_OTRA_compra_conserva_ese_consumo(galpon):
    """Se borra lo que apunta a ESTA compra y nada más: la misma guía anulada
    puede haber tomado de dos lotes."""
    d, _sql, recepcionada, guia_r, consumos, existe, _ = galpon
    esta, otra = recepcionada(), recepcionada()
    guia_r((esta, 4), (otra, 4), anulada=True)

    d.eliminar_compra(esta, forzar=True, origen="gerencia")
    assert not existe(esta)
    assert consumos(otra) == 1


def test_la_EN_ORIGEN_anulada_sigue_frenando_y_LO_DICE(galpon):
    """Su `compra_origen_id` es la FK misma y el CHECK del tipo no la deja en
    NULL. Frenar sin decir que ya está anulada manda a anularla de nuevo."""
    d, sql, recepcionada, _guia_r, _consumos, existe, art = galpon
    compra = recepcionada()
    (cliente,), = sql("INSERT INTO clientes (nombre) VALUES (%s) RETURNING id",
                      (f"EJEMPLO Cliente {compra}",))
    (ficha,), = sql("""INSERT INTO fichas_logistica (articulo_id, cliente_id, unidad_venta,
                       contenido_caja) VALUES (%s,%s,'kilo',6) RETURNING id""", (art, cliente))
    (rid,), = sql("""INSERT INTO reprocesos (articulo_id, fecha_operacion, bultos_tomados,
                     bultos_primera, bultos_segunda, bultos_merma, tipo, compra_origen_id,
                     ficha_id, anulado_el)
                     VALUES (%s, date '2026-09-27', 5, 5, 0, 0, 'en_origen', %s, %s, now())
                     RETURNING id""", (art, compra, ficha))

    detalle, = [c["detalle"] for c in d.lo_que_cuelga_de_la_compra(compra)]
    assert detalle.startswith(f"R{rid} salió de esta compra") and "está anulada" in detalle
    with pytest.raises(ValueError, match=f"R{rid}"):
        d.eliminar_compra(compra, forzar=True, origen="gerencia")
    assert existe(compra)


# --------------------------------------------- las que no miran la anulación

# Las consultas sobre guías R que NO preguntan por `anulado_el`, cada una con
# su razón. Todas operan sobre UNA guía ya elegida por id, o son fragmentos que
# se pegan adentro de una consulta que sí filtra. El barrido compara el
# conjunto ENCONTRADO contra éste (corolario 60): falla con una consulta nueva
# que nadie decidió y con una de la lista que empezó a filtrar.
SIN_FILTRO_DECIDIDAS = {
    "_SQL_FALTA_ALGUN_PRECIO": (1, "fragmento: lo pegan consultas con rp.anulado_el IS NULL"),
    "_SQL_FALTA_UN_PRECIO_IMPOSIBLE": (1, "fragmento: lo pegan consultas con rp.anulado_el IS NULL"),
    "_completar_costos_congelados": (4, "por id; la cola entra solo con guías vivas"),
    "asignar_ficha_a_reproceso": (1, "por id; rechaza la anulada antes"),
    "cambiar_fecha_de_reproceso": (2, "por id; rechaza la anulada antes"),
    "listar_reprocesos_por_rango": (1, "consumos de las guías que ya listó, que muestran si están anuladas"),
}


def _consultas_sin_filtro():
    import ast
    import io
    import re
    from collections import Counter

    encontradas = Counter()
    for archivo in ("app/db.py", "app/main.py", "app/costeo.py"):
        arbol = ast.parse(io.open(os.path.join(RAIZ, archivo), encoding="utf-8").read())
        dueño = {}
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.FunctionDef):
                for hijo in ast.walk(nodo):
                    dueño.setdefault(id(hijo), nodo.name)
            elif isinstance(nodo, ast.Assign) and isinstance(nodo.targets[0], ast.Name):
                for hijo in ast.walk(nodo.value):
                    dueño.setdefault(id(hijo), nodo.targets[0].id)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                texto = nodo.value
            elif isinstance(nodo, ast.JoinedStr):
                texto = "".join(v.value for v in nodo.values if isinstance(v, ast.Constant))
            else:
                continue
            # Sin los comentarios de SQL: un comentario que explica el filtro
            # lo nombra, y pasaría por filtrado (corolario 59).
            texto = re.sub(r"--[^\n]*", "", texto)
            # En POSICIÓN DE TABLA, no la palabra suelta: la prosa de un
            # docstring nombra `reprocesos_consumos` todo el tiempo.
            if (re.search(r"\b(FROM|JOIN|UPDATE)\s+reprocesos(_consumos)?\b", texto)
                    and "anulado_el" not in texto):
                encontradas[dueño.get(id(nodo), f"{archivo}:{nodo.lineno}")] += 1
    return encontradas


def test_TODA_consulta_sobre_guias_R_mira_si_esta_ANULADA_o_esta_DECIDIDA():
    """La 827 frenó por una consulta que contaba una guía anulada como viva.
    Barrido el 28/09: era la única. Esto hace que la próxima no se escriba en
    silencio."""
    encontradas = _consultas_sin_filtro()
    decididas = {nombre: n for nombre, (n, _razon) in SIN_FILTRO_DECIDIDAS.items()}
    assert dict(encontradas) == decididas


# ------------------------------------------------ todo lo que apunta a compras

# Cada FK a `compras`, con qué hace el borrado con ella. Encontrado contra
# decidido (corolario 60): una FK nueva a compras que nadie decidió llega al
# DELETE como un ForeignKeyViolation crudo, que no dice cuál la retiene.
FK_A_COMPRAS_DECIDIDAS = {
    ("fotos_recepcion", "compra_id"): "la borra eliminar_compra: el archivo es de esta compra",
    ("reprocesos_consumos", "compra_id"): "frena si la guía está viva; si está anulada, se borra",
    ("reprocesos", "compra_origen_id"): "frena siempre, viva o anulada: el CHECK no la deja en NULL",
    ("vacios_deposito_devoluciones", "compra_id"): "frena y la nombra",
    ("movimientos_stock", "compra_devolucion_id"): "frena y la nombra",
    ("retroactivos", "compra_id"): "on delete cascade: el registro del ingreso con fecha anterior se va con la compra",
}


def test_TODA_FK_a_compras_esta_DECIDIDA(galpon):
    _d, sql, *_ = galpon
    encontradas = set(sql("""
        SELECT c.conrelid::regclass::text, a.attname
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
         WHERE c.contype = 'f' AND c.confrelid = 'compras'::regclass"""))
    assert encontradas, "no encontró ninguna FK: la consulta no mira lo que dice"
    assert encontradas == set(FK_A_COMPRAS_DECIDIDAS)
