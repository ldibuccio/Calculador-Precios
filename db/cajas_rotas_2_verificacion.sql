select
  'cajas_rotas_1_merma' as QUE_MIGRACION,
  (select count(*) from pg_constraint
    where conname = 'movimientos_envase_origen_check'
      and pg_get_constraintdef(oid) like '%''merma''%') as origen_con_merma,
  (select count(*) from pg_constraint
    where conname = 'movimientos_envase_signo_segun_origen'
      and pg_get_constraintdef(oid) like '%''merma''%') as signo_con_merma,
  (select count(*) from movimientos_envase) as movimientos_POBLACION,
  (select max(fecha_operacion) from movimientos_envase) as ultimo_movimiento;

-- Se corre APARTE del `do`, en las DOS bases. Tiene que dar 1 · 1.
-- Cuenta los CHECK por NOMBRE y por CONTENIDO: los dos existían antes de la
-- migración, así que contarlos solo por nombre daría 1 aunque el `do` no
-- hubiera corrido.
