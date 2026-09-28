do $$
declare
  r record; b record; m record; v_arr bigint; v_marca bigint; total int := 0;
begin
  if not exists (select 1 from proveedores_codigos where codigo = 'N09P39') then
    raise notice 'no es Frutamax: no se hace nada'; return;
  end if;
  if exists (select 1 from vacios_deposito_arranques where motivo = 'Conteo físico 28/09') then
    raise notice 'el conteo del 28/09 ya estaba cargado: no se hace nada'; return;
  end if;
  if not exists (select 1 from proveedores where codigo_puesto = 'N00P00') then
    insert into proveedores (nombre, codigo_puesto) values ('Sin Proveedor', 'N00P00');
  end if;
  insert into vacios_deposito_arranques (motivo) values ('Conteo físico 28/09')
  returning id into v_arr;
  for r in select * from vacios_conteo_2809() order by orden loop
    select * into b from vacios_conteo_2809_proveedor(r.pn);
    if b.proveedor_id is null then
      raise exception 'proveedor "%": % con ese nombre y % que lo contienen; tiene que haber uno',
        r.pn, b.iguales, b.parecidos;
    end if;
    select * into m from vacios_conteo_2809_marca(b.proveedor_id, r.marca);
    v_marca := m.marca_id;
    if v_marca is null and m.parecidas > 0 then
      raise exception 'marca "%": % parecidas y ninguna igual', r.marca, m.parecidas;
    elsif v_marca is null then
      insert into marcas_vacio (proveedor_id, nombre, nombre_normalizado)
      values (b.proveedor_id, r.marca, m.plegado) returning id into v_marca;
    else
      -- "Tomjug" pasa a llamarse "Tom Jug"; "La union" se queda como está.
      update marcas_vacio
         set nombre = case when nombre_normalizado = m.plegado then nombre else r.marca end,
             nombre_normalizado = m.plegado, activo = true
       where id = v_marca;
    end if;
    insert into vacios_deposito_arranque_pilas (arranque_id, proveedor_id, marca_vacio_id, cantidad)
    values (v_arr, b.proveedor_id, v_marca, r.cant);
    total := total + r.cant;
  end loop;
  if total <> 1070 then raise exception 'el total dio %, no 1070', total; end if;
end $$;

-- ARRANQUE DE VACÍOS DESDE EL CONTEO FÍSICO DEL 28/09, bloque 5 (el único
-- que escribe datos). Un solo do: carga las 17 pilas enteras o nada.
-- Solo en Frutamax (la única base con N09P39): en Palmala sale sin tocar
-- nada. Una segunda corrida no hace nada. Crea "Sin Proveedor" (N00P00) y
-- las marcas que falten. La verificación va APARTE, en otra corrida:
-- vacios_conteo_2809_6_verificacion.sql.
