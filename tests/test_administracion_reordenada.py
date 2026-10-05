"""El reorden de Administración (dueño, 04/10).

(La franja de arriba, Tareas y Alertas, la cuida tests/test_franja_hubs.py.)

2. Cuatro grupos de botones: Stock, Pedidos, Facturación y cobranzas, Cajas y
   vacíos. Evolución y Movimientos quedan en Stock hasta que el dueño decida.
3. Cotejo y Ajustar Stock son UNA pantalla: la diferencia y el ajuste en la
   misma tarjeta. No cambia ninguna regla del ajuste.
4. Stock inicial del corte sale de Administración y queda SOLO en Gerencia.

Ningún botón desaparece del sistema, y cada pantalla vieja sigue abriendo.
Contra Postgres donde lo que se afirma sale de una consulta; los nombres son
de EJEMPLO.
"""
import os
import re
import sys
from datetime import date, timedelta
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

# La base real y su siembra: las MISMAS que usa el Cotejo de la segunda.
from tests.test_segunda_negativa import base_real, galpon  # noqa: E402,F401

CLAVES = {"CLAVE_ADMINISTRACION": "admin-secreta", "CLAVE_GERENCIA": "gerencia-secreta",
          "CLAVE_COMPRAS": "compras-secreta"}

# LO DECIDIDO (dueño, 04/10), grupo por grupo y en orden. Evolución y
# Movimientos son pestañas de Stock del depósito (aprobado el 04/10).
GRUPOS_DECIDIDOS = {
    "Stock": [
        ("/administracion/stock/remanente", "Stock del Depósito"),
        ("/administracion/stock/cotejo", "Cotejo y ajuste"),
        ("/administracion/stock/guias-r", "Guías R"),
        ("/administracion/devolver", "Devolver mercadería"),
    ],
    "Pedidos": [
        ("/deposito/pedido/cargar", "Cargar pedido"),
        ("/administracion/pedidos/buscar", "Armar remito"),
        # Vino entera de Sistema el 04/10 (dueño: "Todo a Administración").
        ("/administracion/casilla-pedidos", "Casilla de pedidos"),
        # Fletes (dueño, 05/10): un botón con tres pestañas.
        ("/administracion/fletes/dia", "Fletes"),
    ],
    "Facturación y cobranzas": [
        ("/administracion/facturacion", "Remitos y facturas"),
        ("/administracion/precios-por-periodo", "Precios por período"),
        ("/administracion/vales", "Vales a cobrar"),
        ("/administracion/cobranzas-segunda", "Cobranzas de segunda"),
        ("/administracion/ingresos", "Movimientos del depósito"),
    ],
    "Cajas y vacíos": [
        ("/administracion/cajas", "Cajas"),
        ("/administracion/vacios", "Vacíos del depósito"),
    ],
}

# LOS 18 BOTONES QUE TENÍA EL HUB hasta el 04/10. Cada uno tiene que seguir
# alcanzable: en el hub, o donde se decidió.
BOTONES_VIEJOS = (
    "/administracion/alertas", "/administracion/stock/remanente", "/administracion/stock/evolucion",
    "/administracion/stock/cotejo", "/administracion/stock/ajustar", "/administracion/stock/movimientos",
    "/administracion/stock/guias-r", "/administracion/stock/inicial", "/administracion/devolver",
    "/deposito/pedido/cargar", "/administracion/pedidos/buscar", "/administracion/facturacion",
    "/administracion/ingresos", "/administracion/vales", "/administracion/precios-por-periodo",
    "/administracion/cobranzas-segunda", "/administracion/cajas", "/administracion/vacios",
)
# Los que salieron del hub y DÓNDE quedaron: (pantalla, lo que la lleva).
SE_MUDARON = {
    "/administracion/stock/ajustar": ("/administracion/stock/cotejo", 'action="/administracion/stock/ajustar"'),
    "/administracion/stock/inicial": ("/gerencia", 'href="/gerencia/stock/inicial"'),
    "/administracion/stock/evolucion": ("/administracion/stock/remanente", 'href="/administracion/stock/evolucion"'),
    "/administracion/stock/movimientos": ("/administracion/stock/remanente",
                                          'href="/administracion/stock/movimientos"'),
}


