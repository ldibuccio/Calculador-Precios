-- Verificacion de fotos_6 a fotos_8. SE CORRE APARTE de los do: pegada a un
-- do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
select 'fotos_plazos' as QUE_MIGRACION,
       (select count(*) from pg_class
         where relname in ('fotos_plazos', 'fotos_borrados') and relkind = 'r') as tablas_de_2,
       (select count(*) from information_schema.columns
         where table_name = 'fotos_borradas_por_antiguedad'
           and column_name in ('como', 'borrado_id')) as columnas_de_2,
       (select count(*) from pg_constraint where conname = 'fotos_borradas_como') as check_de_1,
       (select count(*) from fotos_borradas_por_antiguedad where como is null) as sin_como_en_0,
       (select count(*) from fotos_plazos) as plazos_cargados_en_0,
       (select count(*) from fotos_borradas_por_antiguedad) as POBLACION_borradas,
       (select max(creado_en)::date from fotos_recepcion) as testigo_ultima_foto;
