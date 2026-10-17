# -*- coding: utf-8 -*-
"""Panel de control: UN NÚMERO NUNCA SE PARTE EN DOS RENGLONES (dueño, 09/10).

En el celular "$8.379.000" salía "$8.379." arriba y "000" abajo, y "$5.378.446"
como "$5.378.44" y "6". Acá se arma el panel con montos de DIEZ cifras en
todos los cuadros y se mide en un navegador de verdad, a 390px y a 313px:

  · cada número entra en UN renglón (su alto no pasa de un renglón de su letra);
  · ninguno es más ancho que su lugar, ni ningún cuadro más ancho que él mismo;
  · la página no tiene scroll horizontal;
  · y el número dice entero lo que tiene que decir.

Lo que se prueba es la PANTALLA (plantilla + CSS + el script que achica la
letra), así que los datos se arman con las mismas funciones puras del panel,
con montos enormes, y se le dan a la ruta en vez de leerlos de la base.
"""
import os
import sys
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.panel_control import (  # noqa: E402
    estado_de_las_cajas,
    faltantes_por_unidad,
    resumen_de_rechazos,
    resumen_de_segunda,
)
from tests.test_administracion_reordenada import CLAVES, _cliente  # noqa: E402

HOY = date(2026, 10, 9)
MESES = {"anterior": {"desde": date(2026, 9, 1), "hasta": date(2026, 9, 30)},
         "actual": {"desde": date(2026, 10, 1), "hasta": HOY}}
DIEZ_CIFRAS = 8379000000.0                # "$8.379.000.000"
OTRAS_DIEZ = 5378446000.0                 # "$5.378.446.000"


def _segunda(cobrado):
    perdidas = {"renglones": {"segunda": {"total": OTRAS_DIEZ, "bultos": 1234567.0}}, "detalle": []}
    lotes = [{"articulo_id": 1, "articulo": "EJEMPLO Tomate", "importe": cobrado}]
    rechazos = [{"articulo_id": 1, "articulo": "EJEMPLO Tomate", "pesos": 0.0, "bultos": 0.0}]
    return resumen_de_segunda(perdidas, lotes, rechazos, rechazos_sin_costo=0.0)


