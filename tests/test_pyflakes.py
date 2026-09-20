"""Ningún NOMBRE INDEFINIDO en app/, core/ y scripts/.

POR QUÉ EXISTE, y es el corolario 51. `_compras_del_renglon_para_devolucion`
tenía un `except Exception` puesto a propósito para degradar con elegancia
—sin poder rejugar el FIFO, el camino que queda es el del proveedor suelto—
y ese `except` se comía un `NameError`: la función que llamaba no estaba
importada. La pantalla caía al camino degradado PARA SIEMPRE, y el camino
degradado está diseñado justamente para verse bien.

El `except` se escribió contra una falla AMBIENTAL —la base que no contesta,
que pasa a veces— y también atrapa las de PROGRAMACIÓN, que pasan SIEMPRE. Y
las dos se ven idénticas desde afuera. `logger.exception` aparece 43 veces en
app/main.py, así que cualquiera de las 43 puede estar tapando un import que
falta, hoy, sin que nada lo diga en la pantalla.

QUÉ MIRA Y QUÉ NO. Solo los nombres indefinidos. pyflakes también avisa de
imports sin usar y variables asignadas y nunca leídas —hoy hay una docena— y
ésos NO fallan acá a propósito: son de estilo, no tienen un modo de falla, y
un guardia que marca doce cosas inofensivas se aprende a ignorar. Un nombre
indefinido es otra cosa: es un `NameError` esperando a que alguien cruce esa
línea.
"""
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETAS = ("app", "core", "scripts")


def nombres_indefinidos(raiz=RAIZ):
    salida = subprocess.run(
        [sys.executable, "-m", "pyflakes", *CARPETAS],
        cwd=raiz, capture_output=True, text=True,
    ).stdout
    return [l for l in salida.splitlines() if "undefined name" in l]


def test_no_hay_NINGUN_nombre_indefinido():
    encontrados = nombres_indefinidos()
    assert not encontrados, (
        "hay nombres indefinidos, y un `except Exception` los convierte en una "
        "degradación PERMANENTE que se ve igual que el funcionamiento normal:\n  "
        + "\n  ".join(encontrados)
    )


def test_el_GUARDIA_VE_un_nombre_indefinido_plantado(tmp_path):
    """Un cero sin el caso plantado no informa (corolario 36).

    Se planta en una COPIA del repo y no en el repo: mutar el árbol de verdad
    para medir es lo que deja una avería puesta cuando algo se corta en el
    medio.
    """
    import shutil

    copia = tmp_path / "repo"
    copia.mkdir()
    for carpeta in CARPETAS:
        shutil.copytree(os.path.join(RAIZ, carpeta), copia / carpeta)

    assert not nombres_indefinidos(copia), "la copia ya venía sucia: el canario no diría nada"

    archivo = copia / "core" / "canario_del_guardia.py"
    archivo.write_text("def f():\n    return funcion_que_no_existe()\n", encoding="utf-8")
    plantado = nombres_indefinidos(copia)

    assert plantado, "pyflakes NO vio un nombre indefinido plantado: el cero de arriba no vale"
    assert "funcion_que_no_existe" in plantado[0]
