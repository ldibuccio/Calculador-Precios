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
    n := n + 1;
  end loop;
  alter view public.vales_papel_revision set (security_invoker = true);
  raise notice 'candado puesto en % tablas', n;
end $$;

-- CANDADOS (RLS) EN TODAS LAS TABLAS DE public (dueño, 09/10). PALMALA.
-- Igual que Frutamax, sin lectura_claudia (en Palmala no existe). Hoy anon
-- no tiene permiso de lectura en ninguna tabla de Palmala; el candado queda
-- igual, por si alguien se lo vuelve a dar. Se puede correr dos veces.
-- Verificacion APARTE: rls_1_verificacion.sql.
