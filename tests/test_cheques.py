"""CARTERA DE CHEQUES (dueño, 13/10), contra Postgres.

Los frenos son de la base (db/cheques_1..5) y el código los traduce. El
estado de cada cheque lo dice la vista `cheques_con_estado`; las fechas se
plantan relativas a HOY de la base (la vista lee la fecha de Argentina), así
que cada caso cae siempre del mismo lado de su borde.

EL GALPÓN, con nombres inventados:
  cliente 1 EJEMPLO Verdulería, proveedor 1 EJEMPLO Puesto, banco 1 EJEMPLO Banco.
"""
import os
import sys
from datetime import date, timedelta

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.cheques import cheques_leidos, resumen_de_cheques  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into clientes (id, nombre) overriding system value values (1, 'EJEMPLO Verduleria');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJEMPLO Puesto', 'N01P01');
insert into bancos (id, nombre) overriding system value values (1, 'EJEMPLO Banco'), (2, 'EJEMPLO Otro Banco');
-- Como producción: el próximo banco que se agregue no choca con los sembrados.
select setval(pg_get_serial_sequence('bancos', 'id'), 2);
"""
CUIT_A, CUIT_B = "20111111112", "27222222228"   # con el dígito verificador bien


@pytest.fixture
def d(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    monkeypatch.setenv("DATABASE_URL", url)
    import app.db as modulo
    return modulo


def _hoy(d) -> date:
    conexion = d.obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date")
            return cursor.fetchone()[0]
    finally:
        conexion.close()


def _cargar(d, numero="12345", *, banco=1, cuit=CUIT_A, pago=None, importe=1000.0, origen="cliente",
            cliente=1, nombre=None, fotos=()):
    hoy = _hoy(d)
    return d.cargar_cheque(numero=numero, banco_id=banco, tipo="fisico", fecha_carga=hoy - timedelta(days=40),
                           fecha_pago=pago if pago is not None else hoy + timedelta(days=10), importe=importe,
                           origen=origen, cliente_id=cliente if origen == "cliente" else None,
                           nombre_a_mano=nombre, cuit_librador=cuit, fotos=list(fotos))


# --- LOS REPETIDOS: banco + número + CUIT del librador (dueño, 13/10) ---------

def test_REPETIDOS_dos_libradores_distintos_con_el_mismo_banco_y_numero_ENTRAN(d):
    primero = _cargar(d, "12345", cuit=CUIT_A)
    segundo = _cargar(d, "12345", cuit=CUIT_B)
    assert primero != segundo
    assert {c["cuit_librador"] for c in d.buscar_cheques({"numero": "12345"})} == {CUIT_A, CUIT_B}


def test_REPETIDOS_el_mismo_CUIT_con_el_mismo_banco_y_numero_FRENA(d):
    _cargar(d, "12345", cuit=CUIT_A)
    with pytest.raises(d.ChequeNoSePuede, match="ya está cargado"):
        _cargar(d, "00012345", cuit=CUIT_A)              # con ceros adelante es el mismo número
    # El rival: mismo número y CUIT en OTRO banco sí entra.
    _cargar(d, "12345", banco=2, cuit=CUIT_A)
    assert len(d.buscar_cheques({"numero": "12345"})) == 2


# --- DE QUIÉN ES -------------------------------------------------------------

def test_DE_QUIEN_cliente_nombre_a_mano_o_canje_y_nada_a_medias(d):
    _cargar(d, "1")
    _cargar(d, "2", origen="a_mano", nombre="EJEMPLO Persona")
    _cargar(d, "3", origen="canje")
    assert [c["de_quien"] for c in d.buscar_cheques({})] == ["EJEMPLO Verduleria", "EJEMPLO Persona", "Canje"]
    with pytest.raises(d.ChequeNoSePuede, match="Decí de quién"):
        _cargar(d, "4", origen="a_mano", nombre="  ")


# --- ESTADOS, SALIDAS, RECHAZO Y RECLAMO --------------------------------------

def test_los_ESTADOS_los_dice_la_vista(d):
    hoy = _hoy(d)
    en_cartera = _cargar(d, "1", pago=hoy + timedelta(days=3))
    por_vencer = _cargar(d, "2", pago=hoy - timedelta(days=23))
    no_rojo = _cargar(d, "3", pago=hoy - timedelta(days=22))         # el borde del rojo
    vencido = _cargar(d, "4", pago=hoy - timedelta(days=30))
    acreditado = _cargar(d, "5", pago=hoy - timedelta(days=1))
    depositado = _cargar(d, "6", pago=hoy)                            # se acredita mañana
    tarde = _cargar(d, "7", pago=hoy - timedelta(days=5))            # depositado hoy, después del pago
    entregado = _cargar(d, "8")
    d.aplicar_cheque(acreditado, fecha=hoy - timedelta(days=2), concepto_id=3, proveedor_id=None, foto_ruta=None)
    d.aplicar_cheque(depositado, fecha=hoy, concepto_id=3, proveedor_id=None, foto_ruta=None)
    d.aplicar_cheque(tarde, fecha=hoy, concepto_id=3, proveedor_id=None, foto_ruta=None)
    d.aplicar_cheque(entregado, fecha=hoy, concepto_id=1, proveedor_id=1, foto_ruta=None)
    estados = {c["id"]: (c["estado"], c["en_rojo_por_vencer"]) for c in d.buscar_cheques({})}
    assert estados == {en_cartera: ("en_cartera", False), por_vencer: ("en_cartera", True),
                       no_rojo: ("en_cartera", False), vencido: ("vencido", True),
                       acreditado: ("acreditado", False), depositado: ("depositado", False),
                       tarde: ("depositado", False), entregado: ("entregado", False)}
    assert d.obtener_cheque(tarde)["acreditado_el"] == hoy + timedelta(days=1)


def test_APLICAR_los_frenos_de_la_base_traducidos(d):
    hoy = _hoy(d)
    cheque = _cargar(d, "1")
    with pytest.raises(d.ChequeNoSePuede, match="a qué proveedor"):
        d.aplicar_cheque(cheque, fecha=hoy, concepto_id=1, proveedor_id=None, foto_ruta=None)
    with pytest.raises(d.ChequeNoSePuede, match="anterior a la fecha de carga"):
        d.aplicar_cheque(cheque, fecha=hoy - timedelta(days=41), concepto_id=3, proveedor_id=None, foto_ruta=None)
    d.aplicar_cheque(cheque, fecha=hoy, concepto_id=2, proveedor_id=None, foto_ruta=None)    # canje: contra nada
    with pytest.raises(d.ChequeNoSePuede, match="ya se aplicó"):
        d.aplicar_cheque(cheque, fecha=hoy, concepto_id=3, proveedor_id=None, foto_ruta=None)


def test_RECHAZO_desde_cualquier_estado_y_el_reclamo_se_cierra_a_mano(d):
    hoy = _hoy(d)
    entregado = _cargar(d, "1")
    d.aplicar_cheque(entregado, fecha=hoy, concepto_id=1, proveedor_id=1, foto_ruta=None)
    d.rechazar_cheque(entregado, fecha=hoy, motivo="Sin fondos")
    assert d.obtener_cheque(entregado)["estado"] == "rechazado"
    with pytest.raises(d.ChequeNoSePuede, match="antes de la fecha del rechazo"):
        d.resolver_reclamo_de_cheque(entregado, fecha=hoy - timedelta(days=1), resolucion="Pagó")
    d.resolver_reclamo_de_cheque(entregado, fecha=hoy, resolucion="Pagó en efectivo")
    cheque = d.obtener_cheque(entregado)
    assert (cheque["estado"], cheque["resolucion"]) == ("reclamo_resuelto", "Pagó en efectivo")
    with pytest.raises(d.ChequeNoSePuede, match="no tiene un reclamo pendiente"):
        d.resolver_reclamo_de_cheque(entregado, fecha=hoy, resolucion="Otra vez")
    # Uno en cartera rechazado ya no se aplica.
    en_cartera = _cargar(d, "2")
    d.rechazar_cheque(en_cartera, fecha=hoy, motivo="Firma")
    with pytest.raises(d.ChequeNoSePuede, match="está rechazado"):
        d.aplicar_cheque(en_cartera, fecha=hoy, concepto_id=3, proveedor_id=None, foto_ruta=None)


def test_CORREGIR_deja_historial_y_solo_en_cartera(d):
    hoy = _hoy(d)
    cheque = _cargar(d, "1", importe=1000.0, fotos=[("frente", "cheques/1-frente.jpg")])
    datos = d.obtener_cheque(cheque)
    nuevos = {"numero": "1", "banco": 2, "tipo": "fisico", "fecha_carga": datos["fecha_carga"],
              "fecha_pago": datos["fecha_pago"], "importe": 1500.0, "origen": "cliente", "cliente": 1,
              "nombre_a_mano": None, "cuit_librador": CUIT_A}
    assert d.corregir_cheque(cheque, nuevos) == 2
    ficha = d.obtener_cheque(cheque)
    assert (ficha["banco"], float(ficha["importe"])) == ("EJEMPLO Otro Banco", 1500.0)
    assert sorted((h["campo"], h["antes"], h["despues"]) for h in ficha["historial"] if h["que"] == "correccion") \
        == [("banco", "EJEMPLO Banco", "EJEMPLO Otro Banco"), ("importe", "1000.00", "1500.00")]
    assert {h["que"] for h in ficha["historial"]} == {"carga", "foto", "correccion"}
    assert all(h["sector"] == "gerencia" for h in ficha["historial"])
    with pytest.raises(d.ChequeNoSePuede, match="No cambió nada"):
        d.corregir_cheque(cheque, dict(nuevos, banco=2, importe=1500.0))
    d.aplicar_cheque(cheque, fecha=hoy, concepto_id=3, proveedor_id=None, foto_ruta=None)
    with pytest.raises(d.ChequeNoSePuede, match="ya no está en cartera"):
        d.corregir_cheque(cheque, dict(nuevos, importe=2000.0))


# --- LOS FILTROS Y EL RESUMEN ----------------------------------------------------

def test_los_FILTROS_se_combinan_y_EN_CARTERA_son_los_no_aplicados(d):
    hoy = _hoy(d)
    uno = _cargar(d, "1", pago=hoy + timedelta(days=2))
    dos = _cargar(d, "2", banco=2, pago=hoy + timedelta(days=20))
    tres = _cargar(d, "3", pago=hoy - timedelta(days=31))                         # vencido: sigue en cartera
    cuatro = _cargar(d, "4", origen="a_mano", nombre="EJEMPLO Persona", pago=hoy + timedelta(days=5))
    d.aplicar_cheque(cuatro, fecha=hoy, concepto_id=1, proveedor_id=1, foto_ruta=None)
    ids = lambda filtros, **k: [c["id"] for c in d.buscar_cheques(filtros, **k)]  # noqa: E731
    assert ids({}, solo_en_cartera=True) == [tres, uno, dos]
    assert ids({"banco_id": 1, "pago_desde": hoy}) == [uno, cuatro]
    assert ids({"banco_id": 1, "pago_desde": hoy, "estado": "entregado"}) == [cuatro]
    assert ids({"proveedor_id": 1}) == [cuatro]
    assert ids({"de_quien": "persona"}) == [cuatro]
    assert ids({"cliente_id": 1, "pago_hasta": hoy}) == [tres]


def test_el_RESUMEN_de_arriba_y_del_panel(d):
    hoy = _hoy(d)
    _cargar(d, "1", importe=100.0, pago=hoy)                                      # entra hoy
    _cargar(d, "2", importe=200.0, pago=hoy + timedelta(days=7))                  # entra el día 7 (borde)
    _cargar(d, "3", importe=400.0, pago=hoy + timedelta(days=8))                  # fuera de los 7
    _cargar(d, "4", importe=800.0, pago=hoy - timedelta(days=25))                 # por vencer
    _cargar(d, "5", importe=1600.0, pago=hoy - timedelta(days=30))                # vencido
    deposito = _cargar(d, "6", importe=3200.0, pago=hoy + timedelta(days=1))     # aplicado: no está en cartera
    d.aplicar_cheque(deposito, fecha=hoy, concepto_id=3, proveedor_id=None, foto_ruta=None)
    rechazado = _cargar(d, "7", importe=6400.0)
    d.rechazar_cheque(rechazado, fecha=hoy, motivo="Sin fondos")
    resumen = resumen_de_cheques(d.todos_los_cheques_para_el_resumen(), hoy)
    assert (resumen["en_cartera"], resumen["cantidad_en_cartera"]) == (3100.0, 5)
    assert (resumen["entran_7_dias"], resumen["cantidad_entran"]) == (300.0, 2)
    assert (resumen["por_vencer"], resumen["vencidos"], resumen["rechazados"], resumen["en_rojo"]) == (1, 1, 1, 3)


# --- LO LEÍDO DE UNA FOTO (sin base) ------------------------------------------

def test_LO_LEIDO_el_banco_es_el_de_la_lista_solo_si_es_IGUAL_y_el_CUIT_solo_si_son_11():
    bancos = [{"nombre": "EJEMPLO Banco"}, {"nombre": "EJEMPLO Otro Banco"}, {"nombre": "Galicia Más"},
              {"nombre": "Galicia"}]
    leidos = cheques_leidos({"cheques": [
        {"numero": " 0042 ", "banco": "Banco EJEMPLO Otro Banco", "cuit_librador": "20-11111111-1", "importe": 10.5},
        {"numero": "43", "banco": "BANCO DE GALICIA Y BS AS", "cuit_librador": "2011", "tipo": "echeq"},
        {"numero": "44", "banco": "Banco Inventado", "importe": None},
        # Igual sin "Banco": "Galicia", y no "Galicia Más", que lo contiene.
        {"numero": "45", "banco": "Banco Galicia", "tipo": "fisico"},
    ]}, bancos)
    # ECHEQ salvo que la lectura diga que es FÍSICO (dueño, 16/10).
    assert [(c["numero"], c["banco"], c["cuit_librador"], c["importe"], c["tipo"]) for c in leidos] == [
        ("0042", "EJEMPLO Otro Banco", "20111111111", "10.5", "echeq"),
        ("43", "BANCO DE GALICIA Y BS AS", "", "", "echeq"),           # no es igual: queda como se leyó
        ("44", "Banco Inventado", "", "", "echeq"),
        ("45", "Galicia", "", "", "fisico")]


# --- JUNTAR DOS PROVEEDORES (13/10) ------------------------------------------

def test_JUNTAR_proveedores_mueve_los_cheques_entregados_al_que_se_va(d):
    hoy = _hoy(d)
    conexion = d.obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute("insert into proveedores (id, nombre, codigo_puesto) overriding system value "
                       "values (2, 'EJEMPLO Puesto Repetido', 'N01P02')")
    conexion.commit()
    conexion.close()
    cheque, rival = _cargar(d, "1"), _cargar(d, "2")
    d.aplicar_cheque(cheque, fecha=hoy, concepto_id=1, proveedor_id=2, foto_ruta=None)
    d.aplicar_cheque(rival, fecha=hoy, concepto_id=1, proveedor_id=1, foto_ruta=None)
    # Un cheque entregado y DESPUÉS rechazado también se mueve (cheques_2): el
    # freno del rechazo es para que no salga, no para reescribir su proveedor.
    d.rechazar_cheque(cheque, fecha=hoy, motivo="Sin fondos")
    d.juntar_proveedores(1, 2)
    assert {c["id"]: c["proveedor_id"] for c in d.buscar_cheques({})} == {cheque: 1, rival: 1}
