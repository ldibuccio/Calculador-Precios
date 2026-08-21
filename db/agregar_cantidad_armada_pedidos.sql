-- ============================================================================
-- ARMADO DEL PEDIDO (etapa 2): cantidad realmente armada por renglón
-- ============================================================================
-- El tilde de armado (armado_el, ya existente) significa "terminé con este
-- renglón", no "está completo". Si el depósito armó MENOS de lo pedido
-- (Día pide 15 y hay 12), la cantidad real queda acá:
--
--   cantidad_armada NULL  = armado completo (o renglón todavía sin armar:
--                           lo distingue armado_el)
--   cantidad_armada = 12  = armó 12 de los pedidos (renglón "incompleto")
--
-- Pendiente significa "todavía no lo hice", no "no tengo stock" — por eso
-- el incompleto se cierra con su cantidad real en vez de quedar colgado.
--
-- ADITIVO PURO: una columna nullable, sin default, sin tocar datos.
-- Correr en las DOS bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

alter table pedidos_renglones add column cantidad_armada numeric;

comment on column pedidos_renglones.cantidad_armada is
    'Cuantos bultos se armaron REALMENTE si fue menos que lo pedido (NULL = armado completo, o sin armar segun armado_el). Con el reemplazo de un pedido corregido viaja junto con el tilde a los renglones identicos.';

-- Verificación: tiene que devolver una fila.
-- select column_name from information_schema.columns
-- where table_name = 'pedidos_renglones' and column_name = 'cantidad_armada';
