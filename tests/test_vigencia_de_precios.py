"""Cargar un precio que rige desde ANTES de que alguien lo tipee.

El precio se pacta el lunes y se carga el jueves. Hasta el 14/09 el sistema
escribía siempre con la fecha del día, así que el historial y el listado por
período mostraban un mundo donde los precios empiezan a regir el día que
alguien los tipeó — y no había forma de corregir uno mal cargado de un día
pasado.

LAS DOS MITADES QUE HAY QUE PROBAR JUNTAS, porque cada una sin la otra deja
el agujero entero:

1. **La fecha se puede elegir**, con un tilde para la que no es hoy — y la
   guarda vive en el SERVIDOR, donde se escribe, no en el HTML.
2. **Lo tipeado se compara contra el precio que REGÍA ESA FECHA**, no contra
   el que la pantalla mostró. Sin esto, corregir el 05/09 al mismo valor que
   rige hoy se descarta como "no cambió nada": no se escribe nada, la
   pantalla dice que los precios ya estaban al día, y la corrección que se
   pidió no ocurrió.
"""

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)

HOY = date(2026, 9, 14)
ANTES = date(2026, 9, 5)

CLIENTES = [{"id": 1, "nombre": "Día", "utilidad_objetivo": 20.0}]
FICHAS = [
    {"id": 901, "cliente_id": 1, "articulo_id": 1, "articulo_nombre": "Banana", "articulo_grupo": "fruta",
     "envase_id": None, "envase_nombre": None, "contenido_caja": 6, "unidad_venta": "kilo",
     "envase_variable": False, "nombre_cliente": "BANANA BOLIVIA", "codigo_cliente": "90101"},
]

# LOS DOS PRECIOS SON DISTINTOS A PROPÓSITO: hoy rige 1000 y el 05/09 regía
# 800. Con los dos iguales, ningún test podría decir cuál de las dos fuentes
# usó el código — el fixture contestaría por él.
VIGENTE_HOY = [{"ficha_id": 901, "articulo_id": 1, "precio": 1000.0, "vigente_desde": date(2026, 9, 10)}]
VIGENTE_EL_5 = [{"ficha_id": 901, "articulo_id": 1, "precio": 800.0, "vigente_desde": date(2026, 8, 20)}]


def _post(datos, vigentes=None, vigentes_por_fecha=None):
    """Manda la carga manual. `vigentes_por_fecha` responde según la fecha pedida."""
    def _vigentes(cliente_id, fecha):
        if vigentes_por_fecha is not None:
            return vigentes_por_fecha[fecha]
        return VIGENTE_HOY if vigentes is None else vigentes

    with (
        patch("app.main.listar_clientes", return_value=CLIENTES),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS),
        patch("app.main.listar_precios_vigentes_por_cliente", side_effect=_vigentes),
        patch("app.main._hoy_argentina", return_value=HOY),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post("/precios/cargar", data=datos, follow_redirects=False)
    return respuesta, mock_guardar


def _datos(precio="1200", **extra):
    datos = {"cliente_id": "1", "pendiente_precio_901": precio, "pendiente_original_901": "1000.0"}
    datos.update(extra)
    return datos


# --- la fecha: hoy sin pedir nada, hacia atrás con tilde, hacia adelante nunca ---


def test_sin_el_campo_escribe_HOY_y_no_pide_nada():
    """El caso normal no puede costar un paso, y un formulario viejo sigue andando."""
    respuesta, mock_guardar = _post(_datos())

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [{"ficha_id": 901, "precio": 1200.0}], HOY)


def test_una_fecha_ANTERIOR_sin_tilde_se_RECHAZA_y_no_escribe_nada():
    """La guarda va donde se ESCRIBE: este POST no pasó por ninguna pantalla.

    El `required` del HTML no lo ve un formulario armado a mano, y es
    exactamente el caso del mail con la fecha dada vuelta: el candado
    automático frenaba y el camino de la gente solo avisaba.
    """
    respuesta, mock_guardar = _post(_datos(vigente_desde=ANTES.isoformat()))

    assert respuesta.status_code == 400
    assert "05/09/2026" in respuesta.json()["detail"]
    mock_guardar.assert_not_called()


