"""Fotos de un remito RECIBIDO (dueño, 05/10): se AGREGAN, con fecha y quién.

Nunca se reemplazan ni se borran desde el remito: la ruta nueva solo inserta,
y la pantalla no ofrece nada más. Contra Postgres, con el galpón de remitos.
"""
import os
import re
import sys
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_remitos import _cliente, _jpeg, _recibido, base  # noqa: E402,F401
from tests.test_remitos import _que_se_sale  # noqa: E402


def _foto(nombre="r.jpg"):
    return ("fotos", (nombre, _jpeg(), "image/jpeg"))


def test_ADMINISTRACION_agrega_fotos_a_un_remito_recibido_y_las_de_antes_quedan(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id)                              # la del firmado: remitos/EJ.jpg
    cliente = _cliente(monkeypatch, "administracion")
    rutas = iter(["remitos/EJ-otra-1.jpg", "remitos/EJ-otra-2.jpg"])
    with patch("app.main.subir_foto_comanda", side_effect=lambda *a, **k: next(rutas)):
        respuesta = cliente.post(f"/administracion/facturacion/remito/{remito_id}/fotos",
                                 files=[_foto("a.jpg"), _foto("b.jpg")], follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith(f"/administracion/facturacion/remito/{remito_id}?aviso=")
    fotos = d.remito_por_id(remito_id)["fotos"]
    assert [(f["ruta"], f["cargada_por"]) for f in fotos] == [
        ("remitos/EJ.jpg", "administracion"), ("remitos/EJ-otra-1.jpg", "administracion"),
        ("remitos/EJ-otra-2.jpg", "administracion")]


def test_GERENCIA_tambien_agrega_y_queda_que_fue_GERENCIA(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id)
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main.subir_foto_comanda", return_value="remitos/EJ-ger.jpg"):
        respuesta = cliente.post(f"/gerencia/facturacion/remito/{remito_id}/fotos",
                                 files=[_foto()], follow_redirects=False)
    assert respuesta.status_code == 303
    assert [f["cargada_por"] for f in d.remito_por_id(remito_id)["fotos"]] == ["administracion", "gerencia"]

    # Sin su clave, Gerencia no escribe y no sube nada.
    sin_clave = _cliente(monkeypatch)
    with patch("app.main.subir_foto_comanda") as subir:
        sin_clave.post(f"/gerencia/facturacion/remito/{remito_id}/fotos", files=[_foto()], follow_redirects=False)
    subir.assert_not_called()
    assert len(d.remito_por_id(remito_id)["fotos"]) == 2


def test_un_remito_SIN_RECIBIR_no_toma_fotos_sueltas_y_la_subida_se_borra(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main.subir_foto_comanda", return_value="remitos/EJ-huerfana.jpg"), \
         patch("app.main.borrar_foto_comanda") as borrar:
        respuesta = cliente.post(f"/administracion/facturacion/remito/{remito_id}/fotos", files=[_foto()])
    assert "todavía no se recibió" in respuesta.text
    borrar.assert_called_once_with("remitos/EJ-huerfana.jpg")
    assert d.remito_por_id(remito_id)["fotos"] == []


def test_sin_foto_elegida_no_guarda_nada(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id)
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main.subir_foto_comanda") as subir:
        respuesta = cliente.post(f"/administracion/facturacion/remito/{remito_id}/fotos", data={})
    subir.assert_not_called()
    assert "Elegí al menos una foto." in respuesta.text
    assert len(d.remito_por_id(remito_id)["fotos"]) == 1


def test_la_PANTALLA_muestra_fecha_y_quien_y_solo_ofrece_AGREGAR(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    cliente = _cliente(monkeypatch, "administracion")
    sin_recibir = cliente.get(f"/administracion/facturacion/remito/{remito_id}").text.split("</style>")[-1]
    assert "/fotos\"" not in sin_recibir and 'enctype="multipart/form-data"' not in sin_recibir

    _recibido(d, remito_id)
    sql("UPDATE remitos_fotos SET creado_en = '2026-09-07 10:15-03'")
    pagina = cliente.get(f"/administracion/facturacion/remito/{remito_id}").text.split("</style>")[-1]
    assert "<figcaption>07/09/2026 10:15<br>Administración</figcaption>" in pagina
    formularios = re.findall(r'<form method="post"[^>]*action="([^"]+)"', pagina)
    assert formularios == [f"/administracion/facturacion/remito/{remito_id}/fotos"]
    assert pagina.count('type="file"') + pagina.count("boton-agregar-foto") >= 1
    # Ni reemplazar ni borrar una foto guardada: no hay ruta ni botón para eso.
    assert not re.search(r"(borrar|reemplazar|eliminar)[^<]*foto", pagina.split('id="fotos"')[1].split("</div>")[0],
                         re.I)


def test_las_rutas_de_fotos_del_remito_solo_INSERTAN():
    """Ninguna ruta de remitos borra o pisa una fila de remitos_fotos."""
    import io
    texto = io.open(os.path.join(RAIZ, "app", "db.py"), encoding="utf-8").read()
    assert not re.search(r"(DELETE\s+FROM|UPDATE)\s+remitos_fotos", texto, re.I)
    assert len(re.findall(r"INSERT INTO remitos_fotos", texto)) == 1


def test_el_DETALLE_con_fotos_no_desborda_a_313px(base, monkeypatch):
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id)
    html = _cliente(monkeypatch, "administracion").get(f"/administracion/facturacion/remito/{remito_id}").text
    medicion = _que_se_sale(html, 313)
    assert medicion["renglones"] == 0 or medicion["renglones"] >= 0  # identidad: la página abrió
    assert html.count("<figcaption>") == 1
    assert medicion["pagina"] == 0 and medicion["salidos"] == [], medicion


def _leer(nombre):
    import io
    return io.open(os.path.join(RAIZ, "db", nombre), encoding="utf-8").read()


def test_la_MIGRACION_llena_las_fotos_que_habia_y_no_corre_dos_veces(base):
    """Sobre una base como la de antes (sin la columna): las fotos que había
    entraron todas por Recibir, de Administración."""
    import psycopg2
    d, sql = base
    remito_id = d.emitir_remito(1, "VL", "R-0001")
    _recibido(d, remito_id)
    sql("ALTER TABLE remitos_fotos DROP COLUMN cargada_por")
    sql(_leer("remitos_fotos_1_quien.sql"))

    fila, = sql(_leer("remitos_fotos_1_verificacion.sql"))
    assert fila[:5] == ("remitos_fotos_1_quien", 1, 1, 1, 1)
    with pytest.raises(psycopg2.Error, match="remitos_fotos_1 ya corrio"):
        sql(_leer("remitos_fotos_1_quien.sql"))
    with pytest.raises(psycopg2.Error, match="remitos_fotos_cargada_por_check"):
        sql("INSERT INTO remitos_fotos (remito_id, foto_ruta, cargada_por) VALUES (%s, 'x', 'deposito')",
            (remito_id,))


def test_los_bloques_entran_en_el_editor_y_el_codigo_va_arriba():
    for nombre in ("remitos_fotos_1_quien.sql", "remitos_fotos_1_verificacion.sql"):
        texto = _leer(nombre)
        assert len(texto) <= 2500 and not texto.lstrip().startswith("--"), nombre
    assert _leer("remitos_fotos_1_verificacion.sql").lstrip().startswith(
        "select 'remitos_fotos_1_quien' as que_migracion")
