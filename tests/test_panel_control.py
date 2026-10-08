# -*- coding: utf-8 -*-
"""Panel de control de Gerencia (dueño, 08/10) — lo puro, sin base.

Ningún cuadro tiene una cuenta propia: estos tests miran que cada resumen
junte bien lo que le dan, y que la rentabilidad del panel sea la Real sin
mermas ni segunda (dueño, 08/10), con la pantalla de la Real intacta.
"""
from datetime import date

import pytest

from core.costo_real import calcular_rentabilidad_real
from core.panel_control import (
    estado_de_las_cajas,
    faltantes_por_unidad,
    kilos_debajo_del_peso,
    meses_para_comparar,
    resumen_de_mermas,
    resumen_de_rechazos,
    resumen_de_segunda,
    utilidad_de_ahora,
)

DIA = date(2026, 9, 10)
MARGEN = {"precio_vigente": 100.0, "costo_actual": 50.0, "costo_envase_unidad_venta": 0.0, "denominador_tasas": 1.0}


def _armado(cantidad, unidades, cliente_id, orden):
    return {"orden": (DIA, orden), "tipo": "armado", "fecha": DIA, "cantidad": cantidad, "unidades": unidades,
            "cliente_id": cliente_id, "ficha_id": 900 + cliente_id}


def _datos(salidas):
    return [{"articulo_id": 1, "nombre": "EJEMPLO Tomate", "grupo": "hortaliza",
             "entradas": [{"orden": (date(2026, 9, 1), 0), "cantidad": 100, "costo_bulto": 500.0, "tipo_lote": "guia"}],
             "salidas": salidas}]


# El GALPÓN: el cliente 1 se llevó 30 bultos, el 2 se llevó 10. Se tiraron 4
# ($2.000) y se pasaron 2 a segunda ($1.000), la caja de la merma vale $400 y
# el puesto pagó $300 por un lote de segunda.
SALIDAS = [
    _armado(30, 300.0, 1, 1),
    _armado(10, 100.0, 2, 2),
    {"orden": (DIA, 3), "tipo": "merma", "fecha": DIA, "cantidad": 4},
    {"orden": (DIA, 4), "tipo": "pase_a_segunda", "fecha": DIA, "cantidad": 2},
]
CAJAS = {("merma", 1): (4.0, 400.0)}
LOTES = [{"fecha": DIA, "importe": 300.0, "bultos": 2, "articulo_id": 1, "articulo": "EJEMPLO Tomate",
          "grupo": "hortaliza"}]
MARGENES = {DIA: {901: dict(MARGEN), 902: dict(MARGEN)}}


def _real(cliente_id, solo_lo_vendido):
    return calcular_rentabilidad_real(_datos(SALIDAS), MARGENES, cliente_id, DIA, DIA, cajas_del_deposito=CAJAS,
                                      segunda=LOTES, solo_lo_vendido=solo_lo_vendido)


def test_el_PANEL_es_venta_contra_costo_de_lo_vendido_SIN_mermas_ni_segunda():
    panel = _real(1, True)["totales"]
    assert (panel["costo_mermas"], panel["costo_segunda"], panel["recupero_segunda"]) == (0, 0, 0)
    # 300 kg × $100 = $30.000 contra 30 bultos × $500 = $15.000.
    assert panel["venta_neta"] == 30000 and panel["costo_mercaderia"] == 15000
    assert panel["utilidad_pct"] == pytest.approx(100.0)


def test_la_pantalla_de_RENTABILIDAD_REAL_no_cambia_y_la_diferencia_son_las_mermas_y_la_segunda():
    pantalla, panel = _real(1, False)["totales"], _real(1, True)["totales"]
    assert pantalla["costo_mermas"] == pytest.approx(2400)              # el testigo: hay merma con su caja
    assert pantalla["costo_segunda"] == pytest.approx(1000) and pantalla["recupero_segunda"] == 300
    assert panel["renta_pesos"] == pytest.approx(
        pantalla["renta_pesos"] + pantalla["costo_mermas"] + pantalla["costo_segunda"] - pantalla["recupero_segunda"])


def test_un_cliente_SIN_VENTAS_no_aparece_con_las_mermas_de_otro():
    """El RIVAL: Pedidos Ya, sin ventas, no puede salir con la merma del tomate de Día."""
    resultado = _real(3, True)
    assert resultado["grupos"] == [] and resultado["totales"]["costo_mermas"] == 0


