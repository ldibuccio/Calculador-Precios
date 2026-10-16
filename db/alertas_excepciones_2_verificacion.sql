-- EXCEPCIONES DE ALERTAS (dueño, 16/10), migración alertas_excepciones_1, verificación. En Frutamax Y en Palmala, aparte del bloque 1.
select 'alertas_excepciones_1' as QUE_MIGRACION,
  (select count(*) from information_schema.tables
    where table_schema = 'public' and table_name = 'alertas_excepciones') as tabla_1,
  (select count(*) from information_schema.columns
    where table_schema = 'public' and table_name = 'alertas_excepciones') as columnas_6,
  (select count(*) from pg_class where relname = 'alertas_excepciones' and relkind = 'r' and relrowsecurity) as con_candado_1,
  (select count(*) from pg_policies where tablename = 'alertas_excepciones') as politicas_0,
  (select count(*) from pg_constraint where conname = 'alertas_excepciones_una_vez') as una_vez_1,
  (select count(*) from alertas_excepciones) as excepciones_0,
  (select count(*) from remitos) as testigo_remitos;
