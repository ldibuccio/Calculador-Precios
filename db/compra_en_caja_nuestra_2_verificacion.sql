-- VERIFICACION de los cuatro bloques de la guia R 'en_origen'.
-- Corre DESPUES de A, B, C y D, en las dos bases. Esperado en una base sin
-- usar todavia la funcion:  1 · 1 · 1 · 1 · 1 · 0  + poblacion y testigo.
--
-- CUENTA POR NOMBRE Y ADEMAS MIRA LA DEFINICION, y las dos cosas hacen falta:
--   por nombre   -> un drop que no recreo da 0 (un "existe algun check?" daria
--                   1 mirando otro y taparia el agujero).
--   definicion   -> un recrear con la lista vieja da 1 por nombre y 0 aca.
-- El caso del 09/09 —el bloque idempotente que salio `DO` sin hacer nada— solo
-- lo agarro contar por nombre; esta consulta agrega la otra mitad.
--
-- Conteos y no una lista: con conteos siempre vuelve una fila y el cero se ve.
-- Con una lista, "todo bien" y "no corrio" son la misma pantalla vacia.
select
  (select count(*) from information_schema.columns
    where table_schema = 'public' and table_name = 'reprocesos'
      and column_name = 'compra_origen_id')                      as col_compra_origen,
  (select count(*) from pg_indexes
    where schemaname = 'public'
      and indexname = 'reprocesos_una_guia_por_compra')          as candado_por_compra,
  (select count(*) from pg_constraint
    where conname = 'reprocesos_tipo_check'
      and pg_get_constraintdef(oid) like '%en_origen%')          as tipo_acepta_en_origen,
  (select count(*) from pg_constraint
    where conname = 'reprocesos_bultos_tomados_check'
      and pg_get_constraintdef(oid) like '%en_origen%')          as uno_a_uno,
  (select count(*) from pg_constraint
    where conname = 'reprocesos_compra_origen_coherente')        as coherencia_espejo,
  (select count(*) from reprocesos where tipo = 'en_origen')     as guias_en_origen,
  -- La POBLACION al lado del conteo: un numero de hallazgos sin su
  -- denominador no se puede leer, y nadie se acuerda de ir a buscarlo.
  (select count(*) from reprocesos where anulado_el is null)     as guias_vigentes,
  -- El TESTIGO DE ACTIVIDAD: en Palmala va a estar vieja, y entonces los
  -- ceros de esa base no votan. Lo que decide es Frutamax.
  (select max(fecha_operacion) from reprocesos)                  as ultima_guia_r;
