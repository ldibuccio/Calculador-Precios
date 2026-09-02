"""Tests del reparto FIFO del stock del depósito (core/stock.py) — puro, sin base."""

from core.stock import repartir_fifo, salidas_para_reparto


def _lote(orden, cantidad, **extra):
    return dict({"orden": orden, "cantidad": cantidad}, **extra)


def _dirigida(orden, cantidad, lote_tipo, lote_origen_id):
    """Una merma DIRIGIDA: el operario señaló de qué lote sale."""
    return {"orden": orden, "cantidad": cantidad,
            "lote_tipo": lote_tipo, "lote_origen_id": lote_origen_id}


def test_fifo_consume_del_lote_mas_viejo_primero():
    entradas = [_lote(2, 10, nombre="nueva"), _lote(1, 8, nombre="vieja")]
    reparto = repartir_fifo(entradas, [{"orden": 3, "cantidad": 5}])

    # Se ordena por fecha aunque las entradas vengan desordenadas.
    assert [l["nombre"] for l in reparto["lotes"]] == ["vieja", "nueva"]
    assert reparto["lotes"][0]["restante"] == 3
    assert reparto["lotes"][0]["consumido"] == 5
    assert reparto["lotes"][1]["restante"] == 10
    assert reparto["sin_lote"] == 0
    assert reparto["stock"] == 13


def test_fifo_una_salida_grande_cruza_varios_lotes():
    entradas = [_lote(1, 8), _lote(2, 10), _lote(3, 4)]
    reparto = repartir_fifo(entradas, [{"orden": 9, "cantidad": 15}])

    assert [l["restante"] for l in reparto["lotes"]] == [0, 3, 4]
    assert reparto["sin_lote"] == 0
    assert reparto["stock"] == 7


def test_fifo_salidas_de_mas_quedan_sin_lote_y_el_stock_negativo():
    # El armado nunca se traba por stock: el excedente NO se cuelga de
    # ninguna guía — queda como "sin lote" y el stock en negativo, que es
    # la señal de que falta un reproceso o un ajuste.
    entradas = [_lote(1, 8)]
    reparto = repartir_fifo(entradas, [{"orden": 2, "cantidad": 5}, {"orden": 3, "cantidad": 7}])

    assert reparto["lotes"][0]["restante"] == 0
    assert reparto["sin_lote"] == 4
    assert reparto["stock"] == -4


def test_fifo_sin_entradas_todo_queda_sin_lote():
    reparto = repartir_fifo([], [{"orden": 1, "cantidad": 6}])

    assert reparto["lotes"] == []
    assert reparto["sin_lote"] == 6
    assert reparto["stock"] == -6


def test_fifo_sin_salidas_no_toca_nada():
    reparto = repartir_fifo([_lote(1, 8)], [])

    assert reparto["lotes"][0]["restante"] == 8
    assert reparto["lotes"][0]["consumido"] == 0
    assert reparto["sin_lote"] == 0
    assert reparto["stock"] == 8


def test_fifo_un_reingreso_con_fecha_vieja_se_ordena_por_su_fecha_real():
    # El camión del rechazo volvió el 22 y se cargó el 23: la fecha de
    # operación (22) es la que ordena — por eso el orden es una tupla
    # (fecha del hecho, momento de carga) y no el momento de carga solo.
    from datetime import date, datetime

    entradas = [
        _lote((date(2026, 8, 23), datetime(2026, 8, 23, 10)), 10, nombre="guia_23"),
        _lote((date(2026, 8, 22), datetime(2026, 8, 23, 15)), 3, nombre="reingreso_del_22"),
    ]
    reparto = repartir_fifo(entradas, [{"orden": 0, "cantidad": 3}])

    assert [l["nombre"] for l in reparto["lotes"]] == ["reingreso_del_22", "guia_23"]
    assert reparto["lotes"][0]["restante"] == 0
    assert reparto["lotes"][1]["restante"] == 10


def test_fifo_redondea_a_dos_decimales():
    reparto = repartir_fifo([_lote(1, 0.1), _lote(2, 0.2)], [{"orden": 3, "cantidad": 0.4}])

    assert reparto["sin_lote"] == 0.1
    assert reparto["stock"] == -0.1


# --- Merma dirigida a un lote (el operario sabe cuál se pudrió) ---


def test_merma_dirigida_sale_de_su_lote_y_no_del_mas_viejo():
    # La guía R armada hace dos días se pudrió: esa merma no puede
    # comerse el cajón viejo, que sigue sano.
    entradas = [
        _lote(1, 80, tipo_lote="guia", origen_id=55, nombre="cajones viejos"),
        _lote(2, 40, tipo_lote="reproceso", origen_id=9, nombre="guia R"),
    ]
    salidas = salidas_para_reparto([_dirigida(3, 10, "reproceso", 9)])
    reparto = repartir_fifo(entradas, salidas)

    por_nombre = {l["nombre"]: l for l in reparto["lotes"]}
    assert por_nombre["cajones viejos"]["restante"] == 80
    assert por_nombre["guia R"]["restante"] == 30
    assert reparto["sin_lote"] == 0


