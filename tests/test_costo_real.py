"""Tests del motor de Rentabilidad Real (core/costo_real.py) — puro, sin base."""

from datetime import date

from core.costo_real import atribuir_costos_fifo, calcular_rentabilidad_real
from core.stock import repartir_fifo


def _lote(orden, cantidad, costo, tipo_lote="guia"):
    return {"orden": orden, "cantidad": cantidad, "costo_bulto": costo, "tipo_lote": tipo_lote}


def _armado(fecha, cantidad, unidades, cliente_id=1, orden=None, ficha_id=901):
    """Una salida de armado. ficha_id es la clave de VENTA (ancla el precio);
    901 es la ficha del artículo 1, la convención de los fixtures."""
    return {
        "orden": orden if orden is not None else (fecha, 0),
        "tipo": "armado",
        "fecha": fecha,
        "cantidad": cantidad,
        "unidades": unidades,
        "cliente_id": cliente_id,
        "ficha_id": ficha_id,
    }


# --- atribuir_costos_fifo ---


def test_el_lote_ELEGIDO_va_a_la_misma_salida_en_los_DOS_repartos():
    """El test que faltaba, y el que impide que las dos cuentas se separen.

    Un lote de 10. Una salida ANTERIOR sin dirigir que lo consumiría entero
    por FIFO, y una POSTERIOR que lo elige con el dedo. Los dos repartos
    tienen que estar de acuerdo en quién se lo quedó.

    Antes del 02/09 no lo estaban: el stock se lo daba a la que lo eligió y
    el costo se lo cobraba a la anterior, porque acá el reclamo dirigido se
    resolvía adentro del turno cronológico de cada salida en vez de en una
    pasada global. No se duplicaba nada y nada desaparecía —por eso ningún
    test lo agarró—, pero las dos funciones emparejaban distinto.

    NO ALCANZA con verificar que no se duplica: eso pasaba en verde con el
    bug adentro. Lo que se verifica es el EMPAREJAMIENTO.
    """
    lote_elegido = _lote((date(2026, 9, 1), 1), 10, 1000.0)
    lote_elegido["origen_id"] = 77
    anterior = {"orden": (date(2026, 9, 2), 2), "cantidad": 10}
    la_que_elige = {"orden": (date(2026, 9, 3), 3), "cantidad": 10,
                    "lote_tipo": "guia", "lote_origen_id": 77}

    stock = repartir_fifo([lote_elegido], [dict(anterior), dict(la_que_elige)])
    costo = atribuir_costos_fifo([lote_elegido], [dict(anterior), dict(la_que_elige)])

    # STOCK: el lote se consumió entero y la anterior quedó sin nada.
    assert stock["lotes"][0]["restante"] == 0
    assert stock["sin_lote"] == 10

    # COSTO: el MISMO lote tiene que estar en la MISMA salida. Acá se rompía.
    de_la_anterior, de_la_que_elige = costo
    assert [(c["origen_id"], c["bultos"]) for c in de_la_que_elige["consumos_lotes"]] == [(77, 10.0)]
    assert de_la_que_elige["costo"] == 10000.0

    # Y la que se quedó sin el lote no desaparece ni se costea de prestado:
    # cae a sin_lote, con su motivo, igual que en el reparto de stock.
    assert de_la_anterior["consumos_lotes"] == []
    assert de_la_anterior["costo"] is None
    assert de_la_anterior["motivos_sin_costo"] == {"sin_lote": 10.0}

    # Y el lote se cobró UNA sola vez entre las dos.
    assert sum(c["bultos"] for s in costo for c in s["consumos_lotes"]) == 10


def test_el_lote_elegido_gana_aunque_lo_pida_una_salida_de_ANTES_y_le_sobre():
    """La misma regla con la dirigida tomando solo una parte: lo que no se
    lleva vuelve al FIFO y lo agarra la anterior, sin quedar colgado."""
    lote_elegido = _lote((date(2026, 9, 1), 1), 10, 1000.0)
    lote_elegido["origen_id"] = 77
    anterior = {"orden": (date(2026, 9, 2), 2), "cantidad": 10}
    la_que_elige = {"orden": (date(2026, 9, 3), 3), "cantidad": 4,
                    "lote_tipo": "guia", "lote_origen_id": 77}

    stock = repartir_fifo([lote_elegido], [dict(anterior), dict(la_que_elige)])
    de_la_anterior, de_la_que_elige = atribuir_costos_fifo(
        [lote_elegido], [dict(anterior), dict(la_que_elige)]
    )

    assert stock["lotes"][0]["restante"] == 0
    assert stock["sin_lote"] == 4  # la anterior se quedó corta por los 4 elegidos
    assert [(c["origen_id"], c["bultos"]) for c in de_la_que_elige["consumos_lotes"]] == [(77, 4.0)]
    assert [(c["origen_id"], c["bultos"]) for c in de_la_anterior["consumos_lotes"]] == [(77, 6.0)]
    assert de_la_anterior["motivos_sin_costo"] == {"sin_lote": 4.0}


