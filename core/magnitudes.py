"""Las DOS magnitudes de una compra, y el único lugar donde se reparten.

EL MODELO: una compra declara KILOS —siempre— y, cuando el artículo tiene
`unidad_conteo`, también un CONTEO (unidades o cubetas). La misma caja de
mango se carga UNA vez con las dos, y después cada ficha costea contra la
que su cliente compra (ver app.costeo.magnitud_de_la_ficha).

NO HAY CONVERSIÓN ENTRE LAS DOS Y NO LA VA A HABER. Un kilaje por unidad
nunca es exacto —un mango pesa lo que pesa—, así que un factor sería un
promedio disfrazado de dato, y los números con coma que deja no cierran
después contra nada. Por eso las dos se DECLARAN al comprar.

POR QUÉ ESTE MÓDULO EXISTE, que es lo único que hay que entender: el
reparto entre `cantidad_kilos` y `cantidad_fraccion` hace falta en DOS
momentos —cuando el comprador carga la compra (app/main.py) y cuando
Depósito la recepciona con lo que pesó y contó (app/db.py)—. Escrito dos
veces son dos reglas: se separan sin que nadie lo note, y el día que se
separan una compra queda con los kilos en la columna del conteo y ninguna
cuenta se descuadra. Acá está escrito UNA vez y los dos lo llaman.
"""


def repartir_magnitudes(
    unidad_compra: str | None, principal: float | None, segunda: float | None
) -> tuple[float | None, float | None]:
    """(kilos, fraccion) a partir de la magnitud PRINCIPAL y la SEGUNDA de una compra.

    La principal es la que viaja en `contenido_por_cajon`, que sigue
    expresado en `unidad_compra` — es lo único que esa columna deprecada
    todavía dice. La segunda es la otra: los kilos si la compra se cuenta,
    el conteo si se compra por kilo.

    `segunda` en None NO es un cero: es "esta compra no declaró la otra
    magnitud". Es el estado de todas las compras anteriores a este modelo, y
    no se puede deducir — quien costea las deja afuera y las cuenta.
    """
    if unidad_compra == "kilo":
        return principal, segunda
    return segunda, principal



def magnitudes_por_cajon(
    cantidad_kilos: float | None,
    cantidad_fraccion: float | None,
    cantidad_cajones: float | None,
) -> tuple[float | None, float | None]:
    """(kilos_por_cajon, conteo_por_cajon) de una compra ya guardada.

    EXISTE PORQUE LA SEGUNDA MAGNITUD NO TIENE COLUMNA POR CAJÓN: `compras`
    guarda `contenido_por_cajon` —una sola, en `unidad_compra`— y los dos
    TOTALES. Así que las de por cajón son un derivado: `total / cajones`.

    Y NO RECIBE `unidad_compra` a propósito, aunque el reparto de la entrada
    sí lo necesite: las dos columnas ya vienen NOMBRADAS por su magnitud, así
    que para sacarlas no hay nada que repartir. El `if` hace falta solo para
    contestar "¿cuál es la SEGUNDA?", que es otra pregunta y está abajo.

    NINGUNO DE LOS DOS SE DEDUCE: con una de las dos en None devuelve None en
    ese lugar, y eso NO es un cero — es "esta compra no declaró esa
    magnitud", el estado de todas las anteriores al 15/09. La pantalla lo
    muestra como hueco y no lo calla: es lo que explica por qué esa compra no
    va a poder costear en la otra unidad.

    `cantidad_cajones` en cero o None devuelve (None, None): dividir por cero
    no es un dato que falte, pero el resultado tampoco existe.
    """
    if not cantidad_cajones:
        return None, None

    def por_cajon(total: float | None) -> float | None:
        return None if total is None else total / cantidad_cajones

    return por_cajon(cantidad_kilos), por_cajon(cantidad_fraccion)


def segunda_magnitud_por_cajon(
    unidad_compra: str | None, kilos_por_cajon: float | None, conteo_por_cajon: float | None
) -> float | None:
    """La magnitud que NO viaja en `contenido_por_cajon`, por cajón. La INVERSA del reparto.

    Es lo que pide el formulario de Recepción: `contenido_por_cajon` ya
    muestra una, y el campo de al lado pide la otra.

    ESTUVO ESCRITA DOS VECES EN JINJA, en dos bloques de
    `deposito_recepcion.html` separados por 134 líneas, y ninguna de las tres
    copias nombraba a las otras. Con seis pantallas más por mostrar las dos
    magnitudes, eso pasaba de dos copias a ocho.

    Que sea la inversa de `repartir_magnitudes` no se afirma acá: lo exige
    `test_magnitudes_por_cajon_es_la_INVERSA_de_repartir_magnitudes`, que le
    da la vuelta completa a la matriz. Un comentario que dice "esto es la
    inversa" envejece; una vuelta que tiene que cerrar, no.
    """
    return conteo_por_cajon if unidad_compra == "kilo" else kilos_por_cajon
