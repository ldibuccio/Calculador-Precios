"""CARTERA DE CHEQUES: APLICAR en UN SOLO FLUJO de dos pasos (dueño, 16/10).

Paso 1: archivos (capturas, fotos, PDF) y/o cheques tildados de la cartera.
Paso 2: un renglón por cheque, AGRUPADO POR ARCHIVO, y "Confirmar todos".

La IA lee cada archivo (acá se reemplaza por lo que habría devuelto: lo que se
prueba es qué hace el sistema con lo leído). Storage tampoco: la subida
devuelve una ruta inventada por foto.

EL GALPÓN, con nombres inventados:
  proveedor 1 EJEMPLO Puesto con CUIT PROV_A; 2 EJEMPLO Otro Puesto sin CUIT
  (el que se elige a mano); con `_cuatro_proveedores`, 3 y 4 con su CUIT.
  en cartera: 1001 ($10.000), 1002 ($20.000), 1003 ($30.000), 1005 ($50.000)

DEPÓSITOS: la captura REAL que mandó el dueño el 13/10 (cuenta
CC$ 191-220-000247/7, cheques 00932970 y 00020758) se escribe como lo que la
IA leería de ella; acá no hay imagen.
"""
import os
import re
import sys
from datetime import date, timedelta
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.salidas_de_cheques import (  # noqa: E402
    A_MANO,
    grupos_de_las_salidas,
    poner_a_los_tildados,
    problemas_de_las_salidas,
    renglones_de_lo_leido,
    renglones_elegidos_a_mano,
)
from tests.test_administracion_reordenada import _cliente  # noqa: E402
from tests.test_cheques import _cargar, _hoy, d  # noqa: E402,F401
from tests.test_cheques_pantallas import _foto, _sin_estilo, m  # noqa: E402,F401

PROV_A, PROV_B, PROV_C, PROV_D = "30712345671", "20333333334", "30700000016", "20444444445"
CUENTA = "CC$ 191-220-000247/7"


def _captura(cuit, nombre, *cheques, tipo="endoso"):
    return {"tipo": tipo, "cuenta_deposito": None, "proveedor_cuit": cuit, "proveedor_nombre": nombre,
            "cheques": [{"numero": n, "fecha_pago": "2026-11-15", "importe": i, "emisor": "EJEMPLO Emisor SA"}
                        for n, i in cheques]}


# La captura real del dueño. La IA también podría leer el CUIT de quien firma la
# operación: es el RIVAL, un depósito no va a ningún proveedor aunque venga uno.
DEPOSITO_REAL = {"tipo": "deposito", "cuenta_deposito": CUENTA, "proveedor_cuit": PROV_A,
                 "proveedor_nombre": "EJEMPLO PUESTO SRL",
                 "cheques": [{"numero": "00932970", "fecha_pago": "2026-09-22", "importe": 97240,
                              "emisor": "Día Argentina"},
                             {"numero": "00020758", "fecha_pago": "2026-10-05", "importe": 4519691.57,
                              "emisor": "Lartirigoyen & Oromi"}]}


def _galpon(d):
    conexion = d.obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute("UPDATE proveedores SET cuit = %s WHERE id = 1", (PROV_A,))
        cursor.execute("INSERT INTO proveedores (id, nombre, codigo_puesto) OVERRIDING SYSTEM VALUE "
                       "VALUES (2, 'EJEMPLO Otro Puesto', 'N01P02')")
    conexion.commit()
    conexion.close()
    return {n: _cargar(d, n, importe=i) for n, i in (("1001", 10000.0), ("1002", 20000.0), ("1003", 30000.0),
                                                     ("1005", 50000.0))}


def _cuatro_proveedores(d):
    """El 2 recibe su CUIT y se agregan el 3 y el 4: cuatro proveedores, cuatro CUIT."""
    conexion = d.obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute("UPDATE proveedores SET cuit = %s WHERE id = 2", (PROV_B,))
        cursor.execute("INSERT INTO proveedores (id, nombre, codigo_puesto, cuit) OVERRIDING SYSTEM VALUE "
                       "VALUES (3, 'EJEMPLO Tercer Puesto', 'N01P03', %s), (4, 'EJEMPLO Cuarto Puesto', 'N01P04', %s)",
                       (PROV_C, PROV_D))
    conexion.commit()
    conexion.close()


def _los_reales(d) -> dict:
    return {n: _cargar(d, n, importe=i, pago=date.fromisoformat(p))
            for n, i, p in (("00932970", 97240.0, "2026-09-22"), ("00020758", 4519691.57, "2026-10-05"))}


