"""CARTERA DE CHEQUES: LISTADOS GRANDES (dueño, 14/10).

Lionel subió un Excel de 130 cheques y al guardar salió "Too many fields.
Maximum number of fields is 1000": cada cheque manda 12 campos. Acá:
- un listado de 300 cheques se lee, se revisa y se guarda entero;
- el mismo banco escrito de tres formas se avisa UNA vez y se agrega una vez;
- el cliente sale solo por el CUIT del librador si es un CUIT PROPIO (varios
  por cliente); uno de TERCEROS no se asigna y se sugiere el de la última vez;
  al elegir a mano se pregunta si el CUIT es propio;
- "Para todos" cambia los tildados, o todos si no hay ninguno tildado.

EL GALPÓN, con nombres inventados: cliente 1 EJEMPLO Verduleria (sin CUIT
propio), cliente 2 EJEMPLO Día % con DOS CUIT propios (el de Día Argentina,
30685849751, el ejemplo del dueño, y CUIT_DIA_2), bancos EJEMPLO Banco y
EJEMPLO Otro Banco; Galicia NO está.
"""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.cheques import clave_de_banco  # noqa: E402
from core.listado_cheques import cuits_para_preguntar, poner_a_todos, sugerencias  # noqa: E402
from tests.test_administracion_reordenada import _cliente  # noqa: E402
from tests.test_cheques import CUIT_A, CUIT_B, d  # noqa: E402,F401
from tests.test_cheques_listado import _formulario, _leer, _xlsx  # noqa: E402
from tests.test_cheques_pantallas import _sin_estilo, m  # noqa: E402,F401

CUIT_DIA, CUIT_DIA_2 = "30685849751", "30700000008"
CUIT_TERCERO = "20444444445"
TITULOS = ["Nro. Cheque", "Entidad", "Vencimiento", "Monto", "CUIT", "Librador"]
GALICIAS = ("BANCO DE GALICIA", "Galicia", "007 - Banco de Galicia y Buenos Aires S.A.U.")


def _con_dia(d):
    conexion = d.obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute("INSERT INTO clientes (id, nombre) OVERRIDING SYSTEM VALUE VALUES (2, 'EJEMPLO Día %')")
        cursor.execute("INSERT INTO clientes_cuits (cliente_id, cuit) VALUES (2, %s), (2, %s)",
                       (CUIT_DIA, CUIT_DIA_2))
    conexion.commit()
    conexion.close()


def _cuits(d) -> list:
    conexion = d.obtener_conexion()
    with conexion.cursor() as cursor:
        cursor.execute("SELECT cliente_id, cuit FROM clientes_cuits ORDER BY cliente_id, cuit")
        filas = cursor.fetchall()
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


def _con_un_cheque_de_tercero_de_la_verduleria(d):
    """El cheque de un TERCERO (CUIT_TERCERO) que vino de Día y DESPUÉS de la
    Verdulería: la sugerencia es la última (el RIVAL es el de Día)."""
    from tests.test_cheques import _cargar
    _cargar(d, "799", cuit=CUIT_TERCERO, origen="cliente", cliente=2)
    _cargar(d, "800", cuit=CUIT_TERCERO, origen="cliente", cliente=1)


def test_un_cheque_PROPIO_se_asigna_solo_y_el_cliente_puede_tener_DOS_CUIT(m, d):
    _con_dia(d)
    filas = [TITULOS, ["1", "EJEMPLO Banco", "15/11/2026", 100, CUIT_DIA, "DIA ARGENTINA"],
             ["2", "EJEMPLO Banco", "16/11/2026", 200, CUIT_DIA_2, "DIA OTRA RAZON SOCIAL"],
             ["3", "EJEMPLO Banco", "17/11/2026", 300, CUIT_A, "EJEMPLO Día %"]]       # RIVAL: el nombre igual
    pagina = _leer(m, "a.xlsx", _xlsx(filas))
    datos = _formulario(pagina.text)
    assert [(datos[f"origen_{i}"], datos[f"cliente_id_{i}"]) for i in range(3)] == [
        ("cliente", "2"), ("cliente", "2"), ("a_mano", "")]
    assert "data-pregunta-cuit" not in pagina.text and "data-sugerencia" not in pagina.text