def test_merma_dirigida_que_no_entra_en_su_lote_cae_al_fifo():
    # Registra y delata, jamás traba: lo que el lote elegido no cubre
    # sigue el camino de siempre.
    entradas = [
        _lote(1, 80, tipo_lote="guia", origen_id=55, nombre="cajones viejos"),
        _lote(2, 4, tipo_lote="reproceso", origen_id=9, nombre="guia R"),
    ]
    salidas = salidas_para_reparto([_dirigida(3, 10, "reproceso", 9)])
    reparto = repartir_fifo(entradas, salidas)

    por_nombre = {l["nombre"]: l for l in reparto["lotes"]}
    assert por_nombre["guia R"]["restante"] == 0
    assert por_nombre["cajones viejos"]["restante"] == 74  # los 6 que sobraron
    assert reparto["stock"] == 74


def test_merma_dirigida_a_un_lote_que_ya_no_existe_cae_al_fifo():
    entradas = [_lote(1, 80, tipo_lote="guia", origen_id=55, nombre="cajones viejos")]
    salidas = salidas_para_reparto([_dirigida(3, 10, "reproceso", 999)])
    reparto = repartir_fifo(entradas, salidas)

    assert reparto["lotes"][0]["restante"] == 70


def test_la_dirigida_tiene_prioridad_sobre_las_salidas_comunes():
    # El armado del día consume FIFO, pero la merma dirigida se cobra
    # primero de SU lote: si no, el FIFO podría vaciarlo antes.
    entradas = [
        _lote(1, 5, tipo_lote="guia", origen_id=55, nombre="vieja"),
        _lote(2, 5, tipo_lote="reproceso", origen_id=9, nombre="guia R"),
    ]
    salidas = salidas_para_reparto([{"orden": 3, "cantidad": 5}, _dirigida(3, 5, "reproceso", 9)])
    reparto = repartir_fifo(entradas, salidas)

    por_nombre = {l["nombre"]: l for l in reparto["lotes"]}
    assert por_nombre["guia R"]["restante"] == 0
    assert por_nombre["vieja"]["restante"] == 0
    assert reparto["stock"] == 0


def test_salidas_para_reparto_saca_las_de_cantidad_cero():
    """Desde E4 las salidas llegan una por una y fechadas: acá ya no se arma
    nada, solo se sacan las que no sacan nada (el reproceso inicial toma cero)."""
    salidas = [{"orden": 1, "cantidad": 5}, {"orden": 2, "cantidad": 0}]

    assert salidas_para_reparto(salidas) == [{"orden": 1, "cantidad": 5}]
    assert salidas_para_reparto([]) == []


# --- E4: el FIFO no viaja al futuro ---

from datetime import date  # noqa: E402


def _lote_fechado(dia, cantidad, **extra):
    return dict({"orden": (date(2026, 9, dia), dia), "cantidad": cantidad}, **extra)


def _salida_fechada(dia, cantidad, **extra):
    return dict({"orden": (date(2026, 9, dia), dia), "cantidad": cantidad}, **extra)


def test_una_salida_no_puede_consumir_un_lote_posterior():
    """El corazón de E4. Antes, agotado el lote viejo, la salida seguía comiendo
    hacia adelante y tapaba el faltante con mercadería que todavía no había
    llegado. Ahora esa porción queda SIN LOTE y se ve."""
    entradas = [_lote_fechado(1, 5, nombre="vieja"), _lote_fechado(10, 100, nombre="futura")]
    reparto = repartir_fifo(entradas, [_salida_fechada(3, 20)])

    assert reparto["lotes"][0]["restante"] == 0      # se comió la vieja entera
    assert reparto["lotes"][1]["restante"] == 100    # la futura ni se tocó
    assert reparto["sin_lote"] == 15                 # y los 15 que faltan se ven


def test_una_salida_posterior_si_consume_el_lote_que_la_anterior_no_podia():
    """El lote salteado no se pierde: la salida que vino después sí lo alcanza.
    Por eso el índice del recorrido no puede pasarlo de largo."""
    entradas = [_lote_fechado(1, 5), _lote_fechado(10, 100)]
    reparto = repartir_fifo(entradas, [_salida_fechada(3, 20), _salida_fechada(20, 30)])

    assert reparto["lotes"][0]["restante"] == 0
    assert reparto["lotes"][1]["restante"] == 70     # la del día 20 sí lo consumió
    assert reparto["sin_lote"] == 15                 # solo lo de la salida del día 3


