"""Un proveedor con VARIOS puestos, y el puesto por el que llegó cada compra (27/09).

FRUTAMAX S.R.L. es el N09P41 y también el N09P39. Hasta hoy el sistema tenía
un código por proveedor y lo había cargado dos veces. Desde la migración
`codigos_1` a `codigos_4`:

  · `proveedores.codigo_puesto` sigue siendo el PRINCIPAL, y los otros viven
    en `proveedores_codigos`. Una compra que llega por uno de ésos se carga en
    ese proveedor, sin crear otro y sin cambiarle el nombre.
  · `compras.codigo_llegada` guarda por qué puesto llegó, y eso es lo que
    muestran Logística, Recepción, Compras pendientes y los Excel.
  · El alta a mano compara el nombre plegado y, si coincide con uno que ya
    está, pregunta con un modal si es el mismo.

Los de Postgres corren contra `db/esquema_completo.sql`, que tiene el trigger
que no deja que un código sea de dos proveedores: con la base mockeada eso no
se puede ver (corolario 89).
"""
import ast
import io
import os
import re
import sys
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app.main import _agrupar_pendientes_por_guia, app, templates  # noqa: E402
from core.matcheo_comanda import adivinar_proveedor  # noqa: E402
from core.nombres_de_proveedor import nombre_de_proveedor_plegado, nombres_parecidos, son_parecidos  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
cliente = TestClient(app, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _puerta_de_compras_abierta():
    """Copia de la fixture de tests/test_app.py: cada módulo tiene su cliente."""
    from app.main import PUERTA_COMPRAS

    with patch.dict(os.environ, {"CLAVE_COMPRAS": "compras-secreta"}):
        cliente.cookies.set(PUERTA_COMPRAS.cookie, PUERTA_COMPRAS.firma("compras-secreta"))
        try:
            yield
        finally:
            cliente.cookies.delete(PUERTA_COMPRAS.cookie)


# ------------------------------------------------------ el plegado del nombre


def test_el_plegado_saca_PUNTOS_ESPACIOS_TILDES_y_la_FORMA_SOCIETARIA():
    """La regla del dueño, con los cuatro sufijos."""
    base = nombre_de_proveedor_plegado("Frutamax")
    for variante in ("FRUTAMAX S.R.L.", "Frutamax SRL", "frutamax s.a.", "FRUTAMAX SAS", "Frutamax S.H."):
        assert nombre_de_proveedor_plegado(variante) == base, variante
    assert nombre_de_proveedor_plegado("Hermanos Núñez") == nombre_de_proveedor_plegado("HERMANOS NUNEZ")


def test_el_sufijo_se_saca_como_PALABRA_y_no_adentro_de_otra():
    """El caso que no tiene que plegar: con un `replace("sa", "")` suelto,
    CASA PÉREZ y CA PÉREZ serían el mismo proveedor."""
    assert nombre_de_proveedor_plegado("Casa Pérez") != nombre_de_proveedor_plegado("Ca Pérez")
    assert nombre_de_proveedor_plegado("Frutamax Sur") != nombre_de_proveedor_plegado("Frutamax")


def test_un_nombre_que_es_SOLO_un_sufijo_no_coincide_con_nada():
    proveedores = [{"id": 1, "nombre": "S.A."}, {"id": 2, "nombre": "EJEMPLO Uno"}]
    assert nombres_parecidos("S.R.L.", proveedores) == []
    assert nombres_parecidos("ejemplo uno s.a.", proveedores) == [proveedores[1]]


def test_PRODUCTOS_HNOS_HERMANOS_y_CIA_no_distinguen_a_un_proveedor():
    """El par del 27/09: DON LAZZARO y PRODUCTOS DON LAZZARO. Con solo los
    cuatro sufijos societarios, "productos" quedaba y no se igualaban."""
    assert nombre_de_proveedor_plegado("PRODUCTOS DON LAZZARO") == nombre_de_proveedor_plegado("Don Lazzaro")
    base = nombre_de_proveedor_plegado("Núñez")
    for variante in ("Núñez Hnos.", "NUÑEZ HERMANOS", "Núñez y Cía.", "Nuñez Cia"):
        assert nombre_de_proveedor_plegado(variante) in (base, base + "y"), variante
    assert nombres_parecidos("Núñez y Cía.", [{"id": 1, "nombre": "NUÑEZ HNOS"}]) != []


def test_las_palabras_nuevas_se_sacan_como_PALABRA_y_no_adentro_de_otra():
    """"CIAMPI" no pierde su "cia": con un replace suelto sería "mpi"."""
    assert nombre_de_proveedor_plegado("Ciampi") == "ciampi"
    assert nombre_de_proveedor_plegado("Productora del Sur") == "productoradelsur"


def test_un_nombre_que_CONTIENE_al_otro_es_parecido_en_las_DOS_direcciones():
    assert son_parecidos("Frutamax", "Frutamax Sur")
    assert son_parecidos("FRUTAMAX SUR S.A.", "frutamax")
    proveedores = [{"id": 1, "nombre": "Lazzaro"}, {"id": 2, "nombre": "EJEMPLO Otro"}]
    assert nombres_parecidos("Productos Don Lazzaro", proveedores) == [proveedores[0]]


def test_contener_NO_vale_para_un_nombre_CORTO_ni_para_dos_distintos():
    """El caso que no tiene que avisar: sin el mínimo, "Sur" está adentro de
    medio padrón. Y el control de siempre: dos nombres que no se contienen."""
    assert not son_parecidos("Sur", "Frutamax Sur")
    assert not son_parecidos("Luz", "Luzzi Hnos")
    assert son_parecidos("Luzz", "Luzzi Hnos"), "con el mínimo, cuatro letras sí"
    assert not son_parecidos("Casa Pérez", "Ca Pérez")
    assert not son_parecidos("EJEMPLO Uno", "EJEMPLO Nuevo")


# ------------------------------------------------ lo que se adivina y se ofrece


def test_una_comanda_leida_con_un_CODIGO_ALTERNATIVO_sugiere_ESE_proveedor_con_el_codigo_LEIDO():
    """El id es el de la S.R.L. —así se trae su aprendizaje— y el código es el
    leído, porque es el que va al formulario y de ahí a `codigo_llegada`."""
    proveedores = [
        {"id": 3, "codigo_puesto": "N09P41", "nombre": "FRUTAMAX S.R.L.", "codigos_alternativos": ["N09P39"]},
        {"id": 5, "codigo_puesto": "N09P38", "nombre": "EJEMPLO Vecino", "codigos_alternativos": []},
    ]
    leido = {"tipo_pabellon": "nave", "numero_pabellon": "9", "puesto": "39", "nombre": "EJEMPLO Otro nombre"}
    sugerido = adivinar_proveedor(leido, proveedores)
    assert sugerido["id"] == 3
    assert sugerido["codigo_puesto"] == "N09P39"
    assert proveedores[0]["codigo_puesto"] == "N09P41", "no puede pisar la lista que recibió"


CARGAS_CON_AUTOCOMPLETAR = {
    "compra_fotos_multiples.html", "compra_listado.html", "compra_manual.html",
    "compra_revision_foto.html", "deposito_ingresar_proveedor.html",
}


def test_TODAS_las_pantallas_de_carga_ofrecen_los_codigos_alternativos():
    """El conjunto ENCONTRADO contra el DECIDIDO (corolario 60): la pantalla de
    carga que arme su propia lista vuelve a ofrecer solo el principal, y el
    que tipea N09P39 cree que es un proveedor nuevo."""
    encontradas = set()
    for nombre in os.listdir(os.path.join(RAIZ, "templates")):
        texto = io.open(os.path.join(RAIZ, "templates", nombre), encoding="utf-8").read()
        if "PROVEEDORES_LISTA = [" in texto:
            encontradas.add(nombre)
    # Buscar Compras la usa para FILTRAR por proveedor (va por id), no para
    # cargar: ahí un puesto alternativo sería una entrada repetida.
    encontradas.discard("compras_buscar.html")
    assert encontradas == CARGAS_CON_AUTOCOMPLETAR
    for nombre in encontradas:
        texto = io.open(os.path.join(RAIZ, "templates", nombre), encoding="utf-8").read()
        assert texto.count('{% include "_proveedores_lista.html" %}') == 1, nombre


def test_el_autocompletar_saca_UNA_entrada_por_codigo_con_el_mismo_nombre():
    marcado = templates.env.get_template("_proveedores_lista.html").render(proveedores=[
        {"codigo_puesto": "N09P41", "nombre": "FRUTAMAX S.R.L.", "codigos_alternativos": ["N09P39"]},
        {"codigo_puesto": "N01P02", "nombre": "EJEMPLO Uno", "codigos_alternativos": []},
    ])
    entradas = re.findall(r'\{ codigo: "([A-Z0-9]+)", nombre: "([^"]+)" \}', marcado)
    assert entradas == [("N09P41", "FRUTAMAX S.R.L."), ("N09P39", "FRUTAMAX S.R.L."),
                        ("N01P02", "EJEMPLO Uno")]


# ------------------------------------------------------------ la estructura


FUENTE_MAIN = io.open(os.path.join(RAIZ, "app/main.py"), encoding="utf-8").read()
FUENTE_DB = io.open(os.path.join(RAIZ, "app/db.py"), encoding="utf-8").read()


def test_TODO_llamador_de_la_app_pasa_codigo_llegada_EXPLICITO():
    """Sin default en la firma, olvidarlo es un TypeError — pero la suite
    parchea `crear_compra` en todos lados, así que el TypeError no lo ve nadie
    hasta producción. El árbol sí."""
    constructores = {"crear_compra", "crear_compras_de_comanda", "_insertar_compra_con_guia"}
    llamadas = []
    for fuente in (FUENTE_MAIN, FUENTE_DB):
        for nodo in ast.walk(ast.parse(fuente)):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in constructores:
                llamadas.append((nodo.func.id, nodo.lineno,
                                 any(k.arg == "codigo_llegada" for k in nodo.keywords)))
    assert len(llamadas) >= 8, f"se esperaban los ocho llamadores, hay {len(llamadas)}"
    sin_codigo = [(n, l) for n, l, tiene in llamadas if not tiene]
    assert sin_codigo == [], f"no pasan codigo_llegada: {sin_codigo}"


LECTORAS_DECIDIDAS = {
    "buscar_compras", "obtener_compra", "obtener_detalle_compra",
    "listar_compras_pendientes_recepcion", "compra_para_marcar_armada",
    "listar_compras_procesadas_hoy_recepcion", "buscar_retiros", "buscar_ingresos_deposito",
    "listar_compras_pendientes_retiro", "listar_compras_procesadas_hoy_retiro",
    "listar_compras_sin_precio",
}


def test_TODA_lectura_de_compras_que_trae_el_codigo_del_proveedor_trae_TAMBIEN_el_de_llegada():
    """ENCONTRADO contra DECIDIDO: una consulta nueva que muestre el principal
    en vez del de llegada pone a Logística a buscar la mercadería del 39 en el
    41."""
    encontradas = set()
    for nodo in ast.walk(ast.parse(FUENTE_DB)):
        if isinstance(nodo, ast.FunctionDef):
            texto = " ".join(p.value for p in ast.walk(nodo)
                             if isinstance(p, ast.Constant) and isinstance(p.value, str))
            if "p.codigo_puesto AS proveedor_codigo_puesto" in texto:
                encontradas.add(nodo.name)
                assert "coalesce(c.codigo_llegada, p.codigo_puesto) AS codigo_llegada" in texto, nodo.name
    assert encontradas == LECTORAS_DECIDIDAS


def test_la_busqueda_por_codigo_esta_escrita_UNA_vez_y_la_usan_LAS_DOS_puertas():
    llaman = set()
    for nodo in ast.walk(ast.parse(FUENTE_DB)):
        if isinstance(nodo, ast.FunctionDef):
            for p in ast.walk(nodo):
                if isinstance(p, ast.Name) and p.id == "_SQL_PROVEEDOR_POR_CODIGO":
                    llaman.add(nodo.name)
    assert llaman == {"buscar_proveedor_por_codigo", "obtener_o_crear_proveedor_por_codigo"}


def test_la_guia_con_DOS_puestos_los_nombra_a_los_DOS():
    """La guía es una por proveedor y día, así que junta el 41 y el 39: el que
    va a retirar tiene que saber que son dos lugares."""
    compras = [
        {"guia_id": 9, "proveedor_nombre": "FRUTAMAX S.R.L.", "proveedor_codigo_puesto": "N09P41",
         "codigo_llegada": "N09P41"},
        {"guia_id": 9, "proveedor_nombre": "FRUTAMAX S.R.L.", "proveedor_codigo_puesto": "N09P41",
         "codigo_llegada": "N09P39"},
        {"guia_id": 9, "proveedor_nombre": "FRUTAMAX S.R.L.", "proveedor_codigo_puesto": "N09P41",
         "codigo_llegada": "N09P41"},
    ]
    guia, = _agrupar_pendientes_por_guia(compras)
    assert guia["codigos_llegada"] == ["N09P41", "N09P39"]


# ------------------------------------------------------------ el modal del alta


PROVEEDORES_ABM = [
    {"id": 3, "codigo_puesto": "N09P41", "nombre": "FRUTAMAX S.R.L.", "activo": True, "compras": 352,
     "codigos_alternativos": []},
    {"id": 1, "codigo_puesto": "N01P02", "nombre": "EJEMPLO Uno", "activo": True, "compras": 1,
     "codigos_alternativos": []},
]


def _alta(datos):
    with (
        patch("app.main.buscar_proveedor_por_codigo", return_value=None),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(40, False)) as puerta,
        patch("app.main.listar_proveedores_para_abm", return_value=PROVEEDORES_ABM),
        patch("app.main.listar_tipos_cajon", return_value=[]),
    ):
        respuesta = cliente.post("/compras/proveedores/nuevo", data=datos, follow_redirects=False)
    return respuesta, puerta


