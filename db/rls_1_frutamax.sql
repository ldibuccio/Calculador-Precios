do $$
declare
  t record;
  n int := 0;
begin
  for t in
    select c.relname from pg_class c
      join pg_namespace s on s.oid = c.relnamespace
     where s.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity
  loop
    execute format('alter table public.%I enable row level security', t.relname);
    if exists (select 1 from pg_roles where rolname = 'lectura_claudia')
       and has_table_privilege('lectura_claudia', format('public.%I', t.relname), 'SELECT')
       and not exists (select 1 from pg_policies where schemaname = 'public'
                        and tablename = t.relname and policyname = 'lectura_claudia_lee') then
      execute format('create policy lectura_claudia_lee on public.%I for select '
                     'to lectura_claudia using (true)', t.relname);
    end if;
    n := n + 1;
  end loop;
  alter view public.vales_papel_revision set (security_invoker = true);
  raise notice 'candado puesto en % tablas', n;
end $$;

-- CANDADOS (RLS) EN TODAS LAS TABLAS DE public (dueño, 09/10). FRUTAMAX.
-- Prende RLS en cada tabla que no lo tiene, SIN politicas para anon: por la
-- API de Supabase con la clave anon ya no se lee nada. lectura_claudia (que
-- hoy lee esas tablas) recibe una politica de solo lectura en cada una, asi
-- no pierde nada. La vista vales_papel_revision pasa a correr con los
-- permisos de quien la consulta (sin eso, anon leia a traves de ella).
-- El sistema entra como postgres (dueno de las tablas y con bypassrls): el
-- candado no lo afecta. Se puede correr dos veces: la segunda no hace nada.
-- Verificacion APARTE: rls_1_verificacion.sql.
