"""Los VACÍOS DEL DEPÓSITO: los cajones del proveedor de COMPRAS.

NO ES EL CIRCUITO DEL PUESTO, que vive en tests/test_app.py y en otras tablas
enteras. Acá el cajón llega CON la mercadería y se le devuelve al proveedor
que la vendió; allá un cliente del puesto lo trae y un proveedor del puesto lo
retira. No comparten una sola tabla.
"""

import ast
import io
import os
import re
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import (
    COLUMNAS_STOCK_DE_VACIOS_DEPOSITO,
    COMPARADOR_DESDE_EL_CONTEO,
    _SQL_STOCK_DE_VACIOS_DEPOSITO,
    anular_devolucion_vacios,
    crear_devolucion_vacios,
)
from app.main import app

cliente = TestClient(app, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _puerta_de_compras_abierta():
    """Vacíos vive bajo `/compras`, y todo POST ahí tiene el default duro.

    Sin `CLAVE_COMPRAS` cargada un POST no pasa: contesta 503 nombrando la
    variable. Estos tests prueban LAS PANTALLAS, así que la cruzan como la
    cruza una persona, con la clave y su cookie.

    ES UNA SEGUNDA COPIA de la fixture de `tests/test_app.py` y no se puede
    compartir: cada módulo tiene su propio `cliente`, y una fixture le pone
    la cookie a UNO. Lo que sí se comparte es de dónde sale la firma —
    `PUERTA_COMPRAS`— así que el día que la puerta cambie, cambian las dos.
    """
    from app.main import PUERTA_COMPRAS

    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
        try:
            yield
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)
FUENTE_DB = io.open("app/db.py", encoding="utf-8").read()

UN_PROVEEDOR_CONTADO = [{
    "id": 7, "nombre": "Puesto EJEMPLO", "tipo_cajon": "Cajón de ejemplo",
    "desde": date(2026, 9, 17), "contados": 30, "recibidos": 10, "devueltos": 5,
    "stock": 35, "esperando_recepciones": 0, "esperando_devoluciones": 0,
    "esperando_desde": None,
}]

UN_PROVEEDOR_SIN_CONTEO = [{
    "id": 9, "nombre": "Puesto DE EJEMPLO DOS", "tipo_cajon": None,
    "desde": None, "contados": None, "recibidos": 0, "devueltos": 0,
    "stock": None, "esperando_recepciones": 4, "esperando_devoluciones": 1,
    "esperando_desde": date(2026, 9, 11),
}]


def _conexion_falsa(filas_fetchone=None, filas_fetchall=None):
    cursor = MagicMock()
    if filas_fetchone is not None:
        cursor.fetchone.side_effect = filas_fetchone
    if filas_fetchall is not None:
        cursor.fetchall.return_value = filas_fetchall
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conexion = MagicMock()
    conexion.cursor.return_value = cursor
    return conexion, cursor


# ---------------------------------------------------------------------------
# La cuenta derivada
# ---------------------------------------------------------------------------

def test_lo_que_ESPERA_AL_CONTEO_se_cuenta_SIN_PASAR_POR_base():
    """Las dos CTE de "esperando" NO pueden entrar por `base`, o dan cero siempre.

    Las patas del stock entran por `base` —el conteo que arrancó la cuenta— y
    un proveedor sin conteo no produce ni una fila: sus recepciones existen,
    están bien cargadas, y no se ven en ningún lado. Esa es exactamente la
    ausencia de filas del backfill: "acá no hay nada" y "acá hay cosas que no
    te puedo mostrar" se dibujan igual.

    Copiarles el `JOIN base` a estas dos —que es lo natural, están escritas al
    lado de las otras— daría CERO justo en el único caso que les importa. Un
    cero que no puede dar otra cosa, adentro del arreglo escrito para eso.
    """
    for nombre in ("esperando_recep", "esperando_dev"):
        cuerpo = re.search(rf"{nombre} AS \((.*?)\n    \)",
                           _SQL_STOCK_DE_VACIOS_DEPOSITO, re.S)
        assert cuerpo, f"no encontré la CTE {nombre}"
        assert "base" not in cuerpo.group(1), (
            f"{nombre} pasa por `base`: va a contar cero justo para el proveedor "
            "que todavía no tiene conteo, que es el único al que le importa"
        )


