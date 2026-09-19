"""Abre TODAS las pantallas contra una base REAL, sin un solo mock.

POR QUÉ EXISTE, y es de las dos caídas del 19/09: la suite entera mockea la
base, así que **ninguna consulta de este sistema se le manda nunca a un
Postgres durante los tests**. Un SQL que no parsea sale 2749 en verde y tira
la pantalla en producción.

Lo que agarra, medido con los dos casos reales de ese día:

  · `column v.fecha_operacion does not exist` — el CTE no exponía la columna.
    El test de TEXTO del SQL (corolario 65) estaba puesto, afirmaba la lista
    del SELECT, y NO PUEDE ver esto: un assert de texto verifica la forma de
    la consulta, nunca su validez contra el esquema.
  · el desempaque de tres valores sobre una tupla de dos — ahí el fixture
    devolvía una forma que producción no devuelve nunca.

Lo que NO agarra, y hay que decirlo o se lee como más de lo que es: una
pantalla que abre con la base VACÍA ejercita los caminos del caso vacío. Un
`IndexError` sobre la fila 0 de un resultado que acá viene sin filas no se
ve. Por eso `siembra()` planta un caso mínimo de cada cosa.

Y LA PRIMERA VERSIÓN DE ESTO NO AGARRABA EL BUG PARA EL QUE SE ESCRIBIÓ.
Abría las 113 rutas sin parámetros y daba `ROTAS 0` con el bug puesto:
`/administracion/stock/remanente/porcion` pide `articulo_id`, así que
contestaba 422 —routing OK, handler nunca corrido— y la consulta rota no se
tocaba. El canario con el bug real dio NO MORDIÓ, y el dato que lo decía
estaba impreso en la misma línea del resumen: `422 4`. Corolario 53 y 19
juntos, adentro de la herramienta escrita contra ellos.

Por eso el informe cuenta `ABIERTAS` —las que dieron 200— y NO "no rotas", y
por eso la corrida FALLA si ese número baja del piso: un humo que mira menos
pantallas cada mes se ve igual de verde que uno que las mira todas.
"""
import ast
import io
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DE_HUMO = "humo_calculador"

# Las que NO se abren, con la razón al lado. La lista se compara contra el
# conjunto ENCONTRADO (corolario 60), así que falla en las dos direcciones:
# cuando aparece una ruta nueva que nadie decidió, y cuando una de acá deja
# de existir y la excepción queda protegiendo algo que ya no pasa.
NO_SE_ABREN = {
    "/salud/db": "es el healthcheck: contesta sobre la base, no es pantalla",
    # Las que SIRVEN UN ARCHIVO del Storage de Supabase. No hay bucket local,
    # así que acá dan 404 hagamos lo que hagamos — y un 404 sembrado a la
    # fuerza sería peor: mediría que el 404 funciona.
    "/compras/{compra_id}/foto": "sirve la foto desde el Storage, no hay bucket local",
    "/compras/{compra_id}/fotos/{foto_id}/ver": "idem",
    "/compras/vacios/devolucion/{devolucion_id}/foto": "idem",
    "/deposito/pedido/{pedido_id}/fotos/{foto_id}/ver": "idem",
    "/deposito/recepcion/{compra_id}/foto-balanza/ver": "idem",
    # El mail necesita una casilla configurada con su credencial, que por
    # regla del proyecto no vive en la base.
    "/deposito/pedido/mails/{mail_id}/revisar": "necesita una casilla con credencial",
}

# Las que NO dan 200 y está BIEN que no den 200, con su estado al lado. Se
# enumeran en vez de aflojar el umbral a "cualquier cosa que no sea 500":
# un `!= 500` deja pasar el 422 de una pantalla que nunca corrió su consulta,
# que es exactamente el agujero que tenía la primera versión de esto.
ESTADO_ESPERADO = {
    "/administracion/clave": 401,   # dibuja la pantalla de la clave, y 401 es su estado
    "/compras/clave": 401,
}


def rutas_get():
    """TODAS las rutas GET, con el id de la URL sustituido por la fila sembrada.

    Las de `{articulo_id}` entran a propósito: el bug de las 11h del 19/09
    —desempacar tres valores de una tupla de dos— vive en
    `/administracion/stock/sistema/{articulo_id}`, y con las rutas sin
    parámetro solamente el canario de ese bug daba NO MORDIÓ. 21 de 135 rutas
    quedaban afuera, y la pantalla que se había caído era una de ellas.
    """
    arbol = ast.parse(io.open(os.path.join(RAIZ, "app/main.py"), encoding="utf-8").read())
    rutas = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in nodo.decorator_list:
            if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "get" and dec.args
                    and isinstance(dec.args[0], ast.Constant)):
                rutas.append(dec.args[0].value)
    return sorted(set(rutas))


