"""CARTERA DE CHEQUES: LISTADOS GRANDES (dueño, 14/10).

Lionel subió un Excel de 130 cheques y al guardar salió "Too many fields.
Maximum number of fields is 1000": cada cheque manda 12 campos. Acá:
- un listado de 300 cheques se lee, se revisa y se guarda entero;
- el mismo banco escrito de tres formas se avisa UNA vez y se agrega una vez;
- el cliente sale solo por el CUIT del librador, y si se elige a mano el
  cliente aprende el CUIT;
- "Para todos" cambia los tildados, o todos si no hay ninguno tildado.

EL GALPÓN, con nombres inventados: cliente 1 EJEMPLO Verduleria (sin CUIT),
cliente 2 EJEMPLO Día % con el CUIT de Día Argentina (30685849751, el ejemplo
del dueño), bancos EJEMPLO Banco y EJEMPLO Otro Banco; Galicia NO está.
"""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.cheques import clave_de_banco  # noqa: E402
from core.listado_cheques import cuits_para_recordar, poner_a_todos  # noqa: E402
from tests.test_administracion_reordenada import _cliente  # noqa: E402
from tests.test_cheques import CUIT_A, CUIT_B, d  # noqa: E402,F401
from tests.test_cheques_listado import _formulario, _leer, _xlsx  # noqa: E402
from tests.test_cheques_pantallas import _sin_estilo, m  # noqa: E402,F401

CUIT_DIA = "30685849751"
TITULOS = ["Nro. Cheque", "Entidad", "Vencimiento", "Monto", "CUIT", "Librador"]
GALICIAS = ("BANCO DE GALICIA", "Galicia", "007 - Banco de Galicia y Buenos Aires S.A.U.")


def _con_dia(d):
    conexion = d.obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute("INSERT INTO clientes (id, nombre, cuit) OVERRIDING SYSTEM VALUE "
                       "VALUES (2, 'EJEMPLO Día %%', %s)", (CUIT_DIA,))
    conexion.commit()
    conexion.close()


def _cuits(d) -> dict:
    conexion = d.obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute("SELECT id, cuit FROM clientes ORDER BY id")
        filas = dict(cursor.fetchall())
    conexion.close()
    return filas


def _postear(m, datos, **extra):
    return _cliente(m, "gerencia").post("/gerencia/cheques/cargar/listado", data=dict(datos, **extra),
                                        follow_redirects=False)


def _conteo(html) -> str:
    return re.sub(r"<[^>]+>", "", re.search(r'data-conteo>(.*?)</p>', _sin_estilo(html), re.S).group(1))


def test_un_LISTADO_de_300_cheques_se_revisa_y_se_guarda_entero(m, d):
    _con_dia(d)
    # 300 cheques: un tercio de Día (por CUIT), el resto de un librador sin cliente.
    # Galicia escrito de tres formas; algunos en EJEMPLO Banco, que ya está.
    filas = [TITULOS] + [
        [f"{9000 + i}", GALICIAS[i % 3] if i % 4 else "EJEMPLO Banco", "15/11/2026", 1000 + i,
         CUIT_DIA if i % 3 == 0 else CUIT_B, "DIA ARGENTINA S.A." if i % 3 == 0 else "EJEMPLO Persona"]
        for i in range(300)]
    pagina = _leer(m, "grande.xlsx", _xlsx(filas))
    assert pagina.status_code == 200, pagina.text[:300]
    marcado = _sin_estilo(pagina.text)
    assert len(re.findall(r'data-renglon="\d+"', marcado)) == 300
    # Compacto: abiertos solo los que tienen problema, y van primero.
    assert len(re.findall(r'<details open>', marcado)) == 225
    assert re.search(r'data-renglon="(\d+)"', marcado).group(1) == "1"
    total = sum(1000 + i for i in range(300))
    assert _conteo(pagina.text) == f"300 cheques · ${total:,}".replace(",", ".") + " · 75 bien · 225 con problema"
    # Galicia, escrito de tres formas, se avisa UNA vez.
    assert re.findall(r'data-falta-banco><span><strong>([^<]*)</strong> no está en la lista \((\d+) cheques\)',
                      marcado) == [("Galicia", "225")]
    datos = _formulario(pagina.text)
    assert len(datos) > 2 * 1000                 # 9 campos por cheque: el doble del tope de antes
    # El cliente por el CUIT: Día los de Día; el otro, nombre a mano.
    assert {(datos[f"origen_{i}"], datos[f"cliente_id_{i}"]) for i in range(0, 300, 3)} == {("cliente", "2")}
    assert {datos[f"origen_{i}"] for i in range(300) if i % 3} == {"a_mano"}

    agregado = _postear(m, datos, agregar_banco="Galicia")
    assert agregado.status_code == 200, agregado.text[:300]
    assert _conteo(agregado.text) == f"300 cheques · ${total:,}".replace(",", ".") + " · 300 bien"
    assert "data-falta-banco" not in agregado.text and "<details open>" not in agregado.text
    final = _postear(m, _formulario(agregado.text), accion="guardar")
    assert final.status_code == 303 and "300+cheques+cargados" in final.headers["location"]
    cheques = d.buscar_cheques({})
    assert len(cheques) == 300
    assert {c["banco"] for c in cheques} == {"Galicia", "EJEMPLO Banco"}
    assert sum(1 for b in d.listar_bancos() if clave_de_banco(b["nombre"]) == "galicia") == 1
    assert sum(1 for c in cheques if c["cliente_id"] == 2) == 100


