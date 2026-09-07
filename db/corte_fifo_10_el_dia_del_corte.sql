-- Que se movio EL DIA DEL CORTE, por articulo. Es lo que estaba inflando el
-- faltante: la foto se toma a la tarde, asi que las cajas armadas y
-- entregadas esa manana ya no estaban en el piso cuando se conto.
-- entregadas_ese_dia es, articulo por articulo, cuanto se le restaba de mas
-- al faltante de corte_fifo_8 en su version vieja.
with c0 as (select fecha from corte_modelo where id = 1),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
ent as (
 select r.articulo_id aid, sum(coalesce(r.cantidad_armada, r.cantidad)) e,
  count(*) n, min(r.armado_el) prim, max(r.armado_el) ult
 from pedidos_renglones r join vig v on v.id = r.pedido_id
 where r.armado_el is not null and r.anulado_el is null
   and (r.armado_el at time zone
   'America/Argentina/Buenos_Aires')::date = (select fecha from c0)
 group by 1
),
rep as (
 select articulo_id aid,
  sum(bultos_primera) filter (where tipo = 'normal') a,
  sum(bultos_tomados) filter (where tipo = 'normal') t,
  sum(bultos_primera) filter (where tipo = 'inicial') foto_cajas
 from reprocesos where anulado_el is null
   and fecha_operacion = (select fecha from c0)
 group by 1
),
ini as (
 select articulo_id aid, sum(cantidad) foto_cajones
 from movimientos_stock where anulado_el is null and tipo = 'stock_inicial'
   and fecha_operacion = (select fecha from c0)
 group by 1
)
select a.nombre as articulo,
 coalesce(e.e, 0) as entregadas_ese_dia,
 coalesce(e.n, 0) as renglones,
 (e.prim at time zone 'America/Argentina/Buenos_Aires')::time(0) as primer_armado,
 (e.ult at time zone 'America/Argentina/Buenos_Aires')::time(0) as ultimo_armado,
 coalesce(r.a, 0) as armadas_ese_dia,
 coalesce(r.t, 0) as tomados_ese_dia,
 coalesce(i.foto_cajones, 0) as foto_cajones,
 coalesce(r.foto_cajas, 0) as foto_cajas
from ent e
full join rep r on r.aid = e.aid
full join ini i on i.aid = coalesce(e.aid, r.aid)
join articulos a on a.id = coalesce(e.aid, r.aid, i.aid)
order by 2 desc, 1;
