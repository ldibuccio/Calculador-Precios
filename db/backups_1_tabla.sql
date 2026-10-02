do $$
begin
  create table if not exists backups_corridas (
    id bigint generated always as identity primary key,
    parte text not null,
    onedrive_ok boolean not null,
    gdrive_ok boolean not null,
    detalle text,
    terminada_el timestamptz not null default now()
  );
  alter table backups_corridas drop constraint if exists backups_corridas_parte;
  alter table backups_corridas add constraint backups_corridas_parte
    check (parte in ('codigo', 'bases', 'fotos'));
  create index if not exists backups_corridas_parte_fecha
    on backups_corridas (parte, terminada_el desc);
  revoke all on backups_corridas from public;
  if exists (select 1 from pg_roles where rolname = 'anon') then
    revoke all on backups_corridas from anon;
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    revoke all on backups_corridas from authenticated;
  end if;
  comment on table backups_corridas is
    'PLAN B DE BACKUP (duenio, 02/10): una fila por parte (codigo, bases, '
    'fotos) y por corrida diaria, con como le fue en cada destino. Exitoso = '
    'los dos en true. La escribe el workflow de backup con el rol '
    'backup_estado, que solo puede insertar aca. Gerencia la lee.';
end $$;

-- PLAN B DE BACKUP (duenio, 02/10), bloque 1 de 2: la tabla del estado.
--
-- El CHECK de la parte es contenido: drop y recrear. Se le saca todo permiso
-- a anon y authenticated (Supabase se los da por defecto a toda tabla nueva
-- de public, y esta no tiene por que verse por la API).
--
-- Se corre SOLO, en las dos bases, ANTES del deploy. Despues backups_2.
-- Verificacion aparte: backups_3.