def _datos(cuadro, hoy, memo):
    """Lo que cada cuadro le da a la plantilla, con números de diez cifras."""
    if cuadro == "rentabilidad":
        rangos = {"anterior": (MESES["anterior"]["desde"], MESES["anterior"]["hasta"]),
                  "actual": (MESES["actual"]["desde"], HOY), "semana": (HOY, HOY)}
        celda = {"pct": -123456.7, "venta": DIEZ_CIFRAS, "mercaderia": DIEZ_CIFRAS, "carton": DIEZ_CIFRAS,
                 "segunda": DIEZ_CIFRAS, "costo": DIEZ_CIFRAS, "ganancia": -DIEZ_CIFRAS, "afuera_bultos": 0.0}
        # Los remitos sin recibir son un CONTEO, no plata: 999 es más de lo que sale en un mes.
        recibido = dict(celda, pct=98765.4, sin_remitos=False, sin_recibir=999)
        return {"filas": [{"cliente_id": c, "cliente": f"EJEMPLO Cliente con nombre largo {c}", "rangos": rangos,
                           "armado": dict.fromkeys(rangos, celda), "recibido": dict.fromkeys(rangos, recibido)}
                          for c in (1, 2)],
                "rangos": rangos, "segunda_sin_repartir": dict.fromkeys(rangos, DIEZ_CIFRAS)}
    if cuadro == "cajas":
        return estado_de_las_cajas([{"id": i, "nombre": f"EJEMPLO Caja {i}", "stock": 0,
                                     "umbral_reposicion": 10} for i in range(12)])
    if cuadro == "pedidos":
        return {"pedidos": 1234567890, "renglones": []}
    if cuadro == "peso":
        compras = [{"cajones_recibidos": 3456789012, "contenido_comprado": 20, "contenido_recibido": 18,
                    "unidad_compra": u} for u in ("kilo", "unidad", "cubeta")]
        return {**{clave: dict(faltantes_por_unidad(compras), **rango) for clave, rango in MESES.items()},
                "desde_la_foto": None}
    if cuadro == "vales":
        from core.vales import vales_por_proveedor
        vales = [{"proveedor_id": 1, "proveedor": "EJEMPLO Proveedor con un nombre bastante largo SRL",
                  "importe": DIEZ_CIFRAS - 1}, {"proveedor_id": 2, "proveedor": "EJ Dos", "importe": 1.0}]
        return {"total": DIEZ_CIFRAS, "cantidad": 1234567890, "vales": vales,
                "por_proveedor": vales_por_proveedor(vales)}
    if cuadro == "vacios":
        return {"total": -1234567890, "proveedores": []}
    if cuadro == "rechazos":
        devoluciones = [{"bultos": 1234567890, "valor_por_bulto": 7.0}]
        return {clave: dict(resumen_de_rechazos(devoluciones, DIEZ_CIFRAS * 9, 9876543210.0), **rango)
                for clave, rango in MESES.items()}
    if cuadro == "mermas":
        return {clave: {"total": DIEZ_CIFRAS, "mercaderia": DIEZ_CIFRAS, "cajas": 0.0, "bultos": 1234567890.0,
                        "bultos_sin_costo": 0.0, "filas": [], **rango} for clave, rango in MESES.items()}
    if cuadro == "segunda":
        # Septiembre: el puesto pagó $1, se perdieron $5.378.445.999. Octubre:
        # pagó el doble del costo, se recuperaron $5.378.446.000.
        return {"anterior": dict(_segunda(1.0), **MESES["anterior"]),
                "actual": dict(_segunda(OTRAS_DIEZ * 2), **MESES["actual"])}
    if cuadro == "rinde":
        # Rinde de guías R (13/10): kilos de diez cifras y un artículo de nombre largo.
        from core.kilos_guia_r import resumen_del_rinde
        guias = [{"articulo_id": i, "articulo": f"EJEMPLO Morrón Rojo con un nombre largo {i}",
                  "consumos": [(1234567, 6789.0)], "primera": 900000, "segunda": 12345, "merma": 6789,
                  "kg_caja": 8000.0, "guardada_igual": i == 1} for i in (1, 2)]
        return {**resumen_del_rinde(guias), "desde": HOY, "hasta": HOY}
    if cuadro == "kilos":
        # Kilos al armar (13/10): diez cifras de renglones y de kilos.
        filas = [{"articulo_id": i, "articulo": f"EJEMPLO Morrón Rojo con un nombre largo {i}",
                  "renglones": 1234567890, "kg_diferencia": -DIEZ_CIFRAS if i == 2 else DIEZ_CIFRAS} for i in (1, 2)]
        return {"filas": filas, "renglones": 2469135780, "kg_diferencia": 0.5, "desde": HOY, "hasta": HOY}
    if cuadro == "perdida":
        # Pérdida total (13/10): montos de diez cifras, un % de cuatro y un
        # artículo de nombre largo en el top.
        from core.panel_control import resumen_de_perdida_total
        mermas = {"total": DIEZ_CIFRAS, "filas": [{"articulo_id": 1, "articulo": "EJEMPLO Morrón Rojo con un nombre largo",
                                                    "total": DIEZ_CIFRAS}]}
        faltante = {"pesos": -OTRAS_DIEZ, "guias_sin_cuenta": 12, "guias_sin_precio": 3,
                    "por_articulo": {2: {"articulo": "EJEMPLO Zapallito", "pesos": -OTRAS_DIEZ}}}
        return {clave: dict(resumen_de_perdida_total(mermas, _segunda(1.0), faltante, DIEZ_CIFRAS * 9), **rango)
                for clave, rango in MESES.items()}
    if cuadro == "cheques":
        # Cheques (13/10): diez cifras en cartera y en lo que entra.
        return {"en_cartera": DIEZ_CIFRAS, "cantidad_en_cartera": 1234, "entran_7_dias": OTRAS_DIEZ,
                "cantidad_entran": 567, "por_vencer": 12, "vencidos": 3, "rechazados": 4, "en_rojo": 19,
                "hasta": HOY}
    raise AssertionError(cuadro)


def _foto():
    """El tablero se lee de la FOTO (dueño, 09/10): la de todos los cuadros con
    diez cifras, pasada por el JSON como en la base, y un turno de las 14:00
    que falló después, para que el aviso de arriba también se mida."""
    from core.panel_foto import a_texto
    import app.main as m
    calculada = datetime(2026, 10, 9, 9, 1, tzinfo=timezone.utc)          # 06:01 de Argentina
    datos = a_texto({cuadro: _datos(cuadro, HOY, {}) for cuadro in m.CUADROS_DEL_PANEL})
    fallo = {"turno": datetime(2026, 10, 9, 17, 0, tzinfo=timezone.utc),
             "calculada_el": datetime(2026, 10, 9, 17, 2, tzinfo=timezone.utc), "ok": False}
    return {"calculada_el": calculada, "datos_json": datos}, [fallo]


def _paginas():
    import app.main as m
    buena, intentos = _foto()
    with patch.dict(os.environ, CLAVES), patch.object(m, "_hoy_argentina", return_value=HOY), \
            patch.object(m, "foto_buena_del_panel", return_value=buena), \
            patch.object(m, "intentos_automaticos_del_panel", return_value=intentos), \
            patch.object(m, "_datos_del_cuadro", side_effect=_datos):
        cliente = _cliente(m, "gerencia")
        paginas = {"/gerencia/panel": cliente.get("/gerencia/panel")}
        for cuadro in ("vales", "segunda", "mermas", "rechazos", "rinde", "kilos", "perdida", "cheques"):
            paginas[f"/gerencia/panel/{cuadro}"] = cliente.get(f"/gerencia/panel/{cuadro}")
    assert {r: p.status_code for r, p in paginas.items()} == {r: 200 for r in paginas}
    return {r: p.text for r, p in paginas.items()}