def _seguir(m, capturas=(), elegidos=(), *, nombres=None):
    """El paso 1: sube un archivo por captura y tilda los `elegidos`."""
    nombres = nombres or [f"captura{i + 1}.jpg" for i in range(len(capturas))]
    archivos = [("archivos", (nombre, _foto(), "image/jpeg")) for nombre in nombres]
    with patch("app.main.extraer_salida_de_cheques", side_effect=list(capturas)) as lector:
        pagina = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/seguir", files=archivos or None,
                                              data={"cheque_id": [str(e) for e in elegidos]})
    assert lector.call_count == len(capturas)
    return pagina


def _revisar(m, datos, accion, **cambios):
    return _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/revisar",
                                        data=dict(datos, accion=accion, **cambios), follow_redirects=False)


def _formulario(html: str) -> dict:
    """Lo que el navegador mandaría de la página del paso 2, sin tocar nada."""
    marcado = _sin_estilo(html).split('action="/gerencia/cheques/aplicar/revisar">')[1].split("</form>")[0]
    datos: dict = {"foto_leida": re.findall(r'<input type="hidden" name="foto_leida" value="([^"]*)"', marcado)}
    for nombre, valor in re.findall(r'<input type="(?:hidden|text|date)" name="([a-z_0-9-]+)"[^>]*?value="([^"]*)"',
                                   marcado):
        if nombre != "foto_leida":
            datos[nombre] = valor
    for nombre, cuerpo in re.findall(r'<select name="([a-z_0-9-]+)"[^>]*>(.*?)</select>', marcado, re.S):
        elegido = re.search(r'<option value="([^"]*)" selected', cuerpo)
        datos[nombre] = elegido.group(1) if elegido else ""
    for nombre in re.findall(r'<input type="checkbox" name="([a-z_0-9]+)" value="1" checked', marcado):
        datos[nombre] = "1"
    return datos


def _fila(datos, numero) -> int:
    return next(int(k.split("_")[1]) for k, v in datos.items() if k.startswith("numero_") and v == numero)


def _titulos(html: str) -> list[str]:
    return re.findall(r"data-titulo-del-grupo>([^<]*)</h2>", _sin_estilo(html))


def _problemas(html: str) -> list[str]:
    return re.findall(r"data-problemas>([^<]*)</p>", _sin_estilo(html))


def _resumen(html: str) -> str:
    return re.sub(r"<[^>]+>", "", re.search(r"data-resumen>(.*?)</p>", _sin_estilo(html)).group(1))


def _salidas(d) -> dict:
    return {c["numero"]: (c["estado"], c["proveedor_id"], c["foto_salida"])
            for c in d.buscar_cheques({}) if c["estado"] not in ("en_cartera", "vencido")}


# --- PASO 1 ----------------------------------------------------------------------

def test_el_PASO_1_tiene_los_archivos_ARRIBA_y_la_cartera_ABAJO_en_UN_solo_formulario(m, d):
    ids = _galpon(d)
    pagina = _sin_estilo(_cliente(m, "gerencia").get(f"/gerencia/cheques/aplicar?cheque_id={ids['1002']}").text)
    formularios = re.findall(r'<form method="post" action="([^"]+)" enctype="multipart/form-data">', pagina)
    assert formularios == ["/gerencia/cheques/aplicar/seguir"] and pagina.count("<form") == 1
    assert '<input type="file" name="archivos" accept="image/*,.pdf" multiple>' in pagina
    assert pagina.index("data-archivos") < pagina.index("data-cartera")
    assert re.findall(r'name="cheque_id" value="(\d+)" data-importe="[^"]*" checked', pagina) == [str(ids["1002"])]
    assert len(re.findall(r'<input type="checkbox" name="cheque_id"', pagina)) == 4
    # "Cargar" arriba de todo (dueño, 17/10), con lo elegido al entrar desde la ficha; "Seguir" ya no está.
    (boton,) = re.findall(r'<button type="submit" data-boton-cargar>(.*?)</button>', pagina)
    assert re.sub(r"<[^>]+>", "", boton) == "Cargar · 1 cheque · $20.000"
    assert pagina.index("data-cargar") < pagina.index("data-archivos") < pagina.index("data-cartera")
    assert pagina.count('<button type="submit"') == 1 and ">Seguir</button>" not in pagina
    # Nada de los caminos viejos.
    for viejo in ("/aplicar/leer", "/aplicar/endosos", "Operación pendiente de firma"):
        assert viejo not in pagina
    sin_nada = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/seguir", data={})
    assert sin_nada.status_code == 400
    assert "Subí un archivo o tildá al menos un cheque de la cartera." in sin_nada.text


