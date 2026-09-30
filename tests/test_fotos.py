"""FOTOS (dueño, 30/09), contra Postgres: anexar en vales y la regla de 3 años.

- Un vale suma fotos en cualquier estado, desde Administración o Gerencia, y
  ninguna se borra.
- La foto de una DEVOLUCIÓN de mercadería no se borra desde el detalle de la
  compra (la de una pesada sí: es error de carga).
- Borrar una compra no borra sus fotos de pesada: pasan a
  fotos_de_compras_borradas y el archivo queda.
- Una foto de respaldo se borra recién con más de 3 años desde que se SUBIÓ,
  desde Gerencia, y queda el registro. "Ver foto" lo dice.

Corre contra el esquema real (corolario 89). Los nombres son de EJEMPLO y las
fechas, lejos de la real, para que nada dependa del reloj (corolario 95).

  proveedor 1  EJ Uno  N93P01
  compra 21    recepcionada, con una foto de pesada
  compra 22    PENDIENTE, del 2026-09-06, con una foto de pesada
"""
import ast
import io
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"

SIEMBRA = """
insert into articulos (id, nombre) overriding system value values (1, 'EJEMPLO Fruta');
insert into proveedores (id, nombre, codigo_puesto) overriding system value
  values (1, 'EJ Uno', 'N93P01');
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado, procesada_el,
                     cantidad_cajones_real, contenido_por_cajon_real)
  overriding system value values
  (21, 1, 1, '2026-09-05', 10, 16, 160, 100, 'recepcionado', '2026-09-05 18:00-03', 10, 16);
insert into compras (id, proveedor_id, articulo_id, fecha_operacion, cantidad_cajones,
                     contenido_por_cajon, cantidad_kilos, importe, estado)
  overriding system value values (22, 1, 1, '2026-09-06', 5, 16, 80, 100, 'pendiente');
insert into fotos_recepcion (compra_id, foto_ruta, creado_en)
  values (21, 'pesaje/EJ-21.jpg', '2026-09-05 18:01-03'),
         (22, 'pesaje/EJ-22.jpg', '2026-09-06 10:00-03');
insert into vales_a_cobrar (id, origen, proveedor_id, fecha, importe, foto_ruta) overriding system value
  values (1, 'anterior_al_sistema', 1, '2026-08-01', 1000, 'vales/EJ-papel.jpg'),
         (2, 'anterior_al_sistema', 1, '2026-08-02', 2000, null);
"""

HOY = date(2026, 12, 1)
ARG = timezone(timedelta(hours=-3))


@pytest.fixture
def base(monkeypatch):
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: las fotos no se verificaron")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    with conexion.cursor() as cursor:
        cursor.execute(SIEMBRA)
    conexion.commit()
    conexion.close()
    monkeypatch.setenv("DATABASE_URL", url)
    import app.db as d

    def sql(consulta, parametros=None):
        conexion = d.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(consulta, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conexion.commit()
            return filas
        finally:
            conexion.close()
    return d, sql


def _cliente(monkeypatch, *sectores):
    from fastapi.testclient import TestClient
    from app.main import PUERTA_ADMINISTRACION, PUERTA_COMPRAS, PUERTA_GERENCIA, app
    cliente = TestClient(app, base_url="https://testserver")
    for puerta in (PUERTA_ADMINISTRACION, PUERTA_GERENCIA, PUERTA_COMPRAS):
        if puerta.sector in sectores:
            monkeypatch.setenv(puerta.env_var, f"clave-{puerta.sector}")
            cliente.cookies.set(puerta.cookie, puerta.firma(f"clave-{puerta.sector}"))
    return cliente


def _marcado(respuesta):
    return respuesta.text.split("</style>")[-1]


def _jpeg():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color="red").save(buffer, format="JPEG")
    return buffer.getvalue()


def _subidas():
    """subir_foto_comanda falso: rutas previsibles, y cuántas se subieron."""
    rutas = []

    def subir(_bytes, nombre, prefijo):
        rutas.append(f"{prefijo}/EJ-{nombre}-{len(rutas)}.jpg")
        return rutas[-1]
    return rutas, subir


# --- 1. anexar fotos a un vale ----------------------------------------------

