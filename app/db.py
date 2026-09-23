"""Conexión a la base de datos (Supabase / PostgreSQL).

Aísla la conexión en su propio módulo para que sea fácil de reemplazar o
testear (con mocks), igual que se hizo con la llamada a la API de Claude en
core/lector_comandas.py.
"""

import os
import re
from datetime import timedelta
from contextlib import contextmanager

import psycopg2

from core.envases import (como_queda_la_cuenta, efecto_en_la_cuenta,
                          envase_derivado_de_la_ficha, hay_que_reponer)
from core.magnitudes import repartir_magnitudes
from core.matcheo_comanda import normalizar_texto
from core.vino_armada import motivo_para_no_marcar_armada, motivo_sin_lote_por_el_corte

DATABASE_URL_ENV_VAR = "DATABASE_URL"


def obtener_conexion():
    """Abre una conexión nueva a la base de datos.

    Lanza RuntimeError con un mensaje claro si falta configurar la variable
    de entorno DATABASE_URL.
    """
    database_url = os.environ.get(DATABASE_URL_ENV_VAR)
    if not database_url:
        raise RuntimeError(
            f"Falta configurar la variable de entorno {DATABASE_URL_ENV_VAR} con la cadena de conexión a Supabase"
        )
    return psycopg2.connect(database_url)


def contar_articulos() -> int:
    """Cuenta cuántos artículos hay cargados en la tabla articulos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM articulos")
            (cantidad,) = cursor.fetchone()
        return cantidad
    finally:
        conexion.close()


def listar_articulos() -> list[dict]:
    """Devuelve los artículos activos, ordenados por nombre.

    codigo_interno no se lee acá: es un dato del cliente Día (para su email
    de pedido), no del artículo en sí, y se maneja en conversion_articulos_cliente.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, nombre, merma_porcentaje, unidad_compra, unidad_conteo, contenido_referencia, grupo
                FROM articulos WHERE activo = true ORDER BY nombre
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_articulo(articulo_id: int) -> dict | None:
    """Devuelve un artículo por id (para precargar el formulario de edición), o None si no existe."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, nombre, merma_porcentaje, unidad_compra, unidad_conteo, contenido_referencia, grupo
                FROM articulos WHERE id = %s
                """,
                (articulo_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


# EN QUÉ UNIDAD NACE `contenido_por_cajon` DE UN ARTÍCULO NUEVO, y es siempre
# la misma: KILOS. Es lo único que `unidad_compra` todavía dice (ver su
# comment), y desde el 15/09 no lo elige nadie — el formulario dejó de
# preguntarlo. Los cuatro artículos viejos que se compran contados conservan
# su valor y siguen andando igual; lo que se terminó es que alguien cargue
# uno nuevo.
UNIDAD_DEL_CONTENIDO_DE_UN_ARTICULO_NUEVO = "kilo"


def crear_articulo(
    nombre: str,
    contenido_referencia: float | None,
    grupo: str | None = None,
    unidad_conteo: str | None = None,
) -> int:
    """Inserta un artículo nuevo y DEVUELVE SU ID. grupo es opcional: None = sin clasificar todavía.

    Devolvía None. El id hace falta desde que la revisión del archivo puede
    dar de alta un artículo que falta y tiene que dejarlo ELEGIDO en su
    renglón: buscarlo después por nombre sería preguntar por algo que se
    acaba de escribir, con el plegado de por medio.

    `unidad_compra` NO es un parámetro: se escribe 'kilo' y punto. Dejó de
    ser una decisión el día que la compra pasó a declarar las dos magnitudes
    — los kilos van siempre, y lo que el artículo además cuenta lo dice
    `unidad_conteo`.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO articulos (nombre, unidad_compra, unidad_conteo, contenido_referencia, grupo)"
                " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (nombre, UNIDAD_DEL_CONTENIDO_DE_UN_ARTICULO_NUEVO, unidad_conteo,
                 contenido_referencia, grupo),
            )
            nuevo_id = cursor.fetchone()[0]
        conexion.commit()
        return nuevo_id
    finally:
        conexion.close()


# EL CONTEO NO PUEDE CONTRADECIR LA UNIDAD EN QUE ESTÁ ESCRITA LA HISTORIA.
#
# `unidad_compra` dice en qué unidad está expresado `compras.contenido_por_cajon`
# de ese artículo, y `repartir_magnitudes` manda ese total a
# `cantidad_fraccion`. Si `unidad_conteo` declarara OTRA unidad, una ficha que
# venda en esa otra unidad costearía contra un número que está en la primera:
# cuarenta UNIDADES leídas como cuarenta CUBETAS. No se descuadra nada, no hay
# error, y el costo sale mal — que es el modo de falla caro de este modelo.
#
# Las dos que NO entran acá, y cada una por su razón:
#
# - `unidad_compra` en 'kilo' o en nulo: la historia está en kilos, así que el
#   conteo es libre y no puede contradecir nada.
# - El conteo VACÍO en un artículo contado: no miente. Deja sus fichas sin
#   costear, y eso se VE en la pantalla como negativa. Trabar acá sería trabar
#   el caso que se degrada de frente.
def _negar_si_el_conteo_contradice_la_unidad_de_compra(
    unidad_compra: str | None, unidad_conteo: str | None
) -> None:
    """Levanta ValueError si el conteo declarado no es la unidad de la historia."""
    if not unidad_compra or unidad_compra == "kilo":
        return
    if unidad_conteo is None or unidad_conteo == unidad_compra:
        return
    raise ValueError(
        f"Este artículo se compra contado en {unidad_compra}, y su historia de contenido"
        f" por cajón está expresada en eso: no se puede declarar que se cuenta en"
        f" {unidad_conteo}. Dejalo en {unidad_compra}, o sin conteo."
    )


def actualizar_articulo(
    articulo_id: int,
    nombre: str,
    contenido_referencia: float | None,
    grupo: str | None = None,
    unidad_conteo: str | None = None,
) -> None:
    """Actualiza nombre, conteo, contenido de referencia y grupo de un artículo existente.

    `unidad_compra` NO SE TOCA, y es deliberado: los cuatro artículos que se
    compran contados la tienen en 'unidad' y su historia de
    `contenido_por_cajon` está expresada en eso. Pisarla con 'kilo' —o
    nulearla— dejaría cada compra vieja de esos artículos etiquetada en la
    unidad equivocada, sin mover un solo número y sin que nada avise. Es la
    columna que quedó para lo viejo: se lee, no se escribe. Acá se LEE, y para
    una sola cosa: negar el conteo que la contradiga (ver la guarda de arriba).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # La unidad de la historia se lee EN LA MISMA TRANSACCIÓN y con
            # `FOR UPDATE`: leerla antes, afuera, dejaría una ventana donde
            # cambia entre la lectura y el UPDATE. Y va SIN agregado a
            # propósito —un `count(*)` devuelve una fila siempre, así que
            # `fila is None` dejaría de poder decir "no existe" (corolario 27).
            cursor.execute(
                "SELECT unidad_compra FROM articulos WHERE id = %s FOR UPDATE",
                (articulo_id,),
            )
            fila = cursor.fetchone()
            if fila is not None:
                _negar_si_el_conteo_contradice_la_unidad_de_compra(fila[0], unidad_conteo)
            cursor.execute(
                """
                UPDATE articulos
                SET nombre = %s, unidad_conteo = %s,
                    contenido_referencia = %s, grupo = %s, actualizado_en = now()
                WHERE id = %s
                """,
                (nombre, unidad_conteo, contenido_referencia, grupo, articulo_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def desactivar_articulo(articulo_id: int) -> None:
    """Da de baja un artículo (borrado lógico): lo marca activo = false sin borrar su historial."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE articulos SET activo = false, actualizado_en = now() WHERE id = %s",
                (articulo_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


# El "hoy" con el que se resuelve una VIGENCIA, del lado de la base.
#
# `CURRENT_DATE` es la fecha del SERVIDOR, y la base corre en UTC: a partir de
# las 21:00 de Argentina adelanta un día. Todo lo demás del sistema resuelve
# con la fecha argentina, así que eran DOS relojes para el mismo hecho.
#
# Medido el 14/09 y no deducido: cinco tasas de un cliente cargadas el 15/08 a
# las 22:01 quedaron con `vigente_desde` del 16 — no rigieron el día en que se
# cargaron. Ver `db/precios_2_quienes_son_los_fechados_distinto.sql`.
#
# LOS QUE ESCRIBEN NO USAN ESTO: reciben la fecha por parámetro, igual que los
# precios. Acá va solo donde se PREGUNTA qué rige ahora, que no es una decisión
# de nadie y tiene 31 llamadores — meterles un parámetro serían 31 lugares
# donde pasar el reloj equivocado.
#
# La zona va NOMBRADA, como las otras 34 veces de este archivo y como
# `core/zona.py`: un offset fijo de −3 no se entera el día que el país mueva
# el reloj, y lo haría en silencio.
_SQL_HOY_ARGENTINA = "(now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date"


_CLIENTE_CON_TASAS_VIGENTES_SQL = f"""
    WITH vigentes AS (
        SELECT DISTINCT ON (cliente_id, nombre_parametro) cliente_id, nombre_parametro, tipo, valor
        FROM clientes_parametros_historial
        WHERE vigente_desde <= {_SQL_HOY_ARGENTINA}
        ORDER BY cliente_id, nombre_parametro, vigente_desde DESC
    ),
    totales AS (
        SELECT cliente_id,
               COALESCE(SUM(valor) FILTER (WHERE tipo = 'resta'), 0) AS total_resta,
               COALESCE(SUM(valor) FILTER (WHERE tipo = 'suma'), 0) AS total_suma
        FROM vigentes
        GROUP BY cliente_id
    ),
    utilidades AS (
        SELECT DISTINCT ON (cliente_id) cliente_id, valor
        FROM vigentes
        WHERE tipo = 'utilidad'
        ORDER BY cliente_id, (nombre_parametro = 'utilidad_objetivo') DESC
    )
    SELECT c.id, c.nombre,
           COALESCE(totales.total_resta, 0) * 100 AS descuento,
           COALESCE(totales.total_suma, 0) * 100 AS adicionales,
           utilidades.valor * 100 AS utilidad_objetivo
    FROM clientes c
    LEFT JOIN totales ON totales.cliente_id = c.id
    LEFT JOIN utilidades ON utilidades.cliente_id = c.id
"""


def listar_clientes() -> list[dict]:
    """Devuelve los clientes activos (id, nombre, descuento %, adicionales %, utilidad_objetivo %) ordenados por nombre.

    "descuento" es la SUMA de todas las tasas vigentes de tipo 'resta'
    (ej. Logística 23% + Flete 3% -> 26%), "adicionales" la suma de las de
    tipo 'suma' (ej. IVA), y "utilidad_objetivo" la única tasa vigente de
    tipo 'utilidad'. El detalle tasa por tasa se ve al editar el cliente
    (listar_conceptos_editables_por_cliente); acá alcanza con los totales.
    "Vigente" es, para cada nombre_parametro por separado, el registro de
    clientes_parametros_historial con vigente_desde más reciente que ya
    llegó (no futura) — una tasa dada de baja (valor 0) no suma nada, sin
    necesitar ningún caso especial.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_CLIENTE_CON_TASAS_VIGENTES_SQL + " WHERE c.activo = true ORDER BY c.nombre")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_cliente(cliente_id: int) -> dict | None:
    """Devuelve un cliente por id con sus totales de tasas vigentes (ver listar_clientes), o None si no existe."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_CLIENTE_CON_TASAS_VIGENTES_SQL + " WHERE c.id = %s", (cliente_id,))
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def _agrupar_conceptos(filas) -> dict:
    """Las filas vigentes de un cliente, agrupadas por tipo para el motor de costeo.

    Separado de la consulta para que la versión de a una fecha y la de
    varias compartan EXACTAMENTE este criterio (el de la utilidad, sobre
    todo: si hay más de un concepto de tipo 'utilidad' se prioriza
    utilidad_objetivo, y si no está ese nombre, el primero que aparezca).
    """
    tasas_suman = [float(fila["valor"]) for fila in filas if fila["tipo"] == "suma"]
    tasas_restan = [float(fila["valor"]) for fila in filas if fila["tipo"] == "resta"]

    # EL NOMBRE DE CADA TASA, que hasta el 12/09 se tiraba acá. El motor
    # necesita números sueltos y por eso las dos listas de arriba no cambian;
    # pero una pantalla que muestra "Resta −23%" sin decir que ese 23 es el
    # descuento obliga a ir a buscarlo a otra pantalla, y la que lo mira es
    # justamente la que decide si paga o no paga un cajón.
    #
    # Va COMO TERCERA CLAVE y no reemplazando a las otras dos: las listas de
    # floats son el contrato con core.motor_costeo y meterles diccionarios
    # adentro sería cambiar la firma del motor por una razón de presentación.
    detalle = [
        {"nombre": fila["nombre_parametro"], "tipo": fila["tipo"], "valor": float(fila["valor"])}
        for fila in filas
        if fila["tipo"] in ("suma", "resta")
    ]
    detalle.sort(key=lambda t: (t["tipo"] != "suma", t["nombre"]))

    filas_utilidad = [fila for fila in filas if fila["tipo"] == "utilidad"]
    utilidad = None
    if filas_utilidad:
        fila_utilidad = next(
            (fila for fila in filas_utilidad if fila["nombre_parametro"] == "utilidad_objetivo"),
            filas_utilidad[0],
        )
        utilidad = float(fila_utilidad["valor"])

    return {"tasas_suman": tasas_suman, "tasas_restan": tasas_restan,
            "utilidad": utilidad, "detalle": detalle}


def listar_conceptos_vigentes_por_cliente_en_fechas(cliente_id: int, fechas) -> dict:
    """Los conceptos vigentes de un cliente a VARIAS fechas, en una consulta.

    Devuelve {fecha: {tasas_suman, tasas_restan, utilidad}}. Igual que los
    precios y los envases: la consulta de "vigente" es la de siempre, dentro
    de un LATERAL que la corre una vez por fecha, y el agrupado sale del
    mismo _agrupar_conceptos. Un cambio de tasas a mitad del rango tiene que
    pegar solo de esa fecha en adelante, nunca retroactivo.
    """
    fechas_unicas = sorted(set(fechas))
    if not fechas_unicas:
        return {}
    filas_por_fecha = {fecha: [] for fecha in fechas_unicas}
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.fecha, c.nombre_parametro, c.tipo, c.valor
                FROM unnest(%s::date[]) AS f(fecha)
                CROSS JOIN LATERAL (
                    SELECT DISTINCT ON (nombre_parametro) nombre_parametro, tipo, valor
                    FROM clientes_parametros_historial
                    WHERE cliente_id = %s AND vigente_desde <= f.fecha
                    ORDER BY nombre_parametro, vigente_desde DESC
                ) c
                """,
                (fechas_unicas, cliente_id),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            for fila in cursor.fetchall():
                concepto = dict(zip(columnas, fila))
                filas_por_fecha[concepto.pop("fecha")].append(concepto)
    finally:
        conexion.close()
    return {fecha: _agrupar_conceptos(filas) for fecha, filas in filas_por_fecha.items()}


def listar_conceptos_vigentes_por_cliente(cliente_id: int, fecha_referencia) -> dict:
    """Todos los conceptos vigentes de un cliente (clientes_parametros_historial), agrupados por tipo.

    A diferencia de _CLIENTE_CON_DESCUENTO_Y_UTILIDAD_VIGENTES_SQL (que solo
    conoce dos nombre_parametro fijos), esto trae CUALQUIER concepto que
    tenga el cliente cargado — descuento, utilidad, flete, IVA, premios,
    lo que sea — y los agrupa según su columna "tipo" ('suma', 'resta',
    'utilidad'), para alimentar directo a
    core.motor_costeo.precio_sugerido_multi_concepto.

    "Vigente" es, para cada nombre_parametro por separado, la fila con
    vigente_desde más reciente que ya llegó a fecha_referencia (mismo
    patrón que el resto de las tablas *_historial).

    Devuelve:
      - "tasas_suman": lista de fracciones (0.105, no 10.5) de todos los
        conceptos vigentes con tipo='suma'.
      - "tasas_restan": lista de fracciones de todos los conceptos vigentes
        con tipo='resta'.
      - "utilidad": la fracción del concepto vigente con tipo='utilidad'
        (uno solo se usa: si hay más de uno, se prioriza
        nombre_parametro='utilidad_objetivo'; si no está ese nombre, el
        primero que aparezca). None si el cliente no tiene ningún concepto
        de tipo 'utilidad' vigente todavía.

    A diferencia de listar_clientes/obtener_cliente (que devuelven
    descuento/utilidad_objetivo como PORCENTAJE, ×100, por compatibilidad
    con las pantallas viejas), acá los valores vienen tal cual están
    guardados: fracción (0.23), no porcentaje.
    """
    return listar_conceptos_vigentes_por_cliente_en_fechas(cliente_id, [fecha_referencia])[fecha_referencia]


def listar_conceptos_editables_por_cliente(cliente_id: int) -> dict:
    """Tasas suma/resta ACTIVAS y la utilidad objetivo vigentes hoy, para precargar el formulario de cliente.

    A diferencia de listar_conceptos_vigentes_por_cliente (que agrega todo
    en listas de números para el motor de costeo), esto devuelve el detalle
    por concepto (nombre + %) que necesita el formulario editable, y deja
    afuera las tasas dadas de baja (vigentes con valor 0) para que no
    reaparezcan como filas activas — ver calcular_cambios_de_tasas en
    core/conceptos_cliente.py sobre cómo se marca esa baja.

    Devuelve {"tasas_suma": [{"nombre", "valor_pct"}, ...], "tasas_resta":
    [...], "utilidad_pct": float|None}, con valor_pct ya en porcentaje
    (21.0, no 0.21) para precargar directo los inputs del formulario.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT DISTINCT ON (nombre_parametro) nombre_parametro, tipo, valor
                FROM clientes_parametros_historial
                WHERE cliente_id = %s AND vigente_desde <= {_SQL_HOY_ARGENTINA}
                ORDER BY nombre_parametro, vigente_desde DESC
                """,
                (cliente_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()

    tasas_suma = [
        {"nombre": fila["nombre_parametro"], "valor_pct": float(fila["valor"]) * 100}
        for fila in filas
        if fila["tipo"] == "suma" and float(fila["valor"]) != 0
    ]
    tasas_resta = [
        {"nombre": fila["nombre_parametro"], "valor_pct": float(fila["valor"]) * 100}
        for fila in filas
        if fila["tipo"] == "resta" and float(fila["valor"]) != 0
    ]
    fila_utilidad = next((fila for fila in filas if fila["tipo"] == "utilidad"), None)
    utilidad_pct = float(fila_utilidad["valor"]) * 100 if fila_utilidad else None

    return {"tasas_suma": tasas_suma, "tasas_resta": tasas_resta, "utilidad_pct": utilidad_pct}


def _insertar_conceptos_cliente(cursor, cliente_id: int, conceptos: list[dict], vigente_desde) -> None:
    """Inserta cada concepto con la vigencia que le PASAN, sin pisar historial viejo.

    conceptos: [{"nombre_parametro", "tipo", "valor"}, ...] (valor en
    fracción). Si ya existe una fila de esa MISMA fecha para ese mismo
    (cliente_id, nombre_parametro) -- segunda edición el mismo día -- la
    actualiza en vez de duplicarla; nunca toca una fila anterior.

    vigente_desde va por PARÁMETRO y sin default, igual que en
    guardar_precios_cliente: acá decía CURRENT_DATE, que es el reloj del
    servidor de la base (UTC) y adelanta un día pasadas las 21:00 de
    Argentina. Eso ya escribió cinco tasas fechadas mañana (15/08 22:01;
    ver db/precios_2_quienes_son_los_fechados_distinto.sql). Sin default,
    el que se olvide de pasarla se lleva un TypeError y no una fila con
    la fecha equivocada.
    """
    for concepto in conceptos:
        cursor.execute(
            """
            INSERT INTO clientes_parametros_historial (cliente_id, nombre_parametro, valor, tipo, vigente_desde)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (cliente_id, nombre_parametro, vigente_desde)
            DO UPDATE SET valor = EXCLUDED.valor, tipo = EXCLUDED.tipo
            """,
            (cliente_id, concepto["nombre_parametro"], concepto["valor"], concepto["tipo"], vigente_desde),
        )


def crear_cliente(
    nombre: str, tasas_suma: list[dict], tasas_resta: list[dict], utilidad_objetivo: float, vigente_desde
) -> int:
    """Crea un cliente y su primer registro de historial, vigente desde la fecha que le pasan. Devuelve el id.

    tasas_suma/tasas_resta: [{"nombre", "valor"}, ...] con valor ya en
    fracción (0.21, no 21). utilidad_objetivo también en fracción.

    vigente_desde sin default: quién es "hoy" lo decide la aplicación con
    la hora argentina, no el reloj UTC del servidor de la base — ver
    _insertar_conceptos_cliente.
    """
    conceptos = (
        [{"nombre_parametro": tasa["nombre"], "tipo": "suma", "valor": tasa["valor"]} for tasa in tasas_suma]
        + [{"nombre_parametro": tasa["nombre"], "tipo": "resta", "valor": tasa["valor"]} for tasa in tasas_resta]
        + [{"nombre_parametro": "utilidad_objetivo", "tipo": "utilidad", "valor": utilidad_objetivo}]
    )

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("INSERT INTO clientes (nombre) VALUES (%s) RETURNING id", (nombre,))
            (cliente_id,) = cursor.fetchone()
            _insertar_conceptos_cliente(cursor, cliente_id, conceptos, vigente_desde)
        conexion.commit()
        return cliente_id
    finally:
        conexion.close()


def actualizar_cliente(cliente_id: int, nombre: str, conceptos_a_guardar: list[dict], vigente_desde) -> None:
    """Actualiza el nombre del cliente y agrega SOLO las filas de historial que realmente cambiaron.

    conceptos_a_guardar: [{"nombre_parametro", "tipo", "valor"}, ...] — ya
    calculado por core.conceptos_cliente (calcular_cambios_de_tasas /
    calcular_cambio_de_utilidad) a partir de lo que cambió en el
    formulario. El nombre/utilidad/tasas viejos NUNCA se pisan: cada
    cambio agrega una fila nueva con la vigencia que le pasan.

    vigente_desde sin default, por lo mismo que crear_cliente.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE clientes SET nombre = %s, actualizado_en = now() WHERE id = %s", (nombre, cliente_id)
            )
            _insertar_conceptos_cliente(cursor, cliente_id, conceptos_a_guardar, vigente_desde)
        conexion.commit()
    finally:
        conexion.close()


def desactivar_cliente(cliente_id: int) -> None:
    """Da de baja un cliente (borrado lógico): lo marca activo = false sin borrar su historial."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE clientes SET activo = false, actualizado_en = now() WHERE id = %s",
                (cliente_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_fichas_de_todos_los_clientes() -> list[dict]:
    """TODAS las fichas de logística, de todos los clientes, en una consulta.

    Misma consulta y mismo orden que listar_fichas_por_cliente, con el
    cliente_id adentro y agregado al ORDER BY para que cada cliente conserve
    exactamente el orden que tenía suelto. La usa el desglose de Stock del
    Depósito, que antes pedía las fichas cliente por cliente.

    TRAE `a.unidad_conteo` AUNQUE SEA DEL ARTÍCULO Y NO DE LA FICHA, y no
    es de más: `magnitud_de_la_ficha` necesita las DOS —la unidad en que
    vende la ficha y la que el artículo puede declarar— y con la que falta
    hace un `.get()` que devuelve None. O sea que una ficha leída sin esta
    columna contesta «no se puede costear» para todo lo que no sea kilo, en
    silencio y sin descuadrar nada. La consulta de los renglones de pedido
    ya la trae por lo mismo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT fl.id, fl.cliente_id, fl.articulo_id, a.nombre AS articulo_nombre,
                       a.grupo AS articulo_grupo, a.unidad_conteo, fl.envase_id,
                       e.nombre AS envase_nombre,
                       fl.contenido_caja, fl.unidad_venta, fl.envase_variable,
                       fl.nombre_cliente, fl.codigo_cliente
                FROM fichas_logistica fl
                JOIN articulos a ON a.id = fl.articulo_id
                LEFT JOIN envases e ON e.id = fl.envase_id
                ORDER BY fl.cliente_id, a.nombre, COALESCE(fl.nombre_cliente, ''), fl.id
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_fichas_por_cliente(cliente_id: int) -> list[dict]:
    """Devuelve las fichas de logística de un cliente, ordenadas por nombre de artículo.

    Un cliente puede tener VARIAS fichas del mismo artículo (Banana Bolivia
    y Banana Ecuador para Día): el desempate por nombre_cliente y por id
    deja el orden estable, para que las dos no se turnen entre pantalla y
    pantalla.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT fl.id, fl.articulo_id, a.nombre AS articulo_nombre, a.grupo AS articulo_grupo,
                       fl.envase_id, e.nombre AS envase_nombre,
                       fl.contenido_caja, fl.unidad_venta, fl.envase_variable, fl.nombre_cliente, fl.codigo_cliente,
                       -- Las DOS magnitudes que puede traer una compra de este
                       -- artículo, al lado de la unidad de venta de la ficha.
                       -- Los kilos van siempre; unidad_conteo dice si además
                       -- viene un conteo y de qué (unidad o cubeta), o NULL si
                       -- el artículo se compra solo por kilo. Con esto el
                       -- costeo elige CUÁL de las dos dividir (ver
                       -- app.costeo.magnitud_de_la_ficha) y puede NEGARSE
                       -- cuando la ficha pide una que el artículo no tiene.
                       --
                       -- unidad_compra viaja solo porque es la etiqueta de
                       -- compras.contenido_por_cajon (en qué unidad está
                       -- expresado ese número). Para el costeo ya no se usa.
                       a.unidad_compra, a.unidad_conteo
                FROM fichas_logistica fl
                JOIN articulos a ON a.id = fl.articulo_id
                LEFT JOIN envases e ON e.id = fl.envase_id
                WHERE fl.cliente_id = %s
                ORDER BY a.nombre, COALESCE(fl.nombre_cliente, ''), fl.id
                """,
                (cliente_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_ficha(ficha_id: int) -> dict | None:
    """Devuelve una ficha por id (con nombres de artículo y cliente, para mostrarlos al editar), o None."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT fl.id, fl.cliente_id, c.nombre AS cliente_nombre,
                       fl.articulo_id, a.nombre AS articulo_nombre,
                       fl.envase_id, fl.contenido_caja, fl.unidad_venta, fl.envase_variable,
                       fl.nombre_cliente, fl.codigo_cliente
                FROM fichas_logistica fl
                JOIN articulos a ON a.id = fl.articulo_id
                JOIN clientes c ON c.id = fl.cliente_id
                WHERE fl.id = %s
                """,
                (ficha_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def contar_fichas_por_articulo(cliente_id: int) -> dict[int, int]:
    """{articulo_id: cuántas fichas tiene ya este cliente} — para avisar al dar de alta una nueva.

    Reemplaza al viejo listar_articulos_sin_ficha: desde que un cliente
    puede tener varias fichas del mismo artículo, esconder los que ya
    tienen una sería justo lo que impedía cargar Banana Ecuador. Se
    ofrecen TODOS los artículos activos (listar_articulos) y esto se usa
    para decir en la pantalla cuáles ya tienen ficha, que ahora es un
    aviso y no una prohibición: con la pared abajo, lo único que evita
    crear dos fichas iguales sin querer es que se vea.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT articulo_id, COUNT(*) FROM fichas_logistica
                WHERE cliente_id = %s GROUP BY articulo_id
                """,
                (cliente_id,),
            )
            return {fila[0]: fila[1] for fila in cursor.fetchall()}
    finally:
        conexion.close()


def listar_envases() -> list[dict]:
    """El catálogo completo de envases activos — los envases son compartidos, no pertenecen a ningún cliente.

    Un envase exclusivo de un cliente (ej. caja impresa con su marca) se
    distingue por el NOMBRE, no por una columna (ver db/envases_sin_cliente.sql).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM envases WHERE activo = true ORDER BY nombre")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_envases_con_costo(fecha_referencia) -> list[dict]:
    """El catálogo completo de envases activos con su costo VIGENTE a una fecha, desde cuándo rige, y cuántas fichas lo usan.

    fichas_que_lo_usan cuenta las fichas de TODOS los clientes: un cambio
    de costo impacta el precio sugerido de todos ellos. costo/vigente_desde
    vienen NULL si el envase todavía no tiene ningún costo cargado con
    vigencia alcanzada — se muestra como "sin costo", no se inventa un cero.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.id, e.nombre, h.costo, h.vigente_desde,
                       (SELECT COUNT(*) FROM fichas_logistica f WHERE f.envase_id = e.id) AS fichas_que_lo_usan
                FROM envases e
                LEFT JOIN LATERAL (
                    SELECT costo, vigente_desde
                    FROM envases_costo_historial
                    WHERE envase_id = e.id AND vigente_desde <= %s
                    ORDER BY vigente_desde DESC
                    LIMIT 1
                ) h ON true
                WHERE e.activo = true
                ORDER BY e.nombre
                """,
                (fecha_referencia,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_historial_costos_envases() -> list[dict]:
    """Todo el historial de costos de los envases activos (del más nuevo al más viejo), para mostrar la evolución."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT h.envase_id, h.costo, h.vigente_desde
                FROM envases_costo_historial h
                JOIN envases e ON e.id = h.envase_id
                WHERE e.activo = true
                ORDER BY h.envase_id, h.vigente_desde DESC
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def crear_envase(nombre: str, costo: float, vigente_desde) -> None:
    """Crea un envase (del catálogo compartido) con su costo inicial vigente desde la fecha que le pasan.

    Todo en una transacción. Nombre repetido: ValueError con mensaje para
    mostrar tal cual (chequeado acá y además garantizado por el UNIQUE
    global de la tabla).

    vigente_desde sin default: acá decía CURRENT_DATE, el reloj UTC del
    servidor de la base, que pasadas las 21:00 de Argentina fecha un día
    adelante — ver _insertar_conceptos_cliente.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT 1 FROM envases WHERE nombre = %s", (nombre,))
            if cursor.fetchone():
                raise ValueError("Ya existe un envase con ese nombre.")

            cursor.execute("INSERT INTO envases (nombre) VALUES (%s) RETURNING id", (nombre,))
            (envase_id,) = cursor.fetchone()
            cursor.execute(
                "INSERT INTO envases_costo_historial (envase_id, costo, vigente_desde) VALUES (%s, %s, %s)",
                (envase_id, costo, vigente_desde),
            )
        conexion.commit()
    finally:
        conexion.close()


def registrar_costo_envase(envase_id: int, costo: float, vigente_desde) -> None:
    """Registra un costo nuevo para un envase, vigente desde la fecha que le pasan — la regla de oro del historial.

    NUNCA pisa filas anteriores: inserta una fila nueva en
    envases_costo_historial (mismo criterio que los precios de venta y los
    parámetros de cliente) — así los cálculos pasados siguen usando el
    costo que regía en su momento. La única excepción es cambiar dos veces
    el MISMO día: ahí se actualiza la fila de hoy (ON CONFLICT), igual que
    en precios_venta_historial. La baja de un envase es esto mismo con
    costo 0.

    vigente_desde sin default, por lo mismo que crear_envase.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO envases_costo_historial (envase_id, costo, vigente_desde)
                VALUES (%s, %s, %s)
                ON CONFLICT (envase_id, vigente_desde) DO UPDATE SET costo = EXCLUDED.costo
                """,
                (envase_id, costo, vigente_desde),
            )
        conexion.commit()
    finally:
        conexion.close()


def crear_ficha(
    articulo_id: int,
    cliente_id: int,
    envase_id: int | None,
    contenido_caja: float,
    unidad_venta: str,
    envase_variable: bool,
    nombre_cliente: str | None = None,
    codigo_cliente: str | None = None,
) -> None:
    """Crea la ficha de logística de un artículo para un cliente.

    nombre_cliente/codigo_cliente son el alias con el que ese cliente pide el
    artículo (opcional: puede no conocerse todavía al crear la ficha).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fichas_logistica
                    (articulo_id, cliente_id, envase_id, contenido_caja, unidad_venta, envase_variable,
                     nombre_cliente, codigo_cliente)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    articulo_id,
                    cliente_id,
                    envase_id,
                    contenido_caja,
                    unidad_venta,
                    envase_variable,
                    nombre_cliente,
                    codigo_cliente,
                ),
            )
            (ficha_id,) = cursor.fetchone()
            _registrar_foto_ficha(
                cursor,
                "alta",
                ficha_id=ficha_id,
                cliente_id=cliente_id,
                articulo_id=articulo_id,
                envase_id=envase_id,
                contenido_caja=contenido_caja,
                unidad_venta=unidad_venta,
                envase_variable=envase_variable,
                nombre_cliente=nombre_cliente,
                codigo_cliente=codigo_cliente,
            )
        conexion.commit()
    finally:
        conexion.close()


def _registrar_foto_ficha(
    cursor,
    evento: str,
    *,
    ficha_id: int,
    cliente_id: int,
    articulo_id: int,
    envase_id,
    contenido_caja,
    unidad_venta: str,
    envase_variable: bool,
    nombre_cliente,
    codigo_cliente,
) -> None:
    """Deja la foto de una ficha en la bitácora (fichas_logistica_historial), en la transacción abierta.

    Todo cambio de ficha pasa por acá para que la bitácora nunca quede
    incompleta: si la escritura de la foto falla, el cambio tampoco se
    confirma.
    """
    cursor.execute(
        """
        INSERT INTO fichas_logistica_historial
            (ficha_id, cliente_id, articulo_id, envase_id, contenido_caja, unidad_venta,
             envase_variable, nombre_cliente, codigo_cliente, evento)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            ficha_id,
            cliente_id,
            articulo_id,
            envase_id,
            contenido_caja,
            unidad_venta,
            envase_variable,
            nombre_cliente,
            codigo_cliente,
            evento,
        ),
    )


def actualizar_ficha(
    ficha_id: int,
    envase_id: int | None,
    contenido_caja: float,
    unidad_venta: str,
    envase_variable: bool,
    nombre_cliente: str | None = None,
    codigo_cliente: str | None = None,
) -> None:
    """Actualiza envase, contenido solicitado, unidad de venta, envase_variable y el alias del cliente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE fichas_logistica
                SET envase_id = %s, contenido_caja = %s, unidad_venta = %s, envase_variable = %s,
                    nombre_cliente = %s, codigo_cliente = %s, actualizado_en = now()
                WHERE id = %s
                RETURNING cliente_id, articulo_id
                """,
                (envase_id, contenido_caja, unidad_venta, envase_variable, nombre_cliente, codigo_cliente, ficha_id),
            )
            fila = cursor.fetchone()
            if fila is not None:
                cliente_id, articulo_id = fila
                _registrar_foto_ficha(
                    cursor,
                    "edicion",
                    ficha_id=ficha_id,
                    cliente_id=cliente_id,
                    articulo_id=articulo_id,
                    envase_id=envase_id,
                    contenido_caja=contenido_caja,
                    unidad_venta=unidad_venta,
                    envase_variable=envase_variable,
                    nombre_cliente=nombre_cliente,
                    codigo_cliente=codigo_cliente,
                )
        conexion.commit()
    finally:
        conexion.close()


def _negar_si_tiene_precios(cursor, ficha_id: int, accion: str) -> None:
    """Frena las DOS puertas que borran una ficha si esa ficha tiene precios cargados.

    accion es "borrar" o "cambiarle el artículo": son dos pantallas
    distintas y la salida que se le ofrece a cada una es distinta, pero
    la REGLA es una sola y por eso vive en una sola función. Escrita dos
    veces se separaría, y la que quedara vieja seguiría desconectando
    precios sin que nada avise — que es justo el modo de falla que esto
    viene a cerrar.

    Cambiar el artículo no parece una puerta y lo es: por dentro es un
    DELETE + INSERT con id nuevo (ver cambiar_articulo_de_ficha), así que
    la ficha vieja se borra igual que con Eliminar.
    """
    cursor.execute(
        "SELECT count(*) FROM precios_venta_historial WHERE ficha_id = %s",
        (ficha_id,),
    )
    precios = cursor.fetchone()[0]
    if not precios:
        return

    uno = precios == 1
    cuantos = f"{precios} {'precio cargado' if uno else 'precios cargados'}"
    if accion == "borrar":
        raise ValueError(
            f"Esa ficha tiene {cuantos}: no se puede borrar. El historial de precios cuelga de "
            "la ficha, así que borrarla dejaría sin respuesta a qué precio se le facturó a este "
            "cliente. Si ya no se usa, dejala: una ficha quieta no ensucia ninguna cuenta."
        )
    raise ValueError(
        f"Esa ficha tiene {cuantos}: no se le puede cambiar el artículo. Cambiarlo borra esta "
        "ficha y abre otra con id nuevo, y el historial de precios quedaría colgado del id "
        "viejo. Creá una ficha nueva para el artículo que buscás — un cliente puede tener "
        "varias fichas del mismo artículo."
    )


def eliminar_ficha(ficha_id: int) -> None:
    """Borra una ficha de logística (borrado real). El estado final queda en la bitácora.

    YA NO ES CIERTO que "nada más referencia su id": desde que reprocesos
    tiene ficha_id, una ficha con guías R NO SE BORRA, y se niega acá con
    el número adentro en vez de dejar que reviente la foreign key.

    El ON DELETE de esa FK es NO ACTION a propósito. Con SET NULL, borrar
    una ficha nulearía sus guías R en silencio: un reproceso perfectamente
    asignado quedaría indistinguible de uno que el operario dejó SIN
    ASIGNAR, y el stock de cajas de esa ficha cambiaría sin que nadie lo
    haya pedido. Borrar una ficha no puede mover el stock.

    Y DESDE QUE `compras` tiene `ficha_en_origen_id` hay un SEGUNDO caso: una
    compra que viene ya armada en caja nuestra y todavía no se recepcionó
    apunta a su ficha desde ahí. Sin esta guarda el DELETE reventaría con el
    error crudo de la foreign key —que no dice qué compra lo retiene— en vez
    del mensaje. Las tres guardas se enumeran juntas a propósito: son la misma
    pregunta ("¿quién apunta a esta ficha?") y separarlas es cómo se olvida
    la siguiente.

    Y LA TERCERA ES `precios_venta_historial`, que el docstring de arriba
    anunciaba sin tenerla. No se había olvidado por descuido: NO PODÍA
    AVISAR. Las otras dos son NO ACTION y revientan la foreign key si
    alguien borra igual —la guarda solo cambia el error crudo por un
    mensaje—; ésta era SET NULL y ACEPTABA EN SILENCIO, dejando los
    precios con ficha_id en NULL. Y como todas las lecturas filtran
    `ficha_id IS NOT NULL`, esos precios dejan de existir para el
    sistema: un listado de julio no puede contestar por una ficha
    borrada en agosto. La guarda existía donde la base grita y faltaba
    exactamente donde la base calla.

    El argumento es el mismo que el de las guías R, trasladado: borrar
    una ficha no puede mover el stock, y tampoco puede borrar el precio
    al que se facturó. `db/precios_no_se_desconectan_al_borrar_la_ficha.sql`
    pone la FK en NO ACTION y deja a las tres del mismo lado; hasta que
    corra en las dos bases, esta guarda es lo único que lo impide.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM reprocesos WHERE ficha_id = %s AND anulado_el IS NULL",
                (ficha_id,),
            )
            guias = cursor.fetchone()[0]
            if guias:
                una = guias == 1
                raise ValueError(
                    f"Esa ficha tiene {guias} {'guía R cargada' if una else 'guías R cargadas'}: "
                    f"no se puede borrar. {'Reasignala' if una else 'Reasignalas'} a otra ficha "
                    "desde Guías R si hace falta."
                )

            cursor.execute(
                """
                SELECT count(*) FROM compras
                WHERE ficha_en_origen_id = %s AND estado IS DISTINCT FROM 'rechazado'
                """,
                (ficha_id,),
            )
            compras = cursor.fetchone()[0]
            if compras:
                una = compras == 1
                raise ValueError(
                    f"Esa ficha está marcada en {compras} "
                    f"{'compra que viene armada' if una else 'compras que vienen armadas'} "
                    "en caja nuestra: no se puede borrar. "
                    f"{'Sacale la marca' if una else 'Sacales la marca'} a "
                    f"{'esa compra' if una else 'esas compras'} primero."
                )

            _negar_si_tiene_precios(cursor, ficha_id, "borrar")

            cursor.execute(
                """
                DELETE FROM fichas_logistica WHERE id = %s
                RETURNING cliente_id, articulo_id, envase_id, contenido_caja, unidad_venta,
                          envase_variable, nombre_cliente, codigo_cliente
                """,
                (ficha_id,),
            )
            fila = cursor.fetchone()
            if fila is not None:
                cliente_id, articulo_id, envase_id, contenido_caja, unidad_venta, envase_variable, nombre_cliente, codigo_cliente = fila
                _registrar_foto_ficha(
                    cursor,
                    "borrado",
                    ficha_id=ficha_id,
                    cliente_id=cliente_id,
                    articulo_id=articulo_id,
                    envase_id=envase_id,
                    contenido_caja=contenido_caja,
                    unidad_venta=unidad_venta,
                    envase_variable=envase_variable,
                    nombre_cliente=nombre_cliente,
                    codigo_cliente=codigo_cliente,
                )
        conexion.commit()
    finally:
        conexion.close()


def cambiar_articulo_de_ficha(
    ficha_id: int,
    articulo_nuevo_id: int,
    nombre_cliente: str | None,
    codigo_cliente: str | None,
) -> int | None:
    """Cambia el artículo al que apunta una ficha: borrado + alta en UNA transacción, conservando el resto.

    No se "edita" el artículo: se cierra la ficha vieja y se abre una nueva
    con el mismo envase, contenido y unidad. El alias
    (nombre_cliente/codigo_cliente) viene de la pantalla: precargado con el
    de la ficha vieja pero editable, porque si el artículo destino es OTRO
    producto (no otra presentación del mismo), el alias viejo quedaría mal.
    En la bitácora quedan los dos eventos, así se ve a qué artículo (y con
    qué alias) apuntaba antes.

    ESTE CAMINO ES LA SEGUNDA PUERTA DEL BORRADO, y no lo parece: la ficha
    nueva tiene id NUEVO, así que desconectaba el historial de precios y los
    renglones viejos de la ficha vieja igual que Eliminar. Con precios
    cargados ahora se NIEGA (_negar_si_tiene_precios): la regla es una sola
    y vive en una sola función, porque escrita dos veces se separa y la
    copia vieja sigue desconectando sin que nada avise.

    Los renglones de pedido SIGUEN con ON DELETE SET NULL y siguen
    desconectándose. Es a propósito y no es lo mismo: un renglón viejo
    describe una entrega que ya pasó y no se consulta hacia atrás por
    ficha; un precio sí, y eso es lo que la pantalla de Precios por
    Período vino a preguntar.

    Para tener dos presentaciones del mismo artículo (Banana Bolivia y
    Banana Ecuador) no se muda esta ficha: se CREA una segunda, que es
    exactamente lo que habilitó sacar el unique (ver
    db/permitir_varias_fichas_por_articulo.sql) y es también la salida que
    el mensaje de la guarda le ofrece al que llega hasta acá.

    Devuelve el id de la ficha nueva, o None si la ficha no existe (con
    precios cargados no devuelve: levanta ValueError). Desde
    que un cliente puede tener varias fichas del mismo artículo, apuntar a
    un artículo que ya tiene otra ficha ya no lo corta la base — queda como
    dos fichas de ese artículo, que puede ser justo lo buscado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            _negar_si_tiene_precios(cursor, ficha_id, "cambiarle el artículo")

            cursor.execute(
                """
                DELETE FROM fichas_logistica WHERE id = %s
                RETURNING cliente_id, articulo_id, envase_id, contenido_caja, unidad_venta,
                          envase_variable, nombre_cliente, codigo_cliente
                """,
                (ficha_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            cliente_id, _articulo_viejo_id, envase_id, contenido_caja, unidad_venta, envase_variable, nombre_viejo, codigo_viejo = fila
            _registrar_foto_ficha(
                cursor,
                "borrado",
                ficha_id=ficha_id,
                cliente_id=cliente_id,
                articulo_id=_articulo_viejo_id,
                envase_id=envase_id,
                contenido_caja=contenido_caja,
                unidad_venta=unidad_venta,
                envase_variable=envase_variable,
                nombre_cliente=nombre_viejo,
                codigo_cliente=codigo_viejo,
            )
            cursor.execute(
                """
                INSERT INTO fichas_logistica
                    (articulo_id, cliente_id, envase_id, contenido_caja, unidad_venta, envase_variable,
                     nombre_cliente, codigo_cliente)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    articulo_nuevo_id,
                    cliente_id,
                    envase_id,
                    contenido_caja,
                    unidad_venta,
                    envase_variable,
                    nombre_cliente,
                    codigo_cliente,
                ),
            )
            (ficha_nueva_id,) = cursor.fetchone()
            _registrar_foto_ficha(
                cursor,
                "alta",
                ficha_id=ficha_nueva_id,
                cliente_id=cliente_id,
                articulo_id=articulo_nuevo_id,
                envase_id=envase_id,
                contenido_caja=contenido_caja,
                unidad_venta=unidad_venta,
                envase_variable=envase_variable,
                nombre_cliente=nombre_cliente,
                codigo_cliente=codigo_cliente,
            )
        conexion.commit()
        return ficha_nueva_id
    finally:
        conexion.close()


def listar_historial_fichas_por_cliente(cliente_id: int) -> list[dict]:
    """La bitácora de fichas de un cliente, de lo más nuevo a lo más viejo, con nombres para mostrar."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT h.id, h.ficha_id, h.articulo_id, a.nombre AS articulo_nombre,
                       h.envase_id, e.nombre AS envase_nombre,
                       h.contenido_caja, h.unidad_venta, h.envase_variable,
                       h.nombre_cliente, h.codigo_cliente, h.evento, h.registrado_en
                FROM fichas_logistica_historial h
                JOIN articulos a ON a.id = h.articulo_id
                LEFT JOIN envases e ON e.id = h.envase_id
                WHERE h.cliente_id = %s
                ORDER BY h.registrado_en DESC, h.id DESC
                """,
                (cliente_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_todas_las_conversiones() -> list[dict]:
    """Todos los alias nombre_cliente -> articulo_id, de cualquier cliente.

    Los alias viven en fichas_logistica (columnas nombre_cliente/codigo_cliente)
    desde que se fusionó ahí la vieja tabla conversion_articulos_cliente. Se usa
    para adivinar artículos en comandas leídas por foto: los alias que ya se
    cargaron para pedidos de clientes (ej. "MANZANA PG" -> Man Gob) también
    sirven para reconocer abreviaturas de proveedores en el mercado, no son
    exclusivos de un cliente puntual.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT articulo_id, nombre_cliente FROM fichas_logistica WHERE nombre_cliente IS NOT NULL")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def buscar_proveedor_por_codigo(codigo_puesto: str) -> dict | None:
    """El proveedor de ese código, o None. NO crea nada y NO toca el nombre.

    La usa el ALTA a mano para saber si el código ya está antes de decidir qué
    mostrar. Va SIN agregado a propósito: con un `count(*)` la fila volvería
    siempre y `fila is None` dejaría de poder decir "no existe" (corolario 27).

    La carrera entre esta consulta y el alta está cubierta y no por suerte: el
    que crea vuelve a buscar por su cuenta, así que si alguien insertó en el
    medio toma la rama del que ya existe — y con `pisar_nombre` en False no le
    pisa nada. El unique de la columna es el piso de todo esto.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, codigo_puesto, nombre, activo FROM proveedores WHERE codigo_puesto = %s",
                (codigo_puesto,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [d[0] for d in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def obtener_o_crear_proveedor_por_codigo(
    codigo_puesto: str, nombre: str, *, pisar_nombre: bool = True
) -> tuple[int, bool]:
    """Busca un proveedor por codigo_puesto (la identidad) o lo crea. ÚNICO lugar que lo INSERTA.

    "La última corrección manda": si el código ya existe pero con otro nombre guardado, se
    pisa con el nombre recién cargado.

    `pisar_nombre` EXISTE PORQUE LAS DOS FUERZAS SE DECIDEN, NO SE HEREDAN
    (corolario 26). Pisar es lo correcto cuando LLEGÓ MERCADERÍA con ese
    código: el que la recibió acaba de leer el nombre del remito y es el dato
    más fresco que hay. En el ALTA A MANO no llegó nada — alguien está
    tipeando un código que puede recordar mal, y renombrarle un proveedor que
    ya existía por eso sería una corrección que nadie pidió. Por eso el alta
    llama con False, y el default deja a los tres caminos de carga como
    estaban.

    Si el que encuentra estaba DADO DE BAJA, lo vuelve a activar: si llegó
    mercadería con ese código, el proveedor existe, y dejarlo de baja haría
    que el selector mienta — además de dejar la compra recién cargada
    colgando de un proveedor invisible. Devuelve (id, reactivado), y el
    segundo valor existe para que la pantalla lo pueda decir cuando pasa:
    una baja que se deshace sola y en silencio es peor que no tenerla.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, activo FROM proveedores WHERE codigo_puesto = %s", (codigo_puesto,))
            fila = cursor.fetchone()
            reactivado = False
            if fila is not None:
                proveedor_id, activo = fila
                reactivado = not activo
                if pisar_nombre:
                    cursor.execute(
                        "UPDATE proveedores SET nombre = %s, activo = true, actualizado_en = now() WHERE id = %s",
                        (nombre, proveedor_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE proveedores SET activo = true, actualizado_en = now() WHERE id = %s",
                        (proveedor_id,),
                    )
            else:
                cursor.execute(
                    "INSERT INTO proveedores (codigo_puesto, nombre) VALUES (%s, %s) RETURNING id",
                    (codigo_puesto, nombre),
                )
                proveedor_id = cursor.fetchone()[0]
        conexion.commit()
        return proveedor_id, reactivado
    finally:
        conexion.close()


def listar_proveedores() -> list[dict]:
    """Los proveedores ACTIVOS (id, codigo_puesto, nombre), para el autocompletar del alta de compras.

    ÚNICO lugar donde se filtra por activo. Los llamadores no repiten el
    WHERE: eligen entre esta y listar_todos_los_proveedores según para qué
    piden la lista.

    Acá va la lista de ELEGIR: cargar una compra, ingresar mercadería. Un
    proveedor dado de baja no tiene que aparecer para elegir — para eso se
    lo dio de baja.

    Para FILTRAR una búsqueda va la otra (listar_todos_los_proveedores):
    las compras viejas de un proveedor de baja siguen existiendo, y
    esconderlo del filtro esconde historial que sí está.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, codigo_puesto, nombre FROM proveedores WHERE activo ORDER BY codigo_puesto")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_todos_los_proveedores() -> list[dict]:
    """Todos los proveedores, de baja incluidos, para los FILTROS de búsqueda (Buscar Compras, Consultar Retiros).

    Sin WHERE a propósito: dar de baja saca del selector de carga, no
    borra las compras. Si el filtro escondiera al proveedor de baja, esas
    compras dejarían de poder buscarse por él — y peor, la pantalla que
    resuelve el nombre del filtro contra esta lista mostraría el filtro
    vacío mientras filtra igual (ver _renderizar_pantalla_buscar_compras).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, codigo_puesto, nombre FROM proveedores ORDER BY codigo_puesto")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_proveedores_para_abm() -> list[dict]:
    """Todos los proveedores con su estado y CUÁNTAS COMPRAS tienen, para el ABM.

    El conteo es lo que separa los dos casos que la pantalla tiene que
    dejar distinguir antes de dar de baja: un fantasma recién creado por
    un código mal tipeado (0 compras) de un proveedor de verdad que
    alguien está por esconder sin querer. No bloquea nada — la FK queda
    intacta y las compras siguen mostrando el nombre —, solo lo dice.

    Los activos primero: los de baja son la excepción y van al final.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.codigo_puesto, p.nombre, p.activo,
                       (SELECT COUNT(*) FROM compras c WHERE c.proveedor_id = p.id) AS compras
                FROM proveedores p
                ORDER BY p.activo DESC, p.codigo_puesto
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def renombrar_proveedor(proveedor_id: int, nombre: str) -> None:
    """Corrige el nombre de un proveedor de compras. Sin historial: es un tipeo, no otro proveedor.

    El CÓDIGO no se toca nunca: codigo_puesto es la identidad (unique en
    la base), y cambiarlo sería mover todas las compras del proveedor a
    otro. Un código mal tipeado no se renombra — se da de baja.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE proveedores SET nombre = %s, actualizado_en = now() WHERE id = %s",
                (nombre, proveedor_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Ese proveedor ya no existe.")
        conexion.commit()
    finally:
        conexion.close()


def cambiar_actividad_proveedor(proveedor_id: int, activo: bool) -> None:
    """Da de baja (activo=False) o vuelve a dar de alta (activo=True) un proveedor de compras.

    Una sola función para los dos sentidos: es el mismo UPDATE, y partirlo
    en dos sería escribir dos veces la misma regla. No valida nada contra
    las compras a propósito — la baja no borra ni bloquea, solo saca del
    selector de carga (ver listar_proveedores).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE proveedores SET activo = %s, actualizado_en = now() WHERE id = %s",
                (activo, proveedor_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Ese proveedor ya no existe.")
        conexion.commit()
    finally:
        conexion.close()


def obtener_proveedor(proveedor_id: int) -> dict | None:
    """Devuelve un proveedor por id, o None si no existe."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, codigo_puesto, nombre FROM proveedores WHERE id = %s",
                (proveedor_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def _condiciones_buscar_compras(fecha_desde, fecha_hasta, proveedor_id, articulo_id) -> tuple[list[str], list]:
    """El WHERE dinámico de Buscar Compras, compartido entre la búsqueda y su contador."""
    condiciones = ["c.fecha_operacion BETWEEN %s AND %s"]
    parametros: list = [fecha_desde, fecha_hasta]
    if proveedor_id is not None:
        condiciones.append("c.proveedor_id = %s")
        parametros.append(proveedor_id)
    if articulo_id is not None:
        condiciones.append("c.articulo_id = %s")
        parametros.append(articulo_id)
    return condiciones, parametros


def contar_compras_buscadas(
    fecha_desde, fecha_hasta, proveedor_id: int | None = None, articulo_id: int | None = None
) -> int:
    """Cuántas compras matchean los filtros de Buscar Compras — para el aviso "primeras N de M"."""
    condiciones, parametros = _condiciones_buscar_compras(fecha_desde, fecha_hasta, proveedor_id, articulo_id)
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM compras c WHERE {' AND '.join(condiciones)}", parametros)
            (total,) = cursor.fetchone()
        return int(total)
    finally:
        conexion.close()


def buscar_compras(
    fecha_desde,
    fecha_hasta,
    proveedor_id: int | None = None,
    articulo_id: int | None = None,
    limite: int | None = None,
) -> list[dict]:
    """Busca compras por rango de fechas (obligatorio) y, opcionalmente, por proveedor y/o artículo.

    Base de la pantalla Buscar Compras y del export a PDF/Excel — WHERE
    dinámico según qué filtros opcionales vinieron.

    limite: tope de filas para la PANTALLA (un rango ancho no puede tirar
    miles de filas al celular; el aviso lo arma la ruta con
    contar_compras_buscadas). Los exports pasan None: un archivo
    incompleto en silencio sería peor que uno pesado.

    Cantidad/contenido/kilos/fracción vienen con el valor REAL (pesado por
    Depósito al recepcionar) si ya existe, si no el estimado que cargó el
    comprador — ver recepcionar_compra. Quien llama sigue leyendo
    "cantidad_cajones" etc. como si fuera la única columna, sin saber nada
    de esta sustitución.
    """
    condiciones, parametros = _condiciones_buscar_compras(fecha_desde, fecha_hasta, proveedor_id, articulo_id)
    tope_sql = ""
    if limite is not None:
        tope_sql = "LIMIT %s"
        parametros = parametros + [limite]

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.id, c.fecha_operacion, a.nombre AS articulo_nombre, a.unidad_compra, a.unidad_conteo,
                c.segunda_por_cajon, c.segunda_por_cajon_real,
                       p.nombre AS proveedor_nombre,
                       p.codigo_puesto AS proveedor_codigo_puesto,
                       COALESCE(c.cantidad_cajones_real, c.cantidad_cajones) AS cantidad_cajones,
                       COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon) AS contenido_por_cajon,
                       COALESCE(c.cantidad_kilos_real, c.cantidad_kilos) AS cantidad_kilos,
                       COALESCE(c.cantidad_fraccion_real, c.cantidad_fraccion) AS cantidad_fraccion,
                       c.importe, c.sena, c.tipo_retiro,
                       -- Los dos que deciden si esta compra puede recibir la
                       -- marca "vino armada" a mano: solo una recepcionada y
                       -- todavía sin marca. La pantalla no re-deriva la
                       -- condición de otra columna.
                       c.estado, c.ficha_en_origen_id,
                       -- Y LOS DOS QUE FALTABAN para que el menú sepa los
                       -- MISMOS motivos que la pantalla de destino (ver
                       -- core/vino_armada.py). `fecha_del_lote` sale de
                       -- procesada_el con la MISMA expresión con que el FIFO
                       -- fecha el lote, no de fecha_operacion.
                       {_SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col='c.procesada_el')} AS fecha_del_lote,
                       COALESCE(cons.bultos, 0) AS bultos_consumidos,
                       EXISTS (SELECT 1 FROM fotos_guia fg WHERE fg.guia_id = c.guia_id) AS tiene_comanda,
                       -- LA SEGUNDA FOTO, y cuelga de la COMPRA y no de la
                       -- guía: la comanda es el papel del proveedor y es una
                       -- por guía (varios artículos comparten el archivo); el
                       -- pesaje es de ESTE artículo sobre la balanza y no se
                       -- comparte nunca. Por eso son dos EXISTS con dos
                       -- claves distintas y no un `or`.
                       EXISTS (SELECT 1 FROM fotos_recepcion fr WHERE fr.compra_id = c.id) AS tiene_pesaje
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                -- AGRUPADO UNA VEZ, NO UN LATERAL POR FILA, y la diferencia
                -- se midió: con 483 compras y 33.000 consumos, el lateral
                -- tarda 230ms sin índice y 71ms CON un índice nuevo por
                -- compra_id; agrupando una vez son 4ms y no hace falta
                -- ningún índice. O sea que el índice habría "arreglado" el
                -- síntoma dejando puesta la forma cara — la forma natural de
                -- escribirlo es la que cuesta. Si alguien lo vuelve a un
                -- lateral, medir antes de creerle.
                LEFT JOIN (
                    SELECT rc.compra_id, SUM(rc.bultos) AS bultos
                      FROM reprocesos_consumos rc
                      JOIN reprocesos r ON r.id = rc.reproceso_id
                     WHERE rc.origen = 'compra' AND r.anulado_el IS NULL
                     GROUP BY rc.compra_id
                ) cons ON cons.compra_id = c.id
                WHERE {" AND ".join(condiciones)}
                ORDER BY c.fecha_operacion DESC, p.codigo_puesto, c.cargado_el
                {tope_sql}
                """,
                parametros,
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
            compras = [dict(zip(columnas, fila)) for fila in filas]

            # EL MOTIVO SE RESUELVE ACÁ, con el corte leído UNA vez y con la
            # MISMA función que usa la pantalla de destino. Puesto en la
            # plantilla serían dos reglas —que es de donde salió este bug— y
            # puesto en la ruta lo perdería el export, que llama derecho a
            # esta función.
            corte = _fecha_corte(cursor)
            for compra in compras:
                compra["motivo_vino_armada"] = motivo_para_no_marcar_armada(
                    {**compra, "bultos": compra["cantidad_cajones"]}, corte
                )
        return compras
    finally:
        conexion.close()


def listar_compras_para_costeo(fecha_desde, fecha_hasta) -> list[dict]:
    """Compras entre dos fechas (inclusive) con los datos crudos que necesita el motor de costeo.

    No filtra por importe: trae también las compras sin precio (importe
    NULL), para que quien llame decida cómo tratarlas (hoy, el "pegamento"
    en app/costeo.py las excluye del cálculo pero cuenta cuántas quedaron
    afuera por artículo). Incluye fecha_operacion: hace falta para poder
    agrupar las compras por día y reconstruir ventanas de costeo ancladas en
    una fecha puntual (ej. costo actual vs. costo anterior).

    Las cuatro cantidades vienen con el valor REAL (pesado/contado por
    Depósito) si ya existe, si no el estimado — ver recepcionar_compra. Esa
    sustitución alcanza sola para que el costo, el precio sugerido y la
    utilidad aproximada usen el real en cuanto existe, sin tocar ninguna
    fórmula en app/costeo.py.

    LAS DOS MAGNITUDES VIAJAN JUNTAS, y ese es el modelo: una compra
    declara kilos y —cuando el artículo tiene unidad_conteo— también un
    conteo (unidades o cubetas). app/costeo.py divide por UNA de las dos,
    la que pida la unidad de venta de cada ficha (ver
    app.costeo.magnitud_de_la_ficha). La que la compra no declaró vuelve
    en NULL, y eso NO es un cero: es "esta compra no se puede costear en
    esa unidad", que es el caso de todas las compras anteriores al modelo.
    Por eso vienen las dos y decide quien costea, no esta consulta.

    Para excluir compras del costeo manda SOLO el veredicto de Depósito
    (regla fija pedida el 19/08/2026): se excluyen las rechazadas
    (estado = 'rechazado') y las que nunca ingresaron al depósito
    (estado = 'no_ingresado') — no hay mercadería real detrás. Lo que
    diga Logística NO cuenta: un retiro cancelado (estado_retiro =
    'cancelado') no saca la compra del cálculo, porque el retiro no es
    el dato real — el dato real es lo que Depósito recibió o no recibió.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.articulo_id, a.nombre AS articulo_nombre, c.fecha_operacion,
                       COALESCE(c.cantidad_cajones_real, c.cantidad_cajones) AS cantidad_cajones,
                       COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon) AS contenido_por_cajon,
                       COALESCE(c.cantidad_kilos_real, c.cantidad_kilos) AS cantidad_kilos,
                       COALESCE(c.cantidad_fraccion_real, c.cantidad_fraccion) AS cantidad_fraccion,
                       c.importe, c.cargado_el
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.fecha_operacion BETWEEN %s AND %s
                  AND c.estado IS DISTINCT FROM 'rechazado'
                  AND c.estado IS DISTINCT FROM 'no_ingresado'
                ORDER BY a.nombre
                """,
                (fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_precios_vigentes_por_cliente_en_fechas(cliente_id: int, fechas) -> dict:
    """El precio vigente de cada ficha del cliente a VARIAS fechas, en una consulta.

    Devuelve {fecha: [precios vigentes a esa fecha]}, con una entrada por
    cada fecha pedida. La resolución de "vigente" es la MISMA consulta de
    siempre, palabra por palabra: acá va adentro de un LATERAL que la corre
    una vez por fecha. No se reimplementa en Python cuál es el precio
    vigente — eso es justo lo que movería un número sin que se note.

    La usa la Rentabilidad (real y teórica), que ancla el precio a cada
    fecha con pedido del rango: antes abría cinco conexiones POR FECHA.
    """
    fechas_unicas = sorted(set(fechas))
    if not fechas_unicas:
        return {}
    por_fecha = {fecha: [] for fecha in fechas_unicas}
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.fecha, p.ficha_id, p.articulo_id, p.precio, p.vigente_desde
                FROM unnest(%s::date[]) AS f(fecha)
                CROSS JOIN LATERAL (
                    SELECT DISTINCT ON (ficha_id) ficha_id, articulo_id, precio, vigente_desde
                    FROM precios_venta_historial
                    WHERE cliente_id = %s AND vigente_desde <= f.fecha AND ficha_id IS NOT NULL
                    ORDER BY ficha_id, vigente_desde DESC
                ) p
                """,
                (fechas_unicas, cliente_id),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            for fila in cursor.fetchall():
                precio = dict(zip(columnas, fila))
                por_fecha[precio.pop("fecha")].append(precio)
        return por_fecha
    finally:
        conexion.close()


def listar_precios_vigentes_por_cliente(cliente_id: int, fecha_referencia) -> list[dict]:
    """Precio vigente de cada FICHA de un cliente, a una fecha dada.

    La clave de venta es la ficha, no el artículo: dos fichas del mismo
    artículo y cliente (Banana Bolivia y Banana Ecuador para Día) tienen
    su propio precio. Mientras haya una sola ficha por artículo, esto
    devuelve exactamente lo mismo que cuando la clave era el artículo.

    "Vigente" es la fila de precios_venta_historial con vigente_desde más
    reciente que ya llegó a fecha_referencia (mismo patrón que el
    descuento/utilidad vigente de clientes_parametros_historial). Una
    ficha sin ninguna fila con vigente_desde <= fecha_referencia
    simplemente no aparece en el resultado — no tiene precio vigente todavía.

    Los precios huérfanos (ficha_id NULL: su ficha se borró o cambió de
    artículo) quedan afuera — hoy tampoco se leían, porque nadie los
    buscaba por un artículo que ya ninguna ficha usa.

    Trae articulo_id y vigente_desde además de ficha_id y precio: el
    artículo lo usan las pantallas para mostrar y agrupar, y vigente_desde
    lo usa la exportación a PDF/Excel para saber si un precio es "nuevo"
    (cambió justo en la fecha consultada).
    """
    return listar_precios_vigentes_por_cliente_en_fechas(cliente_id, [fecha_referencia])[fecha_referencia]


def listar_precios_anteriores_por_cliente(cliente_id: int, fecha_referencia) -> list[dict]:
    """El precio que tenía cada FICHA ANTES del que hoy está vigente (para la columna "Precio anterior"
    de la Lista de Precios en Excel — ver core.exportar_precios).

    Mismo criterio de "vigente" que listar_precios_vigentes_por_cliente,
    pero un escalón atrás: de las filas de precios_venta_historial con
    vigente_desde <= fecha_referencia, la vigente es la de vigente_desde
    más reciente (fila #1) — esto devuelve la fila #2, la que regía justo
    antes de esa. Una ficha con una sola fila cargada (nunca cambió de
    precio) o sin ninguna simplemente no aparece — no hay "anterior" que
    mostrar.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT ficha_id, articulo_id, precio FROM (
                    SELECT ficha_id, articulo_id, precio,
                           ROW_NUMBER() OVER (PARTITION BY ficha_id ORDER BY vigente_desde DESC) AS orden
                    FROM precios_venta_historial
                    WHERE cliente_id = %s AND vigente_desde <= %s AND ficha_id IS NOT NULL
                ) filas_ordenadas
                WHERE orden = 2
                """,
                (cliente_id, fecha_referencia),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def guardar_precios_cliente(cliente_id: int, cambios: list[dict], vigente_desde, foto_ruta: str | None = None) -> None:
    """Agrega a precios_venta_historial SOLO las filas de precio que realmente cambiaron.

    cambios: [{"ficha_id", "precio"}, ...] — ya calculado por
    core.precios_venta.calcular_cambios_de_precios a partir de lo que
    cambió en el formulario. El precio es de la FICHA (la clave de venta):
    dos fichas del mismo artículo y cliente tienen precios distintos.

    El articulo_id de la fila NO viaja desde la pantalla: sale de la
    propia ficha dentro del INSERT, así no puede quedar apuntando a un
    artículo que no es el de su ficha.

    `vigente_desde` ES OBLIGATORIO Y NO TIENE DEFAULT, aunque casi siempre
    sea hoy. Con un default, el llamador que se olvide de pasarlo escribe
    con fecha de hoy **en silencio** y el precio retroactivo queda fechado
    mal: nadie se entera, porque una fila con la fecha de hoy es
    exactamente lo que se veía antes. Sin default, olvidarlo es un
    TypeError — la misma razón por la que la guarda de una estructura que
    gana un campo se pone donde rompe y no donde calla.

    **Y VIENE EN HORA ARGENTINA, calculado por quien llama.** Hasta el
    14/09 esta consulta decía `CURRENT_DATE`, que es la fecha del SERVIDOR
    de la base — mientras que todas las lecturas resuelven el vigente con
    `_hoy_argentina()`. Son dos relojes para el mismo hecho, y con la base
    en UTC se separan todas las noches a partir de las 21:00 de Argentina:
    lo cargado a esa hora quedaba fechado MAÑANA y no regía hoy. Ahora la
    fecha entra como parámetro y la decide el mismo reloj que la lee.

    El precio viejo NUNCA se pisa: cada carga agrega su fila. Si ya existe
    una para esa misma ficha Y esa misma fecha —segunda edición del mismo
    día, o una corrección con fecha anterior sobre un día ya cargado— se
    actualiza esa en vez de duplicarla. Eso último no es un efecto
    colateral: **es el mecanismo con el que se corrige un precio mal
    cargado de un día pasado**, y es la única forma de hacerlo sin borrar
    filas.

    foto_ruta es la ruta del archivo (foto/PDF/Excel) del bucket "comandas"
    del que salieron estos precios (ver "Cargar Foto Precios") — None para
    la Carga Manual, que no tiene archivo. En un conflicto, solo se pisa
    foto_ruta si el nuevo valor no es None: una corrección manual no debe
    borrar la trazabilidad de una carga por archivo anterior de esa fecha.
    """
    if not cambios:
        return

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            for cambio in cambios:
                cursor.execute(
                    """
                    INSERT INTO precios_venta_historial
                        (ficha_id, articulo_id, cliente_id, precio, vigente_desde, foto_ruta)
                    SELECT fl.id, fl.articulo_id, %s, %s, %s, %s
                    FROM fichas_logistica fl
                    WHERE fl.id = %s AND fl.cliente_id = %s
                    ON CONFLICT (ficha_id, vigente_desde)
                    DO UPDATE SET
                        precio = EXCLUDED.precio,
                        foto_ruta = COALESCE(EXCLUDED.foto_ruta, precios_venta_historial.foto_ruta)
                    """,
                    (cliente_id, cambio["precio"], vigente_desde, foto_ruta, cambio["ficha_id"], cliente_id),
                )
        conexion.commit()
    finally:
        conexion.close()


def listar_historial_de_precios_de_ficha(ficha_id: int, cliente_id: int) -> list[dict]:
    """TODAS las filas de precio de una ficha, de la vigencia más nueva a la más vieja.

    Es la única lectura que muestra la tabla como es en vez de resolverla:
    el resto del sistema pregunta "¿qué precio regía el día X?" y se queda
    con una fila. Acá se ven las filas, que es lo que hace falta para poder
    corregir — sin esto se corrige a ciegas.

    DEVUELVE `creado_en` AL LADO DE `vigente_desde`, y ésas son dos cosas
    distintas: cuándo se escribió la fila y desde cuándo rige. **Desde el
    14/09 se pueden separar de verdad** —la carga elige la fecha— y la
    diferencia entre las dos es lo que delata una carga retroactiva: es la
    única marca que queda de que la hubo. (Hasta ese día coincidían siempre
    porque el INSERT escribía una fecha fija, y esta frase decía eso.)

    VA CON cliente_id aunque `ficha_id` ya sea único: la ficha viene de la
    query string, y sin esa condición un id de otro cliente devolvería su
    historial de precios. La guarda va en el SELECT y no en el llamador.

    El orden es por `vigente_desde` y no hace falta desempate: el unique
    (ficha_id, vigente_desde) garantiza que no haya dos filas del mismo día
    para la misma ficha.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT precio, vigente_desde, creado_en, foto_ruta
                FROM precios_venta_historial
                WHERE ficha_id = %s AND cliente_id = %s
                ORDER BY vigente_desde DESC
                """,
                (ficha_id, cliente_id),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_vigencias_de_precios(cliente_id: int, desde, hasta) -> list[dict]:
    """Una fila por CAMBIO de precio que estuvo rigiendo en la ventana, con desde y hasta.

    Es el listado para facturar para atrás: la que factura busca la fecha
    ADENTRO de un rango en vez de leer una grilla de treinta columnas.
    Medido el 14/09 sobre las dos bases: de 43 fichas del cliente grande,
    18 cambiaron de precio en 30 días — o sea que una grilla por día serían
    25 filas de treinta columnas idénticas.

    EL PRECIO QUE YA REGÍA ANTES DE `desde` ENTRA, y es el error natural de
    esta forma: con un `vigente_desde BETWEEN` esas 25 fichas desaparecerían
    del listado y el primer día del rango quedaría vacío para más de la
    mitad. Acá no hay un caso especial que se pueda olvidar — sale de la
    condición de INTERSECCIÓN, que es la que de verdad se está preguntando:

        la vigencia [vigente_desde, proximo - 1] toca [desde, hasta]
          <=>  vigente_desde <= hasta   Y   (proximo es NULL  o  proximo > desde)

    `vigente_hasta` es el día ANTERIOR al próximo cambio, o NULL cuando no
    hay próximo — eso es "sigue vigente" y no "no se sabe". Sin esa columna,
    para saber hasta cuándo rigió un precio hay que mirar la fila siguiente,
    que es justo lo que un listado impreso hace incómodo.

    NO SE RECORTA `vigente_hasta` a la ventana a propósito: que una vigencia
    diga que termina después del rango es información verdadera —cubre lo que
    sigue— y recortarla haría que dos rangos distintos muestren fechas
    distintas para el mismo hecho.

    El orden es por ficha y, adentro de cada una, CRONOLÓGICO: se busca la
    ficha y después se recorre el tiempo. Es al revés que las alertas de
    reclamo, que van de lo más nuevo a lo más viejo porque ahí lo viejo ya no
    se puede reclamar; acá ninguna fila vence, se busca una fecha.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                WITH vigencias AS (
                    SELECT ficha_id, precio, vigente_desde,
                           LEAD(vigente_desde) OVER (
                               PARTITION BY ficha_id ORDER BY vigente_desde
                           ) AS proximo
                    FROM precios_venta_historial
                    WHERE cliente_id = %s AND ficha_id IS NOT NULL
                      AND vigente_desde <= %s
                )
                SELECT ficha_id, precio, vigente_desde, (proximo - 1) AS vigente_hasta
                FROM vigencias
                WHERE proximo IS NULL OR proximo > %s
                ORDER BY ficha_id, vigente_desde
                """,
                (cliente_id, hasta, desde),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_costos_envases_vigentes_en_fechas(fechas) -> dict:
    """El costo vigente de cada envase a VARIAS fechas, en una consulta.

    Mismo criterio que listar_precios_vigentes_por_cliente_en_fechas: la
    consulta de "vigente" es la de siempre, adentro de un LATERAL que la
    corre una vez por fecha.
    """
    fechas_unicas = sorted(set(fechas))
    if not fechas_unicas:
        return {}
    por_fecha = {fecha: [] for fecha in fechas_unicas}
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.fecha, e.envase_id, e.costo
                FROM unnest(%s::date[]) AS f(fecha)
                CROSS JOIN LATERAL (
                    SELECT DISTINCT ON (envase_id) envase_id, costo
                    FROM envases_costo_historial
                    WHERE vigente_desde <= f.fecha
                    ORDER BY envase_id, vigente_desde DESC
                ) e
                """,
                (fechas_unicas,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            for fila in cursor.fetchall():
                costo = dict(zip(columnas, fila))
                por_fecha[costo.pop("fecha")].append(costo)
        return por_fecha
    finally:
        conexion.close()


def listar_costos_envases_vigentes(fecha_referencia) -> list[dict]:
    """Costo vigente de cada envase, a una fecha dada (mismo patrón "vigente" que el resto).

    Los envases son un catálogo compartido (no pertenecen a ningún
    cliente): envase_id alcanza para identificar cada uno.
    """
    return listar_costos_envases_vigentes_en_fechas([fecha_referencia])[fecha_referencia]


def listar_compras_por_fecha_y_proveedor(fecha_operacion, proveedor_id: int) -> list[dict]:
    """Devuelve las compras de un proveedor puntual en una fecha, para mostrar lo cargado hasta ahora."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, a.nombre AS articulo_nombre, c.cantidad_cajones, c.contenido_por_cajon,
                       c.importe, c.sena
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.fecha_operacion = %s AND c.proveedor_id = %s
                ORDER BY c.cargado_el
                """,
                (fecha_operacion, proveedor_id),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_compra(compra_id: int) -> dict | None:
    """Devuelve una compra por id (para precargar el formulario de edición), o None si no existe."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, c.articulo_id, a.nombre AS articulo_nombre,
                       c.proveedor_id, p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.guia_id, c.cantidad_cajones, c.contenido_por_cajon,
                       c.cantidad_kilos, c.cantidad_fraccion, c.importe, c.sena, c.tipo_retiro,
                       c.estado, c.estado_retiro
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def obtener_detalle_compra(compra_id: int) -> dict | None:
    """Devuelve una compra con toda su historia, para la pantalla de Detalle (solo lectura).

    A diferencia de obtener_compra (que trae lo justo para precargar el
    formulario de edición), esto trae todo lo que hay guardado de las
    tres etapas de la compra: lo cargado por el comprador, el retiro en
    Logística y la recepción en Depósito — más cargado_el (cuándo se
    cargó la compra, existe desde el diseño original) y el punto de
    guía, para poder mostrar "105.2".
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, c.cargado_el,
                       c.articulo_id, a.nombre AS articulo_nombre, a.unidad_compra, a.unidad_conteo,
                       c.segunda_por_cajon, c.segunda_por_cajon_real,
                       c.proveedor_id, p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.guia_id, c.guia_punto,
                       c.cantidad_cajones, c.contenido_por_cajon, c.importe, c.sena, c.tipo_retiro,
                       c.cantidad_kilos, c.cantidad_fraccion,
                       c.cantidad_kilos_real, c.cantidad_fraccion_real,
                       c.estado_retiro, c.retiro_procesado_el, c.retiro_origen, c.cantidad_cajones_retirada,
                       c.estado, c.procesada_el,
                       c.cantidad_cajones_real, c.contenido_por_cajon_real, c.cantidad_fraccion_real,
                       c.cantidad_cajones_rechazada, c.motivo_rechazo,
                       -- LA MARCA DE LA CARGA RETROACTIVA, derivada y sin
                       -- columna nueva: `cargado_el` es cuándo se tipeó y
                       -- `procesada_el` cuándo entró al stock. En una compra
                       -- normal caen el mismo día; si la de entrada es
                       -- ANTERIOR, alguien la fechó para atrás desde
                       -- Gerencia. Sin esto, dentro de tres meses la fila se
                       -- ve igual que una normal fechada un día en que nadie
                       -- cargó nada.
                       --
                       -- Las dos pasadas a hora argentina antes de comparar:
                       -- crudas, una carga de las 22:30 y una entrada del
                       -- mismo día darían días distintos en UTC.
                       ((c.procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                        < (c.cargado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date)
                           AS cargada_retroactiva
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


# Tipos de retiro que los maneja un tercero que nunca entra al sistema: nadie
# tilda nunca esas compras en Logística, así que nacen con el retiro hecho.
# El valor es el retiro_origen con el que se marcan (prefijo automatico_: lo
# marcó el sistema, no una persona).
ORIGEN_RETIRO_AUTOMATICO_POR_TIPO = {"Carro": "automatico_carro", "Cooperativa": "automatico_cooperativa"}

# Los mismos valores de arriba, listos para meter en un IN de SQL. Se arman
# DESDE la constante y no se reescriben a mano: si mañana se agrega un tipo
# automático, esto lo acompaña solo. Son literales del código, no dato de
# usuario — no hay nada que escapar acá.
_ORIGENES_RETIRO_AUTOMATICO_SQL = ", ".join(
    f"'{origen}'" for origen in sorted(ORIGEN_RETIRO_AUTOMATICO_POR_TIPO.values())
)


# POR DÓNDE entró el importe que la compra tiene hoy. Los tres valores son los
# tres caminos que escriben `compras.importe`, enumerados con `ast` y no de
# memoria: el alta (_insertar_compra_con_guia), la edición
# (actualizar_precio_compra) y Compras sin precio (actualizar_importe_compra).
#
# LA LISTA ES LA MISMA QUE LA DEL CHECK de db/importe_1_cuando_y_por_donde.sql,
# y eso lo cuida un test que LEE el `.sql` en vez de copiarlo: una lista copiada
# envejece en silencio, y la que se separe no falla —deja entrar un origen que
# la base rechaza, o al revés, y recién se ve cuando alguien carga.
ORIGENES_DEL_IMPORTE = ("alta", "edicion", "pendiente")


def _sello_del_importe(origen: str, importe) -> tuple[str, tuple]:
    """Las dos columnas que dicen CUÁNDO y POR DÓNDE entró el importe que la fila tiene HOY, para pegar en un UPDATE.

    Devuelve el fragmento de `SET` y sus parámetros, en ese orden. Lo usan
    los DOS caminos que actualizan un importe ya existente; el alta lo
    escribe distinto y a propósito (ver _insertar_compra_con_guia).

    SOLO SELLA SI EL NÚMERO CAMBIÓ, y no es una prolijidad: la pantalla de
    Editar Compra llama a actualizar_precio_compra en CADA guardado, aunque
    lo único que se haya tocado sea la cantidad. Sin el `IS DISTINCT FROM`,
    corregir los cajones de una compra le fecharía el precio como
    renegociado hoy — o sea que la columna mentiría justo en el caso para el
    que existe, y sin que nada se vea raro en ninguna pantalla.

    Y SI EL IMPORTE SE BORRA, el par vuelve a NULL: un "puesto el 19/09 por
    edición" sobre una fila sin precio afirma algo que no pasó. Es la misma
    regla que el comment de la columna ya promete —NULL = sin precio
    todavía— escrita donde se cumple.

    En un UPDATE de Postgres, una columna nombrada a la derecha de un SET
    vale lo VIEJO, así que `importe IS NOT DISTINCT FROM %s` compara lo que
    hay contra lo que llega sin tener que leer la fila antes: una sola
    sentencia, sin ventana entre el SELECT y el UPDATE.

    El `::numeric` no es decorativo: `%s IS NULL` suelto no tiene de dónde
    sacar el tipo y Postgres lo rechaza con "could not determine data type".
    """
    if origen not in ORIGENES_DEL_IMPORTE:
        raise ValueError(f"Origen de importe desconocido: {origen}")
    fragmento = (
        "importe_puesto_el = CASE WHEN importe IS NOT DISTINCT FROM %s THEN importe_puesto_el "
        "WHEN %s::numeric IS NULL THEN NULL ELSE now() END, "
        "importe_origen = CASE WHEN importe IS NOT DISTINCT FROM %s THEN importe_origen "
        f"WHEN %s::numeric IS NULL THEN NULL ELSE '{origen}' END"
    )
    return fragmento, (importe, importe, importe, importe)

# La condición de "esta compra todavía se puede borrar", escrita UNA sola vez
# y en SQL. La usan el borrado de a uno (eliminar_compra) y el Cancelar del
# día (eliminar_compras_del_dia_por_proveedor). Antes vivía dos veces —tres
# `if` en Python y un WHERE en la otra función—, y la excepción de abajo
# habría entrado en una sola: el borrado de a uno y el Cancelar habrían
# empezado a decir cosas distintas de la misma compra.
#
# Lo que bloquea: recepcionada (tiene kilaje real pesado y creó lote), "No
# ingresó" (un registro de Depósito que el comprador no puede hacer
# desaparecer borrando la compra) y retirada (alguien la sacó del puesto).
#
# LA EXCEPCIÓN, y es toda la razón de este cambio: un retiro de origen
# automático NO es un hecho, es un default del alta. crear_compra marca
# 'retirado' en el MISMO INSERT para Carro y Cooperativa, porque las maneja un
# tercero que nunca entra al sistema y "se asume que retira" — nadie verificó
# nada, y esas compras jamás aparecen en la cola de Logística. Mientras la
# compra siga 'pendiente' (Depósito todavía no se expidió), ese retiro
# supuesto no puede impedir que se borre una compra recién cargada: hasta
# ahora una de Cooperativa nacía imposible de borrar, desde el segundo cero.
#
# Las dos condiciones van JUNTAS. Solo el origen dejaría borrar una rechazada
# de Cooperativa, que hoy lo único que la bloquea es justamente el retiro (no
# hay guarda por estado = 'rechazado'), y eso es cambiar una política, no
# arreglar un bug. Solo el estado dejaría borrar una pendiente que Logística
# tildó a mano, que sí es un hecho: una persona vio que salió del puesto.
#
# estado NULL (compras de antes de que existiera Recepción) no es 'pendiente':
# siguen bloqueadas, a propósito.
_SQL_COMPRA_BORRABLE = f"""
    estado IS DISTINCT FROM 'recepcionado'
    AND estado IS DISTINCT FROM 'no_ingresado'
    AND (
        estado_retiro IS DISTINCT FROM 'retirado'
        OR (estado = 'pendiente' AND retiro_origen IN ({_ORIGENES_RETIRO_AUTOMATICO_SQL}))
    )
"""


def crear_compra(
    fecha_operacion,
    articulo_id: int,
    proveedor_id: int,
    cantidad_cajones: float,
    contenido_por_cajon: float,
    cantidad_kilos: float | None,
    cantidad_fraccion: float | None,
    importe: float | None,
    sena: float | None,
    tipo_retiro: str,
    foto_ruta: str | None = None,
    ingreso_directo_deposito: bool = False,
    recepcionada_el=None,
    ficha_en_origen_id: int | None = None,
    *,
    segunda_por_cajon: float | None,
) -> None:
    """Inserta una compra cargada por el comprador, con su guía asignada.

    `segunda_por_cajon` ES KEYWORD-ONLY Y NO TIENE DEFAULT, a propósito: con
    un default, un llamador que se lo olvidara guardaría la compra con la
    columna en NULL — que se ve EXACTAMENTE IGUAL que una compra anterior al
    modelo de dos magnitudes, o sea un hueco legítimo. Sin default, olvidarlo
    es un TypeError. Es el agujero de `ficha_en_origen_id` del 12/09, cerrado
    por construcción en vez de por un grep.

    foto_ruta es la ruta (en el bucket "comandas" de Supabase Storage) de
    la foto de la comanda de la que salió este renglón — None si la
    compra se cargó a mano, o si la subida de la foto falló (la foto es un
    extra, nunca bloquea guardar la compra). Cuando varios renglones salen
    de la misma foto, comparten la misma foto_ruta.

    La guía (para Depósito) es una por proveedor por día: se crea o
    reusa la fila de guias_compra para (fecha_operacion, proveedor_id) con
    ON CONFLICT DO NOTHING, y el punto dentro de la guía (el ".1"/".2"/
    ".3") es la cantidad de compras que ya tiene esa guía más uno — se
    graba una sola vez acá, nunca se recalcula después, así que borrar un
    renglón más adelante no renumera a los demás. Todo en la misma
    transacción que el INSERT de la compra. Igual con o sin
    ingreso_directo_deposito: la guía es la misma cuenta, no importa por
    dónde entró la mercadería.

    estado arranca en 'pendiente' (queda a la espera de Recepción en
    Depósito) — se escribe acá explícitamente, a propósito SIN default a
    nivel de columna: así las compras cargadas antes de este cambio quedan
    con estado NULL para siempre, sin aparecer nunca en Recepción.

    estado_retiro arranca también en 'pendiente' (queda a la espera de
    Logística, que retira del puesto en el Mercado ANTES de que la
    mercadería llegue al depósito — ver listar_compras_pendientes_retiro),
    mismo criterio sin default de columna.

    ingreso_directo_deposito=True (ver /deposito/ingresar): la mercadería
    ya está físicamente en el depósito cuando se carga — alguien del
    depósito la tiene en la mano, ya pesada/contada, sin haber pasado por
    Logística ni por Recepción como pasos separados. En ese caso la
    compra nace directamente 'recepcionado'/'retirado' (con procesada_el
    y retiro_procesado_el en ese mismo instante, retiro_origen
    'ingreso_directo' — nunca 'deposito', que significa otra cosa: auto-
    retiro de algo que sí pasó por el puesto del Mercado), y las
    columnas _real quedan iguales a cantidad_cajones/contenido_por_cajon:
    no hay estimado previo, quien la carga la está viendo y pesando.
    importe/sena típicamente van None acá (el precio lo carga el
    comprador después), pero la función no lo fuerza — eso lo decide
    quien llama.

    tipo_retiro 'Carro' o 'Cooperativa' (ver ORIGEN_RETIRO_AUTOMATICO_POR_
    TIPO): los maneja un tercero que nunca entra al sistema — se le pasa la
    distribución para que vaya a buscar y se ASUME que retira. La compra
    nace con el retiro ya hecho (estado_retiro 'retirado',
    retiro_procesado_el ahora, retiro_origen automatico_carro/
    automatico_cooperativa) y nunca aparece pendiente en Logística. La
    recepción en Depósito sigue siendo la normal (estado 'pendiente'), sin
    valores reales: eso lo completa Depósito cuando la mercadería llega.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # ANTES de tocar nada: si la fecha no pasa la guarda del corte,
            # no se crea ni la guía. En su propia línea y no adentro de la
            # lista de argumentos, donde el orden de evaluación queda
            # escondido y se lee como si corriera después.
            recepcionada_el = _recepcion_retroactiva_validada(
                cursor, recepcionada_el, ingreso_directo_deposito
            )
            _insertar_compra_con_guia(
                cursor,
                fecha_operacion,
                articulo_id,
                proveedor_id,
                cantidad_cajones,
                contenido_por_cajon,
                cantidad_kilos,
                cantidad_fraccion,
                importe,
                sena,
                tipo_retiro,
                foto_ruta,
                ingreso_directo_deposito=ingreso_directo_deposito,
                recepcionada_el=recepcionada_el,
                ficha_en_origen_id=ficha_en_origen_id,
                segunda_por_cajon=segunda_por_cajon,
            )
        conexion.commit()
    finally:
        conexion.close()


def _recepcion_retroactiva_validada(cursor, recepcionada_el, ingreso_directo_deposito: bool):
    """La fecha de recepción elegida, validada contra el CORTE. None = ahora.

    ESTRICTAMENTE POSTERIOR AL CORTE, y el día del corte también se
    rechaza. No es un margen de seguridad: es la asimetría de siempre —el
    conteo del corte se toma A LA TARDE, así que todo lo de ese día ya está
    adentro de la foto—. El lote del FIFO pide que la fecha argentina de
    `procesada_el` sea POSTERIOR al corte, y el total NO tiene piso: una
    compra fechada el día del corte o
    antes **suma al total y no existe como lote**: mercadería que el stock
    tiene y el costeo no, saliendo "sin lote" para siempre. Medido el
    09/09 sobre el esquema real, con el corte en 05/09:

        fechada 06/09  -> lote del FIFO SI  · suma al total SI
        fechada 05/09  -> lote del FIFO NO  · suma al total SI   <- se separan
        fechada 04/09  -> lote del FIFO NO  · suma al total SI   <- se separan

    El corte se lee de la base con `_fecha_corte`, que es de donde lo leen
    las otras cuentas: escrito a mano acá sería otra copia, y además es
    distinto en cada empresa.

    Solo tiene sentido en el ingreso directo: en la carga normal la compra
    nace 'pendiente' y la fecha de recepción la pone Depósito al recibirla.
    """
    if recepcionada_el is None:
        return None
    if not ingreso_directo_deposito:
        raise ValueError("La fecha de recepción solo se puede elegir en un ingreso directo.")
    motivo = _motivo_sin_lote_por_el_corte(cursor, recepcionada_el.date())
    if motivo is not None:
        raise ValueError(motivo)
    return recepcionada_el


def _motivo_sin_lote_por_el_corte(cursor, fecha) -> str | None:
    """Por qué esa fecha NO tiene lote del FIFO, o None si lo tiene. Lee el corte de la base.

    VUELVE UN MOTIVO EN VEZ DE LEVANTAR porque los dos que la usan la
    necesitan de formas distintas: la carga retroactiva la traduce a un
    ValueError al escribir, y la pantalla de "vino armada" la muestra ANTES,
    como aviso, para no ofrecer un botón que no puede funcionar. Una guarda
    que solo sabe explotar obliga a escribir la condición una segunda vez
    para poder avisar, y esa segunda copia es la que se separa.

    LA COMPARACIÓN NO ESTÁ ACÁ: vive en `core.vino_armada`, porque el menú
    de Buscar Compras la necesita para QUINIENTAS filas y leer el corte una
    vez por fila sería pagarlo quinientas veces. Esta función es el corte
    leído de la base más esa regla — no una segunda versión de ella. La
    asimetría del día del corte ya se reescribió ocho veces en lugares que
    no se nombran entre sí (CLAUDE.md lleva la lista); ésta no agrega una
    novena.
    """
    return motivo_sin_lote_por_el_corte(fecha, _fecha_corte(cursor))


def _validar_caja_en_origen(cursor, ficha_en_origen_id: int, articulo_id: int) -> None:
    """Levanta ValueError si esa caja no existe o no es del artículo de la compra.

    LA REGLA VIVE ACÁ UNA SOLA VEZ y la llaman los TRES lugares que escriben
    la marca —el alta, la edición y la marcada a mano de una compra ya
    recepcionada—. Escrita en cada uno serían tres, y el día que se separan
    una de las tres deja entrar una ficha de otro artículo: eso inventa cajas
    que no existen y el Cotejo muestra un rojo imposible de explicar.

    Y VA DONDE SE ESCRIBE, no al recepcionar: allá sería tarde —la recepción
    se caería por un error que se cometió días antes, con el camión en la
    puerta— y el que lo cometió no es el que lo sufriría.

    SIN agregado: `fetchone() is None` sobre un `count(*)` nunca es None y no
    distinguiría "no existe" de "existe" (corolario 27).

    Y RECHAZA LA DE ENVASE PERDIDO, que es la que la pantalla dejó de
    ofrecer. Que no se liste no alcanza: un formulario armado a mano entra
    igual, y la marca no falla ruidosamente —la guía R en origen deriva
    `(False, None)`, el conteo de cajas no se mueve y la compra queda
    diciendo que vino en una caja nuestra que no existe—. La guarda va donde
    se ESCRIBE; la pantalla es la forma de cumplirlo cómodo.

    La condición se la pregunta a `envase_derivado_de_la_ficha`: envase
    perdido es su único caso sin caja que declarar. Escribir acá un
    `envase_id is None` propio sería la segunda copia de esa regla, y el día
    que la de allá cambie ésta se queda vieja sin que nada avise.
    """
    cursor.execute(
        "SELECT articulo_id, envase_id, envase_variable "
        "FROM fichas_logistica WHERE id = %s",
        (ficha_en_origen_id,),
    )
    ficha = cursor.fetchone()
    if ficha is None:
        raise ValueError("Esa caja no existe.")
    if ficha[0] != articulo_id:
        raise ValueError("Esa caja es de otro artículo: no puede ser la de esta compra.")
    lleva, _, hay_que_preguntar = envase_derivado_de_la_ficha(
        {"envase_id": ficha[1], "envase_variable": ficha[2]}
    )
    if not (lleva or hay_que_preguntar):
        raise ValueError(
            "Ese producto sale en el cajón del proveedor: no hay caja nuestra "
            "en la que pueda venir armado."
        )


def _insertar_compra_con_guia(
    cursor,
    fecha_operacion,
    articulo_id: int,
    proveedor_id: int,
    cantidad_cajones: float,
    contenido_por_cajon: float,
    cantidad_kilos: float | None,
    cantidad_fraccion: float | None,
    importe: float | None,
    sena: float | None,
    tipo_retiro: str,
    foto_ruta: str | None,
    ingreso_directo_deposito: bool = False,
    carga_token: str | None = None,
    recepcionada_el=None,
    ficha_en_origen_id: int | None = None,
    *,
    segunda_por_cajon: float | None,
) -> int:
    """Inserta UNA compra (con su guía) usando el cursor que le pasan — sin abrir conexión ni commitear. Devuelve su id.

    Es el cuerpo de crear_compra (ver su docstring para el significado de
    cada campo y de las tres ramas), separado para que
    crear_compras_de_comanda pueda insertar varios renglones en UNA sola
    transacción: quien llama decide cuándo commitear.

    carga_token solo viene en compras que salen de una comanda leída por
    foto (ver crear_compras_de_comanda); en la carga manual y en el
    ingreso directo va None.

    recepcionada_el (solo con ingreso_directo_deposito) es CUÁNDO ENTRÓ la
    mercadería, que puede no ser hoy: mercadería que llegó hace días y se
    descubre después que nunca se cargó. None = ahora, que es el caso
    normal. Va a `procesada_el` y a `retiro_procesado_el`, que son las dos
    columnas por las que el stock y el FIFO fechan una compra — la fecha de
    OPERACIÓN no la mira ninguna de las dos cuentas.

    `cargado_el` NO se toca y queda en `now()`: es cuándo se tipeó de
    verdad, y esa diferencia contra `procesada_el` es lo único que después
    dice que esta compra se cargó con fecha retroactiva. Sin eso, dentro de
    tres meses la fila se ve igual que una normal fechada un día en que
    nadie cargó nada.

    ficha_en_origen_id: la compra viene YA ARMADA en caja nuestra y estas son
    las cajas de esa ficha. Lo marca el COMPRADOR, que es el único que lo
    sabe. Se escribe con un UPDATE aparte y no adentro de los tres INSERT: son
    tres listas de columnas distintas, y una columna repetida en las tres es
    tres lugares de los que una rama nueva se puede olvidar. El `RETURNING id`
    sí va en las tres, pero es un sufijo — no se pierde en el medio de una
    lista.

    Y EN EL INGRESO DIRECTO LA GUÍA R SALE ACÁ MISMO, porque esa compra nace
    'recepcionado' y NO PASA POR RECEPCIÓN: si el disparo viviera solo allá,
    estos dos caminos —el de Depósito y el retroactivo de Gerencia— serían dos
    puertas por las que este caso no se puede registrar, y el operario volvería
    a la guía R a mano. Va en la misma transacción que el insert.
    """
    guia_id, guia_punto = _guia_de_compra(cursor, fecha_operacion, proveedor_id)

    # La foto cuelga de la GUÍA, no del renglón: se registra una vez por
    # guía (el ON CONFLICT absorbe los N renglones de la misma comanda).
    if foto_ruta:
        cursor.execute(
            "INSERT INTO fotos_guia (guia_id, foto_ruta) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (guia_id, foto_ruta),
        )


    if ingreso_directo_deposito:
        cursor.execute(
            """
            INSERT INTO compras
                (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro,
                 guia_id, guia_punto, estado, estado_retiro,
                 cantidad_cajones_real, contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real,
                 segunda_por_cajon, segunda_por_cajon_real,
                 procesada_el, retiro_procesado_el, retiro_origen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'recepcionado', 'retirado', %s, %s, %s, %s, %s, %s,
                    COALESCE(%s, now()), COALESCE(%s, now()), 'ingreso_directo')
            RETURNING id
            """,
            (
                fecha_operacion,
                articulo_id,
                proveedor_id,
                cantidad_cajones,
                contenido_por_cajon,
                cantidad_kilos,
                cantidad_fraccion,
                importe,
                sena,
                tipo_retiro,
                guia_id,
                guia_punto,
                cantidad_cajones,
                contenido_por_cajon,
                cantidad_kilos,
                cantidad_fraccion,
                # A LAS DOS, igual que cantidad_fraccion: el ingreso directo
                # entra ya recepcionado y copia el estimado al real. Escribir
                # solo la estimada dejaria la fila real con un hueco que la
                # pantalla muestra como "esta compra no declaro la otra
                # magnitud", que es falso.
                segunda_por_cajon,
                segunda_por_cajon,
                recepcionada_el,
                recepcionada_el,
            ),
        )
    elif tipo_retiro in ORIGEN_RETIRO_AUTOMATICO_POR_TIPO:
        cursor.execute(
            """
            INSERT INTO compras
                (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro,
                 guia_id, guia_punto, carga_token, segunda_por_cajon,
                 estado, estado_retiro, retiro_procesado_el, retiro_origen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', 'retirado', now(), %s)
            RETURNING id
            """,
            (
                fecha_operacion,
                articulo_id,
                proveedor_id,
                cantidad_cajones,
                contenido_por_cajon,
                cantidad_kilos,
                cantidad_fraccion,
                importe,
                sena,
                tipo_retiro,
                guia_id,
                guia_punto,
                carga_token,
                segunda_por_cajon,
                ORIGEN_RETIRO_AUTOMATICO_POR_TIPO[tipo_retiro],
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO compras
                (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro,
                 guia_id, guia_punto, carga_token, segunda_por_cajon, estado, estado_retiro)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', 'pendiente')
            RETURNING id
            """,
            (
                fecha_operacion,
                articulo_id,
                proveedor_id,
                cantidad_cajones,
                contenido_por_cajon,
                cantidad_kilos,
                cantidad_fraccion,
                importe,
                sena,
                tipo_retiro,
                guia_id,
                guia_punto,
                carga_token,
                segunda_por_cajon,
            ),
        )

    (compra_id,) = cursor.fetchone()

    # EL SELLO DEL IMPORTE VA ACÁ AFUERA y no adentro de las tres listas del
    # INSERT, por el mismo argumento que ficha_en_origen_id: una columna
    # repetida en las tres ramas son tres lugares de los que una CUARTA rama
    # se puede olvidar, y olvidarla no falla —deja el par en NULL, que se ve
    # exactamente igual que una compra que nació sin precio—. Después del
    # if/elif/else corre para todas por construcción.
    #
    # Y solo cuando hay importe: una compra que nace sin precio no tiene nada
    # que fechar. Ese par en NULL es justo el que Compras sin precio va a
    # completar después, y va a escribir 'pendiente', que es la verdad.
    if importe is not None:
        cursor.execute(
            "UPDATE compras SET importe_puesto_el = now(), importe_origen = 'alta' WHERE id = %s",
            (compra_id,),
        )

    if ficha_en_origen_id is not None:
        _validar_caja_en_origen(cursor, ficha_en_origen_id, articulo_id)
        cursor.execute(
            "UPDATE compras SET ficha_en_origen_id = %s WHERE id = %s",
            (ficha_en_origen_id, compra_id),
        )
        if ingreso_directo_deposito:
            _guia_en_origen_si_corresponde(cursor, compra_id)

    return compra_id


def comanda_ya_guardada(carga_token: str) -> bool:
    """True si ya hay compras guardadas con este token de carga.

    Chequeo rápido para detectar el reintento de un guardado cuya
    respuesta se perdió (el server guardó y commiteó, pero el teléfono se
    quedó sin internet antes de ver la respuesta y vuelve a mandar lo
    mismo). Ver crear_compras_de_comanda, que además re-chequea adentro
    de su transacción.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT 1 FROM compras WHERE carga_token = %s LIMIT 1", (carga_token,))
            return cursor.fetchone() is not None
    finally:
        conexion.close()


def crear_compras_de_comanda(
    fecha_operacion,
    proveedor_id: int,
    renglones: list[dict],
    foto_ruta: str | None,
    carga_token: str | None,
) -> bool:
    """Guarda TODOS los renglones de una comanda en UNA sola transacción: o entran todos, o ninguno.

    Antes cada renglón se guardaba con su propia conexión y su propio
    commit: si se cortaba internet a mitad de una comanda de 5 renglones,
    quedaban 3 guardados y 2 perdidos, y nadie se enteraba. Acá un error
    en cualquier renglón deja la base exactamente como estaba (ni compras
    ni guías nuevas quedan a medias).

    carga_token es un token único por comanda que genera el server al
    armar la pantalla de revisión y viaja escondido en el form: todos los
    renglones se guardan con él. Si al guardar ya existen compras con ese
    token, este guardado es el REINTENTO de uno que ya entró (el teléfono
    nunca vio la respuesta) — no se inserta nada y se devuelve False para
    que quien llama responda como si fuera el guardado original, sin
    duplicar. None = sin protección (forms viejos ya abiertos): se
    inserta normal, como siempre.

    Cada renglón es un dict con articulo_id, cantidad_cajones,
    contenido_por_cajon, cantidad_kilos, cantidad_fraccion, importe, sena
    y tipo_retiro (mismo significado que en crear_compra). Devuelve True
    si guardó.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if carga_token is not None:
                cursor.execute("SELECT 1 FROM compras WHERE carga_token = %s LIMIT 1", (carga_token,))
                if cursor.fetchone() is not None:
                    return False

            for renglon in renglones:
                _insertar_compra_con_guia(
                    cursor,
                    fecha_operacion,
                    renglon["articulo_id"],
                    proveedor_id,
                    renglon["cantidad_cajones"],
                    renglon["contenido_por_cajon"],
                    renglon["cantidad_kilos"],
                    renglon["cantidad_fraccion"],
                    renglon["importe"],
                    renglon["sena"],
                    renglon["tipo_retiro"],
                    foto_ruta,
                    carga_token=carga_token,
                    # POR RENGLÓN y no por comanda: al mismo puesto se le
                    # pueden comprar dos cosas y que solo una venga armada.
                    ficha_en_origen_id=renglon.get("ficha_en_origen_id"),
                    # Con [] y NO con .get(): un renglón al que le falte la
                    # clave tiene que reventar. Un `.get()` guardaría la
                    # compra con la columna en NULL, que se ve igual que una
                    # compra anterior al modelo de dos magnitudes — o sea un
                    # hueco legítimo, y nadie lo iría a buscar.
                    segunda_por_cajon=renglon["segunda_por_cajon"],
                )
        conexion.commit()
        return True
    finally:
        conexion.close()


def compra_tiene_cantidad_bloqueada(estado: str | None) -> bool:
    """True si el artículo/cantidad/tipo de retiro de la compra ya no se pueden editar.

    Única definición de esta regla en todo el código — la usan la
    pantalla de Editar Compra (para mostrar el aviso y atenuar los
    campos) y actualizar_cantidad_compra (para bloquear el guardado de
    verdad).

    REGLA (19/08/2026): SOLO Depósito bloquea. Recepcionada: la cantidad
    real ya se pesó/contó, cambiar el estimado después modificaría un
    costo que ya se pudo haber usado para negociar precios. Rechazada o
    nunca ingresada: esa historia ya terminó. El RETIRO de Logística NO
    bloquea nada: hasta que la mercadería entra a Depósito, el comprador
    tiene que poder corregir su compra (un proveedor que llama para
    cancelar cantidad, un cambio de tipo de retiro, etc.) — Logística no
    le traba la edición a nadie.
    """
    return estado in ("recepcionado", "rechazado", "no_ingresado")


def compra_tiene_precio_bloqueado(estado: str | None) -> bool:
    """True si el importe/seña de la compra ya no se pueden editar.

    Única definición de esta regla — la usan la pantalla de Editar
    Compra y actualizar_precio_compra. Rechazada o nunca ingresada al
    depósito: esa mercadería no entra al costeo, no tiene sentido
    tocarle el precio. A propósito NO mira estado_retiro: es habitual
    que el comprador renegocie el precio con el proveedor después de
    que la mercadería ya se retiró del puesto, así que eso solo no
    bloquea nada acá (ver compra_tiene_cantidad_bloqueada, que es la
    que sí lo bloquea para la cantidad).
    """
    return estado in ("rechazado", "no_ingresado")


def actualizar_cantidad_compra(
    compra_id: int,
    articulo_id: int,
    cantidad_cajones: float,
    contenido_por_cajon: float,
    cantidad_kilos: float | None,
    cantidad_fraccion: float | None,
    tipo_retiro: str,
    ficha_en_origen_id: int | None = None,
    *,
    segunda_por_cajon: float | None,
) -> None:
    """Actualiza artículo/cantidad/marca de "viene armada"/tipo de retiro de una compra existente. No toca importe ni seña.

    `segunda_por_cajon` es keyword-only y sin default por lo mismo que en
    `crear_compra`: LA EDICIÓN es justo el camino que se olvidó la marca de
    "viene armada" en el 12/09, y el modo de falla es el mismo — la pantalla
    relee de la base, así que una escritura muerta se ve igual que una viva.

    Bloqueada (ValueError) SOLO si la compra ya pasó por Depósito
    (recepcionada, con rechazo total o nunca ingresada — ver
    compra_tiene_cantidad_bloqueada). El retiro de Logística NO bloquea:
    hasta que entra a Depósito, el comprador puede corregir su compra.
    Independiente del bloqueo de precio (actualizar_precio_compra).

    Transiciones de retiro al cambiar el tipo (las compras de tipos
    automáticos — Carro/Cooperativa, ver ORIGEN_RETIRO_AUTOMATICO_POR_TIPO
    — nunca quedan pendientes en Logística, no existe pantalla que las
    muestre; y al revés, volver de un tipo automático a Clark/Pases tiene
    que devolverla a la cola de Logística):
    - a un tipo automático con retiro pendiente: se marca retirada en el
      mismo UPDATE, como en crear_compra.
    - de un tipo automático (retiro_origen automatico_*) a otro tipo: el
      retiro vuelve a pendiente, sin cicatriz (como deshacer_retiro).
    - cualquier otro caso: el retiro no se toca.

    ficha_en_origen_id VIAJA CON EL ARTÍCULO y por eso entra acá y no en una
    función aparte: cambiar el artículo de una compra marcada dejaría la
    marca apuntando a una caja de OTRO artículo, que es justo lo que la
    guarda prohíbe. Juntos, el chequeo corre contra el artículo NUEVO y no
    hay forma de que se separen. None = "no, llega el cajón del proveedor", y
    eso también se escribe: desmarcar es una decisión, no un campo que se
    dejó vacío.

    Se escribe con un UPDATE aparte y no adentro de las tres ramas de arriba,
    por el mismo motivo que en el alta: tres listas de columnas distintas son
    tres lugares de los que una rama nueva se puede olvidar.

    Y ACÁ NO SE DISPARA NINGUNA GUÍA R. No hace falta: esta función solo
    corre mientras la compra NO esté recepcionada (el bloqueo de arriba), así
    que la guía sale después, al recibirla. Para una compra YA recepcionada el
    camino es otro y está en `marcar_compra_armada_en_origen`.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT estado, estado_retiro, retiro_origen FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            estado, estado_retiro, retiro_origen = fila if fila else (None, None, None)

            if compra_tiene_cantidad_bloqueada(estado):
                if estado == "recepcionado":
                    raise ValueError("Esta compra ya fue recepcionada, no se puede editar la cantidad.")
                if estado == "rechazado":
                    raise ValueError("Esta compra tuvo un rechazo total, no se puede editar la cantidad.")
                raise ValueError("Esta compra nunca ingresó al depósito, no se puede editar la cantidad.")

            if tipo_retiro in ORIGEN_RETIRO_AUTOMATICO_POR_TIPO and estado_retiro == "pendiente":
                cursor.execute(
                    """
                    UPDATE compras
                    SET articulo_id = %s, cantidad_cajones = %s, contenido_por_cajon = %s,
                        cantidad_kilos = %s, cantidad_fraccion = %s, segunda_por_cajon = %s,
                        tipo_retiro = %s,
                        estado_retiro = 'retirado', retiro_procesado_el = now(), retiro_origen = %s
                    WHERE id = %s
                    """,
                    (
                        articulo_id, cantidad_cajones, contenido_por_cajon, cantidad_kilos, cantidad_fraccion,
                        segunda_por_cajon,
                        tipo_retiro, ORIGEN_RETIRO_AUTOMATICO_POR_TIPO[tipo_retiro], compra_id,
                    ),
                )
            elif (
                tipo_retiro not in ORIGEN_RETIRO_AUTOMATICO_POR_TIPO
                and retiro_origen in ORIGEN_RETIRO_AUTOMATICO_POR_TIPO.values()
            ):
                cursor.execute(
                    """
                    UPDATE compras
                    SET articulo_id = %s, cantidad_cajones = %s, contenido_por_cajon = %s,
                        cantidad_kilos = %s, cantidad_fraccion = %s, segunda_por_cajon = %s,
                        tipo_retiro = %s,
                        estado_retiro = 'pendiente', retiro_procesado_el = NULL,
                        retiro_origen = NULL, cantidad_cajones_retirada = NULL
                    WHERE id = %s
                    """,
                    (articulo_id, cantidad_cajones, contenido_por_cajon, cantidad_kilos, cantidad_fraccion,
                     segunda_por_cajon, tipo_retiro, compra_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE compras
                    SET articulo_id = %s, cantidad_cajones = %s, contenido_por_cajon = %s,
                        cantidad_kilos = %s, cantidad_fraccion = %s, segunda_por_cajon = %s,
                        tipo_retiro = %s
                    WHERE id = %s
                    """,
                    (articulo_id, cantidad_cajones, contenido_por_cajon, cantidad_kilos, cantidad_fraccion,
                     segunda_por_cajon, tipo_retiro, compra_id),
                )

            if ficha_en_origen_id is not None:
                _validar_caja_en_origen(cursor, ficha_en_origen_id, articulo_id)
            cursor.execute(
                "UPDATE compras SET ficha_en_origen_id = %s WHERE id = %s",
                (ficha_en_origen_id, compra_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_precio_compra(compra_id: int, importe: float | None, sena: float | None) -> None:
    """Actualiza importe/seña de una compra existente. No toca artículo, cantidad ni tipo de retiro.

    Bloqueada (ValueError) solo si la compra fue rechazada o nunca
    ingresó al depósito (ver compra_tiene_precio_bloqueado). A
    diferencia de la cantidad, el precio SÍ se puede seguir editando
    después de recepcionada o retirada — es habitual que el comprador
    renegocie el precio con el proveedor una vez que la mercadería ya
    llegó.

    Y por eso SELLA el par del importe (ver _sello_del_importe): la
    renegociación es justamente lo que después no se puede distinguir de un
    precio cargado al recibir. Sella SOLO si el número cambió, porque la
    pantalla de Editar Compra llama acá en cada guardado aunque lo único
    tocado sea la cantidad.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT estado FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            estado = fila[0] if fila else None

            if compra_tiene_precio_bloqueado(estado):
                if estado == "rechazado":
                    raise ValueError("Esta compra tuvo un rechazo total, no se puede editar el precio.")
                raise ValueError("Esta compra nunca ingresó al depósito, no se puede editar el precio.")

            sello, sello_params = _sello_del_importe("edicion", importe)
            cursor.execute(
                f"UPDATE compras SET importe = %s, sena = %s, {sello} WHERE id = %s",
                (importe, sena) + sello_params + (compra_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_compras_pendientes_recepcion() -> list[dict]:
    """Compras con estado 'pendiente' (guía asignada, todavía sin procesar en Depósito).

    A diferencia de las consultas de arriba, acá NO se aplica el
    real-si-existe: esta es justo la pantalla donde se cargan los valores
    reales, hace falta el estimado en crudo (para prellenar los inputs) y
    ninguna compra pendiente tiene un real todavía. Las compras cargadas
    antes de la guía/Recepción tienen estado NULL — nunca igualan
    'pendiente' en SQL, así que quedan afuera solas; guia_id IS NOT NULL
    se agrega igual, a modo documental.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.guia_id, c.guia_punto, c.fecha_operacion,
                       -- El id y no solo el nombre: la pantalla busca por
                       -- ARTICULO las fichas de "ya viene armada en caja
                       -- nuestra", y matchear por nombre seria inventar una
                       -- clave donde ya hay una.
                       c.articulo_id,
                       -- NO NULO = viene YA ARMADA en caja nuestra y al
                       -- recepcionarla sale sola su guía R. La pantalla lo
                       -- AVISA y no ofrece nada que elegir: la marca la puso
                       -- el comprador, que es el único que lo sabe.
                       c.ficha_en_origen_id,
                       a.nombre AS articulo_nombre, a.unidad_compra, a.unidad_conteo,
                       c.segunda_por_cajon,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.cantidad_cajones, c.contenido_por_cajon, c.cantidad_kilos, c.cantidad_fraccion,
                       (SELECT COUNT(*) FROM fotos_recepcion f WHERE f.compra_id = c.id) AS fotos_balanza
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.estado = 'pendiente' AND c.guia_id IS NOT NULL
                ORDER BY c.guia_id, c.guia_punto
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def _auto_retirar_si_corresponde(cursor, compra_id: int) -> str | None:
    """Si la compra todavía no fue retirada, la marca retirada con origen='deposito'.

    Si llegó al depósito, alguien la retiró del puesto — aunque Logística
    nunca haya tildado el botón. Si estado_retiro ya es 'retirado', no
    hace nada (ya está bien). Si es 'cancelado', es una contradicción real
    (mercadería que supuestamente no salió del puesto) — NO se pisa, para
    no borrar ese dato; en cambio se devuelve un aviso para mostrar en
    pantalla. Devuelve el aviso, o None si no hay nada que avisar.
    """
    cursor.execute("SELECT estado_retiro FROM compras WHERE id = %s", (compra_id,))
    fila = cursor.fetchone()
    estado_retiro_actual = fila[0] if fila else None

    if estado_retiro_actual == "cancelado":
        return "Esta compra figuraba cancelada en Logística."

    if estado_retiro_actual != "retirado":
        cursor.execute(
            """
            UPDATE compras
            SET estado_retiro = 'retirado', retiro_procesado_el = now(), retiro_origen = 'deposito'
            WHERE id = %s
            """,
            (compra_id,),
        )
    return None


def _exigir_la_segunda_si_la_compra_la_declaro(cantidad_kilos, cantidad_fraccion, segunda_real) -> None:
    """Si la compra declaró las DOS magnitudes, la recepción tiene que traer las dos.

    LA GUARDA VA DONDE SE ESCRIBE, no en la pantalla: la pantalla puede
    mostrar el campo, y un formulario armado a mano no ve ningún cartel.

    Y el motivo es que la asimetría sería INVISIBLE. El costeo lee cada
    magnitud con COALESCE(real, estimado): con el kilo pesado y el conteo
    sin pesar, la ficha que vende por kilo costearía contra lo que Depósito
    pesó y la del mismo artículo que vende por unidad contra lo que el
    comprador estimó — en la MISMA compra, sin que nada se descuadre y sin
    que ninguna pantalla lo diga.

    Al revés no se exige nada: si la compra trajo UNA sola magnitud,
    pedirle a Depósito la otra es pedirle que invente.

    LAS DOS CANTIDADES VIENEN EN LA MISMA CONSULTA que trae unidad_compra, y
    no en una propia: una consulta de más acá es una lectura de más en cada
    recepción, y sobre todo es otro lugar donde se puede leer una compra
    distinta de la que se está por escribir.
    """
    if segunda_real is None and cantidad_kilos is not None and cantidad_fraccion is not None:
        raise ValueError(
            "Esta compra se cargó con las dos magnitudes (kilos y conteo), así que la recepción "
            "necesita las dos: poné también la otra por bulto."
        )


def _derivar_valores_reales(
    unidad_compra: str | None,
    cantidad_cajones_real: float,
    valor_real: float,
    segunda_real: float | None = None,
) -> tuple[float | None, float | None, float | None, float | None]:
    """De lo que Depósito mira en UN cajón, arma (contenido_por_cajon_real, kilos_real, fraccion_real, segunda_por_cajon_real).

    DEVUELVE CUATRO Y EL CUARTO ES `segunda_real` SIN TOCAR, por lo mismo
    que `magnitudes_de_la_compra` devuelve tres: desde el 20/09 la segunda
    magnitud tiene columna propia y tiene que llegar al UPDATE. Viajando en
    la MISMA tupla que los totales no se puede perder — un llamador que
    tomara tres de cuatro revienta al desempacar, en vez de dejar la columna
    en NULL, que se ve igual que una compra que no declaró la segunda.

    valor_real es SIEMPRE por cajón/bulto — nunca el total de toda la
    carga junta — sea kilos, unidades o cubetas: Depósito mira un bulto
    por vez (lo pesa o lo cuenta), no suma de cabeza toda la carga (usado
    tanto para recepcionar por primera vez como para corregir una
    recepción ya hecha, ver recepcionar_compra y corregir_recepcion_compra).

    contenido_por_cajon_real es directamente valor_real. El total (kilos
    o fracción según la unidad) se deriva multiplicando por
    cantidad_cajones_real — nunca al revés, para no terminar promediando
    un total mal cargado en un número por cajón que nadie escribió.

    `segunda_real` es la SEGUNDA magnitud, también por bulto, y va en None
    cuando la compra declaró UNA sola. ESO NO ES UNA COMODIDAD: si la
    compra trajo una magnitud y acá se escribiera la otra, quedaría una
    compra cuyo real dice dos cosas y cuyo estimado dice una — y el costeo
    tomaría el real de una ficha contra un número pesado y el de la otra
    contra uno estimado, en la misma compra y sin que se vea. Pedirle a
    Depósito la magnitud que la compra no declaró es pedirle que invente.

    El reparto entre las dos columnas lo hace core/magnitudes.py, que es el
    mismo que usa la carga de la compra: escrito dos veces son dos reglas.
    """
    principal = cantidad_cajones_real * valor_real
    segunda = cantidad_cajones_real * segunda_real if segunda_real is not None else None
    kilos, fraccion = repartir_magnitudes(unidad_compra, principal, segunda)
    return valor_real, kilos, fraccion, segunda_real


def recepcionar_compra(
    compra_id: int,
    cantidad_cajones_real: float,
    valor_real: float,
    cantidad_cajones_rechazada: float | None = None,
    motivo_rechazo: str | None = None,
    segunda_real: float | None = None,
) -> str | None:
    """Marca una compra como recepcionada, con los valores REALES que pesó/contó Depósito.

    Ver _derivar_valores_reales para el significado de valor_real según la
    unidad de compra del artículo. El estimado (cantidad_cajones/
    contenido_por_cajon/etc., sin "_real") nunca se toca.

    segunda_real es la otra magnitud, también por bulto, y SOLO se manda
    cuando la compra declaró las dos: pedirle a Depósito la que la compra
    no trajo es pedirle que invente. Ver _derivar_valores_reales.

    Rechazo parcial: si Depósito devolvió parte de la carga al proveedor,
    cantidad_cajones_rechazada es cuántos bultos devolvió (y motivo_rechazo
    por qué). Es SOLO registro: cantidad_cajones_real ya viene con los
    bultos aceptados (llegados − rechazados) y es la que usa todo el
    costeo — como el importe es por bulto, ninguna cuenta cambia.

    Además marca la compra como retirada (ver _auto_retirar_si_corresponde)
    si todavía no lo estaba.

    Devuelve (aviso_de_retiro, numero_de_guia_R). El segundo viene con
    número solo cuando el COMPRADOR marcó la compra como "ya viene armada
    en caja nuestra" al cargarla: ahí la guía R sale sola, en esta misma
    transacción. Ver `_guia_en_origen_si_corresponde`.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            aviso, numero_guia = _recepcionar_compra(
                cursor, compra_id, cantidad_cajones_real, valor_real,
                cantidad_cajones_rechazada, motivo_rechazo, segunda_real,
            )
        conexion.commit()
        return aviso, numero_guia
    finally:
        conexion.close()


def _recepcionar_compra(
    cursor,
    compra_id: int,
    cantidad_cajones_real: float,
    valor_real: float,
    cantidad_cajones_rechazada: float | None = None,
    motivo_rechazo: str | None = None,
    segunda_real: float | None = None,
) -> tuple[str | None, int | None]:
    """La escritura de la recepción, con el cursor abierto. Devuelve (aviso, numero_de_guia).

    ACÁ SE DISPARA LA GUÍA R EN ORIGEN, y por eso este cuerpo está separado
    de `recepcionar_compra`: es el único lugar por donde pasan TODAS las
    recepciones —la normal y la del rechazo parcial—, así que la guía sale
    sola en las dos sin escribir la regla dos veces. Con rechazo parcial se
    arma por los bultos ACEPTADOS, que ya vienen en cantidad_cajones_real:
    no hay nada especial que agregar para ese caso.

    QUIÉN DECIDE que viene armada es el COMPRADOR, al cargar la compra
    (`compras.ficha_en_origen_id`). El depósito no elige nada: ve el aviso y
    recibe. Antes esto era un botón en Recepción y le pedía al operario una
    decisión comercial que no había tomado — él no fue al puesto ni mandó
    las cajas.

    LA GUÍA VA EN LA MISMA TRANSACCIÓN que la recepción, y si no se puede
    cargar NO SE RECIBE. Es a propósito: una compra recepcionada sin su guía
    deja el lote crudo y la ficha sin sus cajas. Quien llama traduce el
    motivo a la pantalla — nunca se traga.

    El lote de esta compra está entero por construcción: nace en esta misma
    transacción, así que nadie pudo haber tomado de él todavía. Por eso acá
    no hace falta la guarda de `dependencias_del_lote_de_compra`, que sí va
    a hacer falta el día que se cargue una guía sobre una compra vieja.
    """
    cursor.execute(
        """
        SELECT a.unidad_compra, c.cantidad_kilos, c.cantidad_fraccion
        FROM compras c
        JOIN articulos a ON a.id = c.articulo_id
        WHERE c.id = %s
        """,
        (compra_id,),
    )
    fila = cursor.fetchone()
    unidad_compra, cantidad_kilos, cantidad_fraccion = fila if fila else (None, None, None)

    _exigir_la_segunda_si_la_compra_la_declaro(cantidad_kilos, cantidad_fraccion, segunda_real)
    (contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real,
     segunda_por_cajon_real) = _derivar_valores_reales(
        unidad_compra, cantidad_cajones_real, valor_real, segunda_real
    )

    cursor.execute(
        """
        UPDATE compras
        SET estado = 'recepcionado',
            cantidad_cajones_real = %s,
            contenido_por_cajon_real = %s,
            cantidad_kilos_real = %s,
            cantidad_fraccion_real = %s,
            segunda_por_cajon_real = %s,
            cantidad_cajones_rechazada = %s,
            motivo_rechazo = %s,
            procesada_el = now()
        WHERE id = %s
        """,
        (
            cantidad_cajones_real,
            contenido_por_cajon_real,
            cantidad_kilos_real,
            cantidad_fraccion_real,
            segunda_por_cajon_real,
            cantidad_cajones_rechazada,
            motivo_rechazo,
            compra_id,
        ),
    )

    aviso = _auto_retirar_si_corresponde(cursor, compra_id)
    return aviso, _guia_en_origen_si_corresponde(cursor, compra_id)


def _guia_en_origen_si_corresponde(cursor, compra_id: int) -> int | None:
    """Si esta compra vino YA ARMADA en caja nuestra, carga su guía R. Devuelve el número, o None.

    EL CONSUMO VA DIRIGIDO A SU PROPIA COMPRA, y es lo más delicado del
    camino. Sin dirigirlo decide el FIFO, que toma el lote MÁS VIEJO: con un
    cajón viejo del mismo artículo en el depósito, la guía se comería el
    cajón y dejaría como lote crudo la caja que llegó armada — el resultado
    OPUESTO al del mundo, y sin descuadrar ningún total. Medido.

    Por qué CONSUME en vez de producir y listo: la compra recién
    recepcionada ya sumó +N al stock. Una guía que produjera sin consumir
    (como las 'inicial' del corte) dejaría el artículo con 2N. Toma N y
    produce N —neto cero— y lo único que cambia es que el lote pasa de crudo
    a trabajado, que es lo que la pared del armado necesita para que esas
    cajas salgan de su ficha.

    La fecha se LEE de la compra recién escrita y no se calcula acá: tiene
    que ser la misma que el FIFO le pone a su lote, o el freno busca el lote
    un día antes de que exista.
    """
    cursor.execute(
        f"""
        SELECT c.articulo_id, c.ficha_en_origen_id, c.cantidad_cajones_real,
               {_SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col='c.procesada_el')},
               f.articulo_id, f.cliente_id
        FROM compras c
        LEFT JOIN fichas_logistica f ON f.id = c.ficha_en_origen_id
        WHERE c.id = %s
        """,
        (compra_id,),
    )
    # SIN agregado: `fetchone() is None` sobre un `count(*)` nunca es None y
    # no distinguiría "no existe" de "existe" (corolario 27).
    fila = cursor.fetchone()
    if fila is None:
        raise ValueError("Esa compra no existe.")
    articulo_id, ficha_id, bultos, fecha, ficha_articulo, ficha_cliente = fila
    if ficha_id is None:
        return None

    # La guarda va donde se ESCRIBE. Una ficha de otro artículo inventaría
    # cajas que no existen y el Cotejo mostraría un rojo imposible de
    # explicar — mismo motivo que en asignar_ficha_a_reproceso.
    if ficha_articulo != articulo_id:
        raise ValueError(
            "La ficha marcada en esta compra es de otro artículo: no se puede armar la guía R."
        )

    bultos = float(bultos or 0)
    if bultos <= 0:
        raise ValueError("Esta compra viene armada pero se recepcionó con cero bultos.")

    return _crear_reproceso(
        cursor,
        articulo_id=articulo_id,
        bultos_tomados=bultos,
        bultos_primera=bultos,
        bultos_segunda=0,
        bultos_merma=0,
        fecha_operacion=fecha,
        cliente_id=ficha_cliente,
        ficha_id=ficha_id,
        # DIRIGIDO a su propia compra. Ver el docstring.
        reparto=[{"tipo_lote": "guia", "origen_id": compra_id, "bultos": bultos}],
        tipo="en_origen",
        compra_origen_id=compra_id,
    )


# La fecha del lote de una compra, tal como la arma la consulta de lotes de
# `_entradas_y_salidas_stock_varios` (su columna `fecha_orden`). Va escrita UNA
# vez y no copiada en cada llamador: la guía R en origen tiene que quedar
# fechada EXACTAMENTE el día que el FIFO le pone a su compra, o el lote no
# existe todavía cuando el freno lo busca y la guía rebota por un stock que
# está ahí. Lo cuida
# `test_la_fecha_de_la_guia_en_origen_sale_de_la_MISMA_expresion_que_el_lote`.
_SQL_FECHA_DEL_LOTE_DE_COMPRA = "({col} AT TIME ZONE 'America/Argentina/Buenos_Aires')::date"


def compra_para_marcar_armada(compra_id: int) -> dict | None:
    """Los datos de una compra ya recepcionada para decidir si vino armada. None si no existe.

    Es la pantalla de "Vino armada" de Buscar Compras: la salida para la
    compra que YA se recepcionó sin la marca, porque el comprador se olvidó o
    porque nadie se la había podido poner.

    `motivo` es `core.vino_armada.MotivoVinoArmada` o None, y es la MISMA
    función que decide si el menú de Buscar Compras ofrece el botón. Ésa es
    toda la gracia: la pantalla conocía tres motivos y el menú dos, así que
    el menú ofrecía el botón en casos que esta pantalla rechaza — 325 de 482
    en Frutamax el 16/09, medido. Dos reglas separadas se vuelven a separar.

    `fecha_del_lote` es la fecha que va a llevar la guía, y sale de
    `procesada_el` con la MISMA expresión con que el FIFO fecha el lote — no
    de `fecha_operacion`, que es el día de la compra en el Mercado y puede ser
    otro. La guía tiene que quedar fechada el día en que su lote existe.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.id, c.articulo_id, a.nombre AS articulo_nombre, a.unidad_compra,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.fecha_operacion, c.estado, c.ficha_en_origen_id,
                       c.cantidad_cajones_real, c.cantidad_cajones,
                       COALESCE((
                           SELECT SUM(rc.bultos)
                             FROM reprocesos_consumos rc
                             JOIN reprocesos r ON r.id = rc.reproceso_id
                            WHERE rc.origen = 'compra' AND rc.compra_id = c.id
                              AND r.anulado_el IS NULL
                       ), 0) AS bultos_consumidos,
                       {_SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col='c.procesada_el')} AS fecha_del_lote
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            compra = dict(zip([d[0] for d in cursor.description], fila))
            # `bultos` es el REAL si existe: es contra eso que se compara lo
            # que ya salió del lote, igual que en el listado.
            bultos = compra["cantidad_cajones_real"] or compra["cantidad_cajones"]
            compra["motivo"] = motivo_para_no_marcar_armada(
                {**compra, "bultos": bultos}, _fecha_corte(cursor)
            )
            return compra
    finally:
        conexion.close()


def marcar_compra_armada_en_origen(compra_id: int, ficha_en_origen_id: int) -> int:
    """Marca una compra YA RECEPCIONADA como venida armada en caja nuestra y carga su guía R. Devuelve el número.

    ES LA SALIDA para el caso que el camino normal no cubre: la marca la pone
    el comprador AL CARGAR, y la guía sale sola al recepcionar. Una compra que
    ya se recepcionó sin marca no tiene por dónde — antes de esto, la única
    forma era la guía R a mano, que es documentar un trabajo que no se hizo
    así.

    LAS DOS COSAS VAN EN LA MISMA TRANSACCIÓN, y si la guía no se puede armar
    la marca tampoco se escribe: una compra marcada sin su guía deja el lote
    crudo y la ficha sin sus cajas, que es exactamente el estado que esto
    viene a arreglar.

    ACÁ SÍ HACE FALTA la guarda del lote que en la recepción no hacía: allá el
    lote nace en la misma transacción y nadie pudo haber tomado de él; acá la
    compra puede ser de hace días y su lote puede estar comido. No se decide
    por adelantado quién se lo llevó — de eso se encarga el freno de
    `_crear_reproceso`, que mira el restante real contra la MISMA lista que el
    FIFO. Lo que hace esta función es no esconderlo: la pantalla muestra antes
    qué salió de ese lote (`dependencias_del_lote_de_compra`) para que la
    decisión se tome con eso a la vista, y si el freno rebota, el motivo sube
    tal cual.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # SIN agregado, para que "no existe" y "existe" no se vean igual
            # (corolario 27).
            cursor.execute(
                f"""
                SELECT estado, ficha_en_origen_id, cantidad_cajones_real,
                       {_SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col='procesada_el')}
                FROM compras WHERE id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa compra no existe.")
            estado, ya_marcada, bultos, fecha_del_lote = fila

            if estado != "recepcionado":
                raise ValueError(
                    "Esta compra todavía no se recepcionó: la marca va en la carga, "
                    "y la guía R sale sola cuando Depósito la reciba."
                )
            if ya_marcada is not None:
                raise ValueError("Esta compra ya está marcada como venida armada.")
            if fecha_del_lote is None:
                raise ValueError("Esta compra no tiene fecha de recepción: no hay lote contra el que armar la guía.")

            motivo = _motivo_sin_lote_por_el_corte(cursor, fecha_del_lote)
            if motivo is not None:
                raise ValueError(motivo)

            cursor.execute("SELECT articulo_id FROM compras WHERE id = %s", (compra_id,))
            (articulo_id,) = cursor.fetchone()
            _validar_caja_en_origen(cursor, ficha_en_origen_id, articulo_id)

            cursor.execute(
                "UPDATE compras SET ficha_en_origen_id = %s WHERE id = %s",
                (ficha_en_origen_id, compra_id),
            )
            numero = _guia_en_origen_si_corresponde(cursor, compra_id)
        conexion.commit()
        return numero
    finally:
        conexion.close()


def _guias_r_del_lote(cursor, compra_id: int) -> list[dict]:
    """Los consumos CONGELADOS de este lote, de la guía más vieja a la más nueva.

    Ese orden es el que el lote se fue gastando, y de él depende
    `documentos_que_no_entran`: las que entran en el número nuevo quedan bien
    y las que se pasan son las que van a quedar diciendo algo que ya no se
    puede reconstruir.

    TRAE EL COSTO CONGELADO además de los bultos. Sale de
    `reprocesos_consumos`, que es un documento: si mañana cambia el precio de
    la compra, ESTE número no se mueve — y eso es justo lo que el aviso de
    Editar Compra necesita nombrar.

    Vive aparte porque tiene DOS llamadores con costos muy distintos: la
    pantalla de Corregir Recepción, que además rejuega el FIFO entero, y el
    aviso del precio, que solo necesita esto. Metido adentro de
    `dependencias_del_lote_de_compra`, el aviso pagaría un rejuego que no usa.
    """
    cursor.execute(
        """
        SELECT rp.id, rp.fecha_operacion, rc.bultos, rc.costo_por_bulto
        FROM reprocesos_consumos rc
        JOIN reprocesos rp ON rp.id = rc.reproceso_id
        WHERE rc.compra_id = %s AND rp.anulado_el IS NULL
        ORDER BY rp.fecha_operacion, rp.id
        """,
        (compra_id,),
    )
    return [
        {"reproceso_id": f[0], "fecha": f[1], "bultos": float(f[2]),
         "costo_por_bulto": float(f[3]) if f[3] is not None else None}
        for f in cursor.fetchall()
    ]


def guias_r_congeladas_de_la_compra(compra_id: int) -> list[dict]:
    """`_guias_r_del_lote` con conexión propia, para el aviso del PRECIO.

    Es la lista de guías R que se costearon contra este lote y que NO se van a
    mover si alguien le cambia el precio a la compra. Medido el 19/09: el lote
    vivo pasa de 100.000 a 50.000 y `reprocesos.costo_total` se queda en
    700.000 — las dos son correctas por su lado y nadie las pone juntas.

    No pasa por `dependencias_del_lote_de_compra` a propósito: aquélla rejuega
    el FIFO del artículo entero para poder decir QUÉ RENGLONES armados salieron
    de acá, y el aviso no los necesita — los armados se recostean solos, que es
    exactamente lo que el aviso dice. Editar Compra se abre todo el día.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return _guias_r_del_lote(cursor, compra_id)
    finally:
        conexion.close()


def dependencias_del_lote_de_compra(
    compra_id: int, nueva_cantidad: float | None = None, nueva_recepcion=None
) -> dict | None:
    """Qué salió del lote de esta compra, y qué pasaría si su cantidad bajara.

    Es lo que la pantalla de Corregir Recepción muestra ARRIBA del formulario:
    el que corrige tiene que decidir qué número poner, y eso depende de qué se
    llevó el lote. Con "editar y avisar" la decisión ya está tomada cuando
    llega el cartel.

    Devuelve None si la compra no existe o no está recepcionada (no hay lote).

    Las dos mitades NO son la misma clase de dato, y la pantalla lo dice:

    - `guias_r` sale de `reprocesos_consumos`, que es un documento CONGELADO:
      es exacto y no se mueve nunca, pase lo que pase acá.
    - `renglones` lo calcula el FIFO en el momento, así que puede cambiar solo
      si mañana se corrige otra recepción. Sale de `atribuir_costos_fifo`, la
      misma función que ya corre la alerta de cruce en Guías R — no hay una
      segunda versión del reparto escrita para esta pantalla.

    Con `nueva_cantidad` agrega el impacto medido: cuántos bultos que hoy
    tienen lote se quedarían sin lote, y qué guías R quedarían sin poder
    reconstruirse. Simulado, no estimado.
    """
    from core.costo_real import atribuir_costos_fifo
    from core.stock import documentos_que_no_entran, salidas_para_reparto, sin_lote_si_el_lote_cambia

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT articulo_id, cantidad_cajones_real, estado,
                       (procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                FROM compras WHERE id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            if fila is None or fila[2] != "recepcionado" or fila[1] is None:
                return None
            articulo_id, entraron, fecha_del_lote = fila[0], float(fila[1]), fila[3]

            guias_r = _guias_r_del_lote(cursor, compra_id)

            entradas, salidas = _entradas_y_salidas_stock(cursor, articulo_id)
    finally:
        conexion.close()

    renglones = []
    for salida in atribuir_costos_fifo(entradas, salidas):
        if salida.get("tipo") != "armado":
            continue
        bultos = sum(
            c["bultos"] for c in salida["consumos_lotes"]
            if c["tipo_lote"] == "guia" and c["origen_id"] == compra_id
        )
        if bultos <= 0:
            continue
        # "Lo eligió a mano" sale gratis: los lotes elegidos ya vienen
        # colgados de la salida desde que existe la corrección del armado.
        elegidos = salida.get("lotes_elegidos") or []
        renglones.append(
            {
                "cliente_id": salida.get("cliente_id"),
                "fecha": salida.get("fecha"),
                "bultos": round(bultos, 2),
                "elegido_a_mano": any(
                    e["lote_tipo"] == "guia" and e["lote_origen_id"] == compra_id for e in elegidos
                ),
            }
        )

    resultado = {
        "entraron": entraron,
        "guias_r": guias_r,
        "renglones": renglones,
        "salieron": round(sum(g["bultos"] for g in guias_r) + sum(r["bultos"] for r in renglones), 2),
        "sin_lote_de_mas": 0.0,
        "guias_rotas": [],
    }

    if nueva_cantidad is not None and round(float(nueva_cantidad) - entraron, 2) < 0:
        limpias = salidas_para_reparto(salidas)
        antes, despues = sin_lote_si_el_lote_cambia(
            entradas, limpias, "guia", compra_id, nueva_cantidad=float(nueva_cantidad)
        )
        resultado["sin_lote_de_mas"] = round(max(despues - antes, 0.0), 2)
        resultado["guias_rotas"] = documentos_que_no_entran(guias_r, float(nueva_cantidad))

    # MOVER EL LOTE DE DÍA entra por acá y no por una función aparte: el aviso
    # que arma la pantalla es el MISMO —cuántos bultos quedan sin lote y qué
    # guías R quedan diciendo algo que ya no se puede reconstruir— y dos
    # versiones del mismo aviso se separan el día que una aprende algo.
    #
    # Solo se simula MOVER HACIA ADELANTE: un lote más viejo cubre lo mismo y
    # más, igual que uno más grande, así que la diferencia da cero o negativa
    # y preguntarla sería un cartel que aparece siempre.
    if nueva_recepcion is not None and nueva_recepcion > fecha_del_lote:
        limpias = salidas_para_reparto(salidas)
        antes, despues = sin_lote_si_el_lote_cambia(
            entradas, limpias, "guia", compra_id, nueva_fecha=nueva_recepcion
        )
        resultado["sin_lote_de_mas"] = round(max(despues - antes, 0.0), 2)
        # Y ACÁ LAS ROTAS SE ELIGEN POR FECHA, no por acumulado. Una guía R
        # anterior al día nuevo del lote se costeó contra mercadería que —con
        # la fecha corregida— todavía no había entrado: no es que el lote se
        # quedó corto, es que no existía. `documentos_que_no_entran` cuenta
        # bultos y esta pregunta no es de bultos.
        resultado["guias_rotas"] = [g for g in guias_r if g["fecha"] < nueva_recepcion]

    return resultado


def _guias_en_origen_vivas(cursor, compra_id: int) -> list[int]:
    """Las guías R que ESTA compra generó por venir armada, y que siguen vivas.

    UNA SOLA VEZ, y hasta el 19/09 estaban TRES: la pantalla que ofrece
    desmarcar, el desmarcar en sí y Corregir Recepción, cada una con el mismo
    SELECT copiado. Mover la compra de fecha iba a ser la cuarta — y es el
    momento exacto en que tres copias se vuelven cuatro, que es el único en
    que se puede evitar gratis.

    Devuelve los IDS y no el mensaje: la PRECONDICIÓN es una sola —mientras
    esa guía viva, la compra y la guía dicen lo mismo uno a uno— y la cola
    depende de lo que se estaba por hacer ("anulá y volvé a recepcionar" no
    es lo mismo que "anulá y volvé"). Una cola compartida obligaría a que las
    tres mandaran a hacer lo mismo, que es falso.
    """
    cursor.execute(
        """
        SELECT id FROM reprocesos
        WHERE compra_origen_id = %s AND anulado_el IS NULL
        ORDER BY id
        """,
        (compra_id,),
    )
    return [f[0] for f in cursor.fetchall()]


def _lote_de_la_compra_YA_SE_USO(cursor, compra_id: int) -> tuple[int, int]:
    """(guías R que la consumieron, armados que la eligieron). Las dos vivas.

    Una compra recepcionada NO es una fila de movimientos_stock: es la
    ENTRADA misma, y el FIFO la reparte como un lote. Si alguien ya se llevó
    de ese lote, sacarla deja consumos apuntando a mercadería que el sistema
    dice que nunca entró.

    `lote_tipo = 'guia'` no es decorativo: `lote_origen_id` es POLIMÓRFICO, y
    sin el tipo un reproceso con el mismo id contaría como esta compra.

    Devuelve los DOS conteos por separado y no un booleano, porque el mensaje
    tiene que decir cuál de los dos frena — "la consumió una guía R" y "un
    armado la eligió" se arreglan en pantallas distintas.
    """
    cursor.execute(
        """
        SELECT (SELECT count(*) FROM reprocesos_consumos rc
                  JOIN reprocesos rp ON rp.id = rc.reproceso_id
                 WHERE rc.compra_id = %s AND rp.anulado_el IS NULL),
               (SELECT count(*) FROM pedidos_renglones_lotes_elegidos le
                  JOIN pedidos_renglones r ON r.id = le.renglon_id
                 WHERE le.lote_tipo = 'guia' AND le.lote_origen_id = %s
                   AND r.anulado_el IS NULL)
        """,
        (compra_id, compra_id),
    )
    consumida, elegida = cursor.fetchone()
    return int(consumida), int(elegida)


def uso_del_lote_de_la_compra(compra_id: int) -> dict:
    """{"guias": n, "armados": n}: si alguno es > 0, la recepción no se puede deshacer.

    La usa LA PANTALLA para decidir si ofrece el botón, y la escritura la usa
    para rechazar. LA MISMA función en las dos puntas, no dos SELECT: un botón
    que el POST después rechaza es un callejón —el que lo aprieta se come un
    error por algo que la pantalla le propuso— y con dos copias el día que una
    cambie el callejón aparece sin que nada avise.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            guias, armados = _lote_de_la_compra_YA_SE_USO(cursor, compra_id)
        return {"guias": guias, "armados": armados}
    finally:
        conexion.close()


def revertir_recepcion_de_compra(compra_id: int) -> None:
    """Devuelve una compra recepcionada a 'pendiente' y le saca los valores reales.

    LA OPERACIÓN QUE FALTABA. Hasta el 20/09 ninguna pantalla podía hacerlo:
    el Deshacer de Depósito está bloqueado para las recepcionadas ("para
    corregirla hace falta Gerencia") y lo que Gerencia tiene es Corregir
    Recepción, que es OTRA COSA —su docstring lo dice: corrige el número de
    una recepción que pasó, no deshace una que no tenía que pasar—. Una
    recepción apretada por error terminaba en el editor de la base, con
    `db/revertir_una_recepcion.sql`.

    POR QUÉ NO VA UN MOVIMIENTO COMPENSATORIO, y es el argumento de ese
    `.sql`: la entrada de stock no es una fila en `movimientos_stock`, es LA
    COMPRA MISMA —`_SQL_SUMAS_STOCK` suma `cantidad_cajones_real` de las
    recepcionadas—. Un ajuste en menos dejaría DOS registros falsos que se
    cancelan (un ingreso que no pasó y un ajuste que tampoco), y cualquier
    pantalla que los muestre por separado va a mentir. Volver a 'pendiente'
    borra la entrada y no deja rastro que después haya que explicar.

    LAS TRES GUARDAS, todas adentro de la misma transacción:

      1. que la compra exista — con un SELECT SIN agregado, porque con
         `count(*)` el "no encontrado" no salta nunca;
      2. que esté recepcionada;
      3. que su lote NO se haya usado todavía.

    EL RETIRO SE DESHACE SOLO SI LO PUSO LA RECEPCIÓN. `_auto_retirar_si_
    corresponde` deja `retiro_origen = 'deposito'`; si lo marcó Logística, es
    un hecho aparte que esta compra no puede pisar.

    Y NULEA `segunda_por_cajon_real`, que el `.sql` del 08/09 no nulea porque
    esa columna es del 20/09. Sin eso, la compra vuelve a 'pendiente'
    llevándose un valor "real" de una recepción que ya no existe, y las siete
    consultas que hacen `COALESCE(real, estimado)` lo muestran como si se
    hubiera recibido.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # SIN AGREGADO: con count(*) la fila vuelve con 0 y `is None` no
            # se cumple nunca, así que la guarda no podría distinguir "no
            # existe" de "existe" (corolario 27).
            cursor.execute("SELECT estado FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa compra ya no existe.")
            if fila[0] != "recepcionado":
                raise ValueError(
                    "Esta compra no está recepcionada, no hay recepción que deshacer."
                )

            consumida, elegida = _lote_de_la_compra_YA_SE_USO(cursor, compra_id)
            if consumida or elegida:
                partes = []
                if consumida:
                    partes.append(f"{consumida} guía{'' if consumida == 1 else 's'} R la consumió")
                if elegida:
                    partes.append(f"{elegida} armado{'' if elegida == 1 else 's'} la eligió")
                raise ValueError(
                    "De esta compra ya se tomó mercadería (" + " y ".join(partes) + "). "
                    "Para deshacer la recepción hay que anular eso primero."
                )

            cursor.execute(
                """
                UPDATE compras
                SET estado = 'pendiente',
                    cantidad_cajones_real = NULL,
                    contenido_por_cajon_real = NULL,
                    cantidad_kilos_real = NULL,
                    cantidad_fraccion_real = NULL,
                    segunda_por_cajon_real = NULL,
                    cantidad_cajones_rechazada = NULL,
                    motivo_rechazo = NULL,
                    procesada_el = NULL,
                    estado_retiro = CASE WHEN retiro_origen = 'deposito'
                                         THEN 'pendiente' ELSE estado_retiro END,
                    retiro_procesado_el = CASE WHEN retiro_origen = 'deposito'
                                               THEN NULL ELSE retiro_procesado_el END,
                    retiro_origen = CASE WHEN retiro_origen = 'deposito'
                                         THEN NULL ELSE retiro_origen END
                WHERE id = %s
                """,
                (compra_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def marca_en_origen_de_la_compra(compra_id: int) -> dict:
    """¿Esta compra dice que vino armada en caja nuestra, y su guía R sigue viva?

    LAS DOS COSAS EN UNA LECTURA a propósito: la pantalla que ofrece
    desmarcarla necesita las dos para no ser un callejón. Con la guía viva el
    botón no va —la escritura lo rechaza— y lo que hay que mostrar es cuál
    anular; preguntadas por separado, un día una pantalla ofrece lo que la
    otra sabe que no se puede.

    `ficha_id` en None es "no está marcada", que es el caso normal y no un
    hueco: la inmensa mayoría de las compras llegan en el cajón del proveedor.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # SIN agregado: `fetchone() is None` sobre un `count(*)` nunca es
            # None y no distinguiría "no existe" de "existe" (corolario 27).
            cursor.execute(
                """
                SELECT c.ficha_en_origen_id, f.nombre_cliente, e.nombre, cl.nombre
                FROM compras c
                LEFT JOIN fichas_logistica f ON f.id = c.ficha_en_origen_id
                LEFT JOIN envases e ON e.id = f.envase_id
                LEFT JOIN clientes cl ON cl.id = f.cliente_id
                WHERE c.id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa compra no existe.")
            ficha_id, codigo, envase, cliente = fila

            vivas = [f"R{g}" for g in _guias_en_origen_vivas(cursor, compra_id)]
    finally:
        conexion.close()

    return {"ficha_id": ficha_id, "codigo_cliente": codigo,
            "envase_nombre": envase, "cliente_nombre": cliente,
            "guias_vivas": vivas}


def desmarcar_compra_armada_en_origen(compra_id: int) -> None:
    """Saca la marca "vino armada en caja nuestra" de una compra mal marcada.

    ES LA INVERSA DE `marcar_compra_armada_en_origen`, y no es simétrica a
    propósito: aquélla marca Y carga la guía R en la misma transacción; ésta
    NO anula nada y EXIGE que la guía ya no esté. Anular tiene su propia
    pantalla en Guías R, y hacerlo también acá sería la misma operación
    escrita dos veces — la copia que se separe anularía guías que la otra
    puerta no anula.

    Es además la MISMA precondición que pide `corregir_recepcion_compra`, con
    el mismo orden y nombrando la guía igual: mientras la guía viva exista,
    la compra y la guía dicen lo mismo uno a uno y sacarle la marca a una
    dejaría a la otra afirmando un reproceso que nadie declaró.

    Deshacerlo NO MUEVE NINGÚN NÚMERO. Medido contra el esquema real: el
    stock del artículo da lo mismo antes de la guía, con la guía, anulada y
    desmarcada — y con las cajas YA ARMADAS el armado vuelve a tomar del
    cajón, con `sin_lote` en cero. El reparto se rejuega en cada lectura.

    NO se restringe a las recepcionadas: una compra pendiente mal marcada se
    corrige desde Editar Compra, pero negarlo acá sería una pared en un
    camino que no molesta a nadie.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT ficha_en_origen_id FROM compras WHERE id = %s", (compra_id,)
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa compra no existe.")
            if fila[0] is None:
                raise ValueError("Esta compra no está marcada como armada en caja nuestra.")

            vivas = _guias_en_origen_vivas(cursor, compra_id)
            if vivas:
                raise ValueError(
                    "Esta compra todavía tiene viva la guía R "
                    + ", ".join(f"R{g}" for g in vivas)
                    + ". Anulá esa guía desde Guías R y volvé."
                )

            cursor.execute(
                "UPDATE compras SET ficha_en_origen_id = NULL WHERE id = %s", (compra_id,)
            )
        conexion.commit()
    finally:
        conexion.close()


def _mismo_dia_otra_hora(momento, nuevo_dia):
    """El mismo instante trasladado a `nuevo_dia`, conservando la HORA.

    No es cosmético: `procesada_el` es a la vez la fecha que mueve el stock Y
    el desempate del FIFO adentro del día (`momento_orden` de un lote de compra
    ES esta columna). Mover el día poniendo una hora inventada —medianoche, o
    `now()`— le cambia el lugar a la compra entre las demás recepciones de ese
    día, que es un segundo cambio que nadie pidió.

    Trabaja en hora ARGENTINA, que es la zona en la que `procesada_el` se lee
    en todas las cuentas: tomar la hora en UTC movería el día en las compras de
    la tarde.
    """
    from zoneinfo import ZoneInfo

    argentina = ZoneInfo("America/Argentina/Buenos_Aires")
    local = momento.astimezone(argentina)
    return local.replace(year=nuevo_dia.year, month=nuevo_dia.month, day=nuevo_dia.day)


def _guia_de_compra(cursor, fecha_operacion, proveedor_id: int) -> tuple[int, int]:
    """La guía de ese proveedor ese día —creándola si no existe— y el punto que sigue.

    Sale de `crear_compra`, donde estaba escrito en línea: mover una compra de
    día es MUDARLA a la guía del día nuevo, y hacerlo con un `insert` copiado
    sería la misma regla en dos lugares. La guía es `unique (fecha_operacion,
    proveedor_id)`, así que el `on conflict do nothing` la reusa.

    El punto es `count + 1` de esa guía y NO se renumera nada: el número es el
    renglón del papel del proveedor y ya está escrito en otro lado.
    """
    cursor.execute(
        """
        INSERT INTO guias_compra (fecha_operacion, proveedor_id)
        VALUES (%s, %s)
        ON CONFLICT (fecha_operacion, proveedor_id) DO NOTHING
        """,
        (fecha_operacion, proveedor_id),
    )
    cursor.execute(
        "SELECT id FROM guias_compra WHERE fecha_operacion = %s AND proveedor_id = %s",
        (fecha_operacion, proveedor_id),
    )
    (guia_id,) = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM compras WHERE guia_id = %s", (guia_id,))
    (cuantas,) = cursor.fetchone()
    return guia_id, cuantas + 1


def mover_compra_de_fecha(compra_id: int, nueva_fecha, nueva_recepcion=None) -> dict:
    # nueva_fecha y nueva_recepcion son DATES. La hora de la recepción no se
    # pide ni se inventa: se conserva la que tenía (ver _mismo_dia_otra_hora).
    """Mueve una compra de día: su fecha, su GUÍA y —si está recepcionada— su recepción.

    SON DOS FECHAS Y NO UNA, a propósito. Una compra puede ser del 09 y haberse
    recibido el 14: ese hueco es real y aplastarlo sería inventar un dato.

      - `fecha_operacion` es el día de la compra. Mueve la ventana del costeo y
        las búsquedas, y decide EN QUÉ GUÍA está. NO mueve el stock.
      - `procesada_el` es cuándo entró al depósito. Es la que mueve el stock, el
        FIFO y el orden de los lotes — medido el 19/09: cambiar sola la primera
        deja el stock exactamente donde estaba.

    Devuelve {"guia_id", "guia_punto", "guia_vieja_id", "quedo_vacia"}, para que
    la pantalla pueda decir a qué guía fue a parar y si la vieja quedó sin
    renglones. La guía vieja NO se borra aunque se vacíe: el número es el papel
    del proveedor y no se recicla.

    TRES GUARDAS, y las tres acá porque acá se escribe — un formulario armado a
    mano no ve ningún cartel:

    1. **El CORTE es un freno y no un aviso.** Una compra recibida el día del
       corte o antes ya está adentro de la foto, que se toma a la tarde; meterla
       ADEMÁS como lote la cuenta dos veces. Medido: con la recepción movida al
       día del corte, el FIFO se queda sin el lote (`lotes 1 -> 0`, `sin_lote
       0 -> 4`) y el Remanente NO SE MUEVE. Del otro lado no queda un dato raro
       para mirar: quedan dos cuentas del mismo hecho contradiciéndose sin que
       nada se ponga rojo.
    2. **La guía R `en_origen` viva.** Esa guía dice uno a uno lo mismo que la
       compra; moverle el día a una y no a la otra las separa en silencio. Misma
       precondición que Corregir Recepción y que el desmarcar, y por eso sale de
       `_guias_en_origen_vivas` y no de un SELECT copiado.
    3. **La recepción no puede ser anterior a la compra.** Es el único orden que
       el mundo impone: la mercadería no entra al depósito antes de comprarse.

    LO QUE NO FRENA, por decisión del dueño (19/09): una guía R NORMAL viva
    sobre el lote. Esa AVISA con su nombre y él decide — frenar ahí lo deja otra
    vez sin salida, que es el problema que esto viene a resolver. Lo que salga
    sin lote se ve en Stock por Guía y en el Remanente.

    Y NO RECALCULA NADA DE LO CONGELADO. `reprocesos_consumos` y los costos de
    la guía R quedan como están: son un documento de lo que se decidió aquel
    día. Qué quedó viejo lo dice la pantalla DESPUÉS de guardar.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # SIN agregado: `fetchone() is None` sobre un `count(*)` nunca es
            # None y no distinguiría "no existe" de "existe" (corolario 27).
            cursor.execute(
                """
                SELECT proveedor_id, fecha_operacion, estado, procesada_el, guia_id
                FROM compras WHERE id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa compra no existe.")
            proveedor_id, fecha_vieja, estado, procesada_vieja, guia_vieja_id = fila

            vivas = _guias_en_origen_vivas(cursor, compra_id)
            if vivas:
                raise ValueError(
                    "Esta compra llegó armada en caja nuestra y generó la guía R "
                    + ", ".join(f"R{g}" for g in vivas)
                    + ". Esa guía dice lo mismo que la compra, uno a uno: anulala "
                    "desde Guías R y volvé."
                )

            if estado == "recepcionado":
                if nueva_recepcion is None:
                    raise ValueError(
                        "Esta compra está recepcionada: hace falta también la fecha "
                        "en que entró al depósito, que es la que mueve el stock."
                    )
                if nueva_recepcion < nueva_fecha:
                    raise ValueError(
                        "La recepción no puede ser anterior a la compra: la "
                        "mercadería no entra al depósito antes de comprarse."
                    )
                corte = _fecha_corte(cursor)
                if nueva_recepcion <= corte:
                    raise ValueError(
                        f"El conteo del corte es del {corte:%d/%m} y se toma a la tarde, "
                        "así que una compra recibida ese día o antes ya está contada "
                        "adentro de esa foto. Fechar la recepción ahí la contaría dos "
                        "veces: el Remanente la seguiría sumando y el FIFO se quedaría "
                        f"sin el lote. La recepción tiene que ser posterior al {corte:%d/%m}."
                    )

            guia_id, guia_punto = _guia_de_compra(cursor, nueva_fecha, proveedor_id)

            if estado == "recepcionado":
                cursor.execute(
                    """
                    UPDATE compras
                    SET fecha_operacion = %s, guia_id = %s, guia_punto = %s, procesada_el = %s
                    WHERE id = %s
                    """,
                    (nueva_fecha, guia_id, guia_punto,
                     _mismo_dia_otra_hora(procesada_vieja, nueva_recepcion), compra_id),
                )
            else:
                # Sin recepción no hay `procesada_el` que mover, y escribirlo
                # igual (en NULL) sería pisar con un dato que esta operación no
                # tiene por qué conocer.
                cursor.execute(
                    "UPDATE compras SET fecha_operacion = %s, guia_id = %s, guia_punto = %s WHERE id = %s",
                    (nueva_fecha, guia_id, guia_punto, compra_id),
                )

            quedo_vacia = False
            if guia_vieja_id is not None and guia_vieja_id != guia_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM compras WHERE guia_id = %s", (guia_vieja_id,)
                )
                (restantes,) = cursor.fetchone()
                quedo_vacia = restantes == 0
        conexion.commit()
        return {
            "guia_id": guia_id,
            "guia_punto": guia_punto,
            "guia_vieja_id": guia_vieja_id,
            "quedo_vacia": quedo_vacia,
            "fecha_vieja": fecha_vieja,
            "recepcion_vieja": procesada_vieja,
        }
    finally:
        conexion.close()


def corregir_recepcion_compra(
    compra_id: int,
    cantidad_cajones_real: float,
    valor_real: float,
    cantidad_cajones_rechazada: float | None = None,
    motivo_rechazo: str | None = None,
    segunda_real: float | None = None,
) -> None:
    """Corrige los valores reales de una compra YA recepcionada (ej. error de tipeo al recepcionar en Depósito).

    Mismo significado de valor_real que recepcionar_compra (ver
    _derivar_valores_reales), y misma cuenta para derivar los otros
    campos. También corrige el rechazo parcial (bultos devueltos y
    motivo): lo que venga acá pisa lo guardado — None borra un rechazo
    mal cargado. A diferencia de recepcionar_compra, esto NO cambia el
    estado (sigue "recepcionado") ni toca procesada_el ni el retiro — es
    una corrección del número ya cargado, no una recepción nueva.
    Bloqueada (ValueError) si la compra no está recepcionada: no hay
    valores reales que corregir en una que nunca se pesó/contó de verdad.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.estado, a.unidad_compra, c.cantidad_kilos, c.cantidad_fraccion
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            estado, unidad_compra, cantidad_kilos, cantidad_fraccion = fila if fila else (None, None, None, None)

            if estado != "recepcionado":
                raise ValueError("Esta compra no está recepcionada, no hay valores reales para corregir.")

            # Si esta compra llegó ya armada en caja nuestra, su guía R dice
            # EXACTAMENTE lo que dice la compra (uno a uno). Corregir los
            # cajones acá dejaría la compra en 12 y la guía en 10, sin que
            # nada avise: un descuadre silencioso entre el lote y lo que se
            # armó de él. Se bloquea y se nombra la guía, porque un error que
            # no dice qué lo retiene manda a adivinar.
            guias = _guias_en_origen_vivas(cursor, compra_id)
            if guias:
                raise ValueError(
                    "Esta compra llegó armada en caja nuestra y generó la guía R "
                    + ", ".join(f"R{g}" for g in guias)
                    + ". Anulá esa guía y volvé a recepcionar la compra."
                )

            _exigir_la_segunda_si_la_compra_la_declaro(cantidad_kilos, cantidad_fraccion, segunda_real)
            (contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real,
             segunda_por_cajon_real) = _derivar_valores_reales(
                unidad_compra, cantidad_cajones_real, valor_real, segunda_real
            )

            cursor.execute(
                """
                UPDATE compras
                SET cantidad_cajones_real = %s,
                    contenido_por_cajon_real = %s,
                    cantidad_kilos_real = %s,
                    cantidad_fraccion_real = %s,
                    segunda_por_cajon_real = %s,
                    cantidad_cajones_rechazada = %s,
                    motivo_rechazo = %s
                WHERE id = %s
                """,
                (
                    cantidad_cajones_real,
                    contenido_por_cajon_real,
                    cantidad_kilos_real,
                    cantidad_fraccion_real,
                    segunda_por_cajon_real,
                    cantidad_cajones_rechazada,
                    motivo_rechazo,
                    compra_id,
                ),
            )
        conexion.commit()
    finally:
        conexion.close()


def rechazar_compra(compra_id: int) -> str | None:
    """Marca una compra como rechazada. No toca ningún valor real — nada se pesó ni se contó.

    Igual que recepcionar_compra, también marca la compra como retirada
    si todavía no lo estaba (ver _auto_retirar_si_corresponde) — rechazar
    algo en Depósito también implica que llegó hasta ahí. Devuelve el
    aviso de esa función (o None).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE compras SET estado = 'rechazado', procesada_el = now() WHERE id = %s",
                (compra_id,),
            )
            aviso = _auto_retirar_si_corresponde(cursor, compra_id)
        conexion.commit()
        return aviso
    finally:
        conexion.close()


def marcar_compra_no_ingresada(compra_id: int) -> None:
    """Marca una compra como no_ingresado: nunca llegó al depósito (no se la fueron a buscar, se perdió, etc.).

    A diferencia de recepcionar_compra/rechazar_compra, NO llama a
    _auto_retirar_si_corresponde: si la mercadería nunca llegó al
    depósito, no hay ninguna base para asumir que sí se retiró del
    puesto en el Mercado — estado_retiro queda exactamente como estaba.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE compras SET estado = 'no_ingresado', procesada_el = now() WHERE id = %s",
                (compra_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def compra_tiene_deshacer_recepcion_bloqueado(estado: str | None) -> bool:
    """True si ya no se puede deshacer lo que se marcó en Recepción (ver /deposito/recepcion, deshacer_procesado_compra).

    Única definición de esta regla — la usan el panel "Procesados hoy" de
    Recepción (para mostrar el botón Deshacer o el aviso de por qué no) y
    deshacer_procesado_compra (para bloquear el guardado de verdad).

    Solo bloquea 'recepcionado'. Recepcionar escribe cantidades reales y
    CREA UN LOTE de stock: deshacerlo movería stock, FIFO y costos ya
    congelados en reprocesos_consumos. Eso no se deshace desde acá — se
    corrige por Corregir Recepción, en Gerencia. El rechazo parcial es
    una recepción (queda 'recepcionado'), así que cae en el mismo lado.

    'no_ingresado' y 'rechazado' SÍ se pueden volver a pendiente: ninguno
    de los dos escribió un valor real ni creó un lote (la única FK que
    apunta a compras es reprocesos_consumos.compra_id, y ahí solo entran
    lotes de compras recepcionadas). No hay ningún número de stock ni
    ningún costo congelado que se pueda mover al deshacerlos.

    OJO: compra_tiene_deshacer_retiro_bloqueado (el Deshacer de Logística)
    devuelve el mismo par de estados que devolvía esta, y NO acompaña este
    cambio: son dos reglas distintas que coincidían en el valor. Mientras
    la compra está rechazada, la mercadería sí llegó al depósito, y
    Logística no tiene que poder desmarcar ese retiro.
    """
    return estado == "recepcionado"


def deshacer_procesado_compra(compra_id: int) -> str | None:
    """Vuelve una compra marcada "No ingresó" o con "Rechazo total" a pendiente de recepción (deshacer, ver /deposito/recepcion).

    Vuelve estado a 'pendiente' y borra procesada_el junto con todos los
    valores reales (cantidad_cajones_real, contenido_por_cajon_real,
    cantidad_kilos_real, cantidad_fraccion_real) — ni marcar_compra_no_
    ingresada ni rechazar_compra los llegan a cargar, se limpian igual acá
    por las dudas, mismo criterio "sin cicatriz" que deshacer_retiro_compra.
    Bloqueada (ValueError) si compra_tiene_deshacer_recepcion_bloqueado ya
    dio True — re-chequeado acá adentro, no solo en la pantalla.

    El retiro se revierte SOLO si lo escribió este mismo rechazo, o sea si
    retiro_origen = 'deposito' (rechazar_compra llama a _auto_retirar_si_
    corresponde, que marca retirado con ese origen si el retiro estaba
    pendiente). Se puede afirmar que fue el rechazo y no otra cosa porque
    una compra rechazada NUNCA pasó por recepción, y recepcionar es lo
    único que escribe ese origen. Cualquier otro origen es un tilde de
    Logística y no se pisa; 'cancelado' tampoco, porque _auto_retirar
    tampoco lo había pisado. Sin esta reversión el deshacer no destraba
    nada: eliminar_compra bloquea por estado_retiro = 'retirado'.

    Devuelve el estado que se deshizo ('rechazado' o 'no_ingresado'),
    para que la pantalla pueda decir qué se deshizo.

    Al volver a 'pendiente' la compra REENTRA al costeo con el estimado
    (listar_compras_para_costeo excluye 'rechazado' y 'no_ingresado'). Por
    eso el botón vive solo dentro del día, en "Procesados hoy": deshacer
    un rechazo viejo le movería la cotización a un día ya cerrado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT estado, retiro_origen FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            estado, retiro_origen = fila if fila else (None, None)

            if compra_tiene_deshacer_recepcion_bloqueado(estado):
                raise ValueError("Esta compra ya fue recepcionada, no se puede deshacer.")

            cursor.execute(
                """
                UPDATE compras
                SET estado = 'pendiente', procesada_el = NULL,
                    cantidad_cajones_real = NULL, contenido_por_cajon_real = NULL,
                    cantidad_kilos_real = NULL, cantidad_fraccion_real = NULL
                WHERE id = %s
                """,
                (compra_id,),
            )

            if estado == "rechazado" and retiro_origen == "deposito":
                cursor.execute(
                    """
                    UPDATE compras
                    SET estado_retiro = 'pendiente', retiro_procesado_el = NULL, retiro_origen = NULL
                    WHERE id = %s
                    """,
                    (compra_id,),
                )
        conexion.commit()
        return estado
    finally:
        conexion.close()


def listar_compras_procesadas_hoy_recepcion(fecha) -> list[dict]:
    """Compras marcadas recepcionado/rechazado/no_ingresado HOY, para la tarjeta efímera y el panel
    "Procesados hoy" de /deposito/recepcion. Más recientes primero.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, a.nombre AS articulo_nombre, a.unidad_compra,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.cantidad_cajones, c.contenido_por_cajon,
                       c.cantidad_cajones_real, c.contenido_por_cajon_real,
                       c.estado, c.procesada_el,
                       (SELECT COUNT(*) FROM fotos_recepcion f WHERE f.compra_id = c.id) AS fotos_balanza
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.estado IN ('recepcionado', 'rechazado', 'no_ingresado')
                  AND c.procesada_el >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND c.procesada_el < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                ORDER BY c.procesada_el DESC
                """,
                (fecha, fecha),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def _condiciones_buscar_retiros(
    fecha_desde, fecha_hasta, proveedor_id, articulo_id, tipo_retiro, estado_retiro
) -> tuple[list[str], list]:
    """El WHERE dinámico de Consultar Retiros, compartido entre la búsqueda y su contador."""
    condiciones = ["c.fecha_operacion BETWEEN %s AND %s"]
    parametros: list = [fecha_desde, fecha_hasta]

    if proveedor_id is not None:
        condiciones.append("c.proveedor_id = %s")
        parametros.append(proveedor_id)
    if articulo_id is not None:
        condiciones.append("c.articulo_id = %s")
        parametros.append(articulo_id)
    if tipo_retiro is not None:
        condiciones.append("c.tipo_retiro = %s")
        parametros.append(tipo_retiro)
    if estado_retiro == "pendiente":
        condiciones.append("c.estado_retiro IS DISTINCT FROM 'retirado' AND c.estado_retiro IS DISTINCT FROM 'cancelado'")
    elif estado_retiro is not None:
        condiciones.append("c.estado_retiro = %s")
        parametros.append(estado_retiro)
    return condiciones, parametros


def contar_retiros_buscados(
    fecha_desde,
    fecha_hasta,
    proveedor_id: int | None = None,
    articulo_id: int | None = None,
    tipo_retiro: str | None = None,
    estado_retiro: str | None = None,
) -> int:
    """Cuántos retiros matchean los filtros de Consultar Retiros — para el aviso "primeras N de M"."""
    condiciones, parametros = _condiciones_buscar_retiros(
        fecha_desde, fecha_hasta, proveedor_id, articulo_id, tipo_retiro, estado_retiro
    )
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM compras c WHERE {' AND '.join(condiciones)}", parametros)
            (total,) = cursor.fetchone()
        return int(total)
    finally:
        conexion.close()


def buscar_retiros(
    fecha_desde,
    fecha_hasta,
    proveedor_id: int | None = None,
    articulo_id: int | None = None,
    tipo_retiro: str | None = None,
    estado_retiro: str | None = None,
    limite: int | None = None,
) -> list[dict]:
    """El histórico de Logística (ver /logistica/consultar): retiros entre dos fechas, con filtros opcionales.

    estado_retiro: 'pendiente' incluye también las filas con estado NULL
    (compras de antes de que existiera Retiro) — mismo criterio que
    listar_compras_pendientes_retiro: lo raro se muestra, no desaparece.
    'retirado'/'cancelado' filtran exacto. None trae todo.

    limite: tope de filas para la pantalla (mismo criterio que
    buscar_compras); el export pasa None.

    Cada fila trae cantidad_cajones (lo que cargó el comprador) y
    cantidad_cajones_retirada (lo anotado al retirar, si se anotó): el
    total de bultos para liquidar al carrero/cooperativa lo arma quien
    llama con COALESCE de esos dos — acá se devuelven separados para poder
    mostrar de dónde sale cada número.

    También trae c.estado (el veredicto de Depósito): una compra
    'no_ingresado' figura retirada (Carro/Cooperativa nacen así solas)
    pero la mercadería nunca llegó — la pantalla la marca y desglosa el
    total para no pagarle al carrero bultos que no trajo.
    """
    condiciones, parametros = _condiciones_buscar_retiros(
        fecha_desde, fecha_hasta, proveedor_id, articulo_id, tipo_retiro, estado_retiro
    )
    tope_sql = ""
    if limite is not None:
        tope_sql = "LIMIT %s"
        parametros = parametros + [limite]

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.id, c.fecha_operacion, c.retiro_procesado_el, c.tipo_retiro, c.estado_retiro,
                       c.estado, c.cantidad_cajones, c.cantidad_cajones_retirada,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       a.nombre AS articulo_nombre
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE {" AND ".join(condiciones)}
                ORDER BY c.fecha_operacion DESC, p.nombre, a.nombre
                {tope_sql}
                """,
                parametros,
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def _condiciones_buscar_ingresos(fecha_desde, fecha_hasta, proveedor_id, articulo_id, estado):
    """Las condiciones de Ingresos a Depósito (ver /facturacion/ingresos), compartidas entre buscar y contar.

    El rango filtra por procesada_el (el día en que Depósito la procesó,
    patrón sargable sobre el índice de procesada_el): el listado es de lo
    que ENTRÓ, no de lo que se compró. Las pendientes quedan afuera solas
    (procesada_el NULL).

    estado: 'recepcionado' (lo que hay que pagar, incluye los rechazos
    parciales — son recepciones), 'rechazado', 'no_ingresado', o None =
    las tres (para controlar).
    """
    condiciones = ["c.procesada_el >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')", "c.procesada_el < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')"]
    parametros: list = [fecha_desde, fecha_hasta]
    if proveedor_id is not None:
        condiciones.append("c.proveedor_id = %s")
        parametros.append(proveedor_id)
    if articulo_id is not None:
        condiciones.append("c.articulo_id = %s")
        parametros.append(articulo_id)
    if estado is None:
        condiciones.append("c.estado IN ('recepcionado', 'rechazado', 'no_ingresado')")
    else:
        condiciones.append("c.estado = %s")
        parametros.append(estado)
    return condiciones, parametros


def buscar_ingresos_deposito(
    fecha_desde,
    fecha_hasta,
    proveedor_id: int | None = None,
    articulo_id: int | None = None,
    estado: str | None = "recepcionado",
    limite: int | None = None,
) -> list[dict]:
    """Lo que realmente entró a la empresa (ver /facturacion/ingresos): recepciones entre dos fechas.

    Trae SIEMPRE las columnas reales (cantidad_cajones_real,
    contenido_por_cajon_real — lo que Depósito pesó/contó) y no las del
    comprador: para facturar y pagarle al proveedor vale lo que entró.
    El rechazo parcial viaja aparte (cantidad_cajones_rechazada, motivo)
    para explicar por qué el número no coincide con lo comprado.

    Ordenado por proveedor (y adentro por recepción): así quien llama
    arma los subtotales por proveedor recorriendo una sola vez.

    limite: tope de filas para la pantalla (mismo criterio que
    buscar_compras/buscar_retiros); el export pasa None.
    """
    condiciones, parametros = _condiciones_buscar_ingresos(fecha_desde, fecha_hasta, proveedor_id, articulo_id, estado)
    tope_sql = ""
    if limite is not None:
        tope_sql = "LIMIT %s"
        parametros = parametros + [limite]

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.id, c.fecha_operacion, c.procesada_el, c.guia_id, c.guia_punto, c.estado,
                       c.cantidad_cajones_real, c.contenido_por_cajon_real,
                       -- Las dos magnitudes REALES: acá se muestra lo que ENTRÓ, no lo
                       -- declarado. En NULL es "no se declaró", y la pantalla lo muestra
                       -- como hueco: es lo que explica por qué esa compra no costea en la
                       -- otra unidad.
                       c.cantidad_kilos_real, c.cantidad_fraccion_real,
                       c.cantidad_cajones_rechazada, c.motivo_rechazo, c.importe, c.sena,
                       a.nombre AS articulo_nombre, a.unidad_compra, a.unidad_conteo,
                       c.segunda_por_cajon,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE {" AND ".join(condiciones)}
                ORDER BY p.nombre, p.codigo_puesto, c.procesada_el, c.id
                {tope_sql}
                """,
                parametros,
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def contar_ingresos_deposito(
    fecha_desde,
    fecha_hasta,
    proveedor_id: int | None = None,
    articulo_id: int | None = None,
    estado: str | None = "recepcionado",
) -> int:
    """Cuántos ingresos matchean los filtros de buscar_ingresos_deposito — para el aviso del tope."""
    condiciones, parametros = _condiciones_buscar_ingresos(fecha_desde, fecha_hasta, proveedor_id, articulo_id, estado)
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM compras c WHERE {' AND '.join(condiciones)}", parametros)
            (total,) = cursor.fetchone()
        return int(total)
    finally:
        conexion.close()


# EL RECORTE, escrito UNA vez: lo usan el conteo y la lista. Con un WHERE
# cada una, el banner diría un número y la pantalla listaría otro — es la
# regla escrita dos veces, en su versión más barata de evitar.
# Lo que se comparte es EL WHERE, que es la regla; el FROM y los JOIN los
# escribe cada consulta, porque la lista necesita el artículo y el proveedor
# y el conteo no. Partido así no hay que hacerle cirugía de texto a una
# constante compartida para reusarla.
_SQL_COMPRAS_SIN_PRECIO_DONDE = """
    WHERE c.importe IS NULL
      AND c.estado IN ('pendiente', 'recepcionado')
      AND c.estado_retiro IN ('pendiente', 'retirado')
"""


def contar_compras_sin_precio() -> dict:
    """Compras que siguen sin precio de compra cargado, y la más vieja.

    Plata que no se sabe cuánto costó: mientras falte, el costeo del día
    siguiente sale mal. Por eso NO tiene ventana de tiempo — no se espera a que
    la compra "envejezca" para avisar, y no deja de avisar por vieja: un
    agujero sigue siendo un agujero tenga un día o tres meses, hasta que
    alguien le carga el precio.

    El filtro por ESTADO es lo que la hace accionable: una compra rechazada o
    cancelada NUNCA va a tener precio, así que contarla es ruido. Esta versión
    reemplaza a la vieja contar_compras_sin_precio_viejas, que filtraba por
    fecha y NO por estado: contaba rechazadas de hace meses y se perdía las de
    hoy. Las dos convivían —el banner con una, Auditoría con la otra— y
    llegaron a devolver el mismo número contando compras distintas.

    Sigue apoyada en el índice parcial compras_sin_precio_idx (solo las filas
    sin precio): sacar el filtro de fecha no lo desaprovecha, porque lo que
    achica la tabla es el "importe IS NULL", no la fecha.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*), MIN(c.fecha_operacion) FROM compras c"
                + _SQL_COMPRAS_SIN_PRECIO_DONDE
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def contar_stock_vacios_negativos() -> int:
    """Auditoría: cuántos pares proveedor+tipo de Vacíos tienen stock por debajo de cero.

    Menos que cero es imposible en el mundo real: si pasa hay un error de
    carga (o faltó registrar entradas). Misma cuenta que stock_vacios(),
    solo el conteo; los índices parciales *_stock_idx cubren los SUM.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM tipos_envase_puesto t
                LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM vacios_recibidos
                           WHERE anulado_el IS NULL GROUP BY tipo_envase_id) r ON r.tipo_envase_id = t.id
                LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM vacios_devueltos
                           WHERE anulado_el IS NULL GROUP BY tipo_envase_id) d ON d.tipo_envase_id = t.id
                LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM ajustes_vacios
                           WHERE anulado_el IS NULL GROUP BY tipo_envase_id) aj ON aj.tipo_envase_id = t.id
                WHERE COALESCE(r.total, 0) - COALESCE(d.total, 0) + COALESCE(aj.total, 0) < 0
                """
            )
            (casos,) = cursor.fetchone()
        return int(casos)
    finally:
        conexion.close()


# LAS DOS MITADES DEL PROBLEMA, escritas UNA vez cada una. Las usan el
# conteo (como filtro) y la lista (como filtro Y como columna, para decir
# CUÁL de las dos falta). Sin esto, la columna que explica el caso y el
# criterio que lo selecciona serían dos reglas y se separarían.
_SQL_SIN_FICHA = ("NOT EXISTS (SELECT 1 FROM fichas_logistica f"
                  " WHERE f.articulo_id = comprados.articulo_id)")
_SQL_SIN_PRECIO_DE_VENTA = ("NOT EXISTS (SELECT 1 FROM precios_venta_historial p"
                            " WHERE p.articulo_id = comprados.articulo_id"
                            " AND p.vigente_desde <= %s)")

# El bloque interno completo: los comprados desde la fecha, con las dos
# marcas puestas. El orden de los %s es el del TEXTO — primero el de
# `sin_precio` (está en el SELECT) y después el de la ventana (está en el
# FROM)— y por eso los dos llamadores pasan (hoy, fecha_desde) y no al revés.
_SQL_INCOTIZABLES = f"""
    FROM (
        SELECT comprados.articulo_id,
               {_SQL_SIN_FICHA} AS sin_ficha,
               {_SQL_SIN_PRECIO_DE_VENTA} AS sin_precio
        FROM (SELECT DISTINCT c.articulo_id FROM compras c
               WHERE c.fecha_operacion >= %s) comprados
    ) x
"""


def contar_articulos_comprados_incotizables(fecha_desde, hoy) -> int:
    """Auditoría: artículos con compras desde fecha_desde que no se pueden cotizar para NINGÚN cliente.

    "No se puede cotizar" = sin ficha logística en ningún cliente, o sin
    ningún precio de venta vigente. Los faltantes por cliente puntual ya
    los avisan Objetivo de Compra y Márgenes al elegir ese cliente; acá
    se cazan los agujeros totales, que son los graves.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*)" + _SQL_INCOTIZABLES + " WHERE x.sin_ficha OR x.sin_precio",
                (hoy, fecha_desde),
            )
            (casos,) = cursor.fetchone()
        return int(casos)
    finally:
        conexion.close()


def listar_articulos_comprados_incotizables(fecha_desde, hoy) -> list[dict]:
    """Los mismos artículos que cuenta contar_articulos_comprados_incotizables.

    Y trae CUÁL DE LAS DOS COSAS falta, que es lo único que vuelve accionable
    el número: "sin ficha" se arregla en Fichas y "sin precio" en Cargar
    Precios — son dos pantallas distintas del mismo sector. Un artículo puede
    tener las dos.

    Las marcas salen de las MISMAS expresiones que filtran (_SQL_SIN_FICHA y
    _SQL_SIN_PRECIO_DE_VENTA), no de repetirlas: si la columna dijera una cosa
    y el filtro otra, la lista mostraría casos que no explica.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT a.nombre AS articulo, x.sin_ficha, x.sin_precio"
                + _SQL_INCOTIZABLES
                + """ JOIN articulos a ON a.id = x.articulo_id
                      WHERE x.sin_ficha OR x.sin_precio
                      ORDER BY a.nombre""",
                (hoy, fecha_desde),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def contar_senas_pendientes_viejas(fecha_limite) -> dict:
    """Auditoría: señas de Vacíos sin resolver de antes de fecha_limite, y la más vieja.

    Plata que se le debe a alguien y quedó colgada: el circuito normal las
    cierra en el día (pagada, vale o anulada).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN(creado_en) FROM vacios_recibidos v
                WHERE v.sena_pagada_el IS NULL AND v.sena_vale_el IS NULL AND v.sena_anulada_el IS NULL
                  AND v.anulado_el IS NULL
                  AND v.creado_en < ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                """,
                (fecha_limite,),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def contar_retiros_pendientes_viejos(fecha_limite) -> dict:
    """Auditoría: cuántas compras siguen sin retirar con fecha_operacion de fecha_limite para atrás, y la más vieja.

    Mismo criterio de "pendiente" que la pantalla de Retiro (IS DISTINCT
    FROM, los NULL raros cuentan). Consulta de conteo liviana: usa el
    índice parcial compras_pendientes_retiro_idx.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN(fecha_operacion) FROM compras c
                WHERE c.estado_retiro IS DISTINCT FROM 'retirado'
                  AND c.estado_retiro IS DISTINCT FROM 'cancelado'
                  AND c.fecha_operacion <= %s
                """,
                (fecha_limite,),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def contar_recepciones_pendientes_viejas(fecha_limite) -> dict:
    """Auditoría: compras sin recepcionar (ni rechazar ni marcar no ingresada) de fecha_limite para atrás.

    Mismo filtro que la pantalla de Recepción (estado pendiente con guía).
    Usa el índice parcial compras_pendientes_recepcion_idx.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN(fecha_operacion) FROM compras c
                WHERE c.estado = 'pendiente' AND c.guia_id IS NOT NULL
                  AND c.fecha_operacion <= %s
                """,
                (fecha_limite,),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def contar_recepciones_sin_pesaje(desde) -> dict:
    """Recepciones sin NINGUNA evidencia de que alguien haya pesado, desde una fecha.

    Sin evidencia son DOS condiciones a la vez, y hacen falta las dos:

      · **no hay foto de balanza** — y está medido que la foto es lo que hace
        que se pese, no lo que lo documenta: con foto se corrige el 63% de las
        recepciones y sin foto el 8%, medido en la misma ventana de días para
        que no sea el período el que cambió; y
      · **el contenido real quedó igual al estimado** (o en NULL), que es
        apretar Recibir con el número precargado.

    Cada una sola NO alcanza, y por eso no es un `OR`. Tocar el número es
    pesaje aunque no haya foto: el que corrigió 16 por 18 pesó. Y una foto con
    el número sin tocar puede ser perfectamente "pesé y dio 16" — ahí la foto
    ES la evidencia. Lo que no tiene ninguna defensa es el cruce.

    LO QUE ESTA CUENTA NO PUEDE HACER, dicho acá para que nadie lo lea de
    más: distinguir "lo pesaron y dio exactamente el estimado" de "lo
    aceptaron sin mirar". Son indistinguibles en la base y siempre lo van a
    ser. Por eso la alerta cuenta los que no tienen NINGUNA de las dos
    señales, que es el conjunto más chico del que se puede afirmar algo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN(c.procesada_el)
                FROM compras c
                WHERE c.estado = 'recepcionado'
                  -- EN ZONA ARGENTINA, como el resto del modulo:
                  -- procesada_el es timestamptz y compararlo contra una
                  -- fecha pelada mueve la ventana tres horas segun de
                  -- que lado del mediodia UTC caiga. Lo agarro el test
                  -- que barre las consultas buscando justo esto.
                  AND (c.procesada_el AT TIME ZONE
                       'America/Argentina/Buenos_Aires')::date >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM fotos_recepcion f WHERE f.compra_id = c.id
                  )
                  -- IS NOT DISTINCT FROM y no `=`: con el real en NULL la
                  -- comparacion daria NULL y la fila se caeria del WHERE,
                  -- que es justo la recepcion que menos evidencia tiene.
                  AND (c.contenido_por_cajon_real IS NULL
                       OR c.contenido_por_cajon_real
                          IS NOT DISTINCT FROM c.contenido_por_cajon)
                """,
                (desde,),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def listar_recepciones_sin_pesaje(desde) -> list[dict]:
    """Las mismas, con nombre y fecha, para el detalle de la alerta.

    El MISMO recorte que el conteo, escrito una sola vez: si el detalle
    filtrara distinto, el banner diria un numero y la lista mostraria otro, y
    el que abre no sabe cual creer.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, a.nombre AS articulo, p.nombre AS proveedor,
                       c.procesada_el, c.cantidad_cajones_real,
                       c.contenido_por_cajon, a.unidad_compra
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.estado = 'recepcionado'
                  -- EN ZONA ARGENTINA, como el resto del modulo:
                  -- procesada_el es timestamptz y compararlo contra una
                  -- fecha pelada mueve la ventana tres horas segun de
                  -- que lado del mediodia UTC caiga. Lo agarro el test
                  -- que barre las consultas buscando justo esto.
                  AND (c.procesada_el AT TIME ZONE
                       'America/Argentina/Buenos_Aires')::date >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM fotos_recepcion f WHERE f.compra_id = c.id
                  )
                  AND (c.contenido_por_cajon_real IS NULL
                       OR c.contenido_por_cajon_real
                          IS NOT DISTINCT FROM c.contenido_por_cajon)
                ORDER BY c.procesada_el DESC
                """,
                (desde,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_compras_pendientes_retiro(tipo_retiro: str) -> list[dict]:
    """Compras de un tipo de retiro puntual (Clark/Carro/Pases) que todavía no se procesaron en Logística.

    Sin límite de fechas (a diferencia de Recepción, acá puede haber
    compras de hace rato si nadie las retiró todavía). Ordenado por
    código de puesto del proveedor — como cada guía es de un solo
    proveedor, ordenar así ya deja las guías agrupadas de forma natural,
    sin necesidad de un ORDER BY guia_id aparte.

    El filtro es "estado_retiro IS DISTINCT FROM 'retirado' AND ... FROM
    'cancelado'" en vez de "= 'pendiente'" a propósito: si por algún error
    una compra quedara con estado_retiro NULL (no debería pasar — los 4
    métodos de carga pasan todos por crear_compra, que siempre pone
    'pendiente' — pero por las dudas), con este filtro esa fila SIGUE
    apareciendo acá (molesta, se nota, se puede arreglar) en vez de
    desaparecer en silencio para siempre.

    Sin real-si-existe (COALESCE): el retiro pasa ANTES de la recepción,
    ninguna compra pendiente de retiro puede tener un valor real todavía.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.guia_id, c.guia_punto, c.fecha_operacion,
                       a.nombre AS articulo_nombre, a.unidad_compra, a.unidad_conteo,
                       c.segunda_por_cajon,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.cantidad_cajones, c.contenido_por_cajon, c.cantidad_kilos, c.cantidad_fraccion
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.tipo_retiro = %s
                  AND c.estado_retiro IS DISTINCT FROM 'retirado'
                  AND c.estado_retiro IS DISTINCT FROM 'cancelado'
                ORDER BY p.codigo_puesto, c.guia_id, c.guia_punto
                """,
                (tipo_retiro,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def marcar_compra_retirada(compra_id: int, origen: str, cantidad_cajones_retirada: float | None = None) -> None:
    """Marca una compra como retirada del puesto (ver Logística, /logistica/retiro).

    cantidad_cajones_retirada es un dato aparte, opcional, que anota
    quien retira — nunca pisa cantidad_cajones (lo que cargó el
    comprador) ni cantidad_cajones_real (lo que cuenta Depósito al
    recepcionar). Es solo registro: no entra en ningún cálculo (costeo,
    precios, Recepción). None (no se anotó nada) se interpreta como "se
    retiró todo lo cargado" — no hace falta completarlo para eso.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE compras
                SET estado_retiro = 'retirado', retiro_procesado_el = now(), retiro_origen = %s,
                    cantidad_cajones_retirada = %s
                WHERE id = %s
                """,
                (origen, cantidad_cajones_retirada, compra_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def marcar_compra_cancelada(compra_id: int, origen: str) -> None:
    """Marca una compra como cancelada en el retiro: nunca salió del puesto."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE compras
                SET estado_retiro = 'cancelado', retiro_procesado_el = now(), retiro_origen = %s
                WHERE id = %s
                """,
                (origen, compra_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def compra_tiene_deshacer_retiro_bloqueado(estado: str | None) -> bool:
    """True si ya no se puede deshacer un Retirado/Cancelado (ver /logistica/retiro, deshacer_retiro_compra).

    Única definición de esta regla — la usan la tarjeta efímera y el
    panel "Procesados hoy" (para mostrar el botón Deshacer o el aviso de
    por qué no) y deshacer_retiro_compra (para bloquear el guardado de
    verdad). Recepcionada o rechazada: la mercadería llegó y se contó (o
    se rechazó después de contarla) — ahí el retiro ya es un hecho, no
    se puede deshacer. no_ingresado NO bloquea a propósito: significa
    justo lo contrario, que nada llegó, así que no hay ningún motivo
    para impedir que Logística corrija un Retirado/Cancelado hecho por
    error (ver también compra_tiene_deshacer_recepcion_bloqueado, la
    misma idea para el lado de Depósito).
    """
    return estado in ("recepcionado", "rechazado")


def deshacer_retiro_compra(compra_id: int) -> None:
    """Vuelve una compra retirada/cancelada a pendiente de retiro (deshacer, ver /logistica/retiro).

    Vuelve estado_retiro/retiro_procesado_el/retiro_origen/
    cantidad_cajones_retirada a su valor original de antes de marcarla
    — no queda ningún rastro de que hubo un toque y un deshacer (a
    propósito: el objetivo es poder corregir un toque accidental sin
    dejar cicatriz, no auditar quién se equivocó). Bloqueada (ValueError)
    si compra_tiene_deshacer_retiro_bloqueado ya dio True — re-chequeado
    acá adentro, no solo en la pantalla, por si el botón quedó mostrado
    con datos viejos (ej. dos pestañas abiertas).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT estado FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            estado = fila[0] if fila else None

            if compra_tiene_deshacer_retiro_bloqueado(estado):
                raise ValueError("Esta compra ya fue procesada en Depósito, no se puede deshacer el retiro.")

            cursor.execute(
                """
                UPDATE compras
                SET estado_retiro = 'pendiente', retiro_procesado_el = NULL,
                    retiro_origen = NULL, cantidad_cajones_retirada = NULL
                WHERE id = %s
                """,
                (compra_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_compras_procesadas_hoy_retiro(tipo_retiro: str, fecha) -> list[dict]:
    """Compras de un tipo de retiro marcadas retirado/cancelado HOY, para la tarjeta efímera y el panel
    "Procesados hoy" de /logistica/retiro. Más recientes primero (lo último que se tocó, arriba).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, a.nombre AS articulo_nombre, a.unidad_compra, a.unidad_conteo,
                c.segunda_por_cajon,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.cantidad_cajones, c.contenido_por_cajon, c.cantidad_cajones_retirada,
                       c.cantidad_kilos, c.cantidad_fraccion,
                       c.estado_retiro, c.retiro_procesado_el, c.estado
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.tipo_retiro = %s
                  AND c.estado_retiro IN ('retirado', 'cancelado')
                  AND c.retiro_procesado_el >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND c.retiro_procesado_el < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                ORDER BY c.retiro_procesado_el DESC
                """,
                (tipo_retiro, fecha, fecha),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_compras_sin_precio() -> list[dict]:
    """Compras (de cualquier fecha) con importe todavía vacío, para completarlo desde /compras/pendientes.

    Solo las que todavía pueden llegar a venderse: estado en (pendiente,
    recepcionado) y estado_retiro en (pendiente, retirado). Ese recorte sale
    de _SQL_COMPRAS_SIN_PRECIO_DONDE, la MISMA constante que usa
    contar_compras_sin_precio — hasta el 12/09 estaba escrito a mano en las
    dos, que es la regla escrita dos veces esperando separarse. Rechazada,
    no_ingresado o con el retiro cancelado significan que esa mercadería
    nunca se va a vender — no tiene sentido perseguirle el costo, así que
    quedan afuera aunque el importe siga en NULL.

    NOTA para cuando el motor de costeo empiece a leer compras de la base
    (hoy no lo hace): las consultas de costeo tienen que excluir las filas
    con importe IS NULL, son compras sin precio todavía.

    cantidad_cajones/contenido_por_cajon vienen con el valor REAL si ya se
    recepcionó, si no el estimado — mismo criterio que el resto de las
    pantallas de consulta (ver listar_compras_por_rango_fechas).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, a.nombre AS articulo_nombre, a.unidad_compra, a.unidad_conteo,
                c.segunda_por_cajon, c.segunda_por_cajon_real,
                       p.nombre AS proveedor_nombre,
                       p.codigo_puesto AS proveedor_codigo_puesto,
                       COALESCE(c.cantidad_cajones_real, c.cantidad_cajones) AS cantidad_cajones,
                       COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon) AS contenido_por_cajon,
                       -- LAS DOS MAGNITUDES, para que la pantalla no muestre solo la de
                       -- `unidad_compra`. Mismo COALESCE que arriba: lo recibido manda.
                       COALESCE(c.cantidad_kilos_real, c.cantidad_kilos) AS cantidad_kilos,
                       COALESCE(c.cantidad_fraccion_real, c.cantidad_fraccion) AS cantidad_fraccion
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                """
                + _SQL_COMPRAS_SIN_PRECIO_DONDE
                # ASCENDENTE, Y ES A PROPÓSITO: acá lo viejo es lo urgente.
                #
                # Sus dos alertas vecinas —kilos faltantes y bultos faltantes—
                # van por fecha DESCENDENTE, y la diferencia no es un descuido:
                # es que contestan otra pregunta. Aquéllas son RECLAMOS y un
                # reclamo tiene ventana —la compra de hace cuatro días ya no se
                # reclama—, así que arriba va lo de hoy. Ésta es "¿a cuál le
                # falta el precio?", que no vence: una compra sin costear hace
                # cuatro días lleva cuatro días ensuciando la rentabilidad, así
                # que arriba va la más vieja.
                #
                # Queda escrito porque el que vea las tres juntas va a ver dos
                # descendentes y una ascendente, y sin esto no puede distinguir
                # una decisión de un "salió así" — y la va a "corregir".
                + " ORDER BY c.fecha_operacion, p.codigo_puesto, c.cargado_el"
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def actualizar_importe_compra(compra_id: int, importe: float) -> None:
    """Completa el importe de una compra que había quedado sin precio.

    Sella el par del importe como 'pendiente' (ver _sello_del_importe), que
    es la verdad de este camino: el precio no se cargó con la compra ni se
    renegoció — se completó después, desde Compras sin precio.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            sello, sello_params = _sello_del_importe("pendiente", importe)
            cursor.execute(
                f"UPDATE compras SET importe = %s, {sello} WHERE id = %s",
                (importe,) + sello_params + (compra_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def _motivo_por_el_que_no_se_puede_eliminar(cursor, compra_id: int) -> str:
    """Traduce a un mensaje el rechazo del DELETE de eliminar_compra. La regla la decide el SQL (_SQL_COMPRA_BORRABLE), esto solo la cuenta.

    Se llama SOLO cuando el DELETE no borró ninguna fila. El orden importa:
    "No ingresó" va antes que el retiro porque para el usuario el dato
    importante es que Depósito se expidió, no si además estaba retirada.

    Si no encuentra el motivo, LO DICE en vez de tragarlo. Que el SQL
    rechace y esta función no sepa por qué significa que la condición y su
    traducción se separaron, y enterarse de eso es más importante que
    mostrar un mensaje prolijo.
    """
    cursor.execute("SELECT estado, estado_retiro FROM compras WHERE id = %s", (compra_id,))
    fila = cursor.fetchone()
    if fila is None:
        return "Esa compra ya no existe."

    estado, estado_retiro = fila
    if estado == "recepcionado":
        return "Esta compra ya fue recepcionada, no se puede eliminar."
    if estado == "no_ingresado":
        return 'Esta compra quedó registrada como "No ingresó" en Depósito, no se puede eliminar.'
    if estado_retiro == "retirado":
        return "Esta compra ya fue retirada, no se puede eliminar."

    return (
        "No se pudo eliminar la compra y el sistema no sabe por qué: la regla que la rechazó "
        "y el mensaje que la explica se separaron. Avisá que pasó esto."
    )


def _lo_que_cuelga(cursor, compra_id: int) -> list[dict]:
    """Qué apunta a esta compra y le impide desaparecer. Vacío = se puede borrar.

    SON LAS CUATRO FK QUE NO SE PUEDEN LIMPIAR SOLAS. `fotos_recepcion` no
    está acá a propósito: `eliminar_compra` la borra él mismo, porque el
    archivo es de ESTA compra y de ninguna otra.

    Medido el 19/09 contra el esquema real, sacándole el bloqueo por estado al
    DELETE: con cualquiera de estas cuatro puesta, Postgres tira un
    `ForeignKeyViolation` crudo. Un error que no dice qué lo retiene manda a
    adivinar, así que se enumeran antes y se nombran.

    LA MISMA FUNCIÓN la usan la pantalla (para mostrar por qué no se puede,
    ANTES del botón) y la escritura (para rechazar). Preguntadas por separado,
    un día la pantalla ofrece un botón que el POST después rechaza — el
    callejón.

    Cada fila es {"que", "detalle"}: `que` es la clase de cosa —para que el
    que lo lee sepa a qué pantalla ir— y `detalle` la nombra.
    """
    cuelgan = []

    cursor.execute(
        """
        SELECT DISTINCT rp.id FROM reprocesos_consumos rc
        JOIN reprocesos rp ON rp.id = rc.reproceso_id
        WHERE rc.compra_id = %s ORDER BY rp.id
        """,
        (compra_id,),
    )
    for (reproceso_id,) in cursor.fetchall():
        cuelgan.append({"que": "guia_r_consumo",
                        "detalle": f"R{reproceso_id} se costeó contra este lote"})

    cursor.execute(
        "SELECT id FROM reprocesos WHERE compra_origen_id = %s ORDER BY id",
        (compra_id,),
    )
    for (reproceso_id,) in cursor.fetchall():
        cuelgan.append({"que": "guia_r_en_origen",
                        "detalle": f"R{reproceso_id} salió de esta compra, que vino armada"})

    cursor.execute(
        "SELECT id FROM vacios_deposito_devoluciones WHERE compra_id = %s ORDER BY id",
        (compra_id,),
    )
    for (devolucion_id,) in cursor.fetchall():
        cuelgan.append({"que": "vale_de_vacios",
                        "detalle": f"el vale de vacíos {devolucion_id} cuelga de esta compra"})

    cursor.execute(
        "SELECT id FROM movimientos_stock WHERE compra_devolucion_id = %s ORDER BY id",
        (compra_id,),
    )
    for (movimiento_id,) in cursor.fetchall():
        cuelgan.append({"que": "devolucion_al_proveedor",
                        "detalle": f"la devolución al proveedor {movimiento_id} dice que salió de acá"})

    return cuelgan


def lo_que_cuelga_de_la_compra(compra_id: int) -> list[dict]:
    """`_lo_que_cuelga` con conexión propia, para la PANTALLA.

    Dos funciones y UNA regla: la de adentro la usa `eliminar_compra` dentro
    de su transacción, y ésta la pantalla, que no tiene ninguna abierta. Si la
    pantalla escribiera su propia consulta, un día ofrece un botón que el POST
    después rechaza.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return _lo_que_cuelga(cursor, compra_id)
    finally:
        conexion.close()


# EL DELETE SE ARCHIVA A SI MISMO, en una sola sentencia. Con un SELECT
# aparte habria una carrera entre leer la fila y borrarla, y con el archivo
# en otro execute habria un camino donde la compra se va y el registro no
# queda. Adentro de un CTE las dos cosas son la misma sentencia o no son.
#
# `to_jsonb(compras.*)` y no una lista de columnas: asi no hay nada que
# actualizar el dia que compras gane una columna, que es como se pierde un
# campo sin que nada falle (corolario 3).
_SQL_BORRAR_Y_ARCHIVAR = """
    WITH borrada AS (
        DELETE FROM compras WHERE id = %s AND ({condicion})
        RETURNING guia_id, to_jsonb(compras.*) AS fila
    ), archivo AS (
        INSERT INTO compras_eliminadas (compra_id, origen, fila)
        SELECT (fila->>'id')::bigint, %s, fila FROM borrada
    )
    SELECT guia_id FROM borrada
"""


def eliminar_compra(compra_id: int, forzar: bool = False, *, origen: str) -> list[str]:
    """Borra una compra (borrado real), salvo que ya haya pasado por Depósito o por un retiro de verdad.

    `forzar` SALTEA EL BLOQUEO POR ESTADO y nada más. Es la puerta de
    Gerencia: una compra recepcionada por error hoy solo se arregla con SQL a
    mano, y que la única salida sea ésa es el agujero de siempre — hoy es el
    dueño, mañana es un operario que no puede.

    LO QUE NO SALTEA, Y NO SE PUEDE SALTEAR: lo que le cuelga. Si alguna guía
    R se costeó contra este lote, o salió de esta compra, o hay un vale de
    vacíos o una devolución que la nombra, el borrado se rechaza NOMBRANDO
    cada una. No es una política que Gerencia pueda pisar: son filas que
    apuntan acá, y Postgres las defiende igual — la diferencia es que así el
    error dice qué lo retiene en vez de un ForeignKeyViolation crudo.

    La política vive en el LLAMADOR (quién puede forzar) y la guarda de
    integridad acá, que es donde se escribe.

    Quién decide es el SQL, no esta función: el DELETE lleva pegada la
    condición _SQL_COMPRA_BORRABLE —la misma que usa el Cancelar del día,
    escrita una sola vez— y si no borra ninguna fila, recién ahí se lee la
    compra para armar el mensaje (_motivo_por_el_que_no_se_puede_eliminar).
    Se rechaza con un ValueError y el mensaje es el que se le muestra al
    usuario tal cual. Por ahora esto no tiene excepción: cuando exista el
    sistema de permisos, un gerente podrá forzarlo con su acceso, pero eso
    no se resuelve acá.

    Un retiro AUTOMÁTICO (Carro/Cooperativa) no bloquea mientras la compra
    siga 'pendiente': ese "retirado" lo escribió crear_compra por default,
    nadie lo verificó (ver _SQL_COMPRA_BORRABLE). Hasta el 04/09/2026 sí
    bloqueaba, y una compra de Cooperativa nacía imposible de borrar.

    Una RECHAZADA hoy queda bloqueada, pero de rebote: no hay ninguna
    guarda por estado = 'rechazado' — lo que la frena es que rechazarla
    marca el retiro (_auto_retirar_si_corresponde). Si algún día se decide
    bloquearla a propósito, el motivo es que Depósito ya se expidió (igual
    que "No ingresó"), no el retiro. Eso es una política a decidir, no un
    bug; mientras tanto el caso real —un rechazo apretado por error— se
    resuelve con el Deshacer del mismo día, que la devuelve a 'pendiente'.

    Las fotos de COMANDA cuelgan de la GUÍA (fotos_guia), no del renglón:
    borrar una compra no las toca mientras la guía siga teniendo renglones.
    Si esta era la ÚLTIMA compra de su guía, las fotos de la guía se dan
    de baja también, y se devuelven las rutas a borrar del Storage — SOLO
    las que ninguna otra guía usa (el Listado consolidado comparte un
    archivo entre varias guías). Todo dentro de la misma transacción,
    para no tener carrera entre el DELETE y los conteos.

    La foto de BALANZA (fotos_recepcion) es al revés en las dos cosas:
    cuelga de ESTA compra y su archivo no se comparte con nadie, así que
    se va siempre y sin contar usos. Se devuelve junto con las otras: para
    quien llama son todas "rutas a borrar del Storage".
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # LA FOTO DE BALANZA VA PRIMERO, y no es un detalle de orden:
            # fotos_recepcion.compra_id es una FK SIN "on delete cascade"
            # —a propósito, para que el archivo no quede huérfano en el
            # bucket—, así que el DELETE de compras FALLA mientras la foto
            # esté. Si después resulta que la compra no se puede borrar,
            # esto se deshace solo: se sale por el ValueError sin commit.
            cursor.execute(
                "DELETE FROM fotos_recepcion WHERE compra_id = %s RETURNING foto_ruta",
                (compra_id,),
            )
            rutas_de_balanza = [f[0] for f in cursor.fetchall()]

            if forzar:
                # LO QUE CUELGA SE MIRA IGUAL, y ANTES del DELETE: el
                # ForeignKeyViolation llega sin decir cuál de las cuatro fue.
                cuelgan = _lo_que_cuelga(cursor, compra_id)
                if cuelgan:
                    raise ValueError(
                        "No se puede borrar esta compra todavía: "
                        + "; ".join(c["detalle"] for c in cuelgan)
                        + ". Anulá o corregí eso primero."
                    )
                cursor.execute(
                    _SQL_BORRAR_Y_ARCHIVAR.format(condicion="TRUE"), (compra_id, origen)
                )
            else:
                cursor.execute(
                    _SQL_BORRAR_Y_ARCHIVAR.format(condicion=_SQL_COMPRA_BORRABLE),
                    (compra_id, origen),
                )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError(_motivo_por_el_que_no_se_puede_eliminar(cursor, compra_id))
            (guia_id,) = fila

            rutas_a_borrar: list[str] = list(rutas_de_balanza)
            if guia_id is not None:
                cursor.execute("SELECT COUNT(*) FROM compras WHERE guia_id = %s", (guia_id,))
                (renglones_restantes,) = cursor.fetchone()
                if renglones_restantes == 0:
                    cursor.execute(
                        "DELETE FROM fotos_guia WHERE guia_id = %s RETURNING foto_ruta", (guia_id,)
                    )
                    rutas_borradas = [f[0] for f in cursor.fetchall()]
                    for ruta in rutas_borradas:
                        cursor.execute("SELECT COUNT(*) FROM fotos_guia WHERE foto_ruta = %s", (ruta,))
                        (usos,) = cursor.fetchone()
                        if usos == 0:
                            rutas_a_borrar.append(ruta)
        conexion.commit()
        return rutas_a_borrar
    finally:
        conexion.close()


def obtener_uso_storage_bucket(bucket_id: str) -> dict:
    """Cuenta archivos y suma bytes de un bucket de Supabase Storage, por SQL directo.

    Storage guarda los metadatos de cada archivo (incluido el tamaño) en
    storage.objects, dentro de esta misma base — no hace falta pasar por
    la API de Storage ni por SUPABASE_SERVICE_KEY para esto, alcanza con
    la conexión de DATABASE_URL que ya se usa en todos lados. Devuelve
    {"cantidad": int, "bytes_totales": int}.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*), COALESCE(SUM((metadata->>'size')::bigint), 0) "
                "FROM storage.objects WHERE bucket_id = %s",
                (bucket_id,),
            )
            cantidad, bytes_totales = cursor.fetchone()
        return {"cantidad": cantidad, "bytes_totales": bytes_totales}
    finally:
        conexion.close()


def listar_fotos_para_limpiar(fecha_corte) -> list[str]:
    """Devuelve los foto_ruta candidatos a borrar del Storage: comandas de antes de fecha_corte.

    Una misma foto puede estar compartida por varios renglones/compras. Un
    foto_ruta solo es candidato si NINGUNA compra que lo usa tiene
    fecha_operacion dentro del período a conservar (>= fecha_corte) — así
    nunca se ofrece borrar una foto que todavía necesita un renglón más
    nuevo. Hasta el 19/09 todos los renglones de una misma foto compartían
    la misma fecha_operacion —se cargan juntos y esa fecha no se podía editar
    después— y este chequeo era "por las dudas". Desde que existe
    `mover_compra_de_fecha` (Gerencia) DEJÓ DE SERLO: mover una compra de día
    la manda a la guía de ese día, así que dos renglones de la misma foto
    pueden quedar en fechas distintas. El chequeo pasó de precaución a
    necesario, y por eso está.

    Las fotos de comanda cuelgan de las guías (fotos_guia): un archivo es
    candidato si TODAS las guías que lo usan son de antes de fecha_corte —
    MAX(fecha de guía) por ruta, una sola pasada.

    Los SEIS tipos del bucket entran acá, con el MISMO corte: una sola
    perilla de retención. Que sea la misma es una decisión, no una
    herencia — si alguno tiene que durar distinto, la razón va escrita acá.

    - comandas (fotos_guia), por la fecha de la guía.
    - balanza (fotos_recepcion), por la fecha de su compra.
    - capturas del mail (fotos_pedido), por la fecha del pedido.
    - archivos de precios (precios_venta_historial), por cuando se subieron.
    - fotos de merma (fotos_merma), por la fecha del movimiento.
    - vales de vacíos del depósito (vacios_deposito_devoluciones).

    (Este párrafo decía CUATRO y ya listaba cuatro cuando la función tocaba
    seis: la merma entró sin que nadie lo actualizara. Es el comentario que
    envejece en el mismo commit que lo vuelve falso — corregido el 18/09, al
    entrar el sexto.)

    Los dos últimos NO estaban, y sus archivos no se borraban nunca: ni
    siquiera aparecían como candidatos. Entran ahora porque el bucket pasó
    a tener prefijo por tipo SOLO para lo nuevo (ver core/storage.py), y
    eso converge únicamente si lo viejo se va venciendo — con dos tipos
    inmortales, la mitad plana no se iba nunca.

    Van con olvidar_foto_borrada, que limpia las CUATRO tablas: separarlas
    deja el archivo borrado del bucket y la fila viva, que es "Ver foto"
    roto sin ningún síntoma.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.foto_ruta FROM fotos_guia f
                JOIN guias_compra g ON g.id = f.guia_id
                GROUP BY f.foto_ruta
                HAVING MAX(g.fecha_operacion) < %s
                UNION
                -- Sin MAX ni GROUP BY, y a diferencia del lado de arriba:
                -- una foto de balanza NO se comparte entre compras. Lo
                -- garantiza _armar_ruta_unica (core/storage.py), que le
                -- pone timestamp en ms + 8 random a cada subida, así que
                -- dos filas nunca traen la misma ruta. Si eso cambiara,
                -- este es uno de los lugares que cambia.
                SELECT f.foto_ruta FROM fotos_recepcion f
                JOIN compras c ON c.id = f.compra_id
                WHERE c.fecha_operacion < %s
                UNION
                SELECT f.foto_ruta FROM fotos_pedido f
                JOIN pedidos p ON p.id = f.pedido_id
                GROUP BY f.foto_ruta
                HAVING MAX(p.fecha_operacion) < %s
                UNION
                -- Acá la ruta es una columna, no una tabla de fotos: un
                -- mismo archivo puede respaldar varios precios del mismo
                -- día, así que va con MAX igual que las comandas.
                SELECT h.foto_ruta FROM precios_venta_historial h
                WHERE h.foto_ruta IS NOT NULL
                GROUP BY h.foto_ruta
                HAVING MAX(h.creado_en) < ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                UNION
                -- LA FOTO DE LA MERMA, y son DOS dueños posibles: la merma
                -- de stock normal cuelga de movimientos_stock y la del pool
                -- de segunda de remitos_segunda. Las dos por su
                -- `fecha_operacion`, que es la fecha declarada del hecho.
                --
                -- La ANULADA también entra: la foto es el registro de lo
                -- que se afirmó y no se borra al anular la merma, pero a
                -- los 3 años se va como todo lo demás.
                SELECT f.foto_ruta FROM fotos_merma f
                JOIN movimientos_stock m ON m.id = f.movimiento_id
                WHERE m.fecha_operacion < %s
                UNION
                SELECT f.foto_ruta FROM fotos_merma f
                JOIN remitos_segunda r ON r.id = f.salida_segunda_id
                WHERE r.fecha_operacion < %s
                UNION
                -- EL VALE DE VACÍOS DEL DEPÓSITO. La ruta es una columna y no
                -- una tabla de fotos, igual que en precios, así que va con
                -- GROUP BY + MAX: nada impide que dos vales compartan archivo.
                --
                -- La ANULADA también entra: la foto es el registro de lo que
                -- se afirmó y no se borra al anular, pero a los 3 años se va
                -- como todo lo demás.
                SELECT d.foto_ruta FROM vacios_deposito_devoluciones d
                WHERE d.foto_ruta IS NOT NULL
                GROUP BY d.foto_ruta
                HAVING MAX(d.creado_en) < ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                """,
                (fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte, fecha_corte,
                 fecha_corte),
            )
            filas = cursor.fetchall()
        return [fila[0] for fila in filas]
    finally:
        conexion.close()


def olvidar_foto_borrada(foto_ruta: str) -> None:
    """Borra los registros de un archivo ya eliminado del bucket: fotos_guia, fotos_recepcion, fotos_merma y precios_venta_historial.

    Se llama DESPUÉS de sacar el archivo del Storage (limpieza de fotos
    viejas), así que si acá no se borra ninguna fila queda una apuntando a
    un archivo que ya no existe: "Ver foto" roto para siempre y sin ningún
    síntoma. Por eso, si no tocó nada, LEVANTA — no se puede distinguir
    "ya estaba limpio" de "miré la tabla equivocada", y la segunda es la
    que hay que ver. Quien llama loguea y no cuenta esa foto como
    borrada, así que la pantalla muestra el desfasaje.

    Antes se llamaba limpiar_foto_ruta_de_compras y el nombre mentía dos
    veces: nunca tocó compras (compras.foto_ruta murió en
    db/drop_foto_ruta_compras.sql) y ahora tampoco es una sola tabla.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM fotos_guia WHERE foto_ruta = %s", (foto_ruta,))
            filas_tocadas = cursor.rowcount
            cursor.execute("DELETE FROM fotos_recepcion WHERE foto_ruta = %s", (foto_ruta,))
            filas_tocadas += cursor.rowcount
            cursor.execute("DELETE FROM fotos_pedido WHERE foto_ruta = %s", (foto_ruta,))
            filas_tocadas += cursor.rowcount
            cursor.execute("DELETE FROM fotos_merma WHERE foto_ruta = %s", (foto_ruta,))
            filas_tocadas += cursor.rowcount
            # Acá NO se borra la fila: el precio es el dato y la foto era
            # solo de dónde salió. Se le saca la ruta, que es lo que quedó
            # apuntando a un archivo que ya no existe.
            cursor.execute(
                "UPDATE precios_venta_historial SET foto_ruta = NULL WHERE foto_ruta = %s", (foto_ruta,)
            )
            filas_tocadas += cursor.rowcount
            # Tampoco se borra la fila del vale, y por lo mismo: la devolución
            # es el dato —cuántos cajones salieron y contra qué compra— y la
            # foto era de dónde salió. Borrarla se llevaría el movimiento de
            # stock puesto.
            cursor.execute(
                "UPDATE vacios_deposito_devoluciones SET foto_ruta = NULL WHERE foto_ruta = %s",
                (foto_ruta,),
            )
            filas_tocadas += cursor.rowcount
            if filas_tocadas == 0:
                raise ValueError(
                    f"El archivo {foto_ruta} ya se borró del Storage y no tenía fila en ninguna "
                    "de las tablas que guardan rutas (fotos_guia, fotos_recepcion, fotos_pedido, "
                    "fotos_merma, precios_venta_historial, vacios_deposito_devoluciones): o alguien "
                    "la borró en el medio, o esta "
                    "función está mirando tablas que no son"
                )
        conexion.commit()
    finally:
        conexion.close()


def listar_fotos_de_guia(guia_id: int) -> list[dict]:
    """Las fotos/archivos de una guía, más viejas primero (el orden en que se fueron sumando)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, foto_ruta, creado_en FROM fotos_guia WHERE guia_id = %s ORDER BY creado_en, id",
                (guia_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def agregar_foto_guia_del_dia(fecha_operacion, proveedor_id: int, foto_ruta: str) -> bool:
    """Cuelga una foto a la guía de (fecha, proveedor) SI existe. Devuelve si la encontró.

    Para la carga manual: adjuntar la comanda al cerrar, sin renglón nuevo
    — la guía ya la crearon los renglones cargados antes. Sin guía (nada
    cargado ese día) no hay dónde colgarla: False, y quien llama avisa.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM guias_compra WHERE fecha_operacion = %s AND proveedor_id = %s",
                (fecha_operacion, proveedor_id),
            )
            fila = cursor.fetchone()
            if fila is None:
                return False
            cursor.execute(
                "INSERT INTO fotos_guia (guia_id, foto_ruta) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (fila[0], foto_ruta),
            )
        conexion.commit()
        return True
    finally:
        conexion.close()


def agregar_foto_guia(guia_id: int, foto_ruta: str) -> None:
    """Suma una foto/archivo a la guía. Nunca reemplaza: si la ruta ya estaba en esa guía, no hace nada."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fotos_guia (guia_id, foto_ruta) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (guia_id, foto_ruta),
            )
        conexion.commit()
    finally:
        conexion.close()


def agregar_foto_recepcion(compra_id: int, foto_ruta: str) -> None:
    """Cuelga una foto de balanza a ESTA compra. Nunca reemplaza: si la ruta ya estaba, no hace nada.

    Varias filas por compra a propósito: si la primera salió movida, el
    operario saca otra y quedan las dos. "Falta la foto" es que no haya
    NINGUNA, no que no haya exactamente una.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fotos_recepcion (compra_id, foto_ruta) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (compra_id, foto_ruta),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_fotos_de_recepcion(compra_id: int) -> list[dict]:
    """Las fotos de balanza de una compra, más viejas primero (el orden en que se sacaron)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, foto_ruta, creado_en FROM fotos_recepcion WHERE compra_id = %s ORDER BY creado_en, id",
                (compra_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def borrar_foto_guia(foto_id: int) -> str | None:
    """Saca una foto de su guía. Devuelve la ruta a borrar del Storage SOLO si ninguna otra guía la usa.

    El Listado consolidado comparte un mismo archivo entre varias guías:
    la decisión de si el archivo físico sobra se toma acá, en la misma
    transacción, para no tener carrera entre el DELETE y el conteo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM fotos_guia WHERE id = %s RETURNING foto_ruta", (foto_id,))
            fila = cursor.fetchone()
            if fila is None:
                conexion.commit()
                return None
            (foto_ruta,) = fila
            cursor.execute("SELECT COUNT(*) FROM fotos_guia WHERE foto_ruta = %s", (foto_ruta,))
            (restantes,) = cursor.fetchone()
        conexion.commit()
        return foto_ruta if restantes == 0 else None
    finally:
        conexion.close()


def eliminar_compras_del_dia_por_proveedor(fecha_operacion, proveedor_id: int) -> dict:
    """Borra las compras de un proveedor en una fecha que todavía se pueden borrar (mismo criterio que eliminar_compra).

    Usado por "Cancelar" en /compras/nueva: descarta de una toda la carga
    del día para ese proveedor, incluso los renglones que ya se habían
    guardado al apretar "Agregar artículo" (esa acción guarda cada renglón
    al toque, no queda nada pendiente del lado del cliente).

    Ya no es un DELETE ciego de todo el lote: las compras ya recepcionadas,
    retiradas o marcadas "No ingresó" quedan afuera del borrado — nunca en
    silencio, quien llama tiene que avisar con los números que devuelve
    esta función, no dar por hecho que se borró todo.

    El criterio no está escrito acá: es _SQL_COMPRA_BORRABLE, el mismo que
    usa eliminar_compra, y ahí está la excepción que importa para este
    Cancelar — una compra de Carro o Cooperativa que todavía está
    'pendiente' SÍ se borra, aunque figure retirada, porque ese retiro lo
    puso el alta por default y no lo verificó nadie. Antes contaba como
    "protegida" y el comprador no podía descartar su propia carga.

    Devuelve {"borradas": int, "protegidas": int, "rutas_a_borrar": list[str]}
    — las rutas son fotos de balanza de las compras que SÍ se borraron, y
    quien llama tiene que sacarlas del Storage (igual que con
    eliminar_compra).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM compras WHERE fecha_operacion = %s AND proveedor_id = %s",
                (fecha_operacion, proveedor_id),
            )
            (total,) = cursor.fetchone()

            # La misma razón que en eliminar_compra, y es LA COPIA de esa
            # regla: sin este DELETE previo, el de abajo revienta por la FK
            # apenas una de estas compras tenga foto de balanza. El
            # criterio de borrable NO se reescribe acá — va adentro del
            # subselect, donde las únicas columnas visibles son las de
            # compras y no se puede colar la de otra tabla.
            cursor.execute(
                f"""
                DELETE FROM fotos_recepcion
                WHERE compra_id IN (
                    SELECT id FROM compras
                    WHERE fecha_operacion = %s AND proveedor_id = %s
                      AND ({_SQL_COMPRA_BORRABLE})
                )
                RETURNING foto_ruta
                """,
                (fecha_operacion, proveedor_id),
            )
            rutas_a_borrar = [f[0] for f in cursor.fetchall()]

            # El MISMO archivo que el borrado de a una, y en la misma
            # sentencia: son CUATRO las superficies que borran una compra y
            # si ésta no escribiera, el registro tendría un agujero
            # exactamente donde se borra de a muchas.
            cursor.execute(
                f"""
                WITH borradas AS (
                    DELETE FROM compras
                    WHERE fecha_operacion = %s AND proveedor_id = %s
                      AND ({_SQL_COMPRA_BORRABLE})
                    RETURNING to_jsonb(compras.*) AS fila
                ), archivo AS (
                    INSERT INTO compras_eliminadas (compra_id, origen, fila)
                    SELECT (fila->>'id')::bigint, 'cancelar_dia', fila FROM borradas
                )
                SELECT count(*) FROM borradas
                """,
                (fecha_operacion, proveedor_id),
            )
            (borradas,) = cursor.fetchone()
        conexion.commit()
        return {"borradas": borradas, "protegidas": total - borradas, "rutas_a_borrar": rutas_a_borrar}
    finally:
        conexion.close()


def listar_aprendizaje_articulos_por_proveedor(proveedor_id: int) -> list[dict]:
    """Devuelve lo aprendido (texto_leido -> articulo_id) para un proveedor puntual."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT texto_leido, articulo_id FROM aprendizaje_articulos WHERE proveedor_id = %s",
                (proveedor_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def aprender_articulo(proveedor_id: int, texto_leido: str, articulo_id: int) -> None:
    """Guarda (o corrige) que este proveedor usa este texto para este artículo."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO aprendizaje_articulos (proveedor_id, texto_leido, articulo_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (proveedor_id, texto_leido) DO UPDATE SET articulo_id = EXCLUDED.articulo_id
                """,
                (proveedor_id, texto_leido, articulo_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def obtener_borrador_disponible(cliente_id: int) -> dict | None:
    """El borrador de Disponibles abierto de este cliente, si hay uno (a lo sumo uno, por el índice único)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cliente_id, fecha_desde, fecha_hasta, estado, version, creado_en, actualizado_en
                FROM disponibles
                WHERE cliente_id = %s AND estado = 'borrador'
                """,
                (cliente_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def obtener_ultimo_disponible_cliente(cliente_id: int) -> dict | None:
    """El Disponible más reciente de este cliente (cualquier estado), para precargar uno nuevo cuando
    no hay borrador abierto. None si el cliente nunca tuvo uno."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cliente_id, fecha_desde, fecha_hasta, estado, version, creado_en, actualizado_en
                FROM disponibles
                WHERE cliente_id = %s
                ORDER BY creado_en DESC
                LIMIT 1
                """,
                (cliente_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def listar_detalle_disponible(disponible_id: int) -> list[dict]:
    """Renglones de un Disponible, en el orden en que van en la planilla."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, articulo_id, codigo, nombre, cantidad, orden
                FROM disponibles_detalle
                WHERE disponible_id = %s
                ORDER BY orden
                """,
                (disponible_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def guardar_disponible(
    disponible_id: int | None, cliente_id: int, fecha_desde, fecha_hasta, renglones: list[dict]
) -> int:
    """Crea (si disponible_id es None) o actualiza in place un borrador de Disponibles, reemplazando
    todo su detalle. Nunca toca un Disponible 'generado' — quien llama solo pasa acá el id de un
    borrador (ver obtener_borrador_disponible) o None para crear uno nuevo.

    renglones: [{"articulo_id": int | None, "codigo": str | None, "nombre": str, "cantidad": float}, ...],
    ya en el orden final (el orden en pantalla al guardar) — orden se asigna acá mismo, 1 a N.

    Devuelve el id del Disponible (el mismo que se pasó, o el recién creado).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if disponible_id is None:
                cursor.execute(
                    """
                    INSERT INTO disponibles (cliente_id, fecha_desde, fecha_hasta, estado)
                    VALUES (%s, %s, %s, 'borrador')
                    RETURNING id
                    """,
                    (cliente_id, fecha_desde, fecha_hasta),
                )
                disponible_id = cursor.fetchone()[0]
            else:
                cursor.execute(
                    """
                    UPDATE disponibles
                    SET fecha_desde = %s, fecha_hasta = %s, actualizado_en = now()
                    WHERE id = %s AND estado = 'borrador'
                    """,
                    (fecha_desde, fecha_hasta, disponible_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("Este Disponible ya fue generado, no se puede seguir editando.")

            cursor.execute("DELETE FROM disponibles_detalle WHERE disponible_id = %s", (disponible_id,))
            for orden, renglon in enumerate(renglones, start=1):
                cursor.execute(
                    """
                    INSERT INTO disponibles_detalle (disponible_id, articulo_id, codigo, nombre, cantidad, orden)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (disponible_id, renglon["articulo_id"], renglon["codigo"], renglon["nombre"], renglon["cantidad"], orden),
                )
        conexion.commit()
        return disponible_id
    finally:
        conexion.close()


def cerrar_disponible_generado(disponible_id: int, cliente_id: int, fecha_desde) -> int:
    """Pasa un Disponible a 'generado' (queda cerrado, como historial) y devuelve la versión que le tocó.

    version = cuántos 'generado' ya existen para este mismo cliente_id + fecha_desde, + 1 — así el
    nombre del archivo sale numerado (_v2, _v3, ...) si se genera más de uno el mismo día sin que se
    pisen entre sí. Todo en una sola transacción para que el conteo y el cierre sean atómicos.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM disponibles WHERE cliente_id = %s AND fecha_desde = %s AND estado = 'generado'",
                (cliente_id, fecha_desde),
            )
            version = cursor.fetchone()[0] + 1

            cursor.execute(
                """
                UPDATE disponibles
                SET estado = 'generado', version = %s, actualizado_en = now()
                WHERE id = %s AND estado = 'borrador'
                """,
                (version, disponible_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Este Disponible ya fue generado antes.")
        conexion.commit()
        return version
    finally:
        conexion.close()


# ----------------------------------------------------------------------------
# Vacíos (Envases Puesto): cajones físicos de proveedores que entran y salen
# del puesto del Mercado. Nada que ver con la tabla envases (esa es el costo
# del envase facturado al cliente de distribución).
# ----------------------------------------------------------------------------


def listar_tipos_envase_puesto() -> list[dict]:
    """Tipos de cajón EN CIRCULACIÓN con su proveedor, para las pantallas de Vacíos y el ABM de tipos.

    En circulación = el tipo activo Y su proveedor activo. Dar de baja al
    proveedor NO da de baja sus tipos (son dos tablas), así que mirar solo
    t.activo dejaba a un proveedor muerto en las listas del empleado: seguía
    apareciendo en Recibir y en Devolver, y se le podían cargar movimientos
    nuevos a alguien que ya no existe.

    El orden dentro de cada proveedor es por id (orden de carga): el
    PRIMERO cargado es el que viene preseleccionado en Recibir.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, t.proveedor_id, t.nombre,
                       p.nombre AS proveedor_nombre
                FROM tipos_envase_puesto t
                JOIN proveedores_puesto p ON p.id = t.proveedor_id
                WHERE t.activo AND p.activo
                ORDER BY p.nombre, t.id
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def crear_tipo_envase_puesto(proveedor_id: int, nombre: str) -> int:
    """Alta de un tipo de cajón para un proveedor. Si existía dado de baja, lo reactiva (mismo nombre).

    Devuelve el id, sirva para el alta nueva o para la reactivación: el
    alta puede venir con el valor de la seña en el mismo formulario, y sin
    el id no hay a qué colgársela.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tipos_envase_puesto (proveedor_id, nombre)
                VALUES (%s, %s)
                ON CONFLICT (proveedor_id, nombre) DO UPDATE SET activo = true
                RETURNING id
                """,
                (proveedor_id, nombre),
            )
            tipo_id = cursor.fetchone()[0]
        conexion.commit()
        return tipo_id
    finally:
        conexion.close()


def renombrar_tipo_envase_puesto(tipo_id: int, nombre: str) -> None:
    """Corrige el nombre de un tipo de cajón. UPDATE directo, SIN historial.

    Es corrección de tipeo, no cambio de entidad: el id no se toca, así que
    todos los movimientos viejos siguen colgando de la misma fila y no hay
    nada que versionar. Si algún día "renombrar" pasara a significar "ahora
    es otro cajón", eso NO es esto: sería un tipo nuevo.

    Se niega si el tipo ya no está en circulación (dado de baja él o su
    proveedor): esas filas no se muestran en la pantalla, y un formulario
    viejo o un POST a mano no tienen que poder tocarlas.

    Nombre repetido dentro del MISMO proveedor: ValueError con el nombre del
    que ya existe, para mostrar tal cual. Se chequea acá para dar un mensaje
    decente, y el unique (proveedor_id, nombre) de la tabla queda de red.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.proveedor_id, t.activo, p.activo
                FROM tipos_envase_puesto t
                JOIN proveedores_puesto p ON p.id = t.proveedor_id
                WHERE t.id = %s
                """,
                (tipo_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Ese tipo de envase no existe.")
            proveedor_id, tipo_activo, proveedor_activo = fila
            if not (tipo_activo and proveedor_activo):
                raise ValueError("Ese tipo de envase está dado de baja: no se puede renombrar.")

            cursor.execute(
                "SELECT nombre FROM tipos_envase_puesto WHERE proveedor_id = %s AND nombre = %s AND id <> %s",
                (proveedor_id, nombre, tipo_id),
            )
            repetido = cursor.fetchone()
            if repetido:
                raise ValueError(f"Ese proveedor ya tiene un tipo llamado '{repetido[0]}'.")

            cursor.execute("UPDATE tipos_envase_puesto SET nombre = %s WHERE id = %s", (nombre, tipo_id))
        conexion.commit()
    finally:
        conexion.close()


def desactivar_tipo_envase_puesto(tipo_id: int) -> None:
    """Baja lógica de un tipo de cajón: deja de ofrecerse en las pantallas, los movimientos viejos quedan.

    SE NIEGA si el tipo todavía tiene saldo. Antes se podía dar de baja
    cualquier cosa: el tipo salía de los selects pero seguía con cajones
    adentro, y quedaba medio vivo y medio muerto — invisible para cargar,
    presente en Stock y en rojo en el Cotejo para siempre, sin que nadie
    pudiera hacer nada al respecto.

    Con esta regla, "activo = false" pasa a significar algo: saldo cero,
    cuenta cerrada. Es lo que le permite al Cotejo mostrar esos pares como
    CERRADOS sin adivinar.

    El saldo no se cierra solo con un ajuste automático, a propósito: un
    faltante se cierra con un motivo que escribió alguien, nunca tapado
    por el sistema (misma regla que el resto del módulo).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT proveedor_id, nombre FROM tipos_envase_puesto WHERE id = %s", (tipo_id,))
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Ese tipo de envase no existe.")
            proveedor_id, nombre = fila
            saldo = _stock_vacios_actual(cursor, proveedor_id, tipo_id)
            if saldo != 0:
                raise ValueError(
                    f"'{nombre}' todavía tiene {saldo} en stock. Devolvelos o ajustá a cero antes de darlo de baja."
                )
            cursor.execute("UPDATE tipos_envase_puesto SET activo = false WHERE id = %s", (tipo_id,))
        conexion.commit()
    finally:
        conexion.close()


def listar_clientes_puesto() -> list[dict]:
    """Clientes del puesto activos, para el buscador de la pantalla Recibir."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM clientes_puesto WHERE activo ORDER BY nombre")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_o_crear_cliente_puesto(nombre: str, nombre_normalizado: str) -> int:
    """Devuelve el id del cliente del puesto con ese nombre, creándolo si no existe.

    La identidad es nombre_normalizado (minúsculas, sin acentos ni
    espacios de más — lo normaliza quien llama con normalizar_texto):
    "Juan", "juan " y "JUAN" son EL MISMO cliente, nunca tres. Si existía
    dado de baja, se reactiva — volvió a aparecer por el puesto.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, activo FROM clientes_puesto WHERE nombre_normalizado = %s",
                (nombre_normalizado,),
            )
            fila = cursor.fetchone()
            if fila is not None:
                cliente_id, activo = fila
                if not activo:
                    cursor.execute("UPDATE clientes_puesto SET activo = true WHERE id = %s", (cliente_id,))
                    conexion.commit()
                return cliente_id

            cursor.execute(
                "INSERT INTO clientes_puesto (nombre, nombre_normalizado) VALUES (%s, %s) RETURNING id",
                (nombre, nombre_normalizado),
            )
            (cliente_id,) = cursor.fetchone()
        conexion.commit()
        return cliente_id
    finally:
        conexion.close()


def _saldos_vacios_del_proveedor(cursor, proveedor_id: int) -> list[dict]:
    """El saldo de CADA tipo de un proveedor (los que no dan cero), con el cursor abierto.

    Lo usa la baja del proveedor para saber si quedó algo abierto: dar de
    baja al proveedor no toca sus tipos, así que el saldo hay que mirarlo
    tipo por tipo, no de a uno.
    """
    cursor.execute(
        """
        SELECT t.id, t.nombre,
               COALESCE(r.total, 0) - COALESCE(d.total, 0) + COALESCE(a.total, 0) AS saldo
        FROM tipos_envase_puesto t
        LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM vacios_recibidos
                   WHERE anulado_el IS NULL GROUP BY tipo_envase_id) r ON r.tipo_envase_id = t.id
        LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM vacios_devueltos
                   WHERE anulado_el IS NULL GROUP BY tipo_envase_id) d ON d.tipo_envase_id = t.id
        LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM ajustes_vacios
                   WHERE anulado_el IS NULL GROUP BY tipo_envase_id) a ON a.tipo_envase_id = t.id
        WHERE t.proveedor_id = %s
          AND COALESCE(r.total, 0) - COALESCE(d.total, 0) + COALESCE(a.total, 0) <> 0
        ORDER BY t.nombre
        """,
        (proveedor_id,),
    )
    return [{"tipo_id": fila[0], "tipo_nombre": fila[1], "saldo": int(fila[2])} for fila in cursor.fetchall()]


def _stock_vacios_actual(cursor, proveedor_id: int, tipo_envase_id: int) -> int:
    """Stock del sistema para un proveedor+tipo: recibidos − devueltos + ajustes, sin los movimientos anulados."""
    cursor.execute(
        """
        SELECT COALESCE((SELECT SUM(cantidad) FROM vacios_recibidos
                         WHERE proveedor_id = %s AND tipo_envase_id = %s AND anulado_el IS NULL), 0)
             - COALESCE((SELECT SUM(cantidad) FROM vacios_devueltos
                         WHERE proveedor_id = %s AND tipo_envase_id = %s AND anulado_el IS NULL), 0)
             + COALESCE((SELECT SUM(cantidad) FROM ajustes_vacios
                         WHERE proveedor_id = %s AND tipo_envase_id = %s AND anulado_el IS NULL), 0)
        """,
        (proveedor_id, tipo_envase_id) * 3,
    )
    (stock,) = cursor.fetchone()
    return int(stock)


def stock_vacios_de_tipo(proveedor_id: int, tipo_envase_id: int) -> int:
    """Stock actual del sistema para UN proveedor+tipo (para precargar el ajuste desde el Cotejo)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return _stock_vacios_actual(cursor, proveedor_id, tipo_envase_id)
    finally:
        conexion.close()


def crear_vacio_recibido(cliente_puesto_id: int, proveedor_id: int, tipo_envase_id: int, cantidad: int) -> None:
    """Entrada: un cliente trae cajones vacíos. La seña queda pendiente de pagar (sena_pagada_el NULL)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vacios_recibidos (cliente_puesto_id, proveedor_id, tipo_envase_id, cantidad)
                VALUES (%s, %s, %s, %s)
                """,
                (cliente_puesto_id, proveedor_id, tipo_envase_id, cantidad),
            )
        conexion.commit()
    finally:
        conexion.close()


def crear_vacio_devuelto(proveedor_id: int, tipo_envase_id: int, cantidad: int) -> int:
    """Salida: el proveedor retira cajones con el camión. Devuelve el stock del sistema ANTES del movimiento.

    Ese stock queda GRABADO en la fila (stock_sistema, misma transacción):
    si la devolución supera lo que el sistema decía, la diferencia es un
    dato registrado para revisar después — no un cartel que se cierra.
    Nunca se bloquea el guardado: el camión se lleva los cajones aunque
    el sistema esté atrasado; el negativo se ve en Stock y en el Cotejo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            stock_sistema = _stock_vacios_actual(cursor, proveedor_id, tipo_envase_id)
            cursor.execute(
                """
                INSERT INTO vacios_devueltos (proveedor_id, tipo_envase_id, cantidad, stock_sistema)
                VALUES (%s, %s, %s, %s)
                """,
                (proveedor_id, tipo_envase_id, cantidad, stock_sistema),
            )
        conexion.commit()
        return stock_sistema
    finally:
        conexion.close()


def listar_vacios_recibidos_por_rango(fecha_desde, fecha_hasta) -> list[dict]:
    """Entradas de un rango de fechas (anuladas incluidas, marcadas): "Recibido hoy" y la pantalla Movimientos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.cantidad, v.creado_en, v.anulado_el,
                       -- Para que la pantalla NO ofrezca el botón de anular
                       -- donde el server lo va a rechazar: ofrecido y
                       -- prohibido es lo peor de los dos mundos.
                       v.sena_pagada_el, v.sena_vale_el, v.sena_vale_caducado_el,
                       c.nombre AS cliente_nombre,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre
                FROM vacios_recibidos v
                JOIN clientes_puesto c ON c.id = v.cliente_puesto_id
                JOIN proveedores_puesto p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id
                WHERE v.creado_en >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND v.creado_en < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                ORDER BY v.creado_en DESC
                """,
                (fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_vacios_recibidos_de_fecha(fecha) -> list[dict]:
    """Entradas de UN día, para la lista "Recibido hoy" de la pantalla Recibir."""
    return listar_vacios_recibidos_por_rango(fecha, fecha)


def listar_vacios_devueltos_por_rango(fecha_desde, fecha_hasta) -> list[dict]:
    """Salidas de un rango de fechas (anuladas incluidas, marcadas): "Devuelto hoy" y la pantalla Movimientos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.cantidad, v.stock_sistema, v.creado_en, v.anulado_el,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre
                FROM vacios_devueltos v
                JOIN proveedores_puesto p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id
                WHERE v.creado_en >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND v.creado_en < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                ORDER BY v.creado_en DESC
                """,
                (fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_vacios_devueltos_de_fecha(fecha) -> list[dict]:
    """Salidas de UN día, para la lista "Devuelto hoy" de la pantalla Devolver."""
    return listar_vacios_devueltos_por_rango(fecha, fecha)


class SenaYaCobrada(Exception):
    """Se quiso anular una recepción de vacíos cuya seña ya se pagó o se cerró con vale.

    `cierre` es 'pagada' o 'vale'. La plata ya salió de la caja: anular la
    recepción devolvería los cajones al aire —salen del stock— y dejaría la
    diferencia a favor de quien la anuló, sin que ninguna pantalla lo muestre.
    """

    def __init__(self, cierre: str):
        self.cierre = cierre
        super().__init__(f"La seña de esta entrada ya se cerró: {cierre}")


def anular_vacio_recibido(movimiento_id: int) -> None:
    """Anula una entrada (baja lógica): el registro queda visible como corrección, el stock lo excluye.

    NO SE PUEDE si la seña ya se pagó o se cerró con vale. La guarda vivía en
    un solo sentido —`cerrar_sena` no deja pagar una anulada, pero esto sí
    dejaba anular una pagada— y el agujero es de plata: el pago ya salió, los
    cajones vuelven a salir del stock, y la fila desaparece de las dos listas
    de Señas (las dos filtran `anulado_el IS NULL`), así que ni siquiera queda
    a la vista como cobrada. Reportado desde la operación el 07/09 con un caso
    real de $26.000.

    `sena_anulada_el` SÍ deja anular: ahí se decidió no pagar, no hay plata
    que perseguir.

    La condición va DENTRO del UPDATE, no en un SELECT previo: entre el
    "¿está pagada?" y el UPDATE puede entrar el pago. Cuando no afecta
    ninguna fila se lee la fila para saber por qué y traducir el error;
    ese SELECT es solo para el mensaje, la decisión ya la tomó el UPDATE.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vacios_recibidos SET anulado_el = now()
                WHERE id = %s AND anulado_el IS NULL
                  AND sena_pagada_el IS NULL AND sena_vale_el IS NULL
                """,
                (movimiento_id,),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    SELECT sena_pagada_el IS NOT NULL, sena_vale_el IS NOT NULL
                    FROM vacios_recibidos WHERE id = %s AND anulado_el IS NULL
                    """,
                    (movimiento_id,),
                )
                fila = cursor.fetchone()
                if fila is not None:
                    pagada, vale = fila
                    # Ya anulada o inexistente NO es error: anular dos veces es
                    # el mismo resultado. Solo se levanta si hay plata.
                    if pagada or vale:
                        raise SenaYaCobrada("pagada" if pagada else "vale")
        conexion.commit()
    finally:
        conexion.close()


def anular_vacio_devuelto(movimiento_id: int) -> None:
    """Anula una salida (baja lógica), mismo criterio que anular_vacio_recibido."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE vacios_devueltos SET anulado_el = now() WHERE id = %s AND anulado_el IS NULL",
                (movimiento_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def stock_vacios(fecha_hasta=None) -> list[dict]:
    """Stock del sistema por proveedor y tipo: recibidos − devueltos + ajustes (sin anulados), calculado siempre.

    Con fecha_hasta, es el stock A ESE DÍA (movimientos con creado_en hasta
    esa fecha inclusive); sin fecha_hasta, el de hoy (todos los movimientos).
    Los anulados se excluyen SIEMPRE, sin importar cuándo se anularon: un
    movimiento anulado no existió nunca, así que también desaparece del
    stock de fechas anteriores a su anulación (a propósito — el stock de un
    día pasado puede cambiar si después se descubre un movimiento mal cargado).

    Muestra los pares EN CIRCULACIÓN (tipo y proveedor activos) más
    cualquiera que todavía tenga saldo, esté dado de baja o no: esconder
    cajones que están en el galpón sería mentir.

    Lo que NO muestra es lo CERRADO: dado de baja (el tipo o el proveedor) y
    con saldo cero. Ahí no queda nada que mirar — el que lo dio de baja ya
    decidió que no lo quiere ver más, y un renglón en cero de algo que no
    existe solo ensucia la pantalla. Mismo criterio de "cerrado" que usa el
    Cotejo, aunque ahí el par cerrado SÍ se muestra (en gris y al final):
    esa pantalla cuenta qué pasó el día del conteo, y esta cuenta qué hay
    hoy. En cero y cerrado, no hay nada que haya.
    """
    filtro_fecha = "" if fecha_hasta is None else "AND creado_en < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')"
    parametros = tuple() if fecha_hasta is None else (fecha_hasta, fecha_hasta, fecha_hasta)
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT p.id AS proveedor_id, p.nombre AS proveedor_nombre,
                       t.id AS tipo_envase_id, t.nombre AS tipo_nombre,
                       COALESCE(r.total, 0) AS recibidos,
                       COALESCE(d.total, 0) AS devueltos,
                       COALESCE(aj.total, 0) AS ajustes
                FROM tipos_envase_puesto t
                JOIN proveedores_puesto p ON p.id = t.proveedor_id
                LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM vacios_recibidos
                           WHERE anulado_el IS NULL {filtro_fecha} GROUP BY tipo_envase_id) r ON r.tipo_envase_id = t.id
                LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM vacios_devueltos
                           WHERE anulado_el IS NULL {filtro_fecha} GROUP BY tipo_envase_id) d ON d.tipo_envase_id = t.id
                LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM ajustes_vacios
                           WHERE anulado_el IS NULL {filtro_fecha} GROUP BY tipo_envase_id) aj ON aj.tipo_envase_id = t.id
                WHERE (t.activo AND p.activo)
                   OR COALESCE(r.total, 0) - COALESCE(d.total, 0) + COALESCE(aj.total, 0) <> 0
                ORDER BY p.nombre, t.id
                """,
                parametros,
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        resultado = [dict(zip(columnas, fila)) for fila in filas]
        for fila in resultado:
            fila["stock"] = int(fila["recibidos"]) - int(fila["devueltos"]) + int(fila["ajustes"])
        return resultado
    finally:
        conexion.close()


def crear_ajuste_vacios(proveedor_id: int, tipo_envase_id: int, cantidad: int, motivo: str) -> int:
    """Ajuste de stock (cajera): cantidad con signo (nunca 0) y motivo obligatorio. Devuelve el stock RESULTANTE.

    Es un movimiento más, NUNCA pisa el stock: fila nueva con la foto del
    sistema del momento (stock_sistema, SIN este ajuste) — igual que
    devoluciones y conteos. Sin ese rastro, cualquier faltante se taparía
    con un ajuste y se acaba el control cruzado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            stock_sistema = _stock_vacios_actual(cursor, proveedor_id, tipo_envase_id)
            cursor.execute(
                """
                INSERT INTO ajustes_vacios (proveedor_id, tipo_envase_id, cantidad, motivo, stock_sistema)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (proveedor_id, tipo_envase_id, cantidad, motivo, stock_sistema),
            )
        conexion.commit()
        return stock_sistema + cantidad
    finally:
        conexion.close()


def listar_ajustes_vacios_por_rango(fecha_desde, fecha_hasta) -> list[dict]:
    """Ajustes de un rango de fechas (anulados incluidos, marcados), para la pantalla Movimientos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.cantidad, a.motivo, a.stock_sistema, a.creado_en, a.anulado_el,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre
                FROM ajustes_vacios a
                JOIN proveedores_puesto p ON p.id = a.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = a.tipo_envase_id
                WHERE a.creado_en >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND a.creado_en < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                ORDER BY a.creado_en DESC
                """,
                (fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def anular_ajuste_vacios(ajuste_id: int) -> None:
    """Anula un ajuste (baja lógica): el registro queda visible como corrección, el stock lo excluye."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE ajustes_vacios SET anulado_el = now() WHERE id = %s AND anulado_el IS NULL",
                (ajuste_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def crear_conteo_vacios(proveedor_id: int, tipo_envase_id: int, cantidad: int) -> None:
    """Conteo físico del empleado. El stock del sistema se graba acá, del lado del server — NUNCA se le devuelve.

    A propósito no retorna nada: la pantalla de Stock Físico no puede
    mostrar el número del sistema (si el empleado lo ve, transcribe en
    vez de contar — se pierde el control cruzado). El Cotejo compara
    después contra esta foto exacta. Si el empleado se equivoca, carga el
    conteo de nuevo: en el Cotejo vale el último por proveedor+tipo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            stock_sistema = _stock_vacios_actual(cursor, proveedor_id, tipo_envase_id)
            cursor.execute(
                """
                INSERT INTO conteos_vacios (proveedor_id, tipo_envase_id, cantidad, stock_sistema)
                VALUES (%s, %s, %s, %s)
                """,
                (proveedor_id, tipo_envase_id, cantidad, stock_sistema),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_conteos_vacios_de_fecha(fecha) -> list[dict]:
    """Conteos de un día para la lista "Contado hoy" del empleado.

    SIN stock_sistema en el SELECT, a propósito: esta lista la ve el
    empleado, y el número del sistema no puede viajar ni escondido en el
    HTML de su pantalla.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.cantidad, c.creado_en,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre
                FROM conteos_vacios c
                JOIN proveedores_puesto p ON p.id = c.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = c.tipo_envase_id
                WHERE c.creado_en >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND c.creado_en < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                ORDER BY c.creado_en DESC
                """,
                (fecha, fecha),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_ultimos_conteos_vacios() -> list[dict]:
    """El ÚLTIMO conteo por proveedor+tipo, con su foto del stock del sistema, para el Cotejo (cajera).

    Trae además tres cosas que el Cotejo necesita para saber qué queda por
    hacer, porque la foto congelada sola no alcanza:

    - ajustes_posteriores: cuánto se ajustó DESPUÉS de este conteo. Es lo
      que absorbe la diferencia que el conteo encontró. Sin esto, una
      tarjeta ya ajustada seguía en rojo para siempre —el ajuste no crea un
      conteo nuevo, así que la comparación quedaba clavada en los mismos dos
      números viejos— y el módulo se dejaba de mirar.
    - stock_actual: el saldo de hoy, para el par dado de baja al que le
      quedó stock.
    - proveedor_activo / tipo_activo: si el par sigue vivo.

    Se mide contra los ajustes posteriores y NO contra el stock de hoy: si
    después del conteo entraron o salieron cajones legítimamente, el stock
    ya no coincide con lo contado, y medir así pondría en rojo algo que está
    bien, pidiendo un ajuste que sería incorrecto.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (c.proveedor_id, c.tipo_envase_id)
                       c.id, c.proveedor_id, c.tipo_envase_id,
                       c.cantidad, c.stock_sistema, c.creado_en,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre,
                       p.activo AS proveedor_activo,
                       t.activo AS tipo_activo,
                       -- Los ajustes hechos DESPUÉS de este conteo: son los
                       -- que absorben la diferencia que el conteo encontró.
                       -- Se mide contra esto y NO contra el stock de hoy: si
                       -- después del conteo entraron cajones legítimamente,
                       -- el stock ya no coincide con lo contado y medir así
                       -- inventaría una alarma pidiendo un ajuste incorrecto.
                       COALESCE((SELECT SUM(a.cantidad) FROM ajustes_vacios a
                                 WHERE a.proveedor_id = c.proveedor_id
                                   AND a.tipo_envase_id = c.tipo_envase_id
                                   AND a.anulado_el IS NULL
                                   AND a.creado_en > c.creado_en), 0) AS ajustes_posteriores,
                       -- El saldo de hoy: lo necesita el par dado de baja al
                       -- que le quedó stock, donde lo pendiente no es ajustar
                       -- a lo contado sino cerrar la cuenta en cero.
                       COALESCE((SELECT SUM(r.cantidad) FROM vacios_recibidos r
                                 WHERE r.proveedor_id = c.proveedor_id
                                   AND r.tipo_envase_id = c.tipo_envase_id
                                   AND r.anulado_el IS NULL), 0)
                     - COALESCE((SELECT SUM(d.cantidad) FROM vacios_devueltos d
                                 WHERE d.proveedor_id = c.proveedor_id
                                   AND d.tipo_envase_id = c.tipo_envase_id
                                   AND d.anulado_el IS NULL), 0)
                     + COALESCE((SELECT SUM(a.cantidad) FROM ajustes_vacios a
                                 WHERE a.proveedor_id = c.proveedor_id
                                   AND a.tipo_envase_id = c.tipo_envase_id
                                   AND a.anulado_el IS NULL), 0) AS stock_actual
                FROM conteos_vacios c
                JOIN proveedores_puesto p ON p.id = c.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = c.tipo_envase_id
                ORDER BY c.proveedor_id, c.tipo_envase_id, c.creado_en DESC
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        resultado = [dict(zip(columnas, fila)) for fila in filas]
        for fila in resultado:
            fila["stock_actual"] = int(fila["stock_actual"])
            fila["ajustes_posteriores"] = int(fila["ajustes_posteriores"])
        resultado.sort(key=lambda fila: (fila["proveedor_nombre"], fila["tipo_nombre"]))
        return resultado
    finally:
        conexion.close()


# El valor de la seña se resuelve SIEMPRE con este fragmento: por tipo de
# envase, la fila de mayor vigente_desde que no pase de la fecha de la
# RECEPCIÓN. Va como LEFT JOIN LATERAL dentro de la consulta que lista las
# señas, no como una consulta por fila: una sola ida a la base.
#
# LEFT, no CROSS: un tipo sin valor cargado tiene que devolver la seña con
# monto NULL, no desaparecer del listado. NULL no es cero — es "sin valor
# cargado", y así lo muestran las pantallas.
#
# EL SEGUNDO CRITERIO DE ORDEN NO ES DECORACIÓN. Desde que la tabla no
# tiene UNIQUE por fecha, una misma fecha puede tener varias filas (así se
# corrige un tipeo del mismo día sin perder el número anterior). Ordenando
# solo por vigente_desde, con dos filas de esa fecha la base devuelve
# cualquiera de las dos — o sea, a veces el monto viejo. creado_en DESC es
# lo que hace ganar a la última cargada. El índice
# senas_valor_historial_vigente_idx está hecho para este ORDER BY.
VALOR_SENA_VIGENTE = """
    LEFT JOIN LATERAL (
        SELECT h.monto, h.vigente_desde
        FROM senas_valor_historial h
        WHERE h.tipo_envase_id = v.tipo_envase_id
          AND h.vigente_desde <= (v.creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
        ORDER BY h.vigente_desde DESC, h.creado_en DESC
        LIMIT 1
    ) valor ON true
"""


def listar_valores_sena() -> list[dict]:
    """Cada tipo de envase activo con el valor de seña que rige HOY, para la pantalla de carga.

    monto en NULL = ese tipo no tiene ningún valor cargado. NO es cero: la
    pantalla lo dice con palabras ("sin valor cargado"), nunca con un $0
    que parece un dato real.

    Trae además ultima_vigencia (el vigente_desde más alto que tiene ese
    tipo, haya empezado a regir o no): es contra ese valor que se compara
    la fecha nueva para saber si hay que avisar por carga retroactiva.

    EL "HOY" ES EL ARGENTINO, y hasta el 14/09 acá decía CURRENT_DATE
    mientras VALOR_SENA_VIGENTE —el otro lector de esta misma tabla, cuatro
    funciones más abajo— ya nombraba la zona. Era la misma regla escrita
    dos veces con dos relojes: el que decidía en esta pantalla no era el
    que decide en las otras.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT t.id AS tipo_envase_id, t.nombre AS tipo_nombre,
                       p.nombre AS proveedor_nombre,
                       vigente.monto, vigente.vigente_desde,
                       (SELECT max(h.vigente_desde) FROM senas_valor_historial h
                        WHERE h.tipo_envase_id = t.id) AS ultima_vigencia
                FROM tipos_envase_puesto t
                JOIN proveedores_puesto p ON p.id = t.proveedor_id
                LEFT JOIN LATERAL (
                    SELECT h.monto, h.vigente_desde
                    FROM senas_valor_historial h
                    WHERE h.tipo_envase_id = t.id AND h.vigente_desde <= {_SQL_HOY_ARGENTINA}
                    ORDER BY h.vigente_desde DESC, h.creado_en DESC
                    LIMIT 1
                ) vigente ON true
                WHERE t.activo AND p.activo
                ORDER BY p.nombre, t.nombre
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_historiales_valores_sena(tipo_envase_ids) -> dict:
    """El historial de valores de VARIOS tipos, en una sola consulta.

    La pantalla de Tipos de Envase lista todos los tipos con su historial
    plegado: pedirlo tipo por tipo es un N+1 que crece con el catálogo.

    Devuelve {tipo_envase_id: [filas]}, con lista vacía para los que no
    tienen ninguna — el que pregunta no tiene que andar con .get().
    """
    if not tipo_envase_ids:
        return {}
    ids = list(tipo_envase_ids)
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT tipo_envase_id, monto, vigente_desde, creado_en,
                       -- La que rige de esa fecha es la última cargada; las
                       -- anteriores de la misma fecha quedan a la vista,
                       -- marcadas. PARTITION por tipo Y fecha: sin el tipo,
                       -- la fecha de un tipo pisaría la de otro.
                       creado_en < max(creado_en) OVER (PARTITION BY tipo_envase_id, vigente_desde)
                           AS reemplazada
                FROM senas_valor_historial
                WHERE tipo_envase_id = ANY(%s)
                ORDER BY tipo_envase_id, vigente_desde DESC, creado_en DESC
                """,
                (ids,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()

    historiales = {tipo_id: [] for tipo_id in ids}
    for fila in filas:
        historiales[fila.pop("tipo_envase_id")].append(fila)
    return historiales


def listar_historial_valores_sena(tipo_envase_id: int) -> list[dict]:
    """Todas las filas de valor de un tipo, de la más nueva a la más vieja. Solo lectura: nada se borra ni se corrige.

    Una misma fecha puede tener varias filas (una corrección del mismo
    día). Trae `reemplazada` en las que ya no rigen: sin eso el historial
    mostraría dos montos para el mismo día sin decir cuál ganó, que es
    peor que no mostrar nada.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT monto, vigente_desde, creado_en,
                       -- La que rige de esa fecha es la última cargada;
                       -- las anteriores de la misma fecha quedan a la
                       -- vista, marcadas.
                       creado_en < max(creado_en) OVER (PARTITION BY vigente_desde) AS reemplazada
                FROM senas_valor_historial
                WHERE tipo_envase_id = %s
                ORDER BY vigente_desde DESC, creado_en DESC
                """,
                (tipo_envase_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def contar_senas_afectadas_por_valor(tipo_envase_id: int, monto, vigente_desde) -> int:
    """Cuántas señas YA RECIBIDAS cambiarían de valor si se cargara este monto desde esta fecha.

    Sirve para AVISAR antes de guardar, nunca para trabar: cargar una fecha
    vieja es legítimo (recién ahora se carga lo que rige desde la semana
    pasada), pero mueve plata que ya se estaba mostrando y el que lo carga
    tiene que enterarse ANTES, no después.

    Cuenta una seña si se dan las tres:
      - se recibió en la fecha nueva o después (antes de esa fecha la fila
        nueva no rige y no la toca);
      - hoy resuelve a una vigencia igual o anterior a la nueva, o a
        ninguna — o sea, la fila nueva le va a ganar;
      - y el monto que le queda es DISTINTO del que tiene hoy. Recargar el
        mismo número no cambia nada y no tiene sentido avisarlo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM vacios_recibidos v
                LEFT JOIN LATERAL (
                    SELECT h.monto, h.vigente_desde
                    FROM senas_valor_historial h
                    WHERE h.tipo_envase_id = v.tipo_envase_id
                      AND h.vigente_desde <= (v.creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                    ORDER BY h.vigente_desde DESC, h.creado_en DESC
                    LIMIT 1
                ) actual ON true
                WHERE v.tipo_envase_id = %s
                  AND v.anulado_el IS NULL
                  AND v.creado_en >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                  AND (actual.vigente_desde IS NULL OR actual.vigente_desde <= %s)
                  AND actual.monto IS DISTINCT FROM %s
                """,
                (tipo_envase_id, vigente_desde, vigente_desde, monto),
            )
            return cursor.fetchone()[0]
    finally:
        conexion.close()


def cargar_valor_sena(tipo_envase_id: int, monto, vigente_desde) -> None:
    """Carga el valor de la seña de un tipo de envase desde una fecha. SIEMPRE agrega una fila; nunca pisa ni borra.

    Append-only de verdad, no de nombre: cargar de nuevo una fecha ya
    cargada NO actualiza la fila existente, agrega otra. Gana la de
    creado_en más alto y la anterior queda visible en el historial,
    marcada como reemplazada.

    Eso es lo que permite corregir un tipeo del MISMO día. Si en vez de
    esto la fecha repetida se rechazara, un 7000 cargado hoy en lugar de
    700 no tendría arreglo: las señas que se reciban hoy quedan ancladas a
    hoy, y una corrección fechada mañana no las alcanza.

    El monto va tal cual: cero es un dato válido ("este envase no lleva
    seña") y es distinto de no tener fila. Lo que la base corta es el
    negativo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT t.activo AND p.activo FROM tipos_envase_puesto t "
                           "JOIN proveedores_puesto p ON p.id = t.proveedor_id WHERE t.id = %s",
                           (tipo_envase_id,))
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Ese tipo de envase no existe.")
            if not fila[0]:
                raise ValueError("Ese tipo de envase está dado de baja: no se le carga valor de seña.")

            cursor.execute(
                """
                INSERT INTO senas_valor_historial (tipo_envase_id, monto, vigente_desde)
                VALUES (%s, %s, %s)
                """,
                (tipo_envase_id, monto, vigente_desde),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_senas_pendientes() -> list[dict]:
    """Entradas vigentes con la seña sin resolver, para la pantalla Pendientes de Pago (cajera). LAS MÁS NUEVAS ARRIBA.

    Pendiente = los TRES cierres en NULL (ni pagada, ni vale, ni anulada)
    y el movimiento vigente (no anulado).

    El orden es el de la caja, no el de una cola: lo que se acaba de
    recibir es lo que alguien va a venir a cobrar ahora, y tiene que
    estar a la vista sin scrollear. Las viejas bajan solas — son las de
    la gente que no vino a cobrar, y ésas no se pierden: quedan abajo
    para siempre y la alerta de Auditoría las cuenta aparte
    (contar_senas_pendientes_viejas).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.cantidad, v.creado_en,
                       c.nombre AS cliente_nombre,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre,
                       valor.monto AS monto_unitario
                FROM vacios_recibidos v
                JOIN clientes_puesto c ON c.id = v.cliente_puesto_id
                JOIN proveedores_puesto p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id"""
                + VALOR_SENA_VIGENTE
                + """
                WHERE v.sena_pagada_el IS NULL AND v.sena_vale_el IS NULL AND v.sena_anulada_el IS NULL
                  AND v.anulado_el IS NULL
                ORDER BY v.creado_en DESC, v.id DESC
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_senas_resueltas(limite: int = 50) -> list[dict]:
    """Últimas señas cerradas — pagadas, con vale o anuladas — para el historial plegado de Pendientes de Pago.

    Cada fila trae cierre ('pagada'/'vale'/'anulada') y cerrada_el (la
    fecha del cierre que corresponda), para que el historial distinga los
    tres tipos de un vistazo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.cantidad, v.creado_en,
                       CASE
                           WHEN v.sena_pagada_el IS NOT NULL THEN 'pagada'
                           -- El caducado va ANTES que el vale: si no, un vale
                           -- dado de baja se mostraría igual que uno vivo, y
                           -- la diferencia es si todavía se le debe la plata.
                           WHEN v.sena_vale_caducado_el IS NOT NULL THEN 'vale_caducado'
                           WHEN v.sena_vale_el IS NOT NULL THEN 'vale'
                           ELSE 'anulada'
                       END AS cierre,
                       v.sena_vale_caducado_el, v.sena_vale_caducado_motivo,
                       -- El caducado va PRIMERO en el coalesce, y por eso el
                       -- historial ordena por el último hecho y no por el
                       -- primero: un vale de marzo dado de baja hoy tiene que
                       -- aparecer arriba, no perdido en marzo. La fecha del
                       -- vale sigue disponible aparte, y la pantalla muestra
                       -- las dos.
                       COALESCE(v.sena_vale_caducado_el, v.sena_pagada_el,
                                v.sena_vale_el, v.sena_anulada_el) AS cerrada_el,
                       v.sena_vale_el,
                       c.nombre AS cliente_nombre,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre,
                       valor.monto AS monto_unitario
                FROM vacios_recibidos v
                JOIN clientes_puesto c ON c.id = v.cliente_puesto_id
                JOIN proveedores_puesto p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id"""
                + VALOR_SENA_VIGENTE
                + """
                WHERE num_nonnulls(v.sena_pagada_el, v.sena_vale_el, v.sena_anulada_el) = 1
                  AND v.anulado_el IS NULL
                ORDER BY COALESCE(v.sena_vale_caducado_el, v.sena_pagada_el,
                                  v.sena_vale_el, v.sena_anulada_el) DESC
                LIMIT %s
                """,
                (limite,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


# Los tres cierres posibles de un pendiente de pago, con la columna de fecha
# que escribe cada uno (patrón fecha-como-estado; el CHECK de la tabla
# garantiza que nunca haya dos a la vez).
CIERRES_SENA = {"pagada": "sena_pagada_el", "vale": "sena_vale_el", "anulada": "sena_anulada_el"}


def cerrar_sena(movimiento_id: int, cierre: str) -> None:
    """Cierra un pendiente de pago: 'pagada' (se le pagó al cliente), 'vale' (se hizo vale) o 'anulada' (no se paga).

    Queda registrado QUÉ pasó (la columna) y CUÁNDO (la fecha). Solo
    sobre entradas vigentes y todavía pendientes: no pisa un cierre
    anterior ni "cierra" un movimiento anulado. 'anulada' cierra LA SEÑA,
    no el movimiento — los cajones siguen en el stock.
    """
    columna = CIERRES_SENA.get(cierre)
    if columna is None:
        raise ValueError(f"Cierre de seña desconocido: {cierre}")

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE vacios_recibidos SET {columna} = now()
                WHERE id = %s
                  AND sena_pagada_el IS NULL AND sena_vale_el IS NULL AND sena_anulada_el IS NULL
                  AND anulado_el IS NULL
                """,
                (movimiento_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


class ValeNoCaducable(Exception):
    """Se quiso dar por no cobrado un vale que no está en condiciones.

    `motivo_tecnico` dice cuál de los tres: 'sin_vale' (esa entrada nunca
    tuvo vale), 'ya_caducado' (alguien lo hizo antes) o 'anulada' (la
    recepción está anulada, así que los cajones no están en el stock y
    "cancelar sin tocar el stock" no significa nada ahí).
    """

    def __init__(self, motivo_tecnico: str):
        self.motivo_tecnico = motivo_tecnico
        super().__init__(f"No se puede dar por no cobrado: {motivo_tecnico}")


def caducar_vale(movimiento_id: int, motivo: str) -> None:
    """El vale no se va a cobrar nunca: se cancela lo que se debe SIN tocar el stock.

    Es el caso del cliente que dejó los cajones y no volvió. Los cajones
    ESTÁN en el galpón, así que anular la recepción —que es lo único que
    había— dejaría el stock mal en menos.

    NO borra `sena_vale_el`: las dos fechas conviven a propósito. El vale
    existió y el papel puede aparecer; taparlo con "anulada" perdería
    justo el dato que administración necesita ese día. Por eso tampoco se
    reusó `sena_anulada_el`: haría `num_nonnulls = 2` y la fila
    desaparecería del historial, que filtra `= 1`.

    El motivo es obligatorio y lo garantiza el CHECK de la base, no solo
    esta función: como no hay login, ese texto es el único rastro de POR
    QUÉ se dio de baja una deuda.
    """
    limpio = (motivo or "").strip()
    if not limpio:
        raise ValueError("El motivo es obligatorio para dar un vale por no cobrado.")

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE vacios_recibidos
                SET sena_vale_caducado_el = now(), sena_vale_caducado_motivo = %s
                WHERE id = %s AND anulado_el IS NULL
                  AND sena_vale_el IS NOT NULL AND sena_vale_caducado_el IS NULL
                """,
                (limpio, movimiento_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    SELECT sena_vale_el IS NULL, sena_vale_caducado_el IS NOT NULL,
                           anulado_el IS NOT NULL
                    FROM vacios_recibidos WHERE id = %s
                    """,
                    (movimiento_id,),
                )
                fila = cursor.fetchone()
                if fila is None:
                    raise ValeNoCaducable("sin_vale")
                sin_vale, ya_caducado, anulada = fila
                raise ValeNoCaducable(
                    "anulada" if anulada else "ya_caducado" if ya_caducado else "sin_vale"
                )
        conexion.commit()
    finally:
        conexion.close()


def desactivar_cliente_puesto(cliente_id: int) -> None:
    """Baja lógica de un cliente del puesto: deja de sugerirse al tipear; sus movimientos quedan.

    Si vuelve a aparecer por el puesto, obtener_o_crear_cliente_puesto lo
    reactiva solo al tipear su nombre.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE clientes_puesto SET activo = false WHERE id = %s", (cliente_id,))
        conexion.commit()
    finally:
        conexion.close()


def listar_proveedores_puesto() -> list[dict]:
    """Proveedores del puesto activos, para los selects cerrados de Vacíos y el ABM de la cajera.

    NO son los proveedores de Compras (tabla proveedores): circuito
    aparte del otro lado del Mercado, tabla propia.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM proveedores_puesto WHERE activo ORDER BY nombre")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_o_crear_proveedor_puesto(nombre: str, nombre_normalizado: str) -> int:
    """Devuelve el id del proveedor del puesto con ese nombre, creándolo si no existe (ABM de la cajera).

    Misma unificación por nombre_normalizado que clientes_puesto: el
    mismo proveedor escrito de tres formas es UNO solo. Si existía dado
    de baja, se reactiva. El empleado del fondo NUNCA llega acá: él solo
    elige de listas cerradas — crear es de la cajera.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, activo FROM proveedores_puesto WHERE nombre_normalizado = %s",
                (nombre_normalizado,),
            )
            fila = cursor.fetchone()
            if fila is not None:
                proveedor_id, activo = fila
                if not activo:
                    cursor.execute("UPDATE proveedores_puesto SET activo = true WHERE id = %s", (proveedor_id,))
                    conexion.commit()
                return proveedor_id

            cursor.execute(
                "INSERT INTO proveedores_puesto (nombre, nombre_normalizado) VALUES (%s, %s) RETURNING id",
                (nombre, nombre_normalizado),
            )
            (proveedor_id,) = cursor.fetchone()
        conexion.commit()
        return proveedor_id
    finally:
        conexion.close()


def renombrar_proveedor_puesto(proveedor_id: int, nombre: str, nombre_normalizado: str) -> None:
    """Corrige el nombre de un proveedor del puesto. UPDATE directo, SIN historial.

    Es corrección de tipeo, no cambio de entidad: el id no se toca y sus
    movimientos siguen colgando de la misma fila.

    Escribe nombre Y nombre_normalizado EN LA MISMA SENTENCIA, y eso no es
    un detalle: el normalizado es la identidad con la que
    obtener_o_crear_proveedor_puesto decide si un alta reusa o crea. Si se
    actualizara solo el nombre, el normalizado quedaría mintiendo y la
    próxima alta escribiendo el nombre nuevo crearía un duplicado en vez de
    reusar este.

    Se niega si el proveedor está dado de baja: la pantalla solo lista los
    activos, y un POST a mano no tiene que poder saltearlo.

    Nombre repetido (por normalizado, o sea ignorando mayúsculas y acentos):
    ValueError con el nombre del que ya existe. El UNIQUE de la tabla queda
    de red.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT activo FROM proveedores_puesto WHERE id = %s", (proveedor_id,))
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Ese proveedor no existe.")
            if not fila[0]:
                raise ValueError("Ese proveedor está dado de baja: no se puede renombrar.")

            cursor.execute(
                "SELECT nombre FROM proveedores_puesto WHERE nombre_normalizado = %s AND id <> %s",
                (nombre_normalizado, proveedor_id),
            )
            repetido = cursor.fetchone()
            if repetido:
                raise ValueError(f"Ya existe un proveedor llamado '{repetido[0]}'.")

            cursor.execute(
                "UPDATE proveedores_puesto SET nombre = %s, nombre_normalizado = %s WHERE id = %s",
                (nombre, nombre_normalizado, proveedor_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def desactivar_proveedor_puesto(proveedor_id: int) -> None:
    """Baja lógica de un proveedor del puesto: sale de los selects; sus movimientos y stock histórico quedan.

    SE NIEGA si le queda saldo en ALGUNO de sus tipos, y el error los
    nombra a todos con su número: dar de baja al proveedor no da de baja
    sus tipos, así que mirar un solo tipo dejaría pasar el resto.

    Misma razón que en desactivar_tipo_envase_puesto: sin esta regla,
    "de baja" no quiere decir nada, y el Cotejo no tiene forma de saber
    qué está realmente cerrado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT nombre FROM proveedores_puesto WHERE id = %s", (proveedor_id,))
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Ese proveedor no existe.")
            (nombre,) = fila
            abiertos = _saldos_vacios_del_proveedor(cursor, proveedor_id)
            if abiertos:
                detalle = ", ".join(f"{a['tipo_nombre']}: {a['saldo']}" for a in abiertos)
                raise ValueError(
                    f"{nombre} todavía tiene stock ({detalle}). Devolvelos o ajustá a cero antes de darlo de baja."
                )
            cursor.execute("UPDATE proveedores_puesto SET activo = false WHERE id = %s", (proveedor_id,))
        conexion.commit()
    finally:
        conexion.close()


# ----------------------------------------------------------------------------
# Pedidos de clientes (el mail diario de Día): demanda pura, sin FK contra
# compras. Nada del mail se pierde: los renglones que no matchean ninguna
# ficha se guardan igual, con su texto crudo y articulo_id NULL.
# ----------------------------------------------------------------------------


def crear_pedido(
    cliente_id: int,
    fecha_operacion,
    origen: str,
    texto_original: str | None,
    sucursales: list[dict],
    renglones: list[dict],
    reemplaza_a_pedido_id: int | None = None,
    mail_message_id: str | None = None,
    recibido_el=None,
) -> int:
    """Guarda un pedido completo (cabecera + sucursales + renglones) en UNA transacción. Devuelve el id.

    sucursales: [{"sucursal", "orden_compra", "total_bultos_declarado"}].
    renglones: [{"sucursal", "articulo_id" (None = sin identificar),
    "ficha_id" (con qué ficha del cliente se vende: la clave de VENTA —
    precio, kilaje y envase salen de ahí), "texto_codigo",
    "texto_descripcion", "cantidad"}].

    Si reemplaza_a_pedido_id viene, el pedido viejo se ANULA en la misma
    transacción (baja lógica, nunca DELETE): el corregido manda, el viejo
    queda de registro. Si algo falla, no queda ni el nuevo a medias ni el
    viejo anulado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if reemplaza_a_pedido_id is not None:
                cursor.execute(
                    "UPDATE pedidos SET anulado_el = now() WHERE id = %s AND anulado_el IS NULL",
                    (reemplaza_a_pedido_id,),
                )
            cursor.execute(
                """
                INSERT INTO pedidos (cliente_id, fecha_operacion, origen, texto_original,
                                     reemplaza_a_pedido_id, mail_message_id, recibido_el)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (cliente_id, fecha_operacion, origen, texto_original, reemplaza_a_pedido_id, mail_message_id, recibido_el),
            )
            (pedido_id,) = cursor.fetchone()

            for sucursal in sucursales:
                cursor.execute(
                    """
                    INSERT INTO pedidos_sucursales (pedido_id, sucursal, orden_compra, total_bultos_declarado)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (pedido_id, sucursal["sucursal"], sucursal.get("orden_compra"), sucursal.get("total_bultos_declarado")),
                )

            for renglon in renglones:
                cursor.execute(
                    """
                    INSERT INTO pedidos_renglones
                        (pedido_id, sucursal, articulo_id, ficha_id, texto_codigo,
                         texto_descripcion, cantidad)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        pedido_id,
                        renglon.get("sucursal"),
                        renglon.get("articulo_id"),
                        renglon.get("ficha_id"),
                        renglon.get("texto_codigo"),
                        renglon.get("texto_descripcion"),
                        renglon.get("cantidad", 0),
                    ),
                )

            if reemplaza_a_pedido_id is not None:
                # LOS RENGLONES AGREGADOS A MANO SOBREVIVEN A LA RECARGA, y
                # esto va ANTES del traslado del armado a propósito: el
                # renglón copiado tiene que existir para que el traslado de
                # abajo le devuelva su tilde.
                #
                # La decisión es del dueño (18/09): "si el súper agregó un
                # artículo por teléfono, eso es real y no está en el mail.
                # Que una recarga lo borre significa que al operario se le
                # desaparece mercadería que ya armó, sin que nada avise". Y
                # el mail corregido no lo va a traer nunca — si lo trajera,
                # ya no sería un renglón agregado a mano.
                #
                # GANA EL DEL MAIL cuando el pedido nuevo YA trae ese
                # (artículo, sucursal). No son dos pedidos: es el mismo
                # dicho dos veces —pediste por teléfono y después llegó por
                # mail— así que conservar los dos contaría la demanda dos
                # veces en la Rentabilidad, que suma por fecha y artículo. Y
                # entre los dos gana la comanda porque es contra ella que se
                # concilia la orden de compra, porque es más nueva, y porque
                # la razón de existir del manual era justamente que el mail
                # no lo traía. El armado no se pierde: el traslado de abajo
                # lo lleva del viejo al del mail si la cantidad coincide.
                #
                # Y la SUCURSAL se copia si falta: la pantalla de armar itera
                # `pedidos_sucursales`, así que un renglón conservado cuya
                # sucursal el mail nuevo ya no trae existiría sin que nadie
                # pueda verlo (corolario 68).
                cursor.execute(
                    """
                    INSERT INTO pedidos_sucursales (pedido_id, sucursal, orden_compra, total_bultos_declarado)
                    SELECT DISTINCT %s, viejo.sucursal, NULL, NULL
                      FROM pedidos_renglones viejo
                     WHERE viejo.pedido_id = %s
                       AND viejo.agregado_a_mano_el IS NOT NULL
                       AND viejo.anulado_el IS NULL
                       AND viejo.sucursal IS NOT NULL
                       AND NOT EXISTS (SELECT 1 FROM pedidos_sucursales s
                                        WHERE s.pedido_id = %s AND s.sucursal = viejo.sucursal)
                    """,
                    (pedido_id, reemplaza_a_pedido_id, pedido_id),
                )
                cursor.execute(
                    """
                    INSERT INTO pedidos_renglones
                        (pedido_id, sucursal, articulo_id, ficha_id, texto_codigo,
                         texto_descripcion, cantidad, agregado_a_mano_el, cantidad_original)
                    SELECT %s, viejo.sucursal, viejo.articulo_id, viejo.ficha_id,
                           viejo.texto_codigo, viejo.texto_descripcion, viejo.cantidad,
                           viejo.agregado_a_mano_el, viejo.cantidad_original
                      FROM pedidos_renglones viejo
                     WHERE viejo.pedido_id = %s
                       AND viejo.agregado_a_mano_el IS NOT NULL
                       AND viejo.anulado_el IS NULL
                       AND NOT EXISTS (
                           SELECT 1 FROM pedidos_renglones nuevo
                            WHERE nuevo.pedido_id = %s
                              AND nuevo.articulo_id IS NOT DISTINCT FROM viejo.articulo_id
                              AND nuevo.sucursal IS NOT DISTINCT FROM viejo.sucursal
                       )
                    """,
                    (pedido_id, reemplaza_a_pedido_id, pedido_id),
                )
                # `agregado_a_mano_el` viaja con su hora ORIGINAL y no con
                # now(): es la misma adición de aquel día, no una nueva.

                # Traslado del armado: el tilde (y la cantidad parcial)
                # viajan SOLO a los renglones IDÉNTICOS al pedido viejo
                # (misma sucursal, mismo artículo, misma cantidad) — lo ya
                # armado sigue armado. Lo que cambió queda sin tildar y la
                # pantalla de armado muestra el diff. Copiar todo mentiría
                # (armó 40 y ahora piden 60); no copiar nada haría rearmar
                # de cero.
                cursor.execute(
                    """
                    UPDATE pedidos_renglones nuevo
                    SET armado_el = viejo.armado_el, cantidad_armada = viejo.cantidad_armada
                    FROM pedidos_renglones viejo
                    WHERE nuevo.pedido_id = %s AND viejo.pedido_id = %s
                      AND viejo.armado_el IS NOT NULL
                      AND nuevo.articulo_id IS NOT NULL AND nuevo.articulo_id = viejo.articulo_id
                      AND nuevo.sucursal IS NOT DISTINCT FROM viejo.sucursal
                      AND nuevo.cantidad = viejo.cantidad
                    """,
                    (pedido_id, reemplaza_a_pedido_id),
                )
        conexion.commit()
        return pedido_id
    finally:
        conexion.close()


class PedidoInexistente(Exception):
    """No hay pedido con ese id."""

    def __init__(self, pedido_id: int):
        self.pedido_id = pedido_id
        super().__init__(f"No existe el pedido {pedido_id}")


class PedidoYaAnulado(Exception):
    """Ya estaba anulado: no se pisa su fecha original."""

    def __init__(self, pedido_id: int, anulado_el):
        self.pedido_id = pedido_id
        self.anulado_el = anulado_el
        super().__init__(f"El pedido {pedido_id} ya estaba anulado")


class PedidoConArmado(Exception):
    """Anular un pedido con renglones ARMADOS borraría salidas de stock que ya pasaron."""

    def __init__(self, armados: int):
        self.armados = armados
        super().__init__(f"El pedido tiene {armados} renglón(es) armados")


def anular_pedido(pedido_id: int) -> None:
    """Baja lógica de un pedido ENTERO. Nunca DELETE: queda de registro.

    Alcanza con `pedidos.anulado_el` y los renglones NO se tocan. Los
    lectores de `pedidos_renglones` que trabajan por RANGO descartan el
    pedido anulado —o por el CTE `vigentes`, que es `from pedidos where
    anulado_el is null`, o por un `p.anulado_el is null` propio—; los que
    no lo filtran piden UN pedido o UN renglón por id y no suman en
    ninguna cuenta. Anular además los renglones sería escribir el mismo
    hecho dos veces, y `anular_renglon_pedido` BORRA el armado, así que
    restaurar el pedido después perdería los tildes.

    TRES GUARDAS, y la del medio es la que importa: con renglones armados
    la mercadería ya salió del galpón, así que anular el pedido borraría
    salidas de stock que ocurrieron. Eso se decide renglón por renglón.

    La existencia se lee con un SELECT SIN AGREGADO. Con `count(*)`,
    `cursor.rowcount` y el `not found` de plpgsql dan siempre una fila:
    la versión SQL de esto anulaba ids inexistentes en silencio y pisaba
    el `anulado_el` original de uno ya anulado. Ver corolario 27.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT anulado_el FROM pedidos WHERE id = %s", (pedido_id,))
            fila = cursor.fetchone()
            if fila is None:
                raise PedidoInexistente(pedido_id)
            if fila[0] is not None:
                raise PedidoYaAnulado(pedido_id, fila[0])

            cursor.execute(
                """
                SELECT COUNT(*) FROM pedidos_renglones
                WHERE pedido_id = %s AND armado_el IS NOT NULL AND anulado_el IS NULL
                """,
                (pedido_id,),
            )
            (armados,) = cursor.fetchone()
            if armados:
                raise PedidoConArmado(int(armados))

            cursor.execute("UPDATE pedidos SET anulado_el = now() WHERE id = %s", (pedido_id,))
        conexion.commit()
    finally:
        conexion.close()


def obtener_pedido_vigente(cliente_id: int, fecha) -> dict | None:
    """El pedido VIVO de un cliente para una fecha (el más nuevo sin anular), o None.

    Un día puede tener varios pedidos por los reemplazos: los anulados no
    cuentan acá (se listan aparte si hiciera falta); el vigente es el que
    el depósito arma.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.cliente_id, p.fecha_operacion, p.origen, p.recibido_el,
                       p.reemplaza_a_pedido_id, p.creado_en, p.armado_cerrado_el,
                       reemplazado.creado_en AS reemplazado_creado_en
                FROM pedidos p
                LEFT JOIN pedidos reemplazado ON reemplazado.id = p.reemplaza_a_pedido_id
                WHERE p.cliente_id = %s AND p.fecha_operacion = %s AND p.anulado_el IS NULL
                ORDER BY p.creado_en DESC
                LIMIT 1
                """,
                (cliente_id, fecha),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def listar_sucursales_pedido(pedido_id: int) -> list[dict]:
    """Las sucursales de un pedido con su orden de compra y el total declarado, en el orden del mail (id)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, sucursal, orden_compra, total_bultos_declarado
                FROM pedidos_sucursales WHERE pedido_id = %s ORDER BY id
                """,
                (pedido_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_renglones_pedido(pedido_id: int) -> list[dict]:
    """Los renglones de un pedido, con el nombre de la FICHA con la que se pidió (NULL si no está identificado).

    nombre_venta es lo que hay que mostrarle al que arma: "Banana Ecuador",
    no "Banana" — con dos fichas del mismo artículo, el nombre del catálogo
    no le dice qué caja usar. Sale de nombre_cliente de la ficha y cae al
    nombre del artículo cuando la ficha no tiene nombre propio (o cuando la
    ficha se borró después). articulo_nombre viaja al lado, intacto, para
    lo que sigue hablando del artículo.

    Ordenados para la pantalla del depósito: los SIN identificar primero
    (hay que resolverlos), después por sucursal y nombre.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.sucursal, r.articulo_id, a.nombre AS articulo_nombre,
                       r.ficha_id, COALESCE(NULLIF(TRIM(fl.nombre_cliente), ''), a.nombre) AS nombre_venta,
                       r.texto_codigo, r.texto_descripcion, r.cantidad, r.armado_el, r.cantidad_armada,
                       r.kilos_enviados, r.anulado_el,
                       -- Las dos marcas de "acá metió mano una persona". Sin
                       -- ellas la pantalla no puede distinguir un renglón que
                       -- vino en la comanda de uno que agregué yo, que es
                       -- exactamente lo que el dueño pidió que se viera.
                       r.agregado_a_mano_el, r.cantidad_original
                FROM pedidos_renglones r
                LEFT JOIN articulos a ON a.id = r.articulo_id
                LEFT JOIN fichas_logistica fl ON fl.id = r.ficha_id
                WHERE r.pedido_id = %s
                ORDER BY (r.articulo_id IS NULL) DESC, r.sucursal,
                         COALESCE(NULLIF(TRIM(fl.nombre_cliente), ''), a.nombre, r.texto_descripcion, r.texto_codigo)
                """,
                (pedido_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def asignar_ficha_a_renglon_pedido(renglon_id: int, ficha_id: int) -> None:
    """Asigna a mano la FICHA de un renglón "sin identificar" (o corrige uno mal asignado).

    El artículo sale de la ficha en el mismo UPDATE, sin viajar por el
    formulario: la ficha es la clave de venta (precio, kilaje, envase y el
    nombre que ve el que arma) y el artículo, el de compra. Asignar solo el
    artículo dejaba el renglón sin saber con cuál de las fichas de ese
    artículo se le vende.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pedidos_renglones r
                   SET ficha_id = fl.id, articulo_id = fl.articulo_id
                  FROM fichas_logistica fl
                 WHERE fl.id = %s AND r.id = %s
                """,
                (ficha_id, renglon_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def contar_renglones_agregados_a_mano(pedido_id: int) -> int:
    """Cuántos renglones VIGENTES de un pedido se agregaron a mano.

    Lo usa el aviso de la recarga: el que pega una comanda nueva tiene que
    saber que el resultado no va a ser solo lo que pegó. Cuenta los
    vigentes porque un renglón anulado no se copia al pedido nuevo — el
    aviso estaría prometiendo conservar algo que no se conserva.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*) FROM pedidos_renglones
                 WHERE pedido_id = %s AND agregado_a_mano_el IS NOT NULL
                   AND anulado_el IS NULL
                """,
                (pedido_id,),
            )
            (cantidad,) = cursor.fetchone()
        return int(cantidad)
    finally:
        conexion.close()


def agregar_renglon_a_pedido(pedido_id: int, ficha_id: int, sucursal: str, cantidad) -> int:
    """Agrega A MANO un renglón a un pedido YA CARGADO. Devuelve el id del renglón.

    El caso: el súper pide por teléfono un artículo que la comanda no traía.
    Hasta el 18/09 la única salida era recargar el pedido entero —el nuevo
    anula al viejo— y eso le cuesta el armado a todo renglón cuya cantidad
    haya cambiado.

    EL ARTÍCULO SALE DE LA FICHA, acá adentro, y no viaja por el formulario.
    Es la misma regla que `confirmar_pedido` y que `asignar_ficha_a_renglon_
    pedido`: la ficha es la clave de VENTA (precio, kilaje, envase, el nombre
    que ve el que arma) y el artículo la de COMPRA. Un `articulo_id` que
    llegara del POST podría no ser el de la ficha elegida.

    CUATRO GUARDAS, y las cuatro van ACÁ y no en la pantalla — un formulario
    armado a mano no ve ningún cartel:

    1. El pedido existe y no está anulado.
    2. **La ficha es de ESE cliente.** Es el límite que pidió el dueño: solo
       artículos que ese cliente tiene ficha para recibir, no el catálogo.
    3. **La sucursal es una de las del pedido.** No es texto libre: la
       pantalla de armar itera `pedidos_sucursales`, así que un renglón con
       una sucursal que no está ahí existiría y no se vería nunca.
    4. **No hay ya un renglón vigente con ese artículo en esa sucursal.** Si
       lo hay —el caso más común, el que vino en la comanda EN CERO— lo que
       corresponde es corregirle la cantidad, no agregar un segundo: dos
       renglones del mismo artículo y sucursal cuentan la demanda dos veces
       en la Rentabilidad, que suma por fecha y artículo.

    La existencia se lee con un SELECT SIN AGREGADO: con `count(*)` la fila
    vuelve con 0 y `fetchone() is None` no se cumple nunca (corolario 27).
    """
    if float(cantidad) <= 0:
        raise ValueError("La cantidad tiene que ser mayor a cero.")
    nombre_sucursal = " ".join(str(sucursal).split())
    if not nombre_sucursal:
        raise ValueError("Falta la sucursal.")

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT cliente_id, anulado_el FROM pedidos WHERE id = %s", (pedido_id,))
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("No existe ese pedido.")
            cliente_id, anulado_el = fila
            if anulado_el is not None:
                raise ValueError("Ese pedido está anulado: no se le pueden agregar renglones.")

            cursor.execute(
                "SELECT articulo_id FROM fichas_logistica WHERE id = %s AND cliente_id = %s",
                (ficha_id, cliente_id),
            )
            fila_ficha = cursor.fetchone()
            if fila_ficha is None:
                raise ValueError("Esa ficha no es de este cliente.")
            (articulo_id,) = fila_ficha

            cursor.execute(
                "SELECT 1 FROM pedidos_sucursales WHERE pedido_id = %s AND sucursal = %s",
                (pedido_id, nombre_sucursal),
            )
            if cursor.fetchone() is None:
                raise ValueError(f"El pedido no tiene la sucursal {nombre_sucursal}.")

            cursor.execute(
                """
                SELECT 1 FROM pedidos_renglones
                 WHERE pedido_id = %s AND articulo_id = %s AND sucursal = %s
                   AND anulado_el IS NULL
                """,
                (pedido_id, articulo_id, nombre_sucursal),
            )
            if cursor.fetchone() is not None:
                raise ValueError(
                    f"Ese artículo ya está en {nombre_sucursal}: corregile la cantidad en vez de agregarlo de nuevo."
                )

            cursor.execute(
                """
                INSERT INTO pedidos_renglones
                    (pedido_id, sucursal, articulo_id, ficha_id, cantidad, agregado_a_mano_el)
                VALUES (%s, %s, %s, %s, %s, now())
                RETURNING id
                """,
                (pedido_id, nombre_sucursal, articulo_id, ficha_id, cantidad),
            )
            (renglon_id,) = cursor.fetchone()
        conexion.commit()
        return renglon_id
    finally:
        conexion.close()


def corregir_cantidad_renglon(renglon_id: int, cantidad) -> bool:
    """Corrige A MANO lo que el súper pidió en un renglón. True si cambió algo.

    `cantidad` es LO PEDIDO, no lo armado: `cantidad_armada` es otra columna
    y otra pregunta ("cuánto salió de verdad"), y ésta no la toca. Un renglón
    ya armado se puede corregir —el súper cambia el pedido después de que
    armaste— y la pantalla muestra el diff, que es justamente para qué está.

    LO QUE SÍ SE CAE ES EL TILDE DE CONTROL. Es la misma regla que ya estaba
    escrita para el desarmado: lo que Administración controló fue este renglón
    contra este pedido, y con el número movido el tilde afirma algo sobre otra
    cosa. Queda armado y sin controlar, que es el estado normal.

    `cantidad_original` SE ESCRIBE UNA SOLA VEZ, con el COALESCE: la segunda
    corrección ya tiene guardado con qué nació el renglón y pisarlo borraría
    el único dato que contesta "la orden de compra dice 5 y el sistema 8, por
    qué".

    Y NO HACE NADA si el número es el mismo: marcar como corregido un renglón
    que nadie cambió lo dejaría señalado para siempre por un click.
    """
    if float(cantidad) <= 0:
        raise ValueError("La cantidad tiene que ser mayor a cero.")

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT cantidad, anulado_el FROM pedidos_renglones WHERE id = %s",
                (renglon_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("No existe ese renglón.")
            cantidad_vieja, anulado_el = fila
            if anulado_el is not None:
                raise ValueError("Ese renglón está anulado: desanulalo antes de corregirle la cantidad.")
            if float(cantidad_vieja) == float(cantidad):
                return False

            cursor.execute(
                """
                UPDATE pedidos_renglones
                   SET cantidad = %s,
                       cantidad_original = COALESCE(cantidad_original, cantidad),
                       -- EL TILDE DE CONTROL SE CAE, y es por la misma razón
                       -- que lo tira `desmarcar_renglon_armado`: lo que
                       -- Administración controló fue ESTE renglón contra
                       -- ESTE pedido. Movido el número, el tilde estaría
                       -- afirmando algo sobre otra cosa. El armado NO se
                       -- toca —`cantidad_armada` es cuánto salió y es otra
                       -- pregunta— así que el renglón queda armado y sin
                       -- controlar, que es el estado normal y el que el
                       -- CHECK `controlado_solo_armado` permite.
                       controlado_el = NULL
                 WHERE id = %s
                """,
                (cantidad, renglon_id),
            )
        conexion.commit()
        return True
    finally:
        conexion.close()


def guardar_alias_en_ficha(ficha_id: int, texto_codigo: str | None, texto_descripcion: str | None) -> None:
    """Guarda el código/nombre con el que el cliente pidió, en LA ficha con la que pidió, para que la próxima matchee sola.

    Va por ficha_id, no por (cliente, artículo): con dos fichas del mismo
    artículo (Banana Bolivia y Banana Ecuador) esa clave devolvía las dos
    y el alias de una terminaba pegado en la otra — justo el dato que las
    distingue.

    SOLO completa los campos vacíos de la ficha — nunca pisa un alias ya
    cargado (si el que está difiere del que llegó, se corrige a mano desde
    Editar Ficha, no desde acá). Deja la foto en la bitácora, como
    cualquier edición de ficha. Sin ficha (renglón sin identificar) no se
    llama: el alias vive en la ficha, primero hay que crearla.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE fichas_logistica
                SET codigo_cliente = COALESCE(codigo_cliente, %s),
                    nombre_cliente = COALESCE(nombre_cliente, %s),
                    actualizado_en = now()
                WHERE id = %s
                  AND (codigo_cliente IS DISTINCT FROM COALESCE(codigo_cliente, %s)
                       OR nombre_cliente IS DISTINCT FROM COALESCE(nombre_cliente, %s))
                RETURNING cliente_id, articulo_id, envase_id, contenido_caja, unidad_venta,
                          envase_variable, nombre_cliente, codigo_cliente
                """,
                (texto_codigo, texto_descripcion, ficha_id, texto_codigo, texto_descripcion),
            )
            fila = cursor.fetchone()
            if fila is not None:
                cliente_id, articulo_id, envase_id, contenido_caja, unidad_venta, envase_variable, nombre_cliente, codigo_cliente = fila
                _registrar_foto_ficha(
                    cursor,
                    "edicion",
                    ficha_id=ficha_id,
                    cliente_id=cliente_id,
                    articulo_id=articulo_id,
                    envase_id=envase_id,
                    contenido_caja=contenido_caja,
                    unidad_venta=unidad_venta,
                    envase_variable=envase_variable,
                    nombre_cliente=nombre_cliente,
                    codigo_cliente=codigo_cliente,
                )
        conexion.commit()
    finally:
        conexion.close()


def contar_pedidos_con_renglones_sin_identificar() -> dict:
    """Auditoría: pedidos vivos con al menos un renglón sin identificar, y el más viejo.

    Renglones que llegaron en el mail y todavía no se sabe qué artículo
    son: el depósito no los puede armar y facturación no los puede cruzar.
    Usa el índice parcial pedidos_renglones_sin_identificar_idx.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT p.id), MIN(p.fecha_operacion)
                FROM pedidos p
                WHERE p.anulado_el IS NULL
                  AND EXISTS (SELECT 1 FROM pedidos_renglones r
                              WHERE r.pedido_id = p.id AND r.articulo_id IS NULL)
                """
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def listar_fotos_pedido(pedido_id: int) -> list[dict]:
    """Las capturas de respaldo de un pedido, en orden de llegada."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, foto_ruta FROM fotos_pedido WHERE pedido_id = %s ORDER BY creado_en, id",
                (pedido_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def agregar_foto_pedido(pedido_id: int, foto_ruta: str) -> None:
    """Suma una captura de respaldo al pedido (nunca reemplaza). Repetida exacta, se ignora."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fotos_pedido (pedido_id, foto_ruta) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (pedido_id, foto_ruta),
            )
        conexion.commit()
    finally:
        conexion.close()


def borrar_foto_pedido(foto_id: int) -> str | None:
    """Borra una captura del pedido. Devuelve la ruta si ningún otro pedido la usa (para borrarla del Storage)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM fotos_pedido WHERE id = %s RETURNING foto_ruta", (foto_id,))
            fila = cursor.fetchone()
            if fila is None:
                return None
            (foto_ruta,) = fila
            cursor.execute("SELECT COUNT(*) FROM fotos_pedido WHERE foto_ruta = %s", (foto_ruta,))
            (usos,) = cursor.fetchone()
        conexion.commit()
        return foto_ruta if usos == 0 else None
    finally:
        conexion.close()


def marcar_renglon_armado(renglon_id: int, cantidad_armada=None, kilos_enviados=None) -> None:
    """Tilda un renglón como armado. El tilde significa "terminé con este renglón", no "está completo".

    cantidad_armada solo si armó MENOS de lo pedido (Día pide 15 y hay
    12): la cantidad real queda grabada y el renglón figura "incompleto".
    Armado completo va con None — no se guarda un número redundante.

    kilos_enviados: los kilos REALES con los que se mandó el renglón (lo
    que se factura). El default sugerido en pantalla sale de la ficha,
    pero acá se guarda lo que el depósito dijo — puede diferir.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE pedidos_renglones SET armado_el = now(), cantidad_armada = %s, kilos_enviados = %s WHERE id = %s",
                (cantidad_armada, kilos_enviados, renglon_id),
            )
            # Vuelve a tildar: la corrección vieja se va. Puede estar
            # cambiando la cantidad, y una corrección que reparte 15 bultos
            # sobre un renglón que ahora manda 8 es una mentira guardada.
            _borrar_lotes_elegidos(cursor, renglon_id)
        conexion.commit()
    finally:
        conexion.close()


def _borrar_lotes_elegidos(cursor, renglon_id: int) -> None:
    """Borra la corrección del renglón. Va con el cursor abierto: nunca se
    borra por su cuenta, siempre adentro de la operación que la invalida."""
    cursor.execute("DELETE FROM pedidos_renglones_lotes_elegidos WHERE renglon_id = %s", (renglon_id,))


def contenido_por_bulto_de_lotes(claves: list[tuple[str, int]]) -> dict[str, dict]:
    """De cuánto es cada bulto de estos lotes, para el que ELIGE de cuál sacar.

    Tres cajones no son tres cajones: uno de 16 kg y uno de 10 no sirven para
    lo mismo, y el que reprocesa necesita el número exacto de lo que va a
    usar. Sin esto la fila dice fecha, proveedor y cuántos quedan — todo menos
    lo único que cambia la decisión.

    SOLO CONTESTA POR LOS LOTES DE COMPRA (`tipo_lote = 'guia'`, cuyo
    `origen_id` es el id de la compra): son los únicos que tienen el contenido
    DECLARADO. Un ajuste o el stock inicial no lo tienen, y no se deduce — un
    campo derivado acierta en la mayoría y miente en un tercio. La fila de
    esos lotes se dibuja sin el dato, que es verdadero: no lo sabemos.

    Lo REAL primero y el estimado de respaldo, que es la misma regla que usa
    la cuenta de stock: lo pesado es lo que hay en el piso, y el estimado
    entra solo donde nadie pesó.

    La unidad sale de `articulos.unidad_compra`, que es exactamente lo que esa
    columna deprecada sigue diciendo: en qué unidad está escrito
    `compras.contenido_por_cajon`. Deducirla de otra cosa la re-etiquetaría.
    """
    ids = [origen_id for tipo, origen_id in claves if tipo == "guia"]
    if not ids:
        return {}

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id,
                       COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon),
                       a.unidad_compra
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.id = ANY(%s)
                """,
                (ids,),
            )
            filas = cursor.fetchall()
    finally:
        conexion.close()

    return {
        f"guia:{compra_id}": {"contenido": float(contenido), "unidad": unidad}
        for compra_id, contenido, unidad in filas
        if contenido is not None and float(contenido) > 0
    }


def desglose_de_renglon_armado(renglon_id: int) -> dict | None:
    """De qué lotes salió este renglón armado, para mostrárselo al que lo armó.

    Devuelve None si el renglón no existe o todavía no está tildado: ANTES DEL
    TILDE no hay nada que mostrar, y no es un detalle de implementación. La
    pantalla de armado no puede enseñar números del sistema mientras el que
    arma todavía no declaró nada —si los ve, arma contra el sistema en vez de
    contra el piso—; después del tilde ya declaró cuánto mandó, y lo que ve es
    de dónde sale.

    Los lotes que ofrece son los que había A LA FECHA DEL ARMADO contando solo
    las salidas ANTERIORES a este renglón: es "cuánto quedaba en ese lote
    cuando armaste", que es lo único que el que armó puede reconocer.

    Límite conocido, anotado y no tapado: una salida SEÑALADA posterior (otra
    corrección, o una merma dirigida) se lleva su lote antes que este renglón
    en el reparto de verdad, y esta propuesta no la ve. Es el mismo agujero
    que el pendiente "los dos FIFO son dos implementaciones del mismo
    emparejamiento": se cierra con la función de emparejamiento única, no
    escribiendo acá una tercera versión del reparto.
    """
    from core.stock import lotes_ofrecidos, propuesta_fifo, reparto_a_la_fecha, salidas_para_reparto

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.articulo_id, COALESCE(r.cantidad_armada, r.cantidad), r.armado_el
                FROM pedidos_renglones r
                WHERE r.id = %s AND r.armado_el IS NOT NULL AND r.anulado_el IS NULL
                """,
                (renglon_id,),
            )
            fila = cursor.fetchone()
            if fila is None or fila[0] is None:
                return None
            articulo_id, armado, _armado_el = fila[0], float(fila[1]), fila[2]

            entradas, salidas = _entradas_y_salidas_stock(cursor, articulo_id)
    finally:
        conexion.close()

    esta = next((s for s in salidas if s.get("renglon_id") == renglon_id), None)
    if esta is None:
        return None

    anteriores = [s for s in salidas if s["orden"] < esta["orden"]]
    reparto = reparto_a_la_fecha(entradas, salidas_para_reparto(anteriores), esta["orden"][0])
    elegidos = esta.get("lotes_elegidos")

    # EL CAJÓN NO SE LISTA. En una ficha con envase un cajón no es una opción
    # peor: es la cosa que la regla prohíbe. Listarlo sin input, o listarlo y
    # avisar al guardar, dejan a la vista algo que no se puede elegir, y eso
    # invita a preguntarse por qué está ahí. Si no queda ninguno, el caso
    # vacío de la pantalla ya dice lo que corresponde —"faltan cajas armadas
    # de esta ficha: cargá la guía R"— y no "no hay lotes".
    #
    # Sale de `lotes_ofrecidos`, la MISMA que usa el reparto y la que
    # rechaza en guardar_lotes_elegidos: la pantalla no puede ofrecer algo
    # que el server después no acepte.
    ofrecidos = lotes_ofrecidos(reparto["lotes"], esta)
    claves_ofrecidas = {(lote["tipo_lote"], lote["origen_id"]) for lote in ofrecidos}

    return {
        "articulo_id": articulo_id,
        "armado": armado,
        "lotes": ofrecidos,
        "editado": bool(elegidos),
        # Viaja a la pantalla para que el cartel del caso vacío diga la
        # verdad: con envase, "no hay lotes" es FALSO —el cajón está ahí— y
        # lo que falta es la guía R. Sale de la MISMA salida que decide la
        # pared, no de una segunda lectura de la ficha.
        "ficha_con_envase": bool(esta.get("ficha_con_envase")),
        # Lo que ya eligió, o la propuesta del más viejo primero si no tocó nada.
        # Una corrección VIEJA puede apuntar a un lote que hoy no se ofrece
        # (se guardó antes de la pared). Se filtra con la misma clave: si no
        # se filtrara, la propuesta pondría bultos en una fila que no existe
        # y el total de la pantalla no cerraría con ninguna suma visible.
        # Lo que queda afuera aparece como "sin lote" en el total, que es lo
        # que de verdad es.
        "propuesta": (
            {f"{e['lote_tipo']}:{e['lote_origen_id']}": float(e["bultos"]) for e in elegidos
             if (e["lote_tipo"], e["lote_origen_id"]) in claves_ofrecidas}
            if elegidos
            else {f"{c['tipo_lote']}:{c['origen_id']}": c["bultos"]
                  # Con `esta` para que proponga lo mismo que va a repartir:
                  # el armado toma caja armada antes que cajón.
                  for c in propuesta_fifo(reparto["lotes"], armado, esta)}
        ),
    }


def compras_que_alimentaron_el_renglon(renglon_id: int) -> list[dict]:
    """De qué COMPRAS salió la mercadería de este renglón, SEGÚN EL FIFO, con cuántos bultos puso cada una.

    Es lo que la pantalla de devolución ofrece para elegir: "25 de la compra
    del 08, 5 de la del 09". La persona elige UNA — el sistema no reparte los
    bultos devueltos entre compras, porque nadie miró qué caja venía de qué
    cajón y cualquier reparto sería inventado.

    De la MÁS GRANDE a la más chica: la que puso más bultos es la que más
    probablemente trajo lo que volvió, y ponerla primera es proponer sin
    afirmar. La lista vacía es información: el renglón salió sin lote, o de
    guías R, y ahí no hay compra que elegir.

    Solo mira los lotes de tipo 'guia', que son los únicos que apuntan a una
    compra (`origen_id` = compras.id). Un lote de reproceso es una caja
    armada acá: su proveedor está un escalón más atrás y no se sigue.

    LO REPARTIDO Y NO LO OFRECIDO: lo que se ofreció es lo que había, y lo
    que interesa es de dónde salió de verdad.

    Y ES UNA FOTO DEL MOMENTO, no un hecho congelado: el FIFO se rejuega en
    cada lectura, así que esto puede cambiar si mañana se corrige otra
    recepción. Por eso lo que se GUARDA es la compra que la persona eligió,
    no este cálculo — una vez elegida, la respuesta no se mueve más.
    """
    desglose = desglose_de_renglon_armado(renglon_id)
    if not desglose:
        return []

    bultos_por_compra: dict[int, float] = {}
    for clave, bultos in (desglose.get("propuestos") or {}).items():
        tipo, _, origen = clave.partition(":")
        if tipo != "guia" or not origen.isdigit():
            continue
        bultos_por_compra[int(origen)] = bultos_por_compra.get(int(origen), 0.0) + float(bultos)

    if not bultos_por_compra:
        return []

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, p.id, p.nombre, p.codigo_puesto,
                       COALESCE(c.cantidad_cajones_real, c.cantidad_cajones)
                FROM compras c JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.id = ANY(%s)
                """,
                (list(bultos_por_compra),),
            )
            filas = cursor.fetchall()
    finally:
        conexion.close()

    compras = [
        {
            "compra_id": f[0],
            "fecha_operacion": f[1],
            "proveedor_id": f[2],
            "proveedor_nombre": f[3],
            "codigo_puesto": f[4],
            "cajones_de_la_compra": float(f[5]) if f[5] is not None else None,
            "bultos": round(bultos_por_compra[f[0]], 2),
        }
        for f in filas
    ]
    compras.sort(key=lambda c: (-c["bultos"], c["compra_id"]))
    return compras


def devoluciones_de_la_compra(compra_id: int) -> list[dict]:
    """Qué se le devolvió al proveedor de ESTA compra, para el reclamo.

    Es el otro extremo de `compra_devolucion_id`: la pantalla de reingreso lo
    escribe y el detalle de la compra lo lee. Sin esto, el vínculo se guarda
    y no se ve, que es la familia del campo que se escribe y nadie lee —
    `proveedor_devolucion_id` estuvo así desde que se creó.

    Solo las devoluciones VIVAS: una anulada no se reclama. Y devuelve las
    filas, no un total, porque el reclamo se hace por fecha y motivo ("el
    martes te devolví 8 por podrido"); el total lo suma la pantalla.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.id, m.fecha_operacion, m.cantidad, m.motivo, c.nombre, a.nombre
                FROM movimientos_stock m
                LEFT JOIN clientes c ON c.id = m.cliente_id
                JOIN articulos a ON a.id = m.articulo_id
                WHERE m.compra_devolucion_id = %s AND m.anulado_el IS NULL
                ORDER BY m.fecha_operacion, m.id
                """,
                (compra_id,),
            )
            filas = cursor.fetchall()
    finally:
        conexion.close()

    return [
        {
            "movimiento_id": f[0],
            "fecha_operacion": f[1],
            "bultos": float(f[2]),
            "motivo": f[3],
            "cliente_nombre": f[4],
            "articulo_nombre": f[5],
        }
        for f in filas
    ]


def guardar_lotes_elegidos(renglon_id: int, lotes: list[dict]) -> None:
    """De qué lote dijo el que arma que sacó este renglón. Reemplaza lo anterior.

    Se guarda SOLO LA EXCEPCIÓN: con `lotes` vacío no queda ninguna fila, y un
    renglón sin filas se reparte por FIFO como siempre. Aceptar la propuesta
    es no guardar nada — el default nunca se escribe, así que no puede quedar
    viejo cuando cambie el stock.

    Borra y reescribe en UNA transacción en vez de actualizar fila por fila:
    la corrección es un documento chico y entero, no un conjunto de renglones
    con vida propia.

    Lo que NO valida acá: que la suma dé lo armado. Acá se AVISA Y NO SE
    TRABA — lo que no esté elegido cae al FIFO, igual que hoy. Lo único que
    rechaza es lo imposible, y lo rechaza la base: más de lo que hay en un
    lote no se puede pedir, pero eso lo mira quien arma la propuesta.

    LO QUE SÍ RECHAZA, y es la excepción a "avisa y no traba": un lote que la
    pared no le ofrece a esta salida. No es un reparto discutible, es uno que
    no pudo pasar — con envase, una caja no sale de un cajón sin una guía R
    en el medio. La guarda va acá y no solo en la pantalla porque la pantalla
    es la forma cómoda de cumplirla, no la que decide: sin esto, un POST a
    mano entra igual y `lotes_senalados` —que corre ANTES de la pared, en la
    pasada de los dirigidos— se lleva el cajón. Es el mismo hallazgo del
    tilde de la fecha del 08/09: la guarda va donde se ESCRIBE.

    El motivo sale de `lote_ofrecido`, que pregunta por `pasadas_de_lotes`.
    Escrito acá como una condición propia se separaría de la pared el día
    que la pared cambie, que es como se abrió este agujero.
    """
    from core.stock import lote_ofrecido

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if lotes:
                cursor.execute(
                    """
                    SELECT articulo_id FROM pedidos_renglones
                    WHERE id = %s AND armado_el IS NOT NULL AND anulado_el IS NULL
                    """,
                    (renglon_id,),
                )
                fila = cursor.fetchone()
                # SIN AGREGADO a propósito: con un count(*) esto nunca sería
                # None y el renglón inexistente pasaría de largo (corolario 27).
                if fila is None:
                    raise ValueError("Ese renglón no está armado: no se puede corregir de dónde salió.")
                _, salidas = _entradas_y_salidas_stock(cursor, fila[0])
                esta = next((s for s in salidas if s.get("renglon_id") == renglon_id), None)
                if esta is None:
                    raise ValueError("No se encontró la salida de ese renglón.")
                for lote in lotes:
                    candidato = {"tipo_lote": lote["lote_tipo"], "origen_id": lote["lote_origen_id"]}
                    if not lote_ofrecido(candidato, esta):
                        raise ValueError(
                            "Esa mercadería sale en caja propia: no puede salir de un cajón. "
                            "Lo que falta es la guía R que arme esas cajas."
                        )
            _borrar_lotes_elegidos(cursor, renglon_id)
            for lote in lotes:
                if float(lote["bultos"]) <= 0:
                    continue
                cursor.execute(
                    """
                    INSERT INTO pedidos_renglones_lotes_elegidos
                        (renglon_id, lote_tipo, lote_origen_id, bultos)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (renglon_id, lote["lote_tipo"], lote["lote_origen_id"], lote["bultos"]),
                )
        conexion.commit()
    finally:
        conexion.close()


def desmarcar_renglon_armado(renglon_id: int) -> bool:
    """Destilda un renglón (toque por error, o apareció el stock): vuelve arriba, sin cantidad parcial.

    Y BORRA LA CORRECCIÓN de lotes, en la misma transacción: el tilde se fue,
    así que ya no hay salida de la que decir de dónde salió. Dejarla sería una
    corrección apuntando a una cantidad que ya no existe, esperando a que
    alguien vuelva a tildar con otro número.

    Y BORRA EL CONTROL DE ADMINISTRACIÓN, por lo mismo y un escalón más
    fuerte: lo que se controló fue ESTE renglón con estos bultos y estos
    kilos, así que un tilde de control sobre un renglón desarmado estaría
    afirmando algo sobre números que ya no existen. No es una cortesía del
    código: sin el `controlado_el = NULL` el CHECK
    pedidos_renglones_controlado_solo_armado RECHAZA este UPDATE.

    Devuelve True si había un control puesto, para que la pantalla pueda
    decir que se tiró abajo — el que desarma tiene que enterarse.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pedidos_renglones
                SET armado_el = NULL, cantidad_armada = NULL, kilos_enviados = NULL,
                    controlado_el = NULL
                WHERE id = %s
                RETURNING (controlado_el IS NOT NULL)
                """,
                (renglon_id,),
            )
            fila = cursor.fetchone()
            estaba_controlado = bool(fila and fila[0])
            _borrar_lotes_elegidos(cursor, renglon_id)
        conexion.commit()
        return estaba_controlado
    finally:
        conexion.close()


def anular_renglon_pedido(renglon_id: int) -> None:
    """La CRUZ del armado: este renglón directamente no se va a armar. Anulado, nunca borrado.

    Si estaba tildado, el tilde y sus números se limpian: anulado y armado
    son estados excluyentes — un renglón anulado no manda nada. Y con ellos
    el control de Administración, que sin el armado no puede quedar: lo
    obliga el CHECK pedidos_renglones_controlado_solo_armado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pedidos_renglones
                SET anulado_el = now(), armado_el = NULL, cantidad_armada = NULL,
                    kilos_enviados = NULL, controlado_el = NULL
                WHERE id = %s
                """,
                (renglon_id,),
            )
            # Un renglón anulado no manda nada: su corrección de lotes tampoco.
            _borrar_lotes_elegidos(cursor, renglon_id)
        conexion.commit()
    finally:
        conexion.close()


def desanular_renglon_pedido(renglon_id: int) -> None:
    """Deshace la cruz: el renglón vuelve a los pendientes de armar."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE pedidos_renglones SET anulado_el = NULL WHERE id = %s", (renglon_id,))
        conexion.commit()
    finally:
        conexion.close()


def cerrar_armado_pedido(pedido_id: int) -> None:
    """El "Terminar pedido": cierre explícito del armado. Operativo, no un candado — se puede reabrir."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE pedidos SET armado_cerrado_el = now() WHERE id = %s", (pedido_id,))
        conexion.commit()
    finally:
        conexion.close()


def reabrir_armado_pedido(pedido_id: int) -> None:
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE pedidos SET armado_cerrado_el = NULL WHERE id = %s", (pedido_id,))
        conexion.commit()
    finally:
        conexion.close()


def buscar_renglones_pedidos(cliente_id: int, fecha_desde, fecha_hasta) -> list[dict]:
    """Los renglones de los pedidos VIGENTES del rango, para Armar Remito (lo que se factura).

    Trae los KILOS ENVIADOS tal cual los grabó el depósito al armar —
    NULL si el renglón no se armó: la pantalla lo dice, jamás se calcula
    el kilaje de la ficha en el listado. Los anulados vienen marcados
    (anulado_el), nunca desaparecen. Una fila por renglón, del pedido
    vigente de cada fecha (los reemplazados no cuentan doble).

    Trae la ORDEN DE COMPRA de la sucursal del renglón, para el encabezado
    del grupo. LEFT JOIN y no JOIN: `pedidos_sucursales` se llena al leer el
    mail, así que un pedido cargado a mano puede no tener fila — y ahí el
    encabezado dice "sin orden de compra", que es un dato y no un error. El
    `unique (pedido_id, sucursal)` de esa tabla es lo que hace que el join
    no pueda duplicar renglones.

    ORDENADO POR SUCURSAL primero: la pantalla agrupa por sucursal adentro
    de cada fecha, y el agrupador arma los grupos en el orden en que vienen
    las filas.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                WITH vigentes AS (
                    SELECT DISTINCT ON (fecha_operacion) id, fecha_operacion
                    FROM pedidos
                    WHERE cliente_id = %s AND anulado_el IS NULL
                      AND fecha_operacion >= %s AND fecha_operacion <= %s
                    ORDER BY fecha_operacion, creado_en DESC
                )
                SELECT v.fecha_operacion, v.id AS pedido_id, r.id, r.sucursal, r.articulo_id,
                       COALESCE(a.nombre, r.texto_descripcion, r.texto_codigo) AS articulo_nombre,
                       r.cantidad, r.cantidad_armada, r.kilos_enviados, r.armado_el, r.anulado_el,
                       r.controlado_el, ps.orden_compra,
                       -- EN QUE UNIDAD estan los `kilos_enviados` de ESTE
                       -- renglon. La columna se llama kilos y guarda la
                       -- magnitud de LA FICHA: kilos, unidades o cubetas.
                       -- Sin esta columna la pantalla suma las tres en un
                       -- solo total y no hay nada que se vea raro.
                       fl.unidad_venta
                FROM vigentes v
                JOIN pedidos_renglones r ON r.pedido_id = v.id
                LEFT JOIN articulos a ON a.id = r.articulo_id
                -- LEFT: un renglon sin ficha asignada tiene que VOLVER, con
                -- la unidad en NULL. Con un JOIN normal desapareceria del
                -- remito y el total cerraria contra menos de lo que se mando.
                LEFT JOIN fichas_logistica fl ON fl.id = r.ficha_id
                LEFT JOIN pedidos_sucursales ps
                       ON ps.pedido_id = v.id AND ps.sucursal = r.sucursal
                ORDER BY v.fecha_operacion DESC, r.sucursal,
                         (r.anulado_el IS NOT NULL),
                         COALESCE(a.nombre, r.texto_descripcion, r.texto_codigo)
                """,
                (cliente_id, fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


class PedidoInexistenteParaControl(Exception):
    """El pedido que se quiso controlar no existe."""


def guardar_control_de_pedido(pedido_id: int, renglones_tildados: list[int]) -> int:
    """Guarda el control de Administración de un pedido: tilda los que vienen y DESTILDA el resto.

    Destildar los que no vienen y no solo tildar los que sí es lo que hace
    que el destildado exista: un checkbox que se apaga no manda nada, así
    que "los que no llegaron" es la única forma de saber cuáles se sacaron.

    SOLO LOS ARMADOS Y NO ANULADOS: la lista puede llegar armada a mano por
    un POST. La guarda va acá, donde se ESCRIBE, y no en la pantalla —
    aunque el CHECK de la base ya rechazaría el caso del sin armar, el del
    anulado no lo cubre y no tiene por qué: anulado y armado ya son
    excluyentes por otro lado.

    LA EXISTENCIA SE PREGUNTA SIN AGREGADO. Un `select count(*)` devuelve
    (0,) para un pedido que no existe, así que `fetchone() is None` no se
    cumple nunca y la guarda no distinguiría "no hay" de "hay cero"
    (corolario 27).

    Devuelve cuántos quedaron tildados, que es lo que la pantalla avisa.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id FROM pedidos WHERE id = %s", (pedido_id,))
            if cursor.fetchone() is None:
                raise PedidoInexistenteParaControl(f"El pedido {pedido_id} no existe.")

            cursor.execute(
                """
                UPDATE pedidos_renglones
                SET controlado_el = CASE WHEN id = ANY(%s) THEN now() ELSE NULL END
                WHERE pedido_id = %s
                  AND armado_el IS NOT NULL
                  AND anulado_el IS NULL
                """,
                (list(renglones_tildados), pedido_id),
            )
            cursor.execute(
                """
                SELECT count(*) FROM pedidos_renglones
                WHERE pedido_id = %s AND controlado_el IS NOT NULL
                """,
                (pedido_id,),
            )
            (tildados,) = cursor.fetchone()
        conexion.commit()
        return tildados
    finally:
        conexion.close()


def contar_pedidos_sin_controlar(desde, hasta) -> dict:
    """Pedidos ENTREGADOS en el rango con algún renglón armado que nadie controló.

    "Entregado" es tener al menos un renglón armado: la mercadería salió del
    galpón, así que ya se factura y el control llega tarde o no llega.

    HASTA EXCLUYE HOY, y lo decide el que llama: el pedido de hoy se
    controla hoy a la tarde, y una alerta que se prende a la mañana con lo
    que todavía se está por hacer se aprende a ignorar en una semana.

    Con VENTANA, como los pedidos incompletos y por la misma razón: un
    pedido viejo sin controlar ya no se puede controlar —los números que
    había que mirar contra el remito son de hace un mes— así que sin
    ventana quedaría prendida para siempre, sin forma de resolverla ni de
    limpiarla.

    Cuenta PEDIDOS y no renglones: el que abre la pantalla abre un pedido.
    Solo los VIGENTES (anulado_el IS NULL): un pedido anulado no se factura.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*), min(fecha_operacion)
                FROM (
                    SELECT p.id, p.fecha_operacion
                    FROM pedidos p
                    JOIN pedidos_renglones r ON r.pedido_id = p.id
                    WHERE p.anulado_el IS NULL
                      AND p.fecha_operacion >= %s AND p.fecha_operacion <= %s
                      AND r.armado_el IS NOT NULL AND r.anulado_el IS NULL
                    GROUP BY p.id, p.fecha_operacion
                    HAVING count(*) FILTER (WHERE r.controlado_el IS NULL) > 0
                ) sin_controlar
                """,
                (desde, hasta),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": casos, "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def facturacion_por_ficha(cliente_id: int, fecha_desde, fecha_hasta) -> dict:
    """{"por_ficha": {ficha_id: facturación}, "dias": N} de un cliente en un rango — para Márgenes por Artículo.

    LOS DÍAS SE CUENTAN DISTINTO QUE LA PLATA, y la diferencia es a
    propósito: "días con entregas armadas" es sobre el ARMADO, no sobre el
    precio. Un día en el que se armó y entregó algo cuya ficha no tenía
    precio vigente **es un día con entregas** —la mercadería salió— aunque
    no sume un peso a la facturación. Contarlo con el precio de por medio
    haría desaparecer justo el día que hay que ir a mirar.

    LA FACTURACIÓN ES kilos_enviados × PRECIO VIGENTE A LA FECHA DEL
    PEDIDO. Los dos lados de esa multiplicación son deliberados:

    - kilos_enviados es "el número que se factura" (así lo dice el comment
      de la columna): lo que el depósito grabó al armar, congelado. NO se
      usa cantidad × contenido_caja de la ficha, que es lo que mira
      Rentabilidad de Pedidos — esa cuenta es de LO PEDIDO y su propio
      docstring aclara que es "una estimación de rentabilidad, no
      facturación". A pesar del nombre, la columna guarda UNIDADES DE
      VENTA (kilos, unidades o cubetas según la ficha), que es la misma
      unidad en la que está el precio.
    - El precio sale del mismo LATERAL de siempre (ver
      listar_precios_vigentes_por_cliente_en_fechas), anclado a la fecha
      de cada pedido: un cambio de precio no se aplica para atrás.

    Un renglón sin kilaje (nunca se armó), sin ficha (sin identificar, o
    ficha borrada) o sin precio vigente a esa fecha NO SUMA COMO CERO: no
    aparece, y por eso el total de esto puede ser menor que lo realmente
    facturado. Cuánto menor lo mide db/incidencia_facturacion_no_atribuida.sql,
    que parte los renglones en los baldes que compiten con "atribuible".

    El DISTINCT ON de pedidos vigentes es el mismo de buscar_renglones_pedidos
    y listar_renglones_pedidos_vigentes: un pedido corregido es una fila
    nueva y la vieja queda anulada — sin esto, un día con corrección
    facturaría dos veces.

    A diferencia de listar_renglones_pedidos_vigentes, acá SÍ se filtra
    r.anulado_el: un renglón dado de baja no se facturó. Es el criterio de
    Armar Remito (ver _grupos_buscar_pedidos), que es la pantalla con la
    que este número tiene que cerrar.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                WITH vigentes AS (
                    SELECT DISTINCT ON (fecha_operacion) id, fecha_operacion
                    FROM pedidos
                    WHERE cliente_id = %s AND anulado_el IS NULL
                      AND fecha_operacion >= %s AND fecha_operacion <= %s
                    ORDER BY fecha_operacion, creado_en DESC
                ), entregas AS (
                    -- Lo ENTREGADO, sin mirar el precio todavía: de acá salen
                    -- los días. Una sola definición de "esto salió del
                    -- galpón", que después se valúa o no.
                    SELECT v.fecha_operacion, r.ficha_id, r.kilos_enviados
                    FROM vigentes v
                    JOIN pedidos_renglones r ON r.pedido_id = v.id
                    WHERE r.ficha_id IS NOT NULL AND r.anulado_el IS NULL
                      AND r.kilos_enviados IS NOT NULL
                )
                SELECT e.ficha_id, SUM(e.kilos_enviados * p.precio) AS facturado,
                       (SELECT COUNT(DISTINCT fecha_operacion) FROM entregas) AS dias
                FROM entregas e
                -- LEFT y no CROSS: la ficha sin precio vigente a esa fecha
                -- tiene que seguir contando su DÍA aunque no sume plata. Con
                -- CROSS, el renglón desaparecía entero y el día con él.
                LEFT JOIN LATERAL (
                    SELECT precio FROM precios_venta_historial
                    WHERE ficha_id = e.ficha_id AND vigente_desde <= e.fecha_operacion
                    ORDER BY vigente_desde DESC LIMIT 1
                ) p ON TRUE
                GROUP BY e.ficha_id
                """,
                (cliente_id, fecha_desde, fecha_hasta),
            )
            filas = cursor.fetchall()
        # Los días se leen ANTES de filtrar por plata: si ninguna ficha tuvo
        # precio, igual hubo entregas y el número tiene que decirlo.
        dias = int(filas[0][2]) if filas else 0
        return {
            "por_ficha": {f[0]: float(f[1]) for f in filas if f[1] is not None},
            "dias": dias,
        }
    finally:
        conexion.close()


# FALTARON CAJONES: se recibieron MENOS bultos de los que se compraron.
#
# NO ES una diferencia de kilos, y la distinción costó tres mediciones el
# 12/09. De las 25 diferencias de kilaje más grandes, 21 eran de CONTENIDO
# —el cajón vino más pesado o más liviano— y eso resultó ser variación real
# de la fruta: medido por artículo, 17 de 22 referencias tienen desvío menor
# a un kilo y ocho están en cero exacto. Un aviso sobre eso dispararía
# veintiún veces por semana sin nada que corregir.
#
# Las que importan son las otras 2 de 25: Limón 45 -> 35 y Pera 40 -> 34.
# Ahí FALTA MERCADERÍA, no varía el peso del bulto.
#
# MENOS y no "distinto": recibir de más también es un dato, pero no es el
# mismo problema —no falta nada— y mezclarlos dejaría al aviso sin una sola
# cosa que decir.
#
# TODAS LAS UNIDADES, al revés que el intento anterior: los cajones se
# cuentan igual sean de kilo, de unidad o de cubeta. El filtro por 'kilo'
# tenía sentido cuando el umbral era en kilos; acá sería dejar afuera
# faltantes reales por el envase del artículo.
# El par (cómo se COMPRA el artículo, cómo se VENDE la ficha). Escrito UNA
# vez y compartido por el conteo y el detalle: si fueran dos consultas, el
# banner podría decir 1 y la pantalla no mostrar ninguno, y eso es lo único
# que el que lo lee no puede explicar.
#
# POR QUÉ ES UN PROBLEMA: `_costear_compras` (app/costeo.py) divide
# SUM(importe x cajones) por SUM(cajones x contenido_por_cajon) y llama al
# resultado "costo por unidad de VENTA". El numerador es plata y el
# denominador es contenido de COMPRA, así que esa igualdad SOLO vale si las
# dos unidades son la misma. No hay conversión en ningún lado — ver la
# sección de CLAUDE.md sobre unidad_compra y unidad_venta.
# LA MISMA REGLA QUE app.costeo.magnitud_de_la_ficha, escrita en SQL, y hay
# un test que las compara EN LOS DOS SENTIDOS. Una compra declara KILOS
# siempre y —cuando el artículo tiene unidad_conteo— también un conteo: eso
# son las dos magnitudes que este artículo puede ofrecer. Una ficha que
# vende en cualquier OTRA unidad no se puede costear, ni hoy ni con más
# compras.
#
# Ojo con la dirección: `unidad_venta = 'kilo'` NUNCA entra, tenga el
# artículo el conteo que tenga. Los kilos van siempre.
_SQL_UNIDADES_QUE_DIFIEREN = """
    FROM articulos a
    JOIN fichas_logistica f ON f.articulo_id = a.id
    JOIN clientes cl ON cl.id = f.cliente_id
    WHERE a.activo
      AND f.unidad_venta IS NOT NULL
      AND f.unidad_venta <> 'kilo'
      AND f.unidad_venta IS DISTINCT FROM a.unidad_conteo
"""


def contar_unidades_que_diferen() -> int:
    """Fichas que venden en una unidad que su artículo NO PUEDE declarar.

    NO ES "ESTÁ MAL CARGADO", Y ESA PREMISA ESTUVO ACÁ ESCRITA HASTA EL
    15/09. Un artículo se le puede vender a un cliente por unidad y a otro
    por kilo, y eso es el negocio: el mango se compra una vez y va a dos
    clientes que lo quieren distinto. Decir "configuración que queda mal"
    mandaba a ALINEAR la ficha, y alinearla le hace decir que ese cliente
    compra en una unidad en la que no compra — o sea, borra el dato. Un
    aviso que propone destruir información es peor que no tener aviso.

    LO QUE CUENTA HOY, con el modelo de dos magnitudes: una compra declara
    KILOS siempre y, cuando el artículo tiene `unidad_conteo`, también un
    conteo (unidades o cubetas). Ésas son las dos unidades en las que ese
    artículo se puede costear. Una ficha que vende en otra queda SIN COSTO
    —sin precio sugerido y sin utilidad— y no se arregla sola con más
    compras: hay que tocar el artículo.

    POR ESO EL CASO DE LAS DOS UNIDADES YA NO ENTRA. Mango comprado con las
    dos magnitudes, con una ficha en kilo y otra en unidad, costea las dos
    y no aparece acá. Lo que aparece es lo que de verdad no tiene salida
    hasta que alguien haga algo, y el detalle dice qué.

    ES LA MISMA REGLA QUE app.costeo.magnitud_de_la_ficha, y lo cuida un
    test que las compara en los DOS sentidos: si la base admite algo que
    Python no, la pantalla muestra costo donde el aviso dice que no hay; si
    Python admite algo que la base no, la ficha queda sin costear y sin
    aviso, que es el caso caro.

    SIN VENTANA DE TIEMPO, y a propósito: no es un hecho que pase y se
    resuelva solo. Con ventana se apagaría sola a los dos días dejando las
    fichas sin costear para siempre y sin avisar.

    Y NO MIRA SI SE USA. Un par dormido no le falta a nadie hoy, pero el día
    que se compre ese artículo la ficha queda sin costo desde la primera
    compra y nadie va a estar mirando. El que se usa y el que duerme se
    distinguen en el DETALLE, que es donde se decide cuál atender primero.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT COUNT(*)" + _SQL_UNIDADES_QUE_DIFIEREN)
            (casos,) = cursor.fetchone()
        return int(casos)
    finally:
        conexion.close()


def listar_unidades_que_diferen() -> list[dict]:
    """Las fichas sin unidad costeable, con lo que decide si urgen: si ya se usan.

    `compras`, `precios` y `renglones` en cero es un dato DORMIDO —se
    corrige y listo—; con cualquiera en distinto de cero hay una ficha que
    HOY no tiene costo, ni precio sugerido, ni utilidad.

    El nombre del cliente sale de `nombre_cliente` si la ficha lo tiene, y si
    no del cliente: son dos cosas distintas y confundirlas manda a buscar un
    cliente que no existe. Acá gana el de la ficha porque es el que el que
    mira la ficha va a reconocer.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.nombre AS articulo, a.unidad_conteo,
                       COALESCE(f.nombre_cliente, cl.nombre) AS cliente,
                       f.unidad_venta, f.id AS ficha_id,
                       (SELECT COUNT(*) FROM compras c WHERE c.articulo_id = a.id) AS compras,
                       (SELECT COUNT(*) FROM precios_venta_historial v
                         WHERE v.ficha_id = f.id) AS precios,
                       (SELECT COUNT(*) FROM pedidos_renglones r
                         WHERE r.ficha_id = f.id AND r.anulado_el IS NULL) AS renglones
                """
                + _SQL_UNIDADES_QUE_DIFIEREN
                + " ORDER BY a.nombre, f.id"
            )
            columnas = [d[0] for d in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


_SQL_CAJONES_FALTANTES = """
    FROM compras c
    JOIN articulos a ON a.id = c.articulo_id
    JOIN proveedores p ON p.id = c.proveedor_id
    WHERE c.estado = 'recepcionado'
      AND c.cantidad_cajones_real IS NOT NULL
      AND c.fecha_operacion >= %s AND c.fecha_operacion <= %s
      AND (c.cantidad_cajones - c.cantidad_cajones_real) >= %s
"""


def contar_cajones_faltantes(desde, hasta, umbral_cajones) -> dict:
    """Compras que se recibieron con al menos `umbral_cajones` bultos MENOS de los comprados.

    NO SE RECORTA POR EL CORTE, y es a propósito: el corte existe para el
    modelo de STOCK —de ahí para atrás la foto ya trae todo neteado— y esto
    no es una cuenta de stock, es un cotejo entre dos números que alguien
    cargó. El motivo de aquella exclusión no es el motivo de ésta, así que
    no se hereda. Lo que sí lleva es la ventana, por lo de siempre: una
    compra de hace un mes ya no se corrige, y sin ventana la alerta queda
    prendida para siempre.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*), MIN(c.fecha_operacion)" + _SQL_CAJONES_FALTANTES,
                (desde, hasta, umbral_cajones),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def listar_cajones_faltantes(desde, hasta, umbral_cajones) -> list[dict]:
    """Las mismas compras que cuenta contar_cajones_faltantes, con su detalle.

    MISMO RECORTE, escrito UNA vez (_SQL_CAJONES_FALTANTES): si la cuenta y
    la lista tuvieran cada una su WHERE, el día que se separen el banner
    diría un número y la pantalla listaría otro, y nadie sabría cuál mirar.

    Trae los KILOS que representa el faltante además de los bultos: seis
    cajones de Pera son ciento ocho kilos, y el que decide si reclamar mira
    la plata, no la cantidad de cajas.

    Las más grandes primero.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, a.nombre AS articulo,
                       a.unidad_compra, p.nombre AS proveedor,
                       p.codigo_puesto AS puesto,
                       c.cantidad_cajones AS cajones_comprados,
                       c.cantidad_cajones_real AS cajones_recibidos,
                       (c.cantidad_cajones - c.cantidad_cajones_real) AS cajones_faltantes,
                       ((c.cantidad_cajones - c.cantidad_cajones_real)
                        * COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon))
                        AS contenido_faltante
                """
                + _SQL_CAJONES_FALTANTES
                + """
                -- POR FECHA DESCENDENTE, con la magnitud de desempate: es una
                -- lista de reclamos y un reclamo tiene ventana. El porqué entero
                -- está en `listar_diferencia_de_kilos`, que es su hermana y lleva
                -- EL MISMO ORDEN a propósito — se muestran juntas y contestan la
                -- misma pregunta.
                ORDER BY c.fecha_operacion DESC,
                         (c.cantidad_cajones - c.cantidad_cajones_real) DESC
                """,
                (desde, hasta, umbral_cajones),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()



# LA DIFERENCIA DE KILOS, y su recorte más importante NO es el umbral: es
# que solo mira DESDE QUE EXISTE LA FOTO DE BALANZA.
#
# Antes de la foto, el 82% de las recepciones se aceptaba con el estimado
# precargado sin tocarlo, así que "lo recibido" no era un pesaje: era la
# referencia repitiéndose. Una diferencia calculada contra eso no mide
# kilos que faltaron — mide qué tan vieja está la referencia, y ya se midió
# que la referencia está bien en casi todos (12/09). Medir desde la foto es
# lo que convierte esta alerta en algo que se puede reclamar.
#
# EL PISO SALE DE LA BASE Y NO DE UNA FECHA ESCRITA ACÁ, y eso hace dos
# cosas: cada base contesta la suya —el deploy es el mismo, el uso no— y una
# base donde nadie sacó una foto devuelve MIN() NULL, la comparación da NULL
# y no sale ninguna fila. Que una base que no pesa no diga nada es correcto;
# lo que NO puede pasar es que ese cero se lea como "acá no hay problema",
# y por eso `contar` devuelve la fecha del piso al lado del número.
_SQL_DIFERENCIA_DE_KILOS = """
    FROM compras c
    JOIN articulos a ON a.id = c.articulo_id
    JOIN proveedores p ON p.id = c.proveedor_id
    WHERE c.estado = 'recepcionado'
      AND c.contenido_por_cajon_real IS NOT NULL
      AND c.cantidad_cajones_real IS NOT NULL
      AND c.fecha_operacion >= %s AND c.fecha_operacion <= %s
      AND c.fecha_operacion >= (SELECT MIN(""" + _SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col="f.creado_en") + """)
                                  FROM fotos_recepcion f)
      AND (c.contenido_por_cajon - c.contenido_por_cajon_real) >= %s
"""

# El piso, solo, para poder MOSTRARLO. Es la misma expresión que el `where`
# de arriba y por eso sale de un solo lugar: si la consulta recorta por una
# fecha y la pantalla dice otra, el que lee no sabe cuál creer.
_SQL_DESDE_QUE_HAY_FOTO = (
    "SELECT MIN(" + _SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col="f.creado_en") + ") FROM fotos_recepcion f"
)


def contar_diferencia_de_kilos(desde, hasta, umbral_por_cajon) -> dict:
    """Compras donde CADA CAJÓN pesó al menos `umbral_por_cajon` menos de lo comprado.

    SOLO LO QUE FALTÓ, no la diferencia en valor absoluto: un cajón que vino
    más pesado no se le reclama a nadie. Es la misma dirección que la alerta
    de bultos, que también cuenta faltantes y no sobrantes.

    EL UMBRAL VA POR CAJÓN Y NO SOBRE EL TOTAL, y la distinción es la que
    decide si la alerta sirve: **el total dimensiona y el por cajón detecta**.
    Un total grande no dice que haya pasado algo — con treinta y tres cajones,
    tres décimas de ruido de balanza llegan a diez kilos—, así que filtrar por
    el total llena la pantalla de compras GRANDES con diferencias CHICAS. Lo
    que se le reclama a alguien es un cajón que vino livianito de verdad, y eso
    solo se ve en el número por cajón.

    El total se sigue devolviendo y ordena la lista (es la plata, y es lo que
    decide si vale el reclamo); lo que no hace es decidir quién entra.

    NO SE RECORTA POR EL CORTE, por lo mismo que la de bultos: el corte es del
    modelo de stock y esto es un cotejo entre dos números que alguien cargó.
    Lo que sí lleva es la ventana —una compra de hace un mes ya no se
    reclama— y el piso de la foto, que es lo que hace que los números
    signifiquen algo.

    Devuelve `desde_la_foto` AL LADO del número: sin eso, un cero de una base
    que nunca pesó se lee igual que un cero de una base que pesa y no tiene
    diferencias, y los dos ceros dicen cosas opuestas.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*), MIN(c.fecha_operacion), (" + _SQL_DESDE_QUE_HAY_FOTO + ")"
                + _SQL_DIFERENCIA_DE_KILOS,
                (desde, hasta, umbral_por_cajon),
            )
            casos, mas_viejo, desde_la_foto = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo, "desde_la_foto": desde_la_foto}
    finally:
        conexion.close()


def listar_diferencia_de_kilos(desde, hasta, umbral_por_cajon) -> list[dict]:
    """Las mismas compras que cuenta contar_diferencia_de_kilos, con su detalle.

    MISMO RECORTE, escrito UNA vez (_SQL_DIFERENCIA_DE_KILOS): si la cuenta y
    la lista tuvieran cada una su WHERE, el banner diría un número y la
    pantalla listaría otro.

    Trae el contenido POR CAJÓN —que es lo que el comprador cargó, lo que
    Depósito pesó, y lo que DECIDE si la compra entra— y el total faltante al
    lado, que es lo que se reclama y por lo que se ordena. Las más grandes
    primero: entrar lo decide el cajón, atender primero lo decide el total.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, a.nombre AS articulo,
                       a.unidad_compra, p.nombre AS proveedor,
                       p.codigo_puesto AS puesto,
                       c.contenido_por_cajon AS contenido_comprado,
                       c.contenido_por_cajon_real AS contenido_recibido,
                       (c.contenido_por_cajon - c.contenido_por_cajon_real)
                        AS contenido_faltante_por_cajon,
                       c.cantidad_cajones_real AS cajones_recibidos,
                       ((c.contenido_por_cajon - c.contenido_por_cajon_real)
                        * c.cantidad_cajones_real) AS contenido_faltante_total
                """
                + _SQL_DIFERENCIA_DE_KILOS
                + """
                -- POR FECHA DESCENDENTE, y la magnitud es el desempate.
                -- Esta lista contesta "¿qué compra reclamo?", y un reclamo tiene
                -- ventana: la de hoy y la de ayer se reclaman, la de hace cuatro
                -- días ya pasó. Ordenada por magnitud, el faltante más grande de
                -- la semana quedaba arriba aunque ya no se pudiera hacer nada con
                -- él, y el de hoy —accionable— caía al fondo. Dentro del mismo
                -- día sí manda el tamaño.
                --
                -- MISMO CRITERIO QUE `listar_cajones_faltantes`, y es a
                -- propósito: las dos alertas se muestran una al lado de la otra y
                -- contestan la misma pregunta. Dos órdenes distintos ahí no son
                -- dos estilos: uno de los dos está mal.
                ORDER BY c.fecha_operacion DESC,
                         ((c.contenido_por_cajon - c.contenido_por_cajon_real)
                          * c.cantidad_cajones_real) DESC
                """,
                (desde, hasta, umbral_por_cajon),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def fecha_de_la_primera_foto_de_balanza():
    """Desde cuándo esta base pesa de verdad, o None si nunca se sacó una foto.

    Lo lee la pantalla de Alertas para poder DECIR contra qué se midió. Es la
    misma expresión que usa el recorte, en una sola constante: una pantalla
    que dice una fecha distinta de la que la consulta usó es peor que no
    decir ninguna.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_SQL_DESDE_QUE_HAY_FOTO)
            (fecha,) = cursor.fetchone()
        return fecha
    finally:
        conexion.close()

def listar_pedidos_incompletos(fecha_desde) -> list[dict]:
    """Los RENGLONES que explican los pedidos que cuenta contar_pedidos_incompletos.

    OJO CON LAS DOS UNIDADES, que es la trampa de esta pareja: la cuenta
    devuelve PEDIDOS y esto devuelve RENGLONES. Son dos números distintos con
    el mismo tema, y por eso la pantalla muestra los dos con su nombre — "3
    pedidos, 11 renglones"— en vez de elegir uno y dejar al otro sin rótulo.

    MISMO CRITERIO que la cuenta: renglones armables (con sucursal e
    identificados), del pedido VIGENTE de cada cliente y fecha, armados con
    menos bultos de los pedidos. Lo que la cuenta agrega y esto no puede
    mostrar como renglón es la otra mitad del criterio —un pedido CERRADO con
    renglones sin armar—, así que ésos también entran acá, con lo armado en
    NULL: el renglón no se armó, y decir 0 sería inventar un número.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                WITH vigentes AS (
                    SELECT DISTINCT ON (p.cliente_id, p.fecha_operacion)
                           p.id, p.fecha_operacion, p.cliente_id, p.armado_cerrado_el
                    FROM pedidos p
                    WHERE p.anulado_el IS NULL AND p.fecha_operacion >= %s
                    ORDER BY p.cliente_id, p.fecha_operacion, p.creado_en DESC
                )
                SELECT v.id AS pedido_id, v.fecha_operacion, cl.nombre AS cliente,
                       r.sucursal,
                       COALESCE(a.nombre, r.texto_descripcion, r.texto_codigo) AS articulo,
                       r.cantidad AS pedido, r.cantidad_armada AS armado,
                       r.cantidad - COALESCE(r.cantidad_armada, 0) AS faltante
                FROM vigentes v
                JOIN clientes cl ON cl.id = v.cliente_id
                JOIN pedidos_renglones r ON r.pedido_id = v.id
                LEFT JOIN articulos a ON a.id = r.articulo_id
                WHERE r.articulo_id IS NOT NULL AND r.anulado_el IS NULL
                  AND r.sucursal IS NOT NULL
                  AND (
                        (r.armado_el IS NOT NULL AND r.cantidad_armada IS NOT NULL
                         AND r.cantidad_armada < r.cantidad)
                     OR (v.armado_cerrado_el IS NOT NULL AND r.armado_el IS NULL)
                  )
                ORDER BY v.fecha_operacion DESC, cl.nombre, r.sucursal,
                         COALESCE(a.nombre, r.texto_descripcion, r.texto_codigo)
                """,
                (fecha_desde,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def contar_pedidos_incompletos(fecha_desde) -> dict:
    """Pedidos vigentes desde una fecha que salieron con mercadería incompleta, y el más viejo.

    Incompleto = algún renglón armado con MENOS bultos que los pedidos, o
    renglones sin armar en un pedido ya cerrado con Terminar (un pedido a medio
    armar todavía no es noticia). Solo renglones armables (con sucursal e
    identificados), mismo criterio que los conteos de Armar.

    El "<" es a propósito y arregla un bug: la versión vieja de Auditoría
    comparaba con "<>", así que un renglón armado de MÁS (18 de 15) aparecía
    bajo un título que decía "se armó menos de lo pedido".

    LLEVA VENTANA, al revés que las compras sin precio: un pedido que ya salió
    incompleto no se puede completar después. Sin ventana, quedaría en la lista
    para siempre sin forma de resolverlo ni limpiarlo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN(fecha_operacion) FROM (
                    SELECT DISTINCT ON (p.cliente_id, p.fecha_operacion)
                           p.id, p.fecha_operacion, p.armado_cerrado_el,
                           (SELECT COUNT(*) FROM pedidos_renglones r
                            WHERE r.pedido_id = p.id AND r.articulo_id IS NOT NULL
                              AND r.anulado_el IS NULL AND r.sucursal IS NOT NULL
                              AND r.armado_el IS NOT NULL AND r.cantidad_armada IS NOT NULL
                              AND r.cantidad_armada < r.cantidad) AS renglones_cortos,
                           (SELECT COUNT(*) FROM pedidos_renglones r
                            WHERE r.pedido_id = p.id AND r.articulo_id IS NOT NULL
                              AND r.anulado_el IS NULL AND r.sucursal IS NOT NULL
                              AND r.armado_el IS NULL) AS renglones_sin_armar
                    FROM pedidos p
                    WHERE p.anulado_el IS NULL AND p.fecha_operacion >= %s
                    ORDER BY p.cliente_id, p.fecha_operacion, p.creado_en DESC
                ) vigentes
                WHERE renglones_cortos > 0
                   OR (armado_cerrado_el IS NOT NULL AND renglones_sin_armar > 0)
                """,
                (fecha_desde,),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def listar_casillas_pedidos() -> list[dict]:
    """Las casillas de pedidos configuradas (hoy una: Día), con el nombre del cliente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT ca.id, ca.direccion, ca.servidor_imap, ca.cliente_id,
                       ca.asunto_filtro, ca.remitentes_permitidos,
                       ca.activa, ca.fecha_activacion, ca.auto_confirmar,
                       ca.revision_desde, ca.revision_hasta, ca.revision_cada_minutos,
                       ca.ultima_revision_el, ca.ultima_revision_automatica_el,
                       ca.ultimo_error, ca.ultimo_error_el,
                       c.nombre AS cliente_nombre
                FROM casillas_pedidos ca
                JOIN clientes c ON c.id = ca.cliente_id
                ORDER BY ca.id
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def obtener_casilla_pedidos(casilla_id: int) -> dict | None:
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT ca.id, ca.direccion, ca.servidor_imap, ca.cliente_id,
                       ca.asunto_filtro, ca.remitentes_permitidos,
                       ca.activa, ca.fecha_activacion, ca.auto_confirmar,
                       ca.revision_desde, ca.revision_hasta, ca.revision_cada_minutos,
                       ca.ultima_revision_el, ca.ultima_revision_automatica_el,
                       ca.ultimo_error, ca.ultimo_error_el,
                       c.nombre AS cliente_nombre
                FROM casillas_pedidos ca
                JOIN clientes c ON c.id = ca.cliente_id
                WHERE ca.id = %s
                """,
                (casilla_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def crear_casilla_pedidos(
    direccion: str, servidor_imap: str, cliente_id: int, asunto_filtro: str, remitentes_permitidos: str | None
) -> int:
    """Da de alta una casilla, DESACTIVADA: se activa aparte, cuando la clave ya está en Railway.

    El asunto es el filtro obligatorio (por contenido); los remitentes son
    opcionales (None = cualquier remitente, para no perder un pedido
    porque cambió quién lo manda).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO casillas_pedidos (direccion, servidor_imap, cliente_id, asunto_filtro, remitentes_permitidos)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (direccion, servidor_imap, cliente_id, asunto_filtro, remitentes_permitidos),
            )
            (casilla_id,) = cursor.fetchone()
        conexion.commit()
        return casilla_id
    finally:
        conexion.close()


def actualizar_casilla_pedidos(
    casilla_id: int, direccion: str, servidor_imap: str, cliente_id: int, asunto_filtro: str, remitentes_permitidos: str | None
) -> None:
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE casillas_pedidos
                SET direccion = %s, servidor_imap = %s, cliente_id = %s, asunto_filtro = %s, remitentes_permitidos = %s
                WHERE id = %s
                """,
                (direccion, servidor_imap, cliente_id, asunto_filtro, remitentes_permitidos, casilla_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def activar_casilla_pedidos(casilla_id: int, fecha_activacion) -> None:
    """Activa la casilla con su fecha de activación: solo se miran correos POSTERIORES a esto."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE casillas_pedidos SET activa = true, fecha_activacion = %s WHERE id = %s",
                (fecha_activacion, casilla_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def desactivar_casilla_pedidos(casilla_id: int) -> None:
    """Baja el interruptor. La fecha de activación queda: si se reactiva, sigue desde ahí."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE casillas_pedidos SET activa = false WHERE id = %s", (casilla_id,))
        conexion.commit()
    finally:
        conexion.close()


def cambiar_fecha_activacion_casilla(casilla_id: int, fecha_activacion) -> None:
    """Corrige a mano desde cuándo se miran los correos (p. ej. para releer un día puntual)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE casillas_pedidos SET fecha_activacion = %s WHERE id = %s",
                (fecha_activacion, casilla_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def fijar_auto_confirmar_casilla(casilla_id: int, valor: bool) -> None:
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE casillas_pedidos SET auto_confirmar = %s WHERE id = %s", (valor, casilla_id))
        conexion.commit()
    finally:
        conexion.close()


def guardar_horario_revision_casilla(casilla_id: int, desde, hasta, cada_minutos: int) -> None:
    """El horario de la revisión automática de UNA casilla: desde, hasta y cada cuántos minutos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE casillas_pedidos
                SET revision_desde = %s, revision_hasta = %s, revision_cada_minutos = %s
                WHERE id = %s
                """,
                (desde, hasta, cada_minutos, casilla_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def registrar_revision_casilla(casilla_id: int, error: str | None = None, automatica: bool = False) -> None:
    """Deja rastro de cada revisión: la exitosa por un lado, el último error por el otro.

    Si el último error es más nuevo que la última revisión exitosa, la
    casilla está fallando — eso mira la pantalla. Una revisión exitosa
    AUTOMÁTICA además sella ultima_revision_automatica_el: el botón
    manual NO la toca, y la alerta de Auditoría mira SOLO esa — así un
    tick muerto se detecta aunque el dueño revise a mano todos los días
    (el punto ciego del diagnóstico del 25/08). Nunca se pisa una cosa
    con la otra.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if error is None and automatica:
                cursor.execute(
                    "UPDATE casillas_pedidos SET ultima_revision_el = now(), ultima_revision_automatica_el = now() WHERE id = %s",
                    (casilla_id,),
                )
            elif error is None:
                cursor.execute(
                    "UPDATE casillas_pedidos SET ultima_revision_el = now() WHERE id = %s",
                    (casilla_id,),
                )
            else:
                cursor.execute(
                    "UPDATE casillas_pedidos SET ultimo_error = %s, ultimo_error_el = now() WHERE id = %s",
                    (error, casilla_id),
                )
        conexion.commit()
    finally:
        conexion.close()


def registrar_tick_revision() -> None:
    """El latido del bucle: se sella en CADA tick, aunque no toque revisar nada.

    Es lo que separa "sin novedades" de "el bucle está muerto": si esta
    marca queda vieja, el bucle no corre — visible en Sistema sin
    deducir nada de los logs.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO revision_tick (id, ultimo_tick_el) VALUES (1, now())
                ON CONFLICT (id) DO UPDATE SET ultimo_tick_el = now()
                """
            )
        conexion.commit()
    finally:
        conexion.close()


def obtener_ultimo_tick_revision():
    """Cuándo fue el último tick del bucle (None si nunca corrió), para la pantalla de Sistema."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT ultimo_tick_el FROM revision_tick WHERE id = 1")
            fila = cursor.fetchone()
        return fila[0] if fila else None
    finally:
        conexion.close()


def registrar_mail_pedido(
    casilla_id: int,
    cliente_id: int,
    message_id: str,
    remitente: str,
    asunto: str | None,
    recibido_el,
    cuerpo_crudo: str,
    cuerpo_texto: str | None,
) -> int | None:
    """Registra un mail detectado, UNA sola vez: si el Message-ID ya está, devuelve None y no toca nada.

    Esta es la idempotencia de toda la etapa 3 — la revisión puede correr
    mil veces sobre el mismo buzón sin duplicar nada y sin marcar nada en
    el mailbox.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO mails_pedido
                    (casilla_id, cliente_id, message_id, remitente, asunto, recibido_el, cuerpo_crudo, cuerpo_texto)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING
                RETURNING id
                """,
                (casilla_id, cliente_id, message_id, remitente, asunto, recibido_el, cuerpo_crudo, cuerpo_texto),
            )
            fila = cursor.fetchone()
        conexion.commit()
        return fila[0] if fila else None
    finally:
        conexion.close()


def obtener_mail_pedido(mail_id: int) -> dict | None:
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.id, m.casilla_id, m.cliente_id, m.message_id, m.remitente, m.asunto,
                       m.recibido_el, m.cuerpo_crudo, m.cuerpo_texto, m.estado, m.motivo,
                       m.pedido_id, m.procesado_el, m.creado_en,
                       c.nombre AS cliente_nombre
                FROM mails_pedido m
                JOIN clientes c ON c.id = m.cliente_id
                WHERE m.id = %s
                """,
                (mail_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def listar_mails_pedido(limite: int = 30) -> list[dict]:
    """Los últimos mails registrados, pendientes y con error arriba (son los que piden acción)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.id, m.message_id, m.remitente, m.asunto, m.recibido_el, m.estado,
                       m.motivo, m.pedido_id, m.procesado_el, m.creado_en,
                       c.nombre AS cliente_nombre
                FROM mails_pedido m
                JOIN clientes c ON c.id = m.cliente_id
                ORDER BY (m.estado IN ('pendiente', 'error')) DESC, m.recibido_el DESC
                LIMIT %s
                """,
                (limite,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_mails_pedido_sin_procesar_de_cliente(cliente_id: int) -> list[dict]:
    """Los mails PENDIENTES o CON ERROR de un cliente, para mostrarlos en SU pantalla de Pedido.

    El mail trabado no puede quedar estacionado solo en Sistema: el que
    arma tiene que verlo donde trabaja. Los más nuevos primero.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, remitente, asunto, recibido_el, estado, motivo
                FROM mails_pedido
                WHERE cliente_id = %s AND estado IN ('pendiente', 'error')
                ORDER BY recibido_el DESC
                """,
                (cliente_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def marcar_mail_pedido_confirmado(mail_id: int, pedido_id: int, motivo: str | None = None) -> None:
    """Confirma el mail apuntando al pedido. motivo distingue el auto-confirmado ("Confirmado automáticamente")."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE mails_pedido
                SET estado = 'confirmado', pedido_id = %s, motivo = %s, procesado_el = now()
                WHERE id = %s
                """,
                (pedido_id, motivo, mail_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def marcar_mail_pedido_ignorado(mail_id: int, motivo: str | None = None) -> None:
    """Marca el mail como ignorado (no era un pedido). El registro queda: nada desaparece en silencio."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE mails_pedido
                SET estado = 'ignorado', motivo = %s, procesado_el = now()
                WHERE id = %s AND estado IN ('pendiente', 'error')
                """,
                (motivo, mail_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def marcar_mail_pedido_error(mail_id: int, motivo: str) -> None:
    """Deja grabado que la lectura de este mail FALLÓ, con el motivo.

    El mail no se pierde: queda en estado error (reintentable desde la
    pantalla, igual que un pendiente) y alimenta la alerta de Auditoría —
    una lectura que falla a las 12:00 corriendo sola se tiene que ver.
    Un mail ya confirmado o ignorado no se pisa.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE mails_pedido
                SET estado = 'error', motivo = %s, procesado_el = now()
                WHERE id = %s AND estado IN ('pendiente', 'error')
                """,
                (motivo, mail_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def contar_mails_pedido_sin_procesar() -> dict:
    """Auditoría: mails de pedido registrados que nadie confirmó todavía (pendientes o con error), y el más viejo."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN((recibido_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date)
                FROM mails_pedido
                WHERE estado IN ('pendiente', 'error')
                """
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def marcar_lectura_mail_pedido(mail_id: int, leido_con_ia: bool) -> None:
    """Graba CÓMO se leyó el mail la última vez: por estructura (false) o cayendo al camino IA (true).

    Se pisa en cada lectura: si un reintento posterior entra por
    estructura, la marca vuelve a false — la alerta refleja el estado
    real, no la historia.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE mails_pedido SET leido_con_ia = %s WHERE id = %s",
                (leido_con_ia, mail_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def contar_mails_pedido_leidos_con_ia(fecha_desde) -> dict:
    """Auditoría: mails de pedido recientes cuya lectura cayó al camino IA (el parser no pudo), y el más viejo.

    Si Día cambia el formato del mail, esto lo dice ese mismo día — antes
    de que un cruce de bultos llegue a una entrega.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN((recibido_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date)
                FROM mails_pedido
                WHERE leido_con_ia AND recibido_el >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                """,
                (fecha_desde,),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def compras_de_hoy_por_articulo() -> dict:
    """Lo comprado HOY por artículo: {articulo_id: {cajones, kilos, conteo}}.

    Para la columna "Compré hoy" de "Qué comprar hoy", que tiene que bajar
    el saldo MIENTRAS SE COMPRA y no cuando llega.

    ENTRAN 'pendiente' Y 'recepcionado', y es decisión del dueño (21/09):
    "parado en el Mercado el saldo tiene que bajar cuando compro, no cuando
    llega". Una compra recién cargada está en 'pendiente' — contando solo lo
    recepcionado, la columna no se movería justo en el momento en que se la
    mira. Quedan afuera 'rechazado' y 'no_ingresado', que no entraron.

    LAS DOS MAGNITUDES VIAJAN SEPARADAS y ninguna se deduce de la otra:
    quien llama elige con `magnitud_de_la_ficha` cuál corresponde a la fila.
    Sumarlas o convertirlas sería el factor que este sistema rechazó.

    LO REAL PRIMERO Y EL ESTIMADO DE RESPALDO, que es la misma regla que usa
    la cuenta de stock: lo pesado es lo que hay, y el estimado entra solo
    donde nadie pesó todavía — que es el caso normal de una compra de hoy,
    porque el camión no llegó.

    HOY es el día ARGENTINO, no el del servidor: un offset fijo no se entera
    el día que el país mueva el reloj, y lo haría en silencio.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.articulo_id,
                       SUM(COALESCE(c.cantidad_cajones_real, c.cantidad_cajones)) AS cajones,
                       SUM(COALESCE(c.cantidad_kilos_real, c.cantidad_kilos))     AS kilos,
                       SUM(COALESCE(c.cantidad_fraccion_real, c.cantidad_fraccion)) AS conteo
                FROM compras c
                WHERE c.fecha_operacion = {_SQL_HOY_ARGENTINA}
                  AND c.estado IN ('pendiente', 'recepcionado')
                GROUP BY c.articulo_id
                """
            )
            return {
                fila[0]: {
                    "cajones": float(fila[1]) if fila[1] is not None else 0.0,
                    "kilos": float(fila[2]) if fila[2] is not None else None,
                    "conteo": float(fila[3]) if fila[3] is not None else None,
                }
                for fila in cursor.fetchall()
            }
    finally:
        conexion.close()


def renglones_de_los_ultimos_pedidos(cliente_ids: list[int], anterior_a, pedidos: int = 6) -> list[dict]:
    """Lo que pidieron estos clientes en sus últimos `pedidos` pedidos VIGENTES.

    Para "Qué comprar hoy": una fila por (cliente, artículo, ficha) con los
    BULTOS sumados y con qué dividirlos para llegar a la magnitud de la fila.

    VIGENTES, NO "NO ANULADOS", y es la diferencia que más caro sale: un
    pedido RECARGADO no se anula — deja de ser el vigente, y su reemplazo
    queda con la misma `fecha_operacion`. Contando los dos, la demanda de
    ese día entra DOS VECES y el promedio sale inflado sin que nada se vea
    raro. Es el bug exacto que tuvo `arandano_1` el 18/09. El `DISTINCT ON
    (cliente_id, fecha_operacion) ORDER BY ... creado_en DESC` se queda con
    el último cargado de cada día, que es la misma regla que usa el resto
    del sistema.

    LOS RENGLONES SON LOS ARMABLES, con el filtro de la casa:
    `articulo_id IS NOT NULL AND anulado_el IS NULL AND sucursal IS NOT NULL`.
    El tercero es el que no es obvio: un renglón identificado SIN sucursal
    "vino sin cantidades en el mail y no se arma jamás" — el confirmar los
    guarda igual, en cero, porque nada del mail se pierde. Sin ese filtro
    entran al promedio como ceros y lo hunden.

    `anterior_a` ES EL ANCLA Y NO TIENE DEFAULT, a propósito. Se miran los
    pedidos con `fecha_operacion < anterior_a`, ESTRICTO: el día que se carga
    no entra. Es el día en que se abrió la carga y no la fecha de compra
    (dueño, 22/09): si se carga hoy para el 27, el promedio mira los 6
    anteriores a hoy.

    SIN ESTE RECORTE LA CONSULTA NO FILTRABA POR FECHA NINGUNA y tomaba los
    últimos 6 por `fecha_operacion DESC`, FUTUROS INCLUIDOS. O sea que el
    pedido real de la fecha que se va a comprar entraba al promedio y, con
    divisor 6, contaba como un sexto de sí mismo — diluyéndolo en vez de
    usarlo. Un default acá volvería a abrir eso para el llamador que se lo
    olvide, y no fallaría: devolvería un número plausible.

    `pedidos_del_cliente` ES EL DIVISOR, y viene por fila porque puede ser
    MENOR que `pedidos`: un cliente con tres pedidos en su historia tiene
    "los últimos 6" = 3, y dividir igual por 6 lo parte al medio. Eso es
    distinto de dividir por los días en que el ARTÍCULO apareció, que es lo
    que el dueño rechazó el 21/09: ahí el divisor es fijo justamente porque
    se compra para un día cualquiera.

    `contenido_caja` puede venir en NULL (renglón sin ficha, o ficha sin
    contenido): quien llama deja esa fila SIN NÚMERO en vez de en cero. Un
    cero diría que ese cliente no pide nada.
    """
    if not cliente_ids:
        return []
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                WITH vigentes AS (
                    SELECT DISTINCT ON (p.cliente_id, p.fecha_operacion)
                           p.id, p.cliente_id, p.fecha_operacion
                    FROM pedidos p
                    WHERE p.cliente_id = ANY(%s) AND p.anulado_el IS NULL
                      AND p.fecha_operacion < %s
                    ORDER BY p.cliente_id, p.fecha_operacion DESC, p.creado_en DESC
                ), elegidos AS (
                    SELECT v.id, v.cliente_id, v.fecha_operacion
                    FROM (SELECT v.*, row_number() OVER (PARTITION BY v.cliente_id
                                                         ORDER BY v.fecha_operacion DESC) AS n
                          FROM vigentes v) v
                    WHERE v.n <= %s
                )
                SELECT e.cliente_id, r.articulo_id, a.nombre AS articulo_nombre,
                       a.unidad_conteo, a.contenido_referencia,
                       r.ficha_id, f.contenido_caja, f.unidad_venta,
                       SUM(r.cantidad) AS bultos,
                       (SELECT count(*) FROM elegidos e2
                         WHERE e2.cliente_id = e.cliente_id) AS pedidos_del_cliente,
                       MIN(e.fecha_operacion) AS desde,
                       MAX(e.fecha_operacion) AS hasta
                FROM elegidos e
                JOIN pedidos_renglones r ON r.pedido_id = e.id
                JOIN articulos a ON a.id = r.articulo_id
                LEFT JOIN fichas_logistica f ON f.id = r.ficha_id
                WHERE r.articulo_id IS NOT NULL
                  AND r.anulado_el IS NULL
                  AND r.sucursal IS NOT NULL
                GROUP BY e.cliente_id, r.articulo_id, a.nombre, a.unidad_conteo,
                         a.contenido_referencia, r.ficha_id, f.contenido_caja, f.unidad_venta
                """,
                (list(cliente_ids), anterior_a, pedidos),
            )
            columnas = [c[0] for c in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def borrador_de_compra(fecha) -> dict | None:
    """El borrador de "Qué comprar hoy" de esa fecha: qué cargas arma y los kilajes tocados.

    Devuelve `None` cuando no hay ninguno, que es distinto de un borrador
    vacío: el `None` dice que hoy todavía no se armó ninguno, y la pantalla
    no ofrece cerrar algo que no existe.

    NO TRAE MARGEN, a propósito (dueño, 23/09): el margen vive en cada
    carga. Un segundo margen acá se multiplica con el de la carga —20% y 10%
    son 32%— y nadie hace esa cuenta con el pulgar. No existe "los dos, pero
    uno casi siempre en cero": el día que alguien toque el apagado, vuelve la
    multiplicación y vuelve invisible.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, fecha, estado
                FROM listados_compra
                WHERE fecha = %s AND estado = 'borrador'
                """,
                (fecha,),
            )
            cabecera = cursor.fetchone()
            if cabecera is None:
                return None
            listado_id = cabecera[0]

            cursor.execute(
                "SELECT carga_id FROM listados_compra_cargas WHERE listado_id = %s",
                (listado_id,),
            )
            cargas = {int(f[0]) for f in cursor.fetchall()}

            cursor.execute(
                "SELECT articulo_id, kilaje FROM listados_compra_kilaje WHERE listado_id = %s",
                (listado_id,),
            )
            kilajes = {int(f[0]): float(f[1]) for f in cursor.fetchall()}

            return {
                "id": listado_id,
                "fecha": cabecera[1],
                "estado": cabecera[2],
                "cargas": cargas,
                "kilajes": kilajes,
            }
    finally:
        conexion.close()


def guardar_borrador_de_compra(fecha, cargas: set, kilajes: dict) -> int:
    """Guarda el borrador de esa fecha entero, y devuelve su id.

    TODO EN UNA TRANSACCIÓN Y BORRANDO ANTES DE ESCRIBIR. Las dos tablas
    hijas se reemplazan, no se mezclan: destildar una carga o borrar un
    kilaje son operaciones que un `upsert` no puede expresar —lo que ya no
    está tiene que irse— y un borrado parcial dejaría la pantalla mostrando
    algo que el comprador sacó.

    `cargas` es el conjunto de ids tildados y `kilajes` {articulo_id: kilaje}.
    Los dos son lo que quedó, no lo que cambió.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM listados_compra
                WHERE fecha = %s AND estado = 'borrador'
                """,
                (fecha,),
            )
            fila = cursor.fetchone()
            if fila is None:
                cursor.execute(
                    """
                    INSERT INTO listados_compra (fecha, estado)
                    VALUES (%s, 'borrador') RETURNING id
                    """,
                    (fecha,),
                )
                listado_id = cursor.fetchone()[0]
            else:
                listado_id = fila[0]
                cursor.execute(
                    "UPDATE listados_compra SET actualizado_en = now() WHERE id = %s",
                    (listado_id,),
                )

            cursor.execute("DELETE FROM listados_compra_kilaje WHERE listado_id = %s", (listado_id,))
            cursor.execute("DELETE FROM listados_compra_cargas WHERE listado_id = %s", (listado_id,))

            for carga_id in sorted(cargas):
                cursor.execute(
                    "INSERT INTO listados_compra_cargas VALUES (%s, %s)",
                    (listado_id, carga_id),
                )
            for articulo_id, kilaje in kilajes.items():
                cursor.execute(
                    "INSERT INTO listados_compra_kilaje VALUES (%s, %s, %s)",
                    (listado_id, articulo_id, kilaje),
                )
            conexion.commit()
            return listado_id
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def cerrar_borrador_de_compra(fecha) -> bool:
    """Pasa el borrador de esa fecha a 'cerrado'. Devuelve si había uno.

    Cerrar NO borra nada: el listado queda como historial de lo que se salió
    a comprar ese día, y el índice parcial deja abrir uno nuevo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE listados_compra SET estado = 'cerrado', actualizado_en = now()
                 WHERE fecha = %s AND estado = 'borrador'
                """,
                (fecha,),
            )
            cambiadas = cursor.rowcount
            conexion.commit()
            return cambiadas > 0
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def carga_de_compra(cliente_id: int, fecha) -> dict | None:
    """La carga de ESE cliente para ESA fecha, con sus renglones. None si no hay.

    `None` no es una carga vacía: una carga que existe en modo automático
    tampoco tiene renglones, y las dos cosas se ven igual mirando solo la
    lista. La pantalla necesita distinguirlas para poder preguntar lo que
    el dueño pidió —editarla o borrarla y empezar de cero— en vez de crear
    una segunda que sume doble.

    VIENE ENTERA EN UNA LECTURA porque la pantalla usa las dos mitades en el
    mismo render.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cliente_id, fecha, modo, promedio_anterior_a,
                       margen_porcentaje
                FROM cargas_compra WHERE cliente_id = %s AND fecha = %s
                """,
                (cliente_id, fecha),
            )
            cabecera = cursor.fetchone()
            if cabecera is None:
                return None
            carga_id = cabecera[0]
            cursor.execute(
                """
                SELECT articulo_id, total, contenido_por_bulto FROM cargas_compra_renglones
                WHERE carga_id = %s
                """,
                (carga_id,),
            )
            filas = cursor.fetchall()
            renglones = {int(f[0]): float(f[1]) for f in filas}
            # EL "POR BULTO" VIAJA APARTE y no adentro de `renglones`: ese dict
            # es {articulo: total} y lo leen el listado y `lo_que_pide_la_carga`,
            # que suman kilos y no necesitan saber de bultos. Meterlo adentro
            # cambiaría la forma de lo que tres lugares ya leen.
            por_bulto = {int(f[0]): float(f[2]) for f in filas if f[2] is not None}
            return {
                "id": carga_id,
                "cliente_id": int(cabecera[1]),
                "fecha": cabecera[2],
                "modo": cabecera[3],
                "promedio_anterior_a": cabecera[4],
                "margen": float(cabecera[5]),
                "renglones": renglones,
                "por_bulto": por_bulto,
            }
    finally:
        conexion.close()


def cargas_con_renglones(carga_ids) -> list[dict]:
    """Las cargas de esos ids, cada una con sus renglones guardados.

    Es la lectura del Paso 2: el listado suma cargas, y cada una trae lo
    mismo que `carga_de_compra` —cliente, modo, ancla, margen y renglones—
    para que lo que se sume sea exactamente lo que la carga mostró.

    DOS CONSULTAS PARA TODAS y no dos por carga: un listado arma varias.
    """
    ids = sorted({int(i) for i in carga_ids})
    if not ids:
        return []
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.cliente_id, cl.nombre, c.fecha, c.modo,
                       c.promedio_anterior_a, c.margen_porcentaje
                FROM cargas_compra c
                JOIN clientes cl ON cl.id = c.cliente_id
                WHERE c.id = ANY(%s)
                ORDER BY c.fecha, cl.nombre
                """,
                (ids,),
            )
            cargas = [
                {"id": int(f[0]), "cliente_id": int(f[1]), "cliente_nombre": f[2],
                 "fecha": f[3], "modo": f[4], "promedio_anterior_a": f[5],
                 "margen": float(f[6]), "renglones": {}}
                for f in cursor.fetchall()
            ]
            por_id = {c["id"]: c for c in cargas}
            cursor.execute(
                """
                SELECT carga_id, articulo_id, total FROM cargas_compra_renglones
                WHERE carga_id = ANY(%s)
                """,
                (ids,),
            )
            for carga_id, articulo_id, total in cursor.fetchall():
                por_id[int(carga_id)]["renglones"][int(articulo_id)] = float(total)
            return cargas
    finally:
        conexion.close()


def guardar_carga_de_compra(cliente_id: int, fecha, modo, promedio_anterior_a, margen) -> int:
    """Crea o actualiza la carga de ese cliente para esa fecha. Devuelve su id.

    EL MARGEN SÍ SE PISA Y EL ANCLA NO, y no es una inconsistencia: el
    margen es lo que el comprador acaba de tipear en esta pantalla, así que
    guardarlo es el punto de guardar. El ancla es cuándo se abrió la carga,
    que no cambia porque alguien la edite.

    EL `ON CONFLICT` NO PISA `promedio_anterior_a`, Y ESO ES LA REGLA, no una
    omisión: editar una carga NO mueve el ancla del promedio —es la misma
    carga— y borrarla y empezar de cero SÍ, porque ahí la fila se borra y la
    nueva nace con la de hoy. Son exactamente las dos opciones que el dueño
    pidió al re-entrar (22/09), y completar el SET con esta columna haría
    que la ventana del promedio se corriera sola cada vez que alguien toca
    la pantalla.

    Los renglones NO se tocan acá y también es a propósito: pasar un rato a
    automático no puede borrar lo que se tipeó o se leyó de un archivo. Con
    el archivo adentro eso dejó de ser barato — re-tipear molesta, releer un
    archivo cuesta una lectura con IA y otra revisión.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cargas_compra
                       (cliente_id, fecha, modo, promedio_anterior_a, margen_porcentaje)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (cliente_id, fecha) DO UPDATE
                   SET modo = EXCLUDED.modo,
                       margen_porcentaje = EXCLUDED.margen_porcentaje,
                       actualizado_en = now()
                RETURNING id
                """,
                (cliente_id, fecha, modo, promedio_anterior_a, margen),
            )
            carga_id = cursor.fetchone()[0]
            conexion.commit()
            return carga_id
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def guardar_renglones_de_carga(carga_id: int, renglones: dict,
                               por_bulto: dict | None = None) -> None:
    """Reemplaza los renglones de una carga. `renglones` es {articulo_id: total}.

    `por_bulto` es {articulo_id: cuánto trae un bulto}, SOLO de los que el
    que cargó declaró distinto del de la ficha: el que falta queda en NULL y
    la pantalla le propone el de la ficha, que es lo que la columna dice.

    BORRA ANTES DE ESCRIBIR, en una transacción: es lo que quedó, no lo que
    cambió. Sacarle un artículo a la carga tiene que llevárselo, y eso un
    `upsert` no lo puede expresar.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "DELETE FROM cargas_compra_renglones WHERE carga_id = %s", (carga_id,)
            )
            por_bulto = por_bulto or {}
            for articulo_id, total in renglones.items():
                # CON LAS COLUMNAS NOMBRADAS: el INSERT posicional de antes
                # dependía del orden de la tabla, y la columna nueva quedó al
                # final justo por eso. El que se agregue en el medio no avisaría.
                cursor.execute(
                    "INSERT INTO cargas_compra_renglones"
                    " (carga_id, articulo_id, total, contenido_por_bulto)"
                    " VALUES (%s, %s, %s, %s)",
                    (carga_id, articulo_id, total, por_bulto.get(articulo_id)),
                )
            conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def borrar_carga_de_compra(cliente_id: int, fecha) -> bool:
    """Borra la carga de ese cliente y esa fecha. Devuelve si había una.

    Se lleva sus renglones por la cascada. Si algún listado ya la usó, la
    base RECHAZA el borrado (`listados_compra_cargas.carga_id` no va en
    cascada) y quien llama traduce el error: borrarla cambiaría en silencio
    lo que ese listado dice que se salió a comprar.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "DELETE FROM cargas_compra WHERE cliente_id = %s AND fecha = %s",
                (cliente_id, fecha),
            )
            borradas = cursor.rowcount
            conexion.commit()
            return borradas > 0
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def listar_cargas_desde(desde, excepto_listado_id: int | None = None) -> list[dict]:
    """Las cargas de compra con fecha >= `desde`, para elegirlas en el Paso 2.

    DESDE AYER Y NO DESDE HOY, y lo decidió el dueño (22/09): se trabaja de
    noche, así que esconder lo de ayer a medianoche deja al comprador sin lo
    que está comprando en ese momento. El recorte lo elige quien llama.

    `usada_en_otros` Y `ultimo_listado` SON EL AVISO, no una traba: una carga
    que ya se usó se muestra igual y se puede volver a sumar —capaz no se
    llegó a comprar, o se la quiere de plantilla—. El sistema avisa y decide
    el comprador.

    Y SE EXCLUYE EL LISTADO QUE SE ESTÁ EDITANDO, que es lo que hace legible
    el aviso: sin eso, toda carga que se acaba de tildar diría "ya se usó" y
    el cartel pasaría a estar siempre puesto, que es como se aprende a no
    leerlo. El conteo va al lado de la fecha porque una carga puede estar en
    varios y "el del 26/09" sola no lo dice.

    LAS QUE ESE LISTADO YA TIENE ENTRAN AUNQUE SEAN MÁS VIEJAS que `desde`.
    La pantalla guarda lo que viene tildado en el formulario, así que una
    carga del listado que no se dibuja se DESTILDA sola al primer Guardar,
    sin que el comprador la haya tocado. Con `excepto_listado_id` en None el
    `IN` no encuentra nada y la lista es la de siempre.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.cliente_id, cl.nombre AS cliente_nombre, c.fecha,
                       c.modo, c.promedio_anterior_a, c.margen_porcentaje,
                       (SELECT count(*) FROM cargas_compra_renglones r
                         WHERE r.carga_id = c.id) AS renglones,
                       (SELECT count(*) FROM listados_compra_cargas lc
                         WHERE lc.carga_id = c.id
                           AND lc.listado_id IS DISTINCT FROM %s) AS usada_en_otros,
                       (SELECT max(l.fecha) FROM listados_compra_cargas lc
                          JOIN listados_compra l ON l.id = lc.listado_id
                         WHERE lc.carga_id = c.id
                           AND lc.listado_id IS DISTINCT FROM %s) AS ultimo_listado
                FROM cargas_compra c
                JOIN clientes cl ON cl.id = c.cliente_id
                WHERE c.fecha >= %s
                   OR c.id IN (SELECT lc.carga_id FROM listados_compra_cargas lc
                                WHERE lc.listado_id = %s)
                ORDER BY c.fecha, cl.nombre
                """,
                (excepto_listado_id, excepto_listado_id, desde, excepto_listado_id),
            )
            columnas = [c[0] for c in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_pedidos_vigentes_con_armado(cliente_id: int, fecha_desde) -> list[dict]:
    """Los pedidos VIVOS de un cliente desde una fecha (pasados recientes y TODOS los futuros), con su estado de armado.

    Una fila por fecha (el vigente: el más nuevo sin anular), con lo justo
    para verlos de un vistazo sin entrar a cada uno: renglones
    identificados, cuántos están armados, cuántos quedaron sin identificar y
    cuántos se armaron CORTOS — "Pedido del 22/08 — 18 de 32 armados".

    Los cortos son la cuarta cuenta y entraron el 02/09: "18 de 32" mira
    renglones TILDADOS, y un renglón tildado con "armé 12 de 15" cuenta como
    armado. Sin este número, un pedido con diez renglones cortos decía
    "32 de 32" en verde y con un tilde — le decía al que mira que no hay
    nada que hacer.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (p.fecha_operacion)
                       p.id, p.fecha_operacion, p.origen, p.creado_en, p.armado_cerrado_el,
                       -- Solo renglones ARMABLES (con sucursal): un renglón
                       -- identificado sin sucursal vino sin cantidades en el
                       -- mail y no se arma jamás — contarlo dejaría el pedido
                       -- "62 de 72" para siempre (mismo criterio que el botón
                       -- Terminar y los conteos por sucursal de Armar).
                       (SELECT COUNT(*) FROM pedidos_renglones r
                        WHERE r.pedido_id = p.id AND r.articulo_id IS NOT NULL
                          AND r.anulado_el IS NULL AND r.sucursal IS NOT NULL) AS renglones_totales,
                       (SELECT COUNT(*) FROM pedidos_renglones r
                        WHERE r.pedido_id = p.id AND r.articulo_id IS NOT NULL
                          AND r.anulado_el IS NULL AND r.sucursal IS NOT NULL
                          AND r.armado_el IS NOT NULL) AS renglones_armados,
                       (SELECT COUNT(*) FROM pedidos_renglones r
                        WHERE r.pedido_id = p.id AND r.articulo_id IS NULL) AS sin_identificar,
                       -- Armados con MENOS bultos de los pedidos. El "<" y no
                       -- "<>": armar de más no es incompleto. Mismo criterio
                       -- que contar_pedidos_incompletos, para que la tarjeta y
                       -- la alerta no puedan decir cosas distintas.
                       (SELECT COUNT(*) FROM pedidos_renglones r
                        WHERE r.pedido_id = p.id AND r.articulo_id IS NOT NULL
                          AND r.anulado_el IS NULL AND r.sucursal IS NOT NULL
                          AND r.armado_el IS NOT NULL AND r.cantidad_armada IS NOT NULL
                          AND r.cantidad_armada < r.cantidad) AS renglones_cortos
                FROM pedidos p
                WHERE p.cliente_id = %s AND p.anulado_el IS NULL AND p.fecha_operacion >= %s
                ORDER BY p.fecha_operacion, p.creado_en DESC
                """,
                (cliente_id, fecha_desde),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def obtener_condiciones_pedido(cliente_id: int) -> dict | None:
    """Las condiciones de pedido de un cliente, o None si nunca se configuraron (= esporádico)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT cliente_id, dias_esperados FROM clientes_condiciones_pedido WHERE cliente_id = %s",
                (cliente_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def guardar_condiciones_pedido(cliente_id: int, dias_esperados: str | None) -> None:
    """Guarda los días esperados de pedido del cliente (None = esporádico: sin alerta de faltantes)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO clientes_condiciones_pedido (cliente_id, dias_esperados)
                VALUES (%s, %s)
                ON CONFLICT (cliente_id)
                DO UPDATE SET dias_esperados = EXCLUDED.dias_esperados, actualizado_en = now()
                """,
                (cliente_id, dias_esperados),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_condiciones_pedido() -> list[dict]:
    """Los clientes CON días esperados configurados (los esporádicos no aparecen: sin alerta)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT cc.cliente_id, cc.dias_esperados, c.nombre AS cliente_nombre
                FROM clientes_condiciones_pedido cc
                JOIN clientes c ON c.id = cc.cliente_id
                WHERE cc.dias_esperados IS NOT NULL AND c.activo
                ORDER BY c.nombre
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_fechas_con_pedido_vigente(cliente_id: int, fecha_desde) -> list:
    """Las fechas (desde fecha_desde) que tienen pedido VIVO para el cliente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT fecha_operacion FROM pedidos
                WHERE cliente_id = %s AND anulado_el IS NULL AND fecha_operacion >= %s
                """,
                (cliente_id, fecha_desde),
            )
            return [fila[0] for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_renglones_pedidos_vigentes(cliente_id: int, fecha_desde, fecha_hasta) -> list[dict]:
    """Los renglones de los pedidos VIGENTES del rango, sumados por fecha y artículo — la base de Rentabilidad.

    "Vigente" por fecha = el pedido más nuevo sin anular (los anulados por
    reemplazo no cuentan: contarían la demanda dos veces). Los renglones
    sin identificar (articulo_id NULL) vienen agrupados por fecha con
    nombre y grupo NULL: se reportan aparte, nunca se descartan en
    silencio. Suma sobre TODAS las sucursales: la rentabilidad es del
    artículo, no de la sucursal.

    SE FILTRAN LOS DOS anulado_el, Y HACEN FALTA LOS DOS. El de `pedidos`
    saca el pedido reemplazado; el de `pedidos_renglones` saca la CRUZ del
    armado (ver anular_renglon_pedido): ese renglón no se armó y no salió
    del galpón. Hasta el 07/09 solo estaba el primero, y era el único
    lector de pedidos_renglones que no filtraba el segundo — los otros
    dieciséis sí, incluidas las tres consultas que derivan las salidas de
    stock.

    Lo que eso rompía no era el total: era la COMPARATIVA de
    /gerencia/rentabilidad-real. La real sale de los movimientos de stock,
    que sí excluyen el anulado; la teórica salía de acá, que no. El renglón
    anulado aparecía de un lado y no del otro, y la diferencia —que esa
    pantalla promete que es "exactamente la lista de cosas a explicar
    (merma, reproceso, kilajes), nunca ruido de cuentas distintas"— se lo
    comía como si fuera merma.

    Ojo al leer histórico: anular un renglón viejo cambia la teórica de ese
    día. Ya pasaba antes al revés (anularlo lo SUMABA, porque `cantidad` no
    se limpia al anular; `kilos_enviados` y el tilde sí).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                WITH vigentes AS (
                    SELECT DISTINCT ON (fecha_operacion) id, fecha_operacion
                    FROM pedidos
                    WHERE cliente_id = %s AND anulado_el IS NULL
                      AND fecha_operacion >= %s AND fecha_operacion <= %s
                    ORDER BY fecha_operacion, creado_en DESC
                )
                SELECT v.fecha_operacion, r.ficha_id, r.articulo_id,
                       a.nombre AS articulo_nombre, a.grupo AS articulo_grupo,
                       SUM(r.cantidad) AS bultos
                FROM vigentes v
                JOIN pedidos_renglones r ON r.pedido_id = v.id AND r.anulado_el IS NULL
                LEFT JOIN articulos a ON a.id = r.articulo_id
                GROUP BY v.fecha_operacion, r.ficha_id, r.articulo_id, a.nombre, a.grupo
                ORDER BY v.fecha_operacion, a.nombre
                """,
                (cliente_id, fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_dias_sin_pedido(cliente_id: int, fecha_desde) -> list[dict]:
    """Las marcas "no hubo pedido" del cliente desde una fecha."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, fecha, motivo, registrado_en FROM dias_sin_pedido
                WHERE cliente_id = %s AND fecha >= %s
                ORDER BY fecha
                """,
                (cliente_id, fecha_desde),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def marcar_dia_sin_pedido(cliente_id: int, fecha, motivo: str | None = None) -> None:
    """Cierra un día esperado sin pedido (feriado, el cliente no pidió): la alerta lo deja de contar."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO dias_sin_pedido (cliente_id, fecha, motivo)
                VALUES (%s, %s, %s)
                ON CONFLICT (cliente_id, fecha) DO NOTHING
                """,
                (cliente_id, fecha, motivo),
            )
        conexion.commit()
    finally:
        conexion.close()


def borrar_dia_sin_pedido(cliente_id: int, fecha) -> None:
    """Deshace la marca "no hubo pedido". Es una marca administrativa, no un registro operativo:
    el borrado físico es la excepción acordada a la regla de bajas lógicas."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "DELETE FROM dias_sin_pedido WHERE cliente_id = %s AND fecha = %s",
                (cliente_id, fecha),
            )
        conexion.commit()
    finally:
        conexion.close()


def obtener_mail_de_pedido(pedido_id: int) -> dict | None:
    """El mail del que salió un pedido (si vino de la casilla), para mostrar cómo se confirmó."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, remitente, asunto, recibido_el, motivo, procesado_el
                FROM mails_pedido WHERE pedido_id = %s
                """,
                (pedido_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


# --- La fecha de corte del modelo nuevo ---


def _fecha_corte(cursor):
    """La fecha de corte con un cursor YA abierto, para usarla dentro de una transacción.

    La consulta está escrita acá y en ningún otro lado: `fecha_corte()`
    es esta misma con conexión propia. El piso de fecha del reproceso la
    necesita adentro de la transacción que ya tiene abierta, y abrir una
    segunda conexión para leer una fila sería pagar dos veces por el
    mismo dato — pero copiar el SELECT sería peor: serían dos reglas.
    """
    cursor.execute("SELECT fecha FROM corte_modelo WHERE id = 1")
    fila = cursor.fetchone()
    if fila is None:
        raise RuntimeError(
            "No hay fecha de corte cargada (corte_modelo está vacía): "
            "la base quedó a medio configurar."
        )
    return fila[0]


def fecha_corte():
    """La fecha desde la que rige el modelo nuevo (una sola fila en corte_modelo).

    Vive en la base y no en el código para que se lea de UN lugar: la
    usan el stock inicial, las guías R sin ficha (antes del corte un NULL
    es dato viejo, después es "sin asignar"), el piso de fecha del
    reproceso y todo lo que venga.

    **Se lee, nunca se escribe a mano en el código.** El día que se haga
    un corte nuevo se cambia esa fila y todo lo que la lee la sigue sola.
    Una constante `31/08` suelta quedaría mintiendo el lunes siguiente.

    Si la fila no está, revienta a propósito: una base a medio configurar
    tiene que avisar, no elegir una fecha por su cuenta y costear contra
    lotes que no corresponden.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return _fecha_corte(cursor)
    finally:
        conexion.close()


# --- Stock del Depósito ---
# El stock por artículo NUNCA se guarda: se calcula siempre, derivado de
# compras recepcionadas (entradas), renglones armados de pedidos vigentes
# (salidas) y movimientos_stock (ajustes, mermas, reingresos por rechazo).
# Todo en BULTOS. Puede quedar negativo a propósito: el armado no se traba
# por stock — el negativo es la señal de que falta un reproceso o un ajuste.

# LA FECHA TOPE viaja como CTE y no como un %s por cada pata: son seis sumas y
# tres más en el pool de segunda, y nueve parámetros posicionales en fila se
# desordenan el día que alguien agrega una. Así entra UNA sola vez, primera, y
# el resto de la consulta la lee por nombre — el mismo molde que `corte`.
#
# QUÉ FECHA MIRA CADA PATA, que no es la misma columna en todas:
#
# - Las COMPRAS entran al stock cuando el depósito las RECEPCIONA, no cuando
#   se compraron: `procesada_el`. Es la misma expresión con la que el FIFO
#   ordena sus lotes de compra, y tiene que serlo — si acá dijera
#   `fecha_operacion`, el total del artículo y el reparto por lote no
#   coincidirían en los días entre la compra y la recepción. Las viejas, de
#   antes de que existiera Recepción, tienen `procesada_el` en NULL y caen a
#   `fecha_operacion`: sin ese COALESCE desaparecerían de toda consulta con
#   fecha, incluida la de hoy.
# - Las SALIDAS de pedidos, por `armado_el` pasado a fecha argentina: el
#   renglón sale del stock cuando se arma.
# - El resto —movimientos, reprocesos, remitos— por su `fecha_operacion`, que
#   es la fecha declarada de la operación y es la que el módulo usa en todos
#   lados.
#
# LO QUE **NO** SE RETROCEDE, y es una decisión: `anulado_el IS NULL` y el
# `DISTINCT ON` de los pedidos vigentes se evalúan HOY, no a la fecha pedida.
# O sea que esto muestra "lo que hoy sabemos que había el día X", no "lo que el
# sistema creía el día X". Una anulación es una corrección —dice que eso nunca
# tendría que haber contado—, y una consulta histórica que resucitara pedidos
# ya corregidos mostraría números que nadie quiere de vuelta.
# NULL = hoy, para el que quiere el estado actual y no una fecha. Así hay UN
# solo camino: la consulta de hoy es la misma que la del 3 de septiembre con
# otra fecha, y no una segunda versión sin tope que se pueda ir separando.
_SQL_TOPE = """SELECT COALESCE(%s::date,
        (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date) AS fecha"""

_SQL_SUMAS_STOCK = """
    WITH tope AS (""" + _SQL_TOPE + """),
    entradas AS (
        SELECT c.articulo_id, SUM(c.cantidad_cajones_real) AS total
        FROM compras c, tope
        WHERE c.estado = 'recepcionado'
          AND COALESCE((c.procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date,
                       c.fecha_operacion) <= tope.fecha
          {filtro_c_articulo}
        GROUP BY c.articulo_id
    ), vigentes AS (
        SELECT DISTINCT ON (cliente_id, fecha_operacion) id
        FROM pedidos WHERE anulado_el IS NULL
        ORDER BY cliente_id, fecha_operacion, creado_en DESC
    ), salidas AS (
        SELECT r.articulo_id, SUM(COALESCE(r.cantidad_armada, r.cantidad)) AS total
        FROM pedidos_renglones r JOIN vigentes v ON v.id = r.pedido_id, tope
        WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL
          AND r.articulo_id IS NOT NULL
          AND (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date <= tope.fecha
          {filtro_r_articulo}
        GROUP BY r.articulo_id
    ), reingresos AS (
        -- Solo los que QUEDAN en stock: un rechazo mandado a segunda (o
        -- pasado de vuelta a cajón grande) sale del stock normal y suma
        -- al pool de segunda. NULL = los reingresos viejos, que quedaban
        -- en stock por definición.
        SELECT articulo_id, SUM(cantidad) AS total
        FROM movimientos_stock, tope
        WHERE anulado_el IS NULL AND tipo = 'reingreso_rechazo'
          AND fecha_operacion <= tope.fecha
          AND (destino_rechazo IS NULL OR destino_rechazo = 'stock') {filtro_articulo}
        GROUP BY articulo_id
    ), ajustes AS (
        SELECT articulo_id, SUM(cantidad) AS total
        FROM movimientos_stock, tope
        WHERE anulado_el IS NULL AND tipo <> 'reingreso_rechazo'
          AND fecha_operacion <= tope.fecha {filtro_articulo}
        GROUP BY articulo_id
    ), reproc AS (
        SELECT articulo_id, SUM(bultos_primera) AS entradas, SUM(bultos_tomados) AS salidas
        FROM reprocesos, tope
        WHERE anulado_el IS NULL AND fecha_operacion <= tope.fecha {filtro_articulo}
        GROUP BY articulo_id
    )
"""


def _sql_sumas_stock(por_articulo: bool) -> str:
    """La consulta de las seis patas. El primer parámetro es SIEMPRE la fecha tope."""
    filtro = "AND articulo_id = %s" if por_articulo else ""
    return _SQL_SUMAS_STOCK.format(
        filtro_articulo=filtro,
        filtro_c_articulo="AND c.articulo_id = %s" if por_articulo else "",
        filtro_r_articulo="AND r.articulo_id = %s" if por_articulo else "",
    )


# EL POOL DE SEGUNDA, escrito UNA sola vez. Lo usan la cuenta de todos los
# artículos (`stock_deposito_por_articulo`, que dibuja el Remanente) y la de
# UNO (`_segunda_de_articulo`, que congela el `stock_sistema` de un conteo de
# segunda y le da el número al Cotejo cuando el pool no está en las
# porciones). Con la cuenta escrita dos veces, el conteo se congelaría contra
# un número y el Cotejo lo compararía contra otro — que es el bug del 08/09
# con `stock_deposito_de_articulo` y los sueltos, servido de nuevo.
#
# Pide un CTE `tope` ya definido arriba (la fecha techo).
_SQL_POOL_SEGUNDA = """
                , corte_seg AS (SELECT fecha FROM corte_modelo WHERE id = 1)
                , segunda AS (
                    SELECT articulo_id, SUM(bultos_segunda) AS total
                    FROM reprocesos, corte_seg, tope
                    WHERE anulado_el IS NULL AND fecha_operacion <= tope.fecha
                      AND (fecha_operacion > corte_seg.fecha
                           OR (tipo = 'inicial' AND fecha_operacion >= corte_seg.fecha))
                      {filtro_articulo}
                    GROUP BY articulo_id
                ), segunda_rechazo AS (
                    -- Los rechazos que no volvieron al stock: entran al
                    -- mismo pool que la segunda de los reprocesos.
                    SELECT articulo_id, SUM(bultos_segunda) AS total
                    FROM movimientos_stock, corte_seg, tope
                    WHERE anulado_el IS NULL AND destino_rechazo IN ('segunda', 'reproceso')
                      AND fecha_operacion > corte_seg.fecha
                      AND fecha_operacion <= tope.fecha
                      {filtro_articulo}
                    GROUP BY articulo_id
                ), segunda_pase AS (
                    -- LO QUE EL DEPOSITO PASO DE PRIMERA A SEGUNDA. Pata
                    -- PROPIA y no metida adentro de `segunda_rechazo`: esa
                    -- se llama asi porque cuenta rechazos, y un pase no lo
                    -- es. El nombre lleva el alcance (corolario 8).
                    --
                    -- Y con el MISMO recorte del corte que las otras dos: la
                    -- foto del stock inicial se toma a la tarde, asi que ya
                    -- viene neta del trabajo de ese dia. Con `>=` el dia del
                    -- corte se contaria dos veces (corolario 12).
                    SELECT articulo_id, SUM(bultos_segunda) AS total
                    FROM movimientos_stock, corte_seg, tope
                    WHERE anulado_el IS NULL AND tipo = 'pase_a_segunda'
                      AND fecha_operacion > corte_seg.fecha
                      AND fecha_operacion <= tope.fecha
                      {filtro_articulo}
                    GROUP BY articulo_id
                ), remitida AS (
                    SELECT articulo_id, SUM(bultos) AS total
                    FROM remitos_segunda, corte_seg, tope
                    WHERE anulado_el IS NULL AND fecha_operacion > corte_seg.fecha
                      AND fecha_operacion <= tope.fecha
                      {filtro_articulo}
                    GROUP BY articulo_id
                )
"""


def _pool_segunda(producida, de_rechazos, de_pases, remitida) -> float:
    """Lo que HAY en el pool de segunda, sumando las TRES entradas y restando la salida.

    Entra lo PRODUCIDO en un reproceso, lo que volvió RECHAZADO y no fue al
    stock, y lo que el depósito PASÓ de primera a segunda porque ya no daba
    para primera. Sale lo remitido al Puesto.

    La resta va acá y no en cada llamador por lo mismo que el SQL: es una
    sola cuenta, y dos copias se separan.

    `de_pases` ES UN PARÁMETRO POSICIONAL SIN DEFAULT, y no está al final por
    comodidad: con un default, un llamador que se lo olvidara devolvería un
    pool CHICO —le faltaría lo que el depósito pasó— y eso no se descuadra
    contra nada, solo hace que no se pueda remitir mercadería que está.
    """
    return round(float(producida) + float(de_rechazos) + float(de_pases) - float(remitida), 2)


def _segunda_de_articulo(cursor, articulo_id: int, hasta=None) -> float:
    """El pool de segunda de UN artículo al cierre de `hasta`, con el cursor abierto.

    Es la porción "Artículo Segunda" del Remanente, y sale de la MISMA
    consulta y de la MISMA resta que la de todos los artículos. Por eso el
    conteo, el Cotejo y el Remanente comparan el mismo número: si esta cuenta
    cambia, los tres la siguen juntos (mismo criterio que `_stock_de_ficha`).
    """
    cursor.execute(
        """
        WITH tope AS (SELECT COALESCE(%s::date, CURRENT_DATE) AS fecha)
        """
        + _SQL_POOL_SEGUNDA.format(filtro_articulo="AND articulo_id = %s")
        + """
        SELECT COALESCE((SELECT total FROM segunda), 0),
               COALESCE((SELECT total FROM segunda_rechazo), 0),
               COALESCE((SELECT total FROM segunda_pase), 0),
               COALESCE((SELECT total FROM remitida), 0)
        """,
        (hasta, articulo_id, articulo_id, articulo_id, articulo_id),
    )
    return _pool_segunda(*cursor.fetchone())


def stock_deposito_por_articulo(hasta, articulo_id=None) -> list[dict]:
    """El stock del sistema por artículo (bultos) AL CIERRE DE `hasta`, calculado siempre.

    `articulo_id` opcional acota a UNO, y filtra en el SELECT final y no
    adentro de cada CTE. Es a propósito y tiene un costo dicho: las CTE
    siguen agregando todo el catálogo, así que lo que se ahorra es el
    armado de las filas y no el escaneo. Bajar el filtro a las ocho CTE
    (cinco de las sumas más tres del pool de segunda) significa ocho
    parámetros más en un orden posicional, y un orden posicional mal
    escrito no falla: devuelve OTRO artículo. Medido el 10/09, además, el
    costo de esta consulta es por LLAMADA y no por fila —mover el corte de
    38 días a 5 no movió el tiempo—, así que el escaneo no era lo caro.

    El paréntesis del WHERE no es cosmético: sin él, el `AND a.id` se
    ataría solo al último `OR` y la consulta traería medio catálogo.
    

    `hasta` es obligatorio y no tiene default: es la única forma de que
    nadie escriba sin querer una consulta "de hoy" que en realidad suma
    todo. El que quiere hoy pasa hoy, y la pantalla lo dice.

    entradas = compras recepcionadas (cantidad_cajones_real, la cuenta REAL
    de Depósito, ya neta del rechazo al proveedor). salidas = renglones
    armados de pedidos VIGENTES (cantidad_armada si armó menos, sino la
    pedida); los reemplazados y anulados no cuentan. reingresos va aparte
    de los otros movimientos porque el dueño lo quiere ver como número
    propio: es mercadería ya costeada y ya vendida que volvió (plata
    perdida), no stock "normal".

    La columna `segunda` (el pool) arranca en la FECHA DE CORTE desde el
    05/09 — ver el comentario adentro de la consulta. Es el único número de
    acá que se rebasea con una fecha; el resto lo rebasea el compensatorio.

    LA LEEN TRES PANTALLAS y las tres salen de esta misma función: el
    Remanente (sus porciones, sus negativos y los dos totales), Stock por
    Guía (la línea de las seis patas) y el selector de Remito de Segunda
    (que filtra por segunda > 0). Que el cálculo esté acá y no repetido es
    lo que hace que no puedan decir cosas distintas.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                _sql_sumas_stock(por_articulo=False)
                + """
                -- EL PISO DE FECHA DEL POOL DE SEGUNDA. Hasta el 05/09 esta
                -- era la ÚNICA cuenta del módulo que ningún corte rebaseaba:
                -- el total del artículo lo rebasea el compensatorio, la
                -- cuenta por ficha su propio piso, el FIFO se recalcula
                -- entero, y la segunda sumaba desde el primer día de la base.
                -- El compensatorio no la alcanza: es una fila de
                -- movimientos_stock y esto casi no lee movimientos.
                --
                -- Medido la noche del corte: ~40 bultos de cola vieja en
                -- cinco artículos, y en Zapallito sumándose a lo contado (23
                -- donde había 15). Ver "el pool de segunda es la única cuenta
                -- que ningún corte rebasea" en docs/diseno_base_datos.md.
                --
                -- Asimétrico igual que la cuenta por ficha, y por lo mismo:
                -- el conteo físico se toma A LA TARDE del día del corte, así
                -- que todo lo del día ya está adentro de lo contado. Entran
                -- los 'inicial' DEL corte (la foto) más lo POSTERIOR; los
                -- remitos y los rechazos, solo lo posterior.
                --
                -- El pool tiene PISO (el corte) y TECHO (la fecha pedida):
                -- el piso lo rebasea y el techo lo corta. Los dos son sobre
                -- `fecha_operacion`, así que se leen juntos.
                """
                + _SQL_POOL_SEGUNDA.format(filtro_articulo="")
                + """
                SELECT a.id AS articulo_id, a.nombre, a.grupo,
                       COALESCE(e.total, 0) AS entradas,
                       COALESCE(s.total, 0) AS salidas,
                       COALESCE(r.total, 0) AS reingresos,
                       COALESCE(aj.total, 0) AS ajustes,
                       COALESCE(rp.entradas, 0) AS reproceso_primera,
                       COALESCE(rp.salidas, 0) AS reproceso_tomados,
                       COALESCE(sg.total, 0) AS segunda_producida,
                       COALESCE(sr.total, 0) AS segunda_de_rechazos,
                       COALESCE(sp.total, 0) AS segunda_de_pases,
                       COALESCE(rm.total, 0) AS segunda_remitida
                FROM articulos a
                LEFT JOIN entradas e ON e.articulo_id = a.id
                LEFT JOIN salidas s ON s.articulo_id = a.id
                LEFT JOIN reingresos r ON r.articulo_id = a.id
                LEFT JOIN ajustes aj ON aj.articulo_id = a.id
                LEFT JOIN reproc rp ON rp.articulo_id = a.id
                LEFT JOIN segunda sg ON sg.articulo_id = a.id
                LEFT JOIN segunda_rechazo sr ON sr.articulo_id = a.id
                LEFT JOIN segunda_pase sp ON sp.articulo_id = a.id
                LEFT JOIN remitida rm ON rm.articulo_id = a.id
                -- `sp` VA EN EL FILTRO aunque hoy sea redundante: un pase
                -- resta del stock por la pata de `ajustes` (que es
                -- `tipo <> 'reingreso_rechazo'`), así que el artículo ya
                -- aparecería por ahí. Pero eso es un acuerdo tácito entre
                -- dos patas, y el día que alguien filtre `ajustes` por tipo,
                -- un artículo cuyo único movimiento sea un pase desaparece
                -- de la consulta ENTERA — la resta quedaría bien escrita y
                -- no se haría nunca (corolario 35).
                WHERE (e.total IS NOT NULL OR s.total IS NOT NULL
                   OR r.total IS NOT NULL OR aj.total IS NOT NULL
                   OR rp.articulo_id IS NOT NULL OR sr.articulo_id IS NOT NULL
                   OR sp.articulo_id IS NOT NULL)
                  {filtro_articulo_final}
                ORDER BY a.nombre
                """.format(
                    filtro_articulo_final="AND a.id = %s" if articulo_id else ""
                ),
                (hasta,) + ((articulo_id,) if articulo_id else ()),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        for fila in filas:
            fila["stock"] = (
                float(fila["entradas"]) + float(fila["reingresos"]) + float(fila["ajustes"])
                + float(fila["reproceso_primera"]) - float(fila["reproceso_tomados"]) - float(fila["salidas"])
            )
            # La SEGUNDA es un pool aparte: no es vendible por pedidos y no
            # infla el stock normal — lo que se produjo (en reprocesos y en
            # rechazos que no volvieron al stock) menos lo remitido.
            fila["segunda"] = _pool_segunda(
                fila["segunda_producida"], fila["segunda_de_rechazos"],
                fila["segunda_de_pases"], fila["segunda_remitida"],
            )
        return filas
    finally:
        conexion.close()


def _stock_deposito_actual(cursor, articulo_id: int) -> float:
    """El stock actual de UN artículo, con el cursor abierto — para la foto (stock_sistema) de un movimiento nuevo.

    Sin fecha tope (None = hoy): la foto es del momento en que se carga el
    movimiento, que es de lo que se trata.
    """
    cursor.execute(
        _sql_sumas_stock(por_articulo=True)
        + """
        SELECT COALESCE((SELECT total FROM entradas), 0)
             + COALESCE((SELECT total FROM reingresos), 0)
             + COALESCE((SELECT total FROM ajustes), 0)
             + COALESCE((SELECT entradas FROM reproc), 0)
             - COALESCE((SELECT salidas FROM reproc), 0)
             - COALESCE((SELECT total FROM salidas), 0)
        """,
        (None, articulo_id, articulo_id, articulo_id, articulo_id, articulo_id),
    )
    return float(cursor.fetchone()[0])


def stock_deposito_de_articulo(articulo_id: int) -> float:
    """El TOTAL actual de un artículo: sus sueltos MÁS las cajas de todas sus fichas.

    NO es lo que muestra el Cotejo. El Cotejo lista PORCIONES, y la de los
    sueltos vale `total − cajas`. Confundir las dos costó caro el 08/09: la
    precarga del ajuste comparaba los sueltos contados contra este total y
    proponía borrar tantos bultos como cajas armadas tuviera el artículo (un
    limón con 5 sueltos y 30 cajas daba una precarga de −30 contando los 5
    exactos). Para una porción va `stock_de_porcion`.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return _stock_deposito_actual(cursor, articulo_id)
    finally:
        conexion.close()


def stock_de_porcion(articulo_id: int, ficha_id: int | None = None,
                     es_segunda: bool = False) -> float:
    """El stock actual de UNA porción: los sueltos, las cajas de una ficha, o la segunda.

    Es `_stock_de_ficha` con conexión propia — la MISMA función que congela
    el `stock_sistema` de cada conteo y que arma el Remanente. Por eso el
    Cotejo, el conteo y la precarga del ajuste comparan todos el mismo
    número: si esta cuenta cambia, los tres la siguen juntos.

    `ficha_id` None son los bultos SUELTOS, que es el caso del ajuste: un
    ajuste de stock es por artículo y el Cotejo solo ofrece el botón en esos
    renglones (ver `ver_cotejo_stock`). Como el movimiento suma al total y
    las cajas no se tocan, mover el total en `contado − sueltos` deja los
    sueltos exactamente en lo contado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if es_segunda:
                return _segunda_de_articulo(cursor, articulo_id)
            return _stock_de_ficha(cursor, articulo_id, ficha_id)
    finally:
        conexion.close()



def crear_movimiento_stock(
    articulo_id: int,
    tipo: str,
    cantidad: float,
    motivo: str,
    fecha_operacion,
    cliente_id: int | None = None,
    pedido_renglon_id: int | None = None,
    costo_por_bulto: float | None = None,
    destino_rechazo: str | None = None,
    bultos_segunda: float | None = None,
    lote_tipo: str | None = None,
    lote_origen_id: int | None = None,
    foto_ruta: str | None = None,
    ficha_id: int | None = None,
    proveedor_devolucion_id: int | None = None,
    compra_devolucion_id: int | None = None,
) -> float:
    """Un movimiento de stock (ajuste/merma/reingreso): fila nueva, NUNCA pisa el stock. Devuelve el stock resultante.

    Guarda la foto del sistema del momento (stock_sistema, SIN este
    movimiento) — igual que ajustes_vacios: sin ese rastro, cualquier
    faltante se taparía con un ajuste y se acaba el control cruzado.
    fecha_operacion es la fecha REAL del hecho (un reingreso puede
    cargarse al día siguiente de que volvió el camión).

    Un reingreso VINCULADO lleva además el renglón de pedido que se
    devolvió y el costo por bulto congelado del listado anclado a la
    fecha del pedido de origen (lo calcula el server, jamás la pantalla),
    y el DESTINO elegido al cargarlo: queda en stock, va a segunda tal
    cual, o vuelve a cajón grande y esos cajones (bultos_segunda) van al
    pool de segunda.

    Una merma puede venir DIRIGIDA a un lote (lote_tipo + lote_origen_id):
    el operario sabe cuál se pudrió y esa merma sale de ese lote, no del
    más viejo. Sin lote, todo sigue como siempre.

    Y `ficha_id` dice de QUÉ PORCIÓN salió: None son los bultos sueltos (el
    caso común) y con ficha son cajas ya armadas de ese cliente. Hasta el
    10/09 no existía, y sin él mermar cajas armadas bajaba el total del
    artículo sin bajar la ficha: como los sueltos se derivan por resta, la
    baja caía entera sobre los sueltos y las dos porciones quedaban dadas
    vuelta. La base lo limita a las mermas con
    `movimientos_stock_ficha_solo_merma` —un reingreso ya llega a su ficha
    por el renglón, y dos caminos al mismo dato es la regla escrita dos
    veces— y a las fichas DEL ARTÍCULO con la FK compuesta
    `movimientos_stock_ficha_del_articulo`.

    `foto_ruta` (la foto de lo que se tiró, ya subida al Storage) entra en
    LA MISMA TRANSACCIÓN que el movimiento, y eso es lo que importa: una
    merma guardada y su foto perdida porque el segundo commit falló sería
    exactamente el agujero que la foto viene a tapar. O quedan las dos o no
    queda ninguna.

    El archivo se sube ANTES, así que un fallo del INSERT deja un huérfano
    en el bucket. Es el mismo trato que la foto de balanza, y lo barre la
    limpieza de 3 años.

    `compra_devolucion_id` es DE QUÉ COMPRA salió lo que se le devolvió al
    proveedor, elegido por la persona entre las que el FIFO dice que
    alimentaron el renglón. Es lo que el reclamo necesita —"de la compra del
    martes te devolví 8"— y por eso se GUARDA en vez de recalcularse: el FIFO
    se rejuega en cada lectura y puede cambiar mañana; la compra elegida no.
    Va SIEMPRE a una sola compra, sin reparto: nadie miró qué caja venía de
    qué cajón, y repartir sería inventarlo. Los dos vínculos son excluyentes
    (`movimientos_stock_compra_o_proveedor`): con compra, el proveedor sale
    de ella y mandarlo aparte sería la misma cosa escrita dos veces.

    NO HAY COLUMNA DE ENVASE, y es la decisión del 17/09: un rechazo que
    vuelve a cajón grande NO libera la caja. Se tira — la fruta pasa al
    cajón y la caja de Día se descarta—, así que no hay nada que devolverle
    al stock de cajas. `movimientos_stock.envase_id` y su `lleva_caja_nuestra`
    existieron dos días sobre la premisa contraria y se sacaron con su
    migración (db/envases_9_*.sql): un camino que nunca se va a recorrer es
    peor que no tenerlo, porque el próximo que lo lea va a creer que falta
    cablearlo.

    La caja de ese rechazo ya está contada, y como PÉRDIDA: se descontó del
    stock el día que la guía R la armó, y `rechazos_perdidos` le carga el
    envase junto con la mercadería. Ver core/envases.py, que tiene el modelo
    entero escrito arriba.

    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            stock_sistema = _stock_deposito_actual(cursor, articulo_id)
            cursor.execute(
                """
                INSERT INTO movimientos_stock
                    (articulo_id, tipo, cantidad, motivo, cliente_id, fecha_operacion, stock_sistema,
                     pedido_renglon_id, costo_por_bulto, destino_rechazo, bultos_segunda,
                     lote_tipo, lote_origen_id, ficha_id, proveedor_devolucion_id, compra_devolucion_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (articulo_id, tipo, cantidad, motivo, cliente_id, fecha_operacion, stock_sistema,
                 pedido_renglon_id, costo_por_bulto, destino_rechazo, bultos_segunda,
                 lote_tipo, lote_origen_id, ficha_id, proveedor_devolucion_id, compra_devolucion_id),
            )
            if foto_ruta:
                # RETURNING y no currval(pg_get_serial_sequence(...)): el
                # segundo también anda, pero se apoya en cómo se llama la
                # secuencia y no se puede leer de un vistazo.
                (movimiento_id,) = cursor.fetchone()
                cursor.execute(
                    "INSERT INTO fotos_merma (movimiento_id, foto_ruta) VALUES (%s, %s)",
                    (movimiento_id, foto_ruta),
                )
        conexion.commit()
        # Un rechazo que se va a segunda no toca el stock normal: entró y
        # salió en el mismo acto.
        if destino_rechazo in ("segunda", "reproceso"):
            return stock_sistema
        return stock_sistema + float(cantidad)
    finally:
        conexion.close()


def crear_stock_inicial(articulo_id: int, cantidad: float, costo_por_bulto: float, fecha_operacion) -> float:
    """Los bultos SIN PROCESAR que había en el piso el día del corte, con su costo. Devuelve el stock resultante.

    Es un movimiento de stock como cualquier otro, pero con TIPO PROPIO
    en vez de entrar como 'ajuste': los saldos iniciales de Vacíos se
    cargaron por la pantalla de Ajustes y hoy son indistinguibles de una
    corrección de faltante — cualquier reporte de mermas los suma como
    perdidos. Acá se separa desde el día uno, que es cuando sale gratis.

    El costo es OBLIGATORIO y por eso no tiene default: sin él, el lote
    entra al FIFO sin precio y todo lo que salga de él queda sin costear.
    Es lo único que este stock no puede recuperar después — no hay compra
    a la que ir a buscarle el importe.
    """
    if cantidad <= 0:
        raise ValueError("El stock inicial son bultos que están en el piso: tiene que ser mayor a cero.")
    if costo_por_bulto is None or costo_por_bulto < 0:
        raise ValueError("El stock inicial necesita un costo por bulto de cero o más.")
    return crear_movimiento_stock(
        articulo_id,
        "stock_inicial",
        cantidad,
        f"Stock inicial del corte ({fecha_operacion})",
        fecha_operacion,
        costo_por_bulto=costo_por_bulto,
    )


# El acumulado "ya devuelto" por renglón (solo reingresos no anulados):
# el tope duro del server es armado − este número.
_SQL_DEVUELTO_POR_RENGLON = """
    SELECT pedido_renglon_id, SUM(cantidad) AS devuelto
    FROM movimientos_stock
    WHERE pedido_renglon_id IS NOT NULL AND anulado_el IS NULL
    GROUP BY pedido_renglon_id
"""


def listar_pedidos_para_reingreso(oc: str | None = None, limite: int = 30) -> list[dict]:
    """Los (pedido VIGENTE, sucursal) con renglones ARMADOS, del más nuevo al más viejo: el origen a elegir de un reingreso.

    Pantalla de OPERARIO: solo datos operativos que él ya maneja en Armar
    Pedido (fecha, cliente, sucursal, OC, cuántos renglones armó) — nada
    de costos ni de stock del sistema. Con ``oc`` busca por número de
    orden de compra exacto.
    """
    filtro_oc = "AND ps.orden_compra = %s" if oc else ""
    parametros: list = [oc] if oc else []
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                WITH vigentes AS (
                    SELECT DISTINCT ON (cliente_id, fecha_operacion) id
                    FROM pedidos WHERE anulado_el IS NULL
                    ORDER BY cliente_id, fecha_operacion, creado_en DESC
                )
                SELECT p.id AS pedido_id, p.fecha_operacion, cl.nombre AS cliente_nombre,
                       r.sucursal, ps.orden_compra,
                       COUNT(*) AS renglones_armados
                FROM pedidos_renglones r
                JOIN vigentes v ON v.id = r.pedido_id
                JOIN pedidos p ON p.id = r.pedido_id
                JOIN clientes cl ON cl.id = p.cliente_id
                LEFT JOIN pedidos_sucursales ps ON ps.pedido_id = p.id AND ps.sucursal = r.sucursal
                WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL
                  AND r.articulo_id IS NOT NULL AND r.sucursal IS NOT NULL
                  {filtro_oc}
                GROUP BY p.id, p.fecha_operacion, cl.nombre, r.sucursal, ps.orden_compra
                ORDER BY p.fecha_operacion DESC, cl.nombre, r.sucursal
                LIMIT %s
                """,
                (*parametros, limite),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_renglones_para_reingreso(pedido_id: int, sucursal: str) -> list[dict]:
    """Los renglones ARMADOS de esa sucursal del pedido, con lo ya devuelto acumulado (el tope es armado − devuelto)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT r.id, a.nombre AS articulo_nombre,
                       COALESCE(r.cantidad_armada, r.cantidad) AS bultos_armados,
                       COALESCE(d.devuelto, 0) AS ya_devuelto
                FROM pedidos_renglones r
                JOIN articulos a ON a.id = r.articulo_id
                LEFT JOIN ({_SQL_DEVUELTO_POR_RENGLON}) d ON d.pedido_renglon_id = r.id
                WHERE r.pedido_id = %s AND r.sucursal = %s
                  AND r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id IS NOT NULL
                ORDER BY a.nombre
                """,
                (pedido_id, sucursal),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def obtener_renglon_para_reingreso(renglon_id: int) -> dict | None:
    """El renglón ARMADO con todo lo que el reingreso necesita: pedido, cliente, artículo, OC, kilos y lo ya devuelto.

    Solo de pedidos VIGENTES: un pedido anulado o reemplazado no aportó su
    armado al stock, así que no se le puede devolver nada. El cliente y el
    artículo salen de acá — la pantalla no los pide nunca.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                WITH vigentes AS (
                    SELECT DISTINCT ON (cliente_id, fecha_operacion) id
                    FROM pedidos WHERE anulado_el IS NULL
                    ORDER BY cliente_id, fecha_operacion, creado_en DESC
                )
                SELECT r.id, r.pedido_id, r.sucursal, r.articulo_id, r.ficha_id,
                       a.nombre AS articulo_nombre,
                       p.cliente_id, cl.nombre AS cliente_nombre,
                       p.fecha_operacion AS fecha_pedido,
                       ps.orden_compra,
                       COALESCE(r.cantidad_armada, r.cantidad) AS bultos_armados,
                       r.kilos_enviados,
                       COALESCE(d.devuelto, 0) AS ya_devuelto
                FROM pedidos_renglones r
                JOIN vigentes v ON v.id = r.pedido_id
                JOIN pedidos p ON p.id = r.pedido_id
                JOIN clientes cl ON cl.id = p.cliente_id
                JOIN articulos a ON a.id = r.articulo_id
                LEFT JOIN fichas_logistica fl ON fl.id = r.ficha_id
                LEFT JOIN pedidos_sucursales ps ON ps.pedido_id = p.id AND ps.sucursal = r.sucursal
                LEFT JOIN ({_SQL_DEVUELTO_POR_RENGLON}) d ON d.pedido_renglon_id = r.id
                WHERE r.id = %s AND r.armado_el IS NOT NULL AND r.anulado_el IS NULL
                """,
                (renglon_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
            return dict(zip(columnas, fila))
    finally:
        conexion.close()


def devoluciones_vinculadas_por_rango(cliente_id: int, fecha_desde, fecha_hasta) -> list[dict]:
    """Las devoluciones VINCULADAS a pedido del cliente en el rango (por la fecha del reingreso).

    La materia prima de la línea "− devoluciones" de la Rentabilidad REAL:
    cada una con su renglón de origen (kilos enviados y bultos armados,
    para pasar bultos a kilos), la fecha del PEDIDO (ancla el precio en el
    mismo listado que todo lo demás) y el costo congelado. La TEÓRICA no
    mira esta tabla jamás.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.id, m.cantidad AS bultos, m.fecha_operacion, m.costo_por_bulto,
                       m.destino_rechazo, r.ficha_id,
                       r.kilos_enviados, COALESCE(r.cantidad_armada, r.cantidad) AS bultos_armados,
                       p.fecha_operacion AS fecha_pedido,
                       a.id AS articulo_id, a.nombre AS articulo_nombre, a.grupo
                FROM movimientos_stock m
                JOIN pedidos_renglones r ON r.id = m.pedido_renglon_id
                JOIN pedidos p ON p.id = r.pedido_id
                JOIN articulos a ON a.id = m.articulo_id
                WHERE m.anulado_el IS NULL AND m.pedido_renglon_id IS NOT NULL
                  AND p.cliente_id = %s
                  AND m.fecha_operacion >= %s AND m.fecha_operacion <= %s
                ORDER BY m.fecha_operacion, m.creado_en
                """,
                (cliente_id, fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def _entradas_y_salidas_stock_varios(cursor, articulo_ids: list[int], corte=None) -> dict:
    """La cuenta de lotes y salidas de VARIOS artículos, con el cursor abierto.

    Devuelve {articulo_id: (entradas, salidas)}, con una entrada por cada id
    pedido — el que no tiene ningún movimiento sale con listas vacías, nunca
    ausente: un artículo que no aparece rompería al que lo lee, y "sin
    movimiento" es un resultado, no un faltante.

    Desde E4 las salidas vienen UNA POR UNA y FECHADAS, no como un total.
    Ese total sin fecha era lo que le permitía al reparto de stock consumir
    un lote posterior a la salida para tapar un faltante. Las mermas
    dirigidas ya no viajan aparte: cada una es una salida más, con su
    lote_tipo y su lote_origen_id encima, así que no hay forma de contarlas
    dos veces ni de olvidarse de restarlas.

    Son las MISMAS tres consultas de siempre con "= ANY(%s)" en vez de "= %s".
    Antes se corrían una vez por artículo, con su conexión cada vez: el listado
    de Stock del Sistema —la pantalla que se borró el 06/09— abría una por
    artículo con guía R, y la Rentabilidad
    Real dos por artículo del rango. Con el reproceso funcionando eso crece con
    el catálogo.

    El reparto en sí NO cambia: cada artículo recibe exactamente las mismas
    listas que recibía antes, y el motor (core/stock.py, core/costo_real.py)
    ni se entera.

    EL PISO DEL CORTE VIVE ACÁ Y EN NINGÚN OTRO LADO, y es asimétrico a
    propósito:

    - Las ENTRADAS se recortan: un lote anterior al corte no existe para el
      FIFO. Más el compensatorio, que se va POR TIPO y no por fecha.
    - Las SALIDAS también se recortan, y ESTRICTO en las tres patas: el
      conteo del corte se toma a la tarde, así que una salida de ese día ya
      está adentro de la foto y volver a restarla la contaría dos veces. El
      criterio vive en `_salidas_stock_varios`, que además dice qué se
      pierde (las entregas del día del corte y anteriores se quedan sin
      atribución de costo).

      Este párrafo decía lo contrario hasta el 08/09 —"las salidas no se
      recortan, y no es un olvido"— y era cierto mientras el piso estuvo
      solo de un lado. Queda anotado porque es exactamente la señal que
      describe CLAUDE.md: un comentario que envejeció sin que nadie lo
      tocara.

    Lo que el piso NO arregla, y hay que decirlo acá porque es el mismo
    lugar donde se decide qué es un lote: `reprocesos.bultos_primera` entra
    como lote del MISMO artículo que los cajones de las compras, así que un
    reproceso puede tomar cajas ya armadas como si fueran materia prima.
    Medido bien el 08/09: 10 de 20 guías R posteriores al corte,
    $2.798.438,92 en dos días (06 y 07/09; el corte de Frutamax es el
    05/09). El 07/09 dijimos 19 de 32 y $3.572.620: esa medición contaba
    el día del corte —`>=`— y por eso abarcaba tres días. Ver e5_5.
    LA FECHA DE CORTE ES POR BASE Y SE MUEVE: Palmala tiene 31/08. No
    asumirla nunca; sale de corte_modelo. Es otro
    problema —la mezcla de unidades, E5— y necesita otro arreglo.
    """
    from core.stock import orden_de

    ids = list(articulo_ids)
    entradas_por_articulo = {articulo_id: [] for articulo_id in ids}
    dirigidas_por_articulo = {articulo_id: [] for articulo_id in ids}
    if not ids:
        return {}

    # EL PISO DEL CORTE, y va acá porque acá se define qué es un lote. Antes
    # el FIFO veía toda la historia: el 07/09 medimos que 18 de las 32 guías
    # R de dos días se habían costeado contra lotes que el corte declaró
    # inexistentes ($4.705.353). El corte cancela el saldo viejo en el TOTAL
    # —ese es el compensatorio— pero el compensatorio opera sobre el neto y
    # el FIFO razona por lote, así que los restantes sobrevivían al cierre.
    #
    # `crear_reproceso` ya tenía la mitad de esta regla: prohíbe FECHAR una
    # guía R antes del corte (ReprocesoAnteriorAlCorte) y permitía COSTEARLA
    # con mercadería anterior al corte. Ésta es la otra mitad.
    #
    # `corte` se recibe hecho cuando el llamador ya lo leyó en su misma
    # transacción (crear_reproceso, que lo necesita antes para el freno de
    # fecha): así es UNA lectura por transacción y no dos, y sigue siendo
    # la misma función la que define de dónde sale la fecha.
    if corte is None:
        corte = _fecha_corte(cursor)

    cursor.execute(
        """
        SELECT * FROM (
            SELECT (c.procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date AS fecha_orden,
                   c.procesada_el AS momento_orden,
                   'guia' AS tipo_lote,
                   c.id AS origen_id,
                   g.fecha_operacion AS fecha_lote,
                   p.nombre AS detalle,
                   NULL AS motivo,
                   -- COALESCE y no la columna pelada: cantidad_cajones_real
                   -- es NULLABLE y el unico check de compras
                   -- (compras_cantidad_cargada_check) exige kilos o
                   -- fraccion, NO cajones. Nada obliga a que una compra
                   -- recepcionada los tenga cargados, asi que sin esto un
                   -- lote podria entrar al FIFO con cantidad NULL y romper
                   -- la aritmetica de core/stock.py. Medido el 08/09
                   -- (db/nulos_1_compras_sin_cajones.sql): cero en las dos
                   -- bases, o sea que esto es preventivo y no repara nada.
                   COALESCE(c.cantidad_cajones_real, 0) AS cantidad,
                   c.importe AS costo_bulto,
                   NULL::bigint AS cliente_lote_id,
                   c.articulo_id AS articulo_id
            FROM compras c
            JOIN proveedores p ON p.id = c.proveedor_id
            LEFT JOIN guias_compra g ON g.id = c.guia_id
            WHERE c.estado = 'recepcionado' AND c.articulo_id = ANY(%s)
              -- ESTRICTO: una compra recepcionada el día del corte ya está
              -- adentro de la foto que se contó esa tarde.
              AND (c.procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date > %s
              -- LA MISMA GUARDA QUE LAS OTRAS DOS RAMAS de este UNION:
              -- movimientos pide `m.cantidad > 0` y reprocesos
              -- `rp.bultos_primera > 0`. Esta era la unica sin ella, asi que
              -- una compra recepcionada con 0 cajones —o con NULL— entraba
              -- como un lote que no aporta ningun bulto. Un lote de cero no
              -- es un lote: el FIFO lo saltea igual, pero aparece en el
              -- detalle y hace ruido.
              AND c.cantidad_cajones_real > 0
            UNION ALL
            -- costo_por_bulto: solo los reingresos VINCULADOS lo tienen (el
            -- congelado del listado anclado al pedido de origen); ajustes y
            -- reingresos viejos sin vínculo siguen siendo lotes sin costo.
            -- Un rechazo mandado a segunda NO es un lote de stock: salió del
            -- circuito normal al pool de segunda, y su costo ya se imputó
            -- entero como pérdida en la Rentabilidad Real.
            SELECT m.fecha_operacion, m.creado_en, m.tipo, m.id, m.fecha_operacion,
                   cl.nombre, m.motivo, m.cantidad, m.costo_por_bulto, NULL::bigint,
                   m.articulo_id
            FROM movimientos_stock m
            LEFT JOIN clientes cl ON cl.id = m.cliente_id
            WHERE m.anulado_el IS NULL AND m.cantidad > 0 AND m.articulo_id = ANY(%s)
              AND (m.destino_rechazo IS NULL OR m.destino_rechazo = 'stock')
              -- EL DÍA DEL CORTE ES ASIMÉTRICO. El 'stock_inicial' DEL
              -- corte es la foto —la línea de base— y entra; todo lo demás
              -- de ese día ya está adentro de esa foto y NO entra. Con `>=`
              -- el día del corte se cuenta dos veces.
              AND (
                  (m.tipo = 'stock_inicial' AND m.fecha_operacion = %s)
                  OR m.fecha_operacion > %s
              )
              -- El compensatorio sale POR TIPO y no por fecha: está fechado
              -- EN el corte, así que un piso por fecha lo dejaría adentro y
              -- el FIFO seguiría teniendo un lote de mercadería que no
              -- existe. Su trabajo es el TOTAL (la cuenta 1), no el reparto.
              AND m.tipo <> 'cierre_modelo_viejo'
            UNION ALL
            -- La primera lleva PARA QUIÉN se armó (dato de trazabilidad: el
            -- stock sigue sin dueño); cliente_lote_id alimenta la alerta de
            -- cruce y el detalle muestra "armada para X".
            SELECT rp.fecha_operacion, rp.creado_en, 'reproceso', rp.id, rp.fecha_operacion,
                   cl.nombre, NULL, rp.bultos_primera, rp.costo_por_bulto_primera, rp.cliente_id,
                   rp.articulo_id
            FROM reprocesos rp
            LEFT JOIN clientes cl ON cl.id = rp.cliente_id
            WHERE rp.anulado_el IS NULL AND rp.bultos_primera > 0 AND rp.articulo_id = ANY(%s)
              -- Misma asimetría: las guías R 'inicial' DEL corte son la foto
              -- de las cajas que estaban armadas en el piso. Una guía R
              -- NORMAL de ese mismo día armó cajas que la foto ya contó.
              AND (
                  (rp.tipo = 'inicial' AND rp.fecha_operacion = %s)
                  OR rp.fecha_operacion > %s
              )
        ) lotes
        ORDER BY articulo_id, fecha_orden, momento_orden
        """,
        (ids, corte, ids, corte, corte, ids, corte, corte),
    )
    columnas = [descripcion[0] for descripcion in cursor.description]
    for fila in cursor.fetchall():
        lote = dict(zip(columnas, fila))
        # El "orden" del FIFO se arma acá y en ningún otro lado: antes cada
        # pantalla lo rehacía con la misma línea copiada, y alcanzaba con que
        # una se olvidara para que su reparto ordenara por otra cosa. Desde el
        # 19/09 la TUPLA en sí sale de `orden_de` (core/stock.py), pegada a su
        # inversa `fecha_de_orden`: la simulación de mover un lote de fecha
        # necesitaba rearmarla y ése era el tercer lugar que la copiaba.
        lote["orden"] = orden_de(lote["fecha_orden"], lote["momento_orden"])
        entradas_por_articulo[lote.pop("articulo_id")].append(lote)

    # Las SALIDAS son las mismas que usa el FIFO de costo, ya fechadas y
    # tipadas: desde E4 hay UNA sola definición de "qué salió y cuándo".
    # Antes acá se armaba un total sin fecha, y ese total era justamente lo
    # que dejaba al reparto de stock consumir lotes del futuro.
    salidas_por_articulo = _salidas_stock_varios(cursor, ids, corte)

    resultado = {}
    for articulo_id in ids:
        resultado[articulo_id] = (entradas_por_articulo[articulo_id], salidas_por_articulo[articulo_id])
    return resultado


def _entradas_y_salidas_stock(cursor, articulo_id: int, corte=None) -> tuple[list[dict], list[dict]]:
    """La cuenta interna de lotes y salidas de UN artículo, con el cursor abierto.

    La usa crear_reproceso, que necesita rejugar el FIFO adentro de su propia
    transacción antes de insertar. Es la de varios con un solo id: una sola
    consulta de cada cosa, para que no puedan desincronizarse nunca.
    """
    return _entradas_y_salidas_stock_varios(cursor, [articulo_id], corte)[articulo_id]


def entradas_y_salidas_stock_articulos(articulo_ids: list[int]) -> dict:
    """Los lotes y las salidas fechadas de VARIOS artículos, en UNA conexión.

    Devuelve {articulo_id: (entradas, salidas)}. Es la que
    usan las pantallas que miran muchos artículos de una (Stock del Depósito,
    Guías R, Rentabilidad Real): antes abrían una conexión por artículo.
    """
    if not articulo_ids:
        return {}
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return _entradas_y_salidas_stock_varios(cursor, articulo_ids)
    finally:
        conexion.close()


def entradas_y_salidas_stock_articulo(articulo_id: int) -> tuple[list[dict], list[dict]]:
    """Los lotes de entrada de un artículo (orden FIFO) y sus salidas, una por una y fechadas.

    Entradas: compras recepcionadas (el lote es la guía: fecha + proveedor),
    reingresos por rechazo que quedaron en stock, ajustes positivos y la
    primera de las guías R. Salidas (un total, se reparten FIFO en
    core/stock.py): renglones armados de pedidos vigentes, mermas, ajustes
    negativos y lo tomado por reprocesos. El orden de un movimiento es su
    fecha_operacion (la REAL del hecho), con el momento de carga de
    desempate; el de una compra, el instante de su recepción.

    Las mermas con lote elegido salen aparte (y ya descontadas del total):
    esas no van al lote más viejo sino al que el operario marcó.

    Para un artículo solo (el detalle FIFO de una pantalla). Quien mire varios
    tiene que usar entradas_y_salidas_stock_articulos, que los trae todos en
    una conexión.
    """
    return entradas_y_salidas_stock_articulos([articulo_id])[articulo_id]


def total_reingresos_rechazo(hasta=None) -> float:
    """Bultos reingresados por rechazo del cliente (plata perdida) hasta la fecha: el dueño lo quiere a la vista.

    `hasta=None` es hoy, igual que el resto del módulo. Va acumulado desde
    el principio y no desde el corte a propósito: es plata perdida, no
    stock, y el corte no la perdona.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                WITH tope AS (""" + _SQL_TOPE + """)
                SELECT COALESCE(SUM(cantidad), 0) FROM movimientos_stock, tope
                WHERE anulado_el IS NULL AND tipo = 'reingreso_rechazo'
                  AND fecha_operacion <= tope.fecha
                """,
                (hasta,),
            )
            return float(cursor.fetchone()[0])
    finally:
        conexion.close()


def listar_movimientos_stock_por_rango(fecha_desde, fecha_hasta) -> list[dict]:
    """Los movimientos de stock del rango (por fecha_operacion, la REAL del hecho), anulados incluidos y marcados.

    Para la pantalla Movimientos (control): corregir = anular el movimiento
    equivocado y cargarlo de nuevo bien — nunca editar ni borrar.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.id, m.tipo, m.cantidad, m.motivo, m.fecha_operacion,
                       m.stock_sistema, m.creado_en, m.anulado_el,
                       a.nombre AS articulo_nombre, cl.nombre AS cliente_nombre,
                       m.pedido_renglon_id, m.destino_rechazo, m.bultos_segunda, m.lote_tipo,
                       -- LA FICHA, y faltaba: `movimientos_stock` la ganó con
                       -- la merma de cajas armadas y este lector —que es el
                       -- que ARMA el renglón de la pantalla— se quedó sin
                       -- ella, así que una merma de la caja de un cliente se
                       -- listaba igual que una de los sueltos. Es el
                       -- corolario 3: al agregar un campo hay que grepear
                       -- quién CONSTRUYE la estructura, no quién la nombra.
                       m.ficha_id,
                       -- A QUIÉN se le devolvió, y faltaba por la MISMA razón
                       -- que la ficha de arriba: la columna se agregó con el
                       -- cuarto destino del rechazo y este lector no se
                       -- actualizó. El comentario que explica el corolario 3
                       -- está tres líneas más arriba y el caso volvió a pasar
                       -- con la columna siguiente — un comentario avisa al que
                       -- lo lee, y al que agrega una columna no lo lee nadie.
                       --
                       -- Sin esto la pantalla decía "se le devolvió al
                       -- proveedor" y no decía a cuál: el dato estaba en la
                       -- base y no salía por ninguna pantalla, que es el campo
                       -- sin consecuencia con otra ropa.
                       m.proveedor_devolucion_id,
                       -- POR LOS DOS CAMINOS, y esto es del 12/09: desde que
                       -- la devolución se puede vincular a la COMPRA, el
                       -- proveedor suelto queda en NULL en ese caso (los dos
                       -- juntos los rechaza `movimientos_stock_compra_o_
                       -- proveedor`). Sin el COALESCE la pantalla volvía a
                       -- decir "se le devolvió al proveedor" sin nombrarlo,
                       -- que es el agujero que se acababa de tapar — el
                       -- camino nuevo cayendo en la rama vieja.
                       COALESCE(pd.nombre, pc.nombre) AS proveedor_devolucion_nombre,
                       COALESCE(pd.codigo_puesto, pc.codigo_puesto) AS proveedor_devolucion_puesto,
                       -- Y CUÁL COMPRA, que es lo que el reclamo necesita
                       -- nombrar: "de la del martes te devolví 8".
                       m.compra_devolucion_id,
                       cd.fecha_operacion AS compra_devolucion_fecha,
                       p.fecha_operacion AS fecha_pedido, r.sucursal AS sucursal_pedido,
                       -- CUÁNTAS FOTOS TIENE, no si tiene: el listado lo
                       -- muestra como "sin foto" en gris cuando da 0, y eso
                       -- es lo único que cambia el incentivo. Una merma
                       -- legítima y una que tapa un faltante se ven iguales
                       -- como número; el "sin foto" a la vista es lo que las
                       -- separa sin trabar a nadie.
                       (SELECT COUNT(*) FROM fotos_merma f WHERE f.movimiento_id = m.id) AS fotos
                FROM movimientos_stock m
                JOIN articulos a ON a.id = m.articulo_id
                LEFT JOIN clientes cl ON cl.id = m.cliente_id
                LEFT JOIN pedidos_renglones r ON r.id = m.pedido_renglon_id
                LEFT JOIN pedidos p ON p.id = r.pedido_id
                LEFT JOIN proveedores pd ON pd.id = m.proveedor_devolucion_id
                LEFT JOIN compras cd ON cd.id = m.compra_devolucion_id
                LEFT JOIN proveedores pc ON pc.id = cd.proveedor_id
                WHERE m.fecha_operacion >= %s AND m.fecha_operacion <= %s
                ORDER BY m.fecha_operacion DESC, m.creado_en DESC
                """,
                (fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def anular_movimiento_stock(movimiento_id: int) -> None:
    """Anula un movimiento de stock (baja lógica): queda visible como corrección, el stock y el FIFO lo excluyen solos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE movimientos_stock SET anulado_el = now() WHERE id = %s AND anulado_el IS NULL",
                (movimiento_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


# El stock PARTIDO: los bultos sueltos del artículo por un lado, y las cajas
# ya armadas de cada ficha por otro. Es la cuenta del Cotejo desde la etapa
# 3, y suma exactamente lo mismo que stock_deposito_por_articulo: cada
# renglón es una porción de ese total, no una cuenta nueva.
#
# cajas(ficha)   = lo reprocesado a esa ficha − lo que salió atribuido a ella
# sueltos(art)   = el stock del artículo − la suma de las cajas de sus fichas
#
# Las SALIDAS se atribuyen por la ficha del renglón, que es con la que el
# cliente PIDIÓ. Si pidió Banana Bolivia y se le mandaron cajas de Banana
# Ecuador, la salida se le descuenta a Bolivia igual. Eso NO es un error a
# tapar: aparece como dos diferencias a la vez —Bolivia de menos, Ecuador
# de más— y es la única forma que tiene el sistema de mostrar un cambio de
# ficha, que hasta ahora no se veía en ningún lado.
# EL PISO DE FECHA, y es la mitad del sentido de esta consulta.
#
# Las DOS patas arrancan en la fecha de corte. Sin eso, la cuenta por ficha
# es la única del sistema que sigue sumando desde el principio de los
# tiempos: el total del artículo se rebasea en cada corte con el
# compensatorio, y acá no hay compensatorio posible — `cierre_modelo_viejo`
# es un movimiento por ARTÍCULO y esta consulta no lee movimientos.
#
# Tienen que ser las DOS o es peor que ninguna. Recortar solo las entradas
# deja las salidas viejas restando contra cajas que ya no están, y eso es
# exactamente el negativo estructural que produjo el corte del 31/08 (ver
# "Deuda que dejamos nosotros" en docs/diseno_base_datos.md).
#
# Sale de corte_modelo y NO de una constante: la fecha se mueve en cada
# corte, y un piso viejo no falla — deja pasar.
#
# EL DÍA DEL CORTE ES ASIMÉTRICO, y no es un detalle: el conteo físico se
# toma A LA TARDE de ese día, así que todo lo que pasó ANTES del conteo ya
# está adentro de lo que se contó. Por eso el piso es:
#
#   entradas: los 'inicial' DEL corte (son la línea de base, la foto de lo
#             contado) + cualquier guía R POSTERIOR al corte.
#   salidas:  solo las POSTERIORES al corte.
#
# Con `>=` en las dos, el día del corte se cuenta dos veces y en las dos
# direcciones. Simulado el 05/09 contra Postgres: una ficha con 50 cajas de
# una guía R del 03/09, 30 que salieron el sábado y 20 contadas daba **-10**
# (la salida resta y su guía R queda afuera); y una guía R normal cargada
# ese mismo sábado se sumaba ADEMÁS del inicial que ya la contenía, dando
# **30** donde había 15. Con el piso asimétrico dan 20 y 15, que es lo que
# hay en el piso.
#
# El total del ARTÍCULO no tiene este problema porque no se rebasea con una
# fecha sino con el compensatorio, que es una FOTO tomada esa misma tarde y
# ya incluye los movimientos del día. Esta cuenta usa un filtro de fecha, y
# UN FILTRO NO SABE A QUÉ HORA SE CONTÓ: por eso el día del corte hay que
# partirlo a mano, y por eso la asimetría de arriba no es un caso borde sino
# la forma correcta de la regla.
# Igual que las seis patas: PISO del corte y TECHO de la fecha pedida.
# ¿ESTE REINGRESO ENTRA EN LA CUENTA DE UNA FICHA? Escrito UNA SOLA VEZ y
# usado por las dos que tienen que coincidir: `_SQL_STOCK_PARTIDO`, que lo
# SUMA a la ficha, y `eventos_de_stock_del_dia`, que lo MUESTRA en el
# extracto de esa ficha.
#
# Hasta el 09/09 estaban separadas, y el paso 1 las partió: la cuenta empezó
# a atribuirlo a la ficha y el extracto lo siguió listando como evento de
# sueltos. El síntoma es inconfundible y sirve para reconocerlo si vuelve a
# pasar — los dos "Sin explicar" del mismo día salen IGUALES Y DE SIGNO
# OPUESTO (Limón 08/09: −15 en sueltos y +15 en la ficha), porque el evento
# está de un lado y el saldo del otro.
#
# Pide el alias `m` para movimientos_stock y `pr` para el renglón por el que
# salió (pr.id = m.pedido_renglon_id). La VENTANA del corte no está acá a
# propósito: no es parte de "de quién es este reingreso", y cada consulta
# recorta con la suya.
# LOS TIPOS QUE DICEN DE QUÉ FICHA SALIERON, escrito UNA vez y usado por la
# CUENTA (`_SQL_STOCK_PARTIDO`) y por el EXTRACTO (`eventos_de_stock_del_dia`).
#
# La merma lo tiene desde el 10/09 y el pase desde el 21/09, y los dos por el
# mismo motivo: son bultos que se van de una pila concreta. Si sale de cajas
# ya armadas hay que restárselo a esa ficha — sin eso baja el TOTAL y no baja
# la ficha, y como los sueltos se derivan por resta la baja cae ENTERA sobre
# ellos, que es el bug que este CTE vino a arreglar.
#
# ESTABAN SEPARADOS Y SE HABÍAN SEPARADO DE VERDAD: hasta el 21/09 la cuenta
# leía `m.ficha_id` y el extracto NO LO LEÍA EN ABSOLUTO —derivaba la ficha
# solo por el camino del reingreso— así que una merma de cajas armadas salía
# restada de la ficha en el saldo y dibujada en sueltos en el extracto.
# Medido antes de arreglarlo: 10 cajas armadas, se tiran 3, la cuenta dice
# ficha 7 y el extracto dice `ficha_id` None.
# La lista de esos tipos vive en `core.stock.TIPOS_CON_FICHA_PROPIA`, al lado
# de la prioridad del FIFO que la usa. Acá va escrita como SQL porque esto es
# un fragmento de consulta; lo que ata las dos es un test.
_SQL_TIPO_TIENE_FICHA_PROPIA = "m.tipo IN ('merma', 'pase_a_segunda') AND m.ficha_id IS NOT NULL"

# LOS DOS TIPOS QUE SON UNA PERDIDA, sin mirar la ficha: un pase de SUELTOS
# tambien se lleva mercaderia, lo que no se lleva es una caja nuestra. Va
# aparte de la de arriba porque contestan preguntas distintas —aquella es
# "¿de que pila salio?" y esta "¿esto es una perdida?"— y una sola sirviendo
# para las dos es como se separan despues sin que nadie lo note.
# Misma lista que `core.stock.TIPOS_CON_FICHA_PROPIA`, atada por un test.
_SQL_TIPOS_QUE_SON_PERDIDA = "('merma', 'pase_a_segunda')"

_SQL_REINGRESO_ES_DE_LA_FICHA = """
    m.tipo = 'reingreso_rechazo'
    AND (m.destino_rechazo IS NULL OR m.destino_rechazo = 'stock')
    AND pr.ficha_id IS NOT NULL
"""

_SQL_STOCK_PARTIDO = """
    WITH corte AS (SELECT fecha FROM corte_modelo WHERE id = 1),
    tope AS (""" + _SQL_TOPE + f"""),
    vigentes AS (
        SELECT DISTINCT ON (cliente_id, fecha_operacion) id
        FROM pedidos WHERE anulado_el IS NULL
        ORDER BY cliente_id, fecha_operacion, creado_en DESC
    ), armadas AS (
        SELECT articulo_id, ficha_id, SUM(bultos_primera) AS total
        FROM reprocesos, corte, tope
        WHERE anulado_el IS NULL AND ficha_id IS NOT NULL
          AND fecha_operacion <= tope.fecha
          AND (fecha_operacion > corte.fecha
               OR (tipo = 'inicial' AND fecha_operacion >= corte.fecha))
        GROUP BY articulo_id, ficha_id
    ), salidas_ficha AS (
        SELECT r.articulo_id, r.ficha_id,
               SUM(COALESCE(r.cantidad_armada, r.cantidad)) AS total
        FROM pedidos_renglones r JOIN vigentes v ON v.id = r.pedido_id, corte, tope
        WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL
          AND r.articulo_id IS NOT NULL AND r.ficha_id IS NOT NULL
          AND (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
              > corte.fecha
          AND (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
              <= tope.fecha
        GROUP BY r.articulo_id, r.ficha_id
    ), reingresos_ficha AS (
        -- LO QUE VUELVE YA ARMADO. Vuelven cajas de un cliente, en su caja,
        -- y son de la ficha por la que salieron. Hasta el 09/09 esta cuenta
        -- no leía movimientos_stock, así que NINGÚN reingreso entró nunca en
        -- una ficha: se los comían los sueltos por resta, y el sistema
        -- contaba cajas armadas como cajones sin procesar.
        --
        -- LA FICHA NO ES UNA COLUMNA SUYA: se llega por el renglón del que
        -- volvió (pedido_renglon_id -> pedidos_renglones.ficha_id), que es
        -- el mismo vínculo que ya usa el costo del reingreso. Medido en
        -- Frutamax el 09/09: 5 reingresos, los 5 con ficha alcanzable, 0
        -- huérfanos.
        --
        -- 'segunda' y 'reproceso' quedan afuera: eso NO vuelve al stock
        -- normal, va al pool de segunda (mismo criterio que la pata
        -- `reingresos` de _SQL_SUMAS_STOCK).
        --
        -- Y el corte con la MISMA ventana que los otros dos términos: si
        -- este mirara toda la historia y los otros solo lo posterior, la
        -- resta mezclaría dos eras. Un reingreso anterior al corte ya está
        -- adentro de la foto del stock inicial.
        SELECT pr.articulo_id, pr.ficha_id, SUM(m.cantidad) AS total
        FROM movimientos_stock m
        JOIN pedidos_renglones pr ON pr.id = m.pedido_renglon_id, corte, tope
        WHERE m.anulado_el IS NULL AND {_SQL_REINGRESO_ES_DE_LA_FICHA}
          AND m.fecha_operacion > corte.fecha
          AND m.fecha_operacion <= tope.fecha
        GROUP BY pr.articulo_id, pr.ficha_id
    ), bajas_ficha AS (
        -- LO QUE SE FUE DE ESA FICHA: lo que se TIRÓ y lo que PASÓ A SEGUNDA.
        -- Resta igual que una salida, porque es una: son cajas que ya no
        -- están. Hasta el 10/09 la merma no podía decir de qué ficha salía,
        -- así que bajaba el TOTAL del artículo y no bajaba la ficha — y como
        -- los sueltos se derivan por resta, la baja caía ENTERA sobre los
        -- sueltos. Medido antes de arreglarlo: tirando las 10 cajas de una
        -- ficha, el sistema quedaba diciendo 10 cajas y 0 sueltos, con el
        -- galpón exactamente al revés.
        --
        -- EL PASE ENTRÓ EL 21/09 Y SE LLAMABA `mermas_ficha`. El nombre se
        -- movió con la condición a propósito: un CTE que se llama "mermas" y
        -- suma dos tipos es la clase de nombre que se lee y no se verifica, y
        -- el que venga a agregar el tercero va a buscar acá.
        --
        -- LA MISMA VENTANA que los otros tres términos (> corte, <= tope), y
        -- por la misma razón que dice `reingresos_ficha`: si éste mirara toda
        -- la historia y los otros solo lo posterior, la resta mezclaría dos
        -- eras. Verificado con el canario de siempre — corrida con `>=` el
        -- número SE MUEVE (7 cajas contra 3), así que el piso está puesto.
        SELECT m.articulo_id, m.ficha_id, SUM(-m.cantidad) AS total
        FROM movimientos_stock m, corte, tope
        WHERE m.anulado_el IS NULL AND {_SQL_TIPO_TIENE_FICHA_PROPIA}
          AND m.fecha_operacion > corte.fecha
          AND m.fecha_operacion <= tope.fecha
        GROUP BY m.articulo_id, m.ficha_id
    ), fichas_con_algo AS (
        SELECT articulo_id, ficha_id FROM armadas
        UNION
        SELECT articulo_id, ficha_id FROM salidas_ficha
        UNION
        SELECT articulo_id, ficha_id FROM reingresos_ficha
        UNION
        -- Y ACÁ TAMBIÉN, que es lo fácil de olvidar: sin esta pata, una
        -- ficha cuyo ÚNICO movimiento sea una baja —una merma o un pase a
        -- segunda— no existe para la consulta y no aparece en ningún lado.
        -- La resta la haría bien y no la haría nunca.
        SELECT articulo_id, ficha_id FROM bajas_ficha
    )
    SELECT f.articulo_id, f.ficha_id,
           COALESCE(a.total, 0) + COALESCE(re.total, 0)
               - COALESCE(s.total, 0) - COALESCE(me.total, 0) AS stock,
           -- MISMA CONDICIÓN QUE LA PARED DEL FIFO (`ficha_con_envase` en
           -- _SQL_SALIDAS_STOCK): la ficha que declara envase se reenvasa, y
           -- un armado suyo NO puede salir de un cajón. Viaja acá para que
           -- el piso se aplique o no según eso, en vez de ser dos reglas.
           (fl.envase_id IS NOT NULL) AS con_envase
    FROM fichas_con_algo f
    LEFT JOIN armadas a ON a.articulo_id = f.articulo_id AND a.ficha_id = f.ficha_id
    LEFT JOIN salidas_ficha s ON s.articulo_id = f.articulo_id AND s.ficha_id = f.ficha_id
    LEFT JOIN reingresos_ficha re ON re.articulo_id = f.articulo_id AND re.ficha_id = f.ficha_id
    LEFT JOIN bajas_ficha me ON me.articulo_id = f.articulo_id AND me.ficha_id = f.ficha_id
    LEFT JOIN fichas_logistica fl ON fl.id = f.ficha_id
"""


def _cajas_por_ficha(cursor, hasta=None) -> dict:
    """{(articulo_id, ficha_id): (disponibles, deficit)}, SOLO las fichas con algún movimiento.

    Una ficha sin nada reprocesado ni nada salido no aparece. Es a
    propósito: si el Cotejo listara todas las fichas de todos los clientes
    en cero, la pantalla se vuelve ilegible y se deja de mirar.

    EL SALDO CRUDO PUEDE SER NEGATIVO, y por eso esto devuelve DOS números
    en vez de uno. El SQL calcula `producidas − salidas` sin piso, y salir
    de más es normal:

    - Un artículo que NO SE REPROCESA (manzana, pera, arándano: salen en el
      envase que vienen) tiene cero producidas y todas sus salidas del otro
      lado. Su saldo es negativo puro y crece todos los días.
    - Un artículo que sí se reprocesa puede haberse armado desde la PILA
      SUELTA cuando no había cajas. También legítimo.

    Una salida solo puede consumir cajas hasta lo que se produjo; el resto
    salió de los sueltos. Por eso:

      disponibles = max(saldo, 0)   ← lo que hay de verdad en cajas
      deficit     = max(-saldo, 0)  ← lo que salió sin caja detrás

    El piso NO va en el SQL: si se clavara ahí, el déficit se perdería y
    con él la única pista de que falta cargar una guía R (ver
    listar_articulos_para_reproceso, que lo necesita para no esconder el
    artículo que hay que reprocesar — la falla de producción del 31/08).

    Sin el piso, `sueltos = total − Σ cajas` daba MÁS que el total del
    artículo, y el Cotejo ofrecía un ajuste destructivo precargado para
    tapar esa diferencia inventada (04/09/2026: Manzana Gob, total 63,
    sueltos 233, botón de ajuste por 170).
    """
    cursor.execute(_SQL_STOCK_PARTIDO, (hasta,))
    saldos = {}
    for articulo_id, ficha_id, saldo, con_envase in cursor.fetchall():
        valor = float(saldo)
        if con_envase:
            # CON ENVASE NO HAY PISO. Un pedido de Caja de Día no puede tomar
            # nada que no sea de esa ficha: si no hay cajas, el armado queda
            # en déficit y se resuelve cuando entra la guía R — igual que el
            # costo, que la pared del FIFO deja sin lote hasta ese momento.
            # Antes el excedente se escurría a los sueltos y el sistema
            # descontaba limón sin procesar por un armado de caja.
            saldos[(articulo_id, ficha_id)] = (valor, 0.0)
        else:
            # SIN ENVASE es envase perdido (manzana, pera, arándano): sale en
            # el cajón del proveedor y NUNCA se reprocesa, así que su saldo es
            # negativo puro y crece todos los días. Acá el piso SÍ va — sin él
            # vuelve el 04/09: Manzana Gob, total 63, sueltos 233, botón de
            # ajuste destructivo por 170. Medido el 09/09: sin scopear se
            # moverían 320 bultos y 290 son de estas fichas.
            saldos[(articulo_id, ficha_id)] = (max(valor, 0.0), max(-valor, 0.0))
    return saldos


def listar_articulos_para_reproceso() -> list[dict]:
    """Los artículos que se pueden reprocesar: id y nombre, SIN cantidades.

    Entra el artículo con TOTAL a favor (el criterio de siempre) O con
    BULTOS SUELTOS a favor. La condición es OR y no un reemplazo, a
    propósito: esto solo AGREGA a la lista de antes, nunca saca nada.

    El que faltaba es el de los sueltos, y es la falla del 31/08 en
    producción: si el depósito arma cajas de una ficha antes de cargar su
    guía R, el TOTAL del artículo baja —puede llegar a cero— mientras la
    pila suelta sigue intacta en el piso. Con el filtro por total, el
    artículo desaparecía del selector exactamente cuando había que cargar
    el reproceso que reconcilia esa diferencia; y sin ese reproceso la
    diferencia no se cierra nunca. Es circular, y ese círculo se corta acá.

    sueltos(art) = stock del artículo − Σ cajas de sus fichas: la misma
    resta del Cotejo (_SQL_STOCK_PARTIDO), así las porciones suman
    siempre el total y no se pierde ni se duplica nada.

    Por qué OR y no "solo sueltos": un artículo cuyo stock son TODO cajas
    de una ficha tiene sueltos en cero, y filtrando solo por sueltos
    desaparecería. Reprocesar cajas ya armadas es raro pero el FIFO lo
    admite (un lote de guía R es un lote como cualquier otro), así que
    esta pantalla no es el lugar para prohibirlo — eso lo decide el freno
    cuando llegue, a la vista y con motivo.

    Devuelve id y nombre y NADA MÁS: es para una pantalla de operario, y
    el número del sistema no viaja ahí ni escondido en el HTML (mismo
    criterio que Vacíos).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cajas = _cajas_por_ficha(cursor)
            cursor.execute(
                _sql_sumas_stock(por_articulo=False)
                + """
                SELECT a.id, a.nombre,
                       COALESCE(e.total, 0) + COALESCE(r.total, 0) + COALESCE(aj.total, 0)
                       + COALESCE(rp.entradas, 0) - COALESCE(rp.salidas, 0)
                       - COALESCE(s.total, 0) AS stock
                FROM articulos a
                LEFT JOIN entradas e ON e.articulo_id = a.id
                LEFT JOIN salidas s ON s.articulo_id = a.id
                LEFT JOIN reingresos r ON r.articulo_id = a.id
                LEFT JOIN ajustes aj ON aj.articulo_id = a.id
                LEFT JOIN reproc rp ON rp.articulo_id = a.id
                ORDER BY a.nombre
                """,
                (None,),
            )
            filas = cursor.fetchall()
        articulos = []
        for articulo_id, nombre, stock in filas:
            en_cajas = sum(d for (a, _), (d, _f) in cajas.items() if a == articulo_id)
            deficit = sum(f for (a, _), (_d, f) in cajas.items() if a == articulo_id)
            sueltos = round(float(stock) - en_cajas, 2)
            if float(stock) > 0 or sueltos > 0 or deficit > 0:
                articulos.append({"id": articulo_id, "nombre": nombre})
        return articulos
    finally:
        conexion.close()


def cajas_armadas_por_ficha(hasta=None) -> dict:
    """{(articulo_id, ficha_id): cajas disponibles} AL CIERRE DE `hasta` — las porciones con cajas del Remanente.

    Es `_cajas_por_ficha` con conexión propia y sin el déficit: el
    Remanente lista lo que HAY, y un déficit no se puede contar. Los que
    salieron de más se ven abajo del Remanente, en "bultos que faltan
    explicar", y el déficit POR FICHA en el Cotejo.

    Devuelve las que tienen algo, EN CUALQUIER SENTIDO: una ficha con envase
    en déficit viene en negativo y tiene que aparecer. Filtrarla acá sería un
    SEGUNDO piso —el primero está en _cajas_por_ficha— y entonces el
    Remanente mostraría una cosa y _stock_de_ficha otra, que es la misma
    cuenta escrita dos veces.

    La que sí sigue pidiendo "más de cero" es fichas_con_cajas_armadas, y ahí
    es correcto: al que arma no se le ofrece una pila vacía, y menos una
    negativa.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return {
                clave: disponibles
                for clave, (disponibles, _deficit) in _cajas_por_ficha(cursor, hasta).items()
                if disponibles != 0
            }
    finally:
        conexion.close()


def deficit_de_cajas_por_ficha(hasta=None) -> dict:
    """{(articulo_id, ficha_id): cuánto salió SIN caja armada detrás} al cierre de `hasta`.

    La otra mitad de `cajas_armadas_por_ficha`, y sale de la MISMA
    `_cajas_por_ficha`: una devuelve el índice 0 y ésta el 1, así que no
    hay dos cuentas que se puedan separar.

    Para qué: los sueltos se derivan por resta con el piso puesto
    (`total − Σ disponibles`), así que un déficit de una ficha BAJA los
    sueltos exactamente en esa cantidad — es el "resto salió de los
    sueltos" del docstring de `_cajas_por_ficha`. Sin este número, ese
    movimiento aparece en el extracto como "Sin explicar", que es lo único
    que no es: el sistema sabe perfectamente qué es.

    Solo las que tienen déficit: una ficha sin faltante no es un renglón.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return {
                clave: deficit
                for clave, (_disponibles, deficit) in _cajas_por_ficha(cursor, hasta).items()
                if deficit > 0
            }
    finally:
        conexion.close()


def fichas_con_cajas_armadas() -> set:
    """Los ficha_id que HOY tienen cajas armadas disponibles (más de cero).

    Devuelve solo ids, sin cantidades, y eso es a propósito: la usa la
    pantalla de armado, que es de OPERARIO. El número del sistema se usa
    del lado del server para decidir si avisar, pero no puede viajar a su
    pantalla ni escondido en el HTML — si lo ve, arma contra el sistema en
    vez de contra el piso (mismo criterio que Vacíos y que Reproceso, que
    filtra por stock sin mostrar la cifra).

    "No está en el conjunto" cubre los dos casos que al que arma le dan
    lo mismo: nunca se reprocesó nada para esa ficha, o ya salió todo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return {
                ficha_id
                for (_, ficha_id), (disponibles, _deficit) in _cajas_por_ficha(cursor).items()
                if disponibles > 0
            }
    finally:
        conexion.close()


def _stock_de_ficha(cursor, articulo_id: int, ficha_id: int | None) -> float:
    """El stock de UNA porción: las cajas de una ficha, o los bultos sueltos del artículo (ficha_id None).

    Es la foto que se congela al cargar un conteo. Los sueltos se calculan
    por resta y no por una cuenta propia: así la suma de las porciones da
    siempre el total del artículo, sin que se pueda perder ni duplicar
    nada por el camino.
    """
    cajas = _cajas_por_ficha(cursor)
    if ficha_id is not None:
        return cajas.get((articulo_id, ficha_id), (0.0, 0.0))[0]
    total = _stock_deposito_actual(cursor, articulo_id)
    en_cajas = sum(disponibles for (a, _), (disponibles, _f) in cajas.items() if a == articulo_id)
    return round(total - en_cajas, 2)


def crear_conteo_stock(articulo_id: int, cantidad: float, ficha_id: int | None = None,
                       es_segunda: bool = False) -> None:
    """Conteo físico del operario del depósito. El stock del sistema se graba acá, del lado del server — NUNCA se le devuelve.

    A propósito no retorna nada: la pantalla de Stock Físico no puede
    mostrar el número del sistema (si el operario lo ve, transcribe en
    vez de contar — se pierde el control cruzado; mismo criterio que
    Vacíos). El Cotejo compara después contra esta foto exacta. Si se
    equivoca, carga de nuevo: en el Cotejo vale el último por porción.

    ficha_id dice QUÉ contó: una ficha son sus cajas ya armadas, y None
    son los bultos sueltos del artículo, sin procesar. Los sueltos son el
    caso más común, no una excepción.

    Y `es_segunda` es la TERCERA porción, desde el 09/09. Hasta entonces la
    segunda no se podía contar: no tiene ficha, así que un conteo suyo
    entraba como (articulo, NULL) y pisaba al de sueltos. No faltaba una
    pantalla — no había dónde guardarlo. La base lo separa con el check
    `conteos_stock_segunda_sin_ficha`, así que un llamador que mande las dos
    cosas rebota ahí y no se guarda a medias.

    Su foto sale de `_segunda_de_articulo`, que es la MISMA cuenta que dibuja
    la porción en el Remanente. Con dos cuentas, el conteo se congelaría
    contra un número y el Cotejo lo compararía contra otro.

    El conteo es DECLARATIVO: no se valida contra lo que el sistema cree
    tener. Si cuenta cajas de una ficha de la que el sistema no tiene
    nada, se guarda igual y el Cotejo muestra la diferencia — que es
    exactamente para lo que está.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            stock_sistema = (
                _segunda_de_articulo(cursor, articulo_id) if es_segunda
                else _stock_de_ficha(cursor, articulo_id, ficha_id)
            )
            cursor.execute(
                """
                INSERT INTO conteos_stock (articulo_id, cantidad, stock_sistema, ficha_id, es_segunda)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (articulo_id, cantidad, stock_sistema, ficha_id, es_segunda),
            )
        conexion.commit()
    finally:
        conexion.close()


def fecha_conteo_stock_mas_cercana(fecha):
    """El día con conteos más cercano al pedido, para cuando el pedido no tiene ninguno.

    Sirve para no dejar al operario en un "no hay nada" sin salida: si
    buscó el martes y contó el lunes, la pantalla le ofrece el lunes.

    Mira para los dos lados. Si empatan (uno antes y uno después, a la
    misma distancia) gana el POSTERIOR, que es el conteo más nuevo.

    Devuelve None solo si no hay ningún conteo en toda la tabla.

    Devuelve una FECHA y nada más: ningún número del sistema puede salir
    por esta pantalla, que es la del operario.

    El día es ARGENTINO, como el de listar_conteos_stock_de_fecha: sin la
    conversión, el casteo a fecha usa la zona de la sesión (UTC en Supabase)
    y ofrecería un día corrido tres horas respecto del que la lista muestra.
    Acá se convierte la columna y no un borde porque no hay borde: es un
    DISTINCT sobre toda la tabla, no un filtro con índice que preservar.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.fecha
                FROM (SELECT DISTINCT (creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date AS fecha
                      FROM conteos_stock) f
                ORDER BY abs(f.fecha - %s::date), f.fecha DESC
                LIMIT 1
                """,
                (fecha,),
            )
            fila = cursor.fetchone()
            return fila[0] if fila else None
    finally:
        conexion.close()


# LA CLAVE DE UNA PORCIÓN, y son TRES cosas. La segunda y los sueltos tienen
# los dos `ficha_id` nulo: con dos, el conteo de una pisa al de la otra.
_CLAVE_PORCION_SQL = "c.articulo_id, c.ficha_id, c.es_segunda"


def _ordenar_porciones_contadas(filas: list[dict]) -> list[dict]:
    """Cada artículo junto, y adentro el orden en que se recorre el depósito.

    Los sueltos primero (0), después las cajas de cada ficha (1) y la segunda
    al final (2) — el MISMO `orden` que usa `_porciones_de_deposito` para el
    Remanente. Lo usan el Cotejo y la lista de "Contado hoy": escrito dos
    veces, el día que uno cambie las dos pantallas muestran el mismo conteo
    en distinto lugar y parece que hay dos conteos.

    Ordenar por HORA —que es lo que hacía "Contado hoy" hasta el 11/09— deja
    "Lima Caja Día %" arriba y "Lima" quince renglones abajo, porque se
    contaron en momentos distintos. Para leer un conteo hay que ver juntas
    las porciones del mismo artículo; la hora se muestra, pero no manda.
    """
    return sorted(
        filas,
        key=lambda fila: (
            fila["articulo_nombre"],
            2 if fila["es_segunda"] else (1 if fila["ficha_id"] else 0),
            fila["ficha_nombre"] or "",
        ),
    )


def listar_conteos_stock_de_fecha(fecha) -> list[dict]:
    """Conteos de un día para la lista "Contado hoy" del operario.

    EL DÍA ES ARGENTINO Y HAY QUE DECIRLO. `fecha` viene de
    `_hoy_argentina()`, pero comparar un `timestamptz` contra un `date`
    pelado deja que Postgres resuelva el borde con la zona de la SESIÓN, y
    acá no se fija ninguna: queda la del servidor, UTC en Supabase. Así el
    día corría de 21:00 a 21:00 hora argentina y **un conteo cargado a las
    21:30 aparecía en la lista de mañana** — verificado contra Postgres 16
    en UTC. Por eso los bordes se construyen con AT TIME ZONE.

    La columna queda PELADA a propósito: convertirla a ella en vez de a los
    bordes da el mismo resultado y tira el índice (Index Only Scan pasa a
    Seq Scan, verificado con EXPLAIN).

    SIN stock_sistema en el SELECT, a propósito: esta lista la ve el
    operario, y el número del sistema no puede viajar ni escondido en el
    HTML de su pantalla.

    Trae la ficha Y `es_segunda` porque el mismo artículo aparece varias
    veces en la lista —los sueltos, cada ficha y la segunda— y sin decir
    cuál es cada uno, "Banana 40 / Banana 12" no se entiende. Sin
    `es_segunda`, el conteo de segunda se leería como uno de sueltos, que es
    la misma confusión que el DISTINCT ON tenía adentro.

    UN RENGLÓN POR PORCIÓN, EL MÁS NUEVO DEL DÍA (11/09). Antes traía todos
    y ordenaba por hora, así que un conteo corregido aparecía DOS VECES —
    "Tomate Redondo Segunda 7 a las 15:53" y "5 a las 15:51"— y se leía como
    que se contó dos veces. No se contó dos veces: se corrigió, y corregir
    un conteo es cargarlo de nuevo (no hay UPDATE ni anulación de conteos,
    verificado). El viejo queda tapado y mostrarlo es mostrar algo que ya
    no vale.

    Y es el MISMO criterio que el Cotejo, que ya tomaba el más nuevo por
    `creado_en`: con la lista mostrando dos y el Cotejo usando uno eran dos
    respuestas a la misma pregunta. La diferencia que queda es de VENTANA y
    es a propósito: el Cotejo toma el último de la historia hasta una fecha
    (le importa el estado), esta lista el último DE ESE DÍA (le importa la
    jornada).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (""" + _CLAVE_PORCION_SQL + """)
                       c.id, c.cantidad, c.creado_en, a.nombre AS articulo_nombre,
                       c.ficha_id, c.es_segunda,
                       COALESCE(NULLIF(BTRIM(f.nombre_cliente), ''), fa.nombre) AS ficha_nombre,
                       cl.nombre AS ficha_cliente
                FROM conteos_stock c
                JOIN articulos a ON a.id = c.articulo_id
                LEFT JOIN fichas_logistica f ON f.id = c.ficha_id
                LEFT JOIN articulos fa ON fa.id = f.articulo_id
                LEFT JOIN clientes cl ON cl.id = f.cliente_id
                WHERE c.creado_en >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND c.creado_en < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
                ORDER BY """ + _CLAVE_PORCION_SQL + """, c.creado_en DESC
                """,
                (fecha, fecha),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return _ordenar_porciones_contadas(filas)
    finally:
        conexion.close()


def listar_ultimos_conteos_stock(hasta=None) -> list[dict]:
    """El ÚLTIMO conteo por PORCIÓN (artículo + ficha + segunda), con su foto del sistema, para el Cotejo.

    Desde la etapa 3 un artículo tiene varias porciones: sus bultos
    sueltos, las cajas de cada ficha y —desde el 09/09— su segunda. El
    último de cada una vale por su cuenta: contar las cajas de una ficha no
    invalida el conteo de sueltos de la mañana.

    LAS TRES CLAVES EN EL DISTINCT ON, y no dos. La segunda y los sueltos
    tienen los dos `ficha_id` NULL, así que con la clave vieja compiten por
    el mismo renglón y el último cargado TAPA al otro sin decir nada.
    Medido: con (articulo_id, ficha_id) sobre sueltos 5 / ficha 7 / segunda
    42, los 42 no vuelven.

    Sale de conteos_stock y de ningún otro lado: una ficha que nunca se
    contó no genera renglón. Si el Cotejo listara todas las fichas de
    todos los clientes en cero, la pantalla se vuelve ilegible y se deja
    de mirar.

    NO HAY VENTANA: "el último" es el último que exista, aunque sea de
    hace un mes. Por eso quien lo muestre tiene que mostrar también
    creado_en — una diferencia contra un conteo de hace cinco días no
    significa lo mismo que contra el de hoy.

    `hasta` (fecha, en hora argentina) topea los conteos al cierre de ese
    día. Lo usa el Remanente a una fecha pasada: sin esto traería el
    último conteo de HOY contra un stock del 03/09 — físico del futuro
    contra sistema del pasado, adentro del mismo archivo. None = sin
    tope, que es lo que quiere el Cotejo (siempre mira el presente).

    El orden del DISTINCT ON es el del índice conteos_stock_cotejo_idx.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (c.articulo_id, c.ficha_id, c.es_segunda)
                       c.id, c.articulo_id, c.ficha_id, c.es_segunda,
                       c.cantidad, c.stock_sistema, c.creado_en,
                       a.nombre AS articulo_nombre,
                       COALESCE(NULLIF(BTRIM(f.nombre_cliente), ''), fa.nombre) AS ficha_nombre,
                       cl.nombre AS ficha_cliente
                FROM conteos_stock c
                JOIN articulos a ON a.id = c.articulo_id
                LEFT JOIN fichas_logistica f ON f.id = c.ficha_id
                LEFT JOIN articulos fa ON fa.id = f.articulo_id
                LEFT JOIN clientes cl ON cl.id = f.cliente_id
                WHERE %s::date IS NULL
                   OR (c.creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date <= %s::date
                ORDER BY c.articulo_id, c.ficha_id, c.es_segunda, c.creado_en DESC
                """,
                (hasta, hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        # El MISMO ordenador que "Contado hoy": ver _ordenar_porciones_contadas.
        return _ordenar_porciones_contadas(filas)
    finally:
        conexion.close()


def eventos_de_stock_del_dia(articulo_id: int, fecha) -> dict:
    """Todo lo que le pasó a UN artículo en UN día, crudo y por origen, para el extracto por porción.

    NO CALCULA NINGÚN SALDO, y es la decisión de fondo del extracto: los
    saldos de las puntas salen de _remanente_a_fecha (la misma función que
    dibuja el Remanente), así que la pantalla cierra por construcción. Esto
    solo EXPLICA el medio. Sumar estos eventos para obtener el saldo sería
    una quinta versión de la cuenta de stock, y las cuatro que hay ya se
    separaron entre sí una vez cada una.

    Cada origen trae su fecha con el MISMO criterio que las seis patas de
    _SQL_SUMAS_STOCK, que es lo que hace que los eventos caigan en el día en
    que la cuenta los mueve:

    - compras por COALESCE(procesada_el en hora argentina, fecha_operacion):
      una compra cargada el lunes y recepcionada el miércoles entra el
      miércoles, que es cuando la mercadería llegó.
    - armados por armado_el en hora argentina: el renglón sale del stock
      cuando se arma, no cuando se pidió.
    - reprocesos, movimientos y remitos por su fecha_operacion declarada.

    Los filtros de vigencia son los mismos de siempre: pedido vigente por
    (cliente, fecha), renglón no anulado, compra recepcionada, movimiento no
    anulado. Un evento que la cuenta no mira tampoco puede aparecer acá
    explicándola.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.nombre, c.cantidad_cajones_real
                FROM compras c JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.articulo_id = %s AND c.estado = 'recepcionado'
                  AND COALESCE((c.procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date,
                               c.fecha_operacion) = %s
                ORDER BY p.nombre
                """,
                (articulo_id, fecha),
            )
            compras = [{"proveedor": f[0], "bultos": float(f[1] or 0)} for f in cursor.fetchall()]

            cursor.execute(
                """
                SELECT id, bultos_tomados, bultos_primera, bultos_segunda, ficha_id, tipo
                FROM reprocesos
                WHERE articulo_id = %s AND anulado_el IS NULL AND fecha_operacion = %s
                ORDER BY id
                """,
                (articulo_id, fecha),
            )
            reprocesos = [
                {"id": f[0], "tomados": float(f[1]), "primera": float(f[2]),
                 "segunda": float(f[3]), "ficha_id": f[4], "tipo": f[5]}
                for f in cursor.fetchall()
            ]

            cursor.execute(
                """
                WITH vigentes AS (
                    -- fecha_operacion SE SELECCIONA, no alcanza con que esté en
                    -- el DISTINCT ON: ahí nombra la columna de `pedidos`, y lo
                    -- que el alias `v` expone es esta lista. El renglón del
                    -- extracto la muestra ("Pedido 28 del 17/09"), así que sin
                    -- ella la consulta no parsea.
                    SELECT DISTINCT ON (cliente_id, fecha_operacion)
                           id, cliente_id, fecha_operacion
                    FROM pedidos WHERE anulado_el IS NULL
                    ORDER BY cliente_id, fecha_operacion, creado_en DESC
                )
                SELECT cl.nombre, r.sucursal, r.ficha_id, r.pedido_id,
                       v.fecha_operacion,
                       SUM(COALESCE(r.cantidad_armada, r.cantidad)) AS bultos
                FROM pedidos_renglones r
                JOIN vigentes v ON v.id = r.pedido_id
                JOIN clientes cl ON cl.id = v.cliente_id
                WHERE r.articulo_id = %s AND r.armado_el IS NOT NULL AND r.anulado_el IS NULL
                  AND (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date = %s
                GROUP BY cl.nombre, r.sucursal, r.ficha_id, r.pedido_id, v.fecha_operacion
                ORDER BY r.pedido_id, r.sucursal
                """,
                (articulo_id, fecha),
            )
            armados = [
                {"cliente": f[0], "sucursal": f[1], "ficha_id": f[2],
                 "pedido_id": f[3], "fecha_pedido": f[4], "bultos": float(f[5])}
                for f in cursor.fetchall()
            ]

            # DE QUÉ PORCIÓN ES ESTE MOVIMIENTO. `ficha_id` viene NO NULO solo
            # cuando la CUENTA lo atribuye a esa ficha, y se decide con las
            # MISMAS DOS CONSTANTES que usa `_SQL_STOCK_PARTIDO`, no con una
            # condición escrita acá. El extracto no puede repartir un evento
            # con un criterio distinto del que reparte el saldo: eso es
            # exactamente lo que rompió el 09/09, con los dos "Sin explicar"
            # saliendo ±15.
            #
            # Y SE HABÍA VUELTO A ROMPER, por la mitad que faltaba: la cuenta
            # leía `m.ficha_id` desde el 10/09 y esto NO LO LEÍA. Una merma de
            # cajas armadas salía restada de la ficha en el saldo y dibujada
            # en sueltos acá. Medido: 10 armadas, se tiran 3, la cuenta dice
            # ficha 7 y el extracto decía `ficha_id` None. Las dos formas de
            # llegar a la ficha van juntas ahora, y ninguna es una condición
            # propia de este archivo.
            #
            # `m.ficha_id` GANA y el reingreso queda de respaldo: son
            # excluyentes por construcción —el CHECK solo deja escribir
            # `ficha_id` en merma y pase, y `pedido_renglon_id` solo en el
            # reingreso— así que el COALESCE no puede elegir mal.
            #
            # El LEFT JOIN no puede duplicar: `pr.id` es la clave primaria.
            cursor.execute(
                f"""
                SELECT m.tipo, m.cantidad, m.motivo, m.destino_rechazo, m.bultos_segunda,
                       COALESCE(
                           CASE WHEN {_SQL_TIPO_TIENE_FICHA_PROPIA} THEN m.ficha_id END,
                           CASE WHEN {_SQL_REINGRESO_ES_DE_LA_FICHA} THEN pr.ficha_id END
                       ) AS ficha_id
                FROM movimientos_stock m
                LEFT JOIN pedidos_renglones pr ON pr.id = m.pedido_renglon_id
                WHERE m.articulo_id = %s AND m.anulado_el IS NULL AND m.fecha_operacion = %s
                ORDER BY m.id
                """,
                (articulo_id, fecha),
            )
            movimientos = [
                {"tipo": f[0], "cantidad": float(f[1]), "motivo": f[2],
                 "destino_rechazo": f[3], "bultos_segunda": float(f[4]) if f[4] is not None else None,
                 "ficha_id": f[5]}
                for f in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT id, bultos FROM remitos_segunda
                WHERE articulo_id = %s AND anulado_el IS NULL AND fecha_operacion = %s
                ORDER BY id
                """,
                (articulo_id, fecha),
            )
            remitos = [{"id": f[0], "bultos": float(f[1])} for f in cursor.fetchall()]

        return {"compras": compras, "reprocesos": reprocesos, "armados": armados,
                "movimientos": movimientos, "remitos": remitos}
    finally:
        conexion.close()


def bultos_esperando_guia_r_por_articulo() -> dict:
    """{articulo_id: {"nombre", "bultos", "mas_viejo"}} de armados SIN LOTE esperando la guía R.

    SE APAGA SOLA, y no por un truco: sale del MISMO rejuego del FIFO que
    la Rentabilidad Real y la pantalla del artículo, y ese rejuego se
    recalcula entero en cada lectura. Cuando entra la guía R —fechada en el
    día que armó— la siguiente corrida cuenta cero. No hay nada persistido
    que limpiar ni botón que apretar.

    Sale de `atribuir_costos_fifo` y NO de una consulta propia: una segunda
    versión de la cuenta se separaría de la pantalla, y el día que difieran
    la alerta va a mandar a mirar donde el problema no está.

    Cuenta BULTOS y no salidas: "faltan 3 guías R" no dice el tamaño, y el
    que decide qué hacer primero mira los bultos. `mas_viejo` es la fecha
    del armado más viejo que sigue esperando.

    Y `mas_nuevo` viene al lado porque la pregunta que se hace el que mira
    este bloque no es cuánto hay: es **si está creciendo**. Una cola de 132
    bultos que empieza y termina el 07/09 es un día que quedó sin cargar; la
    misma cola con el más nuevo de hoy es una costumbre. Los dos números son
    el mismo dato con dos lecturas opuestas, y con uno solo hay que ir a
    buscar el otro — que es la salvaguarda que nadie lee (corolario 19).

    Sale del MISMO recorrido, sin una segunda consulta: el rejuego ya tiene
    la fecha de cada salida en la mano.

    Solo lo que ALGUIEN PUEDE CERRAR, igual que la alerta de las guías R
    incompletas: acá todo lo contado se cierra cargando el papel. El
    `sin_lote` de verdad —salió más de lo que había— no entra: ése no se
    arregla con una guía R y haría que el número no baje nunca.
    """
    from core.costo_real import atribuir_costos_fifo

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            corte = _fecha_corte(cursor)
            # Los candidatos: artículos con armado posterior al corte sobre una
            # ficha CON envase. Sin este recorte habría que rejugar el FIFO de
            # todo el catálogo para contestar por unos pocos.
            cursor.execute(
                """
                SELECT DISTINCT r.articulo_id, a.nombre
                FROM pedidos_renglones r
                JOIN pedidos p ON p.id = r.pedido_id
                JOIN fichas_logistica f ON f.id = r.ficha_id
                JOIN articulos a ON a.id = r.articulo_id
                -- p.anulado_el: un pedido anulado no aporta candidatos. Hoy
                -- no cambia el numero —el conteo sale del rejuego, que ya lo
                -- descarta— pero era el unico lector de pedidos_renglones por
                -- RANGO que no lo filtraba, y un criterio que falta en un
                -- lugar es como empiezan a separarse.
                WHERE p.anulado_el IS NULL
                  AND r.armado_el IS NOT NULL AND r.anulado_el IS NULL
                  AND r.articulo_id IS NOT NULL AND f.envase_id IS NOT NULL
                  AND (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date > %s
                """,
                (corte,),
            )
            # El nombre viene de acá y no lo busca el llamador: sale de
            # `articulos.nombre`, la misma fuente que el resto del módulo, y
            # así el que muestra no necesita una segunda consulta para
            # ponerle nombre a un id.
            nombres = dict(cursor.fetchall())
            ids = list(nombres)
            if not ids:
                return {}

            por_articulo = _entradas_y_salidas_stock_varios(cursor, ids, corte)
    finally:
        conexion.close()

    por_id = {}
    for articulo_id, (entradas, salidas) in por_articulo.items():
        for salida in atribuir_costos_fifo(entradas, salidas):
            esperando = salida["motivos_sin_costo"].get("falta_cargar_guia_r", 0.0)
            if esperando <= 0:
                continue
            fila = por_id.setdefault(
                articulo_id,
                {"nombre": nombres.get(articulo_id, "?"), "bultos": 0.0,
                 "mas_viejo": None, "mas_nuevo": None},
            )
            fila["bultos"] += esperando
            fecha = salida.get("fecha")
            if fecha is not None:
                if fila["mas_viejo"] is None or fecha < fila["mas_viejo"]:
                    fila["mas_viejo"] = fecha
                if fila["mas_nuevo"] is None or fecha > fila["mas_nuevo"]:
                    fila["mas_nuevo"] = fecha
    for fila in por_id.values():
        fila["bultos"] = round(fila["bultos"], 2)
    return por_id


def contar_bultos_esperando_guia_r() -> dict:
    """El TOTAL de lo de arriba, para la alerta. Una cuenta, dos lectores.

    La alerta y el Remanente salen de la misma función a propósito: con dos
    consultas, un día una diría un número y la otra otro, y la alerta
    mandaría a mirar donde el problema no está. Ya nos costó una vez.
    """
    por_articulo = bultos_esperando_guia_r_por_articulo()
    if not por_articulo:
        return {"casos": 0, "mas_viejo": None}
    fechas = [f["mas_viejo"] for f in por_articulo.values() if f["mas_viejo"] is not None]
    # SIN `mas_nuevo`: `guardar_estado_alerta` persiste solo `casos` y
    # `mas_viejo`, así que una clave más acá no la lee nadie — sería el campo
    # sin consecuencia, escrito por mí en el mismo commit que lo agregó a la
    # pantalla, que sí lo muestra. El par de fechas vive donde se mira.
    return {
        "casos": round(sum(f["bultos"] for f in por_articulo.values()), 2),
        "mas_viejo": min(fechas) if fechas else None,
    }


# LOS ARMADOS DE LA VENTANA, con su fecha. La regla de los pedidos VIGENTES
# (un pedido recargado no se anula: deja de ser el vigente) está escrita siete
# veces más en este archivo — no se unifica acá, pero el día que se unifique
# ésta entra en la lista.
_SQL_ARMADOS_DESDE = """
    WITH vigentes AS (
        SELECT DISTINCT ON (cliente_id, fecha_operacion) id
        FROM pedidos WHERE anulado_el IS NULL
        ORDER BY cliente_id, fecha_operacion, creado_en DESC
    )
    SELECT r.articulo_id, a.nombre,
           (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date AS fecha,
           SUM(COALESCE(r.cantidad_armada, r.cantidad)) AS bultos
    FROM pedidos_renglones r
    JOIN vigentes v ON v.id = r.pedido_id
    JOIN articulos a ON a.id = r.articulo_id
    WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id IS NOT NULL
      AND (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date >= %s
    GROUP BY 1, 2, 3
    -- UN ARMADO DE CERO NO ES UNA SALIDA: el renglón existe (se confirmó el
    -- pedido y nada del mail se pierde) pero no salió un bulto, así que ese
    -- día no se armó nada sin tener con qué. Sin esto, un artículo que queda
    -- descubierto suma un caso por cada día que alguien le cargue un renglón
    -- en cero, y el número crece sin que pase nada nuevo.
    HAVING SUM(COALESCE(r.cantidad_armada, r.cantidad)) > 0
"""

# El saldo de CADA artículo a la fecha tope. Se le pega a _sql_sumas_stock, que
# es LA cuenta del stock —las seis patas— en vez de escribirla de nuevo: una
# consulta con menos patas inventa rojos en todo artículo que se mueva por guía
# R, y eso ya costó un número falso (corolario 85).
_SELECT_SALDO_POR_ARTICULO = """
    SELECT a.id,
           COALESCE(e.total, 0) + COALESCE(r.total, 0) + COALESCE(aj.total, 0)
           + COALESCE(rp.entradas, 0) - COALESCE(rp.salidas, 0) - COALESCE(s.total, 0)
    FROM articulos a
    LEFT JOIN entradas e ON e.articulo_id = a.id
    LEFT JOIN salidas s ON s.articulo_id = a.id
    LEFT JOIN reingresos r ON r.articulo_id = a.id
    LEFT JOIN ajustes aj ON aj.articulo_id = a.id
    LEFT JOIN reproc rp ON rp.articulo_id = a.id
"""


def dias_articulo_en_rojo(desde) -> list[dict]:
    """Los días en que se armó un artículo SIN TENER CON QUÉ, a la fecha de ese día.

    LO QUE ESTO VE Y `contar_stock_deposito_negativo` NO: aquella corre sin
    tope de fecha, o sea que mira el saldo de HOY, y un faltante que el ingreso
    del día siguiente cubre no dispara nunca. Medido con el caso de Arándano
    contra el esquema real —12 bultos el 16, armado de 30 el 17, 18 más el 18—:

        al 17/09  −18        HOY  0        la alerta de hoy: 0

    Son DOS preguntas y las dos sirven: "hoy tengo artículos en rojo" es
    accionable ahora, y ésta es "qué días salió mercadería que nada cubría".

    UNA CONSULTA POR FECHA DE ARMADO, y no una sola que rejuegue todo: el saldo
    a cada fecha sale de `_sql_sumas_stock`, que es la cuenta real del stock. La
    ventana son siete días, así que son a lo sumo ocho consultas por recálculo
    —uno cada seis horas— y cada una es la del Remanente, que corre en cada
    carga de esa pantalla. Reescribirla en una sola pasada sería una segunda
    versión de la cuenta, que es exactamente lo que dio 192 donde había 45.

    Devuelve una fila por (artículo, día) con `falta` = cuánto faltaba ESE día.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # EL PISO NUNCA CRUZA EL CORTE, y hoy no hace falta: la ventana son
            # siete días y el corte está a trece. Está puesto porque siete es
            # una constante que alguien va a querer mover, y el día que la
            # mueva más allá del corte esto empieza a contar ARTEFACTOS sin que
            # nada avise: `corte2_frutamax.sql` fecha los `stock_inicial` en
            # `fecha_operacion = corte`, así que TODO armado anterior al corte
            # queda descubierto por construcción — no porque haya faltado algo.
            # Medido con el caso plantado: un artículo cuya única entrada es su
            # stock inicial, armado el 29/08, sale rojo por 40 bultos.
            #
            # `corte + 1` y no `corte`: la foto del corte se toma a la tarde,
            # así que ya viene neta del trabajo de ese día y contar el armado
            # del propio corte lo resta dos veces (corolario 12). Medido: con
            # el día del corte adentro, 1 caso pasa a 2 y 18 bultos a 43.
            piso = max(desde, _fecha_corte(cursor) + timedelta(days=1))
            cursor.execute(_SQL_ARMADOS_DESDE, (piso,))
            armados = cursor.fetchall()
            saldos: dict = {}
            for fecha in sorted({fila[2] for fila in armados}):
                cursor.execute(
                    _sql_sumas_stock(por_articulo=False) + _SELECT_SALDO_POR_ARTICULO,
                    (fecha,),
                )
                saldos[fecha] = {fila[0]: float(fila[1]) for fila in cursor.fetchall()}
            filas = []
            for articulo_id, nombre, fecha, bultos in armados:
                saldo = saldos[fecha].get(articulo_id, 0.0)
                if saldo < 0:
                    filas.append({
                        "articulo": nombre, "fecha": fecha,
                        "falta": -saldo, "armado": float(bultos),
                    })
            filas.sort(key=lambda f: (f["fecha"], f["articulo"]))
            return filas
    finally:
        conexion.close()


def contar_dias_articulo_en_rojo(desde) -> dict:
    """El conteo de `dias_articulo_en_rojo`, para el registro de alertas.

    `mas_viejo` y no otro nombre: es la clave que lee `normalizar_conteo`, y
    estrenar uno propio la dejaría afuera sin que nada avise — el banner
    mostraría el caso sin fecha.
    """
    filas = dias_articulo_en_rojo(desde)
    return {
        "casos": len(filas),
        "articulos": len({f["articulo"] for f in filas}),
        "bultos": sum(f["falta"] for f in filas),
        "mas_viejo": min((f["fecha"] for f in filas), default=None),
    }


def contar_stock_deposito_negativo() -> int:
    """Auditoría: cuántos artículos del depósito tienen stock por debajo de cero.

    Negativo = salió más de lo que entró: salidas sin lote que un
    reproceso o un ajuste tienen que explicar. No es un error del
    sistema — es la señal para el dueño. Misma cuenta que
    stock_deposito_por_articulo(), solo el conteo; los índices parciales
    *_stock_idx cubren los SUM.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                _sql_sumas_stock(por_articulo=False)
                + """
                SELECT COUNT(*) FROM articulos a
                LEFT JOIN entradas e ON e.articulo_id = a.id
                LEFT JOIN salidas s ON s.articulo_id = a.id
                LEFT JOIN reingresos r ON r.articulo_id = a.id
                LEFT JOIN ajustes aj ON aj.articulo_id = a.id
                LEFT JOIN reproc rp ON rp.articulo_id = a.id
                WHERE COALESCE(e.total, 0) + COALESCE(r.total, 0)
                    + COALESCE(aj.total, 0) + COALESCE(rp.entradas, 0)
                    - COALESCE(rp.salidas, 0) - COALESCE(s.total, 0) < 0
                """,
                (None,),
            )
            return int(cursor.fetchone()[0])
    finally:
        conexion.close()


# --- Reproceso (Guías R) ---


def asignar_ficha_a_reproceso(reproceso_id: int, ficha_id: int | None) -> None:
    """Completa (o corrige) a qué ficha fueron las cajas de primera de una guía R ya cargada.

    Solo toca ficha_id: los consumos y el costo quedaron congelados
    cuando se cargó la guía y no se recalculan — asignar la ficha es
    decir a qué producto de venta fueron esas cajas, no rehacer el FIFO.

    La ficha tiene que ser DEL MISMO ARTÍCULO que la guía. No es
    burocracia: el stock de cajas de una ficha se cuenta como
    "reprocesadas de esa ficha menos salidas de esa ficha", así que una
    ficha de otro artículo inventaría cajas que no existen y el Cotejo
    mostraría un rojo imposible de explicar.

    Y TIENE QUE SER DEL MISMO CLIENTE, salvo que la guía no tenga cliente
    (las viejas, anteriores al dato: ahí no hay contra qué comparar y se
    acepta cualquiera del artículo, o quedarían trabadas para siempre).

    Esa guarda va ACÁ, donde se ESCRIBE, y no alcanza con que la pantalla
    no lo ofrezca: es el mismo hallazgo del cajón con envase, donde un
    formulario armado a mano entraba sin ver el cartel. Medido el 11/09
    sobre Frutamax antes de cerrarla: 0 cruces en 198 guías comparables
    (`sin_cliente_no_se_juzga` en 0, así que las 198 se compararon de
    verdad). El caso no existe, y la pantalla de armar nunca lo permitió
    —ahí el selector es por cliente Y artículo—: era la misma regla en
    dos pantallas con dos durezas, y la floja era la de corregir.

    Una guía anulada no se asigna: ya no cuenta para nada.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT articulo_id, cliente_id, anulado_el IS NOT NULL FROM reprocesos WHERE id = %s",
                (reproceso_id,),
            )
            # SIN agregado a propósito: `fetchone() is None` sobre un
            # `count(*)` nunca es None y la guarda no distinguiría "no hay"
            # de "hay cero" (corolario 27).
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa guía R no existe.")
            articulo_id, cliente_id, anulada = fila
            if anulada:
                raise ValueError("Esa guía R está anulada: no se le asigna ficha.")

            if ficha_id is not None:
                cursor.execute(
                    "SELECT articulo_id, cliente_id FROM fichas_logistica WHERE id = %s",
                    (ficha_id,),
                )
                ficha = cursor.fetchone()
                if ficha is None:
                    raise ValueError("Esa ficha no existe.")
                if ficha[0] != articulo_id:
                    raise ValueError("Esa ficha es de otro artículo: no puede ser la de esta guía R.")
                if cliente_id is not None and ficha[1] != cliente_id:
                    raise ValueError(
                        "Esa ficha es de otro cliente: esta guía R se armó para otro."
                    )

            # Y EL ENVASE VIAJA CON LA FICHA. Una guía R sin asignar no tiene
            # de dónde derivar en qué caja se armó, así que queda "sin
            # declarar" y el stock de cajas la muestra como hueco. El momento
            # en que eso se puede contestar es justo éste: asignar la ficha es
            # lo que dice cuál era el envase. Si no se completara acá, el
            # hueco quedaría abierto para siempre sin que nada lo señale —
            # que es el modo de falla de todas las columnas que este archivo
            # persigue.
            #
            # Y CON LA FICHA PUESTA SIEMPRE SE PUEDE DERIVAR: la caja sale
            # de la ficha. Por eso asignar la ficha es el arreglo COMPLETO de
            # una guía sin asignar, y no hace falta ninguna otra puerta que
            # pregunte en qué caja quedó — hubo una entre el 17 y el 18/09 y
            # dejaba elegir una caja distinta de la que la ficha declara.
            lleva_caja, envase_de_la_caja = _envase_de_esta_guia(cursor, ficha_id)
            cursor.execute(
                """
                UPDATE reprocesos
                   SET ficha_id = %s, lleva_caja_nuestra = %s, envase_id = %s
                 WHERE id = %s
                """,
                (ficha_id, lleva_caja, envase_de_la_caja, reproceso_id),
            )
        conexion.commit()
    finally:
        conexion.close()


class StockInsuficienteParaReproceso(Exception):
    """El freno: a la fecha del reproceso los lotes no llegaban a lo declarado.

    El reproceso es 100% o nada. No hay salida de escape y no hay `sin_lote`:
    lo que no se puede explicar con lotes reales no se guarda, porque un
    consumo sin lote congela un costo incompleto que después no se corrige
    nunca (no hay compra a la que irle a buscar el importe).

    Lleva encima TODO lo que la pantalla necesita para explicarlo sin volver
    a preguntarle nada a la base: cuánto declaró, cuánto había ese día, y el
    detalle por lote.
    """

    def __init__(self, declarado: float, disponible: float, lotes: list[dict],
                 tomado_hoy: list[dict] | None = None):
        self.declarado = declarado
        self.disponible = disponible
        self.lotes = lotes
        # QUIÉN SE LLEVÓ LO DE HOY, para que la pared no sea muda. Desde el
        # 16/09 el freno descuenta lo que otra guía R del mismo día ya tomó,
        # así que puede trabar un día en que el operario VE los cajones en el
        # piso. Un "no hay stock" en esa situación es la clase de cartel que
        # se aprende a esquivar; nombrar la guía de hoy le dice exactamente
        # qué mirar.
        self.tomado_hoy = list(tomado_hoy or ())
        super().__init__(f"El stock a esa fecha no alcanza: declaró {declarado} y había {disponible}.")



def _lo_tomado_hoy(cursor, articulo_id: int, fecha_operacion, excepto: int | None = None) -> list[dict]:
    """Lo que las guías R YA CARGADAS de este artículo y este día se llevaron de cada lote.

    `excepto` deja afuera UNA guía, y lo usa `cambiar_fecha_de_reproceso`:
    al mover una guía a otro día hay que preguntarse si habría entrado ESE
    día, y una guía que se descuenta a sí misma se rebota siempre. Es un
    parámetro y no una segunda consulta porque la pregunta es la misma —qué
    se llevó el día— y escrita dos veces se separa: el que lee dejaría de
    encontrar lo que el que escribe guardó.

    Sale del documento congelado (`reprocesos_consumos`) y no de un
    rejuego, y es a propósito: lo que hay que restar no es lo que el FIFO
    diría hoy, sino lo que esas guías DECLARARON haberse llevado. Es el
    mismo número que quedó escrito y que después se lee como costo.

    Solo guías R, y no los armados de pedidos. Un armado que deja una
    ficha en negativo es comportamiento deliberado del sistema —la ficha
    queda en el aire hasta que se cargue la guía R que la explica— así que
    meterlos acá rebotaría cargas por un motivo que el sistema permite.

    Los consumos 'sin_lote' viejos quedan afuera: no apuntan a ningún lote,
    así que no hay a qué descontárselos.
    """
    cursor.execute(
        """
        SELECT rc.reproceso_id, rc.origen, rc.origen_id, rc.bultos
        FROM reprocesos_consumos rc
        JOIN reprocesos r ON r.id = rc.reproceso_id
        WHERE r.articulo_id = %s AND r.fecha_operacion = %s
          AND r.anulado_el IS NULL AND rc.origen <> 'sin_lote'
          AND (%s::bigint IS NULL OR r.id <> %s)
        ORDER BY rc.reproceso_id
        """,
        (articulo_id, fecha_operacion, excepto, excepto),
    )
    return [
        {"reproceso_id": fila[0], "origen": fila[1], "origen_id": fila[2], "bultos": float(fila[3])}
        for fila in cursor.fetchall()
    ]


class RepartoDesactualizado(Exception):
    """El reparto que llegó de la pantalla ya no se puede cumplir contra los lotes de ahora."""


class ReprocesoAnteriorAlCorte(Exception):
    """La fecha del reproceso cae antes del corte del modelo nuevo, donde el FIFO nuevo no rige."""

    def __init__(self, fecha, corte):
        self.fecha = fecha
        self.corte = corte
        super().__init__(f"La fecha del reproceso ({fecha}) es anterior al corte ({corte}).")


def contar_guias_r_afectadas_por_fecha(articulo_id: int, fecha) -> int:
    """Cuántas guías R quedarían con el reparto desactualizado si se carga una con ESTA fecha.

    Sirve para AVISAR antes de escribir, nunca para trabar: es el mismo
    molde que `contar_senas_afectadas_por_valor`. La fecha vieja es
    legítima —recién ahora se carga lo que pasó el lunes—, pero mete un
    lote ANTES de salidas ya repartidas, y los consumos de las guías R
    posteriores están congelados en `reprocesos_consumos` y no se
    recalculan nunca. El que carga tiene que enterarse ANTES.

    **La plata no se mueve** y por eso el aviso lo dice con todas las
    letras: `costo_total` y `costo_por_bulto_primera` quedan congelados
    al cargar, y el FIFO vivo usa ese mismo número como costo del lote de
    primera. Lo que puede dejar de coincidir es la trazabilidad: de qué
    lote dice cada guía R que salió cada bulto.

    `>=` y no `>`: el recorte de `reparto_para_reproceso` toma las
    entradas HASTA LA FECHA INCLUSIVE, así que una guía R del mismo día
    también se repartiría contra el lote nuevo.

    Solo las 'normal': la inicial produce sin consumir, no tiene ninguna
    fila en `reprocesos_consumos` y no hay reparto que se le desactualice.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM reprocesos
                WHERE articulo_id = %s
                  AND anulado_el IS NULL
                  AND tipo = 'normal'
                  AND fecha_operacion >= %s
                """,
                (articulo_id, fecha),
            )
            return cursor.fetchone()[0]
    finally:
        conexion.close()


def lotes_para_reproceso(articulo_id: int, fecha) -> dict:
    """Los lotes contra los que se mide un reproceso de esa fecha, y qué quedaba en cada uno.

    Es la consulta que alimenta el desglose de la pantalla. Corre el MISMO
    `reparto_para_reproceso` que después usan el freno y la escritura dentro
    de `crear_reproceso`: el operario tiene que ver exactamente los lotes que
    el guardado va a consumir, no una foto parecida.

    Devuelve lo mismo que repartir_fifo: {"lotes", "sin_lote", "stock"}, con
    los lotes de más viejo a más nuevo y su restante a esa fecha, MÁS
    `tomado_hoy` — lo que las guías R ya cargadas de ese día se llevaron.

    Ese último viaja porque el freno de `crear_reproceso` lo descuenta desde
    el 16/09, y el aviso que la pantalla da antes de Guardar es el mismo
    freno adelantado: si acá no llegara, la pantalla diría que alcanza y el
    server rebotaría al apretar. La regla está escrita una vez
    (`descontar_lo_tomado_hoy`) y los dos la aplican sobre el mismo dato.

    Y `sin_lote_antes`: cuántos bultos de este artículo ya habían salido SIN
    QUE NINGÚN LOTE LOS CUBRA al cerrar el día ANTERIOR a la fecha elegida.
    Pedido del dueño el 19/09, y es la mitad preventiva de poder refechar una
    guía: ese número es el síntoma de que unas cajas se armaron antes y la
    guía que las explica todavía no está — o está con la fecha del día que se
    cargó. Verlo MIENTRAS se elige la fecha es lo que evita fabricar el
    problema otra vez.

    Sale de `reparto_a_la_fecha` sobre las MISMAS entradas y salidas que ya
    se leyeron —ni una consulta más— y con el mismo recorte que el resto del
    módulo: escribir acá una segunda versión de esa cuenta es exactamente lo
    que el corolario 85 dice que devuelve números plausibles y falsos.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            entradas, salidas = _entradas_y_salidas_stock(cursor, articulo_id)
            tomado_hoy = _lo_tomado_hoy(cursor, articulo_id, fecha)
    finally:
        conexion.close()
    from core.stock import reparto_a_la_fecha, reparto_para_reproceso, salidas_para_reparto

    salidas_fifo = salidas_para_reparto(salidas)
    reparto = reparto_para_reproceso(entradas, salidas_fifo, fecha)
    reparto["tomado_hoy"] = tomado_hoy
    # La foto al CERRAR el día anterior: las dos puntas recortadas ahí, que
    # es lo que hace que el número signifique "antes de este día" y no "antes
    # o durante". Una guía del mismo día ya la está por cargar.
    reparto["sin_lote_antes"] = reparto_a_la_fecha(
        entradas, salidas_fifo, fecha - timedelta(days=1)
    )["sin_lote"]
    return reparto


def crear_reproceso(
    articulo_id: int,
    bultos_tomados: float,
    bultos_primera: float,
    bultos_segunda: float,
    bultos_merma: float,
    fecha_operacion,
    cliente_id: int | None = None,
    ficha_id: int | None = None,
    reparto: list[dict] | None = None,

) -> int:
    """Carga una guía R: el SERVER frena, reparte y congela consumos y costo. Devuelve el número de guía.

    LOS DOS FRENOS VIVEN ACÁ, y acá solo. Es el único camino que escribe
    una guía R normal, así que ponerlos en la ruta sería escribir la regla
    dos veces y dejar que se separen. Son el de STOCK (lo de abajo) y el
    de FECHA: nada antes del corte, leído de corte_modelo — antes de esa
    fecha el FIFO nuevo no rige, y una guía R fechada ahí levanta
    ReprocesoAnteriorAlCorte sin escribir nada.

    Si a la fecha del reproceso los lotes no llegan a cubrir
    lo declarado, levanta StockInsuficienteParaReproceso y NO escribe nada:
    el reproceso es 100% o nada, y ya no existe el consumo 'sin_lote' por
    esta vía —el que quedaba congelaba un costo incompleto para siempre.

    `reparto` es lo que el operario editó en el desglose: [{"tipo_lote",
    "origen_id", "bultos"}]. None = no tocó nada y va la propuesta FIFO (del
    más viejo primero), que es el caso normal. Se revalida siempre contra
    los lotes frescos de esta misma transacción; si ya no se puede cumplir,
    levanta RepartoDesactualizado y tampoco escribe.

    El costo por bulto se congela del importe de la compra de cada lote (o
    del costo de primera si el lote es de otra guía R); un lote sin precio
    deja el consumo sin costo, y con UN consumo sin costo la guía queda con
    costo_total NULL = "costo incompleto" — nunca se promedia con números
    inventados. Todo en UNA transacción.

    ficha_id: a qué ficha fueron las cajas de primera. None = SIN
    ASIGNAR, y en la pantalla eso se elige a propósito, no se llega por
    no contestar. No se puede derivar de (cliente, artículo): un cliente
    puede tener varias fichas del mismo artículo — pide Banana Bolivia y
    recibe Banana Ecuador — así que esa derivación es ambigua por diseño
    y lo va a ser siempre.

    EN QUÉ CAJA quedó armada no se pregunta: sale de la ficha, y lo escribe
    `_crear_reproceso` para los dos caminos a la vez.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            reproceso_id = _crear_reproceso(
                cursor,
                articulo_id=articulo_id,
                bultos_tomados=bultos_tomados,
                bultos_primera=bultos_primera,
                bultos_segunda=bultos_segunda,
                bultos_merma=bultos_merma,
                fecha_operacion=fecha_operacion,
                cliente_id=cliente_id,
                ficha_id=ficha_id,
                reparto=reparto,
            )
        conexion.commit()
        return reproceso_id
    finally:
        conexion.close()


def _envase_de_esta_guia(cursor, ficha_id) -> tuple:
    """(lleva_caja_nuestra, envase_id) de una guía R que se está por escribir.

    La ficha se LEE ACÁ ADENTRO, en la misma transacción que el INSERT, y no
    se recibe de la ruta: si la ruta la pasara, el día que aparezca un tercer
    llamador de `_crear_reproceso` la columna se escribiría en NULL y la
    pantalla volvería a mostrar una sola cosa sin que nada se vea roto.

    NO PREGUNTA NADA Y NO RECIBE NINGUNA RESPUESTA, y eso es una corrección
    del 18/09. Entre el 17 y el 18 recibió un `envase_declarado` que ganaba
    sobre la derivación, porque la regla trataba la ficha VARIABLE como un
    caso a preguntar. Era falso: ese flag decide si se usa una caja nuestra,
    no cuál, y la caja sale siempre de la ficha (ver
    `envase_derivado_de_la_ficha`). Preguntarlo dejaba elegir una caja
    distinta de la que la ficha declara, que es peor que no preguntar.

    Con una guía SIN FICHA quedan las dos en NULL: eso es "no se pudo
    derivar", y NO es cero consumido — un cero se sumaría al total como si
    fuera un hecho. Se arregla asignándole la ficha, que vuelve a derivar.
    """
    ficha = None
    if ficha_id is not None:
        # SIN agregado: `fetchone() is None` sobre un `count(*)` nunca es None.
        cursor.execute(
            "SELECT envase_id FROM fichas_logistica WHERE id = %s",
            (ficha_id,),
        )
        fila = cursor.fetchone()
        if fila is not None:
            ficha = {"envase_id": fila[0]}

    lleva, envase_id, _ = envase_derivado_de_la_ficha(ficha)
    return lleva, envase_id


def _lotes_de_reproceso_a_su_fecha(
    cursor, articulo_id: int, fecha_operacion, bultos_tomados, excepto: int | None = None
) -> list[dict]:
    """Los lotes contra los que se mide una guía R de ESA fecha, con los dos frenos aplicados.

    Devuelve la lista ENTERA de lotes permitidos a esa fecha —la misma que
    ve el operario en el desglose— y levanta:

    - `ReprocesoAnteriorAlCorte` si la fecha cae antes del corte. Antes del
      corte los datos están declarados no confiables y fuera del alcance del
      FIFO nuevo: una guía R fechada ahí metería el FIFO nuevo adentro de lo
      que el corte cerró. El corte sale de `corte_modelo` y NO de una
      constante: se mueve cada vez que se hace un corte nuevo, y un 31/08
      clavado en el código quedaría mintiendo el lunes siguiente.
    - `StockInsuficienteParaReproceso` si lo declarado no entra.

    EXISTE PORQUE HAY DOS PREGUNTAS IDÉNTICAS EN DOS MOMENTOS: la de
    `_crear_reproceso` ("¿entra hoy?") y la de `cambiar_fecha_de_reproceso`
    ("¿habría entrado ese otro día?"). Son la misma y por eso es una sola
    función — la copia que se separara dejaría que una guía entrara por la
    puerta de la corrección donde la de la carga la rebota.

    `excepto` deja una guía afuera del descuento del día, y lo usa el que
    mueve la fecha: una guía que se descuenta a sí misma se rebota siempre.

    EL FRENO CUENTA EL MISMO DÍA; EL REPARTO NO. Son dos preguntas distintas
    y hasta el 16/09 las contestaba la misma lista. El recorte asimétrico de
    `reparto_para_reproceso` contesta "¿qué lotes había ese día?", y para eso
    está bien que no descuente las salidas del día: adentro de un día no hay
    orden que afirmar. El freno pregunta otra cosa —"¿cuánto se llevó ya el
    día?"— y ESA no necesita orden: 30 y 26 no entran en 40 se haya cargado
    primero cualquiera de las dos. Sin esto, cada guía R del día veía el lote
    entero y de uno de 40 salieron 56 (56 lotes, 472 bultos medidos).

    Se descuenta SOLO para el freno: lo que se devuelve son los lotes
    ENTEROS, que es lo que usan la propuesta y la validación del reparto, así
    que el desglose que vio el operario no cambia y el rebote queda donde la
    suma ya no entra.
    """
    from core.stock import (
        SALIDA_REPROCESO,
        bultos_en_los_lotes,
        descontar_lo_tomado_hoy,
        lotes_permitidos,
        reparto_para_reproceso,
        salidas_para_reparto,
    )

    corte = _fecha_corte(cursor)
    if fecha_operacion < corte:
        raise ReprocesoAnteriorAlCorte(fecha_operacion, corte)

    entradas, salidas = _entradas_y_salidas_stock(cursor, articulo_id, corte)
    # Los lotes A LA FECHA DEL REPROCESO, con el recorte asimétrico de
    # reparto_para_reproceso. El freno, el desglose que vio el operario y la
    # escritura miran la MISMA lista: si midieran contra listas distintas, la
    # pantalla aprobaría un reparto que después no se puede cumplir.
    a_la_fecha = reparto_para_reproceso(entradas, salidas_para_reparto(salidas), fecha_operacion)
    # LA PARED (pieza 2 de E5): una guía R no puede costearse contra una caja
    # ya armada. El reparto de arriba sigue siendo la foto completa —los
    # armados tienen que poder haberse comido esas cajas— y lo que se recorta
    # es lo que ESTA salida puede tomar. Filtrar antes del reparto sería otra
    # cosa: le devolvería a los cajones las salidas que comieron cajas.
    lotes = lotes_permitidos(a_la_fecha["lotes"], SALIDA_REPROCESO)

    tomado_hoy = _lo_tomado_hoy(cursor, articulo_id, fecha_operacion, excepto=excepto)
    disponible = bultos_en_los_lotes(descontar_lo_tomado_hoy(lotes, tomado_hoy))
    if round(float(bultos_tomados) - disponible, 2) > 0:
        # Los lotes que viajan son los ENTEROS y no los netos: la pared dice
        # "lo que había ese día", igual que el desglose, y lo que el día ya se
        # llevó va aparte. Netos, el operario leería un lote en 10 sin nada
        # que explique de dónde salió ese 10.
        raise StockInsuficienteParaReproceso(
            float(bultos_tomados), disponible, lotes, tomado_hoy
        )
    return lotes


def _crear_reproceso(
    cursor,
    articulo_id: int,
    bultos_tomados: float,
    bultos_primera: float,
    bultos_segunda: float,
    bultos_merma: float,
    fecha_operacion,
    cliente_id: int | None = None,
    ficha_id: int | None = None,
    reparto: list[dict] | None = None,
    tipo: str = "normal",
    compra_origen_id: int | None = None,
) -> int:
    """El NUCLEO de la guia R, con el cursor abierto. Los dos frenos viven aca.

    Existe porque hay DOS caminos que cargan una guia R normal y los dos
    tienen que frenar igual: `crear_reproceso`, que abre su propia conexion,
    y `_recepcionar_compra`, que carga la guia R en origen en la MISMA
    transaccion que la recepcion. Copiar el cuerpo seria la regla escrita dos
    veces, con los dos frenos adentro — y las dos copias se separan sin que
    nadie lo note.

    `tipo` y `compra_origen_id` los usa SOLO el camino en origen. El CHECK
    de la base (db/compra_en_caja_nuestra_2c_uno_a_uno.sql) es el que exige
    que esa guia sea uno a uno; aca no se repite.
    """
    from core.stock import (
        SALIDA_REPROCESO,
        origen_de_consumo,
        propuesta_fifo,
        validar_reparto_declarado,
    )

    # LOS DOS FRENOS —el de la fecha y el del stock— y la lista de lotes
    # contra la que se escribe. Viven en `_lotes_de_reproceso_a_su_fecha`
    # desde el 19/09, porque el que MUEVE la fecha de una guía ya cargada
    # tiene que preguntar exactamente lo mismo: "¿habría entrado ese día?".
    # Escrito dos veces, la copia que se separe dejaría pasar por una puerta
    # lo que la otra rechaza.
    lotes = _lotes_de_reproceso_a_su_fecha(cursor, articulo_id, fecha_operacion, bultos_tomados)

    # EN QUÉ CAJA se armó esta primera. SALE DE LA FICHA y lo resuelve el
    # SERVER: no hay nada que preguntarle a nadie, porque no se puede armar en
    # otra caja que la de la ficha. Escribirlo acá y no en la ruta es lo que
    # hace que los DOS caminos que crean una guía R —la normal y la de la
    # compra que vino armada— salgan con el dato puesto: el que falta, por
    # definición, no nombra la columna.
    lleva_caja, envase_de_la_caja = _envase_de_esta_guia(cursor, ficha_id)

    editados = False
    if reparto is None:
        declarado = propuesta_fifo(lotes, bultos_tomados, SALIDA_REPROCESO)
    else:
        motivo = validar_reparto_declarado(lotes, bultos_tomados, reparto, SALIDA_REPROCESO)
        if motivo is not None:
            raise RepartoDesactualizado(motivo)
        declarado = [fila for fila in reparto if float(fila.get("bultos") or 0) > 0]
        # `consumos_editados` contesta "¿el reparto lo eligió una PERSONA en
        # vez del sistema?", y la pantalla lo muestra para que un costo que no
        # eligió el sistema se pueda distinguir. En la guía EN ORIGEN el
        # reparto lo arma el server —dirigido a la compra que la generó— así
        # que difiere del FIFO SIEMPRE y por construcción: marcarla como
        # editada le diría al que la lee que alguien la tocó a mano, que es
        # falso. No es una excepción al cálculo: es que la pregunta no aplica
        # cuando no hubo operario.
        editados = tipo == "normal" and declarado != propuesta_fifo(lotes, bultos_tomados, SALIDA_REPROCESO)

    por_lote = {(lote["tipo_lote"], lote["origen_id"]): lote for lote in lotes}
    consumos = []
    for fila in declarado:
        lote = por_lote[(fila["tipo_lote"], fila["origen_id"])]
        origen = origen_de_consumo(lote["tipo_lote"])
        consumos.append(
            {
                "origen": origen,
                "compra_id": lote["origen_id"] if origen == "compra" else None,
                "origen_id": lote["origen_id"],
                "bultos": float(fila["bultos"]),
                "costo_por_bulto": float(lote["costo_bulto"]) if lote["costo_bulto"] is not None else None,
            }
        )

    costo_total = None
    costo_por_bulto_primera = None
    if all(c["costo_por_bulto"] is not None for c in consumos):
        costo_total = round(sum(c["bultos"] * c["costo_por_bulto"] for c in consumos), 2)
        if float(bultos_primera) > 0:
            # TODO el costo va a la primera: segunda y merma valen cero.
            costo_por_bulto_primera = round(costo_total / float(bultos_primera), 2)

    cursor.execute(
        """
        INSERT INTO reprocesos
            (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
             bultos_segunda, bultos_merma, costo_total, costo_por_bulto_primera,
             cliente_id, ficha_id, consumos_editados, tipo, compra_origen_id,
             lleva_caja_nuestra, envase_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
         bultos_segunda, bultos_merma, costo_total, costo_por_bulto_primera,
         cliente_id, ficha_id, editados, tipo, compra_origen_id,
         lleva_caja, envase_de_la_caja),
    )
    reproceso_id = cursor.fetchone()[0]
    for c in consumos:
        cursor.execute(
            """
            INSERT INTO reprocesos_consumos
                (reproceso_id, origen, compra_id, origen_id, bultos, costo_por_bulto)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (reproceso_id, c["origen"], c["compra_id"], c["origen_id"],
             c["bultos"], c["costo_por_bulto"]),
        )
    return reproceso_id


def cambiar_fecha_de_reproceso(reproceso_id: int, fecha_nueva) -> dict:
    """Mueve la fecha de una guía R ya cargada. Devuelve {"articulo_id", "fecha_vieja", "fecha_nueva"}.

    EL PROBLEMA QUE RESUELVE, y es del dueño (19/09): la guía se fecha el
    día que se CARGA y no el día que se ARMÓ, así que no cubre las salidas
    que la preceden y esos bultos quedan "sin lote" para siempre. Hasta hoy
    la única salida era anular y recargar — "es la tercera vez esta semana
    que algo se arregla así".

    NO SE RECALCULA NADA. `reprocesos_consumos` es un documento congelado y
    sigue diciendo de qué lote salió cada bulto, con su costo. Lo único que
    se mueve es CUÁNDO ocurrió, que es lo que decide qué salidas puede
    cubrir esa primera en el FIFO vivo — y como el stock se rejuega en cada
    lectura, con eso alcanza: no hay una segunda columna que poner al día
    (corolario 80).

    LAS GUARDAS SON LAS DE LA CARGA, no unas propias. Se ESCRIBE primero y
    se valida después, adentro de la misma transacción: así lo que se
    pregunta es literalmente "¿esta guía habría entrado si se hubiera
    cargado ese día?", con la guía ya puesta ahí y su propia toma fuera del
    recorte. Si la respuesta es no, la excepción sale y no se commitea nada.

    Lo que puede levantar, y todas son de `_lotes_de_reproceso_a_su_fecha`
    o de `validar_reparto_declarado`, o sea las mismas que rebotan al
    cargar:

    - `ValueError`: no existe, está anulada, o no es una guía 'normal'.
    - `ReprocesoAnteriorAlCorte`: la fecha cae antes del corte.
    - `StockInsuficienteParaReproceso`: ese día no había con qué.
    - `RepartoDesactualizado`: alguno de los lotes que la guía declaró
      HABER CONSUMIDO todavía no existía ese día, o ya no llegaba. Es el
      caso que el freno del total no puede ver: la suma entra y el lote
      nombrado es del futuro.

    Las 'inicial' y las 'en_origen' NO se mueven, y no es simetría: la
    inicial ES la foto del corte y está fechada ahí por definición, y la
    de origen es uno a uno con la recepción de su compra —moverla sola la
    despegaría del hecho que la generó—. Corregir esa fecha es corregir la
    recepción, que tiene su propia pantalla.
    """
    from core.stock import SALIDA_REPROCESO, origen_de_consumo, validar_reparto_declarado

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # SIN AGREGADO, para que `fila is None` signifique "no existe":
            # un `count(*)` devuelve (0,) y la guarda no dispararía nunca.
            cursor.execute(
                """
                SELECT articulo_id, fecha_operacion, bultos_tomados, tipo, anulado_el
                FROM reprocesos WHERE id = %s FOR UPDATE
                """,
                (reproceso_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa guía R no existe.")
            articulo_id, fecha_vieja, bultos_tomados, tipo, anulado_el = fila
            if anulado_el is not None:
                raise ValueError("Esa guía R está anulada: no se le puede cambiar la fecha.")
            if tipo != "normal":
                raise ValueError(
                    "Esa guía R no se puede refechar: la inicial es la foto del corte y la de "
                    "origen va con la fecha de su recepción."
                )
            if fecha_nueva == fecha_vieja:
                return {"articulo_id": articulo_id, "fecha_vieja": fecha_vieja,
                        "fecha_nueva": fecha_nueva}

            cursor.execute(
                "UPDATE reprocesos SET fecha_operacion = %s WHERE id = %s",
                (fecha_nueva, reproceso_id),
            )
            # Con la guía YA en la fecha nueva: su propia toma queda fuera del
            # recorte (las salidas se cortan al día anterior) y su propia
            # primera es un lote 'reproceso', que `lotes_permitidos` le
            # prohíbe a una guía R. O sea que no puede costearse a sí misma
            # por ninguno de los dos lados.
            lotes = _lotes_de_reproceso_a_su_fecha(
                cursor, articulo_id, fecha_nueva, bultos_tomados, excepto=reproceso_id
            )

            # Y LOS CONSUMOS CONGELADOS TIENEN QUE SEGUIR SIENDO POSIBLES.
            # El freno de arriba mira el TOTAL y esto mira los lotes POR
            # NOMBRE: la suma puede entrar y el lote que la guía declaró
            # puede ser de un día posterior al nuevo. Sin esto quedaría un
            # documento apuntando a un lote del futuro, que es la misma
            # trazabilidad rota que esta pantalla viene a arreglar.
            cursor.execute(
                """
                SELECT origen, origen_id, bultos FROM reprocesos_consumos
                WHERE reproceso_id = %s AND origen <> 'sin_lote'
                """,
                (reproceso_id,),
            )
            consumos = cursor.fetchall()
            # El tipo_lote se busca por el MISMO camino que usa
            # `descontar_lo_tomado_hoy` —de lote a origen, nunca al revés—
            # para no estrenar una tabla inversa que se separe de la de ida.
            tipo_por_origen = {
                (origen_de_consumo(l["tipo_lote"]), l["origen_id"]): l["tipo_lote"]
                for l in lotes
            }
            declarado = [
                {"tipo_lote": tipo_por_origen.get((origen, origen_id)),
                 "origen_id": origen_id, "bultos": float(bultos)}
                for origen, origen_id, bultos in consumos
            ]
            # El TOTAL que se le pasa es la suma de los propios consumos, así
            # que la rama del "no da los bultos que declaraste" NO PUEDE
            # fallar acá — y se dice para que nadie la lea como verificada
            # (corolario 41: una vuelta completa se ve igual que una lectura).
            # Lo que esta llamada sí compra es la revisión LOTE POR LOTE:
            # que cada uno exista a la fecha nueva, no esté prohibido y
            # tenga restante. El total ya lo miró el freno de arriba, que es
            # de donde tiene que salir.
            #
            # Y la suma NO se compara contra `bultos_tomados` a propósito:
            # las guías viejas pueden tener un consumo 'sin_lote', que queda
            # afuera de esta lista por diseño, así que exigir la igualdad
            # rebotaría exactamente a las guías que esto viene a arreglar.
            if declarado:
                motivo = validar_reparto_declarado(
                    lotes, sum(f["bultos"] for f in declarado), declarado, SALIDA_REPROCESO
                )
                if motivo is not None:
                    raise RepartoDesactualizado(motivo)
        conexion.commit()
        return {"articulo_id": articulo_id, "fecha_vieja": fecha_vieja, "fecha_nueva": fecha_nueva}
    finally:
        conexion.close()


def crear_reproceso_inicial(
    articulo_id: int,
    bultos_primera: float,
    costo_por_bulto_primera: float,
    fecha_operacion,
    ficha_id: int,
    cliente_id: int | None = None,
) -> int:
    """Las cajas que YA ESTABAN ARMADAS en el piso el día del corte. PRODUCE SIN CONSUMIR. Devuelve el número de guía.

    No corre el FIFO ni escribe consumos, y eso no es un atajo: los
    cajones que originaron estas cajas nunca se van a cargar, así que no
    hay lote del que salgan. Un reproceso normal descuenta lo que tomó;
    si este descontara igual, dejaría el artículo en negativo o se
    comería el stock inicial sin procesar recién cargado.

    Que no consuma vive EN EL DATO: bultos_tomados = 0, y el cálculo de
    stock ya resta SUM(bultos_tomados). No hay ninguna excepción escrita
    en una consulta que alguien pueda olvidar después, y el check de la
    base no deja cargarlo de otra forma.

    El costo por caja se carga a mano por la misma razón: no hay consumos
    de los que derivarlo. costo_total sale de multiplicar, para que
    siga valiendo costo_por_bulto_primera = costo_total / bultos_primera
    como en cualquier otra guía.

    La ficha es OBLIGATORIA acá, al revés que en el reproceso normal: una
    caja armada que está en el piso ya es de una ficha concreta — se la
    puede ir a mirar. Un "sin asignar" en el stock inicial sería no
    haberla mirado.
    """
    if bultos_primera <= 0:
        raise ValueError("Un reproceso inicial son cajas que están armadas en el piso: tiene que ser mayor a cero.")
    if costo_por_bulto_primera is None or costo_por_bulto_primera < 0:
        raise ValueError("Las cajas del stock inicial necesitan un costo por caja de cero o más.")
    if ficha_id is None:
        raise ValueError("Una caja ya armada tiene ficha: elegí cuál.")

    costo_total = round(float(bultos_primera) * float(costo_por_bulto_primera), 2)
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reprocesos
                    (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                     bultos_segunda, bultos_merma, costo_total, costo_por_bulto_primera,
                     cliente_id, ficha_id, tipo)
                VALUES (%s, %s, 0, %s, 0, 0, %s, %s, %s, %s, 'inicial')
                RETURNING id
                """,
                (articulo_id, fecha_operacion, bultos_primera, costo_total,
                 costo_por_bulto_primera, cliente_id, ficha_id),
            )
            reproceso_id = cursor.fetchone()[0]
        conexion.commit()
        return reproceso_id
    finally:
        conexion.close()


def listar_stock_inicial() -> dict:
    """Todo lo cargado como stock inicial, de las dos formas, para mostrarlo abajo de la pantalla de carga.

    Devuelve {"sueltos": [...], "armadas": [...], "total_bultos": n,
    "total_pesos": n}. Sirve para dos cosas concretas mientras se carga:
    saber por dónde se va, y no cargar dos veces lo mismo.

    Lo anulado no viene: se carga a mano y equivocarse es parte del
    trabajo, así que lo que se ve tiene que ser lo que cuenta.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT m.id, m.articulo_id, a.nombre AS articulo_nombre,
                       m.cantidad, m.costo_por_bulto, m.fecha_operacion, m.creado_en
                FROM movimientos_stock m
                JOIN articulos a ON a.id = m.articulo_id
                WHERE m.tipo = 'stock_inicial' AND m.anulado_el IS NULL
                ORDER BY m.creado_en DESC
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            sueltos = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]

            cursor.execute(
                """
                SELECT r.id, r.articulo_id, a.nombre AS articulo_nombre,
                       r.bultos_primera, r.costo_por_bulto_primera,
                       r.ficha_id, r.cliente_id, cl.nombre AS cliente_nombre,
                       -- El mismo nombre de ficha que muestra Guías R: el
                       -- alias del cliente si lo tiene, y si no el artículo
                       -- de la ficha. Que las dos pantallas la llamen
                       -- distinto sería peor que no mostrarla.
                       COALESCE(NULLIF(BTRIM(f.nombre_cliente), ''), fa.nombre) AS ficha_nombre,
                       r.fecha_operacion, r.creado_en
                FROM reprocesos r
                JOIN articulos a ON a.id = r.articulo_id
                LEFT JOIN clientes cl ON cl.id = r.cliente_id
                LEFT JOIN fichas_logistica f ON f.id = r.ficha_id
                LEFT JOIN articulos fa ON fa.id = f.articulo_id
                WHERE r.tipo = 'inicial' AND r.anulado_el IS NULL
                ORDER BY r.creado_en DESC
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            armadas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()

    total_bultos = sum(float(f["cantidad"]) for f in sueltos) + sum(
        float(f["bultos_primera"]) for f in armadas
    )
    total_pesos = sum(float(f["cantidad"]) * float(f["costo_por_bulto"]) for f in sueltos) + sum(
        float(f["bultos_primera"]) * float(f["costo_por_bulto_primera"]) for f in armadas
    )
    return {
        "sueltos": sueltos,
        "armadas": armadas,
        "total_bultos": round(total_bultos, 2),
        "total_pesos": round(total_pesos, 2),
    }


def anular_renglon_stock_inicial(clase: str, renglon_id: int) -> None:
    """Anula un renglón del stock inicial, sueltos o armadas. Se carga a mano: equivocarse es parte del trabajo.

    Comprueba el tipo antes de anular. Sin eso, la pantalla del stock
    inicial sería una puerta de atrás para anular cualquier ajuste o
    cualquier guía R del depósito cambiando un número en el formulario.
    """
    if clase not in ("sueltos", "armadas"):
        raise ValueError("Clase de renglón desconocida.")
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if clase == "sueltos":
                cursor.execute(
                    "UPDATE movimientos_stock SET anulado_el = now() "
                    "WHERE id = %s AND tipo = 'stock_inicial' AND anulado_el IS NULL",
                    (renglon_id,),
                )
            else:
                cursor.execute(
                    "UPDATE reprocesos SET anulado_el = now() "
                    "WHERE id = %s AND tipo = 'inicial' AND anulado_el IS NULL",
                    (renglon_id,),
                )
            if cursor.rowcount == 0:
                raise ValueError("Ese renglón no es del stock inicial, o ya estaba anulado.")
        conexion.commit()
    finally:
        conexion.close()


def listar_reprocesos_por_rango(fecha_desde, fecha_hasta, articulo_id=None,
                                guia_id=None) -> list[dict]:
    """Las guías R del rango (por fecha_operacion), anuladas incluidas y marcadas, con sus consumos adentro.

    Cada guía trae "consumos": de qué lote salió cada bulto, con la guía
    de compra y el proveedor cuando el lote es una compra — la
    trazabilidad hacia atrás completa ("de la 105 tomé 30...").

    Y trae la FICHA a la que fueron las cajas de primera, con su nombre
    para mostrar. ficha_id en NULL = sin asignar: esta pantalla es donde
    se completa, así que esas guías tienen que aparecer, no esconderse.

    `articulo_id` opcional acota a UN artículo. Filtra sobre `rp.articulo_id`
    —el artículo de la guía— y NO sobre los consumos: una guía de Limón que
    tomó cajones de Limón es de Limón, y buscar "Limón" tiene que traer esa
    guía entera, no las guías de otros artículos que tocaron un lote suyo.
    Los dos criterios son defendibles y hacen falta los dos algún día; el
    que contesta "mostrame las de Limón" es éste.

    `guia_id` PISA A LOS OTROS DOS, y eso se decide acá y no en la pantalla.
    El que escribe "R251" ya sabe qué guía quiere: el rango de fechas y el
    artículo son ayudas para BUSCAR, y una vez que hay un id no hay nada que
    buscar. Que el default de 7 días dejara afuera la guía pedida es la peor
    forma de fallar que tiene un filtro por id — devuelve vacío, y el vacío
    se lee como "esa guía no existe".

    Va en el WHERE y no como un filtro más al lado: con los tres `AND`, la
    guía R251 del 02/09 buscada dentro del rango de esta semana daría cero
    filas y las dos condiciones estarían "bien" por separado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT rp.id, rp.articulo_id, rp.fecha_operacion, rp.bultos_tomados,
                       rp.bultos_primera, rp.bultos_segunda, rp.bultos_merma,
                       rp.costo_total, rp.costo_por_bulto_primera, rp.creado_en,
                       rp.anulado_el, a.nombre AS articulo_nombre,
                       rp.cliente_id, cl.nombre AS cliente_nombre,
                       -- A qué ficha fueron las cajas. NULL = sin asignar;
                       -- LEFT porque una guía sin ficha no puede
                       -- desaparecer del listado, que es justo donde se
                       -- la va a completar.
                       rp.ficha_id,
                       -- true = el operario cambió el reparto por lote que
                       -- le propuso el FIFO. Se muestra: un costo que no
                       -- eligió el sistema tiene que poder distinguirse.
                       rp.consumos_editados,
                       -- 'normal' / 'inicial' / 'en_origen'. La pantalla lo
                       -- necesita para poder decir que una guía NO es un
                       -- armado del galpón: la de origen se ve igual que
                       -- cualquier otra (toma 10, produce 10) y sin el rótulo
                       -- nadie podría distinguirlas.
                       rp.tipo, rp.compra_origen_id,
                       COALESCE(NULLIF(BTRIM(f.nombre_cliente), ''), fa.nombre) AS ficha_nombre,
                       -- El cliente DE LA FICHA, que NO es `rp.cliente_id`:
                       -- son dos columnas sueltas y nada las ata. El selector
                       -- de esta pantalla ofrece las fichas POR ARTÍCULO —de
                       -- todos los clientes— y `asignar_ficha_a_reproceso`
                       -- solo valida que la ficha exista y que la guía no
                       -- esté anulada. Así que una guía armada para un
                       -- cliente PUEDE terminar en la ficha de otro, y la
                       -- pantalla lo necesita para poder mostrarlo: el
                       -- título sale de la FICHA y taparía la diferencia.
                       f.cliente_id AS ficha_cliente_id
                FROM reprocesos rp
                JOIN articulos a ON a.id = rp.articulo_id
                LEFT JOIN clientes cl ON cl.id = rp.cliente_id
                LEFT JOIN fichas_logistica f ON f.id = rp.ficha_id
                LEFT JOIN articulos fa ON fa.id = f.articulo_id
                WHERE {recorte}
                ORDER BY rp.fecha_operacion DESC, rp.id DESC
                """.format(recorte=(
                    "rp.id = %s" if guia_id else
                    "rp.fecha_operacion >= %s AND rp.fecha_operacion <= %s"
                    + (" AND rp.articulo_id = %s" if articulo_id else "")
                )),
                (guia_id,) if guia_id else
                (fecha_desde, fecha_hasta) + ((articulo_id,) if articulo_id else ()),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            guias = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
            if not guias:
                return []

            cursor.execute(
                """
                SELECT rc.reproceso_id, rc.origen, rc.origen_id, rc.bultos, rc.costo_por_bulto,
                       g.fecha_operacion AS guia_fecha, p.nombre AS proveedor_nombre
                FROM reprocesos_consumos rc
                LEFT JOIN compras c ON c.id = rc.compra_id
                LEFT JOIN guias_compra g ON g.id = c.guia_id
                LEFT JOIN proveedores p ON p.id = c.proveedor_id
                WHERE rc.reproceso_id = ANY(%s)
                ORDER BY rc.id
                """,
                ([g["id"] for g in guias],),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            consumos = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        por_guia = {}
        for c in consumos:
            por_guia.setdefault(c["reproceso_id"], []).append(c)
        for g in guias:
            g["consumos"] = por_guia.get(g["id"], [])
        return guias
    finally:
        conexion.close()


def anular_reproceso(reproceso_id: int) -> None:
    """Anula una guía R (baja lógica): lo tomado vuelve a sus lotes y la primera sale del stock, solos.

    Como el stock y el FIFO vivos nunca guardaron asignaciones, no hay
    nada que descoser: excluir la guía de las sumas alcanza, y la
    repetición reasigna en la próxima consulta. Los consumos quedan como
    registro de la guía anulada. Corregir = anular y cargar de nuevo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE reprocesos SET anulado_el = now() WHERE id = %s AND anulado_el IS NULL",
                (reproceso_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def crear_salida_de_segunda(articulo_id: int, bultos: float, fecha_operacion,
                            destino: str = "puesto", motivo: str | None = None,
                            foto_ruta: str | None = None) -> None:
    """Saca bultos del pool de segunda. `destino` dice a dónde fueron.

    Dos destinos y la misma resta: 'puesto' es el remito de siempre —se lo
    lleva el Puesto y deja de ser problema del depósito— y 'merma' es que
    se tiró. El pool baja igual con los dos, y ninguno mueve plata: la
    segunda no lleva costo, porque el del reproceso viaja entero a la
    primera y el de un rechazo mandado a segunda ya se imputó como pérdida
    al entrar. Imputarla nombraría la misma pérdida dos veces.

    NO TRABA CONTRA EL POOL, igual que el remito de siempre: si se saca más
    de lo que el sistema cree tener, el pool queda negativo y se ve. Un
    número negativo dice "acá pasó algo", que es información; un freno
    diría "no pasó nada", que es mentira.

    El motivo va SOLO con destino 'merma' y es obligatorio ahí — lo decide
    la base con `remitos_segunda_motivo_solo_merma`, que cubre las dos
    direcciones, y `remitos_segunda_motivo_de_la_lista`. Acá no se
    revalida: si el constraint rechaza, el error sube.

    `foto_ruta` entra en la MISMA transacción, por lo mismo que en
    crear_movimiento_stock: una merma guardada con su foto perdida es
    justo el agujero que la foto viene a tapar.

    A propósito no devuelve nada: la pantalla es de operario y el pool no
    se le muestra. El recupero económico va aparte, más adelante.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO remitos_segunda (articulo_id, bultos, fecha_operacion, destino, motivo)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (articulo_id, bultos, fecha_operacion, destino, motivo),
            )
            if foto_ruta:
                (salida_id,) = cursor.fetchone()
                cursor.execute(
                    "INSERT INTO fotos_merma (salida_segunda_id, foto_ruta) VALUES (%s, %s)",
                    (salida_id, foto_ruta),
                )
        conexion.commit()
    finally:
        conexion.close()


def listar_remitos_segunda_por_rango(fecha_desde, fecha_hasta) -> list[dict]:
    """Las SALIDAS del pool de segunda del rango (por fecha_operacion), anuladas incluidas y marcadas — para Movimientos.

    Dos destinos: 'puesto' (el remito de siempre) y 'merma' (se tiró, con
    motivo y foto). El nombre de la función quedó del día en que el remito
    era la única salida, igual que el de la tabla.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.bultos, r.fecha_operacion, r.creado_en, r.anulado_el,
                       r.destino, r.motivo,
                       a.nombre AS articulo_nombre,
                       (SELECT COUNT(*) FROM fotos_merma f WHERE f.salida_segunda_id = r.id) AS fotos
                FROM remitos_segunda r
                JOIN articulos a ON a.id = r.articulo_id
                WHERE r.fecha_operacion >= %s AND r.fecha_operacion <= %s
                ORDER BY r.fecha_operacion DESC, r.creado_en DESC
                """,
                (fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def anular_remito_segunda(remito_id: int) -> None:
    """Anula un remito de segunda (baja lógica): la segunda vuelve al pool sola."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE remitos_segunda SET anulado_el = now() WHERE id = %s AND anulado_el IS NULL",
                (remito_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def completar_costo_reproceso(reproceso_id: int) -> dict:
    """Rellena los costos que faltaban en una guía R con los precios ya cargados — SOLO los NULL, jamás pisa.

    El caso real: se reprocesó a la tarde consumiendo la compra de la
    mañana, que todavía no tenía precio. Cuando el precio se carga, este
    botón completa los consumos 'compra' sin costo con el importe actual
    de esa compra. Si con eso TODOS los consumos quedan con costo, se
    calculan y graban costo_total y costo_por_bulto_primera (todo a la
    primera). Los consumos de ajuste/reingreso/sin_lote no tienen precio
    posible: si los hay, la guía sigue incompleta y se dice.

    Devuelve {"completado": bool, "sin_precio": cuántos consumos siguen
    sin costo}.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE reprocesos_consumos rc
                SET costo_por_bulto = c.importe
                FROM compras c
                WHERE c.id = rc.compra_id AND rc.reproceso_id = %s
                  AND rc.costo_por_bulto IS NULL AND c.importe IS NOT NULL
                """,
                (reproceso_id,),
            )
            cursor.execute(
                """
                SELECT COUNT(*) FILTER (WHERE costo_por_bulto IS NULL),
                       COALESCE(SUM(bultos * costo_por_bulto), 0)
                FROM reprocesos_consumos WHERE reproceso_id = %s
                """,
                (reproceso_id,),
            )
            sin_precio, costo_total = cursor.fetchone()
            completado = int(sin_precio) == 0
            if completado:
                cursor.execute(
                    """
                    UPDATE reprocesos
                    SET costo_total = %s,
                        costo_por_bulto_primera = CASE WHEN bultos_primera > 0
                                                       THEN round(%s / bultos_primera, 2) END
                    WHERE id = %s AND costo_total IS NULL
                    """,
                    (round(float(costo_total), 2), round(float(costo_total), 2), reproceso_id),
                )
        conexion.commit()
        return {"completado": completado, "sin_precio": int(sin_precio)}
    finally:
        conexion.close()


# La partición del costo sin cerrar, en UN solo lugar. La misma regla la
# aplica la pantalla de Guías R por guía (`costo_completable` en main.py) sobre
# los consumos que ya trajo: si se escribiera distinto en los dos lados, un día
# el banner diría una cosa y el botón haría otra.
#
# Un consumo sin precio se puede llenar DESPUÉS solo si vino de una compra:
# "Completar costo" copia `compras.importe`, y para eso necesita `compra_id`.
# Cualquier otro origen —ajuste, stock inicial sin costo, reingreso,
# cierre_modelo_viejo, sin_lote— NO TIENE de dónde sacar un precio, ni hoy ni
# nunca. Las dos consultas de abajo son la misma partición, y por eso la
# condición vive UNA sola vez acá: la alerta cuenta un lado y la pantalla el
# otro, y no se pueden separar.
_SQL_FALTA_ALGUN_PRECIO = """
    EXISTS (SELECT 1 FROM reprocesos_consumos rc
            WHERE rc.reproceso_id = rp.id AND rc.costo_por_bulto IS NULL)
"""

_SQL_FALTA_UN_PRECIO_IMPOSIBLE = """
    EXISTS (SELECT 1 FROM reprocesos_consumos rc
            WHERE rc.reproceso_id = rp.id
              AND rc.costo_por_bulto IS NULL AND rc.origen <> 'compra')
"""


def contar_reprocesos_costo_incompleto() -> dict:
    """Auditoría: guías R vigentes que ESPERAN un precio que puede llegar, y la más vieja.

    Cuenta SOLO las que "Completar costo" va a poder cerrar: las que
    quedaron sin costo porque falta cargar el precio de alguna compra.

    Las que consumieron un lote sin precio POSIBLE quedan afuera a
    propósito, y no es que se escondan: van a
    `contar_reprocesos_sin_costo_posible`, que la pantalla de Guías R
    muestra como dato, y cada salida suya ya aparece nombrada en el
    "afuera del cálculo" de Rentabilidad Real. Contarlas acá tenía un
    costo peor que el problema: son guías que NADIE puede arreglar, así
    que la alerta no bajaba nunca —y una alerta que no se puede apagar
    enseña a ignorar todas las alertas—. Se separaron el 06/09, cuando el
    lote fantasma del compensatorio (804 bultos sin costo posible) hizo
    inevitable lo que el modelo ya permitía desde el stock inicial.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*), MIN(fecha_operacion) FROM reprocesos rp
                WHERE anulado_el IS NULL AND costo_total IS NULL
                  AND {_SQL_FALTA_ALGUN_PRECIO}
                  AND NOT {_SQL_FALTA_UN_PRECIO_IMPOSIBLE}
                """
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def contar_reprocesos_sin_costo_posible() -> dict:
    """Las guías R vigentes cuyo costo NO se va a poder cerrar nunca, y la más vieja.

    El otro lado de `contar_reprocesos_costo_incompleto`. Las dos juntas
    cubren todas las vigentes con `costo_total IS NULL` MENOS un caso que
    no debería existir: una guía sin costo y sin ningún consumo sin
    precio. Esa no entra en ninguna a propósito — no hay nada que
    completar ni nada que declarar imposible, es una anomalía, y meterla
    en cualquiera de las dos la escondería.

    NO es una alerta y no tiene que serlo: no hay nada que hacer con
    ellas. Es un dato de la pantalla de Guías R, para que el número se
    pueda mirar sin que grite todos los días.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*), MIN(fecha_operacion) FROM reprocesos rp
                WHERE anulado_el IS NULL AND costo_total IS NULL
                  AND {_SQL_FALTA_UN_PRECIO_IMPOSIBLE}
                """
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


# --- Rentabilidad Real ---


def articulos_con_salidas_stock(cliente_id: int, fecha_desde, fecha_hasta) -> list[dict]:
    """Los artículos que la Rentabilidad Real tiene que mirar en el rango: con armados del cliente, mermas o reprocesos.

    Mermas y reprocesos son del DEPÓSITO (no de un cliente): entran igual
    — con un solo cliente todo cuadra; si algún día hay varios, se decide
    el prorrateo en ese momento.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id AS articulo_id, a.nombre, a.grupo
                FROM articulos a
                WHERE a.id IN (
                    SELECT r.articulo_id
                    FROM pedidos_renglones r
                    JOIN (SELECT DISTINCT ON (cliente_id, fecha_operacion) id, cliente_id, fecha_operacion
                          FROM pedidos WHERE anulado_el IS NULL
                          ORDER BY cliente_id, fecha_operacion, creado_en DESC) v ON v.id = r.pedido_id
                    WHERE v.cliente_id = %s AND v.fecha_operacion >= %s AND v.fecha_operacion <= %s
                      AND r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id IS NOT NULL
                    UNION
                    -- EL PASE ENTRA ACA, y esta es la compuerta que de verdad
                    -- decide: filtrando solo 'merma', una berenjena que no se
                    -- vendio y a la que solo se le pasaron diez cajones a
                    -- segunda no llegaba ni a la funcion pura. No aparecia en
                    -- cero — no aparecia, y su perdida quedaba invisible.
                    SELECT articulo_id FROM movimientos_stock
                    WHERE anulado_el IS NULL AND tipo IN {tipos}
                      AND fecha_operacion >= %s AND fecha_operacion <= %s
                    UNION
                    SELECT articulo_id FROM reprocesos
                    WHERE anulado_el IS NULL
                      AND fecha_operacion >= %s AND fecha_operacion <= %s
                )
                ORDER BY a.nombre
                """.format(tipos=_SQL_TIPOS_QUE_SON_PERDIDA),
                (cliente_id, fecha_desde, fecha_hasta, fecha_desde, fecha_hasta, fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


# CADA salida individual, tipada y fechada. Es la MISMA lista que usan el FIFO
# de costo y el de stock: desde E4 hay una sola definición de "qué salió y
# cuándo", y no dos que se puedan ir separando con el tiempo.
_SQL_SALIDAS_STOCK = """
    WITH vigentes AS (
        SELECT DISTINCT ON (cliente_id, fecha_operacion) id, cliente_id, fecha_operacion
        FROM pedidos WHERE anulado_el IS NULL
        ORDER BY cliente_id, fecha_operacion, creado_en DESC
    )
    SELECT * FROM (
        SELECT (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date AS fecha_orden,
               r.armado_el AS momento_orden,
               'armado' AS tipo,
               v.fecha_operacion AS fecha,
               COALESCE(r.cantidad_armada, r.cantidad) AS cantidad,
               r.kilos_enviados AS unidades,
               v.cliente_id AS cliente_id,
               NULL AS motivo,
               NULL::numeric AS bultos_segunda,
               NULL AS lote_tipo,
               NULL::bigint AS lote_origen_id,
               r.ficha_id,
               -- LA PARED DEL ARMADO viaja con la salida, no se deduce
               -- después: con envase, la mercadería sale en NUESTRA caja, y
               -- una caja no puede salir de un cajón sin pasar por una guía
               -- R. Sin envase es "envase perdido" (manzana, pera, arándano)
               -- y el cajón del proveedor ES lo que se despacha.
               -- Es el campo que acertó 630 de 630 y 135 de 135 el 08/09.
               (f.envase_id IS NOT NULL) AS ficha_con_envase,
               r.id AS renglon_id,
               r.articulo_id AS articulo_id
        FROM pedidos_renglones r
        JOIN vigentes v ON v.id = r.pedido_id
        LEFT JOIN fichas_logistica f ON f.id = r.ficha_id
        WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id = ANY(%s)
          AND (r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date > %s
        UNION ALL
        -- LA FICHA VIAJA, y desde el 21/09 no es siempre NULL. Iba en NULL
        -- porque cuando esto se escribió un movimiento no podía tener ficha;
        -- la merma puede desde el 10/09 y el pase desde el 21/09, y esta
        -- rama nunca se enteró. Es el corolario 3: el que falta no nombra el
        -- campo, así que grepear `ficha_id` no lo encuentra — lo encuentra
        -- mirar quién CONSTRUYE la salida.
        --
        -- La usa `prioridad_de_lote`: un pase de CAJAS ARMADAS prefiere
        -- lotes trabajados, porque lo que se está perdiendo es una caja y no
        -- un cajón. Sin esta columna la preferencia no tiene con qué
        -- decidir y el pase se costea contra el cajón más viejo.
        --
        -- `ficha_con_envase` SIGUE EN FALSE a propósito: esa columna es la
        -- pared del ARMADO (con envase, el armado no puede salir de un
        -- cajón) y un movimiento no es un armado.
        SELECT m.fecha_operacion, m.creado_en, m.tipo, m.fecha_operacion,
               -m.cantidad, NULL, NULL, m.motivo, NULL,
               m.lote_tipo, m.lote_origen_id, m.ficha_id, FALSE, NULL::bigint, m.articulo_id
        FROM movimientos_stock m
        WHERE m.anulado_el IS NULL AND m.cantidad < 0 AND m.articulo_id = ANY(%s)
          AND m.fecha_operacion > %s
          -- El compensatorio NEGATIVO del corte tampoco es una salida del
          -- FIFO, por la misma razón que el positivo no es un lote: cancela
          -- el saldo viejo en el TOTAL. Con el piso puesto ya no queda nada
          -- viejo que cancelar, así que dejarlo acá sería restarle a los
          -- lotes NUEVOS mercadería que nunca salió de ellos.
          AND m.tipo <> 'cierre_modelo_viejo'
        UNION ALL
        SELECT rp.fecha_operacion, rp.creado_en, 'reproceso_toma', rp.fecha_operacion,
               rp.bultos_tomados, NULL, NULL, NULL, rp.bultos_segunda,
               NULL, NULL, NULL, FALSE, NULL::bigint, rp.articulo_id
        FROM reprocesos rp
        WHERE rp.anulado_el IS NULL AND rp.articulo_id = ANY(%s)
          AND rp.fecha_operacion > %s
    ) salidas
    ORDER BY articulo_id, fecha_orden, momento_orden
"""


def _salidas_stock_varios(cursor, articulo_ids: list[int], corte=None) -> dict:
    """{articulo_id: [salidas fechadas]}, con el cursor abierto. Una lista por id pedido, vacía si no tuvo ninguna.

    SOLO LAS POSTERIORES AL CORTE, estricto. El día del corte es asimétrico
    —el conteo se toma a la tarde, así que todo lo del día ya está adentro de
    la foto— y una salida de ese día que consumiera la foto la estaría
    restando dos veces. Es la misma regla que ya usan la cuenta por ficha y
    el pool de segunda; el comentario de `_SQL_STOCK_PARTIDO` la mide.

    Lo que se pierde, y hay que decirlo: las entregas del día del corte y
    anteriores dejan de tener atribución de costo, y como los dos llamadores
    de `atribuir_costos_fifo` arman sus filas iterando su salida, esas
    entregas desaparecen de ahí. Su costo venía de lotes anteriores al corte,
    que están declarados no confiables, así que era cero de todas formas.
    """
    ids = list(articulo_ids)
    por_articulo = {articulo_id: [] for articulo_id in ids}
    if not ids:
        return por_articulo
    if corte is None:
        corte = _fecha_corte(cursor)
    cursor.execute(_SQL_SALIDAS_STOCK, (ids, corte, ids, corte, ids, corte))
    columnas = [descripcion[0] for descripcion in cursor.description]
    salidas = []
    for fila in cursor.fetchall():
        salida = dict(zip(columnas, fila))
        salida["orden"] = (salida["fecha_orden"], salida["momento_orden"])
        salidas.append(salida)

    # Las correcciones del que arma: de qué lote dijo que sacó cada renglón.
    # Son la EXCEPCIÓN —la enorme mayoría de los renglones no tiene ninguna—,
    # así que se piden en UNA consulta para todos y se cuelgan de su salida.
    # Un renglón sin filas queda sin "lotes_elegidos" y se reparte como
    # siempre: el default no se guarda nunca.
    renglones = [s["renglon_id"] for s in salidas if s["renglon_id"] is not None]
    elegidos_por_renglon = {}
    if renglones:
        cursor.execute(
            """
            SELECT renglon_id, lote_tipo, lote_origen_id, bultos
            FROM pedidos_renglones_lotes_elegidos
            WHERE renglon_id = ANY(%s)
            ORDER BY id
            """,
            (renglones,),
        )
        for renglon_id, lote_tipo, lote_origen_id, bultos in cursor.fetchall():
            elegidos_por_renglon.setdefault(renglon_id, []).append(
                {"lote_tipo": lote_tipo, "lote_origen_id": lote_origen_id, "bultos": float(bultos)}
            )

    for salida in salidas:
        elegidos = elegidos_por_renglon.get(salida["renglon_id"])
        if elegidos:
            salida["lotes_elegidos"] = elegidos
        por_articulo[salida.pop("articulo_id")].append(salida)
    return por_articulo


def salidas_stock_articulos(articulo_ids: list[int]) -> dict:
    """CADA salida individual de VARIOS artículos, tipada y en orden cronológico — TODA la historia.

    Devuelve {articulo_id: [salidas]}, con una lista por cada id pedido
    (vacía si no tuvo ninguna). Es `_salidas_stock_varios` con su propia
    conexión, para el que la llama de afuera de una transacción.

    La atribución FIFO de la Rentabilidad Real necesita el pasado
    completo (qué lote consumió cada salida depende de todas las
    anteriores); el rango de la pantalla filtra después. Tipos: 'armado'
    (renglón de pedido vigente, con la fecha del PEDIDO — la que ancla el
    precio — y los kilos enviados), 'merma' y 'ajuste' (movimientos
    negativos), 'reproceso_toma' (con la segunda del reproceso como dato).
    Una merma DIRIGIDA trae su lote_tipo/lote_origen_id: se cuesta al lote
    que el operario marcó, no al más viejo.
    El orden FIFO es el mismo del resto del módulo: fecha real del hecho
    + momento de carga de desempate; el armado, por su instante de tilde.
    """
    if not articulo_ids:
        return {}
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return _salidas_stock_varios(cursor, articulo_ids)
    finally:
        conexion.close()


def salidas_stock_articulo(articulo_id: int) -> list[dict]:
    """Las salidas de UN artículo. Quien mire varios usa salidas_stock_articulos, que los trae en una conexión."""
    return salidas_stock_articulos([articulo_id])[articulo_id]


# --- Costos Fijos (Gerencia): plan de cuentas, fotos de importe e índices ---


def listar_grupos_costos_fijos() -> list[dict]:
    """Los grupos del plan de cuentas (bajas incluidas: el motor y las pantallas deciden qué mostrar)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, numero, nombre, creado_en, baja_el FROM grupos_costos_fijos ORDER BY numero"
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def crear_grupo_costos_fijos(numero: int, nombre: str) -> int:
    """Alta de grupo con el número que ELIGIÓ el dueño (el sistema jamás genera números)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO grupos_costos_fijos (numero, nombre) VALUES (%s, %s) RETURNING id",
                (numero, nombre),
            )
            grupo_id = cursor.fetchone()[0]
        conexion.commit()
        return grupo_id
    finally:
        conexion.close()


def listar_subcuentas_costos_fijos() -> list[dict]:
    """Todas las subcuentas con su grupo (número y nombre), para el plan, el motor y los selectores."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.grupo_id, s.numero, s.nombre, s.creado_en, s.baja_desde,
                       g.numero AS grupo_numero, g.nombre AS grupo_nombre
                FROM subcuentas_costos_fijos s
                JOIN grupos_costos_fijos g ON g.id = s.grupo_id
                ORDER BY g.numero, s.numero
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def obtener_subcuenta_costos_fijos(subcuenta_id: int) -> dict | None:
    """Una subcuenta con su grupo, para la pantalla de carga de importes."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.grupo_id, s.numero, s.nombre, s.baja_desde,
                       g.numero AS grupo_numero, g.nombre AS grupo_nombre
                FROM subcuentas_costos_fijos s
                JOIN grupos_costos_fijos g ON g.id = s.grupo_id
                WHERE s.id = %s
                """,
                (subcuenta_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
            return dict(zip(columnas, fila))
    finally:
        conexion.close()


def crear_subcuenta_costos_fijos(grupo_id: int, numero: int, nombre: str) -> int:
    """Alta de subcuenta con el número que ELIGIÓ el dueño, dentro de su grupo."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO subcuentas_costos_fijos (grupo_id, numero, nombre) VALUES (%s, %s, %s) RETURNING id",
                (grupo_id, numero, nombre),
            )
            subcuenta_id = cursor.fetchone()[0]
        conexion.commit()
        return subcuenta_id
    finally:
        conexion.close()


def listar_importes_costos_fijos() -> list[dict]:
    """TODAS las fotos de importe no anuladas: el valor de cada mes se deriva siempre de acá (regla 1)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, subcuenta_id, mes_desde, importe, alcance, creado_en
                FROM importes_costos_fijos
                WHERE anulado_el IS NULL
                ORDER BY subcuenta_id, mes_desde, creado_en
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_importes_de_subcuenta(subcuenta_id: int) -> list[dict]:
    """El historial de fotos de UNA subcuenta (anuladas incluidas y marcadas), para la pantalla de carga."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, mes_desde, importe, alcance, creado_en, anulado_el
                FROM importes_costos_fijos
                WHERE subcuenta_id = %s
                ORDER BY mes_desde DESC, creado_en DESC
                """,
                (subcuenta_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def crear_importe_costos_fijos(subcuenta_id: int, mes_desde, importe: float, alcance: str = "en_adelante") -> None:
    """Una foto nueva (carga o corrección): SIEMPRE fila nueva, jamás UPDATE — la serie es el historial."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO importes_costos_fijos (subcuenta_id, mes_desde, importe, alcance)
                VALUES (%s, %s, %s, %s)
                """,
                (subcuenta_id, mes_desde, importe, alcance),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_indices_inflacion() -> list[dict]:
    """La tabla de índices completa, del mes más nuevo al más viejo."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT mes, porcentaje, actualizado_en FROM indices_inflacion ORDER BY mes DESC"
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def guardar_indice_inflacion(mes, porcentaje: float) -> None:
    """El índice de un mes (upsert): es un PARÁMETRO editable, no un hecho — editar un mes pasado recalcula lo que lo usa (decisión del dueño, 25/08)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO indices_inflacion (mes, porcentaje)
                VALUES (%s, %s)
                ON CONFLICT (mes) DO UPDATE
                    SET porcentaje = EXCLUDED.porcentaje, actualizado_en = now()
                """,
                (mes, porcentaje),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_articulos_con_primera_de_cliente() -> list[dict]:
    """Los artículos con alguna guía R VIGENTE armada para un cliente: los únicos donde puede haber cruce.

    Acota la alerta de Auditoría: la atribución FIFO se rejuega solo para
    estos artículos, no para todo el catálogo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT rp.articulo_id, a.nombre AS articulo_nombre
                FROM reprocesos rp
                JOIN articulos a ON a.id = rp.articulo_id
                WHERE rp.anulado_el IS NULL AND rp.cliente_id IS NOT NULL
                  AND rp.bultos_primera > 0
                ORDER BY a.nombre
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


# ----------------------------------------------------------------------------
# ALERTAS GUARDADAS (ver app/alertas.py para el porqué del diseño)
# ----------------------------------------------------------------------------

# Número arbitrario y fijo: identifica al candado de la recalculación de
# alertas entre todos los advisory locks de la base.
CLAVE_CANDADO_ALERTAS = 8_270_001


@contextmanager
def candado_alertas():
    """Toma el candado de la recalculación de alertas mientras dure el bloque.

    Devuelve True si lo consiguió y False si ya lo tiene otro (el bucle de
    fondo y el botón de "recalcular ahora" pueden coincidir).

    Los advisory locks viven en la CONEXIÓN, y acá cada consulta abre la suya,
    así que este es el único lugar del sistema donde una conexión se mantiene
    abierta un rato: la que sostiene el candado. Al cerrarla, Postgres lo
    suelta solo — un corte a mitad de camino no deja el candado trabado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (CLAVE_CANDADO_ALERTAS,))
            (tomado,) = cursor.fetchone()
        yield tomado
    finally:
        conexion.close()


def guardar_estado_alerta(codigo: str, casos: int | None = None, mas_viejo=None,
                          duracion_ms: int | None = None, error: str | None = None) -> None:
    """Guarda la foto de UNA alerta. Con error, no pisa el conteo: solo lo anota.

    Que el error no pise el conteo es a propósito: la alerta queda con su
    último valor bueno y su fecha vieja, y la pantalla la muestra vencida.
    Poner cero cuando la consulta se rompió sería decir que el problema
    desapareció.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if error is not None:
                cursor.execute(
                    """
                    INSERT INTO alertas_estado (codigo, casos, calculada_el, error)
                    VALUES (%s, 0, now(), %s)
                    ON CONFLICT (codigo) DO UPDATE SET error = EXCLUDED.error
                    """,
                    (codigo, error),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO alertas_estado (codigo, casos, mas_viejo, calculada_el, duracion_ms, error)
                    VALUES (%s, %s, %s, now(), %s, NULL)
                    ON CONFLICT (codigo) DO UPDATE SET
                        casos = EXCLUDED.casos,
                        mas_viejo = EXCLUDED.mas_viejo,
                        calculada_el = EXCLUDED.calculada_el,
                        duracion_ms = EXCLUDED.duracion_ms,
                        error = NULL
                    """,
                    (codigo, casos, mas_viejo, duracion_ms),
                )
        conexion.commit()
    finally:
        conexion.close()


def listar_estado_alertas() -> list[dict]:
    """La foto entera, de una sola consulta: es lo único que cada pantalla con banner lee.

    Son 15-100 filas: se traen todas y el filtrado por módulo se hace en
    Python contra el registro. Así agregar una alerta no toca la base ni
    obliga a duplicar los módulos en dos lugares.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT codigo, casos, mas_viejo, calculada_el, duracion_ms, error FROM alertas_estado"
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


# ---------------------------------------------------------------------------
# STOCK DE CAJAS NUESTRAS
# ---------------------------------------------------------------------------

# EL RECORTE CONTRA LA FECHA DEL CONTEO INICIAL, escrito UNA vez y usado por
# las TRES patas derivadas. Es `>=` porque las cajas se cuentan A LA MAÑANA,
# antes de que se arme nada: la foto NO viene neta del trabajo del día, así
# que ese día cuenta entero.
#
# Y ESO ES UNA DECISIÓN SOBRE CÓMO SE TOMA EL DATO EN LA REALIDAD, no sobre
# el código: el día que alguien cuente a la tarde, la foto ya viene neta del
# trabajo de ese día y con `>=` las guías R de esa jornada se descontarían
# DOS VECES, sin descuadrar nada y sin que nada avise. Es la misma asimetría
# que apareció ocho veces con el corte del modelo.
#
# Por eso está acá arriba y no escrita a mano en cada pata, y por eso lo
# cuida `test_el_recorte_del_CONTEO_INICIAL_lleva_canario`, que lo cambia a
# `>` y exige que el número SE MUEVA. Un piso que no cambia nada al romperlo
# es un piso que no está puesto.
COMPARADOR_DESDE_EL_CONTEO = ">="

# LAS COLUMNAS DE LA CONSULTA, EN ORDEN Y EN UN SOLO LUGAR, porque hay DOS
# lectores y el segundo direccionaba POR INDICE. Al sacar la pata `liberadas`
# el 17/09 la consulta pasó de nueve columnas a ocho: `stock_de_envases` se
# actualizó a `f[7]` y `crear_movimiento_envase` quedó leyendo `fila[8]`, así
# que TODO guardado reventaba con "tuple index out of range" — el conteo
# inicial incluido, que es lo primero que alguien carga.
#
# Es el corolario 3 en su forma más cara: un lector que direcciona por índice
# NO NOMBRA NINGUNA COLUMNA, así que el grep del campo que se saca no lo
# encuentra nunca. Igual que el CSS que ubica por `nth-child`.
#
# Lo cuida `test_los_NOMBRES_de_las_columnas_son_los_que_la_consulta_DEVUELVE`,
# que cuenta las columnas del SELECT y exige que sean éstas.
COLUMNAS_STOCK_DE_ENVASES = (
    "id", "nombre", "umbral_reposicion", "desde",
    "contadas", "declaradas", "por_guias", "stock",
    "esperando_mov", "esperando_guias", "esperando_desde",
)

_SQL_STOCK_DE_ENVASES = """
    WITH base AS (
        SELECT envase_id, cantidad, fecha_operacion
          FROM movimientos_envase
         WHERE origen = 'conteo_inicial' AND anulado_el IS NULL
    ),
    declarados AS (
        SELECT m.envase_id, SUM(m.cantidad) AS cajas
          FROM movimientos_envase m
          JOIN base b ON b.envase_id = m.envase_id
         WHERE m.anulado_el IS NULL
           AND m.origen <> 'conteo_inicial'
           AND m.fecha_operacion {comp} b.fecha_operacion
         GROUP BY m.envase_id
    ),
    -- LO QUE ESPERA AL CONTEO. Las dos patas de arriba ENTRAN POR `base`,
    -- así que un envase sin conteo inicial no tiene ninguna fila: sus
    -- movimientos y sus guías R existen, están bien cargados, y no se ven
    -- en ningún lado. El que carga un envase nuevo, compra doscientas cajas
    -- y entra a la pantalla lee "la cuenta no arrancó" y no tiene forma de
    -- saber que esas doscientas están invisibles.
    --
    -- POR ESO ESTAS DOS CTE NO PASAN POR `base`: cuentan lo que hay, exista
    -- o no el conteo. Y el SELECT las devuelve en CERO cuando el conteo SÍ
    -- está, para que la columna signifique UNA sola cosa —cuántos
    -- movimientos son invisibles por falta de conteo— y no dos.
    --
    -- Van SEPARADAS a propósito: el que lee "3 esperando" y abre la lista de
    -- movimientos de ese envase encuentra 2, porque la tercera es una guía R
    -- y no se carga por ahí. Un solo número obligaría a que la pantalla
    -- mienta o a que el operario adivine cuál falta.
    esperando_mov AS (
        SELECT m.envase_id,
               COUNT(*) AS movimientos,
               MIN(m.fecha_operacion) AS desde
          FROM movimientos_envase m
         WHERE m.anulado_el IS NULL
           AND m.origen <> 'conteo_inicial'
         GROUP BY m.envase_id
    ),
    esperando_guias AS (
        SELECT r.envase_id,
               COUNT(*) AS guias,
               MIN(r.fecha_operacion) AS desde
          FROM reprocesos r
         WHERE r.anulado_el IS NULL
           AND r.lleva_caja_nuestra IS TRUE
         GROUP BY r.envase_id
    ),
    guias AS (
        -- SOLO LA PRIMERA. Al reprocesar un cajón, la primera va en caja de
        -- Día y LA SEGUNDA QUEDA EN EL ENVASE DEL PROVEEDOR: no lleva caja
        -- nuestra y no hay nada que descontar por ella.
        --
        -- El 16/09 esto sumó `bultos_segunda` durante unas horas, sobre una
        -- premisa del galpón que el dueño dio vuelta el mismo día ("la segunda
        -- se pone en caja de Día igual que la primera"). Restaba 80,97 bultos
        -- por trimestre de un stock del que nunca salieron — el stock BAJO y
        -- el aviso de reposición temprano. Queda escrito acá para que nadie
        -- lo vuelva a agregar leyendo el número sin la premisa.
        --
        -- LA SEGUNDA QUE SÍ ESTÁ EN CAJA NUESTRA ES OTRA: la del RECHAZO, que
        -- vuelve del súper en la caja en la que salió. Ésa no pasa por acá
        -- —vive en movimientos_stock— y ya está descontada desde la guía R
        -- que la armó, así que no se cuenta de nuevo.
        --
        -- LA MERMA TAMPOCO ENTRA, y es una decisión, no un olvido: lo que se
        -- descarta se tira, no se pone en una caja para tirarlo. Si algún día
        -- resulta que sí ocupa caja, el término va acá y en
        -- core/envases.cajas_que_mueve_la_guia, que son los dos únicos
        -- lugares donde esta suma está escrita.
        SELECT r.envase_id,
               SUM(CASE r.tipo WHEN 'en_origen' THEN  r.bultos_primera
                               WHEN 'normal'    THEN -r.bultos_primera
                               ELSE 0 END) AS cajas
          FROM reprocesos r
          JOIN base b ON b.envase_id = r.envase_id
         WHERE r.anulado_el IS NULL
           AND r.lleva_caja_nuestra IS TRUE
           AND r.fecha_operacion {comp} b.fecha_operacion
         GROUP BY r.envase_id
    )
    SELECT e.id, e.nombre, e.umbral_reposicion,
           b.fecha_operacion AS desde,
           b.cantidad AS contadas,
           COALESCE(d.cajas, 0) AS declaradas,
           COALESCE(g.cajas, 0) AS por_guias,
           b.cantidad + COALESCE(d.cajas, 0) + COALESCE(g.cajas, 0) AS stock,
           CASE WHEN b.envase_id IS NULL THEN COALESCE(em.movimientos, 0) ELSE 0 END AS esperando_mov,
           CASE WHEN b.envase_id IS NULL THEN COALESCE(eg.guias, 0) ELSE 0 END AS esperando_guias,
           CASE WHEN b.envase_id IS NULL THEN LEAST(em.desde, eg.desde) END AS esperando_desde
      FROM envases e
      LEFT JOIN base b      ON b.envase_id = e.id
      LEFT JOIN declarados d ON d.envase_id = e.id
      LEFT JOIN guias g      ON g.envase_id = e.id
      LEFT JOIN esperando_mov em ON em.envase_id = e.id
      LEFT JOIN esperando_guias eg ON eg.envase_id = e.id
     WHERE e.activo = true
     ORDER BY e.nombre
"""


def stock_de_envases() -> list[dict]:
    """El stock de cajas nuestras, DERIVADO. Una fila por envase activo.

    NO HAY UNA COLUMNA CON EL STOCK, y es la decisión que sostiene todo lo
    demás: se recalcula en cada lectura sumando el conteo inicial, lo que
    declaró una persona y lo que sale de las guías R y de los rechazos que
    vacían una caja. Por eso **anular una guía R corrige el stock de cajas
    sola**: la fila deja de cumplir `anulado_el IS NULL` y ya no está en la
    suma. Escrita como una columna que alguien actualiza, anular sería un
    segundo lugar del que acordarse, y el día que se olvide el stock queda
    mintiendo sin que nada avise.

    `desde` en None = ese envase NO TIENE CONTEO INICIAL, y por eso `stock`
    también viene en None. Eso no es cero: es que la cuenta no arrancó, y la
    pantalla lo dice con esas palabras. Un cero ahí se leería como "no
    quedan cajas", que es lo contrario de lo que pasa.

    Y CON ESA FILA VIENEN `esperando_mov`, `esperando_guias` y
    `esperando_desde`: cuántos movimientos y cuántas guías R ya cargadas
    están invisibles por falta de conteo, y la fecha de la más vieja. Sin
    eso, "la cuenta no arrancó" es verdadero y no alcanza — el que compró
    doscientas cajas ayer no tiene forma de saber que no se ven. Las tres
    valen CERO/None cuando el conteo existe, así que la columna significa
    una sola cosa y no hay que acordarse de mirar `desde` para leerla.

    Las TRES patas vuelven por separado —`contadas`, `declaradas`,
    `por_guias`— y no solo el total: un número solo no se puede leer, y
    cuando el stock no cierre contra el galpón lo primero que hay que poder
    mirar es cuál de las tres se movió.

    ERAN CUATRO HASTA EL 17/09: había una `liberadas`, que sumaba las cajas
    que devolvía un rechazo con destino 'reproceso'. Esa caja no vuelve —se
    tira al pasar la fruta al cajón grande— así que la pata sumaba algo que
    no ocurre. Se fue con `movimientos_stock.envase_id`
    (db/envases_9_*.sql). El stock de cajas SOLO SUBE POR COMPRA y por la
    guía R `en_origen`, que es una caja nuestra que vuelve llena de afuera.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_SQL_STOCK_DE_ENVASES.format(comp=COMPARADOR_DESDE_EL_CONTEO))
            filas = cursor.fetchall()
    finally:
        conexion.close()

    return [dict(zip(COLUMNAS_STOCK_DE_ENVASES, f)) for f in filas]


def listar_colegas(incluir_inactivos: bool = False) -> list[dict]:
    """Los colegas con los que se prestan cajas. Por nombre.

    LISTA APARTE de `proveedores` y de `proveedores_puesto`, igual que
    aquéllas entre sí: circuitos distintos, listas distintas. Un colega que
    además sea proveedor va a estar escrito dos veces y está bien — no se
    suman en ninguna cuenta.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre, activo FROM colegas"
                + ("" if incluir_inactivos else " WHERE activo = true")
                + " ORDER BY nombre"
            )
            return [{"id": f[0], "nombre": f[1], "activo": f[2]}
                    for f in cursor.fetchall()]
    finally:
        conexion.close()


def obtener_o_crear_colega(nombre: str, nombre_normalizado: str) -> int:
    """Devuelve el id del colega, creándolo si no estaba. Unifica por el normalizado.

    MISMA UNIFICACION que clientes_puesto y proveedores_puesto, y el plegado
    lo hace el llamador con `normalizar_texto`: el UNIQUE de la base solo
    exige que lo guardado sea distinto, no pliega nada. Así la regla está
    escrita UNA vez, en Python. Un índice que plegara por su cuenta serían
    DOS, y ése es el caso de "ruben" al lado de "Rubén".

    REACTIVA al que estaba dado de baja en vez de crear uno nuevo: dos filas
    del mismo colega partirían su cuenta en dos y ninguna de las dos diría
    cuánto debe.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, activo FROM colegas WHERE nombre_normalizado = %s",
                (nombre_normalizado,),
            )
            fila = cursor.fetchone()
            if fila is not None:
                if not fila[1]:
                    cursor.execute("UPDATE colegas SET activo = true WHERE id = %s",
                                   (fila[0],))
                    conexion.commit()
                return fila[0]
            cursor.execute(
                "INSERT INTO colegas (nombre, nombre_normalizado) VALUES (%s, %s)"
                " RETURNING id",
                (nombre, nombre_normalizado),
            )
            nuevo = cursor.fetchone()[0]
        conexion.commit()
        return nuevo
    finally:
        conexion.close()


# UNA sola consulta para la LISTA y para el DETALLE, y por eso devuelve los
# movimientos crudos en vez de un saldo: dos consultas —una que suma y otra
# que lista— son la misma regla escrita dos veces, y el día que se separen el
# renglón del colega y su detalle van a decir números distintos sin que nada
# avise. La suma la hace Python con `efecto_en_la_cuenta`, que es el único
# lugar donde el signo de la cuenta está escrito.
#
# ***NO LLEVA EL RECORTE DEL CONTEO INICIAL, Y ESO ES TODO EL ASUNTO.*** El
# stock FISICO sí lo lleva —la foto del piso ya refleja lo que se prestó antes
# de contarla— pero la CUENTA no: si le presté 200 el mes pasado y conté el
# piso hoy, el piso está bien sin esas 200 y el colega me las sigue debiendo.
# Copiar acá el `{comp} b.fecha_operacion` de la pata de al lado borraría esas
# deudas EN SILENCIO. Es la novena aparición de la asimetría del corte, y la
# cuida `test_la_cuenta_del_colega_NO_lleva_el_recorte_del_conteo_inicial`,
# que corre la cuenta con el recorte puesto y exige que el número SE MUEVA.
_SQL_MOVIMIENTOS_DE_COLEGAS = """
    SELECT m.id, m.colega_id, c.nombre, m.envase_id, e.nombre,
           m.origen, m.cantidad, m.fecha_operacion, m.motivo
      FROM movimientos_envase m
      JOIN colegas c ON c.id = m.colega_id
      JOIN envases e ON e.id = m.envase_id
     WHERE m.anulado_el IS NULL
       AND m.colega_id IS NOT NULL
       {filtro}
     ORDER BY m.fecha_operacion DESC, m.id DESC
"""


def movimientos_de_colegas(colega_id: int | None = None) -> list[dict]:
    """Los movimientos de cuenta, todos o los de un colega. El más nuevo primero."""
    filtro = "AND m.colega_id = %s" if colega_id is not None else ""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_SQL_MOVIMIENTOS_DE_COLEGAS.format(filtro=filtro),
                           (colega_id,) if colega_id is not None else ())
            return [{"id": f[0], "colega_id": f[1], "colega": f[2],
                     "envase_id": f[3], "envase": f[4], "origen": f[5],
                     "cantidad": f[6], "fecha": f[7], "motivo": f[8]}
                    for f in cursor.fetchall()]
    finally:
        conexion.close()


def cuentas_de_colegas() -> list[dict]:
    """Un renglón por colega, con el neto POR TIPO DE CAJA.

    SIN TOTAL ENTRE TIPOS, y es una decisión: un colega puede deberme Grandes
    mientras yo le debo Chicas, y sumarlas diría que están a mano. No se
    cancelan porque no son la misma cosa — netear entre tipos es exactamente
    el error que netear adentro de un tipo no es.

    LOS COLEGAS SIN MOVIMIENTOS APARECEN IGUAL, con la lista vacía: uno recién
    cargado tiene que verse en la pantalla, o no hay forma de saber si se
    guardó. Una lista que solo muestra a los que deben no distingue "no debe
    nada" de "no está cargado".

    EL NETO SALE DE `efecto_en_la_cuenta`, sumado acá y no en el SQL: son
    pocas filas —movimientos DECLARADOS por una persona— y así el signo de la
    cuenta está escrito en UN solo lugar, que además es el que los tests
    miran. Un `SUM(-cantidad)` en la consulta sería la segunda copia.
    """
    cuentas = {}
    for colega in listar_colegas():
        cuentas[colega["id"]] = {"colega_id": colega["id"], "colega": colega["nombre"],
                                 "por_envase": [], "movimientos": 0}

    netos = {}
    for movimiento in movimientos_de_colegas():
        # POR ID Y NO POR NOMBRE: dos cajas con el mismo nombre no existen hoy,
        # pero renombrar una partiría su cuenta en dos sin que nada avise. El
        # nombre viaja al lado para mostrarlo.
        clave = (movimiento["colega_id"], movimiento["envase_id"], movimiento["envase"])
        netos[clave] = netos.get(clave, 0) + efecto_en_la_cuenta(movimiento["cantidad"])
        if movimiento["colega_id"] in cuentas:
            cuentas[movimiento["colega_id"]]["movimientos"] += 1

    for (colega_id, envase_id, envase), neto in sorted(netos.items(), key=lambda p: p[0][2]):
        if colega_id not in cuentas:
            continue
        lado, cuantas = como_queda_la_cuenta(neto)
        cuentas[colega_id]["por_envase"].append(
            {"envase_id": envase_id, "envase": envase, "neto": neto,
             "lado": lado, "cuantas": cuantas})

    return sorted(cuentas.values(), key=lambda c: c["colega"])


def crear_movimiento_envase(envase_id: int, origen: str, cantidad: int,
                            fecha_operacion, motivo: str | None = None,
                            colega_id: int | None = None) -> int:
    """Escribe un movimiento DECLARADO de cajas. Devuelve su id.

    `colega_id` VIAJA HASTA EL INSERT y no se queda en la firma: el CHECK
    `movimientos_envase_colega_segun_origen` ata las DOS columnas, así que una
    guarda con una sola mitad escrita por el código es una pared que rechaza
    todo préstamo entre colegas — la forma exacta del 17/09, que estuvo un día
    enterrada y la desactivó un drop en vez del uso. Lo cuida el test que
    compara la tupla ENTERA del INSERT.

    DECIDE LA BASE Y ACÁ SE TRADUCE EL ERROR: el origen, el signo que le
    corresponde y el motivo obligatorio del ajuste los rechazan los CHECK de
    `movimientos_envase` (ver db/envases_2_*.sql). No se pre-chequea nada
    acá — un pre-chequeo en Python es una segunda copia de la regla, y el
    día que se separen la que rechaza deja de ser la que el código cree.

    `stock_sistema` lo escribe el SERVER, leído en la MISMA transacción: es
    la foto de antes de este movimiento, y es lo único que después permite
    reconstruir contra qué se cargó un ajuste. Si se calculara en la ruta y
    se pasara como argumento, dos movimientos simultáneos guardarían la
    misma foto.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                _SQL_STOCK_DE_ENVASES.format(comp=COMPARADOR_DESDE_EL_CONTEO)
            )
            antes = 0
            for fila in cursor.fetchall():
                # POR NOMBRE Y NO POR INDICE: acá vivía `fila[8]`, que dejó de
                # existir el día que la consulta perdió una columna y siguió
                # pareciendo correcto porque no nombra nada.
                envase = dict(zip(COLUMNAS_STOCK_DE_ENVASES, fila))
                if envase["id"] == envase_id and envase["stock"] is not None:
                    antes = int(envase["stock"])
            cursor.execute(
                """
                INSERT INTO movimientos_envase
                    (envase_id, origen, cantidad, motivo, fecha_operacion, stock_sistema,
                     colega_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (envase_id, origen, cantidad, motivo, fecha_operacion, antes, colega_id),
            )
            movimiento_id = cursor.fetchone()[0]
        conexion.commit()
        return movimiento_id
    finally:
        conexion.close()


def contar_guias_sin_declarar_el_envase() -> dict:
    """Las guías R que consumieron cajas y no dicen cuál. {"casos": n, "poblacion": n}.

    ES EL HUECO, Y SE MUESTRA. Una guía sin ficha asignada no tiene de dónde
    derivar el envase, así que queda con `lleva_caja_nuestra` en NULL — que
    NO es "no consumió caja": es "no sabemos cuál". Sumarla como cero la
    haría desaparecer adentro del total y el stock diría que sobran cajas.

    La población viaja al lado del conteo, en la misma fila: `casos 3` solo
    se puede leer contra `de 314`, y nadie se acuerda de ir a buscar el
    denominador.

    Solo cuenta desde el conteo inicial más viejo: antes de esa fecha
    ninguna guía tiene la columna escrita, y contarlas daría un hueco enorme
    y falso el primer día.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                WITH desde AS (
                    SELECT MIN(fecha_operacion) AS f
                      FROM movimientos_envase
                     WHERE origen = 'conteo_inicial' AND anulado_el IS NULL
                )
                SELECT COUNT(*) FILTER (WHERE r.lleva_caja_nuestra IS NULL),
                       COUNT(*)
                  FROM reprocesos r, desde d
                 WHERE r.anulado_el IS NULL
                   AND r.tipo <> 'inicial'
                   AND d.f IS NOT NULL
                   AND r.fecha_operacion {COMPARADOR_DESDE_EL_CONTEO} d.f
                """
            )
            casos, poblacion = cursor.fetchone()
    finally:
        conexion.close()
    return {"casos": int(casos or 0), "poblacion": int(poblacion or 0)}


VENTANA_GASTO_EN_CAJAS_DIAS = 90

_SQL_GASTO_EN_CAJAS = """
    SELECT e.nombre,
           SUM(m.cantidad)                         AS cajas,
           SUM(m.cantidad * c.costo)               AS gasto,
           COUNT(*) FILTER (WHERE c.costo IS NULL) AS sin_costo,
           MAX(m.fecha_operacion)                  AS ultima
      FROM movimientos_envase m
      JOIN envases e ON e.id = m.envase_id
      LEFT JOIN LATERAL (
          SELECT h.costo
            FROM envases_costo_historial h
           WHERE h.envase_id = m.envase_id
             AND h.vigente_desde <= m.fecha_operacion
           ORDER BY h.vigente_desde DESC
           LIMIT 1
      ) c ON true
     WHERE m.anulado_el IS NULL
       AND m.origen = 'compra'
       AND m.fecha_operacion >= %s
       AND m.fecha_operacion <= %s
     GROUP BY e.nombre
     ORDER BY e.nombre
"""


def gasto_en_cajas(desde, hasta) -> dict:
    """Cuánta plata se gastó en cajas en un período, por envase y en total.

    `hasta` NO TIENE DEFAULT, por lo mismo que en `cajas_perdidas`:
    un llamador que se lo olvidara recibiría todo hasta hoy, que es un número
    plausible contestando otra pregunta. Las dos cuentas de esta pantalla se
    leen juntas, así que tienen que recortar por el mismo período o la resta
    entre ellas no significa nada.

    ES LA ÚNICA CUENTA DE ESTE SISTEMA QUE MIRA LA PLATA DE LAS CAJAS. El
    envase se cobra adentro del precio sugerido (una caja por cada
    `contenido_caja` unidades de primera) y la Rentabilidad Real no lo toca,
    así que hasta acá comprar cajas no aparecía en ninguna pantalla: el gasto
    llegaba como sorpresa. `movimientos_envase` guarda CAJAS y no pesos, y el
    precio vive aparte en `envases_costo_historial` — esto es lo que los junta.

    EL COSTO ES EL VIGENTE A LA FECHA DE CADA COMPRA, no el de hoy. Con el
    costo de hoy una compra vieja se revalúa sola: medido sobre el fixture del
    16/09, Caja Grande daba $240.000 en vez de $200.000 — 20% de más, sin que
    nada se vea raro. Es la misma familia que leer un valor de la migración
    que lo creó en vez de leerlo de la base.

    `cajas` Y `gasto` NO TIENEN LA MISMA POBLACIÓN cuando `sin_costo` no es
    cero: una compra anterior al primer costo cargado de su envase suma cajas
    y no suma pesos (el `SUM` saltea el NULL). Por eso `sin_costo` vuelve al
    lado y la pantalla lo dice; sin esa columna el total se leería como si
    cubriera todo.

    `prestamo_salida`, `conteo_inicial` y `ajuste` NO son compras y no entran:
    mover cajas de lugar o corregir un conteo no cuesta plata. Verificado con
    los tres canarios contra `db/esquema_completo.sql` — sin el filtro de
    origen, Caja Grande pasa de 150 a 320 cajas; sin el de anuladas, a 1149.

    El LATERAL es a propósito y está medido (corolario 70): la forma agrupada
    de una pasada —tramos con `lead(vigente_desde)`— da 1,4ms contra 2,4ms a
    escala real (500 movimientos) y **80ms contra 35ms** a 50.000. Acá la
    pregunta del corolario 70 se contesta que NO: la tabla de costos tiene
    decenas de filas, así que "por fila" es una búsqueda chica y no 500
    entradas a una tabla grande. Si alguien lo cambia, medir antes de creerle.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_SQL_GASTO_EN_CAJAS, (desde, hasta))
            filas = cursor.fetchall()
    finally:
        conexion.close()

    por_envase = [
        {
            "nombre": f[0],
            "cajas": int(f[1] or 0),
            "gasto": float(f[2]) if f[2] is not None else 0.0,
            "sin_costo": int(f[3] or 0),
            "ultima": f[4],
        }
        for f in filas
    ]
    return {
        "desde": desde,
        "hasta": hasta,
        "por_envase": por_envase,
        "cajas": sum(e["cajas"] for e in por_envase),
        "gasto": sum(e["gasto"] for e in por_envase),
        "sin_costo": sum(e["sin_costo"] for e in por_envase),
        "ultima": max((e["ultima"] for e in por_envase if e["ultima"]), default=None),
    }


# EL COSTO DE LA CAJA A LA FECHA DEL HECHO, y no el de hoy: una caja perdida
# en julio no se revalúa sola. Escrito UNA vez porque lo leen dos cuentas que
# contestan preguntas distintas —la lista de reclamo por cliente y el estado
# de resultados por destino— con la misma regla de precio. Escrito dos veces
# se separa, y el día que difieran los dos números salen de la misma pantalla.
#
# Pide los alias `f` (la ficha) y `ev` (el evento, con `fecha_operacion`).
_SQL_COSTO_DEL_ENVASE_A_LA_FECHA = """
      LEFT JOIN LATERAL (
          SELECT h.costo
            FROM envases_costo_historial h
           WHERE h.envase_id = f.envase_id
             AND h.vigente_desde <= ev.fecha_operacion
           ORDER BY h.vigente_desde DESC
           LIMIT 1
      ) c ON true
"""


_SQL_CAJAS_PERDIDAS = """
    WITH eventos AS (
        -- LOS RECHAZOS. La caja se va con la mercadería que vuelve del súper
        -- y no se reusa. `cantidad` es POSITIVA acá: es un reingreso.
        SELECT pr.ficha_id, m.fecha_operacion, m.cantidad AS cajas, 'rechazo' AS origen
          FROM movimientos_stock m
          JOIN pedidos_renglones pr ON pr.id = m.pedido_renglon_id
         WHERE m.anulado_el IS NULL
           AND m.tipo = 'reingreso_rechazo'
           AND m.destino_rechazo IN ('segunda', 'devolucion_proveedor', 'reproceso')
           AND m.fecha_operacion >= %s AND m.fecha_operacion <= %s
        UNION ALL
        -- LO QUE SALE DE UNA CAJA ARMADA: la merma y el pase a segunda.
        -- Una caja armada para un cliente que se pone fea pierde la caja se
        -- tire o se mande a segunda, así que su costo tampoco se recuperó
        -- — exactamente igual que las de arriba, y por eso están en la
        -- misma lista. Es la regla del dueño del 21/09: "merma y pase se
        -- costean igual, es la misma pérdida con otro destino".
        --
        -- SOLO CON FICHA: de bultos SUELTOS no hay caja nuestra que perder
        -- (la fruta está en el cajón del proveedor), así que sumarlos
        -- contaría cajas que nunca existieron. Y los sueltos son el caso
        -- NORMAL de las dos, así que el número sería casi todo invento.
        --
        -- `-m.cantidad` PORQUE LAS DOS SON NEGATIVAS, y no `bultos_segunda`
        -- —que además la merma no tiene—: la columna que mide cuántas cajas
        -- se fueron es la del stock, y contesta para los dos tipos.
        SELECT m.ficha_id, m.fecha_operacion, -m.cantidad AS cajas,
               CASE WHEN m.tipo = 'merma' THEN 'merma' ELSE 'pase' END AS origen
          FROM movimientos_stock m
         WHERE m.anulado_el IS NULL
           AND m.tipo IN ('merma', 'pase_a_segunda')
           AND m.ficha_id IS NOT NULL
           AND m.fecha_operacion >= %s AND m.fecha_operacion <= %s
    )
    SELECT cl.nombre, a.nombre, e.nombre,
           SUM(ev.cajas)                                             AS cajas,
           SUM(ev.cajas * c.costo)                                   AS pesos,
           COUNT(*)                                                  AS veces,
           COALESCE(SUM(ev.cajas) FILTER (WHERE ev.origen <> 'rechazo'), 0) AS cajas_del_deposito,
           MAX(ev.fecha_operacion)                                   AS ultimo
      FROM eventos ev
      JOIN fichas_logistica f ON f.id = ev.ficha_id
      JOIN envases e          ON e.id = f.envase_id
      JOIN clientes cl        ON cl.id = f.cliente_id
      JOIN articulos a        ON a.id = f.articulo_id
      {costo_del_envase}
     GROUP BY cl.nombre, a.nombre, e.nombre
     ORDER BY SUM(ev.cajas * c.costo) DESC NULLS LAST, SUM(ev.cajas) DESC
"""


def cajas_perdidas(desde, hasta) -> dict:
    """Las cajas nuestras que salieron sin venderse como primera, por cliente y artículo.

    SE LLAMABA `cajas_perdidas` HASTA EL 21/09, y el nombre dejó
    de ser cierto ese día: el pase a segunda de una caja ya armada pierde la
    caja igual y no es un rechazo. Un nombre con un alcance que la función ya
    no tiene es de los que se leen y no se verifican.

    `hasta` NO TIENE DEFAULT, y es a propósito. Un llamador que se lo
    olvidara no recibiría un error: recibiría todo desde `desde` hasta hoy,
    que es un número plausible contestando otra pregunta — justo el modo de
    falla que un informe por período no puede tener.

    ORDENADA POR PLATA, y eso es lo que la vuelve una lista de trabajo: en
    Frutamax cuatro artículos se llevan el 80%, así que ordenada por cajas o
    por nombre haría falta leerla entera para encontrar los dos que importan.

    DOS ORÍGENES Y NO UNO. Los RECHAZOS, con sus tres puertas: `segunda` (se
    remite al Puesto en la caja en la que volvió), `devolucion_proveedor` (se
    va con la mercadería) y `reproceso` (se tira al pasar la fruta al cajón
    grande). Y el PASE A SEGUNDA de cajas ya armadas, desde el 21/09: la caja
    se va con la fruta y no se reusa (dicho por el dueño; con eso el modelo
    de `core/envases.py` cierra —la caja se descontó al armarla y no vuelve—
    y no hay nada que tocar en la pantalla de Cajas).

    `cajas_del_deposito` SEPARA LOS DOS LADOS, y no es un adorno: cinco cajas
    perdidas en rechazos son una conversación con el CLIENTE —le volvió
    mercadería— y cinco tiradas o pasadas a segunda son una conversación con
    el DEPÓSITO, porque la fruta se puso fea acá adentro. Sumadas en una sola
    columna, una fila del segundo tipo se lee como del primero y manda a
    reclamarle a quien no fue.

    Cuenta las DOS del depósito juntas —merma y pase— porque para esa
    pregunta son lo mismo: la caja se perdió acá. En qué se perdió lo
    contesta la pantalla de Pérdidas, que las parte por destino.

    `reproceso` ENTRÓ EL 17/09, dos días después que las otras dos. Estuvo
    afuera porque su caja ya está cobrada adentro de `rechazos_perdidos` —lo
    sigue estando— y eso contestaba sobre la plata una pregunta que era sobre
    el NOMBRE: esta lista no cobra, enumera, y sin el reproceso enumeraba dos
    tercios. `stock` es la única que no está, y es la única donde la caja se
    reusa. El porqué entero, en
    `core.costo_real.DESTINOS_QUE_SE_LLEVAN_LA_CAJA`, que es la misma lista
    que `db/cajas_7_*.sql` — y hay un test que ata las tres.

    `veces` ES LA COLUMNA QUE HACE LEGIBLE EL RESTO, y no estaba en el
    pedido: dice de cuántos eventos DISTINTOS salen esas cajas. Se llamaba
    `rechazos` hasta el 21/09, por lo mismo que la función. Un artículo
    que perdió 5 cajas en UN rechazo es un camión que volvió; el mismo número
    en CINCO es algo que pasa siempre, y son dos conversaciones distintas con
    el cliente. Sin ella, un porcentaje alto sobre números chicos no se puede
    leer (Pomelo, 5 de 5).

    EL COSTO ES EL VIGENTE A LA FECHA DE CADA RECHAZO, igual que en
    `gasto_en_cajas`: con el de hoy, una caja perdida en julio se revalúa
    sola. Las dos cuentas de esta pantalla tienen que usar el mismo reloj o
    no se pueden restar.

    `JOIN envases` Y NO `LEFT JOIN`: una ficha sin envase es envase perdido de
    origen —manzana, pera, arándano— y ahí no hay caja nuestra que perder. Con
    un LEFT JOIN esas devoluciones entrarían con `cajas` en positivo y `pesos`
    en NULL, que se lee como una fuga sin precio en vez de como lo que es.

    EL ENVASE SALE DE LA FICHA DE HOY, que es lo único que hay: ninguno de
    los dos orígenes lo declara. Cambiarle el envase a una ficha re-etiqueta
    esta historia en silencio. Ver
    docs/el_costo_de_las_cajas_que_salen_sin_venta.md
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                _SQL_CAJAS_PERDIDAS.format(costo_del_envase=_SQL_COSTO_DEL_ENVASE_A_LA_FECHA),
                (desde, hasta, desde, hasta),
            )
            filas = cursor.fetchall()
    finally:
        conexion.close()

    renglones = [
        {
            "cliente": f[0], "articulo": f[1], "envase": f[2],
            "cajas": float(f[3] or 0),
            "pesos": float(f[4]) if f[4] is not None else 0.0,
            "veces": int(f[5] or 0),
            "cajas_del_deposito": float(f[6] or 0),
            "ultimo": f[7],
        }
        for f in filas
    ]
    return {
        "desde": desde,
        "hasta": hasta,
        "renglones": renglones,
        "cajas": sum(r["cajas"] for r in renglones),
        "pesos": sum(r["pesos"] for r in renglones),
        "ultimo": max((r["ultimo"] for r in renglones if r["ultimo"]), default=None),
    }


_SQL_CAJAS_DEL_DEPOSITO_PERDIDAS = """
    WITH eventos AS (
        SELECT m.ficha_id, m.fecha_operacion, m.articulo_id,
               -m.cantidad AS cajas,
               CASE WHEN m.tipo = 'merma' THEN 'merma' ELSE 'segunda' END AS destino
          FROM movimientos_stock m
         WHERE m.anulado_el IS NULL
           AND m.tipo IN ('merma', 'pase_a_segunda')
           AND m.ficha_id IS NOT NULL
           AND m.fecha_operacion >= %s AND m.fecha_operacion <= %s
    )
    SELECT ev.destino, ev.articulo_id,
           SUM(ev.cajas)           AS cajas,
           SUM(ev.cajas * c.costo) AS pesos
      FROM eventos ev
      JOIN fichas_logistica f ON f.id = ev.ficha_id
      JOIN envases e          ON e.id = f.envase_id
      {costo_del_envase}
     GROUP BY ev.destino, ev.articulo_id
"""


def cajas_perdidas_del_deposito_por_articulo(desde, hasta) -> dict:
    """{(destino, articulo_id): (cajas, pesos)} — la caja de las MERMAS Y LOS PASES.

    PARA LA RENTABILIDAD REAL, y sale de la MISMA consulta que Pérdidas y del
    mismo `_SQL_COSTO_DEL_ENVASE_A_LA_FECHA` que Plata de cajas: el envase se
    valúa al costo vigente el día del hecho, no al de hoy. Tres pantallas
    muestran plata de la misma caja y tienen que decir lo mismo — una cuarta
    versión de la valuación se separa y nadie se entera hasta que dos números
    no cierran.

    LOS DOS DESTINOS, Y LA REGLA ES UNA SOLA (del dueño, 21/09): *"caja de Día
    armada, sea merma o pase, la pérdida son los kilos MÁS la caja"*. Se
    costean igual y se muestran separadas, así que lo que esta función tiene
    que devolver es el grano ENTERO y no una de las dos mitades: quien la lee
    manda la merma a `costo_mermas` y el pase a `costo_segunda`.

    SE LLAMABA `cajas_de_pases_por_articulo` Y DEVOLVÍA SOLO LA SEGUNDA, hasta
    el 22/09. El nombre era honesto sobre lo que hacía y la exclusión estaba
    escrita como una decisión pendiente; el dueño la cerró ese día —ya la había
    decidido el 21— y el nombre se movió con el alcance en el mismo commit.

    LA CLAVE ES EL GRANO COMPLETO DE LA CONSULTA, y eso no es prolijidad: con
    la clave más gruesa que el `GROUP BY`, un artículo con merma Y pase vuelve
    en DOS filas que colisionan, y cuál gana lo decide el orden en que Postgres
    las devuelva —no hay `ORDER BY`— (corolario 93). Acá no puede pasar: la
    clave es la del `GROUP BY`.

    `pesos` en None cuando el envase no tiene costo cargado a esa fecha: se
    devuelve 0.0 para poder sumar, y los bultos igual se cuentan. Un envase
    sin costo no es una caja que no se perdió.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                _SQL_CAJAS_DEL_DEPOSITO_PERDIDAS.format(
                    costo_del_envase=_SQL_COSTO_DEL_ENVASE_A_LA_FECHA),
                (desde, hasta),
            )
            return {
                (destino, articulo_id): (float(cantidad or 0), float(pesos or 0))
                for destino, articulo_id, cantidad, pesos in cursor.fetchall()
            }
    finally:
        conexion.close()


def perdidas_por_periodo(desde, hasta) -> dict:
    """La plata perdida en el período, partida en MERMAS y SEGUNDA.

    LA REGLA ES UNA SOLA Y ES DEL DUEÑO (21/09): *"todo lo que se tira o
    pasa a segunda es plata perdida. Va a una cuenta de resultado negativo,
    no costea a nadie y no vuelve a ningún lote. Una caja de Día armada
    pierde los kilos que tenía MÁS la caja; los bultos sueltos pierden solo
    los kilos."*

    DOS RENGLONES Y NO UNO: merma y segunda se costean IGUAL —es la misma
    pérdida con otro destino— y por eso la cuenta es la misma; se separan al
    MOSTRAR porque son dos hechos distintos del galpón y el que lee el
    resultado quiere saber cuál pesa más.

    LA MERCADERÍA SALE DEL REJUEGO DEL FIFO (`atribuir_costos_fifo`) y NO de
    una consulta propia. Es la misma función que costea la Rentabilidad Real
    y la pantalla del artículo: una segunda versión de la cuenta se separa, y
    el día que difieran los dos números salen de la misma pantalla.

    EL REJUEGO VA DESDE EL CORTE Y LA SUMA SOLO SOBRE LA VENTANA, y son dos
    recortes distintos a propósito: para saber a qué lote se le cobra una
    merma de ayer hay que haber repartido todo lo anterior. Recortar el
    rejuego a la ventana costearía contra los lotes equivocados — y
    devolvería un número plausible.

    LA CAJA SALE DE LA MISMA VALUACIÓN QUE CAJAS PERDIDAS
    (`_SQL_COSTO_DEL_ENVASE_A_LA_FECHA`): el costo vigente a la fecha del
    hecho, no el de hoy. Las dos pantallas muestran plata de la misma caja y
    tienen que decir lo mismo.

    LO QUE NO SE PUEDE COSTEAR SE MUESTRA, no se suma como cero:
    `bultos_sin_costo` son los bultos que salieron de un lote sin precio. Un
    total que se los come en silencio es más chico y se lee igual de
    cerrado — y este número va a un estado de resultados.

    `hasta` NO TIENE DEFAULT, por lo mismo que en `cajas_perdidas`: un
    llamador que se lo olvidara recibiría todo hasta hoy, que es un número
    plausible contestando otra pregunta.
    """
    from core.costo_real import atribuir_costos_fifo
    from core.stock import TIPOS_CON_FICHA_PROPIA

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            corte = _fecha_corte(cursor)
            # LOS CANDIDATOS, y el recorte es por la VENTANA: sin esto habría
            # que rejugar el FIFO del catálogo entero para contestar por los
            # pocos artículos que perdieron algo.
            cursor.execute(
                """
                SELECT DISTINCT m.articulo_id, a.nombre
                FROM movimientos_stock m
                JOIN articulos a ON a.id = m.articulo_id
                WHERE m.anulado_el IS NULL
                  AND m.tipo IN ('merma', 'pase_a_segunda')
                  AND m.fecha_operacion >= %s AND m.fecha_operacion <= %s
                """,
                (desde, hasta),
            )
            nombres = dict(cursor.fetchall())
            por_articulo = (
                _entradas_y_salidas_stock_varios(cursor, list(nombres), corte)
                if nombres else {}
            )
            cursor.execute(
                _SQL_CAJAS_DEL_DEPOSITO_PERDIDAS.format(
                    costo_del_envase=_SQL_COSTO_DEL_ENVASE_A_LA_FECHA),
                (desde, hasta),
            )
            cajas = {
                (fila[0], fila[1]): (float(fila[2] or 0),
                                     float(fila[3]) if fila[3] is not None else None)
                for fila in cursor.fetchall()
            }
    finally:
        conexion.close()

    vacio = {"bultos": 0.0, "mercaderia": 0.0, "cajas": 0.0, "caja_pesos": 0.0,
             "bultos_sin_costo": 0.0}
    renglones = {"merma": dict(vacio), "segunda": dict(vacio)}
    por_articulo_salida: dict = {}

    for articulo_id, (entradas, salidas) in por_articulo.items():
        for salida in atribuir_costos_fifo(entradas, salidas):
            if salida["tipo"] not in TIPOS_CON_FICHA_PROPIA:
                continue
            # LA VENTANA SE APLICA ACÁ, después de rejugar todo.
            if not (desde <= salida["fecha"] <= hasta):
                continue
            destino = "merma" if salida["tipo"] == "merma" else "segunda"
            bultos = float(salida["cantidad"])
            fila = renglones[destino]
            fila["bultos"] += bultos
            fila["bultos_sin_costo"] += float(salida["bultos_sin_costo"])
            # `costo` viene en None cuando NINGUNA porción tuvo precio; las
            # parciales ya están contadas en `bultos_sin_costo`.
            fila["mercaderia"] += float(salida["costo"] or 0.0)

            clave = (destino, articulo_id)
            detalle = por_articulo_salida.setdefault(
                clave, dict(vacio, destino=destino, articulo_id=articulo_id,
                            articulo=nombres.get(articulo_id, "")))
            detalle["bultos"] += bultos
            detalle["bultos_sin_costo"] += float(salida["bultos_sin_costo"])
            detalle["mercaderia"] += float(salida["costo"] or 0.0)

    for (destino, articulo_id), (cuantas, pesos) in cajas.items():
        fila = renglones[destino]
        fila["cajas"] += cuantas
        fila["caja_pesos"] += pesos or 0.0
        detalle = por_articulo_salida.setdefault(
            (destino, articulo_id),
            dict(vacio, destino=destino, articulo_id=articulo_id,
                 articulo=nombres.get(articulo_id, "")))
        detalle["cajas"] += cuantas
        detalle["caja_pesos"] += pesos or 0.0

    for fila in list(renglones.values()) + list(por_articulo_salida.values()):
        fila["total"] = fila["mercaderia"] + fila["caja_pesos"]

    return {
        "desde": desde,
        "hasta": hasta,
        "renglones": renglones,
        # ORDENADO POR PLATA, que es lo que lo vuelve una lista de trabajo:
        # por nombre habría que leerla entera para encontrar los dos que
        # importan.
        "detalle": sorted(por_articulo_salida.values(),
                          key=lambda f: (-f["total"], f["articulo"])),
        "total": sum(f["total"] for f in renglones.values()),
        "bultos_sin_costo": sum(f["bultos_sin_costo"] for f in renglones.values()),
    }


def guardar_umbral_de_envase(envase_id: int, umbral: int | None) -> None:
    """Debajo de cuántas cajas avisa la alerta de Compras. None = no vigilar este envase.

    El `>= 0` lo rechaza el CHECK de la base (`envases_umbral_no_negativo`),
    no un `if` acá: un umbral negativo es contenido, y la regla vive donde se
    escribe.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE envases SET umbral_reposicion = %s, actualizado_en = now() WHERE id = %s",
                (umbral, envase_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def _envases_a_reponer() -> list[dict]:
    """Los envases debajo de su aviso, con el faltante calculado. Uso interno.

    SALE DEL MISMO `stock_de_envases()` que la pantalla, y el filtro es la
    MISMA función (`hay_que_reponer`). Una consulta SQL propia para la alerta
    habría sido más corta y habría sido la regla escrita dos veces: el día que
    el criterio cambie, el banner y el rojo de la tarjeta dirían cosas
    distintas del mismo envase.

    Es una consulta sobre un puñado de filas —el catálogo de envases— que se
    corre cada seis horas. No hay nada que optimizar acá.
    """
    return [
        dict(envase, faltan=envase["umbral_reposicion"] - envase["stock"])
        for envase in stock_de_envases()
        if hay_que_reponer(envase)
    ]


def contar_envases_a_reponer() -> dict:
    """Cuántos envases están debajo de su aviso. Para el registro de alertas.

    Sin `mas_viejo`: un envase no tiene fecha de "cuándo empezó a faltar" —
    el stock se rejuega en cada lectura y no hay un instante en que cruzó el
    umbral. Devolver la fecha del conteo inicial sería inventar una
    antigüedad que no significa eso.
    """
    return {"casos": len(_envases_a_reponer()), "mas_viejo": None}


def detallar_envases_a_reponer() -> dict:
    """Cuáles son y cuántas faltan, para la pantalla de Alertas de Compras.

    CUENTA SUS PROPIAS FILAS: el número del banner sale de la foto de hasta
    seis horas atrás y éste sale de ahora. Que no coincidan no es un bug —son
    dos instantes— pero el resumen y la lista de ESTA pantalla tienen que
    salir del mismo lugar, que es lo único que un lector no podría explicar.
    """
    filas = _envases_a_reponer()
    return {
        "columnas": ["Envase", "Quedan", "Avisa debajo de", "Faltan"],
        "filas": [
            [f["nombre"], f["stock"], f["umbral_reposicion"], f["faltan"]]
            for f in filas
        ],
        "resumen": (
            f"{len(filas)} envase{'s' if len(filas) != 1 else ''} debajo de su aviso"
            if filas else "Ningún envase debajo de su aviso"
        ),
    }


# ============================================================================
# VACÍOS DEL DEPÓSITO — los cajones DEL PROVEEDOR DE COMPRAS
#
# NO ES EL CIRCUITO DEL PUESTO, que existe desde antes y vive en
# `vacios_recibidos` / `vacios_devueltos` / `conteos_vacios` con su propio
# universo (`proveedores_puesto`, `clientes_puesto`, `tipos_envase_puesto`).
# Allá un cliente del puesto TRAE cajones y un proveedor del puesto los
# retira; acá el cajón LLEGA CON LA MERCADERÍA y se le devuelve al proveedor
# que la vendió. No comparten una sola tabla, y los dos "proveedor" son
# tablas distintas.
#
# Y `tipos_cajon` NO ES `envases`: `envases` es la caja NUESTRA con su costo,
# la que se le factura al cliente. `tipos_cajon` es el cajón AJENO en el que
# llega la fruta. Uno se paga, el otro se devuelve.
# ============================================================================

# LAS COLUMNAS EN UN SOLO LUGAR Y EN ORDEN, por lo mismo que en el stock de
# cajas: hay dos lectores y el que direccione por índice no nombra ninguna
# columna, así que el día que la consulta gane o pierda una el `grep` del
# campo no lo encuentra. Ahí eso reventó TODO guardado con un
# "tuple index out of range" y ningún test en rojo.
COLUMNAS_STOCK_DE_VACIOS_DEPOSITO = (
    "id", "nombre", "tipo_cajon", "desde",
    "contados", "recibidos", "devueltos", "stock",
    "esperando_recepciones", "esperando_devoluciones", "esperando_desde",
)

# EL COMPARADOR NO ES PROPIO: es el MISMO de la cuenta de cajas
# (`COMPARADOR_DESDE_EL_CONTEO`), y se importa en vez de copiarse. Es la
# misma pregunta —¿lo del día del conteo ya está adentro de lo contado?— y
# escribirla dos veces es exactamente como la asimetría del día del corte
# apareció ocho veces en siete lugares que no se nombraban entre sí.
#
# Lo que la decide no es este archivo sino la PANTALLA, que le dice al que
# arranca la cuenta los tres casos: contar lo que ya llegó y fechar hoy,
# fechar ANTES para que una recepción vieja se sume, y nunca las dos cosas
# juntas. Ver el corolario 77 en CLAUDE.md.
_SQL_STOCK_DE_VACIOS_DEPOSITO = """
    WITH base AS (
        -- EL MÁS VIEJO, no el último. Un conteo posterior que re-basara la
        -- cuenta sería un ajuste disfrazado: pisaría el stock sin dejar
        -- rastro, que es justo lo que `ajustes_vacios` del puesto se niega
        -- a hacer con todas las letras. Acá el conteo ARRANCA la cuenta una
        -- vez y después el stock se deriva.
        SELECT DISTINCT ON (c.proveedor_id)
               c.proveedor_id, c.cantidad, c.fecha
          FROM conteos_vacios_deposito c
         ORDER BY c.proveedor_id, c.fecha ASC, c.id ASC
    ),
    -- LAS ENTRADAS NO SE CARGAN: SON LAS RECEPCIONES. No hay tabla de
    -- entradas ni campo que alguien tenga que acordarse de llenar — el dato
    -- ya lo carga Depósito porque necesita otra cosa. Un campo cuya única
    -- consecuencia fuera que este stock quede bien es exactamente el que se
    -- deja de llenar en dos semanas.
    --
    -- `cantidad_cajones_real` es lo ACEPTADO. Lo que se rechaza vuelve con
    -- la mercadería en el cajón del proveedor, así que esos cajones nunca
    -- se quedaron y no hay nada que devolver por ellos.
    recibidos AS (
        SELECT co.proveedor_id,
               SUM(COALESCE(co.cantidad_cajones_real, co.cantidad_cajones)) AS cajones
          FROM compras co
          JOIN base b ON b.proveedor_id = co.proveedor_id
         WHERE co.estado = 'recepcionado'
           AND co.procesada_el IS NOT NULL
           AND (co.procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
               {comp} b.fecha
         GROUP BY co.proveedor_id
    ),
    devueltos AS (
        SELECT d.proveedor_id, SUM(d.cantidad) AS cajones
          FROM vacios_deposito_devoluciones d
          JOIN base b ON b.proveedor_id = d.proveedor_id
         WHERE d.anulado_el IS NULL
           AND (d.creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
               {comp} b.fecha
         GROUP BY d.proveedor_id
    ),
    -- LO QUE ESPERA AL CONTEO, Y NO PASA POR `base` A PROPÓSITO. Las dos
    -- patas de arriba entran por `base`, así que un proveedor sin conteo no
    -- produce ni una fila: sus recepciones existen, están bien cargadas, y
    -- no se ven en ningún lado. El que entra y lee "la cuenta no arrancó" no
    -- tiene forma de saber que hay cuarenta cajones invisibles.
    --
    -- Copiarles el `JOIN base` a estas dos daría CERO justo en el único caso
    -- que les importa — un cero que no puede dar otra cosa, adentro del
    -- arreglo escrito para eso. Lo cuida el test que lee el cuerpo de las
    -- dos CTE y exige que la palabra `base` no esté.
    --
    -- Y VAN SEPARADAS: se cargan en pantallas distintas. Un solo "5
    -- esperando" manda a buscar entre las devoluciones una recepción que
    -- nunca estuvo ahí.
    esperando_recep AS (
        SELECT co.proveedor_id,
               COUNT(*) AS recepciones,
               MIN((co.procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date) AS desde
          FROM compras co
         WHERE co.estado = 'recepcionado'
           AND co.procesada_el IS NOT NULL
         GROUP BY co.proveedor_id
    ),
    esperando_dev AS (
        SELECT d.proveedor_id,
               COUNT(*) AS devoluciones,
               MIN((d.creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date) AS desde
          FROM vacios_deposito_devoluciones d
         WHERE d.anulado_el IS NULL
         GROUP BY d.proveedor_id
    )
    SELECT p.id, p.nombre, tc.nombre AS tipo_cajon,
           b.fecha AS desde,
           b.cantidad AS contados,
           COALESCE(r.cajones, 0) AS recibidos,
           COALESCE(v.cajones, 0) AS devueltos,
           b.cantidad + COALESCE(r.cajones, 0) - COALESCE(v.cajones, 0) AS stock,
           -- EN CERO CUANDO EL CONTEO SÍ ESTÁ, para que la columna signifique
           -- UNA sola cosa: cuántos movimientos son invisibles por falta de
           -- conteo. Una columna que significa dos cosas según otra columna
           -- no es una columna, son dos.
           CASE WHEN b.proveedor_id IS NULL THEN COALESCE(er.recepciones, 0) ELSE 0 END
               AS esperando_recepciones,
           CASE WHEN b.proveedor_id IS NULL THEN COALESCE(ed.devoluciones, 0) ELSE 0 END
               AS esperando_devoluciones,
           CASE WHEN b.proveedor_id IS NULL THEN LEAST(er.desde, ed.desde) END
               AS esperando_desde
      FROM proveedores p
      LEFT JOIN tipos_cajon tc ON tc.id = p.tipo_cajon_id
      LEFT JOIN base b         ON b.proveedor_id = p.id
      LEFT JOIN recibidos r    ON r.proveedor_id = p.id
      LEFT JOIN devueltos v    ON v.proveedor_id = p.id
      LEFT JOIN esperando_recep er ON er.proveedor_id = p.id
      LEFT JOIN esperando_dev ed   ON ed.proveedor_id = p.id
     WHERE p.activo = true
       AND (b.proveedor_id IS NOT NULL
            OR er.proveedor_id IS NOT NULL
            OR ed.proveedor_id IS NOT NULL)
     ORDER BY (b.proveedor_id IS NULL), 8 DESC NULLS LAST, p.nombre
"""


def stock_de_vacios_deposito() -> list[dict]:
    """Los cajones de cada proveedor que hay en el galpón. DERIVADO, una fila por proveedor.

    NO HAY UNA COLUMNA CON EL STOCK y no la va a haber: se recalcula en cada
    lectura sumando el conteo que arrancó la cuenta, las recepciones
    posteriores y las devoluciones. De ahí sale, gratis, que anular una
    devolución corrija el stock sola — no hay un segundo lugar que alguien
    tenga que acordarse de mantener al día.

    SOLO APARECEN LOS PROVEEDORES QUE TIENEN ALGO: un conteo, una recepción
    o una devolución. Los cuarenta y pico del catálogo enteros serían una
    lista que nadie lee en el celular, y el que no tiene nada no tiene nada
    que mirar.

    Y con cada fila vienen `esperando_recepciones`, `esperando_devoluciones`
    y `esperando_desde`: cuántos movimientos ya cargados NO se están
    contando porque ese proveedor todavía no tiene conteo. Sin eso, "la
    cuenta no arrancó" y "hay cuarenta cajones que no te puedo mostrar" se
    dibujan exactamente igual.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                _SQL_STOCK_DE_VACIOS_DEPOSITO.format(comp=COMPARADOR_DESDE_EL_CONTEO)
            )
            filas = cursor.fetchall()
    finally:
        conexion.close()
    return [dict(zip(COLUMNAS_STOCK_DE_VACIOS_DEPOSITO, f)) for f in filas]


def _stock_de_vacios_en_la_misma_transaccion(cursor, proveedor_id: int) -> int:
    """El stock derivado de ESE proveedor, leído con el cursor que va a escribir.

    LA FOTO LA SACA EL SERVER Y NO LA RUTA, y es lo único que después permite
    reconstruir contra qué se cargó una devolución. Calculada en la ruta y
    pasada como argumento, dos cargas simultáneas guardarían la misma foto.

    POR NOMBRE Y NO POR ÍNDICE: acá es donde en la cuenta de cajas vivía un
    `fila[8]` que dejó de existir el día que la consulta perdió una columna
    — y siguió pareciendo correcto, porque un lector por índice no nombra
    ninguna columna.
    """
    cursor.execute(
        _SQL_STOCK_DE_VACIOS_DEPOSITO.format(comp=COMPARADOR_DESDE_EL_CONTEO)
    )
    for fila in cursor.fetchall():
        proveedor = dict(zip(COLUMNAS_STOCK_DE_VACIOS_DEPOSITO, fila))
        if proveedor["id"] == proveedor_id and proveedor["stock"] is not None:
            return int(proveedor["stock"])
    return 0


def crear_conteo_vacios_deposito(proveedor_id: int, cantidad: int, fecha) -> int:
    """Arranca (o registra) el conteo físico de los cajones de un proveedor. Devuelve su id.

    DECIDE LA BASE Y ACÁ SE TRADUCE EL ERROR: que la cantidad no sea negativa
    lo rechaza el CHECK de `conteos_vacios_deposito`. No se pre-chequea — un
    pre-chequeo en Python es una segunda copia de la regla, y el día que se
    separen la que rechaza deja de ser la que el código cree que rechaza.

    CERO ES UNA CANTIDAD VÁLIDA, y no es un descuido del CHECK: contar cero
    es contar. Es además el camino para que una recepción ya cargada SE SUME
    —conteo en cero, fechado antes de esa recepción— que es uno de los tres
    casos que la pantalla explica.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            antes = _stock_de_vacios_en_la_misma_transaccion(cursor, proveedor_id)
            cursor.execute(
                """
                INSERT INTO conteos_vacios_deposito
                    (proveedor_id, cantidad, fecha, stock_sistema)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (proveedor_id, cantidad, fecha, antes),
            )
            conteo_id = cursor.fetchone()[0]
        conexion.commit()
        return conteo_id
    finally:
        conexion.close()


def crear_devolucion_vacios(proveedor_id: int, compra_id: int, cantidad: int,
                            importe: float | None = None,
                            foto_ruta: str | None = None) -> int:
    """Le devuelve al proveedor SUS cajones vacíos, contra una compra concreta. Devuelve su id.

    `compra_id` ES OBLIGATORIO y viaja hasta el INSERT: el vale no es una
    cuenta corriente contra el proveedor, vive pegado a la compra contra la
    que se entregó. Lo ata el NOT NULL de la base.

    EL IMPORTE NO TOCA `compras.importe` NI EL COSTEO, y es una decisión del
    dueño, no un pendiente: es plata de ENVASE y no de mercadería, y el
    sistema ya trata al envase por su lado. Meterlo adentro del importe de la
    compra mezclaría dos cosas que hoy están separadas y re-escribiría un
    número que ya se cargó en Administración. El neto se lee SUMANDO las dos
    —la devolución guarda `compra_id`, así que es un join— no cambiando una.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            antes = _stock_de_vacios_en_la_misma_transaccion(cursor, proveedor_id)
            cursor.execute(
                """
                INSERT INTO vacios_deposito_devoluciones
                    (proveedor_id, compra_id, cantidad, importe, foto_ruta, stock_sistema)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (proveedor_id, compra_id, cantidad, importe, foto_ruta, antes),
            )
            devolucion_id = cursor.fetchone()[0]
        conexion.commit()
        return devolucion_id
    finally:
        conexion.close()


def anular_devolucion_vacios(devolucion_id: int) -> None:
    """Anula una devolución. NUNCA la borra: el registro queda como corrección.

    LA EXISTENCIA SE PREGUNTA CON UN SELECT SIN AGREGADO, que es lo único que
    puede contestar "no hay". Con un `count(*)` la fila vuelve con 0 aunque
    no haya nada que contar, así que `fetchone() is None` no es None JAMÁS y
    la guarda no se dispara — el mismo hecho que en plpgsql hace que
    `if not found` después de un agregado no salte nunca.

    Y NO PISA UN `anulado_el` YA PUESTO: anular dos veces borraría cuándo se
    anuló de verdad, que es peor que no anular.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT anulado_el FROM vacios_deposito_devoluciones WHERE id = %s",
                (devolucion_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa devolución no existe.")
            if fila[0] is not None:
                raise ValueError("Esa devolución ya estaba anulada.")
            cursor.execute(
                "UPDATE vacios_deposito_devoluciones SET anulado_el = now() WHERE id = %s",
                (devolucion_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_devoluciones_vacios(proveedor_id: int, limite: int = 30) -> list[dict]:
    """Las devoluciones de un proveedor, la más nueva primero. Las anuladas TAMBIÉN.

    Se muestran las anuladas a propósito: una devolución que desaparece de la
    lista deja al que la cargó buscando qué hizo mal. Viene `anulada` para que
    la pantalla la pinte como lo que es — una corrección, no un hueco.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id, d.cantidad, d.importe, d.foto_ruta,
                       (d.creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date,
                       d.anulado_el IS NOT NULL,
                       d.compra_id, a.nombre, c.fecha_operacion
                  FROM vacios_deposito_devoluciones d
                  JOIN compras c   ON c.id = d.compra_id
                  JOIN articulos a ON a.id = c.articulo_id
                 WHERE d.proveedor_id = %s
                 ORDER BY d.creado_en DESC, d.id DESC
                 LIMIT %s
                """,
                (proveedor_id, limite),
            )
            filas = cursor.fetchall()
    finally:
        conexion.close()
    return [
        {"id": f[0], "cantidad": f[1], "importe": f[2], "foto_ruta": f[3],
         "fecha": f[4], "anulada": f[5], "compra_id": f[6],
         "articulo": f[7], "fecha_compra": f[8]}
        for f in filas
    ]


def compras_para_vale_de_vacios(proveedor_id: int, limite: int = 40) -> list[dict]:
    """Las compras recepcionadas de ese proveedor, para elegir contra cuál va el vale.

    Solo las RECEPCIONADAS: un vale contra una compra que todavía no llegó
    describe cajones que no están en el galpón. La pantalla no ofrece lo que
    la escritura después rechazaría — un callejón es peor que no ofrecer nada.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, a.nombre,
                       COALESCE(c.cantidad_cajones_real, c.cantidad_cajones)
                  FROM compras c
                  JOIN articulos a ON a.id = c.articulo_id
                 WHERE c.proveedor_id = %s
                   AND c.estado = 'recepcionado'
                 ORDER BY c.fecha_operacion DESC, c.id DESC
                 LIMIT %s
                """,
                (proveedor_id, limite),
            )
            filas = cursor.fetchall()
    finally:
        conexion.close()
    return [{"id": f[0], "fecha": f[1], "articulo": f[2], "cajones": f[3]} for f in filas]


def listar_tipos_cajon() -> list[dict]:
    """El catálogo de tipos de cajón del depósito, activos, por nombre."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre FROM tipos_cajon WHERE activo = true ORDER BY nombre"
            )
            filas = cursor.fetchall()
    finally:
        conexion.close()
    return [{"id": f[0], "nombre": f[1]} for f in filas]


def crear_tipo_cajon(nombre: str) -> int:
    """Agrega un tipo de cajón. Devuelve su id.

    EL PLEGADO ESTÁ ESCRITO UNA SOLA VEZ, en `normalizar_texto`, y la base
    solo hace cumplir la unicidad de lo que Python escribió. No hay una
    segunda expresión en SQL que pueda separarse de ésta — que es como "Cajón
    Chico" entró al lado de "cajon  chico" en la tabla de al lado.

    Y NO SE PRE-PREGUNTA "¿ya existe?": se intenta insertar y se traduce la
    violación del unique. Preguntar antes es la regla escrita dos veces, y
    entre la pregunta y el INSERT cabe otra carga.
    """
    normalizado = normalizar_texto(nombre)
    if not normalizado:
        raise ValueError("Poné un nombre para el cajón.")
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO tipos_cajon (nombre, nombre_normalizado) VALUES (%s, %s) RETURNING id",
                    # El nombre que se MUESTRA también colapsa los espacios de
                    # adentro: si no, "Cajón  Chico" y "Cajón Chico" se ven
                    # distintos en la pantalla y el índice los considera el
                    # mismo — dos cosas que el operario no puede conciliar.
                    (" ".join(nombre.split()), normalizado),
                )
            except psycopg2.errors.UniqueViolation:
                conexion.rollback()
                # SI EL CONSTRAINT RECHAZA Y NO ENCONTRAMOS EL MOTIVO, ESO SE
                # DICE: es la señal de que las dos reglas se separaron, y
                # tragarla es cómo se pierde meses después.
                with conexion.cursor() as buscador:
                    buscador.execute(
                        "SELECT nombre FROM tipos_cajon WHERE nombre_normalizado = %s",
                        (normalizado,),
                    )
                    fila = buscador.fetchone()
                if fila is None:
                    raise ValueError(
                        "La base rechazó el cajón por repetido y no encuentro cuál es: "
                        "el plegado de Python y el de la base dejaron de coincidir."
                    )
                raise ValueError(f"Ese cajón ya está cargado como «{fila[0]}».")
            tipo_id = cursor.fetchone()[0]
        conexion.commit()
        return tipo_id
    finally:
        conexion.close()


def asignar_tipo_cajon(proveedor_id: int, tipo_cajon_id: int | None) -> None:
    """En qué cajón entrega ese proveedor. UNO SOLO.

    Es un atributo del proveedor y no una segunda dimensión de la cuenta,
    porque un proveedor entrega siempre en el mismo tipo: el tipo es CÓMO SE
    LLAMA su cajón, no un eje contra el cual contar. El circuito del puesto
    sí tiene las dos dimensiones —allá un cliente trae cajones de varios
    tipos— y por eso todas sus tablas llevan `tipo_envase_id`. La diferencia
    no es de estilo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE proveedores SET tipo_cajon_id = %s, actualizado_en = now() WHERE id = %s",
                (tipo_cajon_id, proveedor_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def buscar_tipo_cajon_por_nombre(nombre: str) -> int | None:
    """El id del tipo de cajón que se llame así, o None. Pliega igual que el alta.

    USA `normalizar_texto`, que es la MISMA función con la que se escribió
    `nombre_normalizado`. Una comparación escrita a mano acá sería la regla
    dos veces: la que busca dejaría de encontrar lo que la que guarda
    considera repetido, y el que tipea "Cajón Chico" se comería un rechazo
    sin ver dónde está el que ya existe.
    """
    normalizado = normalizar_texto(nombre)
    if not normalizado:
        return None
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM tipos_cajon WHERE nombre_normalizado = %s", (normalizado,)
            )
            fila = cursor.fetchone()
    finally:
        conexion.close()
    return None if fila is None else int(fila[0])
