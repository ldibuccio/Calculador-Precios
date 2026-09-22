do $$
begin
  if not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                 where c.relname = 'cargas_compra_renglones' and n.nspname = 'public') then
    create table cargas_compra_renglones (
        carga_id     bigint not null references cargas_compra (id) on delete cascade,
        articulo_id  bigint not null references articulos (id),
        total        numeric not null,
        primary key (carga_id, articulo_id)
    );
  end if;
  if not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                 where c.relname = 'listados_compra_cargas' and n.nspname = 'public') then
    create table listados_compra_cargas (
        listado_id  bigint not null references listados_compra (id) on delete cascade,
        carga_id    bigint not null references cargas_compra (id),
        primary key (listado_id, carga_id)
    );
  end if;
end $$;

alter table cargas_compra_renglones drop constraint if exists cargas_compra_renglones_total_check;
alter table cargas_compra_renglones add constraint cargas_compra_renglones_total_check
    check (total > 0);

comment on table cargas_compra_renglones is 'Lo que ese cliente pide de un articulo, EN LA UNIDAD DEL ARTICULO. La carga es contra ARTICULOS DE COMPRA y no contra las fichas del cliente (dueno, 22/09): se compra tomate, no "el tomate de Dia"; cada cliente arma despues su ficha con eso. Por eso apunta a articulos: uno que ningun cliente tiene en ficha se carga igual. Cuelga de la carga (cascade) porque sin ella no dice nada; el articulo NO va en cascada: borrarlo no puede vaciar una carga en silencio.';
comment on column cargas_compra_renglones.total is 'EL TOTAL DEL DIA en la magnitud del articulo. Los cajones NO se guardan: salen de dividirlo por listados_compra_kilaje, que es el kilaje DE COMPRA del Mercado y no el contenido_caja de la ficha. Medido el 22/09 en las dos bases: sin_ficha_Y_con_conteo 0, asi que el articulo sin ficha es siempre kilos.';
comment on table listados_compra_cargas is 'Que cargas arma este listado. Una carga puede estar en VARIOS a proposito (dueno, 22/09): si no se llego a comprar, o se la quiere de plantilla, se suma de nuevo y la pantalla avisa "ya se uso en el listado del 26/09". La PK impide sumarla dos veces EN EL MISMO listado, que es el unico doble conteo que no se puede querer. carga_id NO va en cascada: borrar una carga que un listado ya uso cambiaria en silencio lo que ese listado dice.';