def _cliente(m, *puertas):
    from fastapi.testclient import TestClient
    cliente = TestClient(m.app, base_url="https://testserver")
    for puerta in puertas:
        clave = {"administracion": "admin-secreta", "gerencia": "gerencia-secreta",
                 "compras": "compras-secreta"}[puerta]
        objeto = getattr(m, f"PUERTA_{puerta.upper()}")
        cliente.cookies.set(objeto.cookie, objeto.firma(clave))
    return cliente


_BOTON = re.compile(r'<a class="boton color-(\d)" href="([^"]*)"><svg [^>]*>.*?</svg><span>([^<]*)</span></a>', re.S)


def _grupos(marcado):
    """{título: [(href, texto)]} de cada tarjeta con <h2> del hub."""
    return {t: [(h, x) for _c, h, x in botones] for t, botones in _grupos_con_color(marcado).items()}


def _grupos_con_color(marcado):
    """{título: [(color, href, texto)]}: cada botón con su dibujo y su color."""
    grupos = {}
    for tarjeta in marcado.split('<div class="tarjeta">')[1:]:
        titulo = re.search(r"<h2>([^<]*)</h2>", tarjeta)
        if titulo:
            grupos[titulo.group(1)] = _BOTON.findall(tarjeta)
    return grupos


# --- 2. Los grupos ----------------------------------------------------------------

def test_el_hub_tiene_los_CUATRO_grupos_con_EXACTAMENTE_sus_botones():
    import app.main as m
    with patch.dict(os.environ, CLAVES):
        marcado = _cliente(m, "administracion").get("/administracion").text.split("</style>")[-1]
    assert _grupos(marcado) == GRUPOS_DECIDIDOS
    # y no hay botones sueltos fuera de los grupos, ni botones sin dibujo
    assert marcado.count('<a class="boton ') == sum(len(b) for b in GRUPOS_DECIDIDOS.values())
    # UN COLOR POR RECUADRO, en orden y volviendo a empezar (dueño, 04/10)
    colores = {t: {c for c, _h, _x in b} for t, b in _grupos_con_color(marcado).items()}
    assert colores == {"Stock": {"1"}, "Pedidos": {"2"}, "Facturación y cobranzas": {"3"}, "Cajas y vacíos": {"1"}}
    # el Stock inicial del corte y el Ajustar Stock suelto ya no están en el hub
    assert 'href="/administracion/stock/inicial"' not in marcado
    assert 'href="/administracion/stock/ajustar"' not in marcado


def test_NINGUN_boton_viejo_desaparece_y_cada_pantalla_VIEJA_sigue_abriendo(galpon):
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "administracion", "gerencia")
        hub = cliente.get("/administracion").text.split("</style>")[-1]
        en_el_hub = set(re.findall(r'href="(/[^"?#]*)"', hub))
        donde = {}
        for viejo in BOTONES_VIEJOS:
            if viejo in en_el_hub:
                continue
            pantalla, marca = SE_MUDARON[viejo]
            donde[viejo] = cliente.get(pantalla).text.split("</style>")[-1].count(marca)
        abren = {ruta: cliente.get(ruta).status_code
                 for ruta in BOTONES_VIEJOS + ("/administracion/stock/ajustar-segunda", "/gerencia/stock/inicial")}
    # los que se mudaron son EXACTAMENTE los decididos, y están donde se decidió
    assert set(donde) == set(SE_MUDARON)
    assert donde["/administracion/stock/inicial"] == 1
    assert donde["/administracion/stock/ajustar"] >= 1
    assert abren == {ruta: 200 for ruta in abren}, {r: c for r, c in abren.items() if c != 200}


# --- 4. Stock inicial del corte, solo en Gerencia ---------------------------------------

