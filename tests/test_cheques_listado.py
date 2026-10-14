"""CARTERA DE CHEQUES: cargar un LISTADO con muchos cheques (dueño, 13/10).

Excel (.xlsx, .xls), CSV o PDF, con las columnas con cualquier nombre y en
cualquier orden. Antes de guardar, una tabla editable con el total y en rojo
los que tienen problema; "Guardar todos" guarda los que están bien y los otros
quedan hasta corregirlos o sacarlos.

EL GALPÓN, con nombres inventados: cliente 1 EJEMPLO Verdulería, bancos
EJEMPLO Banco y EJEMPLO Otro Banco, y un cheque ya cargado (el rival del
repetido): EJEMPLO Banco Nº 900, CUIT_A.
"""
import io
import os
import re
import sys
from datetime import date, datetime
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.listado_cheques import (  # noqa: E402
    COLUMNAS_DE_LA_PLANILLA,
    cuit_valido,
    filas_de_la_planilla,
    problemas_de_los_renglones,
    reconocer_columnas,
    renglones_de_la_planilla,
)
from tests.test_administracion_reordenada import _cliente  # noqa: E402
from tests.test_cheques import CUIT_A, CUIT_B, _cargar, d  # noqa: E402,F401
from tests.test_cheques_pantallas import _sin_estilo, m  # noqa: E402,F401

CUIT_MAL = "20111111111"          # 11 números, el dígito verificador no da


# --- SIN BASE: columnas, valores y problemas -----------------------------------

def test_las_COLUMNAS_se_reconocen_con_cualquier_nombre_y_orden():
    titulos = ["Razón Social", "Monto $", "Nro. Cheque", "CUIT Librador", "Entidad", "Fecha de Pago", "Observ."]
    assert reconocer_columnas(titulos) == {"librador": 0, "importe": 1, "numero": 2, "cuit_librador": 3,
                                           "banco": 4, "fecha_pago": 5}
    # La planilla modelo se reconoce entera.
    assert set(reconocer_columnas(list(COLUMNAS_DE_LA_PLANILLA))) == {
        "numero", "banco", "fecha_pago", "importe", "cuit_librador", "librador", "tipo"}


def test_un_CSV_con_punto_y_coma_titulos_abajo_y_montos_argentinos():
    csv = ("Listado de cheques del banco;;;\n;;;\n"
           "Fecha de cobro;Importe;N° de cheque;CUIT\n"
           "15/11/2026;$ 1.234,56;00012345;20-11111111-2\n"
           ";;;\n"
           "16/11/2026;980;777;27-22222222-8\n"
           "Total;$ 2.214,56;;\n").encode("latin-1")
    renglones = renglones_de_la_planilla(filas_de_la_planilla(csv, "csv"))
    assert [(r["fecha_pago"], r["importe"], r["numero"], r["cuit_librador"]) for r in renglones] == [
        ("15/11/2026", "$ 1.234,56", "00012345", "20-11111111-2"), ("16/11/2026", "980", "777", "27-22222222-8")]


def test_sin_TITULOS_que_se_reconozcan_no_inventa_columnas():
    assert renglones_de_la_planilla([["a", "b"], ["1", "2"]]) is None


def test_el_CUIT_valido_lleva_el_digito_verificador():
    assert cuit_valido(CUIT_A) and cuit_valido(CUIT_B)
    assert not cuit_valido(CUIT_MAL) and not cuit_valido("2011111111") and not cuit_valido("")


def _renglon(numero, cuit=CUIT_A, banco="EJEMPLO Banco", **otros):
    return {"numero": numero, "banco": banco, "fecha_pago": "2026-11-15", "importe": "1000", "cuit_librador": cuit,
            "tipo": "fisico", "origen": "canje", "cliente_id": None, "nombre_a_mano": "", **otros}


def test_los_PROBLEMAS_de_cada_renglon():
    bancos = [{"nombre": "EJEMPLO Banco"}]
    ya = {("EJEMPLO BANCO", "900", CUIT_A)}
    renglones = [_renglon("1"), _renglon("0900"), _renglon("2", CUIT_MAL), _renglon("3", banco="EJEMPLO Nuevo"),
                 _renglon("5"), _renglon("005", banco="BANCO DE EJEMPLO"), _renglon("6", importe="", origen="a_mano"),
                 _renglon("7", origen="cliente"), _renglon("8"), _renglon("8", sacar=True)]
    # "BANCO DE EJEMPLO" es "EJEMPLO Banco": el 005 es el 5 repetido. Un sacado no repite.
    assert problemas_de_los_renglones(renglones, bancos, ya) == [
        [], ["ya está cargado"], ["CUIT inválido"], ["el banco no está en la lista"],
        ["repetido en el listado"], ["repetido en el listado"], ["falta el importe", "falta de quién es"],
        ["elegí el cliente"], [], []]


# --- CONTRA LA BASE, POR LA PANTALLA -------------------------------------------

def _xlsx(filas: list[list]) -> bytes:
    from openpyxl import Workbook
    libro = Workbook()
    for fila in filas:
        libro.active.append(fila)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


