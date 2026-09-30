-- devolucion_deposito_1_tipo.sql — CORRIDA el 30/09 en las dos bases (ver db/corridas_confirmadas.md).
do $$
begin
    if exists (select 1 from movimientos_stock where tipo = 'devolucion_deposito') then
        raise exception 'ya hay devoluciones desde deposito: no se vuelve a correr';
    end if;

    alter table movimientos_stock drop constraint if exists movimientos_stock_tipo_check;
    alter table movimientos_stock add constraint movimientos_stock_tipo_check
        check (tipo in ('ajuste', 'merma', 'reingreso_rechazo', 'stock_inicial',
                        'cierre_modelo_viejo', 'pase_a_segunda', 'devolucion_deposito'));

    alter table movimientos_stock drop constraint if exists movimientos_stock_compra_solo_devolucion;
    alter table movimientos_stock add constraint movimientos_stock_compra_solo_devolucion
        check (compra_devolucion_id is null
               or destino_rechazo is not distinct from 'devolucion_proveedor'
               or tipo = 'devolucion_deposito');

    alter table movimientos_stock drop constraint if exists movimientos_stock_devolucion_deposito_completa;
    alter table movimientos_stock add constraint movimientos_stock_devolucion_deposito_completa
        check (tipo <> 'devolucion_deposito'
               or (compra_devolucion_id is not null and cantidad < 0));
end $$;

-- DEVOLUCION DESDE DEPOSITO (duenio, 30/09): lo que queda en el piso y se le
-- devuelve al proveedor, sin pasar por un rechazo. Es un tipo NUEVO de
-- movimiento, con la cantidad NEGATIVA (sale del stock) y SIEMPRE con la
-- compra de la que sale: el sistema la costea al costo por bulto de ESA
-- compra y no deja devolver mas de lo que queda de ella.
--
-- NO TOCA NINGUNA FILA: son tres reglas sobre filas nuevas. El stock actual
-- no se mueve.
--
-- ES CONTENIDO —listas de valores— asi que va con drop y recrear, nunca con
-- `if not exists`: un CHECK viejo con la lista vieja se saltearia en silencio.
--
-- El tipo se llama `devolucion_deposito` y NO `devolucion_proveedor`, que es
-- un valor de OTRA columna (destino_rechazo): la devolucion POR RECHAZO. Dos
-- cosas distintas con el mismo nombre se confunden en la proxima lectura.
--
-- La guarda del principio aborta si ya corrio y alguien cargo una: correrla
-- de nuevo no romperia nada, pero asi se sabe que ya estaba.
--
-- Se corre SOLO. La verificacion va aparte: devolucion_deposito_2_verificacion.sql.
