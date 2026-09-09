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

from datetime import timedelta
from typing import NamedTuple


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


# ── Qué lote prefiere cada salida ────────────────────────────────────────
#
# El FIFO ordena por FECHA y hasta acá no miraba QUÉ era cada lote, así que
# `reprocesos.bultos_primera` (una caja ya armada) entraba a la misma pila
# que los cajones de las compras. Medido el 08/09 desde el corte: 10 guías R
# se costearon contra cajas armadas ($2.798.438,92 — e5_1) y 359 de 494
# bultos de armado se costearon contra cajones TENIENDO caja disponible
# ($9.658.218,30 — e5_4).
#
# Esto es SOLO la regla. Nadie la usa todavía: quién la aplica y cómo son
# las piezas 2 y 3.

# La merma parte en dos: qué se está tirando, materia prima o trabajo.
# Tirar un cajón crudo cuesta lo que costó comprarlo; tirar un bulto que
# ya pasó por la mesa cuesta eso MÁS el laburo que se le puso, y el costo
# del lote ya lo refleja. Un lote de compra es el cajón como vino, y un
# ajuste (stock inicial, corrección de registro) se cuenta igual: es
# mercadería sin procesar. Una guía R ya pasó por la mesa, y un reingreso
# por rechazo también — salió armado y volvió.
#
# Vive acá y no en core/costo_real.py porque ese módulo importa de éste, y
# al revés sería un ciclo. Es UNA definición: el corte de la merma y la
# prioridad del FIFO tienen que decir lo mismo o se separan.
TIPOS_LOTE_TRABAJADO = ("reproceso", "reingreso_rechazo")


def es_lote_trabajado(tipo_lote) -> bool:
    """¿Este lote ya pasó por la mesa? (guía R o reingreso por rechazo)."""
    return tipo_lote in TIPOS_LOTE_TRABAJADO


class Prioridad(NamedTuple):
    """Qué lotes prefiere una salida y cuáles tiene PROHIBIDOS.

    Son dos cosas distintas y conviene que se llamen distinto:

    - `prefiere` es un ORDEN. La salida busca primero entre esos tipos y,
      si no alcanzan, sigue con el resto. Nunca deja bultos sin lote por
      preferir: un artículo que no se reprocesa nunca (manzana, pera,
      arándano) no tiene una sola caja armada, y su armado tiene que poder
      salir del cajón como siempre. Medido: 135 de los 494 bultos son eso.
    - `prohibe` es una PARED. La salida no puede tocar esos tipos aunque se
      quede corta; el que decide qué hacer con eso es el freno, no el
      reparto.

    Un tipo no puede estar en las dos.
    """

    prefiere: tuple
    prohibe: tuple


SIN_PREFERENCIA = Prioridad(prefiere=(), prohibe=())

# La tabla completa, y explícita hasta en los casos que no hacen nada: un
# tipo que cayera al default por olvido y otro que caiga por decisión se
# ven igual desde afuera. El test que lee el CHECK de la base exige que
# estén todos nombrados acá.
_PRIORIDAD_POR_SALIDA = {
    # Un armado toma CAJA ARMADA primero. Es preferencia y no pared: si no
    # hay cajas, sale del cajón, que es lo que pasa todos los días con los
    # artículos que no se reprocesan.
    "armado": Prioridad(prefiere=TIPOS_LOTE_TRABAJADO, prohibe=()),
    # Una guía R toma MATERIA PRIMA y nada más. Acá sí es pared: reprocesar
    # una caja ya armada no es un reproceso, es contar dos veces el mismo
    # trabajo. Si no alcanza, frena (crear_reproceso), no se estira.
    "reproceso_toma": Prioridad(prefiere=(), prohibe=TIPOS_LOTE_TRABAJADO),
    # Merma y ajuste: FIFO PURO, sin preferencia, y es una decisión tomada
    # el 08/09, no un olvido. Una merma puede ser de un cajón podrido o de
    # una caja que se golpeó, y no hay forma de saberlo desde el tipo de
    # movimiento. Inventar una preferencia acá sería afirmar algo que nadie
    # verificó; el operario que SÍ lo sabe ya tiene la merma dirigida
    # (lote_tipo / lote_origen_id), que gana antes que cualquier FIFO.
    "merma": SIN_PREFERENCIA,
    "ajuste": SIN_PREFERENCIA,
    # Un stock_inicial negativo no debería existir —la foto del corte suma—
    # pero la base no lo prohíbe (no hay CHECK de signo), así que si aparece
    # como salida se comporta como un ajuste. Nombrado a propósito: es la
    # diferencia entre "decidido" y "se nos pasó".
    "stock_inicial": SIN_PREFERENCIA,
}


