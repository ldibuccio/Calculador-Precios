# -*- coding: utf-8 -*-
"""EL BACKUP LO LANZA EL SISTEMA A LAS 03:47 (dueño, 09/10).

Los horarios de GitHub salían entre 6 y 8 horas tarde. El reloj de fondo del
sistema le pide a GitHub que corra el Backup a las 03:47, con una llave que
vence en un año, y Gerencia → Backups avisa un mes antes. Los dos horarios de
GitHub quedan de respaldo: se saltean si ese día ya hubo un backup bueno.

GitHub no se llama nunca de verdad: el cliente HTTP es de mentira y anota qué
se le pidió. La decisión del workflow (`hace_falta`) se corre en bash de
verdad, con un `gh` de mentira que contesta cuántos backups buenos hubo hoy.
"""
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core import backup_github as bg  # noqa: E402

AR = ZoneInfo("America/Argentina/Buenos_Aires")
TOKEN = "github_pat_EJEMPLO_de_mentira"


def _ar(dia, hora, minuto=0):
    return datetime(2026, 10, dia, hora, minuto, tzinfo=AR)


class _Respuesta:
    def __init__(self, status_code, vence=None):
        self.status_code = status_code
        self.headers = {"github-authentication-token-expiration": vence} if vence else {}


class _Cliente:
    """Un cliente HTTP de mentira: anota cada pedido y contesta lo que se le dice."""

    def __init__(self, status_code=204, vence=None, falla=None):
        self.pedidos, self.status_code, self.vence, self.falla = [], status_code, vence, falla

    def _pedido(self, metodo, url, **opciones):
        self.pedidos.append((metodo, url, opciones))
        if self.falla:
            raise self.falla
        return _Respuesta(self.status_code, self.vence)

    def post(self, url, **opciones):
        return self._pedido("POST", url, **opciones)

    def get(self, url, **opciones):
        return self._pedido("GET", url, **opciones)


# --- cuándo se lanza ------------------------------------------------------------

@pytest.mark.parametrize("ahora, toca", [
    (_ar(9, 3, 46), False), (_ar(9, 3, 47), True), (_ar(9, 6, 59), True), (_ar(9, 7, 0), False),
    (_ar(9, 14, 0), False),
])
def test_se_lanza_SOLO_en_la_ventana_de_las_0347_a_las_0700(ahora, toca):
    assert bg.toca_lanzar(ahora, None, None) is toca


def test_una_vez_por_dia_y_si_GitHub_no_contesto_reintenta_a_los_15_minutos():
    assert bg.toca_lanzar(_ar(9, 5), _ar(9, 3, 47), _ar(9, 3, 47).date()) is False      # ya se lanzó hoy
    assert bg.toca_lanzar(_ar(9, 4), _ar(8, 3, 47), _ar(8, 3, 47).date()) is True       # el rival: ayer
    assert bg.toca_lanzar(_ar(9, 4, 1), _ar(9, 3, 47), None) is False                   # falló hace 14 min
    assert bg.toca_lanzar(_ar(9, 4, 2), _ar(9, 3, 47), None) is True                    # falló hace 15 min


# --- lo que se le pide a GitHub ---------------------------------------------------

def test_LANZAR_pide_el_workflow_del_Backup_en_main_marcado_como_del_sistema():
    cliente = _Cliente(204)
    bg.lanzar(cliente, TOKEN)
    ((metodo, url, opciones),) = cliente.pedidos
    assert (metodo, url) == ("POST", "https://api.github.com/repos/ldibuccio/Calculador-Precios"
                                     "/actions/workflows/backup.yml/dispatches")
    assert opciones["json"] == {"ref": "main", "inputs": {"origen": "sistema"}}
    assert opciones["headers"]["Authorization"] == f"Bearer {TOKEN}"
    with pytest.raises(RuntimeError) as error:
        bg.lanzar(_Cliente(401), TOKEN)
    assert TOKEN not in str(error.value)            # la llave no va a parar a un log


def test_el_VENCIMIENTO_se_lee_del_encabezado_que_manda_GitHub():
    utc = timezone.utc
    assert bg.vencimiento(_Respuesta(200, "2027-10-09 03:47:00 UTC")) == datetime(2027, 10, 9, 3, 47, tzinfo=utc)
    assert bg.vencimiento(_Respuesta(200, "2027-10-09 03:47:00 -0300")) == datetime(2027, 10, 9, 6, 47, tzinfo=utc)
    assert bg.vencimiento(_Respuesta(200)) is None


