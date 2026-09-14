"""El listado de vigencias: qué precio rigió cada día de un período, para facturar.

Contesta "¿a cuánto le facturo el 8?" sin una grilla de treinta columnas.
La forma la decidió una medición del 14/09 sobre las dos bases: de las 43
fichas del cliente grande, 18 cambiaron de precio en 30 días — o sea que
una grilla por día serían 25 filas de treinta números iguales.

Las dos trampas que estos tests cuidan, y ninguna se ve leyendo el código:

1. **El precio que ya regía ANTES del período.** Un `vigente_desde BETWEEN`
   deja sin precio al primer día del rango para más de la mitad de las
   fichas, y el listado sale prolijo igual.
2. **La ficha sin ningún precio.** Si no aparece, el que factura no tiene
   cómo enterarse de que existe y no tiene con qué facturarse.
"""

from datetime import date
from io import BytesIO
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.main import _armar_filas_vigencias, _rango_de_vigencias_desde_query, app
from core.exportar_precios import generar_excel_vigencias

cliente = TestClient(app)

CLIENTES = [{"id": 1, "nombre": "Día", "utilidad_objetivo": 20.0}]

# Dos fichas del MISMO artículo, que es el caso que obliga a desambiguar el
# nombre, más una tercera sin ningún precio: el hueco que hay que ver.
BANANA_BOLIVIA = {
    "id": 901, "cliente_id": 1, "articulo_id": 1, "articulo_nombre": "Banana", "articulo_grupo": "fruta",
    "envase_id": None, "envase_nombre": None, "contenido_caja": 6, "unidad_venta": "kilo",
    "envase_variable": False, "nombre_cliente": "BANANA BOLIVIA", "codigo_cliente": "90101",
}
BANANA_ECUADOR = {
    "id": 902, "cliente_id": 1, "articulo_id": 1, "articulo_nombre": "Banana", "articulo_grupo": "fruta",
    "envase_id": None, "envase_nombre": None, "contenido_caja": 10, "unidad_venta": "kilo",
    "envase_variable": False, "nombre_cliente": "BANANA ECUADOR", "codigo_cliente": "90102",
}
ANANA_SIN_PRECIO = {
    "id": 903, "cliente_id": 1, "articulo_id": 2, "articulo_nombre": "Ananá", "articulo_grupo": "fruta",
    "envase_id": None, "envase_nombre": None, "contenido_caja": 8, "unidad_venta": "unidad",
    "envase_variable": False, "nombre_cliente": None, "codigo_cliente": "90201",
}
TRES_FICHAS = [BANANA_BOLIVIA, BANANA_ECUADOR, ANANA_SIN_PRECIO]

# Bolivia: el precio que ya regía antes del rango (arranca en julio y no
# cambió nunca) — el caso 1. Ecuador: cambia adentro del rango.
VIGENCIAS = [
    {"ficha_id": 901, "precio": 800.0, "vigente_desde": date(2026, 7, 1), "vigente_hasta": None},
    {"ficha_id": 902, "precio": 900.0, "vigente_desde": date(2026, 8, 20), "vigente_hasta": date(2026, 9, 4)},
    {"ficha_id": 902, "precio": 1000.0, "vigente_desde": date(2026, 9, 5), "vigente_hasta": None},
]


def _filas():
    with (
        patch("app.main.listar_fichas_por_cliente", return_value=TRES_FICHAS),
        patch("app.main.listar_vigencias_de_precios", return_value=[dict(v) for v in VIGENCIAS]),
    ):
        return _armar_filas_vigencias(1, date(2026, 9, 1), date(2026, 9, 14))


def _pantalla(url="/precios/vigencias?cliente_id=1&desde=2026-09-01&hasta=2026-09-14"):
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES),
        patch("app.main.listar_fichas_por_cliente", return_value=TRES_FICHAS),
        patch("app.main.listar_vigencias_de_precios", return_value=[dict(v) for v in VIGENCIAS]),
    ):
        return cliente.get(url)


def _marcado(respuesta):
    """El HTML sin el CSS ni el comentario del <style> (corolarios 38 y 50)."""
    return respuesta.text.split("</style>")[-1]


# --- la consulta: la condición de intersección, que es lo que trae el arrastre ---


