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
        return _armar_filas_vigencias(1, date(2026, 9, 1), date(2026, 9, 14))[0]


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


# --- las filas: la ficha SIN precio no va, y el nombre es el de Analizar ---


def test_la_ficha_sin_ningun_precio_NO_aparece():
    """Decisión del dueño del 14/09, que revierte la de la mañana.

    Esta pantalla es para FACTURAR y una ficha sin precio no produce
    ningún renglón de factura: lo único que hacía era ocupar lugar entre
    las que sí se facturan. El argumento que las incluía —que si
    desaparecen nadie se entera de que esa ficha no tiene precio— sigue
    siendo cierto y es OTRA pantalla; ver el docstring de
    `_armar_filas_vigencias`.

    El assert de la ausencia está a propósito además del de la lista: sin
    él, agregar la ficha de vuelta con cualquier otro id pasaría en verde.
    """
    filas = _filas()

    assert [fila["ficha_id"] for fila in filas] == [901, 902]  # alfabético: Banana·BOLIVIA, Banana·ECUADOR
    assert 903 not in [fila["ficha_id"] for fila in filas]
    assert all(fila["vigencias"] for fila in filas), "ninguna fila puede venir con la lista vacía"


def test_el_SEGUNDO_valor_dice_si_el_cliente_TIENE_fichas_aunque_no_tengan_precio():
    """Es lo único que separa los dos vacíos, y cada uno manda a otro lado.

    Sin fichas hay que cargarlas; con fichas y sin precios, o se carga el
    precio o el período elegido no es el que se busca. El cartel que había
    —"no tiene ninguna ficha cargada"— pasaría a ser falso casi siempre
    ahora que las fichas sin precio no llegan a `filas`.
    """
    with (
        patch("app.main.listar_fichas_por_cliente", return_value=[dict(f) for f in TRES_FICHAS]),
        patch("app.main.listar_vigencias_de_precios", return_value=[]),
    ):
        filas, hay_fichas = _armar_filas_vigencias(1, date(2026, 9, 1), date(2026, 9, 14))
    assert filas == [] and hay_fichas is True

    with (
        patch("app.main.listar_fichas_por_cliente", return_value=[]),
        patch("app.main.listar_vigencias_de_precios", return_value=[]),
    ):
        filas, hay_fichas = _armar_filas_vigencias(1, date(2026, 9, 1), date(2026, 9, 14))
    assert filas == [] and hay_fichas is False


def test_el_nombre_sale_de_etiqueta_de_ficha_y_no_de_una_regla_propia():
    """Las dos fichas del mismo artículo se tienen que leer igual acá y en Analizar.

    Es la regla escrita dos veces: con una condición propia, el día que
    cambie qué nombre gana, el que busca "Banana · BANANA BOLIVIA" la
    encuentra escrita distinto en cada pantalla.
    """
    from app.main import _etiqueta_de_ficha

    # Fixture propio: a la Ananá se le da un precio para que LLEGUE a las
    # filas. Desde el 14/09 las fichas sin precio no entran, y sin este
    # renglón el caso "ficha sin nombre propio" se quedaría sin probar —
    # que es distinto de probarlo y que dé bien.
    with (
        patch("app.main.listar_fichas_por_cliente", return_value=[dict(f) for f in TRES_FICHAS]),
        patch(
            "app.main.listar_vigencias_de_precios",
            return_value=[dict(v) for v in VIGENCIAS]
            + [{"ficha_id": 903, "precio": 500.0, "vigente_desde": date(2026, 9, 2), "vigente_hasta": None}],
        ),
    ):
        filas, _ = _armar_filas_vigencias(1, date(2026, 9, 1), date(2026, 9, 14))
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


def test_la_pantalla_muestra_cada_precio_con_su_rango_y_NO_la_ficha_sin_precio():
    respuesta = _pantalla()
    assert respuesta.status_code == 200
    marcado = _marcado(respuesta)

    # El arrastre de julio se ve como tal, con su fecha real y sin fin.
    assert "01/07/2026 → sigue vigente" in marcado
    # El cambio de adentro del rango, con el hasta ya calculado.
    assert "20/08/2026 → 04/09/2026" in marcado
    assert "05/09/2026 → sigue vigente" in marcado

    # Y la ficha sin precio no está, ni ella ni el aviso con la cuenta.
    # Por la CLASE y no por el texto visible (corolario 38): un comentario
    # que explique por qué no va nombraría la frase y el assert matchearía
    # su propia explicación.
    assert 'class="sin-precio"' not in marcado
    assert 'class="aviso-sin-precio"' not in marcado
    assert "Ananá" not in marcado