def test_un_lote_del_mismo_dia_si_cubre_la_salida():
    """La comparación es por FECHA, no por momento de carga: en el galpón las dos
    cosas pasaron el mismo día, y el reproceso que se carga a la tarde cubre el
    pedido que salió a la mañana."""
    entradas = [dict(_lote_fechado(5, 10), orden=(date(2026, 9, 5), 999))]
    reparto = repartir_fifo(entradas, [dict(_salida_fechada(5, 8), orden=(date(2026, 9, 5), 1))])

    assert reparto["lotes"][0]["restante"] == 2
    assert reparto["sin_lote"] == 0


def test_sin_fechas_el_reparto_se_comporta_como_siempre():
    """Compatibilidad: una salida sin fecha no puede aplicar la regla, así que no
    la aplica. Avisa por lo que sabe, nunca por lo que supone."""
    entradas = [_lote_fechado(1, 5), _lote_fechado(10, 100)]
    reparto = repartir_fifo(entradas, salidas_para_reparto([{"orden": 0, "cantidad": 20}]))

    assert reparto["lotes"][0]["restante"] == 0
    assert reparto["lotes"][1]["restante"] == 85
    assert reparto["sin_lote"] == 0


def test_la_merma_dirigida_alcanza_su_lote_aunque_sea_posterior():
    """La dirigida es una excepción deliberada: el operario SEÑALA el lote que se
    pudrió, no lo adivina. Discutirle la fecha sería negarle el piso."""
    entradas = [_lote_fechado(10, 30, tipo_lote="reproceso", origen_id=9)]
    salidas = [dict(_salida_fechada(3, 10), lote_tipo="reproceso", lote_origen_id=9)]
    reparto = repartir_fifo(entradas, salidas)

    assert reparto["lotes"][0]["restante"] == 20
    assert reparto["sin_lote"] == 0


# --- E4: qué quedaba en cada lote a una fecha ---

from core.stock import reparto_a_la_fecha  # noqa: E402


def test_a_la_fecha_no_cuenta_los_lotes_que_todavia_no_habian_entrado():
    """Es la pregunta que le va a hacer el freno: "¿había con qué el día que el
    operario dice que reprocesó?". Un lote que entró después no cuenta, aunque
    hoy esté ahí lleno."""
    entradas = [_lote_fechado(1, 10), _lote_fechado(20, 500)]
    reparto = reparto_a_la_fecha(entradas, [], date(2026, 9, 5))

    assert [l["restante"] for l in reparto["lotes"]] == [10]
    assert reparto["stock"] == 10


def test_a_la_fecha_no_cuenta_las_salidas_posteriores():
    """La otra punta: lo que salió después no puede achicar la foto de ese día."""
    entradas = [_lote_fechado(1, 10)]
    salidas = [_salida_fechada(3, 4), _salida_fechada(20, 6)]
    reparto = reparto_a_la_fecha(entradas, salidas, date(2026, 9, 5))

    assert reparto["lotes"][0]["restante"] == 6
    assert reparto["stock"] == 6


def test_a_la_fecha_del_dia_mismo_incluye_lo_de_ese_dia():
    """El corte es <= la fecha: lo que pasó ese día entra, igual que en la regla
    del lote posterior."""
    entradas = [_lote_fechado(5, 10)]
    salidas = [_salida_fechada(5, 3)]
    reparto = reparto_a_la_fecha(entradas, salidas, date(2026, 9, 5))

    assert reparto["lotes"][0]["restante"] == 7


def test_a_la_fecha_de_hoy_da_lo_mismo_que_el_reparto_normal():
    """La foto del pasado y el reparto de hoy son LA MISMA cuenta con distinto
    recorte. Si se separan, los números dejan de cerrar y nadie se entera."""
    entradas = [_lote_fechado(1, 10), _lote_fechado(3, 20)]
    salidas = [_salida_fechada(2, 4), _salida_fechada(4, 8)]

    completo = repartir_fifo(entradas, salidas)
    a_la_fecha = reparto_a_la_fecha(entradas, salidas, date(2026, 9, 30))

    assert [l["restante"] for l in a_la_fecha["lotes"]] == [l["restante"] for l in completo["lotes"]]
    assert a_la_fecha["sin_lote"] == completo["sin_lote"]
    assert a_la_fecha["stock"] == completo["stock"]


# --- El freno del reproceso y el desglose (Merge B) ---

from core.stock import (  # noqa: E402
    bultos_en_los_lotes,
    propuesta_fifo,
    reparto_para_reproceso,
    validar_reparto_declarado,
)


def _lote_con_origen(dia, cantidad):
    """Un lote como llega de la base: con su tipo y su origen, que es como lo
    nombran el desglose y el reparto que vuelve de la pantalla."""
    return _lote_fechado(dia, cantidad, tipo_lote="guia", origen_id=dia)


