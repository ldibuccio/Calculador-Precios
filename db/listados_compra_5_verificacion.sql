-- Verificación de listados_compra_5_margen_opcional. SE CORRE APARTE.
-- Tiene que dar: 1 · 1 · <listados> · <fecha>.
select 'listados_compra_5_margen_opcional' as QUE_MIGRACION,
       (select count(*) from information_schema.columns
         where table_schema = 'public' and table_name = 'listados_compra'
           and column_name = 'margen_porcentaje') as columna_de_1,
       -- El NOT NULL existe o no y la columna está en los dos estados: se
       -- cuenta el COMPORTAMIENTO. Antes de correr da 0; después, 1.
       (select count(*) from information_schema.columns
         where table_schema = 'public' and table_name = 'listados_compra'
           and column_name = 'margen_porcentaje'
           and is_nullable = 'YES') as ACEPTA_NULL_de_1,
       (select count(*) from listados_compra) as POBLACION_listados,
       (select max(fecha_operacion) from pedidos) as testigo_ultimo_pedido;