def test_las_dos_cosas_que_esperan_van_SEPARADAS_y_no_sumadas():
    """Se cargan en pantallas distintas, así que un solo número manda a buscar mal.

    El que lee "5 esperando" y abre la lista de devoluciones encuentra una,
    porque las otras cuatro son recepciones y no se cargan por ahí. Un solo
    número obligaría a que la pantalla mienta o a que el operario adivine.
    """
    assert "esperando_recepciones" in COLUMNAS_STOCK_DE_VACIOS_DEPOSITO
    assert "esperando_devoluciones" in COLUMNAS_STOCK_DE_VACIOS_DEPOSITO


def test_el_contador_de_lo_que_espera_se_APAGA_cuando_el_conteo_existe():
    """En cero con conteo puesto, o la columna significa dos cosas según otra columna.

    Sin el `CASE`, un proveedor con la cuenta andando devolvería sus
    recepciones como "esperando" y habría que mirar `desde` al lado para
    saber si el número significa algo.
    """
    # EL ANCLA TERMINA EN `END AS <columna>` y no en "hasta la próxima coma":
    # el `COALESCE(er.recepciones, 0)` de adentro tiene una, así que `[^,]*`
    # no llega. El test falló apenas se escribió y el equivocado era el ancla,
    # no el código — la señal de siempre: antes de aflojar el assert, mirar
    # QUÉ fragmento matcheó.
    for columna in ("esperando_recepciones", "esperando_devoluciones", "esperando_desde"):
        assert re.search(rf"CASE WHEN b\.proveedor_id IS NULL THEN.*?END\s*\n?\s*AS {columna}",
                         _SQL_STOCK_DE_VACIOS_DEPOSITO, re.S), columna


def test_el_comparador_del_conteo_NO_ES_PROPIO_sino_el_MISMO_de_las_cajas():
    """Dos constantes para la misma pregunta es como la asimetría del corte apareció ocho veces.

    La pregunta es una sola —¿lo del día del conteo ya está adentro de lo
    contado?— y escribirla dos veces deja dos reglas que se separan sin que
    nadie lo note. Por eso la consulta lleva un `{comp}` y lo formatea con
    `COMPARADOR_DESDE_EL_CONTEO`, que es el de la cuenta de cajas.

    EL TEST PREGUNTA POR LA AUSENCIA, que es la mitad que impide volver: con
    solo afirmar que se usa el bueno, una segunda constante escrita al lado
    pasa igual.
    """
    assert "{comp}" in _SQL_STOCK_DE_VACIOS_DEPOSITO
    cuerpo = ast.parse(FUENTE_DB)
    constantes = {
        objetivo.id
        for nodo in ast.walk(cuerpo)
        if isinstance(nodo, ast.Assign)
        for objetivo in nodo.targets
        if isinstance(objetivo, ast.Name) and "COMPARADOR" in objetivo.id
    }
    assert constantes == {"COMPARADOR_DESDE_EL_CONTEO"}, (
        f"apareció un segundo comparador del conteo: {sorted(constantes)}. "
        "Es la misma pregunta escrita dos veces."
    )


def test_los_NOMBRES_de_las_columnas_son_los_que_la_consulta_DEVUELVE():
    """La tupla y el SELECT tienen que coincidir, o el que lee por índice lee otra cosa.

    En la cuenta de cajas esto reventó TODO guardado: la consulta perdió una
    columna, un lector quedó en `fila[8]`, y como un índice no nombra ninguna
    columna el `grep` del campo sacado no lo encontró nunca.
    """
    seleccion = _SQL_STOCK_DE_VACIOS_DEPOSITO.rsplit("SELECT", 1)[1].split("FROM")[0]
    alias = re.findall(r"AS (\w+)", seleccion)
    # Los tres primeros salen sin alias (p.id, p.nombre viene con alias, ...),
    # así que se cuenta lo que el SELECT produce contra lo DECIDIDO.
    for columna in COLUMNAS_STOCK_DE_VACIOS_DEPOSITO:
        assert columna in seleccion, f"{columna} no está en el SELECT"
    assert len(COLUMNAS_STOCK_DE_VACIOS_DEPOSITO) == 11
    for columna in alias:
        assert columna in COLUMNAS_STOCK_DE_VACIOS_DEPOSITO, (
            f"el SELECT devuelve `{columna}` y la tupla de nombres no lo tiene"
        )