def test_la_consulta_NO_recorta_por_vigente_desde_mayor_que_el_desde():
    """El precio que ya regía antes del rango tiene que entrar, y por construcción.

    Con `vigente_desde >= desde` la consulta sale prolija y pierde a las 25
    fichas que no cambiaron de precio en el mes — el primer día del período
    quedaría vacío justo para las que nunca dan problema.

    El assert va sobre el TEXTO y no sobre las filas porque las filas las
    entrega el mock: con la columna o la condición cambiadas, el fixture
    devuelve lo mismo igual (corolario 40).
    """
    from app.db import listar_vigencias_de_precios

    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.description = [("ficha_id",), ("precio",), ("vigente_desde",), ("vigente_hasta",)]
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conexion = MagicMock()
    conexion.cursor.return_value = cursor

    with patch("app.db.obtener_conexion", return_value=conexion):
        listar_vigencias_de_precios(1, date(2026, 9, 1), date(2026, 9, 14))

    consulta, parametros = cursor.execute.call_args.args
    plana = " ".join(consulta.split())

    # Las DOS mitades de la intersección: la vigencia empieza antes de que
    # termine la ventana Y no había terminado cuando la ventana empieza.
    assert "vigente_desde <= %s" in plana
    assert "WHERE proximo IS NULL OR proximo > %s" in plana
    # Y la que NO puede estar: es el recorte intuitivo y el que pierde el arrastre.
    assert "vigente_desde >= %s" not in plana
    assert "BETWEEN" not in plana.upper()

    # El orden de los %s es (cliente, hasta, desde) y se liga por POSICIÓN en
    # el texto: `hasta` está en el CTE, que va arriba, y `desde` en el WHERE
    # de afuera. Dados vuelta la consulta corre igual y devuelve otra cosa.
    assert parametros == (1, date(2026, 9, 14), date(2026, 9, 1))

    # El `vigente_hasta` calculado: sin él hay que mirar la fila siguiente
    # para saber hasta cuándo rigió un precio.
    assert "LEAD(vigente_desde)" in plana
    assert "(proximo - 1) AS vigente_hasta" in plana
    # Los precios sin ficha no se pueden facturar: la ficha es la que tiene precio.
    assert "ficha_id IS NOT NULL" in plana


# --- las filas: la ficha sin precio va IGUAL, y el nombre es el de Analizar ---


def test_la_ficha_sin_ningun_precio_aparece_con_la_lista_vacia():
    """Es el hueco medido el 14/09: 8 fichas entre Cook Master y Grupo L.

    Si se filtraran las que no tienen vigencias, el listado saldría completo
    y correcto salvo por las fichas que son justamente el problema — y nada
    en la pantalla diría que faltan.
    """
    filas = _filas()

    assert [fila["ficha_id"] for fila in filas] == [903, 901, 902]  # alfabético: Ananá, Banana·BOLIVIA, Banana·ECUADOR
    sin_precio = [fila for fila in filas if not fila["vigencias"]]
    assert [fila["ficha_id"] for fila in sin_precio] == [903]


def test_el_nombre_sale_de_etiqueta_de_ficha_y_no_de_una_regla_propia():
    """Las dos fichas del mismo artículo se tienen que leer igual acá y en Analizar.

    Es la regla escrita dos veces: con una condición propia, el día que
    cambie qué nombre gana, el que busca "Banana · BANANA BOLIVIA" la
    encuentra escrita distinto en cada pantalla.
    """
    from app.main import _etiqueta_de_ficha

    filas = _filas()
    por_id = {fila["ficha_id"]: fila["nombre"] for fila in filas}

    assert por_id[901] == _etiqueta_de_ficha(BANANA_BOLIVIA) == "Banana · BANANA BOLIVIA"
    assert por_id[902] == _etiqueta_de_ficha(BANANA_ECUADOR) == "Banana · BANANA ECUADOR"
    # La que no tiene nombre propio se queda con el del catálogo, sin el " · ".
    assert por_id[903] == _etiqueta_de_ficha(ANANA_SIN_PRECIO) == "Ananá"


