-- ============================================================================
-- HORARIO DE REVISIÓN AUTOMÁTICA POR CASILLA (etapa 3, ajuste)
-- ============================================================================
-- Hasta ahora la ventana de revisión automática era fija para todo el
-- sistema (12:00 a 15:00, cada 15 minutos). Pasa a ser configurable POR
-- CASILLA (o sea, por cliente) desde la pantalla de la casilla: desde qué
-- hora, hasta qué hora y cada cuántos minutos se chequea el buzón.
--
-- Los DEFAULT reproducen el comportamiento vigente: las casillas ya
-- creadas quedan exactamente como venían andando hasta que el dueño
-- toque el horario.
--
-- ADITIVO PURO: no modifica filas existentes ni otras tablas. Correr en
-- las DOS bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

alter table casillas_pedidos
    add column revision_desde time not null default '12:00',
    add column revision_hasta time not null default '15:00',
    add column revision_cada_minutos integer not null default 15
        constraint casillas_revision_cada_minutos_check
        check (revision_cada_minutos between 5 and 240);

comment on column casillas_pedidos.revision_desde is
    'Hora argentina desde la que la revisión automática chequea el buzón cada día.';
comment on column casillas_pedidos.revision_hasta is
    'Hora argentina de cierre de la ventana de revisión automática (no inclusive).';
comment on column casillas_pedidos.revision_cada_minutos is
    'Cada cuántos minutos se chequea el buzón dentro de la ventana (5 a 240).';

-- Verificación: las tres columnas creadas con sus defaults.
-- select column_name, column_default from information_schema.columns
-- where table_name = 'casillas_pedidos' and column_name like 'revision%';