def test_ADMINISTRACION_anexa_VARIAS_fotos_y_el_detalle_las_muestra_en_orden_con_su_origen(base, monkeypatch):
    d, sql = base
    rutas, subir = _subidas()
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main._hoy_argentina", return_value=HOY), patch("app.main.subir_foto_comanda", side_effect=subir):
        respuesta = cliente.post("/administracion/vales/1/fotos",
                                 files=[("fotos", ("a.jpg", _jpeg(), "image/jpeg")),
                                        ("fotos", ("b.jpg", _jpeg(), "image/jpeg"))],
                                 follow_redirects=False)
        detalle = cliente.get("/administracion/vales/1")
        listado = cliente.get("/administracion/vales?estado=todos")
    assert respuesta.status_code == 303 and "#fotos" in respuesta.headers["location"]
    assert len(rutas) == 2 and all(r.startswith("vales/") for r in rutas)
    assert sql("SELECT foto_ruta, sector FROM vales_a_cobrar_fotos ORDER BY id") == [
        (rutas[0], "administracion"), (rutas[1], "administracion")]
    fotos = d.fotos_del_vale(1)
    assert [f["que"] for f in fotos] == ["papel", "anexada", "anexada"]
    marcado = _marcado(detalle)
    assert "Fotos (3)" in marcado
    assert "Foto del vale en papel (cargado el" in marcado
    assert marcado.count("desde Administración") == 2
    assert re.search(r"Anexada el \d\d/\d\d \d\d:\d\d desde Administración", marcado)
    # El listado dice cuántas tiene cada uno, y marca el que no tiene ninguna.
    marcado = _marcado(listado)
    assert "3 fotos" in marcado
    assert '<span class="sin-foto">sin foto</span>' in marcado


def test_se_anexa_en_CUALQUIER_estado_y_desde_GERENCIA_queda_su_sector(base, monkeypatch):
    d, sql = base
    d.registrar_salida_de_vale(2, "anulado", date(2026, 11, 30), sector="gerencia", hoy=HOY, motivo="EJ")
    rutas, subir = _subidas()
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=HOY), patch("app.main.subir_foto_comanda", side_effect=subir):
        respuesta = cliente.post("/gerencia/vales/2/fotos", files=[("fotos", ("a.jpg", _jpeg(), "image/jpeg"))],
                                 follow_redirects=False)
        detalle = cliente.get("/gerencia/vales/2")
    assert respuesta.status_code == 303
    assert sql("SELECT sector FROM vales_a_cobrar_fotos") == [("gerencia",)]
    assert "desde Gerencia" in _marcado(detalle)
    assert 'action="/gerencia/vales/2/fotos"' in _marcado(detalle)


def test_GERENCIA_sin_su_clave_no_anexa(base, monkeypatch):
    d, sql = base
    monkeypatch.setenv("CLAVE_GERENCIA", "clave-gerencia")
    cliente = _cliente(monkeypatch)
    with patch("app.main.subir_foto_comanda") as subir:
        respuesta = cliente.post("/gerencia/vales/1/fotos", files=[("fotos", ("a.jpg", _jpeg(), "image/jpeg"))],
                                 follow_redirects=False)
    assert respuesta.status_code != 303 or "clave" in respuesta.headers.get("location", "")
    subir.assert_not_called()
    assert sql("SELECT count(*) FROM vales_a_cobrar_fotos") == [(0,)]


def test_un_archivo_que_NO_es_foto_frena_TODO_antes_de_subir(base, monkeypatch):
    d, sql = base
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main._hoy_argentina", return_value=HOY), patch("app.main.subir_foto_comanda") as subir:
        respuesta = cliente.post("/administracion/vales/1/fotos",
                                 files=[("fotos", ("a.jpg", _jpeg(), "image/jpeg")),
                                        ("fotos", ("b.txt", b"no soy una foto", "text/plain"))])
    assert respuesta.status_code == 400 and "no es una foto" in respuesta.text
    subir.assert_not_called()
    assert sql("SELECT count(*) FROM vales_a_cobrar_fotos") == [(0,)]


