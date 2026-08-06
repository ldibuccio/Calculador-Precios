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
    """Devuelve los artículos activos (id, nombre, merma), ordenados por nombre.

    codigo_interno no se lee acá: es un dato del cliente Día (para su email
    de pedido), no del artículo en sí, y se va a manejar en una tabla de
    conversión por cliente aparte.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre, merma_porcentaje FROM articulos WHERE activo = true ORDER BY nombre"
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
            cursor.execute("SELECT id, nombre, merma_porcentaje FROM articulos WHERE id = %s", (articulo_id,))
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def crear_articulo(nombre: str) -> None:
    """Inserta un artículo nuevo en la tabla articulos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("INSERT INTO articulos (nombre) VALUES (%s)", (nombre,))
        conexion.commit()
    finally:
        conexion.close()


def actualizar_articulo(articulo_id: int, nombre: str) -> None:
    """Actualiza el nombre de un artículo existente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE articulos SET nombre = %s, actualizado_en = now() WHERE id = %s",
                (nombre, articulo_id),
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


_CLIENTE_CON_DESCUENTO_Y_UTILIDAD_VIGENTES_SQL = """
    SELECT c.id, c.nombre, d.valor * 100 AS descuento, u.valor * 100 AS utilidad_objetivo
    FROM clientes c
    LEFT JOIN LATERAL (
        SELECT valor FROM clientes_parametros_historial
        WHERE cliente_id = c.id AND nombre_parametro = 'descuento' AND vigente_desde <= CURRENT_DATE
        ORDER BY vigente_desde DESC LIMIT 1
    ) d ON true
    LEFT JOIN LATERAL (
        SELECT valor FROM clientes_parametros_historial
        WHERE cliente_id = c.id AND nombre_parametro = 'utilidad_objetivo' AND vigente_desde <= CURRENT_DATE
        ORDER BY vigente_desde DESC LIMIT 1
    ) u ON true
"""


def listar_clientes() -> list[dict]:
    """Devuelve los clientes activos (id, nombre, descuento %, utilidad_objetivo %) ordenados por nombre.

    El descuento/utilidad vigente es el registro de clientes_parametros_historial
    con la fecha de vigencia más reciente que ya llegó (no futura).
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_CLIENTE_CON_DESCUENTO_Y_UTILIDAD_VIGENTES_SQL + " WHERE c.activo = true ORDER BY c.nombre")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_cliente(cliente_id: int) -> dict | None:
    """Devuelve un cliente por id con su descuento/utilidad vigentes, o None si no existe."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_CLIENTE_CON_DESCUENTO_Y_UTILIDAD_VIGENTES_SQL + " WHERE c.id = %s", (cliente_id,))
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def crear_cliente(nombre: str, descuento: float, utilidad_objetivo: float) -> None:
    """Crea un cliente y su primer registro de historial (vigente_desde = hoy).

    descuento y utilidad_objetivo llegan como porcentaje (23 = 23%) y se
    guardan como fracción (0.23) en clientes_parametros_historial.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("INSERT INTO clientes (nombre) VALUES (%s) RETURNING id", (nombre,))
            (cliente_id,) = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO clientes_parametros_historial (cliente_id, nombre_parametro, valor, vigente_desde)
                VALUES (%s, 'descuento', %s, CURRENT_DATE), (%s, 'utilidad_objetivo', %s, CURRENT_DATE)
                """,
                (cliente_id, descuento / 100, cliente_id, utilidad_objetivo / 100),
            )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_cliente(cliente_id: int, nombre: str, descuento: float, utilidad_objetivo: float) -> None:
    """Actualiza el nombre del cliente.

    El descuento/utilidad NO se pisan: se agrega un registro nuevo en
    clientes_parametros_historial con vigente_desde = hoy, para que los
    cálculos de fechas pasadas sigan usando el valor que regía en ese
    momento. Si ya existe un registro de hoy para ese parámetro (segunda
    edición el mismo día), se actualiza ese en vez de duplicarlo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE clientes SET nombre = %s, actualizado_en = now() WHERE id = %s", (nombre, cliente_id)
            )
            cursor.execute(
                """
                INSERT INTO clientes_parametros_historial (cliente_id, nombre_parametro, valor, vigente_desde)
                VALUES (%s, 'descuento', %s, CURRENT_DATE), (%s, 'utilidad_objetivo', %s, CURRENT_DATE)
                ON CONFLICT (cliente_id, nombre_parametro, vigente_desde)
                DO UPDATE SET valor = EXCLUDED.valor
                """,
                (cliente_id, descuento / 100, cliente_id, utilidad_objetivo / 100),
            )
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
