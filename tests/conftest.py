"""Configuración de la suite.

EL BARAJADOR: `SEMILLA_ORDEN=7 pytest` corre los mismos tests en otro orden.

Existe porque el 12/09 la suite dio `1 failed, 2267 passed` una vez y nunca
más, y las diez corridas verdes que vinieron después **fueron las diez el
MISMO orden**: no hay ningún plugin de orden instalado, así que el default es
determinista. Diez verdes sin variar nada prueban que la corrida es
repetible, no que la suite sea sana — y eso se leyó como lo segundo.

La semilla va por entorno y no automática, y eso es a propósito: barajar
siempre haría que una corrida roja no se pueda repetir, que es lo peor que le
puede pasar a un test intermitente. Con la semilla escrita al lado del rojo,
la corrida se reproduce entera.
"""
import os
import random


def pytest_collection_modifyitems(session, config, items):
    semilla = os.environ.get("SEMILLA_ORDEN")
    if semilla is None:
        return
    random.Random(int(semilla)).shuffle(items)
    print(f"\n[orden barajado con semilla {semilla}: {len(items)} tests]")
