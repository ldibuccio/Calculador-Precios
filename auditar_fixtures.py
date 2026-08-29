"""Busca fixtures que inventan columnas.

El caso que lo motivó: una fixture declaraba "cliente_nombre" en el
return_value de listar_fichas_de_todos_los_clientes, la consulta real
nunca devolvió esa columna, y la pantalla de Guías R tiraba 500 en
producción mientras los tests pasaban en verde.

Compara las claves de cada fixture contra los alias del SELECT de la
función que parchea. Se corre a mano:  python auditar_fixtures.py

LO QUE NO VE, para no confiarse:
  - Funciones que arman el dict en Python (return {"casos": ...}): se
    saltean, porque sus claves no salen de ningún SELECT.
  - Claves que la función AGREGA después de la consulta (stock_vacios le
    pone "stock" a cada fila). Salen como falso positivo.
  - Fixtures construidas con dict(OTRA, clave=valor) o armadas dentro de
    una función: solo mira literales y constantes del módulo.
  - Y al revés: una fixture que declara de MÁS pero que nadie lee es
    inofensiva. Lo que rompe es que el código lea esa clave.

El chequeo más fuerte no es este: es levantar la app contra una base real
con datos y recorrer las pantallas. Eso ejecuta la consulta de verdad
junto al código de verdad, que es la única forma de que las dos mentiras
se encuentren.
"""
import ast, re, sys

FUENTE_DB = open("/home/user/Calculador-Precios/app/db.py").read()
arbol_db = ast.parse(FUENTE_DB)

def columnas_de(fn_nodo):
    """Los alias que devuelve el/los SELECT de una función de db.py."""
    sqls = [n.value for n in ast.walk(fn_nodo)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and re.search(r"\bSELECT\b", n.value, re.I)]
    if not sqls:
        return None
    cols = set()
    for sql in sqls:
        for m in re.finditer(r"\bSELECT\b(.*?)\bFROM\b", sql, re.I | re.S):
            cuerpo = m.group(1)
            cuerpo = re.sub(r"\bDISTINCT\s+ON\s*\([^)]*\)", "", cuerpo, flags=re.I)
            cuerpo = re.sub(r"^\s*\bDISTINCT\b", "", cuerpo, flags=re.I)
            profundidad, actual, partes = 0, "", []
            for ch in cuerpo:
                if ch == "(": profundidad += 1
                elif ch == ")": profundidad -= 1
                if ch == "," and profundidad == 0:
                    partes.append(actual); actual = ""
                else:
                    actual += ch
            partes.append(actual)
            for parte in partes:
                parte = parte.strip()
                if not parte: continue
                alias = re.search(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", parte, re.I)
                if alias:
                    cols.add(alias.group(1).lower()); continue
                simple = re.match(r"^(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)$", parte)
                if simple:
                    cols.add(simple.group(1).lower())
                elif parte == "*":
                    return "ESTRELLA"
    return cols

COLUMNAS = {}
for nodo in arbol_db.body:
    if isinstance(nodo, ast.FunctionDef):
        # Las que arman el dict en Python (return {"casos": ...}) no se
        # pueden auditar contra el SELECT: sus claves no salen de ahí.
        arma_a_mano = any(isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)
                          for n in ast.walk(nodo))
        c = columnas_de(nodo)
        if c and not arma_a_mano: COLUMNAS[nodo.name] = c

hallazgos = []
for archivo in ["tests/test_app.py", "tests/test_db.py", "tests/test_dos_fichas_por_articulo.py",
                "tests/test_exportar_rentabilidad_real.py", "tests/test_precio_por_ficha_invisible.py"]:
    try:
        fuente = open(f"/home/user/Calculador-Precios/{archivo}").read()
    except FileNotFoundError:
        continue
    arbol = ast.parse(fuente)
    # Las constantes del módulo: FICHAS_DE_PRUEBA = [{...}] y compañía.
    constantes = {}
    for n in arbol.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            constantes[n.targets[0].id] = n.value
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
                and nodo.func.id == "patch"):
            continue
        if not (nodo.args and isinstance(nodo.args[0], ast.Constant)):
            continue
        objetivo = nodo.args[0].value
        if not isinstance(objetivo, str):
            continue
        fn = objetivo.rsplit(".", 1)[-1]
        cols = COLUMNAS.get(fn)
        if not cols or cols == "ESTRELLA":
            continue
        for kw in nodo.keywords:
            if kw.arg != "return_value":
                continue
            valor = kw.value
            if isinstance(valor, ast.Name) and valor.id in constantes:
                valor = constantes[valor.id]
            for d in ast.walk(valor):
                if not isinstance(d, ast.Dict):
                    continue
                for k in d.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        if k.value.lower() not in cols:
                            hallazgos.append((archivo, nodo.lineno, fn, k.value))

vistos = set()
for a, l, fn, clave in hallazgos:
    if (fn, clave) in vistos: continue
    vistos.add((fn, clave))
    print(f"{a}:{l}  {fn}()  ->  la fixture declara '{clave}' y la consulta no lo devuelve")
print()
print(f"{len(vistos)} combinaciones (función, clave) sospechosas")
