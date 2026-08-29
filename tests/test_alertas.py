"""Las alertas guardadas: el registro, la frescura y la garantía de que ninguna quede invisible."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.alertas import (
    HORAS_RECALCULO,
    HORAS_VENCIMIENTO,
    DefinicionAlerta,
    frescura,
    hay_que_recalcular,
    modulos_conocidos,
    modulos_inexistentes,
    normalizar_conteo,
    para_mostrar,
    recalcular,
    unir,
)
from app.main import ALERTAS, app

ARGENTINA = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 8, 27, 12, 0, tzinfo=ARGENTINA)


def _definicion(codigo="prueba", modulos=(), contar=None):
    return DefinicionAlerta(
        codigo=codigo,
        titulo="Título de prueba",
        url="/compras",
        texto_link="Ver",
        modulos=modulos,
        contar=contar or (lambda: {"casos": 0, "mas_viejo": None}),
    )


def _fila(codigo="prueba", casos=0, calculada_el=AHORA, error=None, mas_viejo=None):
    return {"codigo": codigo, "casos": casos, "mas_viejo": mas_viejo,
            "calculada_el": calculada_el, "duracion_ms": 1, "error": error}


# ---------------------------------------------------------------------------
# El registro real
# ---------------------------------------------------------------------------

def test_los_codigos_del_registro_no_se_repiten():
    """Dos alertas con el mismo código se pisarían la fila en la base: una desaparecería."""
    codigos = [a.codigo for a in ALERTAS]
    assert len(codigos) == len(set(codigos))


def test_cada_alerta_del_registro_tiene_lo_que_hace_falta():
    for alerta in ALERTAS:
        assert alerta.codigo and alerta.titulo and alerta.texto_link, alerta.codigo
        assert callable(alerta.contar), alerta.codigo
        assert alerta.url, alerta.codigo


def test_ninguna_alerta_apunta_a_un_modulo_que_no_existe():
    """El chequeo NO tiene una lista escrita a mano: los módulos válidos salen de las rutas.

    Por eso agregar un módulo nuevo no le rompe este test a nadie — que era
    justo lo que no queríamos que pasara.
    """
    sueltas = modulos_inexistentes(ALERTAS, [ruta.path for ruta in app.routes])
    assert sueltas == [], f"Alertas apuntando a módulos inexistentes: {sueltas}"


# ---------------------------------------------------------------------------
# Los módulos salen de las rutas, no de una lista
# ---------------------------------------------------------------------------

def test_los_modulos_salen_del_primer_segmento_de_las_rutas():
    conocidos = modulos_conocidos(["/compras/pendientes", "/deposito", "/", "/fichas/{id}/editar"])
    assert conocidos == {"compras", "deposito", "fichas"}


def test_un_modulo_mal_escrito_se_detecta():
    sueltas = modulos_inexistentes([_definicion(modulos=("comrpas",))], ["/compras"])
    assert sueltas == [{"codigo": "prueba", "modulo": "comrpas"}]


def test_detectar_modulos_inexistentes_nunca_explota():
    """Avisa, jamás traba: un módulo a medio construir no puede tirar abajo la pantalla."""
    assert modulos_inexistentes([_definicion(modulos=("todavia_no_existe",))], []) != []


# ---------------------------------------------------------------------------
# LA GARANTÍA: una alerta mal apuntada NO queda invisible
# ---------------------------------------------------------------------------

def test_una_alerta_con_el_modulo_mal_escrito_igual_se_ve_en_auditoria():
    """Auditoría no filtra por módulo. El error de tipeo cuesta el banner, no la alerta."""
    definiciones = [_definicion(codigo="con_typo", modulos=("comrpas",))]
    estado = [_fila(codigo="con_typo", casos=3)]

    en_auditoria = para_mostrar(definiciones, estado)
    assert [a["codigo"] for a in en_auditoria] == ["con_typo"]

    en_banner = para_mostrar(definiciones, estado, modulo="compras")
    assert en_banner == []


def test_una_alerta_sin_calcular_no_se_muestra_como_cero():
    """Mostrar cero sin haber mirado sería decir que está todo bien. Sale como desconocida."""
    unidas = unir([_definicion()], estado=[])
    assert unidas[0]["casos"] is None
    assert para_mostrar([_definicion()], estado=[]) != []


def test_una_alerta_que_fallo_se_muestra_aunque_su_ultimo_conteo_diera_cero():
    """Que no se haya podido calcular ES la noticia."""
    mostradas = para_mostrar([_definicion()], [_fila(casos=0, error="se cayó la consulta")])
    assert len(mostradas) == 1
    assert mostradas[0]["error"] == "se cayó la consulta"


def test_una_alerta_en_cero_y_sin_error_no_aparece():
    assert para_mostrar([_definicion()], [_fila(casos=0)]) == []


def test_las_filas_viejas_de_la_foto_se_ignoran():
    """Una alerta que se borró del registro deja su fila: no tiene que aparecer."""
    unidas = unir([_definicion(codigo="vive")], [_fila(codigo="ya_no_existe", casos=9)])
    assert [u["codigo"] for u in unidas] == ["vive"]


# ---------------------------------------------------------------------------
# La forma de los conteos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("crudo, esperado", [
    ({"casos": 3, "mas_viejo": date(2026, 8, 1)}, {"casos": 3, "mas_viejo": date(2026, 8, 1)}),
    (5, {"casos": 5, "mas_viejo": None}),
    (0, {"casos": 0, "mas_viejo": None}),
    ({"casos": None, "mas_viejo": None}, {"casos": 0, "mas_viejo": None}),
])
def test_normalizar_conteo(crudo, esperado):
    """11 funciones devuelven el diccionario y 3 devuelven un entero: el registro empareja."""
    assert normalizar_conteo(crudo) == esperado


# ---------------------------------------------------------------------------
# La frescura se calcula contra el reloj, no se lee de la foto
# ---------------------------------------------------------------------------

def test_sin_datos_la_frescura_es_vencida():
    estado = frescura([], AHORA)
    assert estado["hay_datos"] is False and estado["vencida"] is True


def test_recien_calculada_no_esta_vencida():
    estado = frescura([_fila(calculada_el=AHORA - timedelta(hours=2))], AHORA)
    assert estado["vencida"] is False
    assert "hace 2 horas" in estado["texto"]


def test_pasado_el_vencimiento_se_marca_vencida():
    vieja = AHORA - timedelta(hours=HORAS_VENCIMIENTO + 1)
    assert frescura([_fila(calculada_el=vieja)], AHORA)["vencida"] is True


def test_justo_en_el_umbral_todavia_no_esta_vencida():
    """Una corrida perdida no asusta; dos sí. El borde no puede gritar de más."""
    justo = AHORA - timedelta(hours=HORAS_VENCIMIENTO)
    assert frescura([_fila(calculada_el=justo)], AHORA)["vencida"] is False


def test_la_frescura_mira_la_mas_nueva():
    estado = frescura(
        [_fila(codigo="a", calculada_el=AHORA - timedelta(days=3)),
         _fila(codigo="b", calculada_el=AHORA - timedelta(minutes=5))],
        AHORA,
    )
    assert estado["vencida"] is False


# ---------------------------------------------------------------------------
# Cuándo toca recalcular
# ---------------------------------------------------------------------------

def test_sin_datos_hay_que_recalcular():
    assert hay_que_recalcular([], AHORA) is True


def test_recien_calculadas_no_hay_que_recalcular():
    assert hay_que_recalcular([_fila(calculada_el=AHORA - timedelta(hours=1))], AHORA) is False


def test_pasadas_las_horas_de_recalculo_hay_que_recalcular():
    vieja = AHORA - timedelta(hours=HORAS_RECALCULO + 1)
    assert hay_que_recalcular([_fila(calculada_el=vieja)], AHORA) is True


def test_el_vencimiento_cae_entre_una_y_dos_corridas():
    """Una corrida perdida no dispara el aviso, dos sí.

    No alcanza con que el vencimiento sea MAYOR que el recálculo: si es
    más del doble hacen falta tres corridas perdidas para que el banner
    avise, y la regla se rompe en silencio al cambiar solo uno de los dos
    números.
    """
    assert HORAS_RECALCULO < HORAS_VENCIMIENTO <= 2 * HORAS_RECALCULO


# ---------------------------------------------------------------------------
# La recalculación
# ---------------------------------------------------------------------------

def test_una_alerta_que_falla_no_frena_a_las_demas_ni_se_guarda_en_cero():
    """La que falla queda con su valor viejo y su error anotado. Nunca en cero."""
    guardadas = []

    def _guardar(codigo, casos=None, mas_viejo=None, duracion_ms=None, error=None):
        guardadas.append({"codigo": codigo, "casos": casos, "error": error})

    def _explota():
        raise RuntimeError("se cayó la base")

    definiciones = [
        _definicion(codigo="rota", contar=_explota),
        _definicion(codigo="sana", contar=lambda: {"casos": 2, "mas_viejo": None}),
    ]
    with patch("app.alertas.candado_alertas") as candado, \
         patch("app.alertas.guardar_estado_alerta", _guardar):
        candado.return_value.__enter__.return_value = True
        resumen = recalcular(definiciones)

    assert resumen == {"corrio": True, "ok": 1, "fallaron": 1}
    rota = next(g for g in guardadas if g["codigo"] == "rota")
    assert rota["casos"] is None and "se cayó la base" in rota["error"]
    sana = next(g for g in guardadas if g["codigo"] == "sana")
    assert sana["casos"] == 2 and sana["error"] is None


def test_si_el_candado_esta_tomado_no_recalcula():
    """El bucle de fondo y el botón pueden coincidir: no se duplica el trabajo."""
    with patch("app.alertas.candado_alertas") as candado, \
         patch("app.alertas.guardar_estado_alerta") as guardar:
        candado.return_value.__enter__.return_value = False
        resumen = recalcular([_definicion()])
    assert resumen["corrio"] is False
    guardar.assert_not_called()


# ---------------------------------------------------------------------------
# El link que se arma con el dato
# ---------------------------------------------------------------------------

def test_la_url_puede_calcularse_con_el_dato():
    definicion = DefinicionAlerta(
        codigo="con_url_calculada",
        titulo="T",
        url=lambda datos: f"/logistica/consultar?desde={datos['mas_viejo']}",
        texto_link="Ver",
        contar=lambda: {"casos": 1, "mas_viejo": date(2026, 8, 20)},
    )
    unidas = unir([definicion], [_fila(codigo="con_url_calculada", casos=1, mas_viejo=date(2026, 8, 20))])
    assert unidas[0]["url"] == "/logistica/consultar?desde=2026-08-20"


def test_si_el_link_no_se_puede_armar_la_alerta_igual_se_ve():
    """Un link roto no puede tapar la alerta."""
    def _explota(datos):
        raise ValueError("no se pudo")

    definicion = DefinicionAlerta(codigo="x", titulo="T", url=_explota, texto_link="Ver",
                                 contar=lambda: {"casos": 1})
    unidas = unir([definicion], [_fila(codigo="x", casos=1)])
    assert unidas[0]["url"] == "/auditoria"
