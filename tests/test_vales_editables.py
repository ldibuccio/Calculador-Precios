"""Gerencia corrige CUALQUIER vale en cartera, y maneja sus fotos (dueño, 02/10), contra Postgres.

Hasta el 02/10 solo se corregían los vales con datos propios (anterior al
sistema y carga manual): los 13 de Frutamax son de una DEVOLUCIÓN y la base
les exigía importe y fecha en NULL. Desde db/vales_editables_1:

- el IMPORTE DEL VALE es coalesce(vale.importe, devolución.importe): NULL en
  el vale es "el de la devolución", y un valor es la corrección de Gerencia.
  La fecha igual. `importe_calculado` no cambia nunca;
- el proveedor de un vale de devolución sigue siendo el de la devolución;
- un vale que salió (cobrado o cruzado) no se corrige: la pared de siempre;
- Gerencia borra y reemplaza fotos en cualquier estado. Se va el ARCHIVO y
  queda registrado como borrado 'a_mano', con su fecha y su renglón en el
  historial de borrados.

Los números de la "copia" son los de Frutamax el 02/10 (importe de la
devolución, calculado, cajones, número y salida); los nombres son de EJEMPLO.
"""
import io
import os
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests.test_vales_a_cobrar import _cliente, _devolucion, _marcado  # noqa: E402
from tests.test_vales_carga_manual import HOY, _cargar, base  # noqa: E402,F401  (fixture)

# Frutamax, 02/10: (importe de la devolución, calculado, cajones, número, salida).
LOS_13 = (
    (4000, None, 7, "180365", None), (750000, 750000, 150, None, "cruzado"),
    (1405000, 1405000, 281, None, "cruzado"), (432000, 432000, 144, "4750", None),
    (69000, 69000, 23, "4720", None), (240000, 240000, 60, "14536", None),
    (1000, None, 35, None, "cobrado"), (930000, 930000, 186, None, "cruzado"),
    (72000, None, 24, "3", None), (117000, 117000, 39, "4773", None),
    (72000, 72000, 24, "4772", None), (215000, None, 43, "34971", None),
    (6000, None, 6, None, "cobrado"),
)

CHECK_VIEJO = """
  alter table vales_a_cobrar drop constraint vales_origen_coherente;
  alter table vales_a_cobrar add constraint vales_origen_coherente check (
    (origen = 'devolucion' and devolucion_id is not null
      and proveedor_id is null and fecha is null
      and importe is null and foto_ruta is null)
    or (origen in ('anterior_al_sistema', 'carga_manual') and devolucion_id is null
      and proveedor_id is not null and fecha is not null
      and coalesce(importe > 0, false) and importe_calculado is null));
"""


def _sembrar_los_13(sql):
    """Los 13 vales de Frutamax como estaban, con la base en el CHECK VIEJO."""
    sql(CHECK_VIEJO)
    for importe, calculado, cajones, numero, salida in LOS_13:
        (dev,), = sql("INSERT INTO vacios_deposito_devoluciones (proveedor_id, cantidad, importe, foto_ruta, "
                      "stock_sistema, cargada_desde) VALUES (1, %s, %s, 'x/vale.jpg', 0, 'administracion') "
                      "RETURNING id", (cajones, importe))
        (vale,), = sql("INSERT INTO vales_a_cobrar (origen, devolucion_id, importe_calculado, numero) "
                       "VALUES ('devolucion', %s, %s, %s) RETURNING id", (dev, calculado, numero))
        if salida == "cobrado":
            sql("INSERT INTO vales_a_cobrar_salidas (vale_id, tipo, fecha, importe_cobrado, sector) "
                "VALUES (%s, 'cobrado', '2026-10-02', %s, 'administracion')", (vale, importe))
        elif salida == "cruzado":
            sql("INSERT INTO vales_a_cobrar_salidas (vale_id, tipo, fecha, referencia, sector) "
                "VALUES (%s, 'cruzado', '2026-10-02', 'EJ liq', 'administracion')", (vale,))


def _sin_la_ultima_consulta(archivo):
    """El bloque `do` del archivo, sin los comentarios del pie."""
    texto = io.open(os.path.join(RAIZ, "db", archivo), encoding="utf-8").read()
    return texto[: texto.index("end $$;") + len("end $$;")]


