"""La aritmética de "Qué comprar hoy": el divisor fijo y la resta en magnitud.

Los dos tests que importan son los que PLANTAN EL RIVAL: la versión
equivocada de cada decisión da un número distinto y plausible, así que sin
el rival adentro del fixture cualquiera de las dos se "simplifica" sin que
caiga nada.
"""
import pytest

from core.que_comprar import (
    PEDIDOS_DEL_PROMEDIO,
    cajones_que_faltan,
    falta_por_comprar,
    promedio_de_un_dia,
)


def test_el_divisor_es_FIJO_y_no_los_dias_en_que_el_articulo_aparecio():
    """El rival: 300 pedidos en 2 de 6 días. /6 da 50, /apariciones daría 150.

    Es la decisión del dueño del 21/09 y la diferencia es 3x, no de
    redondeo: "si Día pidió tomate en 2 de 6 pedidos, comprar el promedio de
    esos 2 me deja con tomate los otros 4 días".
    """
    total_de_los_6_pedidos = 300.0
    aparecio_en = 2

    assert promedio_de_un_dia(total_de_los_6_pedidos) == 50.0
    # El rival, escrito para que se vea que NO es el que va:
    assert total_de_los_6_pedidos / aparecio_en == 150.0


def test_el_divisor_sale_de_la_CONSTANTE_y_no_de_un_6_tipeado():
    """Moverla tiene que mover el resultado, o el número está suelto."""
    assert PEDIDOS_DEL_PROMEDIO == 6
    assert promedio_de_un_dia(300.0, pedidos=3) == 100.0
    assert promedio_de_un_dia(300.0) == 300.0 / PEDIDOS_DEL_PROMEDIO


def test_la_RESTA_VA_EN_MAGNITUD_y_restar_cajones_da_otro_numero():
    """El rival: 40 cajones de 16 contra una fila de 18.

    A comprar = (1440 − 320) / 18 = 62,2 cajones. Si después compra 40
    cajones DE 16 —que es lo que encontró en el Mercado— esos 40 no son 40
    de los suyos: son 640 de magnitud, no 720.

    En magnitud quedan 26,7 cajones por comprar. Restando cajones contra
    cajones darían 22, y ese 22 supone que todos los cajones miden lo mismo
    — que es exactamente lo que el kilaje editable existe para negar.
    """
    pide, piso, kilaje_de_la_fila = 1440.0, 320.0, 18.0
    compro_cajones, kilaje_de_lo_comprado = 40.0, 16.0

    a_comprar = cajones_que_faltan(falta_por_comprar(pide, piso, 0.0), kilaje_de_la_fila)
    assert round(a_comprar, 1) == 62.2

    comprado_en_magnitud = compro_cajones * kilaje_de_lo_comprado
    falta = falta_por_comprar(pide, piso, comprado_en_magnitud)
    assert falta == 480.0
    assert round(cajones_que_faltan(falta, kilaje_de_la_fila), 1) == 26.7

    # El rival: la resta en cajones. Da 22 y está mal.
    assert round(a_comprar - compro_cajones) == 22


def test_comprar_de_mas_da_CERO_y_no_un_negativo():
    """"Si compré de más, dice OK" — el piso es por FILA."""
    assert falta_por_comprar(280.0, 40.0, 500.0) == 0.0
    assert cajones_que_faltan(falta_por_comprar(280.0, 40.0, 500.0), 10.0) == 0.0


@pytest.mark.parametrize(
    "pide, piso, comprado",
    [(None, 320.0, 0.0), (1440.0, None, 0.0), (1440.0, 320.0, None)],
)
def test_un_HUECO_en_cualquiera_de_los_tres_deja_la_fila_SIN_NUMERO(pide, piso, comprado):
    """No se sabe cuánto hay en el piso -> no se sabe cuánto falta.

    Devolver el pedido entero sería comprar de más con cara de cuenta
    cerrada. El piso no siempre se puede decir: `_pilas_cierran` devuelve
    vacío cuando el desglose por kilaje no suma el total.
    """
    assert falta_por_comprar(pide, piso, comprado) is None


