"""Los VACÍOS DEL DEPÓSITO: los cajones del proveedor de COMPRAS, por PILA.

NO ES EL CIRCUITO DEL PUESTO, que vive en tests/test_app.py y en otras tablas
enteras. Acá el cajón llega CON la mercadería y se le devuelve al proveedor
que la vendió; allá un cliente del puesto lo trae y un proveedor del puesto lo
retira. No comparten una sola tabla.

DESDE EL 25/09 la cuenta es por PILA —proveedor y marca de cajón— y arranca
de una FOTO: el stock que el sistema mostraba ese día. Lo que la cuenta hace
con números se prueba CONTRA POSTGRES en
`tests/test_vacios_pilas_contra_la_base.py`; acá va lo que un mock SÍ puede
ver: el texto de la consulta, lo que se escribe, y las pantallas.
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
    COLUMNAS_PILAS_DE_VACIOS,
    _SQL_PILAS_DE_VACIOS,
    anular_ajuste_vacios_deposito,
    anular_devolucion_vacios,
    crear_devolucion_vacios,
)
from app.main import PUERTA_ADMINISTRACION, app

cliente = TestClient(app, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _puerta_de_compras_abierta():
    """Vacíos vive bajo `/compras` y `/administracion`, y los dos tienen puerta.

    ES UNA SEGUNDA COPIA de la fixture de `tests/test_app.py` y no se puede
    compartir: cada módulo tiene su propio `cliente`, y una fixture le pone
    la cookie a UNO. Lo que sí se comparte es de dónde sale la firma.
    """
    from app.main import PUERTA_COMPRAS

    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta",
                                 "CLAVE_ADMINISTRACION": "admin-secreta"}):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
        cliente.cookies.set(PUERTA_ADMINISTRACION.cookie,
                            PUERTA_ADMINISTRACION.firma("admin-secreta"))
        try:
            yield
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)
            cliente.cookies.delete(PUERTA_ADMINISTRACION.cookie)


FUENTE_DB = io.open("app/db.py", encoding="utf-8").read()


def _pila(marca_id, marca, stock):
    return {"proveedor_id": 7, "proveedor": "Puesto EJEMPLO", "tipo_cajon": "Cajón de ejemplo",
            "marca_id": marca_id, "marca": marca, "foto": 0, "recibidos": 0,
            "devueltos": 0, "ajustes": 0, "asignados": 0, "stock": stock}


UN_PROVEEDOR = [{
    "id": 7, "nombre": "Puesto EJEMPLO", "tipo_cajon": "Cajón de ejemplo", "stock": 35,
    "pilas": [_pila(None, None, 12), _pila(71, "EJ Roja", 23)],
}]
MARCAS = [{"id": 71, "nombre": "EJ Roja"}, {"id": 72, "nombre": "EJ Azul"}]


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


def _parches_del_detalle(proveedores=UN_PROVEEDOR, marcas=MARCAS, devoluciones=(),
                         movimientos=(), senas=None, tipos=()):
    return [
        patch("app.main.stock_de_vacios_deposito", return_value=list(proveedores)),
        patch("app.main.proveedor_para_vacios", return_value=None),
        patch("app.main.listar_marcas_vacio", return_value=list(marcas)),
        patch("app.main.listar_devoluciones_vacios", return_value=list(devoluciones)),
        patch("app.main.listar_ajustes_y_asignaciones_vacios", return_value=list(movimientos)),
        patch("app.main.sena_por_cajon_de_la_ultima_recepcion", return_value=senas or {}),
        patch("app.main.listar_tipos_cajon", return_value=list(tipos)),
    ]


def _con(parches):
    from contextlib import ExitStack
    pila = ExitStack()
    for parche in parches:
        pila.enter_context(parche)
    return pila


# ---------------------------------------------------------------------------
# La cuenta derivada: el TEXTO (los números van contra Postgres)
# ---------------------------------------------------------------------------

def test_los_NOMBRES_de_las_columnas_son_los_que_la_consulta_DEVUELVE():
    """La tupla y el SELECT final tienen que coincidir, en orden.

    En la cuenta de cajas esto reventó TODO guardado: la consulta perdió una
    columna, un lector quedó en `fila[8]`, y un índice no nombra ninguna
    columna — el `grep` del campo sacado no lo encuentra nunca.
    """
    seleccion = _SQL_PILAS_DE_VACIOS.rsplit("SELECT", 1)[1].split("FROM")[0]
    alias = re.findall(r"AS (\w+)", seleccion)
    assert tuple(alias) == COLUMNAS_PILAS_DE_VACIOS


def test_las_entradas_son_las_recepciones_CON_SENA_y_nada_mas():
    """Sin seña no hay cajón que devolver (dueño, 25/09); pendiente no llegó."""
    assert "co.estado = 'recepcionado'" in _SQL_PILAS_DE_VACIOS
    assert "COALESCE(co.sena, 0) > 0" in _SQL_PILAS_DE_VACIOS
    assert "vacios_deposito_entradas" not in FUENTE_DB, (
        "apareció una tabla de entradas: las entradas se derivan de las recepciones")


def test_el_corte_compara_contra_el_INSTANTE_de_la_foto_y_no_contra_su_dia():
    """Con la fecha, lo recibido el 25/09 después de sacar la foto se perdía.

    Encontrado corriendo la cuenta contra Postgres, no leyéndola: la foto es
    de las 14, la recepción de las 16 del mismo día, y `procesada_el::date >
    f.fecha` la descartaba. Se compara contra `f.creado_en`, en las DOS patas
    que la foto ya incluye.
    """
    assert "co.procesada_el > f.creado_en" in _SQL_PILAS_DE_VACIOS
    assert "d.creado_en > f.creado_en" in _SQL_PILAS_DE_VACIOS
    assert "f.fecha" not in _SQL_PILAS_DE_VACIOS


def test_las_ANULADAS_no_cuentan_en_ninguna_de_las_tres_tablas_que_se_anulan():
    """Calificado por ALIAS (corolario 4): son tres tablas con la misma columna."""
    # CON EL CONTEO: la asignación entra dos veces (sale de una pila y entra
    # en otra), y un `in` pasa con una de las dos patas sin el filtro.
    for alias, veces in (("d", 1), ("a", 1), ("s", 2)):
        assert _SQL_PILAS_DE_VACIOS.count(f"{alias}.anulado_el IS NULL") == veces, alias


def test_la_ASIGNACION_resta_de_una_pila_y_suma_en_la_otra():
    """Una pata sola —o las dos con el mismo signo— cambia el total de un movimiento
    que por definición no lo cambia."""
    assert "s.marca_desde_id, 0, 0, 0, 0, -s.cantidad" in _SQL_PILAS_DE_VACIOS
    assert "s.marca_hasta_id, 0, 0, 0, 0, s.cantidad" in _SQL_PILAS_DE_VACIOS


def test_la_pila_se_lee_con_el_PROVEEDOR_BLOQUEADO_y_con_LA_MISMA_consulta():
    """Dos devoluciones a la vez no pueden leer el mismo stock y sacar de más.

    Y la cuenta no se escribe dos veces: el freno filtra la consulta de la
    pantalla, no una segunda versión.
    """
    cuerpo = ast.parse(FUENTE_DB)
    funcion = next(n for n in ast.walk(cuerpo)
                   if isinstance(n, ast.FunctionDef) and n.name == "_stock_de_la_pila")
    texto = ast.unparse(funcion)
    assert "FOR UPDATE" in texto
    assert "_SQL_PILAS_DE_VACIOS" in texto
    for escritor in ("crear_devolucion_vacios", "crear_asignacion_vacios"):
        nodo = next(n for n in ast.walk(cuerpo)
                    if isinstance(n, ast.FunctionDef) and n.name == escritor)
        llamadas = {c.func.id for c in ast.walk(nodo)
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        assert "_stock_de_la_pila" in llamadas, escritor


# ---------------------------------------------------------------------------
# Lo que se escribe
# ---------------------------------------------------------------------------

def test_el_INSERT_de_la_devolucion_guarda_la_ESTRUCTURA_ENTERA():
    """La tupla completa, y `stock_sistema` es lo que la pila tenía al devolver."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[(88,)])
    with patch("app.db.obtener_conexion", return_value=conexion), \
         patch("app.db._stock_de_la_pila", return_value=30):
        devolucion_id = crear_devolucion_vacios(
            7, 71, 12, foto_ruta="vacios/2026-09-25/v.jpg", importe=5000.0)

    assert devolucion_id == 88
    insert = next(ll for ll in cursor.execute.call_args_list
                  if "INSERT INTO vacios_deposito_devoluciones" in ll.args[0])
    assert insert.args[1] == (7, 71, 12, 5000.0, "vacios/2026-09-25/v.jpg", 30)
    for columna in ("proveedor_id", "marca_vacio_id", "cantidad", "importe",
                    "foto_ruta", "stock_sistema"):
        assert columna in insert.args[0], columna
    assert "compra_id" not in insert.args[0], "la devolución ya no va contra una compra"


