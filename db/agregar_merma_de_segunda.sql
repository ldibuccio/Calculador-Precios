-- MERMA DEL POOL DE SEGUNDA + FOTO OBLIGATORIA EN TODA MERMA.
-- Se corre en las DOS bases, bloque por bloque, de arriba abajo.
--
-- Por qué la merma de segunda NO va en movimientos_stock: ahí bajaría el
-- stock NORMAL del artículo (la pata `ajustes` toma todo `tipo <>
-- 'reingreso_rechazo'`) Y sería una salida del FIFO que consume lotes (la
-- pata de `_SQL_SALIDAS_STOCK` toma todo movimiento con cantidad < 0). La
-- segunda no tiene lotes: su costo ya se fue a la primera. Restaría de dos
-- pilas equivocadas a la vez.
--
-- `remitos_segunda` ya ES "salida del pool, por artículo, con fecha,
-- anulable". Con `destino` la aritmética del pool NO cambia: las dos
-- restan igual. Y el circuito de segunda queda entero afuera de
-- movimientos_stock, que es lo que impide que algo que lee stock normal lo
-- vea por accidente.

-- BLOQUE 1 — el destino y la coherencia con el motivo.
do $$
begin
    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'remitos_segunda'
          and column_name = 'destino'
    ) then
        alter table remitos_segunda
            add column destino text not null default 'puesto'
                check (destino in ('puesto', 'merma'));
    end if;

    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'remitos_segunda'
          and column_name = 'motivo'
    ) then
        alter table remitos_segunda add column motivo text;
    end if;

    -- LAS DOS DIRECCIONES EN UNA SOLA IGUALDAD: la merma SIEMPRE lleva
    -- motivo y el remito al Puesto NUNCA. Escrito como implicación simple
    -- dejaría pasar el caso espejo — es el CHECK de pedidos_renglones, que
    -- prohibía "ficha sin artículo" y permitía justo lo contrario.
    if not exists (
        select 1 from pg_constraint where conname = 'remitos_segunda_motivo_solo_merma'
    ) then
        alter table remitos_segunda
            add constraint remitos_segunda_motivo_solo_merma
            check ((destino = 'merma') = (motivo is not null));
    end if;
end $$;
