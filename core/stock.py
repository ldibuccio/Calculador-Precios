"""FIFO del stock del depósito: repartir las salidas entre los lotes — puro, sin tocar la base.

La decisión de fondo, cerrada por el dueño: el FIFO se CALCULA cada vez,
nunca se guardan asignaciones. Guardar "esta salida salió de tal guía" se
rompe con la operatoria real (destildar un renglón, corregir una
recepción, cargar un reingreso con fecha de ayer): habría que mantener
sincronizado un dato derivado. Repitiendo el reparto sobre los hechos, el
detalle por lote se reacomoda solo en cada consulta.

El reparto: entradas ordenadas de más vieja a más nueva, salidas idem;
cada salida consume del lote más viejo que todavía tenga resto. Si las
salidas superan las entradas, el excedente queda como SIN LOTE — no se
cuelga de ninguna guía (sería falsear la trazabilidad) y no es un error:
es mercadería que salió y que un reproceso (módulo 2) o un ajuste tiene
que explicar. El stock del artículo puede quedar negativo a propósito:
el armado jamás se traba por stock.

Todo en BULTOS (lo que se cuenta en el piso).
"""


def repartir_fifo(entradas: list[dict], salidas: list[dict]) -> dict:
    """Reparte las salidas entre las entradas por orden de fecha (FIFO).

    entradas: [{"orden": comparable, ...}, ...] con "cantidad" (> 0). Cada
    una es un lote (guía, reingreso o ajuste positivo). Se les agrega
    "restante" (lo que queda del lote) y "consumido".
    salidas: [{"orden": comparable, "cantidad": > 0, ...}, ...] (tildes de
    armado, mermas, ajustes negativos — ya en valor absoluto).

    Devuelve {"lotes": entradas con restante/consumido (más vieja primero),
    "sin_lote": bultos salidos que ningún lote cubre (0 si alcanzó),
    "stock": entradas − salidas (negativo si quedó sin explicar)}.
    """
    lotes = [dict(e, restante=float(e["cantidad"]), consumido=0.0) for e in sorted(entradas, key=lambda e: e["orden"])]
    total_salidas = sum(float(s["cantidad"]) for s in salidas)

    pendiente = total_salidas
    for lote in lotes:
        if pendiente <= 0:
            break
        consumo = min(lote["restante"], pendiente)
        lote["consumido"] = consumo
        lote["restante"] -= consumo
        pendiente -= consumo

    total_entradas = sum(float(e["cantidad"]) for e in entradas)
    return {
        "lotes": lotes,
        "sin_lote": round(pendiente, 2),
        "stock": round(total_entradas - total_salidas, 2),
    }
