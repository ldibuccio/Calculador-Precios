# -*- coding: utf-8 -*-
"""La pantalla de Pérdidas: lo que se tiró y lo que pasó a segunda, en plata.

LO QUE ESTOS TESTS PUEDEN Y LO QUE NO. Acá la base está mockeada, así que
el número lo decide el fixture: nada de esto verifica que la cuenta esté
bien. Eso lo verifica `tests/test_perdidas_contra_la_base.py`, que corre el
rejuego contra un Postgres de verdad. Lo de acá es la PANTALLA — que el
filtro viaje, que los dos renglones se dibujen, que lo que no se pudo
costear se vea.

LA REGLA QUE DEFIENDE, y es del dueño (21/09): *"todo lo que se tira o pasa
a segunda es plata perdida. Una caja de Día armada pierde los kilos que
tenía MÁS la caja; los bultos sueltos pierden solo los kilos."*
"""
import ast
import contextlib
import io
import os
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def _renglon(bultos, mercaderia, cajas, caja_pesos, sin_costo=0.0):
    return {"bultos": bultos, "mercaderia": mercaderia, "cajas": cajas,
            "caja_pesos": caja_pesos, "bultos_sin_costo": sin_costo,
            "total": mercaderia + caja_pesos}


# LOS DOS DESTINOS CON PLATA Y UN ARTÍCULO SIN COSTEAR. El `sin_costo` está
# puesto a propósito: es lo que distingue un total que cubre todo de uno que
# se comió bultos en silencio, y este número va a un estado de resultados.
PERDIDAS = {
    "desde": date(2026, 9, 12), "hasta": date(2026, 9, 19),
    "renglones": {
        "merma": _renglon(10.0, 2000.0, 2.0, 100.0, sin_costo=3.0),
        "segunda": _renglon(3.0, 900.0, 3.0, 150.0),
    },
    "detalle": [
        {"destino": "merma", "articulo_id": 1, "articulo": "EJEMPLO Tomate",
         **_renglon(10.0, 2000.0, 2.0, 100.0, sin_costo=3.0)},
        {"destino": "segunda", "articulo_id": 1, "articulo": "EJEMPLO Berenjena",
         **_renglon(3.0, 900.0, 3.0, 150.0)},
    ],
    "total": 3150.0,
    "bultos_sin_costo": 3.0,
}

# TODO EN CERO menos la merma: el renglón de segunda tiene que dibujarse
# IGUAL. Si desapareciera, "no hubo segunda" y "esta pantalla no cuenta la
# segunda" se verían iguales.
SOLO_MERMA = dict(
    PERDIDAS,
    renglones={"merma": _renglon(4.0, 400.0, 0.0, 0.0),
               "segunda": _renglon(0.0, 0.0, 0.0, 0.0)},
    detalle=[{"destino": "merma", "articulo_id": 1, "articulo": "EJEMPLO Tomate",
              **_renglon(4.0, 400.0, 0.0, 0.0)}],
    total=400.0, bultos_sin_costo=0.0,
)


@contextlib.contextmanager
def _con_clave_de_gerencia(con_cookie=True):
    """La clave PUESTA en el entorno, y la cookie según lo que se quiera probar.

    Sin la primera mitad el test no prueba nada: `PUERTA_GERENCIA.abierta()`
    devuelve True cuando no hay clave configurada, así que en la suite la
    puerta está abierta y cualquier request entra.
    """
    from app.main import _firma_acceso_gerencia

    with patch.dict(os.environ, {"CLAVE_GERENCIA": "secreta"}):
        c = TestClient(app, base_url="https://testserver")
        if con_cookie:
            c.cookies.set("acceso_gerencia", _firma_acceso_gerencia("secreta"))
        yield c


def _marcado(query="", resultado=PERDIDAS):
    with _con_clave_de_gerencia() as c, \
         patch("app.main.perdidas_por_periodo", return_value=resultado):
        return c.get("/gerencia/perdidas" + query).text.split("</style>")[-1]


