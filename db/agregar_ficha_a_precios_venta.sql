-- ============================================================================
-- EL PRECIO DE VENTA PASA A SER DE LA FICHA (Parte 1 de 3, decisión del 26/08)
-- ============================================================================
-- El caso: un artículo de compra (Banana) del que se abastecen DOS fichas
-- del mismo cliente — "Banana Bolivia" y "Banana Ecuador" para Día —, cada
-- una con su código, su kilaje, su envase y SU PRECIO. Hoy no se puede:
-- fichas_logistica tiene unique (articulo_id, cliente_id), y aunque se
-- sacara, precios_venta_historial tiene unique (articulo_id, cliente_id,
-- vigente_desde) y las dos fichas no podrían tener precios distintos.
--
-- El cambio de fondo: la clave de VENTA pasa a ser la ficha en vez del
-- artículo. La de COMPRA no se toca — se compra Banana, hay stock de
-- Banana, y las dos fichas salen de ese mismo stock.
--
-- Esta migración es la PRIMERA de tres, y va sola a propósito:
--   1. (esta) el precio pasa a colgar de la ficha.
--   2. pedidos_renglones + ficha_id.
--   3. recién ahí, el drop del unique de fichas_logistica.
--
-- El ORDEN ES OBLIGATORIO: el backfill de acá es exacto PORQUE hoy el
-- unique de fichas_logistica garantiza una sola ficha por artículo y
-- cliente. Sacándolo antes, dejaría de ser determinista.
--
-- INVISIBLE POR DISEÑO: mientras haya una sola ficha por artículo y
-- cliente, esto no cambia ningún número ni ninguna pantalla. Es un cambio
-- de clave, no de cuenta.
--
-- articulo_id NO se borra: lo sigue usando el chequeo de Disponibles
-- (¿este artículo tiene algún precio cargado?) y sirve de referencia
-- histórica de a qué artículo apuntaba ese precio.
--
-- ON DELETE SET NULL, y es a propósito: "Cambiar artículo" de una ficha
-- (ver cambiar_articulo_de_ficha) BORRA la ficha y crea otra nueva con
-- otro id, y borrar una ficha también es una operación normal. En los dos
-- casos, hoy los precios viejos quedan colgados de un artículo que ya
-- ninguna ficha usa: dejan de leerse pero no se borran. Con SET NULL pasa
-- exactamente lo mismo — el precio queda huérfano y deja de leerse, con
-- su historia intacta. Sin esto, el FK bloquearía el borrado de fichas.
--
-- ADITIVO: no borra ni modifica ninguna fila (solo completa la columna
-- nueva). Correr en las DOS bases (Frutamax y Palmala) y marcar en
-- APLICADO.md. El código que usa la columna se mergea recién después de
-- la confirmación.
-- ============================================================================

alter table precios_venta_historial
    add column ficha_id bigint references fichas_logistica (id) on delete set null;

-- Backfill: cada precio se cuelga de la ficha de su (cliente, artículo).
-- Un precio sin ficha (la ficha se borró o cambió de artículo en algún
-- momento) queda en NULL: es dato histórico que hoy tampoco se lee.
update precios_venta_historial p
   set ficha_id = fl.id
  from fichas_logistica fl
 where fl.cliente_id = p.cliente_id
   and fl.articulo_id = p.articulo_id;

-- El unique se muda a la ficha. Es lo que habilita que Banana Bolivia y
-- Banana Ecuador tengan precios distintos el mismo día. Los huérfanos
-- (ficha_id NULL) no se estorban entre sí: en Postgres los NULL son
-- distintos entre sí para un unique.
alter table precios_venta_historial
    drop constraint precios_venta_historial_articulo_id_cliente_id_vigente_desd_key;

alter table precios_venta_historial
    add constraint precios_venta_historial_ficha_vigente_key
        unique (ficha_id, vigente_desde);

-- El mismo índice de siempre, con la clave nueva: el precio vigente de
-- cada ficha sale por index scan (DISTINCT ON (ficha_id) ... ORDER BY
-- ficha_id, vigente_desde DESC). El viejo, por (cliente_id, articulo_id),
-- queda sin uso — se dropea en la limpieza, junto con lo demás, cuando
-- las tres partes estén andando.
create index precios_venta_historial_ficha_vigente_idx
    on precios_venta_historial (cliente_id, ficha_id, vigente_desde desc);

comment on column precios_venta_historial.ficha_id is
    'La ficha a la que pertenece este precio: la clave de VENTA. Dos fichas del mismo artículo y cliente (Banana Bolivia y Banana Ecuador) tienen precios distintos porque son fichas distintas. NULL = precio huérfano (su ficha se borró o cambió de artículo): queda de historia y no se lee.';

-- Verificación. (1) la columna y el índice creados; (2) el unique nuevo en
-- lugar del viejo; (3) cuántos precios quedaron colgados de su ficha y
-- cuántos huérfanos — los huérfanos son los que hoy tampoco se leen, así
-- que el número tiene que ser chico o cero.
--
-- select column_name from information_schema.columns
--  where table_name = 'precios_venta_historial' and column_name = 'ficha_id';
--
-- select conname from pg_constraint
--  where conrelid = 'precios_venta_historial'::regclass and contype = 'u';
--
-- select count(*) filter (where ficha_id is not null) as con_ficha,
--        count(*) filter (where ficha_id is null)     as huerfanos
--   from precios_venta_historial;
