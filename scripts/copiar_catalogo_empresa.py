"""Copia el catálogo de una empresa a la base (VACÍA) de otra — una sola vez, como punto de partida.

Qué copia (en orden de dependencias, preservando los IDs para que las claves
foráneas queden bien apuntadas):

    articulos, proveedores, clientes, envases, envases_costo_historial,
    clientes_parametros_historial, fichas_logistica, aprendizaje_articulos

Qué NO copia (a propósito — eso es historia de la empresa origen):
    compras, guias_compra, precios_venta_historial, disponibles,
    disponibles_detalle, fotos del Storage.

Uso:

    export DATABASE_URL_ORIGEN="postgresql://...   (la base de Frutamax)"
    export DATABASE_URL_DESTINO="postgresql://...  (la base nueva, ya con db/esquema_completo.sql corrido)"

    python -m scripts.copiar_catalogo_empresa              # EN SECO: muestra qué copiaría, no escribe nada
    python -m scripts.copiar_catalogo_empresa --ejecutar   # copia de verdad

Reglas de seguridad:
  - Sin --ejecutar NUNCA escribe: solo lee las dos bases y muestra el resumen.
  - Se niega a ejecutar si la base destino ya tiene datos en CUALQUIERA de
    esas tablas (para que correrlo dos veces no duplique nada).
  - Todo en UNA transacción en destino: si algo falla a mitad de camino, no
    queda nada a medio copiar.
  - Al final ajusta las secuencias de IDs de destino (sin esto, el primer
    alta nueva en la empresa destino explotaría por ID duplicado).

Después de copiar, REVISAR A MANO en la base destino los parámetros de cada
cliente (descuentos/adicionales/utilidad) y los costos de envase — el script
los lista justamente para eso: cada empresa negocia sus propias condiciones,
los valores copiados son solo el punto de partida.

No hay sincronización posterior: de acá en adelante cada empresa maneja su
propio catálogo.
"""

import argparse
import os
import sys

import psycopg2

# Orden de dependencias: cada tabla solo referencia a las anteriores.
TABLAS_A_COPIAR = [
    "articulos",
    "proveedores",
    "clientes",
    "envases",
    "envases_costo_historial",
    "clientes_parametros_historial",
    "fichas_logistica",
    "aprendizaje_articulos",
]


def _conectar(nombre_variable: str):
    url = os.environ.get(nombre_variable)
    if not url:
        print(f"ERROR: falta la variable de entorno {nombre_variable}")
        sys.exit(1)
    return psycopg2.connect(url)


def _contar_filas(conexion, tabla: str) -> int:
    with conexion.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
        (cantidad,) = cursor.fetchone()
    return cantidad


def _leer_tabla(conexion, tabla: str) -> tuple[list[str], list[tuple]]:
    with conexion.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {tabla} ORDER BY 1")
        columnas = [descripcion[0] for descripcion in cursor.description]
        filas = cursor.fetchall()
    return columnas, filas