def test_si_la_BASE_rebota_se_borra_del_Storage_lo_que_ya_se_subio(base, monkeypatch):
    d, sql = base
    rutas, subir = _subidas()
    cliente = _cliente(monkeypatch, "administracion")
    with (patch("app.main._hoy_argentina", return_value=HOY),
          patch("app.main.subir_foto_comanda", side_effect=subir),
          patch("app.main.anexar_fotos_al_vale", side_effect=RuntimeError("se cayó la base")),
          patch("app.main.borrar_foto_comanda") as borrar):
        respuesta = cliente.post("/administracion/vales/1/fotos",
                                 files=[("fotos", ("a.jpg", _jpeg(), "image/jpeg")),
                                        ("fotos", ("b.jpg", _jpeg(), "image/jpeg"))])
    assert respuesta.status_code == 500
    assert sorted(c.args[0] for c in borrar.call_args_list) == sorted(rutas)


def test_anexar_a_un_vale_que_no_existe_no_escribe_nada(base):
    d, sql = base
    with pytest.raises(ValueError, match="no existe"):
        d.anexar_fotos_al_vale(999, ["vales/EJ.jpg"], sector="administracion")
    assert sql("SELECT count(*) FROM vales_a_cobrar_fotos") == [(0,)]


def test_la_foto_anexada_se_ve_por_SU_vale_y_un_id_ajeno_es_404(base, monkeypatch):
    d, sql = base
    d.anexar_fotos_al_vale(1, ["vales/EJ-a.jpg"], sector="administracion")
    (fid,), = sql("SELECT id FROM vales_a_cobrar_fotos")
    cliente = _cliente(monkeypatch, "administracion")
    with patch("app.main.obtener_url_foto", return_value="https://storage.example/firmada"):
        buena = cliente.get(f"/administracion/vales/1/fotos/{fid}/ver", follow_redirects=False)
        ajena = cliente.get(f"/administracion/vales/2/fotos/{fid}/ver", follow_redirects=False)
    assert buena.status_code == 303 and buena.headers["location"] == "https://storage.example/firmada"
    assert ajena.status_code == 404


def test_NINGUNA_pantalla_borra_una_foto_de_un_vale():
    """Ni la original ni las anexadas (dueño, 30/09). Se mira el CÓDIGO: una
    ruta de borrar o un DELETE sobre la tabla no puede existir."""
    from app.main import app
    for ruta in app.routes:
        if "/vales/" in getattr(ruta, "path", ""):
            assert "borrar" not in ruta.path, ruta.path
    for archivo in ("app/main.py", "app/db.py"):
        texto = io.open(os.path.join(RAIZ, archivo), encoding="utf-8").read()
        assert not re.search(r"DELETE\s+FROM\s+vales_a_cobrar_fotos", texto, re.I), archivo
        assert not re.search(r"UPDATE\s+vales_a_cobrar\b[^;]*foto_ruta", texto, re.I), archivo


# --- 2. la foto de una devolución de mercadería no se borra -------------------

def test_la_foto_de_una_DEVOLUCION_queda_marcada_y_NO_se_borra_la_de_la_pesada_SI(base, monkeypatch):
    d, sql = base
    mov = d.crear_devolucion_deposito(21, 2, "EJ motivo", date(2026, 11, 30), fotos_pesada=["pesaje/EJ-dev.jpg"])
    (fid_dev,), = sql("SELECT id FROM fotos_recepcion WHERE foto_ruta = 'pesaje/EJ-dev.jpg'")
    assert sql("SELECT movimiento_id FROM fotos_recepcion WHERE id = %s", (fid_dev,)) == [(mov,)]
    # la de la devolución: la escritura la rechaza
    assert d.borrar_foto_recepcion(21, fid_dev) is None
    assert sql("SELECT count(*) FROM fotos_recepcion WHERE id = %s", (fid_dev,)) == [(1,)]
    # el rival: la pesada de la MISMA compra sí se borra (error de carga)
    (fid_pes,), = sql("SELECT id FROM fotos_recepcion WHERE foto_ruta = 'pesaje/EJ-21.jpg'")
    assert d.borrar_foto_recepcion(21, fid_pes) == "pesaje/EJ-21.jpg"