def test_la_MIGRACION_sobre_los_13_de_Frutamax_no_cambia_NINGUN_importe_vigente(base):
    d, sql = base
    _sembrar_los_13(sql)
    antes = {v["id"]: (v["importe"], v["fecha"], v["estado"]) for v in d.listar_vales(estado=None, hoy=HOY)}
    assert len(antes) == 13                                                     # el denominador
    sql(_sin_la_ultima_consulta("vales_editables_1_importe_del_vale.sql"))
    despues = {v["id"]: (v["importe"], v["fecha"], v["estado"]) for v in d.listar_vales(estado=None, hoy=HOY)}
    assert despues == antes
    verificacion = io.open(os.path.join(RAIZ, "db", "vales_editables_2_verificacion.sql"),
                           encoding="utf-8").read()
    (fila,) = sql(verificacion[: verificacion.index(";") + 1])
    assert fila[:6] == ("vales_editables", 1, 0, 0, 4313000, 13)
    # Y ahora la base acepta la corrección que antes rebotaba.
    vale = min(antes)
    d.corregir_vale(vale, importe=4500.0, numero="180365", fecha=antes[vale][1], hoy=HOY)
    assert d.vale_a_cobrar(vale, HOY)["importe"] == 4500.0


def test_el_bloque_entra_en_el_EDITOR_y_tiene_el_CODIGO_ARRIBA():
    for archivo in ("vales_editables_1_importe_del_vale.sql", "vales_editables_2_verificacion.sql"):
        texto = io.open(os.path.join(RAIZ, "db", archivo), encoding="utf-8").read()
        assert len(texto) <= 2500, archivo
        assert not texto.lstrip().startswith("--"), archivo


def _vale_de_devolucion(d, importe=2000.0, numero=None):
    dev = _devolucion(d, cajones=4, importe=importe, numero=numero)
    (vale_id,) = [v["id"] for v in d.listar_vales(hoy=HOY) if v["devolucion_id"] == dev]
    return dev, vale_id


def test_GERENCIA_corrige_importe_fecha_y_numero_de_un_vale_de_DEVOLUCION(base):
    """El RIVAL es la regla hasta el 02/10: "se corrige en la devolución"."""
    d, sql = base
    dev, vale_id = _vale_de_devolucion(d, numero="V-1")
    original = d.vale_a_cobrar(vale_id, HOY)
    cambios = d.corregir_vale(vale_id, importe=2500.0, numero="V-2", fecha=date(2026, 9, 20), hoy=HOY)
    assert cambios == 3
    vale = d.vale_a_cobrar(vale_id, HOY)
    assert (vale["importe"], vale["numero"], vale["fecha"]) == (2500.0, "V-2", date(2026, 9, 20))
    assert vale["importe_calculado"] == original["importe_calculado"]           # no se toca nunca
    assert vale["importe_devolucion"] == 2000.0
    assert sql("SELECT importe FROM vacios_deposito_devoluciones WHERE id = %s", (dev,)) == [(2000,)]
    assert d.resumen_de_la_cartera(HOY)["total"] == 2500.0                      # vale en cartera
    assert [(c["campo"], c["valor_anterior"], c["valor_nuevo"]) for c in d.correcciones_del_vale(vale_id)] == [
        ("importe", "2000.00", "2500.00"), ("numero", "V-1", "V-2"),
        ("fecha", original["fecha"].isoformat(), "2026-09-20")]


def test_volver_al_valor_de_la_DEVOLUCION_deja_la_correccion_en_NULL(base):
    d, sql = base
    _dev, vale_id = _vale_de_devolucion(d)
    fecha = d.vale_a_cobrar(vale_id, HOY)["fecha"]
    d.corregir_vale(vale_id, importe=2500.0, numero=None, fecha=fecha, hoy=HOY)
    assert sql("SELECT importe, fecha FROM vales_a_cobrar WHERE id = %s", (vale_id,)) == [(2500, None)]
    d.corregir_vale(vale_id, importe=2000.0, numero=None, fecha=fecha, hoy=HOY)
    assert sql("SELECT importe, fecha FROM vales_a_cobrar WHERE id = %s", (vale_id,)) == [(None, None)]
    assert len(d.correcciones_del_vale(vale_id)) == 2