def test_un_cheque_de_TERCERO_no_se_asigna_y_se_SUGIERE_el_de_la_ultima_vez(m, d):
    _con_dia(d)
    _con_un_cheque_de_tercero_de_la_verduleria(d)
    filas = [TITULOS, ["1", "EJEMPLO Banco", "15/11/2026", 100, CUIT_TERCERO, "EJEMPLO Tercero SA"],
             ["2", "EJEMPLO Banco", "16/11/2026", 200, CUIT_B, "EJEMPLO Persona"]]       # nunca vino
    pagina = _leer(m, "t.xlsx", _xlsx(filas))
    marcado = _sin_estilo(pagina.text)
    datos = _formulario(pagina.text)
    assert (datos["origen_0"], datos["cliente_id_0"]) == ("a_mano", "")
    assert [(t.strip(), i) for t, i in re.findall(
        r'data-sugerencia>([^<]*)<button type="submit" name="usar_sugerencia" value="(\d+)"', marcado)] == [
        ("La última vez vino de EJEMPLO Verduleria", "0")]
    usada = _postear(m, datos, usar_sugerencia="0")
    nuevos = _formulario(usada.text)
    assert (nuevos["origen_0"], nuevos["cliente_id_0"], nuevos["origen_1"]) == ("cliente", "1", "a_mano")
    assert "data-sugerencia>" not in _sin_estilo(usada.text)
    # Un CUIT que ya vino es de un tercero: no se pregunta si es propio, ni se aprende al guardar.
    assert "data-pregunta-cuit" not in usada.text
    final = _postear(m, nuevos, accion="guardar")
    assert final.status_code == 303
    assert _cuits(d) == [(2, CUIT_DIA), (2, CUIT_DIA_2)]


def test_al_ELEGIR_A_MANO_pregunta_una_vez_por_CUIT_si_es_PROPIO(m, d):
    _con_dia(d)
    filas = [TITULOS] + [[str(i), "EJEMPLO Banco", "15/11/2026", 100 + i, cuit, "EJEMPLO SRL"]
                         for i, cuit in enumerate((CUIT_A, CUIT_A, CUIT_B))]
    datos = _formulario(_leer(m, "p.xlsx", _xlsx(filas)).text)
    # Se elige Día a mano para el 0 y el 2 (tildados); el 1, con el mismo CUIT que el 0, queda.
    elegido = _postear(m, datos, tildado_0="1", tildado_2="1", accion="a_todos", origen_todos="cliente",
                       cliente_todos="2")
    preguntas = re.findall(r'data-pregunta-cuit="(\d+)"><span><strong>\d+</strong> ¿es un CUIT propio de ([^?]*)\?',
                           _sin_estilo(elegido.text))
    assert preguntas == [(CUIT_A, "EJEMPLO Día %"), (CUIT_B, "EJEMPLO Día %")]     # una por CUIT, no por cheque
    # CUIT_B es de un tercero: no se vuelve a preguntar en este listado.
    tercero = _postear(m, _formulario(elegido.text), cuit_tercero=CUIT_B)
    assert re.findall(r'data-pregunta-cuit="(\d+)"', tercero.text) == [CUIT_A]
    revisado = _postear(m, _formulario(tercero.text), accion="revisar")
    assert re.findall(r'data-pregunta-cuit="(\d+)"', revisado.text) == [CUIT_A]
    # CUIT_A sí es propio: queda en el cliente, no se pregunta más, y el 1 (mismo CUIT) pasa solo a Día.
    propio = _postear(m, _formulario(revisado.text), cuit_propio=f"{CUIT_A}:2")
    assert f"El CUIT {CUIT_A} quedó como propio del cliente" in propio.text
    assert "Se asignaron 1 más de este listado." in propio.text
    assert [(_formulario(propio.text)[f"origen_{i}"], _formulario(propio.text)[f"cliente_id_{i}"])
            for i in range(3)] == [("cliente", "2")] * 3
    assert "data-pregunta-cuit" not in propio.text
    final = _postear(m, _formulario(propio.text), accion="guardar")
    assert final.status_code == 303
    assert _cuits(d) == [(2, CUIT_A), (2, CUIT_DIA), (2, CUIT_DIA_2)]               # CUIT_B no
    # La próxima vez el de CUIT_A se asigna solo; el de CUIT_B se sugiere.
    otra = _leer(m, "q.xlsx", _xlsx([TITULOS, ["9", "EJEMPLO Banco", "15/11/2026", 1, CUIT_A, "X"],
                                    ["10", "EJEMPLO Banco", "15/11/2026", 1, CUIT_B, "X"]]))
    nuevos = _formulario(otra.text)
    assert (nuevos["origen_0"], nuevos["cliente_id_0"], nuevos["origen_1"]) == ("cliente", "2", "a_mano")
    assert len(re.findall(r'data-sugerencia>', _sin_estilo(otra.text))) == 1


