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
    """Borra una ficha de logística (borrado real: nada más referencia su id). El estado final queda en la bitácora."""
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

    Conceptualmente no se "edita" el artículo (el unique articulo+cliente lo
    dice): se cierra la ficha vieja y se abre una nueva con el mismo envase,
    contenido y unidad. El alias (nombre_cliente/codigo_cliente) viene de la
    pantalla: precargado con el de la ficha vieja pero editable, porque si
    el artículo destino es OTRO producto (no otra presentación del mismo),
    el alias viejo quedaría mal. En la bitácora quedan los dos eventos, así
    se ve a qué artículo (y con qué alias) apuntaba antes.

    Devuelve el id de la ficha nueva, o None si la ficha no existe. Si el
    artículo nuevo ya tiene ficha para ese cliente, el unique de la tabla
    corta todo (no se pierde nada: el DELETE se deshace con el rollback).
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
    # guía (el ON CONFLICT absorbe los N renglones de la misma comanda) y
    # compras.foto_ruta queda muerta (se escribe NULL; DROP pendiente,
    # ver db/APLICADO.md).
    if foto_ruta:
        cursor.execute(
            "INSERT INTO fotos_guia (guia_id, foto_ruta) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (guia_id, foto_ruta),
        )
        foto_ruta = None

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
                       c.cantidad_cajones_rechazada, c.motivo_rechazo, c.importe,
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


def contar_compras_sin_precio_viejas(fecha_limite) -> dict:
    """Auditoría: compras que siguen sin precio con fecha_operacion de fecha_limite para atrás, y la más vieja.

    Plata que no se sabe cuánto costó. Usa el índice parcial
    compras_sin_precio_idx (solo filas sin precio, con la fecha adentro).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*), MIN(fecha_operacion) FROM compras c "
                "WHERE c.importe IS NULL AND c.fecha_operacion <= %s",
                (fecha_limite,),
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
    """Borra los registros de un archivo ya eliminado del bucket: sus filas de fotos_guia, y la columna muerta.

    Se usa después de borrar el archivo del Storage (limpieza de fotos
    viejas). El UPDATE de compras.foto_ruta es solo higiene de la columna
    muerta mientras espera su DROP (ver db/APLICADO.md).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM fotos_guia WHERE foto_ruta = %s", (foto_ruta,))
            cursor.execute("UPDATE compras SET foto_ruta = NULL WHERE foto_ruta = %s", (foto_ruta,))
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
                       p.nombre AS proveedor_nombre
                FROM tipos_envase_puesto t
                JOIN proveedores_puesto p ON p.id = t.proveedor_id
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

    Incluye tipos dados de baja que todavía tengan movimientos (su stock
    histórico no puede desaparecer de la pantalla por una baja del ABM).
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
                WHERE t.activo OR COALESCE(r.total, 0) <> 0 OR COALESCE(d.total, 0) <> 0
                   OR COALESCE(aj.total, 0) <> 0
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
    """El ÚLTIMO conteo por proveedor+tipo, con su foto del stock del sistema, para el Cotejo (cajera)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (c.proveedor_id, c.tipo_envase_id)
                       c.id, c.proveedor_id, c.tipo_envase_id,
                       c.cantidad, c.stock_sistema, c.creado_en,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre
                FROM conteos_vacios c
                JOIN proveedores_puesto p ON p.id = c.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = c.tipo_envase_id
                ORDER BY c.proveedor_id, c.tipo_envase_id, c.creado_en DESC
                """
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        resultado = [dict(zip(columnas, fila)) for fila in filas]
        resultado.sort(key=lambda fila: (fila["proveedor_nombre"], fila["tipo_nombre"]))
        return resultado
    finally:
        conexion.close()


