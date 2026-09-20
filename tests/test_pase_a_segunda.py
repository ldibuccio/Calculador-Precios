# -*- coding: utf-8 -*-
"""Pasar mercadería de primera a segunda: la puerta que faltaba.

El depósito lo venía haciendo con una guía R de reproceso con `primera = 0`
—medido: 2 de 395 en Frutamax, $670.000 sin pegarse a nada, las dos
`todo_a_SEGUNDA`— porque era la única puerta que había. Los números que esa
puerta produce están BIEN; lo que estaba mal es que ocupara una guía R.
"""
import ast
import io
import re
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)

ARTICULO = {"id": 7, "nombre": "EJEMPLO Berenjena"}
LOTES = [
    {"tipo": "guia", "origen_id": 1, "restante": 40.0,
     "fecha": date(2026, 9, 17), "etiqueta": "Compra de EJEMPLO Prov"},
]


def _pantalla(**extra):
    de_base = {
        "app.main.listar_articulos": [ARTICULO],
        "app.main.obtener_articulo": ARTICULO,
        "app.main._lotes_con_resto": LOTES,
    }
    de_base.update(extra)
    from contextlib import ExitStack
    pila = ExitStack()
    for nombre, valor in de_base.items():
        pila.enter_context(patch(nombre, return_value=valor))
    return pila


def test_la_pantalla_pide_lo_que_hace_falta_y_NADA_MAS():
    with _pantalla():
        respuesta = cliente.get("/deposito/stock/pase-a-segunda?articulo_id=7")
    marcado = respuesta.text.split("</style>")[-1]

    assert respuesta.status_code == 200
    for campo in ('name="cantidad"', 'name="motivo"', 'name="fecha"', 'name="lote"'):
        assert campo in marcado, f"falta {campo}"

    # SIN FOTO, y es una decisión: en la merma la foto cierra la perilla de
    # tapar un faltante —lo tirado ya no se puede contar— y acá los bultos
    # siguen en el galpón, contables, en la otra pila. Pedirla sería un
    # trámite sin consecuencia, que es cómo se consigue que no se cargue.
    assert 'name="foto"' not in marcado
    assert 'name="sin_foto_confirmado"' not in marcado

    # Y SIN SELECTOR DE PORCIÓN: el pase sale de los sueltos y punto. Lo dice
    # la base (`movimientos_stock_ficha_solo_merma`) y ofrecer una ficha acá
    # sería un callejón — el POST lo rechazaría.
    assert 'name="que_merma"' not in marcado
    assert "Cajas de" not in marcado


def test_el_aviso_de_QUE_PASA_va_ARRIBA_del_campo_y_no_es_un_confirm():
    """Pasar a segunda es la acción LEGÍTIMA de esta pantalla, no la excepción.

    Un `confirm()` acá lo pasa el caso normal todas las veces: se lo cobra a
    todos y no ataja a nadie, que es el escalón que se aprende a esquivar. Lo
    que falta no es una decisión, falta INFORMACIÓN — y va antes de que se
    tipee el número, porque debajo del campo llega cuando ya se tipeó.
    """
    with _pantalla():
        marcado = cliente.get("/deposito/stock/pase-a-segunda?articulo_id=7").text.split("</style>")[-1]

    assert "que-pasa" in marcado
    assert marcado.index("que-pasa") < marcado.index('name="cantidad"'), (
        "el aviso quedó DEBAJO del campo: llega cuando el número ya se tipeó"
    )
    assert "segunda" in marcado and "Puesto" in marcado
    # Ningún escalón: ni confirm(), ni tilde, ni modal.
    assert "confirm(" not in marcado
    assert 'type="checkbox"' not in marcado


def test_el_pase_es_UN_SOLO_MOVIMIENTO_con_las_dos_mitades():
    """La misma fila lleva lo que sale de primera y lo que entra al pool.

    Con dos filas, una podría anularse sin la otra y quedaría mercadería en
    las dos pilas o en ninguna. Y el uno a uno lo exige además la base
    (`movimientos_stock_pase_uno_a_uno`), así que esto es el cableado de una
    regla que ya está escrita donde se escribe.
    """
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        respuesta = cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "cantidad": "10", "motivo": "sobremadurado",
            "fecha": "", "lote": "",
        }, follow_redirects=False)

    assert respuesta.status_code == 303
    mock_mov.assert_called_once()
    args, kwargs = mock_mov.call_args
    assert args[0] == 7
    assert args[1] == "pase_a_segunda"
    # LOS DOS NÚMEROS Y CON SIGNO: −10 sale de primera, +10 entra al pool.
    # Comparar solo el valor absoluto pasaría igual con el signo dado vuelta,
    # que sumaría a las DOS pilas.
    assert args[2] == -10.0, "la cantidad tiene que ser NEGATIVA"
    assert kwargs["bultos_segunda"] == 10.0
    assert args[3] == "sobremadurado"


