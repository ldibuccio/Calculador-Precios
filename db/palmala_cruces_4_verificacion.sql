-- Verificación de palmala_1 (Palmala Cruces), SOLO en Frutamax (se corre aparte).
select 'palmala_1' as QUE_MIGRACION,
  (select count(*) from information_schema.tables where table_schema = 'public' and table_name in
    ('palmala_conceptos', 'palmala_movimientos', 'palmala_correcciones')) as tablas_3,
  (select count(*) from pg_class where relname in ('palmala_conceptos', 'palmala_movimientos',
    'palmala_correcciones') and relrowsecurity) as con_candado_3,
  (select count(*) from pg_policies where tablename like 'palmala%') as politicas_0,
  (select count(*) from palmala_conceptos) as conceptos_13,
  (select count(*) from palmala_conceptos where pide_cheque) as con_cheque_2,
  (select count(*) from pg_trigger where not tgisinternal
    and tgname = 'palmala_movimiento_valido') as trigger_1,
  (select count(*) from information_schema.views where table_schema = 'public'
    and table_name = 'palmala_movimientos_con_saldo') as vista_1,
  (select count(*) from palmala_movimientos) as movimientos_0,
  (select count(*) from bancos) as testigo_bancos;
