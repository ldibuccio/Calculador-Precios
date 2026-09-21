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
# La ficha como la devuelve `_fichas_por_articulo`: clave TEXTO, que es como la
# indexa la plantilla. CON envase y con kilaje, que es el caso de producción —
# un fixture sin envase defendería lo contrario de lo que pasa en el galpón.
FICHAS = {"7": [{"id": 9, "nombre": "Caja de ejemplo", "kilaje": "16 kg"}]}
LOTES = [
    {"tipo": "guia", "origen_id": 1, "restante": 40.0,
     "fecha": date(2026, 9, 17), "etiqueta": "Compra de EJEMPLO Prov"},
]


def _pantalla(**extra):
    de_base = {
        "app.main.listar_articulos": [ARTICULO],
        "app.main.obtener_articulo": ARTICULO,
        "app.main._lotes_con_resto": LOTES,
        # PARCHEARLO ES, ÉL SOLO, UNA ASERCIÓN DE QUE `app.main` LO IMPORTA:
        # `mock.patch` no crea el atributo. El selector de porción entró el
        # 21/09 y sin esto la pantalla se iba a la base de verdad.
        "app.main._fichas_por_articulo": FICHAS,
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

    # CON SELECTOR DE PORCIÓN desde el 21/09. Hasta ese día este test exigía
    # lo CONTRARIO —"el pase sale de los sueltos y punto"— con su razón al
    # lado, que es lo que lo volvía difícil de cuestionar: un assert con
    # razón escrita se lee como una decisión ya tomada. Era una deducción
    # nuestra sobre cómo se trabaja y el dueño la dio vuelta: una caja armada
    # para Día que no salió y se puso fea pasa a segunda directo.
    # TODOS LOS RADIOS LLEVAN EL NAME, y es un CONTEO y no un `in`: lo
    # encontró un canario en CERO. Sacándole el `name` SOLO al de los sueltos,
    # el `in` lo satisfacían los de las fichas —que lo conservan— y la
    # pantalla quedaba con la opción más usada rota: no manda nada y el POST
    # rebota con "Elegí de qué se trata". Si lo que se afirma vive en algo que
    # la pantalla REPITE, un `in` contesta por el más suertudo.
    radios = re.findall(r'<input type="radio" id="qp-[^>]*>', marcado)
    assert len(radios) >= 2, f"se dibujaron {len(radios)} opciones: no hay qué contar"
    assert all('name="que_pasa"' in r for r in radios), radios
    assert any('value="sueltos"' in r for r in radios)
    assert "Cajas de Caja de ejemplo" in marcado

    # Y LA SEGUNDA NO SE OFRECE, que es la única diferencia con la Merma:
    # pasar segunda a segunda no es ninguna operación. No se lista "avisando
    # al guardar" — eso deja a la vista algo que no se puede elegir.
    assert 'value="segunda"' not in marcado
    # El selector de la Merma se llama distinto y no puede haberse colado.
    assert 'name="que_merma"' not in marcado


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
            "articulo_id": "7", "que_pasa": "sueltos", "cantidad": "10", "motivo": "sobremadurado",
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


def test_el_pase_NO_manda_foto_ni_destino_de_rechazo_y_la_FICHA_va_en_None_si_son_sueltos():
    """Los campos que la base prohíbe para este tipo, no se mandan.

    Se afirma por la NEGATIVA sobre el kwargs entero y no campo por campo: el
    día que alguien agregue uno más, el test lo va a ver. `ficha_id` entró el
    21/09 y por eso está en la lista — de los SUELTOS va en None, que es
    distinto de no mandarlo: la columna existe y el caso es "no salió de
    ninguna ficha".
    """
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "que_pasa": "sueltos", "cantidad": "3", "motivo": "golpeado", "fecha": "", "lote": "",
        }, follow_redirects=False)

    _, kwargs = mock_mov.call_args
    assert set(kwargs) == {"bultos_segunda", "lote_tipo", "lote_origen_id", "ficha_id"}, (
        f"el pase manda campos que no le corresponden: {set(kwargs)}"
    )
    assert kwargs["ficha_id"] is None


