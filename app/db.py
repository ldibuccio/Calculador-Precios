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
                SELECT id, nombre, merma_porcentaje, unidad_compra, contenido_referencia
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
                SELECT id, nombre, merma_porcentaje, unidad_compra, contenido_referencia
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


def crear_articulo(nombre: str, unidad_compra: str, contenido_referencia: float | None) -> None:
    """Inserta un artículo nuevo en la tabla articulos."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO articulos (nombre, unidad_compra, contenido_referencia) VALUES (%s, %s, %s)",
                (nombre, unidad_compra, contenido_referencia),
            )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_articulo(articulo_id: int, nombre: str, unidad_compra: str, contenido_referencia: float | None) -> None:
    """Actualiza nombre, unidad de compra y contenido de referencia de un artículo existente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE articulos
                SET nombre = %s, unidad_compra = %s, contenido_referencia = %s, actualizado_en = now()
                WHERE id = %s
                """,
                (nombre, unidad_compra, contenido_referencia, articulo_id),
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


def listar_fichas_por_cliente(cliente_id: int) -> list[dict]:
    """Devuelve las fichas de logística de un cliente, ordenadas por nombre de artículo."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT fl.id, fl.articulo_id, a.nombre AS articulo_nombre, fl.envase_id, e.nombre AS envase_nombre,
                       fl.contenido_caja, fl.unidad_venta, fl.envase_variable
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
                       fl.envase_id, fl.contenido_caja, fl.unidad_venta, fl.envase_variable
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


def listar_envases_por_cliente(cliente_id: int) -> list[dict]:
    """Envases activos de un cliente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre FROM envases WHERE cliente_id = %s AND activo = true ORDER BY nombre",
                (cliente_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def crear_ficha(
    articulo_id: int,
    cliente_id: int,
    envase_id: int | None,
    contenido_caja: float,
    unidad_venta: str,
    envase_variable: bool,
) -> None:
    """Crea la ficha de logística de un artículo para un cliente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO fichas_logistica
                    (articulo_id, cliente_id, envase_id, contenido_caja, unidad_venta, envase_variable)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (articulo_id, cliente_id, envase_id, contenido_caja, unidad_venta, envase_variable),
            )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_ficha(
    ficha_id: int, envase_id: int | None, contenido_caja: float, unidad_venta: str, envase_variable: bool
) -> None:
    """Actualiza envase, contenido solicitado, unidad de venta y envase_variable de una ficha existente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE fichas_logistica
                SET envase_id = %s, contenido_caja = %s, unidad_venta = %s, envase_variable = %s,
                    actualizado_en = now()
                WHERE id = %s
                """,
                (envase_id, contenido_caja, unidad_venta, envase_variable, ficha_id),
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


def listar_conversiones_por_cliente(cliente_id: int) -> list[dict]:
    """Conversiones de un cliente (cómo llama a cada artículo), ordenadas por nombre de artículo."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, a.nombre AS articulo_nombre, c.nombre_cliente, c.codigo_cliente
                FROM conversion_articulos_cliente c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.cliente_id = %s
                ORDER BY a.nombre
                """,
                (cliente_id,),
            )
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def listar_todas_las_conversiones() -> list[dict]:
    """Todas las conversiones nombre_cliente -> articulo_id, de cualquier cliente.

    Se usa para adivinar artículos en comandas leídas por foto: los alias que
    ya se cargaron para pedidos de clientes (ej. "MANZANA PG" -> Man Gob)
    también sirven para reconocer abreviaturas de proveedores en el mercado,
    no son exclusivos de un cliente puntual.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT articulo_id, nombre_cliente FROM conversion_articulos_cliente")
            columnas = [descripcion[0] for descripcion in cursor.description]
            filas = cursor.fetchall()
        return [dict(zip(columnas, fila)) for fila in filas]
    finally:
        conexion.close()


def obtener_conversion(conversion_id: int) -> dict | None:
    """Devuelve una conversión por id (para precargar el formulario de edición), o None si no existe."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.cliente_id, c.articulo_id, a.nombre AS articulo_nombre,
                       c.nombre_cliente, c.codigo_cliente
                FROM conversion_articulos_cliente c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.id = %s
                """,
                (conversion_id,),
            )
            fila = cursor.fetchone()
            if fila is None:
                return None
            columnas = [descripcion[0] for descripcion in cursor.description]
        return dict(zip(columnas, fila))
    finally:
        conexion.close()


def crear_conversion(articulo_id: int, cliente_id: int, nombre_cliente: str, codigo_cliente: str | None) -> None:
    """Crea una conversión (cómo llama el cliente a un artículo)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversion_articulos_cliente (articulo_id, cliente_id, nombre_cliente, codigo_cliente)
                VALUES (%s, %s, %s, %s)
                """,
                (articulo_id, cliente_id, nombre_cliente, codigo_cliente),
            )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_conversion(
    conversion_id: int, articulo_id: int, nombre_cliente: str, codigo_cliente: str | None
) -> None:
    """Actualiza el artículo, nombre y código de una conversión existente."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE conversion_articulos_cliente
                SET articulo_id = %s, nombre_cliente = %s, codigo_cliente = %s, actualizado_en = now()
                WHERE id = %s
                """,
                (articulo_id, nombre_cliente, codigo_cliente, conversion_id),
            )
        conexion.commit()
    finally:
        conexion.close()


def eliminar_conversion(conversion_id: int) -> None:
    """Borra una conversión (borrado real: nada más referencia su id)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM conversion_articulos_cliente WHERE id = %s", (conversion_id,))
        conexion.commit()
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


