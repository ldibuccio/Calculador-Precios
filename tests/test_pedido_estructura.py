"""Tests del parser por estructura: las cantidades salen de la tabla, sin IA.

Lo crítico: la asignación de cada cantidad a SU sucursal es posicional y
determinista (un cruce de bultos es imposible por construcción), y ante
CUALQUIER estructura inesperada el parser devuelve None — nunca adivina;
el que llama cae al camino IA avisando.
"""

from core.pedido_estructura import parsear_pedido_estructurado

TEXTO_PEDIDO = (
    "9582 FRUTAMAX\n"
    "Código\tProducto\tVL\tBZ\tGR\n"
    "\tOC\t1257673\t1257642\t\n"
    "90101\tBANANA\t225\t\t\n"
    "\tSIN CODIGO\t\t7\t\n"
    "90137\tANCO\t\t\t3\n"
    "133\tANANA\t5\t2,5\t\n"
    "\tTOTAL BULTOS\t230\t9,5\t3\n"
)


def test_parsea_cantidades_por_posicion_con_celdas_vacias_en_cualquier_lado():
    resultado = parsear_pedido_estructurado(TEXTO_PEDIDO)

    bloque = resultado["bloques"][0]
    assert bloque["empresa"] == "9582 FRUTAMAX"
    # Cada cantidad en SU columna: vacía adelante, en el medio o al final.
    cantidades = {r["codigo"] or r["descripcion"]: r["cantidades"] for r in bloque["renglones"]}
    assert cantidades["90101"] == {"VL": 225.0}
    assert cantidades["SIN CODIGO"] == {"BZ": 7.0}
    assert cantidades["90137"] == {"GR": 3.0}
    assert cantidades["133"] == {"VL": 5.0, "BZ": 2.5}
    # Nada de "confianza baja": acá la celda está o no está.
    assert all(r["confianza"] == "alta" for r in bloque["renglones"])


def test_saca_la_oc_y_el_total_declarado_por_columna():
    bloque = parsear_pedido_estructurado(TEXTO_PEDIDO)["bloques"][0]

    por_sucursal = {s["sucursal"]: s for s in bloque["sucursales"]}
    # La OC como TEXTO tal cual; a GR le falta y queda null.
    assert por_sucursal["VL"] == {"sucursal": "VL", "orden_compra": "1257673", "total_bultos": 230.0}
    assert por_sucursal["BZ"]["orden_compra"] == "1257642"
    assert por_sucursal["GR"]["orden_compra"] is None
    assert por_sucursal["GR"]["total_bultos"] == 3.0
    # Las filas de OC y TOTAL no son renglones de producto.
    assert len(bloque["renglones"]) == 4


def test_separa_los_bloques_de_las_dos_empresas():
    texto = TEXTO_PEDIDO + "11344 PALMALA\nCódigo\tProducto\tVL\n555\tOTRA COSA\t10\n"

    resultado = parsear_pedido_estructurado(texto)

    assert [b["empresa"] for b in resultado["bloques"]] == ["9582 FRUTAMAX", "11344 PALMALA"]
    assert resultado["bloques"][1]["renglones"][0]["cantidades"] == {"VL": 10.0}


def test_una_tabla_sin_encabezado_de_empresa_es_un_bloque_anonimo():
    texto = "Código\tProducto\tVL\n90101\tBANANA\t225\n"

    resultado = parsear_pedido_estructurado(texto)

    assert resultado["bloques"][0]["empresa"] == ""
    assert len(resultado["bloques"][0]["renglones"]) == 1


def test_renglon_sin_ninguna_cantidad_se_conserva_igual():
    # Nada del mail se pierde: el renglón queda con cantidades vacías.
    texto = "Código\tProducto\tVL\n90101\tBANANA\t\n"

    resultado = parsear_pedido_estructurado(texto)

    assert resultado["bloques"][0]["renglones"][0]["cantidades"] == {}


# --- Los que NO se pueden leer por estructura: None, jamás adivinar ---


def test_sin_tabuladores_no_hay_estructura():
    assert parsear_pedido_estructurado("pedido pegado sin estructura 90101 BANANA 225") is None


def test_sin_fila_de_titulos_no_se_sabe_que_sucursal_es_cada_columna():
    assert parsear_pedido_estructurado("90101\tBANANA\t225\t40") is None


def test_una_fila_corrida_de_columnas_invalida_todo():
    # Una fila con celdas de más es EXACTAMENTE el error que no puede pasar
    # de largo: mejor caer a IA avisando que leer corrido.
    texto = "Código\tProducto\tVL\tBZ\n90101\tBANANA\t225\t\t99\n"
    assert parsear_pedido_estructurado(texto) is None


def test_una_celda_de_cantidad_no_numerica_invalida_todo():
    texto = "Código\tProducto\tVL\n90101\tBANANA\tveinte\n"
    assert parsear_pedido_estructurado(texto) is None


def test_un_codigo_no_numerico_invalida_todo():
    texto = "Código\tProducto\tVL\nABC-1\tBANANA\t225\n"
    assert parsear_pedido_estructurado(texto) is None


def test_un_bloque_indescifrable_invalida_el_conjunto():
    # Mezclar mitades leídas por estructura con mitades sin leer sería
    # perder renglones en silencio: si un segmento no cierra, None y a IA.
    texto = TEXTO_PEDIDO + "11344 PALMALA\n555\tSIN TITULOS\t10\n"
    assert parsear_pedido_estructurado(texto) is None
