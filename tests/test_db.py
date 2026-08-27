from datetime import date, datetime, time
import pytest
from unittest.mock import MagicMock, patch

from app import db
from app.db import (
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
    contar_recepciones_pendientes_viejas,
    contar_senas_pendientes_viejas,
    contar_stock_vacios_negativos,
    contar_retiros_pendientes_viejos,
    corregir_recepcion_compra,
    crear_cliente,
    crear_compra,
    crear_compras_de_comanda,
    deshacer_no_ingresado_compra,
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
    limpiar_foto_ruta_de_compras,
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


def test_eliminar_compra_ultima_de_su_guia_devuelve_las_fotos_sin_otros_usos():
    # Al borrar el ÚLTIMO renglón de la guía, las fotos de la guía se dan
    # de baja y se devuelven las rutas que ningúna otra guía usa.
    conexion, cursor = _conexion_falsa(
        [
            (105, "pendiente", "pendiente"),  # SELECT guia_id, estado, estado_retiro
            (0,),  # COUNT de compras de la guía tras el DELETE: quedó vacía
            (0,),  # COUNT de otras guías usando la ruta: ninguna
        ],
        filas_fetchall=[("2026-08-13/n07p41-123-abcdef12.jpg",)],  # RETURNING de fotos_guia
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == ["2026-08-13/n07p41-123-abcdef12.jpg"]
    conexion.commit.assert_called_once()
    conexion.close.assert_called_once()


def test_eliminar_compra_con_renglones_restantes_no_toca_las_fotos():
    # La guía sigue teniendo renglones: las fotos son de la GUÍA y se quedan.
    conexion, cursor = _conexion_falsa(
        [
            (105, "pendiente", "pendiente"),
            (2,),  # quedan 2 renglones en la guía
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == []
    # SELECT compra + DELETE + COUNT de la guía: nada de fotos.
    assert cursor.execute.call_count == 3
    assert not any("fotos_guia" in ll.args[0] for ll in cursor.execute.call_args_list)
    conexion.commit.assert_called_once()


def test_eliminar_compra_foto_compartida_por_otra_guia_no_se_borra_del_storage():
    # Listado consolidado: la misma foto cuelga de VARIAS guías. Vaciar una
    # guía saca SU registro, pero el archivo sigue mientras otra guía lo use.
    conexion, cursor = _conexion_falsa(
        [
            (105, "pendiente", "pendiente"),
            (0,),  # la guía quedó vacía
            (1,),  # otra guía sigue usando la misma ruta
        ],
        filas_fetchall=[("2026-08-13/listado-abc123.jpg",)],
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == []
    # El registro de ESTA guía sí se borró.
    assert any("DELETE FROM fotos_guia WHERE guia_id" in ll.args[0] for ll in cursor.execute.call_args_list)


def test_eliminar_compra_sin_guia_no_toca_fotos():
    # Compra viejísima sin guía (no debería quedar ninguna tras la
    # migración): se borra sin mirar fotos.
    conexion, cursor = _conexion_falsa(
        [
            (None, "pendiente", "pendiente"),
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == []
    assert cursor.execute.call_count == 2  # SELECT + DELETE


def test_eliminar_compra_rechazada_se_puede_borrar_igual_que_antes():
    conexion, cursor = _conexion_falsa(
        [
            (105, "rechazado", "pendiente"),
            (0,),
        ],
        filas_fetchall=[],
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == []
    conexion.commit.assert_called_once()


def test_eliminar_compra_cancelada_en_retiro_se_puede_borrar_igual_que_antes():
    conexion, cursor = _conexion_falsa(
        [
            (105, "pendiente", "cancelado"),
            (0,),
        ],
        filas_fetchall=[],
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == []
    conexion.commit.assert_called_once()


def test_eliminar_compra_recepcionada_no_se_borra():
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/n07p41-123-abcdef12.jpg", "recepcionado", "retirado"),  # SELECT foto_ruta, estado, estado_retiro
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            eliminar_compra(30)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra ya fue recepcionada, no se puede eliminar."

    # Ni el DELETE ni ningún commit: se corta antes de tocar nada.
    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()
    conexion.close.assert_called_once()


def test_eliminar_compra_no_ingresada_no_se_borra():
    # Regla fija: "No ingresó" es un registro de Depósito — el comprador no
    # lo puede hacer desaparecer borrando la compra. Y el mensaje habla de
    # eso, aunque la compra además estuviera retirada.
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/n07p41-123-abcdef12.jpg", "no_ingresado", "retirado"),  # SELECT foto_ruta, estado, estado_retiro
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            eliminar_compra(30)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == 'Esta compra quedó registrada como "No ingresó" en Depósito, no se puede eliminar.'

    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_eliminar_compra_retirada_no_se_borra():
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/n07p41-123-abcdef12.jpg", "pendiente", "retirado"),  # SELECT foto_ruta, estado, estado_retiro
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            eliminar_compra(30)
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra ya fue retirada, no se puede eliminar."

    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_crear_compra_asigna_el_primer_punto_de_una_guia_nueva():
    conexion, cursor = _conexion_falsa(
        [
            (105,),  # SELECT id de guias_compra (ya existía o se acaba de crear)
            (0,),  # SELECT COUNT(*) de compras con esa guía: ninguna todavía
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 8, 16), 5, 200, 40, 20, 800, None, 45000.0, None, "Clark"
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
    # guia_id, guia_punto, carga_token (None: carga manual, sin token)
    assert parametros_insert[-3:] == (105, 1, None)
    conexion.commit.assert_called_once()


def test_crear_compra_suma_puntos_si_la_guia_ya_tiene_renglones():
    # Segundo (y tercer) artículo del mismo proveedor el mismo día: misma
    # guía, el punto sigue la cuenta (no vuelve a 1).
    conexion, cursor = _conexion_falsa(
        [
            (105,),  # SELECT id de guias_compra
            (2,),  # ya hay 2 compras con esa guía
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 8, 16), 6, 200, 10, 12, None, 120, None, None, "Clark"
        )

    _, parametros_insert = cursor.execute.call_args_list[3].args
    assert parametros_insert[-3:] == (105, 3, None)  # guia_id, guia_punto, carga_token


def test_crear_compras_de_comanda_guarda_todos_los_renglones_en_un_solo_commit():
    # Dos renglones de la misma comanda: todo en UNA conexión y UN commit
    # (todo-o-nada) — antes cada renglón commiteaba por su cuenta y un corte
    # de internet dejaba la comanda guardada a medias.
    conexion, cursor = _conexion_falsa(
        [
            None,  # SELECT 1 por carga_token: no existe, se guarda normal
            (105,), (0,),  # guía y punto del renglón 1
            (105,), (1,),  # guía y punto del renglón 2
        ]
    )
    renglones = [
        {
            "articulo_id": 5, "cantidad_cajones": 10, "contenido_por_cajon": 18,
            "cantidad_kilos": 180, "cantidad_fraccion": None,
            "importe": 5000.0, "sena": None, "tipo_retiro": "Clark",
        },
        {
            "articulo_id": 6, "cantidad_cajones": 3, "contenido_por_cajon": 12,
            "cantidad_kilos": None, "cantidad_fraccion": 36,
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
        assert llamada.args[1][-1] == "token123"
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
              "cantidad_kilos": 180, "cantidad_fraccion": None,
              "importe": 5000.0, "sena": None, "tipo_retiro": "Clark"}],
            None, "token123",
        )

    assert guardo is False
    assert cursor.execute.call_count == 1  # solo el SELECT del token
    conexion.commit.assert_not_called()


def test_crear_compras_de_comanda_sin_token_guarda_sin_chequear():
    # Forms viejos que quedaron abiertos de antes del cambio: sin token no
    # hay chequeo anti-duplicado, se guarda directo (como siempre).
    conexion, cursor = _conexion_falsa([(105,), (0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardo = crear_compras_de_comanda(
            date(2026, 8, 19), 200,
            [{"articulo_id": 5, "cantidad_cajones": 10, "contenido_por_cajon": 18,
              "cantidad_kilos": 180, "cantidad_fraccion": None,
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
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 8, 16), 5, 200, 40, 20, 800, None, None, None, "Clark",
            ingreso_directo_deposito=True,
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
    # Las cantidades reales (los últimos 4 parámetros posicionales antes de
    # guia_id/guia_punto) son iguales a las cargadas: cantidad_cajones=40,
    # contenido_por_cajon=20, cantidad_kilos=800, cantidad_fraccion=None.
    assert parametros_insert[-6:] == (105, 1, 40, 20, 800, None)
    conexion.commit.assert_called_once()


def test_crear_compra_sin_ingreso_directo_sigue_igual_que_antes():
    # Default False: comportamiento intacto para los 4 flujos del
    # comprador (manual, foto, múltiples fotos, listado) -- no se les
    # tocó ni un carácter.
    conexion, cursor = _conexion_falsa(
        [
            (105,),
            (0,),
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 8, 16), 5, 200, 40, 20, 800, None, 45000.0, None, "Clark")

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
        actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")

    consulta_update, parametros_update = cursor.execute.call_args_list[1].args
    assert "UPDATE compras" in consulta_update
    assert "importe" not in consulta_update
    assert "sena" not in consulta_update
    assert parametros_update[-1] == 30
    conexion.commit.assert_called_once()


def test_actualizar_cantidad_compra_recepcionada_no_se_edita():
    conexion, cursor = _conexion_falsa([("recepcionado", "retirado", "logistica")])  # SELECT estado, estado_retiro, retiro_origen

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")
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
        actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")

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
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra tuvo un rechazo total, no se puede editar la cantidad."

    conexion.commit.assert_not_called()


def test_actualizar_cantidad_compra_no_ingresada_no_se_edita():
    conexion, cursor = _conexion_falsa([("no_ingresado", "retirado", "logistica")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra nunca ingresó al depósito, no se puede editar la cantidad."

    conexion.commit.assert_not_called()


def test_actualizar_precio_compra_pisa_importe_y_sena():
    conexion, cursor = _conexion_falsa([("recepcionado",)])  # SELECT estado

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_precio_compra(30, 55000.0, 1000.0)

    consulta_update, parametros_update = cursor.execute.call_args_list[1].args
    assert "UPDATE compras SET importe = %s, sena = %s" in consulta_update
    assert parametros_update == (55000.0, 1000.0, 30)
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

    consulta = cursor.execute.call_args[0][0]
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
    # 2 fetchone: SELECT unidad_compra, y SELECT estado_retiro dentro de
    # _auto_retirar_si_corresponde (acá viene 'pendiente', se auto-retira).
    conexion, cursor = _conexion_falsa([("kilo",), ("pendiente",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso = recepcionar_compra(30, cantidad_cajones_real=38, valor_real=20)

    consulta_update, parametros_update = cursor.execute.call_args_list[1].args
    assert "estado = 'recepcionado'" in consulta_update
    assert "procesada_el = now()" in consulta_update
    cajones, contenido, kilos, fraccion, rechazada, motivo, compra_id = parametros_update
    assert cajones == 38
    assert contenido == 20  # tomado directo, sin dividir
    assert kilos == 760  # 38 × 20, derivado
    assert fraccion is None
    # Recepción normal: sin rechazo parcial (y borra cualquier resto viejo).
    assert rechazada is None
    assert motivo is None
    assert compra_id == 30
    assert aviso is None
    # Se auto-retira: UPDATE final con estado_retiro = 'retirado', origen 'deposito'.
    consulta_retiro, parametros_retiro = cursor.execute.call_args_list[3].args
    assert "estado_retiro = 'retirado'" in consulta_retiro
    assert "retiro_origen = 'deposito'" in consulta_retiro
    assert parametros_retiro == (30,)
    conexion.commit.assert_called_once()


def test_recepcionar_compra_articulo_por_unidad_toma_unidades_por_cajon_y_deriva_el_total():
    # Depósito cuenta UN cajón (no toda la carga junta) — mismo criterio
    # que kilo: valor_real es directamente contenido_por_cajon_real, y
    # cantidad_fraccion_real (el total) se deriva acá (cajones × valor_real).
    conexion, cursor = _conexion_falsa([("unidad",), ("pendiente",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(31, cantidad_cajones_real=10, valor_real=118)

    _, parametros_update = cursor.execute.call_args_list[1].args
    cajones, contenido, kilos, fraccion, rechazada, motivo, compra_id = parametros_update
    assert contenido == 118  # tomado directo, sin dividir
    assert kilos is None
    assert fraccion == 1180  # 10 × 118, derivado


def test_recepcionar_compra_ya_retirada_no_pisa_el_auto_retiro():
    conexion, cursor = _conexion_falsa([("kilo",), ("retirado",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso = recepcionar_compra(30, cantidad_cajones_real=38, valor_real=20)

    assert aviso is None
    # Solo 2 execute: SELECT unidad_compra + UPDATE recepcionado, y dentro de
    # _auto_retirar_si_corresponde el SELECT estado_retiro — sin UPDATE de más.
    assert cursor.execute.call_count == 3


def test_recepcionar_compra_cancelada_en_logistica_avisa_y_no_la_pisa():
    conexion, cursor = _conexion_falsa([("kilo",), ("cancelado",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        aviso = recepcionar_compra(30, cantidad_cajones_real=38, valor_real=20)

    assert aviso == "Esta compra figuraba cancelada en Logística."
    # Sin UPDATE de estado_retiro: se corta después del SELECT.
    assert cursor.execute.call_count == 3
    conexion.commit.assert_called_once()


def test_corregir_recepcion_compra_articulo_por_kilo_deriva_el_total():
    # 2 fetchone: SELECT estado + unidad_compra, y el UPDATE.
    conexion, cursor = _conexion_falsa([("recepcionado", "kilo")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(30, cantidad_cajones_real=30, valor_real=25)

    assert cursor.execute.call_count == 2
    consulta_update, parametros_update = cursor.execute.call_args_list[1].args
    assert "cantidad_cajones_real = %s" in consulta_update
    assert "contenido_por_cajon_real = %s" in consulta_update
    # A diferencia de recepcionar_compra, NO toca estado ni procesada_el.
    assert "estado" not in consulta_update
    assert "procesada_el" not in consulta_update
    cajones, contenido, kilos, fraccion, rechazada, motivo, compra_id = parametros_update
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
    conexion, cursor = _conexion_falsa([("recepcionado", "unidad")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(30, cantidad_cajones_real=30, valor_real=80)

    _, parametros_update = cursor.execute.call_args_list[1].args
    cajones, contenido, kilos, fraccion, rechazada, motivo, compra_id = parametros_update
    assert contenido == 80  # tomado directo, sin dividir
    assert kilos is None
    assert fraccion == 2400  # 30 × 80, derivado


def test_corregir_recepcion_compra_bloqueada_si_no_esta_recepcionada():
    conexion, cursor = _conexion_falsa([("pendiente", "unidad")])

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
    conexion, cursor = _conexion_falsa([("kilo",), ("pendiente",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra(
            30, cantidad_cajones_real=8, valor_real=20,
            cantidad_cajones_rechazada=2, motivo_rechazo="podrido",
        )

    consulta_update, parametros_update = cursor.execute.call_args_list[1].args
    assert "cantidad_cajones_rechazada = %s" in consulta_update
    assert "motivo_rechazo = %s" in consulta_update
    cajones, contenido, kilos, fraccion, rechazada, motivo, compra_id = parametros_update
    assert cajones == 8  # los aceptados, no los llegados
    assert kilos == 160  # 8 × 20: el total real sale de los aceptados
    assert rechazada == 2
    assert motivo == "podrido"
    conexion.commit.assert_called_once()


def test_corregir_recepcion_compra_corrige_el_rechazo_parcial():
    conexion, cursor = _conexion_falsa([("recepcionado", "kilo")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(
            30, cantidad_cajones_real=7, valor_real=25,
            cantidad_cajones_rechazada=3, motivo_rechazo="golpeado",
        )

    consulta_update, parametros_update = cursor.execute.call_args_list[1].args
    assert "cantidad_cajones_rechazada = %s" in consulta_update
    assert "motivo_rechazo = %s" in consulta_update
    cajones, contenido, kilos, fraccion, rechazada, motivo, compra_id = parametros_update
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

    consulta, parametros = cursor.execute.call_args.args
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


def test_contar_articulos_comprados_incotizables_pide_ficha_y_precio_vigente():
    conexion, cursor = _conexion_falsa([(4,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        casos = contar_articulos_comprados_incotizables(date(2026, 7, 30), date(2026, 8, 6))

    assert casos == 4
    consulta, parametros = cursor.execute.call_args.args
    assert "FROM fichas_logistica" in consulta
    assert "FROM precios_venta_historial" in consulta
    assert "vigente_desde <= %s" in consulta
    assert parametros == (date(2026, 7, 30), date(2026, 8, 6))


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
    assert "creado_en < %s" in consulta
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
    assert "c.retiro_procesado_el >= %s AND c.retiro_procesado_el < %s::date + 1" in consulta
    assert "::date =" not in consulta
    assert "ORDER BY c.retiro_procesado_el DESC" in consulta
    assert parametros == ("Clark", date(2026, 8, 17), date(2026, 8, 17))


def test_compra_tiene_deshacer_recepcion_bloqueado():
    assert compra_tiene_deshacer_recepcion_bloqueado("recepcionado") is True
    assert compra_tiene_deshacer_recepcion_bloqueado("rechazado") is True
    # no_ingresado sí se puede deshacer: no hay ningún conteo real que
    # se pierda, nunca se llegó a contar nada.
    assert compra_tiene_deshacer_recepcion_bloqueado("no_ingresado") is False
    assert compra_tiene_deshacer_recepcion_bloqueado("pendiente") is False
    assert compra_tiene_deshacer_recepcion_bloqueado(None) is False


def test_deshacer_no_ingresado_compra_vuelve_todo_a_pendiente():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("no_ingresado",)])  # SELECT estado

    with patch("app.db.obtener_conexion", return_value=conexion):
        deshacer_no_ingresado_compra(32)

    consulta, parametros = cursor.execute.call_args_list[1].args
    assert "estado = 'pendiente'" in consulta
    assert "procesada_el = NULL" in consulta
    assert "cantidad_cajones_real = NULL" in consulta
    assert "contenido_por_cajon_real = NULL" in consulta
    assert "cantidad_kilos_real = NULL" in consulta
    assert "cantidad_fraccion_real = NULL" in consulta
    assert parametros == (32,)
    conexion.commit.assert_called_once()


def test_deshacer_no_ingresado_compra_bloqueado_si_ya_fue_recepcionada():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("recepcionado",)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            deshacer_no_ingresado_compra(32)
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
    assert "c.procesada_el >= %s AND c.procesada_el < %s::date + 1" in consulta
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
    conexion, cursor = _conexion_falsa([(5,)])  # SELECT COUNT(*): 5 compras en total
    cursor.rowcount = 3  # solo 3 se pudieron borrar (2 protegidas)

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compras_del_dia_por_proveedor(date(2026, 8, 16), 7)

    assert resultado == {"borradas": 3, "protegidas": 2}
    consulta_delete = cursor.execute.call_args_list[1].args[0]
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
    assert parametros == (date(2023, 8, 15),)
    assert "FROM fotos_guia" in consulta
    assert "JOIN guias_compra" in consulta
    assert "GROUP BY f.foto_ruta" in consulta
    assert "HAVING MAX(g.fecha_operacion) < %s" in consulta


def test_listar_fotos_para_limpiar_vacio_da_lista_vacia():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_fotos_para_limpiar(date(2023, 8, 15))

    assert resultado == []


def test_limpiar_foto_ruta_de_compras_borra_solo_fotos_guia():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        limpiar_foto_ruta_de_compras("2020-01-01/a.jpg")

    # Las fotos viven SOLO en fotos_guia: la vieja compras.foto_ruta ya no
    # se toca (columna borrada por drop_foto_ruta_compras.sql).
    assert cursor.execute.call_count == 1
    consulta_delete = cursor.execute.call_args_list[0].args[0]
    assert "DELETE FROM fotos_guia WHERE foto_ruta = %s" in consulta_delete
    conexion.commit.assert_called_once()
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


def test_crear_cliente_inserta_el_cliente_y_todos_los_conceptos_con_tipo():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        cliente_id = crear_cliente(
            "Vea",
            [{"nombre": "IVA", "valor": 0.21}],
            [{"nombre": "Flete", "valor": 0.04}],
            0.20,
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
        assert "CURRENT_DATE" in consulta_concepto

    parametros_conceptos = [llamada.args[1] for llamada in cursor.execute.call_args_list[1:]]
    assert (7, "IVA", 0.21, "suma") in parametros_conceptos
    assert (7, "Flete", 0.04, "resta") in parametros_conceptos
    assert (7, "utilidad_objetivo", 0.20, "utilidad") in parametros_conceptos
    conexion.commit.assert_called_once()


def test_crear_cliente_sin_tasas_solo_inserta_la_utilidad():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_cliente("Vea", [], [], 0.20)

    # 1 INSERT del cliente + 1 de la utilidad, sin tasas.
    assert cursor.execute.call_count == 2


def test_actualizar_cliente_pisa_el_nombre_y_agrega_solo_los_conceptos_que_cambiaron():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cliente(1, "Día", [{"nombre_parametro": "Flete", "tipo": "resta", "valor": 0.05}])

    assert cursor.execute.call_count == 2
    consulta_nombre, parametros_nombre = cursor.execute.call_args_list[0].args
    assert "UPDATE clientes SET nombre" in consulta_nombre
    assert parametros_nombre == ("Día", 1)

    consulta_concepto, parametros_concepto = cursor.execute.call_args_list[1].args
    assert "ON CONFLICT (cliente_id, nombre_parametro, vigente_desde)" in consulta_concepto
    assert "DO UPDATE" in consulta_concepto
    assert "CURRENT_DATE" in consulta_concepto
    assert parametros_concepto == (1, "Flete", 0.05, "resta")
    conexion.commit.assert_called_once()


def test_actualizar_cliente_sin_cambios_de_conceptos_solo_pisa_el_nombre():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cliente(1, "Día", [])

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


def test_guardar_precios_cliente_inserta_con_vigente_desde_hoy_sin_pisar_lo_viejo():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_precios_cliente(1, [{"ficha_id": 907, "precio": 550.0}, {"ficha_id": 903, "precio": 900.0}])

    assert cursor.execute.call_count == 2
    for llamada in cursor.execute.call_args_list:
        consulta, parametros = llamada.args
        assert "INSERT INTO precios_venta_historial" in consulta
        assert "vigente_desde" in consulta
        assert "CURRENT_DATE" in consulta
        # El precio cuelga de la FICHA (dos fichas del mismo artículo y
        # cliente tienen precios distintos), y el artículo NO viaja desde
        # la pantalla: sale de la propia ficha adentro del INSERT.
        assert "ON CONFLICT (ficha_id, vigente_desde)" in consulta
        assert "SELECT fl.id, fl.articulo_id" in consulta
        assert "DO UPDATE" in consulta
    assert cursor.execute.call_args_list[0].args[1] == (1, 550.0, None, 907, 1)
    assert cursor.execute.call_args_list[1].args[1] == (1, 900.0, None, 903, 1)
    conexion.commit.assert_called_once()


def test_guardar_precios_cliente_sin_cambios_no_ejecuta_nada():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_precios_cliente(1, [])

    cursor.execute.assert_not_called()
    conexion.commit.assert_not_called()


def test_guardar_precios_cliente_con_foto_ruta_la_guarda_en_cada_fila():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_precios_cliente(1, [{"ficha_id": 907, "precio": 550.0}], foto_ruta="2026-08-16/dia-123-abc.jpg")

    consulta, parametros = cursor.execute.call_args_list[0].args
    assert "foto_ruta" in consulta
    assert "COALESCE(EXCLUDED.foto_ruta, precios_venta_historial.foto_ruta)" in consulta
    assert parametros == (1, 550.0, "2026-08-16/dia-123-abc.jpg", 907, 1)


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
        registrar_costo_envase(7, 800.0)

    consulta, parametros = cursor.execute.call_args.args
    assert "INSERT INTO envases_costo_historial" in consulta
    assert "CURRENT_DATE" in consulta
    assert "ON CONFLICT (envase_id, vigente_desde) DO UPDATE" in consulta
    assert not consulta.strip().startswith("UPDATE")
    assert parametros == (7, 800.0)
    conexion.commit.assert_called_once()


def test_crear_envase_crea_con_costo_inicial_desde_hoy_en_una_transaccion():
    conexion, cursor = _conexion_falsa(filas_fetchone=[None, (33,)])  # no existe; RETURNING id

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_envase("Caja Nueva", 700.0)

    consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
    assert any("INSERT INTO envases " in consulta for consulta in consultas)
    assert any("INSERT INTO envases_costo_historial" in consulta and "CURRENT_DATE" in consulta for consulta in consultas)
    assert cursor.execute.call_args_list[-1].args[1] == (33, 700.0)
    conexion.commit.assert_called_once()


def test_crear_envase_rechaza_nombre_repetido():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(1,)])  # ya existe

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as salida:
            crear_envase("Caja Chica Día", 700.0)

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
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,)])  # guia_id, punto

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 8, 19), 5, 200, 10, 18, 180, None, 50000.0, None, "Cooperativa")

    consulta_insert, parametros_insert = cursor.execute.call_args_list[-1].args
    assert "'pendiente', 'retirado', now(), %s" in consulta_insert
    assert parametros_insert[-1] == "automatico_cooperativa"
    assert "cantidad_cajones_real" not in consulta_insert  # sin valores reales: los pone Depósito
    conexion.commit.assert_called_once()


def test_actualizar_cantidad_a_cooperativa_marca_el_retiro_en_el_mismo_update():
    # Cambiar el tipo a Cooperativa en Editar Compra no puede dejar la
    # compra pendiente de retiro: no existe pantalla que la muestre.
    conexion, cursor = _conexion_falsa(filas_fetchone=[("pendiente", "pendiente", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Cooperativa")

    consulta_update, parametros_update = cursor.execute.call_args_list[-1].args
    assert "estado_retiro = 'retirado'" in consulta_update
    assert "retiro_origen = %s" in consulta_update
    assert "automatico_cooperativa" in parametros_update


def test_actualizar_cantidad_con_tipo_comun_no_toca_el_retiro():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("pendiente", "pendiente", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Clark")

    consulta_update = cursor.execute.call_args_list[-1].args[0]
    assert "estado_retiro" not in consulta_update
    assert "retiro_origen" not in consulta_update


def test_actualizar_cantidad_de_cooperativa_a_tipo_real_vuelve_el_retiro_a_pendiente():
    # Volver de Cooperativa a un tipo real (Carro/Clark/Pases) tiene que
    # devolver la compra a la cola de Logística — si no, queda "retirada"
    # por una cooperativa que ya no la va a buscar.
    conexion, cursor = _conexion_falsa(filas_fetchone=[("pendiente", "retirado", "automatico_cooperativa")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 18, 180, None, "Clark")

    consulta_update = cursor.execute.call_args_list[1].args[0]
    assert "estado_retiro = 'pendiente'" in consulta_update
    assert "retiro_origen = NULL" in consulta_update
    conexion.commit.assert_called_once()


def test_crear_compra_carro_nace_retirada_con_origen_automatico():
    # Carro lo maneja un tercero que nunca entra al sistema: nadie tilda
    # nunca esas compras — nacen con el retiro hecho, igual que Cooperativa.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 8, 19), 5, 200, 10, 18, 180, None, 50000.0, None, "Carro")

    consulta_insert, parametros_insert = cursor.execute.call_args_list[-1].args
    assert "'pendiente', 'retirado', now(), %s" in consulta_insert
    assert parametros_insert[-1] == "automatico_carro"
    conexion.commit.assert_called_once()


def test_crear_compra_clark_sigue_naciendo_pendiente_de_retiro():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(105,), (0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(date(2026, 8, 19), 5, 200, 10, 18, 180, None, 50000.0, None, "Clark")

    consulta_insert = cursor.execute.call_args_list[-1].args[0]
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
    assert "WHERE t.activo" in consulta
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
    consulta_update, parametros_update = cursor.execute.call_args_list[1].args
    assert "SET activo = true" in consulta_update
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

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_vacio_recibido(5)

    consulta, parametros = cursor.execute.call_args.args
    assert "UPDATE vacios_recibidos SET anulado_el = now()" in consulta
    assert "DELETE" not in consulta
    # Solo si estaba vigente: anular dos veces no pisa la fecha original.
    assert "anulado_el IS NULL" in consulta
    assert parametros == (5,)


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
    assert "a.creado_en >= %s AND a.creado_en < %s::date + 1" in consulta
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
    # Ordenado por la fecha del cierre, el más reciente primero.
    assert "ORDER BY COALESCE(v.sena_pagada_el, v.sena_vale_el, v.sena_anulada_el) DESC" in consulta


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
    conexion, cursor = _conexion_falsa([(1, 5, 100, 6, "kilo", False, "BERENJENA", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        eliminar_ficha(10)

    consulta_delete = cursor.execute.call_args_list[0].args[0]
    assert "DELETE FROM fichas_logistica WHERE id = %s" in consulta_delete
    assert "RETURNING" in consulta_delete
    consulta_foto, parametros_foto = cursor.execute.call_args_list[1].args
    assert "INSERT INTO fichas_logistica_historial" in consulta_foto
    assert parametros_foto == (10, 1, 5, 100, 6, "kilo", False, "BERENJENA", None, "borrado")
    conexion.commit.assert_called_once()


def test_cambiar_articulo_de_ficha_es_borrado_mas_alta_con_el_alias_de_la_pantalla():
    conexion, cursor = _conexion_falsa(
        [
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
    # 4 pasos en UNA transacción: delete + foto borrado + insert + foto alta.
    assert cursor.execute.call_count == 4
    # La foto del borrado conserva el alias VIEJO (es el estado que se cerró).
    _, parametros_borrado = cursor.execute.call_args_list[1].args
    assert parametros_borrado == (10, 1, 4, 100, 6, "kilo", False, "ANANA", "90137", "borrado")
    consulta_insert, parametros_insert = cursor.execute.call_args_list[2].args
    assert "INSERT INTO fichas_logistica" in consulta_insert
    # La ficha nueva apunta al artículo nuevo, conserva envase/contenido/
    # unidad, y lleva el alias que vino de la pantalla.
    assert parametros_insert == (5, 1, 100, 6, "kilo", False, "ANCO", "90200")
    _, parametros_alta = cursor.execute.call_args_list[3].args
    assert parametros_alta == (33, 1, 5, 100, 6, "kilo", False, "ANCO", "90200", "alta")
    conexion.commit.assert_called_once()


def test_cambiar_articulo_de_ficha_inexistente_devuelve_none_sin_escribir():
    conexion, cursor = _conexion_falsa([None])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = cambiar_articulo_de_ficha(999, 5, None, None)

    assert resultado is None
    assert cursor.execute.call_count == 1


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
    assert consulta.count("AND creado_en < %s::date + 1") == 3
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
    assert "c.procesada_el >= %s" in consulta
    assert "c.procesada_el < %s::date + 1" in consulta
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

    consulta, parametros = cursor.execute.call_args.args
    assert "SET armado_el = now(), cantidad_armada = %s, kilos_enviados = %s" in consulta
    assert parametros == (None, None, 11)

    conexion2, cursor2 = _conexion_falsa()
    with patch("app.db.obtener_conexion", return_value=conexion2):
        marcar_renglon_armado(11, 12.0, 120.0)
    assert cursor2.execute.call_args.args[1] == (12.0, 120.0, 11)


def test_desmarcar_renglon_armado_borra_tilde_y_cantidad():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        desmarcar_renglon_armado(12)

    consulta, parametros = cursor.execute.call_args.args
    assert "SET armado_el = NULL, cantidad_armada = NULL" in consulta
    assert parametros == (12,)


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
    assert "leido_con_ia AND recibido_el >= %s" in consulta
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
    assert "anulado_el IS NULL" in consulta
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

    consulta = cursor.execute.call_args.args[0]
    assert "SET anulado_el = now(), armado_el = NULL, cantidad_armada = NULL, kilos_enviados = NULL" in consulta
    conexion.commit.assert_called_once()


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
    assert "anulado_el IS NULL" in consulta
    assert "r.kilos_enviados" in consulta
    assert "r.anulado_el" in consulta
    assert parametros == (1, date(2026, 8, 15), date(2026, 8, 22))


def test_listar_pedidos_vigentes_con_armado_no_cuenta_los_anulados():
    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_pedidos_vigentes_con_armado(1, date(2026, 8, 15))

    consulta = cursor.execute.call_args.args[0]
    # Los anulados quedan fuera del progreso ("18 de 32 armados").
    assert consulta.count("r.anulado_el IS NULL") == 2
    assert "p.armado_cerrado_el" in consulta


# --- Stock del Depósito ---

from app.db import (  # noqa: E402
    crear_movimiento_stock,
    devoluciones_vinculadas_por_rango,
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
                          ("segunda_producida",), ("segunda_de_rechazos",), ("segunda_remitida",)]
    cursor.fetchall.return_value = [(1, "Banana", 40, 15, 2, -3, 6, 10, 5, 4, 2)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        filas = stock_deposito_por_articulo()

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
    # La segunda es un pool APARTE: lo producido en reprocesos + lo que
    # entró por rechazos que no volvieron al stock, − lo remitido.
    assert filas[0]["segunda"] == 5 + 4 - 2
    # Un rechazo mandado a segunda no suma al stock normal.
    assert "destino_rechazo IS NULL OR destino_rechazo = 'stock'" in consulta
    assert "destino_rechazo IN ('segunda', 'reproceso')" in consulta
    assert "SUM(bultos_segunda)" in consulta


def test_crear_movimiento_stock_guarda_la_foto_del_sistema_y_devuelve_el_resultante():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(12.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = crear_movimiento_stock(7, "ajuste", -3.0, "rotura", date(2026, 8, 25))

    insert = cursor.execute.call_args_list[-1]
    assert "INSERT INTO movimientos_stock" in insert.args[0]
    # La foto del stock SIN este movimiento, como en ajustes_vacios:
    # sin ese rastro cualquier faltante se tapa con un ajuste.
    assert insert.args[1] == (
        7, "ajuste", -3.0, "rotura", None, date(2026, 8, 25), 12.0, None, None, None, None, None, None
    )
    assert resultado == 9.0
    conexion.commit.assert_called_once()


def test_crear_movimiento_stock_reingreso_lleva_cliente_y_fecha_propia():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_movimiento_stock(7, "reingreso_rechazo", 4.0, "Devolvió Día", date(2026, 8, 24), cliente_id=1)

    insert = cursor.execute.call_args_list[-1]
    assert insert.args[1] == (
        7, "reingreso_rechazo", 4.0, "Devolvió Día", 1, date(2026, 8, 24), 0.0, None, None, None, None, None, None
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
        None, None, None, None,
    )


def test_crear_movimiento_stock_rechazo_a_segunda_no_toca_el_stock_normal():
    # El destino se decide al cargar: lo que va a segunda entra y sale en
    # el mismo acto, así que el stock del artículo no se mueve.
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
        "reproceso", 12.0, None, None,
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
        None, None, "reproceso", 9,
    )


def test_stock_deposito_de_articulo_hace_la_misma_cuenta_por_articulo():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(-5.0,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        stock = stock_deposito_de_articulo(2)

    consulta = cursor.execute.call_args.args[0]
    assert "AND articulo_id = %s" in consulta
    assert cursor.execute.call_args.args[1] == (2, 2, 2, 2, 2)
    assert stock == -5.0


def test_entradas_y_salidas_para_fifo_ordena_por_fecha_real_del_hecho():
    conexion, cursor = _conexion_falsa()
    cursor.description = [
        ("fecha_orden",), ("momento_orden",), ("tipo_lote",), ("fecha_lote",), ("detalle",), ("motivo",),
        ("cantidad",), ("articulo_id",),
    ]
    cursor.fetchall.side_effect = [[], _total_salidas(2, 20.0), []]

    with patch("app.db.obtener_conexion", return_value=conexion):
        entradas, salidas, dirigidas = entradas_y_salidas_stock_articulo(2)

    consulta_entradas = cursor.execute.call_args_list[0].args[0]
    # El lote de una compra es su guía; el orden, el instante de recepción.
    assert "c.estado = 'recepcionado'" in consulta_entradas
    assert "procesada_el" in consulta_entradas
    # Un movimiento ordena por su fecha_operacion (la REAL del hecho: un
    # reingreso cargado hoy con fecha de ayer entra en el FIFO de ayer).
    assert "m.fecha_operacion, m.creado_en" in consulta_entradas
    assert "m.cantidad > 0" in consulta_entradas

    # Un rechazo mandado a segunda no es lote de stock: no entra al FIFO.
    assert "m.destino_rechazo IS NULL OR m.destino_rechazo = 'stock'" in consulta_entradas

    consulta_salidas = cursor.execute.call_args_list[1].args[0]
    assert "DISTINCT ON (cliente_id, fecha_operacion)" in consulta_salidas
    assert "cantidad < 0" in consulta_salidas
    assert salidas == 20.0

    # Las mermas dirigidas a un lote salen aparte, para que el reparto
    # sepa de qué lote descontarlas (acá no hay ninguna).
    consulta_dirigidas = cursor.execute.call_args_list[2].args[0]
    assert "lote_tipo IS NOT NULL" in consulta_dirigidas
    assert dirigidas == []
    assert entradas == []


def test_entradas_de_varios_articulos_devuelve_una_entrada_por_cada_id_pedido():
    # Igual que las salidas: el artículo sin movimientos sale en cero y con
    # listas vacías, no ausente. Y en UNA sola conexión para todos.
    conexion, cursor = _conexion_falsa()
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 20), 8.0, 1000.0, articulo_id=2)],
        [(2, 20.0), (7, 0.0)],
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        movimientos = entradas_y_salidas_stock_articulos([2, 7])

    assert sorted(movimientos) == [2, 7]
    entradas_2, total_2, dirigidas_2 = movimientos[2]
    assert [e["origen_id"] for e in entradas_2] == [101]
    assert (total_2, dirigidas_2) == (20.0, [])
    assert movimientos[7] == ([], 0.0, [])
    # Tres consultas en total (lotes, total de salidas, dirigidas), no tres
    # por artículo — y una sola conexión.
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

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = crear_conteo_stock(2, 4.0)

    insert = cursor.execute.call_args_list[-1]
    assert "INSERT INTO conteos_stock" in insert.args[0]
    # La foto del sistema se graba del lado del server...
    assert insert.args[1] == (2, 4.0, 7.0)
    # ...y NUNCA se le devuelve al operario: si la ve, transcribe en vez
    # de contar.
    assert resultado is None
    conexion.commit.assert_called_once()


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


def test_listar_ultimos_conteos_stock_trae_el_ultimo_por_articulo():
    from app.db import listar_ultimos_conteos_stock

    conexion, cursor = _conexion_falsa()
    cursor.description = [("id",), ("articulo_nombre",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_ultimos_conteos_stock()

    consulta = cursor.execute.call_args.args[0]
    assert "DISTINCT ON (c.articulo_id)" in consulta
    assert "c.stock_sistema" in consulta
    assert "c.creado_en DESC" in consulta


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
    crear_reproceso,
    listar_reprocesos_por_rango,
)

COLUMNAS_LOTES = [("fecha_orden",), ("momento_orden",), ("tipo_lote",), ("origen_id",),
                  ("fecha_lote",), ("detalle",), ("motivo",), ("cantidad",), ("costo_bulto",),
                  ("cliente_lote_id",), ("articulo_id",)]


def _lote_compra(origen_id, fecha, cantidad, costo, articulo_id=1):
    return (fecha, datetime(2026, 8, fecha.day, 10), "guia", origen_id, fecha, "Norte 15", None,
            cantidad, costo, None, articulo_id)


def _total_salidas(articulo_id, total):
    """La fila del total de salidas: ahora viene por artículo, no como escalar suelto."""
    return [(articulo_id, total)]


def test_crear_reproceso_congela_consumos_fifo_y_todo_el_costo_a_la_primera():
    # Lotes: compra 101 (8 bultos a $1000, viejo) y 102 (10 a $1200). Ya
    # salieron 5 → restos 3 y 10. Tomo 6: 3 del 101 y 3 del 102 (FIFO).
    conexion, cursor = _conexion_falsa(filas_fetchone=[(12,)])
    cursor.description = COLUMNAS_LOTES
    # Las tres tandas de fetchall: lotes, total de salidas y mermas dirigidas.
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 8, 20), 8.0, 1000.0),
            _lote_compra(102, date(2026, 8, 22), 10.0, 1200.0),
        ],
        _total_salidas(1, 5.0),
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
    assert inserts[0].args[1] == (1, date(2026, 8, 25), 6, 4, 1, 1, 6600.0, 1650.0, 7)
    # Consumos congelados, del lote más viejo primero, con su costo.
    assert inserts[1].args[1] == (12, "compra", 101, 101, 3.0, 1000.0)
    assert inserts[2].args[1] == (12, "compra", 102, 102, 3.0, 1200.0)
    # El reproceso JAMÁS toca compras: su costo no puede llegar a la cotización.
    assert all("compras" not in c.args[0].split("FROM")[0] for c in inserts)
    conexion.commit.assert_called_once()


def test_crear_reproceso_con_lote_sin_precio_deja_el_costo_incompleto():
    # Un lote sin importe (compra de la mañana sin precio, o stock
    # inicial): NO se promedia con números inventados — costo NULL.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(13,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [
            _lote_compra(101, date(2026, 8, 20), 8.0, 1000.0),
            _lote_compra(102, date(2026, 8, 22), 10.0, None),
        ],
        _total_salidas(1, 0.0),
        [],  # sin mermas dirigidas
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_reproceso(1, 10, 8, 0, 0, date(2026, 8, 25))

    inserts = [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    assert inserts[0].args[1][6] is None
    assert inserts[0].args[1][7] is None
    assert inserts[2].args[1][5] is None


def test_crear_reproceso_lo_que_excede_los_lotes_queda_sin_lote():
    # El piso es la verdad: si tomó 5 y los lotes cubren 3, no se traba —
    # los 2 de más quedan como consumo sin_lote, a la vista.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(14,)])
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [
        [_lote_compra(101, date(2026, 8, 20), 3.0, 1000.0)],
        _total_salidas(1, 0.0),
        [],
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_reproceso(1, 5, 4, 0, 1, date(2026, 8, 25))

    inserts = [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    assert inserts[1].args[1] == (14, "compra", 101, 101, 3.0, 1000.0)
    assert inserts[2].args[1] == (14, "sin_lote", None, None, 2.0, None)
    # Con un consumo sin costo, la guía queda con costo incompleto.
    assert inserts[0].args[1][6] is None


def test_anular_reproceso_es_baja_logica():
    conexion, cursor = _conexion_falsa()

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


def test_anular_remito_segunda_es_baja_logica():
    from app.db import anular_remito_segunda

    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        anular_remito_segunda(7)

    consulta = cursor.execute.call_args.args[0]
    assert "UPDATE remitos_segunda SET anulado_el = now()" in consulta
    assert "anulado_el IS NULL" in consulta


def test_articulos_con_salidas_stock_junta_armados_mermas_y_reprocesos():
    from app.db import articulos_con_salidas_stock

    conexion, cursor = _conexion_falsa()
    cursor.description = [("articulo_id",), ("nombre",), ("grupo",)]
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        articulos_con_salidas_stock(1, date(2026, 8, 18), date(2026, 8, 25))

    consulta = cursor.execute.call_args.args[0]
    # Armados del cliente en el rango (pedidos vigentes) + mermas y
    # reprocesos del depósito (no son de un cliente: entran igual).
    assert "DISTINCT ON (cliente_id, fecha_operacion)" in consulta
    assert "v.cliente_id = %s" in consulta
    assert "tipo = 'merma'" in consulta
    assert "FROM reprocesos" in consulta


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

    conexion, cursor = _conexion_falsa()
    cursor.description = [("fecha_orden",), ("tipo",), ("articulo_id",)]
    cursor.fetchall.return_value = [(date(2026, 8, 21), "armado", 2)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        salidas = salidas_stock_articulos([2, 7])

    assert sorted(salidas) == [2, 7]
    assert salidas[2] == [{"fecha_orden": date(2026, 8, 21), "tipo": "armado"}]
    assert salidas[7] == []
    # UNA sola consulta para los dos, y sin abrir una conexión por artículo.
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[1] == ([2, 7], [2, 7], [2, 7])


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
    for fragmento in fuente.split("INSERT INTO compras")[1:]:
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
