"""Conexión a la base de datos (Supabase / PostgreSQL).

Aísla la conexión en su propio módulo para que sea fácil de reemplazar o
testear (con mocks), igual que se hizo con la llamada a la API de Claude en
core/lector_comandas.py.
"""

import os
from contextlib import contextmanager

import psycopg2

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
                SELECT id, nombre, merma_porcentaje, unidad_compra, contenido_referencia, grupo
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
                SELECT id, nombre, merma_porcentaje, unidad_compra, contenido_referencia, grupo
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


def crear_articulo(nombre: str, unidad_compra: str, contenido_referencia: float | None, grupo: str | None = None) -> None:
    """Inserta un artículo nuevo en la tabla articulos. grupo es opcional: None = sin clasificar todavía."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO articulos (nombre, unidad_compra, contenido_referencia, grupo) VALUES (%s, %s, %s, %s)",
                (nombre, unidad_compra, contenido_referencia, grupo),
            )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_articulo(
    articulo_id: int, nombre: str, unidad_compra: str, contenido_referencia: float | None, grupo: str | None = None
) -> None:
    """Actualiza nombre, unidad de compra, contenido de referencia y grupo de un artículo existente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE articulos
                SET nombre = %s, unidad_compra = %s, contenido_referencia = %s, grupo = %s, actualizado_en = now()
                WHERE id = %s
                """,
                (nombre, unidad_compra, contenido_referencia, grupo, articulo_id),
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


_CLIENTE_CON_TASAS_VIGENTES_SQL = """
    WITH vigentes AS (
        SELECT DISTINCT ON (cliente_id, nombre_parametro) cliente_id, nombre_parametro, tipo, valor
        FROM clientes_parametros_historial
        WHERE vigente_desde <= CURRENT_DATE
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

    filas_utilidad = [fila for fila in filas if fila["tipo"] == "utilidad"]
    utilidad = None
    if filas_utilidad:
        fila_utilidad = next(
            (fila for fila in filas_utilidad if fila["nombre_parametro"] == "utilidad_objetivo"),
            filas_utilidad[0],
        )
        utilidad = float(fila_utilidad["valor"])

    return {"tasas_suman": tasas_suman, "tasas_restan": tasas_restan, "utilidad": utilidad}


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
                """
                SELECT DISTINCT ON (nombre_parametro) nombre_parametro, tipo, valor
                FROM clientes_parametros_historial
                WHERE cliente_id = %s AND vigente_desde <= CURRENT_DATE
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


def _insertar_conceptos_cliente(cursor, cliente_id: int, conceptos: list[dict]) -> None:
    """Inserta cada concepto con vigente_desde = hoy, sin pisar historial viejo.

    conceptos: [{"nombre_parametro", "tipo", "valor"}, ...] (valor en
    fracción). Si ya existe una fila de HOY para ese mismo (cliente_id,
    nombre_parametro) -- segunda edición el mismo día -- la actualiza en
    vez de duplicarla; nunca toca una fila de vigente_desde anterior.
    """
    for concepto in conceptos:
        cursor.execute(
            """
            INSERT INTO clientes_parametros_historial (cliente_id, nombre_parametro, valor, tipo, vigente_desde)
            VALUES (%s, %s, %s, %s, CURRENT_DATE)
            ON CONFLICT (cliente_id, nombre_parametro, vigente_desde)
            DO UPDATE SET valor = EXCLUDED.valor, tipo = EXCLUDED.tipo
            """,
            (cliente_id, concepto["nombre_parametro"], concepto["valor"], concepto["tipo"]),
        )


def crear_cliente(nombre: str, tasas_suma: list[dict], tasas_resta: list[dict], utilidad_objetivo: float) -> int:
    """Crea un cliente y su primer registro de historial (vigente_desde = hoy). Devuelve el id creado.

    tasas_suma/tasas_resta: [{"nombre", "valor"}, ...] con valor ya en
    fracción (0.21, no 21). utilidad_objetivo también en fracción.
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
            _insertar_conceptos_cliente(cursor, cliente_id, conceptos)
        conexion.commit()
        return cliente_id
    finally:
        conexion.close()


def actualizar_cliente(cliente_id: int, nombre: str, conceptos_a_guardar: list[dict]) -> None:
    """Actualiza el nombre del cliente y agrega SOLO las filas de historial que realmente cambiaron.

    conceptos_a_guardar: [{"nombre_parametro", "tipo", "valor"}, ...] — ya
    calculado por core.conceptos_cliente (calcular_cambios_de_tasas /
    calcular_cambio_de_utilidad) a partir de lo que cambió en el
    formulario. El nombre/utilidad/tasas viejos NUNCA se pisan: cada
    cambio agrega una fila nueva con vigente_desde = hoy.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE clientes SET nombre = %s, actualizado_en = now() WHERE id = %s", (nombre, cliente_id)
            )
            _insertar_conceptos_cliente(cursor, cliente_id, conceptos_a_guardar)
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
    Sistema, que antes pedía las fichas cliente por cliente.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT fl.id, fl.cliente_id, fl.articulo_id, a.nombre AS articulo_nombre,
                       a.grupo AS articulo_grupo, fl.envase_id, e.nombre AS envase_nombre,
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
                       fl.contenido_caja, fl.unidad_venta, fl.envase_variable, fl.nombre_cliente, fl.codigo_cliente
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


def crear_envase(nombre: str, costo: float) -> None:
    """Crea un envase (del catálogo compartido) con su costo inicial vigente desde hoy — todo en una transacción.

    Nombre repetido: ValueError con mensaje para mostrar tal cual (chequeado
    acá y además garantizado por el UNIQUE global de la tabla).
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
                "INSERT INTO envases_costo_historial (envase_id, costo, vigente_desde) VALUES (%s, %s, CURRENT_DATE)",
                (envase_id, costo),
            )
        conexion.commit()
    finally:
        conexion.close()


def registrar_costo_envase(envase_id: int, costo: float) -> None:
    """Registra un costo nuevo para un envase, vigente desde hoy — la regla de oro del historial.

    NUNCA pisa filas anteriores: inserta una fila nueva en
    envases_costo_historial (mismo criterio que los precios de venta y los
    parámetros de cliente) — así los cálculos pasados siguen usando el
    costo que regía en su momento. La única excepción es cambiar dos veces
    el MISMO día: ahí se actualiza la fila de hoy (ON CONFLICT), igual que
    en precios_venta_historial. La baja de un envase es esto mismo con
    costo 0.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO envases_costo_historial (envase_id, costo, vigente_desde)
                VALUES (%s, %s, CURRENT_DATE)
                ON CONFLICT (envase_id, vigente_desde) DO UPDATE SET costo = EXCLUDED.costo
                """,
                (envase_id, costo),
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

    OJO, y por eso este camino ya casi no hace falta: la ficha nueva tiene
    id NUEVO, y los precios y los renglones de pedido cuelgan de la ficha
    con ON DELETE SET NULL. Cambiar el artículo DESCONECTA el historial de
    precios y los renglones viejos de esa ficha. Para tener dos
    presentaciones del mismo artículo (Banana Bolivia y Banana Ecuador) ya
    NO se muda esta ficha: se CREA una segunda, que es exactamente lo que
    habilitó sacar el unique (ver db/permitir_varias_fichas_por_articulo.sql).

    Devuelve el id de la ficha nueva, o None si la ficha no existe. Desde
    que un cliente puede tener varias fichas del mismo artículo, apuntar a
    un artículo que ya tiene otra ficha ya no lo corta la base — queda como
    dos fichas de ese artículo, que puede ser justo lo buscado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
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


