-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 4. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create table if not exists cuentas_etiquetas (
  id         bigint generated always as identity primary key,
  nombre     text not null check (btrim(nombre) <> ''),
  activo     boolean not null default true,
  creado_en  timestamptz not null default now()
);
create unique index if not exists cuentas_etiquetas_nombre on cuentas_etiquetas (upper(btrim(nombre)));
alter table cuentas_etiquetas enable row level security;

create table if not exists cuentas_movimientos (
  id              bigint generated always as identity primary key,
  cuenta_id       bigint not null references cuentas (id),
  fecha           date not null,
  tipo            text not null check (tipo in ('ingreso', 'egreso')),
  importe         numeric(14,2) not null check (importe > 0),
  concepto_id     bigint not null references cuentas_conceptos (id),
  etiqueta_id     bigint references cuentas_etiquetas (id),
  detalle         text,
  foto_ruta       text check (foto_ruta is null or btrim(foto_ruta) <> ''),
  como_se_cargo   text not null
    check (como_se_cargo in ('a_mano', 'foto', 'excel', 'extracto', 'historico')),
  fila_historico  int,
  anulado         boolean not null default false,
  sector          text not null check (sector = 'gerencia'),
  creado_en       timestamptz not null default now(),
  constraint cuentas_mov_fila_solo_del_historico
    check ((fila_historico is null) = (como_se_cargo <> 'historico')),
  constraint cuentas_mov_fila_unica unique (cuenta_id, fila_historico)
);
create index if not exists cuentas_movimientos_por_cuenta on cuentas_movimientos (cuenta_id, fecha, id);
alter table cuentas_movimientos enable row level security;