def test_los_DOS_vacios_de_la_pantalla_dicen_cosas_DISTINTAS():
    """Sacar las fichas sin precio crea un vacío que antes no existía.

    Hasta el 14/09 un cliente con fichas y sin precios igual llenaba la
    pantalla —todas sus fichas con "Sin precio en el período"—, así que el
    único vacío posible era no tener ninguna ficha, y el cartel lo decía. Con
    las fichas filtradas ese cartel pasaría a salir para un cliente que SÍ
    tiene fichas, y mandaría a cargar lo que ya está cargado.

    Son dos acciones distintas: cargar fichas, o cargar el precio / mirar
    otro período. Por eso son dos carteles y no uno.
    """
    def pantalla_con(fichas, vigencias):
        with (
            patch("app.main.listar_clientes", return_value=CLIENTES),
            patch("app.main.listar_fichas_por_cliente", return_value=fichas),
            patch("app.main.listar_vigencias_de_precios", return_value=vigencias),
        ):
            return _marcado(cliente.get("/precios/vigencias?cliente_id=1&desde=2026-09-01&hasta=2026-09-14"))

    con_fichas = pantalla_con([dict(f) for f in TRES_FICHAS], [])
    assert "no tiene ningún precio en este período" in con_fichas
    assert "no tiene ninguna ficha cargada" not in con_fichas
    # Y sin filas no se ofrece exportar: un Excel vacío no se descarga por gusto.
    assert "/precios/vigencias/exportar-excel" not in con_fichas

    sin_fichas = pantalla_con([], [])
    assert "no tiene ninguna ficha cargada" in sin_fichas
    assert "no tiene ningún precio en este período" not in sin_fichas


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

    assert nombres == ["Banana · BANANA BOLIVIA", "Banana · BANANA ECUADOR", "Banana · BANANA ECUADOR"]
    assert None not in nombres
    assert hoja.merged_cells.ranges == [] or all(
        rango.min_row < 3 for rango in hoja.merged_cells.ranges
    ), "no se combinan celdas del cuerpo"


def test_el_Excel_dice_sigue_vigente_con_todas_las_letras_y_NO_lleva_la_ficha_sin_precio():
    """Una celda vacía se lee como un dato que falta. Acá no falta: el precio no terminó.

    Y la ficha sin precio no aparece: hasta el 14/09 iba con "SIN PRECIO"
    en amarillo, y el dueño la sacó — esta planilla es para facturar.
    """
    _, hoja = _hoja_exportada()
    filas = {fila[0].value: [celda.value for celda in fila] for fila in hoja.iter_rows(min_row=3, max_col=4)}

    assert "Ananá" not in filas
    assert "SIN PRECIO" not in [celda for valores in filas.values() for celda in valores]
    assert filas["Banana · BANANA BOLIVIA"][2:] == ["01/07/2026", "sigue vigente"]


def test_el_Excel_SIN_NINGUNA_vigencia_lo_DICE_en_vez_de_salir_con_los_encabezados_solos():
    """Una planilla con encabezados y nada abajo se ve igual que una que se generó mal.

    Es el vacío que no se distingue del error, en un archivo que alguien
    abre solo: la pantalla esconde el botón cuando no hay filas, pero la
    URL se puede pedir igual.
    """
    bytes_excel = generar_excel_vigencias("Día", date(2026, 9, 1), date(2026, 9, 14), [], "Frutamax")
    hoja = load_workbook(BytesIO(bytes_excel)).active

    assert hoja.cell(row=3, column=1).value == "No hay precios en este período."
    assert hoja.cell(row=4, column=1).value is None


def test_el_Excel_SALTA_una_fila_sin_vigencias_aunque_le_llegue():
    """El contrato de la función, aparte de quien la llame.

    `_armar_filas_vigencias` ya las filtra, así que en el sistema esto no
    pasa — y por eso mismo el canario que le devuelve el renglón "SIN
    PRECIO" no hacía caer nada: con el filtro puesto esa rama es
    inalcanzable desde la ruta. Este test la ejercita DIRECTO, que es la
    única forma de que la regla quede cuidada en los dos lados y no solo en
    el de arriba.
    """
    filas = [
        {"nombre": "EJEMPLO Con Precio", "vigencias": [
            {"precio": 100.0, "desde_texto": "01/09/2026", "hasta_texto": "sigue vigente"}]},
        {"nombre": "EJEMPLO Sin Precio", "vigencias": []},
    ]
    bytes_excel = generar_excel_vigencias("Día", date(2026, 9, 1), date(2026, 9, 14), filas, "Frutamax")
    hoja = load_workbook(BytesIO(bytes_excel)).active

    cuerpo = [[celda.value for celda in fila] for fila in hoja.iter_rows(min_row=3, max_col=2)]
    assert cuerpo == [["EJEMPLO Con Precio", 100]]
    assert "EJEMPLO Sin Precio" not in [fila[0] for fila in cuerpo]


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