def test_STOCK_INICIAL_por_Gerencia_saca_la_barra_los_formularios_y_el_volver_del_PREFIJO(galpon):
    _d, m, _sql, _corte, articulo, *_ = galpon
    art = articulo("EJEMPLO Banana Inicial")       # con artículo elegido salen los formularios de carga
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "gerencia")
        ger = cliente.get(f"/gerencia/stock/inicial?articulo_id={art}").text
        cliente_admin = _cliente(m, "administracion")
        adm = cliente_admin.get(f"/administracion/stock/inicial?articulo_id={art}").text
    for entera, base, nombre in ((ger, "/gerencia", "Gerencia"), (adm, "/administracion", "Administración")):
        # la barra trae su propio <style>: el atrás se busca en la página entera (corolario 50)
        assert f'<a class="barra-boton" href="{base}" aria-label="Volver atrás">' in entera, base
        marcado = entera.split("</style>")[-1]
        otra = "/administracion" if base == "/gerencia" else "/gerencia"
        assert marcado.count(f'action="{base}/stock/inicial"') == 1, base               # elegir
        assert marcado.count(f'action="{base}/stock/inicial/sueltos"') == 1, base       # cargar sueltos
        assert f'action="{otra}/stock/inicial' not in marcado
        assert f'<a class="volver" href="{base}">Volver a {nombre}</a>' in marcado


def test_STOCK_INICIAL_por_Gerencia_pide_SU_clave_y_vuelve_a_Gerencia():
    import app.main as m
    with patch.dict(os.environ, CLAVES):
        sin = _cliente(m, "administracion")          # la de Administración NO abre Gerencia
        assert sin.get("/gerencia/stock/inicial").status_code == 401
        with patch("app.main.crear_stock_inicial") as crear:
            rechazado = sin.post("/gerencia/stock/inicial/sueltos", follow_redirects=False,
                                 data={"articulo_id": "7", "bultos": "40", "costo_por_bulto": "1500"})
        assert rechazado.status_code != 303 and not crear.called
        con = _cliente(m, "gerencia")
        with patch("app.main.obtener_articulo", return_value={"id": 7, "nombre": "EJ Banana"}), \
             patch("app.main.crear_stock_inicial", return_value=40.0) as crear, \
             patch("app.main.fecha_corte", return_value=date(2026, 8, 31)):
            guardado = con.post("/gerencia/stock/inicial/sueltos", follow_redirects=False,
                                data={"articulo_id": "7", "bultos": "40", "costo_por_bulto": "1500"})
    assert guardado.status_code == 303
    assert guardado.headers["location"].startswith("/gerencia/stock/inicial?articulo_id=7")
    crear.assert_called_once_with(7, 40.0, 1500.0, date(2026, 8, 31))


# --- 3. Cotejo y ajuste -----------------------------------------------------------

def _sembrar_cotejo(sql, articulo, corte):
    """Un artículo con 10 sueltos según el sistema y 7 contados (diferencia +3),
    y el RIVAL: uno contado igual al sistema, que no lleva ajuste."""
    dia = corte + timedelta(days=20)
    arts = {}
    for nombre, contado in (("EJEMPLO Limon Cotejo", 7), ("EJEMPLO Pera Cotejo", 10)):
        art = articulo(nombre)
        sql("""INSERT INTO movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema)
               VALUES (%s, 'ajuste', 10, 'EJEMPLO', %s, 0)""", (art, corte + timedelta(days=5)))
        sql("INSERT INTO conteos_stock (articulo_id, cantidad, stock_sistema, creado_en) VALUES (%s, %s, 0, %s)",
            (art, contado, f"{dia.isoformat()} 16:00-03"))
        arts[nombre] = art
    return arts, dia


def _tarjeta(marcado, nombre):
    (tarjeta,) = [t for t in marcado.split('<div class="tarjeta') if f'encabezado">{nombre}' in t]
    return tarjeta


