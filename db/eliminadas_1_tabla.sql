do $$
begin
    if not exists (select 1 from pg_tables
                   where schemaname = 'public' and tablename = 'compras_eliminadas') then

        create table compras_eliminadas (
            id           bigint generated always as identity primary key,
            compra_id    bigint not null,
            eliminada_el timestamptz not null default now(),
            origen       text not null check (origen in ('gerencia', 'cancelar_dia')),
            fila         jsonb not null
        );

        create index compras_eliminadas_fecha_idx
            on compras_eliminadas (eliminada_el desc);

        comment on table compras_eliminadas is
            'Que se borro de compras, cuando, y que tenia adentro. El DELETE de compras es REAL: no hay anulado_el, y una compra recepcionada borrada MUEVE STOCK sin dejar rastro, porque la entrada de stock ES la fila de compras (_SQL_SUMAS_STOCK lee FROM compras WHERE estado = recepcionado) y recepcionar no escribe ningun movimientos_stock. No guarda QUIEN: el sistema no tiene usuarios, asi que un quien seria un campo sin consecuencia.';

        comment on column compras_eliminadas.compra_id is
            'El id que TENIA. Sin FK a proposito: la fila ya no existe y una FK haria fallar el insert.';

        comment on column compras_eliminadas.fila is
            'La compra ENTERA como estaba, de to_jsonb(compras.*) en el RETURNING del propio DELETE. La fila entera y no columnas elegidas: asi no hay una lista que actualizar el dia que compras gane una columna, que es como se pierde un campo sin que nada falle.';

        comment on column compras_eliminadas.origen is
            'Cual de los dos caminos la borro: gerencia (POST /gerencia/compras/{id}/eliminar) o cancelar_dia (el borrado en lote por proveedor). Se DERIVA del camino y no lo tipea nadie, asi que no se puede dejar de llenar.';
    end if;
end $$;
