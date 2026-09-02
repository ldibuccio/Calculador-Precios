-- ============================================================================
-- ENTREGA 3 — El que arma un pedido puede DECIR DE QUÉ LOTE lo sacó.
--
-- La tercera pieza de "elegir del stock que hay", y la misma que el desglose
-- del reproceso aplicada a la otra pantalla. Hoy el que arma tilda un renglón
-- y el sistema descuenta del artículo sin decir de dónde: el FIFO lo adivina
-- después. Con esto, propone y él corrige.
--
-- LA DIFERENCIA CON EL REPROCESO, Y ES TODA LA TABLA:
--
--   Acá AVISA Y NO TRABA. El camión sale igual: el piso es la verdad, un
--   pedido puede salir con mercadería que el sistema no tiene, y el sobrante
--   sigue cayendo a sin_lote como hasta hoy. En el reproceso se traba porque
--   ahí se congela un costo que no se corrige nunca; acá no se congela nada.
--
--   Por eso esta tabla NO es reprocesos_consumos. Aquella es el documento
--   COMPLETO de una guía R, con su costo congelado al cargar. Esta guarda
--   SOLO LA EXCEPCIÓN: si el que arma acepta lo que propone el FIFO, no se
--   escribe una sola fila. Sin filas = el reparto es el de siempre.
--
-- CÓMO SE USA (para que la tabla se lea sola dentro de seis meses):
--
--   Cada fila dice "de este renglón, tantos bultos salieron de este lote".
--   No tiene por qué cubrir el renglón entero: lo que no esté elegido cae al
--   FIFO como siempre. El reparto trata cada fila como una SALIDA DIRIGIDA,
--   que es el mecanismo que ya existe para la merma dirigida — y que ya
--   respeta un lote posterior a la salida, porque el que lo elige lo está
--   SEÑALANDO con el dedo, no adivinando.
--
--   Y NO GUARDA COSTO. El costo de un renglón armado lo calcula la
--   Rentabilidad Real cada vez, del lote que le toque. Guardarlo acá sería
--   un dato derivado más para mantener sincronizado, que es exactamente lo
--   que el FIFO calculado vino a evitar.
--
-- El BORRADO no es cosa de la base: destildar el renglón borra su corrección
-- (el tilde se fue, el reparto vuelve a ser el del FIFO), y anularlo también.
-- El on delete cascade es solo la red: un renglón que desaparezca no puede
-- dejar una corrección colgada apuntándole.
--
-- Se corre a mano en el editor de Supabase, en las DOS bases.
-- ============================================================================

do $$
begin
    if not exists (
        select 1 from pg_class where relname = 'pedidos_renglones_lotes_elegidos'
    ) then
        create table pedidos_renglones_lotes_elegidos (
            id         bigint generated always as identity primary key,
            renglon_id bigint not null
                       references pedidos_renglones (id) on delete cascade,
            -- Polimórfico y SIN FK, igual que movimientos_stock.lote_tipo: el
            -- lote se resuelve rejugando el FIFO, no siguiendo una relación.
            -- Los cinco tipos son los mismos de siempre (compras, guías R,
            -- reingresos, ajustes y el stock inicial del corte).
            lote_tipo  text not null
                       check (lote_tipo in ('guia', 'reproceso',
                                            'reingreso_rechazo', 'ajuste',
                                            'stock_inicial')),
            lote_origen_id bigint not null,
            bultos     numeric not null check (bultos > 0),
            creado_en  timestamptz not null default now(),
            -- El mismo lote no puede aparecer dos veces en el mismo renglón:
            -- serían dos verdades sobre lo mismo, y la suma dejaría de ser
            -- una suma. Sirve además de índice para buscar por renglón.
            unique (renglon_id, lote_tipo, lote_origen_id)
        );
    end if;

    -- Los comentarios van afuera del if a propósito: así una segunda corrida
    -- los refresca aunque la tabla ya exista.
    comment on table pedidos_renglones_lotes_elegidos is
        'De qué lote dijo el que arma que sacó los bultos de un renglón. SOLO LA EXCEPCIÓN: si acepta lo que propone el FIFO no se escribe nada, y un renglón sin filas acá se reparte como siempre. No cubre necesariamente el renglón entero — lo que no esté elegido cae al FIFO. Se borra al destildar o anular el renglón. No guarda costo: el costo lo calcula la Rentabilidad Real cada vez, del lote que le toque.';
    comment on column pedidos_renglones_lotes_elegidos.lote_tipo is
        'guia (lote de compra recepcionada), reproceso (primera de una guía R), reingreso_rechazo, ajuste o stock_inicial. Mismo vocabulario que movimientos_stock.lote_tipo y que core/stock.py: los tres tienen que nombrar los lotes igual o el reparto deja de encontrarlos.';
    comment on column pedidos_renglones_lotes_elegidos.lote_origen_id is
        'id del lote en la tabla de su lote_tipo (compras, reprocesos o movimientos_stock). Polimórfico a propósito y sin FK, igual que en la merma dirigida: el lote se resuelve rejugando el FIFO.';
    comment on column pedidos_renglones_lotes_elegidos.bultos is
        'Cuántos bultos de ese renglón salieron de ese lote. La suma de las filas de un renglón NO tiene que dar lo armado: el resto cae al FIFO. Acá se avisa y no se traba — el camión sale igual.';
end $$;
