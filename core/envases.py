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

EL MODELO ENTERO, en tres renglones (del dueño, 17/09), y es más simple que
lo que estuvo construido dos días:

    1. La caja de Día NO VUELVE NUNCA al stock. Por ninguna puerta.
    2. El stock solo SUBE por COMPRA — y por la guía R `en_origen`, que es
       una caja nuestra que vuelve llena de afuera. **Y desde el 17/09,
       por la cuenta con un COLEGA**: una caja que me presta entra al piso,
       y una que le devuelvo sale. Eso no le agrega ninguna pata al stock
       —`cantidad` ya significa el efecto sobre el piso— pero la frase "solo
       compra y en_origen" dejó de ser cierta y acá se corrige.
    3. Toda caja que se llena está PERDIDA, salvo la que vuelve rechazada y
       se remanda; y ésa ya estaba descontada, así que no se cuenta dos
       veces.

LAS CUATRO PUERTAS DEL RECHAZO, contra ese modelo. Las cuatro salen del
mismo lugar —una caja que ya se descontó cuando la guía R la armó— y
ninguna le devuelve nada al stock:

    segunda              se remite al Puesto en la caja en que volvió
    devolucion_proveedor se va con la mercadería que se devuelve
    reproceso            la fruta pasa a cajón grande y la caja SE TIRA
    stock                vuelve llena, se rearma y sale de nuevo: LA MISMA
                         caja, descontada una sola vez

Y POR ESO NO HAY NINGUNA REGLA QUE ESCRIBIR, que es el punto: las tres
primeras ya están restadas y no vuelven; la cuarta está restada una vez y
se reusa sin pasar por una guía R nueva, porque `reproceso_toma` tiene
PROHIBIDOS los lotes trabajados (core/stock.py). El neutro no es una
convención entre dos lugares: es una pared que el FIFO no puede cruzar.