def test_el_pase_NO_manda_ficha_ni_foto_ni_destino_de_rechazo():
    """Los tres campos que la base prohíbe para este tipo, no se mandan.

    Y se afirma por la NEGATIVA sobre el kwargs entero y no campo por campo:
    el día que alguien agregue un cuarto, el test lo va a ver.
    """
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "cantidad": "3", "motivo": "golpeado", "fecha": "", "lote": "",
        }, follow_redirects=False)

    _, kwargs = mock_mov.call_args
    assert set(kwargs) == {"bultos_segunda", "lote_tipo", "lote_origen_id"}, (
        f"el pase manda campos que no le corresponden: {set(kwargs)}"
    )


def test_el_LOTE_se_puede_dirigir_igual_que_en_la_merma():
    """El pase se costea EXACTAMENTE COMO LA MERMA: la plata se pierde, y
    cuál lote la perdió se elige igual. Sin esto serían dos reglas para la
    misma decisión."""
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        respuesta = cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "cantidad": "5", "motivo": "podrido",
            "fecha": "", "lote": "guia:1",
        }, follow_redirects=False)

    _, kwargs = mock_mov.call_args
    assert kwargs["lote_tipo"] == "guia" and kwargs["lote_origen_id"] == 1
    # Y el aviso dice de cuál salieron: el que lo cargó está parado al lado
    # de la mercadería y puede verificarlo ahí mismo.
    # El Location viene URL-encodeado, así que se decodifica: buscar la
    # frase cruda en la URL da falso negativo sobre un aviso correcto.
    from urllib.parse import unquote_plus
    assert "Salieron de: Compra de EJEMPLO Prov" in unquote_plus(respuesta.headers["location"])


@pytest.mark.parametrize("datos, esperado", [
    ({"cantidad": "0"}, "mayor"),
    ({"cantidad": "-5"}, "mayor"),
    ({"motivo": ""}, "Elegí el motivo"),
    ({"motivo": "porque si"}, "no está en la lista"),
    ({"fecha": "2099-01-01"}, "no puede ser futura"),
    ({"fecha": "no es fecha"}, "no es válida"),
    ({"lote": "inventado:9"}, "no es válido"),
])
def test_lo_que_REBOTA_y_no_llega_a_escribir(datos, esperado):
    """Cada rebote, y que NO haya escrito nada: un rebote que igual guarda es
    peor que no rebotar, porque el operario se va creyendo que no pasó."""
    base = {"articulo_id": "7", "cantidad": "10", "motivo": "podrido", "fecha": "", "lote": ""}
    base.update(datos)
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        respuesta = cliente.post("/deposito/stock/pase-a-segunda", data=base)

    assert respuesta.status_code == 400
    assert esperado in respuesta.text
    mock_mov.assert_not_called()


def test_el_REBOTE_conserva_lo_que_ya_estaba_cargado():
    """El corolario 43: el que reintenta corrige lo que la pantalla le señaló
    y aprieta de nuevo — no vuelve a revisar los campos que ya había llenado.
    Un campo que el re-render pierde se va sin que nadie lo mire."""
    with _pantalla(), patch("app.main.crear_movimiento_stock"):
        respuesta = cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "cantidad": "0", "motivo": "golpeado",
            "fecha": "2026-09-18", "lote": "guia:1",
        })
    marcado = respuesta.text.split("</style>")[-1]

    assert 'value="2026-09-18"' in marcado, "perdió la fecha"
    assert re.search(r'value="golpeado"[^>]*selected', marcado), "perdió el motivo"
    assert re.search(r'value="guia:1"[^>]*selected', marcado), "perdió el lote"


def test_la_pantalla_esta_LINKEADA_desde_el_MENU_de_deposito():
    """Una ruta que responde 200 y que nadie linkea es una ruta que no existe.

    Todos los tests entran por la URL, así que la ausencia de puerta es
    invisible para la suite entera por construcción (corolario 31).

    Miraba `deposito_stock.html`, que era el hub intermedio; ese hub se borró
    el 20/09 y las seis operaciones subieron al menú de Depósito.
    """
    menu = io.open("templates/deposito.html", encoding="utf-8").read()
    assert 'href="/deposito/stock/pase-a-segunda"' in menu.split("</style>")[-1]


