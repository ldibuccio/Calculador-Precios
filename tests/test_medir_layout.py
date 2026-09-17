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
    # Las dos mitades por separado: el 14/09 el `getComputedStyle(celda)` se
    # sacó a una variable para poder leer también el padding, y un assert
    # sobre la expresión pegada cayó por un refactor que no cambió la regla.
    assert "getComputedStyle(celda)" in _MEDICION
    assert "lineHeight" in _MEDICION
    assert "linea * opciones.tolerancia" in _MEDICION
    # Y el relleno se descuenta antes de comparar: un botón de 44px mide el
    # doble que su línea sin haber envuelto nada.
    assert "paddingTop" in _MEDICION and "paddingBottom" in _MEDICION
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


# --- La celda que no es un <td>: las pantallas de TARJETAS -----------------

_TARJETAS = """
<style>
  body { margin: 0; font: 16px/20px sans-serif; }
  .ficha { padding: 8px 0; }
  .nombre { margin: 0; font-weight: 600; }
  .vigencia { display: flex; justify-content: space-between; gap: 8px; }
  .rango { min-width: 0; }
</style>
<div class="ficha">
  <p class="nombre">PRIMERA_CELDA</p>
  <div class="vigencia"><span class="precio">$ 12.345</span><span class="rango">01/07/2026 &rarr; sigue vigente</span></div>
</div>
<div class="ficha">
  <p class="nombre">Otra</p>
  <div class="vigencia"><span class="precio">$ 900</span><span class="rango">05/09/2026 &rarr; sigue vigente</span></div>
</div>
"""


def test_en_una_pantalla_de_TARJETAS_tambien_detecta_el_quiebre():
    """Mirando solo "td, th", toda pantalla sin tabla daba `quebradas: 0` SIEMPRE.

    Es el corolario 47 adentro de la herramienta que salió del corolario 47:
    un cero que no puede dar distinto de cero. Se descubrió el 14/09 midiendo
    Precios por Período —un nombre plantado hizo subir el alto de 69,8 a
    123,8px, o sea que envolvió, y `quebradas` siguió en 0— y en este
    proyecto la mayoría de las pantallas de celular son tarjetas.
    """
    medicion = _medir(_TARJETAS.replace("PRIMERA_CELDA", _ANCHA), ancho=390, selector_filas=".ficha")

    assert medicion["quebradas"], "el detector no ve el quiebre fuera de una tabla"
    assert medicion["quebradas"][0].startswith("palabra larga")


def test_en_una_pantalla_de_TARJETAS_lo_que_entra_NO_se_marca():
    """La otra mitad: sin ésta, un detector que marcara todo pasa la de arriba."""
    medicion = _medir(_TARJETAS.replace("PRIMERA_CELDA", "Banana"), ancho=390, selector_filas=".ficha")

    assert medicion["quebradas"] == []
    assert medicion["filas"] == 2


def test_la_medicion_dice_CONTRA_CUANTAS_CELDAS_conto():
    """Sin el denominador, "quebradas: 0" no distingue ninguna envolvió de no se miró ninguna.

    Las dos se imprimen igual y significan lo contrario. Es el mismo
    denominador que condena una heurística con más hallazgos que población,
    usado acá para saber si la medición llegó a mirar algo.
    """
    tarjetas = _medir(_TARJETAS.replace("PRIMERA_CELDA", "Banana"), ancho=390, selector_filas=".ficha")
    tabla = _medir(_PAGINA.replace("PRIMERA_CELDA", "corta"), ancho=390)

    assert tarjetas["celdas"] > 0, "una pantalla de tarjetas tiene que contar celdas miradas"
    assert tabla["celdas"] == 4  # dos filas de dos <td>: las tablas se miden igual que antes


def test_una_fila_SIN_NADA_ADENTRO_cuenta_cero_celdas_y_no_finge_que_miro():
    medicion = _medir(
        '<style>.f{height:20px}</style><div class="f"></div><div class="f"></div>',
        ancho=390, selector_filas=".f",
    )

    assert medicion["filas"] == 2
    assert medicion["celdas"] == 0
    assert medicion["quebradas"] == []


