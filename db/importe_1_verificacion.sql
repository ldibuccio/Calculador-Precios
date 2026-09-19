select
    'importe_1_cuando_y_por_donde'                                   as QUE_MIGRACION,
    (select count(*) from information_schema.columns
       where table_schema = 'public' and table_name = 'compras'
         and column_name in ('importe_puesto_el', 'importe_origen')) as columnas_de_2,
    (select count(*) from regexp_matches(
        coalesce((select pg_get_constraintdef(oid) from pg_constraint
                   where conname = 'compras_importe_origen_check'), ''),
        '''[a-z]+''', 'g'))                                          as valores_del_CHECK_de_3,
    (select count(*) from compras
       where importe is not null and importe_origen is null)         as CON_precio_SIN_origen,
    (select count(*) from compras where importe_origen is not null)  as ya_con_origen,
    (select count(*) from compras)                                   as compras_POBLACION,
    (select max(cargado_el)::date from compras)                      as ultima_compra_cargada;

-- COMO SE LEE, con el esperado al lado:
--   columnas_de_2           2
--   valores_del_CHECK_de_3  3   <- CUENTA LA LISTA, no que el check exista:
--                                  existe en los dos estados y lo que cambia
--                                  es el contenido.
--   CON_precio_SIN_origen       TODAS las que ya estan. Es el numero
--                               esperado y NO es deuda: no se dedujo nada
--                               hacia atras porque no se puede. Baja solo
--                               en el sentido de que las nuevas nacen con
--                               origen; estas no lo van a tener nunca.
--   ya_con_origen           0   antes de cablear el codigo. Despues de la
--                               primera compra con precio, 1.
--
-- SE CORRE APARTE del bloque `do`.
