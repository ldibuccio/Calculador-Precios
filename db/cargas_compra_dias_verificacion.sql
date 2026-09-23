select 'cargas_compra_dias' as que_migracion,
  (select count(*) from information_schema.columns
    where table_name = 'cargas_compra' and column_name = 'dias') as columna,
  (select is_nullable from information_schema.columns
    where table_name = 'cargas_compra' and column_name = 'dias') as acepta_null,
  (select count(*) from pg_constraint
    where conname = 'cargas_compra_dias_check'
      and pg_get_constraintdef(oid) like '%>= 1%') as guarda,
  (select count(*) from cargas_compra) as cargas_poblacion,
  (select count(*) from cargas_compra where dias is null) as sin_dias,
  (select count(*) from cargas_compra where dias <> 1) as distintas_de_uno,
  (select max(creado_en)::date from cargas_compra) as testigo_ultima_carga;

-- Después del bloque 1: columna 1 · acepta_null YES · guarda 1 · sin_dias 0 · distintas_de_uno 0.
-- Después del bloque 2: acepta_null NO, el resto igual.
