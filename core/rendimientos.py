"""RENDIMIENTOS (dueño, 13/10): cuánto rinde lo que se compra, por artículo.

Dos mitades:

- Los que pasan por GUÍA R: la cuenta del cuadro "Rinde de guías R" del panel
  (`core.kilos_guia_r.rinde_por_articulo`, por guía): % aprovechado (primera),
  % segunda, % merma, % que falta sin registrar y % de pérdida total.
- Los que NO pasan por guía R: kg por cajón comprado contra kg por bulto
  enviado, y la diferencia en %. Positiva: se envía más de lo que trae el
  cajón (se factura de más); negativa: se envía menos (se regala). Ej. Uva 7,6
  contra 8,5 y Pera 18,6 contra 18.

Al lado de cada artículo, el % de pérdida que tienen cargado sus fichas, para
comparar con lo real.
"""

from core.kilos_guia_r import cuenta_de_kilos, kg_de_la_primera, rinde_por_articulo


def _con_la_perdida(fila: dict, perdidas: dict) -> dict:
    return {**fila, "perdida_ficha": perdidas.get(fila["articulo_id"], [])}


def diferencia_por_bulto(kg_por_cajon, kg_por_bulto) -> float | None:
    """(enviado − comprado) / comprado, en %. None si falta un lado."""
    if not kg_por_cajon or kg_por_bulto is None:
        return None
    return round((kg_por_bulto - kg_por_cajon) / kg_por_cajon * 100, 1)


def armar_rendimientos(guias: list[dict], sin_guia: list[dict], perdidas: dict) -> dict:
    """`guias` como las da `guias_r_con_sus_kilos`, `sin_guia` como
    `kilos_comprados_y_enviados` y `perdidas` como `perdidas_cargadas_por_articulo`."""
    con_guia = sorted((_con_la_perdida(f, perdidas) for f in rinde_por_articulo(guias)),
                      key=lambda f: (-(f["perdida_total_pct"] or 0), f["articulo"].lower()))
    filas_sin = []
    for fila in sin_guia:
        diferencia = diferencia_por_bulto(fila["kg_por_cajon"], fila["kg_por_bulto"])
        que_pasa = None
        if diferencia is not None and diferencia > 0:
            que_pasa = "se factura de más"
        elif diferencia is not None and diferencia < 0:
            que_pasa = "se regala"
        filas_sin.append({**_con_la_perdida(fila, perdidas), "diferencia_pct": diferencia,
                          "que_pasa": que_pasa})
    filas_sin.sort(key=lambda f: (-(abs(f["diferencia_pct"]) if f["diferencia_pct"] is not None else -1),
                                  f["articulo"].lower()))
    return {"con_guia": con_guia, "sin_guia": filas_sin,
            "resumen": resumen_de_rendimientos(guias, sin_guia)}


def texto_de_la_perdida(valores: list[float]) -> str:
    """Lo que tienen cargado las fichas del artículo: "18%", "0% a 18%" o "—"."""
    def pct(v):
        return f"{round(v * 100, 1):g}".replace(".", ",") + "%"
    if not valores:
        return "—"
    if len(valores) == 1:
        return pct(valores[0])
    return f"{pct(valores[0])} a {pct(valores[-1])}"


# --- EL RESUMEN DE ARRIBA (dueño, 15/10) ---------------------------------------
# Tres renglones PONDERADOS POR KILO (nunca el promedio de los % de cada
# artículo): las guías R, lo que no pasa por guía R, y el total. Cada uno con
# los kg que entraron y cuánto fue aprovechado (primera / enviado), segunda,
# merma y no explicado, la pérdida total (todo lo que no se aprovechó), y esa
# pérdida valuada al costo, con su % sobre lo que costó lo que entró.

def _renglon(nombre: str, kg: dict, plata: dict) -> dict:
    entraron = kg["entraron"]
    perdida = entraron - kg["aprovechado"]
    no_explicado = perdida - kg["segunda"] - kg["merma"]

    def pct(parte):
        return round(parte / entraron * 100, 1) if entraron else None

    return {
        "nombre": nombre, "entraron": round(entraron, 1), "aprovechado": round(kg["aprovechado"], 1),
        "segunda": round(kg["segunda"], 1), "merma": round(kg["merma"], 1),
        "no_explicado": round(no_explicado, 1), "perdida": round(perdida, 1),
        "aprovechado_pct": pct(kg["aprovechado"]), "segunda_pct": pct(kg["segunda"]),
        "merma_pct": pct(kg["merma"]), "no_explicado_pct": pct(no_explicado), "perdida_pct": pct(perdida),
        "costo": round(plata["costo"], 2), "perdida_pesos": round(plata["perdida"], 2),
        "perdida_costo_pct": round(plata["perdida"] / plata["costo"] * 100, 1) if plata["costo"] else None,
        "kg_sin_costo": round(plata["kg_sin_costo"], 1),
    }


