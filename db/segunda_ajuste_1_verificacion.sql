select 'segunda_ajuste_1' as QUE_MIGRACION,
       (select count(*) from information_schema.tables
         where table_schema = 'public' and table_name = 'ajustes_segunda') as tabla,
       (select count(*) from information_schema.columns
         where table_schema = 'public' and table_name = 'ajustes_segunda') as columnas,
       (select count(*) from pg_constraint
         where conrelid = 'ajustes_segunda'::regclass and contype = 'c') as checks,
       (select count(*) from pg_indexes where indexname = 'ajustes_segunda_articulo') as indice,
       (select count(*) from ajustes_segunda) as filas,
       (select max(fecha_operacion) from remitos_segunda) as ultimo_remito;

-- Se corre APARTE del `do`. Resultado bueno en las dos bases:
-- tabla 1 · columnas 8 · checks 2 · indice 1 · filas 0. ultimo_remito dice
-- de qué base es la fila.
