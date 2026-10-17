-- CONSULTAS (dueño, 16/10), migración consultas_ia_1, bloque 2 de 3. En Frutamax Y en Palmala.
-- El registro de cada pregunta y el tope de gasto del mes. Las dos con candado.
do $$
begin
  create table if not exists consultas_ia_preguntas (
    id             bigint generated always as identity primary key,
    sector         text not null check (sector in ('gerencia')),
    quien          text not null check (btrim(quien) <> ''),
    conversacion   uuid not null,
    pregunta       text not null check (btrim(pregunta) <> ''),
    respuesta      text,
    consultas      jsonb not null default '[]'::jsonb,
    modelo         text not null check (btrim(modelo) <> ''),
    tokens_entrada integer not null default 0 check (tokens_entrada >= 0),
    tokens_salida  integer not null default 0 check (tokens_salida >= 0),
    tokens_cache   integer not null default 0 check (tokens_cache >= 0),
    costo_usd      numeric(10,4) not null default 0 check (costo_usd >= 0),
    error          text,
    creado_en      timestamptz not null default now()
  );
  create index if not exists consultas_ia_preguntas_por_fecha on consultas_ia_preguntas (creado_en);
  alter table consultas_ia_preguntas enable row level security;
  create table if not exists consultas_ia_config (
    id               smallint primary key default 1 check (id = 1),
    tope_mensual_usd numeric(10,2) not null default 100 check (tope_mensual_usd > 0),
    actualizado_en   timestamptz not null default now()
  );
  alter table consultas_ia_config enable row level security;
  insert into consultas_ia_config (id) values (1) on conflict (id) do nothing;
end $$;
