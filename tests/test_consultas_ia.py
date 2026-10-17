"""CONSULTAS (dueño, 16/10): el chat de Gerencia con IA.

La IA se reemplaza por un cliente que contesta lo que contestaría la API (un
pedido de herramienta, después el texto): lo que se prueba es qué hace el
sistema con eso. El SQL corre de verdad contra Postgres.
"""
import os
import re
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.consultas_ia import (  # noqa: E402
    TABLAS_AFUERA,
    VUELTAS_MAXIMAS,
    ConsultaNoPermitida,
    consulta_de_lectura,
    costo_en_usd,
    esquema_resumido,
    leer_documento,
    preguntar,
)
from tests.test_panel_control_contra_la_base import _base_con, _cliente_gerencia, _sin_foto_del_panel  # noqa: E402,F401

ESQUEMA = open(os.path.join(RAIZ, "db", "esquema_completo.sql"), encoding="utf-8").read()


# --- LA IA DE MENTIRA ------------------------------------------------------------

def _uso(entrada=10_000, salida=100):
    return SimpleNamespace(input_tokens=entrada, output_tokens=salida, cache_creation_input_tokens=0,
                           cache_read_input_tokens=0)


def _texto(texto, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)], stop_reason=stop, usage=_uso(),
                           model="claude-sonnet-5-5")


def _pide(*herramientas):
    bloques = [SimpleNamespace(type="tool_use", id=f"t{n}", name=nombre, input=entrada)
               for n, (nombre, entrada) in enumerate(herramientas)]
    return SimpleNamespace(content=bloques, stop_reason="tool_use", usage=_uso(), model="claude-sonnet-5-5")


class ClienteDeMentira:
    """Contesta en orden lo que se le dio y anota lo que le mandaron."""

    def __init__(self, *respuestas):
        self.respuestas, self.pedidos = list(respuestas), []
        self.messages = self

    def create(self, **pedido):
        self.pedidos.append({**pedido, "messages": list(pedido["messages"])})
        return self.respuestas.pop(0)


# --- LO PURO -------------------------------------------------------------------

def test_solo_se_corre_UNA_LECTURA():
    assert consulta_de_lectura("  select 1;  ") == "select 1"
    assert consulta_de_lectura("-- cuántos\nWITH a AS (select 1) select * from a") == "WITH a AS (select 1) select * from a"
    for mala in ("insert into articulos (nombre) values ('x')", "select 1; delete from articulos", "", "  ;  ",
                 "update articulos set nombre = 'x'"):
        with pytest.raises(ConsultaNoPermitida):
            consulta_de_lectura(mala)


def test_el_ESQUEMA_que_ve_la_IA_es_el_del_sistema_SIN_las_tablas_de_afuera():
    resumido = esquema_resumido(ESQUEMA)
    encontradas = set(re.findall(r"^(\w+):", resumido, re.M))
    decididas = set(re.findall(r"^create table (\w+) \(", ESQUEMA, re.M)) - set(TABLAS_AFUERA)
    assert encontradas == decididas                                  # las dos direcciones
    assert set(TABLAS_AFUERA) & set(re.findall(r"^create table (\w+) \(", ESQUEMA, re.M))  # el testigo: están
    cheques = next(r for r in resumido.splitlines() if r.startswith("cheques:"))
    assert "importe numeric(14,2)" in cheques and "constraint" not in cheques
    assert "cheques_con_estado" in resumido.splitlines()[-1]          # las vistas, en un renglón


def test_el_COSTO_con_los_precios_de_Sonnet_5_5_y_un_modelo_desconocido_al_mas_caro():
    assert costo_en_usd("claude-sonnet-5-5", 1_000_000, 100_000, 0, 0) == pytest.approx(2.0 + 1.0)
    assert costo_en_usd("claude-sonnet-5-5", 0, 0, 1_000_000, 1_000_000) == pytest.approx(2.0 * 1.25 + 0.20)
    assert costo_en_usd("un-modelo-nuevo", 0, 1_000_000) == pytest.approx(20.0)  # el de Opus 5.5


