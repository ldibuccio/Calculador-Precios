"""La aritmética de "Qué comprar hoy": el divisor fijo y la resta en magnitud.

Los dos tests que importan son los que PLANTAN EL RIVAL: la versión
equivocada de cada decisión da un número distinto y plausible, así que sin
el rival adentro del fixture cualquiera de las dos se "simplifica" sin que
caiga nada.
"""
from datetime import date

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


# --- LO QUE PIDE UNA CARGA: la regla de las dos pantallas --------------------

from core.que_comprar import lo_que_pide_la_carga  # noqa: E402


def test_el_margen_de_la_carga_va_SOLO_sobre_lo_PROPUESTO():
    """Decisión del dueño (23/09): lo corregido y lo tipeado ya es lo que se
    compra, y entra tal cual.

    El rival es inflar todo: lo corregido se corrige MIRANDO la propuesta que
    ya tiene el margen, así que inflarlo de nuevo le cobra el margen dos
    veces. Con 10%: el tomate propuesto 100 va a 110, la lima corregida a 50
    se queda en 50 — el rival diría 55.
    """
    pide = lo_que_pide_la_carga({2: 50.0}, {1: 100.0, 2: 80.0}, 10)
    assert pide == {1: pytest.approx(110.0), 2: 50.0}
    assert pide[2] != pytest.approx(55.0)


def test_lo_GUARDADO_le_gana_a_lo_propuesto_y_lo_que_no_se_toco_se_propone():
    """Es la distinción que hace que "del promedio" signifique algo: lo que
    no se tocó se vuelve a calcular, lo corregido queda fijo."""
    pide = lo_que_pide_la_carga({1: 7.0}, {1: 100.0, 3: 20.0}, 0)
    assert pide == {1: 7.0, 3: 20.0}


def test_A_MANO_no_tiene_propuesta_y_el_margen_no_mueve_nada():
    """En "a mano" el que llama pasa la propuesta vacía: lo tipeado entra tal
    cual con cualquier margen. Por eso la pantalla de la carga no muestra el
    campo en ese modo."""
    assert lo_que_pide_la_carga({1: 500.0}, {}, 0) == lo_que_pide_la_carga({1: 500.0}, {}, 35)



def test_los_DIAS_multiplican_SOLO_lo_propuesto_igual_que_el_margen():
    """Dueño, 23/09: "para cuántos días es la compra" multiplica el promedio
    diario. Con 3 días y 10%: el tomate propuesto 100 va a 330; la lima
    corregida a 50 se queda en 50. El RIVAL es multiplicar también lo
    corregido, que daría 150."""
    from core.que_comprar import lo_que_pide_la_carga as regla
    pide = regla({2: 50.0}, {1: 100.0, 2: 80.0}, 10, dias=3)
    assert pide == {1: pytest.approx(330.0), 2: 50.0}


def test_los_DIAS_en_None_o_basura_son_UNO_y_nunca_cero():
    from core.que_comprar import dias_validos, para_los_dias
    assert para_los_dias(100.0, None) == 100.0
    assert para_los_dias(None, 3) is None
    assert [dias_validos(x) for x in ("3", " 2 ", "", "0", "-1", "abc", None)] == \
        [3, 2, 1, 1, 1, 1, 1]

# --- El armado de las filas, llamado DIRECTO ---------------------------------
#
# Sin mocks: `_filas_de_que_comprar` es pura y recibe lo que las consultas
# devuelven. Parchearla para probarla seria tapar exactamente la linea que se
# quiere mirar.

from app.main import _filas_de_que_comprar  # noqa: E402

ARTICULOS = {1: {"id": 1, "nombre": "TOMATE", "contenido_referencia": 18},
             9: {"id": 9, "nombre": "BANANA", "contenido_referencia": 20}}
UNIDADES = {1: "kilo", 9: "kilo"}
PISO_VACIO = {1: {"magnitud": 0.0, "sueltos": 0, "cajas": 0},
              9: {"magnitud": 0.0, "sueltos": 0, "cajas": 0}}


def _aporte(etiqueta, **pide):
    return {"etiqueta": etiqueta, "pide": {int(k[1:]): v for k, v in pide.items()}}


def test_la_fila_SUMA_el_mismo_articulo_entre_CARGAS():
    """Dos fechas de Día y una de Tailem son una sola fila de tomate: el
    listado toma cargas, no clientes, y la misma estructura vieja no podía
    decir "dos días de Día"."""
    filas = _filas_de_que_comprar(
        [_aporte("Dia 26/09", a1=160.0), _aporte("Dia 27/09", a1=100.0),
         _aporte("Tailem 26/09", a1=40.0)],
        ARTICULOS, UNIDADES, piso={1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}},
        comprado={},
    )
    assert len(filas) == 1
    assert filas[0]["pide"] == 300.0
    assert filas[0]["falta"] == 260.0