def test_el_DETALLE_no_ofrece_borrar_la_foto_de_la_devolucion(base, monkeypatch):
    d, sql = base
    d.crear_devolucion_deposito(21, 2, "EJ motivo", date(2026, 11, 30), fotos_pesada=["pesaje/EJ-dev.jpg"])
    (fid_dev,), = sql("SELECT id FROM fotos_recepcion WHERE foto_ruta = 'pesaje/EJ-dev.jpg'")
    (fid_pes,), = sql("SELECT id FROM fotos_recepcion WHERE foto_ruta = 'pesaje/EJ-21.jpg'")
    cliente = _cliente(monkeypatch, "compras")
    with patch("app.main._hoy_argentina", return_value=HOY):
        detalle = cliente.get("/compras/21/detalle")
        post = cliente.post(f"/compras/21/fotos-balanza/{fid_dev}/borrar", follow_redirects=False)
    marcado = _marcado(detalle)
    assert detalle.status_code == 200
    assert f"/fotos-balanza/{fid_pes}/borrar" in marcado
    assert f"/fotos-balanza/{fid_dev}/borrar" not in marcado
    assert "De la devolución al proveedor" in marcado
    assert post.status_code == 404
    assert sql("SELECT count(*) FROM fotos_recepcion WHERE id = %s", (fid_dev,)) == [(1,)]


def test_la_migracion_MARCA_las_fotos_de_devolucion_que_ya_estaban(base):
    """fotos_2 corrido sobre una base sin la columna: la foto con "/devolucion-"
    va a la devolución de SU compra; la pesada queda en NULL."""
    d, sql = base
    sql("INSERT INTO movimientos_stock (articulo_id, tipo, cantidad, motivo, fecha_operacion, "
        "stock_sistema, compra_devolucion_id, creado_en) "
        "VALUES (1, 'devolucion_deposito', -2, 'EJ', '2026-11-30', 10, 21, '2026-11-30 10:00-03')")
    sql("ALTER TABLE fotos_recepcion DROP COLUMN movimiento_id")
    sql("INSERT INTO fotos_recepcion (compra_id, foto_ruta, creado_en) "
        "VALUES (21, 'pesaje/2026-11-30/devolucion-21-1-ab.jpg', '2026-11-30 10:00-03')")
    migracion = io.open(os.path.join(RAIZ, "db/fotos_2_foto_de_la_devolucion.sql"), encoding="utf-8").read()
    sql(migracion)
    marcadas = sql("SELECT foto_ruta, movimiento_id IS NOT NULL FROM fotos_recepcion ORDER BY foto_ruta")
    assert marcadas == [("pesaje/2026-11-30/devolucion-21-1-ab.jpg", True),
                        ("pesaje/EJ-21.jpg", False), ("pesaje/EJ-22.jpg", False)]
    with pytest.raises(Exception, match="ya corrio"):
        sql(migracion)


# --- 3. borrar una compra no borra sus fotos de pesada ------------------------

def test_borrar_una_compra_FORZADO_guarda_su_foto_y_NO_la_saca_del_Storage(base, monkeypatch):
    d, sql = base
    cliente = _cliente(monkeypatch, "gerencia")
    with patch("app.main._hoy_argentina", return_value=HOY), patch("app.main.borrar_foto_comanda") as borrar:
        rutas = d.eliminar_compra(21, forzar=True, origen="gerencia")
    assert rutas == []
    borrar.assert_not_called()
    assert sql("SELECT compra_id, foto_ruta, subida_el FROM fotos_de_compras_borradas") == [
        (21, "pesaje/EJ-21.jpg", datetime(2026, 9, 5, 21, 1, tzinfo=timezone.utc))]
    assert sql("SELECT count(*) FROM compras WHERE id = 21") == [(0,)]
    with patch("app.main._hoy_argentina", return_value=HOY):
        pantalla = cliente.get("/gerencia/fotos")
    marcado = _marcado(pantalla)
    assert "De la compra N° 21, borrada el" in marcado
    (fid,), = sql("SELECT id FROM fotos_de_compras_borradas")
    assert f'href="/gerencia/fotos/compras-borradas/{fid}/ver"' in marcado