def prioridad_de_lote(salida) -> Prioridad:
    """Qué lotes prefiere y cuáles tiene prohibidos esta salida.

    El default es SIN_PREFERENCIA —el FIFO de siempre— y es el default
    SEGURO: una salida de un tipo que todavía no existe se reparte como se
    repartía antes, nunca se queda sin lote por una regla nueva. Lo que
    avisa de un tipo nuevo es el test contra el CHECK, no una excepción en
    producción con el galpón trabajando.
    """
    return _PRIORIDAD_POR_SALIDA.get(salida.get("tipo"), SIN_PREFERENCIA)


# Cuando el freno del reproceso corre, la guía R TODAVÍA NO EXISTE: es la
# salida que está por nacer. Va como constante porque son tres los que
# tienen que preguntar por ella —el freno, el desglose de la pantalla y la
# escritura de los consumos— y el tipo escrito a mano en tres lados es una
# regla escrita tres veces.
SALIDA_REPROCESO = {"tipo": "reproceso_toma"}


def lotes_permitidos(lotes: list[dict], salida: dict) -> list[dict]:
    """Los lotes que ESTA salida tiene permitido consumir, en el MISMO orden.

    Saca los PROHIBIDOS y nada más. La preferencia (`prefiere`) es un orden
    y NO se aplica acá a propósito: reordenar la lista rompería el `break`
    de `repartir_fifo` y de `atribuir_costos_fifo`, que vale justamente
    porque los lotes vienen ordenados por fecha. La preferencia se aplica
    adentro del reparto, con dos pasadas sobre esta misma lista ordenada.
    """
    prohibidos = prioridad_de_lote(salida).prohibe
    if not prohibidos:
        return lotes
    return [lote for lote in lotes if lote["tipo_lote"] not in prohibidos]


