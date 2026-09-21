#!/usr/bin/env python3
"""Escribe VERSION_NUMERO con la cantidad de commits de `main`.

POR QUÉ EL NÚMERO VIAJA EN EL REPO Y NO SE CALCULA EN EL BUILD. Hasta el
20/09 lo horneaba `nixpacks.toml` con `git rev-list --count HEAD`. En
Railway eso devolvió NADA: el pie mostró "sin número" — y esa salida es la
que distingue el diagnóstico, porque un clon SHALLOW habría dado "1". O sea
que en ese build git no funciona en absoluto (sin `.git`, o sin el binario),
no que la historia esté truncada.

Contra eso no hay comando que valga: si el dato no está en el contenedor, la
única forma de que llegue es que esté adentro de lo que se despliega.

EL HUEVO Y LA GALLINA se resuelve con `--amend`: el archivo es parte del
commit que cuenta, así que se commitea primero, se sella después, y se
enmienda. Un `--amend` no agrega un commit, así que el número no se mueve:

    git commit -m "..."
    python3 scripts/sellar_version.py
    git commit --amend --no-edit

Y EL `git add` LO HACE ESTE SCRIPT, no el que lo corre. Es lo que faltaba
el 21/09: `git commit --amend --no-edit` SIN `-a` y sin rutas enmienda con
el índice tal como está, y el archivo se acaba de escribir DESPUÉS del `git
add`, así que queda afuera. El commit sale con el número viejo adentro, el
conteo ya se movió, y el test lo agarra — en el CI, o sea donde frena el
deploy y no donde se escribe. La receta de arriba, escrita así, no
funcionaba: le faltaba un paso que nadie iba a recordar. Ponerlo acá adentro
es el chequeo mecánico en vez de la regla escrita.

Y LO QUE IMPIDE QUE SE OLVIDE NO ES ACORDARSE: es
`test_VERSION_NUMERO_esta_al_dia`, que compara el archivo contra el conteo y
pone el CI en rojo. Sobre un clon shallow ese test se saltea —ahí el conteo
es 1 y no significa nada—, y por eso el workflow clona con `fetch-depth: 0`.
"""
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def contar_commits() -> str:
    return subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=RAIZ, capture_output=True, text=True, check=True,
    ).stdout.strip()


def es_shallow() -> bool:
    salida = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=RAIZ, capture_output=True, text=True, check=True,
    ).stdout.strip()
    return salida == "true"


def main() -> int:
    if es_shallow():
        # Sellar desde un clon truncado escribiría un número chico y
        # PLAUSIBLE, que es peor que ninguno: el que lo lee actúa.
        print("clon SHALLOW: no se sella (el conteo acá no significa nada)", file=sys.stderr)
        return 1
    numero = contar_commits()
    (RAIZ / "VERSION_NUMERO").write_text(numero + "\n", encoding="utf-8")
    # STAGEADO ACÁ: un `--amend` sin `-a` enmienda con el índice como está, y
    # este archivo se escribió recién. Sin esto el commit sale con el número
    # viejo adentro y el CI lo agarra después de pushear.
    subprocess.run(["git", "add", "VERSION_NUMERO"], cwd=RAIZ, check=True)
    print(f"VERSION_NUMERO = {numero} (stageado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