def test_devolver_MAS_de_lo_que_hay_NO_escribe_nada():
    conexion, cursor = _conexion_falsa(filas_fetchone=[("EJ Roja",)])
    with patch("app.db.obtener_conexion", return_value=conexion), \
         patch("app.db._stock_de_la_pila", return_value=3):
        with pytest.raises(ValueError, match="hay 3 cajones: no se pueden devolver 4"):
            crear_devolucion_vacios(7, 71, 4, foto_ruta="v.jpg")
    assert not any("INSERT" in ll.args[0] for ll in cursor.execute.call_args_list)
    conexion.commit.assert_not_called()


def test_sin_FOTO_no_llega_ni_a_abrir_la_base():
    """La guarda va donde se ESCRIBE, antes que nada: un POST armado a mano no la saltea."""
    with patch("app.db.obtener_conexion") as abrir:
        with pytest.raises(ValueError, match="ajuste"):
            crear_devolucion_vacios(7, None, 1, foto_ruta="   ")
    abrir.assert_not_called()


def test_el_vale_NO_TOCA_compras_importe_ni_el_costeo():
    """El descuento vive SOLO en la fila de la devolución. Es plata de envase."""
    cuerpo = ast.parse(FUENTE_DB)
    funcion = next(n for n in ast.walk(cuerpo)
                   if isinstance(n, ast.FunctionDef) and n.name == "crear_devolucion_vacios")
    assert "UPDATE compras" not in ast.unparse(funcion)


