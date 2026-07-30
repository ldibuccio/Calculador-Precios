"""Fichas de artículos: cómo se compra y se fracciona cada uno.

Este módulo NO hace cálculos de costeo (eso sigue en motor_costeo.py).

El envase y el contenido de la caja de un artículo pueden variar según el
cliente (un mismo artículo puede repartirse distinto para cada uno), así
que esos datos ya NO viven en la ficha del artículo: viven en
FICHAS_LOGISTICA, indexada por (artículo, cliente).

La ficha del artículo (FICHAS) solo guarda lo que es intrínseco al
producto en sí, sin importar a qué cliente se le venda: la unidad en la
que se vende, y los datos físicos de cómo llega el cajón del productor al
depósito (cubetas por caja, unidades/kg por cajón para calcular palets de
flete) — esto se define en la recepción, antes de repartir nada a ningún
cliente.
"""

import math

CUBETAS_POR_CAJA_ESTANDAR = 12
KG_POR_PALET_ESTANDAR = 800

UNIDAD_VENTA_KILO = "kilo"
UNIDAD_VENTA_CUBETA = "cubeta"
UNIDAD_VENTA_UNIDAD = "unidad"


def _ficha_por_kilo() -> dict:
    return {"unidad_venta": UNIDAD_VENTA_KILO}


def _ficha_por_cubeta() -> dict:
    return {"unidad_venta": UNIDAD_VENTA_CUBETA, "cubetas_por_caja": CUBETAS_POR_CAJA_ESTANDAR}


def _ficha_por_unidad(unidades_por_cajon: float, kg_por_cajon: float) -> dict:
    return {
        "unidad_venta": UNIDAD_VENTA_UNIDAD,
        "datos_palet": {"unidades_por_cajon": unidades_por_cajon, "kg_por_cajon": kg_por_cajon},
    }


FICHAS = {
    # Por kilo
    "Mzn Granny": _ficha_por_kilo(),
    "Mzn Red": _ficha_por_kilo(),
    "Pera": _ficha_por_kilo(),
    "Man Gob": _ficha_por_kilo(),
    "Uva": _ficha_por_kilo(),
    "Durazno": _ficha_por_kilo(),
    "Ciruela": _ficha_por_kilo(),
    "Pelón": _ficha_por_kilo(),
    "Melón": _ficha_por_kilo(),
    "Cereza": _ficha_por_kilo(),
    "Sandía": _ficha_por_kilo(),
    "Lima": _ficha_por_kilo(),
    "Tomate Redondo": _ficha_por_kilo(),
    "Tomate Perita": _ficha_por_kilo(),
    "Berenjena": _ficha_por_kilo(),
    "Pepino": _ficha_por_kilo(),
    "Zapallito": _ficha_por_kilo(),
    "Morrón Verde": _ficha_por_kilo(),
    "Tomate Cherry": _ficha_por_kilo(),
    "Mandarina": _ficha_por_kilo(),
    "Limón": _ficha_por_kilo(),
    "Jugo": _ficha_por_kilo(),
    "Ombligo": _ficha_por_kilo(),
    "Pomelo": _ficha_por_kilo(),
    "Morrón Rojo": _ficha_por_kilo(),
    # Por cubeta (12 cubetas por caja, propia del artículo)
    "Frutilla": _ficha_por_cubeta(),
    "Arándano": _ficha_por_cubeta(),
    # Por unidad, con datos de palet (propios del artículo)
    "Mango": _ficha_por_unidad(unidades_por_cajon=40, kg_por_cajon=16),
    "Palta": _ficha_por_unidad(unidades_por_cajon=80, kg_por_cajon=10),
}


def buscar_ficha(nombre: str) -> dict:
    """Devuelve la ficha intrínseca del artículo. Lanza ValueError si no está cargada."""
    if nombre not in FICHAS:
        raise ValueError(f"No hay ficha cargada para el artículo '{nombre}'")
    return FICHAS[nombre]


# ----------------------------------------------------------------------------
# Ficha de logística por artículo + cliente: qué envase usa y contenido de la
# caja para ESE cliente puntual. Cargado acá para el cliente "Día".
# ----------------------------------------------------------------------------

_SIN_ENVASE_COMPARTIDO = {"envase": None, "contenido_caja": None}

FICHAS_LOGISTICA = {
    # Envase perdido (cajón propio, sin fraccionar en ningún envase compartido)
    ("Mzn Granny", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Mzn Red", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Pera", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Man Gob", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Uva", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Durazno", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Ciruela", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Pelón", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Melón", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Cereza", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Sandía", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Frutilla", "Día"): _SIN_ENVASE_COMPARTIDO,
    ("Arándano", "Día"): _SIN_ENVASE_COMPARTIDO,
    # Caja Chica Día
    ("Lima", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 5},
    ("Tomate Redondo", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 6},
    ("Tomate Perita", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 6},
    ("Berenjena", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 6},
    ("Pepino", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 6},
    ("Zapallito", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 6},
    ("Morrón Verde", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 4},
    ("Tomate Cherry", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 5},
    ("Mango", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 10},
    ("Palta", "Día"): {"envase": "Caja Chica Día", "contenido_caja": 50},
    # Caja Grande Día
    ("Mandarina", "Día"): {"envase": "Caja Grande Día", "contenido_caja": 16},
    ("Limón", "Día"): {"envase": "Caja Grande Día", "contenido_caja": 16},
    ("Jugo", "Día"): {"envase": "Caja Grande Día", "contenido_caja": 16},
    ("Ombligo", "Día"): {"envase": "Caja Grande Día", "contenido_caja": 16},
    ("Pomelo", "Día"): {"envase": "Caja Grande Día", "contenido_caja": 16},
    ("Morrón Rojo", "Día"): {"envase": "Caja Grande Día", "contenido_caja": 8},
}


def buscar_ficha_logistica(articulo: str, cliente: str) -> dict:
    """Devuelve qué envase usa un artículo para un cliente puntual, y el contenido de la caja."""
    clave = (articulo, cliente)
    if clave not in FICHAS_LOGISTICA:
        raise ValueError(f"No hay ficha de logística para '{articulo}' del cliente '{cliente}'")
    return FICHAS_LOGISTICA[clave]


def calcular_cantidad_cajas(cantidad_comprada: float, contenido_caja: float) -> float:
    """Cuántas cajas equivalen a lo comprado, sin redondear.

    No aplica a artículos sin envase compartido (no se fraccionan en una
    caja chica/grande).
    """
    if contenido_caja == 0:
        raise ValueError("contenido_caja no puede ser cero")
    return cantidad_comprada / contenido_caja


def calcular_palets(kg_totales: float, kg_por_palet: float = KG_POR_PALET_ESTANDAR) -> int:
    """Cantidad de palets a pagar: siempre redondea hacia arriba (1,2 palets = 2)."""
    if kg_por_palet == 0:
        raise ValueError("kg_por_palet no puede ser cero")
    return math.ceil(kg_totales / kg_por_palet)
