do $$
declare problemas text; cargados integer;
begin
  select string_agg('fila ' || fila || ': ' || problema, '; ' order by fila)
    into problemas from vales_papel_revision where problema is not null;
  if problemas is not null then
    raise exception 'No se cargo ningun vale. %', problemas;
  end if;
  if not exists (select 1 from vales_papel_listado) then
    raise exception 'El listado esta vacio: primero vales_papel_1_pegar.sql';
  end if;
  insert into vales_a_cobrar (origen, proveedor_id, fecha, importe, numero, foto_ruta)
  select 'anterior_al_sistema', proveedor_id, to_date(fecha, 'DD/MM/YYYY'),
         importe, numero, foto
    from vales_papel_revision;
  get diagnostics cargados = row_count;
  delete from vales_papel_listado;
  raise notice 'vales cargados: %', cargados;
end $$;

-- VALES ANTERIORES AL SISTEMA, paso 3 de 4: CARGAR (duenio, 30/09).
-- Todo o nada, en UN bloque: si una sola fila tiene problema no se carga
-- ninguna y el error dice cuales. Si carga, vacia el listado, asi volver a
-- correrlo no duplica nada (y si se vuelven a pegar las mismas filas, la
-- revision las marca "ya estaba cargado").
-- Los vales entran EN CARTERA, con las mismas salidas, el mismo total y las
-- mismas alertas que los de una devolucion.
-- Se corre SOLO. Paso 4, aparte: vales_papel_4_verificacion.sql.