def test_el_PROVEEDOR_de_un_vale_de_devolucion_no_se_cambia_y_la_BASE_lo_frena(base):
    import psycopg2
    d, sql = base
    _dev, vale_id = _vale_de_devolucion(d)
    fecha = d.vale_a_cobrar(vale_id, HOY)["fecha"]
    with pytest.raises(d.ValeNoSeCorrige, match="proveedor"):
        d.corregir_vale(vale_id, importe=2000.0, numero="X", fecha=fecha, proveedor_id=2, hoy=HOY)
    d.corregir_vale(vale_id, importe=2000.0, numero="X", fecha=fecha, proveedor_id=1, hoy=HOY)  # el mismo, sí
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("UPDATE vales_a_cobrar SET proveedor_id = 1 WHERE id = %s", (vale_id,))
    with pytest.raises(psycopg2.errors.CheckViolation):
        sql("UPDATE vales_a_cobrar SET importe = 0 WHERE id = %s", (vale_id,))


def test_un_vale_de_devolucion_que_SALIO_o_con_la_devolucion_ANULADA_no_se_corrige(base):
    d, sql = base
    _dev, cobrado = _vale_de_devolucion(d)
    d.registrar_salida_de_vale(cobrado, "cobrado", date(2026, 11, 1), sector="administracion", hoy=HOY,
                               importe_cobrado=2000.0)
    fecha = d.vale_a_cobrar(cobrado, HOY)["fecha"]
    with pytest.raises(d.ValeNoSeCorrige, match="salió"):
        d.corregir_vale(cobrado, importe=2100.0, numero=None, fecha=fecha, hoy=HOY)
    assert d.correcciones_del_vale(cobrado) == []
    dev, anulado = _vale_de_devolucion(d)
    d.anular_devolucion_vacios(dev)
    with pytest.raises(d.ValeNoSeCorrige, match="anulada"):
        d.corregir_vale(anulado, importe=2100.0, numero=None, fecha=fecha, hoy=HOY)


def test_la_PANTALLA_corrige_un_vale_de_devolucion_SIN_selector_de_proveedor(base, monkeypatch):
    from unittest.mock import patch
    d, _ = base
    _dev, vale_id = _vale_de_devolucion(d)
    fecha = d.vale_a_cobrar(vale_id, HOY)["fecha"]
    gerencia = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=HOY):
        marcado = _marcado(gerencia.get(f"/gerencia/vales/{vale_id}"))
        assert f'action="/gerencia/vales/{vale_id}/corregir"' in marcado
        assert 'name="proveedor_id"' not in marcado and "(el de la devolución)" in marcado
        assert "/corregir" not in _marcado(_cliente(monkeypatch, "administracion").get(
            f"/administracion/vales/{vale_id}"))
        respuesta = gerencia.post(f"/gerencia/vales/{vale_id}/corregir", follow_redirects=False,
                                  data={"fecha": fecha.isoformat(), "importe": "2.300", "numero": "P-9"})
        assert respuesta.status_code == 303
        marcado = _marcado(gerencia.get(f"/gerencia/vales/{vale_id}"))
    assert d.vale_a_cobrar(vale_id, HOY)["importe"] == 2300.0
    assert "cargada por $2.000" in marcado and "Corrigió importe" in marcado


# --- las fotos ---------------------------------------------------------------

def _registro(sql, ruta):
    return sql("SELECT b.como, f.como, f.tipo, f.cantidad FROM fotos_borradas_por_antiguedad b "
               "JOIN fotos_borrados f ON f.id = b.borrado_id WHERE b.foto_ruta = %s", (ruta,))


