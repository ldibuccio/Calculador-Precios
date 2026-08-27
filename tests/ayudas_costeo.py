"""Ayudas compartidas para parchar el costeo en los tests.

Las consultas de "vigente a una fecha" (precio, costo de envase, conceptos
del cliente) se piden ahora para VARIAS fechas de una: devuelven
{fecha: valor} en vez del valor suelto. Los tests que fijan una foto sola
siguen queriendo decir "esto es lo que hay", sin importar la fecha, así que
acá se parchan con un diccionario que devuelve esa foto para cualquier
fecha que le pidan.

Que el "vigente a la fecha" se resuelva BIEN no lo prueba un mock: lo
prueba la verificación contra una base real con historia sembrada (varias
fechas de vigencia por ficha), que es donde un error de fecha se ve.
"""

from collections import defaultdict
from unittest.mock import patch


def parche_por_fechas(nombre: str, valor):
    """Parcha una consulta *_en_fechas para que cualquier fecha devuelva `valor`."""
    return patch(nombre, side_effect=lambda *argumentos: defaultdict(lambda: valor))


def parches_del_listado(precios=(), envases=(), conceptos=None):
    """Los tres parches de "vigente a la fecha" que necesita el listado de negociación."""
    return [
        parche_por_fechas("app.costeo.listar_precios_vigentes_por_cliente_en_fechas", list(precios)),
        parche_por_fechas("app.costeo.listar_costos_envases_vigentes_en_fechas", list(envases)),
        parche_por_fechas(
            "app.costeo.listar_conceptos_vigentes_por_cliente_en_fechas",
            conceptos if conceptos is not None else {"tasas_suman": [], "tasas_restan": [], "utilidad": None},
        ),
    ]