def test_CARGAR_queda_FIJO_arriba_al_bajar_y_cuenta_los_tildados_a_390_y_313(m, d):
    """Lo mide el navegador (dueño, 17/10): con la cartera larga, al bajar
    hasta el último cheque el botón sigue a la vista, debajo de la barra, y
    dice cuántos hay tildados y el total. Sin tildar nada también se aprieta
    (puede haber subido solo archivos)."""
    pytest.importorskip("playwright", reason="lo fijo lo decide el navegador")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    ids = _galpon(d)
    for n in range(40):                                                   # una cartera larga
        _cargar(d, f"2{n:03d}", importe=1000.0)
    html = _cliente(m, "gerencia").get(f"/gerencia/cheques/aplicar?cheque_id={ids['1002']}").text
    medidas = {}
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            for ancho in (390, 313):
                pagina = navegador.new_page(viewport={"width": ancho, "height": 700})
                pagina.set_content(html)
                pagina.check(f'input[name="cheque_id"][value="{ids["1003"]}"]')
                pagina.locator('input[name="cheque_id"]').last.scroll_into_view_if_needed()
                medidas[ancho] = pagina.evaluate("""() => {
                  const boton = document.querySelector('[data-boton-cargar]').getBoundingClientRect();
                  const barra = document.querySelector('.barra-navegacion').getBoundingClientRect();
                  return {texto: document.querySelector('[data-boton-cargar]').textContent.trim(),
                          arriba: boton.top, debajo_de_la_barra: boton.top >= barra.bottom - 1,
                          bajo: window.scrollY, deshabilitado: document.querySelector('[data-boton-cargar]').disabled,
                          desborde: document.documentElement.scrollWidth - document.documentElement.clientWidth};
                }""")
                pagina.uncheck(f'input[name="cheque_id"][value="{ids["1002"]}"]')
                pagina.uncheck(f'input[name="cheque_id"][value="{ids["1003"]}"]')
                medidas[ancho]["sin_tildar"] = pagina.text_content("[data-boton-cargar]").strip()
                medidas[ancho]["sin_tildar_deshabilitado"] = pagina.is_disabled("[data-boton-cargar]")
                pagina.close()
        finally:
            navegador.close()
    for ancho, medida in medidas.items():
        assert medida["bajo"] > 1000, (ancho, medida)                            # se bajó por la lista
        assert medida["debajo_de_la_barra"] and medida["arriba"] < 140, (ancho, medida)   # y sigue arriba
        assert medida["texto"] == "Cargar · 2 cheques · $50.000", (ancho, medida)
        assert medida["sin_tildar"] == "Cargar" and medida["deshabilitado"] is False
        assert medida["sin_tildar_deshabilitado"] is False                       # solo archivos: igual se aprieta
        assert medida["desborde"] == 0, (ancho, medida)


def test_los_caminos_VIEJOS_ya_no_estan(m):
    cliente = _cliente(m, "gerencia")
    for ruta in ("/gerencia/cheques/aplicar/leer", "/gerencia/cheques/aplicar/endosos",
                 "/gerencia/cheques/aplicar/endosos/confirmar"):
        assert cliente.post(ruta, data={}).status_code in (404, 405), ruta
    assert cliente.post("/gerencia/cheques/aplicar", data={}).status_code == 405


# --- SOLO ARCHIVOS: CUATRO FOTOS DE CUATRO PROVEEDORES --------------------------------

def test_CUATRO_FOTOS_de_cuatro_proveedores_son_CUATRO_GRUPOS_y_cada_cheque_sale_con_el_SUYO(m, d):
    ids = _galpon(d)
    _cuatro_proveedores(d)
    ids["1006"] = _cargar(d, "1006", importe=60000.0)
    pagina = _seguir(m, [_captura(PROV_A, "EJEMPLO PUESTO SRL", ("1001", 10000)),
                         _captura(PROV_B, "EJEMPLO OTRO PUESTO", ("1002", 20000), ("1003", 30000)),
                         _captura(PROV_C, "EJEMPLO TERCERO", ("1005", 50000)),
                         _captura(PROV_D, "EJEMPLO CUARTO", ("1006", 60000))])
    assert pagina.status_code == 200, pagina.text[:300]
    assert _titulos(pagina.text) == [
        "Foto 1 · EJEMPLO Puesto · 1 cheque · $10.000",
        "Foto 2 · EJEMPLO Otro Puesto · 2 cheques · $50.000",
        "Foto 3 · EJEMPLO Tercer Puesto · 1 cheque · $50.000",
        "Foto 4 · EJEMPLO Cuarto Puesto · 1 cheque · $60.000"]
    assert _resumen(pagina.text) == "5 cheques · $170.000 · 5 bien · 0 con problema"
    assert _problemas(pagina.text) == []
    # Ninguno está abierto: no tienen problema.
    assert "<details open>" not in _sin_estilo(pagina.text)
    rutas = iter(f"cheques/foto-{n}.jpg" for n in range(10))
    with patch("app.main.subir_foto_comanda", side_effect=lambda *a, **k: next(rutas)) as subir:
        final = _revisar(m, _formulario(pagina.text), "confirmar")
    assert final.status_code == 303 and "5+cheques+aplicados" in final.headers["location"]
    assert subir.call_count == 4                                                   # una por foto
    assert _salidas(d) == {"1001": ("entregado", 1, "cheques/foto-0.jpg"),
                           "1002": ("entregado", 2, "cheques/foto-1.jpg"),
                           "1003": ("entregado", 2, "cheques/foto-1.jpg"),
                           "1005": ("entregado", 3, "cheques/foto-2.jpg"),
                           "1006": ("entregado", 4, "cheques/foto-3.jpg")}