def test_COTEJO_Y_AJUSTE_propone_la_diferencia_del_dia_y_guarda_desde_la_TARJETA(galpon):
    _d, m, sql, corte, articulo, *_ = galpon
    arts, dia = _sembrar_cotejo(sql, articulo, corte)
    limon, pera = arts["EJEMPLO Limon Cotejo"], arts["EJEMPLO Pera Cotejo"]
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "administracion")
        marcado = cliente.get("/administracion/stock/cotejo").text.split("</style>")[-1]
        tarjeta = _tarjeta(marcado, next(n for n in re.findall(r'encabezado">([^<]*)<', marcado)
                                         if n.startswith("EJEMPLO Limon Cotejo")))
        rival = _tarjeta(marcado, next(n for n in re.findall(r'encabezado">([^<]*)<', marcado)
                                       if n.startswith("EJEMPLO Pera Cotejo")))
        # la pantalla vieja, con el mismo conteo, propone LO MISMO
        vieja = cliente.get(f"/administracion/stock/ajustar?articulo_id={limon}&contado=7"
                            f"&fecha_conteo={dia.isoformat()}").text.split("</style>")[-1]
        guardado = cliente.post("/administracion/stock/ajustar", follow_redirects=False,
                                data={"articulo_id": str(limon), "cantidad": "-3", "volver": "cotejo",
                                      "motivo": f"Conteo del {dia.strftime('%d/%m')}: EJEMPLO"})
        despues = cliente.get(guardado.headers["location"]).text.split("</style>")[-1]
        sin_motivo = cliente.post("/administracion/stock/ajustar", follow_redirects=False,
                                  data={"articulo_id": str(limon), "cantidad": "-3", "motivo": " ",
                                        "volver": "cotejo"})
        con_error = cliente.get(sin_motivo.headers["location"]).text.split("</style>")[-1]
    assert '<title>Cotejo y ajuste</title>' in cliente.get("/administracion/stock/cotejo").text
    # la tarjeta con diferencia lleva el formulario, propuesto, que vuelve acá
    assert tarjeta.count('action="/administracion/stock/ajustar"') == 1
    assert '<input type="hidden" name="volver" value="cotejo">' in tarjeta
    assert f'<input type="hidden" name="articulo_id" value="{limon}">' in tarjeta
    assert re.search(r'name="cantidad" step="0.01" required[^>]*value="-3.0"', tarjeta)
    assert re.search(r'<details class="ajuste-aca" data-ajuste="primera">', tarjeta)   # plegado
    assert re.search(r'name="cantidad" step="0.01" required[^>]*value="-3.0"', vieja)
    # el rival, sin diferencia, no lleva ajuste
    assert "ajuste-aca" not in rival
    # guardado: vuelve al cotejo con el aviso, y el movimiento está en la base
    assert guardado.status_code == 303
    assert guardado.headers["location"].startswith("/administracion/stock/cotejo?aviso=")
    assert '<div class="mensaje bien" role="status">Ajuste guardado: -3 bultos de EJEMPLO Limon Cotejo' in despues
    assert sql("SELECT cantidad FROM movimientos_stock WHERE articulo_id = %s AND tipo = 'ajuste' "
               "ORDER BY id", (limon,)) == [(10,), (-3,)]
    # sin motivo no se guarda, y el error se ve en la misma pantalla
    assert sin_motivo.headers["location"].startswith("/administracion/stock/cotejo?error=")
    assert ('<div class="mensaje mal" role="alert">El motivo es obligatorio: sin motivo no se guarda el '
            'ajuste.</div>') in con_error
    assert sql("SELECT count(*) FROM movimientos_stock WHERE articulo_id IN (%s, %s) AND tipo = 'ajuste'",
               (limon, pera)) == [(3,)]


def test_el_AJUSTE_SIN_CONTEO_vive_en_la_misma_pantalla_plegado():
    import app.main as m
    with patch.dict(os.environ, CLAVES), \
         patch("app.main.listar_ultimos_conteos_stock", return_value=[]), \
         patch("app.main.listar_articulos", return_value=[{"id": 7, "nombre": "EJ Banana"}]), \
         patch("app.main._corte_o_none", return_value=date(2026, 8, 31)):
        marcado = _cliente(m, "administracion").get("/administracion/stock/cotejo").text.split("</style>")[-1]
    sin_conteo = marcado.split('id="sin-conteo"')[1].split('<a class="volver"')[0]
    assert '<details class="ajuste-aca" data-ajuste="sin-conteo">' in sin_conteo
    assert sin_conteo.count('action="/administracion/stock/ajustar"') == 1
    assert '<option value="7">EJ Banana</option>' in sin_conteo
    assert '<input type="hidden" name="volver" value="cotejo">' in sin_conteo
    # los ajustes de segunda ya cargados, con su Anular, siguen a un toque
    assert 'href="/administracion/stock/ajustar-segunda">Ajustes de segunda cargados</a>' in sin_conteo