def test_un_BOTON_de_44px_no_cuenta_como_quebrado():
    """El mínimo para tocar con el pulgar es regla de este proyecto, no una excepción.

    Sin descontar el relleno, toda pantalla con botones sale llena de
    quebradas que están bien — y un detector que marca lo que está bien no se
    vuelve a mirar (corolario 53). Medido el 14/09: en Precios por Período
    marcaba "Ver" y "Exportar Excel".
    """
    pagina = """
    <style>
      body { margin: 0; font: 16px/20px sans-serif; }
      .fila { padding: 0; }
      .boton { display: block; padding: 13px 0; font-size: 16px; }
    </style>
    <div class="fila"><a class="boton">Ver</a></div>
    """
    medicion = _medir(pagina, ancho=390, selector_filas=".fila")

    assert medicion["celdas"] == 1, "tiene que haber mirado el botón"
    assert medicion["quebradas"] == []


# --- SOLAPES: la tercera forma de romperse (15/09) -------------------------
#
# Ni el quiebre ni el desborde la ven: la celda mide una línea y nada se sale
# del ancho. El par va completo —el que TIENE que encontrar y el que NO— que
# es lo único que separa un detector de una herramienta que marca todo
# (corolario 53). Y el tercero es el que este proyecto ya sufrió dos veces:
# que los casos plantados se PAREZCAN a donde se va a usar. Acá eso es un
# FORMULARIO, que NO TIENE FILAS — y es justo la pantalla donde apareció.
#
# Con `replace` y no con `.format`, por lo mismo que el fixture de arriba: el
# CSS tiene llaves.
_FORMULARIO = """
<style>
  label { display: block; margin-top: 0.75rem; }
  select { width: 100%; padding: 0.65rem; margin-top: 0.25rem; box-sizing: border-box; }
  .ayuda { font-size: 0.85rem; margin: MARGEN 0 0; }
</style>
<form>
  <label for="a">Uno</label>
  <select id="a"><option>x</option></select>
  <p class="ayuda">Una ayuda que explica el campo de arriba.</p>
  <label for="b">Dos</label>
  <select id="b"><option>y</option></select>
</form>
"""
_MARGEN_QUE_PISA = "-0.4rem"
_MARGEN_BUENO = "0.35rem"


def test_una_ayuda_con_margen_NEGATIVO_pisa_el_campo_y_se_detecta():
    """El caso real del 15/09, plantado: un `-0.4rem` copiado de otra pantalla.

    En Editar artículo los campos NO llevan margen inferior —el aire lo da el
    `margin-top` de la etiqueta siguiente— así que el negativo no restaba
    nada: se comía 6,4px del <select> de arriba.
    """
    medicion = _medir(_FORMULARIO.replace("MARGEN", _MARGEN_QUE_PISA), ancho=390)

    assert medicion["solapes"], "el solape plantado tiene que aparecer"
    assert "pisa 6.4px" in medicion["solapes"][0]
    # Y las otras dos mitades siguen diciendo que no pasa nada, que es
    # exactamente por qué hizo falta la tercera.
    assert medicion["desborde_pagina"] == 0


def test_el_MISMO_formulario_con_el_margen_BUENO_no_marca_nada():
    """El control, y es la mitad que condena a un detector que marca todo.

    Un test que solo prueba el caso positivo lo pasa igual uno que devuelve
    todos los pares siempre.
    """
    medicion = _medir(_FORMULARIO.replace("MARGEN", _MARGEN_BUENO), ancho=390)

    assert medicion["solapes"] == []
    assert medicion["pares"] > 0, "si no miró ningún par, el cero de arriba no dice nada"


