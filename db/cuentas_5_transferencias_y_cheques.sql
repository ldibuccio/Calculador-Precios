-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 5. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create table if not exists cuentas_transferencias (
  id                bigint generated always as identity primary key,
  fecha             date not null,
  cuenta_origen_id  bigint not null references cuentas (id),
  cuenta_destino_id bigint not null references cuentas (id),
  importe           numeric(14,2) not null check (importe > 0),
  detalle           text,
  foto_ruta         text check (foto_ruta is null or btrim(foto_ruta) <> ''),
  como_se_cargo     text not null check (como_se_cargo in ('a_mano', 'foto', 'excel', 'extracto', 'historico')),
  anulado           boolean not null default false,
  sector            text not null check (sector = 'gerencia'),
  creado_en         timestamptz not null default now(),
  constraint cuentas_transferencia_entre_dos check (cuenta_origen_id <> cuenta_destino_id)
);
create index if not exists cuentas_transferencias_por_fecha on cuentas_transferencias (fecha);
alter table cuentas_transferencias enable row level security;

create table if not exists cuentas_cheques_depositados (
  cheque_id   bigint primary key references cheques_salidas (cheque_id) on delete cascade,
  cuenta_id   bigint not null references cuentas (id),
  creado_en   timestamptz not null default now()
);
create index if not exists cuentas_cheques_por_cuenta on cuentas_cheques_depositados (cuenta_id);
alter table cuentas_cheques_depositados enable row level security;
