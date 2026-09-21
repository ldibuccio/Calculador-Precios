"""La aritmética de "Qué comprar hoy": el divisor fijo y la resta en magnitud.

Los dos tests que importan son los que PLANTAN EL RIVAL: la versión
equivocada de cada decisión da un número distinto y plausible, así que sin
el rival adentro del fixture cualquiera de las dos se "simplifica" sin que
caiga nada.
"""
import pytest

from core.que_comprar import (
    MARGEN_SUGERIDO,
    PEDIDOS_DEL_PROMEDIO,
    cajones_que_faltan,
    con_margen,
    falta_por_comprar,
    margen_valido,
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

    A comprar = techo((1440 − 320) / 18) = techo(62,2) = 63. Si después
    compra 40 cajones DE 16 —que es lo que encontró en el Mercado— esos 40
    no son 40 de los suyos: son 640 de magnitud, no 720.

    En magnitud quedan techo(480 / 18) = 27 por comprar. Restando cajones
    contra cajones darían 23, y ese 23 supone que todos los cajones miden lo
    mismo — que es exactamente lo que el kilaje editable existe para negar.
    """
    pide, piso, kilaje_de_la_fila = 1440.0, 320.0, 18.0
    compro_cajones, kilaje_de_lo_comprado = 40.0, 16.0

    a_comprar = cajones_que_faltan(falta_por_comprar(pide, piso, 0.0), kilaje_de_la_fila)
    assert a_comprar == 63

    comprado_en_magnitud = compro_cajones * kilaje_de_lo_comprado
    falta = falta_por_comprar(pide, piso, comprado_en_magnitud)
    assert falta == 480.0
    assert cajones_que_faltan(falta, kilaje_de_la_fila) == 27

    # El rival: la resta en cajones. Da 23 y está mal.
    assert a_comprar - compro_cajones == 23


def test_el_redondeo_es_PARA_ARRIBA_y_el_rival_es_el_que_redondea_al_MAS_CERCANO():
    """Del dueño (21/09): "quedarse corto es peor que sobrar un cajón".

    1120 contra cajones de 18 dan 62,2. El rival —redondear— da 62, que son
    1116: cuatro kilos cortos, y el caso es al revés de lo que se piensa
    (la parte decimal chica es la que el redondeo se come).
    """
    assert cajones_que_faltan(1120.0, 18.0) == 63
    assert round(1120.0 / 18.0) == 62  # el rival, escrito para que se vea

    # Y EL CASO QUE NO TIENE QUE CRECER, sin el cual un techo que siempre
    # suma uno pasaría igual: 1120 en cajones de 16 son 70 exactos.
    assert cajones_que_faltan(1120.0, 16.0) == 70

    # Un entero y no un float con coma: no se puede comprar medio cajón, y un
    # número que se redondea recién al mostrarlo son dos reglas.
    assert isinstance(cajones_que_faltan(1120.0, 18.0), int)


def test_el_MARGEN_va_sobre_el_PEDIDO_y_no_sobre_el_faltante():
    """El rival da 110 donde lo que va son 200, y los dos son plausibles.

    1000 pedidos, 900 en el piso, 10%:
      sobre el pedido    1100 − 900 = 200   <- el que va
      sobre el faltante  (1000 − 900) × 1,1 = 110

    El margen existe porque lo que se va a VENDER es incierto; el piso no
    —está contado—. Aplicarlo al faltante cubre dos veces la parte que ya se
    tiene, y encima se ve como una cuenta cerrada.
    """
    pide, piso = 1000.0, 900.0

    assert falta_por_comprar(con_margen(pide, 10), piso, 0.0) == 200.0
    # El rival, escrito para que se vea que NO es el que va:
    assert round(falta_por_comprar(pide, piso, 0.0) * 1.1) == 110


def test_el_margen_en_CERO_deja_la_cuenta_como_si_no_estuviera():
    """Cero es "sin margen" y tiene que ser inocuo, no un 1% escondido."""
    assert con_margen(280.0, 0) == 280.0
    assert con_margen(280.0, None) == 280.0
    assert con_margen(None, 10) is None


def test_CERO_NO_ES_VACIO_al_leer_el_margen_de_la_URL():
    """El rival es un `or MARGEN_SUGERIDO`: con 0 tipeado devolvería 10.

    El que escribe 0 está diciendo "sin margen", y cambiárselo por el
    sugerido le haría comprar de más sin que nada se lo diga.
    """
    assert margen_valido("0") == 0.0
    assert margen_valido("") == MARGEN_SUGERIDO
    assert margen_valido(None) == MARGEN_SUGERIDO
    assert margen_valido("12,5") == 12.5          # el celular escribe con coma
    assert margen_valido("diez") == MARGEN_SUGERIDO
    assert margen_valido("-5") == MARGEN_SUGERIDO  # comprar MENOS no es este campo


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
        margen=0,
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
        margen=0,
    )
    assert filas[0]["pide"] == 320.0
    assert filas[0]["pide"] != 240.0


def test_UN_cliente_sin_contenido_de_caja_deja_la_fila_ENTERA_sin_numero():
    """Mostrar la suma de los demas diria que ese cliente no pide nada."""
    filas = _filas_de_que_comprar(
        [_renglon(1, bultos=60), _renglon(2, bultos=30, contenido=None)],
        piso={1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}},
        comprado={},
        margen=0,
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
        margen=0,
    )
    assert filas[0]["en_piso"] is None
    assert filas[0]["falta"] is None


def test_sin_compras_de_hoy_el_aporte_es_CERO_y_no_un_hueco():
    """Que no haya comprado nada es un hecho, no un dato que falte."""
    filas = _filas_de_que_comprar(
        [_renglon(1)], piso={1: {"magnitud": 0.0, "sueltos": 0, "cajas": 0}}, comprado={},
        margen=0,
    )
    assert filas[0]["comprado"] == 0.0
    assert filas[0]["falta"] == 160.0


def test_el_MARGEN_de_la_pantalla_llega_hasta_la_FILA():
    """Sin esto el campo se mueve y los números no, que es peor que no tenerlo.

    Piden 240 por día y hay 40 en el piso. Sin margen faltan 200; al 10% el
    objetivo es 264 y faltan 224. En cajones de 18: 12 contra 13.
    """
    fixture = ([_renglon(1, bultos=60), _renglon(2, bultos=30)],)
    piso = {1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}}

    sin_margen = _filas_de_que_comprar(*fixture, piso=piso, comprado={}, margen=0)
    con_10 = _filas_de_que_comprar(*fixture, piso=piso, comprado={}, margen=10)

    # Lo que PIDEN no lo mueve el margen: es el dato del cliente, no una meta.
    assert sin_margen[0]["pide"] == con_10[0]["pide"] == 240.0
    assert sin_margen[0]["falta"] == 200.0
    assert con_10[0]["falta"] == 224.0
    assert sin_margen[0]["cajones"] == 12
    assert con_10[0]["cajones"] == 13


def test_la_fila_lleva_YA_TENGO_sumado_para_que_el_navegador_no_lo_arme():
    """El JS rehace la resta al mover el margen, y necesita UN número.

    Sumar el piso y lo comprado en el navegador sería la única parte de la
    cuenta que necesita saber de fichas y de lotes, escrita dos veces.
    """
    filas = _filas_de_que_comprar(
        [_renglon(1, bultos=60)],
        piso={1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}},
        comprado={1: {"cajones": 2.0, "kilos": 32.0, "conteo": None}},
        margen=0,
    )
    assert filas[0]["ya_tengo"] == 72.0
    assert filas[0]["falta"] == 160.0 - 72.0


def test_un_hueco_en_el_piso_deja_YA_TENGO_en_None_y_no_en_lo_comprado_solo():
    """Un 32 ahí diría "tengo 32" cuando lo que pasa es que no se sabe."""
    filas = _filas_de_que_comprar(
        [_renglon(1)],
        piso={1: {"magnitud": None, "sueltos": 5, "cajas": 0}},
        comprado={1: {"cajones": 2.0, "kilos": 32.0, "conteo": None}},
        margen=0,
    )
    assert filas[0]["ya_tengo"] is None