def test_LEER_LA_LLAVE_distingue_sin_llave_no_anda_sin_respuesta_y_bien():
    assert bg.leer_la_llave(_Cliente(200), None) == {"estado": "sin_llave", "vence": None}
    assert bg.leer_la_llave(_Cliente(401), TOKEN)["estado"] == "no_anda"
    assert bg.leer_la_llave(_Cliente(falla=OSError("sin red")), TOKEN)["estado"] == "sin_respuesta"
    llave = bg.leer_la_llave(_Cliente(200, "2027-10-09 03:47:00 UTC"), TOKEN)
    assert llave == {"estado": "ok", "vence": datetime(2027, 10, 9, 3, 47, tzinfo=timezone.utc)}


def test_el_AVISO_salta_un_MES_antes_y_en_rojo_si_vencio_falta_o_no_anda():
    ahora = _ar(9, 12)
    def con(dias):
        return bg.aviso_de_la_llave({"estado": "ok", "vence": ahora + timedelta(days=dias)}, ahora)
    assert con(31)["nivel"] == "ok" and con(31)["texto"] == "La llave de GitHub anda hasta el 09/11/2026."
    assert con(30)["nivel"] == "amarillo" and con(30)["texto"].startswith("La llave de GitHub vence el 08/11/2026.")
    assert con(-1)["nivel"] == "rojo" and "venció" in con(-1)["texto"]
    for estado in ("sin_llave", "no_anda"):
        assert bg.aviso_de_la_llave({"estado": estado, "vence": None}, ahora)["nivel"] == "rojo"


def test_la_llave_SIN_VENCIMIENTO_de_hoy_anda_en_VERDE_y_no_avisa_nada():
    """La que cargó el dueño el 09/10 no vence: GitHub no manda el encabezado.
    El rival: la que no anda, que sin vencimiento igual es roja."""
    ahora = _ar(9, 12)
    llave = bg.leer_la_llave(_Cliente(200), TOKEN)
    assert llave == {"estado": "ok", "vence": None}
    assert bg.aviso_de_la_llave(llave, ahora) == {
        "nivel": "ok", "texto": "La llave de GitHub anda y no tiene vencimiento."}
    assert bg.aviso_de_la_llave({"estado": "no_anda", "vence": None}, ahora)["nivel"] == "rojo"


# --- el reloj de fondo ----------------------------------------------------------

def test_el_RELOJ_lanza_una_vez_y_sin_llave_no_hace_nada(monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "_LANZADOR_DE_BACKUP", {"lanzado_el": None, "ultimo_intento": None})
    cliente = _Cliente(204)
    monkeypatch.delenv(bg.TOKEN_ENV_VAR, raising=False)
    m._lanzar_backup_si_toca(_ar(9, 3, 47), cliente)
    assert cliente.pedidos == []
    monkeypatch.setenv(bg.TOKEN_ENV_VAR, TOKEN)
    for hora, minuto in ((3, 47), (3, 48), (3, 59), (4, 30), (6, 59)):
        m._lanzar_backup_si_toca(_ar(9, hora, minuto), cliente)
    assert len(cliente.pedidos) == 1
    m._lanzar_backup_si_toca(_ar(10, 3, 47), cliente)       # al otro día, otra vez
    assert len(cliente.pedidos) == 2


def test_si_GitHub_NO_contesta_el_reloj_reintenta_a_los_15_minutos(monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "_LANZADOR_DE_BACKUP", {"lanzado_el": None, "ultimo_intento": None})
    monkeypatch.setenv(bg.TOKEN_ENV_VAR, TOKEN)
    roto = _Cliente(500)
    with pytest.raises(RuntimeError):
        m._lanzar_backup_si_toca(_ar(9, 3, 47), roto)
    m._lanzar_backup_si_toca(_ar(9, 3, 50), roto)          # antes de los 15 minutos: no prueba
    bien = _Cliente(204)
    m._lanzar_backup_si_toca(_ar(9, 4, 2), bien)
    assert len(roto.pedidos) == 1 and len(bien.pedidos) == 1


