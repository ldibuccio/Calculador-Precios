-- Verificación de devolucion_deposito_1. SE CORRE APARTE: pegada al `do` el
-- editor se queda con la última y el bloque NO SE EJECUTA, sin error.
-- Las guardas se cuentan por DEFINICIÓN y no por nombre: los constraints
-- existen antes y después, lo que cambia es lo que dicen.
select 'devolucion_deposito' as QUE_MIGRACION,
       (select count(*) from pg_constraint
         where conname = 'movimientos_stock_tipo_check'
           and pg_get_constraintdef(oid) like '%devolucion_deposito%') as tipo_nuevo_de_1,
       (select count(*) from pg_constraint
         where conname = 'movimientos_stock_compra_solo_devolucion'
           and pg_get_constraintdef(oid) like '%devolucion_deposito%') as compra_abierta_de_1,
       (select count(*) from pg_constraint
         where conname = 'movimientos_stock_devolucion_deposito_completa') as guarda_nueva_de_1,
       (select count(*) from movimientos_stock
         where anulado_el is null) as POBLACION_movimientos,
       (select max(procesada_el)::date from compras
         where estado = 'recepcionado') as testigo_ultima_recepcion;
