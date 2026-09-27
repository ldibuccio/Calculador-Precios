do $$
declare
  q bigint; v bigint; n int; t text; f text[];
  fks text[] := array[
    ['compras', 'compras_marca_vacio_del_proveedor', 'marca_vacio_id'],
    ['vacios_deposito_devoluciones', 'vacios_dev_marca_del_proveedor', 'marca_vacio_id'],
    ['conteos_vacios_deposito', 'vacios_conteo_marca_del_proveedor', 'marca_vacio_id'],
    ['vacios_deposito_ajustes', 'vacios_aj_marca_del_proveedor', 'marca_vacio_id'],
    ['vacios_deposito_asignaciones', 'vacios_asig_desde_del_proveedor', 'marca_desde_id'],
    ['vacios_deposito_asignaciones', 'vacios_asig_hasta_del_proveedor', 'marca_hasta_id']];
begin
  select count(*), min(id) into n, v from proveedores
   where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'FRUTAMAX';
  if n = 0 then return; end if;
  select id into q from proveedores
   where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'FRUTAMAXSRL';
  if n > 1 or q is null then raise exception 'no es UN par: no se toca nada'; end if;
  if exists (select 1 from marcas_vacio a join marcas_vacio b using (nombre_normalizado)
              where a.proveedor_id = v and b.proveedor_id = q) then
    raise exception 'marca con el mismo nombre en los dos: no se toca nada';
  end if;

  foreach f slice 1 in array fks loop
    execute format('alter table %I drop constraint %I', f[1], f[2]);
  end loop;

  foreach t in array array['marcas_vacio', 'compras', 'vacios_deposito_devoluciones',
      'conteos_vacios_deposito', 'vacios_deposito_ajustes', 'vacios_deposito_asignaciones'] loop
    execute format('update %I set proveedor_id = $1 where proveedor_id = $2', t) using q, v;
  end loop;

  foreach f slice 1 in array fks loop
    execute format('alter table %I add constraint %I foreign key (%I, proveedor_id)'
                   ' references marcas_vacio (id, proveedor_id)', f[1], f[2], f[3]);
  end loop;
end $$;

-- Bloque 3 de 4: compras, marcas y vacíos de FRUTAMAX a FRUTAMAX S.R.L., por
-- nombre. Juntos por las FK compuestas (marca, proveedor): se sueltan, se
-- mueve todo y se vuelven a poner iguales, que las valida. Sin FRUTAMAX
-- (Palmala, o una segunda corrida) sale sin tocar nada.
