select 'lote_dia_anterior_1_historial' as que_migracion,
  (select count(*) from information_schema.tables
    where table_schema = 'public'
      and table_name = 'pedidos_renglones_lotes_correcciones') as tablas,
  (select count(*) from pg_constraint
    where conname = 'lotes_correcciones_con_quien') as checks,
  (select count(*) from pg_indexes
    where indexname = 'lotes_correcciones_por_renglon') as indices,
  (select count(*) from pg_class
    where relname = 'pedidos_renglones_lotes_correcciones'
      and relrowsecurity) as con_candado,
  (select count(*) from pedidos_renglones_lotes_correcciones) as correcciones,
  (select count(*) from pedidos_renglones_lotes_elegidos) as elegidos,
  (select count(*) from compras) as testigo_compras;

-- Se corre DESPUES del bloque, aparte. tablas 1 · checks 1 · indices 1 ·
-- con_candado 1 · correcciones 0.
