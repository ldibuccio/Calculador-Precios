"""PÉRDIDA TOTAL (dueño, 13/10): el cuadro 12 del panel.

(merma + segunda − lo cobrado + faltante de las guías R), en plata al COSTO,
sobre la facturación a precio de lista del período, como Rechazos. Mes
anterior cerrado y mes en curso. El mes en curso va rojo si está peor que el
anterior y verde si está mejor.

El faltante es el de "Rinde de guías R" (entraron − primera − segunda −
merma, con la primera real), valuado por guía al costo del kilo que entró:
el precio por cajón de SU compra sobre lo que pesó el cajón.
"""
import os
import re
import sys
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.kilos_guia_r import faltante_en_plata  # noqa: E402
from core.panel_control import TOP_DE_LA_PERDIDA, resumen_de_perdida_total  # noqa: E402
from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 10, 13)


def _guia(articulo, consumos, importes, primera, segunda=0, merma=0, kg_caja=8.0, real=None):
    return {"articulo_id": articulo, "articulo": f"EJEMPLO {articulo}", "consumos": consumos,
            "importes": importes, "primera": primera, "segunda": segunda, "merma": merma,
            "kg_caja": kg_caja, "primera_real": real}


def test_FALTANTE_cada_guia_al_costo_del_kilo_de_SU_compra():
    """A: 10 cajones de 10 kg a $50.000 ($5.000 el kg) -> 9 cajas de 8 y 1
    cajón de segunda: faltan 100 − 72 − 10 = 18 kg = $90.000.
    B (otro artículo): 5 de 10 kg a $20.000 y 5 de 12 a $36.000 (mezcla): 110
    kg que costaron $280.000; 14 cajas de 8 = 112: sobran 2 kg, −$5.090,91.
    Rivales: C sin pesada (no hay cuenta), D con una compra sin precio."""
    guias = [_guia(1, [(10, 10.0)], [50000.0], 9, segunda=1),
             _guia(2, [(5, 10.0), (5, 12.0)], [20000.0, 36000.0], 14),
             _guia(3, [(10, None)], [50000.0], 9),
             _guia(4, [(5, 10.0), (5, 10.0)], [50000.0, None], 9)]
    resultado = faltante_en_plata(guias)
    assert resultado["por_articulo"] == {1: {"articulo": "EJEMPLO 1", "pesos": 90000.0},
                                         2: {"articulo": "EJEMPLO 2", "pesos": -5090.91}}
    assert resultado["pesos"] == 84909.09
    assert (resultado["guias"], resultado["guias_sin_cuenta"], resultado["guias_sin_precio"]) == (2, 1, 1)


def test_FALTANTE_con_la_primera_REAL():
    """Las 9 cajas de A salieron con 9 kg: la primera pesa 81 y faltan 9 kg."""
    real = faltante_en_plata([_guia(1, [(10, 10.0)], [50000.0], 9, segunda=1, real={"bultos": 9, "kg": 81})])
    assert real["pesos"] == 45000.0


def _mermas(*filas):
    return {"total": sum(f[2] for f in filas),
            "filas": [{"articulo_id": a, "articulo": n, "total": t} for a, n, t in filas]}


def _segunda(*filas):
    return {"perdida": sum(f[2] for f in filas),
            "filas": [{"articulo_id": a, "articulo": n, "perdida": p} for a, n, p in filas]}


def _faltante(*filas, sin_cuenta=0, sin_precio=0):
    return {"pesos": sum(f[2] for f in filas), "guias_sin_cuenta": sin_cuenta, "guias_sin_precio": sin_precio,
            "por_articulo": {a: {"articulo": n, "pesos": p} for a, n, p in filas}}