def test_una_dirigida_a_un_lote_POSTERIOR_no_le_saca_nada_a_nadie():
    """El caso normal de hoy: la merma señala un lote que ninguna salida
    anterior podía tocar (es posterior a ellas). Nada se mueve — es lo que
    hace que el arreglo del 02/09 no haya cambiado un solo número en
    producción, donde no hay una sola merma dirigida."""
    viejo = _lote((date(2026, 9, 1), 1), 10, 1000.0)
    viejo["origen_id"] = 77
    nuevo = _lote((date(2026, 9, 5), 5), 10, 3000.0)
    nuevo["origen_id"] = 99
    anterior = {"orden": (date(2026, 9, 3), 3), "cantidad": 10}
    dirigida = {"orden": (date(2026, 9, 6), 6), "cantidad": 4,
                "lote_tipo": "guia", "lote_origen_id": 99}

    de_la_anterior, de_la_dirigida = atribuir_costos_fifo(
        [viejo, nuevo], [dict(anterior), dict(dirigida)]
    )

    assert de_la_anterior["costo"] == 10000.0
    assert de_la_dirigida["costo"] == 12000.0




def test_atribucion_cada_salida_conoce_su_costo_por_lote():
    entradas = [_lote(1, 10, 1000.0), _lote(2, 10, 1300.0)]
    salidas = [
        {"orden": 3, "cantidad": 8},
        {"orden": 4, "cantidad": 6},
    ]

    resultado = atribuir_costos_fifo(entradas, salidas)

    # La primera consume 8 del lote viejo ($1000); la segunda cruza:
    # 2 del viejo + 4 del nuevo.
    assert resultado[0]["costo"] == 8000.0
    assert resultado[1]["costo"] == 2 * 1000.0 + 4 * 1300.0
    assert all(s["bultos_sin_costo"] == 0 for s in resultado)


def test_atribucion_no_cuesta_una_salida_contra_una_compra_posterior():
    """E4: el costeo no viaja al futuro.

    Antes, agotados los lotes viejos, la salida seguía comiendo hacia adelante y
    se costeaba contra una compra que todavía no había llegado — un faltante
    tapado con mercadería inexistente, y con un costo que además no era el suyo.
    Ahora esa porción cae a sin_lote, que es lo que de verdad pasó.
    """
    entradas = [
        _lote((date(2026, 9, 1), 0), 5, 1000.0),
        _lote((date(2026, 9, 10), 0), 100, 9999.0),
    ]
    salidas = [{"orden": (date(2026, 9, 3), 0), "cantidad": 20}]

    resultado = atribuir_costos_fifo(entradas, salidas)

    assert resultado[0]["bultos_sin_costo"] == 15
    assert resultado[0]["motivos_sin_costo"] == {"sin_lote": 15}
    # Con una porción sin costo, la salida entera queda sin costo: mejor un
    # número chico y cierto que uno grande y mentiroso.
    assert resultado[0]["costo"] is None
    # Y el lote del futuro no se tocó: sus 100 siguen enteros para después.
    assert sum(c["bultos"] for c in resultado[0]["consumos_lotes"]) == 5


def test_atribucion_el_lote_salteado_lo_consume_la_salida_posterior():
    """El lote del futuro no se pierde para siempre: la salida que vino después
    sí lo alcanza. Por eso el índice del recorrido no puede pasarlo de largo
    cuando una salida anterior lo saltea."""
    entradas = [
        _lote((date(2026, 9, 1), 0), 5, 1000.0),
        _lote((date(2026, 9, 10), 0), 100, 2000.0),
    ]
    salidas = [
        {"orden": (date(2026, 9, 3), 0), "cantidad": 20},
        {"orden": (date(2026, 9, 20), 0), "cantidad": 30},
    ]

    resultado = atribuir_costos_fifo(entradas, salidas)

    assert resultado[0]["bultos_sin_costo"] == 15
    # La del día 20 sí puede: el lote del día 10 ya existía para ella.
    assert resultado[1]["bultos_sin_costo"] == 0
    assert resultado[1]["costo"] == 30 * 2000.0


