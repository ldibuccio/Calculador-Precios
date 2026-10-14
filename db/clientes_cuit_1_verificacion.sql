-- Verificación de clientes_cuit_1 (se corre aparte).
select 'clientes_cuit_1' as QUE_MIGRACION,
  (select count(*) from information_schema.columns where table_schema = 'public'
    and table_name = 'clientes' and column_name = 'cuit') as columna_cuit_1,
  (select count(*) from pg_constraint where conname = 'clientes_cuit_check') as check_cuit_1,
  (select count(*) from clientes where cuit is not null) as con_cuit_0,
  (select count(*) from clientes) as testigo_clientes;