def test_SUGERENCIAS_y_PREGUNTAS_sin_base():
    propios = {CUIT_DIA: 2}
    ultimos = {CUIT_TERCERO: 1, CUIT_DIA: 2}
    renglones = [{"cuit_librador": CUIT_TERCERO, "origen": "a_mano", "cliente_id": None},
                 {"cuit_librador": CUIT_TERCERO, "origen": "cliente", "cliente_id": 1},   # ya lo tiene
                 {"cuit_librador": CUIT_DIA, "origen": "a_mano", "cliente_id": None},     # propio: no se sugiere
                 {"cuit_librador": CUIT_TERCERO, "origen": "a_mano", "cliente_id": None, "sacar": True}]
    assert sugerencias(renglones, propios, ultimos) == [1, None, None, None]
    elegidos = [{"cuit_librador": CUIT_A, "origen": "cliente", "cliente_id": 1},
                {"cuit_librador": CUIT_A, "origen": "cliente", "cliente_id": 1},
                {"cuit_librador": CUIT_DIA, "origen": "cliente", "cliente_id": 1},          # propio de otro
                {"cuit_librador": CUIT_TERCERO, "origen": "cliente", "cliente_id": 1},      # ya vino
                {"cuit_librador": CUIT_B, "origen": "cliente", "cliente_id": 1},            # dicho tercero
                {"cuit_librador": "20111111111", "origen": "cliente", "cliente_id": 1}]     # CUIT mal
    assert cuits_para_preguntar(elegidos, propios, {CUIT_TERCERO}, {CUIT_B}) == [(CUIT_A, 1)]


def test_la_FICHA_del_cliente_carga_y_saca_sus_CUIT(m, d):
    _con_dia(d)
    cliente = _cliente(m, "gerencia")
    agregado = cliente.post("/clientes/1/cuits", data={"cuit": "30-70000000-8"})
    assert "ya es de EJEMPLO Día %" in agregado.text                       # uno es de un solo cliente
    cliente.post("/clientes/1/cuits", data={"cuit": "20-44444444-5"})
    assert "no es válido" in cliente.post("/clientes/1/cuits", data={"cuit": "20111111111"}).text
    ficha = _sin_estilo(cliente.get("/clientes/1/editar").text)
    assert re.findall(r'<span data-cuit>(\d+)</span>', ficha) == [CUIT_TERCERO]
    cuit_id = re.search(r'action="/clientes/1/cuits/(\d+)/sacar"', ficha).group(1)
    cliente.post(f"/clientes/1/cuits/{cuit_id}/sacar")
    assert _cuits(d) == [(2, CUIT_DIA), (2, CUIT_DIA_2)]


def _sql(nombre) -> str:
    return open(os.path.join(RAIZ, "db", nombre)).read()