def concretar(ruta):
    """Sustituye los `{x}` de la URL. Devuelve None si no se sabe con qué."""
    import re
    partes = re.findall(r"\{([^}]+)\}", ruta)
    concreta = ruta
    for nombre in partes:
        valor = _valor_para(nombre)
        if valor is None:
            return None
        concreta = concreta.replace("{" + nombre + "}", valor)
    return concreta


def hay_postgres():
    try:
        return subprocess.run(["pg_isready"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def _psql(sql=None, archivo=None, base="postgres"):
    orden = f"psql -q -v ON_ERROR_STOP=1 -d {base} "
    orden += f"-f {archivo}" if archivo else f"-c {sql!r}"
    return subprocess.run(["su", "postgres", "-c", orden], capture_output=True, text=True)


def preparar_base():
    """Crea la base de humo con `db/esquema_completo.sql`, que es el esquema REAL.

    Nunca un `create table` escrito para la ocasión: un esquema propio
    confirma que la consulta es consistente CONSIGO MISMA y no con la base.
    """
    _psql(sql=f"DROP DATABASE IF EXISTS {BASE_DE_HUMO}")
    _psql(sql=f"CREATE DATABASE {BASE_DE_HUMO}")
    r = _psql(archivo=os.path.join(RAIZ, "db/esquema_completo.sql"), base=BASE_DE_HUMO)
    if r.returncode != 0:
        raise RuntimeError(f"no cargó el esquema: {r.stderr[-500:]}")
    _psql(sql="ALTER USER postgres PASSWORD 'humo'")
    return "postgresql://postgres:humo@127.0.0.1:5432/" + BASE_DE_HUMO


def siembra():
    """UN caso de cada cosa, para que las pantallas no midan el caso vacío.

    No pretende ser producción: pretende que las consultas traigan AL MENOS
    UNA FILA, que es la diferencia entre ejercitar el `for` y no ejercitarlo.
    """
    return """
    insert into clientes (nombre) values ('EJEMPLO Cliente');
    insert into articulos (nombre, grupo) values ('EJEMPLO Fruta', 'frutas');
    insert into proveedores (nombre, codigo_puesto) values ('EJEMPLO Puesto', 'N01P01');
    insert into pedidos (cliente_id, fecha_operacion, creado_en, origen)
      select id, current_date, now(), 'mail' from clientes limit 1;
    insert into pedidos_renglones (pedido_id, sucursal, articulo_id, cantidad, cantidad_armada, armado_el)
      select p.id, 'EJ', a.id, 10, 10, now() from pedidos p, articulos a limit 1;
    insert into pedidos_sucursales (pedido_id, sucursal)
      select id, 'EJ' from pedidos limit 1;
    insert into compras (proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                         contenido_por_cajon, cantidad_kilos, importe, estado)
      select pr.id, a.id, current_date, 10, 16, 160, 100000, 'pendiente'
      from proveedores pr, articulos a limit 1;
    insert into fichas_logistica (articulo_id, cliente_id, unidad_venta)
      select a.id, c.id, 'kilo' from articulos a, clientes c limit 1;
    insert into colegas (nombre, nombre_normalizado) values ('EJEMPLO Colega', 'ejemplo colega');
    insert into vacios_deposito_devoluciones (proveedor_id, compra_id, cantidad, stock_sistema)
      select pr.id, co.id, 1, 1 from proveedores pr, compras co limit 1;
    """


def _pedir(cliente, ruta, query=None):
    """Un GET, devolviendo None si la excepción no llegó a ser respuesta."""
    try:
        resp = cliente.get(ruta, params=query or {}, follow_redirects=False)
        # Un 301 es un ALIAS DE RUTEO y se sigue; un 302/303 es la PUERTA
        # mandando a la clave, y seguirlo mediría la pantalla de la clave
        # (corolario 53: el cero prolijo de otra página).
        if resp.status_code == 301:
            resp = cliente.get(resp.headers["location"], follow_redirects=False)
        return resp
    except Exception as e:  # noqa: BLE001
        print(f"  EXCEPCIÓN en {ruta}: {type(e).__name__}: {str(e)[:300]}")
        return None


def _valor_para(nombre):
    """Un valor plausible SEGÚN EL NOMBRE del parámetro.

    Por nombre y no por una tabla ruta→params escrita a mano: la tabla
    envejece en silencio y la pantalla nueva que pida un id vuelve a contestar
    422 sin que nadie lo note (corolario 60 — la lista propia solo confirma lo
    que ya sabías).
    """
    import datetime
    hoy = datetime.date.today()
    if nombre.endswith("_id"):
        return "1"          # la siembra deja la fila 1 de cada tabla
    if nombre == "tipo_retiro":
        return "Clark"      # el default de la columna en el esquema real
    if "desde" in nombre:
        return (hoy - datetime.timedelta(days=30)).isoformat()
    if "hasta" in nombre or nombre in ("fecha", "dia"):
        return hoy.isoformat()
    return None


def _parametros_de(esquema, ruta, solo_requeridos=False):
    declarados = esquema["paths"].get(ruta, {}).get("get", {}).get("parameters", [])
    query = {}
    for p in declarados:
        if p.get("in") != "query":
            continue
        if solo_requeridos and not p.get("required"):
            continue
        valor = _valor_para(p["name"])
        if valor is not None:
            query[p["name"]] = valor
    return query


def abrir_todas(verbose=True):
    """Devuelve (filas, resumen). Cada fila es (ruta, status, detalle)."""
    url = preparar_base()
    os.environ["DATABASE_URL"] = url
    for clave in ("CLAVE_GERENCIA", "CLAVE_ADMINISTRACION",
                  "CLAVE_COMPRAS", "CLAVE_CONTROL_PUESTO"):
        os.environ.setdefault(clave, "humo-secreta")

    sql = "/tmp/siembra_humo.sql"
    io.open(sql, "w", encoding="utf-8").write(siembra())
    os.chmod(sql, 0o644)
    r = _psql(archivo=sql, base=BASE_DE_HUMO)
    if r.returncode != 0:
        raise RuntimeError(f"no sembró: {r.stderr[-800:]}")

    sys.path.insert(0, RAIZ)
    from fastapi.testclient import TestClient
    from app.main import (app, PUERTA_GERENCIA, PUERTA_ADMINISTRACION,
                          PUERTA_COMPRAS, PUERTA_CONTROL)

    cliente = TestClient(app)
    for puerta in (PUERTA_GERENCIA, PUERTA_ADMINISTRACION, PUERTA_COMPRAS, PUERTA_CONTROL):
        cliente.cookies.set(puerta.cookie, puerta.firma("humo-secreta"))

    esquema = app.openapi()
    filas = []
    for ruta in rutas_get():
        if ruta in NO_SE_ABREN:
            continue
        concreta = concretar(ruta)
        if concreta is None:
            filas.append((ruta, 0, "no se pudo concretar el id de la URL"))
            continue
        # DE MENOS A MÁS, y se para en el primero que abra. Sin los
        # parámetros, la pantalla que pide `articulo_id` contesta 422 y NUNCA
        # CORRE su consulta — que es como la primera versión de este script
        # daba verde con el bug del 19/09 adentro. Y con TODOS puestos de
        # prepo da 404: rellenar `ficha_id=1` apunta a una ficha que la
        # siembra no tiene. Los dos extremos dejan la consulta sin tocar.
        resp = None
        for query in (None,
                      _parametros_de(esquema, ruta, solo_requeridos=True),
                      _parametros_de(esquema, ruta)):
            if query is not None and not query and resp is not None:
                continue
            intento = _pedir(cliente, concreta, query)
            if resp is None or (intento is not None and intento.status_code == 200):
                resp = intento
            if resp is not None and resp.status_code == 200:
                break
        if resp is None:
            filas.append((ruta, 500, "la excepción no llegó a respuesta"))
        else:
            detalle = resp.text[:400].replace("\n", " ") if resp.status_code >= 400 else ""
            filas.append((ruta, resp.status_code, detalle))

    resumen = {
        "miradas": len(filas),
        "ABIERTAS": sum(1 for r, s, _ in filas if s == ESTADO_ESPERADO.get(r, 200)),
        "NO_ABREN": sum(1 for r, s, _ in filas if s != ESTADO_ESPERADO.get(r, 200)),
        "ROTAS": sum(1 for _, s, _ in filas if s >= 500),
    }
    if verbose:
        imprimir(filas, resumen)
    return filas, resumen


def imprimir(filas, resumen):
    print("\n=== HUMO: todas las pantallas contra el esquema REAL ===")
    print(f"miradas {resumen['miradas']} · ABIERTAS {resumen['ABIERTAS']} "
          f"de {resumen['miradas']} · NO ABREN {resumen['NO_ABREN']} · "
          f"ROTAS {resumen['ROTAS']}")
    if not resumen["miradas"]:
        print("NINGUNA PANTALLA MIRADA — la corrida no midió nada")
    for ruta, status, detalle in filas:
        if status >= 500:
            print(f"  ROTA {status}  {ruta}\n        {detalle}")
    sin_abrir = [(r, s) for r, s, _ in filas if s != ESTADO_ESPERADO.get(r, 200)]
    if sin_abrir:
        print(f"  NO ABIERTAS ({len(sin_abrir)}), su consulta no se tocó:")
        for r, s in sin_abrir:
            print(f"     {s}  {r}")


if __name__ == "__main__":
    _, resumen = abrir_todas()
    # Falla por ROTAS **y por NO ABREN**: una pantalla que dejó de abrirse no
    # está rota, y tampoco está probada. Sin esta segunda mitad el humo se
    # degrada solo —cada ruta nueva que pida un parámetro sale del conjunto—
    # y la corrida sigue dando verde con menos pantallas cada mes.
    sys.exit(1 if resumen["ROTAS"] or resumen["NO_ABREN"] or not resumen["miradas"] else 0)
