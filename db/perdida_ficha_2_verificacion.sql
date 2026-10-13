select 'perdida_ficha_1_tabla' as que_migracion,
  (select count(*) from information_schema.tables
    where table_schema = 'public' and table_name = 'fichas_perdida_historial') as tablas,
  (select count(*) from pg_class where relname = 'fichas_perdida_historial'
    and relrowsecurity) as con_candado,
  (select count(*) from information_schema.columns
    where table_schema = 'public' and table_name = 'fichas_logistica_historial'
      and column_name = 'perdida') as columna_bitacora,
  (select count(*) from pg_constraint
    where conname = 'fichas_perdida_una_por_dia') as unicos,
  (select count(*) from pg_policies
    where tablename = 'fichas_perdida_historial'
      and policyname = 'lectura_claudia_lee') as politica_claudia,
  (select count(*) from pg_roles where rolname = 'lectura_claudia') as existe_claudia,
  (select count(*) from fichas_logistica) as testigo_fichas;

-- Se corre DESPUES del bloque, aparte. tablas 1 · con_candado 1 ·
-- columna_bitacora 1 · unicos 1 · politica_claudia igual a existe_claudia.
