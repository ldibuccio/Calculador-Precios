-- BLOQUE 3 — la foto de la merma. UNA tabla para las dos mermas, con dos
-- dueños posibles y exactamente uno cargado:
--   * la merma de stock normal es una fila de movimientos_stock (tipo 'merma')
--   * la merma de segunda es una fila de remitos_segunda (destino 'merma')
--
-- Dos FK de verdad y no un (tipo, id) polimórfico: acá las dos tablas se
-- pueden nombrar, así que la base puede atajar un huérfano. El polimórfico
-- de movimientos_stock.lote_origen_id está justificado porque el lote se
-- resuelve rejugando el FIFO; éste no tiene esa excusa.
create table if not exists fotos_merma (
    id                bigint generated always as identity primary key,
    movimiento_id     bigint references movimientos_stock (id),
    salida_segunda_id bigint references remitos_segunda (id),
    foto_ruta         text not null,
    creado_en         timestamptz not null default now(),
    constraint fotos_merma_un_solo_dueno
        check ((movimiento_id is not null) <> (salida_segunda_id is not null)),
    unique (movimiento_id, foto_ruta),
    unique (salida_segunda_id, foto_ruta)
);
