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



# `magnitudes_por_cajon` y `segunda_magnitud_por_cajon` VIVIERON ACA hasta el
# 20/09, y se fueron porque dejo de haber algo que derivar: `compras` guarda
# `segunda_por_cajon` tal como la tipeo el comprador, con su columna, igual
# que `contenido_por_cajon`. Multiplicar por los cajones para guardar el
# total y dividir de vuelta para mostrarlo era la unica manera de leer una
# magnitud que no tenia donde guardarse.
#
# Se BORRARON en vez de quedarse por si acaso: una funcion sin llamadores es
# un documento ejecutable, y el proximo que la lea va a creer que la lectura
# todavia pasa por aca. Su test —el de la vuelta completa— se fue con ellas:
# la vuelta ya no ocurre en ningun lado.
#
# Lo que SI queda es `repartir_magnitudes`, que es de la ESCRITURA y no de la
# lectura: los dos TOTALES se siguen guardando, y decidir en cual de las dos
# columnas cae cada uno sigue siendo la misma regla para la carga y para la
# recepcion.
