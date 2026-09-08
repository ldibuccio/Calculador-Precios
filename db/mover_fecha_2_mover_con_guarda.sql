-- MUEVE LA FECHA DE UN PEDIDO, con guarda. Editar el id y las dos fechas.
-- Un solo do $$: la guarda y el update tienen que ser todo-o-nada. Sueltos,
-- el update corre igual aunque la guarda haya encontrado el choque.
-- NO se rompe nada de lo cargado: renglones, fichas, armado y kilos cuelgan
-- del pedido por id y no de la fecha. Lo que SI cambia:
--   - el precio de venta se resuelve A LA FECHA (precios_venta_historial,
--     anclado al mediodia), asi que la Rentabilidad pasa a usar el del dia
--     nuevo. No hay precio congelado en el pedido.
--   - la venta se mueve de dia en la Rentabilidad Real.
--   - la atribucion de LOTES no se mueve: el FIFO ordena por armado_el, que
--     es cuando se tildo, no por la fecha del pedido.
do $$
declare
  v_pedido  bigint := 0;              -- <<< el id que devolvio mover_fecha_1
  v_nueva   date   := date '2026-09-08';
  v_cliente bigint;
  v_vieja   date;
  v_choque  bigint;
begin
  select cliente_id, fecha_operacion into v_cliente, v_vieja
  from pedidos where id = v_pedido and anulado_el is null;
  if v_cliente is null then
    raise exception 'No hay pedido vigente con id %', v_pedido;
  end if;

  -- LA GUARDA: si en la fecha nueva ya hay otro vigente de este cliente,
  -- despues del update habria DOS y el FIFO se quedaria en silencio con el
  -- mas nuevo por creado_en. Se aborta y se decide a mano cual queda.
  select id into v_choque from pedidos
  where cliente_id = v_cliente and fecha_operacion = v_nueva
    and anulado_el is null and id <> v_pedido
  order by creado_en desc limit 1;
  if v_choque is not null then
    raise exception 'YA HAY un pedido vigente (id %) de ese cliente el %. '
      'Mover este dejaria dos y las cuentas elegirian uno solo. Decidir antes.',
      v_choque, v_nueva;
  end if;

  update pedidos set fecha_operacion = v_nueva where id = v_pedido;
  raise notice 'Pedido % movido del % al %', v_pedido, v_vieja, v_nueva;
end $$;
