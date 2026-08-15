from datetime import date
from unittest.mock import MagicMock, patch

from app.db import (
    eliminar_compra,
    limpiar_foto_ruta_de_compras,
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