def test_un_nombre_PARECIDO_frena_el_alta_con_el_modal_y_NO_crea_nada():
    respuesta, puerta = _alta({"nombre": "Frutamax", "codigo_puesto": "N09P39"})

    assert respuesta.status_code == 409
    puerta.assert_not_called()
    marcado = respuesta.text.split('<div class="modal-fondo">')[1]
    assert 'action="/compras/proveedores/3/asociar-codigo"' in marcado
    assert 'name="codigo_puesto" value="N09P39"' in marcado
    assert 'name="es_otro" value="1"' in marcado
    assert "sumarle el puesto N09P39" in marcado
    # La consecuencia queda a la vista: cambia lo que se hace.
    assert "se cargan en ese proveedor, sin cambiarle el nombre" in marcado


def test_PRODUCTOS_DON_LAZZARO_frena_el_alta_contra_DON_LAZZARO():
    """El caso real que el modal no veía el 27/09, por la ruta entera."""
    lazzaro = {"id": 10, "codigo_puesto": "L02P42", "nombre": "DON LAZZARO", "activo": True,
               "compras": 14, "codigos_alternativos": []}
    with (
        patch("app.main.buscar_proveedor_por_codigo", return_value=None),
        patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(40, False)) as puerta,
        patch("app.main.listar_proveedores_para_abm", return_value=PROVEEDORES_ABM + [lazzaro]),
        patch("app.main.listar_tipos_cajon", return_value=[]),
    ):
        respuesta = cliente.post("/compras/proveedores/nuevo",
                                 data={"nombre": "PRODUCTOS DON LAZZARO", "codigo_puesto": "L02P44"},
                                 follow_redirects=False)

    assert respuesta.status_code == 409
    puerta.assert_not_called()
    marcado = respuesta.text.split('<div class="modal-fondo">')[1]
    assert 'action="/compras/proveedores/10/asociar-codigo"' in marcado
    assert 'action="/compras/proveedores/3/asociar-codigo"' not in marcado