def test_la_fecha_de_la_recepcion_se_lee_EN_HORA_ARGENTINA():
    """`procesada_el` es timestamptz: sin la zona, la recepción de las 23 es del día siguiente.

    Medido con el caso plantado: una recepción del 17/09 a las 23:00
    argentinas, contra un conteo fechado el 18, suma 0 con la zona puesta y 7
    sin ella. Es la novena vez que algo de zona horaria aparece en este
    proyecto.
    """
    # CON EL CONTEO AL LADO, y no `in`: cada fecha se convierte DOS veces —una
    # en la pata del stock y otra en la de lo que espera— así que un `in`
    # pelado pasa en verde con una de las dos sacada. Lo destapó el canario,
    # que reportó "NO APLICA 2 veces" al intentar romper una sola: el aviso de
    # que el texto no dice lo que yo creía.
    for columna, veces in (("co.procesada_el", 2), ("d.creado_en", 2)):
        fragmento = f"({columna} AT TIME ZONE 'America/Argentina/Buenos_Aires')::date"
        assert _SQL_STOCK_DE_VACIOS_DEPOSITO.count(fragmento) == veces, (
            f"{columna} se convierte a hora argentina "
            f"{_SQL_STOCK_DE_VACIOS_DEPOSITO.count(fragmento)} veces y tiene que ser {veces}: "
            "una en la pata del stock y otra en la de lo que espera al conteo"
        )


def test_las_entradas_SALEN_DE_LAS_RECEPCIONES_y_no_de_una_tabla_propia():
    """No hay tabla de entradas, y eso es la decisión que sostiene el módulo.

    Un campo cuya única consecuencia fuera que este stock quede bien es
    exactamente el que se deja de llenar en dos semanas. Derivarlo de algo
    que alguien ya carga porque necesita otra cosa es lo único que lo hace
    inmune.
    """
    assert "FROM compras co" in _SQL_STOCK_DE_VACIOS_DEPOSITO
    assert "co.estado = 'recepcionado'" in _SQL_STOCK_DE_VACIOS_DEPOSITO
    assert "vacios_deposito_entradas" not in FUENTE_DB, (
        "apareció una tabla de entradas: las entradas se derivan de las recepciones"
    )


def test_se_cuenta_lo_ACEPTADO_y_no_lo_que_vino_en_el_remito():
    """Lo rechazado vuelve con la mercadería en el cajón del proveedor: nunca se quedó."""
    assert "COALESCE(co.cantidad_cajones_real, co.cantidad_cajones)" \
        in _SQL_STOCK_DE_VACIOS_DEPOSITO


# ---------------------------------------------------------------------------
# Lo que se escribe
# ---------------------------------------------------------------------------