def test_anular_pregunta_la_EXISTENCIA_con_un_select_SIN_AGREGADO():
    """Con un `count(*)` la guarda no se dispara nunca: la fila vuelve con 0."""
    conexion, cursor = _conexion_falsa(filas_fetchone=[None])
    with patch("app.db.obtener_conexion", return_value=conexion):
        with pytest.raises(ValueError, match="no existe"):
            anular_devolucion_vacios(9999)
    consulta = cursor.execute.call_args_list[0].args[0]
    assert "SELECT anulado_el" in consulta
    for agregado in ("count(", "COUNT(", "sum(", "SUM("):
        assert agregado not in consulta


def test_anular_dos_veces_NO_PISA_la_fecha_original_y_el_genero_viaja():
    """"Ese ajuste ya estaba anulada" salía igual de prolijo que la frase buena."""
    for anular, frase in ((anular_devolucion_vacios, "Esa devolución ya estaba anulada"),
                          (anular_ajuste_vacios_deposito, "Ese ajuste ya estaba anulado")):
        conexion, cursor = _conexion_falsa(filas_fetchone=[("2026-09-18",)])
        with patch("app.db.obtener_conexion", return_value=conexion):
            with pytest.raises(ValueError) as invalido:
                anular(5)
        assert str(invalido.value) == frase + "."
        assert not any("UPDATE" in ll.args[0] for ll in cursor.execute.call_args_list)


# ---------------------------------------------------------------------------
# Las rutas
# ---------------------------------------------------------------------------

def _foto():
    import base64
    # un JPEG de 1x1 de verdad: `_comprimir_foto_jpeg` lo tiene que poder abrir
    return ("vale.jpg", base64.b64decode(
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////"
        "////////////////////////////////////////////wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAA"
        "AAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AN//Z"), "image/jpeg")


def test_la_DEVOLUCION_sin_foto_rebota_400_y_no_escribe():
    with _con(_parches_del_detalle()), \
         patch("app.main.crear_devolucion_vacios") as crear, \
         patch("app.main.subir_foto_comanda") as subir:
        respuesta = cliente.post("/compras/vacios/7/devolucion",
                                 data={"marca_vacio_id": "71", "cantidad": "3"})
    assert respuesta.status_code == 400
    assert "Sin la foto del vale no es una devolución" in respuesta.text
    crear.assert_not_called()
    subir.assert_not_called()


def test_la_DEVOLUCION_con_foto_escribe_la_PILA_elegida_y_la_ruta_subida():
    with _con(_parches_del_detalle()), \
         patch("app.main._comprimir_foto_jpeg", return_value=b"jpg"), \
         patch("app.main.subir_foto_comanda", return_value="vacios/v.jpg"), \
         patch("app.main.crear_devolucion_vacios", return_value=1) as crear:
        respuesta = cliente.post("/compras/vacios/7/devolucion",
                                 data={"marca_vacio_id": "", "cantidad": "3", "importe": "2.400"},
                                 files={"foto": _foto()}, follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].startswith("/compras/vacios/7?")
    crear.assert_called_once_with(7, None, 3, foto_ruta="vacios/v.jpg", importe=2400.0)


