-- listados_compra_4_manual.sql — CORRIDO Y CONFIRMADO en las dos bases el 21/09.
do $$
begin
  if not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                 where c.relname = 'listados_compra_manual' and n.nspname = 'public') then
    create table listados_compra_manual (
        listado_id   bigint not null,
        cliente_id   bigint not null,
        articulo_id  bigint not null references articulos (id),
        total        numeric not null,
        primary key (listado_id, cliente_id, articulo_id),
        foreign key (listado_id, cliente_id)
            references listados_compra_clientes (listado_id, cliente_id) on delete cascade
    );
  end if;
end $$;

alter table listados_compra_manual drop constraint if exists listados_compra_manual_total_check;
alter table listados_compra_manual add constraint listados_compra_manual_total_check
    check (total > 0);

comment on table listados_compra_manual is 'Lo que un cliente en modo manual pide de un articulo, tipeado por el comprador. La FK va contra listados_compra_clientes y no contra listados_compra: una linea a mano de un cliente que no esta en el listado no puede existir, y destildarlo se la lleva. La base NO exige que ese cliente este hoy en modo manual, y es a proposito: pasarlo a automatico un rato no le tiene que borrar lo que tipeo. Quien decide cual se lee es el modo, no la existencia de la fila.';
comment on column listados_compra_manual.total is 'EL TOTAL EN LA MAGNITUD DE LA FILA, y nada mas. Los cajones NO se guardan: salen de dividirlo por listados_compra_kilaje, igual que en la fila automatica. Guardarlos seria una segunda verdad que deja de coincidir en cuanto alguien edita el kilaje.';
