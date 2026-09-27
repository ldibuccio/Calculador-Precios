do $$
declare q bigint; v bigint; n int; m int; codigo_v text;
begin
  select count(*), min(id) into n, v from proveedores
   where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'PRODUCTOSDONLAZZARO';
  if n = 0 or not exists (select 1 from proveedores_codigos where codigo = 'N09P39') then
    return;
  end if;
  select count(*), min(id) into m, q from proveedores
   where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'DONLAZZARO';
  if n > 1 or m <> 1 then raise exception 'no es UN par: no se toca nada'; end if;
  if exists (select 1 from guias_compra a join guias_compra b
               using (fecha_operacion, de_deposito)
              where a.proveedor_id = v and b.proveedor_id = q) then
    raise exception 'guias del mismo dia en los dos: no se toca nada';
  end if;
  if exists (select 1 from vacios_deposito_foto where proveedor_id = v and cantidad <> 0)
     and exists (select 1 from vacios_deposito_foto where proveedor_id = q) then
    raise exception 'los dos tienen foto de vacios con cajones: no se toca nada';
  end if;

  update guias_compra set proveedor_id = q where proveedor_id = v;
  update movimientos_stock set proveedor_devolucion_id = q where proveedor_devolucion_id = v;
  delete from aprendizaje_articulos a where a.proveedor_id = v
     and exists (select 1 from aprendizaje_articulos b
                  where b.proveedor_id = q and b.texto_leido = a.texto_leido);
  update aprendizaje_articulos set proveedor_id = q where proveedor_id = v;
  if exists (select 1 from vacios_deposito_foto where proveedor_id = q) then
    delete from vacios_deposito_foto where proveedor_id = v;
  else
    update vacios_deposito_foto set proveedor_id = q where proveedor_id = v;
  end if;

  select codigo_puesto into codigo_v from proveedores where id = v;
  delete from proveedores where id = v;
  insert into proveedores_codigos (proveedor_id, codigo) values (q, codigo_v);
end $$;

-- Bloque 2 de 2, va DESPUÉS del 1: guías, devoluciones, aprendizaje y foto de
-- vacíos. Borra PRODUCTOS DON LAZZARO y su código (L02P44) pasa a alternativo
-- de DON LAZZARO. Si algo sigue apuntando al que se va, el delete rebota por la
-- FK y no se escribe nada. Misma guarda de Palmala que el bloque 1.
