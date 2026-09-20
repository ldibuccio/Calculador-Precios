"""Abre UNA pantalla contra la base REAL y muestra lo que DICE.

POR QUÉ NO ALCANZA EL HUMO, que es lo que este archivo agrega y es del dueño
(20/09): el humo afirma el CÓDIGO DE ESTADO de las 131 pantallas — que abren,
que su SQL parsea, que el handler corre. **No afirma una sola palabra de lo
que muestran.** Una pantalla a la que le borré el único botón contesta 200
igual, y el humo la cuenta como ABIERTA.

Así que "el humo está verde" y "la pantalla que toqué hace lo que dije" son
dos cosas distintas, y la segunda no se deduce de la primera. Esto es lo que
contesta la segunda: renderiza y devuelve el TEXTO VISIBLE, para leerlo.

Y LO QUE NINGUNO DE LOS DOS CONTESTA es si eso llegó al galpón: entre el push
y el deploy está el gate del CI (ver CLAUDE.md, punto 5 del push). Un humo en
verde sobre un commit cuyo CI está en rojo describe perfectamente una pantalla
que nadie puede abrir.

    python3 scripts/mirar_pantalla.py /deposito /deposito/pedido

LA IDENTIDAD VA PEGADA AL TEXTO (corolario 53): el status y el conteo de
botones y formularios. Sin eso, la pantalla de "Falta la clave" se imprime
igual de prolija que la buena, y ya pasó dos veces en este proyecto.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Jinja busca `templates/` relativo al cwd, asi que esto se corre desde la
# raiz del repo pase lo que pase — si no, la pantalla no existe y el
# "NO CONTESTO" se lee como una pantalla rota.
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from humo import _pedir, concretar, hay_postgres, levantar  # noqa: E402

VISIBLES = re.compile(r"<(script|style|template)\b.*?</\1>", re.S | re.I)


def texto_visible(html):
    cuerpo = VISIBLES.sub(" ", html)
    cuerpo = re.sub(r"<!--.*?-->", " ", cuerpo, flags=re.S)
    cuerpo = re.sub(r"<br\s*/?>|</(p|div|li|h[1-6]|tr|form|a|button)>", "\n", cuerpo, flags=re.I)
    cuerpo = re.sub(r"<[^>]+>", " ", cuerpo)
    cuerpo = cuerpo.replace("&nbsp;", " ").replace("&amp;", "&").replace("&mdash;", "—")
    lineas = [re.sub(r"[ \t]+", " ", l).strip() for l in cuerpo.splitlines()]
    return [l for l in lineas if l]


def mirar(cliente, esquema, ruta, query=None):
    concreta = concretar(ruta) or ruta
    resp = _pedir(cliente, concreta, query)
    if resp is None:
        print(f"\n=== {ruta} · NO CONTESTÓ ===")
        return
    cuerpo = resp.text
    marcado = cuerpo.split("</style>")[-1]
    print(f"\n=== {concreta}{('?' + '&'.join(f'{k}={v}' for k, v in (query or {}).items())) if query else ''}")
    botones = len(re.findall(r"<(a|button)\b", marcado))
    formularios = marcado.count("<form")
    print("    GET %s · botones %d · formularios %d · %d caracteres"
          % (resp.status_code, botones, formularios, len(cuerpo)))
    if resp.status_code != 200:
        print(f"    {cuerpo[:300]}")
        return
    for linea in texto_visible(marcado):
        print(f"    {linea}")


def main(rutas):
    if not hay_postgres():
        print("NO HAY POSTGRES: esto no mide nada. Levantalo antes.")
        return 1
    cliente, esquema = levantar()
    for entrada in rutas:
        ruta, _, cola = entrada.partition("?")
        query = dict(p.split("=", 1) for p in cola.split("&")) if cola else None
        mirar(cliente, esquema, ruta, query)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["/deposito"]))
