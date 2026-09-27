with q as (select id from proveedores
            where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'FRUTAMAXSRL'),
     v as (select id from proveedores
            where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'FRUTAMAX'),
     gq as (select * from guias_compra where proveedor_id in (select id from q)),
     gv as (select * from guias_compra where proveedor_id in (select id from v)),
     gc as (select gv.id as g_va, gq.id as g_queda from gv
              join gq using (fecha_operacion, de_deposito))
select 'proveedor_duplicado_0' as QUE_MIGRACION,
  (select count(*) from q) as filas_queda,
  (select count(*) from v) as filas_se_va,
  (select string_agg(id || ' ' || codigo_puesto || ' ' || nombre, ' | ')
     from proveedores where id in (select id from q union select id from v)) as cuales,
  (select count(*) from compras where proveedor_id in (select id from v)) as compras_se_va,
  (select count(*) from gc) as GUIAS_MISMO_DIA,
  (select count(*) from compras where guia_id in (select g_va from gc)) as compras_en_esas_guias,
  (select count(*) from fotos_guia a join fotos_guia b using (foto_ruta)
    where a.guia_id in (select id from gv)
      and b.guia_id in (select id from gq)) as FOTOS_EN_LAS_DOS,
  (select count(*) from aprendizaje_articulos a join aprendizaje_articulos b using (texto_leido)
    where a.proveedor_id in (select id from v)
      and b.proveedor_id in (select id from q)) as APRENDIZAJE_MISMO_TEXTO,
  (select count(*) from vacios_deposito_foto
    where proveedor_id in (select id from v)) as foto_vacios_se_va,
  (select count(*) from vacios_deposito_foto
    where proveedor_id in (select id from q)) as foto_vacios_queda,
  (select count(*) from marcas_vacio a join marcas_vacio b using (nombre_normalizado)
    where a.proveedor_id in (select id from v)
      and b.proveedor_id in (select id from q)) as MARCAS_MISMO_NOMBRE,
  (select count(*) from conteos_vacios_deposito
    where proveedor_id in (select id from v)) as conteos_vacios_se_va,
  (select count(*) from conteos_vacios_deposito a join conteos_vacios_deposito b using (fecha)
    where a.proveedor_id in (select id from v)
      and b.proveedor_id in (select id from q)) as CONTEOS_MISMO_DIA,
  (select count(*) from proveedores) as POBLACION_proveedores,
  (select max(procesada_el)::date from compras) as ultima_recepcion;
