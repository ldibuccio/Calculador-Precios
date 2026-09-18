select 'renglon_cantidad_corregida' as QUE_MIGRACION,
  (select count(*) from information_schema.columns
    where table_name = 'pedidos_renglones'
      and column_name = 'cantidad_original')               as COLUMNA_de_1,
  (select count(*) from pg_description d
     join pg_class c on c.oid = d.objoid
     join pg_attribute a on a.attrelid = c.oid and a.attnum = d.objsubid
    where c.relname = 'pedidos_renglones'
      and a.attname = 'cantidad_original')                 as COMENTARIO_de_1,
  (select count(*) from pedidos_renglones
    where cantidad_original is not null)                   as corregidos_debe_dar_0,
  (select count(*) from pedidos_renglones)                 as RENGLONES_POBLACION,
  (select max(fecha_operacion) from pedidos
    where anulado_el is null)                              as TESTIGO_ultimo_pedido;