def _sumar(destino: dict, origen: dict) -> None:
    for clave, valor in origen.items():
        destino[clave] = destino.get(clave, 0.0) + valor


def resumen_de_rendimientos(guias: list[dict], sin_guia: list[dict]) -> dict:
    """{"guias_r", "sin_procesar", "total"}, cada uno un renglón de `_renglon`.

    GUÍAS R: la cuenta de `rinde_por_articulo` POR GUÍA (cuenta_de_kilos y la
    primera real), sumada en kilos. El costo es el de `faltante_en_plata`: lo
    que costaron los cajones tomados (el precio de SU compra) sobre los kilos
    que pesaron. Una guía con algún cajón sin precio entra en los kilos y no
    en la plata (`kg_sin_costo`).

    SIN PROCESAR (los artículos sin guía R en el período, `sin_guia` como
    `kilos_comprados_y_enviados`): por artículo, lo que pesaban al comprarse
    los bultos que salieron —enviados, tirados y pasados a segunda— (bultos ×
    kg por cajón comprado) contra los kilos enviados. "No explicado" es la
    diferencia de peso de lo enviado; merma y segunda, sus bultos × kg por
    cajón. Al costo por kilo de sus compras del período. Un artículo sin
    kilos de un lado no entra (`articulos_sin_dato`).
    """
    kg_g, plata_g = {"entraron": 0.0, "aprovechado": 0.0, "segunda": 0.0, "merma": 0.0}, \
        {"costo": 0.0, "perdida": 0.0, "kg_sin_costo": 0.0}
    guias_sin_cuenta = 0
    for guia in guias:
        cuenta = cuenta_de_kilos(guia["consumos"], guia["primera"], guia["segunda"], guia["merma"],
                                 guia["kg_caja"])
        if cuenta is None:
            guias_sin_cuenta += 1
            continue
        entraron = sum(float(b) * float(kg) for b, kg in guia["consumos"])
        por_cajon = entraron / cuenta["tomados"]
        primera = kg_de_la_primera(guia["primera"], guia["kg_caja"], guia.get("primera_real"))
        _sumar(kg_g, {"entraron": entraron, "aprovechado": primera,
                      "segunda": float(guia["segunda"]) * por_cajon, "merma": float(guia["merma"]) * por_cajon})
        importes = guia.get("importes") or []
        if len(importes) != len(guia["consumos"]) or any(i is None or float(i) <= 0 for i in importes):
            plata_g["kg_sin_costo"] += entraron
            continue
        costo = sum(float(b) * float(i) for (b, _), i in zip(guia["consumos"], importes))
        _sumar(plata_g, {"costo": costo, "perdida": (entraron - primera) * costo / entraron})

    kg_s, plata_s = {"entraron": 0.0, "aprovechado": 0.0, "segunda": 0.0, "merma": 0.0}, \
        {"costo": 0.0, "perdida": 0.0, "kg_sin_costo": 0.0}
    comprado = enviado = 0.0
    sin_dato = 0
    for fila in sin_guia:
        por_cajon, bultos = fila.get("kg_por_cajon"), fila.get("bultos")
        if not por_cajon or not bultos or fila.get("kg_enviados") is None:
            sin_dato += 1
            continue
        merma = float(fila.get("bultos_merma") or 0) * por_cajon
        segunda = float(fila.get("bultos_segunda") or 0) * por_cajon
        de_lo_enviado = float(bultos) * por_cajon
        entraron = de_lo_enviado + merma + segunda
        comprado += de_lo_enviado
        enviado += float(fila["kg_enviados"])
        _sumar(kg_s, {"entraron": entraron, "aprovechado": float(fila["kg_enviados"]),
                      "segunda": segunda, "merma": merma})
        if fila.get("costo_por_kg"):
            _sumar(plata_s, {"costo": entraron * fila["costo_por_kg"],
                             "perdida": (entraron - float(fila["kg_enviados"])) * fila["costo_por_kg"]})
        else:
            plata_s["kg_sin_costo"] += entraron

    kg_t, plata_t = dict(kg_g), dict(plata_g)
    _sumar(kg_t, kg_s)
    _sumar(plata_t, plata_s)
    sin_procesar = _renglon("Sin procesar (promedio ponderado)", kg_s, plata_s)
    sin_procesar.update(kg_comprados=round(comprado, 1), kg_enviados=round(enviado, 1),
                        diferencia_pct=round((enviado - comprado) / comprado * 100, 1) if comprado else None)
    return {"guias_r": dict(_renglon("Guías R (promedio ponderado)", kg_g, plata_g),
                            guias_sin_cuenta=guias_sin_cuenta),
            "sin_procesar": dict(sin_procesar, articulos_sin_dato=sin_dato),
            "total": _renglon("TOTAL", kg_t, plata_t)}