def test_ES_OTRO_lo_carga_igual_y_sin_volver_a_preguntar():
    respuesta, puerta = _alta({"nombre": "Frutamax", "codigo_puesto": "N09P39", "es_otro": "1"})

    assert respuesta.status_code == 303
    puerta.assert_called_once_with("N09P39", "Frutamax", pisar_nombre=False)


def test_un_nombre_DISTINTO_no_muestra_el_modal():
    """El control: sin él, un alta que preguntara SIEMPRE pasa el test de arriba."""
    respuesta, puerta = _alta({"nombre": "EJEMPLO Nuevo", "codigo_puesto": "N05P05"})

    assert respuesta.status_code == 303
    assert "modal-fondo" not in respuesta.text
    puerta.assert_called_once()


def test_ASOCIAR_el_codigo_lo_suma_al_proveedor_que_ya_existe():
    with patch("app.main.asociar_codigo_a_proveedor", return_value="FRUTAMAX S.R.L.") as asociar:
        respuesta = cliente.post("/compras/proveedores/3/asociar-codigo",
                                 data={"codigo_puesto": "n09p39"}, follow_redirects=False)

    assert respuesta.status_code == 303
    asociar.assert_called_once_with(3, "N09P39")
    assert "destacado_id=3" in respuesta.headers["location"]


