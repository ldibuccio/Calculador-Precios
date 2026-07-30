"""Funciones puras para cálculos de costeo.

Ejemplo inicial: promedio ponderado por cantidad.
"""


def calcular_costo_por_unidad_medida(importe: float, cantidad: float) -> float:
    """Costo por unidad de medida (kilo, unidad o cubeta) de una compra: importe / cantidad.

    A partir de los datos crudos que carga el comprador (cantidad_kilos y/o
    cantidad_unidades de la compra), esta misma función sirve para sacar el
    costo por kilo (pasándole cantidad_kilos) o el costo por unidad
    (pasándole cantidad_unidades) — sin usar ningún factor de conversión
    entre kilos y unidades.
    """
    if cantidad == 0:
        raise ValueError("cantidad no puede ser cero")
    return importe / cantidad


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


def calcular_costo_ponderado_por_unidad_mango_descartable(
    cantidad_cajas: list[float], unidades_por_caja: list[float], costo_por_caja: list[float]
) -> float:
    """Mango Env. Descartable: costo ponderado por unidad, con cantidad variable de unidades por caja.

    Cada compra aporta su costo_por_unidad (costo_de_la_caja / unidades_de_esa_caja),
    ponderado por el total de unidades compradas en esa compra.
    """
    if not (len(cantidad_cajas) == len(unidades_por_caja) == len(costo_por_caja)):
        raise ValueError("cantidad_cajas, unidades_por_caja y costo_por_caja deben tener la misma longitud")

    costos_por_unidad = [costo / unidades for costo, unidades in zip(costo_por_caja, unidades_por_caja)]
    unidades_totales = [cajas * unidades for cajas, unidades in zip(cantidad_cajas, unidades_por_caja)]
    return calcular_promedio_ponderado(costos_por_unidad, unidades_totales)


MANGO_CC_KG_POR_CAJA = 40


def calcular_costo_ponderado_por_kg_mango_cc(cantidad_cajas: list[float], costo_por_caja: list[float]) -> float:
    """Mango CC: costo ponderado por kg, con cajas de peso fijo (40 kg).

    Cada compra aporta su costo_por_kg (costo_de_la_caja / 40), ponderado
    por los kilos totales comprados en esa compra.
    """
    if len(cantidad_cajas) != len(costo_por_caja):
        raise ValueError("cantidad_cajas y costo_por_caja deben tener la misma longitud")

    costos_por_kg = [costo / MANGO_CC_KG_POR_CAJA for costo in costo_por_caja]
    kilos_totales = [cajas * MANGO_CC_KG_POR_CAJA for cajas in cantidad_cajas]
    return calcular_promedio_ponderado(costos_por_kg, kilos_totales)


def calcular_costo_ponderado_por_cubeta(
    cantidad_cajas: list[float], costo_por_caja: list[float], cubetas_por_caja: float
) -> float:
    """Costo ponderado por cubeta, con cantidad fija de cubetas por caja (parámetro).

    Cada compra aporta su costo_por_cubeta (costo_de_la_caja / cubetas_por_caja),
    ponderado por el total de cubetas compradas en esa compra.
    """
    if len(cantidad_cajas) != len(costo_por_caja):
        raise ValueError("cantidad_cajas y costo_por_caja deben tener la misma longitud")

    costos_por_cubeta = [costo / cubetas_por_caja for costo in costo_por_caja]
    cubetas_totales = [cajas * cubetas_por_caja for cajas in cantidad_cajas]
    return calcular_promedio_ponderado(costos_por_cubeta, cubetas_totales)


def calcular_costo_ponderado_por_cubeta_frutilla(
    cantidad_cajas: list[float], costo_por_caja: list[float], cubetas_por_caja: float = 12
) -> float:
    """Frutilla: costo ponderado por cubeta (12 cubetas por caja, salvo aviso de cambio)."""
    return calcular_costo_ponderado_por_cubeta(cantidad_cajas, costo_por_caja, cubetas_por_caja)


def calcular_costo_ponderado_por_cubeta_arandano(
    cantidad_cajas: list[float], costo_por_caja: list[float], cubetas_por_caja: float = 12
) -> float:
    """Arándano: costo ponderado por cubeta (12 cubetas por caja, salvo aviso de cambio)."""
    return calcular_costo_ponderado_por_cubeta(cantidad_cajas, costo_por_caja, cubetas_por_caja)


SIN_ENVASE = 0


def costo_por_kilo_base(
    costo_bulto: float, kg_bulto: float, costo_envase: float, cantidad_envases: float
) -> float:
    """Costo por kilo antes de aplicar descuento: (costo_bulto + costo_envase*cantidad_envases) / kg_bulto."""
    if kg_bulto == 0:
        raise ValueError("kg_bulto no puede ser cero")
    return (costo_bulto + costo_envase * cantidad_envases) / kg_bulto


def costo_por_kilo(
    costo_bulto: float,
    kg_bulto: float,
    costo_envase: float,
    cantidad_envases: float,
    descuento: float,
) -> float:
    if descuento == 1:
        raise ValueError("descuento no puede ser 1 (dividiría por cero)")
    base = costo_por_kilo_base(costo_bulto, kg_bulto, costo_envase, cantidad_envases)
    return base / (1 - descuento)


def precio_sugerido(
    costo_bulto: float,
    kg_bulto: float,
    costo_envase: float,
    cantidad_envases: float,
    descuento: float,
    utilidad: float,
) -> float:
    """La utilidad se aplica solo al costo del producto; el envase se suma sin utilidad."""
    if kg_bulto == 0:
        raise ValueError("kg_bulto no puede ser cero")
    if descuento == 1:
        raise ValueError("descuento no puede ser 1 (dividiría por cero)")
    costo_producto_por_kg = costo_bulto / kg_bulto
    costo_envase_por_kg = costo_envase * cantidad_envases / kg_bulto
    return (costo_producto_por_kg * (1 + utilidad) + costo_envase_por_kg) / (1 - descuento)


def utilidad_real(
    precio_dia: float,
    kg_bulto: float,
    costo_bulto: float,
    costo_envase: float,
    cantidad_envases: float,
    descuento: float,
) -> float:
    costo_total = costo_bulto + costo_envase * cantidad_envases
    if costo_total == 0:
        raise ValueError("el costo total no puede ser cero")
    ingreso_neto = precio_dia * (1 - descuento) * kg_bulto
    return (ingreso_neto - costo_total) / costo_total
