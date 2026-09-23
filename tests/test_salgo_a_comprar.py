"""El listado atado al momento de SALIR A COMPRAR, contra Postgres de verdad.

Lo que estos tests miran no lo puede ver un mock: que el reparto de las
compras contra el momento lo haga la CONSULTA —por `cargado_el`, estado y
`procesada_el`— y que la foto se saque una sola vez. Con la base mockeada, el
reparto lo decidiría el fixture (corolario 91).

Cada caso de compra va en SU artículo, así cada uno se lee solo y un caso que
cae en el grupo equivocado no se esconde en una suma.
"""
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_cargas_compra import base_real, galpon  # noqa: F401  (fixtures)

# EL MOMENTO DE SALIR: 22/09 a las 22:00 en Argentina. Fijo y lejos de hoy,
# por la misma razón que CARGADA_EL (corolario 95): comparado contra `now()`
# el reparto dependería de la hora a la que se corre la suite.
SALIDA = datetime(2026, 9, 23, 1, 0, tzinfo=timezone.utc)


def _cerrar_abiertos(sql):
    """La base es compartida por el módulo: un listado abierto que dejó otro
    test pasaría a ser "el abierto" de éste."""
    sql("UPDATE listados_compra SET estado = 'cerrado' WHERE estado = 'borrador'")


def _proveedor(sql):
    (n,), = sql("SELECT nextval(pg_get_serial_sequence('proveedores','id'))")
    codigo = f"L{n % 100:02d}P{(n // 100) % 100:02d}"
    (pid,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) "
                  "ON CONFLICT (codigo_puesto) DO UPDATE SET nombre = EXCLUDED.nombre "
                  "RETURNING id", (f"EJEMPLO Puesto {n}", codigo))
    return pid


