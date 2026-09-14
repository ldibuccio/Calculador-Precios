-- El historial de precios deja de desconectarse cuando se borra la ficha.
--
-- POR QUÉ (14/09). Los precios cuelgan de la FICHA y esta FK era
-- `on delete set null`: borrar una ficha —o CAMBIARLE EL ARTÍCULO, que por
-- dentro es un DELETE + INSERT con id nuevo— le ponía `ficha_id` en NULL a
-- sus precios. Y todas las lecturas filtran `ficha_id is not null`, así que
-- esos precios dejan de existir para el sistema: un listado de julio no
-- puede contestar por una ficha borrada en agosto. Sin error y sin que nada
-- se vea raro. Con /precios/vigencias eso ya no es hipotético.
--
-- Es el mismo argumento que ya sostiene la FK de reprocesos.ficha_id en NO
-- ACTION: borrar una ficha no puede mover el stock, y tampoco puede borrar
-- el precio al que se facturó.
--
-- NO TOCA LAS FILAS QUE YA QUEDARON HUÉRFANAS. Rescatarlas es otra decisión
-- y necesita su propio número: la consulta de abajo lo devuelve.
do $$
begin
    -- DROP + ADD y NO un `if not exists`: lo que cambia es el COMPORTAMIENTO
    -- del constraint, no su existencia. Con la guarda de existencia, una base
    -- que ya lo tiene con SET NULL se saltea el bloque y sale `DO` sin haber
    -- cambiado nada — que se ve EXACTAMENTE IGUAL que haberlo cambiado.
    alter table precios_venta_historial
        drop constraint if exists precios_venta_historial_ficha_id_fkey;

    alter table precios_venta_historial
        add constraint precios_venta_historial_ficha_id_fkey
        foreign key (ficha_id) references fichas_logistica (id);
end $$;
