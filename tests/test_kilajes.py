"""El corte del 25%, fijado contra los datos que lo decidieron.

Los saltos y la cantidad de formatos salen de `kilajes_1` corrida en las dos
bases el 18/09. Los VALORES intermedios de algunos casos son de ejemplo —la
medición devolvió el mínimo, el máximo y el salto máximo, no la lista— y eso
va dicho acá: un número de fixture no se presenta con la etiqueta de un dato
de producción.
"""
from core.kilajes import CORTE_DE_RACIMO, pilas_por_formato, racimos_de


def test_el_corte_PARTE_los_que_son_formatos():
    # Batata de Palmala: el dueño la describió "salta de 8 a 12 a 18", y la
    # medición le dio 3 formatos. Es el artículo que nadie había mirado.
    assert len(racimos_de([8, 12, 18])) == 3
    # Mango de Frutamax: 10 → 54 con salto 233%, 2 formatos. Los valores del
    # medio no se midieron; lo que se fija es que los extremos no conviven.
    assert len(racimos_de([10, 54])) == 2
    # EL CHERRY DE FRUTAMAX, que es el caso que motivó todo: su salto máximo
    # es 37%, o sea el más chico de los cinco artículos que se parten. Con un
    # corte de 40% quedaría en un formato solo — y sin este caso escrito como
    # PARTICIÓN, aflojar el corte a 40 no hace caer ningún test de la regla:
    # la Batata y el Mango saltan tanto que se parten igual. Lo midió el
    # canario del 40%, que hacía caer la aritmética y no la regla.
    assert len(racimos_de([5, 6.85])) == 2      # 37%


def test_el_corte_NO_parte_lo_que_es_VARIACION():
    """Lima, Pepino y Cabutia dan 17-19%: es el mismo cajón pesado dos veces.

    Es la mitad que un test del caso bueno no puede ver. Un detector que
    parte todo pasa el test de arriba y se ve igual de trabajador — y llena
    el Remanente de pilas que no existen.
    """
    assert len(racimos_de([16, 18.7])) == 1      # 16,9%
    assert len(racimos_de([16, 19])) == 1        # 18,8%
    # Y el control de un solo valor, que es el caso de 52 de los 57
    # artículos de las dos bases.
    assert len(racimos_de([16])) == 1
    assert racimos_de([]) == []


def test_el_UMBRAL_es_el_25_y_los_otros_dos_fallan_para_lados_opuestos():
    """Los tres umbrales que se midieron, con el caso que condena a cada uno.

    Sin esto el 0,25 es un número suelto que alguien va a "redondear" a 0,2 o
    a 0,3 sin saber qué se rompe de cada lado.
    """
    assert CORTE_DE_RACIMO == 0.25
    # EL 40% SE QUEDA CORTO: el Cherry de Frutamax salta 37% y es el caso
    # que motivó todo. Con 25 se parte; con 40 quedaría en un solo formato.
    assert 0.37 > CORTE_DE_RACIMO
    # EL 15% SE PASA: Lima, Pepino y Cabutia están en 17-19% y son el mismo
    # cajón pesado dos veces.
    assert 0.17 > 0.15 and 0.19 <= CORTE_DE_RACIMO


def test_las_pilas_se_arman_DENTRO_DE_CADA_MAGNITUD():
    """El Mango se compra por UNIDAD: 10 y 54 son unidades por caja.

    Mezclado con los de kilo, ese 10 quedaría pegado a un cajón de 10 kg y el
    artículo saldría partido por una razón falsa. Comparar dos números sin la
    unidad es la familia entera de este proyecto.
    """
    pilas = pilas_por_formato([
        {"contenido": 10, "unidad": "unidad", "bultos": 4},
        {"contenido": 10, "unidad": "kilo", "bultos": 7},
    ])
    # Mismo número, dos pilas: la unidad es lo único que las separa.
    assert len(pilas) == 2
    assert {(p["unidad"], p["bultos"]) for p in pilas} == {("unidad", 4.0), ("kilo", 7.0)}


def test_los_bultos_de_un_MISMO_formato_se_suman_y_los_de_otro_no():
    pilas = pilas_por_formato([
        {"contenido": 16, "unidad": "kilo", "bultos": 3},
        {"contenido": 18.7, "unidad": "kilo", "bultos": 2},   # el mismo cajón
        {"contenido": 5, "unidad": "kilo", "bultos": 9},      # otro formato
    ])
    assert [(p["contenidos"], p["bultos"]) for p in pilas] == [
        ([5.0], 9.0),
        ([16.0, 18.7], 5.0),
    ]


def test_lo_que_NO_declara_contenido_va_a_SU_PROPIA_pila():
    """Un ajuste o el stock inicial no dicen de qué formato son.

    Repartirlos entre las otras pilas sería inventar; dejarlos afuera haría
    que las pilas no sumen el total, que es peor. Van con su nombre.
    """
    pilas = pilas_por_formato([
        {"contenido": 16, "unidad": "kilo", "bultos": 3},
        {"contenido": None, "unidad": None, "bultos": 4},
    ])
    assert pilas[-1] == {"unidad": None, "contenidos": [], "bultos": 4.0}
    # Y LAS PILAS SUMAN EL TOTAL: si no, la pantalla muestra un número que no
    # es el stock y nadie sabe cuál de los dos creer.
    assert round(sum(p["bultos"] for p in pilas), 2) == 7.0


def test_la_regla_del_CODIGO_parte_igual_que_la_CONSULTA_que_midio_el_umbral():
    """`kilajes_1` corta con `lag` sobre los contenidos ordenados y el mismo
    salto relativo. Si el código partiera distinto, el número que decidió el
    corte no diría nada del resultado — sería el umbral de otra regla.
    """
    import io

    consulta = io.open("db/kilajes_1_racimos_por_articulo.sql", encoding="utf-8").read()
    assert "lag(contenido)" in consulta
    assert "(contenido - previo) / nullif(previo, 0)" in consulta
    # El 0.25 de la consulta y el de la constante son el mismo número.
    assert "s.salto > 0.25" in consulta
    assert CORTE_DE_RACIMO == 0.25


def test_las_TRES_copias_de_SUFIJOS_UNIDAD_COMPRA_dicen_lo_MISMO():
    """Está escrita tres veces y hoy las tres son idénticas.

    No se unifican todavía —decisión del 18/09: son tres líneas iguales y
    moverlas ahora es riesgo sin beneficio— así que lo que impide que se
    separen no es que hoy coincidan: es esto. El que agregue una unidad nueva
    va a editar la que tenga abierta, y la que quede vieja **no va a fallar**:
    va a imprimir el número sin letra, que es el hueco que no se ve.
    """
    from app.main import SUFIJOS_UNIDAD_COMPRA as en_main
    from core.exportar_compras import SUFIJOS_UNIDAD_COMPRA as en_compras
    from core.exportar_ingresos import SUFIJOS_UNIDAD_COMPRA as en_ingresos

    assert en_compras == en_ingresos == en_main, (
        "Se separaron: core/exportar_compras.py, core/exportar_ingresos.py y "
        "app/main.py tienen que decir lo mismo mientras sean tres copias."
    )
    # Y las tres unidades que el sistema conoce están en la tabla: una que
    # falte imprime el número pelado, sin la letra.
    assert set(en_main) == {"kilo", "unidad", "cubeta"}
