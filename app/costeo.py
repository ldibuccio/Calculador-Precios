"""'Pegamento' entre las compras cargadas y el motor de costeo (core/motor_costeo.py).

Lee de la base (vía app/db.py) y usa las funciones de cálculo puras de
core/motor_costeo.py. Nada de esto está conectado a ninguna ruta ni pantalla
todavía — son piezas sueltas que se van armando paso a paso.

Este primer paso solo agrupa por artículo y calcula el costo ponderado por
cantidad de cajones, sin ninguna regla especial por artículo o por cliente.
Faltan (pasos siguientes): cherry por kg variable, mango por unidad,
unidad-vs-kilo según la ficha de cada cliente, costo de envase, precio
sugerido.
"""

from datetime import datetime, timedelta, timezone

from app.db import listar_compras_para_costeo
from core.motor_costeo import calcular_costo_por_unidad_medida, calcular_costo_promedio_ponderado

ARGENTINA = timezone(timedelta(hours=-3))
VENTANA_COSTEO_HORAS = 48


def calcular_costos_ponderados_recientes(momento_referencia: datetime | None = None) -> list[dict]:
    """Costo ponderado por cantidad de cajones de cada artículo, con las compras de las últimas 48 hs.

    momento_referencia es el "ahora" desde el que se cuentan las 48 hs hacia
    atrás (por defecto, el momento real de la llamada, en hora argentina).

    OJO con la precisión: fecha_operacion en la base es una fecha sin hora
    (el día en que se cargó la compra), no un instante exacto. Por eso la
    ventana se resuelve por día calendario: se incluyen todas las compras
    cuya fecha_operacion cae entre el día de (momento_referencia - 48 hs) y
    el día de momento_referencia, ambos inclusive. En la práctica esto puede
    incluir un poco más de 48 hs exactas (por ejemplo, todo el día de "ayer"
    aunque momento_referencia sea temprano a la mañana) — nunca menos.

    Para cada compra con importe cargado, se calcula su costo por cajón
    (importe / cantidad_cajones) y se pondera por la cantidad de cajones de
    esa compra (calcular_costo_promedio_ponderado, REGLA 1 genérica). Las
    compras sin importe (compra sin precio todavía) se excluyen del cálculo,
    pero se cuentan por artículo para poder avisar cuántas quedaron afuera.

    Devuelve una lista con un dict por cada artículo que tuvo al menos una
    compra CON precio en la ventana (los artículos sin ninguna compra con
    precio no aparecen), con: articulo_id, articulo_nombre,
    cantidad_cajones_total, costo_ponderado, compras_sin_precio_excluidas.
    Ordenada por nombre de artículo.
    """
    if momento_referencia is None:
        momento_referencia = datetime.now(ARGENTINA)

    fecha_hasta = momento_referencia.date()
    fecha_desde = (momento_referencia - timedelta(hours=VENTANA_COSTEO_HORAS)).date()

    compras = listar_compras_para_costeo(fecha_desde, fecha_hasta)

    cajones_por_articulo: dict[int, list[float]] = {}
    precios_por_cajon_por_articulo: dict[int, list[float]] = {}
    nombres_por_articulo: dict[int, str] = {}
    sin_precio_por_articulo: dict[int, int] = {}

    for compra in compras:
        articulo_id = compra["articulo_id"]
        nombres_por_articulo[articulo_id] = compra["articulo_nombre"]

        if compra["importe"] is None:
            sin_precio_por_articulo[articulo_id] = sin_precio_por_articulo.get(articulo_id, 0) + 1
            continue

        cajones = compra["cantidad_cajones"]
        precio_por_cajon = calcular_costo_por_unidad_medida(compra["importe"], cajones)

        cajones_por_articulo.setdefault(articulo_id, []).append(cajones)
        precios_por_cajon_por_articulo.setdefault(articulo_id, []).append(precio_por_cajon)

    resultado = [
        {
            "articulo_id": articulo_id,
            "articulo_nombre": nombres_por_articulo[articulo_id],
            "cantidad_cajones_total": sum(cajones),
            "costo_ponderado": calcular_costo_promedio_ponderado(
                cajones, precios_por_cajon_por_articulo[articulo_id]
            ),
            "compras_sin_precio_excluidas": sin_precio_por_articulo.get(articulo_id, 0),
        }
        for articulo_id, cajones in cajones_por_articulo.items()
    ]
    resultado.sort(key=lambda fila: fila["articulo_nombre"])
    return resultado
