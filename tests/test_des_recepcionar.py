"""Deshacer una recepción: la compra vuelve a 'pendiente' y sale del stock.

LA OPERACIÓN QUE FALTABA, y el corolario 31 al pie de la letra. Ninguna
pantalla podía devolver una compra a 'pendiente': el Deshacer de Depósito
está bloqueado para las recepcionadas ("para corregirla hace falta Gerencia")
y lo que Gerencia tiene es Corregir Recepción, que es OTRA COSA —su propio
docstring lo dice: "NO cambia el estado (sigue 'recepcionado')"—. Una
recepción apretada por error se arreglaba en el editor de la base con
`db/revertir_una_recepcion.sql`, que existe desde el 08/09.

POR QUÉ NO VA UN MOVIMIENTO COMPENSATORIO: la entrada de stock no es una fila
en `movimientos_stock`, es LA COMPRA MISMA. Un ajuste en menos dejaría dos
registros falsos que se cancelan, y cualquier pantalla que los muestre por
separado va a mentir.
"""
import ast
import io
import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app.db import revertir_recepcion_de_compra, uso_del_lote_de_la_compra  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


# ------------------------------------------------------------------ el SQL


def _cuerpo(nombre):
    """El texto de esa función de app/db.py, SIN su docstring.

    Sin sacarlo, un assert por la negativa matchea la prosa que explica la
    regla: el docstring de esta función NOMBRA las columnas que el test busca,
    que es la colisión garantizada del corolario 59.
    """
    src = io.open(os.path.join(RAIZ, "app/db.py"), encoding="utf-8").read()
    for nodo in ast.walk(ast.parse(src)):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
            cuerpo = list(nodo.body)
            if (cuerpo and isinstance(cuerpo[0], ast.Expr)
                    and isinstance(cuerpo[0].value, ast.Constant)):
                cuerpo = cuerpo[1:]
            return "\n".join(ast.unparse(n) for n in cuerpo)
    raise AssertionError(f"no existe {nombre}")


def test_el_UPDATE_borra_TODAS_las_columnas_que_escribe_la_recepcion():
    """EL CONJUNTO ENCONTRADO CONTRA EL DECIDIDO, y no una lista escrita a mano.

    `_recepcionar_compra` escribe N columnas; deshacer tiene que borrarlas
    todas. Con una lista propia, la columna que la recepción gane mañana no
    se va a nulear — y eso no falla: deja un valor "real" de una recepción que
    ya no existe, y las consultas que hacen COALESCE(real, estimado) lo
    muestran como recibido.

    Ya pasó una vez: `db/revertir_una_recepcion.sql` es del 08/09 y no nulea
    `segunda_por_cajon_real`, que es del 20/09.
    """
    escribe = set(re.findall(r"(\w+)\s*=\s*%s", _cuerpo("_recepcionar_compra")))
    escribe -= {"id"}                       # el WHERE, no una columna escrita
    borra = set(re.findall(r"(\w+)\s*=\s*NULL", _cuerpo("revertir_recepcion_de_compra")))

    faltan = {c for c in escribe if c.endswith("_real") or c in
              ("cantidad_cajones_rechazada", "motivo_rechazo")} - borra
    assert not faltan, f"la recepción escribe {sorted(faltan)} y deshacerla no las borra"


def test_el_estado_vuelve_a_pendiente_y_procesada_el_se_borra():
    cuerpo = _cuerpo("revertir_recepcion_de_compra")
    assert "estado = 'pendiente'" in cuerpo
    assert "procesada_el = NULL" in cuerpo


def test_el_retiro_se_deshace_SOLO_si_lo_puso_la_recepcion():
    """`_auto_retirar_si_corresponde` deja `retiro_origen = 'deposito'`. Si lo
    marcó Logística es un hecho aparte y esta compra no puede pisarlo."""
    cuerpo = _cuerpo("revertir_recepcion_de_compra")
    assert cuerpo.count("retiro_origen = 'deposito'") == 3, (
        "las tres columnas del retiro miran la MISMA condición, o una se deshace "
        "y las otras no"
    )


