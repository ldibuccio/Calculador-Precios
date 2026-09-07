-- Los movimientos de un articulo con LA HORA QUE CADA UNO USA DE VERDAD, y
-- diciendo cual reloj es. No son el mismo: la cuenta 1 mira armado_el para
-- el armado, procesada_el para las compras y fecha_operacion (una FECHA SIN
-- HORA) para movimientos y reprocesos. Mezclarlos en un solo orden es lo que
-- hizo que la reconciliacion de Mango diera distinto en cada vuelta.
-- La columna `visible` dice si esa fila EXISTIA al momento del conteo: eso
-- es lo unico que decide si entro en su stock_sistema congelado.
with a0 as (select id from articulos where nombre ilike '%mango%'),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
ref as (select max(creado_en) t from conteos_stock cs join a0 on a0.id=cs.articulo_id)
select (x.reloj at time zone 'America/Argentina/Buenos_Aires')::timestamp(0) hora,
 x.cual_reloj, x.que, x.bultos,
 case when x.escrito <= ref.t then 'ya estaba' else 'NO estaba' end as visible
from (
 select c.procesada_el reloj, 'procesada_el' cual_reloj, c.procesada_el escrito,
  'compra '||c.id que, coalesce(c.cantidad_cajones_real,0) bultos
 from compras c join a0 on a0.id=c.articulo_id where c.estado='recepcionado'
 union all select m.fecha_operacion, 'fecha_operacion (sin hora)', m.creado_en,
  'mov '||m.id||': '||m.tipo, m.cantidad
 from movimientos_stock m join a0 on a0.id=m.articulo_id where m.anulado_el is null
 union all select rp.fecha_operacion, 'fecha_operacion (sin hora)', rp.creado_en,
  'guia R '||rp.id||' primera', rp.bultos_primera
 from reprocesos rp join a0 on a0.id=rp.articulo_id
 where rp.anulado_el is null and rp.bultos_primera > 0
 union all select rp.fecha_operacion, 'fecha_operacion (sin hora)', rp.creado_en,
  'guia R '||rp.id||' TOMO', -rp.bultos_tomados
 from reprocesos rp join a0 on a0.id=rp.articulo_id
 where rp.anulado_el is null and rp.bultos_tomados > 0
 union all select r.armado_el, 'armado_el', r.armado_el,
  'armado renglon '||r.id, -coalesce(r.cantidad_armada,r.cantidad)
 from pedidos_renglones r join vig v on v.id=r.pedido_id join a0 on a0.id=r.articulo_id
 where r.armado_el is not null and r.anulado_el is null
) x, ref
where x.reloj >= timestamptz '2026-09-05 00:00-03'
order by x.escrito;
