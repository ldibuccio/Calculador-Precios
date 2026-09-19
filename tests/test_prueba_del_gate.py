"""Prueba del gate: este test FALLA A PROPOSITO.

Existe para confirmar que el CI en rojo deja el deploy de Railway en
"waiting" en vez de desplegar. Se pushea, se mira que Railway NO despliegue,
y se revierte. No tiene que quedar en main.

Va en un archivo de TESTS y no toca una sola linea de produccion: si el
"Wait for CI" fallara y Railway desplegara igual, lo desplegado es
identico a lo que hay hoy.
"""


def test_ESTE_TEST_FALLA_A_PROPOSITO_para_probar_que_el_gate_frena():
    assert False, "falla a proposito: prueba del gate, se revierte enseguida"