def listar_compras_por_rango_fechas(fecha_desde, fecha_hasta) -> list[dict]:
    """Devuelve las compras entre dos fechas (inclusive), agrupadas por día y por proveedor (estilo comanda).

    Hoy la pantalla /compras siempre llama a esto con los últimos 2 días fijos
    (hoy y ayer). TODO: a futuro agregar un filtro de fecha/rango a demanda en
    la pantalla, reusando esta misma función con las fechas que elija el
    usuario en vez de un rango fijo.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, a.nombre AS articulo_nombre, a.unidad_compra,
                       p.nombre AS proveedor_nombre,
                       p.codigo_puesto AS proveedor_codigo_puesto,
                       c.cantidad_cajones, c.contenido_por_cajon,
                       c.cantidad_kilos, c.cantidad_fraccion, c.importe, c.sena, c.tipo_retiro, c.foto_ruta
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.fecha_operacion BETWEEN %s AND %s
                ORDER BY c.fecha_operacion DESC, p.codigo_puesto, c.cargado_el
                """,
                (fecha_desde, fecha_hasta),
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
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.articulo_id, a.nombre AS articulo_nombre, c.fecha_operacion,
                       c.cantidad_cajones, c.contenido_por_cajon, c.cantidad_kilos, c.importe
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.fecha_operacion BETWEEN %s AND %s
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
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (articulo_id) articulo_id, precio
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


def listar_costos_envases_vigentes(fecha_referencia) -> list[dict]:
    """Costo vigente de cada envase, a una fecha dada (mismo patrón "vigente" que el resto).

    No filtra por cliente: envases ya está por cliente (envases.cliente_id),
    así que envase_id alcanza para saber a quién pertenece.
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
                       c.cantidad_kilos, c.cantidad_fraccion, c.importe, c.sena, c.tipo_retiro, c.foto_ruta
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
) -> None:
    """Inserta una compra cargada por el comprador.

    foto_ruta es la ruta (en el bucket "comandas" de Supabase Storage) de
    la foto de la comanda de la que salió este renglón — None si la
    compra se cargó a mano, o si la subida de la foto falló (la foto es un
    extra, nunca bloquea guardar la compra). Cuando varios renglones salen
    de la misma foto, comparten la misma foto_ruta.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO compras
                    (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                     cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro, foto_ruta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                ),
            )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_compra(
    compra_id: int,
    articulo_id: int,
    cantidad_cajones: float,
    contenido_por_cajon: float,
    cantidad_kilos: float | None,
    cantidad_fraccion: float | None,
    importe: float | None,
    sena: float | None,
    tipo_retiro: str,
) -> None:
    """Actualiza una compra existente (no cambia su proveedor ni su fecha de operación)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE compras
                SET articulo_id = %s, cantidad_cajones = %s, contenido_por_cajon = %s,
                    cantidad_kilos = %s, cantidad_fraccion = %s,
                    importe = %s, sena = %s, tipo_retiro = %s
                WHERE id = %s
                """,
                (
                    articulo_id,
                    cantidad_cajones,
                    contenido_por_cajon,
                    cantidad_kilos,
                    cantidad_fraccion,
                    importe,
                    sena,
                    tipo_retiro,
                    compra_id,
                ),
            )
        conexion.commit()
    finally:
        conexion.close()


def listar_compras_sin_precio() -> list[dict]:
    """Compras (de cualquier fecha) con importe todavía vacío, para completarlo desde /compras/pendientes.

    NOTA para cuando el motor de costeo empiece a leer compras de la base
    (hoy no lo hace): las consultas de costeo tienen que excluir las filas
    con importe IS NULL, son compras sin precio todavía.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.fecha_operacion, a.nombre AS articulo_nombre, a.unidad_compra,
                       p.nombre AS proveedor_nombre,
                       p.codigo_puesto AS proveedor_codigo_puesto, c.cantidad_cajones, c.contenido_por_cajon
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                JOIN proveedores p ON p.id = c.proveedor_id
                WHERE c.importe IS NULL
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


def eliminar_compra(compra_id: int) -> str | None:
    """Borra una compra (borrado real; Postgres rechaza el borrado si alguna recepción ya la referencia).

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
            cursor.execute("SELECT foto_ruta FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            foto_ruta = fila[0] if fila else None

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


def eliminar_compras_del_dia_por_proveedor(fecha_operacion, proveedor_id: int) -> None:
    """Borra TODAS las compras de un proveedor en una fecha (borrado real, mismo criterio que eliminar_compra).

    Usado por "Cancelar" en /compras/nueva: descarta de una toda la carga
    del día para ese proveedor, incluso los renglones que ya se habían
    guardado al apretar "Agregar artículo" (esa acción guarda cada renglón
    al toque, no queda nada pendiente del lado del cliente). Es una sola
    sentencia DELETE: si Postgres rechaza el borrado de alguna fila (por
    ejemplo, porque una recepción ya la referencia), no se borra ninguna —
    ni siquiera hace falta un rollback explícito, no llega a haber commit.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "DELETE FROM compras WHERE fecha_operacion = %s AND proveedor_id = %s",
                (fecha_operacion, proveedor_id),
            )
        conexion.commit()
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