def test_para_el_reproceso_las_salidas_DEL_MISMO_DIA_no_cuentan():
    """El caso real del 31/08: el depósito arma las cajas y después carga la
    guía R que las explica. Si la salida del mismo día contara, el operario
    quedaría trabado justo por lo que está arreglando."""
    entradas = [_lote_fechado(4, 44)]
    salidas = [_salida_fechada(5, 44)]

    assert reparto_para_reproceso(entradas, salidas, date(2026, 9, 5))["lotes"][0]["restante"] == 44
    # Y con el recorte simétrico —el de la foto honesta del pasado— da 0.
    assert reparto_a_la_fecha(entradas, salidas, date(2026, 9, 5))["lotes"][0]["restante"] == 0


def test_para_el_reproceso_las_salidas_del_dia_ANTERIOR_si_cuentan():
    """El recorte corre un día, no borra la historia."""
    entradas = [_lote_fechado(1, 44)]
    salidas = [_salida_fechada(4, 44)]

    assert reparto_para_reproceso(entradas, salidas, date(2026, 9, 5))["lotes"][0]["restante"] == 0


def test_para_el_reproceso_las_entradas_del_dia_mismo_SI_cuentan():
    """El recorte es asimétrico a propósito: las entradas siguen entrando hasta
    la fecha inclusive. La mercadería que llegó a la mañana se reprocesa a la
    tarde, y eso pasa todos los días."""
    entradas = [_lote_fechado(5, 30)]

    assert reparto_para_reproceso(entradas, [], date(2026, 9, 5))["lotes"][0]["restante"] == 30


def test_el_numero_del_freno_NUNCA_es_negativo():
    """Contra la SUMA DE LOS RESTANTES, no contra el neto. El neto de acá es
    −15 y vive en sin_lote, que es otra cosa: trabar a un operario por un
    agujero anterior sería trabarlo por lo mismo que está arreglando."""
    entradas = [_lote_fechado(1, 10)]
    salidas = [_salida_fechada(2, 25)]
    reparto = reparto_para_reproceso(entradas, salidas, date(2026, 9, 5))

    assert reparto["stock"] == -15
    assert bultos_en_los_lotes(reparto) == 0


def test_la_propuesta_es_del_mas_viejo_primero_y_no_nombra_los_lotes_vacios():
    entradas = [_lote_con_origen(1, 8), _lote_con_origen(3, 10)]
    lotes = reparto_para_reproceso(entradas, [], date(2026, 9, 5))["lotes"]

    assert propuesta_fifo(lotes, 10) == [
        {"tipo_lote": "guia", "origen_id": 1, "bultos": 8.0},
        {"tipo_lote": "guia", "origen_id": 3, "bultos": 2.0},
    ]
    # Con lo que cubre el primero, el segundo ni aparece.
    assert propuesta_fifo(lotes, 5) == [{"tipo_lote": "guia", "origen_id": 1, "bultos": 5.0}]


def test_la_propuesta_devuelve_lo_que_hay_y_no_es_ella_la_que_traba():
    """Si no alcanza, propuesta_fifo no inventa ni levanta nada: el que decide
    que eso no se guarda es el freno, y está escrito en un solo lugar."""
    lotes = reparto_para_reproceso([_lote_con_origen(1, 3)], [], date(2026, 9, 5))["lotes"]

    assert propuesta_fifo(lotes, 5) == [{"tipo_lote": "guia", "origen_id": 1, "bultos": 3.0}]


def test_el_reparto_editado_se_valida_lote_por_lote_y_por_el_total():
    lotes = reparto_para_reproceso([_lote_con_origen(1, 8), _lote_con_origen(3, 10)], [], date(2026, 9, 5))["lotes"]
    bien = [
        {"tipo_lote": "guia", "origen_id": 1, "bultos": 3},
        {"tipo_lote": "guia", "origen_id": 3, "bultos": 7},
    ]

    assert validar_reparto_declarado(lotes, 10, bien) is None
    # De un lote no se puede sacar más de lo que quedaba...
    assert validar_reparto_declarado(
        lotes, 10, [{"tipo_lote": "guia", "origen_id": 1, "bultos": 10}]
    ) is not None
    # ...ni repartir menos de lo declarado: la diferencia no tiene dónde caer.
    assert validar_reparto_declarado(
        lotes, 10, [{"tipo_lote": "guia", "origen_id": 1, "bultos": 8}]
    ) is not None
    # ...ni nombrar un lote que a esa fecha no existe.
    assert validar_reparto_declarado(
        lotes, 10, [{"tipo_lote": "guia", "origen_id": 99, "bultos": 10}]
    ) is not None
