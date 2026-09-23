import ast
import inspect
import io
import re
from datetime import date, datetime, time, timezone
import pytest
from unittest.mock import MagicMock, call, patch

# LA RESPUESTA A "¿quedó armada en caja nuestra?" que llevan estas cargas.
#
# Van SIN FICHA, que en la pantalla es "sin asignar", y desde el 17/09 eso
# EXIGE contestar: sin ficha no hay de dónde derivar el envase, y hasta ese
# día el NULL se escribía en silencio. Estos fixtures no tienen un envase en
# ningún lado, así que la respuesta verdadera es la de abajo — no un relleno
# para que el test pase.
#
# Que estas catorce llamadas hayan tenido que cambiar ES LA FUNCIÓN del
# cambio, no una molestia: la firma ganó algo obligatorio y los llamadores lo
# acusan. El que no lo acusa es el que no pasa por acá.
SIN_CAJA_NUESTRA_DECLARADA = (False, None)

from app import db
from app.main import REGEX_CODIGO_PUESTO
from app.db import (
    _negar_si_el_conteo_contradice_la_unidad_de_compra,
    actualizar_articulo,
    crear_articulo,
    actualizar_cantidad_compra,
    anular_ajuste_vacios,
    anular_vacio_recibido,
    cerrar_sena,
    crear_ajuste_vacios,
    crear_conteo_vacios,
    crear_tipo_envase_puesto,
    crear_vacio_devuelto,
    listar_ajustes_vacios_por_rango,
    listar_conteos_vacios_de_fecha,
    listar_senas_pendientes,
    listar_senas_resueltas,
    listar_tipos_envase_puesto,
    desactivar_proveedor_puesto,
    desactivar_tipo_envase_puesto,
    renombrar_proveedor_puesto,
    renombrar_tipo_envase_puesto,
    listar_senas_pendientes,
    listar_senas_resueltas,
    listar_valores_sena,
    listar_historial_valores_sena,
    listar_historiales_valores_sena,
    asignar_ficha_a_reproceso,
    anular_renglon_stock_inicial,
    crear_reproceso_inicial,
    crear_stock_inicial,
    fecha_corte,
    eliminar_ficha,
    contar_senas_afectadas_por_valor,
    cargar_valor_sena,
    listar_ultimos_conteos_vacios,
    obtener_o_crear_cliente_puesto,
    obtener_o_crear_proveedor_puesto,
    stock_vacios,
    stock_vacios_de_tipo,
    actualizar_cliente,
    actualizar_ficha,
    actualizar_precio_compra,
    cambiar_articulo_de_ficha,
    crear_ficha,
    eliminar_ficha,
    listar_historial_fichas_por_cliente,
    buscar_compras,
    buscar_ingresos_deposito,
    buscar_retiros,
    contar_compras_buscadas,
    contar_ingresos_deposito,
    contar_pedidos_con_renglones_sin_identificar,
    contar_pedidos_incompletos,
    activar_casilla_pedidos,
    anular_renglon_pedido,
    borrar_dia_sin_pedido,
    buscar_renglones_pedidos,
    cerrar_armado_pedido,
    desanular_renglon_pedido,
    reabrir_armado_pedido,
    crear_casilla_pedidos,
    guardar_condiciones_pedido,
    guardar_horario_revision_casilla,
    listar_casillas_pedidos,
    listar_condiciones_pedido,
    listar_fechas_con_pedido_vigente,
    marcar_dia_sin_pedido,
    marcar_mail_pedido_confirmado,
    obtener_condiciones_pedido,
    obtener_mail_de_pedido,
    marcar_lectura_mail_pedido,
    marcar_mail_pedido_error,
    marcar_mail_pedido_ignorado,
    contar_mails_pedido_leidos_con_ia,
    contar_mails_pedido_sin_procesar,
    listar_pedidos_vigentes_con_armado,
    listar_renglones_pedidos_vigentes,
    registrar_mail_pedido,
    registrar_revision_casilla,
    desmarcar_renglon_armado,
    marcar_renglon_armado,
    agregar_renglon_a_pedido,
    contar_renglones_agregados_a_mano,
    corregir_cantidad_renglon,
    crear_pedido,
    borrar_foto_pedido,
    guardar_alias_en_ficha,
    listar_renglones_pedido,
    obtener_pedido_vigente,
    contar_retiros_buscados,
    cerrar_disponible_generado,
    comanda_ya_guardada,
    compra_tiene_cantidad_bloqueada,
    compra_tiene_deshacer_recepcion_bloqueado,
    compra_tiene_deshacer_retiro_bloqueado,
    compra_tiene_precio_bloqueado,
    contar_compras_sin_precio,
    contar_articulos_comprados_incotizables,
    listar_articulos_comprados_incotizables,
    contar_recepciones_pendientes_viejas,
    contar_senas_pendientes_viejas,
    contar_stock_vacios_negativos,
    contar_retiros_pendientes_viejos,
    corregir_recepcion_compra,
    crear_cliente,
    crear_compra,
    crear_compras_de_comanda,
    deshacer_procesado_compra,
    deshacer_retiro_compra,
    crear_envase,
    listar_envases_con_costo,
    registrar_costo_envase,
    eliminar_compra,
    eliminar_compras_del_dia_por_proveedor,
    guardar_disponible,
    guardar_precios_cliente,
    agregar_foto_guia,
    agregar_foto_guia_del_dia,
    borrar_foto_guia,
    listar_fotos_de_guia,
    olvidar_foto_borrada,
    listar_clientes,
    listar_compras_para_costeo,
    listar_compras_pendientes_recepcion,
    listar_compras_pendientes_retiro,
    listar_compras_procesadas_hoy_recepcion,
    listar_compras_procesadas_hoy_retiro,
    listar_compras_sin_precio,
    listar_conceptos_editables_por_cliente,
    listar_detalle_disponible,
    listar_fotos_para_limpiar,
    listar_precios_anteriores_por_cliente,
    listar_precios_vigentes_por_cliente,
    marcar_compra_cancelada,
    marcar_compra_no_ingresada,
    marcar_compra_retirada,
    obtener_borrador_disponible,
    obtener_detalle_compra,
    obtener_ultimo_disponible_cliente,
    obtener_uso_storage_bucket,
    recepcionar_compra,
    rechazar_compra,
)


def _consulta_con(cursor, marca):
    """La ÚNICA consulta ejecutada que contiene `marca`.

    Se busca por contenido y no por índice: `call_args_list[0]` deja de ser
    la consulta que uno cree apenas alguien agrega una lectura antes —pasó
    con el piso del corte, que metió un SELECT a corte_modelo adelante— y un
    assert que corre sobre otra consulta falla por el motivo equivocado o,
    peor, pasa.
    """
    consultas = [c.args[0] for c in cursor.execute.call_args_list if marca in c.args[0]]
    assert len(consultas) == 1, f"Se esperaba UNA consulta con {marca!r}, hay {len(consultas)}"
    return consultas[0]


def _conexion_falsa(filas_fetchone=None, filas_fetchall=None):
    """Arma una conexión y un cursor falsos: cada fetchone()/fetchall() devuelve el próximo valor de la lista dada."""
    cursor = MagicMock()
    if filas_fetchone is not None:
        cursor.fetchone.side_effect = filas_fetchone
    if filas_fetchall is not None:
        cursor.fetchall.return_value = filas_fetchall
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    conexion = MagicMock()
    conexion.cursor.return_value = cursor
    return conexion, cursor


def _sql_que_contiene(cursor, fragmento: str) -> str:
    """La consulta que ejecutó el cursor y contiene este fragmento, sin depender del ORDEN.

    Buscar por posición (`call_args_list[0]`) hace que cualquier sentencia
    nueva rompa tests que no tienen nada que ver con ella.
    """
    return next(ll.args[0] for ll in cursor.execute.call_args_list if fragmento in ll.args[0])


def _sql_y_parametros_que_contienen(cursor, fragmento: str):
    """La consulta que contiene este fragmento Y sus parámetros, sin depender del ORDEN.

    El hermano de `_sql_que_contiene` para cuando también hacen falta los
    parámetros: buscarlos por posición (`call_args_list[3]`) hace que
    cualquier sentencia nueva rompa tests que no tienen nada que ver.
    """
    llamada = next(ll for ll in cursor.execute.call_args_list if fragmento in ll.args[0])
    return llamada.args[0], llamada.args[1]


def _conexion_falsa_con_varios_fetchall(filas_fetchone, secuencia_fetchall):
    """Como _conexion_falsa pero con fetchall() devolviendo un valor DISTINTO por llamada.

    Aparte y no un parámetro más del helper viejo: ése usa return_value y
    hay veinte tests apoyados en eso.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone)
    cursor.fetchall.side_effect = secuencia_fetchall
    return conexion, cursor


def test_borrar_una_compra_CON_FOTO_DE_BALANZA_devuelve_la_ruta_para_sacarla_del_Storage():
    """El caso que hoy revienta, y el que queda mal si alguien lo arregla con cascade.

    La foto de balanza cuelga de ESTA compra y no la comparte con nadie,
    así que al borrar la compra el archivo tiene que irse del bucket. La
    fila sola no alcanza: sin la ruta devuelta, nadie lo saca nunca y el
    archivo queda ocupando lugar para siempre, sin ninguna fila que lo
    nombre — no hay pantalla donde se vea que está de más.

    Y por eso este test es la guarda contra el "on delete cascade": con
    cascade la fila se va sola, este DELETE no existe, la lista vuelve
    VACÍA y el test cae. Que caiga es su función.
    """
    conexion, cursor = _conexion_falsa_con_varios_fetchall(
        [
            (None,),  # RETURNING guia_id: la compra se borró y no tenía guía
        ],
        [
            [("2026-09-08/n07p41-999-abcdef12.jpg",)],  # RETURNING de fotos_recepcion
        ],
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30, origen="compras")

    assert resultado == ["2026-09-08/n07p41-999-abcdef12.jpg"], (
        "la ruta de la foto de balanza tiene que volver para que quien llama la saque del Storage"
    )

    # Y la foto se borra ANTES que la compra: la FK va sin cascade a
    # propósito, así que al revés el DELETE de compras falla.
    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    orden_foto = next(i for i, c in enumerate(consultas) if "DELETE FROM fotos_recepcion" in c)
    orden_compra = next(i for i, c in enumerate(consultas) if "DELETE FROM compras" in c)
    assert orden_foto < orden_compra, "la foto se borra antes que la compra, o la FK rechaza el DELETE"
    conexion.commit.assert_called_once()


def test_la_cuenta_por_ficha_SUMA_los_reingresos_de_esa_ficha():
    """Vuelven cajas ya armadas de un cliente: son de la ficha, no cajones sueltos.

    Hasta el 09/09 `_SQL_STOCK_PARTIDO` no leía `movimientos_stock`, así que
    NINGÚN reingreso entró nunca en una ficha — se los comían los sueltos
    por resta. Reemplaza al testigo que marcaba ese agujero.

    Se mira el SQL y no un resultado porque la consulta es una constante:
    lo que puede volver a romperse es que alguien saque la pata, no que
    calcule mal una fila.
    """
    from app.db import _SQL_STOCK_PARTIDO

    assert "reingresos_ficha" in _SQL_STOCK_PARTIDO
    # Por el renglón del que volvió: la ficha no es columna de movimientos_stock.
    assert "pedidos_renglones pr ON pr.id = m.pedido_renglon_id" in _SQL_STOCK_PARTIDO
    # Y SUMA, no resta: es mercadería que vuelve.
    assert "COALESCE(a.total, 0) + COALESCE(re.total, 0)" in _SQL_STOCK_PARTIDO
    assert "- COALESCE(s.total, 0) - COALESCE(me.total, 0) AS stock" in _SQL_STOCK_PARTIDO


def test_el_reingreso_a_SEGUNDA_no_entra_en_la_ficha():
    """Lo que va al pool de segunda no vuelve al stock normal.

    Mismo criterio que la pata `reingresos` de _SQL_SUMAS_STOCK: si acá
    entrara y allá no, la resta de los sueltos quedaría descuadrada — un
    término en una cuenta y no en la otra cae ENTERO en la diferencia.
    """
    from app.db import _SQL_STOCK_PARTIDO

    assert "m.destino_rechazo IS NULL OR m.destino_rechazo = 'stock'" in _SQL_STOCK_PARTIDO


def test_las_TRES_patas_de_la_cuenta_por_ficha_usan_la_MISMA_ventana_del_corte():
    """Si una mirara toda la historia y las otras solo lo posterior, la resta mezcla dos eras.

    Es la asimetría del día del corte, que en este proyecto ya apareció
    ocho veces. La pata nueva se escribe con el mismo recorte que las dos
    que ya estaban, y esto lo fija.
    """
    from app.db import _SQL_STOCK_PARTIDO

    assert _SQL_STOCK_PARTIDO.count("corte.fecha") >= 3, (
        "alguna pata de la cuenta por ficha dejó de recortar por el corte"
    )
    assert "m.fecha_operacion > corte.fecha" in _SQL_STOCK_PARTIDO


def test_la_migracion_de_fotos_recepcion_NO_lleva_on_delete_cascade():
    """Leído del esquema real, no de la memoria de quien lo escribió.

    Con cascade el archivo queda huérfano en el bucket: la fila se va sin
    que nadie devuelva la ruta, y no hay ninguna pantalla donde se vea un
    archivo que ya no nombra nadie. Es la decisión escrita en
    docs/foto_de_balanza_al_recepcionar.md, y acá está lo que la sostiene
    el día que alguien resuelva el error de FK por el camino corto.
    """
    from pathlib import Path

    esquema = Path("db/esquema_completo.sql").read_text(encoding="utf-8")
    inicio = esquema.index("create table fotos_recepcion")
    definicion = esquema[inicio : esquema.index(");", inicio)]

    assert "references compras (id)" in definicion
    assert "cascade" not in definicion.lower(), (
        "fotos_recepcion.compra_id NO puede llevar on delete cascade: el archivo del Storage "
        "quedaría huérfano. El borrado devuelve la ruta, ver eliminar_compra."
    )


def test_eliminar_compra_ultima_de_su_guia_devuelve_las_fotos_sin_otros_usos():
    # Al borrar el ÚLTIMO renglón de la guía, las fotos de la guía se dan
    # de baja y se devuelven las rutas que ningúna otra guía usa.
    conexion, cursor = _conexion_falsa(
        [
            (105,),  # RETURNING guia_id del DELETE: borro de verdad
            (0,),  # COUNT de compras de la guía tras el DELETE: quedó vacía
            (0,),  # COUNT de otras guías usando la ruta: ninguna
        ],
    )
    # Primer fetchall: el RETURNING de fotos_recepcion — esta compra no tiene
    # foto de balanza. Segundo: el de fotos_guia.
    cursor.fetchall.side_effect = [[], [("2026-08-13/n07p41-123-abcdef12.jpg",)]]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30, origen="compras")

    assert resultado == ["2026-08-13/n07p41-123-abcdef12.jpg"]
    conexion.commit.assert_called_once()
    conexion.close.assert_called_once()


def test_eliminar_compra_con_renglones_restantes_no_toca_las_fotos():
    # La guía sigue teniendo renglones: las fotos son de la GUÍA y se quedan.
    conexion, cursor = _conexion_falsa(
        [
            (105,),
            (2,),  # quedan 2 renglones en la guía
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30, origen="compras")

    assert resultado == []
    # DELETE de fotos_recepcion (vacío) + DELETE de la compra + COUNT de la guía.
    assert cursor.execute.call_count == 3
    assert not any("fotos_guia" in ll.args[0] for ll in cursor.execute.call_args_list)
    conexion.commit.assert_called_once()


def test_eliminar_compra_foto_compartida_por_otra_guia_no_se_borra_del_storage():
    # Listado consolidado: la misma foto cuelga de VARIAS guías. Vaciar una
    # guía saca SU registro, pero el archivo sigue mientras otra guía lo use.
    conexion, cursor = _conexion_falsa(
        [
            (105,),
            (0,),  # la guía quedó vacía
            (1,),  # otra guía sigue usando la misma ruta
        ],
    )
    cursor.fetchall.side_effect = [[], [("2026-08-13/listado-abc123.jpg",)]]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30, origen="compras")

    assert resultado == []
    # El registro de ESTA guía sí se borró.
    assert any("DELETE FROM fotos_guia WHERE guia_id" in ll.args[0] for ll in cursor.execute.call_args_list)


def test_eliminar_compra_sin_guia_no_toca_fotos():
    # Compra viejísima sin guía (no debería quedar ninguna tras la
    # migración): se borra sin mirar fotos.
    conexion, cursor = _conexion_falsa(
        [
            (None,),  # RETURNING guia_id: borro, pero la compra no tenía guía
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30, origen="compras")

    assert resultado == []
    # El DELETE de fotos_recepcion (vacío) y el de la compra: sin guía no hay
    # fotos de comanda que mirar.
    assert cursor.execute.call_count == 2
    assert not any("fotos_guia" in ll.args[0] for ll in cursor.execute.call_args_list)


def test_eliminar_compra_rechazada_se_puede_borrar_igual_que_antes():
    conexion, cursor = _conexion_falsa(
        [
            (105,),
            (0,),
        ],
        filas_fetchall=[],
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30, origen="compras")

    assert resultado == []
    conexion.commit.assert_called_once()


def test_eliminar_compra_cancelada_en_retiro_se_puede_borrar_igual_que_antes():
    conexion, cursor = _conexion_falsa(
        [
            (105,),
            (0,),
        ],
        filas_fetchall=[],
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30, origen="compras")

    assert resultado == []
    conexion.commit.assert_called_once()


def test_eliminar_compra_recepcionada_no_se_borra():
    conexion, cursor = _conexion_falsa(
        [
            None,  # el DELETE no borro nada
            ("recepcionado", "retirado"),  # el SELECT que arma el mensaje
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            eliminar_compra(30, origen="compras")
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra ya fue recepcionada, no se puede eliminar."

    # Sin commit: la transacción entera vuelve atrás, incluido el DELETE de
    # fotos_recepcion que corre primero — la foto sigue ahí.
    assert cursor.execute.call_count == 3  # fotos_recepcion + el DELETE que no borró + el SELECT
    conexion.commit.assert_not_called()
    conexion.close.assert_called_once()


def test_eliminar_compra_no_ingresada_no_se_borra():
    # Regla fija: "No ingresó" es un registro de Depósito — el comprador no
    # lo puede hacer desaparecer borrando la compra. Y el mensaje habla de
    # eso, aunque la compra además estuviera retirada.
    conexion, cursor = _conexion_falsa(
        [
            None,  # el DELETE no borro nada
            ("no_ingresado", "retirado"),  # el SELECT que arma el mensaje
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            eliminar_compra(30, origen="compras")
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == 'Esta compra quedó registrada como "No ingresó" en Depósito, no se puede eliminar.'

    # Sin commit: la transacción entera vuelve atrás, incluido el DELETE de
    # fotos_recepcion que corre primero — la foto sigue ahí.
    assert cursor.execute.call_count == 3  # fotos_recepcion + el DELETE que no borró + el SELECT
    conexion.commit.assert_not_called()


def test_eliminar_compra_retirada_no_se_borra():
    conexion, cursor = _conexion_falsa(
        [
            None,  # el DELETE no borro nada
            ("pendiente", "retirado"),  # el SELECT que arma el mensaje
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            eliminar_compra(30, origen="compras")
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra ya fue retirada, no se puede eliminar."

    # Sin commit: la transacción entera vuelve atrás, incluido el DELETE de
    # fotos_recepcion que corre primero — la foto sigue ahí.
    assert cursor.execute.call_count == 3  # fotos_recepcion + el DELETE que no borró + el SELECT
    conexion.commit.assert_not_called()


def test_crear_compra_asigna_el_primer_punto_de_una_guia_nueva():
    conexion, cursor = _conexion_falsa(
        [
            (105,),  # SELECT id de guias_compra (ya existía o se acaba de crear)
            (0,),  # SELECT COUNT(*) de compras con esa guía: ninguna todavía
            (900,),  # el id que devuelve el INSERT de la compra
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 8, 16), 5, 200, 40, 20, 800, None, 45000.0, None, "Clark",
            segunda_por_cajon=None,
        )

    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    assert "INSERT INTO guias_compra" in consultas[0]
    assert "ON CONFLICT (fecha_operacion, proveedor_id) DO NOTHING" in consultas[0]
    assert "SELECT id FROM guias_compra" in consultas[1]
    assert "SELECT COUNT(*) FROM compras WHERE guia_id" in consultas[2]

    consulta_insert, parametros_insert = cursor.execute.call_args_list[3].args
    assert "INSERT INTO compras" in consulta_insert
    assert "guia_id" in consulta_insert
    assert "guia_punto" in consulta_insert
    assert "'pendiente'" in consulta_insert
    # guia_id, guia_punto, carga_token (None: carga manual, sin token) y la
    # SEGUNDA MAGNITUD POR CAJÓN, que desde el 20/09 tiene columna propia.
    assert parametros_insert[-4:] == (105, 1, None, None)
    conexion.commit.assert_called_once()


def test_crear_compra_suma_puntos_si_la_guia_ya_tiene_renglones():
    # Segundo (y tercer) artículo del mismo proveedor el mismo día: misma
    # guía, el punto sigue la cuenta (no vuelve a 1).
    conexion, cursor = _conexion_falsa(
        [
            (105,),  # SELECT id de guias_compra
            (2,),  # ya hay 2 compras con esa guía
            (900,),  # el id que devuelve el INSERT de la compra
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 8, 16), 6, 200, 10, 12, None, 120, None, None, "Clark",
            segunda_por_cajon=None,
        )

    _, parametros_insert = cursor.execute.call_args_list[3].args
    assert parametros_insert[-4:] == (105, 3, None, None)  # guia_id, guia_punto, carga_token


def test_crear_compras_de_comanda_guarda_todos_los_renglones_en_un_solo_commit():
    # Dos renglones de la misma comanda: todo en UNA conexión y UN commit
    # (todo-o-nada) — antes cada renglón commiteaba por su cuenta y un corte
    # de internet dejaba la comanda guardada a medias.
    conexion, cursor = _conexion_falsa(
        [
            None,  # SELECT 1 por carga_token: no existe, se guarda normal
            (105,), (0,), (900,),  # guía, punto e id del renglón 1
            (105,), (1,), (901,),  # guía, punto e id del renglón 2
        ]
    )
    renglones = [
        {
            "articulo_id": 5, "cantidad_cajones": 10, "contenido_por_cajon": 18,
            "cantidad_kilos": 180, "cantidad_fraccion": None, "segunda_por_cajon": None,
            "importe": 5000.0, "sena": None, "tipo_retiro": "Clark",
        },
        {
            "articulo_id": 6, "cantidad_cajones": 3, "contenido_por_cajon": 12,
            "cantidad_kilos": None, "cantidad_fraccion": 36, "segunda_por_cajon": None,
            "importe": None, "sena": None, "tipo_retiro": "Clark",
        },
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardo = crear_compras_de_comanda(
            date(2026, 8, 19), 200, renglones, "2026-08-19/n07p41-1.jpg", "token123"
        )

    assert guardo is True
    conexion.commit.assert_called_once()
    inserts_compras = [
        llamada for llamada in cursor.execute.call_args_list if "INSERT INTO compras" in llamada.args[0]
    ]
    assert len(inserts_compras) == 2
    # Todos los renglones llevan el mismo carga_token; la FOTO ya no va en
    # los renglones (compras.foto_ruta muerta): cuelga de la guía, una vez
    # (el ON CONFLICT absorbe el segundo renglón).
    for llamada in inserts_compras:
        # EN la tupla y no en la punta: el 20/09 `segunda_por_cajon`
        # entró después del token y el ancla en [-1] se corrió. Es la
        # misma trampa que ya había mordido con las dos fechas.
        assert "token123" in llamada.args[1]
        assert "2026-08-19/n07p41-1.jpg" not in llamada.args[1]
    inserts_fotos = [
        llamada for llamada in cursor.execute.call_args_list if "INSERT INTO fotos_guia" in llamada.args[0]
    ]
    assert len(inserts_fotos) == 2  # una por renglón, absorbidas por ON CONFLICT
    assert inserts_fotos[0].args[1] == (105, "2026-08-19/n07p41-1.jpg")


def test_crear_compras_de_comanda_con_token_ya_usado_no_inserta_nada():
    # El reintento de un guardado que YA entró (el teléfono nunca vio la
    # respuesta): no se inserta nada y se devuelve False, para responder
    # como si fuera el guardado original sin duplicar la comanda.
    conexion, cursor = _conexion_falsa([(1,)])  # SELECT 1 por carga_token: ya existe

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardo = crear_compras_de_comanda(
            date(2026, 8, 19), 200,
            [{"articulo_id": 5, "cantidad_cajones": 10, "contenido_por_cajon": 18,
              "cantidad_kilos": 180, "cantidad_fraccion": None, "segunda_por_cajon": None,
              "importe": 5000.0, "sena": None, "tipo_retiro": "Clark"}],
            None, "token123",
        )

    assert guardo is False
    assert cursor.execute.call_count == 1  # solo el SELECT del token
    conexion.commit.assert_not_called()


def test_crear_compras_de_comanda_sin_token_guarda_sin_chequear():
    # Forms viejos que quedaron abiertos de antes del cambio: sin token no
    # hay chequeo anti-duplicado, se guarda directo (como siempre).
    conexion, cursor = _conexion_falsa([(105,), (0,), (900,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardo = crear_compras_de_comanda(
            date(2026, 8, 19), 200,
            [{"articulo_id": 5, "cantidad_cajones": 10, "contenido_por_cajon": 18,
              "cantidad_kilos": 180, "cantidad_fraccion": None, "segunda_por_cajon": None,
              "importe": 5000.0, "sena": None, "tipo_retiro": "Clark"}],
            None, None,
        )

    assert guardo is True
    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    assert not any("carga_token = %s" in consulta and "SELECT" in consulta for consulta in consultas)
    conexion.commit.assert_called_once()


def test_comanda_ya_guardada_consulta_por_el_token():
    conexion, cursor = _conexion_falsa([(1,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert comanda_ya_guardada("token123") is True

    consulta, parametros = cursor.execute.call_args.args
    assert "SELECT 1 FROM compras WHERE carga_token = %s" in consulta
    assert parametros == ("token123",)


def test_comanda_ya_guardada_devuelve_false_si_no_existe():
    conexion, cursor = _conexion_falsa([None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert comanda_ya_guardada("token123") is False


def test_crear_compra_ingreso_directo_deposito_nace_recepcionada_y_retirada():
    # /deposito/ingresar: la mercadería ya está en el depósito cuando se
    # carga -- nace de una recepcionada/retirada, con las cantidades
    # reales iguales a las cargadas (no hay estimado previo).
    conexion, cursor = _conexion_falsa(
        [
            (105,),  # SELECT id de guias_compra
            (0,),  # SELECT COUNT(*) de compras con esa guía
            (900,),  # el id que devuelve el INSERT de la compra
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 8, 16), 5, 200, 40, 20, 800, None, None, None, "Clark",
            ingreso_directo_deposito=True,
            segunda_por_cajon=None,
        )

    consulta_insert, parametros_insert = cursor.execute.call_args_list[3].args
    assert "INSERT INTO compras" in consulta_insert
    assert "'recepcionado', 'retirado'" in consulta_insert
    assert "cantidad_cajones_real" in consulta_insert
    assert "contenido_por_cajon_real" in consulta_insert
    assert "cantidad_kilos_real" in consulta_insert
    assert "cantidad_fraccion_real" in consulta_insert
    assert "procesada_el" in consulta_insert
    assert "retiro_procesado_el" in consulta_insert
    assert "'ingreso_directo'" in consulta_insert
    # LA TUPLA ENTERA, no un slice desde el final. Hasta el 09/09 esto
    # decía `parametros_insert[-6:]`, y el día que el INSERT ganó dos
    # parámetros —las dos fechas de recepción— el slice se corrió y el test
    # cayó por la razón equivocada: no porque algo estuviera mal, sino
    # porque contaba desde la punta que se movió. Comparada entera, falla
    # el día que alguien agrega un campo, que es su función.
    assert parametros_insert == (
        date(2026, 8, 16), 5, 200, 40, 20, 800, None, None, None, "Clark", 105, 1,
        # Las reales, iguales a las cargadas: no hay estimado previo.
        40, 20, 800, None,
        # La segunda magnitud por cajón, A LAS DOS: el ingreso directo entra
        # ya recepcionado y copia el estimado al real.
        None, None,
        # procesada_el y retiro_procesado_el: None = now(), que es el caso
        # de /deposito/ingresar. La fecha elegible es solo de Gerencia.
        None, None,
    )
    conexion.commit.assert_called_once()


def test_el_ingreso_retroactivo_fecha_las_DOS_columnas_por_las_que_entra_al_stock():
    """`procesada_el` y `retiro_procesado_el`, no `fecha_operacion`.

    La fecha de OPERACIÓN no la mira ninguna de las dos cuentas: el total
    filtra por `COALESCE(procesada_el, fecha_operacion)` y el lote del FIFO
    se ordena por `procesada_el`. Fechar solo la de operación deja la
    mercadería entrando el día en que se cargó, que es justo lo que esta
    pantalla existe para evitar.

    Y `cargado_el` NO va en el INSERT: se queda con su `now()`, que es lo
    único que después distingue esta compra de una normal.
    """
    from app.db import crear_compra

    conexion, cursor = _conexion_falsa([(date(2026, 9, 5),), (105,), (0,), (900,)])
    momento = datetime(2026, 9, 7, 12, 0)

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 9, 7), 5, 200, 10, 16, 160, None, 0, None, "Clark",
            ingreso_directo_deposito=True, recepcionada_el=momento,
            segunda_por_cajon=None,
        )

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "INSERT INTO compras")
    assert "COALESCE(%s, now()), COALESCE(%s, now()), 'ingreso_directo'" in consulta
    # Las dos últimas son la fecha elegida, y son la MISMA.
    assert parametros[-2:] == (momento, momento)
    assert "cargado_el" not in consulta
    # El importe 0 viaja tal cual: no se convierte en NULL por el camino.
    assert parametros[7] == 0


def test_el_ingreso_retroactivo_RECHAZA_una_fecha_del_dia_del_corte_o_anterior():
    """La novena aparición de la asimetría del día del corte.

    El lote del FIFO pide que la fecha argentina de la recepción sea
    POSTERIOR al corte, y el total no tiene piso: fechada el día del corte
    o antes, la compra suma al total y NO existe como lote. Medido el
    09/09 contra el esquema real con el corte en 05/09.

    El corte se lee de `corte_modelo` con `_fecha_corte` —la misma que el
    resto—, no escrito a mano: es distinto en cada empresa.
    """
    from app.db import crear_compra

    for dia, tiene_que_entrar in ((date(2026, 9, 6), True),
                                  (date(2026, 9, 5), False),
                                  (date(2026, 9, 4), False)):
        conexion, cursor = _conexion_falsa([(date(2026, 9, 5),), (105,), (0,), (900,)])
        with patch("app.db.obtener_conexion", return_value=conexion):
            if tiene_que_entrar:
                crear_compra(dia, 5, 200, 10, 16, 160, None, 0, None, "Clark",
                             ingreso_directo_deposito=True,
                             recepcionada_el=datetime(dia.year, dia.month, dia.day, 12, 0),
                             segunda_por_cajon=None)
            else:
                with pytest.raises(ValueError) as rechazo:
                    crear_compra(dia, 5, 200, 10, 16, 160, None, 0, None, "Clark",
                                 ingreso_directo_deposito=True,
                                 recepcionada_el=datetime(dia.year, dia.month, dia.day, 12, 0),
                             segunda_por_cajon=None)
                assert "POSTERIOR al corte" in str(rechazo.value)
                assert "05/09/2026" in str(rechazo.value)


def test_la_fecha_de_recepcion_NO_se_puede_elegir_en_una_carga_normal():
    """La perilla es solo del ingreso directo. En la carga normal la compra
    nace 'pendiente' y la fecha de recepción la pone Depósito al recibirla:
    dejarla elegir ahí sería fechar una recepción que todavía no pasó."""
    from app.db import crear_compra

    conexion, _ = _conexion_falsa([(105,), (0,), (900,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as rechazo:
            crear_compra(date(2026, 9, 7), 5, 200, 10, 16, 160, None, None, None, "Clark",
                         recepcionada_el=datetime(2026, 9, 7, 12, 0),
                         segunda_por_cajon=None)
    assert "solo se puede elegir en un ingreso directo" in str(rechazo.value)


def test_crear_compra_sin_ingreso_directo_sigue_igual_que_antes():
    # Default False: comportamiento intacto para los 4 flujos del
    # comprador (manual, foto, múltiples fotos, listado) -- no se les
    # tocó ni un carácter.
    conexion, cursor = _conexion_falsa(
        [
            (105,),
            (0,),
            (900,),  # el id que devuelve el INSERT de la compra
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 8, 16), 5, 200, 40, 20, 800, None, 45000.0, None, "Clark", segunda_por_cajon=None)

    consulta_insert, _ = cursor.execute.call_args_list[3].args
    assert "'pendiente', 'pendiente'" in consulta_insert
    assert "cantidad_cajones_real" not in consulta_insert
    assert "ingreso_directo" not in consulta_insert


def test_compra_tiene_cantidad_bloqueada():
    # SOLO Depósito bloquea (regla 19/08/2026): recepcionada, rechazada o
    # nunca ingresada. El retiro de Logística NO bloquea nada — hasta que
    # la mercadería entra a Depósito, el comprador puede corregir su compra.
    assert compra_tiene_cantidad_bloqueada("recepcionado") is True
    assert compra_tiene_cantidad_bloqueada("rechazado") is True
    assert compra_tiene_cantidad_bloqueada("no_ingresado") is True
    assert compra_tiene_cantidad_bloqueada("pendiente") is False
    assert compra_tiene_cantidad_bloqueada(None) is False


def test_compra_tiene_precio_bloqueado():
    assert compra_tiene_precio_bloqueado("rechazado") is True
    assert compra_tiene_precio_bloqueado("no_ingresado") is True
    # A propósito NO mira estado_retiro: retirada o recepcionada no bloquean el precio.
    assert compra_tiene_precio_bloqueado("recepcionado") is False
    assert compra_tiene_precio_bloqueado("pendiente") is False
    assert compra_tiene_precio_bloqueado(None) is False


def test_actualizar_cantidad_compra_pisa_los_valores():
    conexion, cursor = _conexion_falsa([(None, None, None)])  # SELECT estado, estado_retiro, retiro_origen

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark", segunda_por_cajon=None)

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    assert "UPDATE compras" in consulta_update
    assert "importe" not in consulta_update
    assert "sena" not in consulta_update
    assert parametros_update[-1] == 30
    conexion.commit.assert_called_once()


def test_actualizar_cantidad_compra_recepcionada_no_se_edita():
    conexion, cursor = _conexion_falsa([("recepcionado", "retirado", "logistica")])  # SELECT estado, estado_retiro, retiro_origen

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark", segunda_por_cajon=None)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra ya fue recepcionada, no se puede editar la cantidad."

    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_actualizar_cantidad_compra_retirada_por_logistica_SI_se_edita():
    # Regla 19/08/2026: el retiro de Logística NO bloquea la edición — solo
    # Depósito bloquea. Un proveedor puede llamar para cancelar cantidad
    # antes de que la mercadería entre al depósito.
    conexion, cursor = _conexion_falsa([("pendiente", "retirado", "logistica")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark", segunda_por_cajon=None)

    consulta_update = cursor.execute.call_args_list[1].args[0]
    assert "UPDATE compras" in consulta_update
    # El retiro que Logística ya marcó no se toca al editar.
    assert "estado_retiro" not in consulta_update
    conexion.commit.assert_called_once()


def test_actualizar_cantidad_compra_rechazada_no_se_edita_aunque_nunca_se_haya_retirado():
    # Rechazada en Depósito, con el retiro cancelado antes en Logística
    # (así que el auto-retiro nunca la marcó 'retirado'): esa historia ya
    # terminó y no entra al costeo, se bloquea igual.
    conexion, cursor = _conexion_falsa([("rechazado", "cancelado", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark", segunda_por_cajon=None)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra tuvo un rechazo total, no se puede editar la cantidad."

    conexion.commit.assert_not_called()


def test_actualizar_cantidad_compra_no_ingresada_no_se_edita():
    conexion, cursor = _conexion_falsa([("no_ingresado", "retirado", "logistica")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark", segunda_por_cajon=None)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra nunca ingresó al depósito, no se puede editar la cantidad."

    conexion.commit.assert_not_called()


def test_actualizar_precio_compra_pisa_importe_y_sena():
    conexion, cursor = _conexion_falsa([("recepcionado",)])  # SELECT estado

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_precio_compra(30, 55000.0, 1000.0)

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    assert "UPDATE compras SET importe = %s, sena = %s" in consulta_update
    # Los cuatro del medio son el sello del importe (ver _sello_del_importe):
    # el mismo valor cuatro veces, que son los dos CASE con sus dos ramas.
    assert parametros_update == (55000.0, 1000.0, 55000.0, 55000.0, 55000.0, 55000.0, 30)
    conexion.commit.assert_called_once()


def test_actualizar_precio_compra_se_puede_editar_aunque_este_retirada_o_recepcionada():
    # A diferencia de la cantidad: retirada y/o recepcionada NO bloquean
    # el precio — el comprador puede renegociar con el proveedor después
    # de que la mercadería ya llegó.
    conexion, cursor = _conexion_falsa([("recepcionado",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_precio_compra(30, 60000.0, None)

    conexion.commit.assert_called_once()


def test_actualizar_precio_compra_rechazada_no_se_edita():
    conexion, cursor = _conexion_falsa([("rechazado",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_precio_compra(30, 60000.0, None)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra tuvo un rechazo total, no se puede editar el precio."

    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_actualizar_precio_compra_no_ingresada_no_se_edita():
    conexion, cursor = _conexion_falsa([("no_ingresado",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_precio_compra(30, 60000.0, None)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra nunca ingresó al depósito, no se puede editar el precio."

    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_buscar_compras_usa_el_real_si_existe():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_compras(date(2026, 8, 15), date(2026, 8, 16))

    # Por CONTENIDO y no por posición: `buscar_compras` ejecuta también la
    # lectura del corte, y buscar "la última" haría que cualquier sentencia
    # nueva rompa un test que no habla de ella.
    consulta = _sql_que_contiene(cursor, "FROM compras c")
    assert "COALESCE(c.cantidad_cajones_real, c.cantidad_cajones) AS cantidad_cajones" in consulta
    assert "COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon) AS contenido_por_cajon" in consulta
    assert "COALESCE(c.cantidad_kilos_real, c.cantidad_kilos) AS cantidad_kilos" in consulta
    assert "COALESCE(c.cantidad_fraccion_real, c.cantidad_fraccion) AS cantidad_fraccion" in consulta


def test_listar_compras_para_costeo_usa_el_real_si_existe_y_excluye_rechazadas():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_para_costeo(date(2026, 8, 1), date(2026, 8, 16))

    consulta = cursor.execute.call_args[0][0]
    assert "COALESCE(c.cantidad_cajones_real, c.cantidad_cajones) AS cantidad_cajones" in consulta
    assert "COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon) AS contenido_por_cajon" in consulta
    assert "COALESCE(c.cantidad_kilos_real, c.cantidad_kilos) AS cantidad_kilos" in consulta
    # Una compra rechazada no se recibió: no puede ensuciar el costo promedio.
    assert "estado IS DISTINCT FROM 'rechazado'" in consulta
    # Una compra que nunca ingresó al depósito tampoco es mercadería real.
    assert "estado IS DISTINCT FROM 'no_ingresado'" in consulta
    # Para el costeo manda SOLO el veredicto de Depósito: lo que diga
    # Logística no cuenta — un retiro cancelado NO saca la compra del
    # cálculo (regla fija del 19/08/2026).
    assert "estado_retiro" not in consulta


def test_listar_compras_sin_precio_usa_el_real_si_existe():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_sin_precio()

    consulta = cursor.execute.call_args[0][0]
    assert "COALESCE(c.cantidad_cajones_real, c.cantidad_cajones) AS cantidad_cajones" in consulta
    assert "COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon) AS contenido_por_cajon" in consulta


def test_listar_compras_sin_precio_excluye_rechazada_no_ingresada_y_retiro_cancelado():
    # Esa mercadería nunca se va a vender -- no tiene sentido perseguirle
    # el costo aunque el importe siga en NULL.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_sin_precio()

    consulta = cursor.execute.call_args[0][0]
    assert "c.estado IN ('pendiente', 'recepcionado')" in consulta
    assert "c.estado_retiro IN ('pendiente', 'retirado')" in consulta


def test_contar_compras_sin_precio_mismo_filtro_que_listar_y_trae_la_mas_vieja():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(4, date(2026, 7, 30))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_compras_sin_precio()

    assert resultado == {"casos": 4, "mas_viejo": date(2026, 7, 30)}
    consulta = cursor.execute.call_args[0][0]
    assert "SELECT COUNT(*), MIN(c.fecha_operacion)" in consulta
    assert "c.importe IS NULL" in consulta
    assert "c.estado IN ('pendiente', 'recepcionado')" in consulta
    assert "c.estado_retiro IN ('pendiente', 'retirado')" in consulta


def test_contar_compras_sin_precio_no_tiene_ventana_de_tiempo():
    # SIN ventana a propósito: una compra sin precio se avisa el mismo día y
    # sigue avisando hasta que se cargue el precio. La versión vieja
    # (contar_compras_sin_precio_viejas) filtraba por fecha y no por estado:
    # contaba rechazadas viejas y se perdía las de hoy.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_compras_sin_precio()

    consulta = cursor.execute.call_args[0][0]
    assert "fecha_operacion <=" not in consulta
    assert "fecha_operacion >=" not in consulta
    assert cursor.execute.call_args.args[1:] == ()


def test_listar_compras_pendientes_recepcion_filtra_por_estado_y_guia():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_pendientes_recepcion()

    consulta = cursor.execute.call_args[0][0]
    assert "estado = 'pendiente'" in consulta
    assert "guia_id IS NOT NULL" in consulta
    # La fecha de la partida viaja a la pantalla: Depósito tiene que ver
    # de un vistazo si lo que recepciona es de un día anterior.
    assert "c.fecha_operacion" in consulta
    # Sin real-si-existe acá: esta pantalla necesita el estimado en crudo
    # para prellenar los inputs (ninguna compra pendiente tiene real todavía).
    assert "COALESCE" not in consulta


def test_recepcionar_compra_articulo_por_kilo_toma_kilos_por_bulto_y_deriva_el_total():
    # Depósito pesa UN bulto en la balanza (no toda la carga): valor_real
    # para un artículo por kilo es directamente contenido_por_cajon_real,
    # y cantidad_kilos_real se deriva acá (cajones × valor_real).
    # 3 fetchone: SELECT unidad_compra, el SELECT estado_retiro de
    # _auto_retirar_si_corresponde (acá 'pendiente', se auto-retira), y la
    # consulta de la marca "viene armada" — que acá viene en None, o sea la
    # compra normal de siempre: llega el cajón del proveedor.
    conexion, cursor = _conexion_falsa([("kilo", 760.0, None), ("pendiente",), (1, None, 38.0, date(2026, 8, 25), None, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso, numero_guia = recepcionar_compra(30, cantidad_cajones_real=38, valor_real=20)

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    assert "estado = 'recepcionado'" in consulta_update
    assert "procesada_el = now()" in consulta_update
    (cajones, contenido, kilos, fraccion, segunda_cajon,
         rechazada, motivo, compra_id) = parametros_update
    assert cajones == 38
    assert contenido == 20  # tomado directo, sin dividir
    assert kilos == 760  # 38 × 20, derivado
    assert fraccion is None
    # Recepción normal: sin rechazo parcial (y borra cualquier resto viejo).
    assert rechazada is None
    assert motivo is None
    assert compra_id == 30
    assert (aviso, numero_guia) == (None, None)
    # Se auto-retira: UPDATE con estado_retiro = 'retirado', origen 'deposito'.
    # Por FRAGMENTO y no por posición: la consulta de la marca entró después
    # y correr los índices rompería tests que no hablan de eso.
    consulta_retiro, parametros_retiro = _sql_y_parametros_que_contienen(cursor, "estado_retiro = 'retirado'")
    assert "estado_retiro = 'retirado'" in consulta_retiro
    assert "retiro_origen = 'deposito'" in consulta_retiro
    assert parametros_retiro == (30,)
    conexion.commit.assert_called_once()


def test_recepcionar_compra_articulo_por_unidad_toma_unidades_por_cajon_y_deriva_el_total():
    # Depósito cuenta UN cajón (no toda la carga junta) — mismo criterio
    # que kilo: valor_real es directamente contenido_por_cajon_real, y
    # cantidad_fraccion_real (el total) se deriva acá (cajones × valor_real).
    conexion, cursor = _conexion_falsa([("unidad", None, 760.0), ("pendiente",), (1, None, 38.0, date(2026, 8, 25), None, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(31, cantidad_cajones_real=10, valor_real=118)

    _, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    (cajones, contenido, kilos, fraccion, segunda_cajon,
         rechazada, motivo, compra_id) = parametros_update
    assert contenido == 118  # tomado directo, sin dividir
    assert kilos is None
    assert fraccion == 1180  # 10 × 118, derivado


def test_recepcionar_compra_ya_retirada_no_pisa_el_auto_retiro():
    conexion, cursor = _conexion_falsa([("kilo", 760.0, None), ("retirado",), (1, None, 38.0, date(2026, 8, 25), None, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso, numero_guia = recepcionar_compra(30, cantidad_cajones_real=38, valor_real=20)

    assert (aviso, numero_guia) == (None, None)
    # Lo que se verifica es que NO haya un UPDATE de estado_retiro de más, no
    # cuántas sentencias hubo: contarlas hacía que cualquier consulta nueva
    # rompiera este test, que no habla de eso.
    assert not [c for c in cursor.execute.call_args_list
                if "estado_retiro = 'retirado'" in c.args[0]]


def test_recepcionar_compra_cancelada_en_logistica_avisa_y_no_la_pisa():
    conexion, cursor = _conexion_falsa([("kilo", 760.0, None), ("cancelado",), (1, None, 38.0, date(2026, 8, 25), None, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso, _ = recepcionar_compra(30, cantidad_cajones_real=38, valor_real=20)

    assert aviso == "Esta compra figuraba cancelada en Logística."
    # Sin UPDATE de estado_retiro: se corta después del SELECT.
    assert not [c for c in cursor.execute.call_args_list
                if "estado_retiro = 'retirado'" in c.args[0]]
    conexion.commit.assert_called_once()


def test_corregir_recepcion_compra_articulo_por_kilo_deriva_el_total():
    conexion, cursor = _conexion_falsa([("recepcionado", "kilo", 760.0, None)])
    # Sin guías R en origen colgadas de esta compra: el camino normal.
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(30, cantidad_cajones_real=30, valor_real=25)

    # Por FRAGMENTO y no por posición: contar las sentencias hacía que
    # cualquier consulta nueva rompiera este test, que no habla de eso. Es
    # para lo que existe el helper.
    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    assert "cantidad_cajones_real = %s" in consulta_update
    assert "contenido_por_cajon_real = %s" in consulta_update
    # A diferencia de recepcionar_compra, NO toca estado ni procesada_el.
    assert "estado" not in consulta_update
    assert "procesada_el" not in consulta_update
    (cajones, contenido, kilos, fraccion, segunda_cajon,
         rechazada, motivo, compra_id) = parametros_update
    assert cajones == 30
    assert contenido == 25
    assert kilos == 750  # 30 × 25
    assert fraccion is None
    assert rechazada is None
    assert motivo is None
    assert compra_id == 30
    conexion.commit.assert_called_once()


def test_corregir_recepcion_compra_articulo_por_unidad_toma_unidades_por_cajon_y_deriva_el_total():
    # Ej. la Palta con "3u" mal cargado: la corrección es 80 por cajón
    # (lo que Depósito mira), no 2400 en total.
    conexion, cursor = _conexion_falsa([("recepcionado", "unidad", None, 760.0)])
    cursor.fetchall.return_value = []   # sin guía R en origen: el camino normal

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(30, cantidad_cajones_real=30, valor_real=80)

    _, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    (cajones, contenido, kilos, fraccion, segunda_cajon,
         rechazada, motivo, compra_id) = parametros_update
    assert contenido == 80  # tomado directo, sin dividir
    assert kilos is None
    assert fraccion == 2400  # 30 × 80, derivado


def test_corregir_recepcion_compra_bloqueada_si_no_esta_recepcionada():
    conexion, cursor = _conexion_falsa([("pendiente", "unidad", None, 2400.0)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            corregir_recepcion_compra(30, cantidad_cajones_real=30, valor_real=2400)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert "no está recepcionada" in str(error)

    # Solo el SELECT — nunca llega a ejecutar el UPDATE ni a hacer commit.
    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_recepcionar_compra_con_rechazo_parcial_guarda_el_registro():
    # Llegaron 10 y se rechazaron 2: la ruta ya manda los 8 aceptados como
    # cantidad_cajones_real (es la que usa todo el costeo, sin cuentas
    # nuevas) y el rechazo queda como registro aparte.
    conexion, cursor = _conexion_falsa(
        [("kilo", 200.0, None), ("pendiente",), (1, None, 8.0, date(2026, 8, 25), None, None)]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(
            30, cantidad_cajones_real=8, valor_real=20,
            cantidad_cajones_rechazada=2, motivo_rechazo="podrido",
        )

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    assert "cantidad_cajones_rechazada = %s" in consulta_update
    assert "motivo_rechazo = %s" in consulta_update
    (cajones, contenido, kilos, fraccion, segunda_cajon,
         rechazada, motivo, compra_id) = parametros_update
    assert cajones == 8  # los aceptados, no los llegados
    assert kilos == 160  # 8 × 20: el total real sale de los aceptados
    assert rechazada == 2
    assert motivo == "podrido"
    conexion.commit.assert_called_once()


def test_corregir_recepcion_compra_corrige_el_rechazo_parcial():
    conexion, cursor = _conexion_falsa([("recepcionado", "kilo", 760.0, None)])
    cursor.fetchall.return_value = []   # sin guía R en origen: el camino normal

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(
            30, cantidad_cajones_real=7, valor_real=25,
            cantidad_cajones_rechazada=3, motivo_rechazo="golpeado",
        )

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    assert "cantidad_cajones_rechazada = %s" in consulta_update
    assert "motivo_rechazo = %s" in consulta_update
    (cajones, contenido, kilos, fraccion, segunda_cajon,
         rechazada, motivo, compra_id) = parametros_update
    assert cajones == 7
    assert rechazada == 3
    assert motivo == "golpeado"


def test_rechazar_compra_marca_estado_y_no_toca_los_reales():
    conexion, cursor = _conexion_falsa([("pendiente",)])  # SELECT estado_retiro (auto-retiro)

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso = rechazar_compra(32)

    consulta, parametros = cursor.execute.call_args_list[0].args
    assert "estado = 'rechazado'" in consulta
    assert "procesada_el = now()" in consulta
    assert "cantidad_cajones_real" not in consulta
    assert parametros == (32,)
    assert aviso is None
    conexion.commit.assert_called_once()


def test_rechazar_compra_cancelada_en_logistica_avisa_y_no_la_pisa():
    conexion, cursor = _conexion_falsa([("cancelado",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso = rechazar_compra(32)

    assert aviso == "Esta compra figuraba cancelada en Logística."


def test_marcar_compra_no_ingresada_marca_estado_y_no_toca_el_retiro():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_compra_no_ingresada(32)

    # Un solo UPDATE — a diferencia de recepcionar/rechazar, no llama a
    # _auto_retirar_si_corresponde (no hay SELECT ni UPDATE de estado_retiro).
    assert cursor.execute.call_count == 1
    consulta, parametros = cursor.execute.call_args[0]
    assert "estado = 'no_ingresado'" in consulta
    assert "procesada_el = now()" in consulta
    assert "estado_retiro" not in consulta
    assert parametros == (32,)
    conexion.commit.assert_called_once()


def test_listar_compras_pendientes_retiro_filtra_por_tipo_y_estado_retiro():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_pendientes_retiro("Clark")

    consulta, parametros = cursor.execute.call_args[0]
    assert "c.tipo_retiro = %s" in consulta
    assert "estado_retiro IS DISTINCT FROM 'retirado'" in consulta
    assert "estado_retiro IS DISTINCT FROM 'cancelado'" in consulta
    assert "ORDER BY p.codigo_puesto" in consulta
    assert parametros == ("Clark",)


def test_marcar_compra_retirada_guarda_origen():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_compra_retirada(30, "logistica")

    consulta, parametros = cursor.execute.call_args[0]
    assert "estado_retiro = 'retirado'" in consulta
    assert "retiro_procesado_el = now()" in consulta
    assert "cantidad_cajones_retirada = %s" in consulta
    assert parametros == ("logistica", None, 30)
    conexion.commit.assert_called_once()


def test_marcar_compra_retirada_guarda_cantidad_cajones_retirada():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_compra_retirada(30, "logistica", 8.5)

    _, parametros = cursor.execute.call_args[0]
    assert parametros == ("logistica", 8.5, 30)
    conexion.commit.assert_called_once()


def test_marcar_compra_cancelada_guarda_origen():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_compra_cancelada(30, "logistica")

    consulta, parametros = cursor.execute.call_args[0]
    assert "estado_retiro = 'cancelado'" in consulta
    assert parametros == ("logistica", 30)
    conexion.commit.assert_called_once()


def test_compra_tiene_deshacer_retiro_bloqueado():
    assert compra_tiene_deshacer_retiro_bloqueado("recepcionado") is True
    assert compra_tiene_deshacer_retiro_bloqueado("rechazado") is True
    # no_ingresado NO bloquea: significa que nada llegó, no hay motivo
    # para impedir que Logística corrija un Retirado/Cancelado por error.
    assert compra_tiene_deshacer_retiro_bloqueado("no_ingresado") is False
    assert compra_tiene_deshacer_retiro_bloqueado("pendiente") is False
    assert compra_tiene_deshacer_retiro_bloqueado(None) is False


def test_deshacer_retiro_compra_vuelve_todo_a_pendiente():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("pendiente",)])  # SELECT estado

    with patch("app.db.obtener_conexion", return_value=conexion):
        deshacer_retiro_compra(30)

    consulta, parametros = cursor.execute.call_args_list[1].args
    assert "estado_retiro = 'pendiente'" in consulta
    assert "retiro_procesado_el = NULL" in consulta
    assert "retiro_origen = NULL" in consulta
    assert "cantidad_cajones_retirada = NULL" in consulta
    assert parametros == (30,)
    conexion.commit.assert_called_once()


def test_deshacer_retiro_compra_bloqueado_si_ya_paso_por_deposito():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("recepcionado",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            deshacer_retiro_compra(30)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert "no se puede deshacer" in str(error)

    # Solo el SELECT — nunca llega a ejecutar el UPDATE ni a hacer commit.
    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_buscar_compras_con_limite_agrega_limit_al_final():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_compras(date(2026, 8, 1), date(2026, 8, 6), limite=501)

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "FROM compras c")
    assert "LIMIT %s" in consulta
    assert parametros[-1] == 501


def test_contar_compras_buscadas_usa_los_mismos_filtros_que_la_busqueda():
    conexion, cursor = _conexion_falsa([(1234,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        total = contar_compras_buscadas(date(2026, 8, 1), date(2026, 8, 6), proveedor_id=7, articulo_id=5)

    assert total == 1234
    consulta, parametros = cursor.execute.call_args.args
    assert "COUNT(*)" in consulta
    assert "c.fecha_operacion BETWEEN %s AND %s" in consulta
    assert "c.proveedor_id = %s" in consulta
    assert "c.articulo_id = %s" in consulta
    assert parametros == [date(2026, 8, 1), date(2026, 8, 6), 7, 5]


def test_contar_retiros_buscados_incluye_el_criterio_de_pendiente():
    conexion, cursor = _conexion_falsa([(88,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        total = contar_retiros_buscados(date(2026, 8, 1), date(2026, 8, 6), estado_retiro="pendiente")

    assert total == 88
    consulta = cursor.execute.call_args.args[0]
    assert "COUNT(*)" in consulta
    assert "IS DISTINCT FROM 'retirado'" in consulta


def test_contar_stock_vacios_negativos_usa_la_misma_cuenta_que_el_stock():
    conexion, cursor = _conexion_falsa([(1,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        casos = contar_stock_vacios_negativos()

    assert casos == 1
    consulta = cursor.execute.call_args.args[0]
    # recibidos − devueltos + ajustes, sin anulados: idéntico a stock_vacios().
    assert consulta.count("anulado_el IS NULL") == 3
    assert "FROM ajustes_vacios" in consulta
    assert "< 0" in consulta


def test_el_historial_de_precios_FILTRA_POR_CLIENTE_y_ordena_por_vigencia():
    """La ficha viene de la query string, así que la guarda va en el SELECT.

    Sin `cliente_id` en el WHERE, un id de otra ficha devuelve el historial de
    precios de otro cliente — y la pantalla no puede ser la única que lo
    impida, porque el que arma la URL no pasa por la pantalla.

    EL ORDEN NO LLEVA DESEMPATE y eso es correcto: el unique
    (ficha_id, vigente_desde) garantiza que no haya dos filas del mismo día
    para la misma ficha, así que `vigente_desde DESC` ya es determinista.
    """
    from app.db import listar_historial_de_precios_de_ficha

    conexion, cursor = _conexion_falsa(filas_fetchall=[])
    cursor.description = [("precio",), ("vigente_desde",), ("creado_en",), ("foto_ruta",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_historial_de_precios_de_ficha(901, 7)

    consulta, parametros = cursor.execute.call_args.args
    assert "WHERE ficha_id = %s AND cliente_id = %s" in " ".join(consulta.split())
    assert parametros == (901, 7)
    # Y las CUATRO columnas: `creado_en` al lado de `vigente_desde` es todo el
    # punto de esta consulta — una sola de las dos no dice si hubo retroactivo.
    for columna in ("precio", "vigente_desde", "creado_en", "foto_ruta"):
        assert columna in consulta, columna
    assert "ORDER BY vigente_desde DESC" in " ".join(consulta.split())


def test_contar_articulos_comprados_incotizables_pide_ficha_y_precio_vigente():
    conexion, cursor = _conexion_falsa([(4,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        casos = contar_articulos_comprados_incotizables(date(2026, 7, 30), date(2026, 8, 6))

    assert casos == 4
    consulta, parametros = cursor.execute.call_args.args
    assert "FROM fichas_logistica" in consulta
    assert "FROM precios_venta_historial" in consulta
    assert "vigente_desde <= %s" in consulta
    # EL ORDEN ES (hoy, desde) y no al revés: desde el 12/09 la marca
    # `sin_precio` vive en el SELECT del bloque interno, que textualmente va
    # ANTES del FROM donde está la ventana, y los %s se ligan por posición.
    #
    # Este assert protege de que alguien cambie la LLAMADA, no de que alguien
    # reordene el SQL: con un cursor falso las dos cosas pasan igual
    # (corolario 40). Que el orden sea el correcto se verificó corriendo la
    # consulta contra db/esquema_completo.sql con los casos plantados, que es
    # lo único que lo puede decir — son dos fechas, así que invertirlas no da
    # error: da otro resultado.
    assert parametros == (date(2026, 8, 6), date(2026, 7, 30))


def test_el_ORDEN_DE_LOS_PARAMETROS_de_incotizables_LO_FIJA_EL_TEXTO_del_SQL():
    """Dos fechas invertidas no dan error: dan otro resultado, y eso no se ve.

    El test de acá arriba fija la LLAMADA, y con un cursor falso eso pasa
    igual con el SQL reordenado (corolario 40): el residuo es que alguien
    mueva la marca `sin_precio` fuera del SELECT, o la ventana al principio, y
    los dos `%s` se liguen al revés sin que nada se queje — la ventana se
    recortaría con `hoy` y el precio se miraría vigente desde hace una semana.
    Ninguna de las dos consultas fallaría; las dos devolverían otra cosa.

    Esto ata las dos mitades: QUÉ POSICIÓN ocupa cada `%s` en el texto, y que
    los dos llamadores pasen (hoy, desde) en ese orden. Movida una sola de las
    dos, el test cae.

    Se cuentan los `%s` ANTERIORES a cada cláusula y no se compara el texto
    entero: así el test sobrevive a que alguien reformatee la consulta, que es
    lo que pasa siempre, y cae solo cuando cambia lo que importa.
    """
    from app.db import _SQL_INCOTIZABLES

    assert _SQL_INCOTIZABLES.count("%s") == 2, "apareció o desapareció un parámetro"
    antes_del_precio = _SQL_INCOTIZABLES[
        :_SQL_INCOTIZABLES.index("vigente_desde <= %s")].count("%s")
    antes_de_la_ventana = _SQL_INCOTIZABLES[
        :_SQL_INCOTIZABLES.index("fecha_operacion >= %s")].count("%s")
    assert antes_del_precio == 0, "el %s del precio vigente ya no es el PRIMERO"
    assert antes_de_la_ventana == 1, "el %s de la ventana ya no es el SEGUNDO"

    # Y LOS DOS LLAMADORES, no solo el que tenía test: comparten el SQL, así
    # que un orden equivocado en uno es el mismo bug en los dos.
    desde, hoy = date(2026, 7, 30), date(2026, 8, 6)
    for funcion, falsa in (
        (contar_articulos_comprados_incotizables, dict(filas_fetchone=[(4,)])),
        (listar_articulos_comprados_incotizables, dict(filas_fetchall=[])),
    ):
        conexion, cursor = _conexion_falsa(**falsa)
        cursor.description = [("articulo",), ("sin_ficha",), ("sin_precio",)]
        with patch("app.db.obtener_conexion", return_value=conexion):
            funcion(desde, hoy)
        _, parametros = cursor.execute.call_args.args
        assert parametros == (hoy, desde), funcion.__name__


def test_contar_senas_pendientes_viejas_usa_el_criterio_de_la_pantalla():
    conexion, cursor = _conexion_falsa([(5, date(2026, 7, 28))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_senas_pendientes_viejas(date(2026, 7, 30))

    assert resultado == {"casos": 5, "mas_viejo": date(2026, 7, 28)}
    consulta, parametros = cursor.execute.call_args.args
    # Mismo "pendiente" que Pendientes de Pago: 3 cierres NULL y sin anular.
    assert "sena_pagada_el IS NULL" in consulta
    assert "sena_vale_el IS NULL" in consulta
    assert "sena_anulada_el IS NULL" in consulta
    assert "anulado_el IS NULL" in consulta
    assert "v.creado_en < ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')" in consulta
    assert parametros == (date(2026, 7, 30),)


def test_contar_retiros_pendientes_viejos_usa_el_criterio_de_la_pantalla():
    conexion, cursor = _conexion_falsa([(7, date(2026, 8, 1))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_retiros_pendientes_viejos(date(2026, 8, 4))

    assert resultado == {"casos": 7, "mas_viejo": date(2026, 8, 1)}
    consulta, parametros = cursor.execute.call_args.args
    # Mismo "pendiente" que la pantalla de Retiro: los NULL raros cuentan.
    assert "IS DISTINCT FROM 'retirado'" in consulta
    assert "IS DISTINCT FROM 'cancelado'" in consulta
    assert "MIN(fecha_operacion)" in consulta
    assert "fecha_operacion <= %s" in consulta
    assert parametros == (date(2026, 8, 4),)


def test_contar_recepciones_pendientes_viejas_usa_el_criterio_de_la_pantalla():
    conexion, cursor = _conexion_falsa([(3, date(2026, 8, 2))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_recepciones_pendientes_viejas(date(2026, 8, 4))

    assert resultado == {"casos": 3, "mas_viejo": date(2026, 8, 2)}
    consulta, parametros = cursor.execute.call_args.args
    assert "estado = 'pendiente'" in consulta
    assert "guia_id IS NOT NULL" in consulta
    assert "MIN(fecha_operacion)" in consulta
    assert parametros == (date(2026, 8, 4),)


def test_listar_compras_pendientes_retiro_trae_la_fecha_de_operacion():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_pendientes_retiro("Clark")

    consulta = cursor.execute.call_args.args[0]
    assert "c.fecha_operacion" in consulta


def test_listar_compras_procesadas_hoy_retiro_filtra_por_tipo_y_fecha():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_procesadas_hoy_retiro("Clark", date(2026, 8, 17))

    consulta, parametros = cursor.execute.call_args[0]
    assert "c.tipo_retiro = %s" in consulta
    assert "estado_retiro IN ('retirado', 'cancelado')" in consulta
    # Rango sargable (>= fecha AND < fecha+1) en vez de ::date, para
    # que la consulta pueda usar el índice de retiro_procesado_el.
    assert "c.retiro_procesado_el >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND c.retiro_procesado_el < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')" in consulta
    assert "::date =" not in consulta
    assert "ORDER BY c.retiro_procesado_el DESC" in consulta
    assert parametros == ("Clark", date(2026, 8, 17), date(2026, 8, 17))


def test_compra_tiene_deshacer_recepcion_bloqueado():
    # Recepcionar escribe cantidades reales y crea un lote de stock: eso
    # no se deshace desde Recepción, se corrige por Gerencia. El rechazo
    # parcial también queda 'recepcionado', así que cae del mismo lado.
    assert compra_tiene_deshacer_recepcion_bloqueado("recepcionado") is True
    # no_ingresado y rechazado sí se pueden deshacer: ninguno de los dos
    # escribió un valor real ni creó un lote, no hay nada que se pierda.
    assert compra_tiene_deshacer_recepcion_bloqueado("rechazado") is False
    assert compra_tiene_deshacer_recepcion_bloqueado("no_ingresado") is False
    assert compra_tiene_deshacer_recepcion_bloqueado("pendiente") is False
    assert compra_tiene_deshacer_recepcion_bloqueado(None) is False


def test_compra_tiene_deshacer_retiro_bloqueado_no_acompana_al_de_recepcion():
    # Las dos funciones devolvían ("recepcionado", "rechazado") y ahora la
    # de Recepción dejó solo "recepcionado". Son DOS reglas distintas que
    # coincidían en el valor: mientras la compra está rechazada la
    # mercadería sí llegó al depósito, así que Logística no tiene que
    # poder desmarcar ese retiro. Un grep del par encuentra las dos y
    # tienta a cambiarlas juntas — este test es el que lo frena.
    assert compra_tiene_deshacer_retiro_bloqueado("rechazado") is True
    assert compra_tiene_deshacer_recepcion_bloqueado("rechazado") is False


def test_deshacer_procesado_compra_vuelve_todo_a_pendiente():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("no_ingresado", None)])  # SELECT estado, retiro_origen

    with patch("app.db.obtener_conexion", return_value=conexion):
        estado = deshacer_procesado_compra(32)

    consulta, parametros = cursor.execute.call_args_list[1].args
    assert "estado = 'pendiente'" in consulta
    assert "procesada_el = NULL" in consulta
    assert "cantidad_cajones_real = NULL" in consulta
    assert "contenido_por_cajon_real = NULL" in consulta
    assert "cantidad_kilos_real = NULL" in consulta
    assert "cantidad_fraccion_real = NULL" in consulta
    assert parametros == (32,)
    # Un "No ingresó" nunca tocó el retiro: no hay segundo UPDATE.
    assert cursor.execute.call_count == 2
    assert estado == "no_ingresado"
    conexion.commit.assert_called_once()


def test_deshacer_procesado_compra_rechazada_revierte_el_retiro_que_puso_el_rechazo():
    # rechazar_compra llama a _auto_retirar_si_corresponde, que marca
    # retirado con retiro_origen='deposito'. Si no se revierte, la compra
    # queda "retirada" y eliminar_compra la sigue bloqueando: el deshacer
    # no destrabaría nada.
    conexion, cursor = _conexion_falsa(filas_fetchone=[("rechazado", "deposito")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        estado = deshacer_procesado_compra(32)

    consulta_retiro, parametros = cursor.execute.call_args_list[2].args
    assert "estado_retiro = 'pendiente'" in consulta_retiro
    assert "retiro_procesado_el = NULL" in consulta_retiro
    assert "retiro_origen = NULL" in consulta_retiro
    assert parametros == (32,)
    assert estado == "rechazado"
    conexion.commit.assert_called_once()


def test_deshacer_procesado_compra_rechazada_no_pisa_el_retiro_de_logistica():
    # Si el retiro lo tildó Logística (otro origen), el dato es de ellos y
    # no se toca: solo se revierte lo que escribió el propio rechazo.
    conexion, cursor = _conexion_falsa(filas_fetchone=[("rechazado", "clark")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        deshacer_procesado_compra(32)

    # SELECT + el UPDATE del estado, y nada más.
    assert cursor.execute.call_count == 2
    conexion.commit.assert_called_once()


def test_deshacer_procesado_compra_bloqueado_si_ya_fue_recepcionada():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("recepcionado", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            deshacer_procesado_compra(32)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert "no se puede deshacer" in str(error)

    # Solo el SELECT — nunca llega a ejecutar el UPDATE ni a hacer commit.
    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_listar_compras_procesadas_hoy_recepcion_filtra_por_estado_y_fecha():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_procesadas_hoy_recepcion(date(2026, 8, 17))

    consulta, parametros = cursor.execute.call_args[0]
    assert "c.estado IN ('recepcionado', 'rechazado', 'no_ingresado')" in consulta
    # Rango sargable en vez de ::date (mismo criterio que Retiro).
    assert "c.procesada_el >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND c.procesada_el < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')" in consulta
    assert "::date =" not in consulta
    assert "ORDER BY c.procesada_el DESC" in consulta
    assert parametros == (date(2026, 8, 17), date(2026, 8, 17))


def test_obtener_detalle_compra_devuelve_la_fila_mapeada():
    fila = (
        30, date(2026, 8, 16), "2026-08-16 09:15:00",
        5, "Tomate", "cajon",
        2, "Don José", "N07P41",
        105, 2,
        10.0, 20.0, 50000.0, 5000.0, "Clark", None,
        "retirado", "2026-08-16 10:00:00", "logistica", 9.0,
        "recepcionado", "2026-08-16 11:00:00",
        9.0, 19.5, None,
    )
    conexion, cursor = _conexion_falsa(filas_fetchone=[fila])
    cursor.description = [
        ("id",), ("fecha_operacion",), ("cargado_el",),
        ("articulo_id",), ("articulo_nombre",), ("unidad_compra",),
        ("proveedor_id",), ("proveedor_nombre",), ("proveedor_codigo_puesto",),
        ("guia_id",), ("guia_punto",),
        ("cantidad_cajones",), ("contenido_por_cajon",), ("importe",), ("sena",), ("tipo_retiro",), ("foto_ruta",),
        ("estado_retiro",), ("retiro_procesado_el",), ("retiro_origen",), ("cantidad_cajones_retirada",),
        ("estado",), ("procesada_el",),
        ("cantidad_cajones_real",), ("contenido_por_cajon_real",), ("cantidad_fraccion_real",),
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_detalle_compra(30)

    assert resultado["articulo_nombre"] == "Tomate"
    assert resultado["proveedor_nombre"] == "Don José"
    assert resultado["cantidad_cajones_retirada"] == 9.0
    assert resultado["cantidad_cajones_real"] == 9.0
    consulta, parametros = cursor.execute.call_args[0]
    assert "WHERE c.id = %s" in consulta
    assert parametros == (30,)
    conexion.close.assert_called_once()


def test_obtener_detalle_compra_devuelve_none_si_no_existe():
    conexion, cursor = _conexion_falsa(filas_fetchone=[None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_detalle_compra(999)

    assert resultado is None
    conexion.close.assert_called_once()


def test_eliminar_compras_del_dia_por_proveedor_devuelve_borradas_y_protegidas():
    # DOS fetchone: el COUNT de cuantas hay, y el count(*) del CTE que borra
    # y archiva. El segundo reemplazo a cursor.rowcount — con el INSERT del
    # archivo adentro de la misma sentencia, rowcount ya no es el de las
    # compras borradas.
    conexion, cursor = _conexion_falsa([(5,), (3,)])  # 5 en total, 3 borradas

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compras_del_dia_por_proveedor(date(2026, 8, 16), 7)

    assert resultado == {"borradas": 3, "protegidas": 2, "rutas_a_borrar": []}
    consulta_delete = next(
        ll.args[0] for ll in cursor.execute.call_args_list if "DELETE FROM compras" in ll.args[0]
    )
    assert "estado IS DISTINCT FROM 'recepcionado'" in consulta_delete
    assert "estado_retiro IS DISTINCT FROM 'retirado'" in consulta_delete
    conexion.commit.assert_called_once()


def test_obtener_uso_storage_bucket_devuelve_cantidad_y_bytes():
    conexion, cursor = _conexion_falsa([(1234, 356000000)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_uso_storage_bucket("comandas")

    assert resultado == {"cantidad": 1234, "bytes_totales": 356000000}
    cursor.execute.assert_called_once()
    consulta, parametros = cursor.execute.call_args[0]
    assert "storage.objects" in consulta
    assert "bucket_id" in consulta
    assert parametros == ("comandas",)


def test_agregar_foto_guia_suma_sin_reemplazar():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        agregar_foto_guia(105, "2026-08-20/guia-105-abc.jpg")

    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO fotos_guia" in consulta
    # Nunca reemplaza: la repetida en la misma guía simplemente no se duplica.
    assert "ON CONFLICT DO NOTHING" in consulta
    assert parametros == (105, "2026-08-20/guia-105-abc.jpg")
    conexion.commit.assert_called_once()


def test_borrar_foto_guia_devuelve_la_ruta_solo_si_ninguna_otra_guia_la_usa():
    conexion, cursor = _conexion_falsa([("2026/x.jpg",), (0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        ruta = borrar_foto_guia(9)

    assert ruta == "2026/x.jpg"
    consulta_delete = cursor.execute.call_args_list[0].args[0]
    assert "DELETE FROM fotos_guia WHERE id = %s RETURNING foto_ruta" in consulta_delete


def test_borrar_foto_guia_compartida_no_devuelve_la_ruta():
    # El Listado consolidado comparte el archivo entre guías: mientras otra
    # guía lo use, el Storage no se toca.
    conexion, cursor = _conexion_falsa([("2026/listado.jpg",), (2,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        ruta = borrar_foto_guia(9)

    assert ruta is None
    conexion.commit.assert_called_once()


def test_listar_fotos_de_guia_ordena_por_llegada():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_fotos_de_guia(105)

    consulta, parametros = cursor.execute.call_args.args
    assert "FROM fotos_guia WHERE guia_id = %s" in consulta
    assert "ORDER BY creado_en" in consulta
    assert parametros == (105,)


def test_obtener_uso_storage_bucket_bucket_vacio_da_cero():
    conexion, cursor = _conexion_falsa([(0, 0)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_uso_storage_bucket("comandas")

    assert resultado == {"cantidad": 0, "bytes_totales": 0}


def test_listar_fotos_para_limpiar_devuelve_los_foto_ruta_encontrados():
    conexion, cursor = _conexion_falsa(
        filas_fetchall=[("2020-01-01/a.jpg",), ("2020-02-02/b.jpg",)]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_fotos_para_limpiar(date(2023, 8, 15))

    assert resultado == ["2020-01-01/a.jpg", "2020-02-02/b.jpg"]
    cursor.execute.assert_called_once()
    consulta, parametros = cursor.execute.call_args[0]
    # Una sola pasada sobre fotos_guia: candidata si TODAS las guías que
    # usan la ruta son de antes del corte.
    assert "FROM fotos_guia" in consulta
    assert "JOIN guias_compra" in consulta
    assert "GROUP BY f.foto_ruta" in consulta
    assert "HAVING MAX(g.fecha_operacion) < %s" in consulta
    # LOS SEIS TIPOS DEL BUCKET EN LA MISMA PASADA. El que no esté acá no
    # se borra NUNCA: no aparece siquiera como candidato. Y eso no es solo
    # desperdicio — el bucket prefija por tipo solo lo NUEVO, así que
    # converge únicamente si lo viejo se vence (ver core/storage.py).
    assert "FROM fotos_recepcion" in consulta
    assert "FROM fotos_pedido" in consulta
    assert "FROM precios_venta_historial" in consulta
    assert "FROM fotos_merma" in consulta
    assert "FROM vacios_deposito_devoluciones" in consulta
    # Y la merma son DOS patas, no una: sus dos dueños posibles viven en
    # tablas distintas (movimientos_stock para el stock normal,
    # remitos_segunda para el pool). Con una sola, las fotos del otro dueño
    # serían inmortales.
    assert consulta.count("FROM fotos_merma") == 2
    assert "JOIN movimientos_stock m" in consulta
    assert "JOIN remitos_segunda r" in consulta
    # LA ESTRUCTURA ADEMÁS DE LOS NOMBRES: siete patas unidas por seis
    # UNION. Sin este conteo, una pata que se caiga entera deja los nombres
    # de arriba en verde —los demás siguen estando— y el test no lo ve.
    assert consulta.count("UNION") == 6, "se cayó (o se agregó) una pata del UNION"
    assert parametros == (date(2023, 8, 15),) * 7, (
        "el corte va a las SIETE patas del UNION, y es el mismo: una sola perilla"
    )


def test_listar_fotos_para_limpiar_vacio_da_lista_vacia():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_fotos_para_limpiar(date(2023, 8, 15))

    assert resultado == []


def test_olvidar_foto_borrada_limpia_TODAS_las_tablas_donde_vive_una_ruta():
    """El archivo ya se fue del Storage: la fila que quede apunta a la nada.

    Antes esto miraba solo fotos_guia y el test lo afirmaba como correcto.
    Con las fotos de balanza eso dejaba "Ver foto" roto para siempre y SIN
    ningún síntoma: el DELETE no encuentra la fila, no da error, y el
    contador de la pantalla la cuenta como borrada.

    Y VOLVIÓ A PASAR, con la misma forma: el test se quedó nombrando DOS
    tablas cuando la función ya tocaba cuatro, así que fotos_pedido y
    fotos_merma entraron sin nadie que las mirara. Un test que afirma un
    subconjunto no protege lo que no nombra — por eso acá van todas Y el
    total, para que agregar una tabla sin tocar este test falle.
    """
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 1

    with patch("app.db.obtener_conexion", return_value=conexion):
        olvidar_foto_borrada("2020-01-01/a.jpg")

    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    for tabla in ("fotos_guia", "fotos_recepcion", "fotos_pedido", "fotos_merma"):
        assert any(f"DELETE FROM {tabla} WHERE foto_ruta = %s" in c for c in consultas), tabla
    # El historial de precios NO se borra: el precio es el dato y la foto
    # era solo de dónde salió. Se le saca la ruta, que es lo que quedó
    # apuntando a un archivo que no existe.
    assert any("UPDATE precios_venta_historial SET foto_ruta = NULL" in c for c in consultas)
    # El vale de vacíos tampoco: la devolución es el dato —cuántos cajones
    # salieron y contra qué compra— y la foto era de dónde salió.
    assert any("UPDATE vacios_deposito_devoluciones SET foto_ruta = NULL" in c for c in consultas)
    assert len(consultas) == 6, (
        "apareció otra tabla con foto_ruta: agregala acá o la ruta huérfana "
        "no se va a limpiar nunca, y el contador la va a contar como borrada"
    )
    conexion.commit.assert_called_once()
    conexion.close.assert_called_once()


def test_olvidar_foto_borrada_LEVANTA_si_no_toco_ninguna_fila():
    """Sin esto, borrar a medias se reporta como éxito.

    El archivo ya no está en el bucket cuando se llama a esta función. Si
    no borra ninguna fila, "ya estaba limpio" y "estoy mirando la tabla
    equivocada" son indistinguibles, y la segunda es la que hay que ver.
    """
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 0

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            olvidar_foto_borrada("2020-01-01/a.jpg")

    assert "2020-01-01/a.jpg" in str(error.value)
    conexion.commit.assert_not_called()
    conexion.close.assert_called_once()


def test_listar_conceptos_editables_por_cliente_agrupa_por_tipo_y_excluye_bajas():
    conexion, cursor = _conexion_falsa(
        filas_fetchall=[
            ("IVA", "suma", 0.21),
            ("Premio viejo", "suma", 0),  # dado de baja, no tiene que aparecer
            ("Flete", "resta", 0.04),
            ("utilidad_objetivo", "utilidad", 0.20),
        ]
    )
    cursor.description = [("nombre_parametro",), ("tipo",), ("valor",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_conceptos_editables_por_cliente(1)

    assert resultado == {
        "tasas_suma": [{"nombre": "IVA", "valor_pct": 21.0}],
        "tasas_resta": [{"nombre": "Flete", "valor_pct": 4.0}],
        "utilidad_pct": 20.0,
    }


def test_listar_conceptos_editables_por_cliente_sin_utilidad_cargada_devuelve_none():
    conexion, cursor = _conexion_falsa(filas_fetchall=[("IVA", "suma", 0.21)])
    cursor.description = [("nombre_parametro",), ("tipo",), ("valor",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_conceptos_editables_por_cliente(1)

    assert resultado["utilidad_pct"] is None


# La fecha que los ESCRITORES reciben por parámetro. El nombre lleva el
# alcance (no es "hoy" de todo el archivo): es la vigencia de una carga.
VIGENCIA_DE_PRUEBA = date(2026, 8, 15)


def test_crear_cliente_inserta_el_cliente_y_todos_los_conceptos_con_tipo():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        cliente_id = crear_cliente(
            "Vea",
            [{"nombre": "IVA", "valor": 0.21}],
            [{"nombre": "Flete", "valor": 0.04}],
            0.20,
            VIGENCIA_DE_PRUEBA,
        )

    assert cliente_id == 7
    # 1 INSERT del cliente + 3 conceptos (IVA, Flete, utilidad_objetivo).
    assert cursor.execute.call_count == 4
    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    assert "INSERT INTO clientes" in consultas[0]
    for consulta_concepto in consultas[1:]:
        assert "INSERT INTO clientes_parametros_historial" in consulta_concepto
        assert "tipo" in consulta_concepto
        assert "vigente_desde" in consulta_concepto
        # La fecha viaja como PARÁMETRO, no como el reloj del servidor de
        # la base: CURRENT_DATE es UTC y pasadas las 21:00 de Argentina
        # fecha un día adelante (ver _insertar_conceptos_cliente).
        assert "CURRENT_DATE" not in consulta_concepto

    parametros_conceptos = [llamada.args[1] for llamada in cursor.execute.call_args_list[1:]]
    assert (7, "IVA", 0.21, "suma", VIGENCIA_DE_PRUEBA) in parametros_conceptos
    assert (7, "Flete", 0.04, "resta", VIGENCIA_DE_PRUEBA) in parametros_conceptos
    assert (7, "utilidad_objetivo", 0.20, "utilidad", VIGENCIA_DE_PRUEBA) in parametros_conceptos
    conexion.commit.assert_called_once()


def test_crear_cliente_sin_tasas_solo_inserta_la_utilidad():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_cliente("Vea", [], [], 0.20, VIGENCIA_DE_PRUEBA)

    # 1 INSERT del cliente + 1 de la utilidad, sin tasas.
    assert cursor.execute.call_count == 2


def test_actualizar_cliente_pisa_el_nombre_y_agrega_solo_los_conceptos_que_cambiaron():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cliente(
            1, "Día", [{"nombre_parametro": "Flete", "tipo": "resta", "valor": 0.05}], VIGENCIA_DE_PRUEBA
        )

    assert cursor.execute.call_count == 2
    consulta_nombre, parametros_nombre = cursor.execute.call_args_list[0].args
    assert "UPDATE clientes SET nombre" in consulta_nombre
    assert parametros_nombre == ("Día", 1)

    consulta_concepto, parametros_concepto = cursor.execute.call_args_list[1].args
    assert "ON CONFLICT (cliente_id, nombre_parametro, vigente_desde)" in consulta_concepto
    assert "DO UPDATE" in consulta_concepto
    assert "CURRENT_DATE" not in consulta_concepto
    assert parametros_concepto == (1, "Flete", 0.05, "resta", VIGENCIA_DE_PRUEBA)
    conexion.commit.assert_called_once()


def test_actualizar_cliente_sin_cambios_de_conceptos_solo_pisa_el_nombre():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cliente(1, "Día", [], VIGENCIA_DE_PRUEBA)

    # Ningún concepto cambió: solo el UPDATE del nombre, ninguna fila nueva
    # de historial de más.
    assert cursor.execute.call_count == 1
    conexion.commit.assert_called_once()


def test_listar_clientes_suma_las_tasas_vigentes_de_descuento_y_adicionales():
    # La consulta real (WITH vigentes/totales/utilidades, ver
    # _CLIENTE_CON_TASAS_VIGENTES_SQL) se probó a mano contra un Postgres
    # real con datos que reproducen el caso reportado: un cliente con 3
    # tasas de descuento (Logística 15% + Flete 5% + Otro 3% = 23%), una
    # tasa vieja de Flete ya reemplazada (no debe sumar) y una tasa dada de
    # baja en 0 (tampoco debe sumar) — dio exactamente 23.00 / 10.500 /
    # 18.00, igual que este mock. Acá solo se verifica que Python arma bien
    # la consulta y mapea las columnas del resultado.
    conexion, cursor = _conexion_falsa(
        filas_fetchall=[
            (2, "Cliente 3", 23.00, 10.500, 18.00),
            (1, "Día", 23.00, 0, 20.00),
        ]
    )
    cursor.description = [("id",), ("nombre",), ("descuento",), ("adicionales",), ("utilidad_objetivo",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_clientes()

    assert resultado == [
        {"id": 2, "nombre": "Cliente 3", "descuento": 23.00, "adicionales": 10.500, "utilidad_objetivo": 18.00},
        {"id": 1, "nombre": "Día", "descuento": 23.00, "adicionales": 0, "utilidad_objetivo": 20.00},
    ]
    consulta = cursor.execute.call_args[0][0]
    assert "WHERE c.activo = true ORDER BY c.nombre" in consulta
    assert "FILTER (WHERE tipo = 'resta')" in consulta
    assert "FILTER (WHERE tipo = 'suma')" in consulta


def test_listar_precios_vigentes_por_cliente_trae_vigente_desde():
    # La exportación a PDF/Excel necesita vigente_desde para saber si un
    # precio es "nuevo" (cambió justo en la fecha exportada).
    # La consulta trae la fecha adelante: se pide para varias de una y cada
    # fila dice a qué fecha corresponde.
    conexion, cursor = _conexion_falsa(
        filas_fetchall=[
            (date(2026, 8, 16), 901, 1, 500.0, date(2026, 8, 16)),
            (date(2026, 8, 16), 902, 2, 350.0, date(2026, 8, 10)),
        ]
    )
    cursor.description = [("fecha",), ("ficha_id",), ("articulo_id",), ("precio",), ("vigente_desde",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_precios_vigentes_por_cliente(1, date(2026, 8, 16))

    assert resultado == [
        {"ficha_id": 901, "articulo_id": 1, "precio": 500.0, "vigente_desde": date(2026, 8, 16)},
        {"ficha_id": 902, "articulo_id": 2, "precio": 350.0, "vigente_desde": date(2026, 8, 10)},
    ]
    consulta = cursor.execute.call_args[0][0]
    assert "vigente_desde" in consulta
    # El precio es de la FICHA, no del artículo: es lo que permite que dos
    # fichas del mismo artículo y cliente tengan precios distintos.
    assert "DISTINCT ON (ficha_id)" in consulta
    # Un precio huérfano (su ficha se borró o cambió de artículo) no se lee.
    assert "ficha_id IS NOT NULL" in consulta


def test_listar_precios_anteriores_por_cliente_trae_la_fila_previa_a_la_vigente():
    # Para la columna "Precio anterior" del Excel: la fila #2 (orden = 2 en
    # el ROW_NUMBER, la que regía justo antes de la vigente), no la #1.
    conexion, cursor = _conexion_falsa(filas_fetchall=[(902, 2, 350.0)])
    cursor.description = [("ficha_id",), ("articulo_id",), ("precio",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_precios_anteriores_por_cliente(1, date(2026, 8, 16))

    assert resultado == [{"ficha_id": 902, "articulo_id": 2, "precio": 350.0}]
    consulta, parametros = cursor.execute.call_args[0]
    assert "PARTITION BY ficha_id" in consulta
    assert "ROW_NUMBER()" in consulta
    assert "WHERE orden = 2" in consulta
    assert parametros == (1, date(2026, 8, 16))


def test_guardar_precios_cliente_escribe_LA_FECHA_QUE_LE_PASAN_y_no_la_del_servidor():
    """Hasta el 14/09 la consulta decía `CURRENT_DATE`, y ese test afirmaba eso.

    `CURRENT_DATE` es la fecha del SERVIDOR de la base, y todas las lecturas
    resuelven el vigente con la fecha ARGENTINA. Son dos relojes para el mismo
    hecho: con la base en UTC se separan todas las noches a partir de las 21:00
    de Argentina, y lo cargado a esa hora quedaba fechado MAÑANA — guardado sin
    error y sin regir hoy.

    Por eso el assert está dado vuelta: `CURRENT_DATE` no puede volver a
    aparecer. Sin esa mitad, el test lo pasa igual una consulta que vuelva a
    poner el reloj del servidor al lado del parámetro.
    """
    conexion, cursor = _conexion_falsa()
    vigencia = date(2026, 9, 5)

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_precios_cliente(
            1, [{"ficha_id": 907, "precio": 550.0}, {"ficha_id": 903, "precio": 900.0}], vigencia
        )

    assert cursor.execute.call_count == 2
    for llamada in cursor.execute.call_args_list:
        consulta, parametros = llamada.args
        assert "INSERT INTO precios_venta_historial" in consulta
        assert "vigente_desde" in consulta
        assert "CURRENT_DATE" not in consulta, "volvió el reloj del servidor"
        # El precio cuelga de la FICHA (dos fichas del mismo artículo y
        # cliente tienen precios distintos), y el artículo NO viaja desde
        # la pantalla: sale de la propia ficha adentro del INSERT.
        assert "ON CONFLICT (ficha_id, vigente_desde)" in consulta
        assert "SELECT fl.id, fl.articulo_id" in consulta
        # DO UPDATE es lo que permite CORREGIR un precio ya cargado de una
        # fecha pasada: la segunda carga de ese día pisa la primera en vez de
        # duplicarla. Sin esto no habría forma de corregir sin borrar filas.
        assert "DO UPDATE" in consulta
    assert cursor.execute.call_args_list[0].args[1] == (1, 550.0, vigencia, None, 907, 1)
    assert cursor.execute.call_args_list[1].args[1] == (1, 900.0, vigencia, None, 903, 1)
    conexion.commit.assert_called_once()


def test_guardar_precios_cliente_EXIGE_la_fecha_y_no_la_inventa():
    """Sin default, el llamador que se olvide explota. Con uno, escribe hoy en silencio.

    Es la diferencia entre un `NO ACTION` y un `SET NULL`: la guarda tiene que
    estar donde la base grita, no donde acepta callada. Un precio retroactivo
    fechado hoy no se distingue de uno normal.
    """
    import pytest

    with pytest.raises(TypeError):
        guardar_precios_cliente(1, [{"ficha_id": 907, "precio": 550.0}])


def test_guardar_precios_cliente_sin_cambios_no_ejecuta_nada():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_precios_cliente(1, [], date(2026, 9, 14))

    cursor.execute.assert_not_called()
    conexion.commit.assert_not_called()


def test_guardar_precios_cliente_con_foto_ruta_la_guarda_en_cada_fila():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_precios_cliente(
            1, [{"ficha_id": 907, "precio": 550.0}], date(2026, 9, 14), foto_ruta="2026-08-16/dia-123-abc.jpg"
        )

    consulta, parametros = cursor.execute.call_args_list[0].args
    assert "foto_ruta" in consulta
    assert "COALESCE(EXCLUDED.foto_ruta, precios_venta_historial.foto_ruta)" in consulta
    assert parametros == (1, 550.0, date(2026, 9, 14), "2026-08-16/dia-123-abc.jpg", 907, 1)


def test_obtener_borrador_disponible_devuelve_la_fila():
    conexion, cursor = _conexion_falsa(
        filas_fetchone=[(30, 1, date(2026, 8, 14), date(2026, 8, 14), "borrador", None, "2026-08-14T09:00", "2026-08-14T09:00")]
    )
    cursor.description = [
        ("id",), ("cliente_id",), ("fecha_desde",), ("fecha_hasta",), ("estado",), ("version",), ("creado_en",), ("actualizado_en",),
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_borrador_disponible(1)

    assert resultado["id"] == 30
    assert resultado["estado"] == "borrador"
    consulta, parametros = cursor.execute.call_args[0]
    assert "estado = 'borrador'" in consulta
    assert parametros == (1,)


def test_obtener_borrador_disponible_devuelve_none_si_no_hay():
    conexion, cursor = _conexion_falsa(filas_fetchone=[None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_borrador_disponible(1)

    assert resultado is None


def test_obtener_ultimo_disponible_cliente_devuelve_el_mas_reciente():
    conexion, cursor = _conexion_falsa(
        filas_fetchone=[(29, 1, date(2026, 8, 10), date(2026, 8, 10), "generado", 1, "2026-08-10T09:00", "2026-08-10T09:00")]
    )
    cursor.description = [
        ("id",), ("cliente_id",), ("fecha_desde",), ("fecha_hasta",), ("estado",), ("version",), ("creado_en",), ("actualizado_en",),
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_ultimo_disponible_cliente(1)

    assert resultado["id"] == 29
    consulta, parametros = cursor.execute.call_args[0]
    assert "ORDER BY creado_en DESC" in consulta
    assert parametros == (1,)


def test_obtener_ultimo_disponible_cliente_devuelve_none_si_nunca_tuvo():
    conexion, cursor = _conexion_falsa(filas_fetchone=[None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_ultimo_disponible_cliente(1)

    assert resultado is None


def test_listar_detalle_disponible_devuelve_filas_en_orden():
    conexion, cursor = _conexion_falsa(
        filas_fetchall=[(1, 5, "90039", "Manzana", 40.0, 1), (2, None, None, "Frutilla", 12.0, 2)]
    )
    cursor.description = [("id",), ("articulo_id",), ("codigo",), ("nombre",), ("cantidad",), ("orden",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_detalle_disponible(30)

    assert resultado == [
        {"id": 1, "articulo_id": 5, "codigo": "90039", "nombre": "Manzana", "cantidad": 40.0, "orden": 1},
        {"id": 2, "articulo_id": None, "codigo": None, "nombre": "Frutilla", "cantidad": 12.0, "orden": 2},
    ]
    consulta, parametros = cursor.execute.call_args[0]
    assert "ORDER BY orden" in consulta
    assert parametros == (30,)


def test_guardar_disponible_nuevo_inserta_cabecera_y_detalle():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(42,)])

    renglones = [
        {"articulo_id": 5, "codigo": "90039", "nombre": "Manzana", "cantidad": 40.0},
        {"articulo_id": None, "codigo": None, "nombre": "Frutilla", "cantidad": 12.0},
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = guardar_disponible(None, 1, date(2026, 8, 14), date(2026, 8, 14), renglones)

    assert resultado == 42
    llamadas = cursor.execute.call_args_list
    assert "INSERT INTO disponibles" in llamadas[0].args[0]
    assert llamadas[0].args[1] == (1, date(2026, 8, 14), date(2026, 8, 14))
    assert "DELETE FROM disponibles_detalle" in llamadas[1].args[0]
    assert llamadas[1].args[1] == (42,)
    assert "INSERT INTO disponibles_detalle" in llamadas[2].args[0]
    assert llamadas[2].args[1] == (42, 5, "90039", "Manzana", 40.0, 1)
    assert llamadas[3].args[1] == (42, None, None, "Frutilla", 12.0, 2)
    conexion.commit.assert_called_once()


def test_guardar_disponible_existente_actualiza_cabecera_y_reemplaza_detalle():
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 1  # el UPDATE encontró el borrador

    renglones = [{"articulo_id": 5, "codigo": "90039", "nombre": "Manzana", "cantidad": 38.0}]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = guardar_disponible(30, 1, date(2026, 8, 14), date(2026, 8, 15), renglones)

    assert resultado == 30
    llamadas = cursor.execute.call_args_list
    assert "UPDATE disponibles" in llamadas[0].args[0]
    assert "estado = 'borrador'" in llamadas[0].args[0]
    assert llamadas[0].args[1] == (date(2026, 8, 14), date(2026, 8, 15), 30)
    assert "DELETE FROM disponibles_detalle" in llamadas[1].args[0]
    conexion.commit.assert_called_once()


def test_guardar_disponible_existente_ya_generado_lanza_error():
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 0  # no matcheó ningún borrador con ese id (ya está generado)

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            guardar_disponible(30, 1, date(2026, 8, 14), date(2026, 8, 14), [])
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert "ya fue generado" in str(error)

    conexion.commit.assert_not_called()


def test_cerrar_disponible_generado_primera_vez_devuelve_version_1():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0,)])  # SELECT COUNT(*): ningún generado previo
    cursor.rowcount = 1

    with patch("app.db.obtener_conexion", return_value=conexion):
        version = cerrar_disponible_generado(30, 1, date(2026, 8, 14))

    assert version == 1
    llamadas = cursor.execute.call_args_list
    assert "SELECT COUNT(*)" in llamadas[0].args[0]
    assert llamadas[0].args[1] == (1, date(2026, 8, 14))
    assert "UPDATE disponibles" in llamadas[1].args[0]
    assert "estado = 'generado'" in llamadas[1].args[0]
    assert llamadas[1].args[1] == (1, 30)
    conexion.commit.assert_called_once()


def test_cerrar_disponible_generado_reenvio_el_mismo_dia_suma_version():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(2,)])  # ya hay 2 generados ese mismo cliente+fecha
    cursor.rowcount = 1

    with patch("app.db.obtener_conexion", return_value=conexion):
        version = cerrar_disponible_generado(31, 1, date(2026, 8, 14))

    assert version == 3


def test_cerrar_disponible_generado_ya_cerrado_lanza_error():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0,)])
    cursor.rowcount = 0  # no matcheó ningún borrador con ese id

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            cerrar_disponible_generado(30, 1, date(2026, 8, 14))
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert "ya fue generado" in str(error)

    conexion.commit.assert_not_called()


# --- Envases: alta, cambio de costo con historial, listado con costo vigente ---


def test_registrar_costo_envase_inserta_fila_nueva_sin_pisar_el_historial():
    # La regla de oro: SIEMPRE una fila nueva vigente desde hoy — nunca un
    # UPDATE de filas viejas (los cálculos pasados no cambian). La única
    # excepción es el mismo día (ON CONFLICT), igual que en precios.
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        registrar_costo_envase(7, 800.0, VIGENCIA_DE_PRUEBA)

    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO envases_costo_historial" in consulta
    assert "CURRENT_DATE" not in consulta
    assert "ON CONFLICT (envase_id, vigente_desde) DO UPDATE" in consulta
    assert not consulta.strip().startswith("UPDATE")
    assert parametros == (7, 800.0, VIGENCIA_DE_PRUEBA)
    conexion.commit.assert_called_once()


def test_crear_envase_crea_con_costo_inicial_desde_hoy_en_una_transaccion():
    conexion, cursor = _conexion_falsa(filas_fetchone=[None, (33,)])  # no existe; RETURNING id

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_envase("Caja Nueva", 700.0, VIGENCIA_DE_PRUEBA)

    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    assert any("INSERT INTO envases " in consulta for consulta in consultas)
    assert any("INSERT INTO envases_costo_historial" in consulta for consulta in consultas)
    assert not any("CURRENT_DATE" in consulta for consulta in consultas)
    assert cursor.execute.call_args_list[-1].args[1] == (33, 700.0, VIGENCIA_DE_PRUEBA)
    conexion.commit.assert_called_once()


def test_crear_envase_rechaza_nombre_repetido():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(1,)])  # ya existe

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as salida:
            crear_envase("Caja Chica Día", 700.0, VIGENCIA_DE_PRUEBA)

    assert "Ya existe un envase con ese nombre" in str(salida.value)
    conexion.commit.assert_not_called()


def test_listar_envases_con_costo_trae_vigente_desde_y_cuantas_fichas_lo_usan():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_envases_con_costo(date(2026, 8, 19))

    consulta = cursor.execute.call_args.args[0]
    # Costo VIGENTE a la fecha (la fila más nueva ya alcanzada), no cualquier fila.
    assert "vigente_desde <= %s" in consulta
    assert "ORDER BY vigente_desde DESC" in consulta
    assert "fichas_logistica" in consulta
    assert "activo = true" in consulta
    # Catálogo compartido: nada de filtrar por cliente.
    assert "cliente_id" not in consulta


# --- tipo_retiro Cooperativa: nace con el retiro hecho ---


def test_crear_compra_cooperativa_nace_retirada_con_origen_cooperativa():
    # La Cooperativa es un tercero: se asume que retira. La compra nace con
    # estado_retiro 'retirado' y retiro_origen 'cooperativa', pero la
    # recepción en Depósito sigue pendiente y sin valores reales.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,), (900,)])  # guia_id, punto

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 8, 19), 5, 200, 10, 18, 180, None, 50000.0, None, "Cooperativa", segunda_por_cajon=None)

    # POR LA SENTENCIA y no por la posición: desde que el alta sella el
    # importe con un UPDATE posterior, `[-1]` es ese UPDATE y el assert
    # pasaba a mirar otra cosa. Es lo que el docstring de
    # _sql_y_parametros_que_contienen viene diciendo.
    consulta_insert, parametros_insert = _sql_y_parametros_que_contienen(cursor, "INSERT INTO compras")
    assert "'pendiente', 'retirado', now(), %s" in consulta_insert
    assert parametros_insert[-1] == "automatico_cooperativa"
    assert "cantidad_cajones_real" not in consulta_insert  # sin valores reales: los pone Depósito
    conexion.commit.assert_called_once()


def test_actualizar_cantidad_a_cooperativa_marca_el_retiro_en_el_mismo_update():
    # Cambiar el tipo a Cooperativa en Editar Compra no puede dejar la
    # compra pendiente de retiro: no existe pantalla que la muestre.
    conexion, cursor = _conexion_falsa(filas_fetchone=[("pendiente", "pendiente", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Cooperativa", segunda_por_cajon=None)

    # EL UPDATE DEL RETIRO, buscado por lo que dice y no por ser el último:
    # la marca de "viene armada" se escribe con un UPDATE propio después, así
    # que `[-1]` dejó de ser éste el día que esa marca se agregó.
    consulta_update, parametros_update = next(
        llamada.args for llamada in cursor.execute.call_args_list
        if "estado_retiro = 'retirado'" in llamada.args[0]
    )
    assert "retiro_origen = %s" in consulta_update
    assert "automatico_cooperativa" in parametros_update


def test_actualizar_cantidad_con_tipo_comun_no_toca_el_retiro():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("pendiente", "pendiente", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Clark", segunda_por_cajon=None)

    consulta_update = cursor.execute.call_args_list[-1].args[0]
    assert "estado_retiro" not in consulta_update
    assert "retiro_origen" not in consulta_update


def test_actualizar_cantidad_de_cooperativa_a_tipo_real_vuelve_el_retiro_a_pendiente():
    # Volver de Cooperativa a un tipo real (Carro/Clark/Pases) tiene que
    # devolver la compra a la cola de Logística — si no, queda "retirada"
    # por una cooperativa que ya no la va a buscar.
    conexion, cursor = _conexion_falsa(filas_fetchone=[("pendiente", "retirado", "automatico_cooperativa")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Clark", segunda_por_cajon=None)

    consulta_update = cursor.execute.call_args_list[1].args[0]
    assert "estado_retiro = 'pendiente'" in consulta_update
    assert "retiro_origen = NULL" in consulta_update
    conexion.commit.assert_called_once()


def test_crear_compra_carro_nace_retirada_con_origen_automatico():
    # Carro lo maneja un tercero que nunca entra al sistema: nadie tilda
    # nunca esas compras — nacen con el retiro hecho, igual que Cooperativa.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,), (900,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 8, 19), 5, 200, 10, 18, 180, None, 50000.0, None, "Carro", segunda_por_cajon=None)

    # POR LA SENTENCIA y no por la posición: desde que el alta sella el
    # importe con un UPDATE posterior, `[-1]` es ese UPDATE y el assert
    # pasaba a mirar otra cosa. Es lo que el docstring de
    # _sql_y_parametros_que_contienen viene diciendo.
    consulta_insert, parametros_insert = _sql_y_parametros_que_contienen(cursor, "INSERT INTO compras")
    assert "'pendiente', 'retirado', now(), %s" in consulta_insert
    assert parametros_insert[-1] == "automatico_carro"
    conexion.commit.assert_called_once()


def test_crear_compra_clark_sigue_naciendo_pendiente_de_retiro():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,), (900,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 8, 19), 5, 200, 10, 18, 180, None, 50000.0, None, "Clark", segunda_por_cajon=None)

    # POR LA SENTENCIA y no por la posición: desde que el alta sella el
    # importe con un UPDATE posterior, `[-1]` es ese UPDATE y el assert
    # pasaba a mirar otra cosa. Es lo que el docstring de
    # _sql_y_parametros_que_contienen viene diciendo.
    consulta_insert, _ = _sql_y_parametros_que_contienen(cursor, "INSERT INTO compras")
    assert "'pendiente', 'pendiente'" in consulta_insert
    assert "retiro_origen" not in consulta_insert


def test_buscar_retiros_arma_los_filtros_y_trae_las_dos_cantidades():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_retiros(date(2026, 8, 18), date(2026, 8, 19), proveedor_id=7, articulo_id=5, tipo_retiro="Carro", estado_retiro="retirado")

    consulta, parametros = cursor.execute.call_args.args
    assert "c.fecha_operacion BETWEEN %s AND %s" in consulta
    assert "c.proveedor_id = %s" in consulta
    assert "c.articulo_id = %s" in consulta
    assert "c.tipo_retiro = %s" in consulta
    assert "c.estado_retiro = %s" in consulta
    # Las dos cantidades por separado: el total de bultos se arma afuera y
    # se muestra de dónde sale cada número.
    assert "c.cantidad_cajones" in consulta and "c.cantidad_cajones_retirada" in consulta
    assert parametros == [date(2026, 8, 18), date(2026, 8, 19), 7, 5, "Carro", "retirado"]


def test_buscar_retiros_pendiente_incluye_los_estados_nulos():
    # Mismo criterio que la pantalla de retiro: una fila con estado NULL
    # (compra de antes de que existiera Retiro) se muestra, no desaparece.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_retiros(date(2026, 8, 18), date(2026, 8, 19), estado_retiro="pendiente")

    consulta = cursor.execute.call_args.args[0]
    assert "IS DISTINCT FROM 'retirado'" in consulta
    assert "IS DISTINCT FROM 'cancelado'" in consulta


# --- Vacíos (Envases Puesto) ---


def test_listar_tipos_envase_puesto_solo_activos_ordenados_por_carga():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_tipos_envase_puesto()

    consulta = cursor.execute.call_args[0][0]
    # El tipo activo Y su proveedor activo. Dar de baja al proveedor NO da
    # de baja sus tipos (son dos tablas), así que sin el p.activo un
    # proveedor muerto seguía apareciendo en Recibir y en Devolver y se le
    # podían cargar movimientos nuevos.
    assert "WHERE t.activo AND p.activo" in consulta
    # Dentro de cada proveedor, por id (orden de carga): el primero cargado
    # es el que Recibir preselecciona.
    assert "ORDER BY p.nombre, t.id" in consulta


def test_crear_tipo_envase_puesto_reactiva_si_existia_dado_de_baja():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_tipo_envase_puesto(200, "cajón negro")

    consulta, parametros = cursor.execute.call_args.args
    assert "ON CONFLICT (proveedor_id, nombre) DO UPDATE SET activo = true" in consulta
    assert parametros == (200, "cajón negro")
    conexion.commit.assert_called_once()


def test_obtener_o_crear_cliente_puesto_reusa_el_existente_por_nombre_normalizado():
    conexion, cursor = _conexion_falsa([(10, True)])  # ya existe, activo

    with patch("app.db.obtener_conexion", return_value=conexion):
        cliente_id = obtener_o_crear_cliente_puesto("JUAN Pérez", "juan perez")

    assert cliente_id == 10
    # Solo el SELECT: ni INSERT ni UPDATE — "Juan", "juan " y "JUAN" son el mismo.
    assert cursor.execute.call_count == 1


def test_obtener_o_crear_cliente_puesto_reactiva_al_dado_de_baja():
    conexion, cursor = _conexion_falsa([(10, False)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        cliente_id = obtener_o_crear_cliente_puesto("Juan", "juan")

    assert cliente_id == 10
    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "SET activo = true")
    assert "clientes_puesto" in consulta_update
    assert parametros_update == (10,)


def test_obtener_o_crear_cliente_puesto_crea_si_no_existe():
    conexion, cursor = _conexion_falsa([None, (33,)])  # no existe; INSERT RETURNING id

    with patch("app.db.obtener_conexion", return_value=conexion):
        cliente_id = obtener_o_crear_cliente_puesto("Marta", "marta")

    assert cliente_id == 33
    consulta_insert, parametros_insert = cursor.execute.call_args_list[1].args
    assert "INSERT INTO clientes_puesto" in consulta_insert
    assert parametros_insert == ("Marta", "marta")
    conexion.commit.assert_called_once()


def test_crear_vacio_devuelto_graba_el_stock_del_sistema_en_la_fila():
    # El sistema decía 40: ese número queda GRABADO en el movimiento (no es
    # solo un cartel), y la función lo devuelve para que la ruta avise.
    conexion, cursor = _conexion_falsa([(40,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock = crear_vacio_devuelto(200, 1, 50)

    assert stock == 40
    consulta_insert, parametros_insert = cursor.execute.call_args_list[1].args
    assert "INSERT INTO vacios_devueltos" in consulta_insert
    assert "stock_sistema" in consulta_insert
    assert parametros_insert == (200, 1, 50, 40)
    conexion.commit.assert_called_once()


def test_anular_vacio_recibido_es_baja_logica_no_delete():
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 1

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_vacio_recibido(5)

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE vacios_recibidos SET anulado_el = now()" in consulta
    assert "DELETE" not in consulta
    # Solo si estaba vigente: anular dos veces no pisa la fecha original.
    assert "anulado_el IS NULL" in consulta
    assert parametros == (5,)


def test_anular_vacio_recibido_NO_deja_si_la_sena_ya_se_pago_o_hay_vale():
    """El agujero del 07/09: la plata ya salió de la caja y los cajones
    volvían a salir del stock, sin que ninguna pantalla lo mostrara — la fila
    desaparece de las dos listas de Señas, que filtran anulado_el IS NULL.

    La condición va DENTRO del UPDATE: entre un "¿está pagada?" y el UPDATE
    puede entrar el pago.
    """
    from app.db import SenaYaCobrada

    for pagada, vale, esperado in ((True, False, "pagada"), (False, True, "vale")):
        conexion, cursor = _conexion_falsa(filas_fetchone=[(pagada, vale)])
        cursor.rowcount = 0

        with patch("app.db.obtener_conexion", return_value=conexion):
            with pytest.raises(SenaYaCobrada) as levantada:
                anular_vacio_recibido(74)

        assert levantada.value.cierre == esperado
        consulta = cursor.execute.call_args_list[0].args[0]
        assert "sena_pagada_el IS NULL AND sena_vale_el IS NULL" in consulta
        # `sena_anulada_el` NO entra: ahí se decidió no pagar, no hay plata.
        assert "sena_anulada_el" not in consulta
        # Y no se escribió nada.
        conexion.commit.assert_not_called()


def test_anular_una_YA_ANULADA_no_es_error():
    """Anular dos veces da el mismo resultado. Solo se levanta si hay plata."""
    from app.db import SenaYaCobrada

    conexion, cursor = _conexion_falsa(filas_fetchone=[None])
    cursor.rowcount = 0

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            anular_vacio_recibido(5)
        except SenaYaCobrada:
            pytest.fail("una entrada ya anulada no puede levantar SenaYaCobrada")
    conexion.commit.assert_called_once()


def test_el_listado_de_recibidos_TRAE_el_estado_de_la_sena():
    """Para que la pantalla no ofrezca un botón que el server va a rechazar:
    ofrecido y prohibido es lo peor de los dos mundos."""
    from app.db import listar_vacios_recibidos_por_rango

    conexion, cursor = _conexion_falsa(filas_fetchall=[])
    cursor.description = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_vacios_recibidos_por_rango(date(2026, 9, 7), date(2026, 9, 7))

    consulta = cursor.execute.call_args.args[0]
    assert "v.sena_pagada_el" in consulta and "v.sena_vale_el" in consulta


def test_stock_vacios_excluye_anulados_y_calcula_la_diferencia():
    conexion, cursor = _conexion_falsa(
        filas_fetchall=[
            (200, "Saturno", 1, "cajón negro", 50, 30, -5),
        ]
    )
    cursor.description = [
        ("proveedor_id",), ("proveedor_nombre",),
        ("tipo_envase_id",), ("tipo_nombre",), ("recibidos",), ("devueltos",), ("ajustes",),
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        filas = stock_vacios()

    consulta = cursor.execute.call_args[0][0]
    # Los movimientos anulados no cuentan para el stock (recibidos,
    # devueltos NI ajustes).
    assert consulta.count("anulado_el IS NULL") == 3
    assert filas[0]["stock"] == 15  # 50 recibidos − 30 devueltos + (-5) ajustes


def test_crear_ajuste_vacios_graba_la_foto_del_stock_y_devuelve_el_resultante():
    # El sistema decía 40: esa foto queda GRABADA en la fila (SIN el
    # ajuste), y la función devuelve 40 + (-5) = 35 para el aviso.
    conexion, cursor = _conexion_falsa([(40,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock_nuevo = crear_ajuste_vacios(200, 1, -5, "Se rompieron dos")

    assert stock_nuevo == 35
    consulta_insert, parametros_insert = cursor.execute.call_args_list[1].args
    assert "INSERT INTO ajustes_vacios" in consulta_insert
    assert "stock_sistema" in consulta_insert
    assert parametros_insert == (200, 1, -5, "Se rompieron dos", 40)
    conexion.commit.assert_called_once()


def test_listar_ajustes_vacios_por_rango_incluye_los_anulados_marcados():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_ajustes_vacios_por_rango(date(2026, 8, 12), date(2026, 8, 19))

    consulta, parametros = cursor.execute.call_args.args
    # Los anulados VIAJAN (con su anulado_el) para verse tachados en
    # Movimientos: no se filtran.
    assert "anulado_el IS NULL" not in consulta
    assert "a.anulado_el" in consulta
    assert "a.motivo" in consulta
    assert "a.creado_en >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires') AND a.creado_en < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')" in consulta
    assert parametros == (date(2026, 8, 12), date(2026, 8, 19))


def test_anular_ajuste_vacios_es_baja_logica_no_delete():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_ajuste_vacios(30)

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE ajustes_vacios SET anulado_el = now()" in consulta
    assert "DELETE" not in consulta
    assert "anulado_el IS NULL" in consulta
    assert parametros == (30,)


def test_stock_vacios_esconde_lo_cerrado_pero_nunca_lo_que_tiene_saldo():
    """Cerrado = dado de baja (el tipo o el proveedor) Y en cero: no se muestra.

    Un par cerrado en cero es un renglón de algo que ya no existe: el que lo
    dio de baja ya decidió que no lo quiere ver. Pero un par dado de baja al
    que le QUEDA saldo se sigue mostrando — esconder cajones que están en el
    galpón sería mentir.
    """
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock_vacios()

    consulta = cursor.execute.call_args[0][0]
    assert "WHERE (t.activo AND p.activo)" in consulta
    assert "COALESCE(r.total, 0) - COALESCE(d.total, 0) + COALESCE(aj.total, 0) <> 0" in consulta


def test_stock_vacios_de_tipo_suma_los_ajustes_y_excluye_anulados():
    conexion, cursor = _conexion_falsa([(62,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock = stock_vacios_de_tipo(200, 1)

    assert stock == 62
    consulta, parametros = cursor.execute.call_args.args
    assert "FROM ajustes_vacios" in consulta
    assert consulta.count("anulado_el IS NULL") == 3
    assert parametros == (200, 1, 200, 1, 200, 1)


def test_crear_conteo_vacios_graba_la_foto_del_stock_y_no_la_devuelve():
    # El stock del sistema al momento de contar queda en la fila, pero la
    # función NO lo retorna: el empleado nunca puede verlo (control cruzado).
    conexion, cursor = _conexion_falsa([(40,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = crear_conteo_vacios(200, 1, 35)

    assert resultado is None
    consulta_insert, parametros_insert = cursor.execute.call_args_list[1].args
    assert "INSERT INTO conteos_vacios" in consulta_insert
    assert parametros_insert == (200, 1, 35, 40)
    conexion.commit.assert_called_once()


def test_listar_conteos_vacios_de_fecha_no_trae_el_stock_del_sistema():
    # Esta lista va a la pantalla del empleado: stock_sistema no puede
    # viajar ni escondido en su HTML.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_conteos_vacios_de_fecha(date(2026, 8, 19))

    consulta = cursor.execute.call_args[0][0]
    assert "stock_sistema" not in consulta


def test_listar_ultimos_conteos_vacios_toma_el_ultimo_por_proveedor_y_tipo():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_ultimos_conteos_vacios()

    consulta = cursor.execute.call_args[0][0]
    assert "DISTINCT ON (c.proveedor_id, c.tipo_envase_id)" in consulta
    assert "c.creado_en DESC" in consulta
    assert "stock_sistema" in consulta


def test_los_conteos_del_cotejo_traen_los_ajustes_hechos_DESPUES_del_conteo():
    """Sin esto el Cotejo no se pone en verde nunca y el módulo se abandona.

    "Ajustar a lo contado" escribe un ajuste, NO un conteo nuevo. Si la
    pantalla solo tiene lo contado y la foto congelada, la misma diferencia
    queda en rojo para siempre. Lo que la resuelve es un ajuste POSTERIOR al
    conteo, y por eso la consulta lo trae.
    """
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_ultimos_conteos_vacios()

    consulta = cursor.execute.call_args[0][0]
    assert "a.creado_en > c.creado_en" in consulta
    assert "AS ajustes_posteriores" in consulta
    # Y el saldo de hoy, que lo necesita el par dado de baja con stock.
    assert "AS stock_actual" in consulta
    # Si el par sigue vivo: es lo que separa "cerrado" de "hay que cerrarlo".
    assert "p.activo AS proveedor_activo" in consulta
    assert "t.activo AS tipo_activo" in consulta


def test_dar_de_baja_un_tipo_con_saldo_se_niega_y_no_toca_la_base():
    # La regla que hace que "de baja" signifique algo: saldo cero, cuenta
    # cerrada. Sin esto el tipo salía de los selects pero seguía con cajones
    # adentro — medio vivo y medio muerto.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(200, "cajón madera"), (12,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            desactivar_tipo_envase_puesto(3)

    assert "cajón madera" in str(error.value)
    assert "12" in str(error.value)
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_dar_de_baja_un_tipo_sin_saldo_lo_desactiva():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(200, "cajón madera"), (0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        desactivar_tipo_envase_puesto(3)

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE tipos_envase_puesto SET activo = false" in consulta
    assert parametros == (3,)
    conexion.commit.assert_called_once()


def test_dar_de_baja_un_proveedor_mira_TODOS_sus_tipos():
    # Dar de baja al proveedor NO da de baja sus tipos: mirar uno solo
    # dejaría pasar el resto. El error los nombra a todos con su número.
    conexion, cursor = _conexion_falsa(filas_fetchone=[("Gómez",)])
    cursor.fetchall.return_value = [(1, "cajón madera", 12), (2, "cajón plástico", -3)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            desactivar_proveedor_puesto(200)

    assert "cajón madera: 12" in str(error.value)
    assert "cajón plástico: -3" in str(error.value)
    consulta_saldos = cursor.execute.call_args_list[1].args[0]
    assert "WHERE t.proveedor_id = %s" in consulta_saldos
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_dar_de_baja_un_proveedor_sin_saldo_lo_desactiva():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("Gómez",)])
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        desactivar_proveedor_puesto(200)

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE proveedores_puesto SET activo = false" in consulta
    assert parametros == (200,)
    conexion.commit.assert_called_once()


def test_renombrar_un_tipo_corrige_el_nombre_sin_tocar_el_id():
    # Corrección de tipeo: UPDATE directo, sin historial y sin fila nueva.
    # El id es lo que mantiene colgados los movimientos viejos.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(200, True, True), None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        renombrar_tipo_envase_puesto(3, "cajón madera")

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE tipos_envase_puesto SET nombre = %s WHERE id = %s" in consulta
    assert parametros == ("cajón madera", 3)
    assert not any("INSERT" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_called_once()


def test_renombrar_un_tipo_al_nombre_de_otro_del_mismo_proveedor_se_niega():
    # El choque tiene que salir por ValueError NOMBRANDO al que ya existe:
    # si llegara al UNIQUE de la tabla, la pantalla mostraría un 500.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(200, True, True), ("cajón madera",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            renombrar_tipo_envase_puesto(3, "cajón madera")

    assert "cajón madera" in str(error.value)
    # El repetido se busca DENTRO del mismo proveedor y sin contarse a sí mismo.
    consulta_repetido, parametros_repetido = cursor.execute.call_args_list[1].args
    assert "proveedor_id = %s AND nombre = %s AND id <> %s" in consulta_repetido
    assert parametros_repetido == (200, "cajón madera", 3)
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_renombrar_un_tipo_dado_de_baja_se_niega():
    # La pantalla no los lista, pero un POST a mano no tiene que poder
    # revivir el nombre de algo que ya está fuera de circulación.
    for tipo_activo, proveedor_activo in ((False, True), (True, False)):
        conexion, cursor = _conexion_falsa(filas_fetchone=[(200, tipo_activo, proveedor_activo)])

        with patch("app.db.obtener_conexion", return_value=conexion):
            with pytest.raises(ValueError) as error:
                renombrar_tipo_envase_puesto(3, "cajón madera")

        assert "de baja" in str(error.value)
        assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
        conexion.commit.assert_not_called()


def test_renombrar_un_proveedor_escribe_TAMBIEN_el_normalizado():
    """Si solo se actualizara el nombre, el normalizado quedaría mintiendo.

    El normalizado es la identidad con la que el alta decide reusar o crear:
    con el viejo adentro, la próxima alta escribiendo el nombre nuevo no
    reusaría este proveedor, crearía un duplicado.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(True,), None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        renombrar_proveedor_puesto(200, "Gómez", "gomez")

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE proveedores_puesto SET nombre = %s, nombre_normalizado = %s" in consulta
    assert parametros == ("Gómez", "gomez", 200)
    conexion.commit.assert_called_once()


def test_renombrar_un_proveedor_al_nombre_de_otro_se_niega_por_el_normalizado():
    # "GOMEZ" y "Gómez" son el mismo: el choque se busca por normalizado,
    # no por el nombre tal cual se escribió.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(True,), ("Gómez",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            renombrar_proveedor_puesto(200, "GOMEZ", "gomez")

    assert "Gómez" in str(error.value)
    consulta_repetido, parametros_repetido = cursor.execute.call_args_list[1].args
    assert "nombre_normalizado = %s AND id <> %s" in consulta_repetido
    assert parametros_repetido == ("gomez", 200)
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_renombrar_un_proveedor_dado_de_baja_se_niega():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(False,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            renombrar_proveedor_puesto(200, "Gómez", "gomez")

    assert "de baja" in str(error.value)
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_las_senas_toman_el_valor_del_dia_QUE_SE_RECIBIERON_no_el_de_hoy():
    """El ancla es v.creado_en::date, no CURRENT_DATE.

    Lo que se le debe al cliente se fijó cuando dejó los cajones. Si la
    consulta anclara en hoy, subir el valor de la seña reescribiría de
    golpe lo que se le debe por todo lo recibido antes.
    """
    for funcion in (listar_senas_pendientes, listar_senas_resueltas):
        conexion, cursor = _conexion_falsa(filas_fetchall=[])

        with patch("app.db.obtener_conexion", return_value=conexion):
            funcion()

        consulta = cursor.execute.call_args[0][0]
        assert "h.vigente_desde <= (v.creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date" in consulta
        assert "CURRENT_DATE" not in consulta
        assert "ORDER BY h.vigente_desde DESC" in consulta


def test_TODAS_las_consultas_desempatan_por_creado_en_dentro_de_la_misma_fecha():
    """Sin UNIQUE por fecha, una fecha puede tener varias filas.

    Ordenando solo por vigente_desde, con dos filas de esa fecha la base
    devuelve cualquiera de las dos — a veces el monto viejo, sin nada que
    lo delate. creado_en DESC es lo que hace ganar a la última cargada, y
    tiene que estar en las CUATRO consultas que resuelven vigencia, no en
    la que uno se acordó.
    """
    for funcion, argumentos in (
        (listar_senas_pendientes, ()),
        (listar_senas_resueltas, ()),
        (listar_valores_sena, ()),
        (contar_senas_afectadas_por_valor, (3, 500, date(2026, 8, 10))),
    ):
        conexion, cursor = _conexion_falsa(filas_fetchall=[], filas_fetchone=[(0,)])

        with patch("app.db.obtener_conexion", return_value=conexion):
            funcion(*argumentos)

        consulta = cursor.execute.call_args[0][0]
        assert "vigente_desde DESC, h.creado_en DESC" in consulta.replace("h.vigente_desde", "vigente_desde"), \
            f"{funcion.__name__} resuelve la vigencia sin desempatar por creado_en"


def test_asignar_ficha_a_reproceso_toca_la_ficha_Y_EL_ENVASE_QUE_VIAJA_CON_ELLA():
    """Este test decía "solo toca la ficha" y dejó de ser cierto el 16/09.

    No se aflojó el assert: cambió lo que hay que afirmar. Una guía R sin
    ficha no tiene de dónde derivar en qué caja se armó, así que queda "sin
    declarar" y el stock de cajas la muestra como hueco. Asignar la ficha es
    LO QUE contesta esa pregunta, y si el UPDATE no la completara el hueco
    quedaría abierto para siempre sin que nada lo señale.

    Lo que SIGUE siendo cierto, y por eso se queda abajo: los consumos y el
    costo se congelaron al cargar la guía y no se recalculan.
    """
    # La tercera fila es la de la ficha que lee `_envase_de_esta_guia`:
    # envase 5, fijo. Puesta a propósito distinta de las otras dos para que
    # el envase no pueda salir bien por copiar el número de al lado.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, 1, False), (7, 1), (5, False)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        asignar_ficha_a_reproceso(12, 901)

    consulta, parametros = cursor.execute.call_args.args
    assert "SET ficha_id = %s, lleva_caja_nuestra = %s, envase_id = %s" in consulta
    assert parametros == (901, True, 5, 12)
    # Nada de recalcular: los consumos no se tocan.
    assert not any("reprocesos_consumos" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_called_once()


def test_desasignar_deja_el_envase_SIN_DECLARAR_y_no_en_cero():
    """Sacarle la ficha a una guía vuelve a abrir el hueco, que es la verdad.

    Escribir `false` diría "esta guía no llevó caja nuestra", que es una
    afirmación; el NULL dice "no sabemos", que es lo que pasa. La diferencia
    se ve en el stock: `false` lo daría por cerrado y el NULL lo cuenta como
    guía sin declarar.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, 1, False)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        asignar_ficha_a_reproceso(12, None)

    _, parametros = cursor.execute.call_args.args
    assert parametros == (None, None, None, 12)


def test_no_se_puede_asignar_una_ficha_de_OTRO_articulo():
    """El stock de cajas de una ficha es "reprocesadas menos salidas".

    Una ficha de otro artículo inventaría cajas que no existen, y el
    Cotejo mostraría un rojo imposible de explicar.
    """
    # La guía es del artículo 7; la ficha, del 9.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, 1, False), (9, 1)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            asignar_ficha_a_reproceso(12, 901)

    assert "otro artículo" in str(error.value)
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_no_se_puede_asignar_una_ficha_de_OTRO_CLIENTE():
    """La pared va donde se ESCRIBE, no donde se muestra.

    Que el selector deje de ofrecer las fichas de otros clientes no alcanza:
    un formulario armado a mano entra igual. Es el mismo hallazgo del cajón
    con envase.

    Medido antes de cerrarla (Frutamax, 11/09): 0 cruces en 198 guías
    comparables, con `sin_cliente_no_se_juzga` en 0 — o sea que las 198 se
    compararon de verdad. El caso nunca pasó, y la pantalla de armar nunca
    lo permitió: era la misma regla en dos pantallas con dos durezas.
    """
    # La guía se armó para el cliente 1; la ficha es del 2. MISMO artículo,
    # así que la guarda vieja no alcanza para frenarla.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, 1, False), (7, 2)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            asignar_ficha_a_reproceso(12, 901)

    assert "otro cliente" in str(error.value)
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_una_guia_SIN_cliente_acepta_cualquier_ficha_del_articulo():
    """Las guías viejas no tienen cliente: no hay contra qué comparar.

    Si la guarda las frenara quedarían sin poder asignarse NUNCA, que es
    peor que el cruce que viene a evitar. Hoy son cero; este test existe
    para el día que aparezca una.
    """
    conexion, cursor = _conexion_falsa(
        filas_fetchone=[(7, None, False), (7, 2), _ENVASE_DE_LA_FICHA])

    with patch("app.db.obtener_conexion", return_value=conexion):
        asignar_ficha_a_reproceso(12, 901)

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE reprocesos" in consulta and "SET ficha_id = %s" in consulta
    # Y el envase viaja con la ficha, también acá: la guía vieja sin cliente
    # no es un caso aparte para eso.
    assert parametros == (901, True, 42, 12)
    conexion.commit.assert_called_once()


def test_una_guia_anulada_no_se_asigna():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, 1, True)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            asignar_ficha_a_reproceso(12, 901)

    assert "anulada" in str(error.value)
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)


def test_desasignar_una_guia_se_permite_y_no_valida_ficha():
    # Volver a "sin asignar" es legítimo: el que se equivocó de ficha
    # tiene que poder sacarla sin inventar otra.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, 1, False)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        asignar_ficha_a_reproceso(12, None)

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE reprocesos" in consulta and "SET ficha_id = %s" in consulta
    # El envase se va con la ficha: ver el test de arriba sobre por qué NULL
    # y no false.
    assert parametros == (None, None, None, 12)
    # No sale a buscar una ficha que no existe.
    assert not any("FROM fichas_logistica" in c.args[0] for c in cursor.execute.call_args_list)


def test_una_ficha_con_guias_R_NO_se_borra_y_lo_dice_con_el_numero():
    """Lo que la migración de la etapa 1 volvió necesario.

    La FK es NO ACTION a propósito: con SET NULL, borrar una ficha
    nulearía sus guías R en silencio y un reproceso asignado quedaría
    indistinguible de uno SIN ASIGNAR — además de mover el stock de esa
    ficha sin que nadie lo pida. Se niega acá con el número adentro, en
    vez de dejar que reviente la foreign key con un 500.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(3,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            eliminar_ficha(901)

    assert "3 guías R cargadas" in str(error.value)
    assert not any("DELETE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_una_ficha_sin_guias_R_se_borra_como_siempre():
    # TRES conteos: guías R, compras que la marcan como "viene armada", y
    # precios cargados. Los tres en cero es el caso feliz, y es el único
    # que distingue una guarda que funciona de una que siempre frena.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0,), (0,), (0,), None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        eliminar_ficha(901)

    assert any("DELETE FROM fichas_logistica" in c.args[0] for c in cursor.execute.call_args_list)


def test_los_historiales_de_todos_los_tipos_salen_en_UNA_consulta():
    # La pantalla de Tipos lista todos los tipos con su historial: pedirlo
    # tipo por tipo es un N+1 que crece con el catálogo.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_historiales_valores_sena([1, 2, 3])

    assert cursor.execute.call_count == 1
    consulta, parametros = cursor.execute.call_args.args
    assert "tipo_envase_id = ANY(%s)" in consulta
    assert parametros == ([1, 2, 3],)
    # Los que no tienen ninguna fila vienen con lista vacía, no ausentes:
    # el que pregunta no tiene que andar con .get().
    assert resultado == {1: [], 2: [], 3: []}


def test_el_historial_batcheado_particiona_por_TIPO_y_fecha():
    # Sin el tipo en el PARTITION, la fecha de un tipo pisaría la de otro
    # y marcaría como reemplazadas filas que sí rigen.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_historiales_valores_sena([1, 2])

    consulta = cursor.execute.call_args[0][0]
    assert "PARTITION BY tipo_envase_id, vigente_desde" in consulta
    assert "ORDER BY tipo_envase_id, vigente_desde DESC, creado_en DESC" in consulta


def test_sin_tipos_el_batch_no_va_a_la_base():
    with patch("app.db.obtener_conexion") as mock_conexion:
        assert listar_historiales_valores_sena([]) == {}
    mock_conexion.assert_not_called()


def test_el_historial_marca_cual_fila_de_la_misma_fecha_quedo_reemplazada():
    # Dos montos para el mismo día sin decir cuál ganó es peor que no
    # mostrar nada.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_historial_valores_sena(3)

    consulta = cursor.execute.call_args[0][0]
    assert "max(creado_en) OVER (PARTITION BY vigente_desde)" in consulta
    assert "AS reemplazada" in consulta
    assert "ORDER BY vigente_desde DESC, creado_en DESC" in consulta


def test_una_sena_sin_valor_cargado_NO_desaparece_del_listado():
    # LEFT JOIN LATERAL, no CROSS: con CROSS, un tipo sin valor cargado
    # haría desaparecer la seña de la pantalla y la cajera no se enteraría
    # de que tiene un pendiente. Sin valor es NULL, no "no existe".
    for funcion in (listar_senas_pendientes, listar_senas_resueltas):
        conexion, cursor = _conexion_falsa(filas_fetchall=[])

        with patch("app.db.obtener_conexion", return_value=conexion):
            funcion()

        consulta = cursor.execute.call_args[0][0]
        assert "LEFT JOIN LATERAL" in consulta
        assert "CROSS JOIN LATERAL" not in consulta


def test_el_valor_de_la_sena_se_resuelve_en_UNA_sola_consulta():
    # El N+1 que había que no hacer: una consulta por seña para buscarle
    # el valor. El LATERAL lo trae en la misma.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_senas_pendientes()

    assert cursor.execute.call_count == 1


def test_listar_valores_sena_devuelve_NULL_para_el_tipo_sin_valor_cargado():
    # Sin filas es NULL, nunca 0: "no lleva seña" y "todavía no lo
    # cargamos" son cosas distintas y la pantalla las dice distinto.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_valores_sena()

    consulta = cursor.execute.call_args[0][0]
    assert "LEFT JOIN LATERAL" in consulta
    # Nada de COALESCE(monto, 0): eso convertiría "sin valor cargado" en un
    # cero que parece un dato real y la pantalla ya no podría distinguirlos.
    assert "COALESCE" not in consulta.upper()
    # Solo tipos vivos, y de proveedor vivo.
    assert "WHERE t.activo AND p.activo" in consulta


def test_cargar_valor_sena_SIEMPRE_agrega_una_fila_y_nunca_pisa_la_anterior():
    """Append-only de verdad, no de nombre.

    Con ON CONFLICT DO UPDATE, recargar una fecha ya cargada pisaba el
    monto anterior y el número viejo se perdía sin rastro. Ese UPDATE es
    lo que se sacó: ahora la fecha repetida agrega otra fila y gana por
    creado_en.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(True,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        cargar_valor_sena(3, 500, date(2026, 8, 20))

    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO senas_valor_historial" in consulta
    assert parametros == (3, 500, date(2026, 8, 20))
    # Nada que pise ni borre una fila que ya está.
    assert "ON CONFLICT" not in consulta
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)
    assert not any("DELETE" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_called_once()


def test_cargar_valor_sena_a_un_tipo_dado_de_baja_se_niega():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(False,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            cargar_valor_sena(3, 500, date(2026, 8, 20))

    assert "de baja" in str(error.value)
    assert not any("INSERT" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_el_aviso_retroactivo_cuenta_solo_las_senas_que_de_verdad_cambian():
    """Las tres condiciones, que son las que hacen que el número no mienta.

    Una seña se cuenta solo si: se recibió en la fecha nueva o después; la
    fila nueva le gana a la que tiene hoy; y el monto que le queda es
    distinto del que ya tenía. Sin la tercera, recargar el mismo número
    avisaría "esto cambia N señas" sin cambiar ninguna.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert contar_senas_afectadas_por_valor(3, 500, date(2026, 8, 10)) == 7

    consulta, parametros = cursor.execute.call_args.args
    assert "v.creado_en >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')" in consulta
    assert "actual.vigente_desde IS NULL OR actual.vigente_desde <= %s" in consulta
    assert "actual.monto IS DISTINCT FROM %s" in consulta
    # Una anulada no es una seña que se le deba a nadie: no se cuenta.
    assert "v.anulado_el IS NULL" in consulta
    assert parametros == (3, date(2026, 8, 10), date(2026, 8, 10), 500)


def test_cerrar_sena_escribe_la_columna_del_cierre_elegido():
    # Los tres cierres, cada uno con su columna de fecha: qué pasó lo dice
    # la columna, cuándo lo dice la fecha.
    for cierre, columna in (("pagada", "sena_pagada_el"), ("vale", "sena_vale_el"), ("anulada", "sena_anulada_el")):
        conexion, cursor = _conexion_falsa()

        with patch("app.db.obtener_conexion", return_value=conexion):
            cerrar_sena(5, cierre)

        consulta, parametros = cursor.execute.call_args.args
        assert f"SET {columna} = now()" in consulta
        # Solo pendientes vigentes: no pisa un cierre anterior (las TRES en
        # NULL) ni "cierra" un movimiento anulado.
        assert "sena_pagada_el IS NULL AND sena_vale_el IS NULL AND sena_anulada_el IS NULL" in consulta
        assert "anulado_el IS NULL" in consulta
        assert parametros == (5,)
        conexion.commit.assert_called_once()


def test_cerrar_sena_con_cierre_desconocido_lanza_error_sin_tocar_la_base():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError):
            cerrar_sena(5, "regalada")

    cursor.execute.assert_not_called()


def test_listar_senas_pendientes_exige_los_tres_cierres_en_null():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_senas_pendientes()

    consulta = cursor.execute.call_args[0][0]
    assert "v.sena_pagada_el IS NULL AND v.sena_vale_el IS NULL AND v.sena_anulada_el IS NULL" in consulta
    assert "v.anulado_el IS NULL" in consulta


def test_listar_senas_pendientes_pone_las_mas_nuevas_arriba():
    """La cajera necesita ver arriba lo que se acaba de recibir: es lo que alguien
    viene a cobrar ahora. Las viejas —la gente que no vino— bajan solas y quedan
    abajo, sin perderse."""
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_senas_pendientes()

    consulta = cursor.execute.call_args[0][0]
    assert "ORDER BY v.creado_en DESC" in consulta
    # El desempate por id evita que dos señas del mismo instante bailen de
    # lugar entre una carga y la siguiente.
    assert "v.creado_en DESC, v.id DESC" in consulta


def test_listar_senas_resueltas_trae_el_tipo_de_cierre_y_su_fecha():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_senas_resueltas()

    consulta = cursor.execute.call_args[0][0]
    assert "'pagada'" in consulta
    assert "'vale'" in consulta
    assert "'anulada'" in consulta
    assert "AS cierre" in consulta
    assert "AS cerrada_el" in consulta
    # Ordenado por el ÚLTIMO hecho, el más reciente primero. El caducado va
    # primero en el coalesce: un vale de marzo dado de baja hoy tiene que
    # aparecer arriba, no perdido en marzo.
    assert ("ORDER BY COALESCE(v.sena_vale_caducado_el, v.sena_pagada_el,\n"
            "                                  v.sena_vale_el, v.sena_anulada_el) DESC") in consulta


def test_el_historial_distingue_el_vale_VIVO_del_dado_por_NO_COBRADO():
    """La diferencia es si todavía se le debe la plata, así que no pueden
    mostrarse igual. Y el caducado se evalúa ANTES que el vale en el CASE:
    los dos timestamps conviven, y el que manda es el último."""
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_senas_resueltas()

    consulta = " ".join(cursor.execute.call_args[0][0].split())
    assert "'vale_caducado'" in consulta
    assert consulta.index("'vale_caducado'") < consulta.index("THEN 'vale'")
    # Y trae las dos fechas y el motivo, que es lo que se lee a los seis meses.
    assert "v.sena_vale_el," in consulta
    assert "v.sena_vale_caducado_el, v.sena_vale_caducado_motivo" in consulta


def test_caducar_vale_NO_borra_el_vale_y_exige_motivo():
    """Las dos fechas conviven a propósito: el vale existió y el papel puede
    aparecer. Taparlo con "anulada" perdería justo el dato que administración
    necesita ese día."""
    from app.db import caducar_vale

    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 1

    with patch("app.db.obtener_conexion", return_value=conexion):
        caducar_vale(74, "  el cliente no volvió desde septiembre  ")

    consulta, parametros = cursor.execute.call_args.args
    assert "SET sena_vale_caducado_el = now()" in consulta
    # NO toca sena_vale_el ni el stock.
    assert "sena_vale_el = NULL" not in consulta
    assert "anulado_el = now()" not in consulta
    # Solo sobre un vale vivo y una entrada vigente.
    assert "sena_vale_el IS NOT NULL AND sena_vale_caducado_el IS NULL" in consulta
    assert "anulado_el IS NULL" in consulta
    # El motivo va limpio de espacios.
    assert parametros == ("el cliente no volvió desde septiembre", 74)


def test_caducar_vale_sin_motivo_no_escribe_nada():
    """Como no hay login, ese texto es el único rastro del porqué."""
    from app.db import caducar_vale

    conexion, _cursor = _conexion_falsa()
    with patch("app.db.obtener_conexion", return_value=conexion):
        for vacio in ("", "   ", None):
            with pytest.raises(ValueError):
                caducar_vale(74, vacio)
    conexion.commit.assert_not_called()


def test_caducar_vale_dice_POR_QUE_no_se_pudo():
    from app.db import ValeNoCaducable, caducar_vale

    casos = (
        ((True, False, False), "sin_vale"),
        ((False, True, False), "ya_caducado"),
        ((False, False, True), "anulada"),
        (None, "sin_vale"),
    )
    for fila, esperado in casos:
        conexion, cursor = _conexion_falsa(filas_fetchone=[fila])
        cursor.rowcount = 0
        with patch("app.db.obtener_conexion", return_value=conexion):
            with pytest.raises(ValeNoCaducable) as levantada:
                caducar_vale(74, "un motivo")
        assert levantada.value.motivo_tecnico == esperado
        conexion.commit.assert_not_called()


def test_listar_tipos_envase_puesto_joinea_proveedores_del_puesto():
    # Los tipos (y todo Vacíos) joinean proveedores_puesto, NUNCA la tabla
    # proveedores de Compras: circuitos separados.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_tipos_envase_puesto()

    consulta = cursor.execute.call_args[0][0]
    assert "JOIN proveedores_puesto p" in consulta
    assert "codigo_puesto" not in consulta


def test_obtener_o_crear_proveedor_puesto_unifica_por_nombre_normalizado():
    conexion, cursor = _conexion_falsa([(7, True)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        proveedor_id = obtener_o_crear_proveedor_puesto("EL Cajónero", "el cajonero")

    assert proveedor_id == 7
    assert cursor.execute.call_count == 1  # solo el SELECT: reusa, no duplica


def test_obtener_o_crear_proveedor_puesto_crea_si_no_existe():
    conexion, cursor = _conexion_falsa([None, (9,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        proveedor_id = obtener_o_crear_proveedor_puesto("Nuevo", "nuevo")

    assert proveedor_id == 9
    consulta_insert, parametros_insert = cursor.execute.call_args_list[1].args
    assert "INSERT INTO proveedores_puesto" in consulta_insert
    assert parametros_insert == ("Nuevo", "nuevo")


# ----------------------------------------------------------------------------
# Bitácora de fichas: toda alta/edición/borrado deja su foto en la MISMA
# transacción (un solo commit) — si la foto falla, el cambio tampoco entra.
# ----------------------------------------------------------------------------


def test_crear_ficha_deja_la_foto_de_alta_en_la_bitacora():
    conexion, cursor = _conexion_falsa([(33,)])  # RETURNING id de la ficha nueva

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_ficha(5, 1, 100, 6, "kilo", False, "BERENJENA", "B01")

    consulta_insert = cursor.execute.call_args_list[0].args[0]
    assert "INSERT INTO fichas_logistica" in consulta_insert
    assert "RETURNING id" in consulta_insert
    consulta_foto, parametros_foto = cursor.execute.call_args_list[1].args
    assert "INSERT INTO fichas_logistica_historial" in consulta_foto
    assert parametros_foto == (33, 1, 5, 100, 6, "kilo", False, "BERENJENA", "B01", "alta")
    conexion.commit.assert_called_once()


def test_actualizar_ficha_deja_la_foto_de_edicion_en_la_bitacora():
    conexion, cursor = _conexion_falsa([(1, 5)])  # RETURNING cliente_id, articulo_id

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_ficha(10, 100, 8, "kilo", True, "BERENJENA", None)

    consulta_foto, parametros_foto = cursor.execute.call_args_list[1].args
    assert "INSERT INTO fichas_logistica_historial" in consulta_foto
    assert parametros_foto == (10, 1, 5, 100, 8, "kilo", True, "BERENJENA", None, "edicion")
    conexion.commit.assert_called_once()


def test_actualizar_ficha_inexistente_no_escribe_bitacora():
    conexion, cursor = _conexion_falsa([None])  # el UPDATE no encontró la ficha

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_ficha(999, 100, 8, "kilo", True)

    assert cursor.execute.call_count == 1  # solo el UPDATE, sin foto fantasma


def test_eliminar_ficha_deja_el_estado_final_en_la_bitacora():
    # Los tres primeros fetchone son las guardas (guías R, compras armadas,
    # precios): en cero, sigue de largo y borra como siempre.
    conexion, cursor = _conexion_falsa(
        [(0,), (0,), (0,), (1, 5, 100, 6, "kilo", False, "BERENJENA", None)]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        eliminar_ficha(10)

    # Por FRAGMENTO y no por posición: la guarda de las compras que vienen
    # armadas entró en el medio, y correr los índices rompe tests que no
    # hablan de eso.
    consulta_delete = _sql_que_contiene(cursor, "DELETE FROM fichas_logistica")
    assert "DELETE FROM fichas_logistica WHERE id = %s" in consulta_delete
    assert "RETURNING" in consulta_delete
    consulta_foto, parametros_foto = _sql_y_parametros_que_contienen(
        cursor, "INSERT INTO fichas_logistica_historial"
    )
    assert parametros_foto == (10, 1, 5, 100, 6, "kilo", False, "BERENJENA", None, "borrado")
    conexion.commit.assert_called_once()


def test_cambiar_articulo_de_ficha_es_borrado_mas_alta_con_el_alias_de_la_pantalla():
    conexion, cursor = _conexion_falsa(
        [
            (0,),  # la guarda de precios: sin precios, sigue de largo
            (1, 4, 100, 6, "kilo", False, "ANANA", "90137"),  # DELETE RETURNING (ficha vieja)
            (33,),  # RETURNING id de la ficha nueva
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        # El alias lo manda la pantalla (editable): acá el destino es otro
        # producto y el usuario lo corrigió — la ficha nueva NO hereda
        # "ANANA" a ciegas.
        ficha_nueva_id = cambiar_articulo_de_ficha(10, 5, "ANCO", "90200")

    assert ficha_nueva_id == 33
    # La guarda de precios + 4 pasos en UNA transacción: delete + foto
    # borrado + insert + foto alta.
    assert cursor.execute.call_count == 5
    # La foto del borrado conserva el alias VIEJO (es el estado que se cerró).
    _, parametros_borrado = cursor.execute.call_args_list[2].args
    assert parametros_borrado == (10, 1, 4, 100, 6, "kilo", False, "ANANA", "90137", "borrado")
    consulta_insert, parametros_insert = cursor.execute.call_args_list[3].args
    assert "INSERT INTO fichas_logistica" in consulta_insert
    # La ficha nueva apunta al artículo nuevo, conserva envase/contenido/
    # unidad, y lleva el alias que vino de la pantalla.
    assert parametros_insert == (5, 1, 100, 6, "kilo", False, "ANCO", "90200")
    _, parametros_alta = cursor.execute.call_args_list[4].args
    assert parametros_alta == (33, 1, 5, 100, 6, "kilo", False, "ANCO", "90200", "alta")
    conexion.commit.assert_called_once()


def test_cambiar_articulo_de_ficha_inexistente_devuelve_none_sin_escribir():
    # Una ficha que no existe no tiene precios, así que la guarda la deja
    # pasar y el DELETE no encuentra nada.
    conexion, cursor = _conexion_falsa([(0,), None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = cambiar_articulo_de_ficha(999, 5, None, None)

    assert resultado is None
    assert cursor.execute.call_count == 2


def test_listar_historial_fichas_va_de_lo_mas_nuevo_a_lo_mas_viejo():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_historial_fichas_por_cliente(1)

    consulta, parametros = cursor.execute.call_args.args
    assert "FROM fichas_logistica_historial h" in consulta
    assert "ORDER BY h.registrado_en DESC, h.id DESC" in consulta
    assert parametros == (1,)


def test_stock_vacios_sin_fecha_no_filtra_por_creado_en():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock_vacios()

    consulta, parametros = cursor.execute.call_args.args
    assert "creado_en" not in consulta
    assert parametros == tuple()


def test_stock_vacios_a_fecha_filtra_las_tres_sumas_y_excluye_anulados_siempre():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock_vacios(date(2026, 8, 10))

    consulta, parametros = cursor.execute.call_args.args
    # Las TRES sumas (recibidos, devueltos, ajustes) cortan a la fecha, con
    # el patrón sargable de siempre.
    assert consulta.count("AND creado_en < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')") == 3
    assert parametros == (date(2026, 8, 10), date(2026, 8, 10), date(2026, 8, 10))
    # Los anulados quedan afuera SIEMPRE (sin mirar cuándo se anularon): un
    # movimiento anulado no existió nunca, ni siquiera en fechas anteriores
    # a su anulación.
    assert consulta.count("anulado_el IS NULL") == 3
    assert "anulado_el <" not in consulta


def test_buscar_ingresos_deposito_filtra_por_dia_de_recepcion_y_estado_default():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_ingresos_deposito(date(2026, 8, 17), date(2026, 8, 18))

    consulta, parametros = cursor.execute.call_args.args
    # El rango es por el día de la RECEPCIÓN (patrón sargable sobre
    # procesada_el), no por la fecha de compra.
    assert "c.procesada_el >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')" in consulta
    assert "c.procesada_el < ((%s::date + 1)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')" in consulta
    # Default: solo lo que hay que pagar (los rechazos parciales entran
    # solos: son estado 'recepcionado').
    assert "c.estado = %s" in consulta
    assert parametros == [date(2026, 8, 17), date(2026, 8, 18), "recepcionado"]
    # Cantidades REALES en el SELECT, nunca las del comprador.
    assert "c.cantidad_cajones_real" in consulta
    assert "c.cantidad_cajones," not in consulta
    assert "c.cantidad_cajones_rechazada" in consulta
    # Ordenado por proveedor, para armar los subtotales de una pasada.
    assert "ORDER BY p.nombre" in consulta


def test_buscar_ingresos_deposito_estado_none_trae_las_tres_procesadas():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_ingresos_deposito(date(2026, 8, 17), date(2026, 8, 18), proveedor_id=7, estado=None, limite=501)

    consulta, parametros = cursor.execute.call_args.args
    assert "c.estado IN ('recepcionado', 'rechazado', 'no_ingresado')" in consulta
    assert "c.proveedor_id = %s" in consulta
    assert "LIMIT %s" in consulta
    assert parametros == [date(2026, 8, 17), date(2026, 8, 18), 7, 501]


def test_contar_ingresos_deposito_usa_las_mismas_condiciones():
    conexion, cursor = _conexion_falsa([(42,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        total = contar_ingresos_deposito(date(2026, 8, 17), date(2026, 8, 18), articulo_id=5)

    assert total == 42
    consulta, parametros = cursor.execute.call_args.args
    assert consulta.startswith("SELECT COUNT(*) FROM compras c WHERE ")
    assert "c.articulo_id = %s" in consulta
    assert parametros == [date(2026, 8, 17), date(2026, 8, 18), 5, "recepcionado"]


# --- Pedidos de clientes ---


def test_crear_pedido_guarda_todo_en_una_transaccion():
    conexion, cursor = _conexion_falsa([(51,)])  # RETURNING id de la cabecera

    with patch("app.db.obtener_conexion", return_value=conexion):
        pedido_id = crear_pedido(
            1,
            date(2026, 8, 21),
            "texto",
            "el mail",
            [{"sucursal": "VL", "orden_compra": "1257673", "total_bultos_declarado": 235.0}],
            [{"sucursal": "VL", "articulo_id": 1, "texto_codigo": "90101", "texto_descripcion": "BANANA", "cantidad": 225.0}],
        )

    assert pedido_id == 51
    # 3 inserts (cabecera + 1 sucursal + 1 renglón), un solo commit.
    assert cursor.execute.call_count == 3
    consulta_cabecera, parametros_cabecera = cursor.execute.call_args_list[0].args
    assert "INSERT INTO pedidos " in consulta_cabecera
    assert parametros_cabecera == (1, date(2026, 8, 21), "texto", "el mail", None, None, None)
    conexion.commit.assert_called_once()


def test_crear_pedido_corregido_anula_el_viejo_en_la_misma_transaccion():
    conexion, cursor = _conexion_falsa([(52,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_pedido(1, date(2026, 8, 21), "texto", None, [], [], reemplaza_a_pedido_id=50)

    consulta_anular, parametros_anular = cursor.execute.call_args_list[0].args
    assert "UPDATE pedidos SET anulado_el = now() WHERE id = %s AND anulado_el IS NULL" in consulta_anular
    assert parametros_anular == (50,)
    conexion.commit.assert_called_once()  # todo o nada


def test_obtener_pedido_vigente_ignora_los_anulados():
    conexion, cursor = _conexion_falsa([None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = obtener_pedido_vigente(1, date(2026, 8, 21))

    assert resultado is None
    consulta, parametros = cursor.execute.call_args.args
    assert "p.anulado_el IS NULL" in consulta
    assert "ORDER BY p.creado_en DESC" in consulta
    assert parametros == (1, date(2026, 8, 21))


def test_listar_renglones_pedido_pone_los_sin_identificar_primero():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_renglones_pedido(51)

    consulta, _ = cursor.execute.call_args.args
    assert "ORDER BY (r.articulo_id IS NULL) DESC" in consulta
    assert "LEFT JOIN articulos" in consulta


def test_guardar_alias_en_ficha_solo_completa_vacios_y_deja_bitacora():
    # La ficha tenía nombre pero no código: el UPDATE completa solo el
    # código, y la bitácora recibe la foto de la edición. El RETURNING trae
    # cliente y artículo (ya no viajan como parámetro: la ficha los sabe).
    conexion, cursor = _conexion_falsa([(1, 2, None, None, "kilo", False, "BATATA", "90102")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_alias_en_ficha(903, "90102", "BATATA")

    consulta_update, parametros_update = cursor.execute.call_args_list[0].args
    assert "COALESCE(codigo_cliente, %s)" in consulta_update
    assert "COALESCE(nombre_cliente, %s)" in consulta_update
    # Va por id de ficha, no por (cliente, artículo): con dos fichas del
    # mismo artículo esa clave pisaba las dos.
    assert "WHERE id = %s" in consulta_update
    assert parametros_update == ("90102", "BATATA", 903, "90102", "BATATA")
    consulta_foto, parametros_foto = cursor.execute.call_args_list[1].args
    assert "INSERT INTO fichas_logistica_historial" in consulta_foto
    assert parametros_foto == (903, 1, 2, None, None, "kilo", False, "BATATA", "90102", "edicion")
    conexion.commit.assert_called_once()


def test_guardar_alias_en_ficha_sin_cambios_no_escribe_bitacora():
    conexion, cursor = _conexion_falsa([None])  # el UPDATE no tocó ninguna fila

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_alias_en_ficha(903, "90102", "BATATA")

    assert cursor.execute.call_count == 1


def test_contar_pedidos_con_renglones_sin_identificar_solo_vivos():
    conexion, cursor = _conexion_falsa([(2, date(2026, 8, 3))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_pedidos_con_renglones_sin_identificar()

    assert resultado == {"casos": 2, "mas_viejo": date(2026, 8, 3)}
    consulta = cursor.execute.call_args.args[0]
    assert "p.anulado_el IS NULL" in consulta
    assert "r.articulo_id IS NULL" in consulta


def test_borrar_foto_pedido_devuelve_la_ruta_solo_si_nadie_mas_la_usa():
    conexion, cursor = _conexion_falsa([("2026/pedido-50-x.jpg",), (0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        ruta = borrar_foto_pedido(9)

    assert ruta == "2026/pedido-50-x.jpg"
    conexion.commit.assert_called_once()


def test_marcar_renglon_armado_completo_y_parcial():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_renglon_armado(11)

    consulta, parametros = cursor.execute.call_args_list[0].args
    assert "SET armado_el = now(), cantidad_armada = %s, kilos_enviados = %s" in consulta
    assert parametros == (None, None, 11)
    # Y en la MISMA transacción se va la corrección de lotes vieja: puede
    # estar cambiando la cantidad, y una corrección que reparte 15 bultos
    # sobre un renglón que ahora manda 8 es una mentira guardada.
    assert "DELETE FROM pedidos_renglones_lotes_elegidos" in cursor.execute.call_args_list[1].args[0]

    conexion2, cursor2 = _conexion_falsa()
    with patch("app.db.obtener_conexion", return_value=conexion2):
        marcar_renglon_armado(11, 12.0, 120.0)
    assert cursor2.execute.call_args_list[0].args[1] == (12.0, 120.0, 11)


def test_desmarcar_renglon_armado_borra_tilde_y_cantidad():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        desmarcar_renglon_armado(12)

    consulta, parametros = cursor.execute.call_args_list[0].args
    # Columna por columna: el assert de una línea entera se cae con un salto
    # de línea y no dice cuál falta.
    for columna in ("armado_el = NULL", "cantidad_armada = NULL", "kilos_enviados = NULL"):
        assert columna in consulta, columna
    # Y EL CONTROL DE ADMINISTRACIÓN. No es una cortesía: sin esta columna,
    # el CHECK pedidos_renglones_controlado_solo_armado RECHAZA el UPDATE, y
    # destildar un renglón controlado explota en la cara del que arma.
    assert "controlado_el = NULL" in consulta
    # Y devuelve si HABÍA un control, para que la pantalla pueda avisar.
    assert "RETURNING (controlado_el IS NOT NULL)" in consulta
    assert parametros == (12,)
    # El tilde se fue: ya no hay salida de la que decir de dónde salió.
    assert "DELETE FROM pedidos_renglones_lotes_elegidos" in cursor.execute.call_args_list[1].args[0]
    assert cursor.execute.call_args_list[1].args[1] == (12,)


def test_crear_pedido_corregido_traslada_los_tildes_solo_a_renglones_identicos():
    conexion, cursor = _conexion_falsa([(52,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_pedido(1, date(2026, 8, 21), "texto", None, [], [], reemplaza_a_pedido_id=50)

    # Después de anular e insertar, el UPDATE de traslado: tilde y cantidad
    # parcial viajan SOLO donde sucursal + artículo + cantidad son idénticos.
    consulta_traslado, parametros_traslado = cursor.execute.call_args_list[-1].args
    assert "SET armado_el = viejo.armado_el, cantidad_armada = viejo.cantidad_armada" in consulta_traslado
    assert "nuevo.articulo_id IS NOT NULL AND nuevo.articulo_id = viejo.articulo_id" in consulta_traslado
    assert "nuevo.sucursal IS NOT DISTINCT FROM viejo.sucursal" in consulta_traslado
    assert "nuevo.cantidad = viejo.cantidad" in consulta_traslado
    assert parametros_traslado == (52, 50)


# ── El renglón que el súper pide por teléfono ──────────────────────────────
# Hasta el 18/09 un artículo que la comanda no traía, o una cantidad que
# cambió, obligaban a RECARGAR el pedido entero: el nuevo anula al viejo y
# todo renglón cuya cantidad se movió pierde su armado.


def _pedido_para_agregar(filas=None):
    """cliente del pedido · artículo de la ficha · la sucursal existe · no hay duplicado."""
    return _conexion_falsa(filas if filas is not None else [(1, None), (7,), (1,), None, (99,)])


def test_agregar_renglon_el_ARTICULO_sale_de_la_FICHA_y_no_del_llamador():
    """La firma no acepta `articulo_id` y el INSERT lo toma de lo que devolvió
    la consulta de la ficha. Es la misma regla que `confirmar_pedido`: un
    artículo que viajara por el formulario podría no ser el de esa ficha."""
    conexion, cursor = _pedido_para_agregar()

    with patch("app.db.obtener_conexion", return_value=conexion):
        renglon_id = agregar_renglon_a_pedido(50, 901, "VL", 5)

    assert renglon_id == 99
    consulta_ficha = _sql_que_contiene(cursor, "FROM fichas_logistica")
    # La ficha se busca CON el cliente del pedido: es el límite pedido —solo
    # lo que ese cliente tiene ficha para recibir— y va en el WHERE, no en un
    # if de la pantalla.
    assert "WHERE id = %s AND cliente_id = %s" in consulta_ficha
    consulta_insert, parametros = _sql_y_parametros_que_contienen(cursor, "INSERT INTO pedidos_renglones")
    assert "agregado_a_mano_el" in consulta_insert
    assert "now()" in consulta_insert
    # 7 es el articulo_id que devolvió la ficha; 901 la ficha elegida.
    assert parametros == (50, "VL", 7, 901, 5)
    conexion.commit.assert_called_once()


def test_agregar_renglon_RECHAZA_la_ficha_de_OTRO_cliente():
    # La consulta de la ficha no devuelve nada: esa ficha no es de este cliente.
    conexion, cursor = _conexion_falsa([(1, None), None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="no es de este cliente"):
            agregar_renglon_a_pedido(50, 901, "VL", 5)

    conexion.commit.assert_not_called()


def test_agregar_renglon_RECHAZA_una_sucursal_que_el_pedido_no_tiene():
    """No es purismo: la pantalla de armar itera `pedidos_sucursales`, así que
    un renglón con una sucursal que no está ahí existiría sin que nadie pueda
    verlo — el camino que funciona y no se ve (corolario 68)."""
    conexion, cursor = _conexion_falsa([(1, None), (7,), None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="no tiene la sucursal"):
            agregar_renglon_a_pedido(50, 901, "ZZ", 5)

    conexion.commit.assert_not_called()


def test_agregar_renglon_RECHAZA_el_articulo_QUE_YA_ESTA_y_manda_a_corregirlo():
    """El caso más común del dueño: el artículo vino en la comanda EN CERO, o
    sea que el renglón YA EXISTE. Agregar un segundo contaría la demanda dos
    veces en la Rentabilidad, que suma por fecha y artículo."""
    conexion, cursor = _conexion_falsa([(1, None), (7,), (1,), (1,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="corregile la cantidad"):
            agregar_renglon_a_pedido(50, 901, "VL", 5)

    conexion.commit.assert_not_called()


def test_agregar_renglon_RECHAZA_un_pedido_ANULADO():
    conexion, cursor = _conexion_falsa([(1, datetime(2026, 9, 18, 10, 0))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="anulado"):
            agregar_renglon_a_pedido(50, 901, "VL", 5)


def test_agregar_renglon_pregunta_la_existencia_SIN_AGREGADO():
    """Con `count(*)` la fila vuelve con 0 y `fetchone() is None` no se cumple
    nunca: el pedido inexistente entraría igual (corolario 27)."""
    import inspect

    from app.db import agregar_renglon_a_pedido as funcion

    cuerpo = inspect.getsource(funcion)
    consulta_existencia = cuerpo[cuerpo.index("SELECT cliente_id"):cuerpo.index("fila = cursor.fetchone()")]
    assert "count(" not in consulta_existencia.lower()


def test_corregir_cantidad_guarda_CON_QUE_NACIO_el_renglon():
    conexion, cursor = _conexion_falsa([(5.0, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        cambio = corregir_cantidad_renglon(11, 8)

    assert cambio is True
    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE pedidos_renglones")
    # EL COALESCE ES LA REGLA: la segunda corrección no pisa el original, que
    # es lo único que contesta "la OC dice 5 y el sistema 8, por qué".
    assert "cantidad_original = COALESCE(cantidad_original, cantidad)" in consulta
    assert parametros == (8, 11)


def test_corregir_la_cantidad_TIRA_EL_TILDE_de_control_y_NO_toca_el_armado():
    """Las dos mitades, y son opuestas a propósito.

    El ARMADO no se toca: `cantidad_armada` es cuánto salió de verdad y es
    otra pregunta que lo pedido. Un renglón armado se corrige —el súper
    cambia el pedido después— y la pantalla muestra el diff, que es para eso.

    El TILDE sí se cae, por la misma razón que ya estaba escrita para el
    desarmado: lo que Administración controló fue este renglón contra este
    pedido, y con el número movido estaría afirmando algo sobre otra cosa.
    """
    conexion, cursor = _conexion_falsa([(5.0, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_cantidad_renglon(11, 8)

    consulta, _ = _sql_y_parametros_que_contienen(cursor, "UPDATE pedidos_renglones")
    # SE MIRA LO QUE EL UPDATE ESCRIBE —el SET, sin sus comentarios— y no el
    # texto entero: el comentario de al lado NOMBRA `cantidad_armada` para
    # explicar por qué no se toca, así que un `not in` sobre la consulta
    # completa matchea la prosa y falla contra el código bueno (corolario 38).
    set_clause = consulta[consulta.index("SET"):consulta.index("WHERE")]
    escrito = "\n".join(l for l in set_clause.splitlines() if not l.strip().startswith("--"))
    assert "controlado_el = NULL" in escrito
    # Y lo que NO tiene que estar: tocar el armado acá convertiría "me
    # pidieron 3 más" en "armá de nuevo".
    assert "armado_el" not in escrito
    assert "cantidad_armada" not in escrito
    assert "kilos_enviados" not in escrito


def test_corregir_cantidad_con_EL_MISMO_numero_no_escribe_nada():
    """Marcar como corregido un renglón que nadie cambió lo dejaría señalado
    para siempre por un click."""
    conexion, cursor = _conexion_falsa([(5.0, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        cambio = corregir_cantidad_renglon(11, 5.0)

    assert cambio is False
    assert not [c for c in cursor.execute.call_args_list if "UPDATE" in c.args[0]]
    conexion.commit.assert_not_called()


def test_corregir_cantidad_RECHAZA_un_renglon_anulado():
    conexion, cursor = _conexion_falsa([(5.0, datetime(2026, 9, 18, 10, 0))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="anulado"):
            corregir_cantidad_renglon(11, 8)


def test_recargar_CONSERVA_los_renglones_agregados_a_mano():
    """Decisión del dueño: si el súper agregó un artículo por teléfono, eso es
    real y no está en el mail. Que una recarga lo borre es mercadería ya
    armada que desaparece sin que nada avise."""
    conexion, cursor = _conexion_falsa([(52,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_pedido(1, date(2026, 8, 21), "texto", None, [], [], reemplaza_a_pedido_id=50)

    # SE ANCLA EN `viejo.cantidad_original`, que solo está en la copia de los
    # RENGLONES: `viejo.agregado_a_mano_el` lo dicen las dos copias —la de la
    # sucursal también— y la de la sucursal va primero, así que el assert
    # contestaba por la vecina (corolario 4). Lo agarró este mismo test al
    # escribirlo mal.
    copia, parametros = _sql_y_parametros_que_contienen(cursor, "viejo.cantidad_original")
    assert "INSERT INTO pedidos_renglones" in copia
    assert "viejo.agregado_a_mano_el IS NOT NULL" in copia
    assert "viejo.anulado_el IS NULL" in copia
    # GANA EL DEL MAIL si el pedido nuevo ya trae ese (artículo, sucursal).
    assert "NOT EXISTS" in copia
    assert "nuevo.articulo_id IS NOT DISTINCT FROM viejo.articulo_id" in copia
    assert "nuevo.sucursal IS NOT DISTINCT FROM viejo.sucursal" in copia
    assert parametros == (52, 50, 52)


def test_la_copia_del_renglon_a_mano_va_ANTES_del_traslado_del_armado():
    """El orden no es estilo: el renglón copiado tiene que EXISTIR para que el
    UPDATE del traslado le devuelva su tilde. Al revés, un renglón agregado a
    mano y ya armado se conserva SIN armar, que es exactamente la mercadería
    que desaparece que esto vino a evitar."""
    conexion, cursor = _conexion_falsa([(52,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_pedido(1, date(2026, 8, 21), "texto", None, [], [], reemplaza_a_pedido_id=50)

    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    # `viejo.cantidad_original` está SOLO en la copia de los renglones. Con
    # `viejo.agregado_a_mano_el` —que también dice la copia de la sucursal, y
    # esa va primero— este test pasaba con la copia de renglones movida
    # DESPUÉS del traslado, que es exactamente el bug que dice cuidar.
    posicion_copia = next(i for i, c in enumerate(consultas) if "viejo.cantidad_original" in c)
    posicion_traslado = next(i for i, c in enumerate(consultas) if "SET armado_el = viejo.armado_el" in c)
    assert posicion_copia < posicion_traslado


def test_la_SUCURSAL_del_renglon_a_mano_se_copia_si_el_mail_nuevo_no_la_trae():
    conexion, cursor = _conexion_falsa([(52,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_pedido(1, date(2026, 8, 21), "texto", None, [], [], reemplaza_a_pedido_id=50)

    copia = _sql_que_contiene(cursor, "INSERT INTO pedidos_sucursales (pedido_id, sucursal, orden_compra")
    assert "SELECT DISTINCT" in copia
    assert "viejo.agregado_a_mano_el IS NOT NULL" in copia
    assert "NOT EXISTS" in copia


def test_el_listado_del_pedido_TRAE_LAS_DOS_MARCAS_de_la_base():
    """El valor lo entrega el mock, así que lo único que puede ver QUÉ COLUMNAS
    pide la consulta es un assert sobre el TEXTO del SQL (corolario 65). Sin
    ellas la pantalla no distingue un renglón de la comanda de uno que puso
    una persona, y se ve exactamente igual que antes."""
    import inspect

    from app.db import listar_renglones_pedido as funcion

    cuerpo = inspect.getsource(funcion)
    consulta = cuerpo[cuerpo.index("SELECT r.id"):cuerpo.index("FROM pedidos_renglones")]
    assert "r.agregado_a_mano_el" in consulta
    assert "r.cantidad_original" in consulta


def test_contar_renglones_a_mano_solo_cuenta_los_VIGENTES():
    """Un renglón anulado no se copia al pedido nuevo: contarlo haría que el
    aviso prometa conservar algo que no se conserva."""
    conexion, cursor = _conexion_falsa([(2,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert contar_renglones_agregados_a_mano(50) == 2

    consulta, parametros = cursor.execute.call_args.args
    assert "agregado_a_mano_el IS NOT NULL" in consulta
    assert "anulado_el IS NULL" in consulta
    assert parametros == (50,)


def test_contar_pedidos_incompletos_cuenta_los_armados_por_menos_y_trae_el_mas_viejo():
    conexion, cursor = _conexion_falsa([(1, date(2026, 8, 5))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_pedidos_incompletos(date(2026, 8, 1))

    assert resultado == {"casos": 1, "mas_viejo": date(2026, 8, 5)}
    consulta, parametros = cursor.execute.call_args.args
    assert "r.armado_el IS NOT NULL AND r.cantidad_armada IS NOT NULL" in consulta
    assert "p.anulado_el IS NULL" in consulta
    assert parametros == (date(2026, 8, 1),)


def test_contar_pedidos_incompletos_compara_con_menor_no_con_distinto():
    # El bug que arregla: con "<>" un renglón armado de MAS (18 de 15) caia
    # bajo un titulo que dice "se armo menos de lo pedido".
    conexion, cursor = _conexion_falsa([(0, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_pedidos_incompletos(date(2026, 8, 1))

    consulta = cursor.execute.call_args.args[0]
    assert "r.cantidad_armada < r.cantidad" in consulta
    assert "r.cantidad_armada <> r.cantidad" not in consulta


def test_contar_pedidos_incompletos_toma_los_sin_armar_solo_con_el_armado_cerrado():
    # Un pedido a medio armar todavia no es noticia: recien cuando se apreto
    # Terminar, lo que quedo sin armar salio faltando.
    conexion, cursor = _conexion_falsa([(0, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_pedidos_incompletos(date(2026, 8, 1))

    consulta = cursor.execute.call_args.args[0]
    assert "armado_cerrado_el IS NOT NULL AND renglones_sin_armar > 0" in consulta
    # Solo renglones armables, mismo criterio que los conteos de Armar.
    assert "r.sucursal IS NOT NULL" in consulta
    assert "r.articulo_id IS NOT NULL" in consulta


def test_contar_pedidos_incompletos_solo_el_pedido_vigente_de_cada_cliente_y_dia():
    conexion, cursor = _conexion_falsa([(0, None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_pedidos_incompletos(date(2026, 8, 1))

    consulta = cursor.execute.call_args.args[0]
    assert "DISTINCT ON (p.cliente_id, p.fecha_operacion)" in consulta
    assert "ORDER BY p.cliente_id, p.fecha_operacion, p.creado_en DESC" in consulta


# --- Casilla de pedidos (etapa 3) ---


def test_crear_casilla_pedidos_nace_desactivada():
    conexion, cursor = _conexion_falsa([(1,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        casilla_id = crear_casilla_pedidos("casilla@empresa.com", "imap.gmail.com", 1, "Pedido Dia", None)

    assert casilla_id == 1
    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO casillas_pedidos" in consulta
    # Ni activa ni fecha_activacion en el insert: nace apagada, se activa aparte.
    assert "activa" not in consulta
    # Remitentes None = cualquier remitente (el filtro obligatorio es el asunto).
    assert parametros == ("casilla@empresa.com", "imap.gmail.com", 1, "Pedido Dia", None)
    conexion.commit.assert_called_once()


def test_activar_casilla_pedidos_fija_la_fecha_de_activacion():
    conexion, cursor = _conexion_falsa()
    momento = datetime(2026, 8, 22, 11, 0)

    with patch("app.db.obtener_conexion", return_value=conexion):
        activar_casilla_pedidos(3, momento)

    consulta, parametros = cursor.execute.call_args.args
    assert "SET activa = true, fecha_activacion = %s" in consulta
    assert parametros == (momento, 3)


def test_registrar_revision_casilla_no_pisa_el_exito_con_el_error():
    # Éxito y error van a columnas distintas: si el error es más nuevo que
    # la última revisión OK, la pantalla lo muestra — nada se pisa.
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        registrar_revision_casilla(3)
        registrar_revision_casilla(3, error="login fallido")

    consulta_ok = cursor.execute.call_args_list[0].args[0]
    consulta_error, parametros_error = cursor.execute.call_args_list[1].args
    assert "SET ultima_revision_el = now()" in consulta_ok
    assert "ultimo_error" not in consulta_ok
    assert "SET ultimo_error = %s, ultimo_error_el = now()" in consulta_error
    assert "ultima_revision_el" not in consulta_error
    assert parametros_error == ("login fallido", 3)


def test_registrar_mail_pedido_es_idempotente_por_message_id():
    conexion, cursor = _conexion_falsa([(9,), None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        primero = registrar_mail_pedido(
            3, 1, "<pedido-1@dia.com.ar>", "pedidos@dia.com.ar", "Pedido",
            datetime(2026, 8, 22, 12, 5), "<html>...</html>", "texto",
        )
        repetido = registrar_mail_pedido(
            3, 1, "<pedido-1@dia.com.ar>", "pedidos@dia.com.ar", "Pedido",
            datetime(2026, 8, 22, 12, 5), "<html>...</html>", "texto",
        )

    assert primero == 9
    # El duplicado devuelve None y no toca nada: ON CONFLICT DO NOTHING.
    assert repetido is None
    consulta = cursor.execute.call_args.args[0]
    assert "ON CONFLICT (message_id) DO NOTHING" in consulta


def test_marcar_mail_pedido_ignorado_solo_toca_pendientes():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_mail_pedido_ignorado(9, "no era un pedido")

    consulta, parametros = cursor.execute.call_args.args
    assert "SET estado = 'ignorado'" in consulta
    # Un mail ya confirmado no se puede pisar a ignorado por un doble toque
    # (un error de lectura sí se puede ignorar: sigue abierto).
    assert "estado IN ('pendiente', 'error')" in consulta
    assert parametros == ("no era un pedido", 9)


def test_listar_casillas_pedidos_trae_el_nombre_del_cliente():
    conexion, cursor = _conexion_falsa()
    cursor.description = [
        ("id",), ("direccion",), ("servidor_imap",), ("cliente_id",), ("asunto_filtro",), ("remitentes_permitidos",),
        ("activa",), ("fecha_activacion",), ("auto_confirmar",),
        ("ultima_revision_el",), ("ultimo_error",), ("ultimo_error_el",), ("cliente_nombre",),
    ]
    cursor.fetchall.return_value = [
        (3, "casilla@empresa.com", "imap.gmail.com", 1, "Pedido Dia", "pedidos@dia.com.ar",
         True, datetime(2026, 8, 22, 11, 0), False, None, None, None, "Dia"),
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        casillas = listar_casillas_pedidos()

    assert casillas == [
        {
            "id": 3, "direccion": "casilla@empresa.com", "servidor_imap": "imap.gmail.com",
            "cliente_id": 1, "asunto_filtro": "Pedido Dia", "remitentes_permitidos": "pedidos@dia.com.ar",
            "activa": True,
            "fecha_activacion": datetime(2026, 8, 22, 11, 0), "auto_confirmar": False,
            "ultima_revision_el": None, "ultimo_error": None, "ultimo_error_el": None,
            "cliente_nombre": "Dia",
        }
    ]
    assert "JOIN clientes c ON c.id = ca.cliente_id" in cursor.execute.call_args.args[0]


def test_crear_pedido_de_mail_guarda_message_id_y_recibido():
    conexion, cursor = _conexion_falsa([(60,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_pedido(
            1, date(2026, 8, 22), "mail", "el cuerpo", [], [],
            mail_message_id="<pedido-1@dia.com.ar>", recibido_el=datetime(2026, 8, 22, 12, 5),
        )

    consulta, parametros = cursor.execute.call_args_list[0].args
    assert "mail_message_id" in consulta and "recibido_el" in consulta
    assert parametros == (
        1, date(2026, 8, 22), "mail", "el cuerpo", None, "<pedido-1@dia.com.ar>", datetime(2026, 8, 22, 12, 5),
    )


def test_marcar_mail_pedido_error_graba_el_motivo_sin_pisar_cerrados():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_mail_pedido_error(9, "La lectura falló: se cortó la respuesta")

    consulta, parametros = cursor.execute.call_args.args
    assert "SET estado = 'error'" in consulta
    # Reintentable: un error se puede volver a marcar error, pero un
    # confirmado o ignorado no se pisa.
    assert "estado IN ('pendiente', 'error')" in consulta
    assert parametros == ("La lectura falló: se cortó la respuesta", 9)


def test_contar_mails_pedido_sin_procesar_suma_pendientes_y_errores():
    conexion, cursor = _conexion_falsa([(3, date(2026, 8, 20))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_mails_pedido_sin_procesar()

    assert resultado == {"casos": 3, "mas_viejo": date(2026, 8, 20)}
    consulta = cursor.execute.call_args.args[0]
    assert "estado IN ('pendiente', 'error')" in consulta


def test_marcar_lectura_mail_pedido_graba_el_metodo_de_la_ultima_lectura():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_lectura_mail_pedido(9, leido_con_ia=True)

    consulta, parametros = cursor.execute.call_args.args
    assert "SET leido_con_ia = %s" in consulta
    assert parametros == (True, 9)


def test_contar_mails_pedido_leidos_con_ia_mira_la_ventana_reciente():
    conexion, cursor = _conexion_falsa([(1, date(2026, 8, 22))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_mails_pedido_leidos_con_ia(date(2026, 8, 15))

    assert resultado == {"casos": 1, "mas_viejo": date(2026, 8, 22)}
    consulta, parametros = cursor.execute.call_args.args
    assert "leido_con_ia AND recibido_el >= ((%s::date)::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')" in consulta
    assert parametros == (date(2026, 8, 15),)


def test_listar_pedidos_vigentes_con_armado_una_fila_por_fecha_desde_el_corte():
    conexion, cursor = _conexion_falsa()
    cursor.description = [
        ("id",), ("fecha_operacion",), ("origen",), ("creado_en",),
        ("renglones_totales",), ("renglones_armados",), ("sin_identificar",),
    ]
    cursor.fetchall.return_value = [(50, date(2026, 8, 22), "mail", datetime(2026, 8, 21, 12, 30), 32, 18, 1)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        pedidos = listar_pedidos_vigentes_con_armado(1, date(2026, 8, 15))

    assert pedidos[0]["renglones_armados"] == 18
    consulta, parametros = cursor.execute.call_args.args
    # Una fila por fecha (el vigente: el más nuevo sin anular), pasados
    # desde el corte y TODOS los futuros (sin tope superior).
    assert "DISTINCT ON (p.fecha_operacion)" in consulta
    assert "p.anulado_el IS NULL" in consulta
    assert "p.fecha_operacion >= %s" in consulta
    assert "<=" not in consulta
    assert parametros == (1, date(2026, 8, 15))


# --- Condiciones de pedido y días sin pedido (etapa 3, tramo 2) ---

def test_guardar_condiciones_pedido_hace_upsert_por_cliente():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_condiciones_pedido(1, "1,2,3,4,5,6")

    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO clientes_condiciones_pedido" in consulta
    assert "ON CONFLICT (cliente_id)" in consulta
    assert "actualizado_en = now()" in consulta
    assert parametros == (1, "1,2,3,4,5,6")
    conexion.commit.assert_called_once()


def test_guardar_condiciones_pedido_acepta_esporadico_con_none():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_condiciones_pedido(1, None)

    assert cursor.execute.call_args.args[1] == (1, None)


def test_obtener_condiciones_pedido_devuelve_none_si_nunca_se_configuro():
    conexion, cursor = _conexion_falsa([None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert obtener_condiciones_pedido(1) is None


def test_listar_condiciones_pedido_solo_clientes_activos_con_dias():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("cliente_id",), ("dias_esperados",), ("cliente_nombre",)]
    cursor.fetchall.return_value = [(1, "1,2,3,4,5,6", "Día")]

    with patch("app.db.obtener_conexion", return_value=conexion):
        condiciones = listar_condiciones_pedido()

    assert condiciones == [{"cliente_id": 1, "dias_esperados": "1,2,3,4,5,6", "cliente_nombre": "Día"}]
    consulta = cursor.execute.call_args.args[0]
    # Los esporádicos (dias NULL) y los clientes dados de baja no alertan.
    assert "dias_esperados IS NOT NULL" in consulta
    assert "c.activo" in consulta


def test_listar_fechas_con_pedido_vigente_solo_los_vivos():
    conexion, cursor = _conexion_falsa(filas_fetchall=[(date(2026, 8, 21),), (date(2026, 8, 22),)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        fechas = listar_fechas_con_pedido_vigente(1, date(2026, 8, 15))

    assert fechas == [date(2026, 8, 21), date(2026, 8, 22)]
    consulta, parametros = cursor.execute.call_args.args
    assert "anulado_el IS NULL" in consulta
    assert parametros == (1, date(2026, 8, 15))


def test_marcar_dia_sin_pedido_es_idempotente_por_cliente_y_fecha():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_dia_sin_pedido(1, date(2026, 8, 20), "Feriado")

    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO dias_sin_pedido" in consulta
    assert "ON CONFLICT (cliente_id, fecha) DO NOTHING" in consulta
    assert parametros == (1, date(2026, 8, 20), "Feriado")
    conexion.commit.assert_called_once()


def test_borrar_dia_sin_pedido_borra_la_marca_administrativa():
    # La excepción acordada a la regla de bajas lógicas: la marca es
    # administrativa (no un registro operativo) y deshacer la borra.
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        borrar_dia_sin_pedido(1, date(2026, 8, 20))

    consulta, parametros = cursor.execute.call_args.args
    assert "DELETE FROM dias_sin_pedido" in consulta
    assert parametros == (1, date(2026, 8, 20))
    conexion.commit.assert_called_once()


def test_marcar_mail_pedido_confirmado_graba_el_motivo():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        marcar_mail_pedido_confirmado(9, 50, motivo="Confirmado automáticamente")

    consulta, parametros = cursor.execute.call_args.args
    assert "SET estado = 'confirmado'" in consulta
    assert parametros == (50, "Confirmado automáticamente", 9)


def test_obtener_mail_de_pedido_devuelve_none_si_no_vino_de_mail():
    conexion, cursor = _conexion_falsa([None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert obtener_mail_de_pedido(50) is None


def test_listar_renglones_pedidos_vigentes_suma_por_fecha_y_articulo():
    conexion, cursor = _conexion_falsa()
    cursor.description = [
        ("fecha_operacion",), ("articulo_id",), ("articulo_nombre",), ("articulo_grupo",), ("bultos",),
    ]
    cursor.fetchall.return_value = [
        (date(2026, 8, 21), 1, "Banana", "fruta", 235.0),
        (date(2026, 8, 21), None, None, None, 5.0),
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        renglones = listar_renglones_pedidos_vigentes(1, date(2026, 8, 15), date(2026, 8, 22))

    assert renglones[0]["bultos"] == 235.0
    assert renglones[1]["articulo_id"] is None  # sin identificar: viene igual, se reporta aparte
    consulta, parametros = cursor.execute.call_args.args
    # Solo pedidos VIGENTES: uno por fecha (el más nuevo sin anular) — los
    # reemplazados no cuentan la demanda dos veces.
    assert "DISTINCT ON (fecha_operacion)" in consulta
    # LOS DOS anulado_el, cada uno CALIFICADO CON SU TABLA. Sin calificar,
    # este assert era `"anulado_el IS NULL" in consulta` y pasaba con el de
    # `pedidos`: parecía cubrir el renglón anulado y nunca lo miró. Es la
    # familia del test que comparaba tres campos de cinco.
    assert "WHERE cliente_id = %s AND anulado_el IS NULL" in consulta  # pedidos
    assert "JOIN pedidos_renglones r ON r.pedido_id = v.id AND r.anulado_el IS NULL" in consulta
    assert "SUM(r.cantidad)" in consulta
    assert "LEFT JOIN articulos" in consulta
    assert parametros == (1, date(2026, 8, 15), date(2026, 8, 22))


def test_agregar_foto_guia_del_dia_cuelga_si_la_guia_existe():
    conexion, cursor = _conexion_falsa([(105,)])  # SELECT id de la guía del día

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = agregar_foto_guia_del_dia(date(2026, 8, 22), 200, "2026-08-22/n07p41-abc.jpg")

    assert resultado is True
    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO fotos_guia" in consulta
    assert "ON CONFLICT DO NOTHING" in consulta
    assert parametros == (105, "2026-08-22/n07p41-abc.jpg")
    conexion.commit.assert_called_once()


def test_agregar_foto_guia_del_dia_sin_guia_devuelve_false():
    conexion, cursor = _conexion_falsa([None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = agregar_foto_guia_del_dia(date(2026, 8, 22), 200, "ruta.jpg")

    assert resultado is False
    assert cursor.execute.call_count == 1  # solo el SELECT, nada que insertar


def test_guardar_horario_revision_casilla_actualiza_los_tres_campos():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_horario_revision_casilla(3, time(12, 0), time(13, 0), 30)

    consulta, parametros = cursor.execute.call_args.args
    assert "SET revision_desde = %s, revision_hasta = %s, revision_cada_minutos = %s" in consulta
    assert parametros == (time(12, 0), time(13, 0), 30, 3)
    conexion.commit.assert_called_once()


def test_listar_casillas_pedidos_trae_el_horario_de_revision():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_casillas_pedidos()

    consulta = cursor.execute.call_args.args[0]
    assert "ca.revision_desde" in consulta
    assert "ca.revision_hasta" in consulta
    assert "ca.revision_cada_minutos" in consulta


def test_anular_renglon_pedido_limpia_el_tilde_y_sus_numeros():
    # Anulado y armado son excluyentes: un renglón anulado no manda nada.
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_renglon_pedido(11)

    consulta = cursor.execute.call_args_list[0].args[0]
    # Columna por columna y no la línea entera: el assert de una línea se cae
    # con un salto de línea y no dice cuál columna falta.
    assert "SET anulado_el = now()" in consulta
    for columna in ("armado_el = NULL", "cantidad_armada = NULL", "kilos_enviados = NULL"):
        assert columna in consulta, columna
    # Y el control de Administración, que sin el armado no puede quedar: lo
    # obliga el CHECK pedidos_renglones_controlado_solo_armado, así que sin
    # esta columna el UPDATE lo RECHAZA la base.
    assert "controlado_el = NULL" in consulta
    # Un renglón anulado no manda nada: su corrección de lotes tampoco.
    assert "DELETE FROM pedidos_renglones_lotes_elegidos" in cursor.execute.call_args_list[1].args[0]
    conexion.commit.assert_called_once()


def test_cajones_faltantes_cuenta_los_que_llegaron_de_MENOS_y_no_los_de_mas():
    """MENOS y no "distinto": recibir de más es un dato, pero no es que falte nada.

    Mezclarlos dejaría al aviso sin una sola cosa que decir. Se mira el
    TEXTO del SQL y no un valor devuelto: lo que cambia acá es el WHERE, y
    con un cursor falso la fila la entrega el mock sin leer una letra de la
    consulta (corolario 40).
    """
    from app.db import contar_cajones_faltantes

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = (2, date(2026, 9, 5))

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_cajones_faltantes(date(2026, 9, 4), date(2026, 9, 11), 1)

    consulta = cursor.execute.call_args_list[0].args[0]
    assert "(c.cantidad_cajones - c.cantidad_cajones_real) >= %s" in consulta
    assert "ABS(c.cantidad_cajones - c.cantidad_cajones_real)" not in consulta
    # Sin número real de cajones no hay nada que comparar.
    assert "c.cantidad_cajones_real IS NOT NULL" in consulta
    # TODAS las unidades: un cajón faltante de un artículo por unidad falta
    # igual. El filtro por 'kilo' era del intento anterior, que medía kilos.
    assert "unidad_compra = 'kilo'" not in consulta
    assert cursor.execute.call_args_list[0].args[1] == (date(2026, 9, 4), date(2026, 9, 11), 1)
    assert resultado == {"casos": 2, "mas_viejo": date(2026, 9, 5)}


def test_la_cuenta_y_la_lista_de_cajones_faltantes_comparten_EL_MISMO_WHERE():
    """Con un WHERE cada una, el día que se separen el banner dice un número y la pantalla lista otro.

    No se comparan los textos enteros —uno trae COUNT y el otro columnas—
    sino que el recorte de las dos salga de la MISMA constante, comprobando
    que cada condición esté en las dos.
    """
    from app.db import contar_cajones_faltantes, listar_cajones_faltantes

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = (0, None)
    cursor.fetchall.return_value = []
    cursor.description = [("id",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_cajones_faltantes(date(2026, 9, 4), date(2026, 9, 11), 1)
        listar_cajones_faltantes(date(2026, 9, 4), date(2026, 9, 11), 1)

    cuenta = cursor.execute.call_args_list[0].args[0]
    lista = cursor.execute.call_args_list[1].args[0]
    for condicion in (
        "c.estado = 'recepcionado'",
        "c.cantidad_cajones_real IS NOT NULL",
        "c.fecha_operacion >= %s AND c.fecha_operacion <= %s",
        "(c.cantidad_cajones - c.cantidad_cajones_real) >= %s",
    ):
        assert condicion in cuenta, ("falta en la cuenta", condicion)
        assert condicion in lista, ("falta en la lista", condicion)
    # Y los MISMOS parámetros, en el mismo orden.
    assert cursor.execute.call_args_list[0].args[1] == cursor.execute.call_args_list[1].args[1]


def test_la_lista_de_cajones_faltantes_trae_lo_que_REPRESENTA_el_faltante():
    """Seis cajones de Pera son ciento ocho kilos: el que decide si reclamar mira la plata.

    Y usa el contenido REAL si existe, no el estimado: el estimado es
    justamente el número del que se desconfía.
    """
    from app.db import listar_cajones_faltantes

    conexion, cursor = _conexion_falsa()
    cursor.fetchall.return_value = []
    cursor.description = [("id",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_cajones_faltantes(date(2026, 9, 4), date(2026, 9, 11), 1)

    consulta = cursor.execute.call_args_list[0].args[0]
    assert "COALESCE(c.contenido_por_cajon_real, c.contenido_por_cajon)" in consulta
    assert "AS contenido_faltante" in consulta
    assert "ORDER BY c.fecha_operacion DESC" in consulta



def test_las_DOS_alertas_de_reclamo_van_POR_FECHA_DESCENDENTE_y_con_el_MISMO_orden():
    """Un reclamo tiene ventana: la compra de hoy se reclama, la de hace cuatro días no.

    Ordenadas por MAGNITUD —como estaban— el faltante más grande de la semana
    quedaba arriba aunque ya no se pudiera hacer nada con él, y el de hoy caía
    al fondo. El tamaño sigue mandando DENTRO del mismo día.

    Y VA UN SOLO TEST PARA LAS DOS, no uno por consulta: se muestran una al
    lado de la otra y contestan la misma pregunta —qué compra reclamar—, así
    que dos órdenes distintos no son dos estilos, es que una está mal. Un test
    por consulta deja que la próxima las separe sin que nada caiga; éste exige
    que el criterio SEA EL MISMO y no solo que cada una tenga el suyo.

    La de bultos tenía su test de orden y la de kilos NO tenía ninguno, que es
    justamente cómo se separan dos cosas que tienen que ir juntas.
    """
    import re
    from app.db import listar_cajones_faltantes, listar_diferencia_de_kilos

    ordenes = {}
    for funcion in (listar_cajones_faltantes, listar_diferencia_de_kilos):
        conexion, cursor = _conexion_falsa()
        cursor.fetchall.return_value = []
        cursor.description = [("id",)]
        with patch("app.db.obtener_conexion", return_value=conexion):
            funcion(date(2026, 9, 4), date(2026, 9, 11), 1)
        consulta = cursor.execute.call_args_list[0].args[0]
        encontrado = re.search(r"ORDER BY(.*?)$", consulta, re.S)
        assert encontrado, funcion.__name__
        ordenes[funcion.__name__] = " ".join(encontrado.group(1).split())

    for nombre, orden in ordenes.items():
        # La fecha PRIMERO: que aparezca no alcanza — antes aparecía, de
        # desempate, y ése era exactamente el bug.
        assert orden.startswith("c.fecha_operacion DESC"), f"{nombre}: {orden}"
        # Y la magnitud sigue estando, de desempate dentro del día.
        assert "DESC" in orden.split("c.fecha_operacion DESC", 1)[1], nombre

    # LAS DOS EMPIEZAN IGUAL. Es la mitad que impide que se vuelvan a separar.
    primeras = {orden.split(",")[0] for orden in ordenes.values()}
    assert len(primeras) == 1, f"las dos hermanas ordenan distinto: {ordenes}"


def test_kilos_faltantes_cuenta_los_que_pesaron_de_MENOS_y_no_los_de_mas():
    """Un cajón que vino más pesado no se le reclama a nadie.

    Misma dirección que su hermana la de bultos: faltantes, no "distintos".
    Con `abs` el aviso llenaría la lista de casos donde no se perdió nada.

    Por el TEXTO del SQL: lo que cambia es el WHERE, y con un cursor falso la
    fila la entrega el mock sin leer una letra de la consulta (corolario 40).
    """
    from app.db import contar_diferencia_de_kilos

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = (2, date(2026, 9, 10), date(2026, 9, 9))

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_diferencia_de_kilos(date(2026, 9, 5), date(2026, 9, 12), 1)

    consulta = cursor.execute.call_args_list[0].args[0]
    # EL UMBRAL VA CONTRA EL POR CAJÓN, NO CONTRA EL TOTAL. Con el producto
    # entraban Jugo (−0,6k por cajón) y Berenjena (−0,3k) por tener muchos
    # cajones: el total dimensiona, el por cajón detecta. El `not in` es la
    # mitad que importa — es la única forma de volver, y sin él este test lo
    # pasa igual una consulta que multiplique.
    assert "(c.contenido_por_cajon - c.contenido_por_cajon_real) >= %s" in consulta
    assert "* c.cantidad_cajones_real) >= %s" not in consulta
    # SIN MAYÚSCULAS: el canario lo escribió en minúscula y el assert no lo
    # vio — un `abs` escrito de la otra forma rompe la regla exactamente
    # igual, y SQL no distingue. Un test que fija una grafía prueba la
    # grafía, no la regla.
    assert "abs(" not in consulta.lower()
    # Sin peso real no hay nada que comparar: esa compra no se pesó.
    assert "c.contenido_por_cajon_real IS NOT NULL" in consulta
    assert cursor.execute.call_args_list[0].args[1] == (date(2026, 9, 5), date(2026, 9, 12), 1)
    assert resultado == {"casos": 2, "mas_viejo": date(2026, 9, 10),
                         "desde_la_foto": date(2026, 9, 9)}


def test_los_kilos_faltantes_se_miden_SOBRE_LOS_CAJONES_RECIBIDOS():
    """Los kilos que se perdieron por PESO solo pudieron perderse en los cajones que llegaron.

    Multiplicar por los comprados metería adentro de esta alerta los kilos de
    los cajones que no llegaron — que son la alerta de bultos— y la misma
    compra aportaría el mismo kilo a las dos. Las dos son disjuntas por causa
    y este es el único lugar del código donde eso está escrito.

    Es sobre el total que se MUESTRA y por el que se ordena, no sobre el
    filtro: quién entra lo decide el por cajón (el test de arriba). El total
    sigue saliendo de los cajones recibidos por esta misma razón.
    """
    from app.db import contar_diferencia_de_kilos, listar_diferencia_de_kilos

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = (0, None, None)
    cursor.fetchall.return_value = []
    cursor.description = [("id",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_diferencia_de_kilos(date(2026, 9, 5), date(2026, 9, 12), 1)
        listar_diferencia_de_kilos(date(2026, 9, 5), date(2026, 9, 12), 1)

    # SOLO LA LISTA, porque el total ya no filtra: la cuenta es un COUNT(*) y
    # no lo calcula. Pedirlo en las dos era correcto cuando el producto estaba
    # en el WHERE — el mismo arreglo que lo sacó de ahí volvió falso a este
    # assert, y el test es parte del arreglo, no un espectador (corolario 22).
    lista = cursor.execute.call_args_list[1].args[0]
    assert "* c.cantidad_cajones_real)" in lista
    assert "* c.cantidad_cajones)" not in lista


def test_los_kilos_faltantes_SOLO_MIRAN_desde_que_hay_foto_de_balanza():
    """El recorte que hace que esta alerta signifique algo.

    Antes de la foto, el 82% de las recepciones se aceptaba con el estimado
    precargado sin tocarlo: la diferencia contra eso no mide kilos que
    faltaron, mide la referencia repitiéndose. Sin este piso la alerta
    arrastraría las 41 compras de la medición vieja, que es exactamente lo
    que la hizo descartar la primera vez.

    Y el piso SALE DE LA BASE, no de una fecha escrita en el código: el
    deploy es el mismo en las dos bases, el uso no.
    """
    from app.db import contar_diferencia_de_kilos, listar_diferencia_de_kilos

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = (0, None, None)
    cursor.fetchall.return_value = []
    cursor.description = [("id",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_diferencia_de_kilos(date(2026, 9, 5), date(2026, 9, 12), 1)
        listar_diferencia_de_kilos(date(2026, 9, 5), date(2026, 9, 12), 1)

    for consulta in (cursor.execute.call_args_list[0].args[0],
                     cursor.execute.call_args_list[1].args[0]):
        assert "FROM fotos_recepcion f" in consulta
        assert "c.fecha_operacion >= (SELECT MIN(" in consulta
        # En hora ARGENTINA: creado_en es timestamptz, y una foto de las 21
        # de un martes es del miércoles en UTC. Es la misma expresión que usa
        # el FIFO para fechar un lote, escrita una sola vez.
        assert "AT TIME ZONE 'America/Argentina/Buenos_Aires'" in consulta


def test_la_cuenta_de_kilos_faltantes_DEVUELVE_el_piso_que_uso():
    """Un cero de una base que nunca pesó y uno de una base sin diferencias dicen cosas OPUESTAS.

    Y se ven igual de prolijos. El testigo al lado del número es lo único que
    los separa (corolario 24), y tiene que salir de la MISMA expresión que el
    recorte: una pantalla que dice una fecha distinta de la que la consulta
    usó es peor que no decir ninguna.
    """
    from app.db import contar_diferencia_de_kilos

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = (0, None, None)

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_diferencia_de_kilos(date(2026, 9, 5), date(2026, 9, 12), 1)

    assert resultado == {"casos": 0, "mas_viejo": None, "desde_la_foto": None}
    # La expresión del testigo y la del recorte salen de LA MISMA constante:
    # si se escribieran dos veces, el día que se separen la pantalla diría
    # una fecha y la consulta recortaría por otra, y nadie se entera.
    #
    # Se compara el CAST, que es la pieza compartida — no la línea entera:
    # en el WHERE va partida y con sangría, así que un `in` del texto completo
    # falla por espacios y no por lo que se quiere probar.
    from app.db import (_SQL_DESDE_QUE_HAY_FOTO, _SQL_DIFERENCIA_DE_KILOS,
                        _SQL_FECHA_DEL_LOTE_DE_COMPRA)
    cast = _SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col="f.creado_en")
    assert cast in _SQL_DESDE_QUE_HAY_FOTO
    assert cast in _SQL_DIFERENCIA_DE_KILOS


def test_la_cuenta_y_la_lista_de_kilos_faltantes_comparten_EL_MISMO_WHERE():
    """Con un WHERE cada una, el banner dice un número y la pantalla lista otro."""
    from app.db import contar_diferencia_de_kilos, listar_diferencia_de_kilos

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = (0, None, None)
    cursor.fetchall.return_value = []
    cursor.description = [("id",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_diferencia_de_kilos(date(2026, 9, 5), date(2026, 9, 12), 1)
        listar_diferencia_de_kilos(date(2026, 9, 5), date(2026, 9, 12), 1)

    cuenta = cursor.execute.call_args_list[0].args[0]
    lista = cursor.execute.call_args_list[1].args[0]
    for condicion in (
        "c.estado = 'recepcionado'",
        "c.contenido_por_cajon_real IS NOT NULL",
        "c.cantidad_cajones_real IS NOT NULL",
        "c.fecha_operacion >= %s AND c.fecha_operacion <= %s",
        "FROM fotos_recepcion f",
        "(c.contenido_por_cajon - c.contenido_por_cajon_real) >= %s",
    ):
        assert condicion in cuenta, ("falta en la cuenta", condicion)
        assert condicion in lista, ("falta en la lista", condicion)
    assert cursor.execute.call_args_list[0].args[1] == cursor.execute.call_args_list[1].args[1]


def test_guardar_control_pregunta_la_EXISTENCIA_sin_agregado():
    """`count(*)` devuelve (0,) para un pedido que no existe: la guarda no serviría.

    Es el corolario 27: un agregado sin group by SIEMPRE produce una fila,
    así que `fetchone() is None` no se cumple nunca. La existencia se
    pregunta con un SELECT sin agregado, y el conteo va después.
    """
    from app.db import guardar_control_de_pedido

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.side_effect = [(71,), (2,)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        tildados = guardar_control_de_pedido(71, [11, 14])

    existencia = cursor.execute.call_args_list[0].args[0]
    assert "count(" not in existencia.lower(), existencia
    assert "SELECT id FROM pedidos WHERE id = %s" in existencia
    assert tildados == 2


def test_guardar_control_de_pedido_INEXISTENTE_no_escribe_y_lo_dice():
    from app.db import PedidoInexistenteParaControl, guardar_control_de_pedido

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = None

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            guardar_control_de_pedido(999, [11])
        except PedidoInexistenteParaControl:
            pass
        else:
            raise AssertionError("tenía que levantar PedidoInexistenteParaControl")

    # Una sola consulta: la de existencia. No se escribió nada.
    assert len(cursor.execute.call_args_list) == 1
    conexion.commit.assert_not_called()


def test_guardar_control_TILDA_los_que_vienen_y_DESTILDA_el_resto():
    """Destildar es "no estar en la lista": un checkbox apagado no manda nada.

    Sin el ELSE NULL, sacar un tilde sería imposible desde la pantalla — se
    podría tildar y nunca destildar, y nadie lo notaría hasta querer sacar
    uno.
    """
    from app.db import guardar_control_de_pedido

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.side_effect = [(71,), (2,)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_control_de_pedido(71, [11, 14])

    llamada = cursor.execute.call_args_list[1]
    consulta, parametros = llamada.args[0], llamada.args[1]
    assert "controlado_el = CASE WHEN id = ANY(%s) THEN now() ELSE NULL END" in consulta
    # La guarda va donde se ESCRIBE: la lista puede llegar por un POST a
    # mano. El CHECK de la base cubre el sin armar; el anulado no, y por eso
    # los dos están acá.
    assert "armado_el IS NOT NULL" in consulta
    assert "anulado_el IS NULL" in consulta
    assert "pedido_id = %s" in consulta
    assert parametros == ([11, 14], 71)
    conexion.commit.assert_called_once()


def test_contar_pedidos_sin_controlar_cuenta_PEDIDOS_vigentes_con_algun_armado():
    from app.db import contar_pedidos_sin_controlar

    conexion, cursor = _conexion_falsa()
    cursor.fetchone.return_value = (3, date(2026, 9, 5))

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_pedidos_sin_controlar(date(2026, 9, 4), date(2026, 9, 10))

    consulta = cursor.execute.call_args_list[0].args[0]
    # "Entregado" = con algún renglón armado: la mercadería salió y ya se
    # factura. Un pedido sin armar nada no es un control que falta.
    assert "r.armado_el IS NOT NULL" in consulta
    # Los anulados no se facturan: ni el pedido ni el renglón.
    assert "p.anulado_el IS NULL" in consulta
    assert "r.anulado_el IS NULL" in consulta
    # Lo que la vuelve un caso: que le FALTE alguno.
    assert "HAVING count(*) FILTER (WHERE r.controlado_el IS NULL) > 0" in consulta
    assert cursor.execute.call_args_list[0].args[1] == (date(2026, 9, 4), date(2026, 9, 10))
    assert resultado == {"casos": 3, "mas_viejo": date(2026, 9, 5)}


def test_desanular_renglon_pedido_vuelve_a_pendientes():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        desanular_renglon_pedido(11)

    assert "SET anulado_el = NULL" in cursor.execute.call_args.args[0]


def test_cerrar_y_reabrir_armado_pedido():
    conexion, cursor = _conexion_falsa()
    with patch("app.db.obtener_conexion", return_value=conexion):
        cerrar_armado_pedido(50)
    assert "SET armado_cerrado_el = now()" in cursor.execute.call_args.args[0]

    conexion2, cursor2 = _conexion_falsa()
    with patch("app.db.obtener_conexion", return_value=conexion2):
        reabrir_armado_pedido(50)
    assert "SET armado_cerrado_el = NULL" in cursor2.execute.call_args.args[0]


def test_listar_renglones_pedidos_vigentes_no_cuenta_el_renglon_anulado():
    """La CRUZ del armado no se vendió: no puede sumar a la rentabilidad teórica.

    Se verifica sobre la consulta y no sobre filas mockeadas a propósito: el
    filtro lo hace Postgres, así que un fixture que devuelva lo que yo quiera
    probaría mi aritmética, no la regla. Lo que hay que afirmar es que el
    JOIN lo pide.
    """
    conexion, cursor = _conexion_falsa()
    cursor.description = [
        ("fecha_operacion",), ("ficha_id",), ("articulo_id",), ("articulo_nombre",),
        ("articulo_grupo",), ("bultos",),
    ]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_renglones_pedidos_vigentes(1, date(2026, 8, 15), date(2026, 8, 22))

    consulta = cursor.execute.call_args.args[0]
    # El criterio de las OTRAS dieciséis lectoras de pedidos_renglones, y el
    # de las tres que derivan las salidas de stock — que es contra las que
    # esta cuenta se compara en /gerencia/rentabilidad-real.
    assert "r.anulado_el IS NULL" in consulta


def test_buscar_renglones_pedidos_trae_kilos_y_anulados_de_los_vigentes():
    conexion, cursor = _conexion_falsa()
    cursor.description = [
        ("fecha_operacion",), ("id",), ("sucursal",), ("articulo_id",), ("articulo_nombre",),
        ("cantidad",), ("cantidad_armada",), ("kilos_enviados",), ("armado_el",), ("anulado_el",),
    ]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_renglones_pedidos(1, date(2026, 8, 15), date(2026, 8, 22))

    consulta, parametros = cursor.execute.call_args.args
    # Solo pedidos VIGENTES (uno por fecha) y los kilos REALES grabados.
    assert "DISTINCT ON (fecha_operacion)" in consulta
    assert "WHERE cliente_id = %s AND anulado_el IS NULL" in consulta  # pedidos
    assert "r.kilos_enviados" in consulta
    # Acá el renglón anulado SÍ viene, y es a propósito: Armar Remito los
    # muestra marcados ("registrados, nunca desaparecen") y los descuenta al
    # sumar, en Python. Queda escrito para que no se lea como el olvido que
    # sí tenía listar_renglones_pedidos_vigentes.
    assert "r.anulado_el" in consulta
    assert "r.anulado_el IS NULL" not in consulta
    assert parametros == (1, date(2026, 8, 15), date(2026, 8, 22))


def test_listar_pedidos_vigentes_con_armado_no_cuenta_los_anulados():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_pedidos_vigentes_con_armado(1, date(2026, 8, 15))

    consulta = cursor.execute.call_args.args[0]
    # Los anulados quedan fuera del progreso ("18 de 32 armados"): en el
    # total, en los armados y en los ARMADOS CORTOS, que es la cuarta cuenta.
    assert consulta.count("r.anulado_el IS NULL") == 3
    # Y los cortos son con "<": armar de MÁS no es incompleto, igual que en
    # contar_pedidos_incompletos. Las dos tienen que decir lo mismo.
    assert "r.cantidad_armada < r.cantidad" in consulta
    assert "p.armado_cerrado_el" in consulta


# --- Stock del Depósito ---

from app.db import (  # noqa: E402
    crear_movimiento_stock,
    devoluciones_vinculadas_por_rango,
    facturacion_por_ficha,
    listar_ultimos_conteos_stock,
    entradas_y_salidas_stock_articulo,
    entradas_y_salidas_stock_articulos,
    listar_pedidos_para_reingreso,
    listar_renglones_para_reingreso,
    obtener_renglon_para_reingreso,
    stock_deposito_de_articulo,
    stock_deposito_por_articulo,
    total_reingresos_rechazo,
)


def test_stock_deposito_se_calcula_de_las_tablas_reales_y_nunca_se_guarda():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("articulo_id",), ("nombre",), ("entradas",), ("salidas",), ("reingresos",),
                          ("ajustes",), ("reproceso_primera",), ("reproceso_tomados",),
                          ("segunda_producida",), ("segunda_de_rechazos",),
                          ("segunda_de_pases",), ("segunda_remitida",)]
    # Los cuatro números del pool son DISTINTOS entre sí a propósito: con
    # dos iguales, una pata leída del lugar equivocado da el mismo total.
    cursor.fetchall.return_value = [(1, "Banana", 40, 15, 2, -3, 6, 10, 5, 4, 7, 2)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        filas = stock_deposito_por_articulo(date(2026, 9, 6))

    consulta = cursor.execute.call_args.args[0]
    # Entradas: SOLO compras recepcionadas, con la cantidad REAL de Depósito.
    assert "estado = 'recepcionado'" in consulta
    assert "cantidad_cajones_real" in consulta
    # Salidas: renglones armados de pedidos VIGENTES (reemplazados no
    # cuentan doble), sin anulados, con la cantidad realmente armada.
    assert "DISTINCT ON (cliente_id, fecha_operacion)" in consulta
    assert "COALESCE(r.cantidad_armada, r.cantidad)" in consulta
    assert "r.armado_el IS NOT NULL AND r.anulado_el IS NULL" in consulta
    # Los reingresos por rechazo vienen APARTE de los otros movimientos.
    assert "tipo = 'reingreso_rechazo'" in consulta
    assert "tipo <> 'reingreso_rechazo'" in consulta
    # El reproceso también deriva: + primera armada, − bultos tomados.
    assert "SUM(bultos_primera)" in consulta
    assert "SUM(bultos_tomados)" in consulta
    # El stock es la cuenta, hecha acá: nada de columnas cacheadas.
    assert filas[0]["stock"] == 40 + 2 + (-3) + 6 - 10 - 15
    # La segunda es un pool APARTE, con TRES entradas y una salida: lo
    # producido en reprocesos, lo que entró por rechazos que no volvieron al
    # stock, y lo que el depósito pasó de primera a segunda − lo remitido.
    assert filas[0]["segunda"] == 5 + 4 + 7 - 2
    # Un rechazo mandado a segunda no suma al stock normal.
    assert "destino_rechazo IS NULL OR destino_rechazo = 'stock'" in consulta
    assert "destino_rechazo IN ('segunda', 'reproceso')" in consulta
    assert "SUM(bultos_segunda)" in consulta


def test_el_pool_de_segunda_arranca_en_el_CORTE_y_por_las_TRES_patas():
    """El piso del pool de segunda, con la asimetría del día del corte.

    Hasta el 05/09 esta era la única cuenta del módulo que ningún corte
    rebaseaba, y la cola vieja se sumaba a lo contado: medido esa noche,
    ~40 bultos en cinco artículos, con Zapallito en 23 donde había 15.

    Las TRES patas o ninguna: si se recorta la producción y no los remitos,
    un remito viejo sigue restando contra segunda que ya no cuenta y el
    pool queda por debajo de lo que hay. No falla ruidosamente — da un
    número equivocado y nada más.

    Y la fecha sale de corte_modelo, nunca de una constante.
    """
    conexion, cursor = _conexion_falsa()
    cursor.description = [("articulo_id",), ("nombre",), ("entradas",), ("salidas",), ("reingresos",),
                          ("ajustes",), ("reproceso_primera",), ("reproceso_tomados",),
                          ("segunda_producida",), ("segunda_de_rechazos",),
                          ("segunda_de_pases",), ("segunda_remitida",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock_deposito_por_articulo(date(2026, 9, 6))

    consulta = cursor.execute.call_args.args[0]
    assert "corte_seg AS (SELECT fecha FROM corte_modelo WHERE id = 1)" in consulta
    # La producción: los 'inicial' DEL corte más lo posterior. Un `>=` a
    # secas metería las guías R normales del día, que el conteo de esa
    # tarde ya vio.
    assert "fecha_operacion > corte_seg.fecha" in consulta
    assert "tipo = 'inicial' AND fecha_operacion >= corte_seg.fecha" in consulta
    # Las otras dos patas, solo lo posterior.
    trozo_rechazos = consulta.split("segunda_rechazo AS")[1].split("remitida AS")[0]
    assert "fecha_operacion > corte_seg.fecha" in trozo_rechazos
    trozo_remitos = consulta.split("remitida AS")[1].split("SELECT a.id")[0]
    assert "fecha_operacion > corte_seg.fecha" in trozo_remitos
    assert "2026" not in trozo_remitos, "la fecha de corte no se escribe a mano"


def test_crear_movimiento_stock_guarda_la_foto_del_sistema_y_devuelve_el_resultante():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(12.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = crear_movimiento_stock(7, "ajuste", -3.0, "rotura", date(2026, 8, 25))

    insert = cursor.execute.call_args_list[-1]
    assert "INSERT INTO movimientos_stock" in insert.args[0]
    # La foto del stock SIN este movimiento, como en ajustes_vacios:
    # sin ese rastro cualquier faltante se tapa con un ajuste.
    assert insert.args[1] == (
        7, "ajuste", -3.0, "rotura", None, date(2026, 8, 25), 12.0, None, None, None, None, None, None,
        None,
        # proveedor_devolucion_id y compra_devolucion_id: solo los usa la
        # devolución al proveedor, y NUNCA los dos juntos.
        None, None,
    )
    assert resultado == 9.0
    conexion.commit.assert_called_once()


def test_crear_movimiento_stock_reingreso_lleva_cliente_y_fecha_propia():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(7, "reingreso_rechazo", 4.0, "Devolvió Día", date(2026, 8, 24), cliente_id=1)

    insert = cursor.execute.call_args_list[-1]
    assert insert.args[1] == (
        7, "reingreso_rechazo", 4.0, "Devolvió Día", 1, date(2026, 8, 24), 0.0, None, None, None, None, None, None,
        None,
        # proveedor_devolucion_id y compra_devolucion_id: solo los usa la
        # devolución al proveedor, y NUNCA los dos juntos.
        None, None,
    )


def test_crear_movimiento_stock_reingreso_vinculado_lleva_renglon_y_costo_congelado():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(
            7, "reingreso_rechazo", 4.0, "rechazo por calidad", date(2026, 8, 24),
            cliente_id=1, pedido_renglon_id=77, costo_por_bulto=2000.0,
        )

    insert = cursor.execute.call_args_list[-1]
    # El vínculo al renglón y el costo congelado (los calcula el server):
    # con esto el lote de reingreso deja de ser "sin costo" para la Real.
    assert insert.args[1] == (
        7, "reingreso_rechazo", 4.0, "rechazo por calidad", 1, date(2026, 8, 24), 0.0, 77, 2000.0,
        None, None, None, None, None,
        # proveedor_devolucion_id y compra_devolucion_id: solo los usa la
        # devolución al proveedor, y NUNCA los dos juntos.
        None, None,
    )


def test_crear_movimiento_stock_rechazo_a_segunda_no_toca_el_stock_normal():
    # El destino se decide al cargar: lo que va a segunda entra y sale en
    # el mismo acto, así que el stock del artículo no se mueve.
    #
    # UN SOLO fetchone: hasta el 17/09 había un segundo, la ficha del renglón,
    # que el server leía para derivar en qué caja nuestra volvía. Esa caja se
    # tira (ver core/envases.py), así que no hay nada que derivar ni escribir.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(30.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = crear_movimiento_stock(
            7, "reingreso_rechazo", 40.0, "rechazado por calidad", date(2026, 8, 24),
            cliente_id=1, pedido_renglon_id=77, costo_por_bulto=2000.0,
            destino_rechazo="reproceso", bultos_segunda=12.0,
        )

    insert = cursor.execute.call_args_list[-1]
    assert insert.args[1] == (
        7, "reingreso_rechazo", 40.0, "rechazado por calidad", 1, date(2026, 8, 24), 30.0, 77, 2000.0,
        "reproceso", 12.0, None, None, None,
        # proveedor_devolucion_id y compra_devolucion_id: solo los usa la
        # devolución al proveedor, y NUNCA los dos juntos.
        None, None,
    )
    assert resultado == 30.0


def test_crear_movimiento_stock_merma_dirigida_guarda_el_lote_elegido():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(30.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(
            7, "merma", -3.0, "se pudrió", date(2026, 8, 26),
            lote_tipo="reproceso", lote_origen_id=9,
        )

    insert = cursor.execute.call_args_list[-1]
    assert insert.args[1] == (
        7, "merma", -3.0, "se pudrió", None, date(2026, 8, 26), 30.0, None, None,
        None, None, "reproceso", 9, None,
        # proveedor_devolucion_id y compra_devolucion_id: solo los usa la
        # devolución al proveedor, y NUNCA los dos juntos.
        None, None,
    )


def test_crear_movimiento_stock_devolucion_ESCRIBE_la_compra_elegida():
    """La columna nueva tiene que LLEGAR al INSERT, no solo a la firma.

    Los otros cinco tests de esta familia la pasan en None, así que un
    INSERT que escribiera NULL a la fuerza los deja a todos en verde — el
    canario lo midió y no caía ninguno. Lo que distingue "el parámetro se
    guarda" de "la columna está en la lista" es un caso con un valor.

    Y el proveedor suelto va en None en el mismo caso: los dos juntos los
    rechaza `movimientos_stock_compra_o_proveedor`, así que si alguna vez
    se escribieran los dos, esto cae acá y no en la base.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(30.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(
            7, "reingreso_rechazo", 4.0, "rechazado por calidad", date(2026, 8, 26),
            cliente_id=1, pedido_renglon_id=77, costo_por_bulto=2000.0,
            destino_rechazo="devolucion_proveedor", compra_devolucion_id=502,
        )

    insert = cursor.execute.call_args_list[-1]
    assert insert.args[1] == (
        7, "reingreso_rechazo", 4.0, "rechazado por calidad", 1, date(2026, 8, 26), 30.0,
        77, 2000.0, "devolucion_proveedor", None,
        None, None, None,
        # El proveedor suelto NO viaja: con compra, sale de ella.
        None, 502,
    )
    # Y la columna está nombrada en el INSERT, no solo el valor en la tupla:
    # con un cursor falso la tupla llega igual con la columna equivocada
    # (corolario 40).
    assert "proveedor_devolucion_id, compra_devolucion_id)" in insert.args[0]
    # Y NO HAY ENVASE. La caja del rechazo a cajón grande se tira, así que no
    # hay nada que devolverle al stock: la columna se fue el 17/09 con la pata
    # `liberadas` (db/envases_9_*.sql). Va como assert y no como comentario
    # porque el que vuelva a cablearla no va a leer el comentario.
    assert "envase_id" not in insert.args[0]


def test_la_ficha_que_SOLO_TIENE_UNA_BAJA_no_se_cae_de_la_cuenta():
    """LA PATA FÁCIL DE OLVIDAR. La baja resta en el SELECT final, pero si
    `bajas_ficha` no está también en el UNION de `fichas_con_algo`, una ficha
    cuyo ÚNICO movimiento sea una baja —una merma o un pase a segunda— no
    existe para la consulta: la resta estaría bien escrita y no se haría
    nunca.

    El CTE se llamaba `mermas_ficha` hasta el 21/09, cuando el pase entró a
    la misma cuenta. El nombre se movió con la condición: un CTE que se llama
    "mermas" y suma dos tipos se lee y no se verifica.

    Se mira el UNION y no el resultado porque los otros tres términos ya
    están: un fixture con armados encima taparía el agujero sin querer.
    """
    from app.db import _SQL_STOCK_PARTIDO

    union = _SQL_STOCK_PARTIDO.split("fichas_con_algo AS (")[1].split(")")[0]
    for pata in ("armadas", "salidas_ficha", "reingresos_ficha", "bajas_ficha"):
        assert f"FROM {pata}" in union, pata
    # Y LAS PATAS ENTERAS, no solo el nombre a la vista: cuatro SELECT unidos
    # por tres UNION. Sin esto el test pasa con el `UNION` borrado —el nombre
    # sigue estando en el texto— que es exactamente como se descubrió que no
    # miraba lo que decía mirar.
    assert union.count("SELECT") == 4
    assert union.count("UNION") == 3


def test_las_BAJAS_por_ficha_usan_LA_MISMA_VENTANA_que_los_otros_terminos():
    """Si ésta mirara toda la historia y las otras solo lo posterior al corte,
    la resta mezclaría dos eras. Medido con el canario: corrida con `>=` el
    número se mueve (7 cajas contra 3), así que el recorte hace trabajo real.

    Se recorta el trozo de la CTE para no matchear el `> corte.fecha` de los
    otros tres — el assert de substring tiene que calificar de quién habla.
    """
    from app.db import _SQL_STOCK_PARTIDO

    trozo = _SQL_STOCK_PARTIDO.split("bajas_ficha AS (")[1].split("), fichas_con_algo")[0]
    # LOS DOS TIPOS, y desde el 21/09 el pase también: una caja armada que se
    # pone fea pasa a segunda directo, y eso baja la ficha igual que tirarla.
    assert "m.tipo IN ('merma', 'pase_a_segunda')" in trozo
    assert "m.ficha_id IS NOT NULL" in trozo
    assert "m.fecha_operacion > corte.fecha" in trozo
    assert "m.fecha_operacion >= corte.fecha" not in trozo, (
        "con >= el día del corte se cuenta dos veces: la foto del stock inicial "
        "se toma a la tarde y ya viene neta del trabajo de ese día"
    )
    assert "m.fecha_operacion <= tope.fecha" in trozo
    # Y RESTA, como cualquier salida: son cajas que se fueron.
    assert "- COALESCE(me.total, 0) AS stock" in _SQL_STOCK_PARTIDO


def _valor_insertado(cursor, columna, fragmento=None):
    """El valor que el INSERT le puso a una columna, buscada POR NOMBRE.

    Indexar desde el final (`args[1][-1]`) parece equivalente y no lo es:
    `ficha_id` era la última hasta que el 11/09 se agregó
    `proveedor_devolucion_id` al final, y el test pasó a mirar la columna
    nueva sin que nada dijera que estaba mirando otra cosa. La lista de
    columnas está en el propio INSERT: se lee de ahí y no envejece.

    `fragmento` elige CUÁL insert mirar cuando hay más de uno (crear_reproceso
    escribe la cabecera y después los consumos, y el último es un consumo).
    Sin él se mira el último, que es lo que ya hacían veinte llamadores.
    """
    llamadas = cursor.execute.call_args_list
    if fragmento is not None:
        llamadas = [ll for ll in llamadas if fragmento in ll.args[0]]
    consulta, parametros = llamadas[-1].args
    columnas = consulta.split("(", 1)[1].split(")", 1)[0]
    nombres = [c.strip() for c in columnas.split(",")]
    return parametros[nombres.index(columna)]


def test_la_merma_puede_nombrar_su_ficha_y_por_default_no_la_tiene():
    """Los sueltos son el caso común, así que `ficha_id` es opcional y viaja
    en None sin que nadie lo pida."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[(30.0,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(7, "merma", -3.0, "podrido", date(2026, 9, 10), ficha_id=9)
    assert _valor_insertado(cursor, "ficha_id") == 9

    conexion, cursor = _conexion_falsa(filas_fetchone=[(30.0,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(7, "merma", -3.0, "podrido", date(2026, 9, 10))
    assert _valor_insertado(cursor, "ficha_id") is None


def test_la_foto_de_la_merma_entra_en_LA_MISMA_TRANSACCION_que_la_merma():
    """O quedan las dos o no queda ninguna: una merma guardada con la foto
    perdida porque el segundo commit falló sería exactamente el agujero que
    la foto viene a tapar.

    Se verifica por el ORDEN contra el único commit: los dos INSERT tienen
    que estar antes. Un `crear_movimiento_stock` que commitea y después
    guarda la foto pasa cualquier assert sobre los parámetros y falla acá.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(30.0,), (555,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(
            7, "merma", -3.0, "se pudrió", date(2026, 8, 26),
            foto_ruta="merma/2026-08-26/abc.jpg",
        )

    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    assert any("INSERT INTO movimientos_stock" in c for c in consultas)
    foto = cursor.execute.call_args_list[-1]
    assert "INSERT INTO fotos_merma" in foto.args[0]
    # El id sale del RETURNING del INSERT de arriba, no de un currval().
    assert foto.args[1] == (555, "merma/2026-08-26/abc.jpg")
    conexion.commit.assert_called_once()
    # Un solo commit, y DESPUÉS de las dos escrituras.
    assert conexion.mock_calls.index(call.commit()) > max(
        i for i, llamada in enumerate(conexion.mock_calls)
        if "execute" in str(llamada)
    )


def test_sin_foto_la_merma_no_toca_fotos_merma():
    """El caso feliz del otro lado: sin foto no se escribe una fila vacía.

    Va con el de arriba a propósito — una batería que solo prueba el caso
    con foto pasa entera con un INSERT que corre siempre.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(30.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(7, "merma", -3.0, "se pudrió", date(2026, 8, 26))

    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    assert not any("fotos_merma" in c for c in consultas)


def test_la_foto_de_la_merma_de_segunda_cuelga_de_la_SALIDA_y_no_del_movimiento():
    """Los dos dueños de fotos_merma son tablas distintas, y la de segunda no
    pasa por movimientos_stock: guardarla como `movimiento_id` la colgaría de
    un id de otra tabla — un puntero que apunta a cualquier cosa."""
    from app.db import crear_salida_de_segunda

    conexion, cursor = _conexion_falsa(filas_fetchone=[(88,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_salida_de_segunda(1, 7.0, date(2026, 9, 9), destino="merma",
                                motivo="podrido", foto_ruta="merma/2026-09-09/x.jpg")

    foto = cursor.execute.call_args_list[-1]
    assert "INSERT INTO fotos_merma (salida_segunda_id, foto_ruta)" in foto.args[0]
    assert foto.args[1] == (88, "merma/2026-09-09/x.jpg")
    conexion.commit.assert_called_once()


def test_stock_de_porcion_es_la_MISMA_funcion_que_congela_el_conteo():
    """Los sueltos salen de `_stock_de_ficha`, la que usa el conteo y el Remanente.

    Si esta cuenta se escribiera aparte, el Cotejo compararía contra un
    número y el ajuste contra otro — que es exactamente lo que pasó hasta el
    08/09, cuando el ajuste usaba el total del artículo.
    """
    from app.db import stock_de_porcion

    conexion, cursor = _conexion_falsa()
    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._stock_de_ficha", return_value=5.0) as cuenta,
    ):
        assert stock_de_porcion(7) == 5.0

    # ficha_id None son los SUELTOS: el caso del ajuste.
    assert cuenta.call_args.args[1:] == (7, None)
    assert conexion.close.call_count == 1


def test_stock_deposito_de_articulo_hace_la_misma_cuenta_por_articulo():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(-5.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock = stock_deposito_de_articulo(2)

    consulta = cursor.execute.call_args.args[0]
    assert "AND articulo_id = %s" in consulta
    # La fecha tope va PRIMERA y siempre: acá None, que el SQL lee como hoy.
    assert cursor.execute.call_args.args[1] == (None, 2, 2, 2, 2, 2)
    assert stock == -5.0


def test_entradas_y_salidas_para_fifo_ordena_por_fecha_real_del_hecho():
    # El primer fetchone es el corte: desde el piso, la consulta de entradas
    # lo lee antes para no mirar nada anterior.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 8, 1),)])
    cursor.description = [
        ("fecha_orden",), ("momento_orden",), ("tipo_lote",), ("fecha_lote",), ("detalle",), ("motivo",),
        ("cantidad",), ("articulo_id",),
    ]
    cursor.fetchall.side_effect = [
        [(date(2026, 8, 20), "10:00", "guia", None, None, None, 30.0, 2)],
        [],  # las salidas: ninguna
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        entradas, salidas = entradas_y_salidas_stock_articulo(2)

    consulta_entradas = _consulta_con(cursor, "c.estado = 'recepcionado'")
    # El lote de una compra es su guía; el orden, el instante de recepción.
    assert "c.estado = 'recepcionado'" in consulta_entradas
    assert "procesada_el" in consulta_entradas
    # Un movimiento ordena por su fecha_operacion (la REAL del hecho: un
    # reingreso cargado hoy con fecha de ayer entra en el FIFO de ayer).
    assert "m.fecha_operacion, m.creado_en" in consulta_entradas
    assert "m.cantidad > 0" in consulta_entradas

    # Un rechazo mandado a segunda no es lote de stock: no entra al FIFO.
    assert "m.destino_rechazo IS NULL OR m.destino_rechazo = 'stock'" in consulta_entradas

    # Desde E4 las salidas son las MISMAS que las del FIFO de costo: una por
    # una, fechadas, y las dirigidas adentro con su lote_tipo — ya no hay un
    # total sin fecha ni una tercera consulta aparte.
    # TRES consultas: el corte, los lotes y las salidas.
    assert cursor.execute.call_count == 3
    consulta_salidas = _consulta_con(cursor, "'reproceso_toma'")
    assert "DISTINCT ON (cliente_id, fecha_operacion)" in consulta_salidas
    assert "m.cantidad < 0" in consulta_salidas
    assert "m.lote_tipo, m.lote_origen_id" in consulta_salidas
    assert salidas == []

    # Y la entrada viaja con su "orden" ya armado, para que ninguna pantalla
    # tenga que rehacerlo.
    assert entradas[0]["orden"] == (date(2026, 8, 20), "10:00")


def test_el_FIFO_no_mira_nada_ANTERIOR_al_corte_en_ninguna_de_las_tres_patas():
    """El piso va en las TRES patas de la consulta de lotes, no en una.

    Medido el 07/09: 18 de las 32 guías R de dos días se habían costeado
    contra lotes que el corte declaró inexistentes ($4.705.353). El
    compensatorio del corte cancela el saldo viejo en el TOTAL, pero opera
    sobre el neto y el FIFO razona por lote, así que los restantes
    sobrevivían al cierre.

    Cada assert lleva el alias de SU tabla: las tres columnas se llaman
    parecido y un substring pelado matchearía la pata equivocada.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 9, 5),)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [[], []]

    with patch("app.db.obtener_conexion", return_value=conexion):
        entradas_y_salidas_stock_articulo(1)

    consulta = _consulta_con(cursor, "c.estado = 'recepcionado'")
    # Compras: ESTRICTO y por el instante de recepción en hora argentina, que
    # es el mismo que ordena el lote. Una compra del día del corte ya está
    # adentro de la foto que se contó esa tarde.
    assert "(c.procesada_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date > %s" in consulta

    # EL DÍA DEL CORTE ES ASIMÉTRICO: entra la FOTO (el 'stock_inicial' y las
    # guías R 'inicial' de ese día) y nada más de ese día. Con `>=` en las dos
    # puntas el día del corte se cuenta dos veces, que es lo que el comentario
    # de _SQL_STOCK_PARTIDO ya midió para la cuenta por ficha.
    assert "(m.tipo = 'stock_inicial' AND m.fecha_operacion = %s)" in consulta
    assert "OR m.fecha_operacion > %s" in consulta
    assert "(rp.tipo = 'inicial' AND rp.fecha_operacion = %s)" in consulta
    assert "OR rp.fecha_operacion > %s" in consulta

    # Y la fecha SALE de corte_modelo: una constante clavada quedaría
    # mintiendo el día que se haga un corte nuevo.
    assert _consulta_con(cursor, "corte_modelo")
    corte = date(2026, 9, 5)
    parametros = [c.args[1] for c in cursor.execute.call_args_list if len(c.args) > 1]
    assert parametros[0] == ([1], corte, [1], corte, corte, [1], corte, corte)


def test_el_compensatorio_del_corte_sale_POR_TIPO_y_no_por_fecha():
    """Está fechado EN el corte: un piso por fecha lo dejaría adentro.

    Y tiene que salir de las DOS listas. Como lote (el positivo) sería
    mercadería que no existe; como salida (el negativo) le restaría a los
    lotes NUEVOS bultos que nunca salieron de ellos, que es el mismo doble
    conteo del otro lado.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 9, 5),)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [[], []]

    with patch("app.db.obtener_conexion", return_value=conexion):
        entradas_y_salidas_stock_articulo(1)

    assert "m.tipo <> 'cierre_modelo_viejo'" in _consulta_con(cursor, "c.estado = 'recepcionado'")
    assert "m.tipo <> 'cierre_modelo_viejo'" in _consulta_con(cursor, "'reproceso_toma'")


def test_las_SALIDAS_llevan_piso_ESTRICTO_en_las_tres_patas():
    """Una salida del día del corte restaría la foto dos veces.

    El conteo se toma a la tarde, así que la foto ya viene neta del trabajo
    de ese día. Si además la salida consume la foto, se resta dos veces: es
    el caso que el comentario de `_SQL_STOCK_PARTIDO` midió en −10 donde
    había 20.

    El costo es real y está asumido: las entregas del día del corte y
    anteriores pierden su atribución, y como los dos llamadores de
    `atribuir_costos_fifo` iteran su salida para armar las filas, esas
    entregas desaparecen de ahí. Su costo salía de lotes anteriores al corte
    —declarados no confiables—, así que era cero igual.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 9, 5),)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [[], []]

    with patch("app.db.obtener_conexion", return_value=conexion):
        entradas_y_salidas_stock_articulo(1)

    salidas = _consulta_con(cursor, "'reproceso_toma'")
    # Las tres patas, cada una con el alias de SU tabla: las tres columnas se
    # llaman parecido y un substring pelado matchearía la equivocada.
    assert "(r.armado_el AT TIME ZONE 'America/Argentina/Buenos_Aires')::date > %s" in salidas
    assert "m.fecha_operacion > %s" in salidas
    assert "rp.fecha_operacion > %s" in salidas
    # Estricto, no `>=`: nada del día del corte.
    assert ">= %s" not in salidas


def test_crear_reproceso_lee_el_corte_UNA_sola_vez():
    """El piso de fecha y el piso de los lotes son la misma fecha.

    Los dos salen de `_fecha_corte`, que es una sola definición; lo que se
    evita acá es pagar dos viajes a la base por el mismo dato adentro de la
    misma transacción.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (77,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 20), 20.0, 1000.0)],
        [],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_reproceso(1, 10, 8, 0, 2, date(2026, 8, 20))

    lecturas = [c for c in cursor.execute.call_args_list if "corte_modelo" in c.args[0]]
    assert len(lecturas) == 1


def test_entradas_de_varios_articulos_devuelve_una_entrada_por_cada_id_pedido():
    # Igual que las salidas: el artículo sin movimientos sale en cero y con
    # listas vacías, no ausente. Y en UNA sola conexión para todos.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 8, 1),)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 20), 8.0, 1000.0, articulo_id=2)],
        [_salida_fifo(date(2026, 8, 22), 20.0, articulo_id=2)],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        movimientos = entradas_y_salidas_stock_articulos([2, 7])

    assert sorted(movimientos) == [2, 7]
    entradas_2, salidas_2 = movimientos[2]
    assert [e["origen_id"] for e in entradas_2] == [101]
    assert [s["cantidad"] for s in salidas_2] == [20.0]
    # El que no tuvo nada sale con las dos listas vacías, nunca ausente.
    assert movimientos[7] == ([], [])
    # TRES consultas en total (el corte, los lotes y las salidas), no tres
    # por artículo — y una sola conexión. La de las dirigidas aparte ya no
    # existe desde E4: cada dirigida es una salida más.
    assert cursor.execute.call_count == 3
    assert conexion.close.call_count == 1


def test_entradas_de_varios_articulos_sin_ids_no_toca_la_base():
    # Sin artículos con guía R no hay nada que traer: ni conexión se abre.
    with patch("app.db.obtener_conexion") as abrir:
        assert entradas_y_salidas_stock_articulos([]) == {}
    abrir.assert_not_called()


def test_total_reingresos_rechazo_excluye_anulados():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(11.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        total = total_reingresos_rechazo()

    consulta = cursor.execute.call_args.args[0]
    assert "anulado_el IS NULL AND tipo = 'reingreso_rechazo'" in consulta
    assert total == 11.0


def test_listar_reprocesos_por_rango_filtra_por_articulo_solo_si_se_lo_piden():
    """El filtro va en el WHERE y con parámetro, no interpolado.

    Y calificado con el alias `rp.`: la consulta une `articulos` dos veces
    (la del reproceso y la de la ficha), así que un `articulo_id = %s`
    pelado no dice cuál de las dos — corolario 4.
    """
    from app.db import listar_reprocesos_por_rango

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_reprocesos_por_rango(date(2026, 9, 1), date(2026, 9, 10), 7)
    consulta, parametros = cursor.execute.call_args.args
    assert "AND rp.articulo_id = %s" in consulta
    assert parametros == (date(2026, 9, 1), date(2026, 9, 10), 7)

    # Sin artículo, la condición NO está: un `articulo_id = NULL` no matchea
    # nada y la pantalla saldría vacía sin decir por qué.
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []
    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_reprocesos_por_rango(date(2026, 9, 1), date(2026, 9, 10))
    consulta, parametros = cursor.execute.call_args.args
    assert "articulo_id = %s" not in consulta
    assert parametros == (date(2026, 9, 1), date(2026, 9, 10))


def test_contado_hoy_trae_UN_renglon_por_porcion_el_mas_nuevo_del_dia():
    """Un conteo corregido aparecía dos veces y se leía como contado dos veces.

    No se contó dos veces: se corrigió. Corregir un conteo es cargarlo de
    nuevo —no hay UPDATE ni anulación de conteos— así que el viejo queda
    tapado, y mostrarlo es mostrar algo que ya no vale.

    Se afirma sobre el SQL porque la regla vive ahí: el DISTINCT ON con las
    TRES claves de la porción y el desempate por `creado_en DESC`. Con dos
    claves, la segunda y los sueltos se pisan (los dos tienen ficha_id nulo).
    """
    from app.db import listar_conteos_stock_de_fecha

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_conteos_stock_de_fecha(date(2026, 9, 11))
    consulta = cursor.execute.call_args.args[0]
    assert "DISTINCT ON (c.articulo_id, c.ficha_id, c.es_segunda)" in consulta
    assert "ORDER BY c.articulo_id, c.ficha_id, c.es_segunda, c.creado_en DESC" in consulta
    # Y sigue recortando al DÍA: el Cotejo toma el último de la historia,
    # esta lista el último de la jornada. Son ventanas distintas a propósito.
    assert "c.creado_en >= ((%s::date)::timestamp" in consulta


def test_contado_hoy_DEVUELVE_las_filas_ya_ordenadas_por_articulo():
    """Que la función ORDENE, no solo que el ordenador exista.

    El cursor devuelve las filas en el orden de la base y este test las da
    a propósito revueltas: si `listar_conteos_stock_de_fecha` dejara de
    llamar al ordenador, las devolvería tal cual y la pantalla volvería a
    mostrar "Lima Caja Día %" arriba y "Lima" quince renglones abajo.

    NO se prueba desde la pantalla: parchear el lector para probar que el
    lector ordena es pedirle al parche que haga el trabajo que se quiere
    verificar, y el test pasaría con la función rota.
    """
    from app.db import listar_conteos_stock_de_fecha

    revueltas = [
        (1, 1.0, datetime(2026, 9, 11, 16, 0), "Palta", 7, False, "Palta", "Cliente"),
        (2, 5.0, datetime(2026, 9, 11, 15, 0), "Lima", None, True, None, None),
        (3, 6.0, datetime(2026, 9, 11, 14, 0), "Lima", None, False, None, None),
    ]
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("cantidad",), ("creado_en",), ("articulo_nombre",),
                          ("ficha_id",), ("es_segunda",), ("ficha_nombre",), ("ficha_cliente",)]
    cursor.fetchall.return_value = revueltas

    with patch("app.db.obtener_conexion", return_value=conexion):
        filas = listar_conteos_stock_de_fecha(date(2026, 9, 11))

    assert [(f["articulo_nombre"], f["es_segunda"], f["ficha_id"]) for f in filas] == [
        ("Lima", False, None),      # sueltos
        ("Lima", True, None),       # segunda
        ("Palta", False, 7),        # las cajas de la ficha
    ]


def test_el_Cotejo_y_Contado_hoy_ordenan_con_LA_MISMA_funcion():
    """Dos pantallas que muestran las mismas porciones tienen que ponerlas en
    el mismo lugar; si no, el mismo conteo parece dos conteos distintos.

    Se prueba el ORDENADOR, que es donde vive la regla, con las tres
    porciones de dos artículos mezcladas a propósito.
    """
    from app.db import _ordenar_porciones_contadas

    revuelto = [
        {"articulo_nombre": "Lima", "ficha_id": None, "es_segunda": True, "ficha_nombre": None},
        {"articulo_nombre": "Palta", "ficha_id": None, "es_segunda": False, "ficha_nombre": None},
        {"articulo_nombre": "Lima", "ficha_id": 9, "es_segunda": False, "ficha_nombre": "B"},
        {"articulo_nombre": "Lima", "ficha_id": None, "es_segunda": False, "ficha_nombre": None},
        {"articulo_nombre": "Lima", "ficha_id": 7, "es_segunda": False, "ficha_nombre": "A"},
    ]
    ordenado = [
        (f["articulo_nombre"], f["ficha_nombre"], f["es_segunda"])
        for f in _ordenar_porciones_contadas(revuelto)
    ]
    # Cada artículo junto; adentro sueltos, después las fichas (alfabéticas)
    # y la segunda al final — el mismo `orden` (0, 1, 2) del Remanente.
    assert ordenado == [
        ("Lima", None, False),
        ("Lima", "A", False),
        ("Lima", "B", False),
        ("Lima", None, True),
        ("Palta", None, False),
    ]


def test_el_numero_de_guia_PISA_la_fecha_y_el_articulo_EN_LA_CONSULTA():
    """Con `guia_id`, el recorte es SOLO `rp.id`: ni la fecha ni el artículo
    entran en el WHERE.

    Se afirma sobre el SQL y no sobre la pantalla porque es donde vive la
    regla — la ruta mockeada no ve la consulta. Y se afirma que las otras
    condiciones NO ESTÁN, no solo que `rp.id` sí: con los tres `AND`, la
    guía R251 del 02/09 buscada dentro del rango de esta semana daría cero
    filas y las dos condiciones estarían "bien" por separado. Ese vacío se
    lee como "esa guía no existe", que es la peor forma de fallar que tiene
    un filtro por id.
    """
    from app.db import listar_reprocesos_por_rango

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_reprocesos_por_rango(date(2026, 9, 1), date(2026, 9, 10), 7, 251)
    consulta, parametros = cursor.execute.call_args.args
    assert "WHERE rp.id = %s" in consulta
    assert "fecha_operacion >=" not in consulta
    assert "rp.articulo_id = %s" not in consulta
    # Los parámetros ACOMPAÑAN al recorte: una consulta de un placeholder con
    # tres parámetros no falla en el test (el cursor es falso) pero revienta
    # en producción.
    assert parametros == (251,)


def test_buscar_compras_pregunta_por_LAS_DOS_fotos_con_claves_distintas():
    """La comanda cuelga de la GUÍA y el pesaje de la COMPRA. Dos EXISTS con
    dos claves: con una sola, una compra sin pesaje mostraría el de otra
    compra de la misma guía."""
    from app.db import buscar_compras

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_compras(date(2026, 9, 1), date(2026, 9, 10), None, None)
    consulta = _sql_que_contiene(cursor, "FROM compras c")
    assert "FROM fotos_guia fg WHERE fg.guia_id = c.guia_id) AS tiene_comanda" in consulta
    assert "FROM fotos_recepcion fr WHERE fr.compra_id = c.id) AS tiene_pesaje" in consulta


def test_listar_movimientos_stock_trae_anulados_marcados_por_fecha_real():
    from app.db import listar_movimientos_stock_por_rango

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_movimientos_stock_por_rango(date(2026, 8, 18), date(2026, 8, 25))

    consulta = cursor.execute.call_args.args[0]
    # Por fecha_operacion (la REAL del hecho) y SIN filtrar anulados: se
    # muestran marcados — nunca desaparecen del listado.
    assert "m.fecha_operacion >= %s AND m.fecha_operacion <= %s" in consulta
    assert "anulado_el IS NULL" not in consulta
    assert "m.anulado_el" in consulta
    assert "cl.nombre AS cliente_nombre" in consulta
    # LA FICHA, que es lo que le pone nombre a la porción en la pantalla. Va
    # calificada con el alias y no como `ficha_id` pelado: la consulta une
    # `pedidos_renglones`, que TAMBIÉN tiene esa columna, así que un assert
    # de substring sin alias matchearía la tabla equivocada — corolario 4.
    #
    # Este test es la mitad que el de la pantalla no puede cubrir: aquél
    # mockea este lector, así que sacar la columna de acá no lo hace caer.
    assert "m.ficha_id" in consulta


def test_anular_movimiento_stock_es_baja_logica_e_idempotente():
    from app.db import anular_movimiento_stock

    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_movimiento_stock(32)

    consulta = cursor.execute.call_args.args[0]
    assert "SET anulado_el = now()" in consulta
    # No re-pisa una anulación previa (el timestamp original se conserva).
    assert "anulado_el IS NULL" in consulta
    assert cursor.execute.call_args.args[1] == (32,)
    conexion.commit.assert_called_once()


def test_crear_conteo_stock_graba_la_foto_y_no_devuelve_nada():
    from app.db import crear_conteo_stock

    conexion, cursor = _conexion_falsa(filas_fetchone=[(7.0,)])
    # Sin fichas con movimiento: el stock partido devuelve vacío, así que
    # los sueltos son el total del artículo.
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = crear_conteo_stock(2, 4.0)

    insert = cursor.execute.call_args_list[-1]
    assert "INSERT INTO conteos_stock" in insert.args[0]
    # La foto del sistema se graba del lado del server...
    assert insert.args[1] == (2, 4.0, 7.0, None, False)
    # ...y NUNCA se le devuelve al operario: si la ve, transcribe en vez
    # de contar.
    assert resultado is None
    conexion.commit.assert_called_once()


def test_crear_conteo_stock_de_una_ficha_congela_el_stock_DE_ESA_FICHA():
    """La foto de un conteo de ficha son SUS cajas, no el total del artículo.

    Si congelara el total, el Cotejo de una ficha compararía 12 cajas
    contadas contra los 300 bultos del artículo y daría siempre rojo.
    """
    from app.db import crear_conteo_stock

    conexion, cursor = _conexion_falsa()
    # cajas por ficha: la 11 tiene 20, la 12 tiene 5.
    cursor.fetchall.return_value = [(2, 11, 20.0, False), (2, 12, 5.0, False)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_conteo_stock(2, 18.0, ficha_id=11)

    insert = cursor.execute.call_args_list[-1]
    assert insert.args[1] == (2, 18.0, 20.0, 11, False)


def test_crear_conteo_stock_de_la_SEGUNDA_congela_EL_POOL_y_no_las_cajas():
    """La foto de un conteo de segunda es el POOL, y sale de
    `_segunda_de_articulo` — la MISMA cuenta que dibuja la porción en el
    Remanente.

    Con dos cuentas, el conteo se congelaría contra un número y el Cotejo lo
    compararía contra otro: es el bug del 08/09 con los sueltos y el total,
    servido de nuevo. Por eso el parche devuelve 42 mientras `_stock_de_ficha`
    daría otra cosa — si alguien enchufa la función equivocada, el test cae.
    """
    from app.db import crear_conteo_stock

    conexion, cursor = _conexion_falsa()
    cursor.fetchall.return_value = [(2, 11, 20.0, False)]

    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._segunda_de_articulo", return_value=42.0) as pool,
        patch("app.db._stock_de_ficha", return_value=999.0) as por_ficha,
    ):
        crear_conteo_stock(2, 40.0, es_segunda=True)

    insert = cursor.execute.call_args_list[-1]
    # es_segunda=True y ficha_id None: la base lo exige con el check
    # conteos_stock_segunda_sin_ficha, y acá se cumple por construcción.
    assert insert.args[1] == (2, 40.0, 42.0, None, True)
    pool.assert_called_once()
    por_ficha.assert_not_called()


def test_crear_conteo_stock_de_sueltos_resta_las_cajas_de_todas_las_fichas():
    """Los sueltos salen por RESTA, no por una cuenta propia.

    Así la suma de las porciones da siempre el total del artículo: no se
    puede perder ni duplicar nada entre los renglones del Cotejo.
    """
    from app.db import crear_conteo_stock

    conexion, cursor = _conexion_falsa(filas_fetchone=[(100.0,)])
    # 20 + 5 en cajas de dos fichas de ESTE artículo, y 40 de otro que no
    # tiene que restar.
    cursor.fetchall.return_value = [(2, 11, 20.0, False), (2, 12, 5.0, False), (9, 30, 40.0, False)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_conteo_stock(2, 70.0)

    insert = cursor.execute.call_args_list[-1]
    assert insert.args[1] == (2, 70.0, 75.0, None, False)


def test_listar_conteos_stock_de_fecha_no_trae_el_stock_del_sistema():
    from app.db import listar_conteos_stock_de_fecha

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_conteos_stock_de_fecha(date(2026, 8, 25))

    consulta = cursor.execute.call_args.args[0]
    # Esta lista la ve el operario: el número del sistema no puede viajar
    # ni escondido en el HTML de su pantalla.
    assert "stock_sistema" not in consulta


def test_listar_ultimos_conteos_stock_trae_el_ultimo_por_PORCION():
    """Desde la etapa 3 el último vale por porción, no por artículo.

    Contar las cajas de una ficha a la tarde no puede invalidar el conteo
    de bultos sueltos de la mañana: son dos cosas distintas del piso.

    Y LAS PORCIONES SON TRES desde el 09/09. Este assert pedía dos claves
    —era el diseño de ayer— y por eso no podía ver el choque: la segunda y
    los sueltos tienen los dos `ficha_id` NULL, así que con
    `DISTINCT ON (articulo_id, ficha_id)` el último cargado tapa al otro.
    Medido antes de escribir esto, sobre sueltos 5 / ficha 7 / segunda 42:
    con dos claves vuelven dos filas y los 42 no están.
    """
    from app.db import listar_ultimos_conteos_stock

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("articulo_nombre",), ("ficha_id",),
                          ("ficha_nombre",), ("es_segunda",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_ultimos_conteos_stock()

    consulta = cursor.execute.call_args.args[0]
    assert "DISTINCT ON (c.articulo_id, c.ficha_id, c.es_segunda)" in consulta
    assert "c.stock_sistema" in consulta
    # El mismo orden que el índice conteos_stock_cotejo_idx, con la tercera
    # clave adentro: si el índice y el DISTINCT ON se separan, la consulta
    # sigue dando bien y deja de salir del índice.
    assert "ORDER BY c.articulo_id, c.ficha_id, c.es_segunda, c.creado_en DESC" in consulta


def test_el_INDICE_del_cotejo_tiene_LAS_MISMAS_TRES_claves_que_el_DISTINCT_ON():
    """Lee la migración, no la copia: copiada envejece en silencio.

    Si el índice se quedara con dos claves, la consulta seguiría siendo
    correcta y dejaría de salir del índice — un problema que no se ve
    mirando resultados.
    """
    import pathlib
    from app.db import listar_ultimos_conteos_stock

    migracion = pathlib.Path("db/agregar_conteo_de_segunda_2_indice.sql").read_text()
    assert "(articulo_id, ficha_id, es_segunda, creado_en desc)" in migracion

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []
    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_ultimos_conteos_stock()
    consulta = cursor.execute.call_args.args[0]
    assert "ORDER BY c.articulo_id, c.ficha_id, c.es_segunda, c.creado_en DESC" in consulta


def test_el_cotejo_ordena_los_sueltos_ANTES_que_las_fichas_y_la_SEGUNDA_AL_FINAL():
    """El mismo orden en que se recorre el depósito, y el mismo `orden`
    (0, 1, 2) que usa _porciones_de_deposito para el Remanente.

    La segunda entra con `ficha_id` None igual que los sueltos, así que
    ordenar por "tiene ficha o no" la mandaría al principio, mezclada con
    ellos: son las dos únicas porciones que comparten ese campo.
    """
    from app.db import listar_ultimos_conteos_stock

    conexion, cursor = _conexion_falsa()
    cursor.description = [("articulo_nombre",), ("ficha_id",), ("ficha_nombre",), ("es_segunda",)]
    cursor.fetchall.return_value = [
        ("Banana", None, None, True),
        ("Banana", 12, "Banana Ecuador", False),
        ("Banana", None, None, False),
        ("Banana", 11, "Banana Bolivia", False),
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        filas = listar_ultimos_conteos_stock()

    assert [(f["ficha_nombre"], f["es_segunda"]) for f in filas] == [
        (None, False), ("Banana Bolivia", False), ("Banana Ecuador", False), (None, True),
    ]


def test_contar_stock_deposito_negativo_hace_la_misma_cuenta_que_el_stock():
    from app.db import contar_stock_deposito_negativo

    conexion, cursor = _conexion_falsa(filas_fetchone=[(2,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        casos = contar_stock_deposito_negativo()

    consulta = cursor.execute.call_args.args[0]
    # La misma cuenta que stock_deposito_por_articulo, solo el conteo.
    assert "estado = 'recepcionado'" in consulta
    assert "DISTINCT ON (cliente_id, fecha_operacion)" in consulta
    assert "< 0" in consulta
    assert casos == 2


# --- Reproceso (Guías R) ---

from app.db import (  # noqa: E402
    anular_reproceso,
    contar_guias_r_afectadas_por_fecha,
    crear_reproceso,
    listar_reprocesos_por_rango,
    RepartoDesactualizado,
    ReprocesoAnteriorAlCorte,
    StockInsuficienteParaReproceso,
)

# renglon_id va al final: las salidas de armado lo traen (es lo que las ata a
# sus lotes elegidos) y los lotes no, pero la conexión falsa tiene UNA sola
# description para las dos cosas, así que la columna viaja en las dos.
COLUMNAS_LOTES = [("fecha_orden",), ("momento_orden",), ("tipo_lote",), ("origen_id",),
                  ("fecha_lote",), ("detalle",), ("motivo",), ("cantidad",), ("costo_bulto",),
                  ("cliente_lote_id",), ("articulo_id",), ("renglon_id",)]


# La fecha de corte que devuelve corte_modelo. Es la PRIMERA consulta de
# crear_reproceso —el piso de fecha— así que encabeza la cola de fetchone.
# Va antes que todas las fechas de estos tests a propósito: acá se prueba
# el FIFO, no el piso (el piso tiene los suyos).
_CORTE = (date(2026, 8, 15),)


def _lote_compra(origen_id, fecha, cantidad, costo, articulo_id=1):
    return (fecha, datetime(2026, 8, fecha.day, 10), "guia", origen_id, fecha, "Norte 15", None,
            cantidad, costo, None, articulo_id, None)


def _salida_fifo(fecha, cantidad, articulo_id=1):
    """Una salida fechada, con la forma ancha de COLUMNAS_LOTES.

    Desde E4 las salidas del FIFO de stock son las mismas del de costo y se
    leen con cursor.description, igual que los lotes: la conexión falsa tiene
    una sola description, así que la fila de salida viaja con el mismo ancho.
    Lo que el reparto mira de acá es fecha_orden, momento_orden y cantidad.
    """
    return (fecha, datetime(2026, 8, fecha.day, 12), None, None, None, None, None,
            cantidad, None, None, articulo_id, None)


def test_el_piso_de_fecha_NO_deja_cargar_una_guia_R_ANTES_del_corte():
    """Antes del corte el FIFO nuevo no rige: no hay lotes contra los que medir.

    Y no escribe NADA: revienta antes de la consulta de lotes, que es lo
    más barato de descartar.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ReprocesoAnteriorAlCorte) as levantada:
            crear_reproceso(1, 10, 8, 0, 2, date(2026, 8, 14))

    assert levantada.value.corte == date(2026, 8, 15)
    assert levantada.value.fecha == date(2026, 8, 14)
    conexion.commit.assert_not_called()
    assert not [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]


def test_el_piso_SALE_de_corte_modelo_y_no_de_una_constante():
    """El día del corte nuevo se cambia una fila y el piso la sigue solo.

    Acá el corte es el 01/09, así que el 25/08 —que en todos los otros
    tests entra— tiene que rebotar. Una constante clavada lo dejaría pasar.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 9, 1),)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ReprocesoAnteriorAlCorte) as levantada:
            crear_reproceso(1, 10, 8, 0, 2, date(2026, 8, 25))

    assert levantada.value.corte == date(2026, 9, 1)


def test_con_ficha_VARIABLE_la_guia_R_ENTRA_y_escribe_EL_ENVASE_DE_LA_FICHA():
    """ESTE TEST AFIRMABA LO CONTRARIO entre el 17 y el 18/09.

    Decía que con ficha variable la guía NO SE GUARDABA hasta que alguien
    contestara en qué caja quedó armada, y era el guardián de un selector que
    dejaba elegir una caja DISTINTA de la que la ficha declara. La caja sale
    de la ficha y no se puede armar en otra.

    Lo que el flag decide es SI se usa una caja nuestra, no CUÁL — y en una
    guía R ese "si" ya está contestado por el hecho de que la guía exista:
    anota `bultos_primera`, o sea cajas ARMADAS. El caso descartable es
    exactamente aquel en que no se reprocesa nada y no hay guía R.

    El envase se afirma POR EL NÚMERO (9, el de la ficha) y no por `True`: un
    assert de que "lleva caja" pasaría igual con el envase en NULL, que es el
    hueco que el stock de cajas cuenta aparte.
    """
    # La ficha existe, tiene envase 9, y es VARIABLE. El SELECT pide UNA
    # columna: la regla ya no mira el flag.
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (9,), (32,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 15), 20.0, 1000.0)],
        [],
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(1, 10, 8, 0, 2, date(2026, 8, 25), cliente_id=1, ficha_id=901)

    assert numero == 32
    insert = next(c for c in cursor.execute.call_args_list
                  if "INSERT INTO reprocesos" in c.args[0])
    assert insert.args[1][-2:] == (True, 9), (
        f"tenía que escribir la caja de la ficha; escribió {insert.args[1][-2:]}"
    )


def test_la_regla_de_la_caja_NO_LE_PIDE_A_LA_BASE_el_flag_variable():
    """Y se afirma sobre el TEXTO del SELECT, no sobre el valor.

    Con el mock, la fila la entrega el fixture: lo único que ve QUÉ columna
    pidió la consulta es el SQL. Y acá el modo de falla es mudo — pidiendo
    `envase_variable` de más no se rompe nada hoy, y queda una lectura que
    invita a volver a ramificar por el flag.
    """
    fuente = io.open("app/db.py", encoding="utf-8").read()
    cuerpo = fuente.split("def _envase_de_esta_guia")[1].split("\ndef ")[0]
    assert "envase_variable" not in cuerpo, (
        "la caja sale de la ficha: el flag no entra en esta lectura"
    )


def test_una_ficha_de_envase_FIJO_no_pregunta_NADA_y_lo_deriva_sola():
    """EL CONTROL, y es lo que impide que el arreglo trabe todo el galpón.

    La inmensa mayoría de las fichas tienen envase fijo: ahí el server sabe
    la respuesta y preguntar sería pedir dos veces el mismo dato. Sin este
    test, una guarda que exija SIEMPRE pasa los dos de arriba y rompe la
    pantalla para todos los demás artículos.
    """
    # Ficha con envase 7. El SELECT pide una sola columna.
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (7,), (32,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 15), 20.0, 1000.0)],
        [],
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(1, 10, 8, 0, 2, date(2026, 8, 25), cliente_id=1, ficha_id=901)

    assert numero == 32
    insert = next(c for c in cursor.execute.call_args_list
                  if "INSERT INTO reprocesos" in c.args[0])
    assert True in insert.args[1] and 7 in insert.args[1]


def test_el_dia_DEL_corte_si_se_puede_cargar():
    """El corte es el primer día del modelo nuevo, no el último del viejo.

    El stock inicial se carga con esa misma fecha, así que un reproceso de
    ese día tiene lotes contra los que medirse.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (30,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 15), 20.0, 1000.0)],
        [],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(1, 10, 8, 0, 2, date(2026, 8, 15))

    assert numero == 30


def test_contar_guias_r_afectadas_mira_de_la_fecha_INCLUSIVE_hacia_adelante():
    """`>=` y no `>`: el recorte del reproceso toma las entradas HASTA LA
    FECHA INCLUSIVE, así que una guía R del mismo día también se repartiría
    contra el lote nuevo. Y solo las 'normal': la inicial produce sin
    consumir y no tiene reparto que se le desactualice."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[(3,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert contar_guias_r_afectadas_por_fecha(7, date(2026, 8, 31)) == 3

    consulta, parametros = cursor.execute.call_args.args
    assert "fecha_operacion >= %s" in consulta
    assert "anulado_el IS NULL" in consulta
    assert "tipo = 'normal'" in consulta
    assert parametros == (7, date(2026, 8, 31))


def test_crear_reproceso_congela_consumos_fifo_y_todo_el_costo_a_la_primera():
    # Lotes: compra 101 (8 bultos a $1000, viejo) y 102 (10 a $1200). Ya
    # salieron 5 → restos 3 y 10. Tomo 6: 3 del 101 y 3 del 102 (FIFO).
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (12,)])
    cursor.description = COLUMNAS_LOTES
    # Las dos tandas de fetchall: lotes y salidas fechadas.
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 8, 20), 8.0, 1000.0),
            _lote_compra(102, date(2026, 8, 22), 10.0, 1200.0),
        ],
        [_salida_fifo(date(2026, 8, 24), 5.0)],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(1, 6, 4, 1, 1, date(2026, 8, 25), cliente_id=7)

    assert numero == 12
    inserts = [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    # Cabecera: costo_total = 3×1000 + 3×1200 = 6600, TODO a la primera:
    # 6600 / 4 cajas = 1650. Segunda y merma no llevan nada. El cliente
    # queda como DATO de la guía (para quién se armó la primera).
    assert "INSERT INTO reprocesos" in inserts[0].args[0]
    # El último es la FICHA a la que fueron las cajas de primera: None acá
    # significa SIN ASIGNAR, que en la pantalla se elige a propósito.
    # El False del final es consumos_editados: el operario no tocó el
    # desglose, así que va la propuesta FIFO tal cual.
    # La estructura ENTERA, no tres campos de doce: que caiga el día que
    # alguien agrega una columna es la función del test. Las dos últimas son
    # `tipo` y la compra que originó la guía — 'normal' y None acá, porque
    # ésta es un armado del galpón como cualquier otro.
    # Las dos últimas son EN QUÉ CAJA se armó la primera. Acá van en None las
    # dos porque la guía quedó SIN FICHA: sin ficha no hay de dónde derivar el
    # envase, y eso NO es "no llevó caja nuestra" —que sería `False`— sino
    # "no sabemos", que el stock de cajas cuenta aparte como hueco.
    assert inserts[0].args[1] == (
        1, date(2026, 8, 25), 6, 4, 1, 1, 6600.0, 1650.0, 7, None, False, "normal", None,
        None, None,
    )
    # Consumos congelados, del lote más viejo primero, con su costo.
    assert inserts[1].args[1] == (12, "compra", 101, 101, 3.0, 1000.0)
    assert inserts[2].args[1] == (12, "compra", 102, 102, 3.0, 1200.0)
    # El reproceso JAMÁS toca compras: su costo no puede llegar a la cotización.
    assert all("compras" not in c.args[0].split("FROM")[0] for c in inserts)
    conexion.commit.assert_called_once()


def test_crear_reproceso_con_lote_sin_precio_deja_el_costo_incompleto():
    # Un lote sin importe (compra de la mañana sin precio, o stock
    # inicial): NO se promedia con números inventados — costo NULL.
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (13,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 8, 20), 8.0, 1000.0),
            _lote_compra(102, date(2026, 8, 22), 10.0, None),
        ],
        [],  # sin salidas
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_reproceso(1, 10, 8, 0, 0, date(2026, 8, 25))

    inserts = [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    assert inserts[0].args[1][6] is None
    assert inserts[0].args[1][7] is None
    assert inserts[2].args[1][5] is None


def test_el_freno_traba_lo_que_los_lotes_no_cubren_y_NO_escribe_nada():
    """Lo que ANTES quedaba como consumo sin_lote. El reproceso es 100% o nada.

    El sin_lote del reproceso congelaba un costo incompleto PARA SIEMPRE: no
    hay compra a la que irle a buscar el importe, porque esos bultos no
    existieron. Por eso acá —y solo acá— el depósito sí se traba.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (14,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 20), 3.0, 1000.0)],
        [],  # sin salidas
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(StockInsuficienteParaReproceso) as levantada:
            crear_reproceso(1, 5, 4, 0, 1, date(2026, 8, 25))

    # La excepción trae lo que la pantalla necesita para explicarlo sola.
    assert levantada.value.declarado == 5.0
    assert levantada.value.disponible == 3.0
    assert [lote["origen_id"] for lote in levantada.value.lotes] == [101]
    # Y NO se escribió nada: ni la guía, ni un consumo, ni un commit.
    assert not [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    conexion.commit.assert_not_called()


def test_el_freno_compara_contra_los_RESTANTES_no_contra_el_neto():
    """Decidido el 01/09. El neto puede venir negativo de antes; los restantes no.

    Lote de 10 el 20/08 y una salida de 25 el 22/08: el neto es −15, pero
    los restantes suman 0. Lo que se prueba es que el número contra el que
    compara el freno NUNCA es negativo — si mirara el neto, pedir 4 sería
    "faltan 19" y el mensaje hablaría de un agujero que no es de esta guía.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (15,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 20), 10.0, 1000.0)],
        [_salida_fifo(date(2026, 8, 22), 25.0)],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(StockInsuficienteParaReproceso) as levantada:
            crear_reproceso(1, 4, 4, 0, 0, date(2026, 8, 25))

    assert levantada.value.disponible == 0.0


def test_el_freno_NO_cuenta_las_salidas_DEL_MISMO_DIA():
    """El caso real del 31/08: el depósito arma las cajas y carga la guía R después.

    Lote de 44 el 30/08 y una salida de 44 el 31/08. Si las salidas del
    mismo día contaran, el disponible sería 0 y el operario quedaría trabado
    justo cuando está cargando lo que explica esa salida. Dentro de un día
    el sistema no tiene orden: guarda fechas, no horas.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (16,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 30), 44.0, 1000.0)],
        [_salida_fifo(date(2026, 8, 31), 44.0)],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(1, 44, 40, 0, 4, date(2026, 8, 31))

    assert numero == 16
    inserts = [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    assert inserts[1].args[1] == (16, "compra", 101, 101, 44.0, 1000.0)



# EL AGUJERO DEL MISMO DÍA, cerrado el 16/09. El recorte de arriba está bien
# y contesta "¿qué lotes había ese día?". El freno pregunta otra cosa —"¿cuánto
# se llevó ya el día?"— y ésa no necesita saber el orden: 30 y 26 no entran en
# 40 se haya cargado primero cualquiera de las dos. Sin esto, cada guía R del
# día veía el lote ENTERO y de uno de 40 salieron 56.
def _consumo_de_hoy(numero, origen_id, bultos, origen="compra"):
    """Una fila de `_lo_tomado_hoy`: lo que una guía R de HOY ya se llevó de un lote."""
    return (numero, origen, origen_id, bultos)


def test_EL_CASO_DE_LOS_56_DE_UN_LOTE_DE_40_lo_que_el_dia_ya_tomo_se_descuenta():
    """R300 tomó 30 de un lote de 40 hoy; R307 pide 26 el mismo día.

    Es el caso real del 14/09, medido: 56 bultos salieron de un lote de 40.
    Las dos pasaban porque el recorte del mismo día le mostraba a cada una
    el lote entero.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (307,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 9, 13), 40.0, 1000.0)],
        [],
        [_consumo_de_hoy(300, 101, 30.0)],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(StockInsuficienteParaReproceso) as levantada:
            crear_reproceso(1, 26, 24, 0, 2, date(2026, 9, 14))

    assert levantada.value.disponible == 10.0
    # Y la pared no es muda: dice QUÉ guía de hoy se lo llevó. Sin esto, el
    # operario lee "no alcanza" contra los cajones que tiene delante.
    assert levantada.value.tomado_hoy == [
        {"reproceso_id": 300, "origen": "compra", "origen_id": 101, "bultos": 30.0}
    ]
    assert not [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]


def test_EL_CONTROL_del_caso_de_los_56_sin_nada_tomado_hoy_la_MISMA_carga_entra():
    """El mismo pedido, con el día limpio: 26 de un lote de 40 entra.

    Es el canario del test de arriba puesto como test: lo único que cambia
    entre los dos es lo que otra guía R se llevó hoy. Sin este, un freno que
    trabara siempre pasaría igual el de arriba (corolario 30 — la batería de
    casos negativos no distingue una guarda que anda de una que frena
    siempre).
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (307,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 9, 13), 40.0, 1000.0)],
        [],
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(1, 26, 24, 0, 2, date(2026, 9, 14))

    assert numero == 307


def test_lo_que_TODAVIA_ENTRA_despues_de_lo_de_hoy_no_rebota():
    """R300 tomó 30 de 40 y la segunda pide 10: la suma entra justo y pasa.

    El rebote se limita a donde la suma ya no entra. Una guía que pide lo
    que queda no puede encontrarse con una pared que antes no estaba.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (308,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 9, 13), 40.0, 1000.0)],
        [],
        [_consumo_de_hoy(300, 101, 30.0)],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(1, 10, 9, 0, 1, date(2026, 9, 14))

    assert numero == 308


def test_EL_REPARTO_NO_CAMBIA_la_propuesta_sale_de_los_lotes_ENTEROS():
    """El freno cuenta el mismo día; el desglose que ve el operario, no.

    Dos lotes: el 101 (viejo, 40) con 35 ya tomados hoy, y el 102 (100). La
    guía pide 10. Con el reparto descontado, la propuesta sería 5 del 101 y
    5 del 102; con el reparto entero —que es lo que se decidió— son 10 del
    101. El fixture tiene el RIVAL puesto a propósito: con un solo lote las
    dos versiones dan lo mismo y el test no distingue nada.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (309,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 9, 13), 40.0, 1000.0),
            _lote_compra(102, date(2026, 9, 13), 100.0, 1200.0),
        ],
        [],
        [_consumo_de_hoy(300, 101, 35.0)],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_reproceso(1, 10, 10, 0, 0, date(2026, 9, 14))

    consumos = [c.args[1] for c in cursor.execute.call_args_list
                if "INSERT INTO reprocesos_consumos" in c.args[0]]
    assert consumos == [(309, "compra", 101, 101, 10.0, 1000.0)]


def test_un_lote_YA_SOBRE_ATRIBUIDO_aporta_CERO_y_no_se_come_a_los_otros():
    """El piso en cero, y es la promesa de `bultos_en_los_lotes`.

    El 101 tiene 40 y hoy ya se llevaron 56 de él —uno de los 56 lotes
    medidos—. Ese agujero ya estaba ahí antes de que este operario tocara
    nada: tiene que aportar cero, no restarle 16 al lote de al lado. Si
    restara, esta carga de 20 contra un lote intacto de 20 rebotaría por un
    problema ajeno.

    De acá sale, además, que la guía R de una compra que llega armada no
    pueda rebotar nunca: su propia compra entra como lote intacto.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (310,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 9, 13), 40.0, 1000.0),
            _lote_compra(102, date(2026, 9, 13), 20.0, 1200.0),
        ],
        [],
        [_consumo_de_hoy(300, 101, 56.0)],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(
            1, 20, 20, 0, 0, date(2026, 9, 14),
            reparto=[{"tipo_lote": "guia", "origen_id": 102, "bultos": 20.0}],
        )

    assert numero == 310


def test_lo_tomado_hoy_sale_de_las_GUIAS_R_VIVAS_del_mismo_dia_y_de_nada_mas():
    """Tres recortes, y cada uno tiene su razón. Se miran en el TEXTO.

    - Guías R y no armados: un armado que deja una ficha en negativo es
      comportamiento deliberado del sistema, así que contarlo rebotaría
      cargas por un motivo que el sistema permite.
    - `anulado_el IS NULL`: una guía anulada devolvió lo que tomó.
    - Mismo artículo y misma FECHA: es de lo único que se trata.
    """
    import ast

    # El SQL se saca del ÁRBOL y no del texto de la función: su docstring
    # nombra las tablas para explicar por qué NO están, así que un `in`
    # sobre el fuente matchearía la prosa escrita para excluirlas
    # (corolario 59). Y las tablas se piden en POSICIÓN de tabla por lo
    # mismo.
    arbol = ast.parse(inspect.getsource(db._lo_tomado_hoy).lstrip())
    consulta = next(
        nodo.value for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
        and "SELECT" in nodo.value
    )
    assert "FROM reprocesos_consumos rc" in consulta
    assert "JOIN reprocesos r ON r.id = rc.reproceso_id" in consulta
    assert "r.articulo_id = %s AND r.fecha_operacion = %s" in consulta
    assert "r.anulado_el IS NULL" in consulta
    assert "FROM pedidos_renglones" not in consulta and "JOIN pedidos_renglones" not in consulta
    assert "FROM movimientos_stock" not in consulta and "JOIN movimientos_stock" not in consulta


def test_un_lote_POSTERIOR_a_la_fecha_del_reproceso_no_cuenta():
    """La otra punta del recorte: entradas hasta la fecha INCLUSIVE.

    Tomó 8 el 20/08. El lote de 10 llegó el 22/08, dos días después: no
    puede cubrir un reproceso que ya había pasado.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (17,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(102, date(2026, 8, 22), 10.0, 1200.0)],
        [],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(StockInsuficienteParaReproceso) as levantada:
            crear_reproceso(1, 8, 8, 0, 0, date(2026, 8, 20))

    assert levantada.value.disponible == 0.0


def test_el_reparto_editado_por_el_operario_se_escribe_y_queda_MARCADO():
    """La edición del desglose: dentro de lo que hay de cada lote.

    Dos lotes con 8 y 10. El FIFO propondría 8 del viejo y 2 del nuevo; el
    operario dice que sacó 3 del viejo y 7 del nuevo, y eso es lo que se
    congela —con el costo de los lotes que ÉL eligió— y queda marcado con
    consumos_editados, que es lo que después deja saber que ese reparto no
    lo eligió el sistema.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (18,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 8, 20), 8.0, 1000.0),
            _lote_compra(102, date(2026, 8, 22), 10.0, 1200.0),
        ],
        [],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]
    reparto = [
        {"tipo_lote": "guia", "origen_id": 101, "bultos": 3.0},
        {"tipo_lote": "guia", "origen_id": 102, "bultos": 7.0},
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_reproceso(1, 10, 9, 0, 1, date(2026, 8, 25), reparto=reparto)

    inserts = [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    # POR NOMBRE y no `[-1]`: la última columna dejó de ser ésta el día que
    # el INSERT ganó `tipo` y `compra_origen_id`, y un test que indexa desde
    # el final pasa a mirar otra cosa sin decirlo.
    assert _valor_insertado(cursor, "consumos_editados", "INSERT INTO reprocesos\n") is True
    assert inserts[1].args[1] == (18, "compra", 101, 101, 3.0, 1000.0)
    assert inserts[2].args[1] == (18, "compra", 102, 102, 7.0, 1200.0)
    # 3×1000 + 7×1200 = 11400, y no los 9800 del FIFO.
    assert inserts[0].args[1][6] == 11400.0


def test_confirmar_el_desglose_sin_tocarlo_NO_lo_marca_como_editado():
    """La edición es opcional: mandar la misma propuesta no es haberla cambiado."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (19,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 8, 20), 8.0, 1000.0),
            _lote_compra(102, date(2026, 8, 22), 10.0, 1200.0),
        ],
        [],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]
    igual_al_fifo = [
        {"tipo_lote": "guia", "origen_id": 101, "bultos": 8.0},
        {"tipo_lote": "guia", "origen_id": 102, "bultos": 2.0},
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_reproceso(1, 10, 9, 0, 1, date(2026, 8, 25), reparto=igual_al_fifo)

    inserts = [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    assert _valor_insertado(cursor, "consumos_editados", "INSERT INTO reprocesos\n") is False


def test_un_reparto_que_pide_mas_de_lo_que_hay_en_un_lote_no_se_guarda():
    """Se revalida SIEMPRE en el server: entre el desglose y el Guardar el stock se mueve."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (20,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 8, 20), 8.0, 1000.0),
            _lote_compra(102, date(2026, 8, 22), 10.0, 1200.0),
        ],
        [],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]
    reparto = [
        {"tipo_lote": "guia", "origen_id": 101, "bultos": 9.0},  # quedaban 8
        {"tipo_lote": "guia", "origen_id": 102, "bultos": 1.0},
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(RepartoDesactualizado):
            crear_reproceso(1, 10, 9, 0, 1, date(2026, 8, 25), reparto=reparto)

    assert not [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    conexion.commit.assert_not_called()


def test_un_reparto_que_no_suma_lo_declarado_no_se_guarda():
    """Si lo repartido no da los bultos que declaró, no hay guía: la diferencia
    no puede caer en ningún lado —no existe el sin_lote— así que se frena."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE, (21,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 20), 8.0, 1000.0)],
        [],
        # Lo que YA se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(RepartoDesactualizado):
            crear_reproceso(1, 5, 4, 0, 1, date(2026, 8, 25),
                            reparto=[{"tipo_lote": "guia", "origen_id": 101, "bultos": 4.0}])

    assert not [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]


def test_anular_reproceso_es_baja_logica():
    conexion, cursor = _conexion_falsa(filas_fetchone=[_CORTE])

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_reproceso(12)

    consulta = cursor.execute.call_args.args[0]
    assert "UPDATE reprocesos SET anulado_el = now()" in consulta
    assert "anulado_el IS NULL" in consulta
    conexion.commit.assert_called_once()


def test_listar_reprocesos_trae_las_guias_con_sus_consumos():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("articulo_nombre",)]
    cursor.fetchall.side_effect = [[], []]

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert listar_reprocesos_por_rango(date(2026, 8, 18), date(2026, 8, 25)) == []

    consulta = cursor.execute.call_args.args[0]
    # Anuladas incluidas (marcadas): el listado no las esconde.
    assert "anulado_el IS NULL" not in consulta


def test_la_cotizacion_no_lee_el_costo_del_reproceso():
    # La garantía es estructural: el costeo (la cotización de la mañana)
    # reconstruye el costo SOLO desde compras — si alguna vez alguien le
    # mete el costo del reproceso, este test lo frena.
    import pathlib

    fuente = pathlib.Path("app/costeo.py").read_text()
    assert "reproceso" not in fuente.lower()
    assert "remitos_segunda" not in fuente.lower()


def test_completar_costo_solo_rellena_los_null_y_recalcula_si_quedo_completo():
    from app.db import completar_costo_reproceso

    conexion, cursor = _conexion_falsa(filas_fetchone=[(0, 16500.0)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = completar_costo_reproceso(12)

    llamadas = [c.args[0] for c in cursor.execute.call_args_list]
    # SOLO los consumos sin costo, y solo con compras que YA tienen precio:
    # jamás pisa un costo congelado.
    assert "rc.costo_por_bulto IS NULL AND c.importe IS NOT NULL" in llamadas[0]
    # Quedó completo: recalcula y graba el total y el por-caja (guardado
    # con WHERE costo_total IS NULL: tampoco pisa una guía ya cerrada).
    assert "WHERE id = %s AND costo_total IS NULL" in llamadas[2]
    assert resultado == {"completado": True, "sin_precio": 0}
    conexion.commit.assert_called_once()


def test_completar_costo_sigue_incompleto_si_hay_consumos_sin_precio_posible():
    from app.db import completar_costo_reproceso

    conexion, cursor = _conexion_falsa(filas_fetchone=[(2, 5000.0)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = completar_costo_reproceso(13)

    # Con consumos sin precio posible (stock inicial, reingreso, sin lote)
    # NO se graba ningún total: mejor incompleto visible que un invento.
    assert len(cursor.execute.call_args_list) == 2
    assert resultado == {"completado": False, "sin_precio": 2}


def test_contar_reprocesos_costo_incompleto_solo_vigentes():
    from app.db import contar_reprocesos_costo_incompleto

    conexion, cursor = _conexion_falsa(filas_fetchone=[(1, date(2026, 8, 25))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_reprocesos_costo_incompleto()

    consulta = cursor.execute.call_args.args[0]
    assert "anulado_el IS NULL AND costo_total IS NULL" in consulta
    assert resultado == {"casos": 1, "mas_viejo": date(2026, 8, 25)}


def test_la_alerta_cuenta_SOLO_las_que_esperan_el_precio_de_una_compra():
    """Una guía que consumió un lote sin precio POSIBLE no es una alerta.

    Nadie la puede cerrar: el número no bajaría nunca y eso enseña a
    ignorar el resto de las alertas.
    """
    from app.db import contar_reprocesos_costo_incompleto

    conexion, cursor = _conexion_falsa(filas_fetchone=[(1, date(2026, 8, 25))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_reprocesos_costo_incompleto()

    consulta = " ".join(cursor.execute.call_args.args[0].split())
    assert "NOT EXISTS" in consulta
    assert "rc.costo_por_bulto IS NULL AND rc.origen <> 'compra'" in consulta


def test_las_dos_consultas_del_costo_parten_por_LA_MISMA_condicion():
    """Una sola regla ("¿puede llegar el precio?"), escrita una sola vez.

    Si se escribiera dos veces, un día una diría "ajuste" y la otra no, y
    una guía quedaría contada en las dos —o en ninguna— sin que nadie lo
    note. Es la regla de la casa: el criterio va en una constante.
    """
    from app.db import (
        _SQL_FALTA_UN_PRECIO_IMPOSIBLE,
        contar_reprocesos_costo_incompleto,
        contar_reprocesos_sin_costo_posible,
    )

    consultas = []
    for funcion in (contar_reprocesos_costo_incompleto, contar_reprocesos_sin_costo_posible):
        conexion, cursor = _conexion_falsa(filas_fetchone=[(0, None)])
        with patch("app.db.obtener_conexion", return_value=conexion):
            funcion()
        consultas.append(" ".join(cursor.execute.call_args.args[0].split()))

    condicion = " ".join(_SQL_FALTA_UN_PRECIO_IMPOSIBLE.split())
    alerta, imposibles = consultas
    # La misma condición en las dos, negada en una sola: eso es la partición.
    assert condicion in alerta and condicion in imposibles
    assert f"NOT {condicion}" in alerta
    assert f"NOT {condicion}" not in imposibles
    # Y las dos miran el mismo universo.
    for consulta in consultas:
        assert "anulado_el IS NULL AND costo_total IS NULL" in consulta


def test_la_alerta_exige_que_HAYA_algo_que_completar():
    """El `NOT EXISTS` solo era demasiado generoso: una guía sin costo y SIN
    NINGÚN consumo sin precio lo cumple por vacío, y entraba a la alerta sin
    tener nada que cargar. La condición tiene que ser la misma que la de la
    pantalla, que exige `bool(faltantes)`.
    """
    from app.db import _SQL_FALTA_ALGUN_PRECIO, contar_reprocesos_costo_incompleto

    conexion, cursor = _conexion_falsa(filas_fetchone=[(0, None)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_reprocesos_costo_incompleto()

    consulta = " ".join(cursor.execute.call_args.args[0].split())
    condicion = " ".join(_SQL_FALTA_ALGUN_PRECIO.split())
    assert condicion in consulta
    assert f"NOT {condicion}" not in consulta


def test_contar_reprocesos_sin_costo_posible_solo_vigentes():
    from app.db import contar_reprocesos_sin_costo_posible

    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, date(2026, 8, 31))])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_reprocesos_sin_costo_posible()

    consulta = cursor.execute.call_args.args[0]
    assert "anulado_el IS NULL AND costo_total IS NULL" in consulta
    assert resultado == {"casos": 7, "mas_viejo": date(2026, 8, 31)}


def test_anular_remito_segunda_es_baja_logica():
    from app.db import anular_remito_segunda

    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_remito_segunda(7)

    consulta = cursor.execute.call_args.args[0]
    assert "UPDATE remitos_segunda SET anulado_el = now()" in consulta
    assert "anulado_el IS NULL" in consulta


def test_articulos_con_salidas_stock_junta_armados_MERMAS_PASES_y_reprocesos():
    from app.db import articulos_con_salidas_stock

    conexion, cursor = _conexion_falsa()
    cursor.description = [("articulo_id",), ("nombre",), ("grupo",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        articulos_con_salidas_stock(1, date(2026, 8, 18), date(2026, 8, 25))

    consulta = cursor.execute.call_args.args[0]
    # Armados del cliente en el rango (pedidos vigentes) + mermas, PASES y
    # reprocesos del depósito (no son de un cliente: entran igual).
    assert "DISTINCT ON (cliente_id, fecha_operacion)" in consulta
    assert "v.cliente_id = %s" in consulta
    assert "tipo IN ('merma', 'pase_a_segunda')" in consulta
    assert "FROM reprocesos" in consulta

    # Y LA FORMA VIEJA NO PUEDE ESTAR. Hasta el 22/09 esto decía
    # `tipo = 'merma'` y ERA EL GUARDIÁN DEL AGUJERO: una berenjena que solo
    # se pasó a segunda no llegaba a la pantalla, y este assert lo defendía.
    # Preguntar solo por el texto nuevo pasa igual si el viejo quedó en otra
    # rama del UNION — es el conjunto ENCONTRADO contra el DECIDIDO aplicado
    # a una condición.
    assert "tipo = 'merma'" not in consulta


def test_salidas_stock_articulo_trae_cada_salida_tipada_de_toda_la_historia():
    from app.db import salidas_stock_articulo

    conexion, cursor = _conexion_falsa()
    cursor.description = [("fecha_orden",), ("tipo",), ("articulo_id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        salidas_stock_articulo(2)

    consulta = cursor.execute.call_args.args[0]
    # SIN filtro de fechas: la atribución FIFO necesita el pasado entero.
    assert "fecha_operacion >= " not in consulta.replace("v.fecha_operacion AS", "")
    # El armado ancla el precio a la fecha del PEDIDO y trae los kilos
    # enviados y el cliente; mermas/ajustes y tomas de reproceso, tipados.
    assert "'armado' AS tipo" in consulta
    assert "r.kilos_enviados AS unidades" in consulta
    assert "v.cliente_id AS cliente_id" in consulta
    assert "m.cantidad < 0" in consulta
    assert "'reproceso_toma'" in consulta
    assert "rp.bultos_segunda" in consulta
    # Ordena por artículo y después por el orden FIFO de siempre: la consulta
    # trae varios artículos de una y cada uno conserva su secuencia.
    assert "ORDER BY articulo_id, fecha_orden, momento_orden" in consulta


def test_salidas_de_varios_articulos_devuelve_una_lista_por_cada_id_pedido():
    # El que no tuvo ninguna salida sale con lista vacía, nunca ausente:
    # un artículo que falta del diccionario rompe a quien lo lee.
    from app.db import salidas_stock_articulos

    # El primer fetchone es el corte: desde el piso asimétrico, las salidas lo
    # leen para dejar afuera el día del corte y todo lo anterior.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 9, 5),)])
    # Las columnas son las que devuelve la consulta de verdad: momento_orden
    # va porque desde E4 la salida viaja con su "orden" armado acá, en un solo
    # lugar, y no en cada pantalla que la consume.
    # renglon_id va porque cada salida de armado tiene que poder encontrar los
    # lotes que el que armó eligió para ella.
    cursor.description = [("fecha_orden",), ("momento_orden",), ("tipo",), ("renglon_id",),
                          ("articulo_id",)]
    cursor.fetchall.side_effect = [
        [(date(2026, 8, 21), "10:00", "armado", 55, 2)],
        [],  # ese renglón no tiene lotes elegidos: se reparte como siempre
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        salidas = salidas_stock_articulos([2, 7])

    assert sorted(salidas) == [2, 7]
    assert salidas[2] == [{
        "fecha_orden": date(2026, 8, 21), "momento_orden": "10:00", "tipo": "armado",
        "renglon_id": 55, "orden": (date(2026, 8, 21), "10:00"),
    }]
    # Sin corrección no hay clave: el default del FIFO no se guarda nunca.
    assert "lotes_elegidos" not in salidas[2][0]
    assert salidas[7] == []
    # TRES consultas para los dos artículos y todos sus renglones —el corte,
    # las salidas y los lotes elegidos—, sin abrir una conexión por artículo
    # ni pedir las correcciones renglón por renglón.
    assert cursor.execute.call_count == 3
    # Los ids van tres veces (una por pata) y el corte otras tres: el piso de
    # las salidas es ESTRICTO en las tres.
    corte = date(2026, 9, 5)
    assert _consulta_con(cursor, "'reproceso_toma'")
    parametros = [c.args[1] for c in cursor.execute.call_args_list if len(c.args) > 1]
    assert parametros[0] == ([2, 7], corte, [2, 7], corte, [2, 7], corte)
    # Y la de los lotes elegidos pide TODOS los renglones de una.
    assert parametros[1] == ([55],)


def test_la_funcion_de_a_uno_es_la_de_varios_con_un_solo_id():
    """La de a un artículo NO puede tener SQL propio: es la de varios con una lista de uno.

    Es la garantía de que no vuelvan a desincronizarse dos consultas que
    deberían decir lo mismo — el problema que ya tuvimos con las dos
    funciones de compras sin precio, que daban el mismo número contando
    compras distintas.
    """
    import inspect

    for envoltorio, batch in [
        (db.entradas_y_salidas_stock_articulo, "entradas_y_salidas_stock_articulos"),
        (db.salidas_stock_articulo, "salidas_stock_articulos"),
    ]:
        fuente = inspect.getsource(envoltorio)
        assert "SELECT" not in fuente, f"{envoltorio.__name__} volvió a tener consulta propia"
        assert f"{batch}([articulo_id])" in fuente

    # Lo mismo con las tres consultas de "vigente a una fecha": la de a una
    # fecha no puede resolver el vigente por su cuenta, porque entonces
    # podría resolverlo distinto que la de varias y nadie se enteraría.
    for envoltorio, batch in [
        (db.listar_precios_vigentes_por_cliente, "listar_precios_vigentes_por_cliente_en_fechas"),
        (db.listar_costos_envases_vigentes, "listar_costos_envases_vigentes_en_fechas"),
        (db.listar_conceptos_vigentes_por_cliente, "listar_conceptos_vigentes_por_cliente_en_fechas"),
    ]:
        fuente = inspect.getsource(envoltorio)
        assert "SELECT" not in fuente, f"{envoltorio.__name__} volvió a tener consulta propia"
        assert f"{batch}(" in fuente

    # Y el listado de negociación, que es el que estaba en el bucle por fecha.
    import app.costeo as costeo

    fuente = inspect.getsource(costeo.calcular_listado_para_negociar_precios)
    assert "listar_" not in fuente, "el listado de a una fecha volvió a pedirle datos a la base"
    assert "calcular_listados_para_negociar_precios(cliente_id, [momento_referencia])" in fuente


def test_los_insert_de_compras_ya_no_nombran_la_columna_foto_ruta():
    # La columna compras.foto_ruta se borra con drop_foto_ruta_compras.sql:
    # si algún INSERT volviera a nombrarla, la carga de compras rompería
    # en cuanto la columna no exista. Este test lo frena antes.
    import inspect
    import app.db as db

    fuente = inspect.getsource(db)
    # \b DESPUES DE compras, y no la subcadena suelta: desde que existe
    # `INSERT INTO compras_eliminadas`, un split por el texto pelado matchea
    # al vecino y arrastra hasta el VALUES de OTRO insert (corolario 4).
    # Entre "s" y "_" no hay frontera de palabra, asi que \b lo descarta solo.
    for fragmento in re.split(r"INSERT INTO compras\b", fuente)[1:]:
        columnas = fragmento.split("VALUES")[0]
        assert "foto_ruta" not in columnas
    assert "UPDATE compras SET foto_ruta" not in fuente


def test_registrar_revision_automatica_sella_las_dos_columnas():
    from app.db import registrar_revision_casilla

    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        registrar_revision_casilla(3, automatica=True)

    consulta = cursor.execute.call_args.args[0]
    assert "ultima_revision_el = now(), ultima_revision_automatica_el = now()" in consulta

    # El manual (default) NO toca la automática: es lo que mira la alerta.
    conexion2, cursor2 = _conexion_falsa()
    with patch("app.db.obtener_conexion", return_value=conexion2):
        registrar_revision_casilla(3)
    assert "ultima_revision_automatica_el" not in cursor2.execute.call_args.args[0]


def test_registrar_tick_revision_es_un_upsert_de_una_fila():
    from app.db import registrar_tick_revision

    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        registrar_tick_revision()

    consulta = cursor.execute.call_args.args[0]
    assert "INSERT INTO revision_tick" in consulta
    assert "ON CONFLICT (id) DO UPDATE" in consulta
    conexion.commit.assert_called_once()


def test_listar_pedidos_para_reingreso_solo_vigentes_con_armados_y_busca_por_oc():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("pedido_id",), ("fecha_operacion",), ("cliente_nombre",),
                          ("sucursal",), ("orden_compra",), ("renglones_armados",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_pedidos_para_reingreso(oc="1257673", limite=10)

    consulta = cursor.execute.call_args.args[0]
    # Solo pedidos VIGENTES (el último no anulado por cliente y fecha) y
    # solo renglones ARMADOS identificados: el reingreso se cuelga del stock real.
    assert "DISTINCT ON (cliente_id, fecha_operacion)" in consulta
    assert "r.armado_el IS NOT NULL AND r.anulado_el IS NULL" in consulta
    assert "ps.orden_compra = %s" in consulta
    assert cursor.execute.call_args.args[1] == ("1257673", 10)


def test_obtener_renglon_para_reingreso_trae_todo_y_el_devuelto_acumulado():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("pedido_id",), ("sucursal",), ("articulo_id",),
                          ("articulo_nombre",), ("cliente_id",), ("cliente_nombre",),
                          ("fecha_pedido",), ("orden_compra",), ("bultos_armados",),
                          ("kilos_enviados",), ("ya_devuelto",)]
    cursor.fetchone.return_value = (77, 40, "VL", 2, "Anco", 1, "Día",
                                    date(2026, 8, 24), "1257673", 25.0, 500.0, 5.0)

    with patch("app.db.obtener_conexion", return_value=conexion):
        renglon = obtener_renglon_para_reingreso(77)

    consulta = cursor.execute.call_args.args[0]
    # El acumulado ya devuelto sale de los reingresos NO anulados del
    # renglón (el tope del server), y el armado usa la cantidad real.
    assert "pedido_renglon_id IS NOT NULL AND anulado_el IS NULL" in consulta
    assert "COALESCE(r.cantidad_armada, r.cantidad)" in consulta
    assert "DISTINCT ON (cliente_id, fecha_operacion)" in consulta
    assert renglon["bultos_armados"] == 25.0
    assert renglon["ya_devuelto"] == 5.0


def test_el_renglon_para_reingreso_VUELVE_aunque_NO_TENGA_FICHA():
    """El JOIN con la ficha es LEFT y eso no es cosmético: con un JOIN normal
    el reingreso de un renglón sin ficha asignada daría 404.

    Hasta el 18/09 este test además exigía que la consulta trajera
    `ficha_envase_id` y `ficha_envase_variable`, para que la pantalla supiera
    si preguntar en qué caja volvió. Esa pregunta no existe: sus columnas se
    dropearon el 17/09 (db/envases_9) y las dos del SELECT no las leía nadie
    — corolario 72, una columna que se pide y nadie consume.
    """
    consulta = "\n".join(
        linea for linea in inspect.getsource(obtener_renglon_para_reingreso).split("\n")
        if "--" not in linea
    )
    assert "LEFT JOIN fichas_logistica fl ON fl.id = r.ficha_id" in consulta


def test_listar_renglones_para_reingreso_es_por_pedido_y_sucursal():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("articulo_nombre",), ("bultos_armados",), ("ya_devuelto",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_renglones_para_reingreso(40, "VL")

    consulta = cursor.execute.call_args.args[0]
    assert "r.pedido_id = %s AND r.sucursal = %s" in consulta
    assert cursor.execute.call_args.args[1] == (40, "VL")


def test_devoluciones_vinculadas_por_rango_trae_el_renglon_y_la_fecha_del_pedido():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("bultos",), ("fecha_operacion",), ("costo_por_bulto",),
                          ("kilos_enviados",), ("bultos_armados",), ("fecha_pedido",),
                          ("articulo_id",), ("articulo_nombre",), ("grupo",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        devoluciones_vinculadas_por_rango(1, date(2026, 8, 18), date(2026, 8, 25))

    consulta = cursor.execute.call_args.args[0]
    # Solo reingresos VINCULADOS y no anulados del cliente, por la fecha
    # del reingreso; la fecha del PEDIDO viaja para anclar el precio.
    assert "m.anulado_el IS NULL AND m.pedido_renglon_id IS NOT NULL" in consulta
    assert "p.fecha_operacion AS fecha_pedido" in consulta
    assert cursor.execute.call_args.args[1] == (1, date(2026, 8, 18), date(2026, 8, 25))


# --- Etapa 2: el stock inicial del corte ---


def test_fecha_corte_se_lee_de_la_base_y_no_del_codigo():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 8, 31),)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert fecha_corte() == date(2026, 8, 31)

    consulta = cursor.execute.call_args.args[0]
    assert "corte_modelo" in consulta and "id = 1" in consulta


def test_fecha_corte_sin_fila_revienta_en_vez_de_inventar_una():
    # Una base a medio configurar tiene que avisar: elegir una fecha por su
    # cuenta sería costear contra lotes que no corresponden, en silencio.
    conexion, _ = _conexion_falsa(filas_fetchone=[None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(RuntimeError, match="a medio configurar"):
            fecha_corte()


def test_crear_stock_inicial_es_un_movimiento_de_TIPO_PROPIO_con_costo():
    # Con tipo propio y no como 'ajuste': es exactamente el error que se
    # cometió con los saldos iniciales de Vacíos.
    with patch("app.db.crear_movimiento_stock", return_value=40.0) as mock_mov:
        assert crear_stock_inicial(7, 40, 1500, date(2026, 8, 31)) == 40.0

    args, kwargs = mock_mov.call_args
    assert args[1] == "stock_inicial"
    assert args[2] == 40
    assert kwargs["costo_por_bulto"] == 1500


def test_crear_stock_inicial_sin_costo_no_llega_a_la_base():
    with patch("app.db.crear_movimiento_stock") as mock_mov:
        with pytest.raises(ValueError, match="costo por bulto"):
            crear_stock_inicial(7, 40, None, date(2026, 8, 31))
    mock_mov.assert_not_called()


def test_crear_stock_inicial_con_cero_bultos_no_llega_a_la_base():
    with patch("app.db.crear_movimiento_stock") as mock_mov:
        with pytest.raises(ValueError, match="mayor a cero"):
            crear_stock_inicial(7, 0, 1500, date(2026, 8, 31))
    mock_mov.assert_not_called()


def test_reproceso_inicial_toma_CERO_y_no_escribe_consumos():
    """El corazón de la etapa: produce sin consumir.

    Las cajas armadas del piso ya existen y los cajones que las originaron
    no se van a cargar nunca. Si este reproceso descontara como uno normal,
    dejaría el artículo en negativo o se comería el stock inicial suelto
    recién cargado.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(99,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert crear_reproceso_inicial(7, 20, 2200, date(2026, 8, 31), ficha_id=11, cliente_id=2) == 99

    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO reprocesos" in consulta
    # Toma cero y es de tipo inicial: los dos van escritos en el INSERT, y
    # el check de la base no deja cargarlo de otra forma.
    assert "VALUES (%s, %s, 0, %s, 0, 0, %s, %s, %s, %s, 'inicial')" in consulta
    # costo_total = cajas × costo por caja, para que siga valiendo
    # costo_por_bulto_primera = costo_total / bultos_primera.
    assert parametros == (7, date(2026, 8, 31), 20, 44000.0, 2200, 2, 11)
    # No corre el FIFO ni escribe consumos: no hay lote del que salgan.
    assert not any("reprocesos_consumos" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_called_once()


def test_reproceso_inicial_sin_ficha_no_llega_a_la_base():
    # Al revés que el reproceso normal: una caja armada que está en el piso
    # se puede ir a mirar, así que un "sin asignar" acá sería no haberla
    # mirado.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(99,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="ficha"):
            crear_reproceso_inicial(7, 20, 2200, date(2026, 8, 31), ficha_id=None)

    cursor.execute.assert_not_called()


def test_reproceso_inicial_sin_costo_no_llega_a_la_base():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(99,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="costo por caja"):
            crear_reproceso_inicial(7, 20, None, date(2026, 8, 31), ficha_id=11)

    cursor.execute.assert_not_called()


def test_anular_stock_inicial_no_es_puerta_de_atras_para_otros_movimientos():
    """El UPDATE filtra POR TIPO, no solo por id.

    Sin ese filtro, la pantalla del stock inicial dejaría anular cualquier
    ajuste o cualquier guía R del depósito cambiando un número en el
    formulario.
    """
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 1

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_renglon_stock_inicial("sueltos", 5)
    consulta, parametros = cursor.execute.call_args.args
    assert "movimientos_stock" in consulta and "tipo = 'stock_inicial'" in consulta
    assert parametros == (5,)

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_renglon_stock_inicial("armadas", 99)
    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE reprocesos" in consulta and "tipo = 'inicial'" in consulta
    assert parametros == (99,)


def test_anular_stock_inicial_que_no_es_del_corte_avisa_y_no_commitea():
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 0

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="no es del stock inicial"):
            anular_renglon_stock_inicial("sueltos", 5)

    conexion.commit.assert_not_called()


def test_listar_articulos_para_reproceso_no_esconde_el_articulo_que_hay_que_reprocesar():
    """El caso real del 31/08: el depósito armó cajas de una ficha ANTES de cargar
    su guía R. El total del artículo bajó a cero, pero la pila suelta seguía en el
    piso — y el selector de Reproceso lo escondía justo cuando había que cargar la
    guía que reconcilia esa diferencia.

    El filtro es total > 0 O sueltos > 0: solo AGREGA a la lista de antes.
    """
    from app.db import listar_articulos_para_reproceso

    conexion, cursor = _conexion_falsa()
    cursor.fetchall.side_effect = [
        # _cajas_por_ficha: (articulo_id, ficha_id, cajas, con_envase)
        # Zapallito en déficit y SIN envase: el piso lo deja en 0 y el
        # artículo desaparecería del selector si el filtro fuera solo por
        # total — que es justo la falla del 31/08 que este test cuida.
        [(19, 5, -44.0, False), (17, 7, 12.0, False)],
        # El stock por artículo (las seis patas)
        [(19, "Zapallito", 0.0), (17, "Berenjena", 12.0), (22, "Mango", 0.0), (9, "Pera", 5.0)],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_articulos_para_reproceso()

    ids = [a["id"] for a in resultado]
    # Zapallito: total 0 pero cajas en -44, o sea 44 SUELTOS en el piso. Tiene que estar.
    assert 19 in ids
    # Berenjena: sus 12 bultos son las 12 cajas de la ficha 7, sueltos en cero.
    # Sigue estando, porque el total es a favor: esta entrega NO SACA NADA de la
    # lista de antes. Reprocesar cajas ya armadas lo decide el freno, no acá.
    assert 17 in ids
    # Mango sin nada, afuera. Pera con 5 sueltos y sin fichas, adentro.
    assert 22 not in ids
    assert 9 in ids
    # Y solo id y nombre: ninguna cantidad viaja a la pantalla del operario.
    assert all(set(a) == {"id", "nombre"} for a in resultado)


def test_fichas_con_cajas_armadas_devuelve_SOLO_ids_sin_cantidades():
    """La usa la pantalla de armado, que es de operario.

    El número del sistema se usa del lado del server para decidir si
    avisar, pero no puede viajar a su pantalla ni escondido en el HTML: si
    lo ve, arma contra el sistema en vez de contra el piso.
    """
    from app.db import fichas_con_cajas_armadas

    conexion, cursor = _conexion_falsa()
    cursor.fetchall.return_value = [(1, 11, 20.0, False), (1, 12, 0.0, False),
                                    (2, 13, 5.0, False), (2, 14, -3.0, False)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = fichas_con_cajas_armadas()

    # Solo las que tienen cajas de verdad: cero y negativo no cuentan.
    assert resultado == {11, 13}
    # Y son ids pelados, sin ninguna cantidad adentro.
    assert all(isinstance(x, int) for x in resultado)


def test_guardar_lotes_elegidos_borra_y_reescribe_y_los_ceros_no_entran():
    """La corrección es un documento chico y ENTERO, no filas con vida propia.

    Y guarda SOLO la excepción: un lote en cero no es una corrección, es no
    haber elegido ese lote. Con la lista vacía no queda ninguna fila y el
    renglón vuelve a repartirse por FIFO — aceptar la propuesta es no guardar
    nada, así que el default nunca puede quedar viejo.
    """
    from app.db import guardar_lotes_elegidos

    # Sin envase: la pared no aplica y el cajón es una opción legítima, que
    # es el caso de todos los días.
    salida = {"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 11, 0)), "tipo": "armado",
              "cantidad": 5.0, "renglon_id": 55, "ficha_con_envase": False}
    conexion, cursor = _conexion_falsa(filas_fetchone=[(1,)])

    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._entradas_y_salidas_stock", return_value=([], [salida])),
    ):
        guardar_lotes_elegidos(55, [
            {"lote_tipo": "guia", "lote_origen_id": 101, "bultos": 5},
            {"lote_tipo": "guia", "lote_origen_id": 102, "bultos": 0},
        ])

    consultas = [c.args[0] for c in cursor.execute.call_args_list]
    borrado = _sql_que_contiene(cursor, "DELETE FROM pedidos_renglones_lotes_elegidos")
    assert "DELETE FROM pedidos_renglones_lotes_elegidos" in borrado
    # Un solo INSERT: el de cero no entra.
    inserts = [ll for ll in cursor.execute.call_args_list if "INSERT INTO" in ll.args[0]]
    assert len(inserts) == 1
    assert inserts[0].args[1] == (55, "guia", 101, 5)
    conexion.commit.assert_called_once()


def _guardar_elegido(lote_tipo, *, con_envase, renglon_id=55):
    """`guardar_lotes_elegidos` con una salida armada a mano. Devuelve el cursor.

    Se le da la SALIDA y no la ficha: `ficha_con_envase` viaja con la salida
    desde `_SQL_SALIDAS_STOCK`, que es de donde lo lee la pared. Leer la
    ficha por su cuenta sería la segunda copia de la condición.
    """
    from app.db import guardar_lotes_elegidos

    salida = {"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 11, 0)), "tipo": "armado",
              "cantidad": 5.0, "renglon_id": renglon_id, "ficha_con_envase": con_envase}
    conexion, cursor = _conexion_falsa(filas_fetchone=[(1,)])
    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._entradas_y_salidas_stock", return_value=([], [salida])),
    ):
        guardar_lotes_elegidos(renglon_id, [
            {"lote_tipo": lote_tipo, "lote_origen_id": 101, "bultos": 5},
        ])
    return cursor


def test_guardar_lotes_elegidos_RECHAZA_el_cajon_en_una_ficha_con_envase():
    """LA PUERTA QUE QUEDABA ABIERTA, y no es la pantalla: es el POST.

    `lotes_senalados` corre en la pasada de los DIRIGIDOS, antes de que
    `pasadas_de_lotes` decida qué se ofrece. Un renglón con el cajón elegido
    a mano se llevaba el cajón, con envase y todo — medido el 09/09 sobre
    `repartir_fifo`: 10 bultos consumidos donde la pared sola dejaba 10 sin
    lote.

    Que la pantalla ya no lo liste no alcanza: la guarda va donde se ESCRIBE.
    Es lo mismo del tilde de la fecha del 08/09 — un formulario armado a mano
    entraba sin ver el cartel.
    """
    with pytest.raises(ValueError) as rechazo:
        _guardar_elegido("guia", con_envase=True)

    # Y el motivo dice QUÉ pasó y qué hacer, no "no se pudo guardar".
    assert "cajón" in str(rechazo.value)
    assert "guía R" in str(rechazo.value)


def test_la_pared_del_POST_no_traba_lo_que_SIEMPRE_estuvo_permitido():
    """EL CASO FELIZ, y es el único que distingue una guarda que funciona de
    una que frena siempre (corolario 30: la batería de negativos toda en
    verde con la guarda rota).

    Dos permitidos, por razones distintas: el cajón SIN envase —el caso de
    todos los días, envase perdido— y la caja armada CON envase, que es
    justo lo que la pared sí ofrece.
    """
    for lote_tipo, con_envase in (("guia", False), ("reproceso", True)):
        cursor = _guardar_elegido(lote_tipo, con_envase=con_envase)
        inserts = [ll for ll in cursor.execute.call_args_list if "INSERT INTO" in ll.args[0]]
        assert len(inserts) == 1, f"{lote_tipo} con envase={con_envase} tendría que entrar"


def test_la_pared_del_POST_pregunta_por_pasadas_de_lotes_y_no_por_su_propia_condicion():
    """La razón vive en UN lugar. Si `guardar_lotes_elegidos` escribiera su
    propio `if ficha_con_envase`, el día que la pared cambie quedarían dos
    reglas y la que rechaza dejaría de ser la que el reparto aplica.

    Se verifica moviendo la PARED y comprobando que la guarda la sigue: con
    la pared apagada, el cajón con envase pasa a entrar.
    """
    from app import db as db_modulo

    assert "ficha_con_envase" not in inspect.getsource(db_modulo.guardar_lotes_elegidos)

    with patch("core.stock.pasadas_de_lotes", side_effect=lambda lotes, salida: [lotes]):
        cursor = _guardar_elegido("guia", con_envase=True)
    inserts = [ll for ll in cursor.execute.call_args_list if "INSERT INTO" in ll.args[0]]
    assert len(inserts) == 1, "la guarda no siguió a la pared: tiene condición propia"


def test_guardar_lotes_elegidos_vacio_deja_el_renglon_sin_correccion():
    from app.db import guardar_lotes_elegidos

    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_lotes_elegidos(55, [])

    consultas = [c.args[0] for c in cursor.execute.call_args_list]
    assert len(consultas) == 1
    assert "DELETE FROM pedidos_renglones_lotes_elegidos" in consultas[0]


from app.db import (  # noqa: E402
    cambiar_actividad_proveedor,
    listar_proveedores,
    listar_proveedores_para_abm,
    listar_todos_los_proveedores,
    obtener_o_crear_proveedor_por_codigo,
    renombrar_proveedor,
)


def test_listar_proveedores_es_el_unico_lugar_que_filtra_por_activo():
    # El filtro vive acá y en ningún llamador: los diez que piden la lista
    # eligen entre esta y listar_todos_los_proveedores, no repiten el WHERE.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_proveedores()

    consulta = cursor.execute.call_args.args[0]
    assert "WHERE activo" in consulta
    assert "ORDER BY codigo_puesto" in consulta


def test_listar_todos_los_proveedores_no_filtra_nada():
    # Es la lista de los FILTROS de búsqueda. Un proveedor de baja tiene
    # compras viejas que siguen existiendo: si desapareciera del filtro,
    # ese historial dejaría de poder buscarse por él.
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_todos_los_proveedores()

    consulta = cursor.execute.call_args.args[0]
    assert "WHERE" not in consulta


def test_listar_proveedores_para_abm_trae_el_estado_y_cuantas_compras_tiene():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_proveedores_para_abm()

    consulta = cursor.execute.call_args.args[0]
    assert "p.activo" in consulta
    # El conteo separa el fantasma de un código mal tipeado (0 compras) del
    # proveedor de verdad que alguien está por esconder sin querer.
    assert "SELECT COUNT(*) FROM compras c WHERE c.proveedor_id = p.id" in consulta
    # Los de baja al final: son la excepción.
    assert "ORDER BY p.activo DESC, p.codigo_puesto" in consulta


def test_obtener_o_crear_proveedor_por_codigo_reactiva_al_que_estaba_de_baja():
    # Si llegó mercadería con ese código, el proveedor existe: dejarlo de
    # baja haría que el selector mienta y que la compra recién cargada
    # quede colgando de un proveedor invisible.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, False)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        proveedor_id, reactivado = obtener_o_crear_proveedor_por_codigo("N01P02", "Don Pedro")

    consulta, parametros = cursor.execute.call_args_list[1].args
    assert "activo = true" in consulta
    assert parametros == ("Don Pedro", 7)
    assert (proveedor_id, reactivado) == (7, True)


def test_con_pisar_nombre_en_FALSE_el_UPDATE_no_toca_el_nombre():
    """La mitad que el test de la ruta no puede ver, y la encontró un canario en CERO.

    El de la ruta afirma que la bandera se PASA; con ella ignorada acá, el
    alta a mano renombraría al proveedor que ya existía —una corrección que
    nadie pidió— y ningún test caía. Es la forma del corolario 65: la orden
    dada no prueba que se haya cumplido.

    Se mira el TEXTO del UPDATE y no solo los parámetros: con `nombre = %s`
    de vuelta en la consulta y el nombre sacado de la tupla, los parámetros
    también cambiarían, pero una consulta que nombra la columna y no la
    recibe es un error distinto del que este test cuida.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, True)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        proveedor_id, reactivado = obtener_o_crear_proveedor_por_codigo(
            "N01P02", "EJEMPLO Tipeado", pisar_nombre=False)

    consulta, parametros = cursor.execute.call_args_list[1].args
    assert "activo = true" in consulta, "tiene que seguir reactivándolo"
    assert "nombre" not in consulta, "el alta a mano no renombra al que ya estaba"
    assert "EJEMPLO Tipeado" not in parametros
    assert parametros == (7,)
    assert (proveedor_id, reactivado) == (7, False)


def test_con_pisar_nombre_en_TRUE_sigue_mandando_la_ultima_correccion():
    """El control, y es el que distingue la bandera de un UPDATE que nunca pisa.

    Con el `if` roto para el otro lado —que nunca pise— el test de arriba pasa
    igual. Los dos juntos son lo único que dice que la bandera decide algo.
    Y éste es el camino de todos los días: llegó mercadería con ese código, y
    el que la recibió acaba de leer el nombre del remito.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, True)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        obtener_o_crear_proveedor_por_codigo("N01P02", "EJEMPLO Del Remito")

    consulta, parametros = cursor.execute.call_args_list[1].args
    assert "nombre = %s" in consulta
    assert parametros == ("EJEMPLO Del Remito", 7)


def test_obtener_o_crear_proveedor_por_codigo_no_dice_reactivado_si_ya_estaba_activo():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, True)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        proveedor_id, reactivado = obtener_o_crear_proveedor_por_codigo("N01P02", "Don Pedro")

    assert (proveedor_id, reactivado) == (7, False)


def test_obtener_o_crear_proveedor_por_codigo_nuevo_no_es_una_reactivacion():
    conexion, cursor = _conexion_falsa(filas_fetchone=[None, (9,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        proveedor_id, reactivado = obtener_o_crear_proveedor_por_codigo("N09P09", "Nuevo")

    assert (proveedor_id, reactivado) == (9, False)


def test_renombrar_proveedor_no_toca_el_codigo():
    # codigo_puesto es la identidad: cambiarlo movería todas las compras
    # del proveedor a otro. Un código mal tipeado se da de baja, no se
    # renombra.
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 1

    with patch("app.db.obtener_conexion", return_value=conexion):
        renombrar_proveedor(7, "Don Pedro")

    consulta, parametros = cursor.execute.call_args.args
    assert "codigo_puesto" not in consulta
    assert parametros == ("Don Pedro", 7)
    conexion.commit.assert_called_once()


def test_cambiar_actividad_proveedor_da_de_baja_y_de_alta_con_el_mismo_update():
    for activo in (False, True):
        conexion, cursor = _conexion_falsa()
        cursor.rowcount = 1

        with patch("app.db.obtener_conexion", return_value=conexion):
            cambiar_actividad_proveedor(7, activo)

        consulta, parametros = cursor.execute.call_args.args
        assert "SET activo = %s" in consulta
        # La baja no borra ni valida contra las compras: solo saca del selector.
        assert "DELETE" not in consulta
        assert parametros == (activo, 7)


def test_cambiar_actividad_proveedor_avisa_si_el_proveedor_ya_no_existe():
    conexion, cursor = _conexion_falsa()
    cursor.rowcount = 0

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            cambiar_actividad_proveedor(7, False)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert "ya no existe" in str(error)

    conexion.commit.assert_not_called()


# --- El criterio de "esta compra todavía se puede borrar" ---
#
# La regla vive en SQL (_SQL_COMPRA_BORRABLE) y no en tres `if` de Python,
# así que lo que hay que proteger acá es el TEXTO de la condición y que las
# dos funciones que borran usen la MISMA. Con un cursor falso el WHERE no se
# evalúa: un test de comportamiento sobre un mock no probaría la regla.

from app.db import (  # noqa: E402
    ORIGEN_RETIRO_AUTOMATICO_POR_TIPO,
    _motivo_por_el_que_no_se_puede_eliminar,
    _SQL_COMPRA_BORRABLE,
    eliminar_compras_del_dia_por_proveedor,
)


def test_el_criterio_de_borrado_bloquea_lo_que_paso_por_deposito_o_por_un_retiro_real():
    condicion = " ".join(_SQL_COMPRA_BORRABLE.split())
    assert "estado IS DISTINCT FROM 'recepcionado'" in condicion
    assert "estado IS DISTINCT FROM 'no_ingresado'" in condicion
    assert "estado_retiro IS DISTINCT FROM 'retirado'" in condicion


def test_el_retiro_automatico_no_bloquea_pero_solo_mientras_siga_pendiente():
    # Las dos condiciones van juntas: solo el origen dejaría borrar una
    # rechazada de Cooperativa (hoy lo único que la bloquea es el retiro),
    # y solo el estado dejaría borrar una que Logística tildó a mano.
    condicion = " ".join(_SQL_COMPRA_BORRABLE.split())
    assert "estado = 'pendiente' AND retiro_origen IN (" in condicion


def test_los_origenes_automaticos_del_sql_salen_de_la_constante_de_python():
    # Si mañana se agrega un tipo automático, la condición lo acompaña sola:
    # no hay una segunda lista escrita a mano adentro del SQL.
    condicion = " ".join(_SQL_COMPRA_BORRABLE.split())
    for origen in ORIGEN_RETIRO_AUTOMATICO_POR_TIPO.values():
        assert f"'{origen}'" in condicion


def test_el_borrado_de_a_uno_y_el_cancelar_del_dia_usan_LA_MISMA_condicion():
    # Este es el test que importa. El criterio estaba escrito dos veces —tres
    # `if` en Python y un WHERE en el Cancelar del día—, y la excepción del
    # retiro automático habría entrado en una sola: las dos pantallas habrían
    # empezado a decir cosas distintas de la misma compra.
    conexion, cursor = _conexion_falsa([(105,), (0,)], filas_fetchall=[])
    with patch("app.db.obtener_conexion", return_value=conexion):
        eliminar_compra(30, origen="compras")
    sql_de_a_uno = _sql_que_contiene(cursor, "DELETE FROM compras")

    conexion, cursor = _conexion_falsa([(7,), (7,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        eliminar_compras_del_dia_por_proveedor(date(2026, 9, 4), 3)
    sql_del_dia = _sql_que_contiene(cursor, "DELETE FROM compras")
    sql_fotos_del_dia = _sql_que_contiene(cursor, "DELETE FROM fotos_recepcion")

    assert _SQL_COMPRA_BORRABLE in sql_de_a_uno
    assert _SQL_COMPRA_BORRABLE in sql_del_dia
    # Y LA TERCERA COPIA, que es nueva: el borrado de las fotos del día tiene
    # que recortar por lo MISMO que el de las compras. Con un criterio propio
    # borraría la foto de una compra que después queda protegida — la fila
    # sobrevive, el archivo no, y "Ver foto" queda roto sin que nada avise.
    assert _SQL_COMPRA_BORRABLE in sql_fotos_del_dia


def test_el_borrado_de_a_uno_decide_en_el_delete_y_no_antes():
    # Decide la base; el código traduce el error. No hay un SELECT previo que
    # pregunte "¿se puede?" para después borrar: eso es lo que se separa.
    conexion, cursor = _conexion_falsa([(105,), (0,)], filas_fetchall=[])
    with patch("app.db.obtener_conexion", return_value=conexion):
        eliminar_compra(30, origen="compras")

    consultas = [ll.args[0] for ll in cursor.execute.call_args_list]
    hasta_el_delete = consultas[: next(i for i, c in enumerate(consultas) if "DELETE FROM compras" in c)]
    # Lo que importa no es que el DELETE sea el PRIMERO —hoy lo precede el de
    # fotos_recepcion, que la FK obliga— sino que antes no haya ningún SELECT
    # preguntando "¿se puede?". Eso es lo que se separa del constraint.
    assert not any("SELECT" in c.upper() for c in hasta_el_delete), hasta_el_delete
    assert "RETURNING guia_id" in _sql_que_contiene(cursor, "DELETE FROM compras")


def test_el_motivo_dice_que_no_sabe_cuando_no_sabe():
    # Que el SQL rechace y el traductor no encuentre el motivo significa que
    # la condición y su mensaje se separaron. Tragarlo es cómo se pierde
    # meses después.
    cursor = MagicMock()
    cursor.fetchone.return_value = ("pendiente", "pendiente")

    motivo = _motivo_por_el_que_no_se_puede_eliminar(cursor, 30)

    assert "no sabe por qué" in motivo
    assert "se separaron" in motivo


def test_el_motivo_avisa_si_la_compra_ya_no_existe():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    assert _motivo_por_el_que_no_se_puede_eliminar(cursor, 30) == "Esa compra ya no existe."


# --- El piso de la cuenta por ficha (04/09/2026) ---
#
# El saldo por ficha es "producidas - salidas" y PUEDE SER NEGATIVO: un
# articulo que no se reprocesa (manzana, pera) no produce nunca, y uno que
# si se reprocesa puede haberse armado desde la pila suelta. Sin piso, los
# sueltos daban MAS que el total del articulo y el Cotejo ofrecia un ajuste
# destructivo precargado para tapar esa diferencia inventada.

from app.db import _cajas_por_ficha, _stock_de_ficha  # noqa: E402
from app.db import _SQL_STOCK_PARTIDO  # noqa: E402


def test_la_cuenta_por_ficha_arranca_en_el_CORTE_por_las_DOS_patas_y_asimetrica():
    """El piso de fecha, y se comprueba sobre el texto del SQL a propósito.

    La suite mockea el cursor, así que ninguna prueba de acá ejecuta esta
    consulta de verdad (el comportamiento se verificó contra Postgres el
    05/09). Lo que este test protege son las dos invariantes que NO se
    pueden perder:

    1. **Las dos patas o ninguna.** Recortar solo las entradas deja las
       salidas viejas restando contra cajas que ya no están: es el negativo
       estructural que produjo el corte del 31/08.
    2. **El día del corte es asimétrico.** El conteo se toma a la tarde, así
       que lo del día ya está adentro de lo contado. Entradas: los
       'inicial' DEL corte más lo POSTERIOR. Salidas: solo lo posterior.
       Con `>=` en las dos, el día del corte se cuenta dos veces y en las
       dos direcciones (medido: -10 donde había 20, y 30 donde había 15).

    Ninguna de las dos falla ruidosamente si se rompe: dan un número
    equivocado y nada más. Por eso están pinchadas acá.
    """
    assert "corte_modelo" in _SQL_STOCK_PARTIDO
    assert "2026" not in _SQL_STOCK_PARTIDO, "la fecha de corte no se escribe a mano"

    entradas, salidas = _SQL_STOCK_PARTIDO.split("salidas_ficha AS")

    # Entradas: lo posterior al corte, MÁS los 'inicial' del corte mismo.
    assert "fecha_operacion > corte.fecha" in entradas
    assert "tipo = 'inicial' AND fecha_operacion >= corte.fecha" in entradas

    # Salidas: SOLO lo posterior. Un `>=` acá restaría los armados del día
    # del corte, que el conteo de esa tarde ya descontó.
    assert "> corte.fecha" in salidas
    assert ">= corte.fecha" not in salidas
    assert "armado_el" in salidas.split("> corte.fecha")[0]



def _cursor_con_saldos(saldos, filas_extra=None):
    """Un cursor falso cuyo primer fetchall son los saldos por ficha.

    Las filas se escriben `(articulo, ficha, saldo)` o
    `(articulo, ficha, saldo, con_envase)`. Sin el cuarto se asume envase
    PERDIDO, que es lo que son los casos históricos de estos tests —
    Manzana Gob del 04/09 sale en el cajón del proveedor y no se reprocesa
    nunca. Escribirlos como en producción es lo que hace que sigan
    protegiendo lo que protegían.
    """
    cursor = MagicMock()
    completas = [f if len(f) == 4 else (*f, False) for f in saldos]
    cursor.fetchall.side_effect = [completas] + list(filas_extra or [])
    return cursor


def test_el_saldo_por_ficha_se_parte_en_disponibles_y_deficit():
    cursor = _cursor_con_saldos([(1, 901, -170), (2, 902, 55)])

    saldos = _cajas_por_ficha(cursor)

    # Negativo: cero disponibles y el deficit con su tamaño.
    assert saldos[(1, 901)] == (0.0, 170.0)
    # Positivo: las cajas que hay, sin deficit.
    assert saldos[(2, 902)] == (55.0, 0.0)


def test_el_stock_de_una_ficha_SIN_ENVASE_nunca_es_negativo():
    """Manzana Gob del 04/09: −170 crudo, y el piso lo deja en 0.

    Envase PERDIDO: sale en el cajón del proveedor y no se reprocesa
    nunca, así que su saldo es negativo puro y crece todos los días. Acá
    el piso va y se queda.
    """
    cursor = _cursor_con_saldos([(1, 901, -170, False)])

    assert _stock_de_ficha(cursor, 1, 901) == 0.0


def test_el_stock_de_una_ficha_CON_ENVASE_SI_puede_ser_negativo():
    """Y tiene que serlo: es lo que salió sin la guía R que lo produzca.

    Un pedido de Caja de Día no puede tomar nada que no sea de esa ficha.
    Si no hay cajas, el armado queda en déficit y se resuelve cuando entra
    la guía R — igual que el costo, que la pared del FIFO deja sin lote
    hasta ese momento. Antes el excedente se escurría a los sueltos y el
    sistema descontaba mercadería sin procesar por un armado de caja.
    """
    cursor = _cursor_con_saldos([(1, 901, -10, True)])

    assert _stock_de_ficha(cursor, 1, 901) == -10.0


def test_los_sueltos_no_pueden_superar_el_total_del_articulo():
    # El caso que lo destapo: total 63, saldo por ficha -170. Sin piso los
    # sueltos daban 233 -- mas que TODO el stock del articulo -- y el
    # Cotejo mostraba una diferencia de 170 contra el conteo real.
    cursor = _cursor_con_saldos([(1, 901, -170, False)])

    with patch("app.db._stock_deposito_actual", return_value=63.0):
        sueltos = _stock_de_ficha(cursor, 1, None)

    assert sueltos == 63.0


def test_con_envase_el_deficit_NO_se_escurre_a_los_sueltos():
    """La otra cara del anterior, y es el cambio del 09/09.

    Los sueltos son `total − Σ disponibles`. Con el piso, un déficit de 10
    los bajaba en 10: el armado de una caja descontaba mercadería sin
    procesar. Sin piso, el déficit se queda en la ficha y los sueltos
    quedan como están — que es lo que el operario ve en el piso.

    Los dos números están a propósito separados (total 31, déficit 10)
    para que un signo dado vuelta no pase desapercibido.
    """
    cursor = _cursor_con_saldos([(1, 901, -10, True)])

    with patch("app.db._stock_deposito_actual", return_value=31.0):
        sueltos = _stock_de_ficha(cursor, 1, None)

    assert sueltos == 41.0


def test_las_fichas_con_cajas_no_incluyen_una_ficha_en_deficit():
    conexion, _ = _conexion_falsa()
    conexion.cursor.return_value = _cursor_con_saldos([(1, 901, -170), (2, 902, 3)])
    conexion.cursor.return_value.__enter__ = MagicMock(return_value=conexion.cursor.return_value)
    conexion.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.db.obtener_conexion", return_value=conexion):
        from app.db import fichas_con_cajas_armadas

        assert fichas_con_cajas_armadas() == {902}


def test_el_selector_de_reproceso_no_esconde_el_articulo_con_deficit():
    # La falla de produccion del 31/08: el deposito arma cajas de una ficha
    # ANTES de cargar su guia R, el total del articulo baja a cero y la pila
    # suelta sigue intacta en el piso. Antes esto se salvaba de rebote,
    # porque el saldo negativo inflaba los "sueltos"; con el piso ese rebote
    # ya no existe y el criterio pasa a nombrar lo que mira: el DEFICIT.
    cursor = _cursor_con_saldos(
        [(1, 901, -100)],            # se armaron 100 cajas sin guia R
        [[(1, "Banana", 0)]],        # y el total del articulo quedo en cero
    )
    conexion = MagicMock()
    conexion.cursor.return_value = cursor
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    with patch("app.db.obtener_conexion", return_value=conexion):
        from app.db import listar_articulos_para_reproceso

        assert listar_articulos_para_reproceso() == [{"id": 1, "nombre": "Banana"}]



def test_facturacion_por_ficha_usa_kilos_enviados_y_precio_de_la_fecha():
    conexion, cursor = _conexion_falsa()
    cursor.fetchall.return_value = [(1, 1500.50, 4), (2, 300, 4)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        facturado = facturacion_por_ficha(1, date(2026, 8, 8), date(2026, 9, 7))

    consulta = cursor.execute.call_args.args[0]
    # Lo que se factura son los kilos que grabó el depósito, por el precio
    # vigente A LA FECHA DEL PEDIDO — nunca el precio de hoy hacia atrás.
    assert "SUM(e.kilos_enviados * p.precio)" in consulta
    assert "vigente_desde <= e.fecha_operacion" in consulta
    assert "ORDER BY vigente_desde DESC LIMIT 1" in consulta
    # Un pedido corregido no factura dos veces.
    assert "DISTINCT ON (fecha_operacion)" in consulta
    # Lo que no se puede atribuir NO suma como cero: no entra.
    assert "r.ficha_id IS NOT NULL AND r.anulado_el IS NULL" in consulta
    assert "r.kilos_enviados IS NOT NULL" in consulta
    assert cursor.execute.call_args.args[1] == (1, date(2026, 8, 8), date(2026, 9, 7))
    assert facturado["por_ficha"] == {1: 1500.50, 2: 300.0}
    # LEFT y no CROSS: la ficha sin precio a esa fecha no suma plata pero su
    # DÍA se cuenta igual — la mercadería salió del galpón.
    assert "LEFT JOIN LATERAL" in consulta
    assert "COUNT(DISTINCT fecha_operacion)" in consulta
    assert facturado["dias"] == 4


def test_facturacion_por_ficha_no_puede_leer_renglones_de_otro_cliente():
    """El denominador de la incidencia es de UN cliente, y esto lo fija estructural.

    Es la parte de la incidencia que más caro sale si se rompe: con el
    denominador de todos los clientes, cada porcentaje queda mal sin que nada
    falle ni se vea raro en pantalla.

    NO alcanza con verificar que el WHERE del cliente esté: eso pasaría igual
    si alguien agregara una SEGUNDA lectura de pedidos_renglones sin filtrar.
    Por eso se afirma la ESTRUCTURA — que la tabla se lee una sola vez y
    colgada de `vigentes`, que es el único lugar donde vive el filtro de
    cliente. Un renglón que no venga de un pedido de ese cliente no tiene por
    dónde entrar.

    Verificado además contra Postgres real el 07/09, corriendo esta misma
    función con dos clientes: uno con 100 unidades y otro con 900, a $1.000.
    Dio 100.000 y 900.000 — no 1.000.000 en ninguno de los dos.
    """
    conexion, cursor = _conexion_falsa()
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        facturacion_por_ficha(7, date(2026, 8, 8), date(2026, 9, 7))

    consulta, parametros = cursor.execute.call_args.args
    # El filtro de cliente vive en vigentes, y se le pasa el cliente pedido.
    assert "WHERE cliente_id = %s AND anulado_el IS NULL" in consulta
    assert parametros[0] == 7
    # Y pedidos_renglones se lee UNA sola vez, colgada de vigentes: sin otra
    # puerta de entrada, no hay forma de que se cuele un renglón ajeno.
    assert consulta.count("pedidos_renglones") == 1
    assert "JOIN pedidos_renglones r ON r.pedido_id = v.id" in consulta


def test_facturacion_por_ficha_cuenta_el_dia_aunque_no_haya_precio():
    """El caso del 05/09: se armó y salió mercadería de una ficha sin precio
    vigente. No suma plata —no se puede valuar— pero ES un día con entregas, y
    contarlo con el precio de por medio haría desaparecer justo el día que hay
    que ir a mirar."""
    conexion, cursor = _conexion_falsa()
    # Una sola ficha, sin precio: facturado NULL y dias = 1.
    cursor.fetchall.return_value = [(7, None, 1)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        facturado = facturacion_por_ficha(1, date(2026, 8, 8), date(2026, 9, 7))

    assert facturado["por_ficha"] == {}   # no suma como cero: no aparece
    assert facturado["dias"] == 1         # pero el día se cuenta


def test_facturacion_por_ficha_excluye_el_renglon_anulado():
    # Es el criterio de Armar Remito (_grupos_buscar_pedidos), NO el de
    # listar_renglones_pedidos_vigentes, que hoy no filtra el renglón
    # anulado. La facturación tiene que cerrar con la pantalla que factura.
    conexion, cursor = _conexion_falsa()
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        facturacion_por_ficha(1, date(2026, 8, 8), date(2026, 9, 7))

    assert "r.anulado_el IS NULL" in cursor.execute.call_args.args[0]


def test_listar_ultimos_conteos_stock_sin_tope_es_el_cotejo_de_siempre():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("articulo_id",), ("ficha_id",), ("es_segunda",),
                          ("cantidad",), ("stock_sistema",), ("creado_en",),
                          ("articulo_nombre",), ("ficha_nombre",), ("ficha_cliente",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_ultimos_conteos_stock()

    consulta, parametros = cursor.execute.call_args.args
    # El último por PORCIÓN, en el orden del índice conteos_stock_cotejo_idx.
    assert "DISTINCT ON (c.articulo_id, c.ficha_id, c.es_segunda)" in consulta
    assert "ORDER BY c.articulo_id, c.ficha_id, c.es_segunda, c.creado_en DESC" in consulta
    # None = sin tope: el Cotejo siempre mira el presente.
    assert parametros == (None, None)


def test_listar_ultimos_conteos_stock_con_tope_no_trae_conteos_posteriores():
    """El Remanente a una fecha pasada no puede traer el conteo de HOY.

    Sin este tope, el Remanente del 03/09 mostraría físico del futuro contra
    sistema del pasado adentro del mismo archivo, y nada lo diría.
    """
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("articulo_id",), ("ficha_id",), ("cantidad",),
                          ("stock_sistema",), ("creado_en",), ("articulo_nombre",),
                          ("ficha_nombre",), ("ficha_cliente",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_ultimos_conteos_stock(date(2026, 9, 3))

    consulta, parametros = cursor.execute.call_args.args
    # Por el DÍA en hora argentina, no por el timestamp crudo: un conteo de
    # las 21:15 del 03/09 es del 03/09 acá y del 04/09 en UTC.
    assert "(c.creado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date <= %s::date" in consulta
    assert parametros == (date(2026, 9, 3), date(2026, 9, 3))


def test_las_TRES_ramas_de_los_lotes_exigen_que_el_lote_TENGA_bultos():
    """Un lote sin bultos no es un lote, y eso vale para las tres fuentes.

    La consulta de lotes une compras, movimientos y reprocesos. Dos de las
    tres siempre pidieron `> 0` (`m.cantidad`, `rp.bultos_primera`); la de
    compras era la ÚNICA sin la guarda, así que una compra recepcionada con
    cero cajones —o con `cantidad_cajones_real` en NULL, que la base
    permite: `compras_cantidad_cargada_check` exige kilos o fracción, NO
    cajones— entraba como lote fantasma.

    Es la familia del corolario 5: la misma regla escrita en tres lugares
    que no se nombran entre sí, y una que se la olvidó. El test la fija
    sobre las tres a la vez para que la próxima rama nazca con ella.

    Los asserts van con el ALIAS (corolario 4): sin `c.`/`m.`/`rp.` un
    `cantidad > 0` matchearía la rama de al lado y el test miraría algo que
    se le parece.
    """
    from app.db import _entradas_y_salidas_stock_varios

    cursor = MagicMock()
    cursor.description = []
    cursor.fetchall.return_value = []
    _entradas_y_salidas_stock_varios(cursor, [7], corte=date(2026, 9, 5))

    # call_args da el ÚLTIMO execute, que es el de SALIDAS. La de lotes es la
    # primera: mirar el que no es deja el test verde afirmando otra cosa.
    consulta = " ".join(cursor.execute.call_args_list[0].args[0].split())
    assert "'guia' AS tipo_lote" in consulta, "no es la consulta de lotes"
    assert "AND c.cantidad_cajones_real > 0" in consulta
    assert "m.cantidad > 0" in consulta
    assert "rp.bultos_primera > 0" in consulta


def test_la_cantidad_del_lote_de_compra_nunca_llega_NULA():
    """`cantidad_cajones_real` es nullable y entra directo a la aritmética.

    La guarda del test de arriba ya deja afuera el NULL, pero la cuenta que
    MUESTRA el número se hace cargo igual (corolario 21): si mañana alguien
    afloja el `WHERE`, el `COALESCE` sigue impidiendo que un `None` llegue a
    `core/stock.py`. Redundante a propósito — es la redundancia que sobrevive
    al tercer llamador.
    """
    from app.db import _entradas_y_salidas_stock_varios

    cursor = MagicMock()
    cursor.description = []
    cursor.fetchall.return_value = []
    _entradas_y_salidas_stock_varios(cursor, [7], corte=date(2026, 9, 5))

    consulta = " ".join(cursor.execute.call_args_list[0].args[0].split())
    assert "'guia' AS tipo_lote" in consulta, "no es la consulta de lotes"
    assert "COALESCE(c.cantidad_cajones_real, 0) AS cantidad" in consulta
    assert "c.cantidad_cajones_real AS cantidad" not in consulta


def test_ninguna_consulta_compara_un_timestamptz_contra_una_FECHA_sin_zona():
    """La regla, en un solo lugar, porque estaba escrita en catorce.

    `creado_en >= %s` con un `date` argentino del lado de Python NO compara
    lo que parece: Postgres promueve la fecha usando la zona de la SESIÓN, y
    `app/db.py` no fija ninguna, así que queda la del servidor (UTC en
    Supabase). El día corre de 21:00 a 21:00 hora argentina, y un registro
    de las 21:30 cae en el día siguiente. Verificado contra Postgres 16 en
    UTC: un conteo del 08/09 21:30 aparecía en la lista del 09/09.

    La forma correcta convierte los BORDES y deja la columna pelada, para no
    perder el índice — con la columna convertida el plan pasa de Index Only
    Scan a Seq Scan (verificado con EXPLAIN):

        creado_en >= ((%s::date)::timestamp AT TIME ZONE '<zona>')
        creado_en <  ((%s::date + 1)::timestamp AT TIME ZONE '<zona>')

    Las columnas se leen del ESQUEMA y no de una lista escrita acá: el día
    que una tabla nueva estrene un `timestamptz`, este test la mira sola.
    Los que faltan no se nombran solos — por eso se enumera el esquema.
    """
    import re
    from pathlib import Path

    esquema = Path("db/esquema_completo.sql").read_text(encoding="utf-8")
    columnas = sorted(set(re.findall(r"^\s+([a-z_]+)\s+timestamptz", esquema, re.M)))
    assert len(columnas) > 10, f"el esquema tendría que traer varias; trajo {columnas}"

    ofensoras = []
    for archivo in ("app/db.py", "app/main.py"):
        for numero, linea in enumerate(Path(archivo).read_text(encoding="utf-8").split("\n"), 1):
            if "AT TIME ZONE" in linea:
                continue
            for columna in columnas:
                # Comparada contra un parámetro o una fecha literal, o casteada
                # a date: las tres formas dependen de la zona de la sesión.
                sospechosa = (
                    re.search(rf"\b{columna}\s*(>=|<=|>|<)\s*(%s|')", linea)
                    or re.search(rf"\b{columna}::date", linea)
                )
                if sospechosa:
                    ofensoras.append(f"{archivo}:{numero}: {linea.strip()[:90]}")
                    break

    assert not ofensoras, (
        "comparan un timestamptz contra una fecha sin zona:\n" + "\n".join(ofensoras)
        + "\n\nEs literal a propósito: no distingue SQL de prosa. Si lo que quedó "
          "marcado es un comentario o un docstring que NOMBRA el patrón, reescribí "
          "esa frase — vale más un test estricto con un falso positivo evitable que "
          "uno astuto con un agujero."
    )


def test_la_zona_argentina_es_una_ZONA_y_no_un_offset_numerico():
    """`timezone(timedelta(hours=-3))` es un número, no una zona.

    Hoy coincide: Argentina no mueve el reloj desde 2009. El día que lo
    mueva, un offset fijo sigue diciendo −3 cuando son −2, **en silencio** —
    no hay error que leer, solo horas mal. Y estaba escrito TRES veces
    (app/main.py, app/costeo.py, core/casilla_pedidos.py), así que el día
    del cambio habría que acordarse de los tres.

    Es la misma regla que en el SQL, donde va `AT TIME ZONE
    'America/Argentina/Buenos_Aires'` y nunca un `interval '3 hours'`. El
    test la exige de los dos lados: que las dos mitades nombren la MISMA
    zona, y no un número que hoy da igual.
    """
    import re
    from datetime import timedelta
    from pathlib import Path
    from zoneinfo import ZoneInfo

    from core.zona import ARGENTINA, NOMBRE_ZONA

    assert isinstance(ARGENTINA, ZoneInfo), "tiene que ser una zona, no un offset fijo"
    assert NOMBRE_ZONA == "America/Argentina/Buenos_Aires"
    # Y hoy da lo mismo que el número que reemplazó: el cambio no movió nada.
    assert datetime(2026, 9, 8, 12, 0, tzinfo=ARGENTINA).utcoffset() == timedelta(hours=-3)

    # Nadie vuelve a escribir el offset a mano, ni en Python ni en SQL.
    ofensoras = []
    for archivo in Path(".").glob("[ac]*/**/*.py"):
        if "test" in str(archivo):
            continue
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").split("\n"), 1):
            if re.search(r"timezone\(\s*timedelta\(\s*hours\s*=\s*-3", linea):
                ofensoras.append(f"{archivo}:{numero}: {linea.strip()[:80]}")
    for archivo in list(Path("app").glob("*.py")) + list(Path("core").glob("*.py")):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").split("\n"), 1):
            if re.search(r"interval\s+'-?\s*[0-9]+\s+hours?'", linea):
                ofensoras.append(f"{archivo}:{numero}: {linea.strip()[:80]}")

    assert not ofensoras, (
        "la zona argentina escrita como un número, que no sobrevive a un cambio "
        "de horario de verano:\n" + "\n".join(ofensoras)
    )


def _fifo_de_un_articulo(entradas, salidas):
    """Un cursor falso que devuelve un solo artículo con sus lotes y salidas."""
    cursor = MagicMock()
    # (id, nombre): la consulta de candidatos trae el nombre para que el que
    # muestra no necesite una segunda vuelta.
    cursor.fetchall.return_value = [(7, "EJEMPLO Uno")]
    return cursor, {7: (entradas, salidas)}


def test_la_alerta_de_la_guia_R_cuenta_BULTOS_y_SE_APAGA_SOLA():
    """El número sale del rejuego del FIFO, no de una foto guardada.

    Por eso se apaga sola: cargada la guía R —con la fecha del día que
    armó— la siguiente corrida rejuega la historia entera y ya no encuentra
    nada esperando. No hay estado que limpiar ni botón que apretar.

    El test corre las DOS situaciones con la misma función: sin la guía R y
    con ella. Si alguien cambiara el conteo por una consulta propia que
    lee algo persistido, la segunda mitad seguiría contando 10 y cae.
    """
    from app.db import contar_bultos_esperando_guia_r

    cajon = {"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 8, 0)), "tipo_lote": "guia",
             "cantidad": 10.0, "costo_bulto": 50.0}
    caja = {"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 16, 0)), "tipo_lote": "reproceso",
            "cantidad": 10.0, "costo_bulto": 80.0}
    armado = {"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 11, 0)), "tipo": "armado",
              "cantidad": 10.0, "ficha_con_envase": True, "fecha": date(2026, 9, 7)}

    for etiqueta, lotes, esperado in (("sin la guía R", [cajon], 10.0),
                                      ("con la guía R", [cajon, caja], 0.0)):
        cursor, datos = _fifo_de_un_articulo([dict(l) for l in lotes], [dict(armado)])
        conexion = MagicMock()
        conexion.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conexion.cursor.return_value.__exit__ = MagicMock(return_value=False)
        with (
            patch("app.db.obtener_conexion", return_value=conexion),
            patch("app.db._fecha_corte", return_value=date(2026, 9, 5)),
            patch("app.db._entradas_y_salidas_stock_varios", return_value=datos),
        ):
            resultado = contar_bultos_esperando_guia_r()
        assert resultado["casos"] == esperado, f"{etiqueta}: dio {resultado['casos']}"

    # Y la fecha que muestra la alerta es la del armado que espera.
    assert resultado["mas_viejo"] is None, "sin nada esperando no hay fecha que mostrar"



def test_el_bloque_trae_LAS_DOS_FECHAS_para_que_se_vea_si_la_cola_CRECE():
    """`mas_viejo` solo no distingue un día sin cargar de una cola que se alimenta.

    132 bultos "desde el 07/09" se leen igual si el más nuevo es del 07/09
    —un día que quedó sin cargar, y no crece— o si es de hoy, que es una
    costumbre. Son la misma cola con dos diagnósticos opuestos, y el que
    mira el bloque decide distinto en cada caso.

    Los DOS armados son de días distintos a propósito: con uno solo, las dos
    fechas coinciden por construcción y el test no distinguiría una función
    que devolviera `mas_viejo` en las dos claves.
    """
    from app.db import bultos_esperando_guia_r_por_articulo

    cajon = {"orden": (date(2026, 9, 6), datetime(2026, 9, 6, 8, 0)), "tipo_lote": "guia",
             "cantidad": 40.0, "costo_bulto": 50.0}
    viejo = {"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 11, 0)), "tipo": "armado",
             "cantidad": 10.0, "ficha_con_envase": True, "fecha": date(2026, 9, 7)}
    nuevo = {"orden": (date(2026, 9, 15), datetime(2026, 9, 15, 11, 0)), "tipo": "armado",
             "cantidad": 5.0, "ficha_con_envase": True, "fecha": date(2026, 9, 15)}

    cursor, datos = _fifo_de_un_articulo([cajon], [viejo, nuevo])
    conexion = MagicMock()
    conexion.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conexion.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._fecha_corte", return_value=date(2026, 9, 5)),
        patch("app.db._entradas_y_salidas_stock_varios", return_value=datos),
    ):
        por_articulo = bultos_esperando_guia_r_por_articulo()

    fila = por_articulo[7]
    assert fila["bultos"] == 15.0
    assert fila["mas_viejo"] == date(2026, 9, 7)
    assert fila["mas_nuevo"] == date(2026, 9, 15)


def test_la_alerta_no_cuenta_el_sin_lote_de_VERDAD():
    """Solo lo que alguien puede cerrar cargando el papel.

    Un `sin_lote` real —salió más de lo que había— no se arregla con una
    guía R. Si entrara acá, el número no bajaría nunca y la alerta se
    aprendería a ignorar, arrastrando a las demás. Es la misma razón por la
    que la alerta de guías R incompletas deja afuera las que no tienen
    precio POSIBLE.
    """
    from app.db import contar_bultos_esperando_guia_r

    # Un armado SIN envase que salió sin lote: es sin_lote de verdad.
    armado = {"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 11, 0)), "tipo": "armado",
              "cantidad": 10.0, "ficha_con_envase": False, "fecha": date(2026, 9, 7)}
    cursor, datos = _fifo_de_un_articulo([], [armado])
    conexion = MagicMock()
    conexion.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conexion.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._fecha_corte", return_value=date(2026, 9, 5)),
        patch("app.db._entradas_y_salidas_stock_varios", return_value=datos),
    ):
        resultado = contar_bultos_esperando_guia_r()

    assert resultado["casos"] == 0


def test_anular_pedido_rechaza_lo_que_no_se_puede_anular():
    """Las tres guardas, y la que importa es la del armado.

    Con renglones armados la mercadería YA SALIÓ del galpón: anular el
    pedido borraría salidas de stock que ocurrieron. Eso se decide renglón
    por renglón, no de un saque.

    La existencia se lee con un SELECT SIN AGREGADO. La versión SQL de esto
    usaba `count(*)` y no funcionaba: un agregado devuelve UNA FILA con 0
    aunque no haya nada, así que anular un id inexistente pasaba en
    silencio y sobre uno YA anulado pisaba su `anulado_el` original — que
    es peor que no anular, porque borra cuándo se anuló de verdad.
    """
    from app.db import PedidoConArmado, PedidoInexistente, PedidoYaAnulado, anular_pedido

    casos = [
        ([None], PedidoInexistente),                       # no existe: fetchone da None
        ([(datetime(2026, 8, 11, 10, 0),)], PedidoYaAnulado),
        ([(None,), (2,)], PedidoConArmado),                # vivo, con 2 armados
    ]
    for filas, esperada in casos:
        conexion, cursor = _conexion_falsa(filas_fetchone=filas)
        with patch("app.db.obtener_conexion", return_value=conexion):
            with pytest.raises(esperada):
                anular_pedido(19)
        # Lo que importa: NINGUNO de los tres escribió.
        escrituras = [c for c in cursor.execute.call_args_list if "UPDATE" in c.args[0]]
        assert not escrituras, f"{esperada.__name__} llegó a escribir"


def test_anular_pedido_sin_armados_da_de_baja_SOLO_la_cabecera():
    """Los renglones no se tocan.

    Alcanza con `pedidos.anulado_el`: los lectores por rango descartan el
    pedido anulado por el CTE `vigentes` o por un `p.anulado_el` propio.
    Anular además los renglones sería el mismo hecho escrito dos veces —y
    `anular_renglon_pedido` BORRA el armado, así que restaurar el pedido
    después perdería los tildes.
    """
    from app.db import anular_pedido

    conexion, cursor = _conexion_falsa(filas_fetchone=[(None,), (0,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_pedido(19)

    escrituras = [" ".join(c.args[0].split()) for c in cursor.execute.call_args_list if "UPDATE" in c.args[0]]
    assert escrituras == ["UPDATE pedidos SET anulado_el = now() WHERE id = %s"]
    conexion.commit.assert_called_once()


def test_el_desglose_dice_si_la_ficha_tiene_ENVASE():
    """Para que el cartel del caso vacío no mienta.

    Con envase, "no hay lotes cargados" es FALSO: lo que pasa es que la pared
    no le ofrece el cajón al armado. El dato sale de la MISMA salida que
    decide la pared (`_SQL_SALIDAS_STOCK`), no de una segunda lectura de la
    ficha — con dos lecturas, el día que difieran el cartel diría una cosa y
    el reparto otra.

    Desde el 09/09 EL CAJÓN TAMPOCO SE LISTA. Hasta entonces aparecía con 0
    propuestos, y el input al lado alcanzaba para elegirlo a mano: la
    corrección del que arma corre en la pasada de los dirigidos, ANTES de la
    pared, así que el cajón se consumía igual. Este assert decía "el cajón
    sigue en la lista" y era el diseño de ayer; hoy afirma lo contrario a
    propósito.
    """
    from app.db import desglose_de_renglon_armado

    entradas = [{"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 8, 0)), "tipo_lote": "guia",
                 "origen_id": 5, "cantidad": 10.0, "costo_bulto": 50.0, "detalle": "PROV EJEMPLO",
                 "fecha_lote": date(2026, 9, 7)}]
    salida = {"orden": (date(2026, 9, 7), datetime(2026, 9, 7, 11, 0)), "tipo": "armado",
              "cantidad": 10.0, "renglon_id": 55, "ficha_con_envase": True}

    conexion, cursor = _conexion_falsa(filas_fetchone=[(1, 10.0, datetime(2026, 9, 7, 11, 0))])
    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._entradas_y_salidas_stock", return_value=(entradas, [salida])),
    ):
        desglose = desglose_de_renglon_armado(55)

    assert desglose["ficha_con_envase"] is True
    # Y la pared se ve en la propuesta: el cajón está listado pero no se ofrece.
    assert desglose["propuesta"] == {}, "con envase y sin caja no se propone nada"
    assert desglose["lotes"] == [], "el cajón no se lista: no es una opción peor, es la que la regla prohíbe"


# ---------------------------------------------------------------------------
# LA COMPRA QUE YA VIENE ARMADA EN CAJA NUESTRA (guía R tipo 'en_origen')
# ---------------------------------------------------------------------------
#
# La marca la pone el COMPRADOR al cargar la compra (compras.ficha_en_origen_id)
# y la guía R sale sola AL RECEPCIONAR. El depósito no elige nada.
#
# El fixture lleva DOS lotes a propósito y el segundo es el RIVAL: un cajón
# viejo del mismo artículo, que es el que el FIFO elegiría si el consumo no
# fuera dirigido. Con un solo lote —el fixture mínimo, que es el que uno
# escribe sin pensarlo— la implementación correcta y la equivocada dan el mismo
# resultado. Ver CLAUDE.md, "Un caso que anda con el sistema VACÍO".

_COMPRA_EN_ORIGEN = 777
_CAJON_VIEJO = 555

# (envase_id, envase_variable) de la ficha de la guía. Un envase FIJO, así que
# el server lo deriva solo y no hace falta preguntar nada. El número está
# elegido lejos de los otros ids del fixture a propósito: si el envase saliera
# bien copiando el de al lado, el assert no distinguiría nada.
_ENVASE_DE_LA_FICHA = (42, False)

# La fila que lee `_validar_caja_en_origen`: (articulo_id, envase_id,
# envase_variable). Las TRES y no el artículo solo, porque esa guarda también
# rechaza la ficha de ENVASE PERDIDO: con la tupla de una posición el fixture
# deja de parecerse a producción justo en el campo que la guarda mira.
_CAJA_EN_ORIGEN_FIJA = (42, False)


def _lotes_con_rival():
    """El cajón viejo (rival) y la compra que llegó armada, en ese orden de fecha."""
    return [
        _lote_compra(_CAJON_VIEJO, date(2026, 8, 20), 40.0, 1000.0),
        _lote_compra(_COMPRA_EN_ORIGEN, date(2026, 8, 25), 10.0, 1200.0),
    ]


def _conexion_recepcion(ficha_id=3, ficha_articulo=1, numero_guia=99):
    """La cola de fetchone de una recepción ENTERA, en orden de ejecución.

    `ficha_id` None es la compra normal: ahí la guía no se carga y la cola
    termina en esa consulta.
    """
    filas = [
        ("kilo", 760.0, None),         # SELECT a.unidad_compra + las dos cantidades
        ("retirado",),                 # SELECT estado_retiro (auto-retirar: ya estaba)
        # La compra recién escrita, con su ficha marcada y la fecha de su lote.
        (1, ficha_id, 10.0, date(2026, 8, 25), ficha_articulo, 7),
    ]
    if ficha_id is not None and ficha_articulo == 1:
        # `_ENVASE_DE_LA_FICHA` es la lectura que hace `_envase_de_esta_guia`
        # para saber EN QUÉ CAJA se armó: va entre el corte y el RETURNING
        # del INSERT, que es donde el server la pide.
        filas += [_CORTE, _ENVASE_DE_LA_FICHA, (numero_guia,)]
    conexion, cursor = _conexion_falsa(filas_fetchone=filas)
    cursor.description = COLUMNAS_LOTES
    # Lotes, salidas, y lo que ya se llevaron hoy otras guías R: ninguna.
    cursor.fetchall.side_effect = [_lotes_con_rival(), [], []]
    return conexion, cursor


def test_el_fixture_de_la_guia_en_origen_TIENE_un_rival_que_el_FIFO_ELEGIRIA():
    """El test que cuida al test: sin rival, el de abajo no distingue nada.

    Corre el FIFO real sobre los mismos lotes del fixture y exige que la
    propuesta por defecto caiga en el CAJÓN VIEJO. Si algún día alguien
    "simplifica" el fixture dejando un solo lote, este test cae y avisa que el
    de abajo dejó de poder fallar — que es la forma de bug que no deja rastro.
    """
    from core.stock import (
        SALIDA_REPROCESO,
        lotes_permitidos,
        propuesta_fifo,
        reparto_para_reproceso,
        salidas_para_reparto,
    )

    entradas = [dict(zip([c[0] for c in COLUMNAS_LOTES], fila)) for fila in _lotes_con_rival()]
    for entrada in entradas:
        entrada["orden"] = (entrada["fecha_orden"], entrada["momento_orden"])

    reparto = reparto_para_reproceso(entradas, salidas_para_reparto([]), date(2026, 8, 25))
    propuesta = propuesta_fifo(lotes_permitidos(reparto["lotes"], SALIDA_REPROCESO), 10.0, SALIDA_REPROCESO)

    assert propuesta == [{"tipo_lote": "guia", "origen_id": _CAJON_VIEJO, "bultos": 10.0}]


def test_recepcionar_una_compra_MARCADA_carga_su_guia_consumiendo_SU_COMPRA():
    """EL test del camino. Con stock viejo del mismo artículo en el depósito.

    Sin el reparto dirigido el FIFO se lleva el cajón viejo y deja la caja que
    llegó armada como lote CRUDO: el cajón que sigue en el piso figuraría
    convertido y las cajas que llegaron figurarían como cajón. Ningún total se
    descuadra, así que no habría síntoma — lo único que cambia es cuál lote
    quedó trabajado, que es justo lo que la pared del armado mira al despachar.
    """
    conexion, cursor = _conexion_recepcion()

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso, numero_guia = recepcionar_compra(_COMPRA_EN_ORIGEN, 10, 16)

    assert (aviso, numero_guia) == (None, 99)
    consumos = [c for c in cursor.execute.call_args_list if "INSERT INTO reprocesos_consumos" in c.args[0]]
    # UNO solo, y de SU compra. El cajón viejo queda intacto.
    assert len(consumos) == 1
    assert consumos[0].args[1] == (99, "compra", _COMPRA_EN_ORIGEN, _COMPRA_EN_ORIGEN, 10.0, 1200.0)


def test_la_guia_en_origen_es_UNO_A_UNO_y_se_marca_como_tal():
    """La estructura ENTERA del INSERT, no tres campos de trece.

    Un test que compara un subconjunto no protege los que no mira, y acá lo
    que importa está justo en las dos últimas columnas: `tipo` y la compra de
    la que salió. Sin ellas la guía se vería como un armado del galpón.
    """
    conexion, cursor = _conexion_recepcion()

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(_COMPRA_EN_ORIGEN, 10, 16)

    cabecera = next(c for c in cursor.execute.call_args_list if "INSERT INTO reprocesos\n" in c.args[0])
    assert cabecera.args[1] == (
        1, date(2026, 8, 25), 10.0, 10.0,   # artículo, fecha, tomados, primera: UNO A UNO
        0, 0,                              # segunda y merma: el reenvasado no pasó acá
        12000.0, 1200.0,                   # costo del lote de SU compra, todo a la primera
        7, 3,                              # cliente (sale de la ficha) y ficha
        False, "en_origen", _COMPRA_EN_ORIGEN,
        # Y EN QUÉ CAJA: la compra llegó armada en la caja de esa ficha, que
        # tiene envase fijo, así que el server lo deriva sin preguntar nada.
        # Esta guía SUMA al stock de cajas — es una prestada que vuelve.
        True, 42,
    )


def test_la_recepcion_NORMAL_no_carga_ninguna_guia():
    """El caso feliz del otro lado, y es el que distingue "dispara cuando corresponde" de "dispara siempre".

    Sin marca no hay guía: llegó el cajón del proveedor, como toda la vida.
    """
    conexion, cursor = _conexion_recepcion(ficha_id=None)

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso, numero_guia = recepcionar_compra(_COMPRA_EN_ORIGEN, 10, 16)

    assert (aviso, numero_guia) == (None, None)
    assert not [c for c in cursor.execute.call_args_list if "INSERT INTO reprocesos" in c.args[0]]
    conexion.commit.assert_called_once()


def test_la_guia_en_origen_y_su_recepcion_van_en_UNA_SOLA_transaccion():
    """Partidas, una falla en el medio deja la compra recepcionada SIN su guía.

    El stock quedaría crudo y la ficha sin sus cajas, y nada avisaría: la
    compra se vería perfecta. Un solo commit, y el UPDATE de la recepción y el
    INSERT de la guía sobre el MISMO cursor.
    """
    conexion, cursor = _conexion_recepcion()

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(_COMPRA_EN_ORIGEN, 10, 16)

    conexion.commit.assert_called_once()
    conexion.cursor.assert_called_once()
    hechos = [c.args[0] for c in cursor.execute.call_args_list]
    assert any("UPDATE compras" in sql and "estado = 'recepcionado'" in sql for sql in hechos)
    assert any("INSERT INTO reprocesos\n" in sql for sql in hechos)


def test_el_RECHAZO_PARCIAL_de_una_compra_marcada_arma_la_guia_por_los_ACEPTADOS():
    """No hay nada escrito para este caso y por eso hay que probarlo.

    La guía sale por `cantidad_cajones_real`, que ya viene con los bultos
    aceptados (llegados − rechazados). Si en vez de eso mirara la cantidad
    estimada, armaría cajas que se devolvieron al proveedor.
    """
    filas = [("kilo", 160.0, None), ("retirado",), (1, 3, 8.0, date(2026, 8, 25), 1, 7),
             _CORTE, _ENVASE_DE_LA_FICHA, (99,)]
    conexion, cursor = _conexion_falsa(filas_fetchone=filas)
    cursor.description = COLUMNAS_LOTES
    # Lotes, salidas, y lo que ya se llevaron hoy otras guías R: ninguna.
    cursor.fetchall.side_effect = [_lotes_con_rival(), [], []]

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(_COMPRA_EN_ORIGEN, 8, 16, cantidad_cajones_rechazada=2, motivo_rechazo="golpeado")

    assert _valor_insertado(cursor, "bultos_primera", "INSERT INTO reprocesos\n") == 8.0
    assert _valor_insertado(cursor, "bultos_tomados", "INSERT INTO reprocesos\n") == 8.0
    # Y EL TEXTO DE LA CONSULTA, porque con un cursor falso lo de arriba no
    # alcanza: la fila la entrega el mock, así que el assert del valor pasa
    # igual con la columna cambiada. Verificado con el canario — sin esta
    # línea, leer `cantidad_cajones` (lo ESTIMADO) no hace caer nada, y la
    # guía armaría cajas que se devolvieron al proveedor.
    consulta = _sql_que_contiene(cursor, "ficha_en_origen_id")
    assert "c.cantidad_cajones_real" in consulta
    assert "c.cantidad_cajones," not in consulta


def test_la_guia_en_origen_NO_se_carga_si_la_ficha_marcada_es_de_OTRO_ARTICULO():
    """La guarda va donde se ESCRIBE. Una ficha de otro artículo inventaría cajas."""
    conexion, cursor = _conexion_recepcion(ficha_articulo=2)

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="otro artículo"):
            recepcionar_compra(_COMPRA_EN_ORIGEN, 10, 16)

    conexion.commit.assert_not_called()


def test_la_fecha_de_la_guia_en_origen_sale_de_la_MISMA_expresion_que_su_lote():
    """Una guía fechada otro día no ve su propio lote y rebota por un stock que ESTÁ.

    El lote de una compra se ordena por `procesada_el` en hora argentina. Si la
    guía se fechara con otra expresión —`fecha_operacion` de la compra, o el
    `date.today()` del server— el freno buscaría el lote un día antes de que
    exista. Por eso la expresión está escrita UNA vez y este test la compara
    contra la consulta de lotes de verdad, en vez de copiarla acá (copiada
    envejece en silencio).
    """
    consulta_de_lotes = inspect.getsource(db._entradas_y_salidas_stock_varios)
    assert db._SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col="c.procesada_el") in consulta_de_lotes
    assert "_SQL_FECHA_DEL_LOTE_DE_COMPRA" in inspect.getsource(db._guia_en_origen_si_corresponde)


def test_corregir_recepcion_SE_BLOQUEA_si_la_compra_tiene_una_guia_en_origen_viva():
    """Corregir los cajones dejaría la compra en 12 y su guía en 10, sin que nada avise.

    Y el error NOMBRA la guía: un bloqueo que no dice qué lo retiene manda a
    adivinar, y el que está corrigiendo no tiene cómo saber que existe.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[("recepcionado", "kilo", 760.0, None)])
    cursor.fetchall.return_value = [(214,)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="R214"):
            corregir_recepcion_compra(_COMPRA_EN_ORIGEN, 12, 16)

    assert not [c for c in cursor.execute.call_args_list if "UPDATE compras" in c.args[0]]
    conexion.commit.assert_not_called()


def test_corregir_recepcion_SIGUE_ANDANDO_si_la_guia_en_origen_esta_ANULADA():
    """El caso FELIZ, que es el único que distingue una guarda que funciona de una que siempre frena.

    La consulta filtra `anulado_el IS NULL`: anulada la guía, la compra vuelve
    a ser corregible — que es justo lo que el bloqueo le pide al que llega.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[("recepcionado", "kilo", 760.0, None)])
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(_COMPRA_EN_ORIGEN, 12, 16)

    assert [c for c in cursor.execute.call_args_list if "UPDATE compras" in c.args[0]]
    conexion.commit.assert_called_once()
    consulta = _sql_que_contiene(cursor, "FROM reprocesos")
    assert "compra_origen_id = %s" in consulta and "anulado_el IS NULL" in consulta


def test_una_ficha_MARCADA_en_una_compra_que_viene_armada_NO_se_borra():
    """Sin esta guarda el DELETE revienta con el error crudo de la foreign key.

    Y el error crudo no dice QUÉ compra lo retiene, así que el que llega no
    tiene cómo destrabarlo. Es la misma forma que la guarda de las guías R que
    ya estaba al lado: las dos contestan "¿quién apunta a esta ficha?".
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0,), (2,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="2 compras que vienen armadas"):
            eliminar_ficha(901)

    assert not [c for c in cursor.execute.call_args_list if "DELETE FROM fichas_logistica" in c.args[0]]
    conexion.commit.assert_not_called()


def test_la_guarda_de_la_ficha_NO_cuenta_las_compras_RECHAZADAS():
    """Una compra rechazada ya no va a recepcionarse nunca: su marca no retiene nada.

    El filtro va en la consulta y no en Python — la regla la decide la base.
    """
    # Tres conteos: guías R, compras armadas y precios.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0,), (0,), (0,), None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        eliminar_ficha(901)

    consulta = _sql_que_contiene(cursor, "FROM compras")
    assert "ficha_en_origen_id = %s" in consulta
    assert "estado IS DISTINCT FROM 'rechazado'" in consulta


def test_marcar_una_compra_con_una_caja_de_OTRO_ARTICULO_no_la_guarda():
    """La guarda va donde se ESCRIBE la marca, y eso es la CARGA, no la recepción.

    Puesta al recepcionar, la recepción se caería por un error cometido días
    antes —con el camión en la puerta— y el que lo cometió no es el que lo
    sufre. Acá rebota en el momento, contra el que se equivocó.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,), (900,), (2, *_CAJA_EN_ORIGEN_FIJA)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="otro artículo"):
            crear_compra(
                date(2026, 9, 11), 1, 200, 10, 16, 160, None, 5000.0, None, "Clark",
                ficha_en_origen_id=3,
                segunda_por_cajon=None,
            )

    assert not [c for c in cursor.execute.call_args_list
                if "UPDATE compras SET ficha_en_origen_id" in c.args[0]]
    conexion.commit.assert_not_called()


def test_una_compra_marcada_con_la_caja_de_SU_articulo_se_guarda():
    """El caso FELIZ, el único que distingue una guarda que funciona de una que siempre frena."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,), (900,), (1, *_CAJA_EN_ORIGEN_FIJA)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 9, 11), 1, 200, 10, 16, 160, None, 5000.0, None, "Clark",
            ficha_en_origen_id=3,
            segunda_por_cajon=None,
        )

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "SET ficha_en_origen_id")
    assert parametros == (3, 900)
    conexion.commit.assert_called_once()


def test_una_compra_PENDIENTE_marcada_NO_carga_la_guia_R_todavia():
    """La guía sale al RECEPCIONAR, no al cargar: la mercadería no llegó.

    Solo el ingreso directo la carga en el mismo insert, porque esa compra
    nace 'recepcionado' y no pasa por Recepción nunca.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,), (900,), (1, *_CAJA_EN_ORIGEN_FIJA)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 9, 11), 1, 200, 10, 16, 160, None, 5000.0, None, "Clark",
            ficha_en_origen_id=3,
            segunda_por_cajon=None,
        )

    assert not [c for c in cursor.execute.call_args_list if "INSERT INTO reprocesos" in c.args[0]]


def test_el_ingreso_directo_MARCADO_carga_su_guia_R_en_el_MISMO_insert():
    """Esa compra nace 'recepcionado' y NO PASA POR RECEPCIÓN nunca.

    Si el disparo viviera solo en `_recepcionar_compra`, `/deposito/ingresar`
    y el ingreso retroactivo de Gerencia serían dos puertas por las que este
    caso no se puede registrar — y el operario volvería a la guía R a mano,
    que es exactamente lo que todo esto vino a evitar.
    """
    conexion, cursor = _conexion_falsa(
        filas_fetchone=[
            (105,), (0,), (900,),          # guía, punto e id de la compra
            (1, *_CAJA_EN_ORIGEN_FIJA),    # el artículo y la caja de la ficha marcada
            (1, 3, 10.0, date(2026, 8, 25), 1, 7),  # la compra recién escrita
            _CORTE,
            _ENVASE_DE_LA_FICHA,           # en qué caja se armó (sale de la ficha)
            (99,),                         # INSERT INTO reprocesos RETURNING id
        ]
    )
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(900, date(2026, 8, 25), 10.0, 1200.0)],
        [],
        # Lo que ya se llevaron hoy otras guías R: ninguna.
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 8, 25), 1, 200, 10, 16, 160, None, 5000.0, None, "Clark",
            ingreso_directo_deposito=True,
            ficha_en_origen_id=3,
            segunda_por_cajon=None,
        )

    cabecera = next(c for c in cursor.execute.call_args_list if "INSERT INTO reprocesos\n" in c.args[0])
    assert _valor_insertado(cursor, "tipo", "INSERT INTO reprocesos\n") == "en_origen"
    assert _valor_insertado(cursor, "compra_origen_id", "INSERT INTO reprocesos\n") == 900
    # UNA sola transacción: el insert de la compra y el de la guía sobre el
    # mismo cursor, con un solo commit.
    conexion.cursor.assert_called_once()
    conexion.commit.assert_called_once()
    assert cabecera is not None


# ── Marcar "vino armada" una compra YA recepcionada ────────────────────────


from app.db import (  # noqa: E402
    compra_para_marcar_armada,
    marcar_compra_armada_en_origen,
)


def _conexion_para_marcar(estado="recepcionado", ya_marcada=None, fecha_del_lote=date(2026, 9, 11),
                          corte=date(2026, 9, 5), articulo_de_la_ficha=5):
    """El orden de los fetchone() es el orden en que la función pregunta."""
    return _conexion_falsa(filas_fetchone=[
        (estado, ya_marcada, 10.0, fecha_del_lote),   # el estado de la compra
        (corte,),                                     # corte_modelo
        (5,),                                         # articulo_id de la compra
        (articulo_de_la_ficha, *_CAJA_EN_ORIGEN_FIJA),  # artículo y caja de la ficha
    ])


def test_marcar_armada_escribe_la_marca_Y_CARGA_LA_GUIA_en_la_misma_transaccion():
    """Las dos o ninguna: una compra marcada sin su guía deja el lote crudo y
    la ficha sin sus cajas, que es el estado que esto viene a arreglar."""
    conexion, cursor = _conexion_para_marcar()

    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._guia_en_origen_si_corresponde", return_value=214) as mock_guia,
    ):
        assert marcar_compra_armada_en_origen(30, 3) == 214

    consulta, parametros = next(
        llamada.args for llamada in cursor.execute.call_args_list
        if "UPDATE compras SET ficha_en_origen_id" in llamada.args[0]
    )
    assert parametros == (3, 30)
    mock_guia.assert_called_once_with(cursor, 30)
    conexion.commit.assert_called_once()


def test_marcar_armada_RECHAZA_la_compra_que_no_esta_recepcionada():
    """Sin recepción no hay lote, y además la marca tiene su camino: va en la
    carga y la guía sale sola al recibirla."""
    conexion, cursor = _conexion_para_marcar(estado="pendiente")

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="todavía no se recepcionó"):
            marcar_compra_armada_en_origen(30, 3)

    conexion.commit.assert_not_called()


def test_marcar_armada_RECHAZA_la_que_ya_estaba_marcada():
    """Marcarla dos veces cargaría dos guías R por la misma mercadería."""
    conexion, cursor = _conexion_para_marcar(ya_marcada=3)

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="ya está marcada"):
            marcar_compra_armada_en_origen(30, 3)


def test_marcar_armada_RECHAZA_por_el_corte_con_la_MISMA_regla_que_la_carga_retroactiva():
    """La fecha del lote es la de la RECEPCIÓN, y tiene que ser posterior al
    corte — estricto, el día del corte también queda afuera."""
    conexion, cursor = _conexion_para_marcar(fecha_del_lote=date(2026, 9, 5),
                                             corte=date(2026, 9, 5))

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="POSTERIOR al corte"):
            marcar_compra_armada_en_origen(30, 3)


def test_marcar_armada_RECHAZA_una_caja_de_OTRO_articulo():
    """Inventaría cajas que no existen y el Cotejo mostraría un rojo imposible
    de explicar. Y lo pregunta la MISMA guarda que usan el alta y la edición."""
    conexion, cursor = _conexion_para_marcar(articulo_de_la_ficha=99)

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="de otro artículo"):
            marcar_compra_armada_en_origen(30, 3)


def test_marcar_armada_NO_COMMITEA_si_la_guia_R_rebota():
    """Es la mitad que hace que "las dos o ninguna" sea verdad.

    Sin esto la marca quedaría escrita y la guía no, que es exactamente el
    estado roto que esta función viene a evitar.
    """
    from app.db import StockInsuficienteParaReproceso

    conexion, cursor = _conexion_para_marcar()

    with (
        patch("app.db.obtener_conexion", return_value=conexion),
        patch("app.db._guia_en_origen_si_corresponde",
              side_effect=StockInsuficienteParaReproceso(10.0, 3.0, [])),
    ):
        with pytest.raises(StockInsuficienteParaReproceso):
            marcar_compra_armada_en_origen(30, 3)

    conexion.commit.assert_not_called()


def test_la_fecha_del_lote_de_la_pantalla_sale_de_PROCESADA_EL_y_no_de_fecha_operacion():
    """La guía tiene que quedar fechada el día en que su lote existe.

    Y es la MISMA expresión con la que el FIFO fecha el lote — con la fecha de
    operación, una compra del lunes recibida el miércoles quedaría con la guía
    dos días antes de que su lote exista y el freno la rebotaría por un stock
    que está ahí.

    Se mira el TEXTO de la consulta y no el valor: el valor lo devuelve el
    mock, no la columna que la consulta pidió (corolario 40).
    """
    from app.db import _SQL_FECHA_DEL_LOTE_DE_COMPRA

    conexion, cursor = _conexion_falsa(filas_fetchone=[
        (30, 5, "Kiwi", "kilo", "EJEMPLO Uno", "N07P41",
         date(2026, 9, 9), "recepcionado", None, 10.0, 10.0, 0, date(2026, 9, 11)),
        (date(2026, 9, 5),),
    ])
    cursor.description = [
        ("id",), ("articulo_id",), ("articulo_nombre",), ("unidad_compra",),
        ("proveedor_nombre",), ("proveedor_codigo_puesto",), ("fecha_operacion",),
        ("estado",), ("ficha_en_origen_id",), ("cantidad_cajones_real",),
        ("cantidad_cajones",), ("bultos_consumidos",), ("fecha_del_lote",),
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        compra = compra_para_marcar_armada(30)

    consulta = _sql_que_contiene(cursor, "fecha_del_lote")
    assert _SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col="c.procesada_el") in consulta
    assert compra["fecha_del_lote"] == date(2026, 9, 11)
    # El 11/09 es posterior al corte del 05/09 y su lote está intacto: se puede.
    assert compra["motivo"] is None


def test_buscar_compras_TRAE_estado_y_la_marca_para_decidir_el_boton():
    """Por el TEXTO de la consulta: con un cursor falso, la fila la entrega el
    mock y las columnas llegan igual con el SELECT equivocado (corolario 40)."""
    conexion, cursor = _conexion_falsa(filas_fetchall=[])
    cursor.description = [("id",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_compras(date(2026, 9, 1), date(2026, 9, 12))

    consulta = _sql_que_contiene(cursor, "FROM compras c")
    assert "c.estado" in consulta
    assert "c.ficha_en_origen_id" in consulta


def test_buscar_compras_TRAE_LA_FECHA_DEL_LOTE_Y_LO_CONSUMIDO_o_la_regla_se_apaga_sola():
    """Los dos que un canario destapó en CERO, y es el corolario 65.

    Sin estas dos columnas la consulta corre perfecto y trae una menos:
    `motivo_para_no_marcar_armada` recibe None en `bultos_consumidos` y se
    saltea el motivo del lote consumido, así que el botón vuelve a ofrecerse
    en las 90 compras donde no puede funcionar. Y sin `fecha_del_lote` pasa lo
    contrario: se niega en TODAS. Las dos sin un error, sin un test en rojo y
    sin nada en la pantalla que se vea raro — porque lo que se vería es
    exactamente lo que se veía antes.

    Por el TEXTO y no por el valor: con un cursor falso la fila la entrega el
    mock sin mirar una letra del SQL (corolario 40), así que un assert sobre
    el valor pasa igual con la columna sacada.

    ANCLADO EN LA POSICIÓN, no en el nombre suelto (corolario 59): el
    comentario que está arriba de esas columnas las NOMBRA para explicar por
    qué están, así que buscar la palabra matchearía la prosa. `AS
    <columna>` solo puede ser un SELECT.
    """
    conexion, cursor = _conexion_falsa(filas_fetchall=[])
    cursor.description = [("id",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        buscar_compras(date(2026, 9, 1), date(2026, 9, 12))

    consulta = _sql_que_contiene(cursor, "FROM compras c")
    sin_comentarios = "\n".join(
        linea for linea in consulta.split("\n") if not linea.strip().startswith("--")
    )
    assert "AS fecha_del_lote" in sin_comentarios
    assert "AS bultos_consumidos" in sin_comentarios
    # Y que lo consumido salga de las guías VIVAS: sin este filtro, una guía R
    # anulada seguiría reservando el lote y el botón no volvería nunca.
    assert "r.anulado_el IS NULL" in sin_comentarios


def test_actualizar_cantidad_ESCRIBE_la_marca_y_la_valida_contra_el_articulo_NUEVO():
    """La marca viaja con el artículo, y por eso se valida contra el que QUEDA.

    Cambiar el artículo de una compra marcada dejaría la marca apuntando a una
    caja de otro artículo — que es justo lo que la guarda prohíbe. Separadas en
    dos funciones, cada una haría su mitad bien y el resultado sería inválido.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[
        ("pendiente", "pendiente", None),   # el estado de la compra
        (99,),                              # la ficha es del artículo 99
    ])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="de otro artículo"):
            actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Clark", 3, segunda_por_cajon=None)


def test_actualizar_cantidad_DESMARCA_cuando_la_marca_viene_vacia():
    """Desmarcar es una decisión, no un campo que se dejó vacío.

    Sin el UPDATE a NULL, sacar la caja en la pantalla de editar no sacaría
    nada: la compra seguiría marcada y su guía saldría igual al recepcionarla.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[("pendiente", "pendiente", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Clark", None, segunda_por_cajon=None)

    consulta, parametros = next(
        llamada.args for llamada in cursor.execute.call_args_list
        if "UPDATE compras SET ficha_en_origen_id" in llamada.args[0]
    )
    assert parametros == (None, 30)


# ── La guarda de las unidades ──────────────────────────────────────────────


from app.db import (  # noqa: E402
    contar_unidades_que_diferen,
    listar_unidades_que_diferen,
)


def test_la_guarda_de_unidades_cuenta_y_lista_con_LA_MISMA_condicion():
    """Si fueran dos consultas, el banner podría decir 1 y la pantalla no
    mostrar ninguno — y eso es lo único que el que lo lee no puede explicar.

    Se mira el TEXTO del SQL y no el número: con un cursor falso el valor lo
    entrega el mock, así que el conteo llega igual con el `where` equivocado
    (corolario 40).
    """
    from app.db import _SQL_UNIDADES_QUE_DIFIEREN

    conexion, cursor = _conexion_falsa(filas_fetchone=[(1,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        contar_unidades_que_diferen()
    consulta_conteo = _sql_que_contiene(cursor, "FROM articulos a")

    conexion, cursor = _conexion_falsa(filas_fetchall=[])
    cursor.description = [("articulo",)]
    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_unidades_que_diferen()
    consulta_lista = _sql_que_contiene(cursor, "FROM articulos a")

    assert _SQL_UNIDADES_QUE_DIFIEREN in consulta_conteo
    assert _SQL_UNIDADES_QUE_DIFIEREN in consulta_lista


def test_la_guarda_de_unidades_NO_recorta_por_tiempo_ni_por_uso():
    """Las dos cosas que la apagarían antes de que sirva.

    Con ventana se apagaría sola a los dos días dejando el costo torcido para
    siempre. Y filtrando por "se usa", el par dormido avisaría recién cuando
    ya se compró — o sea, cuando el costo ya salió mal la primera vez.
    """
    from app.db import _SQL_UNIDADES_QUE_DIFIEREN

    assert "fecha_operacion" not in _SQL_UNIDADES_QUE_DIFIEREN
    assert "current_date" not in _SQL_UNIDADES_QUE_DIFIEREN
    assert "EXISTS" not in _SQL_UNIDADES_QUE_DIFIEREN.upper()
    # Lo que SÍ recorta: el artículo inactivo, y las dos magnitudes que
    # una compra de ese artículo puede declarar — los kilos, que van
    # siempre, y el conteo, si lo tiene.
    assert "a.activo" in _SQL_UNIDADES_QUE_DIFIEREN
    assert "f.unidad_venta <> 'kilo'" in _SQL_UNIDADES_QUE_DIFIEREN
    assert "f.unidad_venta IS DISTINCT FROM a.unidad_conteo" in _SQL_UNIDADES_QUE_DIFIEREN
    # `IS DISTINCT FROM` y no `<>` contra el conteo: un artículo SIN conteo lo
    # tiene en NULL, y con `<>` toda la comparación daría NULL — o sea que el
    # caso más común (el artículo que se compra solo por kilo y una ficha que
    # le pide unidades) se escaparía en silencio, que es justo el que hay que
    # avisar. Contra el kilo sí va `<>`, porque ahí no hay NULL posible: la
    # condición de arriba ya exige unidad_venta no nula.


def test_toda_columna_que_agrega_una_MIGRACION_esta_en_el_esquema_completo():
    """`db/esquema_completo.sql` tiene que ser el esquema REAL, no uno viejo.

    CLAUDE.md manda verificar los nombres contra ese archivo antes de escribir
    cualquier SQL. Si una migración agrega una columna y el archivo no la
    tiene, la próxima consulta que alguien escriba contra ella falla **y
    parece que la columna no existe** — que es la peor forma de equivocarse:
    manda a construir lo que ya está.

    El 12/09 faltaban DOS, las dos del mismo turno: `proveedor_devolucion_id`
    (con el CHECK de `destino_rechazo` todavía en la lista vieja) y
    `proveedores.cuit`. Las otras migraciones de la semana sí lo habían
    actualizado en el mismo commit, así que el paso existía y era MANUAL: lo
    único que fallaba era acordarse. Esto lo saca de la memoria.

    RESTA LOS `drop`, y hace falta: cinco columnas que una migración agregó
    fueron borradas después (`compras.foto_ruta`, las dos de la excepción del
    freno) o viven en tablas que ya no existen (`precios_dia`,
    `pedidos_supermercado`). Sin restarlas, el test exigiría poner en el
    esquema columnas que el sistema no tiene — y un test que pide lo
    incorrecto se termina aflojando hasta que no pide nada.
    """
    import io
    import pathlib
    import re

    AGREGA = re.compile(
        r"alter\s+table\s+(?:if\s+exists\s+)?(\w+)\s+add\s+column\s+(?:if\s+not\s+exists\s+)?(\w+)", re.I)
    BORRA_COLUMNA = re.compile(
        r"alter\s+table\s+(?:if\s+exists\s+)?(\w+)\s+drop\s+column\s+(?:if\s+exists\s+)?(\w+)", re.I)
    BORRA_TABLA = re.compile(r"drop\s+table\s+(?:if\s+exists\s+)?(\w+)", re.I)

    esquema = io.open("db/esquema_completo.sql", encoding="utf-8").read()
    agregadas, borradas, tablas_borradas = [], set(), set()
    for ruta in sorted(pathlib.Path("db").glob("*.sql")):
        if ruta.name == "esquema_completo.sql":
            continue
        texto = io.open(ruta, encoding="utf-8").read()
        agregadas += [(t.lower(), c.lower(), ruta.name) for t, c in AGREGA.findall(texto)]
        borradas |= {(t.lower(), c.lower()) for t, c in BORRA_COLUMNA.findall(texto)}
        tablas_borradas |= {t.lower() for t in BORRA_TABLA.findall(texto)}

    # El canario de que el barrido MIRA algo: si el regex dejara de matchear,
    # la lista vacía haría pasar el test sin revisar una sola migración.
    assert len(agregadas) > 40, f"el barrido encontró solo {len(agregadas)} columnas: revisá el regex"

    faltan = []
    for tabla, columna, archivo in agregadas:
        if (tabla, columna) in borradas or tabla in tablas_borradas:
            continue
        bloque = re.search(rf"^create table {tabla} \((.*?)^\);", esquema, re.S | re.M)
        # LA DEFINICIÓN, no cualquier mención: el nombre de la columna también
        # aparece en los `constraint` del mismo bloque, así que un `\bcolumna\b`
        # suelto da por presente una columna que solo está nombrada en su
        # propio CHECK. Lo destapó el canario —borrar la definición y dejar el
        # constraint no hacía caer el test—, no leerlo. Es el corolario 4
        # aplicado al esquema: el assert tiene que poder matchear solo lo que
        # se quiso probar.
        definicion = re.compile(rf"^\s*{columna}\s+\w", re.M)
        if bloque is None or not definicion.search(bloque.group(1)):
            faltan.append(f"{archivo}: {tabla}.{columna}")

    assert not faltan, (
        "Columnas que una migración agregó y no están en db/esquema_completo.sql: "
        f"{sorted(set(faltan))}"
    )


def test_toda_TABLA_que_crea_una_MIGRACION_esta_en_el_esquema_completo():
    """El test de arriba mira COLUMNAS, y una TABLA nueva le pasa al lado.

    Del 19/09. `compras_eliminadas` se migró en las dos bases y
    `db/esquema_completo.sql` no la tenía. El guardia del 12/09 estaba
    puesto, andaba, y no podía verlo: busca `alter table ... add column`, y
    una tabla nueva no agrega ninguna columna por esa vía.

    Y el daño no lo ve ninguna de las dos bases de hoy, que corrieron la
    migración y quedaron bien: cae en LA BASE QUE TODAVÍA NO EXISTE. La
    empresa siguiente nace sin la tabla, y como el archivo se escribe en la
    MISMA sentencia que el DELETE, ahí revienta todo borrado de compra —
    meses después, sin que nadie relacione una cosa con la otra. Es la misma
    familia que "una regla de unicidad no puede depender de una extensión de
    Postgres": lo que se pierde el día que se crea la base siguiente no es
    una regla.

    COMPARA EL CONJUNTO ENCONTRADO CONTRA EL DECIDIDO, no recorre una lista
    propia (corolario 60), así que falla en las dos direcciones: cuando
    aparece una tabla que nadie decidió dejar afuera, Y cuando una de las
    excluidas entra al esquema y la lista se queda protegiendo algo que ya
    no pasa.

    LAS SIETE EXCLUIDAS son las tablas muertas del diseño original, y su
    razón está también en el encabezado de `esquema_completo.sql`. No se
    dan por muertas de memoria: se verificó el 19/09 que ninguna aparece en
    POSICIÓN DE TABLA (`FROM|INTO|JOIN|UPDATE <tabla>`) en `app/` ni en
    `core/`. Un grep del nombre suelto da 20 para `recepciones` y 3 para
    `conversion_articulos_cliente`, y las 23 son prosa y nombres de
    variable — la de conversión, de hecho, se fusionó dentro de
    `fichas_logistica` y lo que la nombra son comentarios que cuentan eso.
    """
    import io
    import pathlib
    import re

    # LOS COMENTARIOS SE SACAN PRIMERO, y no es un detalle: la primera
    # versión de este barrido devolvió una tabla llamada `if`, matcheada
    # adentro del comentario de `agregar_disponibles.sql` que dice "seguro de
    # correr más de una vez (create table if not exists...)". Un comentario
    # explica por qué algo es así, así que NOMBRA la cosa que el test busca:
    # la colisión está garantizada por construcción (corolario 59).
    SIN_COMENTARIOS = re.compile(r"--[^\n]*")
    CREA = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?(\w+)", re.I)
    BORRA = re.compile(r"drop\s+table\s+(?:if\s+exists\s+)?(\w+)", re.I)

    # Las muertas del diseño original, con la razón al lado de cada una.
    MUERTAS_A_PROPOSITO = {
        "recepciones": "diseño viejo: hoy la recepción es un estado de compras",
        "pedidos_supermercado": "diseño viejo: hoy son pedidos + pedidos_renglones",
        "precios_dia": "diseño viejo: hoy precios_venta_historial",
        "parametros_historial": "diseño viejo: hoy clientes_parametros_historial",
        "aprendizaje_proveedores": "nunca se usó",
        "resultados": "nunca se usó",
        "conversion_articulos_cliente": "fusionada dentro de fichas_logistica",
    }

    def tablas(texto):
        return {t.lower() for t in CREA.findall(SIN_COMENTARIOS.sub("", texto))}

    esquema = io.open("db/esquema_completo.sql", encoding="utf-8").read()
    en_el_esquema = tablas(esquema)

    creadas, borradas = {}, set()
    for ruta in sorted(pathlib.Path("db").glob("*.sql")):
        if ruta.name == "esquema_completo.sql":
            continue
        texto = SIN_COMENTARIOS.sub("", io.open(ruta, encoding="utf-8").read())
        for nombre in CREA.findall(texto):
            creadas.setdefault(nombre.lower(), set()).add(ruta.name)
        borradas |= {t.lower() for t in BORRA.findall(texto)}

    # El denominador, que es lo único que distingue "ninguna falta" de "no se
    # miró ninguna" (corolario 45). Con el regex roto, las dos dan lo mismo.
    assert len(creadas) > 40, f"el barrido encontró solo {len(creadas)} tablas: revisá el regex"
    assert len(en_el_esquema) > 40, f"el esquema tiene solo {len(en_el_esquema)} tablas: revisá el regex"

    vivas = {t for t in creadas if t not in borradas}
    faltan = {t for t in vivas if t not in en_el_esquema}

    sin_decidir = {f"{t} (la crea {sorted(creadas[t])})" for t in faltan - set(MUERTAS_A_PROPOSITO)}
    assert not sin_decidir, (
        "Tablas que una migración crea y no están en db/esquema_completo.sql: "
        f"{sorted(sin_decidir)}. Una base nueva nace sin ellas."
    )

    # La otra dirección: una excluida que entró al esquema sale de la lista,
    # o la lista se queda protegiendo lo que ya no pasa (corolario 22).
    ya_no_faltan = sorted(set(MUERTAS_A_PROPOSITO) & en_el_esquema)
    assert not ya_no_faltan, (
        f"{ya_no_faltan} ya están en el esquema: sacalas de MUERTAS_A_PROPOSITO."
    )


# --- Los DOS relojes: el de la base (UTC) y el del negocio (Argentina) ---
#
# `CURRENT_DATE` es la fecha del SERVIDOR de la base, que corre en UTC, y a
# partir de las 21:00 de Argentina adelanta un día. Todo lo demás del sistema
# resuelve con la fecha argentina, así que eran dos reglas escritas para el
# mismo hecho — y la que decidía no era la que el código creía.
#
# No es una hipótesis: el 14/09 se midieron las tres tablas de historial en
# las dos bases y aparecieron CINCO tasas de un cliente, cargadas el 15/08 a
# las 22:01 de Argentina, con `vigente_desde` del 16. No rigieron el día en
# que se cargaron. Ver `db/precios_2_quienes_son_los_fechados_distinto.sql`,
# que trae el baseline confirmado en el encabezado.
#
# Estos dos tests son por el LADO DEL TEXTO del SQL a propósito (corolario
# 40): con un cursor falso la fila la entrega el mock, así que el valor
# devuelto llega igual con la fecha equivocada. Lo único que distingue un
# reloj del otro es qué PIDIÓ la consulta.
#
# Y van por PARSEO y no por una lista escrita a mano (corolario 42): una
# lista protege los lectores de hoy; el parseo protege al próximo, que es el
# que nadie va a recordar.

TABLAS_CON_VIGENCIA = (
    "precios_venta_historial",
    "envases_costo_historial",
    "clientes_parametros_historial",
    "senas_valor_historial",
)


def _sql_del_nodo(nodo):
    """El texto de un literal de SQL, sea string común o f-string.

    Un f-string en el árbol no es un Constant sino un JoinedStr, así que
    leer solo Constant deja afuera EXACTAMENTE las consultas que se
    convirtieron para interpolar el reloj — o sea, las que hay que mirar.
    De la parte interpolada devuelve el NOMBRE de la expresión
    (`_SQL_HOY_ARGENTINA`), que es lo que se quiere afirmar.
    """
    import ast

    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        partes = []
        for trozo in nodo.values:
            if isinstance(trozo, ast.Constant):
                partes.append(str(trozo.value))
            elif isinstance(trozo, ast.FormattedValue):
                partes.append(ast.unparse(trozo.value))
        return "".join(partes)
    return None


def _sql_de_las_tablas_con_vigencia():
    """Todo literal de SQL de app/db.py que nombre una tabla de historial con vigencia."""
    import ast
    import io
    import re

    arbol = ast.parse(io.open("app/db.py", encoding="utf-8").read())
    encontradas = []
    for nodo in ast.walk(arbol):
        texto = _sql_del_nodo(nodo)
        if not texto:
            continue
        # El ancla es la POSICIÓN DE TABLA, no el nombre suelto. La primera
        # versión de esto pedía que el texto dijera "INSERT" y nombrara la
        # tabla, y matcheó el docstring de guardar_precios_cliente — que
        # explica este mismo bug, así que nombra la tabla, dice "dentro del
        # INSERT" y escribe CURRENT_DATE para contar qué decía antes.
        # Corolario 38 al pie de la letra: el comentario nombra justo lo que
        # el test busca, y la colisión está garantizada por construcción.
        if not any(re.search(rf"(?:FROM|INTO|JOIN|UPDATE)\s+{tabla}\b", texto) for tabla in TABLAS_CON_VIGENCIA):
            continue
        encontradas.append(texto)
    return encontradas


def test_ninguna_consulta_de_las_tablas_con_vigencia_usa_el_reloj_del_SERVIDOR():
    consultas = _sql_de_las_tablas_con_vigencia()

    # El denominador, en la misma aserción (corolario 45): sin él, "ninguna
    # usa CURRENT_DATE" y "no se miró ninguna consulta" pasan las dos, y
    # significan lo contrario.
    assert len(consultas) >= 10, f"Se miraron solo {len(consultas)} consultas: el parseo dejó de encontrarlas."

    con_reloj_del_servidor = [sql for sql in consultas if "CURRENT_DATE" in sql]
    assert not con_reloj_del_servidor, (
        "Consultas de una tabla con vigencia que resuelven con el reloj del servidor de la base (UTC) "
        f"en vez de la hora argentina: {con_reloj_del_servidor}"
    )


def test_el_hoy_de_las_vigencias_se_pregunta_con_la_zona_NOMBRADA():
    # La otra mitad: que no haya CURRENT_DATE no prueba que se pregunte
    # bien. Un offset fijo de −3 horas también sacaría el CURRENT_DATE y no
    # se enteraría el día que el país mueva el reloj (ver core/zona.py).
    from app.db import _SQL_HOY_ARGENTINA

    assert "America/Argentina/Buenos_Aires" in _SQL_HOY_ARGENTINA
    assert "interval" not in _SQL_HOY_ARGENTINA.lower()

    preguntan_por_hoy = [sql for sql in _sql_de_las_tablas_con_vigencia() if "_SQL_HOY_ARGENTINA" in sql]
    assert len(preguntan_por_hoy) == 3, (
        "Los lectores que preguntan qué rige AHORA son tres (los totales por cliente, el detalle del "
        f"formulario y el valor de seña vigente); se encontraron {len(preguntan_por_hoy)}."
    )


def test_los_CINCO_caminos_que_fechan_una_carga_pasan_la_hora_ARGENTINA():
    """Ningún llamador de los escritores de historial se fecha con otro reloj.

    El parámetro sin default ya impide olvidarse de pasarlo — el que se
    olvide se lleva un TypeError. Lo que esto cuida es lo otro: que el
    valor que se pasa sea `_hoy_argentina()` y no un `date.today()`, que es
    el reloj del contenedor y vuelve a ser dos relojes para el mismo hecho.
    """
    import ast
    import io

    escritores = {"crear_cliente", "actualizar_cliente", "crear_envase", "registrar_costo_envase"}
    arbol = ast.parse(io.open("app/main.py", encoding="utf-8").read())

    llamadas = [
        nodo
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in escritores
    ]
    assert len(llamadas) == 5, f"Los caminos que fechan una carga eran cinco; ahora son {len(llamadas)}."

    sin_hora_argentina = [
        f"{llamada.func.id} (línea {llamada.lineno})"
        for llamada in llamadas
        if not any(ast.unparse(argumento) == "_hoy_argentina()" for argumento in llamada.args)
    ]
    assert not sin_hora_argentina, f"Caminos que no fechan con la hora argentina: {sin_hora_argentina}"


# --- Borrar una ficha no puede borrar el precio al que se facturó ---
#
# El historial de precios cuelga de la FICHA, y esa FK era `on delete set
# null`: borrar una ficha —o cambiarle el artículo, que por dentro es un
# DELETE + INSERT con id nuevo— le ponía `ficha_id` en NULL a sus precios, y
# todas las lecturas filtran `ficha_id IS NOT NULL`. El precio no se perdía:
# se DESCONECTABA, que para el sistema es lo mismo y encima no deja rastro.
#
# Medido sobre db/esquema_completo.sql el 14/09, no deducido: borrar una
# ficha con un precio cargado dejaba `precios_huerfanos 1` y ningún error.


def test_una_ficha_con_PRECIOS_no_se_borra_y_lo_dice_con_el_numero():
    # Las tres guardas de eliminar_ficha son la misma pregunta ("¿quién
    # apunta a esta ficha?"), pero ésta tapaba un agujero DISTINTO: las otras
    # dos son NO ACTION y la foreign key reventaba igual — la guarda solo
    # cambia el error crudo por un mensaje. Ésta era SET NULL y aceptaba en
    # silencio.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0,), (0,), (4,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            eliminar_ficha(901)

    assert "4 precios cargados" in str(error.value)
    assert not any("DELETE" in llamada.args[0] for llamada in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_cambiarle_el_ARTICULO_a_una_ficha_con_precios_tampoco_se_puede():
    # La segunda puerta, y no parece una puerta: desde la pantalla se ve como
    # editar. Si esta guarda falta, Eliminar queda cerrado y el historial se
    # sigue desconectando por el camino de al lado.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(1,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            cambiar_articulo_de_ficha(10, 5, "ANCO", "90200")

    assert "1 precio cargado" in str(error.value)
    # Y ofrece la salida que existe: un cliente puede tener varias fichas del
    # mismo artículo desde db/permitir_varias_fichas_por_articulo.sql.
    assert "Creá una ficha nueva" in str(error.value)
    assert not any("DELETE" in llamada.args[0] for llamada in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_la_guarda_de_precios_es_UNA_sola_y_las_dos_puertas_llaman_A_ESA():
    """Las dos puertas preguntan por la MISMA función, no cada una por su cuenta.

    Escrita dos veces se separa, y la copia que quede vieja sigue
    desconectando precios sin que nada avise — que es el modo de falla que
    esto viene a cerrar. Va por PARSEO y no por una lista escrita a mano
    (corolario 42): la lista protege las dos puertas de hoy; el parseo
    protege la tercera, que es la que nadie va a recordar.

    Y busca una LLAMADA en el árbol, no el nombre en el texto. La primera
    versión preguntaba `"_negar_si_tiene_precios" in ast.unparse(nodo)` y el
    canario que reemplaza la llamada por una condición propia NO la hacía
    caer: el docstring de cambiar_articulo_de_ficha NOMBRA la guarda para
    explicar por qué está, así que el texto seguía ahí con la llamada
    sacada. Corolario 59 sin salir del mismo turno — un comentario explica
    por qué algo es así, o sea que nombra la cosa, y el test busca la cosa.
    La posición gramatical del 59 acá es literal: un nodo Call, no una
    palabra adentro de una cadena.
    """
    import ast
    import io

    arbol = ast.parse(io.open("app/db.py", encoding="utf-8").read())

    def llama_a_la_guarda(nodo) -> bool:
        return any(
            isinstance(hijo, ast.Call)
            and isinstance(hijo.func, ast.Name)
            and hijo.func.id == "_negar_si_tiene_precios"
            for hijo in ast.walk(nodo)
        )

    puertas = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.FunctionDef):
            continue
        if "DELETE FROM fichas_logistica" in ast.unparse(nodo):
            puertas[nodo.name] = llama_a_la_guarda(nodo)

    # El denominador, en la misma aserción (corolario 45): sin él, "ninguna
    # puerta sin guarda" y "no se encontró ninguna puerta" pasan las dos.
    assert len(puertas) == 2, f"Las puertas que borran una ficha eran dos; ahora son {sorted(puertas)}."

    sin_guarda = sorted(nombre for nombre, tiene in puertas.items() if not tiene)
    assert not sin_guarda, f"Puertas que borran una ficha sin preguntar por sus precios: {sin_guarda}"


def test_la_guarda_cuenta_los_precios_DE_ESA_FICHA_y_no_los_del_cliente():
    # Por el TEXTO del SQL y no por el valor (corolario 40): con un cursor
    # falso el conteo lo entrega el mock, así que un `WHERE cliente_id = %s`
    # devolvería el mismo 4 y el test no vería nada.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0,), (0,), (4,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError):
            eliminar_ficha(901)

    consulta, parametros = cursor.execute.call_args_list[-1].args
    assert "FROM precios_venta_historial" in consulta
    assert "WHERE ficha_id = %s" in consulta
    assert parametros == (901,)


def test_el_ON_DELETE_de_las_FK_a_fichas_esta_DECIDIDO_una_por_una():
    """Qué pasa con lo que apunta a una ficha cuando la ficha se borra.

    El test de arriba cuida las COLUMNAS que agrega una migración y no ve
    esto: cambiar un `on delete` no agrega ninguna columna, así que la
    migración del 14/09 corrió en las dos bases y el esquema del repo se
    quedó diciendo `set null` sin que nada cayera. Una base nueva —la
    empresa siguiente— habría nacido con el bug ya adentro.

    Las SIETE están enumeradas juntas a propósito, la deliberada incluida:
    separarlas es cómo se olvida la octava, y dejar afuera la que SÍ va en
    SET NULL es cómo alguien le copia el arreglo a las otras creyendo que
    faltaba. Buscar la otra copia es obligatorio; copiarle el arreglo, no.

    Y siete es el número que dijo el test, no el que yo conté: la primera
    versión listaba CUATRO, que eran las que había mirado al arreglar los
    precios. Las otras tres estaban bien desde antes y no se nombraban en
    ningún lado junto a éstas — o sea que la lista escrita de memoria ya
    nacía incompleta, que es exactamente lo que un test con denominador
    encuentra y una lectura no.
    """
    import io
    import re

    # Sin los comentarios. El renglón de precios_venta_historial lleva arriba
    # uno que EXPLICA por qué no va en SET NULL, así que dice "on delete set
    # null" en prosa a cinco líneas del `references` — corolario 59 por
    # tercera vez en el turno.
    #
    # MEDIDO, y el resultado corrige la intuición: con el comentario tal como
    # está hoy, sacar el descarte NO hace caer nada, porque el parseo pide
    # las dos cosas EN EL MISMO RENGLÓN y esa prosa no dice "references
    # fichas_logistica". O sea que el ancla de verdad es el renglón, no el
    # descarte. Pero plantando el comentario que alguien escribiría de
    # verdad —`-- antes: ficha_id bigint references fichas_logistica (id) on
    # delete set null`, que es cómo se anota un cambio— con descarte pasa y
    # sin descarte CAE. Se queda por eso, no por si acaso.
    esquema = io.open("db/esquema_completo.sql", encoding="utf-8").read()
    sin_comentarios = "\n".join(
        linea for linea in esquema.splitlines() if not linea.lstrip().startswith("--")
    )

    # El motivo de cada una sale de su comentario en el esquema, no de acá:
    # esta lista dice QUÉ se decidió, y el esquema POR QUÉ.
    NO_SE_NULEAN = {
        # El NULL significa "sin asignar": nulear volvería un reproceso
        # asignado indistinguible de uno que el operario dejó sin asignar.
        "reprocesos",
        # Una compra que viene armada quedaría apuntando a la nada.
        "compras",
        # El precio al que se facturó (14/09). Era la única en SET NULL.
        "precios_venta_historial",
        # Acá el NULL ya significa otra cosa —"los sueltos"—, así que nulear
        # convertiría un conteo de cajas en uno de sueltos.
        "conteos_stock",
        # FK COMPUESTA (ficha_id, articulo_id): una merma dice artículo Y
        # ficha, y una ficha de otro artículo ensuciaría la cuenta por ficha.
        "movimientos_stock",
        # NOT NULL: es el respaldo que hace posible deshacer el corte.
        "corte_respaldo_fichas_reprocesos",
    }
    # Ésta SÍ va en SET NULL, y es a propósito: un renglón viejo describe una
    # entrega que ya pasó y nadie la consulta hacia atrás POR FICHA.
    SE_NULEAN = {"pedidos_renglones"}

    bloques = re.findall(r"create table (\w+) \((.*?)\n\);", sin_comentarios, re.S)
    en_set_null, en_no_action = set(), set()
    for tabla, cuerpo in bloques:
        for renglon in cuerpo.splitlines():
            if not re.search(r"references fichas_logistica\b", renglon):
                continue
            (en_set_null if "on delete set null" in renglon else en_no_action).add(tabla)

    # El denominador (corolario 45): sin esto, "ninguna quedó mal" y "el regex
    # no encontró ninguna FK" se leen igual.
    encontradas = en_set_null | en_no_action
    assert encontradas == NO_SE_NULEAN | SE_NULEAN, (
        f"Las FK a fichas_logistica cambiaron: se encontraron {sorted(encontradas)}, "
        f"y las decididas son {sorted(NO_SE_NULEAN | SE_NULEAN)}. Decidí la nueva, no borres la lista."
    )

    se_nulean_y_no_deberian = sorted(en_set_null & NO_SE_NULEAN)
    assert not se_nulean_y_no_deberian, (
        "Borrar una ficha las dejaría en NULL en silencio: " f"{se_nulean_y_no_deberian}"
    )
    dejaron_de_nulearse = sorted(SE_NULEAN - en_set_null)
    assert not dejaron_de_nulearse, (
        "Éstas van en SET NULL a propósito y alguien les copió el arreglo de las otras: "
        f"{dejaron_de_nulearse}"
    )


def _sql_de_la_funcion(nombre_funcion):
    """El SQL que una función de app/db.py le pide a la base, SIN comentarios.

    Sin sacar los `--`, el assert matchea la prosa que explica la columna en
    vez de la columna: un comentario de SQL existe para NOMBRAR la cosa que
    el test busca, así que la colisión está garantizada por construcción
    (corolario 59).
    """
    import ast
    import io
    import re

    arbol = ast.parse(io.open("app/db.py", encoding="utf-8").read())
    funcion = next(
        (n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == nombre_funcion),
        None,
    )
    assert funcion is not None, f"no existe la función {nombre_funcion}"
    literales = [
        texto
        for nodo in ast.walk(funcion)
        if (texto := _sql_del_nodo(nodo)) and "SELECT" in texto.upper()
    ]
    assert literales, f"{nombre_funcion} no tiene ninguna consulta: el barrido mira lo que no es"
    sin_comentarios = " ".join(
        linea.split("--")[0] for texto in literales for linea in texto.splitlines()
    )
    return re.sub(r"\s+", " ", sin_comentarios)


def test_la_ficha_TRAE_la_unidad_de_compra_del_articulo():
    """Lo que decide si el costeo se puede negar, y ningún test de costeo lo ve.

    `magnitud_de_la_ficha` lee `ficha["unidad_conteo"]`, y todos los tests
    de app/costeo.py le pasan fichas de fixture — así que el valor lo pone el
    fixture, no la consulta. Medido con un canario el 15/09: sacar la columna
    del SELECT hace caer CERO tests.

    Y el modo de falla es el peor: sin la columna,
    `ficha.get("unidad_conteo")` devuelve None, la regla contesta "esta ficha
    no se puede costear" para TODA ficha que no venda por kilo, y el sistema
    se niega en silencio donde antes costeaba bien. Es la degradación
    permanente, con el agravante de que acá ni siquiera hay un `except` que
    la explique.

    Por eso este test mira el TEXTO de la consulta y no un valor (corolario
    40): lo que cambia es QUÉ COLUMNA se pide.
    """
    consulta = _sql_de_la_funcion("listar_fichas_por_cliente")
    assert "a.unidad_conteo" in consulta
    # Calificada con el alias del artículo, no suelta: `fichas_logistica` no
    # tiene esa columna, así que sin el alias el assert podría pasar sobre
    # una consulta que la pide de la tabla equivocada (corolario 4).
    assert "unidad_conteo" not in consulta.replace("a.unidad_conteo", "")


def test_el_detalle_de_la_alerta_TRAE_el_conteo_QUE_DECLARA_el_articulo():
    """La columna que separa "cargale el conteo" de "ya cuenta en otra unidad".

    Mismo caso que la de arriba y mismo canario en cero: el detalle se prueba
    con `listar_unidades_que_diferen` mockeada, así que el valor lo entrega el
    fixture. Si la consulta deja de traerlo, el detalle diría "al artículo le
    falta el conteo" para TODOS —incluido el que ya cuenta en otra unidad y
    donde cargarlo no alcanza— sin un solo test en rojo.
    """
    consulta = _sql_de_la_funcion("listar_unidades_que_diferen")
    assert "a.unidad_conteo" in consulta


# --- LAS DOS MAGNITUDES EN LA RECEPCIÓN (15/09) ------------------------------

def test_recepcionar_con_las_DOS_magnitudes_deriva_los_DOS_totales():
    """Depósito pesa Y cuenta un bulto, y los dos totales salen de los cajones REALES.

    3 fetchone: la consulta que trae unidad_compra y las dos cantidades de la
    compra, el estado_retiro de _auto_retirar_si_corresponde, y la marca
    "viene armada".
    """
    conexion, cursor = _conexion_falsa(
        [("unidad", 160.0, 100.0), ("pendiente",), (1, None, 10.0, date(2026, 8, 25), None, None)]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(30, cantidad_cajones_real=10, valor_real=9, segunda_real=15)

    _, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    cajones, contenido, kilos, fraccion, segunda_cajon, _, _, _ = parametros
    assert cajones == 10
    assert contenido == 9, "contenido_por_cajon_real es el de unidad_compra, directo"
    assert fraccion == 90, "10 × 9 unidades"
    assert kilos == 150, "10 × 15 kilos: la segunda magnitud, por su propio camino"


def test_la_recepcion_SE_NIEGA_si_la_compra_declaro_las_dos_y_llega_una():
    """La guarda va donde se ESCRIBE, no en la pantalla.

    Sin esto la asimetría sería invisible: el costeo lee cada magnitud con
    COALESCE(real, estimado), así que con el kilo pesado y el conteo sin
    pesar, dos fichas del MISMO artículo costearían una contra lo pesado y la
    otra contra lo estimado, en la misma compra y sin que nada se descuadre.
    """
    conexion, cursor = _conexion_falsa([("unidad", 160.0, 100.0)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            recepcionar_compra(30, cantidad_cajones_real=10, valor_real=9)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert "las dos magnitudes" in str(error)

    conexion.commit.assert_not_called()


def test_la_recepcion_NO_pide_la_segunda_si_la_compra_trajo_UNA():
    """El control de la de arriba, y es el caso de todas las compras viejas.

    Pedirle a Depósito la magnitud que la compra no declaró es pedirle que
    invente. Sin este control, una guarda que abortara siempre pasaría el
    test de arriba igual (corolario 30: el caso feliz es el único que
    distingue "la guarda funciona" de "la guarda siempre frena").
    """
    conexion, cursor = _conexion_falsa(
        [("kilo", 760.0, None), ("pendiente",), (1, None, 38.0, date(2026, 8, 25), None, None)]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(30, cantidad_cajones_real=38, valor_real=20)

    _, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    _, _, kilos, fraccion, segunda_cajon, _, _, _ = parametros
    assert kilos == 760
    assert fraccion is None, "la que la compra no declaró queda en None, no en cero"


def test_la_recepcion_LEE_las_dos_cantidades_en_la_MISMA_consulta_que_la_unidad():
    """Lo que cambia es QUÉ COLUMNAS pide la consulta, así que el test lee el SQL.

    El valor lo entrega el cursor falso (corolario 40): con la consulta
    pidiendo solo `unidad_compra`, el fixture seguiría entregando la tupla de
    tres y el test del valor pasaría igual. Y sin esas dos columnas la guarda
    de arriba no puede disparar nunca — se apaga entera y en silencio.
    """
    consulta = _sql_de_la_funcion("_recepcionar_compra")
    assert "c.cantidad_kilos" in consulta
    assert "c.cantidad_fraccion" in consulta

    corregir = _sql_de_la_funcion("corregir_recepcion_compra")
    assert "c.cantidad_kilos" in corregir
    assert "c.cantidad_fraccion" in corregir


def test_el_costeo_TRAE_las_dos_magnitudes_de_cada_compra():
    """Otra vez el corolario 40, y acá apaga media función.

    Sin `cantidad_fraccion`, `_total_de_la_compra` devuelve None para toda
    ficha que venda en el conteo del artículo, el costeo se niega para todas
    ellas y NADA avisa: se ve igual que una compra vieja. Los tests de
    app/costeo.py no lo pueden ver — le pasan las compras de un fixture.
    """
    consulta = _sql_de_la_funcion("listar_compras_para_costeo")
    assert "c.cantidad_fraccion_real, c.cantidad_fraccion" in consulta.replace("COALESCE(", "")
    assert "AS cantidad_fraccion" in consulta


def test_un_articulo_NUEVO_nace_con_la_unidad_del_contenido_en_KILO():
    """Y no en NULL, aunque el código trate el nulo como kilo.

    La diferencia se ve en una pantalla: `SUFIJOS_UNIDAD_COMPRA.get(None, "")`
    devuelve cadena vacía, así que las compras de un artículo con la columna
    en NULL saldrían "41 cajones × 16" —sin la "k"— en Buscar Compras, en
    Movimientos y en el detalle. El sufijo es lo único que dice en qué está
    expresado ese número.

    Lo encontró un canario: poner la constante en None no hacía caer nada.

    LA FILA FALSA ES EL ID QUE DEVUELVE EL `RETURNING`: `crear_articulo`
    devuelve el id desde el 23/09 —la revisión del archivo da de alta un
    artículo y tiene que dejarlo ELEGIDO en su renglón— así que el cursor
    tiene que tener algo que entregar. Con la lista vacía el `fetchone()`
    corta la función antes del commit.
    """
    conexion, cursor = _conexion_falsa([(77,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        assert crear_articulo("EJEMPLO Uno", 16.0, "fruta", "unidad") == 77

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "INSERT INTO articulos")
    assert "RETURNING id" in consulta, "sin esto el alta no puede dejar el artículo elegido"
    assert "unidad_compra" in consulta
    nombre, unidad_compra, unidad_conteo, referencia, grupo = parametros
    assert unidad_compra == "kilo", "el contenido por cajón de un artículo nuevo se carga en kilos"
    assert unidad_conteo == "unidad", "y lo que además cuenta lo dice la otra columna"


# LA COHERENCIA ENTRE EL CONTEO DECLARADO Y LA UNIDAD DE LA HISTORIA.
#
# Hoy dispara CERO en las dos bases: los cuatro artículos contados tienen el
# conteo copiado de `unidad_compra` por la migración. Se arregla justo por
# eso — un aviso que propone romper, o una guarda que falta, cuestan gratis
# mientras no haya un caso y cuestan el caso roto después (corolario 64).


def test_declarar_un_conteo_que_CONTRADICE_la_unidad_de_compra_se_RECHAZA():
    """Y el daño que evita no se ve en ninguna pantalla: sale un costo mal.

    El `contenido_por_cajon` de todas las compras viejas de un artículo
    contado está expresado en `unidad_compra`, y `repartir_magnitudes` lo
    manda a `cantidad_fraccion`. Con el conteo declarado en OTRA unidad, una
    ficha que venda en esa otra unidad divide la plata por ese mismo número:
    cuarenta unidades leídas como cuarenta cubetas. No se descuadra nada, no
    hay error, y el costo sale mal.
    """
    conexion, cursor = _conexion_falsa([("unidad",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as error:
            actualizar_articulo(7, "EJEMPLO Uno", 16.0, "fruta", "cubeta")

    assert "unidad" in str(error.value) and "cubeta" in str(error.value)

    # Y NO ESCRIBIÓ. Que levante no alcanza: si el UPDATE ya corrió, el
    # `raise` llega tarde y lo único que cambia es el mensaje.
    escrituras = [ll for ll in cursor.execute.call_args_list if "UPDATE articulos" in ll.args[0]]
    assert escrituras == []
    conexion.commit.assert_not_called()


def test_el_MISMO_conteo_que_la_unidad_de_compra_ENTRA():
    """El control, y es el que distingue "la guarda funciona" de "la guarda siempre frena".

    Una batería de casos negativos sale toda en verde con una guarda que
    aborta siempre (corolario 30): el caso feliz es el único que los separa.
    """
    conexion, cursor = _conexion_falsa([("unidad",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_articulo(7, "EJEMPLO Uno", 16.0, "fruta", "unidad")

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE articulos")
    assert parametros[1] == "unidad"
    conexion.commit.assert_called_once()


def test_el_conteo_VACIO_en_un_articulo_contado_ENTRA_porque_NO_MIENTE():
    """Deliberado, y es la mitad que la guarda NO cubre.

    Sacarle el conteo a un artículo contado no ensucia ningún número: deja a
    sus fichas sin costear, y eso SE VE en la pantalla como negativa. Trabar
    acá sería trabar el caso que se degrada de frente, y dejaría a los cuatro
    artículos contados sin forma de volver atrás nunca.
    """
    conexion, cursor = _conexion_falsa([("unidad",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_articulo(7, "EJEMPLO Uno", 16.0, "fruta", None)

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE articulos")
    assert parametros[1] is None


@pytest.mark.parametrize("unidad_compra", ["kilo", None])
def test_un_articulo_cuya_historia_esta_en_KILOS_puede_declarar_CUALQUIER_conteo(unidad_compra):
    """Los dos valores son lo mismo: el nulo significa kilo desde el 15/09.

    Acá no hay nada que contradecir —el `contenido_por_cajon` está en kilos y
    el conteo es una magnitud aparte— así que la guarda no tiene por qué
    opinar. Es la mayoría del catálogo: trabarlos sería trabar el caso normal.
    """
    conexion, cursor = _conexion_falsa([(unidad_compra,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_articulo(7, "EJEMPLO Uno", 16.0, "fruta", "cubeta")

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE articulos")
    assert parametros[1] == "cubeta"


def test_el_FORMATO_del_codigo_de_puesto_de_Python_y_el_de_la_BASE_son_LA_MISMA_regla():
    """Escrito dos veces: `REGEX_CODIGO_PUESTO` y el check de la columna.

    Hoy son idénticos, y por eso se ata ahora: separadas, la que rechaza deja
    de ser la que el código cree que rechaza. Cada dirección falla distinto —
    si Python acepta algo que la base niega, la pantalla ofrece cargar un
    código que revienta al guardar; si la base acepta algo que Python niega,
    un INSERT a mano mete un código que las pantallas no dejan tipear y nadie
    puede corregir (el código es la identidad y no se edita).

    El patrón se LEE del .sql — copiado acá envejece en silencio — y se
    compara sobre casos, no como texto: dos expresiones distintas pueden
    aceptar lo mismo, y lo que importa es a quién dejan pasar.
    """
    import re

    esquema = io.open("db/esquema_completo.sql", encoding="utf-8").read()
    escrito = re.search(r"codigo_puesto[^,]*?check\s*\(\s*codigo_puesto\s*~\s*'([^']+)'", esquema)
    assert escrito, "no está el check del formato en el esquema"
    de_la_base = re.compile(escrito.group(1))

    CASOS = [
        "N07P41", "L03P38", "N00P00", "L99P99",          # los buenos
        "", "7P41", "N7P41", "N07P4", "N07P411",         # largo y forma
        "X07P41", "n07p41", "N07Q41", "N07P4A",          # letra, caja, separador
        " N07P41", "N07P41 ", "N07P41\n", "AN07P41",     # bordes y espacios
    ]
    discrepancias = [
        (c, bool(de_la_base.match(c)), bool(REGEX_CODIGO_PUESTO.match(c)))
        for c in CASOS
        if bool(de_la_base.match(c)) != bool(REGEX_CODIGO_PUESTO.match(c))
    ]
    assert not discrepancias, f"los dos formatos se separaron: {discrepancias}"

    # Y que los casos ejerciten LAS DOS respuestas: si todos fueran malos, dos
    # patrones cualesquiera que rechacen todo coincidirían (corolario 53).
    aceptados = [c for c in CASOS if REGEX_CODIGO_PUESTO.match(c)]
    assert 0 < len(aceptados) < len(CASOS), "los casos no ejercitan las dos respuestas"


# Las consultas que alimentan las pantallas donde se muestran las dos
# magnitudes del cajón. La lista es lo DECIDIDO; el test la compara contra lo
# que encuentra, en los dos sentidos (corolario 60).
CONSULTAS_QUE_MUESTRAN_LAS_DOS_MAGNITUDES = {
    "obtener_detalle_compra": "Detalle de la compra (comprado y recepcionado)",
    "listar_compras_sin_precio": "Compras pendientes de precio",
    "buscar_ingresos_deposito": "Ingresos a Depósito",
    "listar_compras_procesadas_hoy_retiro": "Retiro, lo procesado hoy",
    "listar_compras_pendientes_retiro": "Retiro, lo pendiente",
    "buscar_compras": "Buscar compras",
}


# Y QUÉ CONSULTAS alimentan a cada pantalla. Emparejadas y no contadas: el
# conteo suponía UNA consulta por pantalla y la relación es N a N en las dos
# direcciones — tres pantallas leen `obtener_detalle_compra`, y Retiro dibuja
# dos listas con dos consultas distintas.
PANTALLAS_QUE_MUESTRAN_LAS_DOS_MAGNITUDES = {
    "templates/administracion_ingresos.html": ("buscar_ingresos_deposito",),
    "templates/compra_corregir_recepcion.html": ("obtener_detalle_compra",),
    "templates/compra_detalle.html": ("obtener_detalle_compra",),
    "templates/compra_editar_gerencia.html": ("obtener_detalle_compra",),
    "templates/compras_buscar.html": ("buscar_compras",),
    "templates/compras_pendientes.html": ("listar_compras_sin_precio",),
    "templates/logistica_retiro.html": (
        "listar_compras_pendientes_retiro",
        "listar_compras_procesadas_hoy_retiro",
    ),
}


@pytest.mark.parametrize("nombre", sorted(CONSULTAS_QUE_MUESTRAN_LAS_DOS_MAGNITUDES))
def test_las_consultas_del_CAJON_traen_LAS_DOS_magnitudes_y_el_conteo(nombre):
    """Lo que cambia es QUÉ COLUMNAS pide la consulta, así que el test lee el SQL.

    El valor lo entrega el mock (corolario 40/65): medido con un canario, sacar
    `a.unidad_conteo` de la consulta del detalle hace caer CERO tests. Y el modo
    de falla es mudo — sin el conteo, el macro no puede NOMBRAR la magnitud que
    falta, así que el hueco no se dibuja y la pantalla vuelve a mostrar una sola
    magnitud, que es exactamente lo que se veía antes.

    `unidad_conteo` hace falta aunque la cuenta no lo use: no decide el número,
    decide si hay algo que declarar. Sin él, "sin kilos declarados" y "este
    artículo no cuenta nada" son la misma pantalla.
    """
    consulta = _sql_de_la_funcion(nombre)
    faltan = [c for c in ("a.unidad_compra", "a.unidad_conteo",
                          "cantidad_kilos", "cantidad_fraccion")
              if c not in consulta]
    assert not faltan, f"{CONSULTAS_QUE_MUESTRAN_LAS_DOS_MAGNITUDES[nombre]}: faltan {faltan}"


def test_NINGUNA_pantalla_del_cajon_quedo_afuera_de_esa_lista():
    """El otro sentido: una pantalla que muestre el macro y no esté en la lista.

    Recorrer solo la lista propia confirma lo que uno ya sabía. Esto busca a
    los que USAN el macro y exige que su consulta esté decidida — si mañana
    una séptima pantalla lo importa, el test la nombra en vez de dejarla con
    una sola magnitud en silencio.
    """
    import glob

    usan = sorted(
        ruta for ruta in glob.glob("templates/*.html")
        if "magnitudes_del_cajon(" in io.open(ruta, encoding="utf-8").read()
        and not ruta.endswith("_magnitudes_del_cajon.html")
    )
    assert usan, "nadie usa el macro: el test no está mirando nada"
    # LA PANTALLA SE EMPAREJA CON SU CONSULTA, y no se cuentan las dos listas.
    # El conteo asumía UNA consulta por pantalla, y eso dejó de ser cierto el
    # 19/09: Mover de fecha lee `obtener_detalle_compra`, la misma que el
    # Detalle. Emparejado, el test sigue fallando cuando aparece una pantalla
    # que nadie decidió Y cuando una consulta de la lista se queda sin
    # pantalla — que es lo que el conteo pretendía cuidar.
    assert set(PANTALLAS_QUE_MUESTRAN_LAS_DOS_MAGNITUDES) == set(usan), (
        f"cambiaron las pantallas que muestran el macro: {usan}"
    )
    alimentan = {c for consultas in PANTALLAS_QUE_MUESTRAN_LAS_DOS_MAGNITUDES.values()
                 for c in consultas}
    assert alimentan == set(CONSULTAS_QUE_MUESTRAN_LAS_DOS_MAGNITUDES), (
        "hay una consulta decidida que ya no alimenta ninguna pantalla, o al revés"
    )


def test_la_guarda_de_PYTHON_y_el_CHECK_son_LA_MISMA_regla():
    """Las dos rechazan lo mismo, y el test LEE el CHECK del .sql en vez de copiarlo.

    Copiado envejece en silencio: el día que alguien afloje una de las dos, la
    otra sigue diciendo lo que decía y el que rechaza deja de ser el que el
    código cree que rechaza. Es el caso de "ruben" al lado de "Rubén" —dos
    plegados escritos dos veces— con otra columna.

    Se compara en los DOS sentidos sobre la matriz entera, y cada dirección
    falla distinto: si la base acepta algo que Python niega, un UPDATE a mano
    entra y el costeo miente; si Python acepta algo que la base niega, la
    pantalla ofrece algo que revienta al guardar.

    Y las cláusulas del CHECK se RECONOCEN una por una: si aparece una que este
    test no sabe traducir, falla nombrándola en vez de ignorarla — un barrido
    que saltea lo que no entiende solo puede confirmar lo que ya sabía.
    """
    import re

    esquema = io.open("db/esquema_completo.sql", encoding="utf-8").read()
    cuerpo = re.search(
        r"constraint\s+articulos_conteo_coherente\s+check\s*\((.*?)\)\s*\n\s*\);",
        esquema, re.S)
    assert cuerpo, "no está el CHECK en el esquema: la migración no se reflejó (corolario 60)"

    # Las líneas de comentario del `check` no son condiciones.
    texto = " ".join(l.split("--")[0] for l in cuerpo.group(1).splitlines())
    clausulas = [re.sub(r"\s+", " ", c).strip().lower() for c in texto.split(" or ")]
    clausulas = [c for c in clausulas if c]

    TRADUCCION = {
        "coalesce(unidad_compra, 'kilo') = 'kilo'": lambda uc, ucon: (uc or "kilo") == "kilo",
        "unidad_conteo is null": lambda uc, ucon: ucon is None,
        "unidad_conteo = unidad_compra": lambda uc, ucon: uc is not None and ucon == uc,
    }
    desconocidas = [c for c in clausulas if c not in TRADUCCION]
    assert not desconocidas, f"el CHECK tiene condiciones que este test no sabe leer: {desconocidas}"
    assert len(clausulas) == 3, f"el CHECK cambió de forma: {clausulas}"

    def la_base_acepta(uc, ucon):
        return any(TRADUCCION[c](uc, ucon) for c in clausulas)

    def python_acepta(uc, ucon):
        try:
            _negar_si_el_conteo_contradice_la_unidad_de_compra(uc, ucon)
            return True
        except ValueError:
            return False

    matriz = [
        (uc, ucon)
        for uc in (None, "kilo", "unidad", "cubeta")
        for ucon in (None, "unidad", "cubeta")
    ]
    discrepancias = [
        (uc, ucon, la_base_acepta(uc, ucon), python_acepta(uc, ucon))
        for uc, ucon in matriz
        if la_base_acepta(uc, ucon) != python_acepta(uc, ucon)
    ]
    assert not discrepancias, f"las dos reglas se separaron: {discrepancias}"

    # Y que la matriz tenga los dos resultados: si todo diera aceptado, las dos
    # coincidirían sin que ninguna rechace nada (corolario 53).
    aceptados = [1 for uc, ucon in matriz if la_base_acepta(uc, ucon)]
    assert 0 < len(aceptados) < len(matriz), "la matriz no ejercita las dos respuestas"


def test_la_guarda_del_conteo_LEE_la_unidad_de_compra_EN_LA_MISMA_TRANSACCION():
    """Lo que cambia es QUÉ pide la consulta, así que el test mira el TEXTO.

    El valor lo entrega el cursor falso (corolario 40/65): con el SELECT
    sacado, el fixture seguiría entregando la tupla y los tests de arriba
    pasarían igual — la guarda quedaría apagada para TODOS los artículos, en
    producción, sin un solo test en rojo y sin nada raro en la pantalla.

    Y el `FOR UPDATE` no es de adorno: sin él la fila puede cambiar entre la
    lectura y el UPDATE, que es la ventana que la guarda viene a cerrar.
    """
    consulta = _sql_de_la_funcion("actualizar_articulo")
    assert "unidad_compra" in consulta
    assert "FROM articulos" in consulta
    assert "FOR UPDATE" in consulta


def test_el_rojo_A_SU_FECHA_le_PIDE_el_saldo_a_sql_sumas_stock_y_no_lo_reescribe():
    """La cuenta del stock se REUSA, no se vuelve a escribir. Es el corolario 85.

    La primera versión de esta medición tenía DOS de las seis patas —compras y
    armados— y dio 192 días-artículo en rojo sobre 446. El número real es 45:
    sin `reingresos`, `ajustes` y el reproceso, todo artículo que se mueve por
    guía R sale rojo todos los días.

    Por eso el test no pregunta por el resultado —un mock se lo entregaría
    igual (corolario 65)— sino por la ESTRUCTURA: que haya una llamada a
    `_sql_sumas_stock` en el cuerpo, y que las dos consultas propias de la
    función NO nombren las tablas de las patas. Si alguien reescribe la cuenta
    acá, tiene que escribir `reprocesos` o `movimientos_stock` en alguna de las
    dos, y ahí cae.
    """
    import ast as _ast

    arbol = _ast.parse(io.open("app/db.py", encoding="utf-8").read())
    funcion = next(n for n in _ast.walk(arbol)
                   if isinstance(n, _ast.FunctionDef) and n.name == "dias_articulo_en_rojo")
    llamadas = {n.func.id for n in _ast.walk(funcion)
                if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)}
    assert "_sql_sumas_stock" in llamadas, (
        "la cuenta del stock tiene que salir de _sql_sumas_stock, no escribirse de nuevo")

    from app.db import _SELECT_SALDO_POR_ARTICULO, _SQL_ARMADOS_DESDE
    propias = (_SELECT_SALDO_POR_ARTICULO + _SQL_ARMADOS_DESDE).lower()
    for tabla in ("reprocesos", "movimientos_stock", "from compras"):
        assert tabla not in propias, f"{tabla} sale de _sql_sumas_stock, no de acá"


def test_un_armado_de_CERO_no_es_un_dia_en_rojo():
    """El renglón armado en cero existe y no sacó un bulto, así que no cuenta.

    El confirmar guarda los renglones sin cantidad igual —"nada del mail se
    pierde"— así que un artículo puede tener renglones en cero muchos días. Sin
    este filtro, un artículo que quedó descubierto suma un caso por cada uno de
    esos días y el número crece sin que pase nada nuevo. Medido contra el
    esquema real: 4 casos con el filtro sacado, 2 con él puesto.

    Va como test del TEXTO y no del resultado porque el filtro vive en el SQL:
    con un cursor falso la fila la entrega el mock y el HAVING no se ejercita
    (corolario 65).
    """
    from app.db import _SQL_ARMADOS_DESDE

    assert "HAVING SUM(COALESCE(r.cantidad_armada, r.cantidad)) > 0" in _SQL_ARMADOS_DESDE


def test_el_rojo_a_su_fecha_solo_mira_los_pedidos_VIGENTES():
    """Un pedido RECARGADO no se anula: deja de ser el vigente.

    Sin la regla de vigentes, el mismo armado se cuenta dos veces —una por el
    pedido viejo y otra por el nuevo— y el día sale en rojo por un faltante que
    no existe. Verificado plantando un pedido recargado: la regla vigentes ve 1
    armado y `anulado_el IS NULL` a secas ve 2.
    """
    from app.db import _SQL_ARMADOS_DESDE

    assert "DISTINCT ON (cliente_id, fecha_operacion)" in _SQL_ARMADOS_DESDE
    assert "ORDER BY cliente_id, fecha_operacion, creado_en DESC" in _SQL_ARMADOS_DESDE


def test_el_rojo_a_su_fecha_NUNCA_mira_mas_atras_que_el_CORTE():
    """El piso se clampea contra el corte, y hoy la ventana de siete días no lo alcanza.

    Está puesto igual porque siete es una constante que alguien va a querer
    mover, y el día que la mueva más atrás del corte esto empieza a contar
    ARTEFACTOS sin que nada avise: `corte2_frutamax.sql` fecha los
    `stock_inicial` en `fecha_operacion = corte`, así que todo armado anterior
    al corte queda descubierto por construcción y no porque haya faltado algo.
    Medido con el caso plantado: un artículo cuya única entrada es su stock
    inicial, con un armado el 29/08, sale rojo por 40 bultos.

    LOS DOS CASOS, porque uno solo no distingue un clamp de un no-clamp: con
    la ventana CORTA gana la ventana (el clamp no tiene que hacer nada) y con
    la ventana LARGA gana el corte. Un `piso = corte + 1` a secas pasaría el
    segundo y rompería el primero; un `piso = desde` pasaría el primero y no
    el segundo.

    Y `corte + 1` y no `corte`: la foto del corte se toma a la tarde, así que
    ya viene neta del trabajo de ese día (corolario 12).
    """
    from datetime import date

    import app.db as db

    CORTE = date(2026, 9, 5)
    pedidos = []

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, consulta, parametros=None):
            if "corte_modelo" in consulta:
                self.fila = (CORTE,)
                self.filas = [(CORTE,)]
            else:
                pedidos.append(parametros[0])
                self.filas = []

        def fetchone(self):
            return self.fila

        def fetchall(self):
            return self.filas

    with patch.object(db, "obtener_conexion") as conexion:
        conexion.return_value.cursor.return_value = _Cursor()
        db.dias_articulo_en_rojo(date(2026, 9, 12))    # ventana corta: gana ella
        db.dias_articulo_en_rojo(date(2026, 7, 1))     # ventana larga: gana el corte

    assert pedidos == [date(2026, 9, 12), date(2026, 9, 6)], (
        f"el piso tiene que ser el MÁS NUEVO entre la ventana y corte+1, y fue {pedidos}")


# ── Mover la fecha de una guía R ya cargada ────────────────────────────────
#
# Del 19/09, y es del dueño: "el error es fechar la guía el día que se carga
# en vez del día que se armó, y la única salida hoy es anular y recargar. Es
# la tercera vez esta semana que algo se arregla así".
#
# Las guardas NO son propias: son las mismas que rebotan al cargar, porque la
# pregunta es la misma —"¿habría entrado ese día?"— y viven en
# `_lotes_de_reproceso_a_su_fecha`. Lo único que esta función agrega es la
# revisión LOTE POR LOTE de los consumos congelados, que es el caso que el
# freno del total no puede ver.

_GUIA_NORMAL = (1, date(2026, 9, 18), 10.0, "normal", None)


def _mover_fecha(reproceso_id, fecha_nueva, *, guia=_GUIA_NORMAL, corte=date(2026, 8, 15),
                 entradas=None, salidas=None, tomado_hoy=None, consumos=None):
    """Las CUATRO lecturas en orden: entradas, salidas, lo tomado ese día y los consumos.

    Medido corriendo la función, no leído: el orden de los `fetchall` es el
    de las consultas que emite, y un fixture que los ponga al revés prueba
    otra cosa con números plausibles.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[guia, (corte,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        entradas if entradas is not None else [],
        salidas if salidas is not None else [],
        tomado_hoy if tomado_hoy is not None else [],
        consumos if consumos is not None else [],
    ]
    with patch("app.db.obtener_conexion", return_value=conexion):
        from app.db import cambiar_fecha_de_reproceso
        try:
            return conexion, cursor, cambiar_fecha_de_reproceso(reproceso_id, fecha_nueva), None
        except Exception as levantada:
            return conexion, cursor, None, levantada


def test_mover_la_fecha_ESCRIBE_la_fecha_nueva_y_no_toca_nada_mas():
    """Lo único que se mueve es CUÁNDO ocurrió.

    Los consumos y el costo quedaron congelados al cargar, y el stock se
    rejuega en cada lectura: completar el dato de origen ES el arreglo, no
    hay una segunda columna que poner al día (corolario 80). Por eso el test
    afirma las dos mitades — que el UPDATE escriba la fecha, y que no haya
    NINGÚN otro UPDATE ni INSERT.
    """
    conexion, cursor, movida, error = _mover_fecha(
        7, date(2026, 9, 15),
        entradas=[_lote_compra(101, date(2026, 9, 10), 20.0, 1000.0)],
        consumos=[("compra", 101, 10.0)],
    )

    assert error is None, error
    assert movida["fecha_vieja"] == date(2026, 9, 18)
    assert movida["fecha_nueva"] == date(2026, 9, 15)
    conexion.commit.assert_called_once()

    sql, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE reprocesos SET fecha_operacion")
    assert parametros == (date(2026, 9, 15), 7)
    escrituras = [ll.args[0] for ll in cursor.execute.call_args_list
                  if "UPDATE " in ll.args[0] or "INSERT INTO" in ll.args[0]]
    assert escrituras == [sql], f"no puede tocar nada más, y tocó {escrituras}"


def test_mover_la_fecha_REBOTA_si_ese_dia_no_habia_con_que():
    """El MISMO freno que al cargar, y por eso no está escrito acá.

    Una guía que tomó 10 movida a un día en que solo había 5 no se puede
    haber armado ese día. Es `StockInsuficienteParaReproceso`, la misma
    excepción que levanta la carga.
    """
    conexion, cursor, movida, error = _mover_fecha(
        7, date(2026, 9, 15),
        entradas=[_lote_compra(101, date(2026, 9, 10), 5.0, 1000.0)],
        consumos=[("compra", 101, 10.0)],
    )

    assert isinstance(error, StockInsuficienteParaReproceso), error
    assert error.declarado == 10.0
    assert error.disponible == 5.0
    conexion.commit.assert_not_called()


def test_mover_la_fecha_REBOTA_si_el_lote_que_la_guia_DECLARO_todavia_no_existia():
    """EL CASO QUE EL FRENO DEL TOTAL NO PUEDE VER, y es el que hace falta.

    La suma entra —hay un lote viejo de 20 y la guía tomó 10— pero el
    documento congelado dice que esos 10 salieron del lote 102, que entró el
    16/09. Movida al 15, esa guía quedaría apuntando a un lote del futuro:
    la misma trazabilidad rota que esta pantalla viene a arreglar.

    Con el freno del total solo, este caso pasa en verde.
    """
    conexion, cursor, movida, error = _mover_fecha(
        7, date(2026, 9, 15),
        entradas=[_lote_compra(101, date(2026, 9, 10), 20.0, 1000.0),
                  _lote_compra(102, date(2026, 9, 16), 20.0, 1000.0)],
        consumos=[("compra", 102, 10.0)],
    )

    assert isinstance(error, RepartoDesactualizado), error
    conexion.commit.assert_not_called()


def test_mover_la_fecha_NO_SE_DESCUENTA_A_SI_MISMA():
    """Una guía que se descuenta a sí misma se rebota siempre.

    `_lo_tomado_hoy` resta lo que las guías R de ese día ya se llevaron. Al
    mover, la guía YA está fechada ese día —el UPDATE va primero— así que
    sin el `excepto` se restaría sus propios 10 a los lotes y el freno diría
    que no alcanza, sobre un lote que le sobra.

    Se afirma por los PARÁMETROS de la consulta y no por el resultado: con
    el fixture de acá el `fetchall` del tomado_hoy lo decide el test, así
    que un assert del resultado probaría el fixture y no el filtro.
    """
    conexion, cursor, movida, error = _mover_fecha(
        7, date(2026, 9, 15),
        entradas=[_lote_compra(101, date(2026, 9, 10), 20.0, 1000.0)],
        consumos=[("compra", 101, 10.0)],
    )

    assert error is None, error
    sql, parametros = _sql_y_parametros_que_contienen(cursor, "FROM reprocesos_consumos rc")
    assert "r.id <> %s" in sql, "tiene que poder dejarse afuera a sí misma"
    assert parametros == (1, date(2026, 9, 15), 7, 7)


def test_mover_la_fecha_NO_deja_fechar_ANTES_DEL_CORTE():
    """El mismo piso que la carga, leído de corte_modelo y no de una constante."""
    conexion, cursor, movida, error = _mover_fecha(7, date(2026, 8, 14))

    assert isinstance(error, ReprocesoAnteriorAlCorte), error
    assert error.corte == date(2026, 8, 15)
    conexion.commit.assert_not_called()


def test_mover_la_fecha_de_una_guia_ANULADA_o_INICIAL_o_EN_ORIGEN_no_se_puede():
    """Las tres razones son distintas y las tres son ValueError.

    Una anulada ya devolvió lo tomado a sus lotes. La INICIAL *es* la foto
    del corte y está fechada ahí por definición. La de ORIGEN es uno a uno
    con la recepción de su compra: moverla sola la despegaría del hecho que
    la generó, y eso se corrige corrigiendo la recepción.

    Y ninguna de las tres puede haber escrito: el UPDATE va después de las
    tres guardas.
    """
    for guia, que in [
        ((1, date(2026, 9, 18), 10.0, "normal", datetime(2026, 9, 18, 9)), "anulada"),
        ((1, date(2026, 9, 18), 10.0, "inicial", None), "inicial"),
        ((1, date(2026, 9, 18), 10.0, "en_origen", None), "en origen"),
    ]:
        conexion, cursor, movida, error = _mover_fecha(7, date(2026, 9, 15), guia=guia)
        assert isinstance(error, ValueError), f"{que}: {error!r}"
        conexion.commit.assert_not_called()
        assert not [ll for ll in cursor.execute.call_args_list if "UPDATE " in ll.args[0]], que


def test_mover_la_fecha_de_una_guia_QUE_NO_EXISTE_da_ValueError():
    """El SELECT va SIN AGREGADO a propósito: con un `count(*)` la fila vuelve
    con (0,) y `fila is None` no dispara nunca (corolario 27)."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[None])
    with patch("app.db.obtener_conexion", return_value=conexion):
        from app.db import cambiar_fecha_de_reproceso
        with pytest.raises(ValueError):
            cambiar_fecha_de_reproceso(999, date(2026, 9, 15))
    conexion.commit.assert_not_called()


def test_la_guia_se_lee_FOR_UPDATE_antes_de_moverla():
    """Sin el candado, dos correcciones simultáneas leen la misma fecha vieja
    y la segunda valida contra un mundo que la primera ya cambió."""
    conexion, cursor, movida, error = _mover_fecha(
        7, date(2026, 9, 15),
        entradas=[_lote_compra(101, date(2026, 9, 10), 20.0, 1000.0)],
        consumos=[("compra", 101, 10.0)],
    )
    assert "FOR UPDATE" in _sql_que_contiene(cursor, "FROM reprocesos WHERE id = %s")


# ── Lo que ya salió sin lote ANTES del día que se está por cargar ─────────


def _desglose_a_la_fecha(fecha, entradas, salidas):
    conexion, cursor = _conexion_falsa(filas_fetchone=[(date(2026, 8, 15),)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [entradas, salidas, []]
    with patch("app.db.obtener_conexion", return_value=conexion):
        from app.db import lotes_para_reproceso
        return lotes_para_reproceso(1, fecha)


def test_el_desglose_DICE_cuantos_bultos_salieron_sin_lote_antes_de_ese_dia():
    """La mitad PREVENTIVA de poder refechar una guía, pedida por el dueño el 19/09.

    Salieron 10 bultos el 12/09 y el único lote entró el 16: un lote no puede
    cubrir una salida anterior, así que esos 10 quedaron sin lote. El que
    está por cargar una guía el 18 tiene que ver ese número MIENTRAS elige la
    fecha — es el síntoma de que esas cajas se armaron antes.
    """
    reparto = _desglose_a_la_fecha(
        date(2026, 9, 18),
        [_lote_compra(101, date(2026, 9, 16), 20.0, 1000.0)],
        [_salida_fifo(date(2026, 9, 12), 10.0)],
    )

    assert reparto["sin_lote_antes"] == 10.0


def test_el_desglose_dice_CERO_cuando_todo_lo_anterior_tenia_lote():
    """La otra respuesta, y hace falta: un detector que no puede dar las dos
    se ve igual de trabajador que uno que funciona (corolario 53).

    El mismo caso con el lote entrando ANTES de la salida: lo cubre, y el
    aviso no tiene nada que decir.
    """
    reparto = _desglose_a_la_fecha(
        date(2026, 9, 18),
        [_lote_compra(101, date(2026, 9, 10), 20.0, 1000.0)],
        [_salida_fifo(date(2026, 9, 12), 10.0)],
    )

    assert reparto["sin_lote_antes"] == 0


def test_el_sin_lote_de_ANTES_no_cuenta_las_salidas_DEL_DIA_que_se_esta_cargando():
    """"Antes de este día" y no "antes o durante".

    Una salida del MISMO día es justamente la que esta guía viene a cubrir:
    contarla haría que el aviso dispare siempre, en cada carga, sobre el
    hueco que se está por tapar. Un aviso que aparece igual se deja de leer.
    """
    reparto = _desglose_a_la_fecha(
        date(2026, 9, 18),
        [],
        [_salida_fifo(date(2026, 9, 18), 10.0)],
    )

    assert reparto["sin_lote_antes"] == 0
    # Y el otro número sigue contando lo suyo: el reparto del reproceso
    # tampoco mira las salidas del día, así que las dos cuentas coinciden
    # acá por la misma razón y no por casualidad.
    assert reparto["sin_lote"] == 0


# ---------------------------------------------------------------------------
# MOVER UNA COMPRA DE FECHA
# ---------------------------------------------------------------------------
#
# Las DOS FECHAS no hacen lo mismo, y eso está medido contra el esquema real
# (19/09): `fecha_operacion` mueve el costeo, las búsquedas y la GUÍA;
# `procesada_el` mueve el stock, el FIFO y el orden de los lotes. Cambiar sola
# la primera deja el Stock del Depósito exactamente donde estaba.

_HOY_MOVER = date(2026, 9, 19)


def _compra_para_mover(estado="recepcionado", corte=date(2026, 8, 30)):
    """(conexion, cursor) con las lecturas que `mover_compra_de_fecha` hace, en orden."""
    return _conexion_falsa(
        filas_fetchone=[
            (3, date(2026, 9, 9), estado,                    # proveedor, fecha, estado
             datetime(2026, 9, 14, 14, 35, tzinfo=timezone.utc), 5),  # procesada_el, guia vieja
            (corte,),                                        # _fecha_corte
            (9,),                                            # la guía nueva
            (2,),                                            # cuántas compras tiene ya
            (1,),                                            # cuántas le quedan a la vieja
        ],
        filas_fetchall=[],                                   # ninguna guía R en origen viva
    )


def test_mover_de_fecha_FRENA_si_la_recepcion_cae_EL_DIA_DEL_CORTE():
    """El único freno de esta pantalla, y no es una consecuencia para mirar.

    La foto del corte se toma A LA TARDE, así que una compra recibida ese día
    ya está contada adentro; meterla ADEMÁS como lote la cuenta dos veces.
    Medido: con la recepción movida al día del corte el FIFO se queda sin el
    lote (lotes 1 -> 0, sin_lote 0 -> 4) y el Stock del Depósito NO SE MUEVE —
    del otro lado quedan dos cuentas del mismo hecho contradiciéndose sin que
    nada se ponga rojo.

    El `min` del input es la comodidad; la pared va donde se ESCRIBE, porque
    un formulario armado a mano no ve ningún cartel.
    """
    conexion, _ = _compra_para_mover()
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as rechazo:
            db.mover_compra_de_fecha(77, date(2026, 8, 25), date(2026, 8, 30))

    assert "30/08" in str(rechazo.value), "el error nombra la fecha del corte, no 'el corte'"
    conexion.commit.assert_not_called()


def test_mover_de_fecha_DEJA_PASAR_el_dia_siguiente_al_corte():
    """El caso feliz PEGADO a la raya.

    Sin él, el freno podría estar rechazando siempre y los tres casos
    negativos saldrían igual de verdes (corolario 30): una batería de
    negativos no distingue "la guarda funciona" de "la guarda frena todo".
    """
    conexion, cursor = _compra_para_mover()
    with patch("app.db.obtener_conexion", return_value=conexion):
        movida = db.mover_compra_de_fecha(77, date(2026, 8, 25), date(2026, 8, 31))

    assert movida["guia_id"] == 9
    conexion.commit.assert_called_once()


def test_mover_de_fecha_FRENA_si_la_recepcion_es_ANTERIOR_a_la_compra():
    """El único orden que el mundo impone: la mercadería no entra al depósito
    antes de comprarse."""
    conexion, _ = _compra_para_mover()
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="no entra al depósito antes"):
            db.mover_compra_de_fecha(77, date(2026, 9, 16), date(2026, 9, 15))
    conexion.commit.assert_not_called()


def test_mover_de_fecha_FRENA_con_la_guia_R_EN_ORIGEN_viva_y_la_NOMBRA():
    """Esa guía dice lo mismo que la compra, uno a uno: moverle el día a una y
    no a la otra las separa en silencio.

    Y la nombra: un error que no dice qué lo retiene manda a adivinar.
    """
    conexion, cursor = _compra_para_mover()
    cursor.fetchall.return_value = [(31,)]
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="R31"):
            db.mover_compra_de_fecha(77, date(2026, 9, 16), date(2026, 9, 17))
    conexion.commit.assert_not_called()


def test_mover_de_fecha_EXIGE_la_recepcion_si_la_compra_esta_recepcionada():
    """Sin ella se movería la fecha de la compra y el stock quedaría donde
    estaba — que es exactamente el malentendido que esta pantalla viene a
    cerrar."""
    conexion, _ = _compra_para_mover()
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="la que mueve el stock"):
            db.mover_compra_de_fecha(77, date(2026, 9, 16))
    conexion.commit.assert_not_called()


def test_mover_una_compra_PENDIENTE_no_pide_ni_toca_la_recepcion():
    """Sin recepción no hay `procesada_el` que mover, y escribirlo igual —en
    NULL— sería pisar con un dato que esta operación no tiene por qué
    conocer."""
    conexion, cursor = _compra_para_mover(estado="pendiente")
    with patch("app.db.obtener_conexion", return_value=conexion):
        db.mover_compra_de_fecha(77, date(2026, 9, 16))

    update = _sql_que_contiene(cursor, "UPDATE compras SET fecha_operacion")
    assert "procesada_el" not in update
    conexion.commit.assert_called_once()


def test_mover_de_fecha_CONSERVA_LA_HORA_de_la_recepcion():
    """`procesada_el` es a la vez la fecha que mueve el stock Y el desempate
    del FIFO adentro del día. Poner una hora inventada —medianoche, o now()—
    le cambia el lugar a la compra entre las demás recepciones de ese día, que
    es un segundo cambio que nadie pidió."""
    conexion, cursor = _compra_para_mover()
    with patch("app.db.obtener_conexion", return_value=conexion):
        db.mover_compra_de_fecha(77, date(2026, 9, 16), date(2026, 9, 17))

    _, parametros = _sql_y_parametros_que_contienen(cursor, "procesada_el = %s")
    nueva = parametros[3]
    assert nueva.date() == date(2026, 9, 17)
    # 14:35 UTC son las 11:35 en Argentina, y es ESA la que se conserva.
    assert (nueva.hour, nueva.minute) == (11, 35), nueva


def test_mover_de_fecha_avisa_cuando_la_guia_VIEJA_queda_sin_renglones():
    """El número de guía es el papel del proveedor y no se recicla: la vacía se
    queda. Que quedó vacía se dice, porque el que la busque mañana la va a
    encontrar sin nada adentro."""
    conexion, cursor = _compra_para_mover()
    cursor.fetchone.side_effect = [
        (3, date(2026, 9, 9), "recepcionado",
         datetime(2026, 9, 14, 14, 35, tzinfo=timezone.utc), 5),
        (date(2026, 8, 30),), (9,), (2,),
        (0,),                      # la vieja quedó SIN renglones
    ]
    with patch("app.db.obtener_conexion", return_value=conexion):
        movida = db.mover_compra_de_fecha(77, date(2026, 9, 16), date(2026, 9, 17))

    assert movida["quedo_vacia"] is True
    assert movida["guia_vieja_id"] == 5
    # Y NO SE BORRA: ningún DELETE sobre guias_compra.
    assert not any("DELETE" in ll.args[0].upper() and "guias_compra" in ll.args[0]
                   for ll in cursor.execute.call_args_list)


# ---------------------------------------------------------------------------
# BORRAR UNA COMPRA FORZANDO EL BLOQUEO POR ESTADO (Gerencia)
# ---------------------------------------------------------------------------


def test_forzar_SALTEA_el_bloqueo_por_estado_y_borra():
    """Una compra recepcionada por error hoy solo se arregla con SQL a mano, y
    que la única salida sea ésa es el agujero de siempre."""
    conexion, cursor = _conexion_falsa_con_varios_fetchall(
        [(5,), (0,)],                 # el DELETE devuelve la guía; le quedan 0 renglones
        [[], [], [], [], [], []],     # nada colgando, ni fotos
    )
    with patch("app.db.obtener_conexion", return_value=conexion):
        db.eliminar_compra(77, forzar=True, origen="gerencia")

    borrado = _sql_que_contiene(cursor, "DELETE FROM compras")
    # SIN la condición de _SQL_COMPRA_BORRABLE: eso es lo que forzar saltea.
    assert "estado IS DISTINCT FROM" not in borrado
    conexion.commit.assert_called_once()


def test_forzar_NO_saltea_lo_que_CUELGA_y_lo_NOMBRA():
    """No es una política que Gerencia pueda pisar: son filas que apuntan acá,
    y Postgres las defiende igual.

    Medido el 19/09 contra el esquema real: sin esta guarda, las cuatro llegan
    como un `ForeignKeyViolation` crudo — el error que no dice qué lo retiene
    manda a adivinar.
    """
    conexion, cursor = _conexion_falsa_con_varios_fetchall(
        [(5,), (0,)],
        [[], [(31,)], [], [], []],    # fotos, consumos con R31, y el resto vacío
    )
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="R31"):
            db.eliminar_compra(77, forzar=True, origen="gerencia")

    conexion.commit.assert_not_called()
    assert not any("DELETE FROM compras" in ll.args[0] for ll in cursor.execute.call_args_list)


def test_SIN_forzar_el_bloqueo_por_estado_SIGUE_PUESTO():
    """El control, y es el que hace que el de arriba signifique algo: sin él,
    una versión que forzara SIEMPRE los pasaría a los dos."""
    conexion, cursor = _conexion_falsa_con_varios_fetchall(
        [(5,), (0,)], [[], [], [], [], []],
    )
    with patch("app.db.obtener_conexion", return_value=conexion):
        db.eliminar_compra(77, origen="compras")

    borrado = _sql_que_contiene(cursor, "DELETE FROM compras")
    assert "estado IS DISTINCT FROM" in borrado


def test_lo_que_cuelga_enumera_LAS_CUATRO_y_dice_de_que_clase_es_cada_una():
    """Las cuatro FK que no se pueden limpiar solas, medidas contra el esquema
    real. `fotos_recepcion` NO está: la borra `eliminar_compra` él mismo,
    porque el archivo es de ESTA compra y de ninguna otra.

    Y cada fila dice de qué CLASE es, no solo el número: el que la lee tiene
    que saber a qué pantalla ir a arreglarlo.
    """
    conexion, cursor = _conexion_falsa_con_varios_fetchall(
        None, [[(31,)], [(32,)], [(9,)], [(4,)]],
    )
    with patch("app.db.obtener_conexion", return_value=conexion):
        cuelgan = db.lo_que_cuelga_de_la_compra(77)

    assert [c["que"] for c in cuelgan] == [
        "guia_r_consumo", "guia_r_en_origen", "vale_de_vacios", "devolucion_al_proveedor",
    ]
    assert all(c["detalle"] for c in cuelgan), "cada una se NOMBRA, no se cuenta"


def test_lo_que_cuelga_devuelve_VACIO_cuando_no_cuelga_nada():
    """El caso feliz, y sin él una versión que devolviera siempre algo pasaría
    todos los negativos (corolario 30)."""
    conexion, _ = _conexion_falsa_con_varios_fetchall(None, [[], [], [], []])
    with patch("app.db.obtener_conexion", return_value=conexion):
        assert db.lo_que_cuelga_de_la_compra(77) == []


def test_las_guias_R_congeladas_PIDEN_el_costo_y_EXCLUYEN_las_anuladas():
    """Lo que cambia es QUÉ COLUMNA pide la consulta, así que el test lee el SQL.

    El valor lo entrega el mock: los seis tests del aviso parchean
    `guias_r_congeladas_de_la_compra`, así que el texto de la consulta no lo
    ejercita NADIE. Medido con canarios: sacarle `rc.costo_por_bulto` al
    SELECT, y sacarle el filtro de las anuladas, hacían caer CERO.

    Y los dos modos de falla son mudos:

      · sin el costo, el aviso dice "congelada a" y no dice a cuánto — o sea
        nombra la guía y se calla el número, que es lo único que hace la
        comparación posible;
      · sin el filtro, una guía R ANULADA aparece diciendo que se costeó
        contra este lote. Esa guía ya no consume nada: el reparto se rejuega
        en cada lectura y ella no está. Sería un reclamo falso sobre algo que
        ya se arregló.

    Los asserts van CALIFICADOS POR ALIAS: `reprocesos` y `compras` tienen las
    dos una columna `anulado_el`, y un `in` pelado matchea la que aparezca
    (corolario 4).
    """
    consulta = _sql_de_la_funcion("_guias_r_del_lote")

    assert "rc.costo_por_bulto" in consulta
    assert "rp.anulado_el IS NULL" in consulta
    assert "rc.compra_id = %s" in consulta
    # El ORDEN importa: de él depende `documentos_que_no_entran`, que acumula
    # desde la más vieja porque es como el lote se fue gastando.
    assert "ORDER BY rp.fecha_operacion, rp.id" in consulta


def test_las_guias_R_congeladas_traen_el_costo_como_float_o_None():
    """El costo es NULLABLE —una guía R con el costo incompleto lo tiene en
    NULL— y ahí el aviso tiene que nombrarla igual, sin el número. Un `float(None)`
    reventaría la pantalla justo en la guía que más se quiere ver."""
    conexion, _ = _conexion_falsa_con_varios_fetchall(
        None, [[(12, date(2026, 9, 12), 3, 100000), (13, date(2026, 9, 13), 2, None)]]
    )
    with patch("app.db.obtener_conexion", return_value=conexion):
        guias = db.guias_r_congeladas_de_la_compra(77)

    assert [g["costo_por_bulto"] for g in guias] == [100000.0, None]
    assert [g["bultos"] for g in guias] == [3.0, 2.0]


def _origenes_que_el_codigo_PASA():
    """Los que aparecen en el codigo, encontrados y no escritos a mano."""
    import ast as _ast

    # ANCLADO A LA LLAMADA y no al `origen=` suelto: `origen` es un keyword
    # comun en este repo —los movimientos de cajas tienen el suyo— y un
    # detector que barre todos trae valores de otra tabla, que despues
    # alguien agrega al CHECK equivocado. Es la posicion gramatical del
    # corolario 59: la palabra en su llamada, no la palabra.
    BORRADORAS = {"eliminar_compra", "_eliminar_compra_y_su_foto_si_corresponde"}
    encontrados = set()
    for archivo in ("app/main.py", "app/db.py"):
        arbol = _ast.parse(io.open(archivo, encoding="utf-8").read())
        for nodo in _ast.walk(arbol):
            if not isinstance(nodo, _ast.Call):
                continue
            if not (isinstance(nodo.func, _ast.Name) and nodo.func.id in BORRADORAS):
                continue
            for kw in nodo.keywords:
                if kw.arg == "origen" and isinstance(kw.value, _ast.Constant):
                    encontrados.add(kw.value.value)
    # El del lote va LITERAL adentro del SQL (la funcion ES esa operacion,
    # asi que no recibe el origen de nadie): se lee del INSERT del archivo.
    fuente = io.open("app/db.py", encoding="utf-8").read()
    encontrados |= set(re.findall(
        r"INSERT INTO compras_eliminadas.*?::bigint,\s*'([a-z_]+)'", fuente, re.S))
    return encontrados


def _origenes_que_el_CHECK_acepta():
    """Leidos del .sql, NO copiados: una copia envejece en silencio."""
    sql = io.open("db/eliminadas_1_tabla.sql", encoding="utf-8").read()
    lista = re.search(r"check \(origen in\s*\((.*?)\)\)", sql, re.S).group(1)
    return set(re.findall(r"'([a-z_]+)'", lista))


def test_los_origenes_del_CODIGO_y_los_del_CHECK_son_LOS_MISMOS():
    """La lista incompleta no pierde un dato: REVIENTA EL BORRADO.

    El archivo se escribe en la MISMA sentencia que el DELETE, asi que un
    origen que el CHECK no acepta no deja una fila sin archivar — hace fallar
    la transaccion entera y la compra no se borra. Es el corolario 75: un
    CHECK que se vuelve pared en el camino que nadie enumero.

    Y casi pasa: la primera version de esta migracion listaba DOS origenes
    —gerencia y cancelar_dia— y las superficies que borran son CUATRO. Las
    dos que faltaban eran el Eliminar de Buscar Compras y el borrado
    multiple, o sea las que mas se usan.

    Compara el conjunto ENCONTRADO contra el DECIDIDO (corolario 60), y el
    decidido se LEE del .sql en vez de copiarse: una copia coincide hoy y se
    separa sin que nada falle.
    """
    del_codigo = _origenes_que_el_codigo_PASA()
    del_check = _origenes_que_el_CHECK_acepta()

    assert del_codigo == del_check, (
        f"el codigo pasa {sorted(del_codigo)} y el CHECK acepta {sorted(del_check)}"
    )
    assert len(del_codigo) == 4, sorted(del_codigo)


def test_el_DELETE_y_su_archivo_son_LA_MISMA_sentencia():
    """Con dos execute habria un camino donde la compra se va y el registro no."""
    import app.db as db

    fuente = inspect.getsource(db)
    # las TRES: las dos ramas de eliminar_compra (que comparten plantilla) y
    # el borrado en lote.
    assert fuente.count("INSERT INTO compras_eliminadas") == 2, "son dos textos: la plantilla y el lote"
    for bloque in re.split(r"INSERT INTO compras_eliminadas", fuente)[1:]:
        # el DELETE tiene que estar ARRIBA, en el mismo WITH
        anterior = fuente.split(bloque)[0] if bloque in fuente else ""
        assert "DELETE FROM compras" in anterior[-900:], "el archivo quedo fuera del CTE del DELETE"
    assert "to_jsonb(compras.*)" in fuente, "se archiva la fila ENTERA, no columnas elegidas"


def test_el_ORIGEN_no_tiene_DEFAULT():
    """Un default es lo que deja que la quinta superficie no lo decida."""
    import app.db as db

    parametro = inspect.signature(db.eliminar_compra).parameters["origen"]
    assert parametro.default is inspect.Parameter.empty
    assert parametro.kind is inspect.Parameter.KEYWORD_ONLY


def test_la_SEGUNDA_POR_CAJON_llega_al_INSERT_con_un_VALOR_y_no_solo_con_None():
    """El caso con dato, que es el único que distingue guardar de listar.

    Una batería donde el campo va vacío no separa "el parámetro se guarda" de
    "la columna está en la lista del INSERT": con None en los dos lados, un
    INSERT que escribiera NULL a la fuerza pasa igual (corolario 30). Por eso
    el valor es 16 y no None, y el control de al lado es la compra que NO
    declaró la segunda.
    """
    from app.db import crear_compra

    for valor in (16.0, None):
        conexion, cursor = _conexion_falsa([(105,), (0,), (900,)])
        with patch("app.db.obtener_conexion", return_value=conexion):
            crear_compra(date(2026, 9, 20), 5, 200, 10, 18, 180, None, 50000.0, None, "Clark",
                         segunda_por_cajon=valor)

        consulta, parametros = cursor.execute.call_args_list[3].args
        assert "segunda_por_cajon" in consulta, "la columna no está en el INSERT"
        assert valor in parametros, f"la segunda por cajón {valor} no llegó al INSERT"


def test_el_INGRESO_DIRECTO_copia_la_segunda_a_LAS_DOS_columnas():
    """Entra ya recepcionado, así que el estimado ES el real — igual que la fracción.

    Escribir solo la estimada dejaría la fila real con un hueco, y la pantalla
    muestra ese hueco como "esta compra no declaró la otra magnitud", que es
    falso: la declaró y además se recibió en el acto.
    """
    from app.db import crear_compra

    conexion, cursor = _conexion_falsa([(105,), (0,), (900,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 9, 20), 5, 200, 10, 18, 180, None, 50000.0, None, "Clark",
                     ingreso_directo_deposito=True, segunda_por_cajon=16.0)

    consulta, parametros = cursor.execute.call_args_list[3].args
    assert "segunda_por_cajon, segunda_por_cajon_real" in consulta
    assert parametros.count(16.0) == 2, "la segunda tiene que ir a la estimada Y a la real"


def test_la_EDICION_reescribe_la_segunda_por_cajon():
    """La edición es justo el camino que se olvidó `ficha_en_origen_id` el 12/09.

    Y el modo de falla es el mismo: la pantalla relee de la base, así que una
    escritura muerta se ve igual que una viva — el valor que vuelve es el que
    puso OTRO camino.
    """
    from app.db import actualizar_cantidad_compra

    conexion, cursor = _conexion_falsa([("pendiente", "pendiente", None)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Clark", segunda_por_cajon=16.0)

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    assert "segunda_por_cajon = %s" in consulta
    assert 16.0 in parametros


def test_la_RECEPCION_escribe_la_segunda_REAL_tal_como_la_conto_deposito():
    """Por bulto y sin pasar por el total: lo que Depósito contó es lo que se guarda."""
    from app.db import recepcionar_compra

    conexion, cursor = _conexion_falsa(
        [("kilo", 180.0, 400.0), ("pendiente",), (1, None, 10.0, date(2026, 8, 25), None, None)]
    )
    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(30, cantidad_cajones_real=10, valor_real=18, segunda_real=37)

    consulta, parametros = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
    assert "segunda_por_cajon_real = %s" in consulta

    (cajones, contenido, kilos, fraccion, segunda_cajon,
     _, _, _) = parametros
    # POR POSICIÓN y no con un `in`: el total (370) TAMBIÉN está en la tupla
    # —`cantidad_fraccion_real` se sigue guardando— así que preguntar si 37
    # está adentro pasa igual con las dos columnas al revés.
    assert segunda_cajon == 37, "la columna por cajón se quedó con el total"
    assert fraccion == 370, "el total dejó de guardarse"


def test_las_SIETE_consultas_que_muestran_las_DOS_magnitudes_TRAEN_la_columna():
    """Sin la columna en el SELECT, la pantalla dibuja un hueco donde hay dato.

    Y es mudo: un hueco es exactamente lo que se muestra para una compra
    anterior al modelo de dos magnitudes, así que nadie lo iría a buscar
    (corolario 65 — el mock entrega lo que le pidieron, no lo que la consulta
    pidió, y ningún test de valor puede ver esto).

    El conjunto se ENCUENTRA y no se escribe a mano: son las consultas de
    compra que traen `a.unidad_conteo`, que es la columna que dice si hay una
    segunda magnitud que mostrar. La octava no la va a recordar nadie.
    """
    fuente = io.open("app/db.py", encoding="utf-8").read()
    sin_comentarios = "\n".join(l.split("--")[0] for l in fuente.splitlines())

    # EL FILTRO ES `c.contenido_por_cajon` Y NO `a.unidad_conteo`: la primera
    # versión usaba el conteo y se llevaba puesta la consulta del DETALLE DE
    # LA ALERTA de unidades, que lo trae para otra cosa y no dibuja ningún
    # cajón. La que necesita la segunda magnitud es la que trae la primera.
    consultas = [
        sql for sql in re.findall(r'"""(.*?)"""', sin_comentarios, re.S)
        if "c.contenido_por_cajon" in sql and "a.unidad_conteo" in sql
    ]
    assert len(consultas) >= 6, f"solo {len(consultas)} consultas: el test dejó de mirar"

    sin_la_columna = [s.strip()[:70] for s in consultas if "c.segunda_por_cajon" not in s]
    assert not sin_la_columna, f"consultas sin la columna nueva: {sin_la_columna}"


def test_un_RENGLON_DE_COMANDA_sin_la_segunda_REVIENTA_y_no_guarda_NULL():
    """El `[]` contra el `.get()`, que es la diferencia entre reventar y mentir.

    LO ENCONTRÓ UN CANARIO EN CERO: cambiar `renglon["segunda_por_cajon"]` por
    `renglon.get(...)` no hacía caer ni un test, porque las dos formas dan lo
    mismo mientras la clave ESTÉ — y ningún fixture la tenía ausente. Es el
    corolario 30: una batería donde el campo siempre viene no distingue "si
    falta, revienta" de "si falta, escribe NULL".

    Y la diferencia importa porque el NULL es mudo: una compra guardada sin la
    segunda magnitud se ve EXACTAMENTE IGUAL que una anterior al modelo de dos
    magnitudes, o sea un hueco legítimo. Nadie la iría a buscar, y la ficha
    del cliente que compra en la otra unidad se queda sin costo días después y
    en otra pantalla.
    """
    from app.db import crear_compras_de_comanda

    sin_la_clave = {
        "articulo_id": 5, "cantidad_cajones": 10, "contenido_por_cajon": 18,
        "cantidad_kilos": 180, "cantidad_fraccion": None,
        "importe": 5000.0, "sena": None, "tipo_retiro": "Clark",
    }
    conexion, _ = _conexion_falsa([(105,), (0,), (900,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(KeyError) as falla:
            crear_compras_de_comanda(date(2026, 9, 20), 200, [sin_la_clave], None, None)
    assert "segunda_por_cajon" in str(falla.value)

    # Y el control: CON la clave entra, para que el test no pase por estar
    # rebotando por cualquier otra cosa.
    conexion, cursor = _conexion_falsa([(105,), (0,), (900,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compras_de_comanda(
            date(2026, 9, 20), 200, [dict(sin_la_clave, segunda_por_cajon=16.0)], None, None
        )
    _, parametros = _sql_y_parametros_que_contienen(cursor, "INSERT INTO compras")
    assert 16.0 in parametros


def test_los_escritores_de_SEGUNDA_POR_CAJON_no_pueden_tener_DEFAULT():
    """Lo pidió un canario en CERO: ponerle `= None` a los tres no rompía nada.

    Y es correcto que no rompiera: con un default, los llamadores de HOY
    siguen pasándolo explícitamente, así que en runtime no cambia nada. El
    default solo se cobra con el llamador de MAÑANA — el que se lo olvide
    guarda la columna en NULL, que se ve EXACTAMENTE IGUAL que una compra
    anterior al modelo de dos magnitudes, o sea un hueco legítimo que nadie
    va a ir a buscar.

    O sea que la protección no es una llamada: es la FORMA DE LA FIRMA, y por
    eso se verifica ahí. Sin este test, la única guarda contra ese agujero
    era que alguien se acordara.

    Se pregunta al ÁRBOL y el conjunto se ENCUENTRA (corolario 60): toda
    función de app/db.py que reciba `segunda_por_cajon`, no una lista de tres
    escrita a mano. La cuarta no la va a recordar nadie.
    """
    arbol = ast.parse(io.open("app/db.py", encoding="utf-8").read())

    escritores = [
        nodo for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.FunctionDef)
        and any(a.arg == "segunda_por_cajon"
                for a in nodo.args.args + nodo.args.kwonlyargs)
    ]
    assert len(escritores) >= 3, f"solo {len(escritores)} escritores: el test dejó de mirar"

    flojos = []
    for f in escritores:
        kwonly = [a.arg for a in f.args.kwonlyargs]
        if "segunda_por_cajon" not in kwonly:
            flojos.append(f"{f.name}: no es keyword-only, así que un positional puede correrse")
            continue
        i = kwonly.index("segunda_por_cajon")
        if f.args.kw_defaults[i] is not None:
            flojos.append(f"{f.name}: tiene default, así que olvidarlo guarda NULL en silencio")
    assert not flojos, "\n".join(flojos)


def test_las_DOS_consultas_de_fichas_traen_las_que_el_COSTEO_necesita():
    """`magnitud_de_la_ficha` lee DOS columnas —`unidad_venta` de la ficha y
    `unidad_conteo` del artículo— y con la que falta hace un `.get()` que
    devuelve None. O sea que una ficha leída sin `unidad_conteo` contesta
    "no se puede costear en esa unidad" para todo lo que no sea kilo, en
    silencio y sin descuadrar nada.

    Y LAS DOS CONSULTAS SE HABÍAN SEPARADO. El docstring de
    `listar_fichas_de_todos_los_clientes` dice, textual, "misma consulta y
    mismo orden que listar_fichas_por_cliente" — y la de un cliente traía
    `a.unidad_conteo` con su comentario explicando para qué, mientras la de
    todos no. Es la regla escrita dos veces en su forma barata: ninguna
    fallaba, una contestaba distinto.

    NO SE EXIGE QUE TRAIGAN LO MISMO, a propósito: la de un cliente trae
    además `a.unidad_compra`, que está DEPRECADA y sería un error propagar.
    Lo que se exige es el par que el costeo necesita.
    """
    import ast
    import io
    import re

    fuente = io.open("app/db.py", encoding="utf-8").read()
    arbol = ast.parse(fuente)
    consultas = {}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef) and nodo.name in (
            "listar_fichas_por_cliente", "listar_fichas_de_todos_los_clientes"
        ):
            textos = [p.value for p in ast.walk(nodo)
                      if isinstance(p, ast.Constant) and isinstance(p.value, str)]
            consultas[nodo.name] = "\n".join(
                t for t in textos if re.search(r"\bFROM\s+fichas_logistica\b", t, re.I)
            )

    # El denominador: sin esto, un regex roto deja las dos vacías y el test
    # pasa afirmando sobre nada (corolario 45).
    assert len(consultas) == 2, f"se encontraron {len(consultas)} de 2 consultas"
    for nombre, sql in consultas.items():
        assert "FROM fichas_logistica" in sql, f"{nombre}: no se aisló la consulta"
        # Calificadas con el alias: `unidad_venta` suelto matchearía el
        # comentario que explica por qué está (corolario 4 y 59).
        assert "fl.unidad_venta" in sql, f"{nombre} dejó de traer fl.unidad_venta"
        assert "a.unidad_conteo" in sql, (
            f"{nombre} dejó de traer a.unidad_conteo: sus fichas van a contestar "
            "'no se puede costear' para todo lo que no sea kilo, en silencio"
        )
