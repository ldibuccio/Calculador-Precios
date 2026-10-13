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

from core.kilos_guia_r import rinde_por_articulo


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
    return {"con_guia": con_guia, "sin_guia": filas_sin}


def texto_de_la_perdida(valores: list[float]) -> str:
    """Lo que tienen cargado las fichas del artículo: "18%", "0% a 18%" o "—"."""
    def pct(v):
        return f"{round(v * 100, 1):g}".replace(".", ",") + "%"
    if not valores:
        return "—"
    if len(valores) == 1:
        return pct(valores[0])
    return f"{pct(valores[0])} a {pct(valores[-1])}"
