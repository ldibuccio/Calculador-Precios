from unittest.mock import MagicMock, patch

from app.db import eliminar_compra


def _conexion_falsa(filas_fetchone):
    """Arma una conexión y un cursor falsos: cada fetchone() devuelve la próxima fila de la lista, en orden."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = filas_fetchone
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
