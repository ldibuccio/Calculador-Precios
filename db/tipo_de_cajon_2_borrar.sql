do $$
begin
  if exists (select 1 from pg_constraint
              where confrelid = to_regclass('tipos_cajon') and contype = 'f'
                and conrelid <> 'proveedores'::regclass) then
    raise exception 'otra tabla apunta a tipos_cajon: no se borra nada';
  end if;
  alter table proveedores drop column if exists tipo_cajon_id;
  drop table if exists tipos_cajon;
end $$;

-- TIPO DE CAJÓN POR PROVEEDOR, paso 2, bloque 2: BORRA la columna
-- proveedores.tipo_cajon_id y la tabla tipos_cajon (dueño, 29/09: lo
-- reemplazan las marcas). Va en las DOS bases y SOLO DESPUÉS del deploy del
-- paso 1: hasta ese deploy el código vivo todavía las lee. Un solo do: borra
-- las dos o ninguna. Una segunda corrida no hace nada. No toca filas de
-- proveedores. La verificación va APARTE, en otra corrida: bloque 3.
