-- ============================================================================
-- OBSERVABILIDAD DE LA REVISIÓN AUTOMÁTICA DE CASILLAS (fix del tick muerto)
-- ============================================================================
-- Del diagnóstico del 25/08: el bucle de revisión quedó colgado en un
-- connect IMAP sin dejar NINGÚN rastro, y la alerta de Auditoría no lo
-- delataba porque "Revisar ahora" manual también actualiza
-- ultima_revision_el — con el dueño tocando el botón, un tick muerto es
-- invisible para siempre. Dos piezas:
--
-- 1. casillas_pedidos.ultima_revision_automatica_el: cuándo fue la última
--    revisión exitosa hecha POR EL TICK (el botón manual no la toca). La
--    alerta de Auditoría pasa a mirar SOLO esta columna: aunque el dueño
--    revise a mano todos los días, un tick muerto se canta solo.
--
-- 2. revision_tick (una sola fila): el latido del bucle — se actualiza en
--    CADA tick, aunque no le toque revisar a ninguna casilla. Con esto,
--    "sin novedades" y "el bucle está muerto" dejan de verse iguales: la
--    pantalla de Sistema muestra el último tick, y si quedó viejo, el
--    bucle no está corriendo.
--
-- ADITIVO PURO: no modifica filas existentes. Correr en las DOS bases
-- (Frutamax y Palmala) y marcar en APLICADO.md. El código que usa estas
-- columnas se mergea recién después de la confirmación.
-- ============================================================================

alter table casillas_pedidos
    add column ultima_revision_automatica_el timestamptz;

create table revision_tick (
    id integer primary key check (id = 1),
    ultimo_tick_el timestamptz not null
);

comment on column casillas_pedidos.ultima_revision_automatica_el is
    'Última revisión EXITOSA hecha por el tick automático (el botón manual no la toca). La alerta de Auditoría mira SOLO esta: un tick muerto se detecta aunque el dueño revise a mano todos los días.';
comment on table revision_tick is
    'El latido del bucle de revisión automática (una sola fila, id = 1): se actualiza en cada tick, aunque no toque revisar nada. Si quedó viejo, el bucle no está corriendo — visible en Sistema sin deducir nada de logs.';

-- Verificación: la columna y la tabla creadas.
-- select column_name from information_schema.columns
--  where table_name = 'casillas_pedidos' and column_name = 'ultima_revision_automatica_el';
-- select table_name from information_schema.tables where table_name = 'revision_tick';