def pasadas_de_lotes(lotes: list[dict], salida: dict) -> list[list[dict]]:
    """Las listas que ESTA salida recorre, en orden de preferencia.

    Devuelve una lista POR PASADA, cada una en el mismo orden de fecha que
    venía. Sin preferencia devuelve una sola pasada con todo, o sea el FIFO
    de siempre.

    DOS PASADAS Y NO UNA LISTA REORDENADA, y es la parte que importa: el
    `break` de `repartir_fifo` y el de `atribuir_costos_fifo` cortan cuando
    llegan a un lote posterior a la salida, y eso vale SOLO porque los lotes
    vienen por fecha. Reordenando por tipo, los dos cortarían de más y en
    silencio. Adentro de cada pasada el orden sigue siendo la fecha, así que
    el corte sigue siendo correcto.

    Aplica la PREFERENCIA y NO la prohibición, y es una decisión del 08/09,
    no un olvido: la pared de la guía R vive donde se le OFRECEN los lotes
    (`lotes_permitidos`, pieza 2) y no acá adentro. Dos razones:

    - Estas funciones REJUEGAN LA HISTORIA, y la historia de las 10 guías R
      medidas es que sí se comieron cajas armadas: de ahí salieron los
      $2.798.438,92, leídos de `reprocesos_consumos`, que está congelado. Un
      reparto que se las negara pondría la pantalla de stock a contradecir
      el documento congelado.
    - El backtest que autorizó A (`frenan_con_a = 0`) modeló exactamente
      esto. Cambiarlo acá invalidaría la medición que dejó mergear A sin
      avisarle al galpón.
    """
    prefiere = prioridad_de_lote(salida).prefiere
    if not prefiere:
        return [lotes]
    preferidos = [lote for lote in lotes if lote["tipo_lote"] in prefiere]

    # LA PARED DEL ARMADO, y se expresa QUITANDO la pasada de respaldo en vez
    # de agregando una prohibición. Es la misma decisión escrita al revés, y
    # importa: acá está el único lugar donde se decide qué lotes ve una
    # salida, y lo llaman LAS DOS copias del FIFO (`repartir_fifo` para el
    # stock y `atribuir_costos_fifo` para el costo). Escrita así no se pueden
    # desfasar; escrita como un filtro en cada una, sí.
    #
    # Con envase, la mercadería sale en NUESTRA caja: una caja no puede salir
    # de un cajón sin pasar por una guía R. Si no hay caja, el bulto queda
    # SIN LOTE —que es información verdadera: salió y el papel no está— y se
    # asigna solo cuando la guía R aparece, porque el reparto se rejuega en
    # cada lectura y `lote_posterior_a_la_salida` compara FECHAS.
    #
    # El cajón queda intacto A PROPÓSITO: no lo consumió el armado, lo va a
    # consumir el reproceso. Si el armado le bajara el restante, la guía R
    # que viene a explicarlo no lo encontraría y el freno la rechazaría —
    # verificado. Medida la ventana el 08/09 sobre Frutamax: 18 de 20 guías
    # R se cargan el mismo día y el peor caso fue 1 día.
    if salida.get("ficha_con_envase"):
        return [preferidos]

    if not preferidos:
        return [lotes]
    return [preferidos, [lote for lote in lotes if lote["tipo_lote"] not in prefiere]]


def lotes_ofrecidos(lotes: list[dict], salida: dict) -> list[dict]:
    """Los lotes que la pared le OFRECE a esta salida, en orden y sin repetir.

    Sale de `pasadas_de_lotes` y por eso NO vuelve a preguntar por
    `ficha_con_envase`: la condición se decide UNA vez, arriba.

    EN EL ORDEN QUE ENTRARON, que es el de fecha, y no en el de las pasadas.
    Las pasadas están ordenadas por preferencia —primero lo trabajado— y eso
    sirve para repartir, pero acá la lista se le muestra a una persona: un
    desglose que salta del 05/09 al 01/09 porque uno es caja y el otro cajón
    no se lee. Filtra, no reordena.

    Los tres que tienen que decir lo mismo la leen de acá:

    - el reparto, que recorre las pasadas (`repartir_fifo`, `atribuir_costos_fifo`);
    - la pantalla del armado, que NO LISTA lo que no se puede elegir — un
      cajón a la vista en una ficha con envase invita a preguntarse por qué
      está ahí, y la respuesta es que no tendría que estar;
    - `guardar_lotes_elegidos`, que lo RECHAZA si llega igual por un POST a
      mano. La guarda no puede vivir solo en el HTML: el que decide es el
      servidor y la pantalla es la forma de cumplirlo cómodo.

    Hasta el 09/09 la pared vivía solo en `pasadas_de_lotes`, y
    `lotes_senalados` —la corrección del que arma— corre ANTES, en la pasada
    de los dirigidos. Un renglón con el cajón elegido a mano se llevaba el
    cajón, con envase y todo: medido corriendo `repartir_fifo`, 10 bultos
    consumidos del cajón donde la pared sola dejaba 10 sin lote.
    """
    # Por identidad y no por igualdad: las pasadas contienen los MISMOS
    # objetos que entraron, y dos lotes distintos pueden ser dicts iguales.
    ofrecidos = {id(lote) for pasada in pasadas_de_lotes(lotes, salida) for lote in pasada}
    return [lote for lote in lotes if id(lote) in ofrecidos]


