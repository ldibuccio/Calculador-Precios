-- ============================================================================
-- REINGRESO VINCULADO AL PEDIDO (decisión del 25/08)
-- ============================================================================
-- Al cargar un reingreso por rechazo, el operario elige el pedido de
-- origen y el renglón ARMADO que devolvió el cliente. Dos columnas nuevas
-- en movimientos_stock, solo para tipo reingreso_rechazo:
--
-- 1. pedido_renglon_id: el renglón de pedido que se devolvió. Da la
--    trazabilidad (cliente y artículo salen del pedido, no se cargan a
--    mano), el TOPE duro (armado − ya devuelto acumulado, validado por el
--    server) y habilita la línea "− devoluciones" de la Rentabilidad REAL
--    ("si le mandé 25 y me devolvió 5, vendí 20" — la teórica NO se toca).
--
-- 2. costo_por_bulto: el costo del reingreso CONGELADO por el server al
--    cargar, sacado del listado anclado a la fecha del pedido de origen
--    (mismo listado que Márgenes y las dos rentabilidades). Con esto el
--    lote de reingreso deja de ser "sin costo" para el FIFO de la Real.
--    Puede quedar NULL si a esa fecha no había costo: el lote queda como
--    hasta hoy (motivo "reingreso sin costo" en el afuera del cálculo).
--
-- Los reingresos ya cargados quedan con pedido_renglon_id NULL: son los
-- "sin vínculo a pedido", marcados así en las pantallas de control.
-- Corregir uno es anularlo y recargarlo eligiendo el pedido.
--
-- ADITIVO PURO: no modifica filas existentes. Correr en las DOS bases
-- (Frutamax y Palmala) y marcar en APLICADO.md. El código que usa estas
-- columnas se mergea recién después de la confirmación.
-- ============================================================================

alter table movimientos_stock
    add column pedido_renglon_id bigint references pedidos_renglones(id),
    add column costo_por_bulto numeric check (costo_por_bulto is null or costo_por_bulto >= 0);

alter table movimientos_stock
    add constraint movimientos_stock_vinculo_solo_reingreso
        check (tipo = 'reingreso_rechazo' or (pedido_renglon_id is null and costo_por_bulto is null));

-- El acumulado "ya devuelto" por renglón (el tope del server) por
-- index-only scan, aunque la tabla crezca.
create index movimientos_stock_devueltos_idx
    on movimientos_stock (pedido_renglon_id) include (cantidad)
    where pedido_renglon_id is not null and anulado_el is null;

comment on column movimientos_stock.pedido_renglon_id is
    'Solo reingreso_rechazo: el renglón ARMADO del pedido de origen que el cliente devolvió. Da la trazabilidad, el tope (armado − ya devuelto) y la línea "− devoluciones" de la Rentabilidad Real. NULL en reingresos viejos = sin vínculo (corregir = anular y recargar).';
comment on column movimientos_stock.costo_por_bulto is
    'Solo reingreso_rechazo: costo por bulto CONGELADO por el server al cargar, del listado anclado a la fecha del pedido de origen. NULL = no había costo a esa fecha (el lote sigue como reingreso sin costo).';

-- Verificación: las dos columnas y el índice creados.
-- select column_name from information_schema.columns
--  where table_name = 'movimientos_stock'
--    and column_name in ('pedido_renglon_id', 'costo_por_bulto');
-- select indexname from pg_indexes where indexname = 'movimientos_stock_devueltos_idx';