def test_perdidas_PIDE_LA_CLAVE_de_gerencia():
    """Es plata, y vive detrás de la misma puerta que Rentabilidad."""
    with _con_clave_de_gerencia(con_cookie=False) as c:
        respuesta = c.get("/gerencia/perdidas")
    # Lo que SÍ tiene que pasar, no un `!= 200`: un 500 tampoco es 200, así
    # que un assert por la negativa pasa igual con la puerta sacada y el
    # código reventando contra la base (corolario 91).
    assert "clave" in respuesta.text.lower()
    assert "EJEMPLO" not in respuesta.text


def test_perdidas_le_pasa_a_la_cuenta_LAS_DOS_FECHAS_del_filtro():
    """Se afirma sobre la LLAMADA y no sobre el número dibujado: el número lo
    decide el mock, así que un `hasta` que no viajara se vería igual.
    """
    with _con_clave_de_gerencia() as c, \
         patch("app.main.perdidas_por_periodo", return_value=PERDIDAS) as cuenta:
        respuesta = c.get("/gerencia/perdidas?fecha_desde=2026-09-01&fecha_hasta=2026-09-10")
    assert respuesta.status_code == 200
    assert cuenta.call_args.args == (date(2026, 9, 1), date(2026, 9, 10))


def test_perdidas_muestra_EL_TOTAL_Y_SU_VENTANA_pegados():
    """Un total sin el recorte al lado contesta otra pregunta (corolario 69),
    y éste va a un estado de resultados: el que lo cite después no va a volver
    a buscar de qué días era.
    """
    marcado = _marcado("?fecha_desde=2026-09-12&fecha_hasta=2026-09-19")
    assert "3.150" in marcado
    assert "2026-09-12" in marcado and "2026-09-19" in marcado


def test_perdidas_dibuja_LOS_DOS_RENGLONES_aunque_uno_este_en_CERO():
    """Un destino que desaparece cuando no tuvo nada deja al otro solo, y ahí
    "no hubo mermas" y "esta pantalla no cuenta las mermas" se ven igual.

    SE CUENTA, no se pregunta con un `in`: el rótulo "Se tiró" aparece también
    en cada renglón del detalle, así que un `in` contesta por el hermano más
    suertudo y pasaría con UNO solo de los dos dibujados.
    """
    marcado = _marcado(resultado=SOLO_MERMA)
    assert marcado.count('data-destino="merma"') == 1
    assert marcado.count('data-destino="segunda"') == 1
    assert "Pasó a segunda" in marcado


def test_perdidas_muestra_LA_CAJA_de_cada_destino_aunque_sea_CERO():
    """La caja es la MITAD de la regla, así que su cero es información: dice
    que ese destino fue todo mercadería suelta.

    Escondiéndola, un renglón sin caja se ve igual que uno al que se le
    olvidó contarla — que es exactamente el canario de la rama.
    """
    # EL FRAGMENTO ENTERO, no "2 cajas" suelto: el conteo y su plata viajan
    # pegados en la misma pata, y un assert partido pasa con la plata del
    # vecino (corolario 4 — calificar hasta que solo pueda matchear esto).
    marcado = _marcado()
    assert '2 cajas <span class="plata">$100</span>' in marcado      # la merma
    assert '3 cajas <span class="plata">$150</span>' in marcado      # la segunda

    cero = _marcado(resultado=SOLO_MERMA)
    assert '0 cajas <span class="plata">$0</span>' in cero, (
        "el cero de la caja no se dibuja")


def test_perdidas_muestra_LO_QUE_NO_SE_PUDO_COSTEAR_y_dice_que_no_suma():
    """Un total que se come bultos sin precio en silencio es más chico y se
    lee igual de cerrado (corolario 45: el denominador al lado del número).
    """
    marcado = _marcado()
    assert "3 bultos" in marcado
    assert "sin costo cargado" in marcado
    assert "no suman pesos" in marcado

    limpio = _marcado(resultado=SOLO_MERMA)
    # EL ANCLA POSITIVA PRIMERO: un `not in` sobre un recorte que se llevó la
    # pantalla entera pasa siempre (corolario 50), y ese es justo el modo de
    # falla que un assert por la negativa no puede distinguir de estar bien.
    assert 'data-destino="merma"' in limpio
    assert "sin costo cargado" not in limpio, (
        "el aviso se dibuja siempre: un cartel que sale en todas las pantallas "
        "no distingue la que tiene el problema")