def lote_ofrecido(lote: dict, salida: dict) -> bool:
    """¿La pared le ofrece ESTE lote a esta salida?

    Se contesta preguntándole a `lotes_ofrecidos` por una lista de UNO, y no
    con una condición propia: una copia acá se separaría de la pared el día
    que la pared cambie, que es exactamente cómo se abrió el agujero que
    esto viene a cerrar.
    """
    return bool(lotes_ofrecidos([lote], salida))


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


def lotes_senalados(lotes: list[dict], salida: dict) -> list[tuple[dict, float]]:
    """Los lotes que ALGUIEN ELIGIÓ para esta salida, con cuánto sale de cada uno.

    Dos formas de señalar, y son la misma cosa con distinta cantidad de lotes:

    - `lote_tipo` + `lote_origen_id`: UN lote, sin cantidad. Es la merma
      dirigida — el operario dice cuál se pudrió y sale todo lo que ese lote
      pueda cubrir.
    - `lotes_elegidos`: [{"lote_tipo", "lote_origen_id", "bultos"}], VARIOS
      lotes con su cantidad. Es la corrección del que arma un pedido.

    El renglón corregido sigue siendo UNA salida y no varias: si se partiera
    en una salida por lote, todo lo que cuelga de la salida —los kilos
    enviados, la ficha, el cliente— se contaría una vez por lote, y la
    Rentabilidad Real sumaría los kilos multiplicados.

    Un lote elegido que ya no existe se saltea en silencio: el reparto se
    rejuega sobre los hechos de hoy, y si una recepción se corrigió y el lote
    desapareció, esa porción vuelve al FIFO como cualquier otra.
    """
    elegidos = salida.get("lotes_elegidos")
    if elegidos:
        senalados = []
        for fila in elegidos:
            lote = lote_dirigido(lotes, {"lote_tipo": fila["lote_tipo"],
                                         "lote_origen_id": fila["lote_origen_id"]})
            if lote is not None:
                senalados.append((lote, float(fila["bultos"])))
        return senalados

    lote = lote_dirigido(lotes, salida)
    # Sin cantidad: la merma dirigida saca de su lote todo lo que pueda.
    return [(lote, float(salida["cantidad"]))] if lote is not None else []


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

    # Primero las SEÑALADAS: cada una tiene prioridad sobre SUS lotes (el
    # operario vio qué se pudrió, o el que armó dijo de dónde sacó). Lo que
    # esos lotes no cubren cae al FIFO.
    # El lote elegido se respeta aunque sea posterior: lo están SEÑALANDO con
    # el dedo, no adivinándolo — si dicen que salió de ése, salió de ése, y
    # discutirles la fecha sería negarles el piso.
    restos = []
    for salida in salidas:
        cantidad = float(salida["cantidad"])
        for lote, pedidos in lotes_senalados(lotes, salida):
            if cantidad <= 0:
                break
            consumo = min(lote["restante"], pedidos, cantidad)
            lote["consumido"] += consumo
            lote["restante"] -= consumo
            cantidad = round(cantidad - consumo, 2)
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
        # Una pasada por tipo preferido y otra con el resto. Cada pasada
        # sigue ordenada por fecha, que es lo que hace válido el `break`.
        for pasada in pasadas_de_lotes(lotes, salida):
            for lote in pasada:
                if pendiente <= 0:
                    break
                if lote["restante"] <= 0:
                    continue
                if lote_posterior_a_la_salida(lote, salida):
                    # Los lotes vienen ordenados: de acá en adelante son
                    # todos posteriores, no hay más que mirar EN ESTA
                    # pasada. La siguiente arranca de nuevo desde su
                    # primer lote, que puede ser anterior a éste.
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


