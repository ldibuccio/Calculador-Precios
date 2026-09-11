import inspect
from datetime import date, datetime, time
import pytest
from unittest.mock import MagicMock, call, patch

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
    recepcionar_compra_en_caja_propia,
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
        resultado = eliminar_compra(30)

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
        resultado = eliminar_compra(30)

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
        resultado = eliminar_compra(30)

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
        resultado = eliminar_compra(30)

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
        resultado = eliminar_compra(30)

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
        resultado = eliminar_compra(30)

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
        resultado = eliminar_compra(30)

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
            eliminar_compra(30)
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
            eliminar_compra(30)
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
            eliminar_compra(30)
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

    conexion, cursor = _conexion_falsa([(date(2026, 9, 5),), (105,), (0,)])
    momento = datetime(2026, 9, 7, 12, 0)

    with patch("app.db.obtener_conexion", return_value=conexion):
        crear_compra(
            date(2026, 9, 7), 5, 200, 10, 16, 160, None, 0, None, "Clark",
            ingreso_directo_deposito=True, recepcionada_el=momento,
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
        conexion, cursor = _conexion_falsa([(date(2026, 9, 5),), (105,), (0,)])
        with patch("app.db.obtener_conexion", return_value=conexion):
            if tiene_que_entrar:
                crear_compra(dia, 5, 200, 10, 16, 160, None, 0, None, "Clark",
                             ingreso_directo_deposito=True,
                             recepcionada_el=datetime(dia.year, dia.month, dia.day, 12, 0))
            else:
                with pytest.raises(ValueError) as rechazo:
                    crear_compra(dia, 5, 200, 10, 16, 160, None, 0, None, "Clark",
                                 ingreso_directo_deposito=True,
                                 recepcionada_el=datetime(dia.year, dia.month, dia.day, 12, 0))
                assert "POSTERIOR al corte" in str(rechazo.value)
                assert "05/09/2026" in str(rechazo.value)


def test_la_fecha_de_recepcion_NO_se_puede_elegir_en_una_carga_normal():
    """La perilla es solo del ingreso directo. En la carga normal la compra
    nace 'pendiente' y la fecha de recepción la pone Depósito al recibirla:
    dejarla elegir ahí sería fechar una recepción que todavía no pasó."""
    from app.db import crear_compra

    conexion, _ = _conexion_falsa([(105,), (0,)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError) as rechazo:
            crear_compra(date(2026, 9, 7), 5, 200, 10, 16, 160, None, None, None, "Clark",
                         recepcionada_el=datetime(2026, 9, 7, 12, 0))
    assert "solo se puede elegir en un ingreso directo" in str(rechazo.value)


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

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
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

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
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
    conexion, cursor = _conexion_falsa([("recepcionado", "kilo")])
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
    cursor.fetchall.return_value = []   # sin guía R en origen: el camino normal

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(30, cantidad_cajones_real=30, valor_real=80)

    _, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
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

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
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
    cursor.fetchall.return_value = []   # sin guía R en origen: el camino normal

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(
            30, cantidad_cajones_real=7, valor_real=25,
            cantidad_cajones_rechazada=3, motivo_rechazo="golpeado",
        )

    consulta_update, parametros_update = _sql_y_parametros_que_contienen(cursor, "UPDATE compras")
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
    conexion, cursor = _conexion_falsa([(5,)])  # SELECT COUNT(*): 5 compras en total
    cursor.rowcount = 3  # solo 3 se pudieron borrar (2 protegidas)

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
    # LOS CINCO TIPOS DEL BUCKET EN LA MISMA PASADA. El que no esté acá no
    # se borra NUNCA: no aparece siquiera como candidato. Y eso no es solo
    # desperdicio — el bucket prefija por tipo solo lo NUEVO, así que
    # converge únicamente si lo viejo se vence (ver core/storage.py).
    assert "FROM fotos_recepcion" in consulta
    assert "FROM fotos_pedido" in consulta
    assert "FROM precios_venta_historial" in consulta
    assert "FROM fotos_merma" in consulta
    # Y la merma son DOS patas, no una: sus dos dueños posibles viven en
    # tablas distintas (movimientos_stock para el stock normal,
    # remitos_segunda para el pool). Con una sola, las fotos del otro dueño
    # serían inmortales.
    assert consulta.count("FROM fotos_merma") == 2
    assert "JOIN movimientos_stock m" in consulta
    assert "JOIN remitos_segunda r" in consulta
    assert parametros == (date(2023, 8, 15),) * 6, (
        "el corte va a las SEIS patas del UNION, y es el mismo: una sola perilla"
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
    assert len(consultas) == 5, (
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


def test_asignar_ficha_a_reproceso_solo_toca_la_ficha():
    # Los consumos y el costo se congelaron al cargar la guía: asignar la
    # ficha es decir a qué producto de venta fueron esas cajas, no rehacer
    # el FIFO.
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, 1, False), (7, 1)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        asignar_ficha_a_reproceso(12, 901)

    consulta, parametros = cursor.execute.call_args.args
    assert consulta == "UPDATE reprocesos SET ficha_id = %s WHERE id = %s"
    assert parametros == (901, 12)
    # Nada de recalcular: los consumos no se tocan.
    assert not any("reprocesos_consumos" in c.args[0] for c in cursor.execute.call_args_list)
    conexion.commit.assert_called_once()


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
    conexion, cursor = _conexion_falsa(filas_fetchone=[(7, None, False), (7, 2)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        asignar_ficha_a_reproceso(12, 901)

    consulta, parametros = cursor.execute.call_args.args
    assert consulta == "UPDATE reprocesos SET ficha_id = %s WHERE id = %s"
    assert parametros == (901, 12)
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
    assert "UPDATE reprocesos SET ficha_id = %s" in consulta
    assert parametros == (None, 12)
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
    conexion, cursor = _conexion_falsa(filas_fetchone=[(0,), None])

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
    # El primer fetchone es el conteo de guías R: sin guías, sigue de largo
    # y borra como siempre.
    conexion, cursor = _conexion_falsa([(0,), (1, 5, 100, 6, "kilo", False, "BERENJENA", None)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        eliminar_ficha(10)

    consulta_delete = cursor.execute.call_args_list[1].args[0]
    assert "DELETE FROM fichas_logistica WHERE id = %s" in consulta_delete
    assert "RETURNING" in consulta_delete
    consulta_foto, parametros_foto = cursor.execute.call_args_list[2].args
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
    assert "SET armado_el = NULL, cantidad_armada = NULL" in consulta
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
    assert "SET anulado_el = now(), armado_el = NULL, cantidad_armada = NULL, kilos_enviados = NULL" in consulta
    # Un renglón anulado no manda nada: su corrección de lotes tampoco.
    assert "DELETE FROM pedidos_renglones_lotes_elegidos" in cursor.execute.call_args_list[1].args[0]
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
    # Acá el renglón anulado SÍ viene, y es a propósito: Buscar Pedidos los
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
                          ("segunda_producida",), ("segunda_de_rechazos",), ("segunda_remitida",)]
    cursor.fetchall.return_value = [(1, "Banana", 40, 15, 2, -3, 6, 10, 5, 4, 2)]

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
    # La segunda es un pool APARTE: lo producido en reprocesos + lo que
    # entró por rechazos que no volvieron al stock, − lo remitido.
    assert filas[0]["segunda"] == 5 + 4 - 2
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
                          ("segunda_producida",), ("segunda_de_rechazos",), ("segunda_remitida",)]
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
        # proveedor_devolucion_id: solo lo usa la devolución al proveedor.
        None,
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
        # proveedor_devolucion_id: solo lo usa la devolución al proveedor.
        None,
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
        # proveedor_devolucion_id: solo lo usa la devolución al proveedor.
        None,
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
        "reproceso", 12.0, None, None, None,
        # proveedor_devolucion_id: solo lo usa la devolución al proveedor.
        None,
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
        # proveedor_devolucion_id: solo lo usa la devolución al proveedor.
        None,
    )


def test_la_ficha_que_SOLO_TIENE_MERMA_no_se_cae_de_la_cuenta():
    """LA PATA FÁCIL DE OLVIDAR. La merma nueva resta en el SELECT final,
    pero si `mermas_ficha` no está también en el UNION de `fichas_con_algo`,
    una ficha cuyo ÚNICO movimiento sea una merma no existe para la consulta:
    la resta estaría bien escrita y no se haría nunca.

    Se mira el UNION y no el resultado porque los otros tres términos ya
    están: un fixture con armados encima taparía el agujero sin querer.
    """
    from app.db import _SQL_STOCK_PARTIDO

    union = _SQL_STOCK_PARTIDO.split("fichas_con_algo AS (")[1].split(")")[0]
    for pata in ("armadas", "salidas_ficha", "reingresos_ficha", "mermas_ficha"):
        assert f"FROM {pata}" in union, pata
    # Y LAS PATAS ENTERAS, no solo el nombre a la vista: cuatro SELECT unidos
    # por tres UNION. Sin esto el test pasa con el `UNION` borrado —el nombre
    # sigue estando en el texto— que es exactamente como se descubrió que no
    # miraba lo que decía mirar.
    assert union.count("SELECT") == 4
    assert union.count("UNION") == 3


def test_la_merma_por_ficha_usa_LA_MISMA_VENTANA_que_los_otros_terminos():
    """Si ésta mirara toda la historia y las otras solo lo posterior al corte,
    la resta mezclaría dos eras. Medido con el canario: corrida con `>=` el
    número se mueve (7 cajas contra 3), así que el recorte hace trabajo real.

    Se recorta el trozo de la CTE para no matchear el `> corte.fecha` de los
    otros tres — el assert de substring tiene que calificar de quién habla.
    """
    from app.db import _SQL_STOCK_PARTIDO

    trozo = _SQL_STOCK_PARTIDO.split("mermas_ficha AS (")[1].split("), fichas_con_algo")[0]
    assert "m.tipo = 'merma'" in trozo
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
    consulta = cursor.execute.call_args.args[0]
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
    assert inserts[0].args[1] == (
        1, date(2026, 8, 25), 6, 4, 1, 1, 6600.0, 1650.0, 7, None, False, "normal", None
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
    ]

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero = crear_reproceso(1, 44, 40, 0, 4, date(2026, 8, 31))

    assert numero == 16
    inserts = [c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0]]
    assert inserts[1].args[1] == (16, "compra", 101, 101, 44.0, 1000.0)


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
        eliminar_compra(30)
    sql_de_a_uno = _sql_que_contiene(cursor, "DELETE FROM compras")

    conexion, cursor = _conexion_falsa([(7,)])
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
        eliminar_compra(30)

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
    # Es el criterio de Buscar Pedidos (_grupos_buscar_pedidos), NO el de
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
# El fixture de estos tests lleva DOS lotes a propósito y el segundo es el
# RIVAL: un cajón viejo del mismo artículo, que es el que el FIFO elegiría si
# el consumo no fuera dirigido. Con un solo lote —el fixture mínimo, que es el
# que uno escribe sin pensarlo— la implementación correcta y la equivocada dan
# exactamente el mismo resultado, porque "el más viejo" y "el correcto" pasan a
# ser el mismo lote. Ver CLAUDE.md, "Un caso que anda con el sistema VACÍO".

_COMPRA_EN_ORIGEN = 777
_CAJON_VIEJO = 555


def _lotes_con_rival():
    """El cajón viejo (rival) y la compra que llegó armada, en ese orden de fecha."""
    return [
        _lote_compra(_CAJON_VIEJO, date(2026, 8, 20), 40.0, 1000.0),
        _lote_compra(_COMPRA_EN_ORIGEN, date(2026, 8, 25), 10.0, 1200.0),
    ]


def _conexion_para_en_origen(numero_guia=99, estado_compra="pendiente"):
    """La cola de fetchone del camino entero, en orden de ejecución."""
    conexion, cursor = _conexion_falsa(
        filas_fetchone=[
            (1, estado_compra),          # SELECT articulo_id, estado FROM compras
            (1, 7),                      # SELECT articulo_id, cliente_id FROM fichas_logistica
            ("kilo",),                   # SELECT a.unidad_compra (dentro de _recepcionar_compra)
            ("retirado",),               # SELECT estado_retiro (auto-retirar: ya estaba)
            (date(2026, 8, 25),),        # la fecha del lote de la compra recién escrita
            _CORTE,                      # el piso de fecha de _crear_reproceso
            (numero_guia,),              # INSERT INTO reprocesos RETURNING id
        ]
    )
    cursor.description = COLUMNAS_LOTES
    cursor.fetchall.side_effect = [_lotes_con_rival(), []]
    return conexion, cursor


def test_el_fixture_de_la_guia_en_origen_TIENE_un_rival_que_el_FIFO_ELEGIRIA():
    """El test que cuida al test: sin rival, el de abajo no distingue nada.

    Corre el FIFO real sobre los mismos lotes del fixture y exige que la
    propuesta por defecto caiga en el CAJÓN VIEJO. Si algún día alguien
    "simplifica" el fixture dejando un solo lote, este test cae y avisa que
    el de abajo dejó de poder fallar — que es exactamente la forma de bug
    que no deja rastro.
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


def test_la_guia_en_origen_consume_SU_COMPRA_y_no_el_cajon_mas_viejo():
    """EL test del camino. Con stock viejo del mismo artículo en el depósito.

    Sin el reparto dirigido el FIFO se lleva el cajón viejo y deja la caja que
    llegó armada como lote CRUDO: el cajón que sigue en el piso figuraría
    convertido y las cajas que llegaron figurarían como cajón. Ningún total se
    descuadra, así que no habría síntoma — lo único que cambia es cuál lote
    quedó trabajado, que es justo lo que la pared del armado mira al despachar.
    """
    conexion, cursor = _conexion_para_en_origen()

    with patch("app.db.obtener_conexion", return_value=conexion):
        numero, aviso = recepcionar_compra_en_caja_propia(_COMPRA_EN_ORIGEN, 10, 16, ficha_id=3)

    assert (numero, aviso) == (99, None)
    consumos = [c for c in cursor.execute.call_args_list if "INSERT INTO reprocesos_consumos" in c.args[0]]
    # UNO solo, y de SU compra. El cajón viejo queda intacto.
    assert len(consumos) == 1
    assert consumos[0].args[1] == (99, "compra", _COMPRA_EN_ORIGEN, _COMPRA_EN_ORIGEN, 10.0, 1200.0)


def test_la_guia_en_origen_es_UNO_A_UNO_y_se_marca_como_tal():
    """La estructura ENTERA del INSERT, no tres campos de doce.

    Un test que compara un subconjunto no protege los que no mira, y acá lo
    que importa está justo en las dos últimas columnas: `tipo` y la compra de
    la que salió. Sin ellas la guía se vería como un armado del galpón.
    """
    conexion, cursor = _conexion_para_en_origen()

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra_en_caja_propia(_COMPRA_EN_ORIGEN, 10, 16, ficha_id=3)

    cabecera = next(c for c in cursor.execute.call_args_list if "INSERT INTO reprocesos\n" in c.args[0])
    assert cabecera.args[1] == (
        1, date(2026, 8, 25), 10.0, 10.0,   # artículo, fecha, tomados, primera: UNO A UNO
        0, 0,                              # segunda y merma: el reenvasado no pasó acá
        12000.0, 1200.0,                   # costo del lote de SU compra, todo a la primera
        7, 3,                              # cliente (sale de la ficha) y ficha
        False, "en_origen", _COMPRA_EN_ORIGEN,
    )


def test_la_guia_en_origen_y_su_recepcion_van_en_UNA_SOLA_transaccion():
    """Partidas, una falla en el medio deja la compra recepcionada SIN su guía.

    El stock quedaría crudo y la ficha sin sus cajas, y nada avisaría: la
    compra se vería perfecta. Un solo commit, y el UPDATE de la recepción y el
    INSERT de la guía sobre el MISMO cursor.
    """
    conexion, cursor = _conexion_para_en_origen()

    with patch("app.db.obtener_conexion", return_value=conexion):
        recepcionar_compra_en_caja_propia(_COMPRA_EN_ORIGEN, 10, 16, ficha_id=3)

    conexion.commit.assert_called_once()
    conexion.cursor.assert_called_once()
    hechos = [c.args[0] for c in cursor.execute.call_args_list]
    assert any("UPDATE compras" in sql and "estado = 'recepcionado'" in sql for sql in hechos)
    assert any("INSERT INTO reprocesos\n" in sql for sql in hechos)


def test_la_guia_en_origen_NO_se_carga_si_la_ficha_es_de_otro_articulo():
    """La guarda va donde se ESCRIBE: un formulario armado a mano no ve el `<select>`."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[(1, "pendiente"), (2, 7)])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="otro artículo"):
            recepcionar_compra_en_caja_propia(_COMPRA_EN_ORIGEN, 10, 16, ficha_id=3)

    assert not [c for c in cursor.execute.call_args_list if "UPDATE compras" in c.args[0]]
    conexion.commit.assert_not_called()


def test_la_guia_en_origen_NO_se_carga_sobre_una_compra_YA_recepcionada():
    conexion, cursor = _conexion_falsa(filas_fetchone=[(1, "recepcionado")])

    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="ya está recepcionada"):
            recepcionar_compra_en_caja_propia(_COMPRA_EN_ORIGEN, 10, 16, ficha_id=3)

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
    # Se LEE la consulta de lotes de verdad, no se copia la expresión acá:
    # copiada envejece en silencio el día que una de las dos cambie.
    consulta_de_lotes = inspect.getsource(db._entradas_y_salidas_stock_varios)
    assert db._SQL_FECHA_DEL_LOTE_DE_COMPRA.format(col="c.procesada_el") in consulta_de_lotes
    assert "_SQL_FECHA_DEL_LOTE_DE_COMPRA" in inspect.getsource(db.recepcionar_compra_en_caja_propia)


def test_corregir_recepcion_SE_BLOQUEA_si_la_compra_tiene_una_guia_en_origen_viva():
    """Corregir los cajones dejaría la compra en 12 y su guía en 10, sin que nada avise.

    Y el error NOMBRA la guía: un bloqueo que no dice qué lo retiene manda a
    adivinar, y el que está corrigiendo no tiene cómo saber que existe.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[("recepcionado", "kilo")])
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
    conexion, cursor = _conexion_falsa(filas_fetchone=[("recepcionado", "kilo")])
    cursor.fetchall.return_value = []

    with patch("app.db.obtener_conexion", return_value=conexion):
        corregir_recepcion_compra(_COMPRA_EN_ORIGEN, 12, 16)

    assert [c for c in cursor.execute.call_args_list if "UPDATE compras" in c.args[0]]
    conexion.commit.assert_called_once()
    consulta = _sql_que_contiene(cursor, "FROM reprocesos")
    assert "compra_origen_id = %s" in consulta and "anulado_el IS NULL" in consulta