# --- Las pestañas de Stock del depósito ------------------------------------------------

PESTANAS = {"hoy": "/administracion/stock/remanente", "evolucion": "/administracion/stock/evolucion",
            "movimientos": "/administracion/stock/movimientos"}


def test_STOCK_DEL_DEPOSITO_tiene_las_pestanas_Hoy_Evolucion_Movimientos_en_sus_tres_pantallas(galpon):
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "administracion")
        paginas = {activa: cliente.get(ruta).text for activa, ruta in PESTANAS.items()}
    for activa, entera in paginas.items():
        marcado = entera.split("</style>")[-1]
        (nav,) = re.findall(r'<nav class="pestanas" aria-label="Stock del depósito">(.*?)</nav>', marcado, re.S)
        links = re.findall(r'<a href="([^"]+)"( aria-current="page")?>([^<]+)</a>', nav)
        assert [(h, t) for h, _a, t in links] == [(PESTANAS["hoy"], "Hoy"), (PESTANAS["evolucion"], "Evolución"),
                                                    (PESTANAS["movimientos"], "Movimientos")]
        assert [h for h, a, _t in links if a] == [PESTANAS[activa]], activa      # UNA activa, la suya


# --- Cajas: los tipos de caja y su costo en Administración ----------------------------------

def test_los_TIPOS_DE_CAJA_se_cargan_desde_Cajas_de_Administracion_y_el_costo_es_EL_MISMO(galpon):
    d, m, sql, *_ = galpon
    from datetime import datetime
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "administracion", "compras")
        cajas = cliente.get("/administracion/cajas").text.split("</style>")[-1]
        # Compras ya no tiene Cajas (04/10): su dirección vieja lleva acá
        cajas_compras = cliente.get("/compras/cajas", follow_redirects=False)
        tipos = cliente.get("/administracion/cajas/tipos").text
        nombre = f"EJEMPLO Caja Tipos {datetime.now():%H%M%S%f}"
        alta = cliente.post("/administracion/cajas/tipos/nuevo", follow_redirects=False,
                            data={"nombre": nombre, "costo": "1234"})
        ((envase_id,),) = sql("SELECT id FROM envases WHERE nombre = %s", (nombre,))
        costo = cliente.post(f"/administracion/cajas/tipos/{envase_id}/costo", follow_redirects=False,
                             data={"costo": "1500"})
        sin_clave = _cliente(m, "compras").post(f"/administracion/cajas/tipos/{envase_id}/costo",
                                                follow_redirects=False, data={"costo": "1"})
    # se llega desde adentro de Cajas de Administración, y desde Compras no
    assert cajas.count('href="/administracion/cajas/tipos"') == 1
    assert cajas_compras.status_code == 301 and cajas_compras.headers["location"] == "/administracion/cajas"
    # la pantalla saca todo del prefijo: barra, atrás y formularios
    assert '<a class="barra-boton" href="/administracion/cajas" aria-label="Volver atrás">' in tipos
    marcado = tipos.split("</style>")[-1]
    assert marcado.count('action="/administracion/cajas/tipos/nuevo"') == 1
    assert 'action="/envases' not in marcado
    assert alta.status_code == 303 and alta.headers["location"].startswith("/administracion/cajas/tipos?aviso=")
    assert costo.status_code == 303 and costo.headers["location"].startswith("/administracion/cajas/tipos?")
    assert sin_clave.status_code != 303
    # el costeo y la rentabilidad leen EL MISMO costo (costos_envases), el nuevo
    vigentes = {e["envase_id"]: float(e["costo"]) for e in d.listar_costos_envases_vigentes(date(2100, 1, 1))}
    assert vigentes[envase_id] == 1500.0


# --- El estilo de Depósito -----------------------------------------------------------