def obtener_o_crear_proveedor_por_codigo(codigo_puesto: str, nombre: str) -> int:
    """Busca un proveedor por codigo_puesto (la identidad) o lo crea; el nombre siempre se actualiza.

    "La última corrección manda": si el código ya existe pero con otro nombre guardado, se
    pisa con el nombre recién cargado.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id FROM proveedores WHERE codigo_puesto = %s", (codigo_puesto,))
            fila = cursor.fetchone()
            if fila is not None:
                proveedor_id = fila[0]
                cursor.execute(
                    "UPDATE proveedores SET nombre = %s, actualizado_en = now() WHERE id = %s",
                    (nombre, proveedor_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO proveedores (codigo_puesto, nombre) VALUES (%s, %s) RETURNING id",
                    (codigo_puesto, nombre),
                )
                proveedor_id = cursor.fetchone()[0]
        conexion.commit()
        return proveedor_id
    finally:
        conexion.close()


def listar_proveedores() -> list[dict]:
    """Devuelve todos los proveedores (id, codigo_puesto, nombre), para el autocompletar del alta."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, codigo_puesto, nombre FROM proveedores ORDER BY codigo_puesto")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
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
                SELECT c.id, c.fecha_operacion, a.nombre AS articulo_nombre, a.unidad_compra,
                       p.nombre AS proveedor_nombre,
                       p.codigo_puesto AS proveedor_codigo_puesto,
                       COALESCE(c.cantidad_cajones_real, c.cantidad_cajones) AS cantidad_cajones,
                       COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon) AS contenido_por_cajon,
                       COALESCE(c.cantidad_kilos_real, c.cantidad_kilos) AS cantidad_kilos,
                       COALESCE(c.cantidad_fraccion_real, c.cantidad_fraccion) AS cantidad_fraccion,
                       c.importe, c.sena, c.tipo_retiro,
                       EXISTS (SELECT 1 FROM fotos_guia fg WHERE fg.guia_id = c.guia_id) AS tiene_fotos
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE {" AND ".join(condiciones)}
                ORDER BY c.fecha_operacion DESC, p.codigo_puesto, c.cargado_el
                {tope_sql}
                """,
                parametros,
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
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

    cantidad_cajones/contenido_por_cajon/cantidad_kilos vienen con el valor
    REAL (pesado por Depósito) si ya existe, si no el estimado — ver
    recepcionar_compra. app/costeo.py arma su cuenta como
    cantidad_cajones × contenido_por_cajon (nunca lee cantidad_kilos), así
    que esta sustitución alcanza sola para que el costo, el precio sugerido
    y la utilidad aproximada usen el real en cuanto existe, sin tocar
    ninguna fórmula ahí.

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


def guardar_precios_cliente(cliente_id: int, cambios: list[dict], foto_ruta: str | None = None) -> None:
    """Agrega a precios_venta_historial SOLO las filas de precio que realmente cambiaron.

    cambios: [{"ficha_id", "precio"}, ...] — ya calculado por
    core.precios_venta.calcular_cambios_de_precios a partir de lo que
    cambió en el formulario. El precio es de la FICHA (la clave de venta):
    dos fichas del mismo artículo y cliente tienen precios distintos.

    El articulo_id de la fila NO viaja desde la pantalla: sale de la
    propia ficha dentro del INSERT, así no puede quedar apuntando a un
    artículo que no es el de su ficha.

    Cada uno se inserta con vigente_desde = hoy; el precio viejo NUNCA se
    pisa. Si ya existe una fila de HOY para esa misma ficha -- segunda
    edición el mismo día -- se actualiza esa en vez de duplicarla.

    foto_ruta es la ruta del archivo (foto/PDF/Excel) del bucket "comandas"
    del que salieron estos precios (ver "Cargar Foto Precios") — None para
    la Carga Manual, que no tiene archivo. En un conflicto (segunda edición
    el mismo día), solo se pisa foto_ruta si el nuevo valor no es None: una
    corrección manual del mismo día no debe borrar la trazabilidad de una
    carga por archivo anterior de ese mismo día.
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
                    SELECT fl.id, fl.articulo_id, %s, %s, CURRENT_DATE, %s
                    FROM fichas_logistica fl
                    WHERE fl.id = %s AND fl.cliente_id = %s
                    ON CONFLICT (ficha_id, vigente_desde)
                    DO UPDATE SET
                        precio = EXCLUDED.precio,
                        foto_ruta = COALESCE(EXCLUDED.foto_ruta, precios_venta_historial.foto_ruta)
                    """,
                    (cliente_id, cambio["precio"], foto_ruta, cambio["ficha_id"], cliente_id),
                )
        conexion.commit()
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
                       c.articulo_id, a.nombre AS articulo_nombre, a.unidad_compra,
                       c.proveedor_id, p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.guia_id, c.guia_punto,
                       c.cantidad_cajones, c.contenido_por_cajon, c.importe, c.sena, c.tipo_retiro,
                       c.estado_retiro, c.retiro_procesado_el, c.retiro_origen, c.cantidad_cajones_retirada,
                       c.estado, c.procesada_el,
                       c.cantidad_cajones_real, c.contenido_por_cajon_real, c.cantidad_fraccion_real,
                       c.cantidad_cajones_rechazada, c.motivo_rechazo
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
) -> None:
    """Inserta una compra cargada por el comprador, con su guía asignada.

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
            )
        conexion.commit()
    finally:
        conexion.close()


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
) -> None:
    """Inserta UNA compra (con su guía) usando el cursor que le pasan — sin abrir conexión ni commitear.

    Es el cuerpo de crear_compra (ver su docstring para el significado de
    cada campo y de las tres ramas), separado para que
    crear_compras_de_comanda pueda insertar varios renglones en UNA sola
    transacción: quien llama decide cuándo commitear.

    carga_token solo viene en compras que salen de una comanda leída por
    foto (ver crear_compras_de_comanda); en la carga manual y en el
    ingreso directo va None.
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

    # La foto cuelga de la GUÍA, no del renglón: se registra una vez por
    # guía (el ON CONFLICT absorbe los N renglones de la misma comanda).
    if foto_ruta:
        cursor.execute(
            "INSERT INTO fotos_guia (guia_id, foto_ruta) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (guia_id, foto_ruta),
        )

    cursor.execute("SELECT COUNT(*) FROM compras WHERE guia_id = %s", (guia_id,))
    (cantidad_existente,) = cursor.fetchone()
    guia_punto = cantidad_existente + 1

    if ingreso_directo_deposito:
        cursor.execute(
            """
            INSERT INTO compras
                (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro,
                 guia_id, guia_punto, estado, estado_retiro,
                 cantidad_cajones_real, contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real,
                 procesada_el, retiro_procesado_el, retiro_origen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'recepcionado', 'retirado', %s, %s, %s, %s, now(), now(), 'ingreso_directo')
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
            ),
        )
    elif tipo_retiro in ORIGEN_RETIRO_AUTOMATICO_POR_TIPO:
        cursor.execute(
            """
            INSERT INTO compras
                (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro,
                 guia_id, guia_punto, carga_token, estado, estado_retiro, retiro_procesado_el, retiro_origen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', 'retirado', now(), %s)
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
                ORIGEN_RETIRO_AUTOMATICO_POR_TIPO[tipo_retiro],
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO compras
                (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro,
                 guia_id, guia_punto, carga_token, estado, estado_retiro)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', 'pendiente')
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
            ),
        )


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
) -> None:
    """Actualiza artículo/cantidad/tipo de retiro de una compra existente. No toca importe ni seña.

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
                        cantidad_kilos = %s, cantidad_fraccion = %s, tipo_retiro = %s,
                        estado_retiro = 'retirado', retiro_procesado_el = now(), retiro_origen = %s
                    WHERE id = %s
                    """,
                    (
                        articulo_id, cantidad_cajones, contenido_por_cajon, cantidad_kilos, cantidad_fraccion,
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
                        cantidad_kilos = %s, cantidad_fraccion = %s, tipo_retiro = %s,
                        estado_retiro = 'pendiente', retiro_procesado_el = NULL,
                        retiro_origen = NULL, cantidad_cajones_retirada = NULL
                    WHERE id = %s
                    """,
                    (articulo_id, cantidad_cajones, contenido_por_cajon, cantidad_kilos, cantidad_fraccion, tipo_retiro, compra_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE compras
                    SET articulo_id = %s, cantidad_cajones = %s, contenido_por_cajon = %s,
                        cantidad_kilos = %s, cantidad_fraccion = %s, tipo_retiro = %s
                    WHERE id = %s
                    """,
                    (articulo_id, cantidad_cajones, contenido_por_cajon, cantidad_kilos, cantidad_fraccion, tipo_retiro, compra_id),
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

            cursor.execute("UPDATE compras SET importe = %s, sena = %s WHERE id = %s", (importe, sena, compra_id))
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
                       a.nombre AS articulo_nombre, a.unidad_compra,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.cantidad_cajones, c.contenido_por_cajon, c.cantidad_kilos, c.cantidad_fraccion
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


def _derivar_valores_reales(
    unidad_compra: str | None, cantidad_cajones_real: float, valor_real: float
) -> tuple[float | None, float | None, float | None]:
    """A partir de lo que Depósito mira en UN cajón/bulto, arma (contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real).

    valor_real es SIEMPRE por cajón/bulto — nunca el total de toda la
    carga junta — sea kilos, unidades o cubetas: Depósito mira un bulto
    por vez (lo pesa o lo cuenta), no suma de cabeza toda la carga (usado
    tanto para recepcionar por primera vez como para corregir una
    recepción ya hecha, ver recepcionar_compra y corregir_recepcion_compra).

    contenido_por_cajon_real es directamente valor_real. El total (kilos
    o fracción según la unidad) se deriva multiplicando por
    cantidad_cajones_real — nunca al revés, para no terminar promediando
    un total mal cargado en un número por cajón que nadie escribió.
    """
    total = cantidad_cajones_real * valor_real
    if unidad_compra == "kilo":
        return valor_real, total, None
    return valor_real, None, total


def recepcionar_compra(
    compra_id: int,
    cantidad_cajones_real: float,
    valor_real: float,
    cantidad_cajones_rechazada: float | None = None,
    motivo_rechazo: str | None = None,
) -> str | None:
    """Marca una compra como recepcionada, con los valores REALES que pesó/contó Depósito.

    Ver _derivar_valores_reales para el significado de valor_real según la
    unidad de compra del artículo. El estimado (cantidad_cajones/
    contenido_por_cajon/etc., sin "_real") nunca se toca.

    Rechazo parcial: si Depósito devolvió parte de la carga al proveedor,
    cantidad_cajones_rechazada es cuántos bultos devolvió (y motivo_rechazo
    por qué). Es SOLO registro: cantidad_cajones_real ya viene con los
    bultos aceptados (llegados − rechazados) y es la que usa todo el
    costeo — como el importe es por bulto, ninguna cuenta cambia.

    Además marca la compra como retirada (ver _auto_retirar_si_corresponde)
    si todavía no lo estaba. Devuelve el aviso de esa función (o None).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.unidad_compra
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            unidad_compra = fila[0] if fila else None

            contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real = _derivar_valores_reales(
                unidad_compra, cantidad_cajones_real, valor_real
            )

            cursor.execute(
                """
                UPDATE compras
                SET estado = 'recepcionado',
                    cantidad_cajones_real = %s,
                    contenido_por_cajon_real = %s,
                    cantidad_kilos_real = %s,
                    cantidad_fraccion_real = %s,
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
                    cantidad_cajones_rechazada,
                    motivo_rechazo,
                    compra_id,
                ),
            )

            aviso = _auto_retirar_si_corresponde(cursor, compra_id)
        conexion.commit()
        return aviso
    finally:
        conexion.close()


def corregir_recepcion_compra(
    compra_id: int,
    cantidad_cajones_real: float,
    valor_real: float,
    cantidad_cajones_rechazada: float | None = None,
    motivo_rechazo: str | None = None,
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
                SELECT c.estado, a.unidad_compra
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.id = %s
                """,
                (compra_id,),
            )
            fila = cursor.fetchone()
            estado, unidad_compra = fila if fila else (None, None)

            if estado != "recepcionado":
                raise ValueError("Esta compra no está recepcionada, no hay valores reales para corregir.")

            contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real = _derivar_valores_reales(
                unidad_compra, cantidad_cajones_real, valor_real
            )

            cursor.execute(
                """
                UPDATE compras
                SET cantidad_cajones_real = %s,
                    contenido_por_cajon_real = %s,
                    cantidad_kilos_real = %s,
                    cantidad_fraccion_real = %s,
                    cantidad_cajones_rechazada = %s,
                    motivo_rechazo = %s
                WHERE id = %s
                """,
                (
                    cantidad_cajones_real,
                    contenido_por_cajon_real,
                    cantidad_kilos_real,
                    cantidad_fraccion_real,
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
    """True si ya no se puede deshacer un "No ingresó" (ver /deposito/recepcion, deshacer_no_ingresado_compra).

    Única definición de esta regla — la usan el panel "Procesados hoy" de
    Recepción (para mostrar el botón Deshacer o el aviso de por qué no) y
    deshacer_no_ingresado_compra (para bloquear el guardado de verdad).
    Recepcionada o rechazada: la mercadería ya se contó (o se rechazó
    después de contarla), ese resultado ya es un hecho, no hay nada que
    "deshacer" ahí — si hubo un error, se corrige por otro lado. Solo
    no_ingresado se puede volver a pendiente: significa que nunca se
    contó nada, así que no hay ningún conteo real que se pierda al
    corregir el toque.
    """
    return estado in ("recepcionado", "rechazado")


def deshacer_no_ingresado_compra(compra_id: int) -> None:
    """Vuelve una compra marcada "No ingresó" a pendiente de recepción (deshacer, ver /deposito/recepcion).

    Vuelve estado a 'pendiente' y borra procesada_el junto con todos los
    valores reales (cantidad_cajones_real, contenido_por_cajon_real,
    cantidad_kilos_real, cantidad_fraccion_real) — aunque marcar_compra_
    no_ingresada nunca los llega a cargar, se limpian igual acá por las
    dudas, mismo criterio "sin cicatriz" que deshacer_retiro_compra. No
    toca estado_retiro: marcar_compra_no_ingresada tampoco lo tocaba.
    Bloqueada (ValueError) si compra_tiene_deshacer_recepcion_bloqueado
    ya dio True — re-chequeado acá adentro, no solo en la pantalla.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT estado FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            estado = fila[0] if fila else None

            if compra_tiene_deshacer_recepcion_bloqueado(estado):
                raise ValueError("Esta compra ya fue recepcionada o rechazada, no se puede deshacer.")

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
        conexion.commit()
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
                       c.estado, c.procesada_el
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.estado IN ('recepcionado', 'rechazado', 'no_ingresado')
                  AND c.procesada_el >= %s AND c.procesada_el < %s::date + 1
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
    condiciones = ["c.procesada_el >= %s", "c.procesada_el < %s::date + 1"]
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
                       c.cantidad_cajones_rechazada, c.motivo_rechazo, c.importe, c.sena,
                       a.nombre AS articulo_nombre, a.unidad_compra,
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
                """
                SELECT COUNT(*), MIN(c.fecha_operacion)
                FROM compras c
                WHERE c.importe IS NULL
                  AND c.estado IN ('pendiente', 'recepcionado')
                  AND c.estado_retiro IN ('pendiente', 'retirado')
                """
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
                """
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT c.articulo_id FROM compras c WHERE c.fecha_operacion >= %s
                ) comprados
                WHERE NOT EXISTS (
                        SELECT 1 FROM fichas_logistica f WHERE f.articulo_id = comprados.articulo_id)
                   OR NOT EXISTS (
                        SELECT 1 FROM precios_venta_historial p
                        WHERE p.articulo_id = comprados.articulo_id AND p.vigente_desde <= %s)
                """,
                (fecha_desde, hoy),
            )
            (casos,) = cursor.fetchone()
        return int(casos)
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
                  AND v.creado_en < %s
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
                       a.nombre AS articulo_nombre, a.unidad_compra,
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
                SELECT c.id, a.nombre AS articulo_nombre, a.unidad_compra,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       c.cantidad_cajones, c.contenido_por_cajon, c.cantidad_cajones_retirada,
                       c.estado_retiro, c.retiro_procesado_el, c.estado
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.tipo_retiro = %s
                  AND c.estado_retiro IN ('retirado', 'cancelado')
                  AND c.retiro_procesado_el >= %s AND c.retiro_procesado_el < %s::date + 1
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
    recepcionado) y estado_retiro en (pendiente, retirado). Rechazada,
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
                SELECT c.id, c.fecha_operacion, a.nombre AS articulo_nombre, a.unidad_compra,
                       p.nombre AS proveedor_nombre,
                       p.codigo_puesto AS proveedor_codigo_puesto,
                       COALESCE(c.cantidad_cajones_real, c.cantidad_cajones) AS cantidad_cajones,
                       COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon) AS contenido_por_cajon
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.importe IS NULL
                  AND c.estado IN ('pendiente', 'recepcionado')
                  AND c.estado_retiro IN ('pendiente', 'retirado')
                ORDER BY c.fecha_operacion, p.codigo_puesto, c.cargado_el
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def actualizar_importe_compra(compra_id: int, importe: float) -> None:
    """Completa el importe de una compra que había quedado sin precio."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE compras SET importe = %s WHERE id = %s", (importe, compra_id))
        conexion.commit()
    finally:
        conexion.close()


def eliminar_compra(compra_id: int) -> list[str]:
    """Borra una compra (borrado real), salvo que ya haya pasado por Depósito o por el retiro.

    Una compra recepcionada tiene kilaje real pesado, una retirada ya
    salió del puesto, y una marcada "No ingresó" es un registro de
    Depósito que tiene que quedar fijo (el comprador no puede hacerlo
    desaparecer borrando la compra) — borrar cualquiera de las tres se
    rechaza acá con un ValueError (el mensaje es el que se le muestra al
    usuario tal cual). Por ahora esto no tiene excepción: cuando exista
    el sistema de permisos, un gerente podrá forzarlo con su acceso,
    pero eso no se resuelve en esta función. 'pendiente' y
    'rechazado'/'cancelado' se siguen pudiendo borrar sin restricción.

    Las fotos cuelgan de la GUÍA (fotos_guia), no del renglón: borrar una
    compra no toca las fotos mientras la guía siga teniendo renglones.
    Si esta era la ÚLTIMA compra de su guía, las fotos de la guía se dan
    de baja también, y se devuelven las rutas a borrar del Storage — SOLO
    las que ninguna otra guía usa (el Listado consolidado comparte un
    archivo entre varias guías). Todo dentro de la misma transacción,
    para no tener carrera entre el DELETE y los conteos.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT guia_id, estado, estado_retiro FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            guia_id, estado, estado_retiro = fila if fila else (None, None, None)

            if estado == "recepcionado":
                raise ValueError("Esta compra ya fue recepcionada, no se puede eliminar.")
            if estado == "no_ingresado":
                # Antes que el chequeo de retiro: para el usuario el dato
                # importante es que Depósito la marcó "No ingresó", no si
                # además estaba retirada.
                raise ValueError(
                    'Esta compra quedó registrada como "No ingresó" en Depósito, no se puede eliminar.'
                )
            if estado_retiro == "retirado":
                raise ValueError("Esta compra ya fue retirada, no se puede eliminar.")

            cursor.execute("DELETE FROM compras WHERE id = %s", (compra_id,))

            rutas_a_borrar: list[str] = []
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
    nuevo. En la práctica todos los renglones de una misma foto comparten
    la misma fecha_operacion (se cargan juntos y esa fecha no se puede
    editar después), pero este chequeo se hace igual por las dudas.

    Las fotos cuelgan de las guías (fotos_guia): un archivo es candidato
    si TODAS las guías que lo usan son de antes de fecha_corte —
    MAX(fecha de guía) por ruta, una sola pasada.
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
                """,
                (fecha_corte,),
            )
            filas = cursor.fetchall()
        return [fila[0] for fila in filas]
    finally:
        conexion.close()


def limpiar_foto_ruta_de_compras(foto_ruta: str) -> None:
    """Borra los registros de un archivo ya eliminado del bucket: sus filas de fotos_guia.

    Se usa después de borrar el archivo del Storage (limpieza de fotos
    viejas). Las fotos viven SOLO en fotos_guia: compras.foto_ruta quedó
    muerta tras agregar_fotos_guia.sql y su DROP es
    db/drop_foto_ruta_compras.sql.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM fotos_guia WHERE foto_ruta = %s", (foto_ruta,))
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
    retiradas o marcadas "No ingresó" quedan afuera del borrado (mismo
    criterio que eliminar_compra) — nunca en silencio, quien llama tiene
    que avisar con los números que devuelve esta función, no dar por
    hecho que se borró todo.

    Devuelve {"borradas": int, "protegidas": int}.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM compras WHERE fecha_operacion = %s AND proveedor_id = %s",
                (fecha_operacion, proveedor_id),
            )
            (total,) = cursor.fetchone()

            cursor.execute(
                """
                DELETE FROM compras
                WHERE fecha_operacion = %s AND proveedor_id = %s
                  AND estado IS DISTINCT FROM 'recepcionado'
                  AND estado IS DISTINCT FROM 'no_ingresado'
                  AND estado_retiro IS DISTINCT FROM 'retirado'
                """,
                (fecha_operacion, proveedor_id),
            )
            borradas = cursor.rowcount
        conexion.commit()
        return {"borradas": borradas, "protegidas": total - borradas}
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
                       c.nombre AS cliente_nombre,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre
                FROM vacios_recibidos v
                JOIN clientes_puesto c ON c.id = v.cliente_puesto_id
                JOIN proveedores_puesto p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id
                WHERE v.creado_en >= %s AND v.creado_en < %s::date + 1
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
                WHERE v.creado_en >= %s AND v.creado_en < %s::date + 1
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


def anular_vacio_recibido(movimiento_id: int) -> None:
    """Anula una entrada (baja lógica): el registro queda visible como corrección, el stock lo excluye."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE vacios_recibidos SET anulado_el = now() WHERE id = %s AND anulado_el IS NULL",
                (movimiento_id,),
            )
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
    filtro_fecha = "" if fecha_hasta is None else "AND creado_en < %s::date + 1"
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
                WHERE a.creado_en >= %s AND a.creado_en < %s::date + 1
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
                WHERE c.creado_en >= %s AND c.creado_en < %s::date + 1
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
          AND h.vigente_desde <= v.creado_en::date
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
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
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
                    WHERE h.tipo_envase_id = t.id AND h.vigente_desde <= CURRENT_DATE
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
                      AND h.vigente_desde <= v.creado_en::date
                    ORDER BY h.vigente_desde DESC, h.creado_en DESC
                    LIMIT 1
                ) actual ON true
                WHERE v.tipo_envase_id = %s
                  AND v.anulado_el IS NULL
                  AND v.creado_en::date >= %s
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
                           WHEN v.sena_vale_el IS NOT NULL THEN 'vale'
                           ELSE 'anulada'
                       END AS cierre,
                       COALESCE(v.sena_pagada_el, v.sena_vale_el, v.sena_anulada_el) AS cerrada_el,
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
                ORDER BY COALESCE(v.sena_pagada_el, v.sena_vale_el, v.sena_anulada_el) DESC
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
                       r.kilos_enviados, r.anulado_el
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
        conexion.commit()
    finally:
        conexion.close()


