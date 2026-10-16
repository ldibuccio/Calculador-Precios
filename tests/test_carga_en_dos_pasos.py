"""LA CARGA EN DOS PASOS (dueño, 16/10): Palmala Cruces, Caja, Banco e
Inversiones cargan igual que "Aplicar cheques". Paso 1: archivos y/o filas a
mano. Paso 2: revisar agrupado por archivo, "Para todos", el encabezado del
grupo y "Confirmar todos". Contra Postgres.

La lectura de las fotos se reemplaza por lo que la IA habría devuelto, y la
subida a Storage por una ruta inventada: lo que se prueba es qué hace el
sistema con lo leído. Nombres inventados; fechas fijas de 2025, que no
pueden ser hoy.
"""
import os
import re
import sys
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.carga_en_dos_pasos import (  # noqa: E402
    A_MANO,
    REPETIDO_EN_LA_CARGA,
    como_se_cargo,
    grupos,
    poner_a_los_tildados,
    repetidos,
)
from tests.test_cheques import d  # noqa: E402,F401
from tests.test_cheques_pantallas import _foto, _sin_estilo, m  # noqa: E402,F401
from tests.test_cuentas import _concepto as _concepto_de_cuenta, _gerencia, _sembrar_frutamax, _xlsx  # noqa: E402
from tests.test_palmala_cruces import _concepto, _formulario, _mov  # noqa: E402

PALMALA = "/gerencia/palmala-cruces"


