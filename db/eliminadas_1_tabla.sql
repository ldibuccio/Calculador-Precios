do $$
begin
    if not exists (select 1 from pg_tables
                   where schemaname = 'public' and tablename = 'compras_eliminadas') then

        create table compras_eliminadas (
            id           bigint generated always as identity primary key,
            compra_id    bigint not null,
            eliminada_el timestamptz not null default now(),
            origen       text not null,
            fila         jsonb not null
        );

        create index compras_eliminadas_fecha_idx
            on compras_eliminadas (eliminada_el desc);

        comment on table compras_eliminadas is
            'Que se borro de compras, cuando, y que tenia adentro. El DELETE de compras es REAL: no hay anulado_el, y una recepcionada borrada MUEVE STOCK sin dejar rastro, porque la entrada de stock ES la fila de compras y recepcionar no escribe ningun movimientos_stock. No guarda QUIEN: el sistema no tiene usuarios.';

        comment on column compras_eliminadas.fila is
            'La compra ENTERA, de to_jsonb(compras.*) en el RETURNING del propio DELETE. No columnas elegidas: asi no hay lista que actualizar el dia que compras gane una columna.';

        comment on column compras_eliminadas.origen is
            'Por cual de las CUATRO superficies se borro. Se DERIVA del camino, no lo tipea nadie.';
    end if;

    -- EL CHECK VA AFUERA DEL if, Y SE RECREA SIEMPRE. Es CONTENIDO —una
    -- lista de valores— y ahi la idempotencia deja de proteger y pasa a
    -- esconder: si esta tabla ya se creo con una lista vieja, un `if not
    -- exists` la saltearia y el constraint quedaria con la lista de antes,
    -- saliendo DO las dos veces y sin una sola diferencia en la pantalla.
    --
    -- Y una lista incompleta no pierde un dato: REVIENTA EL BORRADO. El
    -- archivo se escribe en la misma sentencia que el DELETE.
    alter table compras_eliminadas
        drop constraint if exists compras_eliminadas_origen_check;
    alter table compras_eliminadas
        add constraint compras_eliminadas_origen_check
        check (origen in ('compras', 'compras_varias', 'gerencia', 'cancelar_dia'));
end $$;
