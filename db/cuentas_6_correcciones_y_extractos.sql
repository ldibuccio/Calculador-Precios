-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 6. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create table if not exists cuentas_correcciones (
  id                bigint generated always as identity primary key,
  movimiento_id     bigint references cuentas_movimientos (id),
  transferencia_id  bigint references cuentas_transferencias (id),
  campo             text not null,
  valor_anterior    text,
  valor_nuevo       text,
  motivo            text not null check (btrim(motivo) <> ''),
  sector            text not null check (sector = 'gerencia'),
  creado_en         timestamptz not null default now(),
  constraint cuentas_correccion_de_uno check ((movimiento_id is null) <> (transferencia_id is null))
);
create index if not exists cuentas_correcciones_mov on cuentas_correcciones (movimiento_id);
create index if not exists cuentas_correcciones_tra on cuentas_correcciones (transferencia_id);
alter table cuentas_correcciones enable row level security;

create table if not exists cuentas_extractos (
  id           bigint generated always as identity primary key,
  cuenta_id    bigint not null references cuentas (id),
  archivo      text not null check (btrim(archivo) <> ''),
  archivo_ruta text check (archivo_ruta is null or btrim(archivo_ruta) <> ''),
  desde        date,
  hasta        date,
  saldo_final  numeric(14,2),
  sector       text not null check (sector = 'gerencia'),
  creado_en    timestamptz not null default now()
);
alter table cuentas_extractos enable row level security;