def test_atribucion_un_lote_del_mismo_dia_si_cuesta_la_salida():
    """La comparación es por FECHA, no por momento de carga: el reproceso que se
    carga a la tarde cubre el pedido que salió esa misma mañana."""
    entradas = [_lote((date(2026, 9, 5), 999), 10, 1500.0)]
    salidas = [{"orden": (date(2026, 9, 5), 1), "cantidad": 8}]

    resultado = atribuir_costos_fifo(entradas, salidas)

    assert resultado[0]["bultos_sin_costo"] == 0
    assert resultado[0]["costo"] == 8 * 1500.0


def test_atribucion_porcion_sin_precio_deja_la_salida_sin_costo_con_motivo():
    entradas = [_lote(1, 5, None, tipo_lote="ajuste"), _lote(2, 10, 1000.0)]
    salidas = [{"orden": 3, "cantidad": 8}]

    resultado = atribuir_costos_fifo(entradas, salidas)

    # 5 del ajuste (stock inicial, sin costo posible) + 3 de la compra:
    # la salida NO tiene costo (nunca se inventa) y dice por qué.
    assert resultado[0]["costo"] is None
    assert resultado[0]["bultos_sin_costo"] == 5
    assert resultado[0]["motivos_sin_costo"] == {"ajuste_sin_costo": 5}


def test_atribucion_exceso_sobre_los_lotes_es_sin_lote():
    entradas = [_lote(1, 3, 1000.0)]
    salidas = [{"orden": 2, "cantidad": 5}]

    resultado = atribuir_costos_fifo(entradas, salidas)

    assert resultado[0]["bultos_sin_costo"] == 2
    assert resultado[0]["motivos_sin_costo"] == {"sin_lote": 2}


def test_atribucion_distingue_los_motivos_por_tipo_de_lote():
    entradas = [
        _lote(1, 2, None, tipo_lote="guia"),
        _lote(2, 2, None, tipo_lote="reingreso_rechazo"),
        _lote(3, 2, None, tipo_lote="reproceso"),
    ]
    salidas = [{"orden": 4, "cantidad": 6}]

    resultado = atribuir_costos_fifo(entradas, salidas)

    assert resultado[0]["motivos_sin_costo"] == {
        "compra_sin_precio": 2,
        "reingreso_sin_costo": 2,
        "guia_r_incompleta": 2,
    }


# --- calcular_rentabilidad_real ---

MARGEN = {"precio_vigente": 100.0, "costo_actual": 60.0, "costo_envase_unidad_venta": 2.0,
          "denominador_tasas": 0.9}


def _datos(salidas, entradas=None):
    return [{
        "articulo_id": 1,
        "nombre": "Banana",
        "grupo": "fruta",
        "entradas": entradas if entradas is not None else [_lote(1, 100, 500.0)],
        "salidas": salidas,
    }]


def test_venta_real_es_lo_enviado_por_precio_vigente_con_tasas_y_costo_fifo():
    fecha = date(2026, 8, 25)
    resultado = calcular_rentabilidad_real(
        _datos([_armado(fecha, 10, 160.0)]),
        {fecha: {901: dict(MARGEN)}},
        cliente_id=1,
        fecha_desde=fecha,
        fecha_hasta=fecha,
    )

    fila = resultado["grupos"][0]["filas"][0]
    # Venta = 160 kg ENVIADOS × $100 × 0.9 tasas = 14.400 (no lo pedido).
    assert fila["venta_neta"] == 160.0 * 100.0 * 0.9
    # Mercadería = costo FIFO del lote: 10 bultos × $500.
    assert fila["costo_mercaderia"] == 5000.0
    # Envase por unidad ENVIADA: 160 × $2.
    assert fila["costo_envase"] == 320.0
    assert fila["renta_pesos"] == 14400.0 - 5000.0 - 320.0
    # Utilidad SOLO sobre mercadería.
    assert round(fila["utilidad_pct"], 2) == round(fila["renta_pesos"] / 5000.0 * 100, 2)


