from datetime import date
from unittest.mock import MagicMock, patch

from app.db import (
    actualizar_cliente,
    crear_cliente,
    eliminar_compra,
    guardar_precios_cliente,
    limpiar_foto_ruta_de_compras,
    listar_clientes,
    listar_conceptos_editables_por_cliente,
    listar_fotos_para_limpiar,
    obtener_uso_storage_bucket,
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
            ("2026-08-13/n07p41-123-abcdef12.jpg",),  # SELECT foto_ruta
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
            ("2026-08-13/n07p41-123-abcdef12.jpg",),  # SELECT foto_ruta
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
            ("2026-08-13/listado-abc123.jpg",),  # SELECT foto_ruta
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
            ("2026-08-13/listado-abc123.jpg",),  # SELECT foto_ruta
            (0,),  # SELECT COUNT(*): ya no queda ninguna compra usándola
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado == "2026-08-13/listado-abc123.jpg"


def test_eliminar_compra_sin_foto_no_cuenta_referencias():
    conexion, cursor = _conexion_falsa(
        [
            (None,),  # SELECT foto_ruta: esta compra no tenía foto
        ]
    )

    with patch("app.db.obtener_conexion", return_value=conexion):
        resultado = eliminar_compra(30)

    assert resultado is None
    # Solo el SELECT foto_ruta y el DELETE — sin el SELECT COUNT de más.
    assert cursor.execute.call_count == 2


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
    assert cursor.execute.call_args_list[0].args[1] == (7, 1, 550.0)
    assert cursor.execute.call_args_list[1].args[1] == (3, 1, 900.0)
    conexion.commit.assert_called_once()


def test_guardar_precios_cliente_sin_cambios_no_ejecuta_nada():
    conexion, cursor = _conexion_falsa()

    with patch("app.db.obtener_conexion", return_value=conexion):
        guardar_precios_cliente(1, [])

    cursor.execute.assert_not_called()
    conexion.commit.assert_not_called()