def test_un_PDF_se_lee_con_TODAS_sus_paginas_y_un_archivo_que_no_se_lee_no_frena_los_demas(m, d):
    _galpon(d)
    paginas = [_foto(), _foto()]
    archivos = [("archivos", ("recibo.pdf", b"%PDF-1.4 inventado", "application/pdf")),
                ("archivos", ("borrosa.jpg", _foto(), "image/jpeg")),
                ("archivos", ("planilla.xlsx", b"PK", "application/octet-stream"))]
    with patch("app.main.imagenes_desde_pdf", return_value=paginas) as pdf, \
         patch("app.main.extraer_salida_de_cheques",
               side_effect=[_captura(PROV_A, "X", ("1001", 10000)), RuntimeError("la API no contestó")]) as lector:
        pagina = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/seguir", files=archivos)
    assert pdf.call_count == 1 and lector.call_args_list[0].args[0] == paginas
    assert lector.call_count == 2                                 # el Excel no llega a la IA
    assert re.findall(r'<div class="aviso" data-aviso>([^<]*)</div>', _sin_estilo(pagina.text)) == [
        "La foto 2 no se pudo leer: «borrosa.jpg» no se entiende como un comprobante de cheques",
        "La foto 3 no se pudo leer: «planilla.xlsx» no se entiende como un comprobante de cheques"]
    assert _titulos(pagina.text) == ["Foto 1 · EJEMPLO Puesto · 1 cheque · $10.000"]
    # Lo que no es un error de lectura no se esconde.
    with patch("app.main.extraer_salida_de_cheques", side_effect=KeyError("otra cosa")), pytest.raises(KeyError):
        _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/seguir",
                                     files=[("archivos", ("a.jpg", _foto(), "image/jpeg"))])


# --- SOLO A MANO Y MEZCLADO --------------------------------------------------------

def test_SOLO_A_MANO_van_en_Elegidos_a_mano_y_el_encabezado_les_pone_el_motivo_y_el_proveedor(m, d):
    ids = _galpon(d)
    pagina = _seguir(m, elegidos=[ids["1001"], ids["1003"]])
    assert _titulos(pagina.text) == ["Elegidos a mano · a elegir · 2 cheques · $40.000"]
    assert _problemas(pagina.text) == ["elegí el motivo"] * 2
    # Falta solo a dónde va: el número, el monto y el cheque de la cartera no se abren.
    assert '<input type="text" name="numero_0"' not in _sin_estilo(pagina.text)
    assert '<input type="hidden" name="numero_0"' in _sin_estilo(pagina.text)
    assert _resumen(pagina.text) == "2 cheques · $40.000 · 0 bien · 2 con problema"
    datos = _formulario(pagina.text)
    cambiada = _revisar(m, datos, f"grupo_{A_MANO}", **{f"grupo_{A_MANO}_concepto_id": "1",
                                                        f"grupo_{A_MANO}_proveedor_id": "2"})
    assert _titulos(cambiada.text) == ["Elegidos a mano · EJEMPLO Otro Puesto · 2 cheques · $40.000"]
    assert _problemas(cambiada.text) == []
    with patch("app.main.subir_foto_comanda") as subir:
        final = _revisar(m, _formulario(cambiada.text), "confirmar")
    assert final.status_code == 303 and subir.call_count == 0                      # a mano no hay foto
    assert _salidas(d) == {"1001": ("entregado", 2, None), "1003": ("entregado", 2, None)}


