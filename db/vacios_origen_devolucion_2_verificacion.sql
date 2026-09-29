select 'vacios_origen_devolucion' as QUE_MIGRACION,
       (select count(*) from information_schema.columns
         where table_name = 'vacios_deposito_devoluciones'
           and column_name = 'cargada_desde') as columna,
       (select count(*) from pg_constraint
         where conname = 'vacios_dev_cargada_desde'
           and pg_get_constraintdef(oid) like '%deposito%'
           and pg_get_constraintdef(oid) like '%administracion%'
           and pg_get_constraintdef(oid) like '%compras%') as guarda_con_la_lista,
       (select count(*) from vacios_deposito_devoluciones) as devoluciones_POBLACION,
       (select max(creado_en)::date from vacios_deposito_devoluciones) as ultima_devolucion;

-- Se corre DESPUÉS del bloque 1 y por separado. Lo bueno es
-- columna 1 · guarda_con_la_lista 1, con la población igual a la de antes
-- (un add column no toca filas). La guarda se cuenta por su DEFINICIÓN y no
-- por el nombre: con la lista vieja el nombre existiría igual.
