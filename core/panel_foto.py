"""LA FOTO DEL PANEL DE CONTROL (dueño, 09/10) — puro, sin base.

El tablero tardaba en abrir porque calculaba los nueve cuadros en cada
entrada. Ahora se calcula DOS VECES POR DÍA, a las 06:00 y a las 14:00 de
Argentina, y al entrar se muestra lo último calculado (`panel_fotos`). El
botón "Actualizar ahora" recalcula en el momento y deja la foto nueva para
todos. Los detalles de cada cuadro se siguen calculando al tocarlos.

LO DISPARA EL MISMO BUCLE QUE LAS ALERTAS (`_bucle_revision_casillas`, en
app/main.py): mira el reloj cada minuto. El criterio es "¿ya se intentó el
turno que corresponde?", no "¿son las 14:00 en punto?": si la aplicación
estuvo caída a las 14:00 y vuelve a las 14:20, lo calcula a las 14:20.

UN TURNO SE INTENTA UNA VEZ. Si falla, queda anotado (la base no deja dos
intentos del mismo turno) y el panel sigue mostrando la última foto buena
con el aviso "no se pudo actualizar a las 14:00". No se reintenta cada
minuto: un cálculo que se rompe cada minuto le come la base a todo lo demás.
Para eso está el botón.

LOS DATOS SE GUARDAN COMO JSON y vuelven con sus FECHAS: el tablero usa
`desde.month` y los rangos de cada cliente. Una fecha va como
{"__fecha__": "2026-10-01"} y vuelve como `date`.
"""
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

TURNOS = (time(6, 0), time(14, 0))


def turno_vigente(ahora: datetime) -> datetime:
    """El último turno que ya pasó: hoy a las 14:00, hoy a las 06:00 o ayer
    a las 14:00. `ahora` es hora de Argentina, con su zona."""
    candidatos = [datetime.combine(dia, hora, tzinfo=ahora.tzinfo)
                  for dia in (ahora.date() - timedelta(days=1), ahora.date()) for hora in TURNOS]
    return max(c for c in candidatos if c <= ahora)


def hay_que_calcular(turnos_intentados, ahora: datetime) -> bool:
    """True si el turno vigente todavía no se intentó (bien o mal)."""
    return turno_vigente(ahora) not in set(turnos_intentados)


def _a_json(valor):
    if isinstance(valor, datetime):
        return {"__instante__": valor.isoformat()}
    if isinstance(valor, date):
        return {"__fecha__": valor.isoformat()}
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (set, frozenset)):
        return sorted(valor)
    raise TypeError(f"la foto del panel no sabe guardar {type(valor).__name__}")


def _de_json(objeto: dict):
    if set(objeto) == {"__fecha__"}:
        return date.fromisoformat(objeto["__fecha__"])
    if set(objeto) == {"__instante__"}:
        return datetime.fromisoformat(objeto["__instante__"])
    return objeto


def a_texto(datos: dict) -> str:
    return json.dumps(datos, default=_a_json, ensure_ascii=False)


def de_texto(texto: str) -> dict:
    return json.loads(texto, object_hook=_de_json)


def cuando(instante: datetime, ahora: datetime) -> str:
    """"hoy a las 14:00", "ayer a las 14:00", "el 07/10 a las 06:00", en la
    hora de `ahora` (la base devuelve los instantes en UTC)."""
    instante = instante.astimezone(ahora.tzinfo)
    hora = instante.strftime("%H:%M")
    if instante.date() == ahora.date():
        return f"hoy a las {hora}"
    if instante.date() == ahora.date() - timedelta(days=1):
        return f"ayer a las {hora}"
    return f"el {instante.strftime('%d/%m')} a las {hora}"


def estado_de_la_foto(buena: dict | None, intentos: list[dict], ahora: datetime) -> dict:
    """Lo que el tablero dice arriba.

    `buena` es la última foto bien calculada ({calculada_el, datos}) o None;
    `intentos` son los últimos intentos AUTOMÁTICOS ({turno, calculada_el,
    ok}). Si el más nuevo de ellos falló y es posterior a la foto buena, se
    avisa con la hora de SU turno: "no se pudo actualizar a las 14:00".
    """
    fallo = None
    fallidos = [i for i in intentos if not i["ok"]
                and (buena is None or i["calculada_el"] > buena["calculada_el"])]
    if fallidos:
        ultimo = max(fallidos, key=lambda i: i["calculada_el"])
        fallo = f"No se pudo actualizar a las {ultimo['turno'].astimezone(ahora.tzinfo).strftime('%H:%M')}."
    return {
        "hay_foto": buena is not None,
        "actualizado": f"Actualizado {cuando(buena['calculada_el'], ahora)}" if buena else None,
        "fallo": fallo,
    }
