-- ============================================================================
-- Tres cierres para los Pendientes de Pago de Vacíos: pagada, vale o anulada.
--
-- Ya existía sena_pagada_el (NULL = pendiente). Se agregan dos hermanas con
-- el mismo patrón fecha-como-estado: pendiente = las tres en NULL; resuelto
-- = exactamente una con fecha (qué pasó lo dice cuál columna está llena,
-- cuándo lo dice la fecha). El CHECK garantiza que nunca haya dos a la vez.
--
-- Del vale NO se arma nada del circuito (numeración, cobro, vencimiento):
-- por ahora es solo el dato "se cerró con vale".
--
-- Correr en LAS DOS bases (Frutamax y Palmala) ANTES de mergear el código.
-- Inofensivo para el código que corre hoy: columnas nuevas que nadie
-- escribe todavía, y el CHECK acepta todas las filas existentes.
-- ============================================================================

begin;

alter table vacios_recibidos add column if not exists sena_vale_el timestamptz;
alter table vacios_recibidos add column if not exists sena_anulada_el timestamptz;

comment on column vacios_recibidos.sena_pagada_el is 'La seña se le pagó al cliente (fecha). Uno de los tres cierres posibles del pendiente de pago; los otros dos son sena_vale_el y sena_anulada_el. NULL en los tres = seña pendiente.';
comment on column vacios_recibidos.sena_vale_el is 'El pendiente se cerró con un vale (fecha). Por ahora es solo el dato "se hizo vale" — sin numeración, cobro ni vencimiento.';
comment on column vacios_recibidos.sena_anulada_el is 'La seña se anuló: no se paga, decidido (fecha). NO anula el movimiento — los cajones entraron y siguen en el stock; para una entrada errónea está el Anular de Movimientos.';

alter table vacios_recibidos drop constraint if exists vacios_recibidos_un_solo_cierre_de_sena;
alter table vacios_recibidos add constraint vacios_recibidos_un_solo_cierre_de_sena
    check (num_nonnulls(sena_pagada_el, sena_vale_el, sena_anulada_el) <= 1);

commit;
