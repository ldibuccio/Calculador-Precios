-- Verificación de los cuatro bloques de listados_compra.
-- SE CORRE APARTE, después de los cuatro: pegada a un `do` el editor se queda
-- con la última y el bloque NO SE EJECUTA, sin error y con "no rows".
-- Tiene que dar: 4 · 5 · 1 · <listados> · <clientes> · <fecha>.
select 'listados_compra' as QUE_MIGRACION,
       (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = 'public'
           and c.relname in ('listados_compra', 'listados_compra_clientes',
                             'listados_compra_kilaje', 'listados_compra_manual')) as tablas_de_4,
       (select count(*) from pg_constraint
         where conname in ('listados_compra_estado_check', 'listados_compra_margen_check',
                           'listados_compra_clientes_modo_check',
                           'listados_compra_kilaje_positivo_check',
                           'listados_compra_manual_total_check')) as guardas_de_5,
       (select count(*) from pg_class where relname = 'listados_compra_un_borrador_por_dia_idx') as indice_de_1,
       (select count(*) from listados_compra) as listados_ya_cargados,
       (select count(*) from clientes) as POBLACION_clientes,
       (select max(fecha_operacion) from pedidos) as testigo_ultimo_pedido;
