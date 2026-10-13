"""CARTERA DE CHEQUES: aplicar con varias capturas de ENDOSOS de ECHEQ (dueño, 13/10).

La IA lee cada captura (acá se reemplaza por lo que habría devuelto: lo que se
prueba es qué hace el sistema con lo leído). Storage tampoco: la subida
devuelve una ruta inventada por foto.

EL GALPÓN, con nombres inventados:
  proveedor 1 EJEMPLO Puesto, con CUIT PROV_A cargado
  proveedor 2 EJEMPLO Otro Puesto, sin CUIT (el que se elige a mano)
  en cartera: 1001 ($10.000), 1002 ($20.000), 1003 ($30.000), 1005 ($50.000)

LAS 4 CAPTURAS, 5 cheques:
  foto 1: a PROV_A, 1001 y 1002
  foto 2: a PROV_A, 1003
  foto 3: a PROV_A, 1004            -> no está en la cartera
  foto 4: a PROV_B, 0001002 y 1005  -> 1002 repetido de la foto 1; PROV_B no es de nadie

DEPÓSITOS (13/10): la captura REAL que mandó el dueño (cuenta CC$ 191-220-000247/7,
cheques 00932970 y 00020758) se escribe como lo que la IA leería de ella; acá
no hay imagen.
"""
import os
import re
import sys
from datetime import date
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.endosos_cheques import problemas_de_los_endosos, renglones_de_los_endosos  # noqa: E402
from tests.test_administracion_reordenada import _cliente  # noqa: E402
from tests.test_cheques import _cargar, _hoy, d  # noqa: E402,F401
from tests.test_cheques_pantallas import _foto, _sin_estilo, m  # noqa: E402,F401

PROV_A, PROV_B = "30712345671", "20333333334"


def _captura(cuit, nombre, *cheques):
    return {"proveedor_cuit": cuit, "proveedor_nombre": nombre,
            "cheques": [{"numero": n, "fecha_pago": "2026-11-15", "importe": i, "emisor": "EJEMPLO Emisor SA"}
                        for n, i in cheques]}


CAPTURAS = [
    _captura("30-71234567-1", "EJEMPLO PUESTO SRL", ("1001", 10000), ("1002", 20000)),
    _captura(PROV_A, "EJEMPLO PUESTO SRL", ("1003", 30000.0)),
    _captura(PROV_A, "EJEMPLO PUESTO SRL", ("1004", 40000)),
    _captura(PROV_B, "EJEMPLO OTRO PUESTO", ("0001002", 20000), ("1005", 50000)),
]


CUENTA = "CC$ 191-220-000247/7"
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


def _leer(m, capturas):
    archivos = [("fotos", (f"captura{i + 1}.jpg", _foto(), "image/jpeg")) for i in range(len(capturas))]
    with patch("app.main.extraer_endoso", side_effect=capturas) as lector:
        pagina = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos", files=archivos)
    assert lector.call_count == len(capturas)
    return pagina


def _los_reales(d) -> dict:
    return {n: _cargar(d, n, importe=i, pago=date.fromisoformat(p))
            for n, i, p in (("00932970", 97240.0, "2026-09-22"), ("00020758", 4519691.57, "2026-10-05"))}


def _formulario(html: str) -> dict:
    marcado = _sin_estilo(html).split('action="/gerencia/cheques/aplicar/endosos/confirmar">')[1].split("</form>")[0]
    datos: dict = {"foto_leida": re.findall(r'<input type="hidden" name="foto_leida" value="([^"]*)"', marcado)}
    for nombre, valor in re.findall(r'<input type="(?:hidden|text|date|number)" name="([a-z_0-9]+)"[^>]*?value="([^"]*)"',
                                   marcado):
        if nombre != "foto_leida":
            datos[nombre] = valor
    for nombre, cuerpo in re.findall(r'<select name="([a-z_0-9]+)">(.*?)</select>', marcado, re.S):
        elegido = re.search(r'<option value="([^"]*)" selected', cuerpo)
        datos[nombre] = elegido.group(1) if elegido else ""
    return datos


def _fila(datos, numero) -> int:
    return next(int(k.split("_")[1]) for k, v in datos.items() if k.startswith("numero_") and v == numero)


