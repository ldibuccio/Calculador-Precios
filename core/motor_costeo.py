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