def _ficha(utilidad, facturado):
    return {"utilidad_aproximada": utilidad, "facturado": facturado}


def test_AHORA_con_ventas_es_el_PROMEDIO_PONDERADO_de_Margenes():
    """Σ(utilidad × facturado) / Σ(facturado), solo las que facturaron y tienen utilidad."""
    resultado = utilidad_de_ahora([_ficha(0.20, 3000), _ficha(0.40, 1000),
                                   _ficha(0.90, None),          # no facturó: no pesa
                                   _ficha(None, 5000)])         # sin utilidad: no pesa
    assert resultado == {"pct": pytest.approx(25.0), "sin_ventas": False, "fichas": 2}


def test_AHORA_sin_ventas_es_el_PROMEDIO_SIMPLE_marcado_sin_ventas():
    assert utilidad_de_ahora([_ficha(0.20, None), _ficha(0.40, 0), _ficha(None, None)]) == {
        "pct": pytest.approx(30.0), "sin_ventas": True, "fichas": 2}
    assert utilidad_de_ahora([_ficha(None, None)]) == {"pct": None, "sin_ventas": True, "fichas": 0}


def test_CAJAS_rojo_debajo_del_umbral_y_sin_umbral_no_es_rojo():
    envases = [
        {"id": 1, "nombre": "EJEMPLO Caja A", "stock": 5, "umbral_reposicion": 10},
        {"id": 2, "nombre": "EJEMPLO Caja B", "stock": 10, "umbral_reposicion": 10},   # justo: bien
        {"id": 3, "nombre": "EJEMPLO Caja C", "stock": -2, "umbral_reposicion": None},
        {"id": 4, "nombre": "EJEMPLO Caja D", "stock": None, "umbral_reposicion": 10},
        {"id": 5, "nombre": "EJEMPLO Caja E", "stock": 50, "umbral_reposicion": 10},
    ]
    resultado = estado_de_las_cajas(envases)
    assert resultado["bajas"] == 1
    assert [(f["id"], f["estado"]) for f in resultado["filas"]] == [
        (1, "bajo"), (2, "bien"), (5, "bien"), (3, "sin_umbral"), (4, "sin_conteo")]


def _pesada(cajones, declarado, pesado):
    return {"cajones_recibidos": cajones, "contenido_comprado": declarado, "contenido_recibido": pesado}


def test_DEBAJO_DEL_PESO_suma_solo_lo_que_falto_sobre_lo_declarado():
    # 10 cajones de 20 kg que pesaron 18: faltan 20 de 200. 5 de 20 que pesaron
    # 21: sobran 5 y NO compensan. Declarados: 200 + 100 = 300. 20 / 300.
    resultado = kilos_debajo_del_peso([_pesada(10, 20, 18), _pesada(5, 20, 21)])
    assert resultado["pct"] == pytest.approx(20 / 300 * 100)
    assert (resultado["declarados"], resultado["faltante"], resultado["compras"]) == (300, 20, 2)
    assert [f["diferencia"] for f in resultado["filas"]] == [-20, 5]
    assert kilos_debajo_del_peso([])["pct"] is None


def test_RECHAZOS_al_costo_contra_la_facturacion_y_los_bultos():
    devoluciones = [{"bultos": 5, "valor_por_bulto": 2000.0}, {"bultos": 3, "valor_por_bulto": 1500.0},
                    {"bultos": 2, "valor_por_bulto": None}]
    resultado = resumen_de_rechazos(devoluciones, facturacion=290000.0, bultos_vendidos=200.0)
    assert resultado["pesos"] == 14500.0                       # el que no tiene valor no suma cero
    assert resultado["bultos"] == 10 and resultado["bultos_sin_valor"] == 2
    assert resultado["pct_plata"] == pytest.approx(5.0)
    assert resultado["pct_bultos"] == pytest.approx(5.0)
    assert resumen_de_rechazos([], 0.0, 0.0)["pct_plata"] is None


def test_los_MESES_son_el_anterior_entero_y_el_actual_a_hoy():
    assert meses_para_comparar(date(2026, 10, 8)) == {
        "anterior": {"desde": date(2026, 9, 1), "hasta": date(2026, 9, 30)},
        "actual": {"desde": date(2026, 10, 1), "hasta": date(2026, 10, 8)}}
    assert meses_para_comparar(date(2027, 1, 1))["anterior"] == {"desde": date(2026, 12, 1), "hasta": date(2026, 12, 31)}