def test_MEZCLADO_un_archivo_y_tildados_y_el_tildado_que_ya_vino_en_el_archivo_va_UNA_vez(m, d):
    ids = _galpon(d)
    pagina = _seguir(m, [_captura(PROV_A, "X", ("1001", 10000), ("1002", 20000))], elegidos=[ids["1002"], ids["1003"]])
    assert re.findall(r'<div class="aviso" data-aviso>([^<]*)</div>', _sin_estilo(pagina.text)) == [
        "El cheque 1002 ya está en la foto 1: se toma una sola vez."]
    assert _titulos(pagina.text) == ["Elegidos a mano · a elegir · 1 cheque · $30.000",
                                     "Foto 1 · EJEMPLO Puesto · 2 cheques · $30.000"]
    with patch("app.main.subir_foto_comanda", return_value="cheques/foto.jpg"):
        confirmada = _revisar(m, _formulario(pagina.text), "confirmar")
    assert confirmada.status_code == 200
    assert "Se aplicaron 2. Quedan 1 con problemas" in confirmada.text
    assert _titulos(confirmada.text) == ["Elegidos a mano · a elegir · 1 cheque · $30.000"]
    assert _salidas(d) == {"1001": ("entregado", 1, "cheques/foto.jpg"), "1002": ("entregado", 1, "cheques/foto.jpg")}


# --- EL ENCABEZADO DEL GRUPO Y "PARA TODOS" -------------------------------------------

def test_cambiar_el_PROVEEDOR_de_un_GRUPO_desde_su_encabezado_no_toca_los_otros(m, d):
    _galpon(d)
    pagina = _seguir(m, [_captura(PROV_A, "X", ("1001", 10000)), _captura(PROV_A, "X", ("1002", 20000), ("1003", 30000))])
    datos = _formulario(pagina.text)
    cambiada = _revisar(m, datos, "grupo_1", grupo_1_proveedor_id="2")
    assert _titulos(cambiada.text) == ["Foto 1 · EJEMPLO Puesto · 1 cheque · $10.000",
                                       "Foto 2 · EJEMPLO Otro Puesto · 2 cheques · $50.000"]
    nuevos = _formulario(cambiada.text)
    assert {nuevos[f"numero_{i}"]: nuevos[f"proveedor_id_{i}"] for i in range(3)} == {
        "1001": "1", "1002": "2", "1003": "2"}
    # El encabezado sin nada elegido no cambia nada y lo dice.
    vacio = _revisar(m, dict(nuevos, grupo_0_concepto_id="", grupo_0_proveedor_id=""), "grupo_0")
    assert "Elegí qué cambiar en el grupo." in vacio.text


def test_PARA_TODOS_va_a_los_TILDADOS_y_sin_tildados_PREGUNTA_antes(m, d):
    _galpon(d)
    otro_dia = (_hoy(d) - timedelta(days=2)).isoformat()
    pagina = _seguir(m, [_captura(PROV_A, "X", ("1001", 10000)), _captura(PROV_A, "X", ("1002", 20000), ("1003", 30000))])
    datos = _formulario(pagina.text)
    # Sin tildados: pregunta y no cambia nada.
    pregunta = _revisar(m, datos, "a_todos", todos_fecha=otro_dia)
    assert "data-pregunta-a-todos" in _sin_estilo(pregunta.text)
    assert "¿Lo pongo en TODOS (3, de todos los grupos)?" in pregunta.text
    sin_cambio = _formulario(pregunta.text)
    assert {sin_cambio[f"fecha_{i}"] for i in range(3)} == {_hoy(d).isoformat()}
    assert sin_cambio["todos_fecha"] == otro_dia                     # lo elegido sigue ahí para el "Sí"
    a_todos = _revisar(m, sin_cambio, "a_todos_si")
    assert "Se cambió en 3 cheques." in a_todos.text
    assert {_formulario(a_todos.text)[f"fecha_{i}"] for i in range(3)} == {otro_dia}
    # Con UNO tildado: solo a ese, sin preguntar.
    tildado = _revisar(m, dict(datos, **{f"tildado_{_fila(datos, '1002')}": "1"}), "a_todos", todos_proveedor_id="2")
    assert "data-pregunta-a-todos" not in _sin_estilo(tildado.text) and "Se cambió en 1 cheque." in tildado.text
    nuevos = _formulario(tildado.text)
    assert {nuevos[f"numero_{i}"]: nuevos[f"proveedor_id_{i}"] for i in range(3)} == {
        "1001": "1", "1002": "2", "1003": "1"}
    assert "Elegí qué poner en" in _revisar(m, datos, "a_todos").text