def test_la_guarda_de_existencia_NO_usa_un_agregado():
    """Con `count(*)` la fila vuelve con 0 y `is None` no se cumple nunca, así
    que la guarda no podría distinguir "no existe" de "existe" (corolario 27).
    """
    cuerpo = _cuerpo("revertir_recepcion_de_compra")
    primer_select = cuerpo.split("execute(", 1)[1][:200]
    assert "count(" not in primer_select.lower(), primer_select


def test_el_uso_del_lote_califica_el_lote_tipo():
    """`lote_origen_id` es POLIMÓRFICO: sin `lote_tipo = 'guia'`, un reproceso
    con el mismo id contaría como esta compra."""
    assert "lote_tipo = 'guia'" in _cuerpo("_lote_de_la_compra_YA_SE_USO")


def test_la_PANTALLA_y_la_ESCRITURA_preguntan_por_LA_MISMA_funcion():
    """Un botón que el POST después rechaza es un callejón: el que lo aprieta
    se come un error por algo que la pantalla le propuso.

    SE MUEVE LA PARED Y SE EXIGE QUE LAS DOS LA SIGAN: las dos tienen que
    llamar a `_lote_de_la_compra_YA_SE_USO`, no tener cada una su SELECT. Con
    dos copias, el día que una cambie el callejón aparece sin que nada avise.
    """
    for funcion in ("revertir_recepcion_de_compra", "uso_del_lote_de_la_compra"):
        assert "_lote_de_la_compra_YA_SE_USO" in _cuerpo(funcion), funcion


# --------------------------------------------------------- comportamiento