def test_PERDIDA_TOTAL_las_tres_partes_sobre_lo_facturado_y_el_TOP():
    """Seis artículos: el sexto (el que menos pierde) queda afuera del top. El
    1 suma de las tres partes; el 6 pierde por merma y gana por la falta."""
    resultado = resumen_de_perdida_total(
        _mermas((1, "EJEMPLO Morron", 100.0), (6, "EJEMPLO Ajo", 50.0)),
        _segunda((1, "EJEMPLO Morron", 200.0), (2, "EJEMPLO Tomate", 900.0), (3, "EJEMPLO Zapallo", 400.0)),
        _faltante((1, "EJEMPLO Morron", 300.0), (4, "EJEMPLO Papa", 350.0), (5, "EJEMPLO Batata", 60.0),
                  (6, "EJEMPLO Ajo", -40.0), sin_cuenta=2, sin_precio=1),
        facturacion=23200.0)
    assert resultado["partes"] == {"merma": 150.0, "segunda": 1500.0, "faltante": 670.0}
    assert (resultado["total"], resultado["facturacion"]) == (2320.0, 23200.0)
    assert resultado["pct"] == pytest.approx(10.0)
    assert resultado["pct_partes"]["segunda"] == pytest.approx(1500 / 232)
    assert TOP_DE_LA_PERDIDA == 5
    assert [(f["articulo_id"], f["total"]) for f in resultado["top"]] == [
        (2, 900.0), (1, 600.0), (3, 400.0), (4, 350.0), (5, 60.0)]
    assert resultado["top"][1] == {"articulo_id": 1, "articulo": "EJEMPLO Morron", "merma": 100.0,
                                   "segunda": 200.0, "faltante": 300.0, "total": 600.0}
    assert (resultado["guias_sin_cuenta"], resultado["guias_sin_precio"]) == (2, 1)


def test_PERDIDA_TOTAL_sin_facturacion_no_inventa_un_porcentaje():
    resultado = resumen_de_perdida_total(_mermas((1, "EJEMPLO Morron", 10.0)), _segunda(), _faltante(), 0.0)
    assert resultado["pct"] is None and resultado["pct_partes"]["merma"] is None and resultado["total"] == 10.0


# --- EL TABLERO: rojo si el mes en curso está peor, verde si está mejor ------

def _tablero(anterior_pct, actual_pct, con_perdida=True):
    import app.main as m
    from core.panel_foto import a_texto
    from tests.test_administracion_reordenada import CLAVES, _cliente
    from tests.test_panel_numeros_enteros import MESES, _datos
    datos = {c: _datos(c, HOY, {}) for c in m.CUADROS_DEL_PANEL if c != "perdida"}
    if con_perdida:
        datos["perdida"] = {clave: {"pct": pct, "total": 1000.0 * (i + 1), **MESES[clave]}
                            for i, (clave, pct) in enumerate((("anterior", anterior_pct), ("actual", actual_pct)))}
    foto = {"calculada_el": datetime(2026, 10, 13, 9, 1, tzinfo=timezone.utc), "datos_json": a_texto(datos)}
    with patch.dict(os.environ, CLAVES), patch.object(m, "_hoy_argentina", return_value=HOY), \
            patch.object(m, "foto_buena_del_panel", return_value=foto), \
            patch.object(m, "intentos_automaticos_del_panel", return_value=[]):
        pagina = _cliente(m, "gerencia").get("/gerencia/panel")
    assert pagina.status_code == 200, pagina.text[:300]
    return pagina.text.split("</style>")[-1].split('data-cuadro="perdida"')[1].split("</a>")[0]


def _clase(cuadro, clave):
    return re.search(r'class="cuadro-numero ?([a-z]*) ?" data-pct="' + clave + '"', cuadro).group(1)


def test_el_TABLERO_rojo_si_empeora_verde_si_mejora_y_nada_si_igual():
    peor, mejor, igual = _tablero(2.0, 3.5), _tablero(3.5, 2.0), _tablero(2.0, 2.0)
    assert (_clase(peor, "anterior"), _clase(peor, "actual")) == ("", "rojo")
    assert (_clase(mejor, "anterior"), _clase(mejor, "actual")) == ("", "verde")
    assert _clase(igual, "actual") == ""
    assert '<div data-ajustar class="cuadro-pie" data-monto="actual">$2.000</div>' in peor
    assert _clase(_tablero(None, 3.5), "actual") == ""          # sin facturación el mes anterior: sin color


def test_una_FOTO_de_antes_dice_que_aparece_en_la_proxima():
    assert "Aparece en la próxima actualización." in _tablero(None, None, con_perdida=False)


