"""El filtro del Remanente por tipo de mercadería. Puro: no toca la base.

Lo usan la pantalla, el Excel y el PDF, y por eso vive acá y no en ninguno de
los tres: si cada uno decidiera por su cuenta qué es "suelta", el papel que se
imprime para bajar al depósito diría otra cosa que la pantalla.

Los tres tipos salen de la CLAVE de la porción, la misma de conteos_stock:

- **Suelta**: la mercadería como vino, sin ficha y que no es segunda.
- **Segunda**: `es_segunda`.
- **Procesada**: las cajas armadas a una ficha (lo que salió de reproceso).

"Todo" no es un cuarto tipo: es no filtrar. Por eso no está en TIPOS.
"""

TIPOS = (
    ("suelta", "Suelta"),
    ("segunda", "Segunda"),
    ("procesada", "Procesada"),
)
CLAVES = tuple(clave for clave, _ in TIPOS)
ROTULOS = dict(TIPOS)


def tipo_de_porcion(porcion: dict) -> str:
    """A cuál de los tres tipos pertenece una porción del Remanente."""
    if porcion.get("es_segunda"):
        return "segunda"
    if porcion.get("ficha_id") is not None:
        return "procesada"
    return "suelta"


def tipos_elegidos(valores) -> tuple:
    """Los tipos pedidos, en el orden fijo. Vacío quiere decir "Todo".

    "todo" no es un tipo: es no elegir ninguno. Si llega junto con un tipo
    —el que tildó Segunda sin destildar Todo, con el JS apagado— gana el
    tipo, porque es lo único que alguien marcó a propósito. Un valor que no
    es un tipo se ignora (la URL la puede escribir cualquiera), y si no queda
    ninguno es Todo — nunca una pantalla vacía por un parámetro mal escrito.
    """
    pedidos = {str(v).strip().lower() for v in (valores or [])}
    elegidos = tuple(clave for clave in CLAVES if clave in pedidos)
    # LOS TRES JUNTOS SON TODO, y se normalizan a Todo: son las mismas filas,
    # y así el título dice "Todo" en vez de una lista que no entra en el
    # encabezado del PDF.
    return () if len(elegidos) == len(CLAVES) else elegidos


def filtrar(porciones: list[dict], tipos: tuple) -> list[dict]:
    """Las porciones de esos tipos, en el orden en que vinieron. Sin tipos, todas."""
    if not tipos:
        return list(porciones)
    return [p for p in porciones if tipo_de_porcion(p) in tipos]


def secciones(porciones: list[dict], tipos: tuple) -> list[dict]:
    """Una sección por tipo elegido, con su total arriba: [{clave, rotulo, total, porciones}].

    Sin tipos (Todo) son los tres. Un tipo sin porciones sale igual, con
    total 0: si se pidió Segunda y no hay, "Segunda: 0 bultos en total" dice
    que se miró; una sección que desaparece no dice nada.

    El total va CON SIGNO: una segunda en −2 resta, igual que en el pool.
    """
    resultado = []
    for clave in (tipos or CLAVES):
        del_tipo = [p for p in porciones if tipo_de_porcion(p) == clave]
        resultado.append({
            "clave": clave,
            "rotulo": ROTULOS[clave],
            "total": round(sum(float(p["bultos"]) for p in del_tipo), 2),
            "porciones": del_tipo,
        })
    return resultado


def nombre_del_filtro(tipos: tuple) -> str:
    """Cómo se escribe el filtro en un título: "Todo", "Segunda", "Suelta + Segunda"."""
    if not tipos:
        return "Todo"
    return " + ".join(ROTULOS[clave] for clave in tipos)


def para_el_archivo(tipos: tuple) -> str:
    """El filtro en el nombre del archivo: "Todo", "Segunda", "Suelta_Segunda"."""
    return "_".join(ROTULOS[clave] for clave in tipos) if tipos else "Todo"
