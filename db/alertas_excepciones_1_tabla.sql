-- EXCEPCIONES DE ALERTAS (dueño, 16/10), migración alertas_excepciones_1, bloque 1. En Frutamax Y en Palmala.
-- Lo que una alerta NO cuenta, con su motivo. Sin pantalla: se carga por SQL.
do $$
begin
  create table if not exists alertas_excepciones (
    id         bigint generated always as identity primary key,
    alerta     text not null check (btrim(alerta) <> ''),
    apunta_a   bigint not null,
    motivo     text not null check (btrim(motivo) <> ''),
    fecha      date not null default ((now() at time zone 'America/Argentina/Buenos_Aires')::date),
    creado_en  timestamptz not null default now(),
    constraint alertas_excepciones_una_vez unique (alerta, apunta_a)
  );
  comment on table alertas_excepciones is 'Lo que una alerta no cuenta (dueño, 16/10): alerta es su código (remitos_rechazo_distinto), apunta_a el id de lo que no cuenta (remitos.id). Se carga por SQL, sin pantalla.';
  alter table alertas_excepciones enable row level security;
end $$;
