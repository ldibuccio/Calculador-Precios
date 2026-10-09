do $$
begin
  if to_regclass('public.panel_fotos') is not null then
    raise exception 'panel_foto_1 ya corrio';
  end if;
  create table panel_fotos (
    id bigint generated always as identity primary key,
    turno timestamptz,
    calculada_el timestamptz not null default now(),
    ok boolean not null,
    datos jsonb,
    error text,
    duracion_ms integer,
    constraint panel_fotos_ok_con_datos check (ok = (datos is not null)),
    constraint panel_fotos_falla_con_error check (ok or error is not null)
  );
  create unique index panel_fotos_un_intento_por_turno
    on panel_fotos (turno) where turno is not null;
  create index panel_fotos_por_fecha on panel_fotos (calculada_el desc);
end $$;

-- LA FOTO DEL PANEL DE CONTROL (dueño, 09/10): el tablero se calcula a las
-- 06:00 y a las 14:00 y al entrar se lee la ultima foto buena. turno es el
-- horario programado (null = "Actualizar ahora"); un turno se intenta una
-- sola vez (el indice unico). Si se corre dos veces, da error y no escribe
-- nada. Verificacion APARTE: panel_foto_1_verificacion.sql.
