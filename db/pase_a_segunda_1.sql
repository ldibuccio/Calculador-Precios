do $$
begin
    alter table movimientos_stock drop constraint if exists movimientos_stock_tipo_check;
    alter table movimientos_stock add constraint movimientos_stock_tipo_check
        check (tipo in ('ajuste', 'merma', 'reingreso_rechazo', 'stock_inicial',
                        'cierre_modelo_viejo', 'pase_a_segunda'));

    alter table movimientos_stock drop constraint if exists movimientos_stock_destino_solo_reingreso;
    alter table movimientos_stock add constraint movimientos_stock_destino_solo_reingreso
        check (tipo in ('reingreso_rechazo', 'pase_a_segunda')
               or (destino_rechazo is null and bultos_segunda is null));

    alter table movimientos_stock drop constraint if exists movimientos_stock_segunda_segun_destino;
    alter table movimientos_stock add constraint movimientos_stock_segunda_segun_destino
        check (
            case
                when tipo = 'pase_a_segunda' then bultos_segunda is not null
                when destino_rechazo in ('segunda', 'reproceso') then bultos_segunda is not null
                else bultos_segunda is null
            end
        );
end $$;

-- BLOQUE 1 de 2. Abre la puerta de "pasar primera a segunda" en la tabla
-- donde ya viven la merma, el ajuste y el reingreso.
--
-- LOS TRES SON CONTENIDO —listas de valores— asi que van con `drop` y
-- recrear, NO con `if not exists`: un CHECK que ya existe con la lista vieja
-- se saltearia en silencio y saldria `DO` igual (ver CLAUDE.md, "Un
-- `if not exists` sobre CONTENIDO es una trampa").
--
-- El `_tipo_check` se llama asi porque Postgres nombra solo los CHECK de
-- columna: <tabla>_<columna>_check. Si esta base lo tiene con otro nombre el
-- `drop if exists` no lo encuentra y el `add` falla por duplicado — eso es
-- ruidoso y es lo que se quiere.
--
-- `pase_a_segunda` NO toca `movimientos_stock_ficha_solo_merma`, y es una
-- decision: el pase sale de los SUELTOS. Una caja ya armada para un cliente
-- que se pone fea no es un pase, es desarmarla primero.
--
-- El bloque 2 trae el lote dirigido y la guarda del uno a uno.
