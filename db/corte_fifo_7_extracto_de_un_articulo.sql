-- El extracto de UN articulo desde el corte: cada movimiento con su saldo
-- corrido, para ver en QUE MOMENTO se fue abajo de cero. Cambiar 'mango'
-- por el articulo que se quiera mirar.
-- OJO: el saldo mezcla CAJONES y CAJAS, igual que la cuenta 1 del sistema.
-- No es un error de la consulta: es lo que el sistema cree, que es lo que
-- se viene a mirar.
with c0 as (select fecha from corte_modelo where id = 1),
a0 as (select id, nombre from articulos where nombre ilike '%mango%'),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
ev(d, orden, que, detalle, bultos) as (
 select (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date,
  1, 'compra', p.nombre, coalesce(c.cantidad_cajones_real, 0)
 from compras c join a0 on a0.id = c.articulo_id
 join proveedores p on p.id = c.proveedor_id
 where c.estado = 'recepcionado'
   and (c.procesada_el at time zone
   'America/Argentina/Buenos_Aires')::date >= (select fecha from c0)
 union all
 select m.fecha_operacion, 1, m.tipo, m.motivo, m.cantidad
 from movimientos_stock m join a0 on a0.id = m.articulo_id
 where m.anulado_el is null and m.fecha_operacion >= (select fecha from c0)
 union all
 select rp.fecha_operacion, 1, 'guia R ' || rp.id || ' primera',
  rp.tipo, rp.bultos_primera
 from reprocesos rp join a0 on a0.id = rp.articulo_id
 where rp.anulado_el is null and rp.bultos_primera > 0
   and rp.fecha_operacion >= (select fecha from c0)
 union all
 select rp.fecha_operacion, 2, 'guia R ' || rp.id || ' TOMO',
  rp.tipo, -rp.bultos_tomados
 from reprocesos rp join a0 on a0.id = rp.articulo_id
 where rp.anulado_el is null and rp.bultos_tomados > 0
   and rp.fecha_operacion >= (select fecha from c0)
 union all
 select (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date,
  2, 'armado', 'renglon ' || r.id, -coalesce(r.cantidad_armada, r.cantidad)
 from pedidos_renglones r join a0 on a0.id = r.articulo_id
 join vig v on v.id = r.pedido_id
 where r.armado_el is not null and r.anulado_el is null
   and (r.armado_el at time zone
   'America/Argentina/Buenos_Aires')::date >= (select fecha from c0)
)
select (select nombre from a0) as articulo, d as fecha, que, detalle, bultos,
 sum(bultos) over (order by d, orden, que
   rows between unbounded preceding and current row) as saldo
from ev order by d, orden, que;
