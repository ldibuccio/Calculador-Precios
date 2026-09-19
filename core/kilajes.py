"""Cuándo dos cajones del mismo artículo son el MISMO formato y cuándo no.

El Remanente y el detalle por artículo suman bultos: "quedan 12". Doce
cajones de 5 kg y doce de 60 no son la misma cosa, y el Cherry se compra en
los dos. Separarlos necesita una regla para decidir dónde corta un formato y
empieza el siguiente — porque el mismo cajón pesado dos veces da 16 y 18, y
eso NO son dos formatos.

EL CORTE ES 25% Y ESTÁ MEDIDO, no elegido (`db/kilajes_1_racimos_por_articulo.sql`,
corrida en las dos bases el 18/09):

    PALMALA (35 arts)   Cherry 5,0 → 60,0 (salto 471%)      4 formatos
                        Batata 8,0 → 18,0 (salto 50%)       3
                        Zanahoria Cubito 9 → 19 (85%)       2
                        los otros 32                        1
    FRUTAMAX (22 arts)  Cherry 5,0 → 15,0 (salto 37%)       3
                        Mango 10,0 → 54,0 (salto 233%)      2   (en unidades)
                        los otros 20                        1

Con 25% se parten cinco artículos y ninguno de los que son variación. Los
otros dos umbrales que se midieron fallan para los dos lados: **el 15% se
pasa** —mete Lima, Pepino y Cabutia, que están en 17-19% y son el mismo cajón
pesado dos veces— y **el 40% se queda corto**, deja al Cherry de Frutamax en
un solo formato, que es el caso que motivó todo.

Y confirma que son FORMATOS y no dispersión: Batata salta 8 → 12 → 18 y
Cherry 5 → 10,5 → 60. No hay nada alrededor de un centro.
"""

# El umbral vive acá y no en cada pantalla: escrito dos veces, el día que se
# mueva una de las dos va a partir un artículo que la otra no parte, y los
# dos números van a ser defendibles por separado.
CORTE_DE_RACIMO = 0.25


def racimos_de(contenidos) -> list[list[float]]:
    """Los contenidos ordenados, partidos en formatos.

    Corta cuando el salto contra el valor ANTERIOR supera el corte, que es
    la misma cuenta que `kilajes_1` hace con `lag`: la consulta que midió el
    umbral y el código que lo aplica tienen que partir igual, o el número que
    decidió el corte no dice nada del resultado.

    Relativo y no absoluto: dos kilos de diferencia son ruido en un cajón de
    18 y son otro producto en uno de 5.
    """
    valores = sorted({float(c) for c in contenidos if c is not None and float(c) > 0})
    if not valores:
        return []
    racimos = [[valores[0]]]
    for valor in valores[1:]:
        previo = racimos[-1][-1]
        if previo > 0 and (valor - previo) / previo > CORTE_DE_RACIMO:
            racimos.append([valor])
        else:
            racimos[-1].append(valor)
    return racimos


def formato_de(contenido, racimos) -> int | None:
    """En qué racimo cae este contenido. None si no hay contenido declarado."""
    if contenido is None:
        return None
    valor = float(contenido)
    for indice, racimo in enumerate(racimos):
        if valor in racimo:
            return indice
    return None


def pilas_por_formato(bultos: list[dict], partir_por: str | None = None) -> list[dict]:
    """Los bultos agrupados por formato, DENTRO DE CADA MAGNITUD.

    Cada entrada de `bultos` trae `contenido`, `unidad` y `bultos`.

    `partir_por` es el nombre de una clave de cada item —hoy solo
    "proveedor"— que parte cada pila una vez más y VIAJA al resultado. Es un
    parámetro y no una segunda función porque el RACIMO se calcula igual en
    los dos casos: sobre todos los contenidos de esa magnitud, antes de
    partir. Calculado después, dos proveedores del mismo artículo podrían
    cortar el formato en lugares distintos y las dos filas serían
    defendibles por separado, que es exactamente lo que el umbral único de
    este módulo viene a impedir.

    LA MAGNITUD PRIMERO Y EL RACIMO DESPUÉS, y no al revés: el Mango se
    compra por UNIDAD y va de 10 a 54 unidades por caja. Metido en la misma
    lista que los artículos que se compran por kilo, ese 10 quedaría pegado a
    un cajón de 10 kg y el 54 arriba de todo — el artículo saldría partido
    por una razón falsa y los dos pedazos serían mentira. Comparar dos
    números sin la unidad es la familia entera de este proyecto.

    Los bultos SIN contenido declarado —un ajuste, el stock inicial— caen en
    su propia pila, con `contenido` en None. No se reparten entre las otras:
    no sabemos de qué formato son, y eso es información verdadera.
    """
    por_unidad: dict = {}
    sin_declarar = 0.0
    for item in bultos:
        if item.get("contenido") is None:
            sin_declarar += float(item["bultos"])
            continue
        por_unidad.setdefault(item.get("unidad"), []).append(item)

    pilas = []
    for unidad, items in por_unidad.items():
        racimos = racimos_de(i["contenido"] for i in items)
        acumulado: dict = {}
        for item in items:
            indice = formato_de(item["contenido"], racimos)
            clave = (indice, item.get(partir_por) if partir_por else None)
            pila = acumulado.setdefault(clave, {"contenidos": set(), "bultos": 0.0})
            pila["contenidos"].add(float(item["contenido"]))
            pila["bultos"] += float(item["bultos"])
        # El orden se arma con str() sobre la segunda mitad: sin partir es
        # None en todas y con partir puede venir un None suelto (un lote sin
        # proveedor), y comparar None contra str revienta.
        for clave in sorted(acumulado, key=lambda c: (c[0], str(c[1] or ""))):
            pila = acumulado[clave]
            fila = {
                "unidad": unidad,
                "contenidos": sorted(pila["contenidos"]),
                "bultos": round(pila["bultos"], 2),
            }
            if partir_por:
                fila[partir_por] = clave[1]
            pilas.append(fila)
    if sin_declarar > 0:
        pilas.append({"unidad": None, "contenidos": [], "bultos": round(sin_declarar, 2)})
    return pilas
