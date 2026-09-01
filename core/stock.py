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


def fecha_de_orden(orden):
    """La FECHA de un "orden" del FIFO, o None si ese orden no la trae.

    El orden de este módulo es (fecha real del hecho, momento de carga):
    la fecha manda y el momento solo desempata dentro del mismo día. Para
    decidir si un lote ya existía cuando salió algo, lo que importa es la
    FECHA — un lote cargado a la tarde cubre una salida de esa misma
    mañana, porque en el galpón pasaron el mismo día.

    Devuelve None para un orden sin fecha (el 0 del reparto por total, que
    no sabe cuándo salió nada): sin fecha no hay regla que aplicar, y el
    reparto se comporta como siempre.
    """
    if isinstance(orden, (tuple, list)) and orden:
        return orden[0]
    return None


def lote_posterior_a_la_salida(lote, salida) -> bool:
    """¿Este lote entró DESPUÉS de que esta salida ocurrió?

    Un lote posterior no puede cubrir una salida anterior: la mercadería
    todavía no estaba en el galpón. Es la regla que separa el FIFO de "más
    viejo primero" de uno que viaja al futuro para tapar un faltante.

    Sin fecha de un lado o del otro no se puede afirmar nada, y entonces no
    se restringe: la regla avisa por lo que sabe, nunca por lo que supone.
    """
    fecha_lote = fecha_de_orden(lote.get("orden"))
    fecha_salida = fecha_de_orden(salida.get("orden"))
    if fecha_lote is None or fecha_salida is None:
        return False
    return fecha_lote > fecha_salida


def salidas_para_reparto(salidas: list[dict]) -> list[dict]:
    """Deja las salidas listas para el reparto: las de cantidad cero se van.

    Desde E4 las salidas llegan UNA POR UNA y FECHADAS (es la misma lista
    que usa el FIFO de costo), así que acá ya no hay nada que armar. Antes
    esta función fabricaba UN total sin fecha más las mermas dirigidas
    aparte, y ese total sin fecha era exactamente lo que dejaba al reparto
    consumir un lote posterior a la salida.

    Las dirigidas tampoco viajan aparte: cada una es una salida más con su
    lote_tipo y lote_origen_id encima, así que no hay forma de contarlas dos
    veces ni de olvidarse de restarlas del total.

    Se filtran las de cantidad cero —el reproceso inicial toma cero, por
    ejemplo— porque una salida que no saca nada solo agrega ruido al reparto.
    """
    return [s for s in salidas if float(s["cantidad"]) != 0]


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
    # El lote elegido se respeta aunque sea posterior: el operario lo está
    # SEÑALANDO con el dedo, no adivinándolo — si dice que se pudrió ése,
    # se pudrió ése, y discutirle la fecha sería negarle el piso.
    restos = []
    for salida in salidas:
        cantidad = float(salida["cantidad"])
        lote = lote_dirigido(lotes, salida)
        if lote is not None:
            consumo = min(lote["restante"], cantidad)
            lote["consumido"] += consumo
            lote["restante"] -= consumo
            cantidad -= consumo
        if cantidad > 0:
            restos.append((salida, cantidad))

    # Y después el FIFO de siempre, salida por salida y en orden: cada una
    # consume del lote más viejo con resto que YA EXISTÍA cuando ella
    # ocurrió. Un lote posterior no puede taparla — para eso hace falta un
    # reproceso o un ajuste con su fecha, y mientras no esté, la salida
    # queda SIN LOTE y a la vista.
    if restos and all(fecha_de_orden(s.get("orden")) is not None for s, _ in restos):
        restos.sort(key=lambda par: par[0]["orden"])

    sin_lote = 0.0
    for salida, cantidad in restos:
        pendiente = cantidad
        for lote in lotes:
            if pendiente <= 0:
                break
            if lote["restante"] <= 0:
                continue
            if lote_posterior_a_la_salida(lote, salida):
                # Los lotes vienen ordenados: de acá en adelante son todos
                # posteriores, no hay nada más que mirar para esta salida.
                break
            consumo = min(lote["restante"], pendiente)
            lote["consumido"] += consumo
            lote["restante"] -= consumo
            pendiente -= consumo
        sin_lote += pendiente

    total_entradas = sum(float(e["cantidad"]) for e in entradas)
    return {
        "lotes": lotes,
        "sin_lote": round(sin_lote, 2),
        "stock": round(total_entradas - total_salidas, 2),
    }


def reparto_a_la_fecha(entradas: list[dict], salidas: list[dict], fecha) -> dict:
    """El reparto tal como estaba AL CERRAR el día `fecha`: qué quedaba en cada lote.

    Es `repartir_fifo` sobre la historia recortada a esa fecha — nada más
    que eso, y a propósito: si la foto del pasado se calculara distinto que
    el reparto de hoy, las dos cuentas se irían separando y nadie se daría
    cuenta hasta que los números no cierren.

    Recorta las DOS puntas: los lotes que todavía no habían entrado y las
    salidas que todavía no habían ocurrido. Un lote sin fecha nunca se
    recorta (no se puede afirmar que no estuviera), que es el mismo criterio
    de `lote_posterior_a_la_salida`: se decide por lo que se sabe.

    La usan el freno del reproceso ("¿había remanente el día que dice el
    operario?") y los dos desgloses editables, que tienen que proponer un
    reparto contra el stock de la fecha del hecho y no contra el de hoy.
    """
    def hasta_la_fecha(filas):
        return [f for f in filas if (fecha_de_orden(f.get("orden")) or fecha) <= fecha]

    return repartir_fifo(hasta_la_fecha(entradas), hasta_la_fecha(salidas))