def test_si_la_BASE_rechaza_el_codigo_se_dice_como_400():
    with (
        patch("app.main.asociar_codigo_a_proveedor",
              side_effect=ValueError("El código N09P39 ya es de otro proveedor: no se puede asociar a X.")),
        patch("app.main.listar_proveedores_para_abm", return_value=PROVEEDORES_ABM),
        patch("app.main.listar_tipos_cajon", return_value=[]),
    ):
        respuesta = cliente.post("/compras/proveedores/3/asociar-codigo", data={"codigo_puesto": "N09P39"})

    assert respuesta.status_code == 400
    assert "ya es de otro proveedor" in respuesta.text


def test_el_codigo_REPETIDO_nombra_el_codigo_TIPEADO_y_no_el_principal():
    """Tipeado el 39, decir "el código N09P41 ya es de…" no explica el rebote."""
    with (
        patch("app.main.buscar_proveedor_por_codigo",
              return_value={"id": 3, "codigo_puesto": "N09P41", "nombre": "FRUTAMAX S.R.L.",
                            "activo": True, "por_alternativo": True}),
        patch("app.main.listar_proveedores_para_abm", return_value=PROVEEDORES_ABM),
        patch("app.main.listar_tipos_cajon", return_value=[]),
    ):
        respuesta = cliente.post("/compras/proveedores/nuevo",
                                 data={"nombre": "Frutamax", "codigo_puesto": "N09P39"})

    assert respuesta.status_code == 400
    assert "El código N09P39 ya es de" in respuesta.text
    assert "El código N09P41" not in respuesta.text