def test_el_solape_se_mide_aunque_la_pantalla_NO_TENGA_FILAS():
    """Un formulario no tiene filas, y ahí es donde apareció el defecto.

    Con el corte por "sin filas" ANTES del bloque de solapes, esta clase de
    pantalla devolvía la lista vacía sin haber mirado un solo par — el cero
    del corolario 47 adentro de la herramienta escrita para el 47. Por eso el
    bloque va arriba del corte, y por eso este test exige las dos cosas: que
    el fixture no tenga filas, y que igual conteste.
    """
    medicion = _medir(_FORMULARIO.replace("MARGEN", _MARGEN_QUE_PISA), ancho=390)

    assert medicion["filas"] == 0, "el fixture tiene que no tener filas, o no prueba esto"
    assert medicion["solapes"], "sin filas también hay solapes que mirar"


def test_dos_botones_LADO_A_LADO_no_son_un_solape():
    """El control que le faltaba al par, y por eso está escrito acá.

    Dos elementos en el mismo renglón tienen el borde inferior del primero
    más abajo que el superior del segundo SIEMPRE — comparten línea, no están
    uno arriba del otro. La primera versión del detector los marcaba, y los
    marcaba en una pantalla real (los botones "Editar" y "Eliminar" de cada
    fila del catálogo): dos falsos positivos por pantalla, que es el
    corolario 53 exacto.

    Y lo que lo dejó pasar fue que los DOS casos plantados del par —el que
    pisa y el que no— eran formularios de una columna, donde no existe el
    lado a lado. Un par que no se parece a donde la herramienta se usa no
    prueba nada.
    """
    html = """
    <div style="display: flex; gap: 6px">
      <button style="padding: 6px">Editar</button>
      <button style="padding: 6px">Eliminar</button>
    </div>
    """
    medicion = _medir(html, ancho=390)

    assert medicion["solapes"] == []


def test_lo_POSICIONADO_que_se_pisa_a_PROPOSITO_no_cuenta_como_solape():
    """Un cartel flotante se pisa por diseño; marcarlo es marcar todo."""
    html = """
    <div style="position: relative; height: 60px">
      <p style="margin: 0">Texto de abajo</p>
      <p style="position: absolute; top: 0; margin: 0">Cartel encima</p>
    </div>
    """
    medicion = _medir(html, ancho=390)

    assert medicion["solapes"] == []


# --- Y LAS PANTALLAS DE VERDAD, que es lo que el canario pidió -------------
#
# Los tests de arriba miden un fixture PLANTADO: prueban la herramienta. Con
# solo esos, devolverle el `margin: -0.4rem` a las dos pantallas de artículos
# no hace caer nada —medido con el canario el 15/09— o sea que el defecto
# real podía volver con la suite en verde.
#
# Van acá y no en test_app.py porque necesitan navegador, que es opcional en
# este proyecto: el resto de la suite no lo tiene que necesitar.


def _pantalla_de_articulos(ruta):
    from unittest.mock import patch

    from tests.test_app import cliente

    articulo = {"id": 6, "nombre": "EJEMPLO Uno", "unidad_compra": "unidad",
                "unidad_conteo": "unidad", "contenido_referencia": 10, "grupo": "fruta"}
    with (
        patch("app.main.obtener_articulo", return_value=articulo),
        patch("app.main.listar_articulos", return_value=[articulo]),
    ):
        respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200, respuesta.status_code
    return respuesta.text


def test_las_DOS_pantallas_de_articulos_no_tienen_nada_que_se_pise_a_390px():
    """El defecto del 15/09: la ayuda del conteo pisaba 6,4px al <select>.

    El artículo del fixture tiene `unidad_conteo`, que es lo que hace
    aparecer el campo y su ayuda — sin eso el bloque no se dibuja y el test
    mediría una pantalla que no tiene el caso.
    """
    for ruta in ("/compras/articulos", "/compras/articulos/6/editar"):
        medicion = _medir(_pantalla_de_articulos(ruta), ancho=390)
        assert medicion["pares"] > 0, f"{ruta}: no se miró un solo par"
        assert medicion["solapes"] == [], f"{ruta}: {medicion['solapes']}"


