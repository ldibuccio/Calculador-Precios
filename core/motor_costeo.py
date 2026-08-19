"""Funciones puras para cálculos de costeo.

Ejemplo inicial: promedio ponderado por cantidad.
"""


def calcular_costo_por_unidad_medida(importe: float, cantidad: float) -> float:
    """Costo por unidad de medida (kilo o fracción) de una compra: importe / cantidad.

    A partir de los datos crudos que carga el comprador (cantidad_kilos y/o
    cantidad_fraccion de la compra), esta misma función sirve para sacar el
    costo por kilo (pasándole cantidad_kilos) o el costo por fracción
    (pasándole cantidad_fraccion) — sin usar ningún factor de conversión.
    "Fracción" es unidad o cubeta según el artículo (nunca ambas a la vez).
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


def precio_sugerido_multi_concepto(
    costo_producto: float,
    costo_envase: float,
    tasas_suman: list[float],
    tasas_restan: list[float],
    utilidad: float,
) -> float:
    """Igual que precio_sugerido, pero con listas abiertas de conceptos en vez de un único descuento.

    costo_producto y costo_envase van ya por unidad de venta (no reciben
    costo_bulto/kg_bulto/cantidad_envases: eso lo resuelve quien llama,
    antes de pasarle acá los dos números ya divididos).

    tasas_suman: fracciones que son plata del cliente y se suman al precio
    (ej. IVA 0.105, premio por desempeño 0.02).
    tasas_restan: fracciones que se descuentan del precio (ej. logística
    0.23, flete 0.03) — generaliza el "descuento" de antes, que era una
    sola de estas tasas.
    utilidad: el margen objetivo, una sola fracción, aplicado solo sobre
    costo_producto — nunca sobre el envase, igual que en precio_sugerido.

    Todas las tasas (suman y restan) se aplican sobre el mismo precio de
    lista, en el mismo nivel: al precio de lista se le suma el IVA, se le
    restan los descuentos (logística, flete), se le resta el costo
    (mercadería + caja), y lo que queda es la utilidad objetivo. Por eso van
    sumadas y restadas juntas en un solo denominador, no como dos factores
    multiplicados:

        precio_sugerido = (costo_producto * (1 + utilidad) + costo_envase)
                           / (1 + suma(tasas_suman) - suma(tasas_restan))

    Con tasas_suman y tasas_restan vacías, ambas sumas dan 0, el
    denominador queda en 1 y el resultado es EXACTAMENTE el mismo que con
    un único descuento/utilidad (equivalente a llamar a precio_sugerido con
    ese descuento como única tasa_restan).
    """
    suma_tasas_suman = sum(tasas_suman)
    suma_tasas_restan = sum(tasas_restan)

    denominador = 1 + suma_tasas_suman - suma_tasas_restan
    if denominador <= 0:
        raise ValueError(
            f"1 + suma de tasas que suman ({suma_tasas_suman}) - suma de tasas que restan "
            f"({suma_tasas_restan}) = {denominador}: no puede ser cero ni negativo, "
            "el precio quedaría negativo o dividiría por cero"
        )

    return (costo_producto * (1 + utilidad) + costo_envase) / denominador


def costo_objetivo_multi_concepto(
    precio_vigente: float,
    costo_envase: float,
    tasas_suman: list[float],
    tasas_restan: list[float],
    utilidad: float,
) -> float:
    """A cuánto comprar COMO MÁXIMO para llegar a la utilidad objetivo — la inversa exacta de las otras dos.

    La utilidad se gana SOLO sobre la mercadería (regla de negocio, ver
    utilidad_real_multi_concepto): al precio vigente se le aplican las
    tasas, se le recupera el envase, y lo que queda dividido por
    (1 + utilidad) es el costo máximo de mercadería:

        costo_objetivo = (precio_vigente * (1 + suma(tasas_suman) - suma(tasas_restan))
                          - costo_envase) / (1 + utilidad)

    Garantía de ida y vuelta (fijada por test): comprando exactamente a
    costo_objetivo, precio_sugerido_multi_concepto devuelve el
    precio_vigente y utilidad_real_multi_concepto devuelve la utilidad
    objetivo, clavados los dos — las tres funciones usan la misma regla.

    precio_vigente y costo_envase van por unidad de venta (kilo/unidad/
    cubeta), y el resultado también: costo máximo por unidad de venta.
    Quien llama lo multiplica por el contenido del bulto para tener el
    objetivo por bulto.

    Puede dar negativo (precio vigente tan bajo que ni el envase se cubre):
    se devuelve tal cual, que quien muestre decida cómo avisarlo.
    """
    if utilidad == -1:
        raise ValueError("utilidad no puede ser -1 (dividiría por cero)")

    suma_tasas_suman = sum(tasas_suman)
    suma_tasas_restan = sum(tasas_restan)

    denominador = 1 + suma_tasas_suman - suma_tasas_restan
    if denominador <= 0:
        raise ValueError(
            f"1 + suma de tasas que suman ({suma_tasas_suman}) - suma de tasas que restan "
            f"({suma_tasas_restan}) = {denominador}: no puede ser cero ni negativo"
        )

    return (precio_vigente * denominador - costo_envase) / (1 + utilidad)


def utilidad_real(
    precio_dia: float,
    kg_bulto: float,
    costo_bulto: float,
    costo_envase: float,
    cantidad_envases: float,
    descuento: float,
) -> float:
    """Versión vieja de un solo descuento — misma regla que utilidad_real_multi_concepto: la utilidad se mide SOLO sobre la mercadería."""
    if costo_bulto == 0:
        raise ValueError("el costo de la mercadería no puede ser cero")
    ingreso_neto = precio_dia * (1 - descuento) * kg_bulto
    return (ingreso_neto - costo_envase * cantidad_envases - costo_bulto) / costo_bulto


def utilidad_real_multi_concepto(
    precio_vigente: float,
    costo_producto: float,
    costo_envase: float,
    tasas_suman: list[float],
    tasas_restan: list[float],
) -> float:
    """Utilidad que deja el precio vigente hoy, con listas abiertas de conceptos — la inversa exacta de precio_sugerido_multi_concepto.

    REGLA DE NEGOCIO (19/08/2026): la utilidad se gana SOLO sobre la
    mercadería — nunca sobre el envase ni ningún otro insumo. El envase es
    un costo que se recupera tal cual (pasa de largo), no una base sobre la
    que se margina. Es el mismo criterio que ya aplicaba
    precio_sugerido_multi_concepto (utilidad solo sobre costo_producto);
    esta función medía antes la utilidad sobre mercadería + envase y estaba
    MAL — quedaron las dos coherentes.

    Mismas listas de tasas que precio_sugerido_multi_concepto, aplicadas al
    revés: se parte del precio_vigente ya cargado, se le aplican las tasas
    del cliente, se recupera el envase, y lo que queda contra la mercadería
    es la utilidad:

        entra = precio_vigente * (1 + suma(tasas_suman) - suma(tasas_restan))
        utilidad = (entra - costo_envase - costo_producto) / costo_producto

    costo_producto, costo_envase y precio_vigente tienen que estar
    expresados en la MISMA unidad entre sí (los tres por kilo, o los tres
    por bulto/caja completa) — el resultado da igual en cualquiera de los
    dos casos, porque es un cociente: la unidad se cancela.
    """
    if costo_producto == 0:
        raise ValueError("el costo de la mercadería no puede ser cero")

    entra = precio_vigente * (1 + sum(tasas_suman) - sum(tasas_restan))
    return (entra - costo_envase - costo_producto) / costo_producto
