-- Verificación de cheques_2 (se corre aparte, después de db/cheques_7).
select 'cheques_2' as QUE_MIGRACION,
  (select count(*) from information_schema.columns where table_schema = 'public'
    and table_name = 'cheques_salidas' and column_name = 'cuenta_deposito') as columna_cuenta_1,
  (select count(*) from pg_constraint
    where conname = 'cheques_salidas_cuenta_no_vacia') as check_cuenta_1,
  (select count(*) from pg_proc where proname = 'cheque_salida_valida'
    and prosrc like '%tg_op = ''INSERT''%') as funcion_nueva_1,
  (select count(*) from pg_trigger where not tgisinternal
    and tgname = 'cheque_salida_valida') as trigger_1,
  (select count(*) from cheques_salidas) as testigo_salidas;