def test_CUATRO_CAPTURAS_cinco_cheques_uno_fuera_de_cartera_y_uno_repetido(m, d):
    ids = _galpon(d)
    pagina = _leer(m, CAPTURAS)
    assert pagina.status_code == 200, pagina.text[:300]
    marcado = _sin_estilo(pagina.text)
    assert len(re.findall(r'data-renglon="\d+"', marcado)) == 5
    assert re.findall(r'<div class="aviso" data-aviso>([^<]*)</div>', marcado) == [
        "El cheque 0001002 está en las fotos 1 y 4: se toma una sola vez."]
    datos = _formulario(pagina.text)
    # El cheque de la cartera por número y monto; el proveedor por CUIT.
    assert {datos[f"numero_{i}"]: (datos[f"cheque_id_{i}"], datos[f"proveedor_id_{i}"], datos[f"foto_{i}"])
            for i in range(5)} == {
        "1001": (str(ids["1001"]), "1", "0"), "1002": (str(ids["1002"]), "1", "0"),
        "1003": (str(ids["1003"]), "1", "1"), "1004": ("", "1", "2"), "1005": (str(ids["1005"]), "", "3")}
    assert re.findall(r'data-problemas>([^<]*)</p>', marcado) == ["no está en la cartera", "elegí el proveedor"]
    assert all(datos[f"concepto_id_{i}"] == "1" and datos[f"fecha_{i}"] == _hoy(d).isoformat() for i in range(5))

    # Se elige el proveedor del 1005 y se confirma: entran 4, queda el 1004.
    datos[f"proveedor_id_{_fila(datos, '1005')}"] = "2"
    rutas = iter(f"cheques/endoso-{n}.jpg" for n in range(10))
    with patch("app.main.subir_foto_comanda", side_effect=lambda *a, **k: next(rutas)) as subir:
        confirmada = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos/confirmar",
                                                  data=dict(datos, accion="confirmar"))
    assert confirmada.status_code == 200
    assert subir.call_count == 3                                              # una por foto que se usó
    assert "Se aplicaron 4. Quedan 1 con problemas" in confirmada.text
    assert re.findall(r'data-problemas>([^<]*)</p>', _sin_estilo(confirmada.text)) == ["no está en la cartera"]
    salidas = {c["numero"]: (c["estado"], c["proveedor_id"], c["foto_salida"]) for c in d.buscar_cheques({})}
    assert salidas == {"1001": ("entregado", 1, "cheques/endoso-0.jpg"),
                       "1002": ("entregado", 1, "cheques/endoso-0.jpg"),
                       "1003": ("entregado", 1, "cheques/endoso-1.jpg"),
                       "1005": ("entregado", 2, "cheques/endoso-2.jpg")}
    # El proveedor elegido a mano se quedó con el CUIT leído: la próxima vez se encuentra solo.
    assert {p["id"]: p["cuit"] for p in d.proveedores_con_cuit()} == {1: PROV_A, 2: PROV_B}
    otra = _formulario(_leer(m, [_captura(PROV_B, "EJEMPLO OTRO PUESTO", ("1001", 10000))]).text)
    assert otra["proveedor_id_0"] == "2"
    assert "ya salió: está entregado" in _leer(m, [_captura(PROV_B, "X", ("1001", 10000))]).text


def test_el_MONTO_que_no_coincide_va_en_rojo_y_no_se_guarda(m, d):
    ids = _galpon(d)
    datos = _formulario(_leer(m, [_captura(PROV_A, "X", ("1001", 10500))]).text)
    assert datos["cheque_id_0"] == ""
    confirmada = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos/confirmar",
                                              data=dict(datos, accion="confirmar"))
    assert "el monto no coincide: en la cartera es $10.000" in confirmada.text
    # Aunque el cheque se elija A MANO, con otro monto tampoco entra.
    elegido = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos/confirmar",
                                           data=dict(datos, cheque_id_0=str(ids["1001"]), accion="confirmar"))
    assert re.findall(r'data-problemas>([^<]*)</p>', _sin_estilo(elegido.text)) == [
        "el monto no coincide: en la cartera es $10.000"]
    assert all(c["estado"] == "en_cartera" for c in d.buscar_cheques({}))


