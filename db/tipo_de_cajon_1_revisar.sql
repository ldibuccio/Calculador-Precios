select 'tipo_de_cajon_1_revisar' as que_migracion,
  (select count(*) from information_schema.columns
    where table_name = 'proveedores' and column_name = 'tipo_cajon_id') as columna_1,
  (select count(*) from information_schema.tables where table_name = 'tipos_cajon') as tabla_1,
  (select count(*) from tipos_cajon) as tipos_cargados,
  (select count(*) from proveedores where tipo_cajon_id is not null) as proveedores_con_tipo,
  (select string_agg(p.nombre || ' → ' || t.nombre, ' · ' order by p.nombre)
     from proveedores p join tipos_cajon t on t.id = p.tipo_cajon_id) as lo_que_se_pierde,
  (select count(*) from pg_constraint
    where confrelid = 'tipos_cajon'::regclass and contype = 'f') as fks_que_la_apuntan_1,
  (select count(*) from proveedores) as proveedores_POBLACION;

-- TIPO DE CAJÓN POR PROVEEDOR, paso 2, bloque 1: SOLO LEE. Dice qué se va a
-- perder antes de borrarlo. Se corre en las dos bases, antes del bloque 2.
-- fks_que_la_apuntan tiene que dar 1 (la de proveedores.tipo_cajon_id): si da
-- más, algo más apunta a la tabla y el bloque 2 va a abortar sin tocar nada.
