-- listados_compra_2_clientes.sql — CORRIDO Y CONFIRMADO en las dos bases el 21/09.
do $$
begin
  if not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                 where c.relname = 'listados_compra_clientes' and n.nspname = 'public') then
    create table listados_compra_clientes (
        listado_id  bigint not null references listados_compra (id) on delete cascade,
        cliente_id  bigint not null references clientes (id),
        modo        text not null,
        primary key (listado_id, cliente_id)
    );
  end if;
end $$;

alter table listados_compra_clientes drop constraint if exists listados_compra_clientes_modo_check;
alter table listados_compra_clientes add constraint listados_compra_clientes_modo_check
    check (modo in ('automatico', 'manual'));

comment on table listados_compra_clientes is 'Que clientes alimentan este listado y de que forma. La fila se borra con el listado (cascade) porque sin el no dice nada; el cliente NO se borra en cascada a proposito: borrar un cliente no puede vaciar un listado viejo en silencio.';
comment on column listados_compra_clientes.modo is 'automatico = lo que ese cliente pide sale del promedio de sus ultimos 6 pedidos vigentes. manual = sale de lo que el comprador tipea en listados_compra_manual. Es por CLIENTE y no por listado: un listado puede tener a Dia en automatico y a Tailem a mano, y los dos suman en la misma fila del articulo.';
