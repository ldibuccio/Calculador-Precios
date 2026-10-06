select 'retroactivo_1_clave_y_registro' as que_migracion,
  (select count(*) from information_schema.tables
    where table_schema = 'public'
      and table_name in ('claves_especiales', 'retroactivos')) as tablas,
  (select count(*) from pg_constraint
    where conname = 'retroactivos_a_que_apunta') as checks,
  (select count(*) from claves_especiales) as claves,
  (select count(*) from retroactivos) as registrados,
  (select count(*) from compras) as testigo_compras;

-- Se corre DESPUES del bloque, aparte. tablas 2 · checks 1 · claves 0 ·
-- registrados 0.
