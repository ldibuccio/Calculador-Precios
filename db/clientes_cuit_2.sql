-- CARTERA DE CHEQUES (dueño, 14/10): un cliente tiene VARIOS CUIT propios.
-- Tabla aparte; pasa el CUIT que haya en clientes.cuit (la columna queda
-- hasta el deploy y se borra con clientes_cuit_3).
create table if not exists clientes_cuits (
  id          bigint generated always as identity primary key,
  cliente_id  bigint not null references clientes (id),
  cuit        text not null constraint clientes_cuits_once_digitos check (cuit ~ '^[0-9]{11}$'),
  creado_en   timestamptz not null default now(),
  constraint clientes_cuits_cuit_unico unique (cuit)
);
create index if not exists clientes_cuits_por_cliente on clientes_cuits (cliente_id);
alter table clientes_cuits enable row level security;

insert into clientes_cuits (cliente_id, cuit)
select id, cuit from clientes where cuit is not null
on conflict (cuit) do nothing;