def test_las_MIGRACIONES_2_y_3_pasan_el_CUIT_a_la_tabla_y_borran_la_columna_dos_veces(d):
    """La base como estaba antes de clientes_cuit_2 (con la columna vieja de
    clientes_cuit_1 y un CUIT adentro): la 2 lo pasa, la 3 borra la columna, y
    las dos se pueden correr dos veces. Con un CUIT SIN pasar, la 3 frena."""
    conexion = d.obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_sql("clientes_cuit_1.sql"))
            cursor.execute("UPDATE clientes SET cuit = %s WHERE id = 1", (CUIT_TERCERO,))
            cursor.execute(_sql("clientes_cuit_3.sql"))
            frenada = False
        conexion.rollback()
    except Exception as error:                   # el RIVAL: la 3 sin haber corrido la 2
        frenada = "no está en clientes_cuits" in str(error)
        conexion.rollback()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(_sql("clientes_cuit_1.sql"))
            cursor.execute("UPDATE clientes SET cuit = %s WHERE id = 1", (CUIT_TERCERO,))
            for _ in range(2):
                cursor.execute(_sql("clientes_cuit_2.sql"))
            for _ in range(2):
                cursor.execute(_sql("clientes_cuit_3.sql"))
            cursor.execute("SELECT cliente_id, cuit FROM clientes_cuits")
            pasados = cursor.fetchall()
            cursor.execute(_sql("clientes_cuit_3_verificacion.sql"))
            verificacion = cursor.fetchone()
    finally:
        conexion.rollback()                      # no deja nada
        conexion.close()
    assert frenada
    assert pasados == [(1, CUIT_TERCERO)]
    assert verificacion == ("clientes_cuit_3", 0, 0, 1, 1)


def test_PARA_TODOS_cambia_los_TILDADOS_o_todos_si_no_hay_ninguno(m, d):
    filas = [TITULOS] + [[str(i), "EJEMPLO Banco", "15/11/2026", 100 + i, CUIT_A, "EJEMPLO SRL"] for i in range(4)]
    datos = _formulario(_leer(m, "c.xlsx", _xlsx(filas)).text)
    # La planilla no dice el tipo: entran como ECHEQ (dueño, 16/10).
    assert [datos[f"tipo_{i}"] for i in range(4)] == ["echeq"] * 4
    # Tildados el 1 y el 3: solo esos pasan a FÍSICO, de canje y del otro banco.
    tildados = _formulario(_postear(m, datos, tildado_1="1", tildado_3="1", accion="a_todos", tipo_todos="fisico",
                                    origen_todos="canje", banco_todos="EJEMPLO Otro Banco").text)
    assert [(tildados[f"tipo_{i}"], tildados[f"origen_{i}"], tildados[f"banco_{i}"]) for i in range(4)] == [
        ("echeq", "a_mano", "EJEMPLO Banco"), ("fisico", "canje", "EJEMPLO Otro Banco"),
        ("echeq", "a_mano", "EJEMPLO Banco"), ("fisico", "canje", "EJEMPLO Otro Banco")]
    # Sin tildar: a todos; "No cambiar" deja el banco y el origen como estaban.
    todos = _formulario(_postear(m, tildados, accion="a_todos", tipo_todos="echeq").text)
    assert [(todos[f"tipo_{i}"], todos[f"origen_{i}"]) for i in range(4)] == [
        ("echeq", "a_mano"), ("echeq", "canje"), ("echeq", "a_mano"), ("echeq", "canje")]
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



def test_el_TIPO_es_ECHEQ_salvo_que_diga_claramente_FISICO():
    from core.listado_cheques import tipo_de_la_celda
    assert [tipo_de_la_celda(v) for v in (None, "", "ECHEQ", "Cheque electrónico", "Físico", "papel", "CH", "x")] == [
        "echeq", "echeq", "echeq", "echeq", "fisico", "fisico", "echeq", "echeq"]


def test_la_CARGA_A_MANO_arranca_en_ECHEQ(m):
    from tests.test_administracion_reordenada import _cliente
    pagina = _cliente(m, "gerencia").get("/gerencia/cheques/cargar").text
    assert re.search(r'<select name="tipo_0"><option value="echeq" selected>ECHEQ</option>'
                     r'<option value="fisico" >Físico</option></select>', pagina)