def desmarcar_renglon_armado(renglon_id: int) -> None:
    """Destilda un renglón (toque por error, o apareció el stock): vuelve arriba, sin cantidad parcial."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE pedidos_renglones SET armado_el = NULL, cantidad_armada = NULL, kilos_enviados = NULL WHERE id = %s",
                (renglon_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def anular_renglon_pedido(renglon_id: int) -> None:
    """La CRUZ del armado: este renglón directamente no se va a armar. Anulado, nunca borrado.

    Si estaba tildado, el tilde y sus números se limpian: anulado y armado
    son estados excluyentes — un renglón anulado no manda nada.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pedidos_renglones
                SET anulado_el = now(), armado_el = NULL, cantidad_armada = NULL, kilos_enviados = NULL
                WHERE id = %s
                """,
                (renglon_id,),
            )
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
    """Los renglones de los pedidos VIGENTES del rango, para Buscar Pedidos (lo que se factura).

    Trae los KILOS ENVIADOS tal cual los grabó el depósito al armar —
    NULL si el renglón no se armó: la pantalla lo dice, jamás se calcula
    el kilaje de la ficha en el listado. Los anulados vienen marcados
    (anulado_el), nunca desaparecen. Una fila por renglón, del pedido
    vigente de cada fecha (los reemplazados no cuentan doble).
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
                SELECT v.fecha_operacion, r.id, r.sucursal, r.articulo_id,
                       COALESCE(a.nombre, r.texto_descripcion, r.texto_codigo) AS articulo_nombre,
                       r.cantidad, r.cantidad_armada, r.kilos_enviados, r.armado_el, r.anulado_el
                FROM vigentes v
                JOIN pedidos_renglones r ON r.pedido_id = v.id
                LEFT JOIN articulos a ON a.id = r.articulo_id
                ORDER BY v.fecha_operacion DESC, (r.anulado_el IS NOT NULL),
                         COALESCE(a.nombre, r.texto_descripcion, r.texto_codigo), r.sucursal
                """,
                (cliente_id, fecha_desde, fecha_hasta),
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
                SELECT COUNT(*), MIN(recibido_el)::date
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
                SELECT COUNT(*), MIN(recibido_el)::date
                FROM mails_pedido
                WHERE leido_con_ia AND recibido_el >= %s
                """,
                (fecha_desde,),
            )
            casos, mas_viejo = cursor.fetchone()
        return {"casos": int(casos), "mas_viejo": mas_viejo}
    finally:
        conexion.close()