def test_SACAR_un_renglon_y_confirmar_termina(m, d):
    _galpon(d)
    datos = _formulario(_leer(m, CAPTURAS[2:3]).text)
    final = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos/confirmar",
                                         data=dict(datos, sacar_0="1", accion="confirmar"), follow_redirects=False)
    assert final.status_code == 303 and "0+cheques+aplicados" in final.headers["location"]


def test_la_CAPTURA_REAL_de_deposito_deja_los_dos_DEPOSITADOS_con_la_cuenta(m, d):
    _galpon(d)
    reales = _los_reales(d)
    pagina = _leer(m, [DEPOSITO_REAL])
    marcado = _sin_estilo(pagina.text)
    assert re.findall(r'data-tipo="([a-z]+)"', marcado) == ["deposito", "deposito"]
    assert re.findall(r'data-problemas>([^<]*)</p>', marcado) == []
    datos = _formulario(pagina.text)
    assert [(datos[f"cheque_id_{i}"], datos[f"concepto_id_{i}"], datos[f"proveedor_id_{i}"],
             datos[f"cuenta_deposito_{i}"]) for i in range(2)] == [
        (str(reales["00932970"]), "3", "", CUENTA), (str(reales["00020758"]), "3", "", CUENTA)]
    with patch("app.main.subir_foto_comanda", return_value="cheques/deposito.jpg"):
        final = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos/confirmar",
                                             data=dict(datos, accion="confirmar"), follow_redirects=False)
    assert final.status_code == 303 and "2+cheques+aplicados" in final.headers["location"]
    assert {c["numero"]: (c["estado"], c["concepto"], c["proveedor_id"], c["cuenta_deposito"])
            for c in d.buscar_cheques({}) if c["id"] in reales.values()} == {
        "00932970": ("depositado", "Depósito en cuenta", None, CUENTA),
        "00020758": ("depositado", "Depósito en cuenta", None, CUENTA)}
    # El CUIT que venía en la captura de depósito no se le pegó a nadie.
    assert {p["id"]: p["cuit"] for p in d.proveedores_con_cuit()} == {1: PROV_A, 2: None}
    ficha = _sin_estilo(_cliente(m, "gerencia").get(f"/gerencia/cheques/{reales['00020758']}").text)
    assert re.findall(r'<span data-cuenta-deposito>([^<]*)</span>', ficha) == [CUENTA]


def test_una_TANDA_MEZCLADA_cada_cheque_sale_como_dice_SU_foto(m, d):
    ids = _galpon(d)
    reales = _los_reales(d)
    pagina = _leer(m, [_captura(PROV_A, "EJEMPLO PUESTO SRL", ("1001", 10000)), DEPOSITO_REAL,
                       _captura(PROV_A, "EJEMPLO PUESTO SRL", ("1003", 30000))])
    marcado = _sin_estilo(pagina.text)
    assert re.findall(r'data-tipo="([a-z]+)"', marcado) == ["endoso", "deposito", "deposito", "endoso"]
    datos = _formulario(pagina.text)
    assert {datos[f"numero_{i}"]: (datos[f"concepto_id_{i}"], datos[f"proveedor_id_{i}"],
                                   datos[f"cuenta_deposito_{i}"]) for i in range(4)} == {
        "1001": ("1", "1", ""), "00932970": ("3", "", CUENTA), "00020758": ("3", "", CUENTA),
        "1003": ("1", "1", "")}
    # El de la foto 3 se pasa a depósito a mano: no se guarda proveedor, y como no
    # tiene cuenta queda sin cuenta. Uno de la foto de depósito pasado a pago a
    # proveedor pide el proveedor.
    datos[f"concepto_id_{_fila(datos, '1003')}"] = "3"
    datos[f"concepto_id_{_fila(datos, '00020758')}"] = "1"
    revisada = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos/confirmar",
                                            data=dict(datos, accion="revisar"))
    assert re.findall(r'data-problemas>([^<]*)</p>', _sin_estilo(revisada.text)) == ["elegí el proveedor"]
    rutas = iter(f"cheques/foto-{n}.jpg" for n in range(10))
    with patch("app.main.subir_foto_comanda", side_effect=lambda *a, **k: next(rutas)):
        confirmada = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos/confirmar",
                                                  data=dict(_formulario(revisada.text), accion="confirmar"))
    assert "Se aplicaron 3. Quedan 1 con problemas" in confirmada.text
    assert {c["numero"]: (c["estado"], c["proveedor_id"], c["cuenta_deposito"], c["foto_salida"])
            for c in d.buscar_cheques({}) if c["estado"] != "en_cartera"} == {
        "1001": ("entregado", 1, None, "cheques/foto-0.jpg"),
        "00932970": ("depositado", None, CUENTA, "cheques/foto-1.jpg"),
        "1003": ("depositado", None, None, "cheques/foto-2.jpg")}