def test_la_CUARTA_pata_del_pool_suma_lo_que_paso_a_segunda():
    """Sin la pata, el pase sale del stock y no entra a ningún lado.

    Y no se descuadraría contra nada: simplemente no se podría remitir al
    Puesto mercadería que está en el galpón. Por eso se pregunta por el TEXTO
    del SQL — ningún test de valor con un cursor falso puede ver esto.
    """
    from app.db import _SQL_POOL_SEGUNDA, _pool_segunda

    sin_comentarios = "\n".join(l.split("--")[0] for l in _SQL_POOL_SEGUNDA.splitlines())
    assert "segunda_pase AS (" in sin_comentarios
    assert "tipo = 'pase_a_segunda'" in sin_comentarios

    # EL RECORTE DEL CORTE, con canario: la foto del stock inicial se toma a
    # la tarde, así que ya viene neta del trabajo de ese día. Con `>=` el día
    # del corte se contaría dos veces (corolario 12). Es la NOVENA aparición
    # de esta asimetría en el proyecto.
    pata = sin_comentarios.split("segunda_pase AS (")[1].split("), remitida")[0]
    assert "fecha_operacion > corte_seg.fecha" in pata
    assert "fecha_operacion >= corte_seg.fecha" not in pata

    # Y la resta suma las TRES entradas: con un default en la pata nueva, un
    # llamador que se la olvidara devolvería un pool chico y nada avisaría.
    assert _pool_segunda(5, 4, 7, 2) == 14
    with pytest.raises(TypeError):
        _pool_segunda(5, 4, 2)


def test_el_pase_SE_NOMBRA_en_Movimientos_y_dice_ADONDE_fue():
    """Sin esto el renglón se lee como una salida a secas —el mismo aspecto
    que una merma— y lo que pasó es lo contrario: la mercadería sigue en el
    galpón, en la otra pila."""
    from core.extracto_porcion import ETIQUETAS_MOVIMIENTO

    assert ETIQUETAS_MOVIMIENTO["pase_a_segunda"] == "Pasó a 2ª"

    plantilla = io.open("templates/deposito_stock_movimientos.html", encoding="utf-8").read()
    marcado = plantilla.split("</style>")[-1]
    assert 'm.tipo == "pase_a_segunda"' in marcado
    assert "al pool de segunda" in marcado
    # Y el color NO es el de la merma: la merma es roja porque la mercadería
    # se fue; el pase no se fue, cambió de pila.
    css = plantilla.split("</style>")[0]
    assert ".pill-pase_a_segunda" in css
    assert "#fecaca" not in css.split(".pill-pase_a_segunda")[1].split("}")[0]


def test_a_390px_no_desborda_NI_CON_UN_NOMBRE_QUE_NO_SE_PUEDE_PARTIR():
    """El largo de un nombre no lo controlamos: sale del catálogo.

    Y el `desborde` que hay que leer en una pantalla de tarjetas es
    `desborde_pagina`: la otra clave viene clavada en 0 cuando no hay filas
    de tabla, así que leerla a mano da un cero que no puede dar otra cosa
    (quinto límite del corolario 53).

    EL CONTROL ES LO QUE HACE LEGIBLE EL CERO: con el `overflow-wrap`
    apagado la misma pantalla desborda —239px con este nombre, 396 con uno
    más largo—. Sin esa tercera medición, un 0 y un 0 se imprimen igual esté
    el arreglo puesto o no. Se afirma que es MAYOR QUE CERO y no un número
    fijo: el valor depende del nombre del fixture, así que clavarlo haría
    caer el test el día que alguien lo cambie, por una razón que no es la
    suya.
    """
    pytest.importorskip("playwright", reason="el ancho de una caja lo decide el navegador")
    from scripts.medir_layout import medir_sync

    largo = {"id": 7, "nombre": "EJEMPLOBerenjenaConUnNombreLarguisimoQueNoSePuedePartirJamas"}
    with _pantalla(**{"app.main.listar_articulos": [largo], "app.main.obtener_articulo": largo}):
        html = cliente.get("/deposito/stock/pase-a-segunda?articulo_id=7").text

    def desborde(m):
        return m.get("desborde_pagina", m.get("desborde", 0))

    medicion = medir_sync(html, ancho=390)
    assert medicion["pares"] > 0, "no se miró ningún par: la medición está vacía"
    assert desborde(medicion) == 0, "la pantalla se arrastra de costado"
    assert medicion["solapes"] == [], f"hay cajas pisándose: {medicion['solapes']}"

    sin_arreglo = html.replace("overflow-wrap", "overflow-wrap-apagado")
    roto = desborde(medir_sync(sin_arreglo, ancho=390))
    assert roto > 0, (
        "sin el overflow-wrap la pantalla NO desborda: entonces el 0 de arriba "
        "no lo produce el arreglo y este test no puede ver nada"
    )


def test_lo_que_se_toca_entra_COMODO_con_el_pulgar():
    """44px es el mínimo de este proyecto, y acá se toca todo: son cinco
    controles y ninguno convive con treinta hermanos."""
    pytest.importorskip("playwright", reason="el alto de un control lo decide el navegador")
    from scripts.medir_layout import medir_sync

    with _pantalla():
        html = cliente.get("/deposito/stock/pase-a-segunda?articulo_id=7").text

    altos = medir_sync(html, ancho=390, selector_filas="select, input, button")
    mirados = altos.get("celdas", 0)
    assert mirados >= 5, f"solo se miraron {mirados} controles: la medición no llegó"