def test_la_merma_del_periodo_resta_al_costo_de_su_lote():
    fecha = date(2026, 8, 25)
    salidas = [
        _armado(fecha, 10, 100.0, orden=(fecha, 1)),
        {"orden": (fecha, 2), "tipo": "merma", "fecha": fecha, "cantidad": 3},
    ]
    resultado = calcular_rentabilidad_real(
        _datos(salidas), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha
    )

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["costo_mermas"] == 3 * 500.0
    assert fila["bultos_mermados"] == 3
    assert resultado["totales"]["costo_mermas"] == 1500.0
    # La merma baja la renta.
    assert fila["renta_pesos"] == fila["venta_neta"] - fila["costo_mercaderia"] - fila["costo_envase"] - 1500.0


# --- la merma abierta: materia prima o trabajo ---


def test_la_merma_de_un_cajon_de_compra_es_cruda():
    fecha = date(2026, 8, 25)
    salidas = [{"orden": (fecha, 1), "tipo": "merma", "fecha": fecha, "cantidad": 3}]
    resultado = calcular_rentabilidad_real(_datos(salidas), {}, 1, fecha, fecha)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["costo_mermas_cruda"] == 1500.0
    assert fila["bultos_mermados_cruda"] == 3
    assert fila["costo_mermas_trabajada"] == 0
    assert fila["bultos_mermados_trabajada"] == 0


def test_la_merma_dirigida_a_una_guia_r_es_trabajada_y_al_costo_de_esa_guia():
    # El caso que motivó el corte: tirar un bulto ya reprocesado sale mucho
    # más caro que tirar el cajón crudo del que salió, y en el reporte tiene
    # que verse por separado — no promediado adentro de "mermas".
    fecha = date(2026, 8, 25)
    entradas = [_lote(1, 10, 500.0), dict(_lote(2, 5, 1800.0, tipo_lote="reproceso"), origen_id=7)]
    salidas = [
        {"orden": (fecha, 1), "tipo": "merma", "fecha": fecha, "cantidad": 2,
         "lote_tipo": "reproceso", "lote_origen_id": 7},
    ]
    resultado = calcular_rentabilidad_real(_datos(salidas, entradas=entradas), {}, 1, fecha, fecha)

    fila = resultado["grupos"][0]["filas"][0]
    # Al costo de la guía R ($1.800), no al del cajón viejo que el FIFO
    # hubiera elegido ($500).
    assert fila["costo_mermas_trabajada"] == 3600.0
    assert fila["bultos_mermados_trabajada"] == 2
    assert fila["costo_mermas_cruda"] == 0
    # Y sigue siendo "− mermas", no "− rechazos perdidos".
    assert fila["costo_mermas"] == 3600.0
    assert fila["rechazos_perdidos"] == 0


def test_la_merma_de_un_reingreso_es_trabajada_y_la_de_un_ajuste_es_cruda():
    # Un reingreso ya salió armado y volvió: es trabajo. Un ajuste (stock
    # inicial, corrección de registro) es mercadería sin procesar.
    fecha = date(2026, 8, 25)
    entradas = [
        dict(_lote(1, 2, 900.0, tipo_lote="reingreso_rechazo"), origen_id=11),
        dict(_lote(2, 4, 300.0, tipo_lote="ajuste"), origen_id=12),
    ]
    salidas = [
        {"orden": (fecha, 1), "tipo": "merma", "fecha": fecha, "cantidad": 2,
         "lote_tipo": "reingreso_rechazo", "lote_origen_id": 11},
        {"orden": (fecha, 2), "tipo": "merma", "fecha": fecha, "cantidad": 4,
         "lote_tipo": "ajuste", "lote_origen_id": 12},
    ]
    resultado = calcular_rentabilidad_real(_datos(salidas, entradas=entradas), {}, 1, fecha, fecha)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["costo_mermas_trabajada"] == 1800.0
    assert fila["bultos_mermados_trabajada"] == 2
    assert fila["costo_mermas_cruda"] == 1200.0
    assert fila["bultos_mermados_cruda"] == 4


