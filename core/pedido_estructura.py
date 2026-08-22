"""Lectura POR ESTRUCTURA del pedido: las cantidades salen de la tabla, sin IA.

La tabla del mail de Día es determinista: fila de títulos con las
sucursales, y renglones con código, descripción y una celda de cantidad
por sucursal. La cantidad que está en la columna de BZ ES de BZ — acá no
hay nada que inferir, y un cruce de bultos entre sucursales es imposible
por construcción, no improbable.

Este parser trabaja sobre el texto TABULADO canónico (el mismo
``cuerpo_texto`` que guarda la casilla: filas por línea, celdas separadas
por tab, celdas vacías conservadas — ver core/casilla_pedidos.py), así el
mismo camino sirve para el mail y para un texto pegado que conserve los
tabs. Devuelve el MISMO contrato que el lector con IA
({"bloques": [...]}) o ``None`` si la estructura no cierra: los controles
de sanidad son estrictos a propósito — ante CUALQUIER cosa inesperada no
se adivina, se devuelve None y el que llama cae al camino IA de siempre,
avisando. Nada queda peor que hoy; todo queda visible.
"""

import re

from core.matcheo_comanda import normalizar_texto

# Un encabezado de bloque de empresa: código y nombre en mayúsculas
# ("9582 FRUTAMAX"), sin tabuladores. Misma forma que usa el recorte.
_PATRON_ENCABEZADO_BLOQUE = re.compile(r"^\d{2,6}\s*[-–]?\s*[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ\s.\-]*$")

_PATRON_NUMERO = re.compile(r"^\d+(?:[.,]\d+)?$")


def _numero_de_celda(celda: str) -> float | None:
    if not _PATRON_NUMERO.match(celda):
        return None
    return float(celda.replace(",", "."))


def _es_fila_de_titulos(celdas: list[str]) -> bool:
    return not any(_numero_de_celda(celda) is not None for celda in celdas if celda)


def _partir_en_segmentos(lineas: list[str]) -> list[tuple[str | None, list[str]]]:
    """(empresa, líneas) por cada bloque. Sin encabezados de bloque, todo es un segmento con empresa None."""
    segmentos: list[tuple[str | None, list[str]]] = []
    actual: list[str] = []
    empresa_actual: str | None = None
    hay_encabezados = False

    for linea in lineas:
        limpia = linea.strip()
        if "\t" not in linea and _PATRON_ENCABEZADO_BLOQUE.match(limpia):
            if hay_encabezados or any("\t" in l for l in actual):
                segmentos.append((empresa_actual, actual))
            actual = []
            empresa_actual = limpia
            hay_encabezados = True
        else:
            actual.append(linea)
    segmentos.append((empresa_actual, actual))
    return segmentos


