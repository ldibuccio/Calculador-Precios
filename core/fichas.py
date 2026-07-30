"""Fichas de artículos: cómo se compra y se fracciona cada uno.

Este módulo NO hace cálculos de costeo (eso sigue en motor_costeo.py).

El envase, el contenido de la caja y la unidad de venta de un artículo
pueden variar según el cliente (el mismo Mango un cliente lo compra por
unidad y otro por kilo), así que esos tres datos NO viven en la ficha del
artículo: viven en FICHAS_LOGISTICA, indexada por (artículo, cliente).

La ficha del artículo (FICHAS) solo guarda lo que es intrínseco al
producto en sí, sin importar a qué cliente se le venda ni en qué unidad se
lo facture: los datos físicos de cómo llega el cajón del productor al
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

FICHAS = {
    "Mzn Granny": {},
    "Mzn Red": {},
    "Pera": {},
    "Man Gob": {},
    "Uva": {},
    "Durazno": {},
    "Ciruela": {},
    "Pelón": {},
    "Melón": {},
    "Cereza": {},
    "Sandía": {},
    "Lima": {},
    "Tomate Redondo": {},
    "Tomate Perita": {},
    "Berenjena": {},
    "Pepino": {},
    "Zapallito": {},
    "Morrón Verde": {},
    "Tomate Cherry": {},
    "Mandarina": {},
    "Limón": {},
    "Jugo": {},
    "Ombligo": {},
    "Pomelo": {},
    "Morrón Rojo": {},
    # Cubetas por caja: cómo llega el cajón del productor (intrínseco)
    "Frutilla": {"cubetas_por_caja": CUBETAS_POR_CAJA_ESTANDAR},
    "Arándano": {"cubetas_por_caja": CUBETAS_POR_CAJA_ESTANDAR},
    # Datos de palet: cómo llega el cajón del productor (intrínseco)
    "Mango": {"datos_palet": {"unidades_por_cajon": 40, "kg_por_cajon": 16}},
    "Palta": {"datos_palet": {"unidades_por_cajon": 80, "kg_por_cajon": 10}},
}


def buscar_ficha(nombre: str) -> dict:
    """Devuelve la ficha intrínseca del artículo. Lanza ValueError si no está cargada."""
    if nombre not in FICHAS:
        raise ValueError(f"No hay ficha cargada para el artículo '{nombre}'")
    return FICHAS[nombre]


# ----------------------------------------------------------------------------
# Ficha de logística por artículo + cliente: unidad de venta, qué envase usa
# y contenido de la caja para ESE cliente puntual. Cargado acá para "Día".
# ----------------------------------------------------------------------------

FICHAS_LOGISTICA = {
    # Sin envase compartido (se entrega en su propio cajón)
    ("Mzn Granny", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Mzn Red", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Pera", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Man Gob", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Uva", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Durazno", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Ciruela", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Pelón", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Melón", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Cereza", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Sandía", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": None, "contenido_caja": None},
    ("Frutilla", "Día"): {"unidad_venta": UNIDAD_VENTA_CUBETA, "envase": None, "contenido_caja": None},
    ("Arándano", "Día"): {"unidad_venta": UNIDAD_VENTA_CUBETA, "envase": None, "contenido_caja": None},
    # Caja Chica Día
    ("Lima", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Chica Día", "contenido_caja": 5},
    ("Tomate Redondo", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Chica Día", "contenido_caja": 6},
    ("Tomate Perita", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Chica Día", "contenido_caja": 6},
    ("Berenjena", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Chica Día", "contenido_caja": 6},
    ("Pepino", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Chica Día", "contenido_caja": 6},
    ("Zapallito", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Chica Día", "contenido_caja": 6},
    ("Morrón Verde", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Chica Día", "contenido_caja": 4},
    ("Tomate Cherry", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Chica Día", "contenido_caja": 5},
    ("Mango", "Día"): {"unidad_venta": UNIDAD_VENTA_UNIDAD, "envase": "Caja Chica Día", "contenido_caja": 10},
    ("Palta", "Día"): {"unidad_venta": UNIDAD_VENTA_UNIDAD, "envase": "Caja Chica Día", "contenido_caja": 50},
    # Caja Grande Día
    ("Mandarina", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Grande Día", "contenido_caja": 16},
    ("Limón", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Grande Día", "contenido_caja": 16},
    ("Jugo", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Grande Día", "contenido_caja": 16},
    ("Ombligo", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Grande Día", "contenido_caja": 16},
    ("Pomelo", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Grande Día", "contenido_caja": 16},
    ("Morrón Rojo", "Día"): {"unidad_venta": UNIDAD_VENTA_KILO, "envase": "Caja Grande Día", "contenido_caja": 8},
}


def buscar_ficha_logistica(articulo: str, cliente: str) -> dict:
    """Devuelve la unidad de venta, el envase y el contenido de caja de un artículo para un cliente puntual."""
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
