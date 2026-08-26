-- ============================================================================
-- EL RENGLÓN DEL PEDIDO GUARDA SU FICHA (Parte 2 de 3, decisión del 26/08)
-- ============================================================================
-- Segunda de tres para que un cliente pueda tener dos fichas del mismo
-- artículo de compra ("Banana Bolivia" y "Banana Ecuador" para Día, cada
-- una con su código, su kilaje, su envase y su precio):
--   1. (hecha) el precio pasa a colgar de la ficha.
--   2. (esta) el renglón del pedido guarda de qué ficha vino.
--   3. recién ahí, el drop del unique de fichas_logistica.
--
-- Hoy el renglón guarda articulo_id y el texto crudo del código de Día,
-- pero NO la ficha. Y el dato existe: el matcheo por código identifica la
-- ficha correcta y el sistema la descarta un paso antes de guardar (ver
-- _alias_de_fichas en app/main.py, que arma {código: articulo_id} y tira
-- el id de la ficha). Con dos fichas del mismo artículo, los dos renglones
-- quedarían idénticos en la base y nada río abajo podría distinguirlos:
-- ni el precio de la rentabilidad, ni el kilaje, ni el nombre que ve el
-- que arma.
--
-- articulo_id NO se toca y sigue siendo la clave de COMPRA: es lo que
-- descuenta stock. Que Banana Bolivia y Banana Ecuador descuenten del
-- mismo stock de Banana es correcto — se compró una sola banana.
-- ficha_id se suma al lado, como clave de VENTA.
--
-- El ORDEN ES OBLIGATORIO: el backfill de acá es exacto PORQUE hoy el
-- unique de fichas_logistica garantiza una sola ficha por artículo y
-- cliente. Sacándolo antes, dejaría de ser determinista.
--
-- INVISIBLE POR DISEÑO: mientras haya una sola ficha por artículo y
-- cliente, esto no cambia ningún número ni ninguna pantalla.
--
-- ON DELETE SET NULL, igual que en precios (Parte 1) y por lo mismo:
-- "Cambiar artículo" de una ficha (ver cambiar_articulo_de_ficha) la BORRA
-- y crea otra con id nuevo, y borrar una ficha también es una operación
-- normal. Sin esto, el FK bloquearía esas dos pantallas. El renglón queda
-- con su ficha en NULL y sigue funcionando igual que hoy: conserva su
-- artículo, su cantidad y su armado, y la rentabilidad lo trata como
-- viene tratando a un renglón cuya ficha ya no existe.
--
-- ADITIVO: no borra ni modifica ninguna fila (solo completa la columna
-- nueva). Correr en las DOS bases (Frutamax y Palmala) y marcar en
-- APLICADO.md. El código que usa la columna se mergea recién después de
-- la confirmación.
-- ============================================================================

alter table pedidos_renglones
    add column ficha_id bigint references fichas_logistica (id) on delete set null;

-- Backfill: la ficha de (cliente del pedido, artículo del renglón).
-- Un renglón SIN IDENTIFICAR (articulo_id NULL) queda en NULL: no se
-- sabe qué pidió el cliente, así que tampoco de qué ficha era. Uno
-- identificado cuya ficha se borró desde entonces, también.
update pedidos_renglones r
   set ficha_id = fl.id
  from pedidos p
  join fichas_logistica fl on fl.cliente_id = p.cliente_id
 where p.id = r.pedido_id
   and fl.articulo_id = r.articulo_id;

-- Un renglón sin identificar no puede tener ficha: si no se sabe qué
-- artículo pidió, menos se sabe con qué ficha se le vende.
alter table pedidos_renglones
    add constraint pedidos_renglones_ficha_solo_identificados
        check (articulo_id is not null or ficha_id is null);

-- Borrar una ficha tiene que poder poner en NULL sus renglones sin
-- recorrer la tabla entera: pedidos_renglones crece con cada pedido.
create index pedidos_renglones_ficha_idx
    on pedidos_renglones (ficha_id)
    where ficha_id is not null;

comment on column pedidos_renglones.ficha_id is
    'La ficha con la que el cliente pidió este renglón: la clave de VENTA (precio, kilaje, envase y el nombre que ve el que arma). Sale del código del cliente al matchear. articulo_id sigue al lado como clave de COMPRA — es lo que descuenta stock, y dos fichas del mismo artículo descuentan del mismo stock. NULL = renglón sin identificar, o ficha borrada después.';

-- Verificación. Los tres números tienen que cerrar contra el total de
-- renglones. El que importa es el tercero: un renglón IDENTIFICADO que
-- quedó sin ficha significa que su ficha ya no existe — hoy tampoco se
-- podía valuar, pero si el número no es chico, avisar antes de seguir.
--
-- select column_name from information_schema.columns
--  where table_name = 'pedidos_renglones' and column_name = 'ficha_id';
--
-- select count(*) filter (where ficha_id is not null)                          as con_ficha,
--        count(*) filter (where articulo_id is null)                           as sin_identificar,
--        count(*) filter (where articulo_id is not null and ficha_id is null)  as identificados_sin_ficha,
--        count(*)                                                              as total
--   from pedidos_renglones;