def test_las_fechas_se_escriben_UNA_vez_y_van_CON_ANO():
    """Una vigencia puede empezar mucho antes del período: "01/07" leído en septiembre engaña.

    Y se escriben en `_armar_filas_vigencias` porque de ahí las toman la
    pantalla y el Excel: formateadas en cada lado serían dos reglas.
    """
    filas = _filas()
    bolivia = next(fila for fila in filas if fila["ficha_id"] == 901)
    ecuador = next(fila for fila in filas if fila["ficha_id"] == 902)

    assert bolivia["vigencias"][0]["desde_texto"] == "01/07/2026"
    assert bolivia["vigencias"][0]["hasta_texto"] == "sigue vigente"
    assert ecuador["vigencias"][0]["hasta_texto"] == "04/09/2026"


# --- el rango: el default es el mes, y lo raro se avisa sin dejar la pantalla vacía ---


def test_sin_fechas_el_rango_es_el_MES_CORRIENTE_hasta_hoy():
    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 14)):
        desde, hasta, error = _rango_de_vigencias_desde_query(None, None)

    assert (desde, hasta) == (date(2026, 9, 1), date(2026, 9, 14))
    assert error is None


def test_un_rango_al_reves_se_avisa_y_NO_se_da_vuelta_solo():
    """Dar vuelta las fechas devuelve un listado correcto de un período que nadie pidió."""
    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 14)):
        desde, hasta, error = _rango_de_vigencias_desde_query("2026-09-30", "2026-09-01")

    assert error == "El desde no puede ser posterior al hasta."
    assert (desde, hasta) == (date(2026, 9, 1), date(2026, 9, 14))


def test_una_fecha_invalida_avisa_pero_NO_deja_la_pantalla_sin_datos():
    with patch("app.main._hoy_argentina", return_value=date(2026, 9, 14)):
        desde, hasta, error = _rango_de_vigencias_desde_query("no-es-una-fecha", None)

    assert error == "La fecha no es válida."
    assert (desde, hasta) == (date(2026, 9, 1), date(2026, 9, 14))


# --- la pantalla ---


def test_la_pantalla_muestra_cada_precio_con_su_rango_y_marca_la_que_no_tiene():
    respuesta = _pantalla()
    assert respuesta.status_code == 200
    marcado = _marcado(respuesta)

    # El arrastre de julio se ve como tal, con su fecha real y sin fin.
    assert "01/07/2026 → sigue vigente" in marcado
    # El cambio de adentro del rango, con el hasta ya calculado.
    assert "20/08/2026 → 04/09/2026" in marcado
    assert "05/09/2026 → sigue vigente" in marcado

    # Y la ficha sin precio, en su lugar alfabético y marcada.
    assert 'class="sin-precio"' in marcado
    assert "Sin precio en el período" in marcado
    assert "1 ficha no tiene precio" in marcado


def test_la_pantalla_ofrece_el_Excel_con_el_MISMO_rango_que_se_esta_viendo():
    """El link se arma con las fechas ya resueltas, no con lo que vino en la URL.

    Sin eso, llegar con una fecha inválida muestra el mes y exporta el
    período roto — dos períodos distintos en la misma pantalla.
    """
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES),
        patch("app.main.listar_fichas_por_cliente", return_value=TRES_FICHAS),
        patch("app.main.listar_vigencias_de_precios", return_value=[dict(v) for v in VIGENCIAS]),
        patch("app.main._hoy_argentina", return_value=date(2026, 9, 14)),
    ):
        respuesta = cliente.get("/precios/vigencias?cliente_id=1&desde=cualquiera")

    marcado = _marcado(respuesta)
    assert "La fecha no es válida." in marcado
    assert "/precios/vigencias/exportar-excel?cliente_id=1&desde=2026-09-01&hasta=2026-09-14" in marcado


def test_sin_cliente_la_pantalla_no_va_a_buscar_precios():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES),
        patch("app.main.listar_vigencias_de_precios", side_effect=AssertionError("no tiene que consultar")),
    ):
        respuesta = cliente.get("/precios/vigencias")

    assert respuesta.status_code == 200
    assert "Elegí un cliente" in _marcado(respuesta)


def test_el_hub_de_precios_lleva_a_la_pantalla():
    respuesta = cliente.get("/precios")
    assert 'href="/precios/vigencias"' in _marcado(respuesta)


# --- el Excel ---


