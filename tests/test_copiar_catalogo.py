"""Tests de scripts/copiar_catalogo_empresa.py — las reglas de seguridad, con conexiones simuladas.

La copia real de punta a punta se probó contra un Postgres real al construir
el script; acá se fija lo que NO puede ser de otra manera: en seco no escribe,
destino con datos se rechaza, y la copia preserva IDs y ajusta secuencias.
"""

from unittest.mock import MagicMock, patch

import pytest

from scripts.copiar_catalogo_empresa import TABLAS_A_COPIAR, main

CANTIDAD_TABLAS = len(TABLAS_A_COPIAR)


def _cursor_falso(fetchone=None, fetchall=None, description=None):
    cursor = MagicMock()
    if fetchone is not None:
        cursor.fetchone.side_effect = fetchone
    if fetchall is not None:
        cursor.fetchall.side_effect = fetchall
    cursor.description = description or [("id",), ("nombre",)]
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _conexion_con(cursor):
    conexion = MagicMock()
    conexion.cursor.return_value = cursor
    return conexion


def _correr(argv, cursor_origen, cursor_destino):
    conexion_origen = _conexion_con(cursor_origen)
    conexion_destino = _conexion_con(cursor_destino)
    with (
        patch("scripts.copiar_catalogo_empresa.psycopg2") as psycopg2_falso,
        patch("sys.argv", argv),
        patch.dict("os.environ", {"DATABASE_URL_ORIGEN": "postgresql://o", "DATABASE_URL_DESTINO": "postgresql://d"}),
    ):
        psycopg2_falso.connect.side_effect = [conexion_origen, conexion_destino]
        main()
    return conexion_origen, conexion_destino


def test_en_seco_no_escribe_nada_en_destino():
    cursor_origen = _cursor_falso(
        fetchone=[(2,)] * CANTIDAD_TABLAS,  # COUNT por tabla
        fetchall=[[], []],  # parámetros de clientes y costos de envase
    )
    cursor_destino = _cursor_falso(fetchone=[(0,)] * CANTIDAD_TABLAS)  # destino vacío

    _, conexion_destino = _correr(["copiar"], cursor_origen, cursor_destino)

    cursor_destino.executemany.assert_not_called()
    conexion_destino.commit.assert_not_called()
    # En seco tampoco toca secuencias: ningún execute de INSERT/setval.
    for llamada in cursor_destino.execute.call_args_list:
        assert "INSERT" not in llamada.args[0] and "setval" not in llamada.args[0]


def test_destino_con_datos_se_niega_y_no_copia():
    cursor_origen = _cursor_falso(fetchone=[(2,)] * CANTIDAD_TABLAS, fetchall=[[], []])
    cursor_destino = _cursor_falso(fetchone=[(3,)] * CANTIDAD_TABLAS)  # destino CON datos

    with pytest.raises(SystemExit) as salida:
        _correr(["copiar", "--ejecutar"], cursor_origen, cursor_destino)

    assert salida.value.code == 1
    cursor_destino.executemany.assert_not_called()


def test_ejecutar_copia_preservando_ids_y_ajusta_secuencias():
    filas = [(1, "Kiwi"), (2, "Mango")]
    cursor_origen = _cursor_falso(
        fetchone=[(2,)] * CANTIDAD_TABLAS,
        fetchall=[[], []] + [filas] * CANTIDAD_TABLAS,  # parámetros + una lectura por tabla
    )
    cursor_destino = _cursor_falso(fetchone=[(0,)] * CANTIDAD_TABLAS)

    _, conexion_destino = _correr(["copiar", "--ejecutar"], cursor_origen, cursor_destino)

    # Un INSERT por tabla, siempre con OVERRIDING SYSTEM VALUE (IDs preservados,
    # así las FKs que viajan con esos IDs quedan bien apuntadas sin remapear).
    inserts = cursor_destino.executemany.call_args_list
    assert len(inserts) == CANTIDAD_TABLAS
    for llamada in inserts:
        assert "OVERRIDING SYSTEM VALUE" in llamada.args[0]
        assert llamada.args[1] == filas

    # Y un setval por tabla, para que el próximo ID autogenerado no choque.
    setvals = [llamada for llamada in cursor_destino.execute.call_args_list if "setval" in llamada.args[0]]
    assert len(setvals) == CANTIDAD_TABLAS

    conexion_destino.commit.assert_called_once()
