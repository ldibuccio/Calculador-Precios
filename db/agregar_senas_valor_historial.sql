-- ============================================================================
-- Valor de la seña por tipo de envase, con historial por fecha de vigencia.
--
-- Hoy el sistema sabe CUÁNTAS señas hay pendientes pero no cuánto suman:
-- el valor de la seña vive en la cabeza de la cajera. Esta tabla lo pone
-- adentro, y con historial: si mañana la seña de un tipo pasa de $500 a
-- $700, las recepciones viejas tienen que seguir valiendo $500.
--
-- Copia exacta de la forma de envases_costo_historial (append-only, una
-- fila por (clave, fecha), se resuelve con DISTINCT ON ... vigente_desde
-- <= fecha ORDER BY vigente_desde DESC). La clave acá es tipo_envase_id.
--
-- Decisiones tomadas:
--
--   * El valor se ancla a la fecha de la RECEPCIÓN (vacios_recibidos.
--     creado_en::date), no a la fecha en que la seña se paga. Lo que se
--     le debe al cliente se fijó cuando dejó los cajones; que se le pague
--     tres semanas después no lo cambia.
--   * vigente_desde es DATE, no timestamptz: se acepta que un cambio de
--     valor rija para todo el día, incluidas las recepciones de esa misma
--     mañana anteriores a la carga. Es lo que hace envases_costo_historial
--     y es como se piensa el precio en el puesto ("desde hoy vale 700").
--   * Un tipo sin valor cargado NO vale $0: las pantallas muestran "sin
--     valor cargado" en texto, nunca un número. Por eso no hay default ni
--     fila sembrada acá: la tabla arranca vacía a propósito.
--
-- Esta migración NO rompe el código desplegado: agrega una tabla que nadie
-- lee todavía. Se puede correr antes de mergear.
-- ============================================================================

begin;

create table senas_valor_historial (
    id              bigint generated always as identity primary key,
    tipo_envase_id  bigint not null references tipos_envase_puesto (id),
    monto           numeric not null check (monto >= 0),
    vigente_desde   date not null,
    creado_en       timestamptz not null default now(),
    unique (tipo_envase_id, vigente_desde)
);

comment on table senas_valor_historial is 'Valor de la seña de cada tipo de envase del puesto, con historial por fecha de vigencia. Append-only: nunca se borra ni se corrige una fila vieja; cargar de nuevo la misma fecha es lo único que la pisa. Un tipo sin filas no vale 0: no tiene valor cargado.';
comment on column senas_valor_historial.monto is 'Cuánto se le señan al cliente por CADA cajón de este tipo. El total de una recepción es monto * cantidad.';
comment on column senas_valor_historial.vigente_desde is 'Desde qué día rige este monto. Se resuelve con el valor de mayor vigente_desde que sea <= la fecha de la RECEPCIÓN (vacios_recibidos.creado_en::date), no la fecha del pago.';

-- El índice que necesita el "vigente a la fecha": por tipo, la fecha más
-- alta que no pase de la buscada. El UNIQUE de arriba ya crea un índice
-- por (tipo_envase_id, vigente_desde) ascendente y alcanza para esto.

commit;