LISTADO = [
    ["Librador", "Nro. Cheque", "Entidad", "Vencimiento", "Monto", "CUIT"],
    ["EJEMPLO Verduleria", 1001, "Banco EJEMPLO Banco", datetime(2026, 11, 15), 15000.5, CUIT_A],
    ["EJEMPLO Persona", "1002", "EJEMPLO Otro Banco", "16/11/2026", "$ 20.000", CUIT_B],
    ["EJEMPLO Persona", "1003", "EJEMPLO Banco", "17/11/2026", "30000", CUIT_MAL],        # CUIT mal
    ["EJEMPLO Verduleria", "00900", "EJEMPLO Banco", "18/11/2026", "40000", CUIT_A],     # repetido
]


def _leer(m, nombre, contenido):
    return _cliente(m, "gerencia").post("/gerencia/cheques/cargar/leer", files={"archivo": (nombre, contenido)})


def _formulario(html: str) -> dict:
    """Lo que el navegador mandaría del formulario de la tabla, tal cual."""
    marcado = _sin_estilo(html).split('action="/gerencia/cheques/cargar/listado">')[1].split("</form>")[0]
    datos = {}
    for nombre, valor in re.findall(r'<input type="(?:hidden|text|date|number)" name="([a-z_0-9]+)"[^>]*?value="([^"]*)"', marcado):
        datos[nombre] = valor
    for nombre, cuerpo in re.findall(r'<select name="([a-z_0-9]+)">(.*?)</select>', marcado, re.S):
        elegido = re.search(r'<option value="([^"]*)" selected', cuerpo)
        datos[nombre] = elegido.group(1) if elegido else ""
    return datos


def test_un_LISTADO_con_un_REPETIDO_y_un_CUIT_MAL_entran_los_demas_y_esos_dos_quedan_marcados(m, d):
    _cargar(d, "900", cuit=CUIT_A)                                         # el que ya estaba
    pagina = _leer(m, "listado.xlsx", _xlsx(LISTADO))
    assert pagina.status_code == 200, pagina.text[:300]
    marcado = _sin_estilo(pagina.text)
    assert len(re.findall(r'data-renglon="\d+"', marcado)) == 4
    assert re.findall(r'data-problemas>([^<]*)<', marcado) == ["CUIT inválido",
                                                                                       "ya está cargado"]
    assert re.search(r'data-conteo>4 cheques · \$105\.000 · <span data-bien>2 bien</span>', marcado)
    assert re.search(r'data-con-problema>2 con problema</span>', marcado)
    # Lo leído: el cliente del sistema por su nombre, el banco de la lista y el monto argentino.
    datos = _formulario(pagina.text)
    assert (datos["origen_0"], datos["cliente_id_0"], datos["banco_0"], datos["importe_0"]) == (
        "cliente", "1", "EJEMPLO Banco", "15000.5")
    assert (datos["origen_1"], datos["nombre_a_mano_1"], datos["importe_1"]) == ("a_mano", "EJEMPLO Persona", "20000")

    guardado = _cliente(m, "gerencia").post("/gerencia/cheques/cargar/listado", data=dict(datos, accion="guardar"))
    assert guardado.status_code == 200
    assert "Se guardaron 2. Quedan 2 con problemas" in guardado.text
    assert sorted(c["numero"] for c in d.buscar_cheques({})) == ["1001", "1002", "900"]
    quedan = _sin_estilo(guardado.text)
    assert re.findall(r'data-problemas>([^<]*)<', quedan) == ["CUIT inválido",
                                                                                      "ya está cargado"]
    # Se corrige el CUIT y se saca el repetido: entra el corregido y termina.
    datos = _formulario(guardado.text)
    datos.update({"cuit_librador_0": "20333333334", "sacar_1": "1", "accion": "guardar"})
    final = _cliente(m, "gerencia").post("/gerencia/cheques/cargar/listado", data=datos, follow_redirects=False)
    assert final.status_code == 303 and "1+cheques+cargados" in final.headers["location"]
    assert sorted(c["numero"] for c in d.buscar_cheques({})) == ["1001", "1002", "1003", "900"]


def test_PARA_TODOS_pone_el_mismo_origen_en_cada_renglon(m, d):
    datos = _formulario(_leer(m, "listado.xlsx", _xlsx(LISTADO[:3])).text)
    datos.update({"accion": "a_todos", "origen_todos": "canje"})
    pagina = _cliente(m, "gerencia").post("/gerencia/cheques/cargar/listado", data=datos)
    nuevos = _formulario(pagina.text)
    assert [nuevos[f"origen_{i}"] for i in range(2)] == ["canje", "canje"]
    assert d.buscar_cheques({}) == []                                      # revisar no guarda


