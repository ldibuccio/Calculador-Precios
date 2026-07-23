"""Fichas de artículos: cómo se compra y se fracciona cada uno.

Este módulo NO hace cálculos de costeo (eso sigue en motor_costeo.py). Acá
vive el catálogo de fichas y los cálculos de cantidad de cajas / palets que
dependen de ese catálogo. Las fichas van a cambiar con el tiempo: la idea es
que editarlas sea simple, sin tocar ninguna lógica.
"""

import math

from core.motor_costeo import COSTO_ENVASE_CHICO, COSTO_ENVASE_GRANDE, SIN_ENVASE

KG_POR_PALET_ESTANDAR = 800
CUBETAS_POR_CAJA_ESTANDAR = 12

TIPO_ENVASE_PERDIDO = "perdido"
TIPO_ENVASE_CAJA_CHICA = "caja_chica"
TIPO_ENVASE_CAJA_GRANDE = "caja_grande"

UNIDAD_VENTA_KILO = "kilo"
UNIDAD_VENTA_CUBETA = "cubeta"
UNIDAD_VENTA_UNIDAD = "unidad"


def _ficha_envase_perdido_por_kilo() -> dict:
    return {"tipo_envase": TIPO_ENVASE_PERDIDO, "unidad_venta": UNIDAD_VENTA_KILO, "costo_envase": SIN_ENVASE}


def _ficha_envase_perdido_por_cubeta() -> dict:
    return {
        "tipo_envase": TIPO_ENVASE_PERDIDO,
        "unidad_venta": UNIDAD_VENTA_CUBETA,
        "costo_envase": SIN_ENVASE,
        "cubetas_por_caja": CUBETAS_POR_CAJA_ESTANDAR,
    }


def _ficha_caja_chica(contenido_caja: float, unidad_venta: str = UNIDAD_VENTA_KILO) -> dict:
    return {
        "tipo_envase": TIPO_ENVASE_CAJA_CHICA,
        "unidad_venta": unidad_venta,
        "costo_envase": COSTO_ENVASE_CHICO,
        "contenido_caja": contenido_caja,
    }


def _ficha_caja_grande(contenido_caja: float, unidad_venta: str = UNIDAD_VENTA_KILO) -> dict:
    return {
        "tipo_envase": TIPO_ENVASE_CAJA_GRANDE,
        "unidad_venta": unidad_venta,
        "costo_envase": COSTO_ENVASE_GRANDE,
        "contenido_caja": contenido_caja,
    }


FICHAS = {
    # Envase perdido (cajón propio, sin fraccionar) — por kilo
    "Mzn Granny": _ficha_envase_perdido_por_kilo(),
    "Mzn Red": _ficha_envase_perdido_por_kilo(),
    "Pera": _ficha_envase_perdido_por_kilo(),
    "Man Gob": _ficha_envase_perdido_por_kilo(),
    "Uva": _ficha_envase_perdido_por_kilo(),
    "Durazno": _ficha_envase_perdido_por_kilo(),
    "Ciruela": _ficha_envase_perdido_por_kilo(),
    "Pelón": _ficha_envase_perdido_por_kilo(),
    "Melón": _ficha_envase_perdido_por_kilo(),
    "Cereza": _ficha_envase_perdido_por_kilo(),
    "Sandía": _ficha_envase_perdido_por_kilo(),
    # Envase perdido — por cubeta (12 cubetas por caja)
    "Frutilla": _ficha_envase_perdido_por_cubeta(),
    "Arándano": _ficha_envase_perdido_por_cubeta(),
    # Caja chica ($650) — contenido de la caja entregada
    "Lima": _ficha_caja_chica(contenido_caja=5),
    "Tomate Redondo": _ficha_caja_chica(contenido_caja=6),
    "Tomate Perita": _ficha_caja_chica(contenido_caja=6),
    "Berenjena": _ficha_caja_chica(contenido_caja=6),
    "Pepino": _ficha_caja_chica(contenido_caja=6),
    "Zapallito": _ficha_caja_chica(contenido_caja=6),
    "Morrón Verde": _ficha_caja_chica(contenido_caja=4),
    "Tomate Cherry": _ficha_caja_chica(contenido_caja=5),
    "Mango": {
        **_ficha_caja_chica(contenido_caja=10, unidad_venta=UNIDAD_VENTA_UNIDAD),
        "datos_palet": {"unidades_por_cajon": 40, "kg_por_cajon": 16},
    },
    "Palta": {
        **_ficha_caja_chica(contenido_caja=50, unidad_venta=UNIDAD_VENTA_UNIDAD),
        "datos_palet": {"unidades_por_cajon": 80, "kg_por_cajon": 10},
    },
    # Caja grande ($1600) — contenido de la caja entregada
    "Mandarina": _ficha_caja_grande(contenido_caja=16),
    "Limón": _ficha_caja_grande(contenido_caja=16),
    "Jugo": _ficha_caja_grande(contenido_caja=16),
    "Ombligo": _ficha_caja_grande(contenido_caja=16),
    "Pomelo": _ficha_caja_grande(contenido_caja=16),
    "Morrón Rojo": _ficha_caja_grande(contenido_caja=8),
}


def buscar_ficha(nombre: str) -> dict:
    """Devuelve la ficha del artículo. Lanza ValueError si no está cargada."""
    if nombre not in FICHAS:
        raise ValueError(f"No hay ficha cargada para el artículo '{nombre}'")
    return FICHAS[nombre]


def calcular_cantidad_cajas(cantidad_comprada: float, contenido_caja: float) -> float:
    """Cuántas cajas equivalen a lo comprado, sin redondear.

    No aplica a artículos de envase perdido (no se fraccionan, no tienen
    contenido_caja en su ficha).
    """
    if contenido_caja == 0:
        raise ValueError("contenido_caja no puede ser cero")
    return cantidad_comprada / contenido_caja


def calcular_palets(kg_totales: float, kg_por_palet: float = KG_POR_PALET_ESTANDAR) -> int:
    """Cantidad de palets a pagar: siempre redondea hacia arriba (1,2 palets = 2)."""
    if kg_por_palet == 0:
        raise ValueError("kg_por_palet no puede ser cero")
    return math.ceil(kg_totales / kg_por_palet)
