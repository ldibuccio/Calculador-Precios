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


def calcular_costo_ponderado_por_kg_cherry(
    cantidad_cajones: list[float], kg_por_cajon: list[float], precio_por_cajon: list[float]
) -> float:
    """Reglas 1-3 (cherry): costo ponderado por kg, sin importar el tamaño del cajón.

    Cada compra aporta su costo_por_kg (precio_del_cajón / kg_del_cajón),
    ponderado por los kilos totales comprados en esa compra.
    """
    if not (len(cantidad_cajones) == len(kg_por_cajon) == len(precio_por_cajon)):
        raise ValueError("cantidad_cajones, kg_por_cajon y precio_por_cajon deben tener la misma longitud")

    costos_por_kg = [precio / kg for precio, kg in zip(precio_por_cajon, kg_por_cajon)]
    kilos_totales = [cajones * kg for cajones, kg in zip(cantidad_cajones, kg_por_cajon)]
    return calcular_promedio_ponderado(costos_por_kg, kilos_totales)


def calcular_costo_por_presentacion(costo_ponderado_por_kg: float, kg_presentacion: float) -> float:
    """Regla 4: costo de una fila/presentación a partir del costo ponderado por kg."""
    return costo_ponderado_por_kg * kg_presentacion


def calcular_utilidad_combinada_ponderada_cherry(
    utilidades_por_presentacion: list[float], kg_por_presentacion: list[float]
) -> float:
    """Regla 5: utilidad combinada del cherry, ponderada por los kilos comprados de cada presentación."""
    return calcular_promedio_ponderado(utilidades_por_presentacion, kg_por_presentacion)
