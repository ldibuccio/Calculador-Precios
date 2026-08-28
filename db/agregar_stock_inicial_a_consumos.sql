-- ============================================================================
-- ETAPA 2 (arrastre) — El stock inicial también puede CONSUMIRSE.
--
-- La migración agregar_corte_y_stock_inicial.sql dejó entrar el lote de
-- stock inicial, pero no lo dejó salir: reprocesos_consumos.origen sigue
-- enumerando los orígenes viejos, y el FIFO escribe ahí el tipo del lote
-- que consumió (app/db.py: origen = lote["tipo_lote"]).
--
-- Reproducido en base local: el PRIMER reproceso normal que el depósito
-- cargue después del corte, tomando del stock inicial —que va a ser el
-- lote más viejo y por lo tanto el primero que el FIFO elige— revienta
-- con reprocesos_consumos_origen_check y no se guarda la guía.
--
-- ADITIVA y sin riesgo: solo agrega un valor a una lista. Ninguna fila
-- existente lo usa (no puede: el valor no existía).
-- ============================================================================

begin;

alter table reprocesos_consumos
    drop constraint reprocesos_consumos_origen_check;

alter table reprocesos_consumos
    add constraint reprocesos_consumos_origen_check
    check (origen in ('compra', 'ajuste', 'reingreso_rechazo', 'reproceso',
                      'stock_inicial', 'sin_lote'));

comment on column reprocesos_consumos.origen is
    'De qué clase de lote salieron estos bultos. compra = una compra recepcionada. stock_inicial = el remanente cargado a mano el día del corte. ajuste / reingreso_rechazo = movimientos_stock de ese tipo. reproceso = la primera de otra guía R. sin_lote = lo tomado que ningún lote cubría (el piso es la verdad: no se traba, y la diferencia queda a la vista).';

commit;