def test_el_listado_NO_aplica_margen_propio():
    """El margen ya viene adentro de cada aporte. Aplicarlo de nuevo acá es
    la multiplicación que el dueño pidió que no exista: 20% y 10% son 32%.

    Sin parámetro `margen` en la firma, no hay forma de que un llamador lo
    pase — y la fila pide exactamente la suma de lo que las cargas mostraron.
    """
    import inspect
    assert "margen" not in inspect.signature(_filas_de_que_comprar).parameters
    filas = _filas_de_que_comprar([_aporte("Dia 26/09", a1=110.0)], ARTICULOS, UNIDADES,
                                  piso=PISO_VACIO, comprado={})
    assert filas[0]["pide"] == 110.0


def test_la_fila_dice_DE_QUIEN_sale_cada_parte():
    """Un total que junta tres cargas y no lo dice se lee como el pedido de
    un solo cliente."""
    filas = _filas_de_que_comprar(
        [_aporte("Dia 26/09", a1=160.0), _aporte("Tailem 26/09", a1=40.0)],
        ARTICULOS, UNIDADES, piso=PISO_VACIO, comprado={})
    assert filas[0]["de_quien"] == [("Dia 26/09", 160.0), ("Tailem 26/09", 40.0)]


def test_un_articulo_SIN_UNIDAD_deja_la_fila_sin_numero():
    """Su total está en una unidad y el piso se mediría en otra: la suma no
    descuadra nada y está mal. Un hueco visible es información."""
    filas = _filas_de_que_comprar([_aporte("Dia 26/09", a1=160.0)], ARTICULOS, {1: None},
                                  piso=PISO_VACIO, comprado={})
    assert filas[0]["pide"] is None and filas[0]["falta"] is None


def test_un_piso_que_NO_CIERRA_deja_la_fila_sin_numero_y_no_en_cero():
    """Un cero diria "no hay nada en el piso" y haria comprar de mas."""
    filas = _filas_de_que_comprar(
        [_aporte("Dia", a1=160.0)], ARTICULOS, UNIDADES,
        piso={1: {"magnitud": None, "sueltos": 5, "cajas": 0}}, comprado={})
    assert filas[0]["en_piso"] is None
    assert filas[0]["falta"] is None
    assert filas[0]["ya_tengo"] is None


def test_sin_compras_de_hoy_el_aporte_es_CERO_y_no_un_hueco():
    """Que no haya comprado nada es un hecho, no un dato que falte."""
    filas = _filas_de_que_comprar([_aporte("Dia", a1=160.0)], ARTICULOS, UNIDADES,
                                  piso=PISO_VACIO, comprado={})
    assert filas[0]["comprado"] == 0.0
    assert filas[0]["falta"] == 160.0


def test_la_fila_lleva_YA_TENGO_sumado_para_que_el_navegador_no_lo_arme():
    """El JS rehace la resta al mover el kilaje, y necesita UN número."""
    filas = _filas_de_que_comprar(
        [_aporte("Dia", a1=160.0)], ARTICULOS, UNIDADES,
        piso={1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}},
        comprado={1: {"cajones": 2.0, "kilos": 32.0, "conteo": None}})
    assert filas[0]["ya_tengo"] == 72.0
    assert filas[0]["falta"] == 160.0 - 72.0


def test_lo_comprado_se_lee_en_la_MAGNITUD_de_la_fila():
    """Un artículo que se cuenta resta lo CONTADO, no los kilos. El rival
    —restar siempre kilos— da otro número y plausible."""
    filas = _filas_de_que_comprar(
        [_aporte("Dia", a1=100.0)], ARTICULOS, {1: "unidad"}, piso=PISO_VACIO,
        comprado={1: {"cajones": 1.0, "kilos": 16.0, "conteo": 40.0}})
    assert filas[0]["comprado"] == 40.0
    assert filas[0]["falta"] == 60.0


def test_el_KILAJE_GUARDADO_le_gana_a_la_referencia_del_articulo():
    """Y solo esta el del articulo que el comprador TOCO."""
    sin_guardar = _filas_de_que_comprar([_aporte("Dia", a1=160.0)], ARTICULOS, UNIDADES,
                                        piso=PISO_VACIO, comprado={})
    guardado = _filas_de_que_comprar([_aporte("Dia", a1=160.0)], ARTICULOS, UNIDADES,
                                     piso=PISO_VACIO, comprado={}, kilajes={1: 10.0})
    assert sin_guardar[0]["kilaje"] == 18.0   # la referencia del articulo
    assert guardado[0]["kilaje"] == 10.0
    assert guardado[0]["cajones"] == 16       # 160 / 10
    assert sin_guardar[0]["cajones"] == 9     # 160 / 18 = 8,9 -> techo 9


# --- EL GUARDADO: el POST y lo que llega a la base ----------------------------

from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

import app.main as _main  # noqa: E402

_cliente = TestClient(_main.app)
_cliente.cookies.set(_main.PUERTA_COMPRAS.cookie, _main.PUERTA_COMPRAS.firma("compras-secreta"))


def _postear(datos):
    import os
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}), \
         patch("app.main.guardar_borrador_de_compra") as guardar:
        respuesta = _cliente.post("/compras/que-comprar", data=datos, follow_redirects=False)
    return respuesta, guardar