def _parsear_segmento(empresa: str | None, lineas: list[str]) -> dict | None:
    """Un bloque del contrato a partir de sus líneas, o None si la estructura no cierra."""
    filas = [[celda.strip() for celda in linea.split("\t")] for linea in lineas if "\t" in linea]
    if not filas:
        return None

    # La fila de títulos tiene que ser la PRIMERA fila tabulada: código,
    # descripción, y una columna por sucursal. Sin ella no hay cómo saber
    # qué sucursal es cada columna — eso jamás se adivina.
    titulos = filas[0]
    if not _es_fila_de_titulos(titulos) or len(titulos) < 3:
        return None
    sucursales_nombres = [celda for celda in titulos[2:]]
    if not all(sucursales_nombres):
        return None

    cantidad_columnas = len(titulos)
    sucursales = [
        {"sucursal": nombre, "orden_compra": None, "total_bultos": None} for nombre in sucursales_nombres
    ]
    renglones = []

    for celdas in filas[1:]:
        # Toda fila tiene que tener EXACTAMENTE las columnas de los
        # títulos (la conversión conserva las celdas vacías): una fila
        # corrida de columnas es justo el error que no se puede dejar pasar.
        if len(celdas) != cantidad_columnas:
            return None

        texto_fila = normalizar_texto(" ".join(celdas[:2]))
        es_total = "total" in texto_fila
        es_oc = "orden de compra" in texto_fila or re.search(r"\boc\b", texto_fila) is not None

        if es_total or es_oc:
            for indice, sucursal in enumerate(sucursales):
                celda = celdas[2 + indice]
                if not celda:
                    continue
                if es_total and sucursal["total_bultos"] is None:
                    valor = _numero_de_celda(celda)
                    if valor is None:
                        return None
                    sucursal["total_bultos"] = valor
                elif es_oc and sucursal["orden_compra"] is None:
                    # La OC queda como TEXTO tal cual (puede traer ceros a
                    # la izquierda).
                    sucursal["orden_compra"] = celda
            continue

        codigo, descripcion = celdas[0], celdas[1]
        # Un renglón de producto: código numérico (o vacío), descripción NO
        # numérica, y cantidades numéricas o vacías. Cualquier otra cosa es
        # una fila que este parser no entiende: no se adivina.
        if codigo and _numero_de_celda(codigo) is None:
            return None
        if not codigo and not descripcion:
            # Fila enteramente vacía de identidad: si además no tiene
            # cantidades es relleno de formato; si tiene, es indescifrable.
            if any(celdas[2:]):
                return None
            continue
        if descripcion and _numero_de_celda(descripcion) is not None:
            return None

        cantidades = {}
        for indice, nombre in enumerate(sucursales_nombres):
            celda = celdas[2 + indice]
            if not celda:
                continue
            valor = _numero_de_celda(celda)
            if valor is None:
                return None
            cantidades[nombre] = valor

        renglones.append(
            {
                "codigo": codigo or "",
                "descripcion": descripcion or "",
                "cantidades": cantidades,
                # Acá no hay lectura dudosa posible: la celda está o no está.
                "confianza": "alta",
            }
        )

    if not renglones:
        return None
    return {"empresa": empresa or "", "sucursales": sucursales, "renglones": renglones}


def _parsear_por_titulos(texto: str) -> dict | None:
    """Formato "títulos completos": fila de títulos con código/descripción/sucursales pegados."""
    segmentos = _partir_en_segmentos(texto.split("\n"))
    bloques = []
    for empresa, lineas in segmentos:
        if not any("\t" in linea for linea in lineas):
            continue
        bloque = _parsear_segmento(empresa, lineas)
        if bloque is None:
            # Un solo segmento indescifrable invalida TODO: mezclar mitades
            # leídas por estructura con mitades sin leer sería perder
            # renglones en silencio.
            return None
        bloques.append(bloque)

    return {"bloques": bloques} if bloques else None


def _es_fila_vacia(celdas: list[str]) -> bool:
    return not any(celdas)


def _es_encabezado_de_sucursales(celdas: list[str]) -> bool:
    """La fila que abre un bloque en el mail real: SOLO los nombres de sucursal, sin ningún número."""
    no_vacias = [celda for celda in celdas if celda]
    return len(no_vacias) >= 1 and all(_numero_de_celda(celda) is None for celda in no_vacias)


