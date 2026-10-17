-- CONSULTAS POR TELEGRAM (dueño, 17/10), migración consultas_ia_2, bloque 1 de 2. En Frutamax Y en Palmala.
-- El canal de cada pregunta (web o telegram) y quién puede preguntar por Telegram.
do $$
begin
  alter table consultas_ia_preguntas add column if not exists canal text not null default 'web';
  alter table consultas_ia_preguntas add column if not exists telegram_id bigint;
  alter table consultas_ia_preguntas drop constraint if exists consultas_ia_preguntas_canal;
  alter table consultas_ia_preguntas add constraint consultas_ia_preguntas_canal
    check (canal in ('web', 'telegram'));
  alter table consultas_ia_preguntas drop constraint if exists consultas_ia_preguntas_telegram_coherente;
  alter table consultas_ia_preguntas add constraint consultas_ia_preguntas_telegram_coherente
    check ((canal = 'telegram') = (telegram_id is not null));
  create table if not exists telegram_autorizados (
    telegram_id    bigint primary key,
    nombre         text not null check (btrim(nombre) <> ''),
    activo         boolean not null default true,
    autorizado_el  timestamptz not null default now(),
    actualizado_el timestamptz not null default now()
  );
  alter table telegram_autorizados enable row level security;
end $$;
