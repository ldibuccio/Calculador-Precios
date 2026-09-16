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
#
# Y EL SIGNO MULTIPLICA SOLO A LA PRIMERA (ver `cajas_que_mueve_la_guia`):
# la segunda de un reproceso queda en el envase del proveedor y no lleva caja
# nuestra. La que sí la lleva es la del RECHAZO, que vuelve del súper en la
# caja en la que salió — y ésa ya está descontada desde la guía R que la armó,
# así que sumarla acá la contaría dos veces.
SIGNO_POR_TIPO_DE_GUIA = {
    "normal": -1,      # se llenó en la mesa: la caja vacía dejó de estar
    "en_origen": +1,   # llegó llena de afuera: es una prestada que vuelve
    "inicial": 0,      # ya estaba armada el día del corte
}


def cajas_que_mueve_la_guia(tipo: str, bultos_primera, lleva_caja_nuestra) -> float:
    """Cuántas cajas suma (+) o resta (−) esta guía R. Cero si no lleva caja nuestra.

    SOLO LA PRIMERA, y la segunda NO ENTRA POR CONSTRUCCIÓN: no recibe el
    parámetro. Al reprocesar un cajón la primera va en caja de Día y la
    segunda queda en el envase del proveedor — no lleva caja nuestra, así que
    no hay nada que descontar. El día que resulte que sí, hay que cambiar la
    FIRMA, y ahí el test dice por qué no estaba.

    El 16/09 esta función recibió `bultos_segunda` durante unas horas, sobre
    una premisa del galpón que el dueño dio vuelta el mismo día. Restaba 80,97
    bultos por trimestre de un stock del que nunca salieron.

    LA SEGUNDA QUE SÍ VA EN CAJA NUESTRA ES LA DEL RECHAZO —vuelve del súper
    en la caja en la que salió— y ésa no pasa por acá: vive en
    movimientos_stock y ya quedó descontada en la guía R que la armó.

    LA MERMA TAMPOCO ENTRA, y es una decisión y no un olvido: lo que se
    descarta se tira, no se pone en una caja para tirarlo.

    `lleva_caja_nuestra` es el DATO DECLARADO de la guía, no algo que se
    deduzca acá: con None —la guía no lo declaró— devuelve 0, y eso NO es
    "no consumió". Es "no sabemos", y se cuenta aparte para que se vea como
    hueco en vez de desaparecer adentro de un total.
    """
    if lleva_caja_nuestra is not True:
        return 0.0
    return SIGNO_POR_TIPO_DE_GUIA.get(tipo, 0) * float(bultos_primera or 0)


def envase_derivado_de_la_ficha(ficha: dict | None) -> tuple[bool | None, int | None, bool]:
    """Qué caja nuestra le corresponde a esta ficha: (lleva, envase_id, hay_que_preguntar).

    LA CONTESTAN DOS OPERACIONES y por eso el nombre dice FICHA y no guía: la
    guía R, que LLENA una caja, y el reingreso que vuelve a cajón grande, que
    la VACÍA. Las dos preguntan lo mismo —¿en qué caja nuestra está esto?— y
    escrita dos veces se separan el día que alguien arregle una.

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


def hay_que_reponer(envase: dict) -> bool:
    """¿Este envase está debajo de su aviso de reposición?

    ESTÁ ACÁ Y NO EN LA PANTALLA NI EN LA ALERTA porque la contestan las dos,
    y escrita dos veces se separan: el día que una cambie, el banner y el rojo
    de la tarjeta van a decir cosas distintas del mismo envase y no va a haber
    forma de saber cuál tiene razón.

    SIN CONTEO INICIAL NO ES "HAY QUE REPONER", y es la mitad que no se ve
    sola: `stock` en None significa que la cuenta de ese envase no arrancó, no
    que no queden cajas. Tratarlo como cero lo pondría debajo de cualquier
    umbral y la alerta saltaría el primer día por todos los envases del
    catálogo — un aviso que nace disparando es un aviso que nadie va a mirar.

    Sin umbral tampoco: ese envase no se vigila, y es una decisión que se
    toma en la pantalla dejando el campo vacío.
    """
    if envase.get("stock") is None or envase.get("umbral_reposicion") is None:
        return False
    return envase["stock"] < envase["umbral_reposicion"]


def envases_por_unidad_de_venta(
    contenido_ficha: float | None,
    envase_variable: bool,
    contenido_del_bulto: float | None,
) -> float:
    """Cuántas CAJAS por unidad de venta lleva UN bulto de esta ficha.

    Devuelve CAJAS, no pesos: multiplicarla por el costo del envase es del
    llamador. Así la regla física queda de un lado y la plata del otro, y el
    día que el costo cambie de fuente esto no se entera.

    LA MISMA REGLA LA APLICAN DOS PANTALLAS y por eso vive acá: la Rutina A
    la corre una vez por compra y la pondera (`_envases_por_unidad_ponderado`),
    y el Techo de Compra la corre una vez sobre el kilaje de la última compra.
    Escrita dos veces se separan, y la que se olvide manda al comprador al
    Mercado con un techo más alto del que corresponde — sin que ninguna
    cuenta se descuadre.

    Envase FIJO: 1 caja cada `contenido_ficha` unidades, siempre (ficha de
    16 kg por Caja Grande => 1/16 cajas por kilo).

    Envase VARIABLE (mango/cherry): si ESE bulto trae menos o igual que el
    contenido de la ficha, sale descartable y no lleva caja; si trae más, es
    caja chica a la misma razón. El número de corte y el "cada cuánto" salen
    los dos de la ficha, nunca hardcodeados.

    `contenido_del_bulto` en None = no hay bulto contra el cual decidir, así
    que NO SE APLICA EL CORTE. Es el caso del renglón del Techo de Compra que
    viaja a la pantalla: el JS decide el corte en vivo cuando el comprador
    edita el kilaje, así que necesita la tasa sin cortar y el umbral al lado.

    LAS DOS MAGNITUDES TIENEN QUE SER LA MISMA (corolario de las unidades):
    `contenido_ficha` está en unidad de VENTA, así que `contenido_del_bulto`
    también. Quién lo convierte es el llamador — acá no se puede saber.
    """
    if not contenido_ficha:
        return 0.0

    contenido_ficha = float(contenido_ficha)

    if (
        envase_variable
        and contenido_del_bulto is not None
        and float(contenido_del_bulto) <= contenido_ficha
    ):
        return 0.0

    return 1.0 / contenido_ficha