def test_el_campo_del_CONTEO_y_su_ayuda_ESTAN_en_las_dos_pantallas():
    """El control del de arriba: sin el campo, "cero solapes" es cero de nada.

    Se pregunta por el `name` del control y no por el texto de la ayuda: el
    texto puede aparecer en un comentario de la plantilla (corolario 38) y el
    atributo entero solo puede ser marcado (corolario 50).
    """
    for ruta in ("/compras/articulos", "/compras/articulos/6/editar"):
        marcado = _pantalla_de_articulos(ruta)
        assert 'name="unidad_conteo"' in marcado, ruta
        assert 'class="ayuda-conteo"' in marcado, ruta


def test_en_CELULAR_el_conteo_del_catalogo_se_explica_y_el_vacio_no_dice_nada():
    """"unidad" suelto debajo del nombre se lee como si el artículo tuviera una unidad.

    No la tiene: la de venta la define cada ficha, y el mismo mango puede ir
    por unidad a un cliente y por kilo a otro. Lo único que sí es del
    artículo es qué cuenta ADEMÁS de los kilos, y eso lo dice el rótulo.

    Se mide el `::before` COMPUTADO y no la regla en el texto: el rótulo es
    un efecto de CSS, y un assert sobre la hoja prueba que la orden se dio,
    no que se cumpla (corolario 32).

    El artículo SIN conteo va de control: ahí la celda tiene que quedar
    muda. Con el `::before` en el <td> en vez de en el <span>, escribiría
    "también se cuenta en " sobre una celda vacía.
    """
    from unittest.mock import patch

    from tests.test_app import cliente

    articulos = [
        {"id": 6, "nombre": "EJEMPLO Con", "unidad_compra": "unidad",
         "unidad_conteo": "unidad", "contenido_referencia": 10, "grupo": "fruta"},
        {"id": 7, "nombre": "EJEMPLO Sin", "unidad_compra": "kilo",
         "unidad_conteo": None, "contenido_referencia": 16, "grupo": "hortaliza"},
    ]
    with patch("app.main.listar_articulos", return_value=articulos):
        html = cliente.get("/compras/articulos").text

    pytest.importorskip("playwright", reason="el rótulo es CSS: hace falta un navegador")

    async def leer(ancho):
        from playwright.async_api import async_playwright

        from scripts.medir_layout import CHROMIUM

        async with async_playwright() as pw:
            navegador = await pw.chromium.launch(executable_path=CHROMIUM)
            pagina = await navegador.new_page(viewport={"width": ancho, "height": 844})
            await pagina.set_content(html)
            leido = await pagina.evaluate("""() =>
              [...document.querySelectorAll('tbody tr')].map(fila => {
                const celda = fila.children[1];
                const span = celda.querySelector('.conteo');
                const antes = span ? getComputedStyle(span, '::before').content : 'none';
                return ((antes && antes !== 'none' ? antes.replace(/"/g, '') : '')
                        + celda.textContent.trim()).trim();
              })""")
            await navegador.close()
        return leido

    en_celular = asyncio.run(leer(390))
    assert en_celular[0] == "también se cuenta en unidad"
    assert en_celular[1] == "", "el artículo sin conteo no tiene nada que declarar"

    # Y en pantalla ancha el rótulo NO va: ahí lo dice el <th>, y repetirlo
    # llenaría la celda de prosa.
    en_ancha = asyncio.run(leer(1200))
    assert en_ancha[0] == "unidad"


