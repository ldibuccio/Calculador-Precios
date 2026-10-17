-- CHEQUES (dueño, 16/10), migración cheques_3, verificación. En Frutamax Y en Palmala, aparte de los bloques.
select 'cheques_3' as QUE_MIGRACION,
  (select count(*) from information_schema.columns where table_schema = 'public'
    and table_name = 'cheques_salidas' and column_name = 'proveedor_a_mano') as columna_1,
  (select count(*) from pg_constraint where conname in ('cheques_salidas_proveedor_a_mano_no_vacio',
    'cheques_salidas_un_proveedor')) as checks_2,
  (select count(*) from pg_proc where proname = 'cheque_salida_valida'
    and prosrc like '%proveedor_a_mano is null%') as freno_nuevo_1,
  (select count(*) from pg_attribute where attrelid = 'public.cheques_con_estado'::regclass
    and attname = 'proveedor_a_mano' and attnum = 26) as vista_columna_26,
  (select count(*) from pg_trigger where tgname = 'cheque_salida_valida' and not tgisinternal) as trigger_1,
  (select count(*) from cheques_salidas) as salidas,
  (select count(*) from cheques) as testigo_cheques;