# --- SIN BASE ----------------------------------------------------------------

DESTINOS = {1: "entregado", 2: "canjeado", 3: "depositado"}
CARTERA = [{"id": 1, "numero": "0042", "importe": 1000, "estado": "en_cartera"},     # con ceros adelante
           {"id": 2, "numero": "42", "importe": 2000, "estado": "en_cartera"},     # mismo número, otro monto
           {"id": 3, "numero": "77", "importe": 500, "estado": "depositado"}]


def test_la_COINCIDENCIA_es_por_numero_y_monto_y_dos_iguales_no_se_adivinan():
    proveedores = [{"id": 1, "cuit": PROV_A}, {"id": 2, "cuit": PROV_B}, {"id": 3, "cuit": PROV_B}]
    renglones, avisos = renglones_de_los_endosos(
        [{"proveedor_cuit": PROV_A, "cheques": [{"numero": "42", "importe": 2000}, {"numero": "77", "importe": 500}]},
         {"proveedor_cuit": PROV_A, "cheques": [{"numero": "00042", "importe": 1000}]},
         {"proveedor_cuit": PROV_B, "cheques": [{"numero": "9", "importe": 1}]}, {"error": "borrosa"}],
        cheques=CARTERA, proveedores=proveedores, concepto_id=1, concepto_deposito_id=3, hoy=date(2026, 10, 13))
    # "00042" de $1.000 es el "0042" de $1.000 (sin ceros adelante y por monto); "42" de $2.000, el
    # otro. Y no son el mismo cheque: no se toman como repetidos.
    assert avisos == ["La foto 4 no se pudo leer: borrosa"]
    assert [(r["numero"], r["cheque_id"], r["proveedor_id"]) for r in renglones] == [
        ("42", 2, 1), ("77", None, 1), ("00042", 1, 1), ("9", None, None)]   # PROV_B lo tienen dos: se elige
    assert problemas_de_los_endosos(renglones, CARTERA, destinos=DESTINOS) == [
        [], ["ya salió: está depositado"], [], ["no está en la cartera", "elegí el proveedor"]]
    # El mismo cheque elegido a mano en dos renglones.
    dos = [dict(renglones[0]), dict(renglones[0], numero="0042", importe="2000")]
    assert problemas_de_los_endosos(dos, CARTERA, destinos=DESTINOS) == [["ese cheque está en otro renglón"]] * 2
    # Sin proveedor: lo pide el pago a proveedor, no el depósito ni el canje.
    sin = [dict(renglones[0], proveedor_id=None, concepto_id=c) for c in (1, 2, 3)]
    assert problemas_de_los_endosos(sin, CARTERA, destinos=DESTINOS) == [
        ["ese cheque está en otro renglón", "elegí el proveedor"], ["ese cheque está en otro renglón"],
        ["ese cheque está en otro renglón"]]


def test_la_FOTO_de_deposito_se_reconoce_por_la_cuenta_aunque_no_diga_el_tipo():
    renglones, _ = renglones_de_los_endosos(
        [{"cuenta_deposito": " CC$ 191-220-000247/7 ", "proveedor_cuit": PROV_A,
          "cheques": [{"numero": "42", "importe": 2000}]},
         {"tipo": "endoso", "cuenta_deposito": None, "proveedor_cuit": PROV_A,
          "cheques": [{"numero": "0042", "importe": 1000}]}],
        cheques=CARTERA, proveedores=[{"id": 1, "cuit": PROV_A}], concepto_id=1, concepto_deposito_id=3,
        hoy=date(2026, 10, 13))
    assert [(r["deposito"], r["concepto_id"], r["proveedor_id"], r["cuenta_deposito"], r["proveedor_cuit"])
            for r in renglones] == [(True, 3, None, "CC$ 191-220-000247/7", ""), (False, 1, 1, "", PROV_A)]
