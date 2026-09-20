select
    'pase_a_segunda'                                                  as QUE_MIGRACION,
    (select count(*) from pg_constraint
      where conrelid = 'movimientos_stock'::regclass
        and pg_get_constraintdef(oid) like '%pase_a_segunda%')        as GUARDAS_CON_PASE_de_5,
    (select count(*) from pg_constraint
      where conrelid = 'movimientos_stock'::regclass
        and conname = 'movimientos_stock_pase_uno_a_uno')             as uno_a_uno_de_1,
    (select count(*) from movimientos_stock
      where tipo = 'pase_a_segunda'
        and (bultos_segunda is null or bultos_segunda <> -cantidad))  as OFENSORES_debe_dar_0,
    (select count(*) from movimientos_stock
      where tipo = 'pase_a_segunda' and anulado_el is null)           as pases_cargados,
    (select count(*) from movimientos_stock)                          as movimientos_POBLACION,
    (select max(fecha_operacion) from movimientos_stock)              as ultimo_movimiento;

-- COMO SE LEE, con el esperado al lado:
--   GUARDAS_CON_PASE_de_5   5   <- las CINCO que nombran el tipo nuevo. Se
--                                  cuentan POR DEFINICION y no por nombre:
--                                  los cuatro viejos existen en los DOS
--                                  estados, asi que un `count` por nombre da
--                                  4 con la lista vieja adentro y no dice
--                                  nada. MEDIDO: solo el bloque 1 da 3, solo
--                                  el bloque 2 da 2. Cualquier cosa que no
--                                  sea 5 es media migracion.
--   uno_a_uno_de_1          1   <- el unico que es nuevo de verdad, asi que
--                                  este SI se puede contar por nombre.
--   OFENSORES_debe_dar_0    0
--   pases_cargados          0 hoy, y sube cuando la pantalla exista.
--
-- `movimientos_POBLACION` va para leer el cero de al lado, y se compara ANTES
-- y DESPUES: un `alter ... add constraint` no toca filas, asi que la
-- poblacion igual en las dos corridas es lo unico que dice que no se llevo
-- nada puesto.
--
-- SE CORRE APARTE de los dos bloques `do`.
