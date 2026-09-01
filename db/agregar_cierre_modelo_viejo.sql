-- Un TIPO PROPIO para el movimiento que cierra el modelo viejo.
--
-- El día del corte (31/08/2026) el stock del sistema arrastra saldos que no
-- son ciertos: salidas contra entradas que nunca se registraron. La puesta a
-- cero no borra ni anula nada (decisión 7: lo anterior queda visible y
-- consultable) — compensa cada artículo con UN movimiento que lo lleva a
-- cero. Ese movimiento necesita decir en el DATO qué es, y no entrar como
-- 'ajuste': los saldos iniciales de Vacíos se cargaron como ajuste y hoy son
-- indistinguibles de una corrección de faltante. Acá se separa desde el día
-- uno, que es cuando sale gratis.
--
-- El signo NO es fijo: 9 de los 22 artículos están en negativo y su
-- compensatorio es POSITIVO. Por eso el tipo no lleva ningún check de signo,
-- a diferencia de 'merma' (siempre negativa) y 'reingreso_rechazo' (siempre
-- positivo).
--
-- Lo que este tipo NO toca, a propósito:
--   * lote_tipo: un movimiento de cierre nunca puede ser el lote al que se
--     dirige una merma. Sus lotes nacen con restante cero (se los come el
--     excedente de salidas históricas que vinieron a compensar), así que no
--     aparecen en la lista de lotes con resto, y TIPOS_LOTE_STOCK del server
--     los rechazaría igual.
--   * costo_por_bulto: sigue siendo exclusivo del reingreso y del stock
--     inicial. El cierre no lleva costo — no es mercadería que llegó, es un
--     saldo que se cancela.

alter table movimientos_stock
    drop constraint movimientos_stock_tipo_check;

alter table movimientos_stock
    add constraint movimientos_stock_tipo_check
    check (tipo in ('ajuste', 'merma', 'reingreso_rechazo', 'stock_inicial', 'cierre_modelo_viejo'));

comment on column movimientos_stock.tipo is
    'ajuste (corrección de registro), merma (siempre negativa), reingreso_rechazo (siempre positivo, lo que volvió del cliente), stock_inicial (los bultos que había en el piso el día del corte, con costo), cierre_modelo_viejo (el compensatorio por artículo que cancela el saldo del modelo anterior al corte del 31/08/2026: signo libre, sin costo, y fuera de mermas y rentabilidad por su tipo).';

-- El respaldo de las fichas que el corte pone en NULL.
-- El paso 1 de la puesta a cero saca la ficha de las guías R pre-corte para
-- que sus cajas dejen de contar POR FICHA. El dato viejo no se pierde: queda
-- acá, que es a la vez el registro de qué se tocó y lo único que hace posible
-- un rollback exacto.
create table corte_respaldo_fichas_reprocesos (
    reproceso_id bigint primary key references reprocesos (id),
    ficha_id     bigint not null references fichas_logistica (id),
    guardado_el  timestamptz not null default now()
);

comment on table corte_respaldo_fichas_reprocesos is
    'Qué ficha tenía cada guía R antes de que el corte del 31/08/2026 se la pusiera en NULL. Una fila por guía tocada. No se borra: es el rastro de la puesta a cero.';
