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


def test_para_mostrar_DEVUELVE_EN_EL_ORDEN_DEL_REGISTRO():
    """El orden del registro es el de las pantallas, y eso es un contrato, no una casualidad.

    La pantalla de Alertas se arma sola recorriendo el registro: por eso el
    orden de los bloques no se escribe en la plantilla —ahí habría que
    enumerar las alertas a mano y se rompería el día que aparezca una nueva—
    sino que sale de acá.

    Si alguien ordenara por casos, por título o alfabéticamente en `unir` o en
    `para_mostrar`, los bloques se moverían solos y nada avisaría. El registro
    de verdad tiene veintiuna entradas y este test usa cuatro a propósito:
    fija el MECANISMO, no un orden concreto que envejezca al agregar alertas.
    """
    definiciones = [_definicion(codigo=c, modulos=("compras",)) for c in ("d", "b", "c", "a")]
    estado = [{"codigo": c, "casos": n, "mas_viejo": None, "calculada_el": None, "error": None}
              for c, n in (("d", 1), ("b", 9), ("c", 5), ("a", 3))]

    # Los casos están desordenados a propósito (1, 9, 5, 3) y los códigos
    # también: un `sort` por cualquiera de los dos daría otra cosa que "dbca".
    assert [a["codigo"] for a in para_mostrar(definiciones, estado)] == ["d", "b", "c", "a"]
    assert [a["codigo"] for a in para_mostrar(definiciones, estado, "compras")] == ["d", "b", "c", "a"]
    assert [a["codigo"] for a in unir(definiciones, estado)] == ["d", "b", "c", "a"]


def test_en_COMPRAS_la_alerta_de_kilos_va_ANTES_que_la_de_bultos():
    """Pedido del comprador el 12/09: la de kilos es la que mira primero.

    Va sobre el registro REAL y no sobre un fixture, porque lo que se está
    fijando es la decisión —este bloque arriba de aquél— y un fixture propio
    la afirmaría sobre datos inventados.

    El de arriba cuida el mecanismo; éste cuida la decisión. Se rompen por
    motivos distintos: aquél si alguien ordena en `unir`, éste si alguien
    reacomoda el registro por prolijidad o agrupando por módulo, que es
    exactamente lo que se ve inofensivo.
    """
    codigos = [definicion.codigo for definicion in ALERTAS]
    assert codigos.index("kilos_faltantes") < codigos.index("cajones_faltantes")


# Las que HOY mandan a un sector contra la puerta de otro. NO es una lista de
# casos aprobados: es deuda conocida, anotada para que una CUARTA no entre en
# silencio. Cada una tiene que decidirse, y la de compras_sin_precio la
# produjo la puerta de Compras del 12/09 (antes /compras no pedía nada).
DEUDA_ALERTAS_CONTRA_PUERTA_AJENA = {
    # LA ÚNICA QUE QUEDA, y no la arregla `destinos_por_sector`: Comercial la
    # ve, el link cae en /compras/pendientes, y en Comercial NO HAY a dónde
    # mandarla — la acción (cargar el precio de compra) vive en Compras y
    # punto. El mecanismo da dónde poner un destino; no inventa uno.
    #
    # Se cierra de una de dos formas, y las dos son decisión de producto:
    # darle `detallar` para que Comercial vea CUÁLES son desde su propia
    # pantalla de alertas (que todavía no existe), o sacarle el sector. Hoy
    # recibe un número que no puede abrir, que es peor que no tener la
    # alerta.
    ("compras_sin_precio", "comercial"),
}


def test_NINGUNA_ALERTA_manda_a_un_sector_contra_la_puerta_de_otro():
    """Una alerta que se muestra en un sector y linkea a la zona de OTRO deja
    a quien la sigue contra una clave que no tiene.

    Pasó el 12/09 con `unidades_que_difieren`: se muestra en Compras y en
    Comercial, y apuntaba a Artículos — que ese mismo día se mudó bajo
    /compras. El usuario de Comercial seguía el link de su propia alerta y
    pegaba contra una puerta ajena. Se reapuntó a Fichas, que es de su sector
    y no tiene puerta.

    LA CAUSA DE FONDO es que `DefinicionAlerta` tiene UNA url para todos los
    sectores que la muestran, así que con dos sectores y una acción que vive
    en uno solo, el otro siempre queda del lado de afuera. Este test no la
    arregla: hace que no crezca.

    Se mide contra las puertas REALES del registro, no contra una lista de
    prefijos escrita acá: el día que un sector gane clave, sus alertas
    entran solas a este control — que es exactamente como apareció el caso
    que lo originó.
    """
    from app.main import ALERTAS, PUERTAS_POR_SECTOR

    # LA URL SALE DE `unir`, que es quien la resuelve en producción, y no de
    # repetir acá la regla de `destinos_por_sector`: copiada, el día que la
    # resolución cambie este test seguiría midiendo la vieja y diría que no
    # hay choques cuando los hay. Es la regla escrita dos veces.
    estado = [{"codigo": d.codigo, "casos": 1, "mas_viejo": None,
               "calculada_el": None, "error": None} for d in ALERTAS]
    ofensores = set()
    for definicion in ALERTAS:
        for modulo in definicion.modulos:
            (alerta,) = [a for a in unir([definicion], estado, modulo)]
            for puerta in PUERTAS_POR_SECTOR.values():
                if alerta["url"].startswith(puerta.prefijo) and puerta.sector != modulo:
                    ofensores.add((definicion.codigo, modulo))

    nuevas = ofensores - DEUDA_ALERTAS_CONTRA_PUERTA_AJENA
    assert nuevas == set(), f"alertas nuevas que mandan a una puerta ajena: {nuevas}"

    # Y al revés: una que se arregle sale de la deuda, para que la lista no
    # quede protegiendo algo que ya no pasa (corolario 22).
    arregladas = DEUDA_ALERTAS_CONTRA_PUERTA_AJENA - ofensores
    assert arregladas == set(), f"ya no chocan, sacalas de la deuda: {arregladas}"


def test_el_destino_por_sector_manda_y_ARRASTRA_SU_TEXTO():
    """Cada sector a donde puede actuar, con el link diciendo a dónde va.

    LAS DOS MITADES JUNTAS es el punto: si la url fuera por sector y el texto
    no, el comprador vería "Ver en Guías R" y caería en Compras sin precio.
    Por eso `destinos_por_sector` guarda el par y no hay un segundo
    diccionario en paralelo — separados se despegan y nadie se entera.

    Auditoría (modulo None) no es un sector: usa el de siempre.
    """
    definicion = DefinicionAlerta(
        codigo="prueba", titulo="Título de prueba", url="/el-de-siempre",
        texto_link="Ver el de siempre", contar=lambda: 1,
        modulos=("compras", "comercial"),
        destinos_por_sector={"comercial": ("/el-de-comercial", "Ver el de Comercial")},
    )
    estado = [{"codigo": "prueba", "casos": 1, "mas_viejo": None,
               "calculada_el": None, "error": None}]

    (auditoria,) = unir([definicion], estado)
    assert (auditoria["url"], auditoria["texto_link"]) == ("/el-de-siempre", "Ver el de siempre")

    # El sector SIN entrada propia sigue con el de siempre.
    (compras,) = unir([definicion], estado, "compras")
    assert (compras["url"], compras["texto_link"]) == ("/el-de-siempre", "Ver el de siempre")

    # Y el que la tiene se lleva LAS DOS MITADES.
    (comercial,) = unir([definicion], estado, "comercial")
    assert (comercial["url"], comercial["texto_link"]) == ("/el-de-comercial", "Ver el de Comercial")