def _pantallas_de_la_cuenta_con_colegas(nombre):
    """Las dos pantallas de la cuenta, con el nombre que se le pase.

    RECIBE EL NOMBRE porque es lo único que en estas pantallas lo escribe una
    persona, y por lo tanto lo único cuyo largo no controlamos.
    """
    from datetime import date
    from unittest.mock import patch

    from tests.test_app import cliente

    vacio_gasto = {"desde": date(2026, 6, 18), "por_envase": [], "cajas": 0,
                   "gasto": 0.0, "sin_costo": 0, "ultima": None}
    vacio_perd = {"desde": date(2026, 6, 18), "renglones": [], "cajas": 0.0,
                  "pesos": 0.0, "ultimo": None}
    envases = [{"id": 1, "nombre": "Caja EJEMPLO Grande", "umbral_reposicion": 100,
                "desde": date(2026, 9, 10), "contadas": 500, "declaradas": -420,
                "por_guias": 0, "stock": 80}]
    cuentas = [{"colega_id": 3, "colega": nombre, "movimientos": 2,
                "por_envase": [{"envase": nombre, "neto": 220,
                                "lado": "me debe", "cuantas": 220},
                               {"envase": "Caja EJEMPLO Chica", "neto": -40,
                                "lado": "le debo", "cuantas": 40}]}]
    movimientos = [{"id": 1, "colega_id": 3, "colega": nombre, "envase_id": 1,
                    "envase": nombre, "origen": "colega_le_presto",
                    "cantidad": -220, "fecha": date(2026, 9, 12), "motivo": nombre}]

    with (
        patch("app.main.cajas_perdidas_por_rechazo", return_value=vacio_perd),
        patch("app.main.gasto_en_cajas", return_value=vacio_gasto),
        patch("app.main.stock_de_envases", return_value=envases),
        patch("app.main.cuentas_de_colegas", return_value=cuentas),
        patch("app.main.listar_colegas",
              return_value=[{"id": 3, "nombre": nombre, "activo": True}]),
        patch("app.main.contar_guias_sin_declarar_el_envase",
              return_value={"casos": 0, "poblacion": 0}),
    ):
        lista = cliente.get("/compras/cajas")
    with (
        patch("app.main.movimientos_de_colegas", return_value=movimientos),
        patch("app.main.cuentas_de_colegas", return_value=cuentas),
    ):
        detalle = cliente.get("/compras/cajas/colega/3")

    # LA IDENTIDAD AL LADO DEL NUMERO: un cero de la pantalla de la clave se
    # ve igual de prolijo que uno bueno, y las dos viven detrás de una puerta.
    assert lista.status_code == 200 and "colega-fila" in lista.text
    assert detalle.status_code == 200 and 'class="mov ' in detalle.text
    return {"/compras/cajas": lista.text, "/compras/cajas/colega/3": detalle.text}


def test_las_DOS_pantallas_de_la_cuenta_aguantan_un_nombre_QUE_NO_SE_PUEDE_PARTIR():
    """El nombre de un colega lo tipea una persona: su largo no lo controlamos.

    EL CASO SE PLANTA, porque un cero sobre un nombre corto no dice nada. Con
    60 caracteres sin un espacio el navegador NO ENVUELVE —`overflow-wrap`
    por defecto es `normal`— así que el texto se sale por el costado y la
    pantalla pide scroll horizontal, que es justo lo que este proyecto no
    admite en celular.

    Medido el 17/09 antes de arreglarlo: la lista desbordaba 395px y el
    detalle 430px. El del detalle NO era el nombre en la tarjeta sino EL
    TITULO DE LA BARRA, que es un componente compartido y la única de las 93
    pantallas que le metía texto tipeado por una persona.

    Y SE MIDE EL DESBORDE DE LA PAGINA, no `medicion["desborde"]`: esa clave
    vale 0 POR CONSTRUCCION cuando la pantalla no tiene filas de tabla, y
    estas dos son de tarjetas. Un cero que no puede ser otra cosa no es una
    medición.
    """
    corto = "Colega EJEMPLO Uno"
    largo = "X" * 60
    for ruta, html in _pantallas_de_la_cuenta_con_colegas(corto).items():
        medicion = _medir(html, ancho=390)
        assert medicion["desborde_pagina"] == 0, f"{ruta}: {medicion['desborde_pagina']}px"
        assert medicion["pares"] > 0, f"{ruta}: no se miró un solo par"
        assert medicion["solapes"] == [], f"{ruta}: {medicion['solapes']}"
    for ruta, html in _pantallas_de_la_cuenta_con_colegas(largo).items():
        medicion = _medir(html, ancho=390)
        assert medicion["desborde_pagina"] == 0, (
            f"{ruta}: un nombre sin espacios desborda {medicion['desborde_pagina']}px"
        )