# ---------------------------------------------------------- contra la base


@pytest.fixture(scope="module")
def base_real():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: esto no se saltea")
        pytest.skip("sin Postgres local")
    return preparar_base()


@pytest.fixture
def galpon(base_real, monkeypatch):
    """Un proveedor con un puesto principal y uno alternativo, y otro proveedor
    aparte. Los códigos salen de una secuencia para no chocar entre tests."""
    monkeypatch.setenv("DATABASE_URL", base_real)
    import app.db as d

    def sql(consulta, parametros=()):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()

    (n,), = sql("SELECT nextval(pg_get_serial_sequence('articulos','id'))")
    principal, alternativo, ajeno = (f"L{(3 * n + k) % 100:02d}P{(3 * n + k) // 100 % 100:02d}" for k in range(3))
    (articulo,), = sql("INSERT INTO articulos (nombre) VALUES (%s) RETURNING id", (f"EJEMPLO Art {n}",))
    (proveedor,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) RETURNING id",
                        (f"EJEMPLO SRL {n}", principal))
    sql("INSERT INTO proveedores_codigos (proveedor_id, codigo) VALUES (%s, %s)", (proveedor, alternativo))
    (otro,), = sql("INSERT INTO proveedores (nombre, codigo_puesto) VALUES (%s, %s) RETURNING id",
                   (f"EJEMPLO Otro {n}", ajeno))
    return {"d": d, "sql": sql, "articulo": articulo, "proveedor": proveedor, "otro": otro,
            "principal": principal, "alternativo": alternativo, "ajeno": ajeno}


def _compra(g, codigo, proveedor=None):
    g["d"].crear_compra(date.today(), g["articulo"], proveedor or g["proveedor"], 10, 16, 160, None,
                        1000, None, "Clark", None, segunda_por_cajon=None, codigo_llegada=codigo)
    (compra_id,), = g["sql"]("SELECT max(id) FROM compras")
    return compra_id