def listar_pedidos_vigentes_con_armado(cliente_id: int, fecha_desde) -> list[dict]:
    """Los pedidos VIVOS de un cliente desde una fecha (pasados recientes y TODOS los futuros), con su estado de armado.

    Una fila por fecha (el vigente: el más nuevo sin anular), con lo justo
    para verlos de un vistazo sin entrar a cada uno: renglones
    identificados, cuántos están armados y cuántos quedaron sin
    identificar — "Pedido del 22/08 — 18 de 32 armados".
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
                        WHERE r.pedido_id = p.id AND r.articulo_id IS NULL) AS sin_identificar
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
                JOIN pedidos_renglones r ON r.pedido_id = v.id
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


def fecha_corte():
    """La fecha desde la que rige el modelo nuevo (una sola fila en corte_modelo).

    Vive en la base y no en el código para que se lea de UN lugar: la
    usan el stock inicial, las guías R sin ficha (antes del corte un NULL
    es dato viejo, después es "sin asignar") y todo lo que venga.

    Si la fila no está, revienta a propósito: una base a medio configurar
    tiene que avisar, no elegir una fecha por su cuenta y costear contra
    lotes que no corresponden.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT fecha FROM corte_modelo WHERE id = 1")
            fila = cursor.fetchone()
        if fila is None:
            raise RuntimeError(
                "No hay fecha de corte cargada (corte_modelo está vacía): "
                "la base quedó a medio configurar."
            )
        return fila[0]
    finally:
        conexion.close()


