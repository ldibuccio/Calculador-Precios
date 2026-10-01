-- Verificacion de devolucion_sector_1 y 2. SE CORRE APARTE de los do: pegada
-- a un do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
-- Despues del bloque 1: columna 1 · valida 1 · coherente 0 · sin_sector 0.
-- Despues del bloque 2: columna 1 · valida 1 · coherente 1 · sin_sector 0.
select 'devolucion_sector' as QUE_MIGRACION,
       (select count(*) from information_schema.columns
         where table_name = 'movimientos_stock' and column_name = 'cargada_desde') as columna_de_1,
       (select count(*) from pg_constraint
         where conname = 'movimientos_stock_cargada_desde_valida') as valida_de_1,
       (select count(*) from pg_constraint
         where conname = 'movimientos_stock_devolucion_con_sector') as coherente,
       (select count(*) from movimientos_stock
         where tipo = 'devolucion_deposito' and cargada_desde is null) as sin_sector_en_0,
       (select count(*) from movimientos_stock
         where tipo <> 'devolucion_deposito' and cargada_desde is not null) as de_mas_en_0,
       (select count(*) from movimientos_stock where tipo = 'devolucion_deposito') as POBLACION_devoluciones,
       (select max(fecha_operacion) from movimientos_stock) as testigo_ultimo_movimiento;