def test_una_fecha_ANTERIOR_con_tilde_escribe_CON_ESA_FECHA():
    respuesta, mock_guardar = _post(
        _datos(vigente_desde=ANTES.isoformat(), confirmo_vigencia="si"),
        vigentes_por_fecha={ANTES: VIGENTE_EL_5},
    )

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [{"ficha_id": 901, "precio": 1200.0}], ANTES)


def test_una_fecha_FUTURA_se_rechaza_aunque_venga_el_tilde():
    """Nadie pidió cargar el precio de mañana, y aceptarlo dejaría "vigente" un
    precio que todavía no rige. Un dedo que tipea mal el año es mucho más
    probable que un precio futuro de verdad — por eso ni con tilde."""
    futuro = date(2026, 12, 25)
    respuesta, mock_guardar = _post(_datos(vigente_desde=futuro.isoformat(), confirmo_vigencia="si"))

    assert respuesta.status_code == 400
    assert "futuro" in respuesta.json()["detail"]
    mock_guardar.assert_not_called()


def test_una_fecha_ILEGIBLE_se_rechaza_en_vez_de_caer_a_hoy():
    """Caer a hoy en silencio sería peor que rechazar: la fila queda con una
    fecha que nadie eligió y se ve igual que una carga normal."""
    respuesta, mock_guardar = _post(_datos(vigente_desde="25/12/2026"))

    assert respuesta.status_code == 400
    mock_guardar.assert_not_called()


def test_la_fecha_de_HOY_explicita_no_pide_tilde():
    respuesta, mock_guardar = _post(_datos(vigente_desde=HOY.isoformat()))

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [{"ficha_id": 901, "precio": 1200.0}], HOY)


# --- la comparación: contra el precio de ESA fecha, no contra el de hoy ---


def test_la_CORRECCION_al_mismo_precio_que_rige_hoy_SI_se_escribe():
    """El caso que el código viejo perdía en silencio, y es el que motivó todo.

    Hoy rige 1000 y el 05/09 quedó cargado 800, que estaba mal: ese día ya
    regían 1000. Se corrige poniendo 1000 con fecha 05/09.

    Comparando contra el vigente de HOY (1000) el diff dice "no cambió nada",
    no se escribe ninguna fila y la pantalla contesta que los precios ya
    estaban al día. Comparando contra el del 05/09 (800) la corrección entra.
    """
    respuesta, mock_guardar = _post(
        _datos(precio="1000", vigente_desde=ANTES.isoformat(), confirmo_vigencia="si"),
        vigentes_por_fecha={ANTES: VIGENTE_EL_5},
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/precios?guardado=1"
    mock_guardar.assert_called_once_with(1, [{"ficha_id": 901, "precio": 1000.0}], ANTES)


def test_lo_que_YA_regia_esa_fecha_no_genera_una_fila_de_mas():
    """La otra mitad: sin ésta, la de arriba la pasa igual un código que
    escriba siempre. Los dos casos juntos son lo único que las separa."""
    respuesta, mock_guardar = _post(
        _datos(precio="800", vigente_desde=ANTES.isoformat(), confirmo_vigencia="si"),
        vigentes_por_fecha={ANTES: VIGENTE_EL_5},
    )

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [], ANTES)


def test_el_precio_ORIGINAL_DEL_FORMULARIO_ya_no_decide_nada():
    """Ese campo es lo que la PANTALLA MOSTRÓ, y mostrar no es decidir.

    Se manda un original absurdo: si todavía entrara en la comparación, el
    resultado cambiaría. La base dice 1000 y se tipea 1000, así que la
    respuesta correcta es "no cambió nada" venga lo que venga en el form.
    """
    respuesta, mock_guardar = _post(
        {"cliente_id": "1", "pendiente_precio_901": "1000", "pendiente_original_901": "7777.77"}
    )

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [], HOY)