def test_un_BANCO_que_no_esta_se_avisa_UNA_vez_y_se_agrega_para_todos(m, d):
    filas = [["Número", "Banco", "Fecha de pago", "Importe", "CUIT del librador"],
             ["55", "EJEMPLO Banco Inventado", "20/11/2026", "500", CUIT_A],
             ["56", "BANCO EJEMPLO INVENTADO S.A.", "20/11/2026", "600", CUIT_A],
             ["57", "EJEMPLO Banco Más Inventado", "20/11/2026", "700", CUIT_A]]       # el RIVAL: otro banco
    datos = _formulario(_leer(m, "listado.xlsx", _xlsx(filas)).text)
    datos.update({f"origen_{i}": "canje" for i in range(3)})
    pagina = _cliente(m, "gerencia").post("/gerencia/cheques/cargar/listado", data=dict(datos, accion="guardar"))
    avisos = re.findall(r'data-falta-banco><span><strong>([^<]*)</strong> no está en la lista \((\d+) cheques?\)',
                        _sin_estilo(pagina.text))
    assert avisos == [("EJEMPLO Banco Inventado", "2"), ("EJEMPLO Banco Más Inventado", "1")]
    assert d.buscar_cheques({}) == []
    agregado = _cliente(m, "gerencia").post("/gerencia/cheques/cargar/listado",
                                            data=dict(_formulario(pagina.text), agregar_banco="EJEMPLO Banco Inventado"))
    assert "Se agregó EJEMPLO Banco Inventado a la lista de bancos." in agregado.text
    marcado = _sin_estilo(agregado.text)
    assert re.findall(r'data-falta-banco><span><strong>([^<]*)</strong>', marcado) == ["EJEMPLO Banco Más Inventado"]
    assert re.findall(r'data-problemas>([^<]*)<', marcado) == ["el banco no está en la lista"]
    final = _cliente(m, "gerencia").post("/gerencia/cheques/cargar/listado",
                                        data=dict(_formulario(agregado.text), accion="guardar"))
    assert "Se guardaron 2." in final.text
    assert sorted((c["numero"], c["banco"]) for c in d.buscar_cheques({})) == [
        ("55", "EJEMPLO Banco Inventado"), ("56", "EJEMPLO Banco Inventado")]
    assert [b["nombre"] for b in d.listar_bancos()].count("EJEMPLO Banco Inventado") == 1


def test_un_CSV_y_un_XLS_se_leen_igual(m, d):
    csv = ("Nro;Banco;Fecha;Importe;CUIT\n1;EJEMPLO Banco;15/11/2026;1.500,00;" + CUIT_A + "\n").encode("utf-8")
    assert "1500" in _formulario(_leer(m, "cheques.csv", csv).text)["importe_0"]
    xlwt = pytest.importorskip("xlwt")
    libro = xlwt.Workbook()
    hoja = libro.add_sheet("Cheques")
    for i, fila in enumerate([["Número", "Banco", "Fecha de pago", "Importe", "CUIT"],
                              ["2", "EJEMPLO Banco", "16/11/2026", 2500, CUIT_B]]):
        for j, valor in enumerate(fila):
            hoja.write(i, j, valor)
    salida = io.BytesIO()
    libro.save(salida)
    datos = _formulario(_leer(m, "cheques.xls", salida.getvalue()).text)
    assert (datos["numero_0"], datos["importe_0"], datos["fecha_pago_0"], datos["cuit_librador_0"]) == (
        "2", "2500", "2026-11-16", CUIT_B)


def test_TITULOS_raros_o_un_PDF_los_lee_la_IA(m, d):
    leido = {"fecha": None, "cheques": [{"numero": "ECH-1", "banco": "EJEMPLO Banco", "fecha_pago": "2026-11-20",
                                         "importe": 7000, "cuit_librador": CUIT_A, "librador": None, "tipo": None},
                                        {"numero": "ECH-2", "banco": "EJEMPLO Banco", "fecha_pago": "2026-11-21",
                                         "importe": 8000, "cuit_librador": CUIT_B, "librador": None, "tipo": None}]}
    with patch("app.main.extraer_cheques_de_texto", return_value=leido) as lector:
        pagina = _leer(m, "raro.xlsx", _xlsx([["col1", "col2"], ["ECH-1", "7000"]]))
    assert lector.call_count == 1 and len(re.findall(r'data-renglon="\d+"', pagina.text)) == 2
    with patch("app.main.extraer_cheques_de_imagenes", return_value=leido), \
            patch("app.main.imagenes_desde_pdf", return_value=[b"pagina"]):
        pdf = _formulario(_leer(m, "echeq.pdf", b"%PDF-1.4").text)
    # Del listado de ECHEQ del banco, sin tipo leído, son ECHEQ.
    assert (pdf["tipo_0"], pdf["tipo_1"]) == ("echeq", "echeq")


def test_la_PLANILLA_MODELO_baja_vacia_y_se_reconoce_sola(m):
    respuesta = _cliente(m, "gerencia").get("/gerencia/cheques/planilla-modelo")
    assert respuesta.headers["content-type"].startswith("application/vnd.openxmlformats")
    filas = filas_de_la_planilla(respuesta.content, "xlsx")
    assert [tuple(f) for f in filas] == [COLUMNAS_DE_LA_PLANILLA]
    assert renglones_de_la_planilla(filas) == []
    pagina = _cliente(m, "gerencia").get("/gerencia/cheques/cargar").text
    assert '<a href="/gerencia/cheques/planilla-modelo">Bajar planilla modelo</a>' in pagina