# --- CONTRA POSTGRES: el galpón de "Kilos al armar" ---------------------------
# R0 (04/10): 1 cajón de 10 kg a $50.000 -> 1 caja que salió con 20 kg: sobran
# 10 kg, −$50.000. R1 (09/10): 10 cajones -> 10 cajas, 9 salieron con 76 kg y
# 1 pesa la ficha (8): faltan 16 kg, $80.000. Octubre: $30.000.
# Rival: R2 (10/10) de la compra 12, SIN PRECIO: no entra y se cuenta.
# SEPTIEMBRE, para que los meses no se confundan: R3 (20/09) de Cherry, 2
# cajones de 10 kg a $30.000 -> 3 cajas de 5: faltan 5 kg, $15.000. Y un
# precio de lista del Morrón desde el 01/10, para que octubre facture.
RIVAL = """
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (13, 1, 3, '2026-09-15', 10, 10, 100, 30000, 'recepcionado', '2026-09-15 18:00-03', 10, 10);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra, creado_en)
  overriding system value
  values (103, 3, '2026-09-20', 2, 3, 0, 0, 20000, 1, 3, 1, true, '2026-09-20 09:00-03');
insert into reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos, costo_por_bulto)
  values (103, 'compra', 13, 13, 2, 30000);
insert into precios_venta_historial (articulo_id, cliente_id, precio, vigente_desde, ficha_id)
  values (1, 1, 1000, '2026-10-01', 1);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value
  values (12, 1, 1, '2026-10-03', 5, 10, 50, null, 'recepcionado', '2026-10-03 18:00-03', 5, 10);
insert into reprocesos (id, articulo_id, fecha_operacion, bultos_tomados, bultos_primera,
                        bultos_segunda, bultos_merma, costo_por_bulto_primera, cliente_id,
                        ficha_id, envase_id, lleva_caja_nuestra, creado_en)
  overriding system value
  values (102, 1, '2026-10-10', 5, 5, 0, 0, 0, 1, 1, 1, true, '2026-10-10 09:00-03');
insert into reprocesos_consumos (reproceso_id, origen, compra_id, origen_id, bultos, costo_por_bulto)
  values (102, 'compra', 12, 12, 5, 0);
"""


@pytest.fixture(scope="module")
def base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres")
        pytest.skip("sin Postgres local")
    from tests.test_kilos_al_armar import SIEMBRA
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
        cursor.execute(RIVAL)
    conexion.commit()
    conexion.close()
    return url


@pytest.fixture
def m(base, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", base)
    import app.main as modulo
    return modulo


def test_la_BASE_trae_el_precio_de_cada_consumo(m):
    import app.db as d
    guias = {g["numero"]: g for g in d.guias_r_con_sus_kilos(date(2026, 10, 1), HOY)}
    assert (guias[100]["importes"], guias[101]["importes"], guias[102]["importes"]) == ([50000.0], [50000.0], [None])


def test_el_CUADRO_suma_las_partes_de_SUS_cuadros_y_el_faltante_de_las_guias(m):
    memo: dict = {}
    datos = m._panel_perdida(HOY, memo)
    octubre, septiembre = datos["actual"], datos["anterior"]
    assert (octubre["desde"], octubre["hasta"], septiembre["desde"]) == (date(2026, 10, 1), HOY, date(2026, 9, 1))
    assert octubre["partes"]["faltante"] == 30000.0
    assert (octubre["guias_sin_cuenta"], octubre["guias_sin_precio"]) == (0, 1)
    # Merma y segunda son las de SUS cuadros; la facturación, la de Rechazos.
    assert octubre["partes"]["merma"] == m._panel_mermas(HOY, {})["actual"]["total"]
    assert octubre["partes"]["segunda"] == m._panel_segunda(HOY, {})["actual"]["perdida"]
    assert octubre["facturacion"] == m._panel_rechazos(HOY, {})["actual"]["facturacion"]
    assert septiembre["partes"]["faltante"] == 15000.0
    assert octubre["facturacion"] > 0 and septiembre["facturacion"] == 0.0   # testigo: los meses se distinguen


def test_el_DETALLE_abre_las_tres_partes_y_el_top(m):
    from tests.test_administracion_reordenada import CLAVES, _cliente
    with patch.dict(os.environ, CLAVES), patch.object(m, "_hoy_argentina", return_value=HOY):
        pagina = _cliente(m, "gerencia").get("/gerencia/panel/perdida")
    assert pagina.status_code == 200, pagina.text[:300]
    octubre = pagina.text.split('data-mes="actual">')[1].split('data-mes=')[0]
    assert re.findall(r'data-parte="([a-z]+)"', octubre) == ["merma", "segunda", "faltante"]
    faltante = octubre.split('data-parte="faltante">')[1].split("</p>")[0]
    assert "<strong data-ajustar>$30.000</strong>" in faltante
    assert re.findall(r'data-top="(\d+)"', octubre) == ["1"]
    assert "1 con una compra sin precio" in octubre
