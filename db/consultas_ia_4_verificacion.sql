-- CONSULTAS (dueño, 16/10), migración consultas_ia_1, verificación. En Frutamax Y en Palmala, aparte de los bloques.
-- Con has_table_privilege (17/10): lo que el usuario PUEDE, no solo lo que se le dio.
with afuera as (select unnest(array['claves_especiales', 'casillas_pedidos', 'backups_corridas', 'panel_fotos',
       'corte_respaldo_fichas_reprocesos', 'consultas_ia_preguntas', 'consultas_ia_config',
       'telegram_autorizados', 'telegram_intentos', 'telegram_conversaciones', 'telegram_updates']) as nombre),
publicas as (select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
             where n.nspname = 'public' and c.relkind in ('r', 'p', 'v'))
select 'consultas_ia_1' as QUE_MIGRACION,
  (select count(*) from pg_roles where rolname = 'consultas_ia' and rolcanlogin and not rolsuper
     and not rolbypassrls and not rolcreaterole and rolconnlimit = 3) as usuario_1,
  (select count(*) from pg_db_role_setting s join pg_roles r on r.oid = s.setrole
    where r.rolname = 'consultas_ia' and 'default_transaction_read_only=on' = any (s.setconfig)
      and 'statement_timeout=10s' = any (s.setconfig)) as solo_lectura_y_10s_1,
  (select count(*) from publicas p
    where has_table_privilege('consultas_ia', 'public.' || quote_ident(p.relname), 'INSERT,UPDATE,DELETE,TRUNCATE')) as escribe_0,
  (select count(*) from publicas p join afuera a on a.nombre = p.relname
    where has_table_privilege('consultas_ia', 'public.' || quote_ident(p.relname), 'SELECT')) as excluidas_legibles_0,
  (select count(*) from publicas p
    where has_table_privilege('consultas_ia', 'public.' || quote_ident(p.relname), 'SELECT')) as lee,
  (select count(*) from publicas where relname not in (select nombre from afuera)) as permitidas_igual_a_lee,
  (select count(*) from pg_class where relname in ('consultas_ia_preguntas', 'consultas_ia_config')
     and relrowsecurity) as tablas_nuevas_con_candado_2,
  (select tope_mensual_usd from consultas_ia_config) as tope_100,
  (select count(*) from articulos) as testigo_articulos;
