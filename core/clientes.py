"""Catálogo de clientes y sus envases.

Cada cliente tiene su propio descuento y utilidad objetivo, y sus propios
envases con su propio costo. Reemplaza a las antiguas constantes globales
únicas (DESCUENTO_ESTANDAR, UTILIDAD_ESTANDAR, COSTO_ENVASE_CHICO,
COSTO_ENVASE_GRANDE) que antes vivían en motor_costeo.py.
"""

CLIENTES = {
    "Día": {"descuento": 0.23, "utilidad_objetivo": 0.20},
}

ENVASES = {
    "Caja Chica Día": {"cliente": "Día", "costo": 650},
    "Caja Grande Día": {"cliente": "Día", "costo": 1600},
}


def buscar_cliente(nombre: str) -> dict:
    """Devuelve el descuento y la utilidad objetivo del cliente."""
    if nombre not in CLIENTES:
        raise ValueError(f"No hay cliente cargado con nombre '{nombre}'")
    return CLIENTES[nombre]


def buscar_envase(nombre: str) -> dict:
    """Devuelve el cliente dueño del envase y su costo."""
    if nombre not in ENVASES:
        raise ValueError(f"No hay envase cargado con nombre '{nombre}'")
    return ENVASES[nombre]
