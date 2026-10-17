-- CONSULTAS (dueño, 16/10), migración consultas_ia_1, bloque 3 de 3. En Frutamax Y en Palmala.
-- consultas_ia lee TODAS las tablas y vistas de public MENOS las de la lista:
-- claves, la casilla de mail (credenciales), backups, las fotos del panel, el
-- respaldo del corte y las de la propia Consultas (también las de Telegram,
-- 17/10: quién puede preguntar y lo que escribió quien no). Una tabla nueva
-- NO entra sola: se vuelve a correr este bloque.
do $$
declare
  t text;
  afuera text[] := array['claves_especiales', 'casillas_pedidos', 'backups_corridas', 'panel_fotos',
                         'corte_respaldo_fichas_reprocesos', 'consultas_ia_preguntas', 'consultas_ia_config',
                         'telegram_autorizados', 'telegram_intentos', 'telegram_conversaciones', 'telegram_updates'];
begin
  for t in select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relkind in ('r', 'p', 'v') and c.relname <> all (afuera)
  loop
    execute format('grant select on public.%I to consultas_ia', t);
  end loop;
  for t in select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relkind in ('r', 'p') and c.relname = any (afuera)
  loop
    execute format('revoke all on public.%I from consultas_ia', t);
    execute format('drop policy if exists consultas_ia_lee on public.%I', t);
  end loop;
  -- El candado (RLS) de cada tabla permitida se abre SOLO para leer y SOLO a este usuario.
  for t in select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relkind in ('r', 'p') and c.relrowsecurity
              and c.relname <> all (afuera)
  loop
    execute format('drop policy if exists consultas_ia_lee on public.%I', t);
    execute format('create policy consultas_ia_lee on public.%I for select to consultas_ia using (true)', t);
  end loop;
end $$;