def _cuantos_proveedores(g):
    (n,), = g["sql"]("SELECT count(*) FROM proveedores")
    return n


def test_una_compra_por_el_codigo_ALTERNATIVO_va_al_MISMO_proveedor_y_NO_le_cambia_el_nombre(galpon):
    g = galpon
    antes = _cuantos_proveedores(g)
    proveedor_id, reactivado = g["d"].obtener_o_crear_proveedor_por_codigo(g["alternativo"], "EJEMPLO Remito 39")

    assert proveedor_id == g["proveedor"]
    assert reactivado is False
    assert _cuantos_proveedores(g) == antes, "no tiene que crear otro proveedor"
    (nombre,), = g["sql"]("SELECT nombre FROM proveedores WHERE id = %s", (g["proveedor"],))
    assert nombre.startswith("EJEMPLO SRL"), "el remito del 39 no renombra a la S.R.L."


def test_por_el_codigo_PRINCIPAL_la_ultima_correccion_SIGUE_mandando(galpon):
    """El control: sin él, un `pisar_nombre` apagado para todos pasa el de arriba."""
    g = galpon
    g["d"].obtener_o_crear_proveedor_por_codigo(g["principal"], "EJEMPLO Nombre Nuevo")
    (nombre,), = g["sql"]("SELECT nombre FROM proveedores WHERE id = %s", (g["proveedor"],))
    assert nombre == "EJEMPLO Nombre Nuevo"


def test_buscar_encuentra_por_los_DOS_codigos_y_dice_por_cual(galpon):
    g = galpon
    por_alt = g["d"].buscar_proveedor_por_codigo(g["alternativo"])
    por_prin = g["d"].buscar_proveedor_por_codigo(g["principal"])
    assert por_alt["id"] == por_prin["id"] == g["proveedor"]
    assert por_alt["codigo_puesto"] == g["principal"]
    assert (por_alt["por_alternativo"], por_prin["por_alternativo"]) == (True, False)
    assert g["d"].buscar_proveedor_por_codigo("L99P99") is None


def test_la_compra_GUARDA_el_codigo_por_el_que_llego(galpon):
    g = galpon
    por_alt = _compra(g, g["alternativo"])
    sin_codigo = _compra(g, None)
    filas = dict(g["sql"]("SELECT id, codigo_llegada FROM compras WHERE id IN (%s, %s)", (por_alt, sin_codigo)))
    assert filas == {por_alt: g["alternativo"], sin_codigo: g["principal"]}


def test_un_codigo_de_OTRO_proveedor_NO_se_guarda_y_la_compra_NO_entra(galpon):
    g = galpon
    (antes,), = g["sql"]("SELECT count(*) FROM compras")
    with pytest.raises(ValueError, match="no es de ese proveedor"):
        _compra(g, g["ajeno"])
    (despues,), = g["sql"]("SELECT count(*) FROM compras")
    assert despues == antes


def test_la_COMANDA_guarda_el_codigo_en_TODOS_sus_renglones(galpon):
    g = galpon
    renglon = {"articulo_id": g["articulo"], "cantidad_cajones": 5, "contenido_por_cajon": 16,
               "cantidad_kilos": 80, "cantidad_fraccion": None, "importe": 1000, "sena": None,
               "tipo_retiro": "Clark", "segunda_por_cajon": None}
    g["d"].crear_compras_de_comanda(date.today(), g["proveedor"], [renglon, dict(renglon)], None, None,
                                    codigo_llegada=g["alternativo"])
    codigos = [c for (c,) in g["sql"](
        "SELECT codigo_llegada FROM compras WHERE proveedor_id = %s ORDER BY id DESC LIMIT 2", (g["proveedor"],))]
    assert codigos == [g["alternativo"], g["alternativo"]]


def test_la_guia_de_RECEPCION_nombra_los_DOS_puestos(galpon):
    """De punta a punta: la consulta de verdad más el agrupado de la pantalla."""
    g = galpon
    _compra(g, g["principal"])
    _compra(g, g["alternativo"])
    compras = [c for c in g["d"].listar_compras_pendientes_recepcion() if c["proveedor_id"] == g["proveedor"]]
    guias = _agrupar_pendientes_por_guia(compras)
    assert len(guias) == 1, "el 41 y el 39 comparten la guía del día"
    assert set(guias[0]["codigos_llegada"]) == {g["principal"], g["alternativo"]}


