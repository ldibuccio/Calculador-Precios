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
    CortarLaPregunta,
    consulta_de_lectura,
    costo_en_usd,
    esquema_resumido,
    falla_de_conexion_en_criollo,
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
    """Contesta en orden lo que se le dio (un error se levanta) y anota lo
    que le mandaron."""

    def __init__(self, *respuestas):
        self.respuestas, self.pedidos = list(respuestas), []
        self.messages = self
        self.models = SimpleNamespace(retrieve=lambda modelo, **_: SimpleNamespace(id=modelo))

    def create(self, **pedido):
        self.pedidos.append({**pedido, "messages": list(pedido["messages"])})
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def _error_de_la_api(clase, codigo, mensaje="algo"):
    import httpx
    respuesta = httpx.Response(codigo, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return clase(mensaje, response=respuesta, body=None)


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


def test_lo_que_la_IA_NO_PUEDE_ARREGLAR_corta_la_pregunta_y_se_cobra_lo_usado():
    def no_conecta(sql):
        raise CortarLaPregunta("No conecta con la base: la contraseña no es la de consultas_ia")
    cliente = ClienteDeMentira(_pide(("correr_sql", {"sql": "select 1", "para_que": "probar"})), _texto("no llega"))
    cortada = preguntar(cliente, "?", [], sistema="S", correr_sql=no_conecta, leer_doc=None,
                        nombre_del_modelo="claude-sonnet-5-5")
    assert cortada.error.startswith("No conecta con la base") and len(cliente.pedidos) == 1   # no reintenta
    assert cortada.consultas[0]["error"] == cortada.error and cortada.costo_usd > 0
    # La API que falla: con traducción termina con el motivo; sin ella, sigue de largo.
    caida = preguntar(ClienteDeMentira(KeyError("x")), "?", [], sistema="S", correr_sql=None, leer_doc=None,
                      nombre_del_modelo="claude-sonnet-5-5",
                      explicar_falla_de_la_api=lambda e: "la IA se cayó" if isinstance(e, KeyError) else None)
    assert caida.error == "la IA se cayó"
    with pytest.raises(KeyError):
        preguntar(ClienteDeMentira(KeyError("x")), "?", [], sistema="S", correr_sql=None, leer_doc=None,
                  nombre_del_modelo="claude-sonnet-5-5", explicar_falla_de_la_api=lambda e: None)


def test_una_pregunta_que_TARDA_DEMASIADO_no_pide_otra_vuelta():
    horas = iter([0, 100, 250])                      # el arranque, la vuelta 1 y la vuelta 2
    cliente = ClienteDeMentira(*[_pide(("leer_documento", {"nombre": "cheques"}))] * 3)
    lenta = preguntar(cliente, "?", [], sistema="S", correr_sql=None, leer_doc=lambda n: "x",
                      nombre_del_modelo="claude-sonnet-5-5", segundos_maximos=240, reloj=lambda: next(horas))
    assert lenta.error.startswith("La respuesta tardó demasiado") and len(cliente.pedidos) == 2


def test_la_FALLA_DE_CONEXION_se_dice_en_criollo():
    casos = {
        'FATAL:  password authentication failed for user "consultas_ia"': "la contraseña",
        "FATAL:  Tenant or user not found": "el usuario está mal",
        'could not translate host name "aws-9-x.pooler.supabase.com" to address': "host",
        "connection to server timed out": "no contesta",
        'invalid dsn: missing "=" after "x"': "mal escrita",
        "otra cosa": "no aceptó la conexión",
    }
    for mensaje, esperado in casos.items():
        dicho = falla_de_conexion_en_criollo(mensaje)
        assert esperado in dicho and "CONSULTAS_IA_DATABASE_URL" in dicho, (mensaje, dicho)


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


def _preguntar(cliente_http, ia, pregunta, claves, **variables):
    """POST de la pregunta (la IA piensa en la tarea de fondo, que el
    cliente de prueba corre antes de volver) y el estado que ve la pantalla."""
    with patch.dict(os.environ, {**claves, **variables}), patch("anthropic.Anthropic", return_value=ia):
        llegada = cliente_http.post("/gerencia/consultas/preguntar", json={"pregunta": pregunta})
        datos = llegada.json()
        if datos.get("estado") == "pensando":
            assert llegada.status_code == 202
            datos = cliente_http.get(f"/gerencia/consultas/pregunta/{datos['id']}").json()
    return datos


def test_PREGUNTAR_corre_el_SQL_de_verdad_lo_anota_con_su_costo_y_el_TOPE_frena(m):
    cliente_http, claves = _cliente_gerencia(m)
    ia = ClienteDeMentira(_pide(("correr_sql", {"sql": "select count(*) as cuantos from articulos",
                                                "para_que": "contar artículos"})),
                          _texto("Hay 2 artículos."))
    with patch.dict(os.environ, claves):
        pagina = cliente_http.get("/gerencia/consultas")
    datos = _preguntar(cliente_http, ia, "¿Cuántos artículos hay?", claves)
    assert pagina.status_code == 200 and 'href="/gerencia/consultas/registro"' in pagina.text
    assert datos["estado"] == "lista" and datos["respuesta"] == "Hay 2 artículos." and datos["error"] is None
    assert [(c["para_que"], c["columnas"], c["filas"]) for c in datos["consultas"]] == [
        ("contar artículos", ["cuantos"], [[2]])]
    assert "EJEMPLO" not in ia.pedidos[0]["system"][0]["text"]                   # el esquema, no los datos
    import app.db as d
    (anotada,) = [p for p in d.ultimas_preguntas_de_consultas() if p["pregunta"] == "¿Cuántos artículos hay?"]
    assert (anotada["quien"], anotada["sector"]) == ("Gerencia", "gerencia")
    assert float(anotada["costo_usd"]) == pytest.approx(round(2 * costo_en_usd("claude-sonnet-5-5", 10_000, 100), 4))
    assert anotada["consultas"][0]["sql"] == "select count(*) as cuantos from articulos"
    assert datos["gasto"]["gastado"] == pytest.approx(d.gasto_de_consultas_desde(m._hoy_argentina().replace(day=1)))
    # Con el tope por debajo de lo gastado, no se le pregunta más a la IA, pero queda anotada.
    antes = len(d.ultimas_preguntas_de_consultas())
    with patch.dict(os.environ, claves), patch("anthropic.Anthropic", side_effect=AssertionError("llamó a la IA")):
        cero = cliente_http.post("/gerencia/consultas/tope", data={"tope": "0,001"}, follow_redirects=False)
        assert "error=" in cero.headers["location"] and d.tope_de_consultas() == 100   # a centavos es cero: no entra
        cliente_http.post("/gerencia/consultas/tope", data={"tope": "0,01"})
        frenada = cliente_http.post("/gerencia/consultas/preguntar", json={"pregunta": "¿Y ahora?"}).json()
        registro = cliente_http.get("/gerencia/consultas/registro").text
        cliente_http.post("/gerencia/consultas/tope", data={"tope": "100"})
    assert frenada["tope_lleno"] is True and "tope del mes" in frenada["error"]
    assert len(d.ultimas_preguntas_de_consultas()) == antes + 1
    assert d.ultimas_preguntas_de_consultas()[0]["error"] == frenada["error"]
    assert registro.count('data-pregunta="') == antes + 1 and "¿Cuántos artículos hay?" in registro


def test_TODA_PREGUNTA_queda_anotada_aunque_falle_con_el_motivo_en_criollo(m):
    import anthropic

    import app.db as d
    cliente_http, claves = _cliente_gerencia(m)
    pide_sql = _pide(("correr_sql", {"sql": "select 1", "para_que": "probar"}))
    url_mala = d.os.environ["DATABASE_URL"].replace("://", "://nadie_x:mala@", 1).split("@", 1)
    url_mala = "postgresql://nadie_x:mala@" + url_mala[1].split("@")[-1]
    casos = [
        # (lo que pasa, la IA, variables, lo que tiene que decir, ¿cobra?)
        ("la base no conecta", ClienteDeMentira(pide_sql, _texto("no llega")), {"CONSULTAS_IA_DATABASE_URL": url_mala},
         "No conecta con la base", True),
        ("la cadena está mal escrita", ClienteDeMentira(pide_sql, _texto("no llega")),
         {"CONSULTAS_IA_DATABASE_URL": "consultas_ia:Secreta123@host"}, "mal escrita", True),
        ("la cadena trae la clave", ClienteDeMentira(pide_sql, _texto("no llega")),
         {"CONSULTAS_IA_DATABASE_URL": "postgresql://consultas_ia.x:Secreta123@127.0.0.1:1/x?sslmod=1"},
         "mal escrita", True),
        ("falta la variable", None, {"CONSULTAS_IA_DATABASE_URL": ""}, "CONSULTAS_IA_DATABASE_URL", False),
        ("falta la clave", None, {"ANTHROPIC_API_KEY": ""}, "ANTHROPIC_API_KEY", False),
        ("la clave no sirve", ClienteDeMentira(_error_de_la_api(anthropic.AuthenticationError, 401)), {},
         "revisá ANTHROPIC_API_KEY", False),
        ("sin saldo", ClienteDeMentira(_error_de_la_api(anthropic.BadRequestError, 400,
                                                        "Your credit balance is too low")), {}, "sin saldo", False),
        ("la IA tarda", ClienteDeMentira(anthropic.APITimeoutError(request=None)), {}, "tardó demasiado", False),
        ("el sistema rompe", ClienteDeMentira(KeyError("columnas")), {}, "Falló el sistema (KeyError", False),
    ]
    for caso, ia, variables, esperado, cobra in casos:
        pregunta = f"¿Qué pasa si {caso}?"
        datos = _preguntar(cliente_http, ia or ClienteDeMentira(), pregunta, claves, **variables)
        anotadas = [p for p in d.ultimas_preguntas_de_consultas() if p["pregunta"] == pregunta]
        assert len(anotadas) == 1, caso
        assert datos["estado"] == "lista" and esperado in datos["error"] and anotadas[0]["error"] == datos["error"], (
            caso, datos)
        assert (float(anotadas[0]["costo_usd"]) > 0) is cobra, caso
        if ia is not None and caso != "el sistema rompe":
            assert len(ia.pedidos) == 1, caso                                       # no reintenta
    # La contraseña de la cadena no queda en el registro ni en la pantalla.
    assert [p["pregunta"] for p in d.ultimas_preguntas_de_consultas() if "Secreta123" in str(p)] == []
    assert sum("mal escrita" in (p["error"] or "") for p in d.ultimas_preguntas_de_consultas()) == 2   # testigo
    assert "password authentication failed" in [p for p in d.ultimas_preguntas_de_consultas()
                                                if p["pregunta"] == "¿Qué pasa si la base no conecta?"][0]["error"]


def test_una_pregunta_que_quedo_PENSANDO_de_mas_se_da_por_cortada(m):
    import app.db as d
    cliente_http, claves = _cliente_gerencia(m)
    id_pregunta = d.guardar_pregunta_de_consultas({"sector": "gerencia", "quien": "Gerencia",
                                                   "conversacion": "00000000-0000-0000-0000-000000000001",
                                                   "pregunta": "¿Quedó colgada?", "modelo": "claude-sonnet-5-5"})
    with patch.dict(os.environ, claves):
        recien = cliente_http.get(f"/gerencia/consultas/pregunta/{id_pregunta}").json()
        with d.obtener_conexion() as conexion, conexion.cursor() as cursor:
            cursor.execute("UPDATE consultas_ia_preguntas SET creado_en = now() - interval '7 minutes' WHERE id = %s",
                           (id_pregunta,))
        vieja = cliente_http.get(f"/gerencia/consultas/pregunta/{id_pregunta}").json()
    assert recien == {"id": id_pregunta, "estado": "pensando"}
    assert vieja["estado"] == "lista" and "se cortó" in vieja["error"]
    assert d.pregunta_de_consultas(id_pregunta)["error"] == vieja["error"]


def test_PROBAR_CONEXION_dice_cual_de_las_dos_falla(m):
    import anthropic

    import app.db as d
    cliente_http, claves = _cliente_gerencia(m)
    ia_que_anda = ClienteDeMentira()

    def probar(ia=ia_que_anda, **variables):
        with patch.dict(os.environ, {**claves, **variables}), patch("anthropic.Anthropic", return_value=ia):
            return cliente_http.post("/gerencia/consultas/probar").json()

    import psycopg2
    with psycopg2.connect(d.os.environ["DATABASE_URL"]) as conexion, conexion.cursor() as cursor:
        cursor.execute("select current_user")
        usuario_de_prueba = cursor.fetchone()[0]
    anda = probar()
    assert anda["ia"] == {"ok": True, "texto": "La IA contesta (modelo claude-sonnet-5-5)."}
    # La base de prueba entra con su usuario, no con consultas_ia: eso se dice.
    assert anda["base"]["ok"] is False and f"como {usuario_de_prueba}" in anda["base"]["texto"]
    with patch("app.main.correr_consulta_de_solo_lectura",
               return_value={"columnas": ["usuario"], "filas": [["consultas_ia"]], "cortada": False, "ms": 1}):
        assert probar()["base"] == {"ok": True, "texto": "Conecta con la base como consultas_ia (solo lectura)."}
    sin_base = probar(CONSULTAS_IA_DATABASE_URL="postgresql://nadie_x:mala@127.0.0.1:1/x")
    assert sin_base["base"]["ok"] is False and "No conecta con la base" in sin_base["base"]["texto"]
    clave_mala = ClienteDeMentira()
    clave_mala.models = SimpleNamespace(retrieve=lambda *a, **k: (_ for _ in ()).throw(
        _error_de_la_api(anthropic.AuthenticationError, 401)))
    assert probar(clave_mala)["ia"] == {"ok": False, "texto": "La clave de la IA no sirve (revisá ANTHROPIC_API_KEY "
                                                              "en Railway)."}
    assert "Falta la clave de la IA" in probar(ANTHROPIC_API_KEY="")["ia"]["texto"]
    with patch.dict(os.environ, claves):
        assert cliente_http.get("/gerencia/consultas").text.count("<button type=\"button\" data-probar-boton>Probar conexión</button>") == 1


def test_sin_la_CLAVE_de_Gerencia_no_se_pregunta_y_el_hub_tiene_el_boton(m):
    from fastapi.testclient import TestClient
    cliente_http, claves = _cliente_gerencia(m)
    with patch.dict(os.environ, claves), patch("anthropic.Anthropic", side_effect=AssertionError("llamó a la IA")):
        sin_clave = TestClient(m.app).post("/gerencia/consultas/preguntar", json={"pregunta": "hola"})
    assert sin_clave.status_code == 401
    with patch.dict(os.environ, claves):
        hub = cliente_http.get("/gerencia").text
    assert hub.count('href="/gerencia/consultas"') == 1


def test_la_PANTALLA_pregunta_por_partes_dice_el_motivo_real_y_prueba_la_conexion(m):
    """La pantalla de verdad, en el navegador, contra la app (cada pedido del
    navegador lo contesta el cliente de prueba)."""
    pytest.importorskip("playwright", reason="el ida y vuelta lo hace el JS de la pantalla")
    from playwright.sync_api import sync_playwright
    from scripts.medir_layout import CHROMIUM
    cliente_http, claves = _cliente_gerencia(m)
    ia = ClienteDeMentira(_pide(("correr_sql", {"sql": "select count(*) as cuantos from articulos",
                                                "para_que": "contar artículos"})), _texto("Hay 2 artículos."))
    pedidos, romper = [], {"preguntar": False}

    def a_la_app(ruta):
        pedido = ruta.request
        camino = pedido.url.split("prueba.local", 1)[1]
        pedidos.append(f"{pedido.method} {camino}")
        if romper["preguntar"] and camino == "/gerencia/consultas/preguntar":
            return ruta.fulfill(status=500, content_type="text/plain", body="Internal Server Error")
        respuesta = cliente_http.request(pedido.method, camino, content=pedido.post_data_buffer,
                                         headers={"content-type": pedido.headers.get("content-type", "")})
        ruta.fulfill(status=respuesta.status_code, content_type=respuesta.headers.get("content-type"),
                     body=respuesta.content)

    with patch.dict(os.environ, claves), patch("anthropic.Anthropic", return_value=ia), sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            pagina = navegador.new_page(viewport={"width": 313, "height": 800})
            pagina.route("http://prueba.local/**", a_la_app)
            pagina.goto("http://prueba.local/gerencia/consultas")
            pagina.fill("#pregunta", "¿Cuántos artículos hay?")
            pagina.click("[data-enviar]")
            pagina.wait_for_selector(".mensaje.respuesta:not(.esperando)", timeout=15000)
            respuesta = pagina.inner_text(".mensaje.respuesta")
            romper["preguntar"] = True
            pagina.fill("#pregunta", "¿Y si el servidor se cae?")
            pagina.click("[data-enviar]")
            pagina.wait_for_selector(".mensaje.fallo", timeout=15000)
            caida = pagina.inner_text(".mensaje.fallo")
            pagina.click("[data-probar-boton]")
            pagina.wait_for_selector("[data-probar-resultado] p:nth-of-type(2)", timeout=15000)
            prueba = [pagina.inner_text(p) for p in ("[data-probar-resultado] p:nth-of-type(1)",
                                                     "[data-probar-resultado] p:nth-of-type(2)")]
            desborde = pagina.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        finally:
            navegador.close()
    assert respuesta.startswith("Hay 2 artículos.") and "Cómo lo calculé" in respuesta
    estados = [p for p in pedidos if p.startswith("GET /gerencia/consultas/pregunta/")]
    assert pedidos.index(estados[0]) > pedidos.index("POST /gerencia/consultas/preguntar")   # preguntó por el id
    assert caida == "El servidor falló (código 500). Mirá el registro o avisale a quien lo programa."
    assert prueba[0].startswith("✗ Base: Conecta, pero como") and prueba[1] == (
        "✓ IA: La IA contesta (modelo claude-sonnet-5-5).")
    assert desborde == 0
