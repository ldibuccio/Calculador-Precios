"""Script de prueba manual: extrae los datos de una foto de comanda con la API real de Claude.

Uso:
    python probar_comanda.py ruta/a/la/foto.jpg

Este script SÍ llama a la API real (consume créditos) y necesita la variable
de entorno ANTHROPIC_API_KEY configurada. No forma parte de los tests
automáticos: se corre a mano.
"""

import json
import sys

from core.lector_comandas import extraer_comanda


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python probar_comanda.py ruta/a/la/foto.jpg")
        sys.exit(1)

    ruta_imagen = sys.argv[1]

    with open(ruta_imagen, "rb") as archivo:
        imagen = archivo.read()

    resultado = extraer_comanda(imagen)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
