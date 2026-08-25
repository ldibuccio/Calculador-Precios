"""Tests del motor de Rentabilidad Real (core/costo_real.py) — puro, sin base."""

from datetime import date

from core.costo_real import atribuir_costos_fifo, calcular_rentabilidad_real


def _lote(orden, cantidad, costo, tipo_lote="guia"):
    return {"orden": orden, "cantidad": cantidad, "costo_bulto": costo, "tipo_lote": tipo_lote}


def _armado(fecha, cantidad, unidades, cliente_id=1, orden=None):
    return {
        "orden": orden if orden is not None else (fecha, 0),
        "tipo": "armado",
        "fecha": fecha,
        "cantidad": cantidad,
        "unidades": unidades,
        "cliente_id": cliente_id,
    }


# --- atribuir_costos_fifo ---


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
        {fecha: {1: dict(MARGEN)}},
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
        _datos(salidas), {fecha: {1: dict(MARGEN)}}, 1, fecha, fecha
    )

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["costo_mermas"] == 3 * 500.0
    assert fila["bultos_mermados"] == 3
    assert resultado["totales"]["costo_mermas"] == 1500.0
    # La merma baja la renta.
    assert fila["renta_pesos"] == fila["venta_neta"] - fila["costo_mercaderia"] - fila["costo_envase"] - 1500.0


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
        {fecha: {1: dict(MARGEN)}},
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
        {fecha: {1: dict(MARGEN)}},
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
        _datos(salidas), {fecha: {1: dict(MARGEN)}}, 1, fecha, fecha
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
        _datos(salidas, entradas=entradas), {fecha: {1: dict(MARGEN)}}, 1, fecha, fecha
    )

    fila = resultado["grupos"][0]["filas"][0]
    # El ajuste se comió el lote barato (corrección de registro, sin
    # pérdida reportada) y el armado costea contra el caro.
    assert fila["costo_mermas"] == 0
    assert fila["costo_mercaderia"] == 5 * 800.0


# --- devoluciones vinculadas ("si le mandé 25 y me devolvió 5, vendí 20") ---


def _devolucion(bultos, fecha_pedido, costo_por_bulto=2000.0, kilos=500.0, armados=25.0):
    return {
        "bultos": bultos,
        "fecha_pedido": fecha_pedido,
        "kilos_enviados": kilos,
        "bultos_armados": armados,
        "costo_por_bulto": costo_por_bulto,
        "articulo_id": 1,
        "articulo_nombre": "Banana",
        "grupo": "fruta",
    }


def test_devolucion_vinculada_resta_venta_y_acredita_mercaderia_al_costo_congelado():
    fecha = date(2026, 8, 25)
    salidas = [_armado(fecha, 25, 500.0)]
    resultado = calcular_rentabilidad_real(
        _datos(salidas), {fecha: {1: dict(MARGEN)}}, 1, fecha, fecha,
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
        _datos(salidas), {fecha: {1: dict(MARGEN)}}, 1, fecha, fecha,
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
        _datos([]), {fecha: {1: dict(MARGEN)}}, 1, fecha, fecha,
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
        fecha_pedido: {1: dict(MARGEN, precio_vigente=80.0)},
        fecha_rango: {1: dict(MARGEN)},
    }
    resultado = calcular_rentabilidad_real(
        _datos([]), margenes, 1, fecha_rango, fecha_rango,
        devoluciones=[_devolucion(5.0, fecha_pedido)],
    )

    fila = resultado["grupos"][0]["filas"][0]
    assert fila["devoluciones_venta"] == 100 * 80.0 * 0.9
