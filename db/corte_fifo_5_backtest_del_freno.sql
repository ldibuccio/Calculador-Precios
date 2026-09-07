-- ¿Las guias R ya cargadas pasarian el freno con el piso? Ventana exacta:
-- entradas HASTA su fecha, salidas HASTA EL DIA ANTERIOR, sin las de despues.
with c0 as (select fecha from corte_modelo where id = 1),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
ent(aid, d, bultos, rid) as (
 select c.articulo_id, (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')
 ::date, coalesce(c.cantidad_cajones_real,0), null::bigint
 from compras c where c.estado = 'recepcionado'
 union all select m.articulo_id, m.fecha_operacion, m.cantidad, null
 from movimientos_stock m where m.anulado_el is null and m.cantidad > 0
 and m.tipo <> 'cierre_modelo_viejo'
 and (m.destino_rechazo is null or m.destino_rechazo = 'stock')
 union all select rp.articulo_id, rp.fecha_operacion, rp.bultos_primera, rp.id
 from reprocesos rp where rp.anulado_el is null
),
sal(aid, d, bultos, rid) as (
 select r.articulo_id, (r.armado_el at time zone 'America/Argentina/Buenos_Aires')
 ::date, coalesce(r.cantidad_armada,r.cantidad), null::bigint from pedidos_renglones r
 join vig v on v.id = r.pedido_id
 where r.armado_el is not null and r.anulado_el is null
 union all
 select m.articulo_id, m.fecha_operacion, -m.cantidad, null from movimientos_stock m
 where m.anulado_el is null and m.cantidad < 0 and m.tipo <> 'cierre_modelo_viejo'
 union all select rp.articulo_id, rp.fecha_operacion, rp.bultos_tomados, rp.id
 from reprocesos rp where rp.anulado_el is null
),
g as (select rp.id, rp.articulo_id aid, rp.fecha_operacion f, rp.bultos_tomados t
 from reprocesos rp where rp.anulado_el is null and rp.tipo = 'normal'
 and rp.fecha_operacion >= (select fecha from c0)),
r as (
 select g.id, g.f, g.t, a.nombre, greatest(
   (select coalesce(sum(bultos),0) from ent where ent.aid = g.aid and ent.d <= g.f
     and ent.d >= (select fecha from c0) and (ent.rid is null or ent.rid < g.id))
 - (select coalesce(sum(bultos),0) from sal where sal.aid = g.aid and sal.d < g.f
     and sal.d >= (select fecha from c0) and (sal.rid is null or sal.rid < g.id)),
   0) as disp
 from g join articulos a on a.id = g.aid
)
select count(*) filter (where t > disp) over () as frenarian,
 count(*) over () as guias_desde_el_corte, id as guia, f as fecha,
 nombre as articulo, t as tomo, disp as disponible,
 case when t > disp then 'FRENA' else '' end as res
from r order by (t > disp) desc, f, id;
