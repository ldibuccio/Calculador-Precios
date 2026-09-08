-- ANULA UN PEDIDO ENTERO. Editar v_pedido.
-- Baja logica, nunca DELETE: el pedido queda de registro, igual que hace
-- crear_pedido cuando uno reemplaza a otro.
-- ALCANZA CON pedidos.anulado_el. Los 22 lectores de pedidos_renglones que
-- trabajan POR RANGO descartan el pedido anulado, o por el CTE `vigentes`
-- (que es `from pedidos where anulado_el is null`) o por un
-- `p.anulado_el is null` propio. Los que no lo filtran piden UN pedido o UN
-- renglon por id —pantallas de detalle— y no suman en ninguna cuenta.
-- Los renglones NO se tocan: anularlos ademas seria escribir el mismo
-- hecho dos veces, y el dia que uno se desanule sin el otro quedaria un
-- pedido a medio anular. Ademas anular_renglon_pedido BORRA el armado
-- (armado_el = NULL), asi que si el pedido se restaura se perderia.
do $$
declare
  v_pedido  bigint := 19;
  v_armados int;
  v_estado  timestamptz;
begin
  -- EXISTE Y ESTA VIVO, en un select SIN agregado. Con count(*) adentro,
  -- `not found` NUNCA se dispara: un agregado devuelve UNA FILA con 0
  -- aunque no haya nada que contar. Probado: con esa version, anular un id
  -- inexistente salia DO, y sobre uno YA anulado pisaba su anulado_el
  -- original con la fecha de hoy.
  select p.anulado_el into v_estado from pedidos p where p.id = v_pedido;
  if not found then
    raise exception 'No existe el pedido %', v_pedido;
  end if;
  if v_estado is not null then
    raise exception 'El pedido % ya estaba anulado el %', v_pedido, v_estado;
  end if;

  select count(*) filter (where r.armado_el is not null and r.anulado_el is null)
    into v_armados
  from pedidos_renglones r where r.pedido_id = v_pedido;

  -- LA GUARDA: con renglones armados, anular el pedido borra salidas de
  -- stock que ya ocurrieron -- la mercaderia salio del galpon igual. Eso se
  -- decide a mano, renglon por renglon, no de un saque.
  if v_armados > 0 then
    raise exception 'El pedido % tiene % renglon(es) ARMADOS. Anularlo borraria '
      'salidas de stock que ya pasaron. Desarmar primero o decidir a mano.',
      v_pedido, v_armados;
  end if;

  update pedidos set anulado_el = now() where id = v_pedido;
end $$;
