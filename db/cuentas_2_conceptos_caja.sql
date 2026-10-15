-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 2. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create table if not exists cuentas_conceptos (
  id         bigint generated always as identity primary key,
  cuenta_id  bigint not null references cuentas (id),
  nombre     text not null check (btrim(nombre) <> ''),
  tipo       text check (tipo in ('ingreso', 'egreso')),
  activo     boolean not null default true,
  creado_en  timestamptz not null default now()
);
create unique index if not exists cuentas_conceptos_nombre
  on cuentas_conceptos (cuenta_id, upper(btrim(nombre)));
alter table cuentas_conceptos enable row level security;

insert into cuentas_conceptos (cuenta_id, nombre, tipo)
select c.id, v.nombre, v.tipo
from (values ('Caja Lionel', 1, 'Saldo inicial', null), ('Caja Lionel', 2, 'Cobro Mecafront', 'ingreso'),
  ('Caja Lionel', 3, 'Cobro de terceros', 'ingreso'), ('Caja Lionel', 4, 'Aporte Lionel', 'ingreso'),
  ('Caja Lionel', 5, 'Aporte Ana', 'ingreso'), ('Caja Lionel', 6, 'Plata del puesto', 'ingreso'),
  ('Caja Lionel', 7, 'Préstamo/devolución recibida', 'ingreso'),
  ('Caja Lionel', 8, 'Cruce banco (ingreso)', 'ingreso'), ('Caja Lionel', 9, 'Otros ingresos', 'ingreso'),
  ('Caja Lionel', 10, 'Retiro Lionel', 'egreso'), ('Caja Lionel', 11, 'Retiro Ana', 'egreso'),
  ('Caja Lionel', 12, 'Entrega MN', 'egreso'), ('Caja Lionel', 13, 'Plata al puesto', 'egreso'),
  ('Caja Lionel', 14, 'Compra de dólares', 'egreso'), ('Caja Lionel', 15, 'BP', 'egreso'),
  ('Caja Lionel', 16, 'Cruce banco', 'egreso'),
  ('Caja Lionel', 17, 'Préstamo/devolución entregada', 'egreso'),
  ('Caja Lionel', 18, 'Pagos a terceros', 'egreso'), ('Caja Lionel', 19, 'Ajuste', null)
  ) as v (cuenta, orden, nombre, tipo)
join cuentas c on c.nombre = v.cuenta
where not exists (select 1 from cuentas_conceptos x
                  where x.cuenta_id = c.id and upper(btrim(x.nombre)) = upper(v.nombre))
order by c.id, v.orden;