def test_si_la_foto_NO_SE_SUBE_no_se_guarda_nada_y_lo_dice():
    with _con(_parches_del_detalle()), \
         patch("app.main._comprimir_foto_jpeg", return_value=b"jpg"), \
         patch("app.main.subir_foto_comanda", side_effect=RuntimeError("storage caído")), \
         patch("app.main.crear_devolucion_vacios") as crear:
        respuesta = cliente.post("/compras/vacios/7/devolucion",
                                 data={"marca_vacio_id": "71", "cantidad": "3"},
                                 files={"foto": _foto()})
    assert respuesta.status_code == 502
    assert "No se guardó nada" in respuesta.text
    crear.assert_not_called()


def test_el_FRENO_de_la_pila_se_ve_en_la_pantalla_con_el_numero():
    with _con(_parches_del_detalle()), \
         patch("app.main._comprimir_foto_jpeg", return_value=b"jpg"), \
         patch("app.main.subir_foto_comanda", return_value="vacios/v.jpg"), \
         patch("app.main.crear_devolucion_vacios",
               side_effect=ValueError("En la pila EJ Roja hay 23 cajones: no se pueden devolver 40.")):
        respuesta = cliente.post("/compras/vacios/7/devolucion",
                                 data={"marca_vacio_id": "71", "cantidad": "40"},
                                 files={"foto": _foto()})
    assert respuesta.status_code == 400
    assert "hay 23 cajones: no se pueden devolver 40" in respuesta.text


def test_AJUSTE_y_ASIGNACION_existen_SOLO_bajo_administracion():
    """Decisión del dueño: los cierra la puerta de Administración, por prefijo.

    ENCONTRADO contra DECIDIDO: se barren las rutas de la app y no una lista
    escrita a mano, así que una tercera puerta bajo /compras falla acá.
    """
    rutas = {r.path for r in app.routes if hasattr(r, "path")}
    encontradas = {r for r in rutas if re.search(r"^/(compras|administracion)/vacios/.*(ajuste|asignacion|movimiento)", r)}
    assert encontradas == {
        "/administracion/vacios/{proveedor_id}/ajuste",
        "/administracion/vacios/{proveedor_id}/asignacion",
        "/administracion/vacios/movimiento/{tipo}/{movimiento_id}/anular",
    }


def test_el_AJUSTE_lleva_el_signo_del_SENTIDO_y_no_uno_tipeado():
    for sentido, esperado in (("sobran", 4), ("faltan", -4)):
        with _con(_parches_del_detalle()), \
             patch("app.main.crear_ajuste_vacios_deposito") as crear:
            respuesta = cliente.post("/administracion/vacios/7/ajuste", data={
                "marca_vacio_id": "71", "sentido": sentido, "cantidad": "4",
                "motivo": "EJ se contaron"}, follow_redirects=False)
        assert respuesta.status_code == 303
        crear.assert_called_once_with(7, 71, esperado, "EJ se contaron")


def test_el_AJUSTE_sin_sentido_rebota_y_no_escribe():
    with _con(_parches_del_detalle()), \
         patch("app.main.crear_ajuste_vacios_deposito") as crear:
        respuesta = cliente.post("/administracion/vacios/7/ajuste", data={
            "marca_vacio_id": "71", "sentido": "", "cantidad": "4", "motivo": "x"})
    assert respuesta.status_code == 400
    crear.assert_not_called()


def test_la_ASIGNACION_pasa_de_la_pila_elegida_a_la_marca_elegida():
    with _con(_parches_del_detalle()), \
         patch("app.main.crear_asignacion_vacios") as crear:
        respuesta = cliente.post("/administracion/vacios/7/asignacion", data={
            "marca_desde_id": "", "marca_hasta_id": "72", "cantidad": "5"},
            follow_redirects=False)
    assert respuesta.status_code == 303
    crear.assert_called_once_with(7, None, 72, 5)


