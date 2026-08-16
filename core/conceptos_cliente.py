"""Calcula qué filas nuevas hay que agregar a clientes_parametros_historial al guardar el formulario de cliente.

Todo acá es Python puro, sin tocar la base: recibe lo que el formulario
mandó (con el estado "original" de cada fila viajando en campos ocultos,
tal como estaba cuando se cargó la pantalla) y devuelve solo las filas que
realmente hay que insertar — nunca pisa nada, respeta el patrón de
historial de la tabla (vigente_desde = hoy para lo nuevo, lo viejo queda
intacto).
"""


def calcular_cambios_de_tasas(tipo: str, filas: list[dict]) -> list[dict]:
    """Compara cada fila de un grupo de tasas (suma o resta) contra su estado original.

    Cada fila de "filas" trae:
      - "nombre_original": nombre tal cual estaba al cargar la pantalla, o
        "" si la fila es nueva (se agregó con "+ Agregar tasa").
      - "valor_original": fracción (0.04) tal cual estaba, o None si es nueva.
      - "nombre": nombre tal cual quedó en el formulario al guardar.
      - "valor": fracción tal cual quedó en el formulario, o None si el
        campo quedó vacío (fila nueva sin completar).
      - "baja": True si se tildó "Dar de baja esta tasa".

    Devuelve una lista de {"nombre_parametro", "tipo", "valor"} — las
    filas que hay que INSERTAR con vigente_desde = hoy (eso lo agrega quien
    escriba a la base, acá no se sabe la fecha). Si nada cambió, devuelve
    lista vacía.

    Casos:
      - Fila existente sin ningún cambio -> no se agrega nada.
      - Fila existente con el % editado -> una fila con el nuevo valor.
      - Fila existente dada de baja -> una fila con valor 0 (nunca se borra
        físicamente el historial; de hoy en adelante esa tasa no pesa más,
        pero los cálculos de fechas pasadas la siguen viendo con su valor
        de entonces).
      - Fila existente con el NOMBRE cambiado -> se interpreta como "se dio
        de baja el concepto viejo y se dio de alta uno nuevo" (nombre_parametro
        es la identidad del concepto en la tabla, cambiarlo es, en los
        hechos, otro concepto): una fila en 0 para el nombre viejo + una
        fila con el valor actual para el nombre nuevo.
      - Fila nueva completa (nombre + valor) -> una fila de alta.
      - Fila nueva vacía o dada de baja -> no se agrega nada (nunca existió,
        no hay nada que dar de baja).
    """
    cambios = []

    for fila in filas:
        nombre_original = (fila.get("nombre_original") or "").strip()
        nombre_nuevo = (fila.get("nombre") or "").strip()
        valor_nuevo = fila.get("valor")
        valor_original = fila.get("valor_original")
        dar_de_baja = bool(fila.get("baja"))

        if not nombre_original:
            if dar_de_baja or not nombre_nuevo or valor_nuevo is None:
                continue
            cambios.append({"nombre_parametro": nombre_nuevo, "tipo": tipo, "valor": valor_nuevo})
            continue

        if dar_de_baja:
            cambios.append({"nombre_parametro": nombre_original, "tipo": tipo, "valor": 0.0})
            continue

        if nombre_nuevo != nombre_original:
            cambios.append({"nombre_parametro": nombre_original, "tipo": tipo, "valor": 0.0})
            if nombre_nuevo and valor_nuevo is not None:
                cambios.append({"nombre_parametro": nombre_nuevo, "tipo": tipo, "valor": valor_nuevo})
            continue

        if valor_nuevo is not None and valor_nuevo != valor_original:
            cambios.append({"nombre_parametro": nombre_nuevo, "tipo": tipo, "valor": valor_nuevo})

    return cambios


def calcular_cambio_de_utilidad(valor_original: float | None, valor_nuevo: float | None) -> dict | None:
    """Igual que calcular_cambios_de_tasas, pero para la utilidad objetivo (un único concepto, no una lista).

    Devuelve la fila a insertar si cambió, o None si no cambió (o si no
    vino ningún valor nuevo).
    """
    if valor_nuevo is None:
        return None
    if valor_original == valor_nuevo:
        return None
    return {"nombre_parametro": "utilidad_objetivo", "tipo": "utilidad", "valor": valor_nuevo}