def test_la_comparacion_pide_el_vigente_A_LA_FECHA_ELEGIDA_y_no_a_hoy():
    """Por la FECHA con la que se consultó la base, no por el resultado.

    El resultado lo entrega el mock: con la fecha equivocada devolvería lo
    mismo si el fixture fuera uno solo. Lo que prueba que se usó la fecha
    elegida es con qué argumento se llamó.
    """
    pedidas = []

    def _vigentes(cliente_id, fecha):
        pedidas.append(fecha)
        return VIGENTE_EL_5

    with (
        patch("app.main.listar_clientes", return_value=CLIENTES),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS),
        patch("app.main.listar_precios_vigentes_por_cliente", side_effect=_vigentes),
        patch("app.main._hoy_argentina", return_value=HOY),
        patch("app.main.guardar_precios_cliente"),
    ):
        cliente.post(
            "/precios/cargar",
            data=_datos(vigente_desde=ANTES.isoformat(), confirmo_vigencia="si"),
            follow_redirects=False,
        )

    assert pedidas == [ANTES], f"se consultó {pedidas} en vez de la fecha elegida"


# --- la pantalla ---


def _marcado_de_cargar():
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS),
        patch("app.main.listar_precios_vigentes_por_cliente", return_value=VIGENTE_HOY),
        patch("app.main._hoy_argentina", return_value=HOY),
        patch("app.main.calcular_listado_para_negociar_precios", return_value=[]),
        patch("app.main.facturacion_por_ficha", return_value={"por_ficha": {}, "dias": 4}),
    ):
        return cliente.get("/precios/cargar?cliente_id=1").text


def test_la_pantalla_de_carga_manual_trae_el_campo_y_el_tilde():
    """Anclado en el ATRIBUTO y no en el texto: el bloque incluido trae su
    propio <style>, así que `split("</style>")[-1]` corta de más (corolario 50)
    y una palabra suelta puede estar en un comentario."""
    texto = _marcado_de_cargar()

    assert 'name="vigente_desde"' in texto
    assert 'name="confirmo_vigencia"' in texto
    assert f'value="{HOY.isoformat()}"' in texto
    # El selector tampoco ofrece el futuro — la misma regla que el servidor.
    assert f'max="{HOY.isoformat()}"' in texto


def test_los_DOS_caminos_de_guardado_de_la_pantalla_manual_mandan_la_vigencia():
    """"Guardar" y "Guardar y generar listado" arman el POST por separado.

    Uno solo con la fecha es un camino que escribe con fecha de hoy sin que
    nada avise — la forma de bug que más veces se repitió acá: una lista de
    lugares que tienen que hacer todos lo mismo y uno se queda afuera.
    """
    texto = _marcado_de_cargar()

    assert texto.count('agregarCampoOculto("vigente_desde"') == 1
    assert texto.count('datos.set("vigente_desde"') == 1
    # Y los dos frenan antes de mandar si falta el tilde.
    assert texto.count("vigenciaListaParaGuardar()") == 3  # la definición + los dos llamados


def test_el_bloque_de_vigencia_es_UNA_sola_copia_incluida_por_las_dos_pantallas():
    """Escrito dos veces serían dos reglas, y la que rechaza dejaría de ser la
    que el servidor cree que rechaza."""
    import io

    incluyen = []
    for plantilla in ("templates/precios_cargar.html", "templates/precios_revision_foto.html"):
        contenido = io.open(plantilla, encoding="utf-8").read()
        assert '{% include "_vigencia_de_precios.html" %}' in contenido, plantilla
        # Y NO tienen el campo escrito a mano al lado del include.
        assert 'name="vigente_desde"' not in contenido, plantilla
        incluyen.append(plantilla)
    assert len(incluyen) == 2


