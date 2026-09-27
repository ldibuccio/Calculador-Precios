"""Cuándo dos nombres de proveedor son el MISMO nombre escrito distinto.

Salió del 27/09: FRUTAMAX (N09P39) y FRUTAMAX S.R.L. (N09P41) eran el mismo
proveedor cargado dos veces, porque el alta por código no tiene cómo saber que
dos puestos son de la misma empresa. El alta a mano compara el nombre nuevo
contra los que ya están con esta regla, y si coincide avisa con un modal —no
bloquea: dos proveedores pueden llamarse igual de verdad—.

La regla es del dueño: sin puntos, sin espacios y sin "SRL" o "SA". Se le
suman las tildes y las mayúsculas, que es lo mismo que ya pliega
`normalizar_texto` para todo lo demás, y "SAS" y "SH", que son la misma clase
de sufijo.
"""

import re

from core.matcheo_comanda import normalizar_texto

# Las formas societarias que no distinguen a un proveedor de otro. Se comparan
# como PALABRA entera, después de sacar los puntos: "S.R.L." queda "srl" y se
# va, pero "SANDRA" no pierde su "sa".
SUFIJOS_SOCIETARIOS = frozenset({"srl", "sa", "sas", "sh"})


def nombre_de_proveedor_plegado(nombre: str | None) -> str:
    """El nombre sin tildes, mayúsculas, puntos, espacios ni forma societaria.

    "FRUTAMAX S.R.L." y "Frutamax" dan lo mismo. Un nombre que es SOLO un
    sufijo ("S.A.") da vacío, y el vacío no coincide con nada: lo decide
    `nombres_parecidos`, no esta función.
    """
    texto = normalizar_texto(nombre).replace(".", "")
    palabras = [p for p in re.split(r"[^0-9a-z]+", texto) if p and p not in SUFIJOS_SOCIETARIOS]
    return "".join(palabras)


def nombres_parecidos(nombre: str, proveedores: list[dict]) -> list[dict]:
    """Los proveedores cuyo nombre, plegado, es igual al plegado de `nombre`.

    Un plegado vacío no matchea: dos nombres que no dicen nada no son el
    mismo proveedor.
    """
    buscado = nombre_de_proveedor_plegado(nombre)
    if not buscado:
        return []
    return [p for p in proveedores if nombre_de_proveedor_plegado(p["nombre"]) == buscado]
