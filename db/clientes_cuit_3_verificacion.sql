-- Verificación de clientes_cuit_3 (se corre aparte).
select 'clientes_cuit_3' as QUE_MIGRACION,
  (select count(*) from information_schema.columns where table_schema = 'public'
    and table_name = 'clientes' and column_name = 'cuit') as columna_0,
  (select count(*) from pg_constraint where conname = 'clientes_cuit_check') as check_0,
  (select count(*) from clientes_cuits) as cuits_propios,
  (select count(*) from clientes) as testigo_clientes;