def test_un_DOCUMENTO_se_lee_por_su_nombre_y_uno_que_no_esta_da_la_lista():
    assert "guía R" in leer_documento("stock_y_guias_r")
    assert leer_documento("../../CLAUDE").startswith("No existe ese documento. Los que hay:")


def test_la_VUELTA_corre_las_herramientas_devuelve_los_errores_y_cobra_todo():
    cliente = ClienteDeMentira(
        _pide(("correr_sql", {"sql": "select 1", "para_que": "probar"}),
              ("correr_sql", {"sql": "select mal", "para_que": "fallar"})),
        _pide(("leer_documento", {"nombre": "cheques"})),
        _texto("Son 3 cajas."))
    corridas = []

    def correr(sql):
        corridas.append(sql)
        if "mal" in sql:
            raise ValueError("columna inexistente")
        return {"columnas": ["n"], "filas": [[1]], "cortada": False, "ms": 5}

    resultado = preguntar(cliente, "¿cuántas?", [{"pregunta": "antes", "respuesta": "hola"}], sistema="S",
                          correr_sql=correr, leer_doc=lambda n: f"doc {n}", nombre_del_modelo="claude-sonnet-5-5")
    assert resultado.texto == "Son 3 cajas." and resultado.error is None
    assert corridas == ["select 1", "select mal"]
    assert [c.get("error") for c in resultado.consultas] == [None, "columna inexistente"]
    assert resultado.documentos == ["cheques"]
    assert resultado.costo_usd == pytest.approx(3 * costo_en_usd("claude-sonnet-5-5", 10_000, 100))
    primero = cliente.pedidos[0]["messages"]
    assert [m["role"] for m in primero] == ["user", "assistant", "user"] and primero[-1]["content"] == "¿cuántas?"
    resultados = cliente.pedidos[1]["messages"][-1]["content"]
    assert [(r["tool_use_id"], r["is_error"]) for r in resultados] == [("t0", False), ("t1", True)]
    assert cliente.pedidos[1]["messages"][-2]["role"] == "assistant"          # el turno de la IA, entero


def test_si_NO_LLEGA_a_una_respuesta_corta_y_lo_dice_y_una_NEGATIVA_es_un_error():
    cliente = ClienteDeMentira(*[_pide(("leer_documento", {"nombre": "cheques"}))] * (VUELTAS_MAXIMAS + 1))
    resultado = preguntar(cliente, "?", [], sistema="S", correr_sql=None, leer_doc=lambda n: "x",
                          nombre_del_modelo="claude-sonnet-5-5")
    assert resultado.error.startswith("La IA no llegó a una respuesta") and len(cliente.pedidos) == VUELTAS_MAXIMAS + 1
    negada = preguntar(ClienteDeMentira(_texto("", stop="refusal")), "?", [], sistema="S", correr_sql=None,
                       leer_doc=None, nombre_del_modelo="claude-sonnet-5-5")
    assert negada.error == "La IA no quiso contestar esa pregunta." and negada.costo_usd > 0


# --- CONTRA LA BASE ----------------------------------------------------------------

SIEMBRA = """
insert into articulos (id, nombre, grupo) overriding system value
  values (1, 'EJEMPLO Tomate', 'hortaliza'), (2, 'EJEMPLO Berenjena', 'hortaliza');
"""


@pytest.fixture(scope="module")
def m():
    url = _base_con(SIEMBRA)
    with patch.dict(os.environ, {"DATABASE_URL": url, "CONSULTAS_IA_DATABASE_URL": url,
                                 "ANTHROPIC_API_KEY": "sk-de-mentira"}):
        import app.main as modulo
        yield modulo


