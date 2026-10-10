select 'lote_dia_anterior_2_como_salio' as que_migracion,
  (select count(*) from information_schema.columns
    where table_schema = 'public' and table_name = 'pedidos_renglones_lotes_correcciones'
      and column_name in ('que', 'en_su_envase_antes', 'en_su_envase_ahora',
                          'kilos_antes', 'kilos_ahora')) as columnas,
  (select count(*) from pg_constraint
    where conname in ('lotes_correcciones_que', 'lotes_correcciones_como_salio_entero',
                      'lotes_correcciones_kilos_solo_como_salio')) as checks,
  (select count(*) from pg_policies
    where tablename = 'pedidos_renglones_lotes_correcciones'
      and policyname = 'lectura_claudia_lee') as politica_claudia,
  (select count(*) from pg_roles where rolname = 'lectura_claudia') as existe_claudia,
  (select count(*) from pedidos_renglones_lotes_correcciones) as correcciones,
  (select count(*) from pedidos_renglones_lotes_correcciones where que <> 'lote') as no_de_lote,
  (select count(*) from compras) as testigo_compras;

-- Se corre DESPUES del bloque, aparte. columnas 5 · checks 3 ·
-- politica_claudia igual a existe_claudia (1 en Frutamax, 0 en Palmala) ·
-- no_de_lote 0.