def test_el_pase_de_CAJAS_ARMADAS_manda_la_ficha_y_el_aviso_dice_de_cual():
    """El caso del dueño: se armó una caja para Día, no salió, se puso fea.

    El rival es guardar el pase SIN ficha aunque el operario haya elegido una
    —que es lo que pasaba hasta el 21/09, porque el campo no existía—: el
    total baja igual y no se ve nada raro, pero la baja cae entera sobre los
    sueltos, y no hay ninguno.
    """
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        respuesta = cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "que_pasa": "9", "cantidad": "3", "motivo": "golpeado",
            "fecha": "", "lote": "",
        }, follow_redirects=False)

    _, kwargs = mock_mov.call_args
    assert kwargs["ficha_id"] == 9
    # Y EL AVISO DICE DE QUÉ PILA SALIÓ: es lo que el operario relee para
    # saber si le pegó al renglón que quería.
    assert "Caja de ejemplo" in respuesta.headers["location"] or "Caja+de+ejemplo" in respuesta.headers["location"]


def test_la_SEGUNDA_la_rechaza_el_POST_aunque_la_pantalla_no_la_ofrezca():
    """La guarda va donde se ESCRIBE: un formulario armado a mano entra sin
    ver el cartel, y pasar segunda a segunda no es ninguna operación.
    """
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        respuesta = cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "que_pasa": "segunda", "cantidad": "3", "motivo": "golpeado",
            "fecha": "", "lote": "",
        }, follow_redirects=False)

    assert respuesta.status_code == 400
    assert "La segunda ya es segunda" in respuesta.text
    assert not mock_mov.called


def test_una_ficha_de_OTRO_articulo_no_entra():
    """No es un dato raro: es un dato roto. Lo rechaza también la FK compuesta
    de la base (`movimientos_stock_ficha_del_articulo`); acá el cartel existe
    para que se entienda, no para sostener la regla.
    """
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        respuesta = cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "que_pasa": "404", "cantidad": "3", "motivo": "golpeado",
            "fecha": "", "lote": "",
        }, follow_redirects=False)

    assert respuesta.status_code == 400
    assert "no es de este artículo" in respuesta.text
    assert not mock_mov.called


