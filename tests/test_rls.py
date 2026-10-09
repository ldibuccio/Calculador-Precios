# -*- coding: utf-8 -*-
"""CANDADOS (RLS) EN TODAS LAS TABLAS (dueño, 09/10).

En Supabase, una tabla de `public` sin RLS se lee por la API con la clave
pública (anon). Desde el 09/10 TODAS tienen el candado, sin políticas para
anon, y las que se creen de acá en adelante nacen con él. Tres cosas:

  · la base de prueba (db/esquema_completo.sql, el esquema real) no tiene
    ninguna tabla sin candado;
  · el sistema sigue LEYENDO y ESCRIBIENDO con un usuario como el suyo en
    Supabase (`postgres`: con bypassrls, sin ser superusuario), y el RIVAL
    —el mismo usuario SIN bypassrls— no lee ni escribe nada: así se sabe que
    el candado está puesto de verdad y no que el test pasa por las dudas;
  · toda migración que crea una tabla le pone el candado, salvo las de antes
    del 09/10 (el conjunto ENCONTRADO contra el DECIDIDO, en las dos
    direcciones).
"""
import glob
import os
import re
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from scripts.humo import hay_postgres, preparar_base  # noqa: E402

OBLIGATORIO = os.environ.get("HUMO_OBLIGATORIO") == "1"
HOY = date(2026, 12, 1)

# Las migraciones que crearon tablas ANTES del 09/10, sin candado: su candado
# lo puso db/rls_1_*.sql. Esta lista NO CRECE: una migración nueva que crea
# una tabla lleva su `alter table ... enable row level security`.
HISTORICAS_SIN_CANDADO = {
    "panel_foto_1_tabla.sql",          # 09/10, corrió antes de esta regla: su candado lo pone rls_1
    "agregar_ajustes_vacios.sql",
    "agregar_alertas_estado.sql",
    "agregar_casilla_pedidos.sql",
    "agregar_cierre_modelo_viejo.sql",
    "agregar_condiciones_pedido.sql",
    "agregar_conversion_articulos.sql",
    "agregar_corte_y_stock_inicial.sql",
    "agregar_costos_fijos.sql",
    "agregar_disponibles.sql",
    "agregar_fotos_guia.sql",
    "agregar_fotos_recepcion.sql",
    "agregar_freno_y_desglose_reproceso.sql",
    "agregar_guia_compras.sql",
    "agregar_historial_fichas.sql",
    "agregar_lotes_elegidos_del_armado.sql",
    "agregar_merma_de_segunda_3_fotos.sql",
    "agregar_observabilidad_revision.sql",
    "agregar_operarios_deposito.sql",
    "agregar_pedidos.sql",
    "agregar_precios_venta_historial.sql",
    "agregar_proveedores_puesto.sql",
    "agregar_reprocesos.sql",
    "agregar_senas_valor_historial.sql",
    "agregar_stock_deposito.sql",
    "agregar_vacios_puesto.sql",
    "backups_1_tabla.sql",
    "cargas_compra_1_cabecera.sql",
    "cargas_compra_2_renglones_y_puente.sql",
    "cobranza_segunda_1_cobros.sql",
    "cobranza_segunda_2_historial.sql",
    "codigos_1_tabla_y_columna.sql",
    "colegas_1_la_lista.sql",
    "corte_fifo_5a_movimientos_con_piso.sql",
    "e5_6a_movimientos.sql",
    "eliminadas_1_tabla.sql",
    "envases_1_tabla_y_columnas.sql",
    "fletes_1_sucursales.sql",
    "fletes_2_catalogo.sql",
    "fletes_3_fletes.sql",
    "fletes_4_correcciones.sql",
    "fotos_1_vales_anexadas.sql",
    "fotos_3_compras_borradas.sql",
    "fotos_4_borradas_por_antiguedad.sql",
    "fotos_6_plazos.sql",
    "fotos_7_historial.sql",
    "listados_compra_1_cabecera.sql",
    "listados_compra_2_clientes.sql",
    "listados_compra_3_kilaje.sql",
    "listados_compra_4_manual.sql",
    "listados_compra_7_foto_del_stock.sql",
    "migracion_clientes_final.sql",
    "permitir_varias_fichas_por_articulo.sql",
    "remitos_1_tabla.sql",
    "remitos_2_renglones.sql",
    "remitos_3_fotos.sql",
    "remitos_4_numeros.sql",
    "retroactivo_1_clave_y_registro.sql",
    "schema.sql",
    "segunda_ajuste_1_tabla.sql",
    "tareas_1_tareas.sql",
    "tareas_2_ocurrencias.sql",
    "tareas_3_reaperturas.sql",
    "vacios_conteo_2809_1_tablas.sql",
    "vacios_deposito_1_tipo_de_cajon.sql",
    "vacios_deposito_2_devoluciones.sql",
    "vacios_deposito_3_conteos.sql",
    "vacios_foto_1_el_corte_de_hoy.sql",
    "vacios_marcas_1_marcas_y_compras.sql",
    "vacios_marcas_3_ajustes.sql",
    "vacios_marcas_4_asignaciones.sql",
    "vales_1_tabla.sql",
    "vales_2_salidas.sql",
    "vales_3_limites.sql",
    "vales_4_listado_en_papel.sql",
    "vales_manual_2_correcciones.sql",
}