def test_el_POST_guarda_las_CARGAS_tildadas_y_REDIRIGE():
    """POST-redirect-GET: recargar despues de guardar no vuelve a guardar."""
    respuesta, guardar = _postear({"accion": "guardar", "carga": ["3", "5"]})
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/que-comprar"
    assert guardar.call_args.args[1] == {3, 5}


def test_el_POST_ignora_un_MARGEN_que_llegue():
    """El margen se fue del listado. Uno que llegue por un formulario viejo o
    armado a mano no puede colarse en ningún lado."""
    _, guardar = _postear({"accion": "guardar", "carga": ["3"], "margen": "20"})
    assert len(guardar.call_args.args) == 3
    assert 20.0 not in guardar.call_args.args


def test_un_kilaje_VACIO_o_en_cero_no_se_guarda():
    """El CHECK de la base es `> 0`, y un cajon de cero kilos no existe."""
    _, guardar = _postear({"accion": "guardar", "carga": ["3"],
                           "kilaje_1": "", "kilaje_2": "0", "kilaje_3": "18,5"})
    assert guardar.call_args.args[2] == {3: 18.5}   # la coma del celular entra


def test_CERRAR_no_guarda_nada_y_es_otra_accion():
    """El rival: cerrar guardando lo que haya en pantalla."""
    import os
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}), \
         patch("app.main.guardar_borrador_de_compra") as guardar, \
         patch("app.main.cerrar_borrador_de_compra") as cerrar:
        respuesta = _cliente.post("/compras/que-comprar", data={"accion": "cerrar"},
                                  follow_redirects=False)
    assert respuesta.status_code == 303
    assert cerrar.called and not guardar.called


def test_SALGO_A_COMPRAR_guarda_PRIMERO_y_saca_la_foto_de_TODO_el_catalogo():
    """El que tildó una carga y apretó directo "Salgo" no puede perder el
    tilde. Y la foto es de todo el catálogo: se puede tildar otra carga
    después de salir, y de un artículo que no está en la foto no se sabe
    qué había."""
    import os
    orden = []
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}), \
         patch("app.main.guardar_borrador_de_compra", return_value=77,
               side_effect=lambda *a: orden.append("guardar") or 77) as guardar, \
         patch("app.main.listar_articulos", return_value=[{"id": 9}, {"id": 1}]), \
         patch("app.main._foto_del_stock", return_value={"sueltos": {}, "cajas": {}}) as foto, \
         patch("app.main.salir_a_comprar",
               side_effect=lambda *a: orden.append("salir")) as salir:
        respuesta = _cliente.post("/compras/que-comprar", data={"accion": "salgo", "carga": ["3"]},
                                  follow_redirects=False)
    assert respuesta.headers["location"] == "/compras/que-comprar"
    assert orden == ["guardar", "salir"]
    assert guardar.call_args.args[1] == {3}
    assert foto.call_args.args[0] == [1, 9]
    assert salir.call_args.args[0] == 77


def test_GUARDAR_no_saca_la_foto():
    """El rival: sacarla en cada guardado, que movería el punto de partida
    cada vez que se toca un kilaje parado en el Mercado."""
    import os
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}), \
         patch("app.main.guardar_borrador_de_compra", return_value=77), \
         patch("app.main.salir_a_comprar") as salir:
        _cliente.post("/compras/que-comprar", data={"accion": "guardar"}, follow_redirects=False)
    assert not salir.called


def test_si_la_FOTO_FALLA_la_pantalla_LO_DICE():
    """Hasta el 23/09 el `?error=` se escribía y nadie lo leía. Con la foto
    es caro: el comprador sale creyendo que el stock quedó fijo."""
    import os
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}), \
         patch("app.main.guardar_borrador_de_compra", return_value=77), \
         patch("app.main.listar_articulos", return_value=[]), \
         patch("app.main._foto_del_stock", side_effect=RuntimeError("se cayó la base")):
        respuesta = _cliente.post("/compras/que-comprar", data={"accion": "salgo"},
                                  follow_redirects=False)
    assert respuesta.headers["location"] == "/compras/que-comprar?error=salgo"
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}), \
         patch("app.main.borrador_de_compra", return_value=None), \
         patch("app.main.listar_cargas_desde", return_value=[]):
        texto = _cliente.get("/compras/que-comprar?error=salgo").text.split("</style>")[-1]
    assert "NO se pudo sacar la foto del stock" in texto


# --- EL GUARDADO CONTRA LA BASE ----------------------------------------------


def _cuerpo(funcion):
    import inspect
    return inspect.getsource(funcion)


def test_las_DOS_tablas_hijas_se_REEMPLAZAN_y_no_se_mezclan():
    """Destildar una carga o borrar un kilaje son operaciones que un
    `upsert` no puede expresar: lo que ya no esta tiene que IRSE."""
    from app.db import guardar_borrador_de_compra
    cuerpo = _cuerpo(guardar_borrador_de_compra)
    for tabla in ("listados_compra_kilaje", "listados_compra_cargas"):
        assert f"DELETE FROM {tabla} WHERE listado_id" in cuerpo


