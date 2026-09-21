-- listados_compra_3_kilaje.sql — CORRIDO Y CONFIRMADO en las dos bases el 21/09.
do $$
begin
  if not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                 where c.relname = 'listados_compra_kilaje' and n.nspname = 'public') then
    create table listados_compra_kilaje (
        listado_id   bigint not null references listados_compra (id) on delete cascade,
        articulo_id  bigint not null references articulos (id),
        kilaje       numeric not null,
        primary key (listado_id, articulo_id)
    );
  end if;
end $$;

alter table listados_compra_kilaje drop constraint if exists listados_compra_kilaje_positivo_check;
alter table listados_compra_kilaje add constraint listados_compra_kilaje_positivo_check
    check (kilaje > 0);

comment on table listados_compra_kilaje is 'Lo que trae un cajon de ese articulo EN EL MERCADO, en la magnitud de la fila, tal como lo dejo el comprador. Se guarda por listado y no en articulos: el mango viene en 40, 12 y 10 y no hay valor dominante, asi que lo de hoy no es una correccion de la referencia del articulo.';
comment on column listados_compra_kilaje.kilaje is 'En la magnitud de la fila (la unidad_venta de las fichas de ese articulo), no siempre en kilos. Solo se escribe la fila que el comprador TOCO: la que no esta usa articulos.contenido_referencia, y asi se distingue "lo dejo como venia" de "puso ese numero".';
