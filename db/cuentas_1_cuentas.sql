-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 1. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create table if not exists cuentas (
  id          bigint generated always as identity primary key,
  nombre      text not null check (btrim(nombre) <> ''),
  tipo        text not null check (tipo in ('caja', 'banco', 'inversion')),
  moneda      text not null default 'pesos' check (moneda in ('pesos', 'dolares')),
  madre_id    bigint references cuentas (id),
  numero      text check (numero is null or btrim(numero) <> ''),
  activa      boolean not null default true,
  creado_en   timestamptz not null default now(),
  constraint cuentas_no_es_su_madre check (madre_id is distinct from id)
);
create unique index if not exists cuentas_nombre on cuentas (upper(btrim(nombre)));
create unique index if not exists cuentas_numero
  on cuentas (regexp_replace(numero, '[^0-9]', '', 'g')) where numero is not null;
alter table cuentas enable row level security;

insert into cuentas (nombre, tipo, numero)
select v.nombre, v.tipo, v.numero
from (values (1, 'Caja Lionel', 'caja', null),
             (2, 'Banco Credicoop', 'banco', 'CC$ 191-220-000247/7'),
             (3, 'Inversiones Credicoop', 'inversion', null)) as v (orden, nombre, tipo, numero)
where not exists (select 1 from cuentas c where upper(btrim(c.nombre)) = upper(v.nombre))
order by v.orden;
update cuentas set madre_id = (select id from cuentas where nombre = 'Banco Credicoop')
 where nombre = 'Inversiones Credicoop' and madre_id is null;
