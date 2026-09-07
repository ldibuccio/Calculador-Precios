"""Qué lotes ve el FIFO HOY y cuáles de ellos son anteriores al corte.

SOLO LEE. No escribe una línea en la base y no toca ninguna tabla.

Es un script y no una consulta SQL a propósito: el `restante` de cada lote
no está guardado en ningún lado — lo calcula `repartir_fifo` en Python cada
vez, repartiendo TODAS las salidas sobre TODAS las entradas. Escribirlo en
SQL sería escribir una segunda versión del FIFO, y una regla escrita dos
veces son dos reglas que se separan sin que nadie lo note.

Por eso acá se llama al MISMO código que usa el sistema (`repartir_fifo` de
core/stock.py sobre `entradas_y_salidas_stock_articulos` de app/db.py): si
el reparto cambia, este número cambia con él.

Se corre con la misma DATABASE_URL que el servicio:

    DATABASE_URL='...' python scripts/lotes_vivos_del_fifo.py

Imprime CONTEOS por artículo, no una lista de lotes: con conteos siempre
sale una fila y el cero se ve; con una lista, "no hay nada" y "no corrió"
son la misma pantalla vacía.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import entradas_y_salidas_stock_articulos, listar_articulos, obtener_conexion
from core.stock import repartir_fifo, salidas_para_reparto

# Los lotes que representan CAJAS ARMADAS y no cajones. Es la lista de la
# consulta de entradas de _entradas_y_salidas_stock_varios (app/db.py): el
# único tipo_lote que sale de reprocesos.bultos_primera es 'reproceso'.
LOTES_DE_CAJA_ARMADA = {"reproceso"}


def fecha_del_corte() -> "object":
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT fecha FROM corte_modelo WHERE id = 1")
            fila = cursor.fetchone()
            return fila[0] if fila else None
    finally:
        conexion.close()


def main() -> None:
    corte = fecha_del_corte()
    if corte is None:
        print("No hay corte cargado en corte_modelo. Sin corte no hay nada que comparar.")
        return
    print(f"Corte vigente: {corte}\n")

    articulos = listar_articulos()
    por_id = {a["id"]: a["nombre"] for a in articulos}
    repartos = entradas_y_salidas_stock_articulos(list(por_id))

    filas = []
    for articulo_id, (entradas, salidas) in repartos.items():
        reparto = repartir_fifo(entradas, salidas_para_reparto(salidas))
        vivos = [lote for lote in reparto["lotes"] if lote["restante"] > 0]
        if not vivos:
            continue
        previos = [lote for lote in vivos if lote["fecha_orden"] < corte]
        cajas = [lote for lote in vivos if lote["tipo_lote"] in LOTES_DE_CAJA_ARMADA]
        filas.append(
            {
                "nombre": por_id[articulo_id],
                "vivos": len(vivos),
                "bultos_vivos": round(sum(l["restante"] for l in vivos), 2),
                "previos": len(previos),
                "bultos_previos": round(sum(l["restante"] for l in previos), 2),
                "cajas": len(cajas),
                "bultos_cajas": round(sum(l["restante"] for l in cajas), 2),
            }
        )

    filas.sort(key=lambda f: (-f["bultos_previos"], f["nombre"]))
    encabezado = f"{'Articulo':28} {'lotes':>6} {'bultos':>9} {'previos':>8} {'b.previos':>10} {'cajas':>6} {'b.cajas':>9}"
    print(encabezado)
    print("-" * len(encabezado))
    for f in filas:
        print(
            f"{f['nombre'][:28]:28} {f['vivos']:6} {f['bultos_vivos']:9} "
            f"{f['previos']:8} {f['bultos_previos']:10} {f['cajas']:6} {f['bultos_cajas']:9}"
        )
    print("-" * len(encabezado))
    print(
        f"{'TOTAL':28} {sum(f['vivos'] for f in filas):6} {round(sum(f['bultos_vivos'] for f in filas), 2):9} "
        f"{sum(f['previos'] for f in filas):8} {round(sum(f['bultos_previos'] for f in filas), 2):10} "
        f"{sum(f['cajas'] for f in filas):6} {round(sum(f['bultos_cajas'] for f in filas), 2):9}"
    )
    print(
        "\nprevios  = lotes con restante > 0 anteriores al corte: lo que el corte"
        "\n           declaro inexistente y el FIFO igual puede consumir."
        "\ncajas    = lotes con restante > 0 que son CAJAS ARMADAS (otra guia R):"
        "\n           lo que un reproceso puede tomar como si fuera materia prima."
    )


if __name__ == "__main__":
    main()
