do $$
begin
  if to_regclass('public.fichas_perdida_historial') is not null then
    raise exception 'perdida_ficha_1 ya corrio';
  end if;
  create table fichas_perdida_historial (
    id bigint generated always as identity primary key,
    ficha_id bigint not null references fichas_logistica (id) on delete cascade,
    perdida numeric not null check (perdida >= 0 and perdida < 1),
    vigente_desde date not null,
    registrado_en timestamptz not null default now(),
    constraint fichas_perdida_una_por_dia unique (ficha_id, vigente_desde)
  );
  alter table fichas_perdida_historial enable row level security;
  alter table fichas_logistica_historial add column perdida numeric;
  if exists (select 1 from pg_roles where rolname = 'lectura_claudia') then
    grant select on fichas_perdida_historial to lectura_claudia;
    create policy lectura_claudia_lee on fichas_perdida_historial
      for select to lectura_claudia using (true);
  end if;
end $$;

-- % DE PERDIDA POR FICHA (dueño, 13/10): de lo que se compra, cuanto no se
-- vende. Rige desde el dia en que se carga: una fila por ficha y por dia (el
-- mismo dia, la ultima pisa). Sin filas la ficha tiene 0 y el sugerido no
-- cambia. Se guarda como fraccion (0,18 = 18%). La bitacora de fichas gana la
-- columna perdida, vacia en lo viejo. Si se corre dos veces, da error y no
-- escribe nada. Verificacion APARTE: perdida_ficha_2_verificacion.sql.
