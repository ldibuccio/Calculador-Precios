"""La aritmética de "Qué comprar hoy": cuánto falta y cuántos cajones son.

TODO EN LA MAGNITUD DE LA FILA, y una sola división al final. Cada artículo
tiene su fila y su magnitud —la de `fichas_logistica.unidad_venta`— así que
un artículo que se vende por unidad tiene su fila entera en unidades: el
promedio, el piso, lo comprado y el kilaje del cajón. Nadie suma Mango con
Cherry; lo único que se suma es el MISMO artículo entre clientes distintos.

Medido antes de escribir esto (`listado_1b`, las dos bases, 21/09):
`ARTICULOS_MIXTOS_TODOS 0` — ningún artículo tiene fichas que no se pongan
de acuerdo entre sí, así que ninguna fila mezcla dos magnitudes. El día que
aparezca uno, esa fila se parte en una línea por magnitud, que es lo que ya
hace Armar Remito: `kilos_enviados` guarda la magnitud de la ficha y esa
pantalla parte el total en vez de sumar las tres.
"""
import math

# CUÁNTOS PEDIDOS ENTRAN AL PROMEDIO, y el divisor es ÉSE y no los días en
# que el artículo apareció. Es decisión del dueño (21/09): "salgo a comprar
# para un día cualquiera, no para el día en que ese artículo aparece — si
# Día pidió tomate en 2 de 6 pedidos, comprar el promedio de esos 2 me deja
# con tomate los otros 4 días".
#
# La diferencia no es de precisión: es de hasta 3x. Con `/6` el número
# contesta "cuánto sale un día cualquiera" y con `/2` contestaría "cuánto
# pide cuando pide", que es otra pregunta.
PEDIDOS_DEL_PROMEDIO = 6

# EL MARGEN QUE LA PANTALLA PROPONE, en por ciento, para una CARGA NUEVA. Es
# un valor de arranque de la PANTALLA y no un default de la base: la columna
# guarda lo que el comprador dejó puesto, y 0 ahí significa "sin margen". Dos
# defaults que no coinciden es como se separan dos reglas, así que el número
# vive una vez acá. El listado NO tiene margen propio desde el 23/09: dos
# márgenes que se multiplican son invisibles (20% y 10% son 32%).
MARGEN_SUGERIDO = 10


def promedio_de_un_dia(total_pedido, pedidos=PEDIDOS_DEL_PROMEDIO):
    """Lo que ese artículo sale un día cualquiera, en la magnitud de la ficha.

    `total_pedido` es la suma sobre los últimos `pedidos` pedidos VIGENTES
    del cliente — vigentes y no "no anulados": un pedido recargado no se
    anula, deja de ser el vigente, y contar los dos cuenta la demanda dos
    veces.

    None entra y sale: un renglón que no se puede pasar a la magnitud de la
    fila —sin ficha, o con la ficha sin `contenido_caja`— deja la fila sin
    número, y un hueco visible es información. Un cero ahí diría que ese
    cliente no pide nada.
    """
    if total_pedido is None:
        return None
    if pedidos <= 0:
        raise ValueError("el promedio no se puede sacar sobre cero pedidos")
    return float(total_pedido) / pedidos


def con_margen(pide, margen_porcentaje):
    """Lo que se compra de más para no quedarse corto, sobre LO QUE PIDEN.

    Del dueño (21/09): "nunca vendo exacto lo que pedí, y prefiero volver
    con un cajón de más que quedarme sin".

    VA SOBRE EL PEDIDO Y NO SOBRE EL FALTANTE, y la diferencia es grande.
    Con 1000 pedidos, 900 en el piso y 10%:

        sobre el pedido    1100 − 900 = 200   <- lo que va
        sobre el faltante  (1000 − 900) × 1,1 = 110

    El margen existe porque LO QUE SE VA A VENDER es incierto; el piso no
    —está contado—. Aplicarlo al faltante infla también lo que ya se tiene,
    que es cubrir dos veces la parte que no hacía falta cubrir.
    """
    if pide is None:
        return None
    if margen_porcentaje is None:
        return float(pide)
    return float(pide) * (1.0 + float(margen_porcentaje) / 100.0)