La 'reproceso' llegó a tener columna propia —`movimientos_stock.envase_id`
con su `lleva_caja_nuestra`— y una pata `liberadas` que se la sumaba al
stock, sobre la premisa de que esa caja quedaba libre. Es falsa: se tira. Se
sacaron las dos el 17/09 (db/envases_9_*.sql). Un camino que nunca se va a
recorrer es peor que no tenerlo — el próximo que lo lea va a creer que falta
cablearlo.
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

    LA CAJA SALE SIEMPRE DE LA FICHA. No se puede armar en otra: la ficha ES
    el acuerdo con el cliente ("Día compra mango en Caja Chica de 10 u"), así
    que preguntarla de nuevo abajo es preguntar dos veces lo mismo — y encima
    deja elegir una distinta de la que la ficha declara.

        ficha con envase       -> (True, su envase, False)
        ficha SIN envase       -> (False, None, False)  envase perdido
        SIN FICHA (sin asignar)-> (None, None, True)    no hay de dónde sacarlo

    `envase_variable` NO ENTRA ACÁ, y eso es una corrección del 18/09. Ese
    flag decide SI se usa una caja nuestra, no CUÁL — lo dice la única cuenta
    que lo lee, `envases_por_unidad_de_venta`, unas líneas más abajo: para el
    caso variable devuelve 0 (el cajón ya es chico, sale como vino) o
    `1/contenido_ficha`, que es LA CAJA DE LA FICHA a la tasa de la ficha.
    No hay ninguna rama que busque otro envase.

    Y en una guía R ese "si" ya está contestado por el hecho de que la guía
    exista: una guía R anota `bultos_primera`, o sea cajas ARMADAS. El caso
    descartable es exactamente aquel en que no se reprocesa nada y no hay
    guía R. Así que en este camino el flag no tiene nada que aportar.

    LA ÚNICA QUE SIGUE PREGUNTANDO ES LA GUÍA SIN FICHA, y su arreglo no es
    un selector de cajas: es ASIGNARLE LA FICHA, que ya existe en Guías R y
    vuelve a derivar. Un selector de cajas ahí dejaría elegir una que no es
    la del cliente al que se le entregó.

    LO ESCRIBE SIEMPRE EL SERVER y queda GUARDADO, no derivado en cada
    lectura: leerlo de la ficha de HOY haría que cambiarle el envase a una
    ficha re-etiquete la historia en silencio — lo mismo que nos negamos a
    hacer con `unidad_compra`.
    """
    if ficha is None:
        return None, None, True
    if ficha.get("envase_id") is None:
        return False, None, False
    return True, ficha["envase_id"], False


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


# ---------------------------------------------------------------------------
# LA CUENTA CORRIENTE CON UN COLEGA
# ---------------------------------------------------------------------------
#
# Se prestan cajas entre colegas, y son CAJAS NUESTRAS: las mismas del
# catálogo. El préstamo funciona justamente porque los dos usan el mismo tipo
# de caja — con cajas suyas no habría intercambio posible.
#
# NO ES EL PRÉSTAMO AL PUESTO, y por eso los orígenes se llaman distinto: al
# puesto la caja vuelve SOLA con la guía R `en_origen` (llega la compra ya
# armada en caja nuestra) y no hay ninguna cuenta que llevar. Con un colega
# la vuelta la declara una persona, y queda un saldo.
#
# LOS DOS ROTULOS Y EL SIGNO VIAJAN JUNTOS a propósito: repartidos en tres
# mapas, el día que se agregue un origen alguno se va a olvidar y los otros
# van a seguir contestando. `piso` es EL EFECTO SOBRE EL PISO.
#
# SON DOS ROTULOS Y NO UNO PORQUE SE LEEN EN DOS LUGARES: en el `<select>` no
# hay ningún colega a la vista todavía, así que la opción tiene que decir "a
# un colega"; adentro de la cuenta de Fulano, repetirlo sería ruido en cada
# renglón. Es la misma distinción del corolario 56 —lo que describe la COSA
# contra lo que describe el CAMINO— y por eso los dos están acá y no uno acá
# y otro en la plantilla.
ORIGENES_DE_COLEGA = {
    "colega_le_presto":   {"corto": "Le presté",
                           "largo": "Le presté cajas a un colega", "piso": -1},
    "colega_me_devuelve": {"corto": "Me devolvió",
                           "largo": "Un colega me devolvió cajas", "piso": +1},
    "colega_me_presta":   {"corto": "Me prestó",
                           "largo": "Un colega me prestó cajas", "piso": +1},
    "colega_le_devuelvo": {"corto": "Le devolví",
                           "largo": "Le devolví cajas a un colega", "piso": -1},
}


def efecto_en_la_cuenta(cantidad) -> int:
    """Cuánto mueve este movimiento la cuenta con el colega. + me debe / - le debo.

    ES `-cantidad`, Y NO HAY MAPA DE SIGNOS POR ORIGEN. Verificado en los
    cuatro, que son todos los que hay:

        le presto 50    piso -50  ->  me debe +50   = -(-50)
        me devuelve 30  piso +30  ->  me debe -30   = -(+30)
        me presta 50    piso +50  ->  le debo +50, o sea neto -50 = -(+50)
        le devuelvo 30  piso -30  ->  le debo -30, o sea neto +30 = -(-30)

    No es una casualidad de los cuatro casos: `cantidad` significa EL EFECTO
    SOBRE EL PISO, y toda caja que sale hacia un colega sube lo que me debe o
    baja lo que le debo, mientras que toda caja que entra hace lo contrario.

    Y de ahí sale lo que más protege a esta cuenta: NO LEE EL ORIGEN, así que
    no se puede separar de la lista de orígenes. Un mapa de signos por origen
    sería una segunda copia de `ORIGENES_DE_COLEGA` esperando a que alguien
    agregue un quinto y actualice uno solo de los dos.

    LOS CUATRO ORIGENES EXISTEN IGUAL y no son decoración: con uno solo y el
    signo suelto, "le presté 50" y "le devolví 50" son los dos -50 y el
    DETALLE no los distingue. El neto saldría bien y la cuenta no se podría
    leer, que es justamente lo que se entra a mirar.
    """
    return -int(cantidad)


def como_queda_la_cuenta(neto) -> tuple[str, int]:
    """Cómo se lee un neto: ("me debe" | "le debo" | "en cero", cuántas cajas).

    DEVUELVE EL NUMERO SIN SIGNO junto con de qué lado está, porque eso es lo
    que se lee en el galpón: "Fulano me debe 20" y no "Fulano: +20". El signo
    obliga a acordarse de una convención, y el que mira la pantalla no tiene
    por qué.

    EL CERO ES SU PROPIO CASO y no cae en ninguno de los otros dos: "me debe
    0" y "le debo 0" son las dos formas de decir que están a mano, y las dos
    se leen como si hubiera algo pendiente.
    """
    valor = int(neto)
    if valor > 0:
        return ("me debe", valor)
    if valor < 0:
        return ("le debo", -valor)
    return ("en cero", 0)


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


def cuenta_por_tipo_de_caja(cuentas: list[dict]) -> dict:
    """Por TIPO de caja: cuántas me deben y cuántas debo, sumadas entre colegas.

    Devuelve {envase_id: {"me_deben": n, "debo": m}}, las dos sin signo, que es
    como se leen en el galpón.

    NO SE NETEA ENTRE COLEGAS, y es la misma razón por la que
    `cuentas_de_colegas` no netea entre tipos: si Juan me debe 20 Chicas y yo
    le debo 15 a Pedro, "me deben 5" es falso — no puedo pagarle a Pedro con
    las cajas que tiene Juan hasta que Juan las traiga. Son dos pendientes
    distintos y los dos tienen que verse, porque los dos hay que ir a buscarlos
    a lugares distintos.

    LEE EL `lado` QUE YA CALCULÓ `como_queda_la_cuenta` en vez de mirar el
    signo del neto. El signo está escrito en UN solo lugar (`efecto_en_la_
    cuenta`, que es `-cantidad` y no un mapa por origen); preguntar acá por
    `neto > 0` sería la segunda copia de esa convención, y la que se separe no
    va a fallar: va a mostrar "me deben" donde dice "le debo".

    Y EL CERO NO SUMA A NINGUNO DE LOS DOS: "en cero" es su propio caso, así
    que una cuenta saldada no infla ni la columna de lo que me deben ni la de
    lo que debo.
    """
    por_tipo: dict = {}
    for cuenta in cuentas:
        for renglon in cuenta.get("por_envase", ()):
            destino = por_tipo.setdefault(renglon["envase_id"], {"me_deben": 0, "debo": 0})
            if renglon["lado"] == "me debe":
                destino["me_deben"] += renglon["cuantas"]
            elif renglon["lado"] == "le debo":
                destino["debo"] += renglon["cuantas"]
    return por_tipo


def en_pallets(cajas, cajas_por_pallet):
    """(pallets enteros, cajas sueltas) de un stock, o None si no se puede decir.

    Del dueño (23/09): el stock se lee como pallets más cajas sueltas. Sin el
    número de cajas por pallet no hay nada que decir, y un stock NEGATIVO
    tampoco se parte — "−2 pallets y 40 sueltas" no describe ningún piso; el
    faltante se lee en cajas.
    """
    if cajas is None or not cajas_por_pallet or cajas_por_pallet <= 0:
        return None
    cajas = int(cajas)
    if cajas < 0:
        return None
    return divmod(cajas, int(cajas_por_pallet))

