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

La ÚNICA excepción al "más viejo primero" es la salida DIRIGIDA a un
lote: una merma que el operario cargó sabiendo cuál se pudrió ("la guía
R que armé hace dos días"). Esa salida descuenta primero de su lote y
recién el excedente cae al FIFO de siempre — registra y delata, jamás
traba. Sin lote elegido (el default), todo funciona como antes.

Todo en BULTOS (lo que se cuenta en el piso).
"""


def salidas_para_reparto(total_salidas: float, dirigidas: list[dict] | None = None) -> list[dict]:
    """Arma la lista de salidas del reparto: el total de siempre + las mermas dirigidas a un lote.

    Las dirigidas viajan aparte del total (no están sumadas adentro)
    porque el reparto tiene que saber a qué lote va cada una.
    """
    salidas = [{"orden": 0, "cantidad": total_salidas}] if total_salidas else []
    for dirigida in dirigidas or []:
        salidas.append(
            {
                "orden": 0,
                "cantidad": float(dirigida["cantidad"]),
                "lote_tipo": dirigida["lote_tipo"],
                "lote_origen_id": dirigida["lote_origen_id"],
            }
        )
    return salidas


def lote_dirigido(lotes: list[dict], salida: dict) -> dict | None:
    """El lote al que apunta una salida dirigida, o None si no dirige a ninguno (o ese lote ya no existe)."""
    if salida.get("lote_tipo") is None:
        return None
    return next(
        (
            lote
            for lote in lotes
            if lote.get("tipo_lote") == salida["lote_tipo"]
            and lote.get("origen_id") == salida.get("lote_origen_id")
        ),
        None,
    )


def repartir_fifo(entradas: list[dict], salidas: list[dict]) -> dict:
    """Reparte las salidas entre las entradas por orden de fecha (FIFO).

    entradas: [{"orden": comparable, ...}, ...] con "cantidad" (> 0). Cada
    una es un lote (guía, reingreso o ajuste positivo). Se les agrega
    "restante" (lo que queda del lote) y "consumido".
    salidas: [{"orden": comparable, "cantidad": > 0, ...}, ...] (tildes de
    armado, mermas, ajustes negativos — ya en valor absoluto). Una salida
    con "lote_tipo" y "lote_origen_id" es DIRIGIDA: sale de ese lote y no
    del más viejo.

    Devuelve {"lotes": entradas con restante/consumido (más vieja primero),
    "sin_lote": bultos salidos que ningún lote cubre (0 si alcanzó),
    "stock": entradas − salidas (negativo si quedó sin explicar)}.
    """
    lotes = [dict(e, restante=float(e["cantidad"]), consumido=0.0) for e in sorted(entradas, key=lambda e: e["orden"])]
    total_salidas = sum(float(s["cantidad"]) for s in salidas)

    # Primero las dirigidas: cada una tiene prioridad sobre SU lote (el
    # operario vio qué se pudrió). Lo que ese lote no cubre cae al FIFO.
    pendiente = 0.0
    for salida in salidas:
        cantidad = float(salida["cantidad"])
        lote = lote_dirigido(lotes, salida)
        if lote is None:
            pendiente += cantidad
            continue
        consumo = min(lote["restante"], cantidad)
        lote["consumido"] += consumo
        lote["restante"] -= consumo
        pendiente += cantidad - consumo

    for lote in lotes:
        if pendiente <= 0:
            break
        consumo = min(lote["restante"], pendiente)
        lote["consumido"] += consumo
        lote["restante"] -= consumo
        pendiente -= consumo

    total_entradas = sum(float(e["cantidad"]) for e in entradas)
    return {
        "lotes": lotes,
        "sin_lote": round(pendiente, 2),
        "stock": round(total_entradas - total_salidas, 2),
    }
