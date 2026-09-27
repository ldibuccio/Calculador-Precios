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

Y el 27/09 no alcanzó: DON LAZZARO (L02P42) y PRODUCTOS DON LAZZARO (L02P44)
eran otro par, y el plegado no los igualaba porque "PRODUCTOS" no es una forma
societaria. Desde ahí se sacan también las palabras que no nombran a nadie
—PRODUCTOS, HNOS, HERMANOS, CIA— y se avisa cuando un nombre plegado CONTIENE
al otro, que es la forma de "FRUTAMAX" contra "FRUTAMAX SUR".
"""

import re

from core.matcheo_comanda import normalizar_texto

# Las palabras que no distinguen a un proveedor de otro: las formas
# societarias y las de relleno ("Productos", "Hnos.", "y Cía."). Se comparan
# como PALABRA entera, después de sacar los puntos: "S.R.L." queda "srl" y se
# va, pero "SANDRA" no pierde su "sa" ni "CIAMPI" su "cia".
PALABRAS_QUE_NO_DISTINGUEN = frozenset({
    "srl", "sa", "sas", "sh",
    "productos", "hnos", "hermanos", "cia",
})

# Contener se mira solo si el plegado más corto tiene al menos esto. Con menos,
# "SUR" o "LUZ" estarían adentro de medio padrón y el modal saltaría en cada
# alta: un aviso que dispara siempre se aprende a pasar de largo.
MINIMO_PARA_CONTENER = 4


def nombre_de_proveedor_plegado(nombre: str | None) -> str:
    """El nombre sin tildes, mayúsculas, puntos, espacios ni forma societaria.

    "FRUTAMAX S.R.L." y "Frutamax" dan lo mismo. Un nombre que es SOLO un
    sufijo ("S.A.") da vacío, y el vacío no coincide con nada: lo decide
    `nombres_parecidos`, no esta función.
    """
    texto = normalizar_texto(nombre).replace(".", "")
    palabras = [p for p in re.split(r"[^0-9a-z]+", texto) if p and p not in PALABRAS_QUE_NO_DISTINGUEN]
    return "".join(palabras)


def son_parecidos(uno: str | None, otro: str | None) -> bool:
    """Iguales plegados, o uno adentro del otro si el más corto no es chico.

    Un plegado vacío no matchea nada: dos nombres que no dicen nada no son el
    mismo proveedor.
    """
    a, b = nombre_de_proveedor_plegado(uno), nombre_de_proveedor_plegado(otro)
    if not a or not b:
        return False
    if a == b:
        return True
    corto, largo = sorted((a, b), key=len)
    return len(corto) >= MINIMO_PARA_CONTENER and corto in largo


def nombres_parecidos(nombre: str, proveedores: list[dict]) -> list[dict]:
    """Los proveedores cuyo nombre es parecido a `nombre` (`son_parecidos`)."""
    return [p for p in proveedores if son_parecidos(nombre, p["nombre"])]
