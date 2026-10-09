select 'rls_1' as que_migracion,
  (select count(*) from pg_class c join pg_namespace s on s.oid = c.relnamespace
    where s.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity) as tablas_sin_rls,
  (select count(*) from pg_class c join pg_namespace s on s.oid = c.relnamespace
    where s.nspname = 'public' and c.relkind = 'r') as tablas,
  (select count(*) from pg_policies where schemaname = 'public'
    and 'anon' = any(roles)) as politicas_anon,
  (select count(*) from animales) as testigo_animales;

-- GANADERIA no lleva bloque: sus 17 tablas ya tenian candado el 09/10.
-- Esperado: tablas_sin_rls 0 · tablas 17 · politicas_anon 0.
