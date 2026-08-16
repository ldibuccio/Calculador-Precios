from core.conceptos_cliente import calcular_cambio_de_utilidad, calcular_cambios_de_tasas


def _fila(nombre_original="", valor_original=None, nombre="", valor=None, baja=False):
    return {
        "nombre_original": nombre_original,
        "valor_original": valor_original,
        "nombre": nombre,
        "valor": valor,
        "baja": baja,
    }


def test_fila_existente_sin_cambios_no_genera_nada():
    filas = [_fila(nombre_original="Flete", valor_original=0.04, nombre="Flete", valor=0.04)]

    assert calcular_cambios_de_tasas("resta", filas) == []


def test_fila_existente_con_porcentaje_editado_genera_una_fila():
    filas = [_fila(nombre_original="Flete", valor_original=0.04, nombre="Flete", valor=0.05)]

    assert calcular_cambios_de_tasas("resta", filas) == [
        {"nombre_parametro": "Flete", "tipo": "resta", "valor": 0.05}
    ]


def test_fila_nueva_completa_genera_alta():
    filas = [_fila(nombre="Premio", valor=0.02)]

    assert calcular_cambios_de_tasas("suma", filas) == [{"nombre_parametro": "Premio", "tipo": "suma", "valor": 0.02}]


def test_fila_nueva_vacia_no_genera_nada():
    filas = [_fila()]

    assert calcular_cambios_de_tasas("suma", filas) == []


def test_fila_nueva_dada_de_baja_no_genera_nada():
    # No tiene sentido: nunca existió, no hay nada que dar de baja.
    filas = [_fila(nombre="Premio", valor=0.02, baja=True)]

    assert calcular_cambios_de_tasas("suma", filas) == []


def test_fila_existente_dada_de_baja_genera_fila_en_cero():
    filas = [_fila(nombre_original="Flete", valor_original=0.04, nombre="Flete", valor=0.04, baja=True)]

    assert calcular_cambios_de_tasas("resta", filas) == [{"nombre_parametro": "Flete", "tipo": "resta", "valor": 0.0}]


def test_fila_existente_renombrada_da_de_baja_la_vieja_y_alta_la_nueva():
    filas = [_fila(nombre_original="Flete", valor_original=0.04, nombre="Flete y logística", valor=0.04)]

    assert calcular_cambios_de_tasas("resta", filas) == [
        {"nombre_parametro": "Flete", "tipo": "resta", "valor": 0.0},
        {"nombre_parametro": "Flete y logística", "tipo": "resta", "valor": 0.04},
    ]


def test_varias_filas_mezcladas_en_un_mismo_guardado():
    filas = [
        _fila(nombre_original="IVA", valor_original=0.21, nombre="IVA", valor=0.21),  # sin cambios
        _fila(nombre_original="Percepcion", valor_original=0.03, nombre="Percepcion", valor=0.05),  # editada
        _fila(nombre_original="Premio viejo", valor_original=0.01, baja=True, nombre="Premio viejo", valor=0.01),  # baja
        _fila(nombre="Fondo publicidad", valor=0.015),  # nueva
    ]

    cambios = calcular_cambios_de_tasas("suma", filas)

    assert cambios == [
        {"nombre_parametro": "Percepcion", "tipo": "suma", "valor": 0.05},
        {"nombre_parametro": "Premio viejo", "tipo": "suma", "valor": 0.0},
        {"nombre_parametro": "Fondo publicidad", "tipo": "suma", "valor": 0.015},
    ]


def test_calcular_cambio_de_utilidad_sin_cambios_devuelve_none():
    assert calcular_cambio_de_utilidad(0.20, 0.20) is None


def test_calcular_cambio_de_utilidad_editada_devuelve_la_fila():
    assert calcular_cambio_de_utilidad(0.20, 0.25) == {
        "nombre_parametro": "utilidad_objetivo",
        "tipo": "utilidad",
        "valor": 0.25,
    }


def test_calcular_cambio_de_utilidad_sin_valor_nuevo_devuelve_none():
    assert calcular_cambio_de_utilidad(0.20, None) is None


def test_calcular_cambio_de_utilidad_sin_original_y_con_nuevo_devuelve_la_fila():
    # Caso borde: cliente cargado antes de que existiera este campo (no
    # debería pasar con el flujo actual, pero por las dudas).
    assert calcular_cambio_de_utilidad(None, 0.20) == {
        "nombre_parametro": "utilidad_objetivo",
        "tipo": "utilidad",
        "valor": 0.20,
    }