def test_el_CANCELAR_DEL_DIA_tambien_guarda_las_fotos(base):
    d, sql = base
    resultado = d.eliminar_compras_del_dia_por_proveedor(date(2026, 9, 6), 1)
    assert resultado["borradas"] == 1 and resultado["rutas_a_borrar"] == []
    assert sql("SELECT compra_id, foto_ruta FROM fotos_de_compras_borradas") == [(22, "pesaje/EJ-22.jpg")]


def test_si_la_compra_NO_se_puede_borrar_la_foto_queda_donde_estaba(base):
    d, sql = base
    with pytest.raises(ValueError):
        d.eliminar_compra(21, origen="compras")          # recepcionada, sin forzar
    assert sql("SELECT count(*) FROM fotos_recepcion WHERE compra_id = 21") == [(1,)]
    assert sql("SELECT count(*) FROM fotos_de_compras_borradas") == [(0,)]


# --- 4. la regla de 3 años ----------------------------------------------------

TABLAS_CON_FOTO = {
    # tabla con una columna foto_ruta -> el tipo con que entra a la regla
    "fotos_guia": "comanda", "fotos_recepcion": "pesada", "fotos_de_compras_borradas": "compra_borrada",
    "fotos_pedido": "pedido", "precios_venta_historial": "precios", "fotos_merma": "merma",
    "vacios_deposito_devoluciones": "vacios", "vales_a_cobrar": "vale", "vales_a_cobrar_fotos": "vale",
    # no es una foto: es el registro de las borradas
    "fotos_borradas_por_antiguedad": None,
}


def test_TODA_tabla_con_foto_entra_en_la_regla_de_3_anios():
    """El conjunto ENCONTRADO en el esquema contra el DECIDIDO (corolario 60):
    una tabla nueva que guarde fotos y no entre a _SQL_FOTOS_DE_RESPALDO deja
    archivos que no vencen nunca y aparecen como "sin registro"."""
    from app.db import _SQL_FOTOS_DE_RESPALDO
    esquema = io.open(os.path.join(RAIZ, "db/esquema_completo.sql"), encoding="utf-8").read()
    encontradas = set()
    for tabla, cuerpo in re.findall(r"^create table (\w+) \((.*?)^\);", esquema, re.S | re.M):
        if re.search(r"^\s*(foto_ruta|foto)\s+text", cuerpo, re.M):
            encontradas.add(tabla)
    assert encontradas == set(TABLAS_CON_FOTO), encontradas ^ set(TABLAS_CON_FOTO)
    for tabla, tipo in TABLAS_CON_FOTO.items():
        if tipo is not None:
            assert re.search(rf"FROM {tabla}\b", _SQL_FOTOS_DE_RESPALDO), tabla


def test_los_NUEVE_tipos_salen_de_la_consulta_y_tienen_su_nombre(base):
    d, sql = base
    from core.fotos import TEXTO_DEL_TIPO
    d.crear_devolucion_deposito(21, 2, "EJ", date(2026, 11, 30), fotos_pesada=["pesaje/EJ-dev.jpg"])
    d.anexar_fotos_al_vale(1, ["vales/EJ-anexada.jpg"], sector="administracion")
    sql("""
      insert into guias_compra (id, proveedor_id, fecha_operacion) overriding system value values (1, 1, '2026-09-05');
      insert into fotos_guia (guia_id, foto_ruta) values (1, 'comanda/EJ.jpg');
      insert into fotos_de_compras_borradas (compra_id, foto_ruta, subida_el) values (99, 'pesaje/EJ-b.jpg', now());
      insert into clientes (id, nombre) overriding system value values (1, 'EJ Cliente');
      insert into pedidos (id, cliente_id, fecha_operacion, origen) overriding system value values (1, 1, '2026-09-05', 'texto');
      insert into fotos_pedido (pedido_id, foto_ruta) values (1, 'pedido/EJ.jpg');
      insert into precios_venta_historial (articulo_id, cliente_id, precio, vigente_desde, foto_ruta)
        values (1, 1, 10, '2026-09-05', 'precios/EJ.pdf');
      insert into movimientos_stock (id, articulo_id, tipo, cantidad, motivo, fecha_operacion, stock_sistema)
        overriding system value values (500, 1, 'merma', -1, 'EJ', '2026-09-05', 10);
      insert into fotos_merma (movimiento_id, foto_ruta) values (500, 'merma/EJ.jpg');
      insert into vacios_deposito_devoluciones (proveedor_id, cantidad, stock_sistema, foto_ruta)
        values (1, 1, 1, 'vacios/EJ.jpg');
    """)
    tipos = {f["tipo"] for f in d.fotos_de_respaldo()}
    assert tipos == set(TEXTO_DEL_TIPO), tipos ^ set(TEXTO_DEL_TIPO)


