"""Tests del reparto FIFO del stock del depósito (core/stock.py) — puro, sin base."""

from core.stock import repartir_fifo, salidas_para_reparto


def _lote(orden, cantidad, **extra):
    return dict({"orden": orden, "cantidad": cantidad}, **extra)


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
    salidas = salidas_para_reparto(0, [{"cantidad": 10, "lote_tipo": "reproceso", "lote_origen_id": 9}])
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
    salidas = salidas_para_reparto(0, [{"cantidad": 10, "lote_tipo": "reproceso", "lote_origen_id": 9}])
    reparto = repartir_fifo(entradas, salidas)

    por_nombre = {l["nombre"]: l for l in reparto["lotes"]}
    assert por_nombre["guia R"]["restante"] == 0
    assert por_nombre["cajones viejos"]["restante"] == 74  # los 6 que sobraron
    assert reparto["stock"] == 74


def test_merma_dirigida_a_un_lote_que_ya_no_existe_cae_al_fifo():
    entradas = [_lote(1, 80, tipo_lote="guia", origen_id=55, nombre="cajones viejos")]
    salidas = salidas_para_reparto(0, [{"cantidad": 10, "lote_tipo": "reproceso", "lote_origen_id": 999}])
    reparto = repartir_fifo(entradas, salidas)

    assert reparto["lotes"][0]["restante"] == 70


def test_la_dirigida_tiene_prioridad_sobre_las_salidas_comunes():
    # El armado del día consume FIFO, pero la merma dirigida se cobra
    # primero de SU lote: si no, el FIFO podría vaciarlo antes.
    entradas = [
        _lote(1, 5, tipo_lote="guia", origen_id=55, nombre="vieja"),
        _lote(2, 5, tipo_lote="reproceso", origen_id=9, nombre="guia R"),
    ]
    salidas = salidas_para_reparto(5, [{"cantidad": 5, "lote_tipo": "reproceso", "lote_origen_id": 9}])
    reparto = repartir_fifo(entradas, salidas)

    por_nombre = {l["nombre"]: l for l in reparto["lotes"]}
    assert por_nombre["guia R"]["restante"] == 0
    assert por_nombre["vieja"]["restante"] == 0
    assert reparto["stock"] == 0


def test_sin_dirigidas_el_reparto_es_el_de_siempre():
    salidas = salidas_para_reparto(5)
    assert salidas == [{"orden": 0, "cantidad": 5}]
    assert salidas_para_reparto(0) == []


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
    """Compatibilidad: un reparto por total (orden 0, sin fecha) no puede aplicar
    la regla, así que no la aplica. Avisa por lo que sabe, nunca por lo que supone."""
    entradas = [_lote_fechado(1, 5), _lote_fechado(10, 100)]
    reparto = repartir_fifo(entradas, salidas_para_reparto(20))

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
