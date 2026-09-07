-- DE DÓNDE SALEN LOS DECIMALES. El FIFO no reparte proporcional: consume
-- min(restante, pendiente), así que si entran enteros salen enteros. Un bulto
-- fraccionado en el desglose viene de una CANTIDAD FRACCIONADA cargada antes.
-- Esto busca esa fila, en las cuatro tablas que alimentan el reparto.
-- Cambiar el artículo de abajo (o sacar el filtro para verlo en todos).
with art as (select id, nombre from articulos where nombre ilike '%cherry%')
select 'compra recepcionada' as donde, c.id, c.fecha_operacion, a.nombre as articulo,
       c.cantidad_cajones_real as cantidad, 'cantidad_cajones_real' as columna
from compras c join art a on a.id = c.articulo_id
where c.estado = 'recepcionado' and c.cantidad_cajones_real is not null
  and c.cantidad_cajones_real <> trunc(c.cantidad_cajones_real)
union all
select 'movimiento de stock', m.id, m.fecha_operacion, a.nombre, m.cantidad, 'cantidad ('||m.tipo||')'
from movimientos_stock m join art a on a.id = m.articulo_id
where m.anulado_el is null and m.cantidad <> trunc(m.cantidad)
union all
select 'guía R (lo que produjo)', r.id, r.fecha_operacion, a.nombre, r.bultos_primera, 'bultos_primera'
from reprocesos r join art a on a.id = r.articulo_id
where r.anulado_el is null and r.bultos_primera <> trunc(r.bultos_primera)
union all
select 'guía R (lo que tomó)', r.id, r.fecha_operacion, a.nombre, r.bultos_tomados, 'bultos_tomados'
from reprocesos r join art a on a.id = r.articulo_id
where r.anulado_el is null and r.bultos_tomados <> trunc(r.bultos_tomados)
union all
select 'renglón de pedido armado', pr.id, p.fecha_operacion, a.nombre,
       coalesce(pr.cantidad_armada, pr.cantidad), 'cantidad armada/pedida'
from pedidos_renglones pr
join pedidos p on p.id = pr.pedido_id
join art a on a.id = pr.articulo_id
where pr.anulado_el is null and p.anulado_el is null and pr.armado_el is not null
  and coalesce(pr.cantidad_armada, pr.cantidad) <> trunc(coalesce(pr.cantidad_armada, pr.cantidad))
order by 3, 1;
