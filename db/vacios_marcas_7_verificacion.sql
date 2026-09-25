select 'vacios_marcas_7_las_viejas_se_anulan' as QUE_MIGRACION,
  (select count(*) from pg_constraint where conname = 'vacios_dev_con_foto'
     and pg_get_constraintdef(oid) like '%compra_id IS NOT NULL%') as guarda_exime_viejas,
  (select count(*) from pg_constraint where conname = 'vacios_dev_con_foto'
     and convalidated) as guarda_validada,
  (select count(*) from vacios_deposito_devoluciones
     where btrim(coalesce(foto_ruta, '')) = '') as viejas_sin_foto,
  (select count(*) from vacios_deposito_devoluciones
     where compra_id is null and btrim(coalesce(foto_ruta, '')) = '') as ofensores,
  (select count(*) from vacios_deposito_devoluciones) as devoluciones_POBLACION;
