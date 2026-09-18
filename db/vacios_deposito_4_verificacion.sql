select 'vacios_deposito_4' as QUE_MIGRACION,
  (select count(*) from pg_tables where schemaname = 'public'
     and tablename = 'tipos_cajon')                                as t_tipos_cajon,
  (select count(*) from information_schema.columns
     where table_name = 'proveedores'
       and column_name = 'tipo_cajon_id')                          as col_en_proveedores,
  (select count(*) from pg_constraint
     where conrelid = to_regclass('public.proveedores') and contype = 'f'
       and pg_get_constraintdef(oid) like '%tipos_cajon%')         as fk_a_tipos_cajon,
  (select count(*) from pg_tables where schemaname = 'public'
     and tablename = 'vacios_deposito_devoluciones')               as t_devoluciones,
  (select count(*) from pg_tables where schemaname = 'public'
     and tablename = 'conteos_vacios_deposito')                    as t_conteos,
  (select count(*) from pg_constraint
     where conrelid = to_regclass('public.vacios_deposito_devoluciones')
       and contype = 'c'
       and pg_get_constraintdef(oid) like '%cantidad > 0%')        as guarda_cantidad,
  (select count(*) from pg_attribute
     where attrelid = to_regclass('public.vacios_deposito_devoluciones')
       and attname = 'compra_id' and attnotnull)                   as guarda_compra_obligatoria,
  (select count(*) from pg_constraint
     where conrelid = to_regclass('public.conteos_vacios_deposito')
       and contype = 'c'
       and pg_get_constraintdef(oid) like '%cantidad >= 0%')       as guarda_conteo_no_negativo,
  (select count(*) from proveedores)                               as POBLACION_proveedores,
  (select max(procesada_el)::date from compras
     where estado = 'recepcionado')                                as TESTIGO_ultima_recepcion;

-- CORRERLA SOLA, aparte de los tres `do $$`. Pegada abajo de un bloque, el
-- editor se queda con la última y EL `do` NO SE EJECUTA: sin error, y con una
-- salida que se ve igual que la de un bloque que sí corrió.
--
-- Las OCHO primeras columnas tienen que dar 1. Se cuentan POR DEFINICIÓN y no
-- por nombre: un check con el nombre puesto y otro texto adentro existe igual.
-- `to_regclass` y no `::regclass`: una tabla que falta cuenta 0 en SU columna
-- en vez de reventar la consulta y dejar las otras siete sin contestar.
--
-- LAS DOS ÚLTIMAS NO SON ADORNO: las ocho primeras dan lo mismo en las dos
-- bases por diseño, así que el testigo es lo único que dice de cuál base es
-- la fila. Se pegan LAS DOS.