def test_cambiar_el_proveedor_pone_el_PRINCIPAL_del_nuevo(galpon):
    g = galpon
    compra = _compra(g, g["alternativo"])
    g["d"].cambiar_proveedor_de_compra(compra, g["otro"])
    (codigo,), = g["sql"]("SELECT codigo_llegada FROM compras WHERE id = %s", (compra,))
    assert codigo == g["ajeno"]


def test_ASOCIAR_suma_el_codigo_y_la_BASE_rechaza_uno_que_ya_es_de_otro(galpon):
    g = galpon
    (n,), = g["sql"]("SELECT nextval(pg_get_serial_sequence('articulos','id'))")
    nuevo = f"N{n % 100:02d}P{n // 100 % 100:02d}"

    assert g["d"].asociar_codigo_a_proveedor(g["otro"], nuevo).startswith("EJEMPLO Otro")
    assert g["d"].obtener_o_crear_proveedor_por_codigo(nuevo, "X")[0] == g["otro"]

    with pytest.raises(ValueError, match="ya es de otro proveedor"):
        g["d"].asociar_codigo_a_proveedor(g["otro"], g["principal"])
    with pytest.raises(ValueError, match="ya es de otro proveedor"):
        g["d"].asociar_codigo_a_proveedor(g["otro"], g["alternativo"])


def test_la_lista_para_ELEGIR_trae_los_codigos_alternativos(galpon):
    g = galpon
    fila, = [p for p in g["d"].listar_proveedores() if p["id"] == g["proveedor"]]
    assert fila["codigos_alternativos"] == [g["alternativo"]]
    otro, = [p for p in g["d"].listar_proveedores() if p["id"] == g["otro"]]
    assert otro["codigos_alternativos"] == []


def _dos_puestos(lista):
    """Una copia del fixture de test_app con el SEGUNDO renglón llegado por otro puesto."""
    copia = [dict(c) for c in lista]
    copia[1]["codigo_llegada"] = "N07P39"
    return copia


def test_LOGISTICA_muestra_los_dos_puestos_de_la_guia_y_de_cual_es_cada_renglon():
    """La pantalla de verdad, no el agrupado solo: el que retira mira el título
    grande para saber adónde ir."""
    from tests.test_app import COMPRAS_PENDIENTES_RETIRO_DE_PRUEBA as COMPRAS

    with (
        patch("app.main.listar_compras_pendientes_retiro", return_value=_dos_puestos(COMPRAS)),
        patch("app.main.listar_compras_procesadas_hoy_retiro", return_value=[]),
    ):
        dos = cliente.get("/logistica/retiro/Clark").text.split("</style>")[-1]
    with (
        patch("app.main.listar_compras_pendientes_retiro", return_value=COMPRAS),
        patch("app.main.listar_compras_procesadas_hoy_retiro", return_value=[]),
    ):
        uno = cliente.get("/logistica/retiro/Clark").text.split("</style>")[-1]

    assert '<p class="puesto-nombre">N07P41 · N07P39</p>' in dos
    assert '<p class="puesto-renglon">Puesto N07P39</p>' in dos
    assert '<p class="puesto-renglon">Puesto N07P41</p>' in dos
    # Con un solo puesto es la pantalla de siempre.
    assert '<p class="puesto-nombre">N07P41</p>' in uno
    assert 'class="puesto-renglon"' not in uno


