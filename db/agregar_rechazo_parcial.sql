-- ============================================================================
-- Rechazo parcial en Recepción: registrar cuántos bultos se devolvieron al
-- proveedor y por qué.
--
-- Solo registro: cuando Depósito rechaza una parte de la carga (ej. llegaron
-- 10 y rechaza 2 por calidad), la devuelve al proveedor y se le paga solo lo
-- recibido. Como el importe es POR BULTO, la cantidad aceptada queda en
-- cantidad_cajones_real y todas las cuentas (costeo incluido) salen solas —
-- ninguna fórmula cambia, no se toca el motor de costeo.
--
-- Correr en LAS DOS bases (Frutamax y Palmala). Inofensivo para el código
-- que corre hoy: columnas nuevas nullables que nadie lee todavía.
-- ============================================================================

begin;

alter table compras add column if not exists cantidad_cajones_rechazada numeric;
alter table compras add column if not exists motivo_rechazo text;

comment on column compras.cantidad_cajones_rechazada is 'Bultos devueltos al proveedor en un rechazo parcial de Recepción. Solo registro: la cantidad aceptada ya queda en cantidad_cajones_real y es la que usa todo el costeo. No entra en ningún cálculo.';
comment on column compras.motivo_rechazo is 'Motivo del rechazo parcial (texto libre, opcional).';

commit;
