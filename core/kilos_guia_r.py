"""LOS KILOS NO DAN (dueño, 13/10): la cuenta de kilos de una guía R al cargarla.

Entraron: cada cajón tomado pesa lo que pesó un cajón de SU compra al
recibirla (`compras.contenido_por_cajon_real`, siempre peso neto).
Salieron: las cajas de primera por los kilos de la ficha, más los cajones de
segunda y de merma por el peso promedio del cajón que entró a la guía (son
cajones de origen, la misma cuenta de "Cómo rindió").

Si la diferencia pasa 0,8 kg por cajón tomado, para arriba o para abajo,
la pantalla muestra el cartel rojo. No frena: el operario puede revisar o
guardar igual, y si guarda igual la guía anota la diferencia.

No hay cuenta (devuelve None) cuando no se puede saber cuánto pesó algo: la
ficha no vende por kilo (Mango, por unidad), la guía no tiene ficha, o algún
cajón tomado no salió de una compra pesada en kilos.
"""

import math

# 0,8 kg por cajón tomado (dueño, 13/10: primero dijo medio kilo y lo
# subió a 0,8 el mismo día, con la R788 que no tenía que saltar).
TOLERANCIA_KG_POR_CAJON = 0.8


def kg_entero(kilos: float) -> int:
    """Kilos sin decimales, como se leen parado en el galpón. Medio para
    arriba: el `round` de Python redondea 286,5 a 286."""
    return math.floor(kilos + 0.5)


def cuenta_de_kilos(consumos: list[tuple], primera, segunda, merma, kg_caja_ficha) -> dict | None:
    """La cuenta de una guía R. `consumos` = [(bultos, kg pesados por cajón o None)].

    Devuelve {"entraron", "tomados", "salieron", "diferencia", "tolerancia",
    "no_dan", "kg_entraron", "kg_salieron", "kg_diferencia"}: `diferencia` =
    entraron − salieron (positiva = faltan, negativa = sobran). Las `kg_` son
    las del cartel, en kilos enteros, y la diferencia del cartel es la resta de
    los dos enteros que muestra: es la que queda anotada si guardan igual, así
    el cartel y la guía dicen el mismo número. None si no hay cuenta posible.
    """
    if kg_caja_ficha is None or float(kg_caja_ficha) <= 0 or not consumos:
        return None
    if any(kg is None or float(kg) <= 0 for _, kg in consumos):
        return None
    tomados = sum(float(b) for b, _ in consumos)
    if tomados <= 0:
        return None
    entraron = sum(float(b) * float(kg) for b, kg in consumos)
    kg_por_cajon = entraron / tomados
    salieron = (float(primera) * float(kg_caja_ficha)
                + (float(segunda) + float(merma)) * kg_por_cajon)
    diferencia = entraron - salieron
    tolerancia = TOLERANCIA_KG_POR_CAJON * tomados
    return {
        "entraron": round(entraron, 2),
        "tomados": tomados,
        "salieron": round(salieron, 2),
        "diferencia": round(diferencia, 2),
        "tolerancia": round(tolerancia, 2),
        "no_dan": round(abs(diferencia), 2) > round(tolerancia, 2),
        "kg_entraron": kg_entero(entraron),
        "kg_salieron": kg_entero(salieron),
        "kg_diferencia": kg_entero(entraron) - kg_entero(salieron),
    }