def test_el_tilde_arranca_ESCONDIDO_de_verdad_y_no_solo_con_el_atributo():
    """El atributo es la INTENCIÓN; lo que el operario ve lo decide el CSS.

    `[hidden]` del navegador viene sin `!important`, así que el `display: flex`
    de la fila le gana y el bloque queda a la vista con el atributo puesto. Ya
    pasó con el tilde de las mermas: la guarda estaba y no hacía nada, y ningún
    test que lea el HTML puede verlo.
    """
    import io

    bloque = io.open("templates/_vigencia_de_precios.html", encoding="utf-8").read()

    # SIN `split("</style>")`: el comentario de arriba de esta plantilla NOMBRA
    # esa expresión —está puesto para avisar del corolario 50— así que cortar
    # ahí se come el bloque entero. Una declaración de CSS no aparece en prosa,
    # así que alcanza con buscarla en el archivo.
    assert "[hidden] { display: none !important; }" in bloque
    # Y el que le gana si eso faltara, para que este test nombre el conflicto.
    assert ".vigencia-tilde {" in bloque and "display: flex;" in bloque


# --- el MISMO recorrido por el otro camino de carga ---------------------
#
# Lo encontró el canario, no la lectura: con la carga por foto escribiendo
# siempre con fecha de hoy, la suite quedaba ENTERA en verde. Los tests de
# arriba ejercitan solo la carga manual, y las dos pantallas guardan por
# funciones distintas — es la lista de lugares que tienen que hacer todos lo
# mismo, con uno afuera.


def _post_foto(datos, vigentes_por_fecha=None):
    def _vigentes(cliente_id, fecha):
        if vigentes_por_fecha is not None:
            return vigentes_por_fecha[fecha]
        return VIGENTE_HOY

    completo = {
        "cliente_id": "1",
        "cantidad_renglones": "1",
        "tipo_archivo": "foto",
        "archivo_preview": "",
        "item_0_ficha_id": "901",
        "item_0_precio_original": "1000.0",
        "item_0_precio_nuevo": "1200",
    }
    completo.update(datos)
    with (
        patch("app.main.listar_clientes", return_value=CLIENTES),
        patch("app.main.listar_fichas_por_cliente", return_value=FICHAS),
        patch("app.main.listar_precios_vigentes_por_cliente", side_effect=_vigentes),
        patch("app.main._hoy_argentina", return_value=HOY),
        patch("app.main.guardar_precios_cliente") as mock_guardar,
    ):
        respuesta = cliente.post("/precios/cargar-foto/confirmar", data=completo, follow_redirects=False)
    return respuesta, mock_guardar


def test_la_carga_por_FOTO_tambien_escribe_con_la_fecha_elegida():
    respuesta, mock_guardar = _post_foto(
        {"vigente_desde": ANTES.isoformat(), "confirmo_vigencia": "si"},
        vigentes_por_fecha={ANTES: VIGENTE_EL_5},
    )

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [{"ficha_id": 901, "precio": 1200.0}], ANTES, foto_ruta=None)


def test_la_carga_por_FOTO_tambien_exige_el_tilde():
    respuesta, mock_guardar = _post_foto({"vigente_desde": ANTES.isoformat()})

    assert respuesta.status_code == 400
    mock_guardar.assert_not_called()


def test_la_carga_por_FOTO_tambien_compara_contra_el_vigente_DE_ESA_FECHA():
    """El mismo caso que el código viejo perdía en silencio, por el otro camino."""
    respuesta, mock_guardar = _post_foto(
        {"item_0_precio_nuevo": "1000", "vigente_desde": ANTES.isoformat(), "confirmo_vigencia": "si"},
        vigentes_por_fecha={ANTES: VIGENTE_EL_5},
    )

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [{"ficha_id": 901, "precio": 1000.0}], ANTES, foto_ruta=None)


def test_la_carga_por_FOTO_sin_el_campo_escribe_HOY():
    respuesta, mock_guardar = _post_foto({})

    assert respuesta.status_code == 303
    mock_guardar.assert_called_once_with(1, [{"ficha_id": 901, "precio": 1200.0}], HOY, foto_ruta=None)