def test_una_merma_sin_dirigir_que_cruza_dos_lotes_se_parte_por_porcion():
    # El corte va por PORCIÓN, no por movimiento: sin lote elegido la merma
    # la reparte el FIFO, y acá se come lo que queda del cajón crudo y sigue
    # con la guía R. Imputarla entera a uno de los dos sería mentira.
    fecha = date(2026, 8, 25)
    entradas = [_lote(1, 2, 500.0), _lote(2, 5, 1800.0, tipo_lote="reproceso")]
    salidas = [{"orden": (fecha, 1), "tipo": "merma", "fecha": fecha, "cantidad": 5}]
    resultado = calcular_rentabilidad_real(_datos(salidas, entradas=entradas), {}, 1, fecha, fecha)

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["costo_mermas_cruda"] == 2 * 500.0
    assert fila["bultos_mermados_cruda"] == 2
    assert fila["costo_mermas_trabajada"] == 3 * 1800.0
    assert fila["bultos_mermados_trabajada"] == 3


def test_la_merma_abierta_siempre_cierra_contra_el_total_de_mermas():
    # El invariante: no es una cuenta nueva, es la misma abierta. Si las dos
    # partes no suman el total, algo se está contando mal o dos veces.
    fecha = date(2026, 8, 25)
    entradas = [_lote(1, 10, 500.0), _lote(2, 5, 1800.0, tipo_lote="reproceso")]
    salidas = [
        _armado(fecha, 4, 60.0, orden=(fecha, 1)),
        {"orden": (fecha, 2), "tipo": "merma", "fecha": fecha, "cantidad": 3},
        {"orden": (fecha, 3), "tipo": "merma", "fecha": fecha, "cantidad": 6},
    ]
    resultado = calcular_rentabilidad_real(
        _datos(salidas, entradas=entradas), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha
    )

    for cuenta in (resultado["grupos"][0]["filas"][0], resultado["grupos"][0]["subtotal"], resultado["totales"]):
        assert cuenta["costo_mermas_cruda"] + cuenta["costo_mermas_trabajada"] == cuenta["costo_mermas"]
    fila = resultado["grupos"][0]["filas"][0]
    assert fila["bultos_mermados_cruda"] + fila["bultos_mermados_trabajada"] == fila["bultos_mermados"]
    # Y la renta no se movió por abrirla: sigue restando el mismo total.
    assert fila["renta_pesos"] == (
        fila["venta_neta"] - fila["costo_mercaderia"] - fila["costo_envase"] - fila["costo_mermas"]
    )


def test_el_reproceso_es_neutro_y_la_segunda_se_informa_sin_plata():
    fecha = date(2026, 8, 25)
    salidas = [
        {"orden": (fecha, 1), "tipo": "reproceso_toma", "fecha": fecha, "cantidad": 6, "bultos_segunda": 2},
    ]
    resultado = calcular_rentabilidad_real(
        _datos(salidas), {}, 1, fecha, fecha
    )

    fila = resultado["grupos"][0]["filas"][0]
    # Ni venta ni pérdida: el costo viaja a la primera. Solo el dato.
    assert fila["venta_neta"] == 0
    assert fila["costo_mermas"] == 0
    assert fila["segunda_bultos"] == 2
    assert resultado["totales"]["segunda_bultos"] == 2


def test_una_porcion_sin_costo_deja_la_salida_entera_afuera_con_su_motivo():
    fecha = date(2026, 8, 25)
    # El lote es stock inicial sin costo: la salida se puede vender pero
    # no costear → ENTERA afuera (venta incluida), nunca a medias.
    resultado = calcular_rentabilidad_real(
        _datos([_armado(fecha, 10, 160.0)], entradas=[_lote(1, 100, None, tipo_lote="ajuste")]),
        {fecha: {901: dict(MARGEN)}},
        1, fecha, fecha,
    )

    assert resultado["grupos"] == []
    afuera = resultado["afuera_por_motivo"]
    assert len(afuera) == 1
    assert afuera[0]["motivo"] == "ajuste_sin_costo"
    assert afuera[0]["bultos"] == 10
    assert afuera[0]["articulos"] == [{"nombre": "Banana", "bultos": 10}]
    assert resultado["totales"]["afuera_bultos"] == 10


