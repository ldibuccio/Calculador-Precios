select
    'eliminadas_1_tabla'                                             as QUE_MIGRACION,
    (select count(*) from pg_tables where schemaname = 'public'
       and tablename = 'compras_eliminadas')                         as tabla_de_1,
    (select count(*) from information_schema.columns
       where table_schema = 'public'
         and table_name = 'compras_eliminadas')                      as columnas_de_5,
    (select count(*) from regexp_matches(
        coalesce((select pg_get_constraintdef(oid) from pg_constraint
                   where conname = 'compras_eliminadas_origen_check'), ''),
        '''[a-z_]+''', 'g'))                                         as valores_del_CHECK_de_4,
    (select count(*) from compras_eliminadas)                        as filas_archivadas,
    (select count(*) from compras)                                   as compras_POBLACION,
    (select max(cargado_el)::date from compras)                      as ultima_compra_cargada;

-- COMO SE LEE, con el valor esperado de cada numero al lado:
--   tabla_de_1               1
--   columnas_de_5            5
--   valores_del_CHECK_de_4   4   <- CUENTA LOS VALORES, no que el constraint
--                                   exista. Existe en los dos estados y lo
--                                   que cambia es la lista: un "¿hay algun
--                                   check?" da 1 con la lista vieja adentro.
--   filas_archivadas         0   recien creada; despues de un borrado, 1
--   compras_POBLACION            poblacion, y ultima_compra_cargada el
--                                testigo: sin ellos una base a medio
--                                configurar da los mismos numeros prolijos.
--
-- SE CORRE APARTE del bloque `do`. Pegados en la misma corrida el editor se
-- queda con la ultima y el `do` NO SE EJECUTA: sin error y con "no rows",
-- que es la salida normal de un `do` que si corrio.
