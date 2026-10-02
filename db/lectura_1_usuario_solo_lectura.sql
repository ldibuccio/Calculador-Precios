do $$
declare
  clave text := 'PEGAR-ACA-LA-CLAVE-NUEVA';
begin
  -- La clave tiene que tener FORMA de clave: 24 o más letras y números.
  -- El texto de ejemplo tiene guiones, así que nunca pasa (corolario 30).
  if clave !~ '^[A-Za-z0-9]{24,}$' then
    raise exception 'Poné una clave de 24 o más letras y números, sin símbolos';
  end if;

  if exists (select 1 from pg_roles where rolname = 'lectura_claudia') then
    execute format('alter role lectura_claudia login password %L', clave);
  else
    execute format('create role lectura_claudia login password %L', clave);
  end if;

  alter role lectura_claudia nosuperuser nocreatedb nocreaterole bypassrls;
  alter role lectura_claudia set default_transaction_read_only = on;
  alter role lectura_claudia set statement_timeout = '30s';

  grant usage on schema public to lectura_claudia;
  grant select on all tables in schema public to lectura_claudia;
  alter default privileges in schema public grant select on tables to lectura_claudia;
  revoke create on schema public from lectura_claudia;
end $$;

-- USUARIO DE SOLO LECTURA para Claude (30/09, dueño). Se corre solo, y la
-- verificación (lectura_2) aparte.
--
-- Lo que sostiene el "solo lectura" son los PERMISOS: solo SELECT sobre las
-- tablas de public, las de hoy y las que creen las migraciones futuras (que
-- corre el dueño como postgres, y por eso el default privileges las cubre).
-- El default_transaction_read_only es una segunda capa y NO la guarda: el
-- mismo usuario se lo puede sacar con un SET.
--
-- BYPASSRLS: una tabla con RLS y sin política para este rol le devuelve CERO
-- filas sin error, que se lee igual que "no hay". Con bypassrls ve lo mismo
-- que el editor. Solo afecta lo que puede LEER.
--
-- Correrlo de nuevo con otra clave la cambia: sirve para rotarla.
-- La clave no se pega en el chat: va en el editor de Supabase y en la
-- variable del entorno de Claude.
