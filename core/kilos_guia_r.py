"""LOS KILOS NO DAN (dueño, 13/10): la cuenta de kilos de una guía R al cargarla.

Entraron: cada cajón tomado pesa lo que pesó un cajón de SU compra al
recibirla (`compras.contenido_por_cajon_real`, siempre peso neto).
Salieron: las cajas de primera por los kilos de la ficha, más los cajones de
segunda y de merma por el peso promedio del cajón que entró a la guía (son
cajones de origen, la misma cuenta de "Cómo rindió").

Si la diferencia pasa 0,8 kg por cajón tomado, para arriba o para abajo,
la pantalla muestra el cartel rojo. No frena: el operario puede revisar o
guardar igual, y si guarda igual la guía anota la diferencia.

No hay cuenta (devuelve None) cuando no se puede saber cuánto pesó algo: la
ficha no vende por kilo (Mango, por unidad), la guía no tiene ficha, o algún
cajón tomado no salió de una compra pesada en kilos.
"""

import math

# 0,8 kg por cajón tomado (dueño, 13/10: primero dijo medio kilo y lo
# subió a 0,8 el mismo día, con la R788 que no tenía que saltar).
TOLERANCIA_KG_POR_CAJON = 0.8


def kg_entero(kilos: float) -> int:
    """Kilos sin decimales, como se leen parado en el galpón. Medio para
    arriba: el `round` de Python redondea 286,5 a 286."""
    return math.floor(kilos + 0.5)


def kg_de_la_primera(primera, kg_caja_ficha, reales: dict | None = None) -> float:
    """Los kilos de las cajas de primera de una guía R (dueño, 13/10).

    Las cajas que ya salieron en un pedido con sus kilos cargados al armar
    (`reales` = {"bultos", "kg"}, de `kilos_reales_de_la_primera`) pesan lo
    que se mandó; las demás —en el piso, o armadas sin kilos— pesan lo de la
    ficha. Sin reales, es cajas × ficha, la cuenta de siempre.
    """
    primera = float(primera)
    if not reales or not reales.get("bultos"):
        return primera * float(kg_caja_ficha)
    con_reales = min(float(reales["bultos"]), primera)
    kg_reales = float(reales["kg"]) * con_reales / float(reales["bultos"])
    return kg_reales + (primera - con_reales) * float(kg_caja_ficha)


def cuenta_de_kilos(consumos: list[tuple], primera, segunda, merma, kg_caja_ficha) -> dict | None:
    """La cuenta de una guía R. `consumos` = [(bultos, kg pesados por cajón o None)].

    Devuelve {"entraron", "tomados", "salieron", "diferencia", "tolerancia",
    "no_dan", "kg_entraron", "kg_salieron", "kg_diferencia"}: `diferencia` =
    entraron − salieron (positiva = faltan, negativa = sobran). Las `kg_` son
    las del cartel, en kilos enteros, y la diferencia del cartel es la resta de
    los dos enteros que muestra: es la que queda anotada si guardan igual, así
    el cartel y la guía dicen el mismo número. None si no hay cuenta posible.
    """
    if kg_caja_ficha is None or float(kg_caja_ficha) <= 0 or not consumos:
        return None
    if any(kg is None or float(kg) <= 0 for _, kg in consumos):
        return None
    tomados = sum(float(b) for b, _ in consumos)
    if tomados <= 0:
        return None
    entraron = sum(float(b) * float(kg) for b, kg in consumos)
    kg_por_cajon = entraron / tomados
    salieron = (float(primera) * float(kg_caja_ficha)
                + (float(segunda) + float(merma)) * kg_por_cajon)
    diferencia = entraron - salieron
    tolerancia = TOLERANCIA_KG_POR_CAJON * tomados
    return {
        "entraron": round(entraron, 2),
        "tomados": tomados,
        "salieron": round(salieron, 2),
        "diferencia": round(diferencia, 2),
        "tolerancia": round(tolerancia, 2),
        "no_dan": round(abs(diferencia), 2) > round(tolerancia, 2),
        "kg_entraron": kg_entero(entraron),
        "kg_salieron": kg_entero(salieron),
        "kg_diferencia": kg_entero(entraron) - kg_entero(salieron),
    }


# RINDE DE GUÍAS R (dueño, 13/10): el cuadro del panel y la pantalla de
# Rendimientos. Un artículo con más de este % de falta se cuenta en rojo.
UMBRAL_FALTA_PCT = 5.0


def _pct(parte: float, total: float) -> float | None:
    return round(parte / total * 100, 1) if total else None


