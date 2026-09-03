"""El mecanismo de las alertas guardadas: calcularlas cada tanto y leerlas de una foto.

POR QUÉ NO SE CALCULAN EN VIVO
Las alertas no viven solo en Auditoría: cada módulo va a tener su banner con
las suyas, y van a ser muchas. Calculando en vivo, cada pantalla con banner
recalcularía todo — el costo crecería con alertas x pantallas. Guardadas, cada
pantalla cuesta UNA consulta, tenga 15 alertas o 100.

QUÉ VIVE DÓNDE, Y POR QUÉ IMPORTA
La base guarda SOLO lo que se calcula: código, casos, el caso más viejo, cuándo
se calculó y el error si lo hubo. El título, la URL y a qué módulos pertenece
cada alerta viven en el REGISTRO, en app/main.py. Por eso agregar una alerta
nueva no toca la base nunca: es una entrada en la lista y su consulta.

LA FRESCURA SE CALCULA EN VIVO, NUNCA SE LEE DE LA FOTO
Si la pantalla leyera de la foto cuán fresca es la foto, un cálculo muerto
haría invisible su propia muerte. Es la misma trampa que el latido de la
casilla (el punto ciego del 25/08): "no hay problemas" y "no se está
calculando" no pueden verse iguales. Por eso el que muestra compara
calculada_el contra el reloj, cada vez.

EL VENCIMIENTO ES MÁS LARGO QUE EL RECÁLCULO, A PROPÓSITO
Se recalcula cada 6 horas y se marca vencida a las 9: una corrida perdida no
dispara el aviso, dos sí. Mismo criterio que la alerta de casilla, que tampoco
grita al primer fallo — una alerta que grita por nada se deja de mirar en una
semana.

El vencimiento acompaña al recálculo y no es un número suelto: si se cambia
uno hay que mover el otro, o la regla de "una perdida no, dos sí" se rompe en
silencio. Con recálculo 6 y vencimiento 18 harían falta TRES corridas perdidas
para que el banner avise que la foto está vieja.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from app.db import (
    candado_alertas,
    guardar_estado_alerta,
    listar_estado_alertas,
)

logger = logging.getLogger(__name__)

# Cada cuánto se recalcula, y a partir de cuándo la foto se considera vencida.
# El vencimiento va entre una y dos corridas: una perdida no avisa, dos sí.
HORAS_RECALCULO = 6
HORAS_VENCIMIENTO = 9


@dataclass(frozen=True)
class DefinicionAlerta:
    """Una alerta del registro. Agregar una es sumar una de estas y escribir su consulta.

    modulos: en qué banners aparece ADEMÁS de Auditoría. Auditoría muestra
    TODAS siempre, así que no se lista acá — si hubiera que listarla, sería un
    ítem más para olvidarse, y una alerta olvidada es una alerta invisible.
    Puede ir a varios: modulos=("compras", "deposito").

    titulo_corto: el mismo título para el BANNER, que es una cinta que corre
    en 390px: ahí un título largo se lee a medias y el número queda para el
    final. Vacío = se usa el título entero, que es lo normal. Auditoría
    muestra SIEMPRE el largo: ahí sobra lugar y la aclaración sirve.
    """

    codigo: str
    titulo: str
    url: object          # str, o un callable(datos) -> str para las que arman el link con el dato
    texto_link: str
    contar: Callable
    modulos: tuple = field(default_factory=tuple)
    titulo_corto: str = ""


def normalizar_conteo(resultado) -> dict:
    """Lleva a {casos, mas_viejo} lo que devuelva una función de conteo.

    Las funciones de conteo no tienen forma uniforme: 11 devuelven el
    diccionario y 3 devuelven un entero pelado. En vez de ir a tocar las tres
    (y arriesgar a quien las use en otro lado), el registro normaliza acá.
    """
    if isinstance(resultado, dict):
        return {"casos": int(resultado.get("casos") or 0), "mas_viejo": resultado.get("mas_viejo")}
    return {"casos": int(resultado or 0), "mas_viejo": None}


def modulos_conocidos(rutas) -> set:
    """Los módulos que el sistema tiene HOY, derivados de sus propias rutas.

    Recibe los paths registrados (app.routes) y devuelve sus primeros
    segmentos: "/compras/pendientes" -> "compras".

    A propósito NO hay una lista de módulos escrita a mano: se desactualiza, y
    después miente. Creás un módulo con su ruta y queda válido solo; lo borrás
    y deja de existir solo. Es permisiva ("salud" también entra): el objetivo
    es cazar el error de tipeo, no curar una taxonomía.
    """
    modulos = set()
    for ruta in rutas:
        partes = [p for p in str(ruta).split("/") if p and not p.startswith("{")]
        if partes:
            modulos.add(partes[0])
    return modulos


def modulos_inexistentes(definiciones, rutas) -> list:
    """Las alertas que apuntan a un módulo que no existe, con su detalle.

    NUNCA lanza excepción: avisa. Un módulo a medio construir no puede tirar
    abajo la pantalla — mismo criterio que el cruce de primera de reproceso,
    que es "aviso, jamás traba". Y como Auditoría no filtra por módulo, la
    alerta mal apuntada se sigue viendo igual: el error de tipeo cuesta el
    banner, no la alerta.
    """
    conocidos = modulos_conocidos(rutas)
    sueltas = []
    for definicion in definiciones:
        for modulo in definicion.modulos:
            if modulo not in conocidos:
                sueltas.append({"codigo": definicion.codigo, "modulo": modulo})
    return sueltas


def recalcular(definiciones) -> dict:
    """Corre todas las alertas y guarda la foto. Devuelve el resumen de la corrida.

    El candado (advisory lock) evita que el bucle y el botón de "recalcular
    ahora" corran a la vez. Se toma sobre una conexión que queda abierta toda
    la corrida: al cerrarse, Postgres lo suelta solo, así que un corte no deja
    el candado trabado.

    Si la consulta de una alerta falla, su fila NO se actualiza: queda con su
    valor y su fecha viejos, y la pantalla la muestra vencida. Nunca en cero —
    un problema que desaparece porque la consulta se rompió es la peor falla
    posible en un sistema de alertas.
    """
    with candado_alertas() as tomado:
        if not tomado:
            logger.info("Las alertas ya se están recalculando en otro lado — esta corrida se saltea")
            return {"corrio": False, "ok": 0, "fallaron": 0}

        ok = 0
        fallaron = 0
        for definicion in definiciones:
            arranque = time.perf_counter()
            try:
                conteo = normalizar_conteo(definicion.contar())
            except Exception as error:
                fallaron += 1
                logger.exception("La alerta %s falló al calcularse", definicion.codigo)
                try:
                    guardar_estado_alerta(definicion.codigo, error=str(error)[:500])
                except Exception:
                    logger.exception("Tampoco se pudo registrar el error de la alerta %s", definicion.codigo)
                continue
            duracion_ms = int((time.perf_counter() - arranque) * 1000)
            try:
                guardar_estado_alerta(
                    definicion.codigo,
                    casos=conteo["casos"],
                    mas_viejo=conteo["mas_viejo"],
                    duracion_ms=duracion_ms,
                )
                ok += 1
            except Exception:
                fallaron += 1
                logger.exception("No se pudo guardar el estado de la alerta %s", definicion.codigo)

        logger.info("Alertas recalculadas: %s ok, %s con problemas", ok, fallaron)
        return {"corrio": True, "ok": ok, "fallaron": fallaron}


def _edad_en_texto(calculada_el, ahora) -> str:
    """"hace 20 minutos", "hace 3 horas", "ayer a las 14:30", "el 25/08 a las 12:00".

    Las cuatro formas tienen que caer bien detrás de un verbo — la pantalla las
    usa como "Calculadas ..." y como "se calcularon ...". Por eso ninguna
    arranca con un sustantivo suelto: "son de el 25/08" se lee mal, y esa
    frase se ve justo cuando algo anda mal y hay que entenderla rápido.
    """
    diferencia = ahora - calculada_el
    minutos = int(diferencia.total_seconds() // 60)
    if minutos < 1:
        return "recién"
    if minutos < 60:
        return f"hace {minutos} minuto{'s' if minutos != 1 else ''}"
    horas = minutos // 60
    if calculada_el.date() == ahora.date():
        return f"hace {horas} hora{'s' if horas != 1 else ''}"
    if calculada_el.date() == (ahora.date() - timedelta(days=1)):
        return f"ayer a las {calculada_el.strftime('%H:%M')}"
    return f"el {calculada_el.strftime('%d/%m a las %H:%M')}"


def frescura(estado, ahora) -> dict:
    """Cuán vieja es la foto, calculado CONTRA EL RELOJ y no leído de la foto.

    Devuelve:
      hay_datos  — False si nunca se calcularon (la tabla está vacía)
      vencida    — True si la más nueva pasó las HORAS_VENCIMIENTO
      texto      — cómo se muestra ("hace 3 horas", "ayer a las 14:30")
    """
    fechas = [fila["calculada_el"] for fila in estado if fila.get("calculada_el")]
    if not fechas:
        return {"hay_datos": False, "vencida": True, "texto": None, "mas_nueva": None}
    mas_nueva = max(fechas)
    return {
        "hay_datos": True,
        "vencida": (ahora - mas_nueva) > timedelta(hours=HORAS_VENCIMIENTO),
        "texto": _edad_en_texto(mas_nueva, ahora),
        "mas_nueva": mas_nueva,
    }


def hay_que_recalcular(estado, ahora) -> bool:
    """True si la foto más nueva pasó las HORAS_RECALCULO, o si nunca se calculó.

    El criterio es "cuán vieja es", no "¿ya corrí el turno de las 6?": así se
    autocorrige después de una caída, sin depender de que el reloj coincida
    con nada.
    """
    fechas = [fila["calculada_el"] for fila in estado if fila.get("calculada_el")]
    if not fechas:
        return True
    return (ahora - max(fechas)) > timedelta(hours=HORAS_RECALCULO)


def unir(definiciones, estado) -> list:
    """Cruza el registro (título, url) con la foto (casos, cuándo), por código.

    Una alerta del registro SIN fila en la foto sale con casos=None: es "sin
    calcular todavía", que no es lo mismo que cero. Mostrarla en cero sería
    decir que está todo bien sin haber mirado.

    Las filas de la foto cuyo código ya no está en el registro se ignoran: son
    alertas que se borraron y su fila quedó de resto.
    """
    por_codigo = {fila["codigo"]: fila for fila in estado}
    unidas = []
    for definicion in definiciones:
        fila = por_codigo.get(definicion.codigo)
        datos = {"casos": fila["casos"] if fila else None,
                 "mas_viejo": fila["mas_viejo"] if fila else None}
        # La URL puede depender del dato (ej. los retiros viejos linkean al
        # rango de fechas del caso más viejo). Si falla, se cae al módulo:
        # un link mal armado no puede tapar la alerta.
        try:
            url = definicion.url(datos) if callable(definicion.url) else definicion.url
        except Exception:
            logger.exception("No se pudo armar el link de la alerta %s", definicion.codigo)
            url = "/auditoria"
        unidas.append({
            "titulo_corto": definicion.titulo_corto or definicion.titulo,
            "codigo": definicion.codigo,
            "titulo": definicion.titulo,
            "url": url,
            "texto_link": definicion.texto_link,
            "modulos": definicion.modulos,
            "casos": fila["casos"] if fila else None,
            "mas_viejo": fila["mas_viejo"] if fila else None,
            "calculada_el": fila["calculada_el"] if fila else None,
            "error": fila["error"] if fila else None,
        })
    return unidas


def para_mostrar(definiciones, estado, modulo=None) -> list:
    """Las alertas que hay que mostrar: las que tienen casos, más las que no se pudieron calcular.

    Si modulo es None (Auditoría) salen TODAS las del registro. Con un módulo,
    solo las que lo declaran — pero Auditoría nunca filtra, y eso es lo que
    garantiza que una alerta mal apuntada no quede invisible.

    Una alerta con error sale aunque su último conteo diera cero: que no se
    haya podido calcular ES la noticia.
    """
    unidas = unir(definiciones, estado)
    if modulo is not None:
        unidas = [a for a in unidas if modulo in a["modulos"]]
    return [a for a in unidas if a["casos"] is None or a["casos"] > 0 or a["error"]]