def _foto_vieja(sql, dias_de_mas):
    """La pesada de la compra 21, subida 3 años (y `dias_de_mas`) antes de HOY."""
    subida = datetime(HOY.year - 3, HOY.month, HOY.day, 12, 0, tzinfo=ARG) - timedelta(days=dias_de_mas)
    sql("UPDATE fotos_recepcion SET creado_en = %s WHERE compra_id = 21", (subida,))


def test_se_cuenta_desde_que_se_SUBIO_y_el_dia_del_corte_TODAVIA_no_vence(base):
    d, sql = base
    from core.fotos import corte_de_respaldo, fotos_para_borrar
    corte = corte_de_respaldo(HOY)
    _foto_vieja(sql, 0)                                   # justo 3 años: todavía no
    assert fotos_para_borrar(d.fotos_de_respaldo(), corte) == []
    _foto_vieja(sql, 1)                                   # un día más: sí
    assert [f["ruta"] for f in fotos_para_borrar(d.fotos_de_respaldo(), corte)] == ["pesaje/EJ-21.jpg"]
    # La fecha de la COMPRA no cuenta: la 22 es de 2026 pero su foto también
    # se subió en 2026, así que no vence aunque se mueva la compra.
    sql("UPDATE compras SET fecha_operacion = '2020-01-01' WHERE id = 22")
    assert [f["ruta"] for f in fotos_para_borrar(d.fotos_de_respaldo(), corte)] == ["pesaje/EJ-21.jpg"]


def test_GERENCIA_borra_con_el_TILDE_deja_el_REGISTRO_y_la_fila_queda(base, monkeypatch):
    d, sql = base
    _foto_vieja(sql, 10)
    cliente = _cliente(monkeypatch, "gerencia")
    with (patch("app.main._hoy_argentina", return_value=HOY),
          patch("app.main.tamanos_del_bucket", return_value={"pesaje/EJ-21.jpg": 5000, "suelto/EJ.jpg": 700}),
          patch("app.main.borrar_foto_comanda") as borrar):
        pantalla = cliente.get("/gerencia/fotos")
        sin_tilde = cliente.post("/gerencia/fotos/borrar-viejas", follow_redirects=False)
        antes = sql("SELECT count(*) FROM fotos_borradas_por_antiguedad")
        con_tilde = cliente.post("/gerencia/fotos/borrar-viejas", data={"confirmo": "si"}, follow_redirects=False)
    marcado = _marcado(pantalla)
    assert "1 foto" in marcado and "Borrar 1 foto" in marcado
    assert "1 archivo" in marcado                         # el suelto, sin registro, no se borra
    assert antes == [(0,)] and sin_tilde.status_code == 303
    assert con_tilde.status_code == 303
    borrar.assert_called_once_with("pesaje/EJ-21.jpg")
    assert sql("SELECT foto_ruta, tipo, bytes FROM fotos_borradas_por_antiguedad") == [
        ("pesaje/EJ-21.jpg", "pesada", 5000)]
    # la fila que la nombraba sigue
    assert sql("SELECT count(*) FROM fotos_recepcion WHERE foto_ruta = 'pesaje/EJ-21.jpg'") == [(1,)]
    # y una segunda vuelta no la vuelve a borrar
    with (patch("app.main._hoy_argentina", return_value=HOY),
          patch("app.main.tamanos_del_bucket", return_value={}),
          patch("app.main.borrar_foto_comanda") as borrar_otra):
        cliente.post("/gerencia/fotos/borrar-viejas", data={"confirmo": "si"}, follow_redirects=False)
    borrar_otra.assert_not_called()


