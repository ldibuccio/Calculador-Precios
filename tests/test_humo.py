"""El humo: abre TODAS las pantallas contra una base REAL, sin un solo mock.

POR QUÉ EXISTE. El 19/09 se cayeron dos pantallas en producción con la suite
en 2749 verdes, y las dos por la misma razón de fondo: **en esta suite la base
está mockeada en todos lados, así que ninguna consulta se le manda nunca a un
Postgres.** Un SQL que no parsea no tiene forma de fallar acá.

  · 11h — `_pilas_de_cajones` desempacaba tres valores de una tupla de dos.
    Los fixtures devolvían la forma inventada, así que el andamio decidía la
    respuesta (corolario 9/40).
  · 14h — `column v.fecha_operacion does not exist`: el CTE no exponía la
    columna. Y acá el test que podía verlo ESTABA PUESTO y era el correcto
    (corolario 65, el que mira el TEXTO del SQL): afirmaba la lista del SELECT
    y pasó. **Un assert de texto verifica la FORMA de la consulta, nunca su
    VALIDEZ contra el esquema** — ninguna cantidad de asserts de texto puede
    saber que un alias no expone una columna. Eso solo lo dice un Postgres.

SE SALTEA SIN POSTGRES, y eso es una debilidad conocida: un test salteado se
lee igual que uno verde. Por eso el que decide antes de un deploy no es este
test sino la corrida a mano, que imprime su denominador:

    python3 scripts/humo.py        # sin pipe, y se mira el $?

Los tres canarios, contra un baseline en 128 de 128 (corolario 82 — con el
árbol ya rojo el canario mide cualquier cosa):

    BUG REAL 14h · el CTE no expone fecha_operacion   -> MORDIÓ
    BUG REAL 11h · desempacar 3 de una tupla de 2     -> MORDIÓ
    CONTROL · una columna inventada en otra consulta  -> MORDIÓ
"""
import os
import re
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


sys.path.insert(0, RAIZ)
from scripts.humo import hay_postgres  # noqa: E402


# EL INTERRUPTOR QUE CIERRA EL AGUJERO DEL SALTEO. Sin Postgres este test se
# saltea, y **un test salteado se lee exactamente igual que uno verde** — en
# una suite de 2750 es una `s` que nadie mira. Eso es tolerable en la máquina
# de alguien y es inaceptable en el CI, que es justo donde este test es la
# única evidencia de su clase.
#
# Con HUMO_OBLIGATORIO=1 —que el workflow pone— dejar de poder correrlo FALLA
# en vez de saltear. Así, el día que el servicio de Postgres del runner no
# levante, el CI se pone rojo en vez de dar verde sin haber mirado nada.
OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"


def test_TODAS_las_pantallas_ABREN_contra_una_base_REAL():
    """Corre el humo en SUBPROCESO, para no filtrarle DATABASE_URL a la suite."""
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail(
                "HUMO_OBLIGATORIO=1 y no hay un Postgres usable: el humo no "
                "corrió, así que esta corrida NO VERIFICÓ NINGUNA PANTALLA "
                "contra el esquema. Revisá el servicio de Postgres del runner.")
        pytest.skip("sin Postgres local: el humo se corre con "
                    "`python3 scripts/humo.py` antes de desplegar")
    r = subprocess.run([sys.executable, "scripts/humo.py"],
                       cwd=RAIZ, capture_output=True, text=True, timeout=600)

    resumen = [l for l in r.stdout.split("\n") if "miradas" in l]
    assert resumen, f"el humo no llegó a medir nada:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    linea = resumen[0]

    # EL DENOMINADOR PRIMERO. Sin esto, un humo que se degrada —cada ruta
    # nueva que pida un parámetro sale del conjunto— sigue dando verde con
    # menos pantallas cada mes, y eso se ve idéntico a uno sano (corolario 53).
    miradas = int(re.search(r"miradas (\d+)", linea).group(1))
    abiertas = int(re.search(r"ABIERTAS (\d+)", linea).group(1))
    assert miradas >= 120, f"el humo miró solo {miradas} pantallas: {linea}"
    assert abiertas == miradas, (
        f"{miradas - abiertas} pantallas NO ABRIERON, así que su consulta no "
        f"se tocó:\n{linea}\n{r.stdout[-3000:]}")

    assert r.returncode == 0, f"el humo falló:\n{linea}\n{r.stdout[-3000:]}"
