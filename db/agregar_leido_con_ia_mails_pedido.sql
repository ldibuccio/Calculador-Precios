-- ============================================================================
-- MARCA "LEÍDO CON IA" EN LOS MAILS DE PEDIDO
-- ============================================================================
-- La lectura principal del pedido ahora es POR ESTRUCTURA (las cantidades
-- salen de la tabla tal cual, sin IA: un cruce de bultos entre sucursales
-- es imposible por construcción). La IA queda como camino de RESPALDO.
--
-- Este flag graba, en cada lectura de un mail, si hubo que caer al
-- respaldo — el fallback tiene que ser VISIBLE, no silencioso: si Día
-- cambia el formato del mail, la alerta de Auditoría lo dice ese mismo
-- día, antes de que aparezca un cruce.
--
-- ADITIVO PURO. Correr en las DOS bases (Frutamax y Palmala) y marcar en
-- APLICADO.md.
-- ============================================================================

alter table mails_pedido add column leido_con_ia boolean not null default false;

comment on column mails_pedido.leido_con_ia is
    'true = la última lectura de este mail cayó al camino IA (el parser de estructura no pudo). Alimenta la alerta de Auditoría "Pedidos de mail leídos con IA": si Día cambia el formato, se ve ese día.';

-- Verificación: la columna nueva existe.
-- select column_name, data_type from information_schema.columns
-- where table_name = 'mails_pedido' and column_name = 'leido_con_ia';