def listar_senas_pendientes() -> list[dict]:
    """Entradas vigentes con la seña sin resolver, para la pantalla Pendientes de Pago (cajera). Más viejas primero.

    Pendiente = los TRES cierres en NULL (ni pagada, ni vale, ni anulada)
    y el movimiento vigente (no anulado).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.cantidad, v.creado_en,
                       c.nombre AS cliente_nombre,
                       p.nombre AS proveedor_nombre,
                       t.nombre AS tipo_nombre
                FROM vacios_recibidos v
                JOIN clientes_puesto c ON c.id = v.cliente_puesto_id
                JOIN proveedores_puesto p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id
                WHERE v.sena_pagada_el IS NULL AND v.sena_vale_el IS NULL AND v.sena_anulada_el IS NULL
                  AND v.anulado_el IS NULL
                ORDER BY v.creado_en
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
                       t.nombre AS tipo_nombre
                FROM vacios_recibidos v
                JOIN clientes_puesto c ON c.id = v.cliente_puesto_id
                JOIN proveedores_puesto p ON p.id = v.proveedor_id
                JOIN tipos_envase_puesto t ON t.id = v.tipo_envase_id
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


def desactivar_proveedor_puesto(proveedor_id: int) -> None:
    """Baja lógica de un proveedor del puesto: sale de los selects; sus movimientos y stock histórico quedan."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
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
    "texto_codigo", "texto_descripcion", "cantidad"}].

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
                        (pedido_id, sucursal, articulo_id, texto_codigo, texto_descripcion, cantidad)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        pedido_id,
                        renglon.get("sucursal"),
                        renglon.get("articulo_id"),
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
                       p.reemplaza_a_pedido_id, p.creado_en,
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
    """Los renglones de un pedido, con el nombre del artículo si está identificado (NULL si no).

    Ordenados para la pantalla del depósito: los SIN identificar primero
    (hay que resolverlos), después por sucursal y nombre.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.sucursal, r.articulo_id, a.nombre AS articulo_nombre,
                       r.texto_codigo, r.texto_descripcion, r.cantidad, r.armado_el, r.cantidad_armada
                FROM pedidos_renglones r
                LEFT JOIN articulos a ON a.id = r.articulo_id
                WHERE r.pedido_id = %s
                ORDER BY (r.articulo_id IS NULL) DESC, r.sucursal, COALESCE(a.nombre, r.texto_descripcion, r.texto_codigo)
                """,
                (pedido_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def asignar_articulo_a_renglon_pedido(renglon_id: int, articulo_id: int) -> None:
    """Asigna a mano el artículo de un renglón "sin identificar" (o corrige uno mal asignado)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE pedidos_renglones SET articulo_id = %s WHERE id = %s",
                (articulo_id, renglon_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def guardar_alias_en_ficha(cliente_id: int, articulo_id: int, texto_codigo: str | None, texto_descripcion: str | None) -> None:
    """Guarda el código/nombre con el que el cliente pidió, en su ficha, para que la próxima matchee solo.

    SOLO completa los campos vacíos de la ficha — nunca pisa un alias ya
    cargado (si el que está difiere del que llegó, se corrige a mano desde
    Editar Ficha, no desde acá). Deja la foto en la bitácora, como
    cualquier edición de ficha. Sin ficha del artículo para ese cliente,
    no hace nada (el alias vive en la ficha; primero hay que crearla).
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
                WHERE cliente_id = %s AND articulo_id = %s
                  AND (codigo_cliente IS DISTINCT FROM COALESCE(codigo_cliente, %s)
                       OR nombre_cliente IS DISTINCT FROM COALESCE(nombre_cliente, %s))
                RETURNING id, envase_id, contenido_caja, unidad_venta, envase_variable,
                          nombre_cliente, codigo_cliente
                """,
                (texto_codigo, texto_descripcion, cliente_id, articulo_id, texto_codigo, texto_descripcion),
            )
            fila = cursor.fetchone()
            if fila is not None:
                ficha_id, envase_id, contenido_caja, unidad_venta, envase_variable, nombre_cliente, codigo_cliente = fila
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


def marcar_renglon_armado(renglon_id: int, cantidad_armada=None) -> None:
    """Tilda un renglón como armado. El tilde significa "terminé con este renglón", no "está completo".

    cantidad_armada solo si armó MENOS de lo pedido (Día pide 15 y hay
    12): la cantidad real queda grabada y el renglón figura "incompleto".
    Armado completo va con None — no se guarda un número redundante.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE pedidos_renglones SET armado_el = now(), cantidad_armada = %s WHERE id = %s",
                (cantidad_armada, renglon_id),
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
                "UPDATE pedidos_renglones SET armado_el = NULL, cantidad_armada = NULL WHERE id = %s",
                (renglon_id,),
            )
        conexion.commit()
    finally:
        conexion.close()


def contar_pedidos_con_renglones_incompletos() -> dict:
    """Auditoría: pedidos vivos con renglones armados por MENOS de lo pedido, y el más viejo.

    "Armé 12 de 15": el dueño se entera por acá, no cuando reclame Día.
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
                              WHERE r.pedido_id = p.id AND r.armado_el IS NOT NULL
                                AND r.cantidad_armada IS NOT NULL AND r.cantidad_armada <> r.cantidad)
                """
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
                       ca.ultima_revision_el, ca.ultimo_error, ca.ultimo_error_el,
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
                       ca.ultima_revision_el, ca.ultimo_error, ca.ultimo_error_el,
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


def registrar_revision_casilla(casilla_id: int, error: str | None = None) -> None:
    """Deja rastro de cada revisión: la exitosa por un lado, el último error por el otro.

    Si el último error es más nuevo que la última revisión exitosa, la
    casilla está fallando — eso es lo que la pantalla (y la futura alerta
    de Auditoría) mira. Nunca se pisa una cosa con la otra.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            if error is None:
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
                       p.id, p.fecha_operacion, p.origen, p.creado_en,
                       (SELECT COUNT(*) FROM pedidos_renglones r
                        WHERE r.pedido_id = p.id AND r.articulo_id IS NOT NULL) AS renglones_totales,
                       (SELECT COUNT(*) FROM pedidos_renglones r
                        WHERE r.pedido_id = p.id AND r.articulo_id IS NOT NULL
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
                SELECT v.fecha_operacion, r.articulo_id,
                       a.nombre AS articulo_nombre, a.grupo AS articulo_grupo,
                       SUM(r.cantidad) AS bultos
                FROM vigentes v
                JOIN pedidos_renglones r ON r.pedido_id = v.id
                LEFT JOIN articulos a ON a.id = r.articulo_id
                GROUP BY v.fecha_operacion, r.articulo_id, a.nombre, a.grupo
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