def _articulo(sql, nombre):
    (aid,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id", (nombre,))
    return aid


def _compra(sql, articulo, proveedor, *, cargada, estado, procesada=None,
            kilos=100.0, kilos_real=None, cajones=5):
    sql("""INSERT INTO compras (fecha_operacion, articulo_id, proveedor_id, cantidad_kilos,
                                cantidad_kilos_real, cantidad_cajones, contenido_por_cajon,
                                estado, cargado_el, procesada_el)
           VALUES (%s, %s, %s, %s, %s, %s, 20, %s, %s, %s)""",
        (cargada.date(), articulo, proveedor, kilos, kilos_real, cajones, estado,
         cargada, procesada))


def test_las_compras_se_REPARTEN_contra_el_momento_de_salir(galpon):
    """Una compra está en la foto, en camino, en Compré o en el aviso según
    cuándo se CARGÓ y cuándo LLEGÓ — y nunca en dos a la vez.

    Los tres rivales que importan, plantados:
      E) cargada antes y recibida ANTES de salir: ya está en la foto, y
         contarla en camino la sumaría dos veces;
      D) cargada antes y recibida DESPUÉS: la foto no la tiene, así que sí
         está en camino aunque hoy diga 'recepcionado';
      H) vieja y recibida antes: no es una pendiente, no va al aviso.
    """
    d, sql, _c, _t, _l = galpon
    proveedor = _proveedor(sql)
    antes, hace_diez = SALIDA - timedelta(days=1), SALIDA - timedelta(days=10)
    despues = SALIDA + timedelta(hours=2)
    casos = {
        "A": dict(cargada=despues, estado="pendiente"),
        "B": dict(cargada=despues, estado="recepcionado", procesada=despues),
        "C": dict(cargada=antes, estado="pendiente"),
        "D": dict(cargada=antes, estado="recepcionado", procesada=despues, kilos_real=90.0),
        "E": dict(cargada=antes, estado="recepcionado", procesada=antes + timedelta(hours=3)),
        "F": dict(cargada=antes, estado="rechazado"),
        "G": dict(cargada=hace_diez, estado="pendiente"),
        "H": dict(cargada=hace_diez, estado="recepcionado", procesada=hace_diez),
    }
    articulos = {}
    for letra, caso in casos.items():
        articulos[letra] = _articulo(sql, f"EJEMPLO Caso {letra} {proveedor}")
        _compra(sql, articulos[letra], proveedor, **caso)

    grupos = d.compras_alrededor_de_la_salida(SALIDA)
    donde = {}
    for grupo, por_articulo in grupos.items():
        for letra, aid in articulos.items():
            if aid in por_articulo:
                donde.setdefault(letra, []).append(grupo)

    assert donde == {"A": ["compre"], "B": ["compre"], "C": ["en_camino"],
                     "D": ["en_camino"], "G": ["viejas"]}
    # LO REAL PRIMERO: D se pesó en 90 y eso es lo que viene.
    assert grupos["en_camino"][articulos["D"]]["kilos"] == 90.0
    assert grupos["viejas"][articulos["G"]]["compras"] == 1
    assert grupos["viejas"][articulos["G"]]["desde"] == hace_diez


def test_la_ventana_de_EN_CAMINO_es_de_TRES_dias_y_no_mas(galpon):
    """El borde, de los dos lados: dos días y veintitrés horas es en camino,
    tres días y una hora es vieja. Un test con casos lejos del corte
    probaría la aritmética y no el corte (corolario 53)."""
    d, sql, _c, _t, _l = galpon
    proveedor = _proveedor(sql)
    adentro = _articulo(sql, f"EJEMPLO Adentro {proveedor}")
    afuera = _articulo(sql, f"EJEMPLO Afuera {proveedor}")
    _compra(sql, adentro, proveedor, estado="pendiente",
            cargada=SALIDA - timedelta(days=3) + timedelta(hours=1))
    _compra(sql, afuera, proveedor, estado="pendiente",
            cargada=SALIDA - timedelta(days=3) - timedelta(hours=1))
    grupos = d.compras_alrededor_de_la_salida(SALIDA)
    assert adentro in grupos["en_camino"] and adentro not in grupos["viejas"]
    assert afuera in grupos["viejas"] and afuera not in grupos["en_camino"]


def test_SALIR_saca_la_foto_UNA_sola_vez(galpon):
    """Una segunda foto movería el punto de partida: lo comprado entre medio
    pasaría de "Compré" al stock. El segundo click no hace nada."""
    d, sql, _c, tomate, lima = galpon
    _cerrar_abiertos(sql)
    listado = d.guardar_borrador_de_compra(SALIDA.date(), set(), {})
    primera = d.salir_a_comprar(listado, {tomate: (3.0, 54.0), lima: (1.0, None)}, {})
    assert primera is not None

    segunda = d.salir_a_comprar(listado, {tomate: (99.0, 999.0)}, {})
    assert segunda is None
    foto = d.foto_del_listado(listado)
    assert foto["sueltos"] == {tomate: (3.0, 54.0), lima: (1.0, None)}
    assert d.borrador_de_compra()["generado_el"] == primera


def test_la_foto_guarda_las_CAJAS_por_ficha_y_una_ficha_en_la_foto_NO_SE_BORRA(galpon):
    """La FK es NO ACTION: borrar la ficha no puede cambiar lo que el listado
    dice que había. Y el que borra tiene que leer por qué, no el error crudo
    de la foreign key."""
    d, sql, cliente, tomate, _l = galpon
    _cerrar_abiertos(sql)
    (ficha,), = sql("INSERT INTO fichas_logistica (articulo_id, cliente_id, unidad_venta, "
                    "contenido_caja) VALUES (%s, %s, 'kilo', 6) RETURNING id", (tomate, cliente))
    listado = d.guardar_borrador_de_compra(SALIDA.date(), set(), {})
    d.salir_a_comprar(listado, {tomate: (0.0, 0.0)}, {ficha: (tomate, 4.0, 24.0)})
    assert d.foto_del_listado(listado)["cajas"] == {ficha: (tomate, 4.0, 24.0)}

    with pytest.raises(ValueError) as rebote:
        d.eliminar_ficha(ficha)
    assert "foto del stock de 1 listado de compra" in str(rebote.value)
    assert "no se puede borrar" in str(rebote.value)
    (quedan,), = sql("SELECT count(*) FROM fichas_logistica WHERE id = %s", (ficha,))
    assert quedan == 1
    # LA SEGUNDA PUERTA que borra una ficha: cambiarle el artículo es DELETE + INSERT.
    with pytest.raises(ValueError) as rebote:
        d.cambiar_articulo_de_ficha(ficha, _l, None, None)
    assert "no se le puede cambiar el artículo" in str(rebote.value)


def test_el_listado_abierto_es_UNO_sea_del_dia_que_sea(galpon):
    """Atado al momento y no al reloj: un listado abierto ayer se sigue
    guardando sobre sí mismo hoy, en vez de abrir otro.

    El RIVAL es el de hasta el 23/09, un borrador por fecha: guardar con la
    fecha de hoy abría uno nuevo y el de anoche quedaba huérfano."""
    d, sql, _c, _t, _l = galpon
    _cerrar_abiertos(sql)
    ayer = d.guardar_borrador_de_compra(SALIDA.date(), set(), {})
    hoy = d.guardar_borrador_de_compra(SALIDA.date() + timedelta(days=1), set(), {})
    assert hoy == ayer
    borrador = d.borrador_de_compra()
    assert borrador["id"] == ayer and borrador["fecha"] == SALIDA.date()


def test_la_BASE_rechaza_un_SEGUNDO_abierto_aunque_sea_de_OTRO_dia(galpon):
    """El índice de `db/listados_compra_8_un_solo_abierto.sql`, que corrió en
    las dos bases el 23/09. El RIVAL es el índice viejo, uno por DÍA: con ése
    el segundo entraba porque la fecha es distinta. Por eso las dos filas
    llevan fechas distintas a propósito — con la misma, los dos índices
    rebotan y el test no los distingue.

    Hasta el 23/09 este test afirmaba lo contrario (que cerrar cerraba DOS
    abiertos), porque el esquema los permitía: era el estado de antes de la
    migración y quedó guardándolo (corolario 22)."""
    d, sql, _c, _t, _l = galpon
    _cerrar_abiertos(sql)
    sql("INSERT INTO listados_compra (fecha, estado) VALUES (%s, 'borrador')",
        (SALIDA.date() - timedelta(days=40),))
    with pytest.raises(Exception) as rebote:
        sql("INSERT INTO listados_compra (fecha, estado) VALUES (%s, 'borrador')",
            (SALIDA.date() - timedelta(days=39),))
    assert "listados_compra_un_solo_abierto_idx" in str(rebote.value)
    assert d.cerrar_borrador_de_compra() is True
    assert d.borrador_de_compra() is None


def test_la_foto_EN_VIVO_de_un_articulo_sin_movimientos_es_CERO_y_no_un_hueco(galpon):
    """Contra el esquema real: las cuatro consultas que arman la foto tienen
    que correr. Sin movimientos, no hay nada en el piso — y eso se sabe."""
    _d, _sql, _c, tomate, _l = galpon
    from app.main import _foto_del_stock
    foto = _foto_del_stock([tomate], SALIDA.date())
    assert foto["sueltos"] == {tomate: (0.0, 0.0)}
    assert foto["cajas"] == {}
