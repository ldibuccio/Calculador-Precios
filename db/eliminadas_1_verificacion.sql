select
    'eliminadas_1_tabla'                                             as QUE_MIGRACION,
    (select count(*) from pg_tables where schemaname = 'public'
       and tablename = 'compras_eliminadas')                         as tabla_de_1,
    (select count(*) from information_schema.columns
       where table_schema = 'public'
         and table_name = 'compras_eliminadas')                      as columnas_de_5,
    (select count(*) from pg_constraint c
       join pg_class t on t.oid = c.conrelid
       where t.relname = 'compras_eliminadas' and c.contype = 'c')   as guarda_del_origen_de_1,
    (select count(*) from compras_eliminadas)                        as filas_archivadas,
    (select count(*) from compras)                                   as compras_POBLACION,
    (select max(cargado_el)::date from compras)                      as ultima_compra_cargada;

-- COMO SE LEE, con el valor esperado de cada numero al lado (corolario 45):
--   tabla_de_1              1
--   columnas_de_5           5
--   guarda_del_origen_de_1  1
--   filas_archivadas        0   <- recien creada; despues de un borrado, 1
--   compras_POBLACION           la poblacion, y ultima_compra_cargada el testigo:
--                               sin ellos una base a medio configurar devuelve
--                               los mismos numeros prolijos que una sana.
--
-- SE CORRE APARTE del bloque `do`, en una segunda corrida. Pegados en la
-- misma, el editor se queda con la ultima y el `do` NO SE EJECUTA: sin error,
-- sin NOTICE, y con "no rows", que es la salida normal de un `do` que si
-- corrio.
--
-- Y si la tabla no existe, esta consulta FALLA en vez de devolver ceros. Eso
-- es lo que se quiere: un cero prolijo no distinguiria "no corrio" de "corrio
-- y no hay filas".
