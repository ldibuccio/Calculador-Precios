"""Las reglas del stock de CAJAS NUESTRAS, sin base de datos adentro.

Acá vive lo que decide CUÁNDO una caja deja de estar disponible y cuándo
vuelve, que es lo único de este módulo que no se puede leer de una columna.

EL ANCLA ES LA GUÍA R Y NO EL ARMADO DEL PEDIDO, y es la decisión de fondo:
la caja se llena en la mesa, no cuando el camión sale. Dos consecuencias que
no son obvias y por eso están escritas:

- Un renglón armado puede salir SIN LOTE (la pared del armado no le ofrece el
  cajón a una ficha con envase). Anclado en el armado, eso descontaría una
  caja que nadie llenó.
- Un rechazo que vuelve a stock se rearma después contra un lote
  `reingreso_rechazo`, que para el sistema ya es un lote TRABAJADO — o sea,
  mercadería que ya está en una caja. Como no se carga ninguna guía R nueva,
  el reuso queda NEUTRO POR CONSTRUCCIÓN y no hace falta escribir ninguna
  regla que lo diga. Anclado en el armado habría que acordarse de escribirla.
"""

# Los tres tipos de guía R le hacen a la caja cosas distintas, y el signo no
# se deduce del nombre: 'en_origen' es una caja que ENTRA al depósito (la
# compra llegó ya armada), así que suma donde las otras restan.
#
# 'inicial' son las cajas que ya estaban armadas el día del corte: existían
# antes de que esta cuenta empezara, así que no mueven nada. Está nombrado a
# propósito y no cae en un default — un tipo nuevo que no esté acá tiene que
# romper el test, no colarse valiendo cero.
SIGNO_POR_TIPO_DE_GUIA = {
    "normal": -1,      # se llenó en la mesa: la caja vacía dejó de estar
    "en_origen": +1,   # llegó llena de afuera: es una prestada que vuelve
    "inicial": 0,      # ya estaba armada el día del corte
}


def cajas_que_mueve_la_guia(tipo: str, bultos_primera, lleva_caja_nuestra) -> float:
    """Cuántas cajas suma (+) o resta (−) esta guía R. Cero si no lleva caja nuestra.

    `lleva_caja_nuestra` es el DATO DECLARADO de la guía, no algo que se
    deduzca acá: con None —la guía no lo declaró— devuelve 0, y eso NO es
    "no consumió". Es "no sabemos", y se cuenta aparte para que se vea como
    hueco en vez de desaparecer adentro de un total.
    """
    if lleva_caja_nuestra is not True:
        return 0.0
    return SIGNO_POR_TIPO_DE_GUIA.get(tipo, 0) * float(bultos_primera or 0)


def envase_de_la_guia(ficha: dict | None) -> tuple[bool | None, int | None, bool]:
    """Qué envase le corresponde a una guía R de esta ficha: (lleva, envase_id, hay_que_preguntar).

    LO ESCRIBE SIEMPRE EL SERVER y la pantalla solo PREGUNTA cuando no se
    puede derivar. Guardarlo únicamente en las fichas variables dejaría el
    conteo de cajas de las fijas leyéndose de la ficha de HOY, y el día que
    alguien le cambie el envase a una ficha se re-etiquetaría la historia en
    silencio — es lo mismo que nos negamos a hacer con `unidad_compra`.

    Los tres casos, y el tercero no estaba en el pedido pero sale de la misma
    regla: si no se puede derivar, se pregunta.

        ficha con envase FIJO      -> (True, su envase, False)
        ficha con envase VARIABLE  -> hay que preguntar: el envase se decide
                                      por compra y puede ser descartable
        SIN FICHA (sin asignar)    -> hay que preguntar: sin ficha no hay de
                                      dónde derivarlo

    Una ficha SIN ENVASE es envase perdido (manzana, pera, arándano): sale en
    el cajón del proveedor y no hay caja nuestra que contar. Eso NO es un
    hueco y por eso devuelve (False, None, False) y no "preguntá".
    """
    if ficha is None:
        return None, None, True
    if ficha.get("envase_id") is None:
        return False, None, False
    if ficha.get("envase_variable"):
        return None, None, True
    return True, ficha["envase_id"], False


def declarado_del_formulario(envase_id, envases_validos) -> tuple[bool | None, int | None]:
    """Traduce lo que eligió la pantalla cuando hubo que preguntar: (lleva, envase_id).

    Vacío es DESCARTABLE —"este cajón no lleva caja nuestra"—, que es una
    respuesta y no la ausencia de una: el select la ofrece con todas las
    letras. Un id que no esté en los válidos vuelve como descartable y no
    como un envase inventado; quien decide si eso alcanza es la ruta, que es
    la que puede exigir que se conteste.
    """
    if envase_id in envases_validos:
        return True, envase_id
    return False, None