def _listar_parametros_para_revisar(conexion) -> list[str]:
    """Los conceptos VIGENTES de cada cliente y los costos de envase vigentes, para revisar a mano en destino."""
    lineas = []
    with conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.nombre, h.nombre_parametro, h.tipo, h.valor, h.vigente_desde
            FROM clientes_parametros_historial h
            JOIN clientes c ON c.id = h.cliente_id
            WHERE h.vigente_desde = (
                SELECT MAX(h2.vigente_desde) FROM clientes_parametros_historial h2
                WHERE h2.cliente_id = h.cliente_id AND h2.nombre_parametro = h.nombre_parametro
                  AND h2.vigente_desde <= CURRENT_DATE
            )
            ORDER BY c.nombre, h.tipo, h.nombre_parametro
            """
        )
        for nombre_cliente, parametro, tipo, valor, vigente_desde in cursor.fetchall():
            lineas.append(f"  {nombre_cliente} | {parametro} ({tipo}) = {valor} (vigente desde {vigente_desde})")

        cursor.execute(
            """
            SELECT e.nombre, h.costo, h.vigente_desde
            FROM envases_costo_historial h
            JOIN envases e ON e.id = h.envase_id
            WHERE h.vigente_desde = (
                SELECT MAX(h2.vigente_desde) FROM envases_costo_historial h2
                WHERE h2.envase_id = h.envase_id AND h2.vigente_desde <= CURRENT_DATE
            )
            ORDER BY e.nombre
            """
        )
        for nombre_envase, costo, vigente_desde in cursor.fetchall():
            lineas.append(f"  envase {nombre_envase} = ${costo} (vigente desde {vigente_desde})")
    return lineas


def main() -> None:
    parser = argparse.ArgumentParser(description="Copia el catálogo de una empresa a la base vacía de otra.")
    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Copia de verdad. Sin esta opción, corre EN SECO: muestra qué copiaría sin escribir nada.",
    )
    argumentos = parser.parse_args()

    origen = _conectar("DATABASE_URL_ORIGEN")
    destino = _conectar("DATABASE_URL_DESTINO")

    try:
        # 1. Resumen de lo que hay en origen.
        print("=== Qué hay para copiar en la base ORIGEN ===")
        for tabla in TABLAS_A_COPIAR:
            print(f"  {tabla}: {_contar_filas(origen, tabla)} filas")

        print("\n=== Parámetros a REVISAR A MANO en destino después de copiar ===")
        print("(cada empresa negocia sus propias condiciones — esto es solo el punto de partida)")
        for linea in _listar_parametros_para_revisar(origen):
            print(linea)

        # 2. Chequeo de destino vacío — vale para los dos modos: en seco
        # también avisa, así el problema se ve antes de intentar nada.
        tablas_con_datos = [tabla for tabla in TABLAS_A_COPIAR if _contar_filas(destino, tabla) > 0]
        if tablas_con_datos:
            print(f"\nERROR: la base DESTINO ya tiene datos en: {', '.join(tablas_con_datos)}.")
            print("Este script se corre UNA sola vez, sobre una base recién creada. No se copió nada.")
            sys.exit(1)
        print("\nBase destino verificada: vacía en las 8 tablas. OK para copiar.")

        if not argumentos.ejecutar:
            print("\nMODO EN SECO: no se escribió nada. Para copiar de verdad, agregá --ejecutar.")
            return

        # 3. Copia real, todo en una transacción en destino.
        print("\n=== Copiando ===")
        with destino.cursor() as cursor:
            for tabla in TABLAS_A_COPIAR:
                columnas, filas = _leer_tabla(origen, tabla)
                if filas:
                    lista_columnas = ", ".join(columnas)
                    marcadores = ", ".join(["%s"] * len(columnas))
                    # OVERRIDING SYSTEM VALUE: los IDs son "generated always",
                    # pero acá se insertan tal cual vienen de origen para que
                    # todas las FKs (que viajan con esos mismos IDs) queden
                    # bien apuntadas sin remapear nada.
                    cursor.executemany(
                        f"INSERT INTO {tabla} ({lista_columnas}) OVERRIDING SYSTEM VALUE VALUES ({marcadores})",
                        filas,
                    )
                print(f"  {tabla}: {len(filas)} filas copiadas")

            # 4. Ajustar las secuencias: el próximo ID autogenerado tiene que
            # arrancar DESPUÉS del máximo copiado.
            for tabla in TABLAS_A_COPIAR:
                cursor.execute(
                    f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), COALESCE((SELECT MAX(id) FROM {tabla}), 1))"
                )
        destino.commit()
        print("\nLISTO: catálogo copiado y secuencias ajustadas. Revisá a mano los parámetros listados arriba.")
    finally:
        origen.close()
        destino.close()


if __name__ == "__main__":
    main()
