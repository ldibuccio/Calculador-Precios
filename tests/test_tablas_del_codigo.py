"""Toda tabla que el código consulta está en db/esquema_completo.sql (28/09).

v1010 le agregó al borrado de compras una consulta a `recepciones`, una tabla
que existía en Frutamax y en el esquema del repo pero NO en Palmala. Ahí
cualquier borrado de compra revienta, y la suite y el humo no pueden verlo:
corren contra el esquema del repo, que la tenía.

Este test no lo habría atajado solo —la tabla estaba en el esquema—, pero
cierra la mitad que depende del repo: el código no puede nombrar una tabla que
una base nueva no tiene. La otra mitad, que el esquema sea igual a las bases,
la contesta la consulta de huellas (db/comparar_esquema.sql), corrida en las
dos.
"""
import io
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# En POSICIÓN DE TABLA y no la palabra suelta (corolario 59): la prosa nombra
# tablas viejas todo el tiempo para explicar por qué no se usan.
EN_POSICION = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-z_][a-z0-9_]*)\b")
CREA = re.compile(r"^create table (?:if not exists )?([a-z_][a-z0-9_]*)", re.M | re.I)

# Palabras que el regex toma por tabla y no lo son, cada una con su razón.
NO_SON_TABLAS = {
    "storage": "storage.objects: el esquema de Supabase, no el nuestro",
    "unnest": "FROM unnest(...): una función",
    "generate_series": "FROM generate_series(...): una función",
    "jsonb_array_elements": "FROM jsonb_array_elements(...): una función",
    "jsonb_each": "FROM jsonb_each(...): una función",
    "pg_constraint": "catálogo de Postgres",
    "information_schema": "catálogo de Postgres",
}


# Un CTE se nombra igual que una tabla: `WITH vigentes AS (...) ... FROM
# vigentes`. Se juntan de TODO el código y no de la misma cadena, porque
# varias consultas se arman pegando fragmentos.
CTE = re.compile(r"\b([a-z_][a-z0-9_]*)\s+AS\s+(?:NOT\s+)?(?:MATERIALIZED\s+)?\(", re.I)
# Y los alias: el de una subconsulta, `FROM (SELECT ...) c`, y el de una
# tabla, `FROM pedidos_renglones viejo`, que el regex de arriba toma por tabla
# cuando la consulta sigue con una subconsulta que lo nombra.
SUBCONSULTA = re.compile(r"\)\s+(?:AS\s+)?([a-z_][a-z0-9_]*)\b")
ALIAS = re.compile(r"\b(?:FROM|JOIN)\s+[a-z_][a-z0-9_]*\s+(?:AS\s+)?([a-z_][a-z0-9_]*)\b")


def _nombradas_por_el_codigo():
    import ast
    nombradas = {}
    ctes = set()
    for carpeta in ("app", "core"):
        for nombre in os.listdir(os.path.join(RAIZ, carpeta)):
            if not nombre.endswith(".py"):
                continue
            ruta = os.path.join(carpeta, nombre)
            arbol = ast.parse(io.open(os.path.join(RAIZ, ruta), encoding="utf-8").read())
            # Los docstrings son prosa: nombran tablas para explicarlas.
            docstrings = {id(n.body[0].value) for n in ast.walk(arbol)
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))
                          and n.body and isinstance(n.body[0], ast.Expr)
                          and isinstance(n.body[0].value, ast.Constant)}
            for nodo in ast.walk(arbol):
                if id(nodo) in docstrings:
                    continue
                if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                    texto = nodo.value
                elif isinstance(nodo, ast.JoinedStr):
                    texto = "".join(v.value for v in nodo.values if isinstance(v, ast.Constant))
                else:
                    continue
                # Solo lo que parece SQL: una frase como "salió from the..."
                # no es una consulta.
                if not re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", texto):
                    continue
                texto = re.sub(r"--[^\n]*", "", texto)
                ctes |= {c.lower() for c in CTE.findall(texto)}
                ctes |= {c.lower() for c in SUBCONSULTA.findall(texto)}
                ctes |= {c.lower() for c in ALIAS.findall(texto)}
                for tabla in EN_POSICION.findall(texto):
                    nombradas.setdefault(tabla, f"{ruta}:{nodo.lineno}")
    return {t: donde for t, donde in nombradas.items() if t not in ctes}


def test_TODA_tabla_que_el_codigo_consulta_esta_en_el_esquema_completo():
    esquema = io.open(os.path.join(RAIZ, "db", "esquema_completo.sql"), encoding="utf-8").read()
    tablas = {t.lower() for t in CREA.findall(esquema)}
    nombradas = _nombradas_por_el_codigo()
    assert len(nombradas) > 30, "el barrido no encontró consultas: no mira lo que dice"
    faltan = {t: donde for t, donde in nombradas.items()
              if t not in tablas and t not in NO_SON_TABLAS}
    assert not faltan, f"el código consulta tablas que una base nueva no tiene: {faltan}"
