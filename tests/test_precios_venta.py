from core.precios_venta import calcular_cambios_de_precios


def _fila(articulo_id=1, precio_original=None, precio_nuevo=None):
    """Una fila del formulario. El precio es de la FICHA: el id de la ficha
    es 900 + el del artículo, a propósito distinto para que confundir las
    dos claves rompa el test."""
    return {"ficha_id": 900 + articulo_id, "precio_original": precio_original, "precio_nuevo": precio_nuevo}


def test_precio_sin_cambios_no_genera_nada():
    filas = [_fila(precio_original=500.0, precio_nuevo=500.0)]

    assert calcular_cambios_de_precios(filas) == []


def test_precio_editado_genera_una_fila():
    filas = [_fila(articulo_id=7, precio_original=500.0, precio_nuevo=550.0)]

    assert calcular_cambios_de_precios(filas) == [{"ficha_id": 907, "precio": 550.0}]


def test_articulo_sin_precio_previo_con_precio_nuevo_genera_alta():
    filas = [_fila(articulo_id=3, precio_original=None, precio_nuevo=800.0)]

    assert calcular_cambios_de_precios(filas) == [{"ficha_id": 903, "precio": 800.0}]


def test_campo_vacio_no_genera_nada_aunque_tenga_precio_original():
    # No hay forma de "dar de baja" un precio desde esta pantalla: dejar
    # el campo en blanco es "no lo toqué", no "sacalo".
    filas = [_fila(precio_original=500.0, precio_nuevo=None)]

    assert calcular_cambios_de_precios(filas) == []


def test_campo_vacio_sin_precio_original_no_genera_nada():
    filas = [_fila(precio_original=None, precio_nuevo=None)]

    assert calcular_cambios_de_precios(filas) == []


def test_varios_articulos_mezclados_en_un_mismo_guardado():
    filas = [
        _fila(articulo_id=1, precio_original=500.0, precio_nuevo=500.0),  # sin cambios
        _fila(articulo_id=2, precio_original=300.0, precio_nuevo=320.0),  # editado
        _fila(articulo_id=3, precio_original=None, precio_nuevo=900.0),  # nuevo
        _fila(articulo_id=4, precio_original=200.0, precio_nuevo=None),  # no tocado
    ]

    assert calcular_cambios_de_precios(filas) == [
        {"ficha_id": 902, "precio": 320.0},
        {"ficha_id": 903, "precio": 900.0},
    ]