MEDIR = r"""() => {
  const numeros = [...document.querySelectorAll('[data-ajustar]')].map(n => {
    const estilo = getComputedStyle(n);
    const letra = parseFloat(estilo.fontSize);
    // El alto de UN renglón: medido con un clon de una sola letra.
    const clon = n.cloneNode(false); clon.textContent = '8'; clon.style.fontSize = estilo.fontSize;
    n.parentNode.insertBefore(clon, n); const renglon = clon.getBoundingClientRect().height; clon.remove();
    const propio = [...n.childNodes].filter(x => x.nodeType === 3).map(x => x.textContent).join('').trim();
    return {texto: propio, alto: n.getBoundingClientRect().height, renglon, letra,
            desborda: n.scrollWidth > n.clientWidth + 1, tieneHijos: n.children.length > 0};
  });
  const cajas = [...document.querySelectorAll('[data-ajustar-contenedor]')].map(c => ({
    desborda: c.scrollWidth > c.clientWidth + 1, ajustado: c.hasAttribute('data-ajustado')}));
  // TODOS los números escritos en la página, también los de adentro de una
  // frase: cada uno tiene que ocupar UN solo renglón.
  const partidos = [];
  let escritos = 0, palabras = 0;
  const palabrasPartidas = [];
  const caminante = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (caminante.nextNode()) {
    const nodo = caminante.currentNode;
    if (nodo.parentElement.closest('script, style')) continue;
    for (const m of nodo.textContent.matchAll(/-?\$?\d[\d.,]{4,}%?/g)) {
      escritos++;
      const rango = document.createRange();
      rango.setStart(nodo, m.index); rango.setEnd(nodo, m.index + m[0].length);
      const tops = new Set([...rango.getClientRects()].filter(r => r.width > 0).map(r => Math.round(r.top)));
      if (tops.size > 1) partidos.push(m[0]);
    }
    // Y las PALABRAS: con un número enorme al lado, una tabla angosta partía
    // el rótulo ("En plata") letra por letra en vez de achicar el número.
    for (const m of nodo.textContent.matchAll(/[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,}/g)) {
      palabras++;
      const rango = document.createRange();
      rango.setStart(nodo, m.index); rango.setEnd(nodo, m.index + m[0].length);
      const tops = new Set([...rango.getClientRects()].filter(r => r.width > 0).map(r => Math.round(r.top)));
      if (tops.size > 1) palabrasPartidas.push(m[0]);
    }
  }
  return {numeros, cajas, escritos, partidos, palabras, palabrasPartidas,
          pagina: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""


@pytest.mark.parametrize("ancho", [390, 313])
def test_ningun_NUMERO_del_panel_se_parte_ni_se_sale_con_DIEZ_cifras(ancho):
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    paginas = _paginas()
    tablero = paginas["/gerencia/panel"]
    # Lo que tiene que estar ENTERO en el tablero (el texto, antes de medir).
    for entero in ("$8.379.000.000", "$5.378.445.999", "$5.378.446.000", "-1234567890", "1234567890"):
        assert entero in tablero, entero
    assert "No se pudo actualizar a las 14:00." in tablero and "Actualizar ahora" in tablero
    # Las fechas vuelven de la foto como fechas: sin eso los meses salen vacíos, sin error.
    # Cuatro cuadros con dos meses: mermas, segunda, peso y pérdida total.
    assert tablero.count('<div class="mes">Septiembre</div>') == 4 and tablero.count('<div class="mes">Octubre (a hoy)</div>') == 4
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            medidas = {}
            for ruta, html in paginas.items():
                pagina = navegador.new_page(viewport={"width": ancho, "height": 900})
                pagina.set_content(html)
                medidas[ruta] = pagina.evaluate(MEDIR)
                pagina.close()
        finally:
            navegador.close()
    for ruta, m in medidas.items():
        assert m["pagina"] <= 0, (ruta, "scroll horizontal", m["pagina"])
        assert m["cajas"] and all(c["ajustado"] for c in m["cajas"]), ruta
        assert not [c for c in m["cajas"] if c["desborda"]], (ruta, "un cuadro se sale")
        # El testigo: hay números que medir.
        assert m["escritos"] >= (10 if ruta == "/gerencia/panel" else 1), (ruta, m["escritos"])
        assert m["partidos"] == [], (ruta, "números partidos en dos renglones", m["partidos"])
        assert m["palabras"] >= 10, (ruta, m["palabras"])
        assert m["palabrasPartidas"] == [], (ruta, "palabras partidas", m["palabrasPartidas"])
        if ruta == "/gerencia/panel":
            assert len(m["numeros"]) >= 15
        for n in m["numeros"]:
            assert not n["desborda"], (ruta, n)
            if not n["tieneHijos"]:
                assert n["alto"] <= n["renglon"] * 1.3, (ruta, "se partió en dos renglones", n)
            assert n["letra"] >= 7, (ruta, "letra ilegible", n)
    # El de Vales y los de Segunda, que eran los que se cortaban, medidos uno por uno.
    vales = [n for n in medidas["/gerencia/panel"]["numeros"] if n["texto"] == "$8.379.000.000"]
    assert len(vales) >= 2                                          # Vales y las Mermas de los dos meses
