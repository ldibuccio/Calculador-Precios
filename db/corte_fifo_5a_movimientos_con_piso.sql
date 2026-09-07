-- BLOQUE A de 2. Deja en una tabla REAL los movimientos que el FIFO ve con
-- el piso puesto. Se parte en dos porque entera no entra en 2500.
-- El dia del corte entra SOLO como foto (stock_inicial y guias R 'inicial'):
-- lo demas de ese dia ya esta adentro de esa foto, en las dos puntas.
drop table if exists corte_mov;
create table corte_mov as
with c0 as (select fecha f0 from corte_modelo where id = 1),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc)
select c.articulo_id aid, (c.procesada_el at time zone
 'America/Argentina/Buenos_Aires')::date d,
 coalesce(c.cantidad_cajones_real,0) bultos, null::bigint rid, true entrada
from compras c, c0 where c.estado = 'recepcionado' and (c.procesada_el
 at time zone 'America/Argentina/Buenos_Aires')::date > c0.f0
union all select m.articulo_id, m.fecha_operacion, m.cantidad, null, true
from movimientos_stock m, c0 where m.anulado_el is null and m.cantidad > 0
 and m.tipo <> 'cierre_modelo_viejo'
 and (m.destino_rechazo is null or m.destino_rechazo = 'stock')
 and ((m.tipo = 'stock_inicial' and m.fecha_operacion = c0.f0)
   or m.fecha_operacion > c0.f0)
union all select rp.articulo_id, rp.fecha_operacion, rp.bultos_primera, rp.id, true
from reprocesos rp, c0 where rp.anulado_el is null
 and ((rp.tipo = 'inicial' and rp.fecha_operacion = c0.f0)
   or rp.fecha_operacion > c0.f0)
union all select r.articulo_id, (r.armado_el at time zone
 'America/Argentina/Buenos_Aires')::date,
 coalesce(r.cantidad_armada,r.cantidad), null, false
from pedidos_renglones r join vig v on v.id = r.pedido_id, c0
where r.armado_el is not null and r.anulado_el is null and (r.armado_el
 at time zone 'America/Argentina/Buenos_Aires')::date > c0.f0
union all select m.articulo_id, m.fecha_operacion, -m.cantidad, null, false
from movimientos_stock m, c0 where m.anulado_el is null and m.cantidad < 0
 and m.tipo <> 'cierre_modelo_viejo' and m.fecha_operacion > c0.f0
union all select rp.articulo_id, rp.fecha_operacion, rp.bultos_tomados, rp.id, false
from reprocesos rp, c0 where rp.anulado_el is null and rp.fecha_operacion > c0.f0;

select count(*) filas, count(*) filter (where entrada) entradas,
 count(*) filter (where not entrada) salidas, min(d) desde, max(d) hasta
from corte_mov;