def test_si_el_STORAGE_falla_no_queda_registro_y_la_foto_sigue(base, monkeypatch):
    d, sql = base
    _foto_vieja(sql, 10)
    cliente = _cliente(monkeypatch, "gerencia")
    with (patch("app.main._hoy_argentina", return_value=HOY),
          patch("app.main.tamanos_del_bucket", return_value={}),
          patch("app.main.borrar_foto_comanda", side_effect=RuntimeError("sin red"))):
        respuesta = cliente.post("/gerencia/fotos/borrar-viejas", data={"confirmo": "si"})
    assert "Se borraron 0 de 1" in respuesta.text
    assert sql("SELECT count(*) FROM fotos_borradas_por_antiguedad") == [(0,)]


def test_VER_una_foto_borrada_dice_cuando_se_borro(base, monkeypatch):
    d, sql = base
    sql("INSERT INTO fotos_borradas_por_antiguedad (foto_ruta, tipo, subida_el, borrada_el) "
        "VALUES ('pesaje/EJ-21.jpg', 'pesada', '2023-01-01', '2029-10-02 12:00-03')")
    (fid,), = sql("SELECT id FROM fotos_recepcion WHERE foto_ruta = 'pesaje/EJ-21.jpg'")
    cliente = _cliente(monkeypatch, "compras")
    with patch("app.main.obtener_url_foto") as firmar:
        respuesta = cliente.get(f"/deposito/recepcion/21/foto-balanza/{fid}/ver", follow_redirects=False)
    firmar.assert_not_called()
    assert respuesta.status_code == 200 and respuesta.headers["content-type"].startswith("image/svg+xml")
    assert "Foto borrada por antigüedad" in respuesta.text and "el 02/10/2029" in respuesta.text


def test_la_GERENCIA_sin_clave_no_ve_ni_borra(base, monkeypatch):
    d, sql = base
    _foto_vieja(sql, 10)
    monkeypatch.setenv("CLAVE_GERENCIA", "clave-gerencia")
    cliente = _cliente(monkeypatch)
    with patch("app.main.borrar_foto_comanda") as borrar:
        pantalla = cliente.get("/gerencia/fotos")
        cliente.post("/gerencia/fotos/borrar-viejas", data={"confirmo": "si"}, follow_redirects=False)
    assert 'type="password"' in pantalla.text and "Borrar 1 foto" not in pantalla.text
    borrar.assert_not_called()
    assert sql("SELECT count(*) FROM fotos_borradas_por_antiguedad") == [(0,)]


# --- 5. las piezas puras y el cableado ------------------------------------------

def test_archivos_sin_registro_son_los_que_ninguna_fila_nombra():
    from core.fotos import archivos_sin_registro
    fotos = [{"ruta": "a.jpg"}, {"ruta": "b.jpg"}]
    assert archivos_sin_registro(fotos, {"a.jpg": 10, "x.jpg": 7, "y.jpg": 3}) == {
        "cantidad": 2, "bytes": 10, "rutas": ["x.jpg", "y.jpg"]}
    assert archivos_sin_registro(fotos, None) is None     # bucket ilegible: sin dato, no cero


def test_el_corte_del_29_de_febrero():
    from core.fotos import corte_de_respaldo
    assert corte_de_respaldo(date(2028, 2, 29)) == date(2025, 2, 28)
    assert corte_de_respaldo(date(2029, 8, 15)) == date(2026, 8, 15)


def test_TODA_pantalla_que_muestra_una_foto_pasa_por_ir_a_la_foto():
    """obtener_url_foto se llama UNA vez en app/main.py: adentro de
    _ir_a_la_foto. Un "Ver foto" que la llamara directo mostraría una imagen
    rota para una foto borrada, sin decir por qué."""
    arbol = ast.parse(io.open(os.path.join(RAIZ, "app/main.py"), encoding="utf-8").read())
    llamadores = set()
    for funcion in ast.walk(arbol):
        if isinstance(funcion, ast.FunctionDef):
            for nodo in ast.walk(funcion):
                if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
                        and nodo.func.id == "obtener_url_foto"):
                    llamadores.add(funcion.name)
    assert llamadores == {"_ir_a_la_foto"}, llamadores