def test_el_borrador_ya_no_nombra_las_tablas_VIEJAS_ni_el_margen():
    """Las dos tablas viejas se dropean DESPUÉS del deploy: un lector que las
    siga nombrando revienta ese día, no antes. Y el margen del listado se va
    en el mismo bloque."""
    from app.db import borrador_de_compra, guardar_borrador_de_compra
    for funcion in (borrador_de_compra, guardar_borrador_de_compra):
        cuerpo = _cuerpo(funcion).split('"""', 2)[-1]   # sin el docstring
        assert "listados_compra_clientes" not in cuerpo
        assert "listados_compra_manual" not in cuerpo
        assert "margen_porcentaje" not in cuerpo


def test_el_borrador_se_lee_SOLO_el_que_esta_en_BORRADOR():
    """Un listado cerrado es historial."""
    from app.db import borrador_de_compra, cerrar_borrador_de_compra
    assert "estado = 'borrador'" in _cuerpo(borrador_de_compra)
    assert "estado = 'borrador'" in _cuerpo(cerrar_borrador_de_compra)


def _render(contexto):
    import os
    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}), \
         patch("app.main._contexto_de_que_comprar", return_value=contexto):
        return _cliente.get("/compras/que-comprar").text


def _fila(articulo_id, nombre):
    return {"articulo_id": articulo_id, "nombre": nombre, "sufijo": "k", "pide": 240.0,
            "de_quien": [("Dia 26/09", 240.0)], "ya_tengo": 40.0, "en_piso": 40.0,
            "sueltos": 2, "cajas": 0, "comprado_cajones": 0.0, "comprado": 0.0,
            "kilaje": 18.0, "falta": 200.0, "cajones": 12,
            "a_comprar": 12, "pide_bultos": 13.3, "stock_bultos": 2.2, "palabra": "kg",
            "de_partida": 40.0, "en_camino": 0.0, "en_camino_cajones": 0.0,
            "a_comprar_magnitud": 200.0}


def _contexto(filas=(), cargas=(), elegidas=(), salio_el=None, viejas=()):
    from app.main import _cargas_por_cliente
    return {"barra_sector": "compras", "barra_titulo": "Qué comprar hoy",
            "clientes": _cargas_por_cliente(list(cargas)), "elegidas": set(elegidas),
            "filas": list(filas), "aviso": None, "hay_borrador": True,
            "salio_el": salio_el, "viejas": list(viejas)}


def test_el_campo_del_KILAJE_lleva_su_NAME_o_lo_editado_no_LLEGA_a_guardarse():
    """Sin `name`, el input recalcula en pantalla y el navegador NO LO MANDA.
    Y el número del name tiene que ser el del artículo de ESA tarjeta."""
    import re
    marcado = _render(_contexto([_fila(3, "TOMATE"), _fila(8, "ZAPALLITO")])).split("</style>")[-1]
    tarjetas = re.findall(r'data-articulo="(\d+)"(.*?)(?=data-articulo="|\Z)', marcado, re.S)
    assert len(tarjetas) == 2                      # el denominador: se miraron las dos
    for articulo_id, tarjeta in tarjetas:
        assert f'name="kilaje_{articulo_id}"' in tarjeta


def test_la_pantalla_NO_tiene_margen_y_el_JS_no_lo_aplica():
    """La jerga que NO puede aparecer: si el campo quedó, el comprador lo
    mueve y cree que infla algo; si el JS quedó, el número salta al primer
    tecleo con un margen que el server no aplicó."""
    texto = _render(_contexto([_fila(3, "TOMATE")]))
    marcado = texto.split("</style>")[-1]
    script = texto.split("<script>")[-1]
    assert 'name="margen"' not in marcado
    assert "% más de lo que piden" not in marcado
    assert "margenActual" not in script
    assert "Math.max(pide - yaTengo, 0)" in script
    assert "Math.ceil(falta / kilaje)" in script


def test_cada_CARGA_se_ofrece_con_su_tilde_y_el_aviso_de_YA_USADA():
    """El aviso no es una traba: la carga ya usada se ofrece igual. Y el
    conteo va al lado, porque "el del 26/09" solo no dice que hay más."""
    import re
    from datetime import date
    cargas = [
        {"id": 3, "cliente_id": 1, "cliente_nombre": "EJEMPLO Uno", "fecha": date(2026, 9, 26),
         "modo": "automatico", "margen_porcentaje": 10, "usada_en_otros": 2,
         "ultimo_listado": date(2026, 9, 25)},
        {"id": 5, "cliente_id": 2, "cliente_nombre": "EJEMPLO Dos", "fecha": date(2026, 9, 27),
         "modo": "manual", "margen_porcentaje": 0, "usada_en_otros": 0,
         "ultimo_listado": None},
    ]
    marcado = _render(_contexto(cargas=cargas, elegidas={3})).split("</style>")[-1]
    # POR CARGA y no por posición: el orden lo decide el agrupado por
    # cliente, no este test (corolario 96).
    etiquetas = re.findall(r"<label>(.*?)</label>", marcado, re.S)
    assert len(etiquetas) == 2
    por_carga = {re.search(r'value="(\d+)"', e).group(1): e for e in etiquetas}
    assert "checked" in por_carga["3"]
    assert "Ya se usó en el listado del 25/09 (y 1 más)" in por_carga["3"]
    assert "checked" not in por_carga["5"]
    assert "Ya se usó" not in por_carga["5"]
    assert "a mano" in por_carga["5"]


