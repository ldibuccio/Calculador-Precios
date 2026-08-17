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
                SELECT fl.id, fl.articulo_id, a.nombre AS articulo_nombre, fl.envase_id, e.nombre AS envase_nombre,
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

    Excluye las compras rechazadas (estado = 'rechazado'): no se
    recibieron, no tienen que ensuciar el costo promedio. Excluye también
    las que nunca ingresaron al depósito (estado = 'no_ingresado'): mismo
    motivo, no hay mercadería real detrás de esa compra. Y las canceladas
    en Logística (estado_retiro = 'cancelado'): una compra cancelada
    nunca se retiró del puesto, o sea nunca se compró de verdad.
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
                       c.importe
                FROM compras c
                JOIN articulos a ON a.id = c.articulo_id
                WHERE c.fecha_operacion BETWEEN %s AND %s
                  AND c.estado IS DISTINCT FROM 'rechazado'
                  AND c.estado IS DISTINCT FROM 'no_ingresado'
                  AND c.estado_retiro IS DISTINCT FROM 'cancelado'
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
    transacción que el INSERT de la compra.

    estado arranca en 'pendiente' (queda a la espera de Recepción en
    Depósito) — se escribe acá explícitamente, a propósito SIN default a
    nivel de columna: así las compras cargadas antes de este cambio quedan
    con estado NULL para siempre, sin aparecer nunca en Recepción.

    estado_retiro arranca también en 'pendiente' (queda a la espera de
    Logística, que retira del puesto en el Mercado ANTES de que la
    mercadería llegue al depósito — ver listar_compras_pendientes_retiro),
    mismo criterio sin default de columna.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
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

            cursor.execute(
                """
                INSERT INTO compras
                    (fecha_operacion, articulo_id, proveedor_id, cantidad_cajones, contenido_por_cajon,
                     cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro, foto_ruta,
                     guia_id, guia_punto, estado, estado_retiro)
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
                    foto_ruta,
                    guia_id,
                    guia_punto,
                ),
            )
        conexion.commit()
    finally:
        conexion.close()


def compra_tiene_cantidad_bloqueada(estado: str | None, estado_retiro: str | None) -> bool:
    """True si el artículo/cantidad/tipo de retiro de la compra ya no se pueden editar.

    Única definición de esta regla en todo el código — la usan la
    pantalla de Editar Compra (para mostrar el aviso y atenuar los
    campos) y actualizar_cantidad_compra (para bloquear el guardado de
    verdad). Recepcionada o retirada: cambiar la cantidad después de eso
    modificaría un costo que ya se pudo haber usado para negociar
    precios con el cliente.
    """
    return estado == "recepcionado" or estado_retiro == "retirado"


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

    Bloqueada (ValueError) si la compra ya fue recepcionada o retirada
    (ver compra_tiene_cantidad_bloqueada) — independiente del bloqueo de
    precio, que vive aparte en actualizar_precio_compra.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT estado, estado_retiro FROM compras WHERE id = %s", (compra_id,))
            fila = cursor.fetchone()
            estado, estado_retiro = fila if fila else (None, None)

            if compra_tiene_cantidad_bloqueada(estado, estado_retiro):
                if estado == "recepcionado":
                    raise ValueError("Esta compra ya fue recepcionada, no se puede editar la cantidad.")
                raise ValueError("Esta compra ya fue retirada, no se puede editar la cantidad.")

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


def recepcionar_compra(compra_id: int, cantidad_cajones_real: float, valor_real: float) -> str | None:
    """Marca una compra como recepcionada, con los valores REALES que pesó/contó Depósito.

    El significado de valor_real depende de la unidad de compra del
    artículo:

    - Por kilo: Depósito pesa UN bulto/cajón en la balanza, no toda la
      carga junta — valor_real es directamente contenido_por_cajon_real
      (kilos de ese bulto), y cantidad_kilos_real se deriva acá adentro
      como cantidad_cajones_real × valor_real.
    - Por unidad/cubeta: se sigue contando el total (no tiene sentido
      "pesar" bulto a bulto algo que se cuenta) — valor_real es
      cantidad_fraccion_real directo, y contenido_por_cajon_real se
      deriva como promedio (valor_real / cantidad_cajones_real), igual
      que antes.

    El estimado (cantidad_cajones/contenido_por_cajon/etc., sin "_real")
    nunca se toca.

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

            if unidad_compra == "kilo":
                contenido_por_cajon_real = valor_real
                cantidad_kilos_real = cantidad_cajones_real * valor_real
                cantidad_fraccion_real = None
            else:
                cantidad_fraccion_real = valor_real
                contenido_por_cajon_real = valor_real / cantidad_cajones_real if cantidad_cajones_real else None
                cantidad_kilos_real = None

            cursor.execute(
                """
                UPDATE compras
                SET estado = 'recepcionado',
                    cantidad_cajones_real = %s,
                    contenido_por_cajon_real = %s,
                    cantidad_kilos_real = %s,
                    cantidad_fraccion_real = %s,
                    procesada_el = now()
                WHERE id = %s
                """,
                (cantidad_cajones_real, contenido_por_cajon_real, cantidad_kilos_real, cantidad_fraccion_real, compra_id),
            )

            aviso = _auto_retirar_si_corresponde(cursor, compra_id)
        conexion.commit()
        return aviso
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


def marcar_compra_retirada(compra_id: int, origen: str) -> None:
    """Marca una compra como retirada del puesto (ver Logística, /logistica/retiro)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE compras
                SET estado_retiro = 'retirado', retiro_procesado_el = now(), retiro_origen = %s
                WHERE id = %s
                """,
                (origen, compra_id),
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


def listar_compras_sin_precio() -> list[dict]:
    """Compras (de cualquier fecha) con importe todavía vacío, para completarlo desde /compras/pendientes.

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
    """Borra una compra (borrado real), salvo que ya haya sido recepcionada o retirada.

    Una compra recepcionada tiene kilaje real pesado, y una retirada ya
    salió del puesto — borrar cualquiera de las dos las perdería para
    siempre, así que se rechaza acá con un ValueError (el mensaje es el
    que se le muestra al usuario tal cual). Por ahora esto no tiene
    excepción: cuando exista el sistema de permisos, un gerente podrá
    forzarlo con su acceso, pero eso no se resuelve en esta función.
    'pendiente', 'rechazado'/'cancelado' y 'no_ingresado' se siguen
    pudiendo borrar sin restricción.

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

    Ya no es un DELETE ciego de todo el lote: las compras ya recepcionadas
    o retiradas quedan afuera del borrado (mismo criterio que
    eliminar_compra) — nunca en silencio, quien llama tiene que avisar
    con los números que devuelve esta función, no dar por hecho que se
    borró todo.

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