def test_sin_kilaje_no_hay_cajones_que_decir():
    """Mango viene en 40, 12 y 10: sin valor dominante el campo va vacío."""
    assert cajones_que_faltan(1120.0, None) is None
    assert cajones_que_faltan(1120.0, 0) is None
    assert promedio_de_un_dia(None) is None


# --- El armado de las filas, llamado DIRECTO ---------------------------------
#
# Sin mocks: `_filas_de_que_comprar` es pura y recibe lo que las tres
# consultas devuelven. Parchearla para probarla seria tapar exactamente la
# linea que se quiere mirar.

from app.main import _filas_de_que_comprar  # noqa: E402


def _renglon(cliente_id, nombre="TOMATE", bultos=60, contenido=16, pedidos=6, unidad="kilo"):
    return {
        "cliente_id": cliente_id, "articulo_id": 1, "articulo_nombre": nombre,
        "unidad_conteo": None, "contenido_referencia": 18, "ficha_id": cliente_id,
        "contenido_caja": contenido, "unidad_venta": unidad,
        "bultos": bultos, "pedidos_del_cliente": pedidos,
    }


def test_la_fila_SUMA_el_mismo_articulo_entre_clientes_distintos():
    """Es el corazon del diseno: nadie suma Mango con Cherry, pero el tomate
    de Dia y el de Tailem son la misma fila.

    Dia: 60 bultos x 16 / 6 pedidos = 160 por dia.
    Tailem: 30 bultos x 16 / 6 = 80 por dia. La fila pide 240.
    """
    filas = _filas_de_que_comprar(
        [_renglon(1, bultos=60), _renglon(2, bultos=30)],
        piso={1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}},
        comprado={},
    )
    assert len(filas) == 1
    assert filas[0]["pide"] == 240.0
    assert filas[0]["falta"] == 200.0


def test_cada_cliente_se_divide_por_SU_propio_numero_de_pedidos():
    """Uno con 3 pedidos en su historia no se divide por 6.

    Sumar primero y dividir despues daria (60x16 + 30x16)/6 = 240. Con el
    divisor por cliente: 160 + 160 = 320.
    """
    filas = _filas_de_que_comprar(
        [_renglon(1, bultos=60, pedidos=6), _renglon(2, bultos=30, pedidos=3)],
        piso={1: {"magnitud": 0.0, "sueltos": 0, "cajas": 0}},
        comprado={},
    )
    assert filas[0]["pide"] == 320.0
    assert filas[0]["pide"] != 240.0


def test_UN_cliente_sin_contenido_de_caja_deja_la_fila_ENTERA_sin_numero():
    """Mostrar la suma de los demas diria que ese cliente no pide nada."""
    filas = _filas_de_que_comprar(
        [_renglon(1, bultos=60), _renglon(2, bultos=30, contenido=None)],
        piso={1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}},
        comprado={},
    )
    assert filas[0]["pide"] is None
    assert filas[0]["falta"] is None
    assert filas[0]["cajones"] is None


def test_un_piso_que_NO_CIERRA_deja_la_fila_sin_numero_y_no_en_cero():
    """Un cero diria "no hay nada en el piso" y haria comprar de mas."""
    filas = _filas_de_que_comprar(
        [_renglon(1)],
        piso={1: {"magnitud": None, "sueltos": 5, "cajas": 0}},
        comprado={},
    )
    assert filas[0]["en_piso"] is None
    assert filas[0]["falta"] is None


def test_sin_compras_de_hoy_el_aporte_es_CERO_y_no_un_hueco():
    """Que no haya comprado nada es un hecho, no un dato que falte."""
    filas = _filas_de_que_comprar(
        [_renglon(1)], piso={1: {"magnitud": 0.0, "sueltos": 0, "cajas": 0}}, comprado={}
    )
    assert filas[0]["comprado"] == 0.0
    assert filas[0]["falta"] == 160.0