def test_RECEPCION_y_COMPRAS_PENDIENTES_muestran_el_puesto_de_LLEGADA():
    from tests.test_app import COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA as RECEPCION

    recepcion = [dict(c, codigo_llegada="N07P39") for c in RECEPCION]
    with (
        patch("app.main.listar_compras_pendientes_recepcion", return_value=recepcion),
        patch("app.main.listar_compras_procesadas_hoy_recepcion", return_value=[]),
        patch("app.main.listar_marcas_vacio_por_proveedor", return_value={}),
    ):
        pantalla = cliente.get("/deposito/recepcion").text.split("</style>")[-1]
    assert "(N07P39)</h2>" in pantalla

    sin_precio = [{"id": 1, "fecha_operacion": date(2026, 9, 20), "articulo_nombre": "EJEMPLO Uno",
                   "proveedor_nombre": "FRUTAMAX S.R.L.", "proveedor_codigo_puesto": "N09P41",
                   "codigo_llegada": "N09P39", "cantidad_cajones": 5, "contenido_por_cajon": 16,
                   "unidad_compra": "kilo", "estado": "pendiente", "importe": None, "sena": None}]
    with patch("app.main.listar_compras_sin_precio", return_value=sin_precio):
        pendientes = cliente.get("/compras/pendientes")
    assert "FRUTAMAX S.R.L. (N09P39)" in pendientes.text.split("</style>")[-1], pendientes.status_code


# ------------------------------------------- los flujos de DOS pasos llevan el código


def test_el_INGRESO_DIRECTO_lleva_el_codigo_tipeado_del_primer_paso_a_la_compra():
    """El primer paso resuelve el proveedor; los renglones se cargan en otra
    pantalla que solo sabe el id. Sin el código en la URL y en el campo
    escondido, una compra del 39 se guardaría como del 41."""
    from tests.test_app import ARTICULO_KILO_DE_PRUEBA, HOY_DE_PRUEBA, PROVEEDOR_DE_PRUEBA

    with patch("app.main.obtener_o_crear_proveedor_por_codigo", return_value=(200, False)):
        paso_1 = cliente.post("/deposito/ingresar/proveedor",
                              data={"codigo_puesto": "N07P39", "nombre": "Saturno"}, follow_redirects=False)
    assert "codigo=N07P39" in paso_1.headers["location"]

    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=[]),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        # Sin cortar por `</style>`: el modal de "vino armada" trae el suyo al
        # final y el corte se llevaría la pantalla (corolario 50). Un input
        # escondido entero solo puede ser marcado.
        pantalla = cliente.get(paso_1.headers["location"]).text
    assert '<input type="hidden" name="codigo_llegada" value="N07P39">' in pantalla

    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.crear_compra") as crear,
    ):
        paso_2 = cliente.post("/deposito/ingresar", data={
            "proveedor_id": "200", "articulo_id": "5", "cantidad_cajones": "10",
            "contenido_por_cajon": "18", "tipo_retiro": "Clark", "codigo_llegada": "N07P39",
        }, follow_redirects=False)
    assert crear.call_args.kwargs["codigo_llegada"] == "N07P39"
    assert "codigo=N07P39" in paso_2.headers["location"], "el renglón siguiente es del mismo puesto"
    assert "codigo_llegada" not in PROVEEDOR_DE_PRUEBA, "no puede ensuciar el dict que le pasaron"


def test_COMPRAS_NUEVA_lleva_el_codigo_a_los_renglones_que_se_agregan_despues():
    from tests.test_app import ARTICULO_KILO_DE_PRUEBA, HOY_DE_PRUEBA, PROVEEDOR_DE_PRUEBA

    with (
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.listar_articulos", return_value=[]),
        patch("app.main.listar_compras_por_fecha_y_proveedor", return_value=[]),
    ):
        pantalla = cliente.get("/compras/nueva?proveedor_id=200&codigo=N07P39").text
    assert '<input type="hidden" name="codigo_llegada" value="N07P39">' in pantalla

    with (
        patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA),
        patch("app.main.obtener_proveedor", return_value=PROVEEDOR_DE_PRUEBA),
        patch("app.main.obtener_articulo", return_value=ARTICULO_KILO_DE_PRUEBA),
        patch("app.main.crear_compra") as crear,
    ):
        respuesta = cliente.post("/compras/nueva", data={
            "proveedor_id": "200", "articulo_id": "5", "cantidad_cajones": "10",
            "contenido_por_cajon": "18", "importe": "50000", "tipo_retiro": "Clark",
            "codigo_llegada": "N07P39",
        }, follow_redirects=False)
    assert crear.call_args.kwargs["codigo_llegada"] == "N07P39"
    assert respuesta.headers["location"] == "/compras/nueva?proveedor_id=200&codigo=N07P39"
