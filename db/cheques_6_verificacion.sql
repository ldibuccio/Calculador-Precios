-- CARTERA DE CHEQUES (dueño, 13/10): verificación de cheques_1..5. Se corre aparte.
select 'cheques_1' as QUE_MIGRACION,
  (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r' and c.relname in ('bancos', 'cheques',
      'cheques_conceptos', 'cheques_salidas', 'cheques_rechazos', 'cheques_fotos',
      'cheques_correcciones')) as tablas_7,
  (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relrowsecurity and c.relname in ('bancos', 'cheques',
      'cheques_conceptos', 'cheques_salidas', 'cheques_rechazos', 'cheques_fotos',
      'cheques_correcciones')) as con_candado_7,
  (select count(*) from pg_policies where schemaname = 'public'
    and tablename like any (array['cheques%', 'bancos'])) as politicas_0,
  (select count(*) from cheques_conceptos) as conceptos_3,
  (select count(*) from pg_trigger where not tgisinternal and tgname in
    ('cheque_salida_valida', 'cheque_que_salio_no_se_corrige')) as triggers_2,
  (select count(*) from pg_views where schemaname = 'public'
    and viewname = 'cheques_con_estado') as vista_1,
  (select count(*) from pg_indexes where schemaname = 'public'
    and indexname = 'cheques_banco_numero_librador'
    and indexdef like '%UNIQUE%' and indexdef like '%cuit_librador%') as indice_repetidos_1,
  (select count(*) from cheques) as cheques_0,
  (select count(*) from clientes) as testigo_clientes;
