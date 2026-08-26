"""Calcula qué filas nuevas hay que agregar a precios_venta_historial al guardar la carga de precios.

Todo acá es Python puro, sin tocar la base: mismo patrón que
core/conceptos_cliente.py — recibe lo que el formulario mandó (con el
precio original viajando en un campo oculto, tal como estaba al cargar la
pantalla) y devuelve solo las filas que realmente cambiaron. Nunca pisa
nada: respeta el historial de la tabla (vigente_desde = hoy para lo
nuevo, lo viejo queda intacto).
"""


def calcular_cambios_de_precios(filas: list[dict]) -> list[dict]:
    """Compara cada precio tipeado contra su valor original (vigente al cargar la pantalla).

    Cada fila de "filas" trae:
      - "ficha_id": int — la clave de VENTA (el precio es de la ficha,
        no del artículo: dos fichas del mismo artículo y cliente tienen
        precios distintos).
      - "precio_original": el precio vigente tal cual estaba al cargar la
        pantalla, o None si el artículo no tenía precio cargado todavía.
      - "precio_nuevo": lo que quedó tipeado al guardar, o None si el
        campo quedó vacío.

    Devuelve una lista de {"ficha_id", "precio"} — las filas que hay
    que INSERTAR con vigente_desde = hoy (esa fecha la agrega quien
    escriba a la base, acá no se sabe la fecha). Si nada cambió, devuelve
    lista vacía.

    - Campo vacío (precio_nuevo is None) nunca genera nada, tenga o no
      precio original: a diferencia de las tasas del cliente, acá no hay
      forma de "dar de baja" un precio desde esta pantalla — un artículo
      activo siempre necesita tener precio en algún momento. Dejarlo en
      blanco es "no toqué esto ahora", no "sacalo".
    - precio_nuevo == precio_original: no cambió nada, no se agrega nada
      (evita filas de historial de más para lo que no se tocó).
    - precio_nuevo distinto del original (incluido cuando no había
      original todavía): se agrega la fila.
    """
    cambios = []
    for fila in filas:
        precio_nuevo = fila.get("precio_nuevo")
        if precio_nuevo is None:
            continue
        if precio_nuevo == fila.get("precio_original"):
            continue
        cambios.append({"ficha_id": fila["ficha_id"], "precio": precio_nuevo})
    return cambios