def test_SELECCIONAR_TODOS_y_SACAR_LOS_TILDADOS(m, d):
    _galpon(d)
    datos = _formulario(_seguir(m, [_captura(PROV_A, "X", ("1001", 10000), ("1002", 20000))]).text)
    todos = _formulario(_revisar(m, datos, "seleccionar_todos").text)
    assert todos["tildado_0"] == todos["tildado_1"] == "1"
    sacados = _revisar(m, dict(datos, tildado_1="1"), "sacar_tildados")
    assert _resumen(sacados.text) == "1 cheque · $10.000 · 1 bien · 0 con problema"
    with patch("app.main.subir_foto_comanda", return_value="cheques/foto.jpg"):
        final = _revisar(m, _formulario(sacados.text), "confirmar")
    assert final.status_code == 303 and "1+cheques+aplicados" in final.headers["location"]
    assert set(_salidas(d)) == {"1001"}


def test_OTRO_MOTIVO_se_agrega_y_queda_para_elegir(m, d):
    _galpon(d)
    datos = _formulario(_seguir(m, [_captura(PROV_A, "X", ("1001", 10000))]).text)
    agregado = _revisar(m, datos, "agregar_motivo", motivo_nuevo="EJEMPLO Pago de flete", destino_nuevo="entregado")
    assert "Se agregó el motivo «EJEMPLO Pago de flete»." in agregado.text
    assert [c["nombre"] for c in d.listar_conceptos_de_cheques()][-1] == "EJEMPLO Pago de flete"
    repetido = _revisar(m, datos, "agregar_motivo", motivo_nuevo="pago a proveedor", destino_nuevo="entregado")
    assert repetido.status_code == 400 and "ya está en la lista" in repetido.text


# --- LOS PROBLEMAS ------------------------------------------------------------------------

def test_REPETIDO_entre_dos_archivos_NO_EN_CARTERA_y_MONTO_DISTINTO_van_en_rojo_PRIMERO_y_ABIERTOS(m, d):
    ids = _galpon(d)
    pagina = _seguir(m, [_captura(PROV_A, "X", ("1003", 30000)),
                         _captura(PROV_A, "X", ("1001", 10000), ("1004", 40000)),
                         _captura(PROV_A, "X", ("0001001", 10000), ("1002", 20500))])
    marcado = _sin_estilo(pagina.text)
    assert re.findall(r'<div class="aviso" data-aviso>([^<]*)</div>', marcado) == [
        "El cheque 0001001 está en las fotos 2 y 3: se toma una sola vez."]
    # Los grupos con problema primero; en cada grupo, el renglón con problema primero y abierto.
    assert _titulos(pagina.text) == ["Foto 2 · EJEMPLO Puesto · 2 cheques · $50.000",
                                     "Foto 3 · EJEMPLO Puesto · 1 cheque · $20.500",
                                     "Foto 1 · EJEMPLO Puesto · 1 cheque · $30.000"]
    assert _problemas(pagina.text) == ["no está en la cartera", "el monto no coincide: en la cartera es $20.000"]
    datos = _formulario(pagina.text)
    orden = [datos[f"numero_{i}"] for i in map(int, re.findall(r'data-renglon="(\d+)"', marcado))]
    assert orden == ["1004", "1001", "1002", "1003"]
    abiertos = re.findall(r'data-renglon="(\d+)">\s*<label class="tilde"[^>]*>.*?</label>\s*<details( open)?>',
                          marcado, re.S)
    assert [(datos[f"numero_{int(i)}"], bool(o)) for i, o in abiertos] == [
        ("1004", True), ("1001", False), ("1002", True), ("1003", False)]
    assert _resumen(pagina.text) == "4 cheques · $100.500 · 2 bien · 2 con problema"
    # Un problema del cheque abre el número, el monto y el cheque de la cartera para corregir.
    assert len(re.findall(r'<input type="text" name="importe_\d+"', marcado)) == 2
    with patch("app.main.subir_foto_comanda", return_value="cheques/foto.jpg"):
        confirmada = _revisar(m, datos, "confirmar")
    assert "Se aplicaron 2. Quedan 2 con problemas" in confirmada.text
    assert set(_salidas(d)) == {"1001", "1003"}
    # Elegido A MANO el cheque de la cartera, con otro monto tampoco entra.
    quedan = _formulario(confirmada.text)
    fila = _fila(quedan, "1002")
    elegido = _revisar(m, dict(quedan, **{f"cheque_id_{fila}": str(ids["1002"])}), "revisar")
    assert _formulario(elegido.text)[f"cheque_id_{fila}"] == str(ids["1002"])
    assert _problemas(elegido.text) == ["no está en la cartera", "el monto no coincide: en la cartera es $20.000"]
    # Corregido el monto, el que se había leído mal entra.
    with patch("app.main.subir_foto_comanda", return_value="cheques/foto.jpg"):
        corregido = _revisar(m, dict(quedan, **{f"importe_{fila}": "20.000,00",
                                                f"sacar_{_fila(quedan, '1004')}": "1"}), "confirmar")
    assert corregido.status_code == 303 and set(_salidas(d)) == {"1001", "1002", "1003"}


