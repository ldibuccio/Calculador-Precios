-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 7. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create table if not exists cuentas_extracto_renglones (
  id           bigint generated always as identity primary key,
  extracto_id  bigint not null references cuentas_extractos (id),
  cuenta_id    bigint not null references cuentas (id),
  fecha        date not null,
  descripcion  text not null,
  importe      numeric(14,2) not null check (importe <> 0),
  saldo        numeric(14,2),
  constraint cuentas_renglon_una_vez
    unique nulls not distinct (cuenta_id, fecha, importe, descripcion, saldo)
);
create index if not exists cuentas_renglones_por_extracto on cuentas_extracto_renglones (extracto_id);
alter table cuentas_extracto_renglones enable row level security;

create table if not exists cuentas_conciliaciones (
  id           bigint generated always as identity primary key,
  renglon_id   bigint not null unique references cuentas_extracto_renglones (id),
  cuenta_id    bigint not null references cuentas (id),
  origen       text not null check (origen in ('movimiento', 'transferencia', 'deposito', 'rechazo')),
  origen_id    bigint not null,
  a_revisar    boolean not null default false,
  sector       text not null check (sector = 'gerencia'),
  creado_en    timestamptz not null default now(),
  constraint cuentas_conciliado_una_vez unique (cuenta_id, origen, origen_id)
);
alter table cuentas_conciliaciones enable row level security;