def test_DEBAJO_DEL_PESO_cada_unidad_se_suma_SOLA_y_ninguna_compra_queda_afuera():
    compras = [dict(_pesada(10, 20, 18), unidad_compra="kilo"), dict(_pesada(4, 8, 6), unidad_compra="unidad"),
               dict(_pesada(2, 5, 5), unidad_compra="cubeta"), dict(_pesada(5, 20, 20), unidad_compra=None)]
    resultado = faltantes_por_unidad(compras)
    assert resultado["kilo"]["pct"] == pytest.approx(20 / 300 * 100)      # la de unidad vacía es kilo
    assert resultado["unidad"]["pct"] == pytest.approx(8 / 32 * 100)
    assert resultado["cubeta"]["pct"] == pytest.approx(0)
    assert sum(r["compras"] for r in resultado.values()) == len(compras)


PERDIDAS = {
    "renglones": {"merma": {"total": 2400.0, "mercaderia": 2000.0, "caja_pesos": 400.0, "bultos": 4.0,
                            "bultos_sin_costo": 0.0},
                  "segunda": {"total": 1000.0, "mercaderia": 1000.0, "caja_pesos": 0.0, "bultos": 2.0,
                              "bultos_sin_costo": 0.0}},
    "detalle": [{"destino": "merma", "articulo_id": 1, "articulo": "EJEMPLO Tomate", "bultos": 4.0, "total": 2400.0},
                {"destino": "segunda", "articulo_id": 1, "articulo": "EJEMPLO Tomate", "bultos": 2.0, "total": 1000.0}],
}


def test_MERMAS_es_el_renglon_de_Perdidas_con_su_detalle():
    resultado = resumen_de_mermas(PERDIDAS)
    assert (resultado["total"], resultado["mercaderia"], resultado["cajas"], resultado["bultos"]) == (2400, 2000, 400, 4)
    assert [f["destino"] for f in resultado["filas"]] == ["merma"]


def test_SEGUNDA_es_el_costo_de_TODO_lo_que_fue_a_segunda_MENOS_lo_que_pago_el_puesto():
    lotes = [{"articulo_id": 1, "articulo": "EJEMPLO Tomate", "importe": 300.0},
             {"articulo_id": 2, "articulo": "EJEMPLO Zapallo", "importe": 50.0},     # cobrado sin nada en el mes
             {"articulo_id": 1, "articulo": "EJEMPLO Tomate", "importe": None}]     # sin cobrar: no suma cero
    rechazos = [{"articulo_id": 1, "articulo": "EJEMPLO Tomate", "pesos": 600.0, "bultos": 3.0}]
    resultado = resumen_de_segunda(PERDIDAS, lotes, rechazos, rechazos_sin_costo=2.0)
    assert resultado["por_origen"] == {"pase": 1000.0, "rechazo": 600.0, "reproceso": 0.0}
    assert (resultado["perdida"], resultado["costo"], resultado["cobrado"]) == (1250.0, 1600.0, 350.0)
    assert (resultado["bultos"], resultado["rechazos_sin_costo"], resultado["lotes_sin_cobrar"]) == (5.0, 2.0, 1)
    assert [(f["articulo"], f["pase"], f["rechazo"], f["perdida"]) for f in resultado["filas"]] == [
        ("EJEMPLO Tomate", 1000.0, 600.0, 1300.0), ("EJEMPLO Zapallo", 0.0, 0.0, -50.0)]


def test_un_RECHAZO_a_segunda_que_se_COBRA_no_da_perdida_NEGATIVA():
    """Sin pases: lo único que fue a segunda es un rechazo de $2.000 y el
    puesto pagó $800. Lo perdido es $1.200, no −$800."""
    sin_pases = {"renglones": {"segunda": {"total": 0.0, "bultos": 0.0}}, "detalle": []}
    resultado = resumen_de_segunda(sin_pases, [{"articulo_id": 1, "articulo": "EJEMPLO Tomate", "importe": 800.0}],
                                   [{"articulo_id": 1, "articulo": "EJEMPLO Tomate", "pesos": 2000.0, "bultos": 4.0}],
                                   rechazos_sin_costo=0.0)
    assert resultado["perdida"] == 1200.0

