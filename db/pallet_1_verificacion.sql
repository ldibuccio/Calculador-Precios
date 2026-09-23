select 'pallet_1_cajas_por_pallet' as que_migracion,
  (select count(*) from information_schema.columns
    where table_name = 'envases' and column_name = 'cajas_por_pallet') as columna,
  (select count(*) from pg_constraint
    where conname = 'envases_cajas_por_pallet_positivo'
      and pg_get_constraintdef(oid) like '%> 0%') as guarda,
  (select count(*) from envases) as envases_poblacion,
  (select count(*) from envases where cajas_por_pallet is not null) as con_pallet,
  (select max(creado_en)::date from movimientos_envase) as testigo_ultimo_mov_cajas;

-- Esperado en las dos bases: columna 1 · guarda 1 · con_pallet 0.