def test_el_CLIENTE_elegido_a_mano_APRENDE_el_CUIT_y_la_proxima_se_elige_solo(m, d):
    _con_dia(d)
    filas = [TITULOS, ["1", "EJEMPLO Banco", "15/11/2026", 100, CUIT_A, "EJEMPLO SRL"],
             ["2", "EJEMPLO Banco", "16/11/2026", 200, CUIT_A, "EJEMPLO SRL"]]
    datos = _formulario(_leer(m, "a.xlsx", _xlsx(filas)).text)
    assert (datos["origen_0"], datos["cliente_id_0"]) == ("a_mano", "")
    # Se elige el cliente para todos, sin tildar ninguno.
    cambiado = _postear(m, datos, accion="a_todos", origen_todos="cliente", cliente_todos="1")
    assert "Se cambiaron 2 cheques." in cambiado.text
    final = _postear(m, _formulario(cambiado.text), accion="guardar")
    assert final.status_code == 303
    assert "EJEMPLO+Verduleria+qued%C3%B3+con+el+CUIT+" + CUIT_A in final.headers["location"]
    assert _cuits(d) == {1: CUIT_A, 2: CUIT_DIA}
    otra = _formulario(_leer(m, "b.xlsx", _xlsx([TITULOS, ["3", "EJEMPLO Banco", "17/11/2026", 300, CUIT_A,
                                                            "Otro nombre cualquiera"]])).text)
    assert (otra["origen_0"], otra["cliente_id_0"]) == ("cliente", "1")


def test_el_CUIT_no_se_aprende_si_es_de_otro_o_si_el_cliente_trae_DOS():
    clientes = [{"id": 1, "cuit": None}, {"id": 2, "cuit": CUIT_DIA}, {"id": 3, "cuit": None},
                {"id": 4, "cuit": CUIT_B}]
    guardados = [{"origen": "cliente", "cliente_id": 1, "cuit_librador": CUIT_A},
                 {"origen": "cliente", "cliente_id": 1, "cuit_librador": CUIT_A},
                 {"origen": "cliente", "cliente_id": 3, "cuit_librador": CUIT_DIA},     # ya es de Día
                 {"origen": "cliente", "cliente_id": 4, "cuit_librador": CUIT_A},      # ya tiene otro
                 {"origen": "a_mano", "cliente_id": None, "cuit_librador": CUIT_B}]
    assert cuits_para_recordar(guardados, clientes) == {1: CUIT_A}
    dos = guardados[:1] + [{"origen": "cliente", "cliente_id": 1, "cuit_librador": CUIT_B}]
    assert cuits_para_recordar(dos, [{"id": 1, "cuit": None}]) == {}             # dos CUIT: no se adivina


