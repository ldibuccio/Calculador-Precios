-- Verificación de la foto del stock. SE CORRE APARTE del bloque.
-- Tiene que dar: listados_compra_7_foto_del_stock · 1 · 1 · 1 · 1 · <listados> · <fecha>.
-- No nombra columnas nuevas en un FROM: corrida antes del bloque da ceros
-- en vez de un error.
select 'listados_compra_7_foto_del_stock' as QUE_MIGRACION,
       (select count(*) from information_schema.columns
         where table_schema = 'public' and table_name = 'listados_compra'
           and column_name = 'generado_el') as columna_de_1,
       (select count(*) from information_schema.tables
         where table_schema = 'public' and table_name = 'listados_compra_foto') as foto_de_1,
       (select count(*) from information_schema.tables
         where table_schema = 'public'
           and table_name = 'listados_compra_foto_cajas') as foto_cajas_de_1,
       -- POR COMPORTAMIENTO y no por nombre: la FK a la ficha tiene que ser
       -- NO ACTION ('a'), como las demás que apuntan a fichas. Borrar una
       -- ficha no puede cambiar lo que un listado dice que había.
       (select count(*) from pg_constraint
         where conrelid = to_regclass('public.listados_compra_foto_cajas')
           and contype = 'f' and confrelid = 'public.fichas_logistica'::regclass
           and confdeltype = 'a') as fk_ficha_no_action_de_1,
       (select count(*) from listados_compra) as POBLACION_listados,
       (select max(fecha_operacion) from pedidos) as testigo_ultimo_pedido;