# --- Stock del Depósito ---
# El stock por artículo NUNCA se guarda: se calcula siempre, derivado de
# compras recepcionadas (entradas), renglones armados de pedidos vigentes
# (salidas) y movimientos_stock (ajustes, mermas, reingresos por rechazo).
# Todo en BULTOS. Puede quedar negativo a propósito: el armado no se traba
# por stock — el negativo es la señal de que falta un reproceso o un ajuste.

_SQL_SUMAS_STOCK = """
    WITH entradas AS (
        SELECT articulo_id, SUM(cantidad_cajones_real) AS total
        FROM compras WHERE estado = 'recepcionado' {filtro_articulo}
        GROUP BY articulo_id
    ), vigentes AS (
        SELECT DISTINCT ON (cliente_id, fecha_operacion) id
        FROM pedidos WHERE anulado_el IS NULL
        ORDER BY cliente_id, fecha_operacion, creado_en DESC
    ), salidas AS (
        SELECT r.articulo_id, SUM(COALESCE(r.cantidad_armada, r.cantidad)) AS total
        FROM pedidos_renglones r JOIN vigentes v ON v.id = r.pedido_id
        WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL
          AND r.articulo_id IS NOT NULL {filtro_r_articulo}
        GROUP BY r.articulo_id
    ), reingresos AS (
        -- Solo los que QUEDAN en stock: un rechazo mandado a segunda (o
        -- pasado de vuelta a cajón grande) sale del stock normal y suma
        -- al pool de segunda. NULL = los reingresos viejos, que quedaban
        -- en stock por definición.
        SELECT articulo_id, SUM(cantidad) AS total
        FROM movimientos_stock
        WHERE anulado_el IS NULL AND tipo = 'reingreso_rechazo'
          AND (destino_rechazo IS NULL OR destino_rechazo = 'stock') {filtro_articulo}
        GROUP BY articulo_id
    ), ajustes AS (
        SELECT articulo_id, SUM(cantidad) AS total
        FROM movimientos_stock
        WHERE anulado_el IS NULL AND tipo <> 'reingreso_rechazo' {filtro_articulo}
        GROUP BY articulo_id
    ), reproc AS (
        SELECT articulo_id, SUM(bultos_primera) AS entradas, SUM(bultos_tomados) AS salidas
        FROM reprocesos
        WHERE anulado_el IS NULL {filtro_articulo}
        GROUP BY articulo_id
    )
"""


def _sql_sumas_stock(por_articulo: bool) -> str:
    filtro = "AND articulo_id = %s" if por_articulo else ""
    filtro_r = "AND r.articulo_id = %s" if por_articulo else ""
    return _SQL_SUMAS_STOCK.format(filtro_articulo=filtro, filtro_r_articulo=filtro_r)


def stock_deposito_por_articulo() -> list[dict]:
    """El stock del sistema por artículo (bultos), calculado siempre — solo artículos con algún movimiento.

    entradas = compras recepcionadas (cantidad_cajones_real, la cuenta REAL
    de Depósito, ya neta del rechazo al proveedor). salidas = renglones
    armados de pedidos VIGENTES (cantidad_armada si armó menos, sino la
    pedida); los reemplazados y anulados no cuentan. reingresos va aparte
    de los otros movimientos porque el dueño lo quiere ver como número
    propio: es mercadería ya costeada y ya vendida que volvió (plata
    perdida), no stock "normal".
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                _sql_sumas_stock(por_articulo=False)
                + """
                , segunda AS (
                    SELECT articulo_id, SUM(bultos_segunda) AS total
                    FROM reprocesos WHERE anulado_el IS NULL GROUP BY articulo_id
                ), segunda_rechazo AS (
                    -- Los rechazos que no volvieron al stock: entran al
                    -- mismo pool que la segunda de los reprocesos.
                    SELECT articulo_id, SUM(bultos_segunda) AS total
                    FROM movimientos_stock
                    WHERE anulado_el IS NULL AND destino_rechazo IN ('segunda', 'reproceso')
                    GROUP BY articulo_id
                ), remitida AS (
                    SELECT articulo_id, SUM(bultos) AS total
                    FROM remitos_segunda WHERE anulado_el IS NULL GROUP BY articulo_id
                )
                SELECT a.id AS articulo_id, a.nombre,
                       COALESCE(e.total, 0) AS entradas,
                       COALESCE(s.total, 0) AS salidas,
                       COALESCE(r.total, 0) AS reingresos,
                       COALESCE(aj.total, 0) AS ajustes,
                       COALESCE(rp.entradas, 0) AS reproceso_primera,
                       COALESCE(rp.salidas, 0) AS reproceso_tomados,
                       COALESCE(sg.total, 0) AS segunda_producida,
                       COALESCE(sr.total, 0) AS segunda_de_rechazos,
                       COALESCE(rm.total, 0) AS segunda_remitida
                FROM articulos a
                LEFT JOIN entradas e ON e.articulo_id = a.id
                LEFT JOIN salidas s ON s.articulo_id = a.id
                LEFT JOIN reingresos r ON r.articulo_id = a.id
                LEFT JOIN ajustes aj ON aj.articulo_id = a.id
                LEFT JOIN reproc rp ON rp.articulo_id = a.id
                LEFT JOIN segunda sg ON sg.articulo_id = a.id
                LEFT JOIN segunda_rechazo sr ON sr.articulo_id = a.id
                LEFT JOIN remitida rm ON rm.articulo_id = a.id
                WHERE e.total IS NOT NULL OR s.total IS NOT NULL
                   OR r.total IS NOT NULL OR aj.total IS NOT NULL
                   OR rp.articulo_id IS NOT NULL OR sr.articulo_id IS NOT NULL
                ORDER BY a.nombre
                """
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
            fila["segunda"] = (
                float(fila["segunda_producida"]) + float(fila["segunda_de_rechazos"])
                - float(fila["segunda_remitida"])
            )
        return filas
    finally:
        conexion.close()


def _stock_deposito_actual(cursor, articulo_id: int) -> float:
    """El stock actual de UN artículo, con el cursor abierto — para la foto (stock_sistema) de un movimiento nuevo."""
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
        (articulo_id, articulo_id, articulo_id, articulo_id, articulo_id),
    )
    return float(cursor.fetchone()[0])


def stock_deposito_de_articulo(articulo_id: int) -> float:
    """El stock actual de un artículo (para pantallas: precarga del ajuste desde el cotejo, avisos)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            return _stock_deposito_actual(cursor, articulo_id)
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
                     lote_tipo, lote_origen_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (articulo_id, tipo, cantidad, motivo, cliente_id, fecha_operacion, stock_sistema,
                 pedido_renglon_id, costo_por_bulto, destino_rechazo, bultos_segunda,
                 lote_tipo, lote_origen_id),
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