def _carga_ofrecida(id, cliente_id, nombre, dia):
    from datetime import date
    return {"id": id, "cliente_id": cliente_id, "cliente_nombre": nombre,
            "fecha": date(2026, 9, dia), "modo": "automatico", "margen_porcentaje": 10,
            "usada_en_otros": 0, "ultimo_listado": None}


def test_las_cargas_se_AGRUPAN_por_cliente_con_sus_FECHAS_adentro():
    """Decisión del dueño (22/09): "se eligen los clientes y, de cada uno,
    qué fechas sumar".

    El RIVAL es la lista como viene de la base, ordenada por FECHA: ahí Día
    aparece dos veces separado por Tailem, y elegir "dos días de Día" es ir
    a buscar sus fechas entre las de otro. Por eso el fixture llega en ese
    orden, mezclado.
    """
    from app.main import _cargas_por_cliente
    # Tailem PRIMERO, con una fecha anterior: así llega de la base (ordenada
    # por fecha), y es el caso donde ordenar por nombre cambia algo. Con Día
    # primero, el orden de la base y el alfabético coinciden y el test no
    # puede distinguirlos (el canario dio cero con ese fixture).
    como_viene = [_carga_ofrecida(2, 8, "EJEMPLO Tailem", 25), _carga_ofrecida(1, 7, "EJEMPLO Dia", 26),
                  _carga_ofrecida(3, 7, "EJEMPLO Dia", 27)]
    bloques = _cargas_por_cliente(como_viene)
    assert [b["cliente_nombre"] for b in bloques] == ["EJEMPLO Dia", "EJEMPLO Tailem"]
    assert [c["id"] for c in bloques[0]["cargas"]] == [1, 3]
    assert [c["id"] for c in bloques[1]["cargas"]] == [2]


def test_las_fechas_de_un_cliente_van_de_la_mas_VIEJA_a_la_mas_nueva():
    """"Ayer" arriba: es la que se está comprando a la madrugada, y no se
    puede perder entre las de mañana."""
    from app.main import _cargas_por_cliente
    bloques = _cargas_por_cliente([_carga_ofrecida(9, 7, "EJEMPLO Dia", 28),
                                   _carga_ofrecida(4, 7, "EJEMPLO Dia", 25)])
    assert [c["id"] for c in bloques[0]["cargas"]] == [4, 9]


def test_la_pantalla_dibuja_UN_bloque_por_cliente_y_UN_tilde_por_fecha():
    """El denominador va al lado: dos clientes, tres tildes. Un `in` sobre la
    página pasaría con el nombre de Día dibujado una sola vez en una lista
    plana (corolario 57)."""
    import re
    cargas = [_carga_ofrecida(1, 7, "EJEMPLO Dia", 26), _carga_ofrecida(2, 8, "EJEMPLO Tailem", 26),
              _carga_ofrecida(3, 7, "EJEMPLO Dia", 27)]
    marcado = _render(_contexto(cargas=cargas, elegidas={1, 3})).split("</style>")[-1]
    bloques = re.findall(r'<div class="cliente">(.*?)</div>\s*</div>', marcado, re.S)
    assert len(bloques) == 2
    assert "EJEMPLO Dia" in bloques[0] and bloques[0].count('name="carga"') == 2
    assert "EJEMPLO Tailem" in bloques[1] and bloques[1].count('name="carga"') == 1
    assert bloques[0].count("checked") == 2 and "checked" not in bloques[1]


# --- LAS SIETE COLUMNAS Y EL STOCK CONGELADO (dueño, 23/09) -----------------


def test_A_COMPRAR_HOY_no_descuenta_lo_COMPRADO_y_FALTA_si():
    """"A comprar hoy sale de restarle el stock a lo que piden" (dueño, 23/09).

    El RIVAL es restarle también lo comprado: daría lo mismo que "Falta" y
    la columna no diría nada. 500 kg de a 20, 40 de stock, ya compré 5 cajones
    de 20: a comprar techo(460/20) = 23, falta techo(360/20) = 18.
    """
    filas = _filas_de_que_comprar(
        [_aporte("Dia", a1=500.0)], ARTICULOS, UNIDADES,
        piso={1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}},
        comprado={1: {"cajones": 5.0, "kilos": 100.0, "conteo": None}},
        kilajes={1: 20.0})
    fila = filas[0]
    assert fila["a_comprar"] == 23
    assert fila["cajones"] == 18
    # Los dos "en bultos" del medio, con un decimal y sin techo: son lo que
    # piden y lo que hay, no lo que se compra.
    assert fila["pide_bultos"] == 25.0
    assert fila["stock_bultos"] == 2.0
    assert fila["palabra"] == "kg"