def rinde_por_articulo(guias: list[dict]) -> list[dict]:
    """Por artículo, lo que entró a sus guías R y a dónde fue, en kilos.

    Cada guía es {"articulo_id", "articulo", "consumos": [(bultos, kg pesados
    por cajón o None)], "primera", "segunda", "merma", "kg_caja",
    "guardada_igual", "primera_real"}; la primera pesa lo que se mandó en los
    pedidos que ya salieron de esa guía (`kg_de_la_primera`). La cuenta es la del cartel (`cuenta_de_kilos`), POR
    GUÍA y con los cajones que tomó cada guía, así no la ensucia cómo se
    repartieron las compras; la guía sin cuenta posible (sin pesada, ficha
    por unidad) no entra y se cuenta en `guias_sin_cuenta`.

    Falta % = (entraron − primera − segunda − merma) / entraron: lo que no
    quedó registrado. Pérdida total % = (entraron − primera) / entraron: todo
    lo que no salió de primera. De mayor a menor falta.
    """
    por_articulo: dict = {}
    for guia in guias:
        fila = por_articulo.setdefault(guia["articulo_id"], {
            "articulo_id": guia["articulo_id"], "articulo": guia["articulo"],
            "entraron": 0.0, "primera": 0.0, "segunda": 0.0, "merma": 0.0,
            "guias": 0, "guardadas_igual": 0, "guias_sin_cuenta": 0})
        cuenta = cuenta_de_kilos(guia["consumos"], guia["primera"], guia["segunda"],
                                 guia["merma"], guia["kg_caja"])
        if cuenta is None:
            fila["guias_sin_cuenta"] += 1
            continue
        kg_por_cajon = cuenta["entraron"] / cuenta["tomados"]
        fila["entraron"] += cuenta["entraron"]
        fila["primera"] += kg_de_la_primera(guia["primera"], guia["kg_caja"], guia.get("primera_real"))
        fila["segunda"] += float(guia["segunda"]) * kg_por_cajon
        fila["merma"] += float(guia["merma"]) * kg_por_cajon
        fila["guias"] += 1
        fila["guardadas_igual"] += 1 if guia.get("guardada_igual") else 0
    filas = []
    for fila in por_articulo.values():
        if not fila["guias"]:
            continue
        entraron = fila["entraron"]
        falta = entraron - fila["primera"] - fila["segunda"] - fila["merma"]
        filas.append({
            **{clave: fila[clave] for clave in ("articulo_id", "articulo", "guias",
                                                  "guardadas_igual", "guias_sin_cuenta")},
            "entraron": round(entraron, 1),
            "primera": round(fila["primera"], 1),
            "segunda": round(fila["segunda"], 1),
            "merma": round(fila["merma"], 1),
            "segunda_y_merma": round(fila["segunda"] + fila["merma"], 1),
            "falta": round(falta, 1),
            "falta_pct": _pct(falta, entraron),
            "primera_pct": _pct(fila["primera"], entraron),
            "segunda_pct": _pct(fila["segunda"], entraron),
            "merma_pct": _pct(fila["merma"], entraron),
            "perdida_total_pct": _pct(entraron - fila["primera"], entraron),
        })
    return sorted(filas, key=lambda f: (-(f["falta_pct"] or 0), f["articulo"].lower()))


def resumen_del_rinde(guias: list[dict]) -> dict:
    """El cuadro del panel: cuántos artículos pasan el 5% de falta, y el detalle."""
    filas = rinde_por_articulo(guias)
    return {
        "filas": filas,
        "con_falta": sum(1 for f in filas if (f["falta_pct"] or 0) > UMBRAL_FALTA_PCT),
        "umbral": UMBRAL_FALTA_PCT,
    }


def faltante_en_plata(guias: list[dict]) -> dict:
    """EL FALTANTE DE LAS GUÍAS R, EN PLATA (dueño, 13/10: cuadro "Pérdida
    total"): por guía, los kg que entraron menos primera, segunda y merma —la
    misma cuenta de `rinde_por_articulo`, con la primera real—, valuados al
    costo del kilo que entró: lo que costaron los cajones tomados (el precio de
    SU compra, `importes`, uno por consumo) sobre los kilos que pesaron.

    Una guía que sobra resta, como en el rinde. La guía sin cuenta de kilos no
    entra (`guias_sin_cuenta`), y la que tiene algún cajón de una compra sin
    precio tampoco (`guias_sin_precio`): no suman cero en silencio.

    Devuelve {"pesos", "por_articulo": {articulo_id: {"articulo", "pesos"}},
    "guias", "guias_sin_cuenta", "guias_sin_precio"}.
    """
    pesos, guias_con_plata, sin_cuenta, sin_precio = 0.0, 0, 0, 0
    por_articulo: dict = {}
    for guia in guias:
        cuenta = cuenta_de_kilos(guia["consumos"], guia["primera"], guia["segunda"],
                                 guia["merma"], guia["kg_caja"])
        if cuenta is None:
            sin_cuenta += 1
            continue
        importes = guia.get("importes") or []
        if len(importes) != len(guia["consumos"]) or any(i is None or float(i) <= 0 for i in importes):
            sin_precio += 1
            continue
        entraron = sum(float(b) * float(kg) for b, kg in guia["consumos"])
        kg_por_cajon = entraron / cuenta["tomados"]
        falta = (entraron - kg_de_la_primera(guia["primera"], guia["kg_caja"], guia.get("primera_real"))
                 - (float(guia["segunda"]) + float(guia["merma"])) * kg_por_cajon)
        costo_del_kilo = sum(float(b) * float(i) for (b, _), i in zip(guia["consumos"], importes)) / entraron
        plata = falta * costo_del_kilo
        pesos += plata
        guias_con_plata += 1
        fila = por_articulo.setdefault(guia["articulo_id"], {"articulo": guia["articulo"], "pesos": 0.0})
        fila["pesos"] += plata
    return {"pesos": round(pesos, 2), "guias": guias_con_plata,
            "por_articulo": {a: {**f, "pesos": round(f["pesos"], 2)} for a, f in por_articulo.items()},
            "guias_sin_cuenta": sin_cuenta, "guias_sin_precio": sin_precio}
