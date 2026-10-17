-- CONSULTAS (dueño, 16/10), migración consultas_ia_1, bloque 1 de 3. En Frutamax Y en Palmala.
-- El usuario con que el chat de Gerencia lee la base: solo lectura, 10 segundos
-- por consulta, sin bypassrls (ve solo lo que el bloque 3 le abre), hasta 3
-- conexiones. Nace SIN contraseña: no puede entrar hasta que Lionel se la pone
-- en Supabase.
-- Corregido el 17/10: en Supabase un `alter role ... nosuperuser nobypassrls
-- connection limit` falla ("only SUPERUSER may alter..."). Un rol nuevo ya nace
-- sin superusuario, sin bypassrls y sin crear roles; el límite va en el create.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'consultas_ia') then
    create role consultas_ia login connection limit 3;
  end if;
  alter role consultas_ia set default_transaction_read_only = on;
  alter role consultas_ia set statement_timeout = '10s';
  alter role consultas_ia set idle_in_transaction_session_timeout = '30s';
  grant usage on schema public to consultas_ia;
end $$;
