select 'panel_foto_1_tabla' as que_migracion,
  (select count(*) from information_schema.tables
    where table_schema = 'public' and table_name = 'panel_fotos') as tablas,
  (select count(*) from pg_constraint
    where conname in ('panel_fotos_ok_con_datos', 'panel_fotos_falla_con_error')) as checks,
  (select count(*) from pg_indexes
    where tablename = 'panel_fotos'
      and indexname in ('panel_fotos_un_intento_por_turno', 'panel_fotos_por_fecha')) as indices,
  (select count(*) from panel_fotos) as fotos,
  (select count(*) from compras) as testigo_compras;

-- Se corre DESPUES del bloque, aparte. tablas 1 · checks 2 · indices 2 ·
-- fotos 0.