def test_sin_POR_BULTO_no_hay_bultos_que_decir_en_ninguna_columna():
    """Sin kilaje los bultos serían una invención: las tres columnas quedan en None."""
    articulos = {1: {"id": 1, "nombre": "MANGO", "contenido_referencia": None}}
    fila = _filas_de_que_comprar([_aporte("Dia", a1=500.0)], articulos, UNIDADES,
                                 piso=PISO_VACIO, comprado={})[0]
    assert fila["pide_bultos"] is None and fila["stock_bultos"] is None
    assert fila["a_comprar"] is None and fila["cajones"] is None


# --- EL LISTADO ATADO AL MOMENTO DE SALIR (dueño, 23/09) --------------------

_CARGA_DIA = {"id": 1, "cliente_id": 7, "cliente_nombre": "EJEMPLO Dia",
              "fecha": date(2026, 9, 24), "modo": "manual", "margen": 0,
              "promedio_anterior_a": date(2026, 9, 23), "renglones": {1: 500.0}}
_SIN_COMPRAS = {"compre": {}, "en_camino": {}, "viejas": {}}


def _contexto_real(borrador, *, foto_guardada=None, compras=_SIN_COMPRAS):
    """El contexto de verdad, con la base parcheada en sus bordes. Devuelve
    también los mocks de las dos fotos para ver CUÁL se leyó."""
    from app.main import _contexto_de_que_comprar
    foto = {"sueltos": {1: (2.0, 40.0)}, "cajas": {}}
    with patch("app.main.borrador_de_compra", return_value=borrador), \
         patch("app.main.listar_cargas_desde", return_value=[]) as ofrecidas, \
         patch("app.main.cargas_con_renglones", return_value=[_CARGA_DIA]), \
         patch("app.main.listar_articulos", return_value=[ARTICULOS[1]]), \
         patch("app.main.listar_fichas_de_todos_los_clientes", return_value=[]), \
         patch("app.main.listar_fichas_por_cliente", return_value=[]), \
         patch("app.main.compras_alrededor_de_la_salida", return_value=compras) as alrededor, \
         patch("app.main._foto_del_stock", return_value=foto) as en_vivo, \
         patch("app.main.foto_del_listado", return_value=foto_guardada or foto) as guardada:
        contexto = _contexto_de_que_comprar(None)
    return contexto, {"en_vivo": en_vivo, "guardada": guardada,
                      "alrededor": alrededor, "ofrecidas": ofrecidas}


def test_ANTES_de_salir_el_stock_es_el_de_AHORA_y_no_el_de_ayer():
    """"El stock de partida es el del momento en que generé el listado"
    (dueño, 23/09). Antes de apretar el botón ese momento es AHORA: la
    pantalla muestra lo que la foto sería si se sacara ya.

    El RIVAL es el del 23/09 a la mañana, el cierre de ayer: con ése una
    compra recepcionada hoy no estaba en el stock NI en camino (ya llegó), y
    se volvía a comprar."""
    from datetime import datetime
    from app.main import ARGENTINA
    borrador = {"id": 3, "fecha": date(2026, 9, 23), "cargas": [1], "kilajes": {},
                "generado_el": None}
    contexto, mocks = _contexto_real(borrador)
    assert mocks["en_vivo"].call_count == 1 and not mocks["guardada"].called
    assert mocks["en_vivo"].call_args.args[1] == datetime.now(ARGENTINA).date()
    assert mocks["alrededor"].call_args.args[0] is None, "antes de salir el momento es AHORA"
    assert contexto["salio_el"] is None
    assert len(contexto["filas"]) == 1 and contexto["filas"][0]["en_piso"] == 40.0


def test_DESPUES_de_salir_el_stock_es_la_FOTO_GUARDADA_y_no_se_recalcula():
    """El stock se cuenta por DÍA: el de las 22 no se puede recalcular a las
    4. Si la pantalla lo recalculara, lo recepcionado entre medio entraría
    al stock Y a "Compré"."""
    from datetime import datetime, timezone
    salida = datetime(2026, 9, 23, 1, 5, tzinfo=timezone.utc)   # 22:05 en Argentina
    borrador = {"id": 3, "fecha": date(2026, 9, 22), "cargas": [1], "kilajes": {},
                "generado_el": salida}
    foto = {"sueltos": {1: (5.0, 90.0)}, "cajas": {}}
    contexto, mocks = _contexto_real(borrador, foto_guardada=foto)
    assert not mocks["en_vivo"].called, "recalculó el stock en vivo después de salir"
    assert mocks["guardada"].call_args.args[0] == 3
    assert mocks["alrededor"].call_args.args[0] == salida
    assert contexto["filas"][0]["en_piso"] == 90.0
    assert contexto["salio_el"].strftime("%d/%m %H:%M") == "22/09 22:05"


