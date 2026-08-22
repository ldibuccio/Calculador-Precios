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


# --- El formato REAL del mail de Día (calibrado con los mails guardados del 21 y 22/08/2026) ---
#
# Réplica estructural byte-equivalente para el parser: misma grilla de 8
# columnas (2 de margen, código, descripción, 1 separadora, VL/BZ/GR),
# encabezado de solo sucursales, fila de OC sin etiqueta, fila de empresa
# con colspan=2 y los totales declarados, productos con celdas vacías en
# cualquier posición, y el pie de confidencialidad. Los valores de
# FRUTAMAX son los del mail real del 22-08: las sumas por columna dan
# EXACTAMENTE los totales declarados (235/275/140) — si una transcripción
# estuviera mal, esta misma suite lo delataría.

from core.casilla_pedidos import html_a_texto  # noqa: E402

FRUTAMAX_22_08 = [
    ("90039", "MANZ ROJ ELE", "15", "10", "10"),
    ("90074", "TOMATE PERIT", "", "15", ""),
    ("90076", "TOMATE PG", "", "", ""),
    ("90111", "MANZANA PG", "", "40", ""),
    ("90112", "MANZANA VDE", "10", "5", "10"),
    ("90113", "PERA COMERCI", "10", "15", "10"),
    ("90114", "LIMON GRANEL", "15", "15", "10"),
    ("90115", "POMELO GRA", "10", "10", ""),
    ("90117", "NARANJA JUGO", "10", "10", ""),
    ("90118", "NARANJA OMB", "15", "10", "10"),
    ("90119", "MANDARINA G", "15", "15", "10"),
    ("90121", "ZAP. RED. GR", "20", "15", ""),
    ("90123", "M.ROJO GRA", "10", "10", "10"),
    ("90124", "M.VERDE GRA", "10", "10", "10"),
    ("90127", "TOM RED 1° E", "", "15", ""),
    ("90135", "DURAZNO", "", "", ""),
    ("90136", "MELON", "", "", ""),
    ("90137", "ANANA", "", "", ""),
    ("90138", "CIRUELA", "", "", ""),
    ("90142", "UVA GRANEL", "", "", ""),
    ("90145", "PEPINO GRANE", "10", "10", "5"),
    ("90189", "CEREZA", "", "", ""),
    ("90191", "PELON", "", "", ""),
    ("90179", "BERENJENA G", "15", "10", "5"),
    ("90192", "SANDIA", "", "", ""),
    ("90314", "TOMATE CHERR", "10", "10", "5"),
    ("101891", "KIWI CUBETA", "", "", ""),
    ("103732", "FRUTILLA", "10", "10", "5"),
    ("225863", "MANGO", "10", "10", "10"),
    ("228219", "PALTA", "20", "20", "20"),
    ("259411", "LIMA X 1KG", "10", "5", "5"),
    ("261379", "ARANDANO", "10", "5", "5"),
]

PALMALA_22_08 = [
    ("21608", "ZUCCHINI", "5", "10", "5"),
    ("90061", "PAPA ELEGIDA", "10", "", "10"),
    ("90094", 'PAPA <a href="http://NEG.COM">NEG.COM</a>', "", "40", "40"),
    ("90110", "BANANA", "", "", ""),
    ("90120", "ANCO COMERCI", "20", "10", ""),
    ("90122", "ZANAHORIA", "20", "30", "15"),
]


def _fila_real(tds):
    """Una fila del mail real: lista de (texto, colspan). Vacío = &nbsp; como en el original."""
    celdas = "".join(
        f'<td{" colspan=" + chr(34) + str(colspan) + chr(34) if colspan > 1 else ""}'
        f' style="padding:0px;color:windowtext;font-size:10pt;font-family:Arial">{texto or "&nbsp;"}</td>'
        for texto, colspan in tds
    )
    return f'<tr height="17">{celdas}</tr>'


def _bloque_real(codigo_bloque, nombre, ocs, totales, productos):
    filas = [
        _fila_real([("", 1)] * 5 + [("VL", 1), ("BZ", 1), ("GR", 1)]),
        _fila_real([("", 1)] * 5 + [(oc, 1) for oc in ocs]),
        _fila_real([(codigo_bloque, 1), (nombre, 2), ("", 1), ("", 1)] + [(t, 1) for t in totales]),
    ]
    for codigo, descripcion, vl, bz, gr in productos:
        filas.append(_fila_real([("", 1), ("", 1), (codigo, 1), (descripcion, 1), ("", 1), (vl, 1), (bz, 1), (gr, 1)]))
    return filas


