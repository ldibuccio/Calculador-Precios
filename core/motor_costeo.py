"""Funciones puras para cálculos de costeo.

Ejemplo inicial: promedio ponderado por cantidad.
"""


def calcular_promedio_ponderado(valores: list[float], cantidades: list[float]) -> float:
    if len(valores) != len(cantidades):
        raise ValueError("valores y cantidades deben tener la misma longitud")
    if not valores:
        raise ValueError("valores no puede estar vacío")

    total_cantidad = sum(cantidades)
    if total_cantidad == 0:
        raise ValueError("la suma de cantidades no puede ser cero")

    suma_ponderada = sum(valor * cantidad for valor, cantidad in zip(valores, cantidades))
    return suma_ponderada / total_cantidad


def calcular_costo_promedio_ponderado(cantidades_compradas: list[float], precios: list[float]) -> float:
    """REGLA 1: costo promedio ponderado por cantidad comprada a cada proveedor."""
    return calcular_promedio_ponderado(precios, cantidades_compradas)


def calcular_kilo_promedio_ponderado_cajon(cantidad_cajones: list[float], kg_por_cajon: list[float]) -> float:
    """REGLA 2: kilo promedio de un cajón, ponderado por la cantidad de cajones de cada peso."""
    return calcular_promedio_ponderado(kg_por_cajon, cantidad_cajones)