def test_un_listado_ABIERTO_AYER_sigue_ofreciendo_sus_cargas_de_antes_de_ayer():
    """Atado al momento y no al reloj: el guardado REEMPLAZA las cargas, así
    que una tildada que no se dibuja se destilda sola al próximo Guardar."""
    from datetime import datetime, timedelta
    from app.main import ARGENTINA
    abierto = datetime.now(ARGENTINA).date() - timedelta(days=3)
    borrador = {"id": 3, "fecha": abierto, "cargas": [1], "kilajes": {}, "generado_el": None}
    _contexto, mocks = _contexto_real(borrador)
    assert mocks["ofrecidas"].call_args.args[0] == abierto - timedelta(days=1)


def test_las_VIEJAS_se_avisan_SOLO_las_de_los_articulos_del_listado():
    """Una compra de pera colgada no le dice nada al que compra tomate."""
    from datetime import datetime, timezone
    viejas = {1: {"cajones": 20.0, "kilos": 360.0, "conteo": None, "compras": 2,
                  "desde": datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)},
              9: {"cajones": 4.0, "kilos": 80.0, "conteo": None, "compras": 1,
                  "desde": datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)}}
    borrador = {"id": 3, "fecha": date(2026, 9, 23), "cargas": [1], "kilajes": {},
                "generado_el": None}
    contexto, _m = _contexto_real(borrador, compras=dict(_SIN_COMPRAS, viejas=viejas))
    assert contexto["viejas"] == [{"nombre": "TOMATE", "compras": 2, "cajones": 20.0,
                                   "desde": date(2026, 9, 10)}]


def test_EN_CAMINO_se_suma_al_punto_de_partida_y_NO_al_stock():
    """500 kg de a 20, 40 en el piso, 100 en camino y 60 comprados: a comprar
    techo(360/20) = 18 y falta techo(300/20) = 15. El stock sigue diciendo 40:
    lo que está en camino no está en el galpón.

    El RIVAL es ignorarlo: a comprar 23, o sea comprar de nuevo lo que ya
    viene."""
    fila = _filas_de_que_comprar(
        [_aporte("Dia", a1=500.0)], ARTICULOS, UNIDADES,
        piso={1: {"magnitud": 40.0, "sueltos": 2, "cajas": 0}},
        comprado={1: {"cajones": 3.0, "kilos": 60.0, "conteo": None}},
        en_camino={1: {"cajones": 5.0, "kilos": 100.0, "conteo": None}},
        kilajes={1: 20.0})[0]
    assert fila["en_piso"] == 40.0 and fila["stock_bultos"] == 2.0
    assert fila["en_camino"] == 100.0 and fila["en_camino_cajones"] == 5.0
    assert fila["de_partida"] == 140.0
    assert fila["a_comprar"] == 18
    assert fila["cajones"] == 15
    assert fila["ya_tengo"] == 200.0


def test_EN_CAMINO_sin_la_magnitud_de_la_fila_deja_la_fila_SIN_NUMERO():
    """Una compra en camino que no declaró el conteo de un artículo que se
    cuenta: no se sabe cuánto viene, y un cero haría comprar de más."""
    fila = _filas_de_que_comprar(
        [_aporte("Dia", a1=100.0)], ARTICULOS, {1: "unidad"}, piso=PISO_VACIO, comprado={},
        en_camino={1: {"cajones": 2.0, "kilos": 30.0, "conteo": None}})[0]
    assert fila["en_camino"] is None
    assert fila["a_comprar"] is None and fila["falta"] is None


def test_sin_POR_BULTO_pero_SIN_NADA_QUE_COMPRAR_las_dos_columnas_dicen_OK():
    """Cero no se divide por nada. El rival era el de hasta el 23/09: A comprar
    decía "poné el por bulto" y Falta decía OK en la misma fila, sobre el
    mismo dato."""
    articulos = {1: {"id": 1, "nombre": "MANGO", "contenido_referencia": None}}
    fila = _filas_de_que_comprar(
        [_aporte("Dia", a1=100.0)], articulos, UNIDADES, piso=PISO_VACIO, comprado={},
        en_camino={1: {"cajones": 10.0, "kilos": 150.0, "conteo": None}})[0]
    assert fila["a_comprar_magnitud"] == 0.0 and fila["falta"] == 0.0
    import re
    marcado = _render(_contexto([dict(_fila(3, "MANGO"), kilaje=None, a_comprar=None,
                                      a_comprar_magnitud=0.0, falta=0.0, cajones=None)]))
    marcado = " ".join(marcado.split("</style>")[-1].split())
    assert re.search(r'class="a-comprar"><span class="ok">OK</span>', marcado)
    assert re.search(r'class="falta"><span class="ok">OK</span>', marcado)


