"""Fletes (dueño, 05/10): armar el flete del día, repartir su costo y el mensaje.

Puro, sin base: lo que acá se decide se prueba sin Postgres y la base solo
guarda lo que sale de acá.

LAS REGLAS DEL DUEÑO
- Un flete es de UN fletero. Un camión va a UNA sola sucursal (05/10).
- "Armar flete" propone, por sucursal, la combinación de camiones más
  BARATA que lleve sus pallets, dentro de la flota del fletero: sin pasarse
  de cuántos tiene de cada tipo, contando los que ya están asignados ese día.
  Empate de precio: menos camiones.
- Si la flota no alcanza, se dice y se elige a mano.
- El precio del camión es el mismo vaya a la sucursal que vaya (05/10), y es
  el vigente el día del flete.
- La parte de Frutamax y la de Palmala salen por pallets.

LA FLOTA SE REPARTE ENTRE LAS SUCURSALES A LA VEZ y no de a una: si la
primera se quedara con el único camión grande porque le sale más barato, la
segunda podría quedarse sin flota aunque repartido de otra forma alcance.
Por eso la búsqueda es sobre el flete entero (lo más barato en total, y a
igual precio, menos camiones), y cada sucursal sigue teniendo su propia
combinación.
"""
from decimal import ROUND_HALF_UP, Decimal
from math import ceil

from core.tareas import DIAS_DE_LA_SEMANA


def _combinaciones(pallets: int, camiones: list[dict], tope: dict) -> list[tuple]:
    """Las combinaciones MÍNIMAS de camiones que llevan `pallets`: cada una es
    una tupla de cantidades (en el orden de `camiones`) a la que no se le
    puede sacar un camión sin que deje pallets afuera. `tope` dice cuántos de
    cada tipo se pueden usar (None = sin tope, para el armado a mano)."""
    resultado = []

    def recorrer(i, actual, capacidad):
        if i == len(camiones):
            if capacidad >= pallets and all(
                capacidad - camiones[j]["pallets"] < pallets for j, n in enumerate(actual) if n
            ):
                resultado.append(tuple(actual))
            return
        camion = camiones[i]
        maximo = ceil(pallets / camion["pallets"])
        if tope is not None:
            maximo = min(maximo, tope[camion["id"]])
        for n in range(maximo + 1):
            recorrer(i + 1, actual + [n], capacidad + n * camion["pallets"])

    recorrer(0, [], 0)
    return resultado


def armar_flete(sucursales: list[dict], camiones: list[dict], usados: dict | None = None) -> dict:
    """La propuesta del flete del día.

    sucursales: [{"codigo", "pallets"}] — las que llevan algo (pallets > 0);
      una en cero no lleva camión y no entra acá.
    camiones: [{"id", "nombre", "pallets", "cantidad", "precio"}] — los tipos
      del fletero, con el precio vigente ESE día (None = sin precio: no se
      puede proponer, y se dice).
    usados: {camion_id: cuántos} ya asignados ese día en otros fletes.

    Devuelve {"alcanza", "asignacion": {codigo: {camion_id: n}}, "costo",
    "camiones", "sin_precio": [nombres]}. Si la flota no alcanza, `alcanza`
    es False y la asignación es la más barata SIN tope de flota (para
    arrancar a elegir a mano), o vacía si ni así se puede.
    """
    usados = usados or {}
    con_precio = [c for c in camiones if c["precio"] is not None]
    sin_precio = [c["nombre"] for c in camiones if c["precio"] is None]
    vacio = {"alcanza": False, "asignacion": {}, "costo": None, "camiones": 0, "sin_precio": sin_precio}
    if not sucursales:
        return dict(vacio, alcanza=True, costo=Decimal("0"))
    if not con_precio:
        return vacio
    disponibles = {c["id"]: max(0, c["cantidad"] - usados.get(c["id"], 0)) for c in con_precio}

    def costo(combo):
        return sum((Decimal(str(c["precio"])) * n for c, n in zip(con_precio, combo)), Decimal("0"))

    def buscar(tope):
        # Programación dinámica sobre lo que queda de la flota: el estado es
        # cuántos quedan de cada tipo, y para cada uno se guarda lo mejor.
        inicial = tuple(tope[c["id"]] for c in con_precio) if tope is not None else None
        estados = {inicial: ((Decimal("0"), 0, ()), [])}
        for sucursal in sucursales:
            nuevos = {}
            for quedan, ((suma, cuantos, clave), elegidas) in estados.items():
                tope_aca = dict(zip((c["id"] for c in con_precio), quedan)) if quedan is not None else None
                for combo in _combinaciones(sucursal["pallets"], con_precio, tope_aca):
                    resto = tuple(q - n for q, n in zip(quedan, combo)) if quedan is not None else None
                    valor = (suma + costo(combo), cuantos + sum(combo), clave + combo)
                    if resto not in nuevos or valor < nuevos[resto][0]:
                        nuevos[resto] = (valor, elegidas + [combo])
            estados = nuevos
            if not estados:
                return None
        return min(estados.values(), key=lambda e: e[0])

    mejor = buscar(disponibles)
    alcanza = mejor is not None
    if mejor is None:
        mejor = buscar(None)
        if mejor is None:
            return vacio
    (total, cuantos, _), elegidas = mejor
    asignacion = {
        s["codigo"]: {c["id"]: n for c, n in zip(con_precio, combo) if n}
        for s, combo in zip(sucursales, elegidas)
    }
    return {"alcanza": alcanza, "asignacion": asignacion, "costo": total, "camiones": cuantos,
            "sin_precio": sin_precio}


def repartir(precio, pallets_frutamax: int, pallets_palmala: int) -> tuple[Decimal, Decimal]:
    """La parte de cada empresa de UN viaje, por pallets. Las dos suman el
    precio al centavo: Frutamax se redondea y Palmala es lo que queda."""
    precio = Decimal(str(precio)).quantize(Decimal("0.01"))
    total = pallets_frutamax + pallets_palmala
    if total <= 0:
        raise ValueError("Un viaje sin pallets no se reparte.")
    frutamax = (precio * pallets_frutamax / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return frutamax, precio - frutamax


def fecha_para_el_mensaje(fecha) -> str:
    """"lunes 06/10": el día de la semana lo lee el fletero sin calendario."""
    return f"{DIAS_DE_LA_SEMANA[fecha.weekday()]} {fecha.strftime('%d/%m')}"


def texto_whatsapp(fletero: str, fecha, sucursales: list[dict]) -> str:
    """El mensaje para el fletero (dueño, 05/10):

    "Hola Juan, para el lunes 06/10 necesito: Vicente López: 1 Grande +
    1 Mediano (18 pallets). Burzaco: 1 Mediano (8 pallets). Gracias."

    sucursales: [{"nombre", "pallets", "camiones": [(nombre, cantidad)]}] en
    el orden en que se cargaron. Los pallets son los de las dos empresas.
    """
    partes = []
    for s in sucursales:
        camiones = " + ".join(f"{n} {nombre}" for nombre, n in s["camiones"] if n)
        partes.append(f"{s['nombre']}: {camiones} ({s['pallets']} pallets).")
    return f"Hola {fletero}, para el {fecha_para_el_mensaje(fecha)} necesito: {' '.join(partes)} Gracias."