def test_el_BUCLE_de_las_alertas_es_el_que_lanza_el_backup_con_su_tope():
    import ast
    arbol = ast.parse(open(os.path.join(RAIZ, "app", "main.py"), encoding="utf-8").read())
    (bucle,) = [n for n in ast.walk(arbol) if isinstance(n, ast.AsyncFunctionDef) and n.name == "_bucle_revision_casillas"]
    llamadas = [n for n in ast.walk(bucle) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "wait_for"]
    del_backup = [c for c in llamadas
                  if any(isinstance(a, ast.Name) and a.id == "_lanzar_backup_si_toca" for a in ast.walk(c.args[0]))]
    assert len(del_backup) == 1
    assert [k.value.id for k in del_backup[0].keywords if k.arg == "timeout"] == ["SEGUNDOS_TIMEOUT_LANZAR_BACKUP"]


# --- la pantalla ---------------------------------------------------------------------

def test_la_PANTALLA_de_Backups_dice_cuando_vence_la_llave(monkeypatch):
    import app.main as m
    from tests.test_administracion_reordenada import CLAVES, _cliente
    vence = (datetime.now(AR) + timedelta(days=20)).astimezone(timezone.utc)
    monkeypatch.setenv(bg.TOKEN_ENV_VAR, TOKEN)
    monkeypatch.setattr(m, "_LLAVE_DE_GITHUB", {"leida_el": None, "llave": None})
    cliente_github = _Cliente(200, vence.strftime("%Y-%m-%d %H:%M:%S UTC"))
    with patch.dict(os.environ, CLAVES), patch.object(m, "estado_de_los_backups", return_value=[]), \
            patch.object(m, "ultimas_corridas_de_backup", return_value=[]), \
            patch.object(m, "_cliente_de_github", return_value=_ConContexto(cliente_github)):
        pagina = _cliente(m, "gerencia").get("/gerencia/backups")
        otra = _cliente(m, "gerencia").get("/gerencia/backups")
    assert pagina.status_code == 200 and otra.status_code == 200
    dia = vence.astimezone(AR).strftime("%d/%m/%Y")
    assert f'<div class="llave amarillo" data-llave="amarillo">La llave de GitHub vence el {dia}.' in pagina.text
    assert len(cliente_github.pedidos) == 1        # la segunda entrada no le vuelve a preguntar a GitHub
    assert TOKEN not in pagina.text


class _ConContexto:
    def __init__(self, cliente):
        self.cliente = cliente

    def __enter__(self):
        return self.cliente

    def __exit__(self, *errores):
        return False


# --- el workflow -----------------------------------------------------------------------

def _decidir(evento, origen, buenos_hoy, tmp_path):
    """Corre el paso `decidir` de backup.yml en bash, con un `gh` de mentira."""
    texto = open(os.path.join(RAIZ, ".github", "workflows", "backup.yml"), encoding="utf-8").read()
    bloque = texto.split("  hace_falta:", 1)[1].split("\n  codigo:", 1)[0]
    guion = textwrap.dedent(bloque.split("run: |\n", 1)[1])
    guion = guion.replace("${{ github.repository }}", "ldibuccio/Calculador-Precios")
    assert "${{" not in guion
    gh = tmp_path / "gh"
    gh.write_text("#!/bin/bash\n" + ("exit 1\n" if buenos_hoy is None else f"echo {buenos_hoy}\n"))
    gh.chmod(0o755)
    salida = tmp_path / "salida"
    salida.write_text("")
    entorno = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "EVENTO": evento, "ORIGEN": origen,
               "GITHUB_OUTPUT": str(salida)}
    subprocess.run(["bash", "-e", "-c", guion], env=entorno, check=True, capture_output=True)
    return salida.read_text().strip()


@pytest.mark.parametrize("evento, origen, buenos_hoy, decide", [
    ("workflow_dispatch", "a_mano", 1, "correr=true"),      # a mano, siempre
    ("workflow_dispatch", "sistema", 0, "correr=true"),
    ("workflow_dispatch", "sistema", 1, "correr=false"),    # el segundo lanzamiento del sistema se saltea
    ("schedule", "", 1, "correr=false"),                    # los dos horarios de GitHub son respaldo
    ("schedule", "", 0, "correr=true"),
    ("schedule", "", None, "correr=true"),                  # si no se puede preguntar, se hace igual
])
def test_el_WORKFLOW_saltea_lo_del_sistema_y_los_horarios_si_hoy_ya_hubo_uno_bueno(
        evento, origen, buenos_hoy, decide, tmp_path):
    assert _decidir(evento, origen, buenos_hoy, tmp_path) == decide
