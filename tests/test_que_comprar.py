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
            "kilaje": 18.0, "falta": 200.0, "cajones": 12}


def _contexto(filas=(), cargas=(), elegidas=()):
    from app.main import _cargas_por_cliente
    return {"barra_sector": "compras", "barra_titulo": "Qué comprar hoy",
            "clientes": _cargas_por_cliente(list(cargas)), "elegidas": set(elegidas),
            "filas": list(filas), "aviso": None, "hay_borrador": True}


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
