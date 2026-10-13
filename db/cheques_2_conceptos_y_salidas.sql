-- CARTERA DE CHEQUES (dueño, 13/10), bloque 2 de 5. Corrido por Lionel en Frutamax y Palmala el 13/10.
do $$
begin
  create table if not exists cheques_conceptos (
    id        bigint generated always as identity primary key,
    nombre    text not null check (btrim(nombre) <> ''),
    destino   text not null check (destino in ('entregado', 'canjeado', 'depositado')),
    creado_en timestamptz not null default now()
  );
  create unique index if not exists cheques_conceptos_nombre
    on cheques_conceptos (upper(btrim(nombre)));
  alter table cheques_conceptos enable row level security;
  insert into cheques_conceptos (nombre, destino)
  select v.nombre, v.destino
  from (values ('Pago a proveedor', 'entregado'), ('Canje', 'canjeado'),
               ('Depósito en cuenta', 'depositado')) as v (nombre, destino)
  where not exists (select 1 from cheques_conceptos c
                    where upper(btrim(c.nombre)) = upper(v.nombre));

  create table if not exists cheques_salidas (
    cheque_id    bigint primary key references cheques (id),
    fecha        date not null,
    concepto_id  bigint not null references cheques_conceptos (id),
    proveedor_id bigint references proveedores (id),
    foto_ruta    text check (foto_ruta is null or btrim(foto_ruta) <> ''),
    sector       text not null check (sector = 'gerencia'),
    creado_en    timestamptz not null default now()
  );
  create index if not exists cheques_salidas_por_proveedor on cheques_salidas (proveedor_id);
  alter table cheques_salidas enable row level security;
end $$;