def _mail_real_dia_22_08():
    filas = (
        _bloque_real("9582", "FRUTAMAX", ["1257673", "1257642", "1258437"], ["235", "275", "140"], FRUTAMAX_22_08)
        + [_fila_real([("", 1)] * 8)]  # la fila separadora vacía entre bloques
        + _bloque_real("11344", "PALMALA", ["1257674", "1257643", "1258438"], ["215", "185", "200"], PALMALA_22_08)
    )
    return (
        '<div dir="ltr"><table border="0" cellpadding="0" cellspacing="0" width="827"><tbody>'
        + "".join(filas)
        + "</tbody></table></div><br>"
        + "<div>Este correo electrónico y todos los ficheros adjuntos son confidenciales...</div>"
    )


def test_mail_real_de_dia_se_lee_entero_por_estructura():
    resultado = parsear_pedido_estructurado(html_a_texto(_mail_real_dia_22_08()))

    assert resultado is not None
    assert [b["empresa"] for b in resultado["bloques"]] == ["9582 FRUTAMAX", "11344 PALMALA"]
    frutamax = resultado["bloques"][0]
    # La OC y el total declarado de cada sucursal, sacados por columna.
    assert {s["sucursal"]: (s["orden_compra"], s["total_bultos"]) for s in frutamax["sucursales"]} == {
        "VL": ("1257673", 235.0), "BZ": ("1257642", 275.0), "GR": ("1258437", 140.0),
    }
    # Los 32 renglones del mail real (los sin cantidades también: nada se pierde).
    assert len(frutamax["renglones"]) == 32


def test_mail_real_de_dia_las_sumas_cuadran_con_los_totales_declarados():
    # La prueba reina: sumar lo parseado por sucursal da EXACTAMENTE el
    # total que declara el mail. Un solo cruce de columna la rompería.
    frutamax = parsear_pedido_estructurado(html_a_texto(_mail_real_dia_22_08()))["bloques"][0]

    for sucursal in frutamax["sucursales"]:
        suma = sum(r["cantidades"].get(sucursal["sucursal"], 0) for r in frutamax["renglones"])
        assert suma == sucursal["total_bultos"]


def test_mail_real_de_dia_celdas_vacias_y_links_en_su_lugar():
    resultado = parsear_pedido_estructurado(html_a_texto(_mail_real_dia_22_08()))
    frutamax, palmala = resultado["bloques"]

    cantidades = {r["codigo"]: r["cantidades"] for r in frutamax["renglones"]}
    # Vacía adelante, en el medio, al final, y renglón sin ninguna cantidad.
    assert cantidades["90111"] == {"BZ": 40.0}
    assert cantidades["90115"] == {"VL": 10.0, "BZ": 10.0}
    assert cantidades["90127"] == {"BZ": 15.0}
    assert cantidades["90135"] == {}
    # La descripción con link queda como texto ("PAPA NEG.COM").
    papa = next(r for r in palmala["renglones"] if r["codigo"] == "90094")
    assert papa["descripcion"] == "PAPA NEG.COM"
    assert papa["cantidades"] == {"BZ": 40.0, "GR": 40.0}


def test_grilla_dia_con_una_fila_que_no_calza_cae_a_ia():
    # Una fila con cantidades pero sin código ni descripción no está en la
    # secuencia conocida: None, jamás adivinar.
    texto = (
        "\t\t\t\t\tVL\tBZ\tGR\n"
        "\t\t\t\t\t111\t222\t333\n"
        "9582\tFRUTAMAX\t\t\t\t10\t20\t30\n"
        "\t\t\t\t\t5\t5\t5\n"
    )
    assert parsear_pedido_estructurado(texto) is None


def test_grilla_dia_no_rectangular_cae_a_ia():
    texto = (
        "\t\t\t\t\tVL\tBZ\tGR\n"
        "\t\t\t\t\t111\t222\t333\n"
        "9582\tFRUTAMAX\t\t\t\t10\t20\t30\n"
        "\t\t90039\tMANZ\t\t15\t10\t10\t99\n"
    )
    assert parsear_pedido_estructurado(texto) is None
