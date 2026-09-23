-- Verificación del margen por carga. SE CORRE APARTE del bloque.
-- Tiene que dar: 1 · 1 · 1 · 0 · <cargas> · <fecha>.
select 'cargas_compra_margen' as QUE_MIGRACION,
       (select count(*) from information_schema.columns
         where table_schema = 'public' and table_name = 'cargas_compra'
           and column_name = 'margen_porcentaje') as columna_de_1,
       (select count(*) from pg_constraint
         where conname = 'cargas_compra_margen_check') as guarda_de_1,
       -- El NOT NULL existe en los dos estados y lo que cambia es el
       -- COMPORTAMIENTO: un conteo de la columna da 1 con y sin él.
       (select count(*) from information_schema.columns
         where table_schema = 'public' and table_name = 'cargas_compra'
           and column_name = 'margen_porcentaje'
           and is_nullable = 'NO') as NOT_NULL_de_1,
       (select count(*) from cargas_compra
         where margen_porcentaje is distinct from 0) as con_margen_ya_puesto,
       (select count(*) from cargas_compra) as POBLACION_cargas,
       (select max(fecha_operacion) from pedidos) as testigo_ultimo_pedido;
