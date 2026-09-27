do $$
declare q bigint; v bigint; n int; codigo_v text;
begin
  select count(*), min(id) into n, v from proveedores
   where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'FRUTAMAX';
  if n = 0 then return; end if;
  select id into q from proveedores
   where regexp_replace(upper(nombre), '[^A-Z0-9]', '', 'g') = 'FRUTAMAXSRL';
  if n > 1 or q is null then raise exception 'no es UN par: no se toca nada'; end if;
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

-- Bloque 4 de 4, va DESPUÉS del 3: guías, devoluciones al proveedor,
-- aprendizaje y foto de vacíos. Del aprendizaje repetido queda el de FRUTAMAX
-- S.R.L. ("limon" queda en Limón). Borra FRUTAMAX, y su código (N09P39) pasa a
-- ser alternativo de FRUTAMAX S.R.L. Si quedara algo apuntando a FRUTAMAX, el
-- delete rebota por la FK y no se escribe nada.
