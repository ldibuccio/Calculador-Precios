from datetime import date
import pytest
from unittest.mock import MagicMock, patch

from app.db import (
    actualizar_cantidad_compra,
    actualizar_cliente,
    actualizar_precio_compra,
    buscar_compras,
    cerrar_disponible_generado,
    compra_tiene_cantidad_bloqueada,
    compra_tiene_deshacer_recepcion_bloqueado,
    compra_tiene_deshacer_retiro_bloqueado,
    compra_tiene_precio_bloqueado,
    contar_compras_sin_precio,
    corregir_recepcion_compra,
    crear_cliente,
    crear_compra,
    deshacer_no_ingresado_compra,
    deshacer_retiro_compra,
    crear_envase,
    listar_envases_con_costo,
    registrar_costo_envase,
    eliminar_compra,
    eliminar_compras_del_dia_por_proveedor,
    guardar_disponible,
    guardar_precios_cliente,
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


def test_eliminar_compra_devuelve_el_foto_ruta_si_era_la_unica_referencia():
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/n07p41-123-abcdef12.jpg", "pendiente", "pendiente"),  # SELECT foto_ruta, estado, estado_retiro
            (0,),  # SELECT COUNT(*) después del DELETE: nadie más la usa
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == "2026-08-13/n07p41-123-abcdef12.jpg"
    conexion.commit.assert_called_once()
    conexion.close.assert_called_once()


def test_eliminar_compra_no_devuelve_el_foto_ruta_si_otro_renglon_lo_sigue_usando():
    # Regresión: una comanda = una foto = varios renglones, todos con el
    # mismo foto_ruta. Si borro uno pero otro sigue vivo, la foto NO se
    # puede borrar del bucket todavía.
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/n07p41-123-abcdef12.jpg", "pendiente", "pendiente"),  # SELECT foto_ruta, estado, estado_retiro
            (1,),  # SELECT COUNT(*) después del DELETE: queda 1 compra usándola
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado is None
    conexion.commit.assert_called_once()


def test_eliminar_compra_no_borra_la_foto_si_otro_proveedor_del_mismo_listado_la_sigue_usando():
    # Regresión explícita para "Cargar Listado de Compras Consolidado": una
    # sola foto de planilla queda compartida por compras de VARIOS
    # proveedores distintos (ej. Saturno, Crefu, Agro), no solo por varios
    # renglones de un mismo proveedor. El conteo de referencias filtra
    # únicamente por foto_ruta, nunca por proveedor_id, así que borrar la
    # compra de un proveedor no borra la foto mientras compras de OTRO
    # proveedor sigan usándola.
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/listado-abc123.jpg", "pendiente", "pendiente"),  # SELECT foto_ruta, estado, estado_retiro
            (2,),  # SELECT COUNT(*): quedan 2 compras de otros proveedores usándola
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado is None
    # El conteo de referencias es global por foto_ruta, sin ningún filtro
    # de proveedor_id — por eso alcanza para cubrir el caso de varios
    # proveedores compartiendo la misma foto de planilla.
    consulta_conteo, parametros_conteo = cursor.execute.call_args_list[2].args
    assert "proveedor_id" not in consulta_conteo
    assert parametros_conteo == ("2026-08-13/listado-abc123.jpg",)


def test_eliminar_compra_borra_la_foto_al_eliminar_la_ultima_compra_de_cualquier_proveedor_del_listado():
    # Mismo escenario que arriba, pero esta es la ÚLTIMA compra que queda
    # (de cualquiera de los proveedores del listado): ahí sí hay que borrar
    # la foto del bucket.
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/listado-abc123.jpg", "pendiente", "pendiente"),  # SELECT foto_ruta, estado, estado_retiro
            (0,),  # SELECT COUNT(*): ya no queda ninguna compra usándola
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == "2026-08-13/listado-abc123.jpg"


def test_eliminar_compra_sin_foto_no_cuenta_referencias():
    conexion, cursor = _conexion_falsa(
        [
            (None, "pendiente", "pendiente"),  # SELECT foto_ruta, estado, estado_retiro: esta compra no tenía foto
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado is None
    # Solo el SELECT foto_ruta y el DELETE — sin el SELECT COUNT de más.
    assert cursor.execute.call_count == 2


def test_eliminar_compra_rechazada_se_puede_borrar_igual_que_antes():
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/n07p41-123-abcdef12.jpg", "rechazado", "pendiente"),  # SELECT foto_ruta, estado, estado_retiro
            (0,),
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == "2026-08-13/n07p41-123-abcdef12.jpg"
    conexion.commit.assert_called_once()


def test_eliminar_compra_cancelada_en_retiro_se_puede_borrar_igual_que_antes():
    conexion, cursor = _conexion_falsa(
        [
            ("2026-08-13/n07p41-123-abcdef12.jpg", "pendiente", "cancelado"),  # SELECT foto_ruta, estado, estado_retiro
            (0,),
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == "2026-08-13/n07p41-123-abcdef12.jpg"
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
    assert parametros_insert[-2:] == (105, 1)  # guia_id, guia_punto
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
            date(2026, 8, 16), 6, 200, 10, 12, None, 120, None, None, "Carro"
        )

    _, parametros_insert = cursor.execute.call_args_list[3].args
    assert parametros_insert[-2:] == (105, 3)  # guia_id, guia_punto


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
    assert compra_tiene_cantidad_bloqueada("recepcionado", "pendiente") is True
    assert compra_tiene_cantidad_bloqueada("pendiente", "retirado") is True
    # Rechazada o nunca ingresada al depósito: esa historia ya terminó, se
    # bloquea también la cantidad (junto con el precio, quedan cerradas del todo).
    assert compra_tiene_cantidad_bloqueada("rechazado", "cancelado") is True
    assert compra_tiene_cantidad_bloqueada("no_ingresado", "cancelado") is True
    assert compra_tiene_cantidad_bloqueada("pendiente", "pendiente") is False
    assert compra_tiene_cantidad_bloqueada(None, None) is False


def test_compra_tiene_precio_bloqueado():
    assert compra_tiene_precio_bloqueado("rechazado") is True
    assert compra_tiene_precio_bloqueado("no_ingresado") is True
    # A propósito NO mira estado_retiro: retirada o recepcionada no bloquean el precio.
    assert compra_tiene_precio_bloqueado("recepcionado") is False
    assert compra_tiene_precio_bloqueado("pendiente") is False
    assert compra_tiene_precio_bloqueado(None) is False


def test_actualizar_cantidad_compra_pisa_los_valores():
    conexion, cursor = _conexion_falsa([(None, None)])  # SELECT estado, estado_retiro: compra sin procesar

    with patch("app.db.obtener_conexion", return_value=conexion):
        actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")

    consulta_update, parametros_update = cursor.execute.call_args_list[1].args
    assert "UPDATE compras" in consulta_update
    assert "importe" not in consulta_update
    assert "sena" not in consulta_update
    assert parametros_update[-1] == 30
    conexion.commit.assert_called_once()


def test_actualizar_cantidad_compra_recepcionada_no_se_edita():
    conexion, cursor = _conexion_falsa([("recepcionado", "retirado")])  # SELECT estado, estado_retiro

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra ya fue recepcionada, no se puede editar la cantidad."

    assert cursor.execute.call_count == 1
    conexion.commit.assert_not_called()


def test_actualizar_cantidad_compra_retirada_no_se_edita():
    conexion, cursor = _conexion_falsa([("pendiente", "retirado")])  # SELECT estado, estado_retiro

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra ya fue retirada, no se puede editar la cantidad."


def test_actualizar_cantidad_compra_rechazada_no_se_edita_aunque_nunca_se_haya_retirado():
    # Rechazada en Depósito, con el retiro cancelado antes en Logística
    # (así que el auto-retiro nunca la marcó 'retirado'): esa historia ya
    # terminó y no entra al costeo, se bloquea igual.
    conexion, cursor = _conexion_falsa([("rechazado", "cancelado")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            actualizar_cantidad_compra(30, 5, 10, 20, 200, None, "Clark")
            assert False, "tenía que lanzar ValueError"
        except ValueError as error:
            assert str(error) == "Esta compra fue rechazada por calidad, no se puede editar la cantidad."

    conexion.commit.assert_not_called()


def test_actualizar_cantidad_compra_no_ingresada_no_se_edita():
    conexion, cursor = _conexion_falsa([("no_ingresado", "retirado")])

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
            assert str(error) == "Esta compra fue rechazada por calidad, no se puede editar el precio."

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


def test_contar_compras_sin_precio_mismo_filtro_que_listar_devuelve_el_numero():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(4,)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = contar_compras_sin_precio()

    assert resultado == 4
    consulta = cursor.execute.call_args[0][0]
    assert "SELECT COUNT(*)" in consulta
    assert "c.importe IS NULL" in consulta
    assert "c.estado IN ('pendiente', 'recepcionado')" in consulta
    assert "c.estado_retiro IN ('pendiente', 'retirado')" in consulta


def test_listar_compras_pendientes_recepcion_filtra_por_estado_y_guia():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_pendientes_recepcion()

    consulta = cursor.execute.call_args[0][0]
    assert "estado = 'pendiente'" in consulta
    assert "guia_id IS NOT NULL" in consulta
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
    cajones, contenido, kilos, fraccion, compra_id = parametros_update
    assert cajones == 38
    assert contenido == 20  # tomado directo, sin dividir
    assert kilos == 760  # 38 × 20, derivado
    assert fraccion is None
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
    cajones, contenido, kilos, fraccion, compra_id = parametros_update
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
    cajones, contenido, kilos, fraccion, compra_id = parametros_update
    assert cajones == 30
    assert contenido == 25
    assert kilos == 750  # 30 × 25
    assert fraccion is None
    assert compra_id == 30
    conexion.commit.assert_called_once()


def test_corregir_recepcion_compra_articulo_por_unidad_toma_unidades_por_cajon_y_deriva_el_total():
    # Ej. la Palta con "3u" mal cargado: la corrección es 80 por cajón
    # (lo que Depósito mira), no 2400 en total.
    conexion, cursor = _conexion_falsa([("recepcionado", "unidad")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(30, cantidad_cajones_real=30, valor_real=80)

    _, parametros_update = cursor.execute.call_args_list[1].args
    cajones, contenido, kilos, fraccion, compra_id = parametros_update
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


def test_listar_compras_procesadas_hoy_retiro_filtra_por_tipo_y_fecha():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_compras_procesadas_hoy_retiro("Clark", date(2026, 8, 17))

    consulta, parametros = cursor.execute.call_args[0]
    assert "c.tipo_retiro = %s" in consulta
    assert "estado_retiro IN ('retirado', 'cancelado')" in consulta
    assert "retiro_procesado_el::date = %s" in consulta
    assert "ORDER BY c.retiro_procesado_el DESC" in consulta
    assert parametros == ("Clark", date(2026, 8, 17))


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
    assert "c.procesada_el::date = %s" in consulta
    assert "ORDER BY c.procesada_el DESC" in consulta
    assert parametros == (date(2026, 8, 17),)


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
    # La misma fecha de corte se usa dos veces: para filtrar lo viejo y
    # para chequear que no quede ningún renglón dentro del período a
    # conservar con ese mismo foto_ruta (NOT EXISTS).
    assert parametros == (date(2023, 8, 15), date(2023, 8, 15))
    assert "NOT EXISTS" in consulta
    assert "fecha_operacion < %s" in consulta
    assert "fecha_operacion >= %s" in consulta


def test_listar_fotos_para_limpiar_vacio_da_lista_vacia():
    conexion, cursor = _conexion_falsa(filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_fotos_para_limpiar(date(2023, 8, 15))

    assert resultado == []


def test_limpiar_foto_ruta_de_compras_actualiza_y_comitea():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        limpiar_foto_ruta_de_compras("2020-01-01/a.jpg")

    cursor.execute.assert_called_once()
    consulta, parametros = cursor.execute.call_args[0]
    assert "UPDATE compras SET foto_ruta = NULL" in consulta
    assert parametros == ("2020-01-01/a.jpg",)
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
    conexion, cursor = _conexion_falsa(
        filas_fetchall=[(1, 500.0, date(2026, 8, 16)), (2, 350.0, date(2026, 8, 10))]
    )
    cursor.description = [("articulo_id",), ("precio",), ("vigente_desde",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_precios_vigentes_por_cliente(1, date(2026, 8, 16))

    assert resultado == [
        {"articulo_id": 1, "precio": 500.0, "vigente_desde": date(2026, 8, 16)},
        {"articulo_id": 2, "precio": 350.0, "vigente_desde": date(2026, 8, 10)},
    ]
    consulta = cursor.execute.call_args[0][0]
    assert "vigente_desde" in consulta


def test_listar_precios_anteriores_por_cliente_trae_la_fila_previa_a_la_vigente():
    # Para la columna "Precio anterior" del Excel: la fila #2 (orden = 2 en
    # el ROW_NUMBER, la que regía justo antes de la vigente), no la #1.
    conexion, cursor = _conexion_falsa(filas_fetchall=[(2, 350.0)])
    cursor.description = [("articulo_id",), ("precio",)]

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = listar_precios_anteriores_por_cliente(1, date(2026, 8, 16))

    assert resultado == [{"articulo_id": 2, "precio": 350.0}]
    consulta, parametros = cursor.execute.call_args[0]
    assert "ROW_NUMBER()" in consulta
    assert "WHERE orden = 2" in consulta
    assert parametros == (1, date(2026, 8, 16))


def test_guardar_precios_cliente_inserta_con_vigente_desde_hoy_sin_pisar_lo_viejo():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_precios_cliente(1, [{"articulo_id": 7, "precio": 550.0}, {"articulo_id": 3, "precio": 900.0}])

    assert cursor.execute.call_count == 2
    for llamada in cursor.execute.call_args_list:
        consulta, parametros = llamada.args
        assert "INSERT INTO precios_venta_historial" in consulta
        assert "vigente_desde" in consulta
        assert "CURRENT_DATE" in consulta
        assert "ON CONFLICT (articulo_id, cliente_id, vigente_desde)" in consulta
        assert "DO UPDATE" in consulta
    assert cursor.execute.call_args_list[0].args[1] == (7, 1, 550.0, None)
    assert cursor.execute.call_args_list[1].args[1] == (3, 1, 900.0, None)
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
        guardar_precios_cliente(1, [{"articulo_id": 7, "precio": 550.0}], foto_ruta="2026-08-16/dia-123-abc.jpg")

    consulta, parametros = cursor.execute.call_args_list[0].args
    assert "foto_ruta" in consulta
    assert "COALESCE(EXCLUDED.foto_ruta, precios_venta_historial.foto_ruta)" in consulta
    assert parametros == (7, 1, 550.0, "2026-08-16/dia-123-abc.jpg")


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
