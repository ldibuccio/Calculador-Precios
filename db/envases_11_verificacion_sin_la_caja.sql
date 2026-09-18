select 'envases_11_sin_la_caja' as QUE_MIGRACION,
  (select count(*) from information_schema.columns
    where table_name = 'movimientos_stock'
      and column_name in ('envase_id', 'lleva_caja_nuestra'))     as columnas_de_0,
  (select count(*) from pg_constraint
    where conname in ('movimientos_stock_envase_solo_reproceso',
                      'movimientos_stock_lleva_caja_solo_reproceso',
                      'movimientos_stock_envase_coherente'))      as guardas_de_0,
  (select count(*) from information_schema.columns
    where table_name = 'reprocesos'
      and column_name in ('envase_id', 'lleva_caja_nuestra'))     as cols_GUIA_R_de_2,
  (select count(*) from pg_constraint
    where conname = 'reprocesos_envase_coherente')                as guarda_GUIA_R_de_1,
  (select count(*) from movimientos_stock where anulado_el is null)
                                                                  as movimientos_POBLACION,
  (select max(fecha_operacion) from movimientos_stock where anulado_el is null)
                                                                  as ultimo_movimiento;

-- ---------------------------------------------------------------------------
-- Verificacion de envases_9. CORRE APARTE, nunca pegada al `do`: pegadas en
-- la misma corrida el editor se queda con la ultima y el `do` NO SE EJECUTA,
-- sin error y con "no rows", que es la salida normal de un `do` que si corrio.
--
-- En LAS DOS BASES, y se pegan las DOS filas CON EL NOMBRE DE LA BASE
-- ADELANTE: las cuatro primeras columnas dan lo mismo en las dos por diseno,
-- asi que las filas son indistinguibles entre si y pegar una creyendo que son
-- las dos es el error natural. `ultimo_movimiento` es el testigo que dice de
-- cual base es cada fila.
--
-- Lo esperado: 0 · 0 · 2 · 1, y `movimientos_POBLACION` igual que en
-- envases_10. Ese ultimo numero es el que dice que se borro una COLUMNA y no
-- filas: un drop de columna no toca ninguna, y si el conteo bajo, paren todo.
--
-- LAS DOS DEL MEDIO SON EL CONTROL, y son la mitad que hace legible al cero:
-- la guia R tiene las MISMAS dos columnas y su propia guarda de coherencia, y
-- esas SI se quedan — ahi la caja se llena de verdad. Sin ellas al lado, un
-- "0 · 0" no distingue "se saco lo que habia que sacar" de "se llevo puesto
-- el ancla del stock de cajas".
