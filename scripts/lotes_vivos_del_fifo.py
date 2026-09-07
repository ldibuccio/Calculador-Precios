"""Qué lotes ve el FIFO hoy, por artículo, y cuántos son cajas armadas.

SOLO LEE. No escribe una línea en la base y no toca ninguna tabla.

Es un script y no una consulta SQL a propósito: el `restante` de cada lote
no está guardado en ningún lado — lo calcula `repartir_fifo` en Python cada
vez, repartiendo TODAS las salidas sobre TODAS las entradas. Escribirlo en
SQL sería escribir una segunda versión del FIFO, y una regla escrita dos
veces son dos reglas que se separan sin que nadie lo note.

Por eso acá se llama al MISMO código que usa el sistema (`repartir_fifo` de
core/stock.py sobre `entradas_y_salidas_stock_articulos` de app/db.py).

El piso del corte NO se simula acá: desde el 07/09 vive en la consulta de
entradas, así que las listas que llegan ya vienen recortadas. Simularlo
encima sería aplicarlo dos veces, y escribir la regla por segunda vez es
exactamente cómo se separan.

Se corre con la misma DATABASE_URL que el servicio:

    DATABASE_URL='...' python scripts/lotes_vivos_del_fifo.py

Imprime CONTEOS por artículo, no una lista de lotes: con conteos siempre
sale una fila y el cero se ve; con una lista, "no hay nada" y "no corrió"
son la misma pantalla vacía.
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import entradas_y_salidas_stock_articulos, listar_articulos, obtener_conexion
from core.stock import repartir_fifo, salidas_para_reparto

# El único tipo_lote que sale de reprocesos.bultos_primera en la consulta de
# entradas de _entradas_y_salidas_stock_varios (app/db.py). O sea: los lotes
# que son CAJAS ARMADAS y no cajones.
LOTES_DE_CAJA_ARMADA = {"reproceso"}


def datos_del_corte() -> tuple:
    """(fecha del corte, {articulo_id: bultos tomados por día desde el corte})."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT fecha FROM corte_modelo WHERE id = 1")
            fila = cursor.fetchone()
            if fila is None:
                return None, {}
            corte = fila[0]
            cursor.execute(
                """
                SELECT articulo_id,
                       SUM(bultos_tomados) / GREATEST(COUNT(DISTINCT fecha_operacion), 1)
                FROM reprocesos
                WHERE anulado_el IS NULL AND tipo = 'normal' AND fecha_operacion >= %s
                GROUP BY articulo_id
                """,
                (corte,),
            )
            return corte, {int(a): float(b) for a, b in cursor.fetchall()}
    finally:
        conexion.close()


def main() -> None:
    corte, ritmo = datos_del_corte()
    if corte is None:
        print("No hay corte cargado en corte_modelo. Sin corte no hay piso que simular.")
        return
    print(f"Corte vigente: {corte}\n")

    por_id = {a["id"]: a["nombre"] for a in listar_articulos()}
    repartos = entradas_y_salidas_stock_articulos(list(por_id))

    filas = []
    for articulo_id, (entradas, salidas) in repartos.items():
        reparto = repartir_fifo(entradas, salidas_para_reparto(salidas))
        vivos = [l for l in reparto["lotes"] if l["restante"] > 0]
        bultos = round(sum(l["restante"] for l in vivos), 2)
        cajas = round(
            sum(l["restante"] for l in vivos if l["tipo_lote"] in LOTES_DE_CAJA_ARMADA), 2
        )
        por_dia = round(ritmo.get(articulo_id, 0.0), 2)
        if bultos == 0 and por_dia == 0:
            continue
        filas.append(
            {
                "nombre": por_id[articulo_id],
                "lotes": len(vivos),
                "bultos": bultos,
                "cajas": cajas,
                "por_dia": por_dia,
                # El síntoma que se va a ver en el galpón: un artículo que se
                # reprocesa y no tiene bultos para un día es un freno que
                # suena mañana a la mañana.
                "frena": por_dia > 0 and bultos < por_dia,
            }
        )

    filas.sort(key=lambda f: (not f["frena"], -f["por_dia"], f["nombre"]))
    enc = f"{'Articulo':26} {'lotes':>6} {'bultos':>9} {'de eso caja':>11} {'x dia':>8}  freno"
    print(enc)
    print("-" * len(enc))
    for f in filas:
        print(
            f"{f['nombre'][:26]:26} {f['lotes']:6} {f['bultos']:9} "
            f"{f['cajas']:11} {f['por_dia']:8}  {'SI' if f['frena'] else ''}"
        )
    print("-" * len(enc))
    frenan = [f for f in filas if f["frena"]]
    print(
        f"\nArticulos con movimiento: {len(filas)}"
        f"\nArticulos que se reprocesan (tomaron algo desde el corte): "
        f"{len([f for f in filas if f['por_dia'] > 0])}"
        f"\nARTICULOS SIN LOTE SUFICIENTE PARA UN DIA: {len(frenan)}"
    )
    print(
        "\nbultos      = restante > 0 que el FIFO ve HOY, ya con el piso del corte."
        "\nde eso caja = cuantos son CAJAS ARMADAS (otra guia R): la mezcla de"
        "\n              unidades, que el piso NO arregla."
        "\nx dia       = promedio de bultos tomados por dia desde el corte."
        "\nfreno       = no le alcanza para un dia como los de esta semana."
    )


if __name__ == "__main__":
    main()