def lo_que_pide_la_carga(guardado, propuesto, margen_porcentaje):
    """{articulo_id: total} — lo que UNA carga pide, tal como la pantalla de la carga lo mostró.

    ES LA REGLA DE LAS DOS PANTALLAS, escrita una vez: la carga la dibuja
    con esto y el listado la suma con esto. Escrita en cada una serían dos
    reglas, y la copia que se separe no falla — el listado compra otra cosa
    que la que el comprador vio en la carga, y los dos números son
    plausibles.

    EL MARGEN VA SOLO SOBRE LO PROPUESTO (dueño, 23/09). Lo guardado —lo
    corregido en "del promedio" y todo lo de "a mano"— es el número que el
    comprador ya decidió comprar, y entra tal cual. Inflarlo de nuevo sería
    cobrarle el margen dos veces a lo corregido: el campo se corrige mirando
    la propuesta que YA tiene el margen puesto.

    `propuesto` es el promedio CRUDO, sin margen, y viene vacío en "a mano":
    el modo lo decide quien llama, porque es quien sabe si hay que calcular
    el promedio.
    """
    pide = {a: con_margen(total, margen_porcentaje) for a, total in (propuesto or {}).items()}
    pide.update(guardado or {})
    return pide


def falta_por_comprar(pide, en_piso, comprado_hoy):
    """Lo que todavía falta comprar, en la MAGNITUD de la fila. Nunca negativo.

    LA RESTA VA EN LA MAGNITUD Y NO EN CAJONES, y es decisión del dueño
    (21/09): "restar cajones supone que todos miden lo mismo, que es justo
    lo que el kilaje editable existe para negar". Si compró 40 cajones de 16
    y la fila dice 18, esos 40 no son 40 — en kilos se corrige solo.

    EL PISO EN CERO ES POR FILA, nunca sobre una suma: un artículo que sobra
    no puede tapar el faltante de otro. Y "compré de más" se muestra como OK
    y no como un negativo, que es lo que el dueño pidió.

    Cualquiera de los tres en None deja la fila sin número: si no se sabe
    cuánto hay en el piso, no se sabe cuánto falta. Devolver el pedido
    entero sería comprar de más con cara de cuenta cerrada.
    """
    if pide is None or en_piso is None or comprado_hoy is None:
        return None
    return max(float(pide) - float(en_piso) - float(comprado_hoy), 0.0)


def cajones_que_faltan(falta, kilaje_del_cajon):
    """La ÚNICA división de toda la cuenta, y va al final.

    `kilaje_del_cajon` es lo que trae un cajón EN EL MERCADO, en la magnitud
    de la fila, y es lo que el comprador edita parado ahí. Sin él no hay
    cajones que decir: un artículo multiformato —el mango viene en 40, 12 y
    10— no tiene valor dominante, así que el campo va vacío y pregunta en
    vez de proponer un número que va a estar mal casi siempre.
    """
    if falta is None or kilaje_del_cajon is None:
        return None
    if float(kilaje_del_cajon) <= 0:
        return None
    # PARA ARRIBA, SIEMPRE, y es decisión del dueño (21/09): "quedarse corto
    # es peor que sobrar un cajón". Redondeando, 1120 kg contra cajones de 18
    # dan 62 — que son 1116, cuatro kilos cortos. Con techo son 63.
    #
    # No se puede comprar medio cajón, así que el resultado es un ENTERO y no
    # un float con coma que la pantalla después recorte: un número que se
    # redondea al mostrarlo es dos reglas, y la que se vea no siempre es la
    # que se calculó.
    return math.ceil(float(falta) / float(kilaje_del_cajon))


def margen_valido(texto):
    """El margen que llega de la URL, en por ciento.

    CERO NO ES VACÍO, y por eso no alcanza un `or MARGEN_SUGERIDO`: el que
    escribe 0 está diciendo "sin margen", y reemplazárselo por 10 le haría
    comprar de más sin que nada se lo diga.

    Lo que no se puede leer como un porcentaje —vacío, basura, un negativo—
    vuelve al sugerido. Un negativo sería comprar MENOS de lo que piden, que
    no es lo que este campo significa.
    """
    if texto is None:
        return MARGEN_SUGERIDO
    texto = str(texto).strip().replace(",", ".")
    if not texto:
        return MARGEN_SUGERIDO
    try:
        margen = float(texto)
    except ValueError:
        return MARGEN_SUGERIDO
    if margen < 0:
        return MARGEN_SUGERIDO
    return margen
