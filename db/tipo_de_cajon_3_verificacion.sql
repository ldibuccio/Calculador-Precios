select 'tipo_de_cajon_2_borrar' as que_migracion,
  (select count(*) from information_schema.columns
    where table_name = 'proveedores' and column_name = 'tipo_cajon_id') as columna_0,
  (select count(*) from information_schema.tables where table_name = 'tipos_cajon') as tabla_0,
  (select count(*) from proveedores) as proveedores_POBLACION,
  (select to_char(max(procesada_el) at time zone 'America/Argentina/Buenos_Aires', 'DD/MM HH24:MI')
     from compras where estado = 'recepcionado') as ultima_recepcion;

-- VERIFICACIÓN del bloque 2, APARTE y en las dos bases. Tiene que dar
-- columna 0 y tabla 0. proveedores_POBLACION se compara contra la del bloque
-- 1 corrido antes (o contra la pantalla): un drop column no toca filas, así
-- que tiene que dar lo mismo.