@pytest.fixture(scope="module")
def base_real():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def galpon(base_real, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", base_real)
    import app.db as d
    from datetime import date

    def sql(consulta, parametros=()):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()

    (n,), = sql("SELECT nextval(pg_get_serial_sequence('articulos','id'))")
    (art,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id", (f"EJEMPLO Art {n}",))
    (prov,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s,%s) RETURNING id",
                   (f"EJEMPLO Prov {n}", f"N01P{n % 100:02d}"))

    def recepcionada(retiro_origen="deposito"):
        d.crear_compra(date.today(), art, prov, 10, 16, 160, None, 50000, None,
                       "Clark", None, segunda_por_cajon=None)
        (cid,), = sql("SELECT max(id) FROM compras")
        sql("""UPDATE compras SET estado='recepcionado', cantidad_cajones_real=10,
               contenido_por_cajon_real=16, cantidad_kilos_real=160,
               segunda_por_cajon_real=3, procesada_el=now(),
               estado_retiro='retirado', retiro_origen=%s, retiro_procesado_el=now()
               WHERE id=%s""", (retiro_origen, cid))
        return cid

    def consumir(compra_id):
        (rid,), = sql("""INSERT INTO reprocesos (articulo_id, fecha_operacion, bultos_tomados,
                         bultos_primera, bultos_segunda, bultos_merma, tipo)
                         VALUES (%s, current_date, 5, 5, 0, 0, 'normal') RETURNING id""", (art,))
        # origen='compra' y no 'guia': lo exige reprocesos_consumos_compra_coherente.
        sql("""INSERT INTO reprocesos_consumos (reproceso_id, origen, compra_id, bultos)
               VALUES (%s,'compra',%s,5)""", (rid, compra_id))
        return rid

    return d, sql, recepcionada, consumir


def test_la_recepcion_se_deshace_y_la_compra_SALE_DEL_STOCK(galpon):
    d, sql, recepcionada, _ = galpon
    compra_id = recepcionada()

    d.revertir_recepcion_de_compra(compra_id)

    fila, = sql("""SELECT estado, cantidad_cajones_real, contenido_por_cajon_real,
                          cantidad_kilos_real, segunda_por_cajon_real, procesada_el
                     FROM compras WHERE id=%s""", (compra_id,))
    assert fila == ("pendiente", None, None, None, None, None)


def test_el_retiro_que_puso_LOGISTICA_no_se_pisa(galpon):
    """El control del de arriba: con los dos casos dando lo mismo, una
    reversión que borrara el retiro SIEMPRE pasaría los dos."""
    d, sql, recepcionada, _ = galpon
    compra_id = recepcionada(retiro_origen="logistica")

    d.revertir_recepcion_de_compra(compra_id)

    fila, = sql("SELECT estado, estado_retiro, retiro_origen FROM compras WHERE id=%s", (compra_id,))
    assert fila == ("pendiente", "retirado", "logistica")


def test_con_el_LOTE_YA_CONSUMIDO_rebota_y_NO_TOCA_NADA(galpon):
    d, sql, recepcionada, consumir = galpon
    compra_id = recepcionada()
    consumir(compra_id)

    with pytest.raises(ValueError) as error:
        d.revertir_recepcion_de_compra(compra_id)
    assert "guía R" in str(error.value)

    fila, = sql("SELECT estado, cantidad_cajones_real FROM compras WHERE id=%s", (compra_id,))
    assert fila == ("recepcionado", 10), "rebotó y además dejó algo escrito"


def test_CON_LA_GUIA_ANULADA_vuelve_a_poder(galpon):
    """EL CASO QUE TIENE QUE PASAR. Sin él, una guarda que rechazara siempre
    pasaría todos los casos negativos (corolario 30)."""
    d, sql, recepcionada, consumir = galpon
    compra_id = recepcionada()
    reproceso_id = consumir(compra_id)
    sql("UPDATE reprocesos SET anulado_el = now() WHERE id=%s", (reproceso_id,))

    d.revertir_recepcion_de_compra(compra_id)

    (estado,), = sql("SELECT estado FROM compras WHERE id=%s", (compra_id,))
    assert estado == "pendiente"


def test_una_compra_que_NO_esta_recepcionada_rebota(galpon):
    d, _, recepcionada, _ = galpon
    compra_id = recepcionada()
    d.revertir_recepcion_de_compra(compra_id)

    with pytest.raises(ValueError) as error:
        d.revertir_recepcion_de_compra(compra_id)
    assert "no está recepcionada" in str(error.value)


def test_un_id_que_no_existe_rebota_sin_romper(galpon):
    d, _, _, _ = galpon
    with pytest.raises(ValueError) as error:
        d.revertir_recepcion_de_compra(999_999_999)
    assert "ya no existe" in str(error.value)


def test_el_lector_de_la_PANTALLA_dice_lo_mismo_que_la_escritura(galpon):
    d, _, recepcionada, consumir = galpon
    libre = recepcionada()
    usada = recepcionada()
    consumir(usada)

    assert d.uso_del_lote_de_la_compra(libre) == {"guias": 0, "armados": 0}
    assert d.uso_del_lote_de_la_compra(usada) == {"guias": 1, "armados": 0}


# -------------------------------------------------------------- la pantalla


def test_el_BOTON_solo_aparece_donde_la_escritura_ACEPTA():
    """Ofrecer algo que el POST después rechaza es un callejón, y eso es peor
    que no ofrecer nada: el que lo aprieta se come un error por algo que la
    pantalla le propuso.

    Los dos casos juntos —con el lote libre y con el lote usado— porque uno
    solo no distingue "ofrece cuando corresponde" de "ofrece siempre" ni de
    "no ofrece nunca" (corolario 30).
    """
    from tests.test_cajas import _pantalla_corregir, NO_MARCADA

    libre = _pantalla_corregir(NO_MARCADA).text
    usada = _pantalla_corregir(NO_MARCADA, uso_lote={"guias": 2, "armados": 0}).text

    assert 'action="/gerencia/compras/663/des-recepcionar"' in libre
    assert 'action="/gerencia/compras/663/des-recepcionar"' not in usada
    assert "ya se tomó mercadería" in usada
    assert "2 guías R" in usada


def test_una_compra_NO_recepcionada_no_ofrece_deshacer_la_recepcion():
    """No hay recepción que deshacer, así que el bloque entero no va."""
    from tests.test_cajas import _pantalla_corregir, NO_MARCADA

    texto = _pantalla_corregir(NO_MARCADA, estado="pendiente").text

    assert "des-recepcionar" not in texto
    assert "<h3>Deshacer la recepción</h3>" not in texto