def test_sin_kilaje_y_sin_precio_van_afuera_por_su_motivo():
    fecha = date(2026, 8, 25)
    salidas = [
        _armado(fecha, 4, None, orden=(fecha, 1)),      # sin kilaje cargado
        _armado(fecha, 6, 90.0, orden=(fecha, 2)),      # sin precio vigente
    ]
    resultado = calcular_rentabilidad_real(_datos(salidas), {}, 1, fecha, fecha)

    motivos = {r["motivo"]: r["bultos"] for r in resultado["afuera_por_motivo"]}
    assert motivos == {"sin_kilaje": 4, "sin_precio": 6}
    # Ordenado por peso: el motivo con más bultos primero (hoja de ruta).
    assert resultado["afuera_por_motivo"][0]["motivo"] == "sin_precio"


def test_la_atribucion_usa_la_historia_completa_pero_reporta_solo_el_rango():
    # Un armado viejo (fuera de rango) consumió el lote barato: el armado
    # del rango tiene que costear contra el lote caro que quedó.
    vieja = date(2026, 8, 10)
    fecha = date(2026, 8, 25)
    entradas = [_lote(1, 10, 500.0), _lote(2, 10, 800.0)]
    salidas = [
        _armado(vieja, 10, 100.0, orden=(vieja, 1)),
        _armado(fecha, 5, 50.0, orden=(fecha, 1)),
    ]
    resultado = calcular_rentabilidad_real(
        _datos(salidas, entradas=entradas),
        {fecha: {901: dict(MARGEN)}},
        1, fecha, fecha,
    )

    fila = resultado["grupos"][0]["filas"][0]
    # Solo el armado del rango se reporta, y al costo del lote de $800.
    assert fila["bultos"] == 5
    assert fila["costo_mercaderia"] == 5 * 800.0
    assert vieja not in resultado["fechas_incluidas"]


def test_los_armados_de_otro_cliente_no_entran_a_esta_pantalla():
    fecha = date(2026, 8, 25)
    salidas = [
        _armado(fecha, 10, 160.0, cliente_id=2),
    ]
    resultado = calcular_rentabilidad_real(
        _datos(salidas), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha
    )

    assert resultado["grupos"] == []
    assert resultado["afuera_por_motivo"] == []


def test_el_ajuste_negativo_consume_lote_pero_no_es_perdida():
    fecha = date(2026, 8, 25)
    salidas = [
        {"orden": (fecha, 1), "tipo": "ajuste", "fecha": fecha, "cantidad": 4},
        _armado(fecha, 5, 50.0, orden=(fecha, 2)),
    ]
    entradas = [_lote(1, 4, 500.0), _lote(2, 10, 800.0)]
    resultado = calcular_rentabilidad_real(
        _datos(salidas, entradas=entradas), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha
    )

    fila = resultado["grupos"][0]["filas"][0]
    # El ajuste se comió el lote barato (corrección de registro, sin
    # pérdida reportada) y el armado costea contra el caro.
    assert fila["costo_mermas"] == 0
    assert fila["costo_mercaderia"] == 5 * 800.0


# --- devoluciones vinculadas ("si le mandé 25 y me devolvió 5, vendí 20") ---


def _devolucion(bultos, fecha_pedido, costo_por_bulto=2000.0, kilos=500.0, armados=25.0, destino="stock"):
    return {
        "bultos": bultos,
        "fecha_pedido": fecha_pedido,
        "kilos_enviados": kilos,
        "bultos_armados": armados,
        "costo_por_bulto": costo_por_bulto,
        "destino_rechazo": destino,
        "ficha_id": 901,
        "articulo_id": 1,
        "articulo_nombre": "Banana",
        "grupo": "fruta",
    }


def test_devolucion_vinculada_resta_venta_y_acredita_mercaderia_al_costo_congelado():
    fecha = date(2026, 8, 25)
    salidas = [_armado(fecha, 25, 500.0)]
    resultado = calcular_rentabilidad_real(
        _datos(salidas), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
        devoluciones=[_devolucion(5.0, fecha)],
    )

    fila = resultado["grupos"][0]["filas"][0]
    # Venta de lo enviado: 500 kg × 100 × 0.9 = 45000. La devolución de 5
    # bultos (a 20 kg/bulto del propio renglón) resta 100 kg × 100 × 0.9.
    assert fila["venta_neta"] == 45000.0
    assert fila["devoluciones_bultos"] == 5.0
    assert fila["devoluciones_venta"] == 100 * 100.0 * 0.9
    # La mercadería se acredita al costo congelado (el lote devuelto queda
    # en stock con ese costo y se vuelve a cargar cuando salga de nuevo):
    # 25 × 500 (FIFO) − 5 × 2000.
    assert fila["costo_mercaderia"] == 25 * 500.0 - 5 * 2000.0
    # La renta descuenta la devolución entera.
    assert fila["renta_pesos"] == (
        fila["venta_neta"] - fila["devoluciones_venta"] - fila["costo_total"]
    )
    assert resultado["totales"]["devoluciones_bultos"] == 5.0


