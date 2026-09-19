select
    'precio_3_la_base_tiene_algo_propio'                              as QUE_CONSULTA,
    (select count(*) from pg_trigger t
        join pg_class c on c.oid = t.tgrelid
        where c.relname = 'compras' and not t.tgisinternal)           as triggers_en_COMPRAS,
    (select count(*) from pg_trigger t
        join pg_class c on c.oid = t.tgrelid
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and not t.tgisinternal)            as triggers_en_TODA_la_base,
    (select count(*) from pg_rules where schemaname = 'public')       as reglas_en_TODA_la_base,
    coalesce((select column_default from information_schema.columns
        where table_schema = 'public' and table_name = 'compras'
          and column_name = 'importe'), 'SIN DEFAULT')                as default_de_IMPORTE,
    (select count(*) from information_schema.columns
        where table_schema = 'public' and table_name = 'compras')     as columnas_de_COMPRAS,
    (select count(*) from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public')                                   as funciones_en_public,
    (select count(*) from compras)                                    as compras_POBLACION,
    (select max(cargado_el)::date from compras)                       as ultima_compra_cargada;

-- QUE CONTESTA
--   Si la BASE tiene algo que db/esquema_completo.sql no dice. Todo lo que
--   verifique del lado del repo es ciego a esto: un trigger, una rule o un
--   DEFAULT no agregan ninguna columna, asi que el archivo del repo se queda
--   viejo sin que nada avise (corolario 60).
--
-- COMO SE LEE, y cada numero tiene su valor esperado al lado (corolario 45):
--   triggers_en_COMPRAS      0   <- cualquier cosa > 0 es LA RESPUESTA
--   triggers_en_TODA_la_base 0
--   reglas_en_TODA_la_base   0
--   default_de_IMPORTE       SIN DEFAULT
--   columnas_de_COMPRAS      29  <- el repo dice 29; otro numero es deriva de esquema
--   funciones_en_public      0
--
--   Los dos ultimos son POBLACION y TESTIGO: sin ellos, una base a medio
--   configurar devuelve los mismos ceros prolijos que una base sana.
--
-- PROBADA plantando el caso (corolario 36/53): con un trigger y un default
--   puestos a mano devuelve 1 y 'now()'; sacandolos vuelve a 0 y 'SIN DEFAULT'.
--   Un cero que no puede dar otra cosa no es una medicion.