def test_el_LOTE_se_puede_dirigir_igual_que_en_la_merma():
    """El pase se costea EXACTAMENTE COMO LA MERMA: la plata se pierde, y
    cuál lote la perdió se elige igual. Sin esto serían dos reglas para la
    misma decisión."""
    with _pantalla(), patch("app.main.crear_movimiento_stock") as mock_mov:
        respuesta = cliente.post("/deposito/stock/pase-a-segunda", data={
            "articulo_id": "7", "que_pasa": "sueltos", "cantidad": "5", "motivo": "podrido",
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
    base = {"articulo_id": "7", "que_pasa": "sueltos", "cantidad": "10", "motivo": "podrido", "fecha": "", "lote": ""}
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
            "articulo_id": "7", "que_pasa": "sueltos", "cantidad": "0", "motivo": "golpeado",
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


# --- LA CUENTA Y EL EXTRACTO REPARTEN CON EL MISMO CRITERIO -------------------


def test_la_CUENTA_y_el_EXTRACTO_leen_la_ficha_de_la_MISMA_constante():
    """El bug del 09/09 servido de nuevo, y estuvo vivo del 10 al 21/09.

    La cuenta (`_SQL_STOCK_PARTIDO`) leía `m.ficha_id` desde que la merma
    ganó su porción; el extracto NO LO LEÍA —derivaba la ficha solo por el
    camino del reingreso—. Medido antes de arreglarlo, con 10 cajas armadas y
    3 tiradas: la cuenta decía ficha 7 y el extracto decía `ficha_id` None.

    El síntoma es inconfundible y está escrito en el código: los dos "Sin
    explicar" del mismo día salen IGUALES Y DE SIGNO OPUESTO, porque el
    evento está de un lado y el saldo del otro.

    Es un test de TEXTO porque con la base mockeada las dos versiones
    "andan": lo que las separa no es el valor, es de dónde sale.
    """
    from app.db import _SQL_STOCK_PARTIDO, _SQL_TIPO_TIENE_FICHA_PROPIA
    import inspect
    from app.db import eventos_de_stock_del_dia

    assert _SQL_TIPO_TIENE_FICHA_PROPIA in _SQL_STOCK_PARTIDO
    # El extracto lo INTERPOLA, así que lo que queda en su cuerpo es el nombre
    # de la constante: preguntar por el SQL ya resuelto no lo encontraría.
    assert "_SQL_TIPO_TIENE_FICHA_PROPIA" in inspect.getsource(eventos_de_stock_del_dia)


def test_los_DOS_tipos_que_llevan_ficha_salen_de_UNA_lista():
    """Merma y pase. Escrita dos veces, el día que aparezca un tercero la
    cuenta lo va a restar de la ficha y el extracto lo va a dibujar en
    sueltos — que es exactamente lo que acaba de pasar con el pase.
    """
    from app.db import TIPOS_CON_FICHA_PROPIA, _SQL_TIPO_TIENE_FICHA_PROPIA

    assert TIPOS_CON_FICHA_PROPIA == ("merma", "pase_a_segunda")
    for tipo in TIPOS_CON_FICHA_PROPIA:
        assert f"'{tipo}'" in _SQL_TIPO_TIENE_FICHA_PROPIA


def test_el_CTE_de_la_cuenta_se_llama_BAJAS_y_no_MERMAS():
    """El nombre se movió con la condición a propósito: un CTE que se llama
    "mermas" y suma dos tipos es la clase de nombre que se lee y no se
    verifica, y el que venga a agregar el tercero va a buscar ahí.
    """
    from app.db import _SQL_STOCK_PARTIDO

    sql = "\n".join(
        l for l in _SQL_STOCK_PARTIDO.splitlines() if not l.strip().startswith("--")
    )
    assert "bajas_ficha AS (" in sql
    assert "mermas_ficha" not in sql
    # Y LA PATA DEL UNION, que es la fácil de olvidar: sin ella una ficha cuyo
    # ÚNICO movimiento sea una baja no existe para la consulta. La resta la
    # haría bien y no la haría nunca.
    assert "SELECT articulo_id, ficha_id FROM bajas_ficha" in sql


def test_el_CHECK_del_ESQUEMA_y_la_lista_de_PYTHON_son_LA_MISMA_regla():
    """Los dos dicen qué tipos pueden llevar ficha, en dos lenguajes.

    Lo encontró un canario en CERO: devolver el CHECK del esquema a su
    versión vieja —la que RECHAZA el pase con ficha— no hacía caer nada. La
    migración corrió en las dos bases, así que las de hoy están bien; lo que
    quedaba roto es la base que TODAVÍA NO EXISTE, que nace de
    `db/esquema_completo.sql` y rechazaría todo pase de caja armada. Ni la
    suite ni el humo lo pueden ver: el humo ABRE pantallas, no escribe un
    pase.

    Se compara contra el CHECK y no contra una lista copiada: copiada
    envejece en silencio, que es justo lo que pasó del 20 al 21/09.
    """
    import re

    from app.db import TIPOS_CON_FICHA_PROPIA

    esquema = open("db/esquema_completo.sql", encoding="utf-8").read()
    bloque = re.search(r"create table movimientos_stock.*?\n\);", esquema, re.S).group(0)
    check = re.search(
        r"constraint movimientos_stock_ficha_solo_\w+\s*\n\s*check \((.*?)\),\n", bloque, re.S
    )
    assert check is not None, "el esquema dejó de tener el CHECK de la ficha"
    del_esquema = tuple(sorted(re.findall(r"'([a-z_]+)'", check.group(1))))

    assert del_esquema == tuple(sorted(TIPOS_CON_FICHA_PROPIA)), (
        f"el esquema permite {del_esquema} y Python reparte {TIPOS_CON_FICHA_PROPIA}: "
        "una base nueva se comportaría distinto de las dos que están corriendo"
    )


# --- DE QUÉ LOTE SALE LA PÉRDIDA (21/09) -------------------------------------


def test_un_pase_de_CAJAS_ARMADAS_prefiere_el_lote_de_CAJA_y_no_el_cajon_mas_viejo():
    """Es del dueño: "armé una caja de Día con tomate; si pasa a segunda es
    lo mismo que tirarla, y la pérdida es al costo de ESA caja —el tomate que
    lleva adentro más la caja—, no al del cajón más viejo".

    El rival está plantado y es plausible: un cajón MÁS VIEJO y más barato
    del mismo artículo. Sin la preferencia el FIFO lo toma primero, la
    pérdida sale a $100 en vez de $300, y no hay nada en ninguna pantalla que
    se vea raro.
    """
    from core.stock import pasadas_de_lotes

    lotes = [
        {"tipo_lote": "guia", "origen_id": 1, "restante": 10.0, "costo": 100.0},
        {"tipo_lote": "reproceso", "origen_id": 2, "restante": 10.0, "costo": 300.0},
    ]
    de_cajas = [l["tipo_lote"] for p in pasadas_de_lotes(
        lotes, {"tipo": "pase_a_segunda", "ficha_id": 9}) for l in p]
    assert de_cajas[0] == "reproceso"

    # EL RIVAL, escrito para que se vea que NO es el que va:
    de_sueltos = [l["tipo_lote"] for p in pasadas_de_lotes(
        lotes, {"tipo": "pase_a_segunda", "ficha_id": None}) for l in p]
    assert de_sueltos[0] == "guia"


def test_la_preferencia_del_pase_es_PREFERENCIA_y_no_PARED():
    """Si por un agujero viejo no hubiera lote de caja armada, una pared
    trabaría al operario por algo que ya estaba ahí antes de que tocara nada.
    Es el mismo criterio que el armado, que tampoco es pared.
    """
    from core.stock import pasadas_de_lotes, prioridad_de_lote

    salida = {"tipo": "pase_a_segunda", "ficha_id": 9}
    assert prioridad_de_lote(salida).prohibe == ()

    solo_cajon = [{"tipo_lote": "guia", "origen_id": 1, "restante": 10.0, "costo": 100.0}]
    cae = [l["tipo_lote"] for p in pasadas_de_lotes(solo_cajon, salida) for l in p]
    assert cae == ["guia"], "sin caja armada tiene que caer al cajón igual"


def test_la_MERMA_con_ficha_NO_cambia_y_eso_es_una_decision():
    """Queda en FIFO puro, como desde el 08/09.

    No es un olvido y no es simetría: el comentario de `_PRIORIDAD_POR_SALIDA`
    dice que una merma puede ser de un cajón podrido o de una caja golpeada y
    que el tipo no lo distingue. Desde el 10/09 la merma TIENE ficha, así que
    hoy sí podría distinguirlo — y moverla cambiaría el costeo de las mermas
    ya cargadas. Es una decisión del dueño, no nuestra, y hasta que la tome
    este test la fija.
    """
    from core.stock import SIN_PREFERENCIA, prioridad_de_lote

    assert prioridad_de_lote({"tipo": "merma", "ficha_id": 9}) is SIN_PREFERENCIA


def test_la_SALIDA_trae_la_ficha_desde_la_consulta_y_no_un_NULL():
    """La rama de movimientos mandaba `NULL` donde la del armado manda la
    ficha: cuando se escribió, un movimiento no podía tener una.

    Es un test de TEXTO porque con la base mockeada el valor lo entrega el
    fixture (corolario 65): sacar la columna del SELECT llega igual, y la
    preferencia se queda sin con qué decidir — en silencio.
    """
    from app.db import _SQL_SALIDAS_STOCK

    sql = "\n".join(
        l for l in _SQL_SALIDAS_STOCK.splitlines() if not l.strip().startswith("--")
    )
    rama = sql[sql.index("FROM movimientos_stock m") - 400:sql.index("FROM movimientos_stock m")]
    assert "m.lote_tipo, m.lote_origen_id, m.ficha_id, FALSE" in rama, rama[-200:]
    # Y `ficha_con_envase` SIGUE EN FALSE: esa columna es la pared del ARMADO
    # —con envase, un armado no puede salir de un cajón— y un movimiento no es
    # un armado. Cambiarla acá movería una regla que no es de esta salida.
    assert "m.ficha_id, TRUE" not in rama
