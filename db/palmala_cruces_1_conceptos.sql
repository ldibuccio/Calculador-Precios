-- PALMALA CRUCES (dueño, 14/10), migración palmala_1. SOLO EN FRUTAMAX: no se corre en Palmala.
create table if not exists palmala_conceptos (
  id          bigint generated always as identity primary key,
  nombre      text not null check (btrim(nombre) <> ''),
  pide_cheque boolean not null default false,
  activo      boolean not null default true,
  creado_en   timestamptz not null default now()
);
create unique index if not exists palmala_conceptos_nombre on palmala_conceptos (upper(btrim(nombre)));
alter table palmala_conceptos enable row level security;

insert into palmala_conceptos (nombre, pide_cheque)
select v.nombre, v.pide
from (values (1, 'Comisiones Día', false), (2, 'Sueldo Lionel', false), (3, 'BP', false),
             (4, 'Alquiler campo', false), (5, 'Intereses', false), (6, 'Gastos obra/Lionel', false),
             (7, 'Retiro socios', false), (8, 'Préstamo', false), (9, 'Pago con cheque', true),
             (10, 'Pago con echeq', true), (11, 'Pago en efectivo', false), (12, 'Ajuste', false),
             (13, 'Saldo inicial', false)) as v (orden, nombre, pide)
where not exists (select 1 from palmala_conceptos c where upper(btrim(c.nombre)) = upper(v.nombre))
order by v.orden;