def test_el_INSERT_de_la_devolucion_guarda_la_ESTRUCTURA_ENTERA():
    """La tupla completa y no tres campos de seis.

    Un test que compara un subconjunto no protege los que no mira: así
    `pedidos_renglones.ficha_id` pasó nueve días guardándose en NULL sin un
    solo error. Que este test falle el día que alguien agregue una columna es
    su función, no una molestia.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[(88,)], filas_fetchall=[])

    with patch("app.db.obtener_conexion", return_value=conexion):
        devolucion_id = crear_devolucion_vacios(
            7, 55, 12, importe=5000.0, foto_ruta="vacios/2026-09-18/v.jpg")

    assert devolucion_id == 88
    insert = next(ll for ll in cursor.execute.call_args_list
                  if "INSERT INTO vacios_deposito_devoluciones" in ll.args[0])
    assert insert.args[1] == (7, 55, 12, 5000.0, "vacios/2026-09-18/v.jpg", 0)
    for columna in ("proveedor_id", "compra_id", "cantidad", "importe",
                    "foto_ruta", "stock_sistema"):
        assert columna in insert.args[0], columna


def test_el_vale_NO_TOCA_compras_importe_ni_el_costeo():
    """El descuento vive SOLO en la fila de la devolución. Es plata de envase.

    EL TEST PREGUNTA POR LA AUSENCIA porque es lo único que impide volver:
    afirmar que el INSERT escribe `importe` pasa igual con un UPDATE a
    `compras` escrito tres líneas más abajo.
    """
    cuerpo = ast.parse(FUENTE_DB)
    funcion = next(n for n in ast.walk(cuerpo)
                   if isinstance(n, ast.FunctionDef) and n.name == "crear_devolucion_vacios")
    texto = ast.unparse(funcion)
    sentencias = [s.strip() for s in texto.split(";")]
    escrituras = [s for s in sentencias
                  if s.upper().lstrip("'\" \n").startswith(("UPDATE", "INSERT"))]
    for escritura in escrituras:
        assert "compras" not in escritura.split("\n")[0].lower() or \
            "vacios_deposito" in escritura.lower(), (
            "la devolución escribe sobre compras: el importe del vale no toca "
            "compras.importe ni el costeo"
        )
    assert "UPDATE compras" not in texto


def test_anular_pregunta_la_EXISTENCIA_con_un_select_SIN_AGREGADO():
    """Con un `count(*)` la guarda no se dispara nunca: la fila vuelve con 0.

    Es el mismo hecho que en plpgsql hace que `if not found` después de un
    agregado no salte jamás, y en Python que `fetchone() is None` no sea
    None. Anular un id inexistente saldría sin hacer nada, y anular uno YA
    anulado pisaría su fecha original — que es peor que no anular.
    """
    conexion, cursor = _conexion_falsa(filas_fetchone=[None])
    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            anular_devolucion_vacios(9999)
            assert False, "no rebotó con un id que no existe"
        except ValueError as invalido:
            assert "no existe" in str(invalido)

    consulta = cursor.execute.call_args_list[0].args[0]
    assert "SELECT anulado_el" in consulta
    for agregado in ("count(", "COUNT(", "sum(", "SUM("):
        assert agregado not in consulta, (
            "la guarda se apoya en un agregado: no puede distinguir "
            "'no hay' de 'hay cero'"
        )


def test_anular_dos_veces_NO_PISA_la_fecha_original():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("2026-09-18",)])
    with patch("app.db.obtener_conexion", return_value=conexion):
        try:
            anular_devolucion_vacios(5)
            assert False, "no rebotó con una devolución ya anulada"
        except ValueError as invalido:
            assert "ya estaba anulada" in str(invalido)
    assert not any("UPDATE" in ll.args[0] for ll in cursor.execute.call_args_list)


# ---------------------------------------------------------------------------
# La pantalla
# ---------------------------------------------------------------------------

def test_sin_conteo_la_pantalla_DICE_QUE_NO_ARRANCO_y_nombra_lo_que_no_se_ve():
    """"No hay nada" y "hay cosas que no te puedo mostrar" no se pueden dibujar igual.

    Y el aviso nombra LA FECHA, porque "fechá el conteo antes" sin un día al
    lado no se puede obedecer.
    """
    with patch("app.main.stock_de_vacios_deposito", return_value=UN_PROVEEDOR_SIN_CONTEO):
        respuesta = cliente.get("/compras/vacios")

    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "todavía no arrancó" in marcado
    assert "4 recepciones" in marcado
    assert "1 devolución" in marcado
    assert "11/09/2026" in marcado
    # Y NO muestra un cero, que es lo que el hueco viene a impedir.
    assert "0 cajones" not in marcado


def test_la_pantalla_explica_LOS_TRES_CASOS_de_la_fecha_del_conteo():
    """El caso que se equivoca suma dos veces, no descuadra nada y no avisa nunca.

    Por eso la regla va en la pantalla —el que arranca la cuenta está acá y no
    va a ir a buscar nada— y con el cuerpo del texto, no en letra chica.
    """
    with patch("app.main.stock_de_vacios_deposito", return_value=UN_PROVEEDOR_SIN_CONTEO):
        respuesta = cliente.get("/compras/vacios")

    marcado = respuesta.text.split("</style>")[-1]
    assert "Contá a la mañana" in marcado
    assert "Contar cero es contar" in marcado
    assert "dos veces" in marcado


def test_con_conteo_la_pantalla_muestra_el_stock_y_SUS_PATAS():
    """El número solo no se puede leer: sin las patas, nadie puede verificarlo."""
    with patch("app.main.stock_de_vacios_deposito", return_value=UN_PROVEEDOR_CONTADO):
        respuesta = cliente.get("/compras/vacios")

    marcado = respuesta.text.split("</style>")[-1]
    assert "35 cajones" in marcado
    assert "contados 30" in marcado
    assert "recibidos +10" in marcado
    assert "devueltos −5" in marcado


def test_el_detalle_ofrece_SOLO_compras_recepcionadas():
    """Un vale contra una compra que no llegó describe cajones que no están.

    La pantalla no ofrece lo que la escritura después rechazaría: un callejón
    —apretar y comerse un error por algo que la pantalla propuso— es peor que
    no ofrecer nada.
    """
    cuerpo = ast.parse(FUENTE_DB)
    funcion = next(n for n in ast.walk(cuerpo)
                   if isinstance(n, ast.FunctionDef) and n.name == "compras_para_vale_de_vacios")
    assert "c.estado = 'recepcionado'" in ast.unparse(funcion)


def test_el_detalle_dice_que_el_importe_NO_se_le_descuenta_a_la_compra():
    """La pantalla lo dice porque el que carga el vale es el que se lo pregunta."""
    with patch("app.main.stock_de_vacios_deposito", return_value=UN_PROVEEDOR_CONTADO), \
         patch("app.main.compras_para_vale_de_vacios",
               return_value=[{"id": 1, "fecha": date(2026, 9, 17),
                              "articulo": "Tomate EJEMPLO", "cajones": 30}]), \
         patch("app.main.listar_devoluciones_vacios", return_value=[]), \
         patch("app.main.listar_tipos_cajon", return_value=[]):
        respuesta = cliente.get("/compras/vacios/7")

    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "no se le descuenta a la compra" in marcado


def test_la_pantalla_esta_LINKEADA_desde_el_hub_de_compras():
    """Una ruta sin botón no la ve nadie, y la suite entera entra por la URL."""
    hub = io.open("templates/compras.html", encoding="utf-8").read()
    assert 'href="/compras/vacios"' in hub


def test_el_boton_NO_se_llama_solo_Vacios_porque_el_del_puesto_ya_se_llama_asi():
    """Dos botones con el mismo nombre en un sistema donde los dos existen."""
    hub = io.open("templates/compras.html", encoding="utf-8").read()
    etiqueta = re.search(r'href="/compras/vacios">([^<]+)<', hub)
    assert etiqueta, "no encontré el botón"
    assert etiqueta.group(1).strip() != "Vacíos"
    assert "depósito" in etiqueta.group(1).lower()


# ---------------------------------------------------------------------------
# A 390px, con lo único cuyo largo NO controlamos
# ---------------------------------------------------------------------------

UN_NOMBRE_QUE_NO_SE_PUEDE_PARTIR = "PUESTODEEJEMPLOSINUNSOLOESPACIOPARAPARTIRLO"


def _medir(html, **opciones):
    from scripts.medir_layout import medir_sync

    return medir_sync(html, ancho=390, selector_filas=".tarjeta", **opciones)


def _pantallas_de_vacios(nombre):
    """Las dos pantallas con el nombre que se le pase, en los TRES lugares.

    RECIBE EL NOMBRE porque es lo único que acá lo escribe una persona: el
    proveedor, el tipo de cajón y el artículo contra el que va el vale. El
    largo de los nombres no lo controlamos, y un diseño que solo entra con
    los de hoy se rompe el día que alguien cargue uno largo.
    """
    proveedores = [dict(UN_PROVEEDOR_CONTADO[0], nombre=nombre, tipo_cajon=nombre)]
    devoluciones = [{"id": 1, "cantidad": 25, "importe": 18500.0,
                     "foto_ruta": "2026-09-12/vale.jpg", "fecha": date(2026, 9, 12),
                     "anulada": False, "compra_id": 501, "articulo": nombre,
                     "fecha_compra": date(2026, 9, 12)}]
    compras = [{"id": 501, "fecha": date(2026, 9, 12),
                "articulo": nombre, "cajones": 40}]

    with patch("app.main.stock_de_vacios_deposito", return_value=proveedores):
        indice = cliente.get("/compras/vacios")
    with patch("app.main.stock_de_vacios_deposito", return_value=proveedores), \
         patch("app.main.listar_devoluciones_vacios", return_value=devoluciones), \
         patch("app.main.compras_para_vale_de_vacios", return_value=compras), \
         patch("app.main.listar_tipos_cajon", return_value=[{"id": 1, "nombre": nombre}]):
        detalle = cliente.get("/compras/vacios/7")

    assert indice.status_code == 200 and detalle.status_code == 200
    return indice.text, detalle.text


def test_las_DOS_pantallas_aguantan_un_nombre_QUE_NO_SE_PUEDE_PARTIR():
    """Medido a 390px, y el desborde se lee de `desborde_pagina`.

    En una pantalla de TARJETAS la clave `desborde` viene clavada en 0 y el
    número real viaja en `desborde_pagina` (corolario 47 adentro del
    resultado). Medido antes del arreglo: el índice desbordaba 384px y el
    detalle 371px — la tarjeta entera se arrastraba de costado.

    Y el del detalle NO estaba en la pantalla sino en la BARRA compartida:
    su fallback es achicar y después envolver en dos líneas, y una palabra
    sin espacios no tiene dónde envolver. Hasta el 18/09 ningún título de
    barra venía de algo que tipea una persona.
    """
    for pantalla, html in zip(("índice", "detalle"),
                              _pantallas_de_vacios(UN_NOMBRE_QUE_NO_SE_PUEDE_PARTIR)):
        medicion = _medir(html)
        desborde = medicion.get("desborde_pagina", medicion["desborde"])
        # El denominador al lado: sin él, "no se pisa nada" y "no se miró
        # nada" son el mismo cero (corolarios 45 y 53).
        assert medicion["pares"] > 0, pantalla
        assert desborde == 0, f"{pantalla} desborda {desborde}px"
        assert medicion["solapes"] == [], f"{pantalla}: {medicion['solapes']}"


def test_las_DOS_pantallas_con_nombres_NORMALES_tampoco_se_pisan():
    """La otra mitad del par: que el caso cómodo también esté medido.

    Sin él, un arreglo que rompiera el caso normal para aguantar el
    impartible pasaría el test de arriba sin que nada cayera.
    """
    for pantalla, html in zip(("índice", "detalle"),
                              _pantallas_de_vacios("Puesto EJEMPLO del Norte")):
        medicion = _medir(html)
        desborde = medicion.get("desborde_pagina", medicion["desborde"])
        assert medicion["pares"] > 0, pantalla
        assert desborde == 0, f"{pantalla} desborda {desborde}px"
        assert medicion["solapes"] == [], f"{pantalla}: {medicion['solapes']}"


# ---------------------------------------------------------------------------
# El cajón se declara EN EL ALTA, y la regla es UNA
# ---------------------------------------------------------------------------

def _rutas_que_resuelven_el_cajon():
    """Las funciones de `app/main.py` que deciden en qué cajón entrega alguien.

    Se buscan por el ÁRBOL y no por el texto: `ast.unparse` de una función
    devuelve también su docstring, y el docstring de una guarda NOMBRA la
    guarda para explicar por qué está — así que un `in` sobre el texto pasa
    igual con la llamada sacada (corolario 59).
    """
    arbol = ast.parse(io.open("app/main.py", encoding="utf-8").read())
    encontradas = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for hijo in ast.walk(nodo):
            if (isinstance(hijo, ast.Call) and isinstance(hijo.func, ast.Name)
                    and hijo.func.id == "_tipo_cajon_elegido"):
                encontradas.add(nodo.name)
    return encontradas


def test_las_DOS_puertas_del_cajon_llaman_a_LA_MISMA_funcion():
    """El alta de Proveedores y el detalle de Vacíos preguntan lo mismo.

    ENCONTRADO contra DECIDIDO y no una lista propia (corolario 60): falla
    cuando aparece una tercera puerta que se escribe su propia versión, y
    también cuando una de las dos deja de usarla.

    La copia que se separe no falla ruidosamente: crea un "Cajón Chico" al
    lado del que ya estaba y parte el stock de vacíos en dos tipos.
    """
    assert _rutas_que_resuelven_el_cajon() == {
        "crear_proveedor_compras_ruta",
        "guardar_tipo_cajon_de_proveedor",
    }


def test_el_ALTA_de_proveedores_OFRECE_declarar_el_cajon():
    with patch("app.main.listar_proveedores_para_abm", return_value=[]), \
         patch("app.main.listar_tipos_cajon",
               return_value=[{"id": 3, "nombre": "Cajón DE EJEMPLO"}]):
        respuesta = cliente.get("/compras/proveedores")

    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert 'name="tipo_cajon_id"' in marcado
    assert 'name="cajon_nombre_nuevo"' in marcado
    assert "Cajón DE EJEMPLO" in marcado
    # NO es obligatorio: los cuarenta y pico que ya están cargados no lo
    # tienen, y exigirlo en el alta la dejaría más estricta que la base.
    assert 'name="tipo_cajon_id" required' not in marcado


def test_el_ALTA_guarda_el_cajon_del_proveedor_RECIEN_CREADO():
    with patch("app.main.buscar_proveedor_por_codigo", return_value=None), \
         patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(88, True)), \
         patch("app.main.buscar_tipo_cajon_por_nombre", return_value=None), \
         patch("app.main.crear_tipo_cajon", return_value=5) as crear, \
         patch("app.main.asignar_tipo_cajon") as asignar:
        respuesta = cliente.post("/compras/proveedores/nuevo", data={
            "nombre": "Puesto EJEMPLO", "codigo_puesto": "N07P41",
            "tipo_cajon_id": "", "cajon_nombre_nuevo": "Cajón cosechero DE EJEMPLO",
        }, follow_redirects=False)

    assert respuesta.status_code == 303
    crear.assert_called_once_with("Cajón cosechero DE EJEMPLO")
    asignar.assert_called_once_with(88, 5)


def test_el_ALTA_sin_cajon_NO_escribe_nada():
    """"Todavía no sé" es una respuesta, y no tiene que pisar nada."""
    with patch("app.main.buscar_proveedor_por_codigo", return_value=None), \
         patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(88, True)), \
         patch("app.main.asignar_tipo_cajon") as asignar:
        respuesta = cliente.post("/compras/proveedores/nuevo", data={
            "nombre": "Puesto EJEMPLO", "codigo_puesto": "N07P41",
            "tipo_cajon_id": "", "cajon_nombre_nuevo": "",
        }, follow_redirects=False)

    assert respuesta.status_code == 303
    asignar.assert_not_called()


def test_si_el_CAJON_falla_el_proveedor_QUEDA_CARGADO_y_lo_dice():
    """El proveedor ya está creado: un 500 acá lo mandaría a reintentar.

    Y reintentar contra un código que ya existe es el camino del aviso "ese
    código ya es de…", que se lee como que el alta no funcionó.
    """
    with patch("app.main.buscar_proveedor_por_codigo", return_value=None), \
         patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(88, True)), \
         patch("app.main.buscar_tipo_cajon_por_nombre",
               side_effect=RuntimeError("la base no contesta")):
        respuesta = cliente.post("/compras/proveedores/nuevo", data={
            "nombre": "Puesto EJEMPLO", "codigo_puesto": "N07P41",
            "tipo_cajon_id": "", "cajon_nombre_nuevo": "Cajón DE EJEMPLO",
        }, follow_redirects=False)

    assert respuesta.status_code == 303
    destino = respuesta.headers["location"]
    assert "cargado" in destino
    assert "el+caj%C3%B3n+no" in destino or "el caj%C3%B3n no" in destino


def test_el_503_de_una_puerta_NOMBRA_SU_SECTOR_y_no_Gerencia():
    """La misma pantalla la comparten las tres zonas con clave.

    Hasta el 18/09 su texto era entero de Gerencia, así que un POST de
    Compras sin la variable cargada contestaba "Falta la clave de Gerencia"
    y explicaba que corregir una recepción mueve la cotización. El que lo
    leía se iba a pedir la clave equivocada: la url era una y los sectores,
    tres (corolario 56).

    Se descubrió acá porque Vacíos es de Compras y su primer POST dio 503.
    """
    from app.main import PUERTA_COMPRAS

    # Sin la variable cargada: es el único caso que dibuja esta pantalla.
    with patch.dict(os.environ, {"CLAVE_COMPRAS": ""}):
        respuesta = cliente.post("/compras/vacios/conteo",
                                 data={"proveedor_id": "7", "cantidad": "30",
                                       "fecha": "2026-09-18"},
                                 follow_redirects=False)

    assert respuesta.status_code == 503
    assert PUERTA_COMPRAS.env_var in respuesta.text, "tiene que decir QUÉ variable falta"
    marcado = respuesta.text.split("</style>")[-1]
    assert PUERTA_COMPRAS.titulo in marcado
    # Y la jerga del sector AJENO no puede aparecer: afirmar el texto bueno
    # pasa igual si la frase vieja quedó tres líneas más abajo.
    assert "Gerencia" not in marcado
    assert "Corregir una recepción" not in marcado


def test_un_cajon_que_YA_EXISTE_se_REUSA_en_vez_de_duplicarse():
    """Lo encontró un canario en CERO, y la causa es el corolario 30.

    Los otros tests del cajón plantan un nombre que NO existe
    (`buscar_tipo_cajon_por_nombre` devuelve None), o sea exactamente la
    rama donde reusar y crear hacen lo mismo. Con esa batería, sacarle el
    `buscar(...) or` a la regla no hace caer nada: el `crear` se llama igual.

    Y lo que se rompería no falla ruidosamente — crea un "Cajón Chico" al
    lado del que ya estaba, y el stock de vacíos queda partido en dos tipos
    que nadie va a notar.
    """
    with patch("app.main.buscar_proveedor_por_codigo", return_value=None), \
         patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(88, True)), \
         patch("app.main.buscar_tipo_cajon_por_nombre", return_value=4), \
         patch("app.main.crear_tipo_cajon") as crear, \
         patch("app.main.asignar_tipo_cajon") as asignar:
        respuesta = cliente.post("/compras/proveedores/nuevo", data={
            "nombre": "Puesto EJEMPLO", "codigo_puesto": "N07P41",
            "tipo_cajon_id": "", "cajon_nombre_nuevo": "Cajón DE EJEMPLO",
        }, follow_redirects=False)

    assert respuesta.status_code == 303
    crear.assert_not_called()
    asignar.assert_called_once_with(88, 4)


def test_el_TEXTO_le_gana_al_de_la_lista_y_no_al_reves():
    """Si tipeó un nombre es porque el de la lista no era.

    Sin este caso, una regla que mirara primero el `<select>` pasaría todos
    los demás tests: en ellos el select viene vacío.
    """
    with patch("app.main.buscar_proveedor_por_codigo", return_value=None), \
         patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(88, True)), \
         patch("app.main.buscar_tipo_cajon_por_nombre", return_value=4), \
         patch("app.main.crear_tipo_cajon"), \
         patch("app.main.asignar_tipo_cajon") as asignar:
        cliente.post("/compras/proveedores/nuevo", data={
            "nombre": "Puesto EJEMPLO", "codigo_puesto": "N07P41",
            "tipo_cajon_id": "9", "cajon_nombre_nuevo": "Cajón DE EJEMPLO",
        }, follow_redirects=False)

    asignar.assert_called_once_with(88, 4)


def test_el_DETALLE_de_vacios_tambien_reusa_el_cajon_que_ya_existe():
    """La otra puerta, con el mismo caso: las dos comparten la función.

    Va escrito igual y no "ya lo cubre el de arriba": el test de la
    estructura dice que HOY las dos llaman a la misma; éste dice qué tiene
    que pasar, así que sobrevive al día que alguien las separe.
    """
    with patch("app.main.buscar_tipo_cajon_por_nombre", return_value=4), \
         patch("app.main.crear_tipo_cajon") as crear, \
         patch("app.main.asignar_tipo_cajon") as asignar:
        respuesta = cliente.post("/compras/vacios/7/cajon", data={
            "tipo_cajon_id": "9", "nombre_nuevo": "Cajón DE EJEMPLO",
        }, follow_redirects=False)

    assert respuesta.status_code == 303
    crear.assert_not_called()
    asignar.assert_called_once_with(7, 4)