def _entradas_y_salidas_stock_varios(cursor, articulo_ids: list[int]) -> dict:
    """La cuenta de lotes y salidas de VARIOS artículos, con el cursor abierto.

    Devuelve {articulo_id: (entradas, total_salidas, dirigidas)}, con una
    entrada por cada id pedido — el que no tiene ningún movimiento sale con
    listas vacías y cero, nunca ausente: un artículo que no aparece rompería
    al que lo lee, y "sin movimiento" es un resultado, no un faltante.

    Son las MISMAS tres consultas de siempre con "= ANY(%s)" en vez de "= %s".
    Antes se corrían una vez por artículo, con su conexión cada vez: el listado
    de Stock del Sistema abría una por artículo con guía R, y la Rentabilidad
    Real dos por artículo del rango. Con el reproceso funcionando eso crece con
    el catálogo.

    El reparto en sí NO cambia: cada artículo recibe exactamente las mismas
    listas que recibía antes, y el motor (core/stock.py, core/costo_real.py)
    ni se entera.
    """
    ids = list(articulo_ids)
    entradas_por_articulo = {articulo_id: [] for articulo_id in ids}
    dirigidas_por_articulo = {articulo_id: [] for articulo_id in ids}
    if not ids:
        return {}

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
                   c.cantidad_cajones_real AS cantidad,
                   c.importe AS costo_bulto,
                   NULL::bigint AS cliente_lote_id,
                   c.articulo_id AS articulo_id
            FROM compras c
            JOIN proveedores p ON p.id = c.proveedor_id
            LEFT JOIN guias_compra g ON g.id = c.guia_id
            WHERE c.estado = 'recepcionado' AND c.articulo_id = ANY(%s)
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
        ) lotes
        ORDER BY articulo_id, fecha_orden, momento_orden
        """,
        (ids, ids, ids),
    )
    columnas = [descripcion[0] for descripcion in cursor.description]
    for fila in cursor.fetchall():
        lote = dict(zip(columnas, fila))
        entradas_por_articulo[lote.pop("articulo_id")].append(lote)

    cursor.execute(
        """
        WITH vigentes AS (
            SELECT DISTINCT ON (cliente_id, fecha_operacion) id
            FROM pedidos WHERE anulado_el IS NULL
            ORDER BY cliente_id, fecha_operacion, creado_en DESC
        ),
        armados AS (
            SELECT r.articulo_id, SUM(COALESCE(r.cantidad_armada, r.cantidad)) AS total
            FROM pedidos_renglones r JOIN vigentes v ON v.id = r.pedido_id
            WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL
              AND r.articulo_id = ANY(%s)
            GROUP BY r.articulo_id
        ),
        negativos AS (
            SELECT articulo_id, -SUM(cantidad) AS total FROM movimientos_stock
            WHERE anulado_el IS NULL AND cantidad < 0 AND articulo_id = ANY(%s)
            GROUP BY articulo_id
        ),
        tomados AS (
            SELECT articulo_id, SUM(bultos_tomados) AS total FROM reprocesos
            WHERE anulado_el IS NULL AND articulo_id = ANY(%s)
            GROUP BY articulo_id
        )
        -- unnest y no una tabla: así sale una fila por CADA id pedido, tenga
        -- movimientos o no. Sin esto, un artículo sin nada quedaría afuera.
        SELECT pedidos_ids.id,
               COALESCE(a.total, 0) + COALESCE(n.total, 0) + COALESCE(t.total, 0)
        FROM unnest(%s::bigint[]) AS pedidos_ids(id)
        LEFT JOIN armados a ON a.articulo_id = pedidos_ids.id
        LEFT JOIN negativos n ON n.articulo_id = pedidos_ids.id
        LEFT JOIN tomados t ON t.articulo_id = pedidos_ids.id
        """,
        (ids, ids, ids, ids),
    )
    total_por_articulo = {articulo_id: float(total) for articulo_id, total in cursor.fetchall()}

    # Las mermas DIRIGIDAS a un lote viajan aparte del total (ya están
    # sumadas adentro): el reparto necesita saber a qué lote va cada una
    # para descontarla de ahí y no del más viejo.
    cursor.execute(
        """
        SELECT -cantidad AS cantidad, lote_tipo, lote_origen_id, articulo_id
        FROM movimientos_stock
        WHERE anulado_el IS NULL AND articulo_id = ANY(%s) AND lote_tipo IS NOT NULL
        ORDER BY articulo_id, fecha_operacion, creado_en
        """,
        (ids,),
    )
    columnas = [descripcion[0] for descripcion in cursor.description]
    for fila in cursor.fetchall():
        dirigida = dict(zip(columnas, fila))
        dirigidas_por_articulo[dirigida.pop("articulo_id")].append(dirigida)

    resultado = {}
    for articulo_id in ids:
        dirigidas = dirigidas_por_articulo[articulo_id]
        # El total NO puede contarlas dos veces: se restan del bloque general.
        total = total_por_articulo[articulo_id] - sum(float(d["cantidad"]) for d in dirigidas)
        resultado[articulo_id] = (entradas_por_articulo[articulo_id], total, dirigidas)
    return resultado


def _entradas_y_salidas_stock(cursor, articulo_id: int) -> tuple[list[dict], float, list[dict]]:
    """La cuenta interna de lotes y salidas de UN artículo, con el cursor abierto.

    La usa crear_reproceso, que necesita rejugar el FIFO adentro de su propia
    transacción antes de insertar. Es la de varios con un solo id: una sola
    consulta de cada cosa, para que no puedan desincronizarse nunca.
    """
    return _entradas_y_salidas_stock_varios(cursor, [articulo_id])[articulo_id]


def entradas_y_salidas_stock_articulos(articulo_ids: list[int]) -> dict:
    """Los lotes, el total de salidas y las mermas dirigidas de VARIOS artículos, en UNA conexión.

    Devuelve {articulo_id: (entradas, total_salidas, dirigidas)}. Es la que
    usan las pantallas que miran muchos artículos de una (Stock del Sistema,
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


def entradas_y_salidas_stock_articulo(articulo_id: int) -> tuple[list[dict], float, list[dict]]:
    """Los lotes de entrada de un artículo (orden FIFO), el total de bultos salidos y las mermas dirigidas a un lote.

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


def total_reingresos_rechazo() -> float:
    """Total histórico de bultos reingresados por rechazo del cliente (plata perdida): el dueño lo quiere a la vista."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(cantidad), 0) FROM movimientos_stock
                WHERE anulado_el IS NULL AND tipo = 'reingreso_rechazo'
                """
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
                       p.fecha_operacion AS fecha_pedido, r.sucursal AS sucursal_pedido
                FROM movimientos_stock m
                JOIN articulos a ON a.id = m.articulo_id
                LEFT JOIN clientes cl ON cl.id = m.cliente_id
                LEFT JOIN pedidos_renglones r ON r.id = m.pedido_renglon_id
                LEFT JOIN pedidos p ON p.id = r.pedido_id
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
_SQL_STOCK_PARTIDO = """
    WITH vigentes AS (
        SELECT DISTINCT ON (cliente_id, fecha_operacion) id
        FROM pedidos WHERE anulado_el IS NULL
        ORDER BY cliente_id, fecha_operacion, creado_en DESC
    ), armadas AS (
        SELECT articulo_id, ficha_id, SUM(bultos_primera) AS total
        FROM reprocesos
        WHERE anulado_el IS NULL AND ficha_id IS NOT NULL
        GROUP BY articulo_id, ficha_id
    ), salidas_ficha AS (
        SELECT r.articulo_id, r.ficha_id,
               SUM(COALESCE(r.cantidad_armada, r.cantidad)) AS total
        FROM pedidos_renglones r JOIN vigentes v ON v.id = r.pedido_id
        WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL
          AND r.articulo_id IS NOT NULL AND r.ficha_id IS NOT NULL
        GROUP BY r.articulo_id, r.ficha_id
    ), fichas_con_algo AS (
        SELECT articulo_id, ficha_id FROM armadas
        UNION
        SELECT articulo_id, ficha_id FROM salidas_ficha
    )
    SELECT f.articulo_id, f.ficha_id,
           COALESCE(a.total, 0) - COALESCE(s.total, 0) AS stock
    FROM fichas_con_algo f
    LEFT JOIN armadas a ON a.articulo_id = f.articulo_id AND a.ficha_id = f.ficha_id
    LEFT JOIN salidas_ficha s ON s.articulo_id = f.articulo_id AND s.ficha_id = f.ficha_id
"""


def _cajas_por_ficha(cursor) -> dict:
    """{(articulo_id, ficha_id): stock de cajas armadas}, SOLO las fichas con algún movimiento.

    Una ficha sin nada reprocesado ni nada salido no aparece. Es a
    propósito: si el Cotejo listara todas las fichas de todos los clientes
    en cero, la pantalla se vuelve ilegible y se deja de mirar.
    """
    cursor.execute(_SQL_STOCK_PARTIDO)
    return {(fila[0], fila[1]): float(fila[2]) for fila in cursor.fetchall()}


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
                for (_, ficha_id), cajas in _cajas_por_ficha(cursor).items()
                if cajas > 0
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
        return cajas.get((articulo_id, ficha_id), 0.0)
    total = _stock_deposito_actual(cursor, articulo_id)
    return round(total - sum(v for (a, _), v in cajas.items() if a == articulo_id), 2)


def crear_conteo_stock(articulo_id: int, cantidad: float, ficha_id: int | None = None) -> None:
    """Conteo físico del operario del depósito. El stock del sistema se graba acá, del lado del server — NUNCA se le devuelve.

    A propósito no retorna nada: la pantalla de Stock Físico no puede
    mostrar el número del sistema (si el operario lo ve, transcribe en
    vez de contar — se pierde el control cruzado; mismo criterio que
    Vacíos). El Cotejo compara después contra esta foto exacta. Si se
    equivoca, carga de nuevo: en el Cotejo vale el último por porción.

    ficha_id dice QUÉ contó: una ficha son sus cajas ya armadas, y None
    son los bultos sueltos del artículo, sin procesar. Los sueltos son el
    caso más común, no una excepción.

    El conteo es DECLARATIVO: no se valida contra lo que el sistema cree
    tener. Si cuenta cajas de una ficha de la que el sistema no tiene
    nada, se guarda igual y el Cotejo muestra la diferencia — que es
    exactamente para lo que está.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            stock_sistema = _stock_de_ficha(cursor, articulo_id, ficha_id)
            cursor.execute(
                """
                INSERT INTO conteos_stock (articulo_id, cantidad, stock_sistema, ficha_id)
                VALUES (%s, %s, %s, %s)
                """,
                (articulo_id, cantidad, stock_sistema, ficha_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_conteos_stock_de_fecha(fecha) -> list[dict]:
    """Conteos de un día para la lista "Contado hoy" del operario.

    SIN stock_sistema en el SELECT, a propósito: esta lista la ve el
    operario, y el número del sistema no puede viajar ni escondido en el
    HTML de su pantalla.

    Trae la ficha porque desde la etapa 3 el mismo artículo aparece
    varias veces en la lista —los sueltos y cada ficha— y sin decir cuál
    es cada uno, "Banana 40 / Banana 12" no se entiende.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.cantidad, c.creado_en, a.nombre AS articulo_nombre,
                       c.ficha_id,
                       COALESCE(NULLIF(BTRIM(f.nombre_cliente), ''), fa.nombre) AS ficha_nombre,
                       cl.nombre AS ficha_cliente
                FROM conteos_stock c
                JOIN articulos a ON a.id = c.articulo_id
                LEFT JOIN fichas_logistica f ON f.id = c.ficha_id
                LEFT JOIN articulos fa ON fa.id = f.articulo_id
                LEFT JOIN clientes cl ON cl.id = f.cliente_id
                WHERE c.creado_en >= %s AND c.creado_en < %s::date + 1
                ORDER BY c.creado_en DESC
                """,
                (fecha, fecha),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def listar_ultimos_conteos_stock() -> list[dict]:
    """El ÚLTIMO conteo por PORCIÓN (artículo + ficha), con su foto del sistema, para el Cotejo.

    Desde la etapa 3 un artículo tiene varias porciones: sus bultos
    sueltos y las cajas de cada ficha. El último de cada una vale por su
    cuenta — contar las cajas de una ficha no invalida el conteo de
    sueltos de la mañana.

    Sale de conteos_stock y de ningún otro lado: una ficha que nunca se
    contó no genera renglón. Si el Cotejo listara todas las fichas de
    todos los clientes en cero, la pantalla se vuelve ilegible y se deja
    de mirar.

    El orden del DISTINCT ON es el del índice conteos_stock_cotejo_idx.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (c.articulo_id, c.ficha_id)
                       c.id, c.articulo_id, c.ficha_id, c.cantidad, c.stock_sistema, c.creado_en,
                       a.nombre AS articulo_nombre,
                       COALESCE(NULLIF(BTRIM(f.nombre_cliente), ''), fa.nombre) AS ficha_nombre,
                       cl.nombre AS ficha_cliente
                FROM conteos_stock c
                JOIN articulos a ON a.id = c.articulo_id
                LEFT JOIN fichas_logistica f ON f.id = c.ficha_id
                LEFT JOIN articulos fa ON fa.id = f.articulo_id
                LEFT JOIN clientes cl ON cl.id = f.cliente_id
                ORDER BY c.articulo_id, c.ficha_id, c.creado_en DESC
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        # Cada artículo junto, y adentro los sueltos primero: es la porción
        # más grande y la que más se cuenta.
        filas.sort(key=lambda fila: (fila["articulo_nombre"],
                                     fila["ficha_id"] is not None,
                                     fila["ficha_nombre"] or ""))
        return filas
    finally:
        conexion.close()


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
                """
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

    Una guía anulada no se asigna: ya no cuenta para nada.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT articulo_id, anulado_el IS NOT NULL FROM reprocesos WHERE id = %s",
                (reproceso_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Esa guía R no existe.")
            articulo_id, anulada = fila
            if anulada:
                raise ValueError("Esa guía R está anulada: no se le asigna ficha.")

            if ficha_id is not None:
                cursor.execute(
                    "SELECT articulo_id FROM fichas_logistica WHERE id = %s", (ficha_id,)
                )
                ficha = cursor.fetchone()
                if ficha is None:
                    raise ValueError("Esa ficha no existe.")
                if ficha[0] != articulo_id:
                    raise ValueError("Esa ficha es de otro artículo: no puede ser la de esta guía R.")

            cursor.execute("UPDATE reprocesos SET ficha_id = %s WHERE id = %s", (ficha_id, reproceso_id))
        conexion.commit()
    finally:
        conexion.close()


def crear_reproceso(
    articulo_id: int,
    bultos_tomados: float,
    bultos_primera: float,
    bultos_segunda: float,
    bultos_merma: float,
    fecha_operacion,
    cliente_id: int | None = None,
    ficha_id: int | None = None,
) -> int:
    """Carga una guía R: el SERVER corre el FIFO acá y congela consumos y costo. Devuelve el número de guía.

    Los consumos salen de repartir lo tomado entre los lotes con resto,
    del más viejo primero — el operario no elige lote jamás. Si lo tomado
    supera lo que los lotes cubren, el resto queda como consumo
    'sin_lote' (el piso es la verdad: no se traba, y la diferencia queda
    a la vista). El costo por bulto se congela del importe de la compra
    de cada lote (o del costo de primera si el lote es de otra guía R);
    un lote sin precio deja el consumo sin costo, y con UN consumo sin
    costo la guía queda con costo_total NULL = "costo incompleto" —
    nunca se promedia con números inventados. Todo en UNA transacción.

    ficha_id: a qué ficha fueron las cajas de primera. None = SIN
    ASIGNAR, y en la pantalla eso se elige a propósito, no se llega por
    no contestar. No se puede derivar de (cliente, artículo): un cliente
    puede tener varias fichas del mismo artículo — pide Banana Bolivia y
    recibe Banana Ecuador — así que esa derivación es ambigua por diseño
    y lo va a ser siempre.
    """
    from core.stock import repartir_fifo, salidas_para_reparto

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            entradas, total_salidas, dirigidas = _entradas_y_salidas_stock(cursor, articulo_id)
            for e in entradas:
                e["orden"] = (e["fecha_orden"], e["momento_orden"])
            lotes = repartir_fifo(entradas, salidas_para_reparto(total_salidas, dirigidas))["lotes"]

            consumos = []
            pendiente = float(bultos_tomados)
            for lote in lotes:
                if pendiente <= 0:
                    break
                if lote["restante"] <= 0:
                    continue
                bultos = min(lote["restante"], pendiente)
                pendiente = round(pendiente - bultos, 2)
                origen = "compra" if lote["tipo_lote"] == "guia" else lote["tipo_lote"]
                consumos.append(
                    {
                        "origen": origen,
                        "compra_id": lote["origen_id"] if origen == "compra" else None,
                        "origen_id": lote["origen_id"],
                        "bultos": bultos,
                        "costo_por_bulto": float(lote["costo_bulto"]) if lote["costo_bulto"] is not None else None,
                    }
                )
            if pendiente > 0:
                consumos.append(
                    {"origen": "sin_lote", "compra_id": None, "origen_id": None,
                     "bultos": pendiente, "costo_por_bulto": None}
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
                     cliente_id, ficha_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                 bultos_segunda, bultos_merma, costo_total, costo_por_bulto_primera,
                 cliente_id, ficha_id),
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
        conexion.commit()
        return reproceso_id
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


def listar_reprocesos_por_rango(fecha_desde, fecha_hasta) -> list[dict]:
    """Las guías R del rango (por fecha_operacion), anuladas incluidas y marcadas, con sus consumos adentro.

    Cada guía trae "consumos": de qué lote salió cada bulto, con la guía
    de compra y el proveedor cuando el lote es una compra — la
    trazabilidad hacia atrás completa ("de la 105 tomé 30...").

    Y trae la FICHA a la que fueron las cajas de primera, con su nombre
    para mostrar. ficha_id en NULL = sin asignar: esta pantalla es donde
    se completa, así que esas guías tienen que aparecer, no esconderse.
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
                       COALESCE(NULLIF(BTRIM(f.nombre_cliente), ''), fa.nombre) AS ficha_nombre
                FROM reprocesos rp
                JOIN articulos a ON a.id = rp.articulo_id
                LEFT JOIN clientes cl ON cl.id = rp.cliente_id
                LEFT JOIN fichas_logistica f ON f.id = rp.ficha_id
                LEFT JOIN articulos fa ON fa.id = f.articulo_id
                WHERE rp.fecha_operacion >= %s AND rp.fecha_operacion <= %s
                ORDER BY rp.fecha_operacion DESC, rp.id DESC
                """,
                (fecha_desde, fecha_hasta),
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


def crear_remito_segunda(articulo_id: int, bultos: float, fecha_operacion) -> None:
    """Remito de segunda al Puesto (destino fijo): sale del pool de segunda y deja de ser problema del depósito.

    A propósito no devuelve nada: la pantalla es de operario y el pool no
    se le muestra. El recupero económico va aparte, más adelante.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO remitos_segunda (articulo_id, bultos, fecha_operacion) VALUES (%s, %s, %s)",
                (articulo_id, bultos, fecha_operacion),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_remitos_segunda_por_rango(fecha_desde, fecha_hasta) -> list[dict]:
    """Los remitos de segunda del rango (por fecha_operacion), anulados incluidos y marcados — para Movimientos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.bultos, r.fecha_operacion, r.creado_en, r.anulado_el,
                       a.nombre AS articulo_nombre
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


def contar_reprocesos_costo_incompleto() -> dict:
    """Auditoría: guías R vigentes con el costo sin cerrar (algún lote sin precio), y la más vieja.

    Mientras haya una, la rentabilidad real de ese reproceso no se puede
    calcular: o falta cargar el precio de una compra (se arregla con
    "Completar costo"), o consumió stock inicial/reingreso/sin lote (no
    hay precio posible y hay que saberlo).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN(fecha_operacion) FROM reprocesos
                WHERE anulado_el IS NULL AND costo_total IS NULL
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
                    SELECT articulo_id FROM movimientos_stock
                    WHERE anulado_el IS NULL AND tipo = 'merma'
                      AND fecha_operacion >= %s AND fecha_operacion <= %s
                    UNION
                    SELECT articulo_id FROM reprocesos
                    WHERE anulado_el IS NULL
                      AND fecha_operacion >= %s AND fecha_operacion <= %s
                )
                ORDER BY a.nombre
                """,
                (cliente_id, fecha_desde, fecha_hasta, fecha_desde, fecha_hasta, fecha_desde, fecha_hasta),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()


def salidas_stock_articulos(articulo_ids: list[int]) -> dict:
    """CADA salida individual de VARIOS artículos, tipada y en orden cronológico — TODA la historia.

    Devuelve {articulo_id: [salidas]}, con una lista por cada id pedido
    (vacía si no tuvo ninguna). Misma consulta de siempre con "= ANY(%s)":
    antes se corría una vez por artículo, con su conexión cada vez.

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
    ids = list(articulo_ids)
    if not ids:
        return {}
    por_articulo = {articulo_id: [] for articulo_id in ids}
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
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
                           r.articulo_id AS articulo_id
                    FROM pedidos_renglones r
                    JOIN vigentes v ON v.id = r.pedido_id
                    WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id = ANY(%s)
                    UNION ALL
                    SELECT m.fecha_operacion, m.creado_en, m.tipo, m.fecha_operacion,
                           -m.cantidad, NULL, NULL, m.motivo, NULL,
                           m.lote_tipo, m.lote_origen_id, NULL, m.articulo_id
                    FROM movimientos_stock m
                    WHERE m.anulado_el IS NULL AND m.cantidad < 0 AND m.articulo_id = ANY(%s)
                    UNION ALL
                    SELECT rp.fecha_operacion, rp.creado_en, 'reproceso_toma', rp.fecha_operacion,
                           rp.bultos_tomados, NULL, NULL, NULL, rp.bultos_segunda,
                           NULL, NULL, NULL, rp.articulo_id
                    FROM reprocesos rp
                    WHERE rp.anulado_el IS NULL AND rp.articulo_id = ANY(%s)
                ) salidas
                ORDER BY articulo_id, fecha_orden, momento_orden
                """,
                (ids, ids, ids),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            for fila in cursor.fetchall():
                salida = dict(zip(columnas, fila))
                por_articulo[salida.pop("articulo_id")].append(salida)
        return por_articulo
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