def _hoja_exportada():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES),
        patch("app.main.listar_fichas_por_cliente", return_value=TRES_FICHAS),
        patch("app.main.listar_vigencias_de_precios", return_value=[dict(v) for v in VIGENCIAS]),
    ):
        respuesta = cliente.get(
            "/precios/vigencias/exportar-excel?cliente_id=1&desde=2026-09-01&hasta=2026-09-14"
        )
    assert respuesta.status_code == 200
    return respuesta, load_workbook(BytesIO(respuesta.content)).active


def test_el_Excel_repite_el_nombre_de_la_ficha_en_CADA_fila():
    """Quien factura FILTRA por producto, y una celda vacía se queda afuera del filtro.

    Combinar celdas o dejar el nombre solo en la primera fila del grupo se ve
    más prolijo y esconde filas de la búsqueda: existirían en la planilla y
    no aparecerían al filtrar, que es peor que no estar.
    """
    _, hoja = _hoja_exportada()

    filas = [[celda.value for celda in fila] for fila in hoja.iter_rows(min_row=3, max_col=4)]
    nombres = [fila[0] for fila in filas]

    assert nombres == ["Ananá", "Banana · BANANA BOLIVIA", "Banana · BANANA ECUADOR", "Banana · BANANA ECUADOR"]
    assert None not in nombres
    assert hoja.merged_cells.ranges == [] or all(
        rango.min_row < 3 for rango in hoja.merged_cells.ranges
    ), "no se combinan celdas del cuerpo"


def test_el_Excel_dice_SIN_PRECIO_y_sigue_vigente_con_todas_las_letras():
    """Una celda vacía se lee como un dato que falta. Acá no falta: el precio no terminó."""
    _, hoja = _hoja_exportada()
    filas = {fila[0].value: [celda.value for celda in fila] for fila in hoja.iter_rows(min_row=3, max_col=4)}

    assert filas["Ananá"][1] == "SIN PRECIO"
    assert filas["Banana · BANANA BOLIVIA"][2:] == ["01/07/2026", "sigue vigente"]


def test_el_Excel_NO_reformatea_las_fechas_por_su_cuenta():
    """Si las escribiera él, la planilla y la pantalla se separan el día que una cambie.

    Se le pasa un texto imposible de derivar de una fecha y tiene que salir
    tal cual: con un `strftime` propio adentro, este test cae.
    """
    filas = [{"nombre": "Ficha", "vigencias": [
        {"precio": 100.0, "desde_texto": "EL PRIMERO", "hasta_texto": "EL ULTIMO"}
    ]}]
    bytes_excel = generar_excel_vigencias("Día", date(2026, 9, 1), date(2026, 9, 14), filas, "Frutamax")
    hoja = load_workbook(BytesIO(bytes_excel)).active

    assert [hoja.cell(row=3, column=columna).value for columna in (3, 4)] == ["EL PRIMERO", "EL ULTIMO"]


def test_la_pantalla_y_el_Excel_dicen_LA_MISMA_fecha_para_el_mismo_hecho():
    """Es el invariante que justifica calcular los textos una sola vez."""
    respuesta_pantalla = _pantalla()
    _, hoja = _hoja_exportada()

    de_la_planilla = [
        (fila[2].value, fila[3].value) for fila in hoja.iter_rows(min_row=3, max_col=4) if fila[2].value
    ]
    assert de_la_planilla  # el control: si la planilla saliera vacía, el for de abajo no probaría nada
    marcado = _marcado(respuesta_pantalla)
    for desde_texto, hasta_texto in de_la_planilla:
        assert f"{desde_texto} → {hasta_texto}" in marcado, (desde_texto, hasta_texto)


def test_el_nombre_del_archivo_lleva_empresa_cliente_y_las_dos_fechas():
    respuesta, _ = _hoja_exportada()
    disposicion = respuesta.headers["content-disposition"]

    assert "Precios_Por_Periodo_" in disposicion
    assert "2026-09-01_a_2026-09-14.xlsx" in disposicion


def test_exportar_con_el_rango_al_reves_es_400_y_no_un_archivo_de_un_periodo_inventado():
    with patch("app.main.listar_clientes", return_value=CLIENTES):
        respuesta = cliente.get(
            "/precios/vigencias/exportar-excel?cliente_id=1&desde=2026-09-30&hasta=2026-09-01"
        )
    assert respuesta.status_code == 400
