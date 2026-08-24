-- ============================================================================
-- KILOS REALES ENVIADOS + ANULAR RENGLÓN + CIERRE DE ARMADO (Armar Pedido)
-- ============================================================================
-- Tres columnas para el armado:
--
-- 1. pedidos_renglones.kilos_enviados: los kilos con los que el depósito
--    MANDÓ realmente el renglón (lo que se factura). El default sugerido
--    en pantalla sale de la ficha (bultos × contenido por caja), pero es
--    editable — acá queda lo que de verdad se mandó. NULL = sin armar /
--    sin kilaje cargado: los listados lo dicen tal cual, nunca calculan
--    el de la ficha por defecto.
--
-- 2. pedidos_renglones.anulado_el: la cruz del armado — un artículo que
--    directamente no se va a armar. Anulado, nunca borrado (baja lógica);
--    queda fuera del progreso y visible como anulado.
--
-- 3. pedidos.armado_cerrado_el: el "Terminar pedido" — cierre explícito
--    del armado. Puede cerrarse con renglones sin tildar (se avisa y se
--    confirma, no se impide) y se puede reabrir.
--
-- ADITIVO PURO: no modifica filas existentes. Correr en las DOS bases
-- (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

alter table pedidos_renglones
    add column kilos_enviados numeric,
    add column anulado_el timestamptz;

alter table pedidos
    add column armado_cerrado_el timestamptz;

comment on column pedidos_renglones.kilos_enviados is
    'Kilos REALES con los que el depósito mandó el renglón (se cargan al tildar; editables). NULL = sin armar. Es el número que se factura.';
comment on column pedidos_renglones.anulado_el is
    'Renglón que no se va a armar: anulado (baja lógica), fuera del progreso, nunca borrado.';
comment on column pedidos.armado_cerrado_el is
    'Cierre explícito del armado ("Terminar pedido"). NULL = abierto; se puede reabrir.';

-- Verificación: las tres columnas creadas.
-- select table_name, column_name from information_schema.columns
-- where column_name in ('kilos_enviados', 'anulado_el', 'armado_cerrado_el')
--   and table_name in ('pedidos', 'pedidos_renglones');
