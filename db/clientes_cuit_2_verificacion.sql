-- Verificación de clientes_cuit_2 (se corre aparte).
select 'clientes_cuit_2' as QUE_MIGRACION,
  (select count(*) from information_schema.tables where table_schema = 'public'
    and table_name = 'clientes_cuits') as tabla_1,
  (select count(*) from pg_class where relname = 'clientes_cuits' and relrowsecurity) as candado_1,
  (select count(*) from pg_policies where tablename = 'clientes_cuits') as politicas_0,
  (select count(*) from pg_constraint where conname in
    ('clientes_cuits_once_digitos', 'clientes_cuits_cuit_unico')) as checks_2,
  (select count(*) from clientes where cuit is not null) as en_la_columna,
  (select count(*) from clientes_cuits) as en_la_tabla,
  (select count(*) from clientes) as testigo_clientes;