def test_una_BOLETA_que_no_dice_a_donde_va_deja_el_DESTINO_vacio(m, d):
    _galpon(d)
    boleta = {"tipo": None, "cuenta_deposito": None, "proveedor_cuit": None, "proveedor_nombre": None,
              "cheques": [{"numero": "1001", "importe": 10000}]}
    pagina = _seguir(m, [boleta])
    assert _titulos(pagina.text) == ["Foto 1 · a elegir · 1 cheque · $10.000"]
    assert _problemas(pagina.text) == ["elegí el motivo"]


def test_la_CAPTURA_REAL_de_deposito_deja_los_dos_DEPOSITADOS_sin_proveedor(m, d):
    _galpon(d)
    reales = _los_reales(d)
    pagina = _seguir(m, [DEPOSITO_REAL])
    assert _problemas(pagina.text) == []
    assert re.findall(r'data-leido="([a-z]+)"', _sin_estilo(pagina.text)) == ["deposito", "deposito"]
    with patch("app.main.subir_foto_comanda", return_value="cheques/deposito.jpg"):
        final = _revisar(m, _formulario(pagina.text), "confirmar")
    assert final.status_code == 303 and "2+cheques+aplicados" in final.headers["location"]
    assert {c["numero"]: (c["estado"], c["concepto"], c["proveedor_id"], c["cuenta_deposito"])
            for c in d.buscar_cheques({}) if c["id"] in reales.values()} == {
        "00932970": ("depositado", "Depósito en cuenta", None, CUENTA),
        "00020758": ("depositado", "Depósito en cuenta", None, CUENTA)}
    # El CUIT que venía en la captura de depósito no se le pegó a nadie.
    assert {p["id"]: p["cuit"] for p in d.proveedores_con_cuit()} == {1: PROV_A, 2: None}


def test_el_PROVEEDOR_elegido_a_mano_se_queda_con_el_CUIT_leido(m, d):
    _galpon(d)
    datos = _formulario(_seguir(m, [_captura(PROV_B, "EJEMPLO OTRO PUESTO", ("1005", 50000))]).text)
    assert datos["proveedor_id_0"] == "" and _problemas(_revisar(m, datos, "revisar").text) == ["elegí el proveedor"]
    with patch("app.main.subir_foto_comanda", return_value="cheques/foto.jpg"):
        assert _revisar(m, dict(datos, proveedor_id_0="2"), "confirmar").status_code == 303
    assert {p["id"]: p["cuit"] for p in d.proveedores_con_cuit()} == {1: PROV_A, 2: PROV_B}
    # La próxima vez se encuentra solo; y el que ya salió lo dice.
    otra = _seguir(m, [_captura(PROV_B, "X", ("1001", 10000)), _captura(PROV_B, "X", ("1005", 50000))])
    assert _formulario(otra.text)["proveedor_id_0"] == "2"
    assert _problemas(otra.text) == ["ya salió: está entregado"]


# --- SIN BASE ----------------------------------------------------------------------------

DESTINOS = {1: "entregado", 2: "canjeado", 3: "depositado"}
CARTERA = [{"id": 1, "numero": "0042", "importe": 1000, "estado": "en_cartera"},     # con ceros adelante
           {"id": 2, "numero": "42", "importe": 2000, "estado": "en_cartera"},     # mismo número, otro monto
           {"id": 3, "numero": "77", "importe": 500, "estado": "depositado"}]
HOY = date(2026, 10, 16)


def _leidos(leidas, proveedores=(), bancos=()):
    return renglones_de_lo_leido(leidas, cheques=CARTERA, proveedores=list(proveedores), bancos=list(bancos),
                                 concepto_pago=1, concepto_deposito=3, hoy=HOY)