def test_el_CONTEO_va_al_COTEJO_y_no_arranca_ninguna_cuenta():
    with patch("app.main.crear_conteo_vacios_deposito") as crear:
        respuesta = cliente.post("/compras/vacios/conteo", data={
            "proveedor_id": "7", "marca_vacio_id": "71", "cantidad": "0",
            "fecha": "2026-09-25"}, follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/compras/vacios/cotejo"
    # CERO VALE: contar cero es contar.
    crear.assert_called_once_with(7, 71, 0, date(2026, 9, 25))


# ---------------------------------------------------------------------------
# Las pantallas
# ---------------------------------------------------------------------------

def _indice(proveedores=UN_PROVEEDOR):
    with patch("app.main.stock_de_vacios_deposito", return_value=proveedores), \
         patch("app.main.listar_proveedores",
               return_value=[{"id": 7, "nombre": "Puesto EJEMPLO"}]), \
         patch("app.main.listar_marcas_vacio_por_proveedor", return_value={7: MARCAS}):
        return cliente.get("/compras/vacios")


def test_el_indice_muestra_el_total_y_CADA_PILA_con_su_marca():
    respuesta = _indice()
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "35 cajones" in marcado
    assert "sin asignar" in marcado
    assert "EJ Roja" in marcado
    # y la cuenta vieja no quedó dibujada en ningún lado
    for jerga in ("todavía no arrancó", "Contá a la mañana", "recibidos +"):
        assert jerga not in marcado, jerga


def test_el_conteo_OFRECE_solo_proveedores_y_marcas_cargados():
    """Dueño, 25/09: solo lo cargado. Por eso son selectores y no texto libre."""
    marcado = _indice().text.split("</style>")[-1]
    assert '<select id="proveedor_id" name="proveedor_id" required>' in marcado
    assert '<select id="marca_vacio_id" name="marca_vacio_id">' in marcado
    assert 'name="proveedor_nuevo"' not in marcado and 'name="marca_nueva"' not in marcado


def test_el_detalle_en_COMPRAS_no_ofrece_ajuste_ni_asignacion():
    with _con(_parches_del_detalle(movimientos=[{
            "tipo": "ajuste", "id": 3, "cantidad": 2, "marca": "EJ Roja",
            "marca_hasta": None, "motivo": "EJ aparecieron",
            "fecha": date(2026, 9, 25), "anulada": False}])):
        respuesta = cliente.get("/compras/vacios/7")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "/ajuste" not in marcado and "/asignacion" not in marcado
    assert "/movimiento/" not in marcado, "anular un ajuste tampoco es de Compras"
    # el movimiento SÍ se ve: esconderlo dejaría el número sin explicar
    assert "EJ aparecieron" in marcado
    assert "se carga en Administración" in marcado


def test_el_detalle_en_ADMINISTRACION_ofrece_ajuste_asignacion_y_anular():
    with _con(_parches_del_detalle(movimientos=[{
            "tipo": "asignacion", "id": 3, "cantidad": 2, "marca": None,
            "marca_hasta": "EJ Roja", "motivo": None,
            "fecha": date(2026, 9, 25), "anulada": False}])):
        respuesta = cliente.get("/administracion/vacios/7")
    marcado = respuesta.text.split("</style>")[-1]
    assert 'action="/administracion/vacios/7/ajuste"' in marcado
    assert 'action="/administracion/vacios/7/asignacion"' in marcado
    assert 'action="/administracion/vacios/movimiento/asignacion/3/anular"' in marcado
    assert "/compras/" not in marcado


def test_el_vale_se_PRECARGA_con_la_sena_de_CADA_pila():
    with _con(_parches_del_detalle(senas={None: 300.0, 71: 800.0})):
        respuesta = cliente.get("/compras/vacios/7")
    marcado = respuesta.text.split("</style>")[-1]
    opciones = re.findall(r'<option value="(\d*)"\s+data-sena="([^"]*)"', marcado)
    # LAS TRES pilas, la azul en cero y sin seña: devolver de ahí lo frena el
    # server con el número, que es más claro que una opción que falta.
    assert opciones == [("", "300.0"), ("71", "800.0"), ("72", "")]
    assert "No se le descuenta a la" in marcado


def test_la_foto_del_vale_es_REQUIRED_en_el_formulario():
    with _con(_parches_del_detalle()):
        marcado = cliente.get("/compras/vacios/7").text.split("</style>")[-1]
    assert re.search(r'<input id="foto" name="foto" type="file"[^>]*required', marcado)


def test_un_proveedor_EN_CERO_se_abre_igual_para_cargarle_marcas():
    parches = _parches_del_detalle(proveedores=[], marcas=[])
    parches[1] = patch("app.main.proveedor_para_vacios", return_value={
        "id": 9, "nombre": "Puesto EJEMPLO DOS", "tipo_cajon": None, "stock": 0, "pilas": []})
    with _con(parches):
        respuesta = cliente.get("/compras/vacios/9")
    assert respuesta.status_code == 200
    assert 'action="/compras/vacios/9/marca"' in respuesta.text


def test_un_proveedor_que_NO_existe_da_404():
    with _con(_parches_del_detalle(proveedores=[])):
        respuesta = cliente.get("/compras/vacios/999")
    assert respuesta.status_code == 404


def test_el_COTEJO_dice_la_diferencia_y_cierra_en_cero():
    filas = [{"proveedor_id": 7, "proveedor": "Puesto EJEMPLO", "marca": "EJ Roja",
              "contado": 20, "fecha": date(2026, 9, 25), "sistema": 23, "diferencia": 3},
             {"proveedor_id": 7, "proveedor": "Puesto EJEMPLO", "marca": None,
              "contado": 12, "fecha": date(2026, 9, 25), "sistema": 12, "diferencia": 0}]
    with patch("app.main.cotejo_de_vacios_deposito", return_value=filas):
        respuesta = cliente.get("/compras/vacios/cotejo")
    assert respuesta.status_code == 200
    marcado = respuesta.text.split("</style>")[-1]
    assert "EJ Roja" in marcado and "cierra" in marcado


def test_la_pantalla_esta_LINKEADA_desde_el_hub_de_compras():
    """Una ruta sin botón no la ve nadie, y la suite entera entra por la URL."""
    hub = io.open("templates/compras.html", encoding="utf-8").read()
    assert 'href="/compras/vacios"' in hub


def test_el_boton_NO_se_llama_solo_Vacios_porque_el_del_puesto_ya_se_llama_asi():
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
    pytest.importorskip("playwright", reason="la medición de layout necesita un navegador")
    from scripts.medir_layout import medir_sync
    return medir_sync(html, ancho=390, selector_filas=".tarjeta", **opciones)


def _pantallas_de_vacios(nombre):
    """Las dos pantallas con el nombre en TODOS los lugares que tipea una persona:
    el proveedor, el tipo de cajón y la MARCA."""
    pilas = [dict(_pila(None, None, 12), proveedor=nombre, tipo_cajon=nombre),
             dict(_pila(71, nombre, 23), proveedor=nombre, tipo_cajon=nombre)]
    proveedores = [dict(UN_PROVEEDOR[0], nombre=nombre, tipo_cajon=nombre, pilas=pilas)]
    marcas = [{"id": 71, "nombre": nombre}]
    devoluciones = [{"id": 1, "cantidad": 25, "importe": 18500.0,
                     "foto_ruta": "2026-09-12/vale.jpg", "fecha": date(2026, 9, 12),
                     "anulada": False, "compra_id": None, "articulo": None,
                     "fecha_compra": None, "marca": nombre}]
    movimientos = [{"tipo": "ajuste", "id": 3, "cantidad": 2, "marca": nombre,
                    "marca_hasta": None, "motivo": nombre,
                    "fecha": date(2026, 9, 25), "anulada": False}]

    with patch("app.main.stock_de_vacios_deposito", return_value=proveedores), \
         patch("app.main.listar_proveedores", return_value=[{"id": 7, "nombre": nombre}]), \
         patch("app.main.listar_marcas_vacio_por_proveedor", return_value={7: marcas}):
        indice = cliente.get("/compras/vacios")
    with _con(_parches_del_detalle(proveedores=proveedores, marcas=marcas,
                                   devoluciones=devoluciones, movimientos=movimientos,
                                   tipos=[{"id": 1, "nombre": nombre}])):
        detalle = cliente.get("/administracion/vacios/7")

    assert indice.status_code == 200 and detalle.status_code == 200
    return indice.text, detalle.text


def test_las_DOS_pantallas_aguantan_un_nombre_QUE_NO_SE_PUEDE_PARTIR():
    """Medido a 390px, y el desborde se lee de `desborde_pagina` (corolario 53)."""
    for pantalla, html in zip(("índice", "detalle"),
                              _pantallas_de_vacios(UN_NOMBRE_QUE_NO_SE_PUEDE_PARTIR)):
        medicion = _medir(html)
        desborde = medicion.get("desborde_pagina", medicion["desborde"])
        assert medicion["pares"] > 0, pantalla
        assert desborde == 0, f"{pantalla} desborda {desborde}px"
        assert medicion["solapes"] == [], f"{pantalla}: {medicion['solapes']}"


def test_las_DOS_pantallas_con_nombres_NORMALES_tampoco_se_pisan():
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