def _parsear_grilla_dia(texto: str) -> dict | None:
    """El formato REAL del mail de Día (calibrado contra los mails guardados del 21 y 22/08/2026).

    Una sola tabla ancha con columnas de margen vacías; cada bloque de
    empresa adentro de la tabla, con esta secuencia fija:

      1. fila encabezado: SOLO los nombres de sucursal (VL/BZ/GR), el
         resto vacío — de acá salen las COLUMNAS de cada sucursal;
      2. fila de OC: números bajo las columnas de sucursal, sin etiqueta
         y nada fuera de ellas;
      3. fila de empresa + totales: "9582 FRUTAMAX" en las columnas de
         margen (con colspan, ya expandido por la conversión) y el total
         declarado bajo cada sucursal;
      4. filas de producto: código numérico y descripción en sus columnas,
         cantidades bajo las sucursales (las vacías son vacías).

    Todo posicional y estricto: cualquier fila que no calce en la
    secuencia devuelve None y se cae al camino IA, avisando.
    """
    filas = [[celda.strip() for celda in linea.split("\t")] for linea in texto.split("\n") if "\t" in linea]
    if not filas:
        return None
    # La grilla tiene que ser rectangular: una fila con celdas de más o de
    # menos es EXACTAMENTE el corrimiento que no puede pasar de largo.
    if len({len(fila) for fila in filas}) != 1:
        return None

    bloques = []
    indice = 0
    while indice < len(filas):
        if _es_fila_vacia(filas[indice]):
            indice += 1
            continue
        if not _es_encabezado_de_sucursales(filas[indice]):
            return None
        columnas = [posicion for posicion, celda in enumerate(filas[indice]) if celda]
        nombres = [filas[indice][posicion] for posicion in columnas]

        # 2. La fila de OC: solo números bajo las sucursales.
        indice += 1
        if indice >= len(filas):
            return None
        fila_oc = filas[indice]
        if any(celda for posicion, celda in enumerate(fila_oc) if posicion not in columnas):
            return None
        ordenes = {}
        for posicion in columnas:
            if fila_oc[posicion]:
                if _numero_de_celda(fila_oc[posicion]) is None:
                    return None
                # La OC como TEXTO tal cual (puede traer ceros a la izquierda).
                ordenes[posicion] = fila_oc[posicion]

        # 3. La fila de empresa + totales declarados.
        indice += 1
        if indice >= len(filas):
            return None
        fila_empresa = filas[indice]
        fuera = [celda for posicion, celda in enumerate(fila_empresa) if posicion not in columnas and celda]
        if not fuera:
            return None
        empresa = " ".join(fuera)
        totales = {}
        for posicion in columnas:
            if fila_empresa[posicion]:
                valor = _numero_de_celda(fila_empresa[posicion])
                if valor is None:
                    return None
                totales[posicion] = valor

        sucursales = [
            {"sucursal": nombres[orden], "orden_compra": ordenes.get(posicion), "total_bultos": totales.get(posicion)}
            for orden, posicion in enumerate(columnas)
        ]

        # 4. Los renglones de producto, hasta el próximo encabezado de bloque.
        renglones = []
        indice += 1
        while indice < len(filas) and not (
            not _es_fila_vacia(filas[indice]) and _es_encabezado_de_sucursales(filas[indice])
        ):
            fila = filas[indice]
            indice += 1
            if _es_fila_vacia(fila):
                continue
            fuera_fila = [celda for posicion, celda in enumerate(fila) if posicion not in columnas and celda]
            codigo = ""
            descripcion = ""
            if len(fuera_fila) == 2:
                # Código numérico y descripción de texto, en ese orden.
                if _numero_de_celda(fuera_fila[0]) is None or _numero_de_celda(fuera_fila[1]) is not None:
                    return None
                codigo, descripcion = fuera_fila
            elif len(fuera_fila) == 1:
                if _numero_de_celda(fuera_fila[0]) is not None:
                    codigo = fuera_fila[0]
                else:
                    descripcion = fuera_fila[0]
            else:
                # Sin identidad (o con celdas de más): este parser no lo
                # entiende — no se adivina.
                return None

            cantidades = {}
            for orden, posicion in enumerate(columnas):
                if fila[posicion]:
                    valor = _numero_de_celda(fila[posicion])
                    if valor is None:
                        return None
                    cantidades[nombres[orden]] = valor

            renglones.append(
                {"codigo": codigo, "descripcion": descripcion, "cantidades": cantidades, "confianza": "alta"}
            )

        if not renglones:
            return None
        bloques.append({"empresa": empresa, "sucursales": sucursales, "renglones": renglones})

    return {"bloques": bloques} if bloques else None


def parsear_pedido_estructurado(texto: str) -> dict | None:
    """El pedido leído de la estructura de la tabla, o None si hay que caer al camino IA.

    Dos formatos deterministas, en orden: el de "títulos completos"
    (código/descripción/sucursales en la fila de títulos) y el REAL del
    mail de Día (grilla ancha con encabezado de solo sucursales, fila de
    OC y fila de empresa+totales). None NUNCA es silencioso: quien llama
    lo registra y lo muestra ("leído con IA — el parser no pudo"), porque
    si Día cambia el formato hay que enterarse ese día, no cuando
    aparezca un cruce de bultos.
    """
    if "\t" not in (texto or ""):
        return None

    resultado = _parsear_por_titulos(texto)
    if resultado is not None:
        return resultado
    return _parsear_grilla_dia(texto)
