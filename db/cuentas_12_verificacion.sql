-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 12. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
select 'cuentas_1' as QUE_MIGRACION,
  (select count(*) from information_schema.tables where table_schema = 'public' and table_type = 'BASE TABLE'
    and (table_name = 'cuentas' or table_name like 'cuentas\_%')) as tablas_10,
  (select count(*) from pg_class where relkind = 'r' and relrowsecurity
    and (relname = 'cuentas' or relname like 'cuentas\_%')) as con_candado_10,
  (select count(*) from pg_policies where tablename = 'cuentas' or tablename like 'cuentas\_%') as politicas_0,
  (select count(*) from cuentas) as cuentas_3,
  (select count(*) from cuentas where madre_id is not null) as con_madre_1,
  (select count(*) from cuentas_conceptos) as conceptos_31,
  (select count(*) from pg_trigger where not tgisinternal and tgname in ('cuentas_movimiento_valido',
    'cuentas_transferencia_valida', 'cuentas_cheque_depositado_valido')) as triggers_3,
  (select count(*) from information_schema.views where table_schema = 'public'
    and table_name in ('cuentas_todos_los_movimientos', 'cuentas_con_saldo')) as vistas_2,
  (select count(*) from cuentas_conceptos where not activo) as solo_historico_3,
  (select count(*) from cuentas_movimientos) as movimientos_0,
  (select count(*) from cheques) as testigo_cheques;
