"""Conexión a la base de datos (Supabase / PostgreSQL).

Aísla la conexión en su propio módulo para que sea fácil de reemplazar o
testear (con mocks), igual que se hizo con la llamada a la API de Claude en
core/lector_comandas.py.
"""

import os

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
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (nombre_parametro) nombre_parametro, tipo, valor
                FROM clientes_parametros_historial
                WHERE cliente_id = %s AND vigente_desde <= %s
                ORDER BY nombre_parametro, vigente_desde DESC
                """,
                (cliente_id, fecha_referencia),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        conexion.close()

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


def listar_fichas_por_cliente(cliente_id: int) -> list[dict]:
    """Devuelve las fichas de logística de un cliente, ordenadas por nombre de artículo."""
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
                ORDER BY a.nombre
                """,
                (cliente_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_ficha(ficha_id: int) -> dict | None:
    """Devuelve una ficha por id (con nombre del artículo, para mostrarlo fijo al editar), o None."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT fl.id, fl.cliente_id, fl.articulo_id, a.nombre AS articulo_nombre,
                       fl.envase_id, fl.contenido_caja, fl.unidad_venta, fl.envase_variable,
                       fl.nombre_cliente, fl.codigo_cliente
                FROM fichas_logistica fl
                JOIN articulos a ON a.id = fl.articulo_id
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


def listar_articulos_sin_ficha(cliente_id: int) -> list[dict]:
    """Artículos activos que todavía no tienen ficha de logística para este cliente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.nombre
                FROM articulos a
                WHERE a.activo = true
                  AND NOT EXISTS (
                      SELECT 1 FROM fichas_logistica fl
                      WHERE fl.articulo_id = a.id AND fl.cliente_id = %s
                  )
                ORDER BY a.nombre
                """,
                (cliente_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
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
        conexion.commit()
    finally:
        conexion.close()


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
                """,
                (envase_id, contenido_caja, unidad_venta, envase_variable, nombre_cliente, codigo_cliente, ficha_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def eliminar_ficha(ficha_id: int) -> None:
    """Borra una ficha de logística (borrado real: nada más referencia su id)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM fichas_logistica WHERE id = %s", (ficha_id,))
        conexion.commit()
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


def buscar_compras(fecha_desde, fecha_hasta, proveedor_id: int | None = None, articulo_id: int | None = None) -> list[dict]:
    """Busca compras por rango de fechas (obligatorio) y, opcionalmente, por proveedor y/o artículo.

    Base de la pantalla Buscar Compras y del export a PDF/Excel — WHERE
    dinámico según qué filtros opcionales vinieron.

    Cantidad/contenido/kilos/fracción vienen con el valor REAL (pesado por
    Depósito al recepcionar) si ya existe, si no el estimado que cargó el
    comprador — ver recepcionar_compra. Quien llama sigue leyendo
    "cantidad_cajones" etc. como si fuera la única columna, sin saber nada
    de esta sustitución.
    """
    condiciones = ["c.fecha_operacion BETWEEN %s AND %s"]
    parametros: list = [fecha_desde, fecha_hasta]
    if proveedor_id is not None:
        condiciones.append("c.proveedor_id = %s")
        parametros.append(proveedor_id)
    if articulo_id is not None:
        condiciones.append("c.articulo_id = %s")
        parametros.append(articulo_id)

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
                       c.importe, c.sena, c.tipo_retiro, c.foto_ruta
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE {" AND ".join(condiciones)}
                ORDER BY c.fecha_operacion DESC, p.codigo_puesto, c.cargado_el
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


def listar_precios_vigentes_por_cliente(cliente_id: int, fecha_referencia) -> list[dict]:
    """Precio vigente de cada artículo para un cliente, a una fecha dada.

    "Vigente" es la fila de precios_venta_historial con vigente_desde más
    reciente que ya llegó a fecha_referencia (mismo patrón que el
    descuento/utilidad vigente de clientes_parametros_historial). Un
    artículo sin ninguna fila con vigente_desde <= fecha_referencia
    simplemente no aparece en el resultado — no tiene precio vigente todavía.

    Trae también vigente_desde (aparte de articulo_id y precio) — lo usa
    la exportación a PDF/Excel para saber si un precio es "nuevo" (cambió
    justo en la fecha consultada). Los demás llamadores lo ignoran, leen
    por clave de diccionario.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (articulo_id) articulo_id, precio, vigente_desde
                FROM precios_venta_historial
                WHERE cliente_id = %s AND vigente_desde <= %s
                ORDER BY articulo_id, vigente_desde DESC
                """,
                (cliente_id, fecha_referencia),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_precios_anteriores_por_cliente(cliente_id: int, fecha_referencia) -> list[dict]:
    """El precio que tenía cada artículo ANTES del que hoy está vigente (para la columna "Precio anterior"
    de la Lista de Precios en Excel — ver core.exportar_precios).

    Mismo criterio de "vigente" que listar_precios_vigentes_por_cliente,
    pero un escalón atrás: de las filas de precios_venta_historial con
    vigente_desde <= fecha_referencia, la vigente es la de vigente_desde
    más reciente (fila #1) — esto devuelve la fila #2, la que regía justo
    antes de esa. Un artículo con una sola fila cargada (nunca cambió de
    precio) o sin ninguna simplemente no aparece — no hay "anterior" que
    mostrar.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT articulo_id, precio FROM (
                    SELECT articulo_id, precio,
                           ROW_NUMBER() OVER (PARTITION BY articulo_id ORDER BY vigente_desde DESC) AS orden
                    FROM precios_venta_historial
                    WHERE cliente_id = %s AND vigente_desde <= %s
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

    cambios: [{"articulo_id", "precio"}, ...] — ya calculado por
    core.precios_venta.calcular_cambios_de_precios a partir de lo que
    cambió en el formulario. Cada uno se inserta con vigente_desde = hoy;
    el precio viejo NUNCA se pisa. Si ya existe una fila de HOY para ese
    mismo (articulo_id, cliente_id) -- segunda edición el mismo día -- se
    actualiza esa en vez de duplicarla.

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
                    INSERT INTO precios_venta_historial (articulo_id, cliente_id, precio, vigente_desde, foto_ruta)
                    VALUES (%s, %s, %s, CURRENT_DATE, %s)
                    ON CONFLICT (articulo_id, cliente_id, vigente_desde)
                    DO UPDATE SET
                        precio = EXCLUDED.precio,
                        foto_ruta = COALESCE(EXCLUDED.foto_ruta, precios_venta_historial.foto_ruta)
                    """,
                    (cambio["articulo_id"], cliente_id, cambio["precio"], foto_ruta),
                )
        conexion.commit()
    finally:
        conexion.close()


def listar_costos_envases_vigentes(fecha_referencia) -> list[dict]:
    """Costo vigente de cada envase, a una fecha dada (mismo patrón "vigente" que el resto).

    Los envases son un catálogo compartido (no pertenecen a ningún
    cliente): envase_id alcanza para identificar cada uno.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (envase_id) envase_id, costo
                FROM envases_costo_historial
                WHERE vigente_desde <= %s
                ORDER BY envase_id, vigente_desde DESC
                """,
                (fecha_referencia,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


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
                       c.cantidad_cajones, c.contenido_por_cajon,
                       c.cantidad_kilos, c.cantidad_fraccion, c.importe, c.sena, c.tipo_retiro, c.foto_ruta,
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
                       c.cantidad_cajones, c.contenido_por_cajon, c.importe, c.sena, c.tipo_retiro, c.foto_ruta,
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

    cursor.execute("SELECT COUNT(*) FROM compras WHERE guia_id = %s", (guia_id,))
    (cantidad_existente,) = cursor.fetchone()
    guia_punto = cantidad_existente + 1

    if ingreso_directo_deposito:
        cursor.execute(
            """
            INSERT INTO compras
                (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro, foto_ruta,
                 guia_id, guia_punto, estado, estado_retiro,
                 cantidad_cajones_real, contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real,
                 procesada_el, retiro_procesado_el, retiro_origen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
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
                foto_ruta,
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
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro, foto_ruta,
                 guia_id, guia_punto, carga_token, estado, estado_retiro, retiro_procesado_el, retiro_origen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', 'retirado', now(), %s)
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
                foto_ruta,
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
                 cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro, foto_ruta,
                 guia_id, guia_punto, carga_token, estado, estado_retiro)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', 'pendiente')
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
                foto_ruta,
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
    (recepcionada, rechazada por calidad o nunca ingresada — ver
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
                    raise ValueError("Esta compra fue rechazada por calidad, no se puede editar la cantidad.")
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
                    raise ValueError("Esta compra fue rechazada por calidad, no se puede editar el precio.")
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
                SELECT c.id, c.guia_id, c.guia_punto, a.nombre AS articulo_nombre, a.unidad_compra,
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
                  AND c.procesada_el::date = %s
                ORDER BY c.procesada_el DESC
                """,
                (fecha,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def buscar_retiros(
    fecha_desde,
    fecha_hasta,
    proveedor_id: int | None = None,
    articulo_id: int | None = None,
    tipo_retiro: str | None = None,
    estado_retiro: str | None = None,
) -> list[dict]:
    """El histórico de Logística (ver /logistica/consultar): retiros entre dos fechas, con filtros opcionales.

    estado_retiro: 'pendiente' incluye también las filas con estado NULL
    (compras de antes de que existiera Retiro) — mismo criterio que
    listar_compras_pendientes_retiro: lo raro se muestra, no desaparece.
    'retirado'/'cancelado' filtran exacto. None trae todo.

    Cada fila trae cantidad_cajones (lo que cargó el comprador) y
    cantidad_cajones_retirada (lo anotado al retirar, si se anotó): el
    total de bultos para liquidar al carrero/cooperativa lo arma quien
    llama con COALESCE de esos dos — acá se devuelven separados para poder
    mostrar de dónde sale cada número.
    """
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

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.id, c.fecha_operacion, c.retiro_procesado_el, c.tipo_retiro, c.estado_retiro,
                       c.cantidad_cajones, c.cantidad_cajones_retirada,
                       p.nombre AS proveedor_nombre, p.codigo_puesto AS proveedor_codigo_puesto,
                       a.nombre AS articulo_nombre
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE {" AND ".join(condiciones)}
                ORDER BY c.fecha_operacion DESC, p.nombre, a.nombre
                """,
                parametros,
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
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
                SELECT c.id, c.guia_id, c.guia_punto, a.nombre AS articulo_nombre, a.unidad_compra,
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
                  AND c.retiro_procesado_el::date = %s
                ORDER BY c.retiro_procesado_el DESC
                """,
                (tipo_retiro, fecha),
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


def contar_compras_sin_precio() -> int:
    """Cuántas compras sin precio de compra cargado hay pendientes de completar (mismo filtro que
    listar_compras_sin_precio, sin traer las filas) — para el cartel de aviso de /comercial, que se
    calcula en cada entrada a esa pantalla y solo necesita el número.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM compras c
                WHERE c.importe IS NULL
                  AND c.estado IN ('pendiente', 'recepcionado')
                  AND c.estado_retiro IN ('pendiente', 'retirado')
                """
            )
            (cantidad,) = cursor.fetchone()
        return cantidad
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


def eliminar_compra(compra_id: int) -> str | None:
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

    Una misma foto de comanda (foto_ruta) puede estar compartida por varios
    renglones/compras. Devuelve el foto_ruta que hay que borrar del Storage
    SOLO si esta era la última compra que lo usaba (si no tenía foto, o si
    otro renglón lo sigue usando, devuelve None) — la decisión queda
    resuelta acá, dentro de la misma transacción, para no tener una
    condición de carrera entre el DELETE y el conteo posterior.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT foto_ruta, estado, estado_retiro FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            foto_ruta, estado, estado_retiro = fila if fila else (None, None, None)

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

            foto_ruta_a_borrar = None
            if foto_ruta:
                cursor.execute("SELECT COUNT(*) FROM compras WHERE foto_ruta = %s", (foto_ruta,))
                (restantes,) = cursor.fetchone()
                if restantes == 0:
                    foto_ruta_a_borrar = foto_ruta
        conexion.commit()
        return foto_ruta_a_borrar
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
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT foto_ruta FROM compras c1
                WHERE c1.foto_ruta IS NOT NULL AND c1.fecha_operacion < %s
                  AND NOT EXISTS (
                    SELECT 1 FROM compras c2
                    WHERE c2.foto_ruta = c1.foto_ruta AND c2.fecha_operacion >= %s
                  )
                """,
                (fecha_corte, fecha_corte),
            )
            filas = cursor.fetchall()
        return [fila[0] for fila in filas]
    finally:
        conexion.close()


def limpiar_foto_ruta_de_compras(foto_ruta: str) -> None:
    """Pone foto_ruta en NULL en todas las compras que lo tenían. Conserva las filas — se usa después de borrar el archivo del bucket."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("UPDATE compras SET foto_ruta = NULL WHERE foto_ruta = %s", (foto_ruta,))
        conexion.commit()
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
    """Tipos de cajón activos con su proveedor, para las pantallas de Vacíos y el ABM de tipos.

    El orden dentro de cada proveedor es por id (orden de carga): el
    PRIMERO cargado es el que viene preseleccionado en Recibir.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, t.proveedor_id, t.nombre,
                       p.nombre AS proveedor_nombre, p.codigo_puesto
                FROM tipos_envase_puesto t
                JOIN proveedores p ON p.id = t.proveedor_id
                WHERE t.activo
                ORDER BY p.nombre, t.id
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def crear_tipo_envase_puesto(proveedor_id: int, nombre: str) -> None:
    """Alta de un tipo de cajón para un proveedor. Si existía dado de baja, lo reactiva (mismo nombre)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tipos_envase_puesto (proveedor_id, nombre)
                VALUES (%s, %s)
                ON CONFLICT (proveedor_id, nombre) DO UPDATE SET activo = true
                """,
                (proveedor_id, nombre),
            )
        conexion.commit()
    finally:
        conexion.close()


def desactivar_tipo_envase_puesto(tipo_id: int) -> None:
    """Baja lógica de un tipo de cajón: deja de ofrecerse en las pantallas, los movimientos viejos quedan."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
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


def _stock_vacios_actual(cursor, proveedor_id: int, tipo_envase_id: int) -> int:
    """Stock del sistema para un proveedor+tipo: recibidos − devueltos, sin los movimientos anulados."""
    cursor.execute(
        """
        SELECT COALESCE((SELECT SUM(cantidad) FROM vacios_recibidos
                         WHERE proveedor_id = %s AND tipo_envase_id = %s AND anulado_el IS NULL), 0)
             - COALESCE((SELECT SUM(cantidad) FROM vacios_devueltos
                         WHERE proveedor_id = %s AND tipo_envase_id = %s AND anulado_el IS NULL), 0)
        """,
        (proveedor_id, tipo_envase_id, proveedor_id, tipo_envase_id),
    )
    (stock,) = cursor.fetchone()
    return int(stock)


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


def listar_vacios_recibidos_de_fecha(fecha) -> list[dict]:
    """Entradas de un día (anuladas incluidas, marcadas), para la lista "Recibido hoy" de la pantalla Recibir."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.cantidad, v.creado_en, v.anulado_el,
                       c.nombre AS cliente_nombre,
                       p.nombre AS proveedor_nombre, p.codigo_puesto,
                       t.nombre AS tipo_nombre
                FROM vacios_recibidos v
                JOIN clientes_puesto c ON c.id = v.cliente_puesto_id
                JOIN proveedores p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id
                WHERE v.creado_en::date = %s
                ORDER BY v.creado_en DESC
                """,
                (fecha,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_vacios_devueltos_de_fecha(fecha) -> list[dict]:
    """Salidas de un día (anuladas incluidas, marcadas), para la lista "Devuelto hoy" de la pantalla Devolver."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.cantidad, v.stock_sistema, v.creado_en, v.anulado_el,
                       p.nombre AS proveedor_nombre, p.codigo_puesto,
                       t.nombre AS tipo_nombre
                FROM vacios_devueltos v
                JOIN proveedores p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id
                WHERE v.creado_en::date = %s
                ORDER BY v.creado_en DESC
                """,
                (fecha,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


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


def stock_vacios() -> list[dict]:
    """Stock del sistema por proveedor y tipo: recibidos − devueltos (sin anulados), calculado siempre.

    Incluye tipos dados de baja que todavía tengan movimientos (su stock
    histórico no puede desaparecer de la pantalla por una baja del ABM).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id AS proveedor_id, p.nombre AS proveedor_nombre, p.codigo_puesto,
                       t.id AS tipo_envase_id, t.nombre AS tipo_nombre,
                       COALESCE(r.total, 0) AS recibidos,
                       COALESCE(d.total, 0) AS devueltos
                FROM tipos_envase_puesto t
                JOIN proveedores p ON p.id = t.proveedor_id
                LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM vacios_recibidos
                           WHERE anulado_el IS NULL GROUP BY tipo_envase_id) r ON r.tipo_envase_id = t.id
                LEFT JOIN (SELECT tipo_envase_id, SUM(cantidad) AS total FROM vacios_devueltos
                           WHERE anulado_el IS NULL GROUP BY tipo_envase_id) d ON d.tipo_envase_id = t.id
                WHERE t.activo OR COALESCE(r.total, 0) <> 0 OR COALESCE(d.total, 0) <> 0
                ORDER BY p.nombre, t.id
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        resultado = [dict(zip(columnas, fila)) for fila in filas]
        for fila in resultado:
            fila["stock"] = int(fila["recibidos"]) - int(fila["devueltos"])
        return resultado
    finally:
        conexion.close()
