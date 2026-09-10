-- MERMA POR FICHA (bloque 2 de 3): la columna, su FK compuesta y la guarda.
--
-- QUÉ ARREGLA: hoy una merma no puede decir de qué ficha salió, así que
-- mermar cajas armadas baja el TOTAL del artículo y no baja la ficha —
-- y como los sueltos se derivan por resta, la baja cae entera sobre los
-- sueltos. Medido: tirando 10 cajas de una ficha, el sistema queda
-- diciendo 10 cajas de la ficha y 0 sueltos, con el galpón exactamente
-- al revés.
--
-- SOLO PARA MERMA, y no es una restricción de más: el reingreso YA llega a
-- su ficha por `pedido_renglon_id -> pedidos_renglones.ficha_id`, que es el
-- camino que usa `reingresos_ficha` en _SQL_STOCK_PARTIDO. Si además
-- pudiera traer `ficha_id` propio habría DOS formas de decir lo mismo, y
-- el día que discrepen gana la que la consulta mire — la regla escrita dos
-- veces, en forma de dato.
--
-- La guarda es de UNA sola dirección a propósito: una merma PUEDE no tener
-- ficha (es la de los bultos sueltos, el caso más común). Lo que no puede
-- es que la tenga un ajuste o un reingreso.
do $$
begin
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'movimientos_stock' and column_name = 'ficha_id'
    ) then
        alter table movimientos_stock add column ficha_id bigint;
    end if;

    if not exists (
        select 1 from pg_constraint
        where conname = 'movimientos_stock_ficha_del_articulo'
    ) then
        alter table movimientos_stock
            add constraint movimientos_stock_ficha_del_articulo
            foreign key (ficha_id, articulo_id)
            references fichas_logistica (id, articulo_id);
    end if;

    -- CONTENIDO (nombra el tipo 'merma'), así que se borra y se recrea:
    -- con `if not exists` una lista vieja se queda adentro y el bloque sale
    -- `DO` igual, sin decir nada.
    alter table movimientos_stock
        drop constraint if exists movimientos_stock_ficha_solo_merma;
    alter table movimientos_stock
        add constraint movimientos_stock_ficha_solo_merma
        check (tipo = 'merma' or ficha_id is null);
end $$;
