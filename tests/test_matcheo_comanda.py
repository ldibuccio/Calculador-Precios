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


def test_construir_codigo_puesto_con_varios_puestos_toma_solo_el_primero():
    # Caso real: membrete "Libre 2 - Puestos 4 y 6" (dos puestos para el
    # mismo proveedor). Antes esto mezclaba mal los dígitos ("4" y "6" -> 46).
    assert construir_codigo_puesto("libre", "2", "4 y 6") == "L02P04"
    assert construir_codigo_puesto("nave", "7", "4 y 6") == "N07P04"


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


def test_adivinar_proveedor_nuevo_sin_ningun_proveedor_existente_igual_arma_el_codigo():
    # Caso real: primera vez que se le compra a este puesto, no hay ningún
    # proveedor cargado todavía. Antes esto perdía el código ya interpretado
    # de la foto y dejaba todo en blanco; ahora lo propone igual (sin id,
    # porque todavía no existe en la base), editable como siempre.
    proveedor_leido = {"nombre": "Rio Uruguay & Goloso", "tipo_pabellon": "libre", "numero_pabellon": "2", "puesto": "4 y 6"}
    resultado = adivinar_proveedor(proveedor_leido, [])

    assert resultado == {"id": None, "codigo_puesto": "L02P04", "nombre": "Rio Uruguay & Goloso"}


def test_adivinar_proveedor_nuevo_sin_ningun_dato_de_codigo_da_none():
    # Si ni siquiera se pudo armar un código (no se leyó pabellón/puesto) y
    # tampoco hay parecido de nombre, no hay nada para proponer.
    proveedor_leido = {"nombre": "", "tipo_pabellon": None, "numero_pabellon": "", "puesto": ""}
    resultado = adivinar_proveedor(proveedor_leido, [])

    assert resultado is None


def test_adivinar_proveedor_codigo_existente_tiene_prioridad_sobre_proponer_uno_nuevo():
    proveedor_leido = {"nombre": "", "tipo_pabellon": "nave", "numero_pabellon": "7", "puesto": "41"}
    resultado = adivinar_proveedor(proveedor_leido, PROVEEDORES_DE_PRUEBA)

    assert resultado == PROVEEDORES_DE_PRUEBA[0]
    assert resultado["id"] == 200


ARTICULOS_DE_PRUEBA = [
    {"id": 5, "nombre": "Tomate Redondo"},
    {"id": 6, "nombre": "Tomate Perita"},
    {"id": 7, "nombre": "Morrón Rojo"},
    {"id": 8, "nombre": "Mzn Granny"},
    {"id": 9, "nombre": "Man Gob"},
    {"id": 11, "nombre": "Pera"},
]

CONVERSIONES_DE_PRUEBA = [
    {"articulo_id": 8, "nombre_cliente": "MANZANA VDE"},
    {"articulo_id": 9, "nombre_cliente": "MANZANA PG"},
]


def test_adivinar_articulo_por_nombre_exacto_normalizado():
    resultado = adivinar_articulo("tomate redondo", {}, ARTICULOS_DE_PRUEBA, [])
    assert resultado == 5


def test_adivinar_articulo_por_nombre_exacto_con_acentos_distintos():
    resultado = adivinar_articulo("Morron Rojo", {}, ARTICULOS_DE_PRUEBA, [])
    assert resultado == 7


def test_adivinar_articulo_texto_ambiguo_no_matchea_por_debajo_del_umbral():
    # "Tomate" solo es demasiado parecido a "Tomate Redondo" Y "Tomate Perita"
    # a la vez (por debajo del umbral de todos modos): no adivina.
    resultado = adivinar_articulo("Tomate", {}, ARTICULOS_DE_PRUEBA, [])
    assert resultado is None


def test_adivinar_articulo_usa_aprendizaje_del_proveedor():
    aprendizaje = {"tom.red": 5}
    resultado = adivinar_articulo("Tom.Red", aprendizaje, ARTICULOS_DE_PRUEBA, [])
    assert resultado == 5


def test_adivinar_articulo_texto_vacio_da_none():
    resultado = adivinar_articulo("", {}, ARTICULOS_DE_PRUEBA, [])
    assert resultado is None


def test_adivinar_articulo_completar_articulo_no_matchea_nada():
    resultado = adivinar_articulo("completar artículo", {}, ARTICULOS_DE_PRUEBA, [])
    assert resultado is None


def test_adivinar_articulo_por_parecido_manzana_granny_vs_mzn_granny():
    # Caso real que fallaba: "Manzana Granny" leído no coincidía con "Mzn Granny".
    resultado = adivinar_articulo("Manzana Granny", {}, ARTICULOS_DE_PRUEBA, [])
    assert resultado == 8


def test_adivinar_articulo_por_conversion_pg_es_palabra_completa_de_manzana_pg():
    # Caso real que fallaba: "PG" leído no coincidía con "Man Gob" (via
    # conversion_articulos_cliente: "MANZANA PG" -> Man Gob).
    resultado = adivinar_articulo("PG", {}, ARTICULOS_DE_PRUEBA, CONVERSIONES_DE_PRUEBA)
    assert resultado == 9


def test_adivinar_articulo_por_conversion_exacta():
    resultado = adivinar_articulo("MANZANA VDE", {}, ARTICULOS_DE_PRUEBA, CONVERSIONES_DE_PRUEBA)
    assert resultado == 8


def test_adivinar_articulo_conversion_tiene_prioridad_sobre_nombre_de_articulo():
    # Si "pg" no matcheara por conversion, por nombre de articulo tampoco
    # matchearía nada (no hay ningún articulo llamado "pg" o parecido) — así
    # que este caso además confirma que el camino de conversion se usa.
    resultado = adivinar_articulo("pg", {}, ARTICULOS_DE_PRUEBA, CONVERSIONES_DE_PRUEBA)
    assert resultado == 9


def test_adivinar_articulo_no_confunde_productos_distintos_con_letras_parecidas():
    # "Cereza" y "Pera" comparten bastantes letras (ratio ~0.6) pero son
    # productos totalmente distintos: no puede adivinar mal esto.
    resultado = adivinar_articulo("Cereza", {}, ARTICULOS_DE_PRUEBA, [])
    assert resultado is None


def test_adivinar_articulo_aprendizaje_tiene_prioridad_sobre_conversion():
    aprendizaje = {"manzana vde": 999}
    resultado = adivinar_articulo("MANZANA VDE", aprendizaje, ARTICULOS_DE_PRUEBA, CONVERSIONES_DE_PRUEBA)
    assert resultado == 999