def test_la_COINCIDENCIA_es_por_numero_y_monto_y_dos_iguales_no_se_adivinan():
    proveedores = [{"id": 1, "cuit": PROV_A}, {"id": 2, "cuit": PROV_B}, {"id": 3, "cuit": PROV_B}]
    renglones, avisos = _leidos(
        [{"proveedor_cuit": PROV_A, "cheques": [{"numero": "42", "importe": 2000}, {"numero": "77", "importe": 500}]},
         {"proveedor_cuit": PROV_A, "cheques": [{"numero": "00042", "importe": "1.000,00"}]},
         {"proveedor_cuit": PROV_B, "cheques": [{"numero": "9", "importe": 1}]}, {"error": "borrosa"}], proveedores)
    assert avisos == ["La foto 4 no se pudo leer: borrosa"]
    assert [(r["numero"], r["cheque_id"], r["proveedor_id"], r["foto"]) for r in renglones] == [
        ("42", 2, 1, 0), ("77", None, 1, 0), ("00042", 1, 1, 1), ("9", None, None, 2)]
    assert problemas_de_las_salidas(renglones, CARTERA, destinos=DESTINOS, bancos=[]) == [
        [], ["ya salió: está depositado"], [], ["no está en la cartera", "elegí el proveedor"]]
    dos = [dict(renglones[0]), dict(renglones[0], numero="0042", importe="2000")]
    assert problemas_de_las_salidas(dos, CARTERA, destinos=DESTINOS, bancos=[]) == [
        ["ese cheque está en otro renglón"]] * 2


def test_el_DEPOSITO_pide_la_cuenta_si_hay_bancos_y_la_reconoce_por_el_numero():
    bancos = [{"id": 7, "tipo": "banco", "numero": "CC$ 191-220-000247/7"}, {"id": 8, "tipo": "banco", "numero": None}]
    renglones, _ = _leidos([{"cuenta_deposito": " 191 220 000247 7 ", "proveedor_cuit": PROV_A,
                             "cheques": [{"numero": "42", "importe": 2000}]},
                            {"tipo": "deposito", "cheques": [{"numero": "0042", "importe": 1000}]}],
                           [{"id": 1, "cuit": PROV_A}], bancos)
    assert [(r["deposito"], r["concepto_id"], r["proveedor_id"], r["cuenta_id"]) for r in renglones] == [
        (True, 3, None, 7), (True, 3, None, None)]
    assert problemas_de_las_salidas(renglones, CARTERA, destinos=DESTINOS, bancos=bancos) == [[], ["elegí la cuenta"]]
    # Sin bancos (Palmala hoy), el depósito sale sin cuenta.
    assert problemas_de_las_salidas(renglones, CARTERA, destinos=DESTINOS, bancos=[]) == [[], []]


def test_A_MANO_no_repite_lo_que_ya_vino_en_un_archivo_y_PARA_TODOS_sin_tildados_devuelve_None():
    ya, _ = _leidos([{"cheques": [{"numero": "42", "importe": 2000}]}])
    a_mano, avisos = renglones_elegidos_a_mano([2, 1, 99], cheques=CARTERA, ya=ya, hoy=HOY)
    assert avisos == ["El cheque 42 ya está en la foto 1: se toma una sola vez."]
    assert [(r["foto"], r["cheque_id"], r["importe"], r["concepto_id"]) for r in a_mano] == [(A_MANO, 1, "1000.00", None)]
    renglones = ya + a_mano
    assert poner_a_los_tildados(renglones, {"concepto_id": 2}, sin_tildar_tambien=False) is None
    assert [r["concepto_id"] for r in renglones] == [None, None]
    assert poner_a_los_tildados(renglones, {"concepto_id": 2}, sin_tildar_tambien=True) == 2
    renglones[0]["tildado"] = True
    assert poner_a_los_tildados(renglones, {"concepto_id": 3}, sin_tildar_tambien=False) == 1
    assert [r["concepto_id"] for r in renglones] == [3, 2]


def test_los_GRUPOS_con_problema_primero_y_a_mano_al_final():
    renglones, _ = _leidos([{"proveedor_cuit": PROV_A, "cheques": [{"numero": "0042", "importe": 1000}]},
                            {"proveedor_cuit": PROV_A, "cheques": [{"numero": "5", "importe": 1}]}],
                           [{"id": 1, "cuit": PROV_A}])
    a_mano, _ = renglones_elegidos_a_mano([2], cheques=CARTERA, ya=renglones, hoy=HOY)
    renglones += [dict(a_mano[0], concepto_id=1, proveedor_id=1)]
    problemas = problemas_de_las_salidas(renglones, CARTERA, destinos=DESTINOS, bancos=[])
    salida = grupos_de_las_salidas(renglones, problemas, nombre_de_proveedor={1: "EJEMPLO Puesto"},
                                   nombre_de_cuenta={}, nombre_de_concepto={1: "Pago a proveedor"})
    assert [(g["titulo"], g["destino"], g["cuantos"], g["con_problema"], g["total"]) for g in salida] == [
        ("Foto 2", "EJEMPLO Puesto", 1, 1, 1.0), ("Foto 1", "EJEMPLO Puesto", 1, 0, 1000.0),
        ("Elegidos a mano", "EJEMPLO Puesto", 1, 0, 2000.0)]
