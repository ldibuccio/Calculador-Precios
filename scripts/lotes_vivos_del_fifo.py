"""Qué ve el FIFO hoy, qué vería con el piso del corte, y de qué tamaño es la ola de frenos.

SOLO LEE. No escribe una línea en la base y no toca ninguna tabla.

Es un script y no una consulta SQL a propósito: el `restante` de cada lote
no está guardado en ningún lado — lo calcula `repartir_fifo` en Python cada
vez, repartiendo TODAS las salidas sobre TODAS las entradas. Escribirlo en
SQL sería escribir una segunda versión del FIFO, y una regla escrita dos
veces son dos reglas que se separan sin que nadie lo note.

Por eso acá se llama al MISMO código que usa el sistema (`repartir_fifo` de
core/stock.py sobre `entradas_y_salidas_stock_articulos` de app/db.py), y la
simulación del piso es ese mismo `repartir_fifo` con las entradas filtradas
— no una cuenta paralela.

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

# El compensatorio del corte no es mercadería: es el ajuste que cancela el
# saldo del modelo viejo. El piso lo saca POR TIPO y no por fecha, porque
# está fechado EN el corte y un piso por fecha lo dejaría adentro.
LOTE_DEL_COMPENSATORIO = "cierre_modelo_viejo"


def con_piso(entradas: list[dict], corte) -> list[dict]:
    """Las entradas que el FIFO vería con el piso del corte puesto.

    Es la misma regla que se va a escribir en la consulta de entradas: se
    van los lotes anteriores al corte y el compensatorio, sea cual sea su
    fecha. Las SALIDAS no se recortan: `lote_posterior_a_la_salida` ya
    impide que una salida vieja alcance un lote nuevo, así que la que se
    queda sin lote cae sola a `sin_lote`, que es lo que se quiere ver.
    """
    return [
        lote
        for lote in entradas
        if lote["fecha_orden"] >= corte and lote["tipo_lote"] != LOTE_DEL_COMPENSATORIO
    ]


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
        listas = salidas_para_reparto(salidas)
        hoy = repartir_fifo(entradas, listas)
        piso = repartir_fifo(con_piso(entradas, corte), listas)

        bultos_hoy = round(sum(l["restante"] for l in hoy["lotes"]), 2)
        bultos_piso = round(sum(l["restante"] for l in piso["lotes"]), 2)
        cajas_piso = round(
            sum(l["restante"] for l in piso["lotes"] if l["tipo_lote"] in LOTES_DE_CAJA_ARMADA), 2
        )
        por_dia = round(ritmo.get(articulo_id, 0.0), 2)
        if bultos_hoy == 0 and por_dia == 0:
            continue
        filas.append(
            {
                "nombre": por_id[articulo_id],
                "hoy": bultos_hoy,
                "piso": bultos_piso,
                "pierde": round(bultos_hoy - bultos_piso, 2),
                "cajas": cajas_piso,
                "por_dia": por_dia,
                # La ola: con el piso puesto, ¿alcanza para un día como los
                # de esta semana? Un artículo que se reprocesa y queda sin
                # bultos es un freno que suena mañana a la mañana.
                "frena": por_dia > 0 and bultos_piso < por_dia,
            }
        )

    filas.sort(key=lambda f: (not f["frena"], -f["pierde"], f["nombre"]))
    enc = f"{'Articulo':26} {'hoy':>9} {'con piso':>9} {'pierde':>9} {'de eso caja':>11} {'x dia':>8}  freno"
    print(enc)
    print("-" * len(enc))
    for f in filas:
        print(
            f"{f['nombre'][:26]:26} {f['hoy']:9} {f['piso']:9} {f['pierde']:9} "
            f"{f['cajas']:11} {f['por_dia']:8}  {'SI' if f['frena'] else ''}"
        )
    print("-" * len(enc))
    frenan = [f for f in filas if f["frena"]]
    print(
        f"\nArticulos con movimiento: {len(filas)}"
        f"\nArticulos que se reprocesan (tomaron algo desde el corte): "
        f"{len([f for f in filas if f['por_dia'] > 0])}"
        f"\nARTICULOS QUE QUEDAN SIN LOTE SUFICIENTE PARA UN DIA: {len(frenan)}"
        f"\nBultos que el FIFO deja de ver en total: "
        f"{round(sum(f['pierde'] for f in filas), 2)}"
    )
    print(
        "\nhoy         = bultos con restante > 0 que el FIFO ve hoy."
        "\ncon piso    = los que veria si no mirara nada anterior al corte."
        "\nde eso caja = cuantos de los que quedan son CAJAS ARMADAS (otra guia R):"
        "\n              la mezcla de unidades, que el piso NO arregla."
        "\nx dia       = promedio de bultos tomados por dia desde el corte."
        "\nfreno       = con el piso no le alcanza para un dia como los de esta semana."
    )


if __name__ == "__main__":
    main()