def test_los_TRES_COLORES_del_hub_son_los_de_DEPOSITO_y_cada_dibujo_existe():
    import io as _io
    deposito = _io.open("templates/deposito.html", encoding="utf-8").read()
    compartido = _io.open("templates/_botones_hub.html", encoding="utf-8").read()
    de_deposito = [re.search(r"\.boton\.%s\s*\{ background: (#[0-9a-f]{6}); \}" % c, deposito).group(1)
                   for c in ("ingresos", "pedidos", "stock")]
    del_hub = [re.search(r"\.boton\.color-%d \{ background: (#[0-9a-f]{6}); \}" % n, compartido).group(1)
               for n in (1, 2, 3)]
    assert del_hub == de_deposito == ["#2563eb", "#0d9488", "#334155"]
    from app.iconos_hubs import ICONOS_HUBS
    hub = _io.open("templates/administracion.html", encoding="utf-8").read()
    usadas = re.findall(r"ICONOS_HUBS\['([a-z_]+)'\]", hub)
    assert len(usadas) == sum(len(b) for b in GRUPOS_DECIDIDOS.values())
    assert set(usadas) <= set(ICONOS_HUBS)


def test_las_PESTANAS_entran_en_UNA_linea_a_313px_sin_partir_ninguna_palabra(galpon):
    """La primera versión partía "Movimie/ntos" a 313px. Lo mide el navegador."""
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        respuesta = _cliente(m, "administracion").get("/administracion/stock/remanente")
    assert respuesta.status_code == 200 and '<nav class="pestanas" aria-label="Stock del depósito">' in respuesta.text
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            pagina = navegador.new_page(viewport={"width": 313, "height": 700})
            pagina.set_content(respuesta.text)
            medidas = pagina.evaluate("""() => [...document.querySelectorAll('.pestanas a')].map(a => ({
              texto: a.textContent.trim(), alto: a.getBoundingClientRect().height,
              arriba: a.getBoundingClientRect().top, derecha: a.getBoundingClientRect().right,
              lineas: Math.round(a.getBoundingClientRect().height / parseFloat(getComputedStyle(a).lineHeight || 20)),
              desborda: a.scrollWidth > a.clientWidth}))""")
            ancho = pagina.evaluate("() => document.documentElement.clientWidth")
        finally:
            navegador.close()
    assert [x["texto"] for x in medidas] == ["Hoy", "Evolución", "Movimientos"]
    assert len({x["arriba"] for x in medidas}) == 1                 # las tres en la misma fila
    assert all(x["alto"] == 44 for x in medidas), medidas          # 44px: una sola línea de texto
    assert not any(x["desborda"] for x in medidas), medidas
    assert max(x["derecha"] for x in medidas) <= ancho


def test_en_CAJAS_la_barra_no_se_aplasta_a_313px(galpon):
    """El `button` de la pantalla agarraba el candado de la barra: el título
    quedaba en una columna de una letra. Lo mide el navegador."""
    pytest.importorskip("playwright", reason="lo que se ve lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    _d, m, *_ = galpon
    with patch.dict(os.environ, CLAVES):
        cliente = _cliente(m, "administracion")
        cajas = cliente.get("/administracion/cajas")
        # EL TESTIGO: la misma barra en una pantalla sin `button` propio
        testigo = cliente.get("/administracion/stock/ajustar")
    assert cajas.status_code == testigo.status_code == 200
    assert 'aria-label="Bloquear' in cajas.text and 'aria-label="Bloquear' in testigo.text

    def anchos(html):
        with sync_playwright() as pw:
            navegador = pw.chromium.launch(executable_path=CHROMIUM)
            try:
                pagina = navegador.new_page(viewport={"width": 313, "height": 700})
                pagina.set_content(html)
                return pagina.evaluate("""() => [...document.querySelectorAll('.barra-boton')]
                  .map(b => Math.round(b.getBoundingClientRect().width))""")
            finally:
                navegador.close()

    en_cajas, en_el_testigo = anchos(cajas.text), anchos(testigo.text)
    # la barra de Cajas mide lo mismo que la de cualquier otra pantalla
    assert len(en_cajas) >= 3 and en_cajas == en_el_testigo, (en_cajas, en_el_testigo)

