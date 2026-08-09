from core.matcheo_comanda import (
    adivinar_articulo,
    adivinar_proveedor,
    construir_codigo_puesto,
    normalizar_texto,
)


def test_normalizar_texto_minusculas_sin_acentos_sin_espacios_de_mas():
    assert normalizar_texto("  Tomate   Redondo  ") == "tomate redondo"
    assert normalizar_texto("Morrón Rojo") == "morron rojo"


def test_normalizar_texto_vacio_o_none():
    assert normalizar_texto("") == ""
    assert normalizar_texto(None) == ""


def test_construir_codigo_puesto_nave_forma_basica():
    assert construir_codigo_puesto("nave", "7", "41") == "N07P41"


def test_construir_codigo_puesto_libre_forma_basica():
    assert construir_codigo_puesto("libre", "3", "38") == "L03P38"


def test_construir_codigo_puesto_ya_con_dos_digitos():
    assert construir_codigo_puesto("nave", "07", "41") == "N07P41"


def test_construir_codigo_puesto_ignora_texto_alrededor_de_los_numeros():
    assert construir_codigo_puesto("nave", "Pab. 7", "P.41") == "N07P41"


def test_construir_codigo_puesto_tipo_invalido_da_none():
    assert construir_codigo_puesto(None, "7", "41") is None
    assert construir_codigo_puesto("otro", "7", "41") is None


def test_construir_codigo_puesto_sin_numero_pabellon_da_none():
    assert construir_codigo_puesto("nave", "", "41") is None
    assert construir_codigo_puesto("nave", None, "41") is None


def test_construir_codigo_puesto_sin_puesto_da_none():
    assert construir_codigo_puesto("nave", "7", "") is None


def test_construir_codigo_puesto_numero_de_tres_digitos_da_none():
    assert construir_codigo_puesto("nave", "123", "41") is None
    assert construir_codigo_puesto("nave", "7", "123") is None


PROVEEDORES_DE_PRUEBA = [
    {"id": 200, "codigo_puesto": "N07P41", "nombre": "Saturno"},
    {"id": 201, "codigo_puesto": "L03P38", "nombre": "Frutamax"},
]


def test_adivinar_proveedor_por_codigo_exacto():
    proveedor_leido = {"nombre": "", "tipo_pabellon": "nave", "numero_pabellon": "7", "puesto": "41"}
    resultado = adivinar_proveedor(proveedor_leido, PROVEEDORES_DE_PRUEBA)

    assert resultado == PROVEEDORES_DE_PRUEBA[0]


def test_adivinar_proveedor_por_codigo_con_formato_distinto_al_leido():
    proveedor_leido = {"nombre": "", "tipo_pabellon": "libre", "numero_pabellon": "Pab 3", "puesto": "Puesto 38"}
    resultado = adivinar_proveedor(proveedor_leido, PROVEEDORES_DE_PRUEBA)

    assert resultado == PROVEEDORES_DE_PRUEBA[1]


def test_adivinar_proveedor_sin_codigo_usa_nombre_parecido():
    proveedor_leido = {"nombre": "Saturno SA", "tipo_pabellon": None, "numero_pabellon": "", "puesto": ""}
    resultado = adivinar_proveedor(proveedor_leido, PROVEEDORES_DE_PRUEBA)

    assert resultado == PROVEEDORES_DE_PRUEBA[0]


def test_adivinar_proveedor_codigo_no_existente_cae_a_nombre():
    proveedor_leido = {"nombre": "Frutamax", "tipo_pabellon": "nave", "numero_pabellon": "99", "puesto": "99"}
    resultado = adivinar_proveedor(proveedor_leido, PROVEEDORES_DE_PRUEBA)

    assert resultado == PROVEEDORES_DE_PRUEBA[1]


def test_adivinar_proveedor_nombre_muy_distinto_da_none():
    proveedor_leido = {"nombre": "Distribuidora XYZ", "tipo_pabellon": None, "numero_pabellon": "", "puesto": ""}
    resultado = adivinar_proveedor(proveedor_leido, PROVEEDORES_DE_PRUEBA)

    assert resultado is None


def test_adivinar_proveedor_sin_nada_leido_da_none():
    proveedor_leido = {"nombre": "", "tipo_pabellon": None, "numero_pabellon": "", "puesto": ""}
    resultado = adivinar_proveedor(proveedor_leido, PROVEEDORES_DE_PRUEBA)

    assert resultado is None


def test_adivinar_proveedor_sin_proveedores_existentes_da_none():
    proveedor_leido = {"nombre": "Saturno", "tipo_pabellon": "nave", "numero_pabellon": "7", "puesto": "41"}
    resultado = adivinar_proveedor(proveedor_leido, [])

    assert resultado is None


ARTICULOS_DE_PRUEBA = [
    {"id": 5, "nombre": "Tomate Redondo"},
    {"id": 6, "nombre": "Tomate Perita"},
    {"id": 7, "nombre": "Morrón Rojo"},
]


def test_adivinar_articulo_por_nombre_exacto_normalizado():
    resultado = adivinar_articulo("tomate redondo", {}, ARTICULOS_DE_PRUEBA)
    assert resultado == 5


def test_adivinar_articulo_por_nombre_exacto_con_acentos_distintos():
    resultado = adivinar_articulo("Morron Rojo", {}, ARTICULOS_DE_PRUEBA)
    assert resultado == 7


def test_adivinar_articulo_no_matchea_por_parecido():
    # "Tomate" solo no es exactamente "Tomate Redondo" ni "Tomate Perita": no adivina.
    resultado = adivinar_articulo("Tomate", {}, ARTICULOS_DE_PRUEBA)
    assert resultado is None


def test_adivinar_articulo_usa_aprendizaje_del_proveedor():
    aprendizaje = {"tom.red": 5}
    resultado = adivinar_articulo("Tom.Red", aprendizaje, ARTICULOS_DE_PRUEBA)
    assert resultado == 5


def test_adivinar_articulo_texto_vacio_da_none():
    resultado = adivinar_articulo("", {}, ARTICULOS_DE_PRUEBA)
    assert resultado is None


def test_adivinar_articulo_completar_articulo_no_matchea_nada():
    resultado = adivinar_articulo("completar artículo", {}, ARTICULOS_DE_PRUEBA)
    assert resultado is None
