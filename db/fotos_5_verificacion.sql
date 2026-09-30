-- Verificacion de fotos_1 a fotos_4. SE CORRE APARTE de los do: pegada a un
-- do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
select 'fotos' as QUE_MIGRACION,
       (select count(*) from pg_class
         where relname in ('vales_a_cobrar_fotos', 'fotos_de_compras_borradas',
                           'fotos_borradas_por_antiguedad') and relkind = 'r') as tablas_de_3,
       (select count(*) from information_schema.columns
         where table_name = 'fotos_recepcion' and column_name = 'movimiento_id') as columna_de_1,
       (select count(*) from fotos_recepcion where movimiento_id is not null) as devolucion_marcadas,
       (select count(*) from fotos_recepcion
         where foto_ruta like '%/devolucion-%' and movimiento_id is null) as devolucion_sin_marcar_en_0,
       (select count(*) from fotos_recepcion) as POBLACION_fotos_recepcion,
       (select max(procesada_el)::date from compras
         where estado = 'recepcionado') as testigo_ultima_recepcion;
