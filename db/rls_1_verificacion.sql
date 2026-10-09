select 'rls_1' as que_migracion,
  (select count(*) from pg_class c join pg_namespace s on s.oid = c.relnamespace
    where s.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity) as tablas_sin_rls,
  (select count(*) from pg_class c join pg_namespace s on s.oid = c.relnamespace
    where s.nspname = 'public' and c.relkind = 'r') as tablas,
  (select count(*) from pg_policies where schemaname = 'public'
    and policyname = 'lectura_claudia_lee') as politicas_claudia,
  (select count(*) from pg_policies where schemaname = 'public'
    and 'anon' = any(roles)) as politicas_anon,
  (select coalesce(bool_or(o = 'security_invoker=true'), false)
     from pg_class, unnest(coalesce(reloptions, '{}')) o
    where oid = 'public.vales_papel_revision'::regclass) as vista_cerrada,
  (select count(*) from compras) as testigo_compras;

-- Se corre DESPUES del bloque, aparte, en cada base.
-- FRUTAMAX: tablas_sin_rls 0 · tablas 106 · politicas_claudia 50 ·
--           politicas_anon 0 · vista_cerrada true.
-- PALMALA:  tablas_sin_rls 0 · tablas 98 · politicas_claudia 0 ·
--           politicas_anon 0 · vista_cerrada true.
-- GANADERIA (no lleva bloque, ya estaba todo con candado):
--           tablas_sin_rls 0 · tablas 17 · politicas_anon 0
--           (la vista y compras no existen ahi: se verifica con
--           rls_1_verificacion_ganaderia.sql).
