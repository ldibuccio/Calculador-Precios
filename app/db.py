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


def crear_articulo(nombre: str, merma_porcentaje: float) -> None:
    """Inserta un artículo nuevo en la tabla articulos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO articulos (nombre, merma_porcentaje) VALUES (%s, %s)",
                (nombre, merma_porcentaje),
            )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_articulo(articulo_id: int, nombre: str, merma_porcentaje: float) -> None:
    """Actualiza nombre y merma de un artículo existente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE articulos SET nombre = %s, merma_porcentaje = %s, actualizado_en = now() WHERE id = %s",
                (nombre, merma_porcentaje, articulo_id),
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
