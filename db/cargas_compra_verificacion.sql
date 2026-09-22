-- Verificación de los dos bloques de cargas_compra.
-- SE CORRE APARTE, después de los dos: pegada a un `do` el editor se queda
-- con la última y el bloque NO SE EJECUTA, sin error y con "no rows".
-- Tiene que dar: 3 · 2 · 1 · 2 · 3 · <clientes> · <fecha>.
select 'cargas_compra' as QUE_MIGRACION,
       (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = 'public'
           and c.relname in ('cargas_compra', 'cargas_compra_renglones',
                             'listados_compra_cargas')) as tablas_de_3,
       (select count(*) from pg_constraint
         where conname in ('cargas_compra_modo_check',
                           'cargas_compra_renglones_total_check')) as guardas_de_2,
       -- Se cuenta por COLUMNAS y no por nombre: el unique va inline y el
       -- nombre lo pone Postgres. contype 'u' deja afuera la PK.
       (select count(*) from pg_constraint
         where contype = 'u'
           and conrelid = to_regclass('public.cargas_compra')) as un_cliente_una_fecha_de_1,
       -- Las FK existen en los dos estados y lo que cambia es el
       -- COMPORTAMIENTO, así que un conteo por nombre daría lo mismo con el
       -- cascade puesto y sin poner. 'c' = cascade, 'a' = no action.
       (select count(*) from pg_constraint
         where contype = 'f' and confdeltype = 'c'
           and conrelid in (to_regclass('public.cargas_compra_renglones'),
                            to_regclass('public.listados_compra_cargas'))) as CASCADAS_de_2,
       (select count(*) from pg_constraint
         where contype = 'f' and confdeltype = 'a'
           and conrelid in (to_regclass('public.cargas_compra'),
                            to_regclass('public.cargas_compra_renglones'),
                            to_regclass('public.listados_compra_cargas'))) as SIN_cascada_de_3,
       (select count(*) from clientes) as POBLACION_clientes,
       (select max(fecha_operacion) from pedidos) as testigo_ultimo_pedido;