def test_devolucion_sin_costo_congelado_solo_resta_venta():
    fecha = date(2026, 8, 25)
    salidas = [_armado(fecha, 25, 500.0)]
    resultado = calcular_rentabilidad_real(
        _datos(salidas), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
        devoluciones=[_devolucion(5.0, fecha, costo_por_bulto=None)],
    )

    fila = resultado["grupos"][0]["filas"][0]
    # Sin costo congelado no se acredita mercadería (el lote sigue "sin
    # costo" y se verá en el afuera cuando se consuma) — la venta sí baja.
    assert fila["devoluciones_venta"] == 100 * 100.0 * 0.9
    assert fila["costo_mercaderia"] == 25 * 500.0


def test_devolucion_que_no_se_puede_valuar_va_afuera_con_motivo():
    fecha = date(2026, 8, 25)
    # Renglón sin kilaje y pedido sin precio a su fecha: dos devoluciones
    # invaluables — van al afuera, jamás suman cero en silencio.
    resultado = calcular_rentabilidad_real(
        _datos([]), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
        devoluciones=[
            _devolucion(3.0, fecha, kilos=None),
            _devolucion(2.0, date(2026, 8, 20)),
        ],
    )

    assert resultado["grupos"] == []
    afuera = resultado["afuera_por_motivo"]
    assert len(afuera) == 1
    assert afuera[0]["motivo"] == "devolucion_sin_valor"
    assert afuera[0]["bultos"] == 5.0


def test_devolucion_ancla_el_precio_a_la_fecha_del_pedido_de_origen():
    fecha_pedido = date(2026, 8, 20)
    fecha_rango = date(2026, 8, 25)
    # El precio a la fecha del PEDIDO (80), no el del rango (100): la
    # devolución deshace la venta al valor con el que se facturó.
    margenes = {
        fecha_pedido: {901: dict(MARGEN, precio_vigente=80.0)},
        fecha_rango: {901: dict(MARGEN)},
    }
    resultado = calcular_rentabilidad_real(
        _datos([]), margenes, 1, fecha_rango, fecha_rango,
        devoluciones=[_devolucion(5.0, fecha_pedido)],
    )

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["devoluciones_venta"] == 100 * 80.0 * 0.9


# --- Destino del rechazo: la línea "− rechazos perdidos" ---


def test_rechazo_a_segunda_es_perdida_entera_de_mercaderia_mas_envase():
    # No vuelve al stock: no queda primera que absorba el costo (a
    # diferencia del reproceso normal). Mercadería congelada + envase.
    fecha = date(2026, 8, 25)
    resultado = calcular_rentabilidad_real(
        _datos([_armado(fecha, 25, 500.0)]), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
        devoluciones=[_devolucion(5.0, fecha, destino="segunda")],
    )

    fila = resultado["grupos"][0]["filas"][0]
    # 5 bultos a 20 kg/bulto = 100 kg de envase a $2 = 200, + 5 × 2000.
    assert fila["rechazos_bultos"] == 5.0
    assert fila["rechazos_perdidos"] == 5 * 2000.0 + 100 * 2.0
    # Sale de la operación normal y entra en su línea propia: la
    # mercadería y el envase se acreditan para no contarlo dos veces.
    assert fila["costo_mercaderia"] == 25 * 500.0 - 5 * 2000.0
    assert fila["costo_envase"] == 500.0 * 2.0 - 100 * 2.0
    # La renta es la misma que si nada se hubiera acreditado: lo que
    # cambia es que la pérdida ahora tiene nombre.
    assert fila["costo_total"] == 25 * 500.0 + 500.0 * 2.0 + fila["costo_mermas"]
    assert resultado["totales"]["rechazos_perdidos"] == fila["rechazos_perdidos"]
    assert resultado["totales"]["rechazos_bultos"] == 5.0


