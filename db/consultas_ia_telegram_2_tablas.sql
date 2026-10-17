-- CONSULTAS POR TELEGRAM (dueño, 17/10), migración consultas_ia_2, bloque 2 de 2. En Frutamax Y en Palmala.
-- Los intentos de quien no está autorizado, la conversación de cada uno (hasta /nueva) y los mensajes
-- que Telegram ya mandó (si reintenta, no se contesta dos veces). Todas con candado.
do $$
begin
  create table if not exists telegram_intentos (
    id          bigint generated always as identity primary key,
    telegram_id bigint not null,
    nombre      text,
    usuario     text,
    texto       text,
    creado_en   timestamptz not null default now()
  );
  create index if not exists telegram_intentos_por_fecha on telegram_intentos (creado_en);
  alter table telegram_intentos enable row level security;
  create table if not exists telegram_conversaciones (
    telegram_id    bigint primary key,
    conversacion   uuid not null,
    empezada_el    timestamptz not null default now()
  );
  alter table telegram_conversaciones enable row level security;
  create table if not exists telegram_updates (
    update_id   bigint primary key,
    recibido_el timestamptz not null default now()
  );
  alter table telegram_updates enable row level security;
end $$;
