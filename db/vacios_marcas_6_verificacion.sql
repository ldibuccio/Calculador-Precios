select
  'vacios_marcas' as QUE_MIGRACION,
  (select count(*) from information_schema.tables where table_name in
     ('marcas_vacio', 'vacios_deposito_ajustes', 'vacios_deposito_asignaciones')) as tablas_de_3,
  (select count(*) from information_schema.columns where (table_name, column_name) in
     (('compras', 'marca_vacio_id'), ('compras', 'marca'),
      ('vacios_deposito_devoluciones', 'marca_vacio_id'),
      ('conteos_vacios_deposito', 'marca_vacio_id'))) as columnas_de_4,
  (select count(*) from pg_constraint where contype = 'f' and conname in
     ('compras_marca_vacio_del_proveedor', 'vacios_dev_marca_del_proveedor',
      'vacios_conteo_marca_del_proveedor', 'vacios_aj_marca_del_proveedor',
      'vacios_asig_desde_del_proveedor', 'vacios_asig_hasta_del_proveedor')) as fks_de_6,
  (select count(*) from pg_constraint where conname in ('vacios_dev_con_foto',
      'vacios_aj_cantidad_y_motivo', 'vacios_asig_cantidad_y_pilas')
      and pg_get_constraintdef(oid) ~* '(foto_ruta|motivo|distinct)') as guardas_de_3,
  (select is_nullable from information_schema.columns
    where table_name = 'vacios_deposito_devoluciones' and column_name = 'compra_id') as compra_acepta_null,
  (select count(*) from vacios_deposito_devoluciones) as devoluciones_POBLACION,
  (select count(*) from vacios_deposito_devoluciones
    where btrim(coalesce(foto_ruta, '')) = '') as viejas_sin_foto,
  (select max(procesada_el)::date from compras where estado = 'recepcionado') as ultima_recepcion;

-- Aparte de los `do`, en las DOS bases. Tiene DOS resultados buenos:
--   después de los bloques 1 a 4 (antes del deploy): 3 · 4 · 6 · 2 · YES
--   después del bloque 5 (foto obligatoria):         3 · 4 · 6 · 3 · YES
-- `viejas_sin_foto` no tiene que dar 0: son las devoluciones de antes de la
-- regla, y el CHECK NOT VALID las deja como están.