def test_rechazo_que_vuelve_a_cajon_grande_se_pierde_igual():
    # El destino "reproceso" (cajas chicas de vuelta a cajón) es la misma
    # pérdida: lo que cambia es el envase en que queda la segunda.
    fecha = date(2026, 8, 25)
    resultado = calcular_rentabilidad_real(
        _datos([_armado(fecha, 25, 500.0)]), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
        devoluciones=[_devolucion(5.0, fecha, destino="reproceso")],
    )

    assert resultado["grupos"][0]["filas"][0]["rechazos_perdidos"] == 5 * 2000.0 + 100 * 2.0


def test_rechazo_que_queda_en_stock_no_es_perdida():
    # Solo se perdió la venta del día: la mercadería vuelve y se va a
    # vender, así que no hay línea de rechazos perdidos.
    fecha = date(2026, 8, 25)
    resultado = calcular_rentabilidad_real(
        _datos([_armado(fecha, 25, 500.0)]), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
        devoluciones=[_devolucion(5.0, fecha, destino="stock")],
    )

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["rechazos_perdidos"] == 0.0
    assert fila["rechazos_bultos"] == 0.0
    assert fila["costo_envase"] == 500.0 * 2.0  # el envase no se toca


def test_rechazo_parcial_solo_pierde_lo_que_se_fue_a_segunda():
    # Dos cargas del mismo renglón: 3 quedan en stock y 2 van a segunda.
    fecha = date(2026, 8, 25)
    resultado = calcular_rentabilidad_real(
        _datos([_armado(fecha, 25, 500.0)]), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
        devoluciones=[
            _devolucion(3.0, fecha, destino="stock"),
            _devolucion(2.0, fecha, destino="segunda"),
        ],
    )

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["rechazos_bultos"] == 2.0
    assert fila["rechazos_perdidos"] == 2 * 2000.0 + 40 * 2.0
    # La venta se resta por los 5, sin importar el destino.
    assert fila["devoluciones_bultos"] == 5.0


def test_rechazo_a_segunda_sin_costo_congelado_va_afuera_con_motivo():
    # Se sabe que se perdió pero no cuánto: número chico y cierto.
    fecha = date(2026, 8, 25)
    resultado = calcular_rentabilidad_real(
        _datos([_armado(fecha, 25, 500.0)]), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
        devoluciones=[_devolucion(4.0, fecha, costo_por_bulto=None, destino="segunda")],
    )

    motivos = {r["motivo"]: r["bultos"] for r in resultado["afuera_por_motivo"]}
    assert motivos["rechazo_sin_costo"] == 4.0
    fila = resultado["grupos"][0]["filas"][0]
    assert fila["rechazos_perdidos"] == 0.0
    assert fila["devoluciones_bultos"] == 0.0


# --- Merma dirigida: se cuesta al lote elegido, no al más viejo ---


def test_merma_dirigida_se_cuesta_al_costo_de_su_lote():
    # El cajón viejo vale $500 y la guía R $1800. Si se pudre la guía R,
    # la pérdida es la de la guía R — no la del cajón que el FIFO elegiría.
    fecha = date(2026, 8, 25)
    entradas = [
        dict(_lote(1, 80, 500.0), origen_id=55),
        dict(_lote(2, 40, 1800.0, tipo_lote="reproceso"), origen_id=9),
    ]
    merma = {
        "orden": (fecha, 1), "tipo": "merma", "fecha": fecha, "cantidad": 10,
        "lote_tipo": "reproceso", "lote_origen_id": 9,
    }
    resultado = calcular_rentabilidad_real(
        _datos([merma], entradas=entradas), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
    )

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["costo_mermas"] == 10 * 1800.0
    assert fila["bultos_mermados"] == 10.0


def test_merma_sin_lote_elegido_sigue_saliendo_del_mas_viejo():
    fecha = date(2026, 8, 25)
    entradas = [
        dict(_lote(1, 80, 500.0), origen_id=55),
        dict(_lote(2, 40, 1800.0, tipo_lote="reproceso"), origen_id=9),
    ]
    merma = {"orden": (fecha, 1), "tipo": "merma", "fecha": fecha, "cantidad": 10}
    resultado = calcular_rentabilidad_real(
        _datos([merma], entradas=entradas), {fecha: {901: dict(MARGEN)}}, 1, fecha, fecha,
    )

    assert resultado["grupos"][0]["filas"][0]["costo_mermas"] == 10 * 500.0
