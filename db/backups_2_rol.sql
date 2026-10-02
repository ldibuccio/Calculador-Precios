do $$
declare
  clave text := 'PEGAR_ACA_LA_CLAVE_DEL_ROL';
begin
  if clave !~ '^[A-Za-z0-9]{32,}$' then
    raise exception 'la clave no tiene forma de clave: pega la que vino con la migracion';
  end if;
  if to_regclass('backups_corridas') is null then
    raise exception 'falta backups_corridas: corre primero backups_1';
  end if;
  if exists (select 1 from pg_roles where rolname = 'backup_estado') then
    execute format('alter role backup_estado with login password %L connection limit 3', clave);
  else
    execute format('create role backup_estado with login password %L connection limit 3', clave);
  end if;
  grant usage on schema public to backup_estado;
  grant insert on backups_corridas to backup_estado;
  alter table backups_corridas enable row level security;
  drop policy if exists backup_estado_inserta on backups_corridas;
  create policy backup_estado_inserta on backups_corridas
    for insert to backup_estado with check (true);
end $$;

-- PLAN B DE BACKUP (duenio, 02/10), bloque 2 de 2: el rol que escribe.
--
-- backup_estado es el usuario con que el workflow de GitHub graba el estado.
-- Solo puede INSERTAR en backups_corridas: ni leer esa tabla ni tocar otra.
-- Si alguien se lleva esa clave, lo unico que puede hacer es agregar filas
-- de estado.
--
-- RLS PRENDIDO A PROPOSITO, con una sola politica: insertar, y solo este rol.
-- Asi no depende de si el editor de Supabase prende RLS solo en las tablas
-- nuevas. La app lee como postgres, duenio de la tabla, y RLS no la frena.
--
-- La clave es contenido: si el rol ya existe se la vuelve a poner (alter),
-- nunca se saltea. Va pegada en la linea de arriba (la que viene en el
-- mensaje, NO esta del archivo: la del archivo no tiene forma de clave y el
-- bloque se niega). La misma clave va al secret de GitHub.
--
-- Se corre SOLO, en las dos bases, cada una con SU clave. Verificacion
-- aparte: backups_3.
