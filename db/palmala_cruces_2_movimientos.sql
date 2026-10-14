-- PALMALA CRUCES (dueño, 14/10), migración palmala_1. SOLO EN FRUTAMAX: no se corre en Palmala.
create table if not exists palmala_movimientos (
  id                bigint generated always as identity primary key,
  fecha             date not null,
  cuenta            text not null check (cuenta in ('pesos', 'dolares_socios', 'dolares_ndt')),
  sentido           text not null check (sentido in ('debe', 'pago')),
  importe           numeric(14,2) not null check (importe > 0),
  concepto_id       bigint not null references palmala_conceptos (id),
  detalle           text,
  cheque_numero     text check (cheque_numero is null or btrim(cheque_numero) <> ''),
  cheque_banco_id   bigint references bancos (id),
  cheque_fecha_pago date,
  foto_ruta         text check (foto_ruta is null or btrim(foto_ruta) <> ''),
  como_se_cargo     text not null check (como_se_cargo in ('a_mano', 'foto', 'excel', 'historico')),
  fila_historico    int unique,
  anulado           boolean not null default false,
  sector            text not null check (sector = 'gerencia'),
  creado_en         timestamptz not null default now(),
  constraint palmala_fila_solo_del_historico
    check ((fila_historico is null) = (como_se_cargo <> 'historico'))
);
create index if not exists palmala_movimientos_por_cuenta on palmala_movimientos (cuenta, fecha, id);
alter table palmala_movimientos enable row level security;

create table if not exists palmala_correcciones (
  id             bigint generated always as identity primary key,
  movimiento_id  bigint not null references palmala_movimientos (id),
  campo          text not null,
  valor_anterior text,
  valor_nuevo    text,
  motivo         text not null check (btrim(motivo) <> ''),
  sector         text not null check (sector = 'gerencia'),
  creado_en      timestamptz not null default now()
);
create index if not exists palmala_correcciones_por_movimiento on palmala_correcciones (movimiento_id);
alter table palmala_correcciones enable row level security;
