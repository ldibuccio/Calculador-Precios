-- BLOQUE 3 — verificación. UNA consulta que devuelve CONTEOS, no una lista:
-- con conteos siempre vuelve una fila y el cero se ve. Con una lista, "todo
-- bien" y "no corrió" son la misma pantalla vacía.
--
-- Esperado en las dos bases: 1, 1, 1, 0 ofensores. `conteos_de_segunda` en 0
-- está bien todavía (nadie contó segunda aún). `ultimo_conteo` es el TESTIGO
-- DE ACTIVIDAD: sin él, una base sin un solo conteo devuelve todo en cero y
-- los ceros se leen como "acá no hay problema".
select
    (select count(*) from information_schema.columns
      where table_schema = 'public' and table_name = 'conteos_stock'
        and column_name = 'es_segunda')                             as columna_puesta,
    (select count(*) from pg_constraint
      where conname = 'conteos_stock_segunda_sin_ficha')            as guarda_puesta,
    (select count(*) from pg_indexes
      where indexname = 'conteos_stock_cotejo_idx'
        and indexdef like '%es_segunda%')                           as indice_con_segunda,
    (select count(*) from conteos_stock)                            as conteos_totales,
    (select count(*) from conteos_stock where es_segunda)           as conteos_de_segunda,
    (select count(*) from conteos_stock
      where es_segunda and ficha_id is not null)                    as ofensores,
    (select max(creado_en) from conteos_stock)                      as ultimo_conteo;