def test_la_pantalla_dice_si_YA_SALISTE_y_desde_cuando():
    """Un stock congelado que no dice de cuándo se lee como el de ahora, y
    uno de ahora se lee como congelado."""
    from datetime import datetime
    from app.main import ARGENTINA
    antes = " ".join(_render(_contexto([_fila(3, "TOMATE")])).split("</style>")[-1].split())
    assert "Todavía no saliste a comprar." in antes
    assert 'value="salgo"' in antes
    salida = datetime(2026, 9, 22, 22, 5, tzinfo=ARGENTINA)
    despues = " ".join(_render(_contexto([_fila(3, "TOMATE")], salio_el=salida))
                       .split("</style>")[-1].split())
    assert "Saliste a comprar el <b>22/09 a las 22:05</b>" in despues
    # LA JERGA QUE NO PUEDE QUEDAR: el botón de salir de nuevo, y el cierre de ayer.
    assert 'value="salgo"' not in despues
    assert "cierre del" not in despues and "cierre del" not in antes


def test_el_aviso_de_las_VIEJAS_se_dibuja_con_cuantas_y_desde_cuando():
    marcado = " ".join(_render(_contexto(
        [_fila(3, "TOMATE")],
        viejas=[{"nombre": "TOMATE", "compras": 2, "cajones": 20.0,
                 "desde": date(2026, 9, 10)}])).split("</style>")[-1].split())
    assert 'class="tarjeta aviso-viejas"' in marcado
    assert "<b>TOMATE</b>: 2 compras, 20 cj, desde el 10/09" in marcado
    assert 'href="/compras/pendientes"' in marcado
    sin = _render(_contexto([_fila(3, "TOMATE")])).split("</style>")[-1]
    assert 'class="tarjeta aviso-viejas"' not in sin


def test_las_OCHO_columnas_van_en_el_ORDEN_del_dueño():
    """Por la CLASE y no por el texto (corolario 38), y con el denominador:
    las dos tarjetas miradas, cada una con las ocho. "En camino" va al lado
    del stock, que es a lo que se suma."""
    import re
    decidido = ["dato-pide", "dato-kilaje", "dato-bultos", "dato-stock", "dato-en-camino",
                "dato-a-comprar", "dato-compre", "dato-falta"]
    marcado = _render(_contexto([_fila(3, "TOMATE"), _fila(8, "ZAPALLITO")])).split("</style>")[-1]
    tarjetas = re.findall(r'data-articulo="\d+"(.*?)(?=data-articulo="|\Z)', marcado, re.S)
    assert len(tarjetas) == 2
    for tarjeta in tarjetas:
        assert re.findall(r'class="dato (dato-[a-z-]+)"', tarjeta) == decidido


def _recalcular_en_el_navegador(html, kilaje):
    pytest.importorskip("playwright", reason="el recálculo en vivo necesita un navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM

    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROMIUM)
        pagina = navegador.new_page(viewport={"width": 390, "height": 844})
        pagina.set_content(html)
        pagina.fill(".kilaje", str(kilaje))
        leido = pagina.evaluate("""() => {
          const t = document.querySelector('[data-articulo]');
          const txt = s => t.querySelector(s).textContent.trim();
          return {tarjetas: document.querySelectorAll('[data-articulo]').length,
                  bultos: txt('.pide-bultos'), stock: txt('.stock-bultos'),
                  a_comprar: txt('.a-comprar'), falta: txt('.falta'),
                  ancho: document.documentElement.scrollWidth - document.documentElement.clientWidth};
        }""")
        navegador.close()
    return leido


def test_mover_el_POR_BULTO_rehace_las_CUATRO_columnas_que_dependen_de_el():
    """El JS es la segunda copia de la cuenta: tiene que dar lo mismo que el
    server con el mismo dato. 240 piden, 40 de stock, 60 ya comprados, de a
    20: 12 bultos, 2 de stock, 10 a comprar y 7 falta.

    CON ALGO COMPRADO A PROPÓSITO: con cero, "stock" y "stock + comprado" son
    el mismo número y un JS que restara lo comprado en "A comprar" pasaba
    igual (el canario dio cero con ese fixture)."""
    fila = dict(_fila(3, "TOMATE"), comprado=60.0, ya_tengo=100.0)
    leido = _recalcular_en_el_navegador(_render(_contexto([fila])), 20)
    assert leido["tarjetas"] == 1
    assert leido["bultos"] == "12"
    assert leido["stock"] == "2 blt"
    assert leido["a_comprar"] == "10 cj"
    assert leido["falta"] == "7 cj"


def test_mover_el_POR_BULTO_resta_LO_EN_CAMINO_en_A_COMPRAR():
    """Con 40 en el piso y 80 en camino, el punto de partida es 120: de a 20
    son 6 a comprar. El RIVAL —restar solo el piso— da 10, y con EN CAMINO
    EN CERO los dos dan lo mismo: por eso el fixture lo trae puesto."""
    fila = dict(_fila(3, "TOMATE"), en_camino=80.0, en_camino_cajones=4.0,
                de_partida=120.0, ya_tengo=120.0)
    leido = _recalcular_en_el_navegador(_render(_contexto([fila])), 20)
    assert leido["tarjetas"] == 1
    assert leido["stock"] == "2 blt"
    assert leido["a_comprar"] == "6 cj"
    assert leido["falta"] == "6 cj"
    assert leido["ancho"] <= 0, "la tarjeta arrastra la pantalla de costado"