def reparto_a_la_fecha(entradas: list[dict], salidas: list[dict], fecha, salidas_hasta=None) -> dict:
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

    `salidas_hasta` recorta las salidas por una fecha distinta que las
    entradas. El default es la misma —la foto honesta del pasado—; el
    reproceso la corre un día para atrás, y por qué lo hace está escrito en
    `reparto_para_reproceso`.
    """
    def hasta(filas, tope):
        return [f for f in filas if (fecha_de_orden(f.get("orden")) or tope) <= tope]

    return repartir_fifo(hasta(entradas, fecha), hasta(salidas, fecha if salidas_hasta is None else salidas_hasta))


def reparto_para_reproceso(entradas: list[dict], salidas: list[dict], fecha) -> dict:
    """El reparto contra el que se mide un reproceso del día `fecha`.

    Recorte ASIMÉTRICO, decidido el 01/09: entradas HASTA LA FECHA
    INCLUSIVE, salidas HASTA EL DÍA ANTERIOR. Las salidas del mismo día no
    cuentan, y no es una concesión: dentro de un día el sistema no tiene
    orden —guarda fechas, no horas—, así que descontar una salida del mismo
    día es afirmar un orden que no sabemos, y afirmarlo justo en contra del
    que está reprocesando. Es la misma simetría que ya se acepta del otro
    lado: un lote cargado a la tarde cubre una salida de esa misma mañana.

    Es UNA sola definición a propósito. La usan las TRES cosas que tienen
    que ver los mismos lotes: el freno ("¿alcanzaba ese día?"), el desglose
    que se le muestra al operario, y la escritura de los consumos. Si el
    freno midiera contra una lista y la escritura consumiera de otra, la
    pantalla aprobaría un reparto que la base después no puede cumplir.
    """
    return reparto_a_la_fecha(entradas, salidas, fecha, salidas_hasta=fecha - timedelta(days=1))


def bultos_en_los_lotes(lotes: list[dict]) -> float:
    """Contra qué número compara el freno: la SUMA DE LOS RESTANTES, no el neto.

    Recibe la LISTA y no el reparto entero desde la pieza 2: el freno de la
    guía R mide contra los lotes que ella TIENE PERMITIDO tomar, que no son
    todos los del reparto. Pedir la lista obliga al llamador a decir cuál.

    Decidido el 01/09. Este número NUNCA puede ser negativo —los restantes
    son >= 0 por construcción— y el negativo del neto vive en `sin_lote`,
    que es otra cosa. Con eso, "¿qué pasa si el stock ya venía negativo?" no
    llega a plantearse: el freno no mira ese número. Trabar a un operario
    por un agujero que ya estaba ahí antes de que tocara nada sería trabarlo
    por lo mismo que está arreglando.
    """
    return round(sum(float(lote["restante"]) for lote in lotes), 2)


def propuesta_fifo(lotes: list[dict], total: float, salida: dict | None = None) -> list[dict]:
    """Del más viejo primero: cuánto sale de cada lote para juntar `total`.

    Es el default del desglose y lo que se escribe si el operario no toca
    nada. Devuelve solo los lotes que aportan algo. Si los lotes no llegan a
    cubrir `total`, devuelve lo que hay: el que decide que eso no se puede
    guardar es el freno, no esta función.

    `salida` le da la MISMA preferencia que va a usar el reparto. Sin ella
    propone el FIFO puro, que es lo que quiere el que ya recibió la lista
    filtrada. Si la propuesta y el reparto salieran de reglas distintas, la
    pantalla aprobaría un reparto que el server después no cumple — que es
    exactamente lo que el comentario de `crear_reproceso` promete que no
    puede pasar.
    """
    consumos = []
    pendiente = round(float(total), 2)
    pasadas = pasadas_de_lotes(lotes, salida) if salida is not None else [lotes]
    for pasada in pasadas:
        for lote in pasada:
            if pendiente <= 0:
                break
            if lote["restante"] <= 0:
                continue
            bultos = round(min(float(lote["restante"]), pendiente), 2)
            pendiente = round(pendiente - bultos, 2)
            consumos.append({"tipo_lote": lote["tipo_lote"], "origen_id": lote["origen_id"], "bultos": bultos})
    return consumos


def validar_reparto_declarado(
    lotes: list[dict], total: float, reparto: list[dict], salida: dict | None = None
) -> str | None:
    """El reparto que editó el operario, ¿se puede cumplir? Devuelve el motivo, o None si está bien.

    Se revalida SIEMPRE en el server contra los lotes frescos, aunque la
    pantalla ya lo haya chequeado: entre que se dibujó el desglose y se
    apretó Guardar, otro pudo armar un pedido y mover los restantes. Si algo
    cambió, el motivo vuelve a la pantalla junto con una propuesta nueva.
    """
    prohibidos = prioridad_de_lote(salida).prohibe if salida is not None else ()
    por_lote = {(lote["tipo_lote"], lote["origen_id"]): lote for lote in lotes}
    suma = 0.0
    for fila in reparto:
        # El prohibido se contesta ANTES de buscarlo: como no está en la
        # lista, el lookup lo daría por "ya no está disponible", que manda
        # al operario a mirar el stock cuando el problema es otro.
        if fila.get("tipo_lote") in prohibidos:
            return "Una guía R no puede tomar cajas ya armadas: elegí mercadería sin procesar."
        lote = por_lote.get((fila.get("tipo_lote"), fila.get("origen_id")))
        if lote is None:
            return "Uno de los lotes que elegiste ya no está disponible."
        bultos = float(fila.get("bultos") or 0)
        if bultos < 0:
            return "No se puede tomar una cantidad negativa de un lote."
        if round(bultos - float(lote["restante"]), 2) > 0:
            return "De uno de los lotes pediste más de lo que quedaba."
        suma = round(suma + bultos, 2)
    if round(suma - float(total), 2) != 0:
        return "Lo repartido entre los lotes no da los bultos que declaraste."
    return None


def sin_lote_si_el_lote_cambia(entradas, salidas, tipo_lote, origen_id, nueva_cantidad) -> tuple[float, float]:
    """(sin_lote de ahora, sin_lote si ese lote pasara a tener `nueva_cantidad`).

    Es la cuenta del aviso de Corregir Recepción, y se hace SIMULANDO en vez
    de estimando: se corre el mismo reparto dos veces y se compara. Bajar un
    lote no rompe siempre —si el artículo tiene otros, el FIFO reacomoda las
    salidas solo—, así que un aviso que salte por "bajaste la cantidad"
    gritaría casi siempre en falso, y un cartel que aparece igual se deja de
    leer. Acá el amarillo aparece solo cuando la diferencia es mayor a cero.

    Subir tampoco se pregunta desde afuera: un lote más grande cubre lo mismo
    y más, así que la diferencia da cero o negativa y no hay nada que avisar.
    """
    de_ahora = repartir_fifo(entradas, salidas)["sin_lote"]
    con_el_nuevo = repartir_fifo(
        [
            dict(lote, cantidad=nueva_cantidad)
            if lote.get("tipo_lote") == tipo_lote and lote.get("origen_id") == origen_id
            else lote
            for lote in entradas
        ],
        salidas,
    )["sin_lote"]
    return de_ahora, con_el_nuevo


def documentos_que_no_entran(consumos: list[dict], nueva_cantidad: float) -> list[dict]:
    """Los consumos CONGELADOS que ya no caben en el lote, del más nuevo para atrás.

    `consumos`: [{"bultos", ...}] de la más vieja a la más nueva. Se acumula
    desde la más vieja porque es el orden en que el lote se fue gastando: las
    que entran en el número nuevo quedan bien, y las que se pasan son las que
    van a quedar diciendo algo que ya no se puede reconstruir.

    Nombrarlas de a una, y no decir "algunas", es la diferencia entre poder
    resolverlo y quedarse mirando el cartel: lo que hay que hacer es anular
    ESAS guías y volver a cargarlas.

    Solo mira los documentos congelados. Los renglones armados no entran acá
    a propósito: su reparto se recalcula, así que ceden solos y no hay nada
    que ir a corregir a mano.
    """
    acumulado = 0.0
    no_entran = []
    for consumo in consumos:
        acumulado = round(acumulado + float(consumo["bultos"]), 2)
        if acumulado > float(nueva_cantidad):
            no_entran.append(consumo)
    return no_entran
