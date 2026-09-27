with q as (select id from proveedores
            where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'FRUTAMAXSRL')
select 'codigos_1_a_4' as QUE_MIGRACION,
  (select count(*) from information_schema.tables
    where table_name = 'proveedores_codigos') as tabla,
  (select count(*) from information_schema.columns
    where table_name = 'compras' and column_name = 'codigo_llegada') as columna,
  (select count(*) from pg_trigger
    where tgname in ('codigo_unico_alternativo', 'codigo_unico_principal')) as guardas_de_2,
  (select count(*) from pg_constraint
    where conname in ('compras_marca_vacio_del_proveedor', 'vacios_dev_marca_del_proveedor',
                      'vacios_conteo_marca_del_proveedor', 'vacios_aj_marca_del_proveedor',
                      'vacios_asig_desde_del_proveedor', 'vacios_asig_hasta_del_proveedor')
  ) as fk_marca_de_6,
  (select count(*) from compras where codigo_llegada is null) as compras_SIN_codigo,
  (select count(*) from proveedores
    where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'FRUTAMAX') as FRUTAMAX_que_queda,
  (select string_agg(p.codigo_puesto || coalesce(' + ' || (select string_agg(codigo, ' + ')
            from proveedores_codigos pc where pc.proveedor_id = p.id), ''), ' | ')
     from proveedores p where p.id in (select id from q)) as codigos_de_SRL,
  (select string_agg(codigo_llegada || ': ' || n, ' · ') from (
     select codigo_llegada, count(*) n from compras
      where proveedor_id in (select id from q) group by 1 order by 1) s) as compras_de_SRL,
  (select count(*) from aprendizaje_articulos
    where proveedor_id in (select id from q)) as aprendizaje_de_SRL,
  (select sum(cantidad) from vacios_deposito_foto
    where proveedor_id in (select id from q)) as foto_vacios_de_SRL,
  (select count(*) from proveedores_codigos) as codigos_alternativos,
  (select count(*) from proveedores) as POBLACION_proveedores,
  (select max(procesada_el)::date from compras) as ultima_recepcion;

-- Correr DESPUÉS de los cuatro bloques. Frutamax: tabla 1 · columna 1 ·
-- guardas 2 · fk 6 · sin código 0 · FRUTAMAX 0 · N09P41 + N09P39 · compras
-- N09P39: 26 · N09P41: 326 · foto 798. Palmala: lo mismo en las cinco
-- primeras, y el resto vacío o en cero.
