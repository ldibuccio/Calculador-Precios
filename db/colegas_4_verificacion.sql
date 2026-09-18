select 'colegas_4' as QUE_MIGRACION,
  (select count(*) from information_schema.tables
    where table_schema = 'public' and table_name = 'colegas')          as tabla_colegas_de_1,
  (select count(*) from information_schema.columns
    where table_name = 'movimientos_envase'
      and column_name = 'colega_id')                                   as columna_de_1,
  (select count(*) from pg_constraint
    where conname = 'movimientos_envase_origen_check'
      and pg_get_constraintdef(oid) like '%colega_le_presto%')         as origen_CON_colega_de_1,
  (select count(*) from pg_constraint
    where conname = 'movimientos_envase_signo_segun_origen'
      and pg_get_constraintdef(oid) like '%colega_le_presto%')         as signo_CON_colega_de_1,
  (select count(*) from pg_constraint
    where conname = 'movimientos_envase_colega_segun_origen'
      and pg_get_constraintdef(oid) like '%IS DISTINCT FROM%')     as coherencia_NULL_SAFE_de_1,
  (select count(*) from movimientos_envase
    where origen = 'prestamo_salida')                                  as OFENSORES_origen_viejo,
  (select count(*) from movimientos_envase
    where origen = 'prestamo_al_puesto' and anulado_el is null)        as renombrados,
  (select count(*) from movimientos_envase where anulado_el is null)   as POBLACION_movimientos,
  (select max(fecha_operacion) from movimientos_envase
    where anulado_el is null)                                          as TESTIGO_ultimo_movimiento;

-- Verificacion de los bloques 1 a 3. SE CORRE APARTE, nunca pegada a un `do`:
-- juntos el editor se queda con la ultima y el `do` NO SE EJECUTA, sin error
-- y con "no rows" — la salida normal de un `do` que si corrio.
--
-- Lo bueno es 1/1/1/1/1 con OFENSORES en 0, y la fila se pega CON EL NOMBRE
-- DE LA BASE ADELANTE: las dos dan lo mismo por diseno, asi que sin el
-- nombre pegar una se ve igual que pegar las dos.
--
-- LAS GUARDAS SE CUENTAN POR DEFINICION, NO POR NOMBRE: existen en los dos
-- estados y lo que cambia es lo que DICEN. Un "existe algun check?" daria 1
-- con la lista vieja adentro.
--
-- EL PATRON ES `IS DISTINCT FROM` Y NO `IS NOT DISTINCT FROM`: Postgres
-- reescribe `a is not distinct from b` como `NOT (a is distinct from b)`,
-- asi que con el NOT adentro esa columna SOLO PODRIA DAR 0. Medido.
--
-- `renombrados` da lo mismo que el `prestamos` del diagnostico corrido
-- ANTES: dos fuentes del mismo numero. Si no es 0, mirar esas filas.