def test_la_LECTURA_corta_las_filas_y_la_base_NO_DEJA_ESCRIBIR(m):
    import app.db as d
    datos = d.correr_consulta_de_solo_lectura("select id, nombre from articulos order by id", 1)
    assert (datos["columnas"], datos["filas"], datos["cortada"]) == (["id", "nombre"], [[1, "EJEMPLO Tomate"]], True)
    with pytest.raises(d.ConsultaIaNoSePuede, match="read-only"):
        d.correr_consulta_de_solo_lectura("with x as (delete from articulos returning id) select * from x", 10)
    assert d.correr_consulta_de_solo_lectura("select count(*) from articulos", 10)["filas"] == [[2]]


def test_PREGUNTAR_corre_el_SQL_de_verdad_lo_anota_con_su_costo_y_el_TOPE_frena(m):
    cliente_http, claves = _cliente_gerencia(m)
    ia = ClienteDeMentira(_pide(("correr_sql", {"sql": "select count(*) as cuantos from articulos",
                                                "para_que": "contar artículos"})),
                          _texto("Hay 2 artículos."))
    with patch.dict(os.environ, claves), patch("anthropic.Anthropic", return_value=ia):
        pagina = cliente_http.get("/gerencia/consultas")
        respuesta = cliente_http.post("/gerencia/consultas/preguntar", json={"pregunta": "¿Cuántos artículos hay?"})
    assert pagina.status_code == 200 and 'href="/gerencia/consultas/registro"' in pagina.text
    datos = respuesta.json()
    assert respuesta.status_code == 200, datos
    assert datos["respuesta"] == "Hay 2 artículos." and datos["error"] is None
    assert [(c["para_que"], c["columnas"], c["filas"]) for c in datos["consultas"]] == [
        ("contar artículos", ["cuantos"], [[2]])]
    assert "EJEMPLO" not in ia.pedidos[0]["system"][0]["text"]                   # el esquema, no los datos
    import app.db as d
    (anotada,) = d.ultimas_preguntas_de_consultas()
    assert (anotada["pregunta"], anotada["quien"], anotada["sector"]) == ("¿Cuántos artículos hay?", "Gerencia", "gerencia")
    assert float(anotada["costo_usd"]) == pytest.approx(round(2 * costo_en_usd("claude-sonnet-5-5", 10_000, 100), 4))
    assert anotada["consultas"][0]["sql"] == "select count(*) as cuantos from articulos"
    assert datos["gasto"]["gastado"] == pytest.approx(float(anotada["costo_usd"]))
    # Con el tope por debajo de lo gastado, no se le pregunta más a la IA.
    with patch.dict(os.environ, claves), patch("anthropic.Anthropic", side_effect=AssertionError("llamó a la IA")):
        cero = cliente_http.post("/gerencia/consultas/tope", data={"tope": "0,001"}, follow_redirects=False)
        assert "error=" in cero.headers["location"] and d.tope_de_consultas() == 100   # a centavos es cero: no entra
        cliente_http.post("/gerencia/consultas/tope", data={"tope": "0,01"})
        frenada = cliente_http.post("/gerencia/consultas/preguntar", json={"pregunta": "¿Y ahora?"}).json()
        registro = cliente_http.get("/gerencia/consultas/registro").text
    assert frenada["tope_lleno"] is True and "tope del mes" in frenada["error"]
    assert len(d.ultimas_preguntas_de_consultas()) == 1
    assert registro.count('data-pregunta="') == 1 and "¿Cuántos artículos hay?" in registro


def test_sin_la_CLAVE_de_Gerencia_no_se_pregunta_y_el_hub_tiene_el_boton(m):
    from fastapi.testclient import TestClient
    cliente_http, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves), patch("anthropic.Anthropic", side_effect=AssertionError("llamó a la IA")):
        sin_clave = TestClient(m.app).post("/gerencia/consultas/preguntar", json={"pregunta": "hola"})
    assert sin_clave.status_code == 401
    with patch.dict(os.environ, claves):
        hub = cliente_http.get("/gerencia").text
    assert hub.count('href="/gerencia/consultas"') == 1
