do $$
begin
    if not exists (select 1 from information_schema.columns
                   where table_schema = 'public' and table_name = 'compras'
                     and column_name = 'importe_puesto_el') then

        alter table compras add column importe_puesto_el timestamptz;
        alter table compras add column importe_origen    text;

        comment on column compras.importe_puesto_el is
            'CUANDO se escribio el importe que la fila tiene HOY. NULL = anterior a esta columna (19/09) o sin precio todavia. No se dedujo nada hacia atras: de donde salio un importe ya escrito no se puede saber, y deducirlo seria inventarlo.';

        comment on column compras.importe_origen is
            'POR DONDE entro ese importe: alta (se cargo con la compra), edicion (POST /compras/{id}/editar) o pendiente (Compras sin precio). Se DERIVA del camino, no lo tipea nadie. No guarda QUIEN: el sistema no tiene usuarios. cargado_el NO sirve para esto: es de la COMPRA, y una que nacio sin precio y se completo tres dias despues lo lleva igual con la fecha del alta.';
    end if;

    -- EL CHECK VA AFUERA DEL if Y SE RECREA SIEMPRE: es CONTENIDO —una lista
    -- de valores— y ahi la idempotencia esconde en vez de proteger. Si esta
    -- columna ya existiera con una lista vieja, un bloque envuelto en el `if`
    -- la saltearia, saldria DO igual, y el constraint quedaria con la lista
    -- de antes sin una sola diferencia en la pantalla.
    --
    -- Y EL NULL PASA A PROPOSITO, no por descuido: las 625 compras que ya
    -- estan tienen importe y no tienen origen, y un CHECK que las rechazara
    -- no dejaria agregar la columna. `importe_origen is null or ...` lo dice
    -- explicito; sin esa mitad pasaria igual (un IN contra NULL da NULL y un
    -- CHECK que evalua NULL se cumple), y esta escrito para que nadie lo
    -- "arregle" creyendo que falta.
    alter table compras drop constraint if exists compras_importe_origen_check;
    alter table compras add constraint compras_importe_origen_check
        check (importe_origen is null
               or importe_origen in ('alta', 'edicion', 'pendiente'));
end $$;