def _resumen(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", "", re.search(r"data-resumen>(.*?)</p>", _sin_estilo(html), re.S)[1]).split())


def _titulos(html: str) -> list[str]:
    return [" ".join(t.split()) for t in re.findall(r"data-titulo-del-grupo>([^<]*)<", _sin_estilo(html))]


def _problemas(html: str) -> list[str]:
    return re.findall(r"data-problemas>([^<]*)<", _sin_estilo(html))


def _seguir(cliente, base, archivos=(), a_mano=0):
    return cliente.post(f"{base}/cargar/seguir", data={"a_mano": str(a_mano)},
                        files=[("archivos", a) for a in archivos] or None)


def _revisar(cliente, base, html, **cambios):
    return cliente.post(f"{base}/revisar", data=dict(_formulario(html, f"{base}/revisar"), **cambios),
                        follow_redirects=False)


# --- LO PURO --------------------------------------------------------------------

def test_PARA_TODOS_va_a_los_tildados_y_sin_ninguno_PREGUNTA():
    renglones = [{"cuenta": "pesos", "tildado": True}, {"cuenta": "pesos"}, {"cuenta": "pesos", "sacar": True}]
    assert poner_a_los_tildados(renglones, {"cuenta": "dolares_ndt", "fecha": ""}) == 1
    assert [r["cuenta"] for r in renglones] == ["dolares_ndt", "pesos", "pesos"]
    assert poner_a_los_tildados(renglones, {"cuenta": "dolares_socios"}) is None          # nadie tildado
    assert [r["cuenta"] for r in renglones] == ["dolares_ndt", "pesos", "pesos"]
    assert poner_a_los_tildados(renglones, {"cuenta": "dolares_socios"}, sin_tildar_tambien=True) == 2
    assert [r["cuenta"] for r in renglones] == ["dolares_socios", "dolares_socios", "pesos"]   # el sacado, no


def test_los_REPETIDOS_contra_la_base_y_dentro_de_la_carga_y_el_que_NO_ES():
    clave = lambda r: r.get("k")  # noqa: E731
    renglones = [{"k": 1}, {"k": 2}, {"k": 2}, {"k": 3, "no_es_repetido": True}, {"k": 2, "sacar": True}, {"k": None}]
    assert repetidos(renglones, clave, {3: "el 01/05/2025", 1: "el 02/05/2025"}) == [
        "repetido: ya está cargado (el 02/05/2025)", None, REPETIDO_EN_LA_CARGA, None, None, None]


def test_los_GRUPOS_por_archivo_en_orden_y_los_a_mano_al_final():
    renglones = [{"archivo": A_MANO}, {"archivo": 1}, {"archivo": 0}, {"archivo": 1, "sacar": True}]
    salida = grupos(renglones, [[], ["mal"], [], ["mal"]], ["a.jpg", "b.xlsx"], lambda rs: str(len(rs)))
    assert [(g["titulo"], g["indices"], g["cuantos"], g["con_problema"], g["total_texto"]) for g in salida] == [
        ("a.jpg", [2], 1, 0, "1"), ("b.xlsx", [1, 3], 1, 1, "1"), ("Cargados a mano", [0], 1, 0, "1")]
    assert [como_se_cargo({"archivo": a}, ["foto", "excel", ""]) for a in (0, 1, 2, A_MANO)] == [
        "foto", "excel", "a_mano", "a_mano"]


# --- PALMALA CRUCES -----------------------------------------------------------------

def test_PALMALA_solo_ARCHIVOS_una_foto_de_cheques_y_un_Excel_cada_uno_su_grupo_y_su_origen(m, d):
    cliente = _gerencia(m)
    leida = {"movimientos": [
        {"fecha": "2025-08-01", "sentido": None, "importe": 1000, "concepto": None, "detalle": "EJEMPLO SA",
         "cheque": {"numero": "100", "banco": "EJEMPLO Banco", "fecha_pago": "2025-09-01", "tipo": "fisico"}},
        {"fecha": "2025-08-01", "sentido": None, "importe": 500, "concepto": None, "detalle": None,
         "cheque": {"numero": "E-5", "banco": "EJEMPLO Banco", "fecha_pago": "2025-09-02", "tipo": "echeq"}}]}
    planilla = _xlsx([["Fecha", "Concepto", "Debe", "Pagó"], ["01/03/2025", "Comisiones Día", 700, None],
                      ["02/03/2025", "Pago en efectivo", None, 300], ["Total", None, 700, 300]])
    with patch("app.main.extraer_movimientos_de_palmala", return_value=leida) as lector:
        pagina = _seguir(cliente, PALMALA, [("cheques.jpg", _foto(), "image/jpeg"),
                                            ("historico.xlsx", planilla, "application/octet-stream")])
    assert pagina.status_code == 200, pagina.text[:300]
    assert lector.call_count == 1                                       # el Excel no pasa por la IA
    assert "Pago con cheque" in lector.call_args.kwargs["conceptos"]
    assert _titulos(pagina.text) == ["cheques.jpg · 2 movimientos · $1.500", "historico.xlsx · 2 movimientos · $1.000"]
    assert _resumen(pagina.text) == "4 movimientos · $2.500 · 4 bien · 0 con problema"
    datos = _formulario(pagina.text, f"{PALMALA}/revisar")
    con, echeq = str(_concepto(d, "Pago con cheque")), str(_concepto(d, "Pago con echeq"))
    assert {datos[f"importe_{i}"]: (datos[f"concepto_id_{i}"], datos[f"sentido_{i}"], datos[f"cuenta_{i}"])
            for i in range(2)} == {"1000": (con, "pago", "pesos"), "500": (echeq, "pago", "pesos")}
    with patch("app.main.subir_foto_comanda", return_value="palmala/cheques.jpg") as subir:
        final = _revisar(cliente, PALMALA, pagina.text, accion="confirmar")
    assert final.status_code == 303 and "4+movimientos+cargados" in final.headers["location"]
    assert subir.call_count == 1                                       # una por foto; el Excel no tiene
    assert sorted((float(x["importe"]), x["foto_ruta"], x["como_se_cargo"])
                  for x in d.buscar_movimientos_de_palmala({})) == [
        (300.0, None, "excel"), (500.0, "palmala/cheques.jpg", "foto"), (700.0, None, "excel"),
        (1000.0, "palmala/cheques.jpg", "foto")]


def test_PALMALA_solo_A_MANO_las_filas_vacias_piden_sus_datos_y_el_cheque_lo_suyo(m, d):
    cliente = _gerencia(m)
    pagina = _seguir(cliente, PALMALA, a_mano=2)
    assert _titulos(pagina.text) == ["Cargados a mano · 2 movimientos · $0"]
    assert _resumen(pagina.text) == "2 movimientos · $0 · 0 bien · 2 con problema"
    assert _problemas(pagina.text)[0] == "decí si Palmala debe o pagó · falta el importe · elegí el concepto"
    cheque = str(_concepto(d, "Pago con cheque"))
    datos = _formulario(pagina.text, f"{PALMALA}/revisar")
    assert datos["cuenta_0"] == "pesos"                                # Pesos por defecto
    datos.update(fecha_0="2025-06-01", sentido_0="pago", importe_0="1500,50", concepto_id_0=cheque,
                 cheque_numero_0="77", fecha_1="2025-06-02", sentido_1="debe", importe_1="10",
                 concepto_id_1=str(_concepto(d, "Comisiones Día")))
    revisado = cliente.post(f"{PALMALA}/revisar", data=dict(datos, accion="confirmar"))
    assert "Se guardaron 1. Quedan 1 con problemas" in revisado.text
    assert _problemas(revisado.text) == ["falta el banco · falta la fecha de pago del cheque"]
    final = _revisar(cliente, PALMALA, revisado.text, accion="confirmar", cheque_banco_0="EJEMPLO Banco",
                     cheque_fecha_pago_0="2025-07-01")
    assert final.status_code == 303
    assert sorted((float(x["importe"]), x["cheque_numero"], x["como_se_cargo"])
                  for x in d.buscar_movimientos_de_palmala({})) == [(10.0, None, "a_mano"), (1500.5, "77", "a_mano")]


def test_PALMALA_MEZCLADO_una_foto_y_una_fila_a_mano_en_la_misma_carga(m, d):
    cliente = _gerencia(m)
    leida = {"movimientos": [{"fecha": "2025-08-05", "sentido": "pago", "importe": 2000,
                              "concepto": "Pago en efectivo", "detalle": "recibo 9", "cheque": None}]}
    with patch("app.main.extraer_movimientos_de_palmala", return_value=leida):
        pagina = _seguir(cliente, PALMALA, [("recibo.jpg", _foto(), "image/jpeg")], a_mano=1)
    assert _titulos(pagina.text) == ["recibo.jpg · 1 movimiento · $2.000", "Cargados a mano · 1 movimiento · $0"]
    datos = _formulario(pagina.text, f"{PALMALA}/revisar")
    a_mano = next(i for i in range(2) if datos[f"archivo_{i}"] == "-1")
    datos.update({f"sentido_{a_mano}": "debe", f"importe_{a_mano}": "300",
                  f"concepto_id_{a_mano}": str(_concepto(d, "Comisiones Día")), f"fecha_{a_mano}": "2025-08-06"})
    with patch("app.main.subir_foto_comanda", return_value="palmala/recibo.jpg"):
        final = cliente.post(f"{PALMALA}/revisar", data=dict(datos, accion="confirmar"), follow_redirects=False)
    assert final.status_code == 303 and "2+movimientos+cargados" in final.headers["location"]
    assert sorted((float(x["importe"]), x["foto_ruta"], x["como_se_cargo"])
                  for x in d.buscar_movimientos_de_palmala({})) == [
        (300.0, None, "a_mano"), (2000.0, "palmala/recibo.jpg", "foto")]


def test_PALMALA_PARA_TODOS_y_el_ENCABEZADO_del_grupo(m, d):
    cliente = _gerencia(m)
    planilla = _xlsx([["Fecha", "Concepto", "Debe"]] + [[f"0{n}/04/2025", "Comisiones Día", 100 * n] for n in (1, 2, 3)])
    pagina = _seguir(cliente, PALMALA, [("abril.xlsx", planilla, "application/octet-stream")], a_mano=1)
    # Sin tildar ninguno, "Para todos" pregunta antes de ponerlo en todos.
    pregunta = _revisar(cliente, PALMALA, pagina.text, accion="a_todos", todos_cuenta="dolares_ndt")
    assert "data-pregunta-a-todos" in pregunta.text
    # Con el primero tildado, va solo a ése.
    uno = _revisar(cliente, PALMALA, pagina.text, accion="a_todos", todos_cuenta="dolares_ndt", tildado_0="1")
    assert "Se cambió en 1 movimiento." in uno.text
    datos = _formulario(uno.text, f"{PALMALA}/revisar")
    assert [datos[f"cuenta_{i}"] for i in range(3)] == ["dolares_ndt", "pesos", "pesos"]
    # El encabezado del grupo del Excel cambia sus tres, no la fila a mano.
    grupo = _revisar(cliente, PALMALA, uno.text, accion="grupo_0", grupo_0_fecha="2025-04-30",
                     grupo_0_sentido="pago")
    datos = _formulario(grupo.text, f"{PALMALA}/revisar")
    assert [(datos[f"fecha_{i}"], datos[f"sentido_{i}"]) for i in range(3)] == [("2025-04-30", "pago")] * 3
    assert (datos["fecha_3"] != "2025-04-30", datos["sentido_3"]) == (True, "")
    # "Sí, a todos": también la fila a mano.
    todos = _revisar(cliente, PALMALA, grupo.text, accion="a_todos_si", todos_cuenta="dolares_socios")
    datos = _formulario(todos.text, f"{PALMALA}/revisar")
    assert [datos[f"cuenta_{i}"] for i in range(4)] == ["dolares_socios"] * 4


def test_PALMALA_un_REPETIDO_queda_en_rojo_hasta_decir_que_NO_ES(m, d):
    _mov(d, "2025-04-01", "pesos", "debe", 100)                              # ya cargado
    cliente = _gerencia(m)
    planilla = _xlsx([["Fecha", "Concepto", "Debe"], ["01/04/2025", "Comisiones Día", 100],
                      ["02/04/2025", "Comisiones Día", 50], ["02/04/2025", "Comisiones Día", 50]])
    pagina = _seguir(cliente, PALMALA, [("abril.xlsx", planilla, "application/octet-stream")])
    assert _problemas(pagina.text) == ["repetido: ya está cargado (el 01/04/2025, Comisiones Día)",
                                       REPETIDO_EN_LA_CARGA]
    assert _resumen(pagina.text) == "3 movimientos · $200 · 1 bien · 2 con problema"
    assert len(re.findall(r"data-no-es-repetido>", _sin_estilo(pagina.text))) == 2
    # "No es repetido" en el segundo de 50: entran los dos de 50; el de 100 queda.
    final = _revisar(cliente, PALMALA, pagina.text, accion="confirmar", no_es_repetido_2="1")
    assert "Se guardaron 2. Quedan 1 con problemas" in final.text
    assert sorted(float(x["importe"]) for x in d.buscar_movimientos_de_palmala({})) == [50.0, 50.0, 100.0]


def test_PALMALA_sin_nada_elegido_no_sigue_y_las_pantallas_viejas_no_estan(m, d):
    cliente = _gerencia(m)
    vacio = _seguir(cliente, PALMALA)
    assert vacio.status_code == 400 and "Subí un archivo o decí cuántos vas a cargar a mano." in vacio.text
    rutas = {r.path for r in m.app.routes}
    assert not rutas & {"/gerencia/palmala-cruces/cargar/fotos", "/gerencia/palmala-cruces/cargar/excel",
                        "/gerencia/cuentas/{cuenta_id}/cargar/fotos", "/gerencia/cuentas/{cuenta_id}/cargar/excel"}
    assert cliente.post(f"{PALMALA}/cargar", data={}).status_code == 405


# --- CAJA, BANCO E INVERSIONES -----------------------------------------------------

def test_CUENTA_solo_A_MANO_con_sus_campos_y_la_etiqueta_que_se_arma_sola(m, d):
    caja = _sembrar_frutamax(d)["Caja Lionel"]
    base = f"/gerencia/cuentas/{caja}"
    cliente = _gerencia(m)
    pagina = _seguir(cliente, base, a_mano=1)
    marcado = _sin_estilo(pagina.text)
    assert 'name="tipo_0"' in marcado and 'name="etiqueta_0"' in marcado and 'name="sentido_0"' not in marcado
    datos = _formulario(pagina.text, f"{base}/revisar")
    datos.update(fecha_0="2025-05-01", tipo_0="egreso", importe_0="5",
                 concepto_id_0=str(_concepto_de_cuenta(d, caja, "Cobro Mecafront")), etiqueta_0="  EJEMPLO  Mecafront ")
    mal = cliente.post(f"{base}/revisar", data=dict(datos, accion="confirmar"))
    assert _problemas(mal.text) == ["Cobro Mecafront es un ingreso"]
    final = _revisar(cliente, base, mal.text, accion="confirmar", tipo_0="ingreso")
    assert final.status_code == 303 and "1+movimiento+cargado" in final.headers["location"]
    assert [e["nombre"] for e in d.etiquetas_de_cuentas()] == ["EJEMPLO Mecafront"]


def test_CUENTA_MEZCLADO_fotos_Excel_y_a_mano_con_PARA_TODOS(m, d):
    banco = _sembrar_frutamax(d)["Banco Credicoop"]
    base = f"/gerencia/cuentas/{banco}"
    cliente = _gerencia(m)
    leidas = [{"movimientos": [{"fecha": "2025-05-01", "tipo": "egreso", "importe": 2500, "quien": "EJEMPLO SRL",
                                "concepto": None, "detalle": "transferencia 7"}]}, RuntimeError("no se entiende")]
    planilla = _xlsx([["Fecha", "Importe", "Tipo"], ["03/05/2025", 300, "Egreso"]])
    with patch("core.lector_cuentas.extraer_movimientos_de_imagenes", side_effect=leidas):
        pagina = _seguir(cliente, base, [("t.jpg", _foto(), "image/jpeg"), ("rota.jpg", _foto(), "image/jpeg"),
                                         ("mayo.xlsx", planilla, "application/octet-stream")], a_mano=1)
    assert "«rota.jpg» no se pudo leer" in pagina.text
    assert _titulos(pagina.text) == ["t.jpg · 1 movimiento · $2.500", "mayo.xlsx · 1 movimiento · $300",
                                     "Cargados a mano · 1 movimiento · $0"]
    concepto = _concepto_de_cuenta(d, banco, "Impuestos y comisiones")
    cambiado = _revisar(cliente, base, pagina.text, accion="a_todos_si", todos_concepto_id=str(concepto),
                        todos_tipo="egreso")
    assert "Se cambió en 3 movimientos." in cambiado.text
    datos = _formulario(cambiado.text, f"{base}/revisar")
    datos.update(importe_2="40")
    with patch("app.main.subir_foto_comanda", return_value="cuentas/t.jpg") as subir:
        final = cliente.post(f"{base}/revisar", data=dict(datos, accion="confirmar"), follow_redirects=False)
    assert final.status_code == 303 and subir.call_count == 1
    origenes = sorted((float(x["importe"]), x["como_se_cargo"], x["foto_ruta"])
                      for x in (d.obtener_movimiento_de_cuenta(mov["origen_id"])
                                for mov in d.movimientos_de_la_cuenta(banco)))
    assert origenes == [(40.0, "a_mano", None), (300.0, "excel", None), (2500.0, "foto", "cuentas/t.jpg")]