def test_PARA_TODOS_cambia_los_TILDADOS_o_todos_si_no_hay_ninguno(m, d):
    filas = [TITULOS] + [[str(i), "EJEMPLO Banco", "15/11/2026", 100 + i, CUIT_A, "EJEMPLO SRL"] for i in range(4)]
    datos = _formulario(_leer(m, "c.xlsx", _xlsx(filas)).text)
    # Tildados el 1 y el 3: solo esos pasan a ECHEQ, de canje y del otro banco.
    tildados = _formulario(_postear(m, datos, tildado_1="1", tildado_3="1", accion="a_todos", tipo_todos="echeq",
                                    origen_todos="canje", banco_todos="EJEMPLO Otro Banco").text)
    assert [(tildados[f"tipo_{i}"], tildados[f"origen_{i}"], tildados[f"banco_{i}"]) for i in range(4)] == [
        ("fisico", "a_mano", "EJEMPLO Banco"), ("echeq", "canje", "EJEMPLO Otro Banco"),
        ("fisico", "a_mano", "EJEMPLO Banco"), ("echeq", "canje", "EJEMPLO Otro Banco")]
    # Sin tildar: a todos; "No cambiar" deja el banco y el origen como estaban.
    todos = _formulario(_postear(m, tildados, accion="a_todos", tipo_todos="fisico").text)
    assert [(todos[f"tipo_{i}"], todos[f"origen_{i}"]) for i in range(4)] == [
        ("fisico", "a_mano"), ("fisico", "canje"), ("fisico", "a_mano"), ("fisico", "canje")]
    # Sacar los tildados: el 0 y el 2 quedan afuera y no cuentan.
    sacados = _postear(m, todos, tildado_0="1", tildado_2="1", accion="sacar_tildados")
    assert _conteo(sacados.text) == "2 cheques · $204 · 2 bien"
    final = _postear(m, _formulario(sacados.text) | {"sacar_0": "1", "sacar_2": "1"}, accion="guardar")
    assert final.status_code == 303
    assert sorted(c["numero"] for c in d.buscar_cheques({})) == ["1", "3"]


def test_PARA_TODOS_elegir_de_quien_pone_los_tres_datos_juntos():
    renglones = [{"origen": "cliente", "cliente_id": 5, "nombre_a_mano": "", "tipo": "fisico", "banco": "X"},
                 {"origen": "a_mano", "cliente_id": None, "nombre_a_mano": "Pepe", "tipo": "fisico", "banco": "X",
                  "sacar": True}]
    assert poner_a_todos(renglones, {"origen": "a_mano", "nombre_a_mano": " Juan ", "cliente_id": 9}) == 1
    assert renglones[0] == {"origen": "a_mano", "cliente_id": None, "nombre_a_mano": "Juan", "tipo": "fisico",
                            "banco": "X"}
    assert renglones[1]["nombre_a_mano"] == "Pepe"                                # el sacado no se toca


def test_los_BANCOS_iguales_con_otro_nombre_y_los_que_NO_son_el_mismo():
    assert {clave_de_banco(n) for n in GALICIAS + ("Banco de Galicia",)} == {"galicia"}
    assert clave_de_banco("Galicia Más") != clave_de_banco("Galicia")
    assert clave_de_banco("Banco de la Nación Argentina") == clave_de_banco("NACION")
    assert clave_de_banco("Banco de la Provincia de Buenos Aires") != clave_de_banco("Banco Ciudad de Buenos Aires")


def test_el_MISMO_banco_con_otro_nombre_no_se_duplica_al_guardar(d):
    d.agregar_banco("Galicia")
    assert d.agregar_banco("BANCO DE GALICIA Y BUENOS AIRES S.A.U.") == d.agregar_banco("Galicia")
    assert d.agregar_banco("Galicia Más") != d.agregar_banco("Galicia")
    assert sorted(b["nombre"] for b in d.listar_bancos()) == [
        "EJEMPLO Banco", "EJEMPLO Otro Banco", "Galicia", "Galicia Más"]


def test_CONFIRMAR_ENDOSOS_con_mas_de_1000_campos_tambien_entra(m, d):
    """La otra pantalla de muchos renglones: 100 cheques de endosos son 1300 campos."""
    datos = {"cantidad": "100", "accion": "confirmar"}
    for i in range(100):
        datos.update({f"{campo}_{i}": "" for campo in ("foto", "numero", "fecha_pago", "importe", "emisor",
                                                        "cheque_id", "proveedor_cuit", "proveedor_nombre",
                                                        "proveedor_id", "cuenta_deposito", "concepto_id", "fecha")})
        datos[f"sacar_{i}"] = "1"
    assert len(datos) > 1000
    final = _cliente(m, "gerencia").post("/gerencia/cheques/aplicar/endosos/confirmar", data=datos,
                                         follow_redirects=False)
    assert final.status_code == 303 and "0+cheques+aplicados" in final.headers["location"]
