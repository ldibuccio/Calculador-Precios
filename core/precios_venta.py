"""Calcula qué filas nuevas hay que agregar a precios_venta_historial al guardar la carga de precios.

Todo acá es Python puro, sin tocar la base: mismo patrón que
core/conceptos_cliente.py — recibe lo que el formulario mandó y devuelve
solo las filas que realmente cambiaron. Nunca pisa nada: respeta el
historial de la tabla, lo viejo queda intacto.

LA FECHA DE VIGENCIA NO SE SABE ACÁ, y desde el 14/09 tampoco es
necesariamente hoy: la elige quien carga (para corregir un precio que
regía desde antes) y la agrega quien escribe a la base.
"""


def calcular_cambios_de_precios(filas: list[dict]) -> list[dict]:
    """Compara cada precio tipeado contra el que YA REGÍA EN LA FECHA DE VIGENCIA ELEGIDA.

    Cada fila de "filas" trae:
      - "ficha_id": int — la clave de VENTA (el precio es de la ficha,
        no del artículo: dos fichas del mismo artículo y cliente tienen
        precios distintos).
      - "precio_vigente_a_la_fecha": el precio que regía en la fecha de
        vigencia elegida, o None si en esa fecha esa ficha no tenía
        precio todavía.
      - "precio_nuevo": lo que quedó tipeado al guardar, o None si el
        campo quedó vacío.

    **EL NOMBRE LLEVA LA FECHA A PROPÓSITO**, porque hay dos precios que
    se parecen y no son el mismo: el que la PANTALLA MOSTRÓ (el vigente
    hoy, que es contra el que se comparaba hasta el 14/09) y el que REGÍA
    EN LA FECHA ELEGIDA. Mientras todo se cargaba con fecha de hoy eran el
    mismo valor y la diferencia no existía.

    Cargando con fecha anterior se separan, y el modo de falla es el peor
    que hay: si hoy rige $1000 y se quiere corregir el 05/09 poniéndole
    $1000 —porque el $800 que quedó ese día estaba mal—, comparar contra
    el de HOY dice "no cambió nada", **no se escribe ninguna fila, y la
    pantalla contesta que los precios ya estaban al día.** La corrección
    que se pidió no ocurrió y nada lo dice.

    Devuelve una lista de {"ficha_id", "precio"} — las filas a INSERTAR.
    Si nada cambió, devuelve lista vacía.

    - Campo vacío (precio_nuevo is None) nunca genera nada, tenga o no
      precio vigente: a diferencia de las tasas del cliente, acá no hay
      forma de "dar de baja" un precio desde esta pantalla — un artículo
      activo siempre necesita tener precio en algún momento. Dejarlo en
      blanco es "no toqué esto ahora", no "sacalo".
    - precio_nuevo igual al que ya regía a esa fecha: no cambió nada, no
      se agrega nada (evita filas de historial de más para lo que no se
      tocó).
    - precio_nuevo distinto (incluido cuando a esa fecha no había ninguno
      todavía): se agrega la fila.
    """
    cambios = []
    for fila in filas:
        precio_nuevo = fila.get("precio_nuevo")
        if precio_nuevo is None:
            continue
        if precio_nuevo == fila.get("precio_vigente_a_la_fecha"):
            continue
        cambios.append({"ficha_id": fila["ficha_id"], "precio": precio_nuevo})
    return cambios
