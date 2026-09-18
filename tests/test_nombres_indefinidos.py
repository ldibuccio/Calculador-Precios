"""Ningún nombre indefinido en `app/` ni en `core/`, y la prueba de que se ve.

POR QUÉ ESTE TEST EXISTE, que es lo que decide qué mira y qué no.

Un `except Exception` escrito para degradar con elegancia —la base que no
contesta, el FIFO que no se puede rejugar— también atrapa las fallas de
PROGRAMACIÓN: un `NameError` por un import que falta entra por la misma
puerta. Y las dos clases son opuestas en lo único que importa: la ambiental
pasa A VECES y el camino degradado es el correcto mientras dure; la de
programación pasa SIEMPRE, así que el camino degradado deja de ser la
excepción y pasa a ser el único que existe.

Desde afuera no se distinguen. La pantalla que cae al proveedor suelto porque
la base está caída y la que cae porque una función no existe se ven iguales —
y las dos se ven iguales que el caso legítimo. `logger.exception` aparece 43
veces en `app/main.py`: cualquiera de esas puede estar tapando un import que
falta, hoy, sin que nada lo diga en la pantalla.

Y agarra un SEGUNDO agujero que no tiene nada que ver con el primero: el
código que sobrevive a una reescritura nombra los IDENTIFICADORES VIEJOS,
porque contra ésos se escribió. Cincuenta líneas de una ruta vieja que
quedaron debajo del `return` de la nueva no las puede ver ninguna suite —el
código inalcanzable no tiene ningún camino que recorrer— pero sí las ve
pyflakes, porque las analiza por dentro.

LO QUE **NO** MIRA, y es una decisión: los imports sin usar, las variables
locales sin usar y los f-string sin placeholders. Hoy hay once de ésos y
ninguno es un bug — hacer fallar la suite con ellos sería convertir una guarda
que sirve en una tarea de limpieza que alguien va a terminar apagando.
"""

import subprocess
import sys

CARPETAS = ["app/", "core/"]


def _pyflakes(*rutas) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-m", "pyflakes", *rutas],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_pyflakes_ENCUENTRA_un_nombre_indefinido_plantado(tmp_path):
    """El par del otro test: sin esto, su cero no se puede leer.

    Un cero de hallazgos y un detector que no corrió se imprimen EXACTAMENTE
    IGUAL. Si pyflakes no está instalado, `python -m pyflakes` no escribe una
    sola línea de aviso y el test de abajo pasa sin haber mirado nada — que es
    la ausencia de filas del backfill con otra ropa.

    Por eso el caso plantado va en la suite y no en una verificación que se
    corrió una vez: es lo único que hace que el cero del otro signifique algo,
    y tiene que seguir siendo cierto mañana.
    """
    archivo = tmp_path / "plantado.py"
    archivo.write_text(
        "def f():\n"
        "    try:\n"
        "        return funcion_que_no_existe()\n"
        "    except Exception:\n"
        "        return []\n",
        encoding="utf-8",
    )
    _, salida = _pyflakes(str(archivo))
    assert "undefined name" in salida, (
        "pyflakes no encontro el nombre indefinido plantado: o no esta "
        f"instalado, o dejo de reportarlos. Salida: {salida!r}")
    assert "funcion_que_no_existe" in salida


def test_NINGUN_nombre_indefinido_en_app_ni_core():
    """El cero que el test de arriba vuelve legible.

    Verificado en su momento plantando el caso real —una llamada a una funcion
    inexistente adentro de un `except` amplio—: pyflakes la nombra con archivo
    y linea, y sacandola vuelve a cero.
    """
    _, salida = _pyflakes(*CARPETAS)
    indefinidos = [l for l in salida.splitlines() if "undefined name" in l]
    assert indefinidos == [], "\n".join(indefinidos)