def _base():
    if not hay_postgres():
        if OBLIGATORIO:
            pytest.fail("HUMO_OBLIGATORIO=1 y no hay Postgres: los candados no se verificaron")
        pytest.skip("sin Postgres local")
    url = preparar_base()
    import psycopg2
    conexion = psycopg2.connect(url)
    conexion.autocommit = True
    return url, conexion


def test_NINGUNA_tabla_de_la_base_de_prueba_queda_sin_candado():
    url, conexion = _base()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                select count(*), count(*) filter (where not c.relrowsecurity),
                       array_agg(c.relname) filter (where not c.relrowsecurity)
                  from pg_class c join pg_namespace s on s.oid = c.relnamespace
                 where s.nspname = 'public' and c.relkind = 'r'""")
            tablas, sin_candado, cuales = cursor.fetchone()
            cursor.execute("select reloptions from pg_class where oid = 'public.vales_papel_revision'::regclass")
            (opciones,) = cursor.fetchone()
    finally:
        conexion.close()
    assert tablas >= 90                                  # el denominador: se miró la base entera
    assert (sin_candado, cuales) == (0, None)
    assert "security_invoker=true" in (opciones or [])


def _rol(conexion, nombre, *, bypass):
    with conexion.cursor() as cursor:
        cursor.execute(f"drop owned by {nombre}" if _existe(cursor, nombre) else "select 1")
        cursor.execute(f"drop role if exists {nombre}")
        cursor.execute(f"create role {nombre} login password 'ejemplo' nosuperuser "
                       f"{'bypassrls' if bypass else 'nobypassrls'}")
        cursor.execute(f"grant usage on schema public to {nombre}")
        cursor.execute(f"grant all on all tables in schema public to {nombre}")
        cursor.execute(f"grant all on all sequences in schema public to {nombre}")


def _existe(cursor, nombre):
    cursor.execute("select 1 from pg_roles where rolname = %s", (nombre,))
    return cursor.fetchone() is not None


def _como(url, rol):
    """La URL de la base de prueba, entrando con `rol`."""
    resto = url.split("@", 1)[1]
    return f"postgresql://{rol}:ejemplo@{resto}"


def test_el_SISTEMA_lee_y_escribe_con_un_usuario_como_el_de_Supabase_y_el_RIVAL_no(monkeypatch):
    url, conexion = _base()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("insert into proveedores (id, nombre, codigo_puesto) overriding system value "
                           "values (1, 'EJ Uno', 'N92P01')")
            cursor.execute("insert into vales_a_cobrar (origen, proveedor_id, fecha, importe) "
                           "values ('anterior_al_sistema', 1, '2026-11-01', 1234)")
        _rol(conexion, "rls_como_postgres", bypass=True)
        _rol(conexion, "rls_sin_bypass", bypass=False)
    finally:
        conexion.close()
    import app.db as d
    import psycopg2

    monkeypatch.setenv("DATABASE_URL", _como(url, "rls_como_postgres"))
    assert d.resumen_de_la_cartera(HOY)["total"] == 1234.0           # lee
    assert len(d.listar_vales(estado=None, hoy=HOY)) == 1
    d.registrar_tick_revision()                                       # escribe
    d.guardar_estado_alerta("rls_prueba", casos=3)
    assert [f["casos"] for f in d.listar_estado_alertas() if f["codigo"] == "rls_prueba"] == [3]

    monkeypatch.setenv("DATABASE_URL", _como(url, "rls_sin_bypass"))
    assert d.listar_vales(estado=None, hoy=HOY) == []                 # el rival no ve nada...
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):        # ...ni puede escribir
        d.guardar_estado_alerta("rls_rival", casos=1)


def test_toda_MIGRACION_que_crea_una_tabla_le_pone_el_candado():
    crean = {}
    for archivo in glob.glob(os.path.join(RAIZ, "db", "*.sql")):
        texto = open(archivo, encoding="utf-8").read()
        if re.search(r"create table", texto, re.I):
            crean[os.path.basename(archivo)] = bool(re.search(r"enable row level security", texto, re.I))
    sin_candado = {nombre for nombre, tiene in crean.items() if not tiene}
    assert sin_candado - HISTORICAS_SIN_CANDADO == set(), "tabla nueva sin `enable row level security`"
    assert HISTORICAS_SIN_CANDADO - sin_candado == set(), "sacala de HISTORICAS_SIN_CANDADO"
