"""El detector de quiebre: que detecte, y que NO marque lo que está bien.

SE PRUEBA PLANTANDO EL CASO, que es lo único que hace leíble a un cero
(corolario 36): una lista de `quebradas` vacía sobre un HTML que no tiene
ninguna celda envuelta no demuestra que el detector vea algo — lo mismo
devolvería uno con el `>` al revés.

Y SE PARTE EN DOS A PROPÓSITO. `playwright` no es dependencia de este
proyecto —no está en requirements.txt y el deploy no lo necesita— así que la
mitad que abre un navegador se saltea donde no está. La otra mitad, la que
fija la REGLA, corre siempre: es la que impide que alguien cambie el
line-height real por un número escrito a mano y el detector deje de detectar
sin que nada avise.
"""

import asyncio

import pytest

from scripts.medir_layout import _MEDICION, TOLERANCIA_LINEA, medir


# --- La mitad que corre SIEMPRE -------------------------------------------


def test_el_quiebre_se_mide_contra_el_LINE_HEIGHT_REAL_de_cada_celda():
    """Un umbral fijo mediría la tipografía en vez del quiebre.

    Cada pantalla tiene su cuerpo y su interlineado: 20px es una línea en un
    lado y dos en otro. Por el TEXTO del JS y no por el resultado, que es lo
    que hace un mock de navegador (corolario 40): con un número escrito a
    mano el detector seguiría devolviendo listas, solo que mal.
    """
    assert 'getComputedStyle(celda).lineHeight' in _MEDICION
    assert "linea * opciones.tolerancia" in _MEDICION
    # La tolerancia existe para que el padding no cuente como quiebre, y no
    # puede ser 1.0: con eso TODA celda daría quebrada y el detector no
    # distinguiría nada — sería un número que no puede dar distinto.
    assert 1.2 <= TOLERANCIA_LINEA <= 2.0


def test_lo_que_se_despliega_NO_cuenta_como_quebrado():
    """Un menú abierto es alto a propósito: marcarlo sería ruido en cada fila."""
    assert 'celda.querySelector("details, ul, ol, table")' in _MEDICION


def test_la_medicion_devuelve_los_TRES_numeros_juntos():
    """El alto solo nunca alcanzó: esa es la regla que este módulo existe para
    imponer. Si alguna vez devuelve solo el alto, se puede volver a decidir un
    rediseño con un número que mejora mientras la pantalla empeora.
    """
    for clave in ("alto_fila", "quebradas", "desborde"):
        assert clave in _MEDICION, clave


# --- La mitad que necesita navegador ---------------------------------------

def _medir(html, **opciones):
    pytest.importorskip("playwright", reason="la medición de layout necesita un navegador")
    return asyncio.run(medir(html, **opciones))


# EL CASO PLANTADO: texto largo de palabras normales, que envuelve seguro a
# 390px. La primera versión de este fixture usaba una palabra de 60 X y NO
# funcionaba: una palabra que no se puede partir no envuelve, se DESBORDA —
# la celda queda de una línea y se sale por el costado. Son dos fallas
# distintas y las agarra un número distinto cada una, que es justamente por
# qué el módulo devuelve los dos juntos (ver el test de abajo).
_ANCHA = "palabra larga que ocupa lugar " * 6
_IMPARTIBLE = "X" * 60
# Con `replace` y no con `.format`: el CSS tiene llaves y `format` las lee
# como marcadores — falla con un KeyError que no dice una palabra de esto.
_PAGINA = """
<style>
  body { margin: 0; font: 16px/20px sans-serif; }
  table, tbody, tr, td { display: block; }
  tr { padding: 8px 0; }
  td { padding: 0; }
</style>
<table><tbody>
  <tr><td>PRIMERA_CELDA</td><td>corta</td></tr>
  <tr><td>tambien corta</td><td>corta</td></tr>
</tbody></table>
"""


def test_con_una_celda_QUE_ENVUELVE_la_detecta_y_la_nombra():
    medicion = _medir(_PAGINA.replace("PRIMERA_CELDA", _ANCHA), ancho=390)

    assert medicion["quebradas"], "el detector no vio una celda que envuelve seguro"
    # Y la NOMBRA, con el texto de la celda: una lista de "hay 3 quebradas"
    # obliga a ir a buscar cuáles, y ahí nadie va (corolario 19).
    assert medicion["quebradas"][0].startswith("palabra larga")


def test_con_TODO_en_una_linea_la_lista_viene_VACIA():
    """La otra mitad, y es la que hace que la primera signifique algo.

    Un detector que marcara todo también pasaría el test de arriba: los dos
    casos juntos son los que lo separan de uno roto.
    """
    medicion = _medir(_PAGINA.replace("PRIMERA_CELDA", "corta"), ancho=390)

    assert medicion["quebradas"] == []
    assert medicion["filas"] == 2


def test_la_celda_que_envuelve_SUBE_el_alto_de_la_fila():
    """El caso completo del 12/09 al revés: acá el alto sube con el quiebre.

    Lo que mordió fue que BAJARA mientras el texto se rompía —por un cambio
    de grilla que apretaba la celda— y por eso el alto solo no alcanza. Este
    test fija que los dos números salen de la misma medición y se pueden
    comparar entre sí.
    """
    con_quiebre = _medir(_PAGINA.replace("PRIMERA_CELDA", _ANCHA), ancho=390)
    sin_quiebre = _medir(_PAGINA.replace("PRIMERA_CELDA", "corta"), ancho=390)

    assert con_quiebre["alto_fila"] > sin_quiebre["alto_fila"]


def test_una_palabra_IMPARTIBLE_sale_por_DESBORDE_y_no_por_quiebre():
    """Las dos fallas son distintas y las agarra un número distinto.

    Una palabra que no se puede partir no envuelve: la celda queda de una
    línea y se sale por el costado. Un detector de quiebre solo la daría por
    buena, y por eso `desborde` viaja en la misma medición — juntos cubren
    las dos formas en que un texto no entra.

    Lo encontró el fixture de arriba, que estaba escrito así y no detectaba
    nada: el caso plantado tenía que plantarse bien.
    """
    medicion = _medir(_PAGINA.replace("PRIMERA_CELDA", _IMPARTIBLE), ancho=390)

    assert medicion["quebradas"] == []
    assert medicion["desborde"] > 0


def test_sin_filas_NO_explota_y_lo_dice():
    """Un selector equivocado tiene que verse como tal.

    Devolver ceros prolijos sería el cero que tranquiliza: quien lo lea va a
    creer que la pantalla mide cero, no que midió la nada.
    """
    medicion = _medir("<p>sin tabla</p>", ancho=390)

    assert medicion["filas"] == 0
    assert medicion["alto_fila"] is None
    assert medicion["quebradas"] == []