def test_GERENCIA_borra_la_foto_ORIGINAL_y_una_ANEXADA_aunque_el_vale_haya_SALIDO(base):
    d, sql = base
    _dev, vale_id = _vale_de_devolucion(d)
    d.anexar_fotos_al_vale(vale_id, ["2026-10-02/anexada.jpg"], sector="administracion")
    d.registrar_salida_de_vale(vale_id, "cobrado", date(2026, 11, 1), sector="administracion", hoy=HOY,
                               importe_cobrado=2000.0)
    assert d.vale_a_cobrar(vale_id, HOY)["fotos"] == 2
    borrados = []
    (anexada,) = [f["id"] for f in d.fotos_del_vale(vale_id) if f["id"] is not None]
    d.borrar_foto_del_vale(vale_id, anexada, borrados.append, hoy=HOY)
    d.borrar_foto_del_vale(vale_id, None, borrados.append, hoy=HOY)
    assert borrados == ["2026-10-02/anexada.jpg", "2026-09-30/vale.jpg"]
    assert _registro(sql, "2026-10-02/anexada.jpg") == [("a_mano", "a_mano", "vale", 1)]
    assert _registro(sql, "2026-09-30/vale.jpg") == [("a_mano", "a_mano", "vacios", 1)]
    assert [f["borrada_el"] is not None for f in d.fotos_del_vale(vale_id)] == [True, True]
    assert d.vale_a_cobrar(vale_id, HOY)["fotos"] == 0                          # el listado lo marca
    with pytest.raises(ValueError, match="ya estaba borrada"):
        d.borrar_foto_del_vale(vale_id, None, borrados.append, hoy=HOY)
    with pytest.raises(ValueError, match="no es de este vale"):
        d.borrar_foto_del_vale(vale_id, 999999, borrados.append, hoy=HOY)


def test_si_el_STORAGE_falla_la_foto_queda_como_estaba_y_sin_historial(base):
    d, sql = base
    _dev, vale_id = _vale_de_devolucion(d)

    def falla(_ruta):
        raise RuntimeError("storage caído")
    with pytest.raises(RuntimeError):
        d.borrar_foto_del_vale(vale_id, None, falla, hoy=HOY)
    assert sql("SELECT count(*) FROM fotos_borradas_por_antiguedad")[0][0] == 0
    assert sql("SELECT count(*) FROM fotos_borrados")[0][0] == 0


def test_la_PANTALLA_reemplaza_y_borra_solo_desde_GERENCIA_con_confirmacion(base, monkeypatch):
    from unittest.mock import patch
    d, sql = base
    vale_id = _cargar(d)
    d.anexar_fotos_al_vale(vale_id, ["2026-10-02/vieja.jpg"], sector="gerencia")
    (vieja,) = [f["id"] for f in d.fotos_del_vale(vale_id)]
    gerencia = _cliente(monkeypatch, "gerencia")
    borrados = []
    with patch("app.main._hoy_argentina", return_value=HOY), \
            patch("app.main.borrar_foto_comanda", side_effect=borrados.append), \
            patch("app.main.subir_foto_comanda", return_value="2026-10-02/nueva.jpg"), \
            patch("app.main._comprimir_foto_jpeg", return_value=b"jpg"):
        marcado = _marcado(gerencia.get(f"/gerencia/vales/{vale_id}"))
        assert marcado.count('action="/gerencia/vales/%d/fotos/borrar"' % vale_id) == 1
        assert "fotos/borrar" not in _marcado(_cliente(monkeypatch, "administracion").get(
            f"/administracion/vales/{vale_id}"))
        sin_tilde = gerencia.post(f"/gerencia/vales/{vale_id}/fotos/borrar", data={"foto": str(vieja)})
        assert sin_tilde.status_code == 400 and borrados == []
        respuesta = gerencia.post(f"/gerencia/vales/{vale_id}/fotos/reemplazar", data={"foto": str(vieja)},
                                  files={"nueva": ("n.jpg", b"crudo", "image/jpeg")}, follow_redirects=False)
        assert respuesta.status_code == 303
    assert borrados == ["2026-10-02/vieja.jpg"]
    fotos = d.fotos_del_vale(vale_id)
    assert [(f["ruta"], f["borrada_el"] is not None) for f in fotos] == [
        ("2026-10-02/vieja.jpg", True), ("2026-10-02/nueva.jpg", False)]
    assert _registro(sql, "2026-10-02/vieja.jpg")[0][0] == "a_mano"
    for ruta in ("/administracion/vales/%d/fotos/borrar", "/administracion/vales/%d/fotos/reemplazar"):
        assert _cliente(monkeypatch, "administracion").post(ruta % vale_id, data={}).status_code in (404, 405)
