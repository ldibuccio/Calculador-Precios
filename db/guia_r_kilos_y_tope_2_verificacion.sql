select 'guia_r_kilos_y_tope_1' as que_migracion,
  (select count(*) from information_schema.columns
    where table_schema = 'public' and table_name = 'reprocesos'
      and column_name in ('kilos_diferencia', 'kilos_guardo_igual',
                          'kilos_guardo_igual_el')) as columnas,
  (select count(*) from pg_constraint
    where conname = 'reprocesos_kilos_guardo_igual_entero') as checks,
  (select count(*) from pg_trigger
    where tgname = 'guia_r_no_pasa_la_compra' and not tgisinternal) as triggers,
  (select count(*) from reprocesos where kilos_diferencia is not null) as guardadas_igual,
  (select count(*) from reprocesos) as testigo_guias_r,
  (select count(*) from compras) as testigo_compras;

-- Se corre DESPUES del bloque, aparte. columnas 3 · checks 1 · triggers 1 ·
-- guardadas_igual 0.