def test_perdidas_dice_que_NO_SE_SUMA_con_Plata_de_cajas():
    """Las dos muestran plata de la MISMA caja contestando dos preguntas
    distintas —allá por cliente para reclamarla, acá por destino para el
    resultado— y el que las sume la cuenta dos veces.
    """
    marcado = _marcado()
    assert "no se suma" in marcado.lower()
    assert "Plata de cajas" in marcado


def test_perdidas_lista_el_DETALLE_por_articulo_en_el_ORDEN_que_le_llega():
    """Ordenado por plata, que es lo que lo vuelve una lista de trabajo: por
    nombre habría que leerla entera para encontrar los dos que importan.
    """
    marcado = _marcado()
    assert marcado.index("EJEMPLO Tomate") < marcado.index("EJEMPLO Berenjena")


def test_perdidas_VACIO_dice_CUAL_vacio_es():
    """"No hubo" y "no se miró" se dibujan igual si la pantalla se calla, y
    con un rango elegido a mano el segundo caso es el más probable.
    """
    vacio = dict(PERDIDAS, detalle=[], total=0.0, bultos_sin_costo=0.0,
                 renglones={"merma": _renglon(0.0, 0.0, 0.0, 0.0),
                            "segunda": _renglon(0.0, 0.0, 0.0, 0.0)})
    marcado = _marcado("?fecha_desde=2026-09-01&fecha_hasta=2026-09-02", vacio)
    assert "No se tiró ni pasó a segunda nada" in marcado
    assert "revisá el rango de fechas" in marcado


def test_perdidas_con_FECHA_INVALIDA_no_le_pregunta_nada_a_la_base():
    """El error se muestra y la cuenta NO se corre con un rango sin validar."""
    with _con_clave_de_gerencia() as c, \
         patch("app.main.perdidas_por_periodo") as cuenta:
        marcado = c.get("/gerencia/perdidas?fecha_desde=2026-13-99").text.split("</style>")[-1]
    assert "no es válida" in marcado
    assert cuenta.call_count == 0


def test_el_HUB_de_gerencia_LINKEA_perdidas():
    """Una ruta sin botón no existe (corolario 31), y ningún test de los de
    arriba puede verlo: todos entran por la URL.
    """
    with _con_clave_de_gerencia() as c:
        marcado = c.get("/gerencia").text.split("</style>")[-1]
    assert 'href="/gerencia/perdidas"' in marcado


def test_el_RANGO_de_Perdidas_y_el_de_Cajas_Perdidas_son_LA_MISMA_funcion():
    """Escrito dos veces se separa, y la copia que quede vieja acepta un rango
    que la otra rechaza sin que nada se ponga rojo.

    Se pregunta por la LLAMADA en el árbol y no por el nombre suelto: el
    docstring de la ruta nombra a las dos pantallas, así que un `in` sobre el
    texto matchea la prosa (corolario 59).
    """
    arbol = ast.parse(io.open("app/main.py", encoding="utf-8").read())
    rutas = {n.name: n for n in ast.walk(arbol)
             if isinstance(n, ast.FunctionDef) and n.name in
             ("ver_perdidas", "ver_cajas_perdidas")}
    assert set(rutas) == {"ver_perdidas", "ver_cajas_perdidas"}, rutas

    for nombre, nodo in rutas.items():
        llamadas = {c.func.id for c in ast.walk(nodo)
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        assert "_leer_rango_de_fechas" in llamadas, (
            f"{nombre} resuelve el rango por su cuenta: son dos reglas")
