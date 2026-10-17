-- CONSULTAS POR TELEGRAM (dueño, 17/10), migración consultas_ia_2, verificación. Aparte de los bloques.
with nuevas as (select unnest(array['telegram_autorizados', 'telegram_intentos',
       'telegram_conversaciones', 'telegram_updates']) as nombre)
select 'consultas_ia_2' as QUE_MIGRACION,
  (select count(*) from information_schema.columns where table_schema = 'public'
     and table_name = 'consultas_ia_preguntas' and column_name in ('canal', 'telegram_id')) as columnas_nuevas_2,
  (select count(*) from pg_constraint where conname in ('consultas_ia_preguntas_canal',
     'consultas_ia_preguntas_telegram_coherente')) as checks_2,
  (select count(*) from consultas_ia_preguntas where canal <> 'web') as preguntas_no_web_0,
  (select count(*) from pg_class c join nuevas n on n.nombre = c.relname
    where c.relnamespace = 'public'::regnamespace and c.relrowsecurity) as tablas_con_candado_4,
  (select count(*) from pg_policies p join nuevas n on n.nombre = p.tablename) as politicas_0,
  (select count(*) from nuevas n
    where has_table_privilege('consultas_ia', 'public.' || n.nombre, 'SELECT')) as consultas_ia_las_lee_0,
  (select count(*) from consultas_ia_preguntas) as testigo_preguntas;
