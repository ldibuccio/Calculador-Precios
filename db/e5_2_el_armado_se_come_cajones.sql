-- E5 direccion inversa: docs/el_corte_no_cerraba_el_fifo.md
with c0 as (select fecha f0,'America/Argentina/Buenos_Aires' z
from corte_modelo where id=1),
vig as (select distinct on (cliente_id,fecha_operacion) id from pedidos
where anulado_el is null order by cliente_id,fecha_operacion,creado_en desc),
mv as (
select c.articulo_id aid,(c.procesada_el at time zone c0.z)::date f,
c.procesada_el m,'guia'::text t,c.cantidad_cajones_real q,c.importe cb,1 lado
from compras c,c0 where c.estado='recepcionado'
and (c.procesada_el at time zone c0.z)::date>c0.f0
union all
select m.articulo_id,m.fecha_operacion,m.creado_en,m.tipo,m.cantidad,
m.costo_por_bulto,1
from movimientos_stock m,c0 where m.anulado_el is null and m.cantidad>0
and (m.destino_rechazo is null or m.destino_rechazo='stock')
and ((m.tipo='stock_inicial' and m.fecha_operacion=c0.f0)
or m.fecha_operacion>c0.f0) and m.tipo<>'cierre_modelo_viejo'
union all
select rp.articulo_id,rp.fecha_operacion,rp.creado_en,'reproceso',
rp.bultos_primera,rp.costo_por_bulto_primera,1
from reprocesos rp,c0 where rp.anulado_el is null and rp.bultos_primera>0
and ((rp.tipo='inicial' and rp.fecha_operacion=c0.f0)
or rp.fecha_operacion>c0.f0)
union all
select r.articulo_id,(r.armado_el at time zone c0.z)::date,r.armado_el,
'armado',coalesce(r.cantidad_armada,r.cantidad),null,0
from pedidos_renglones r join vig v on v.id=r.pedido_id,c0
where r.armado_el is not null and r.anulado_el is null
and (r.armado_el at time zone c0.z)::date>c0.f0
union all
select m.articulo_id,m.fecha_operacion,m.creado_en,null,-m.cantidad,null,0
from movimientos_stock m,c0 where m.anulado_el is null and m.cantidad<0
and m.fecha_operacion>c0.f0 and m.tipo<>'cierre_modelo_viejo'
union all
select rp.articulo_id,rp.fecha_operacion,rp.creado_en,null,rp.bultos_tomados,null,0
from reprocesos rp,c0 where rp.anulado_el is null and rp.fecha_operacion>c0.f0
),
p as (select aid,f,t,cb,lado,sum(q) over w-q ini,sum(q) over w fin from mv
window w as (partition by aid,lado order by f,m)),
cru as (select l.cb,l.t in ('reproceso','reingreso_rechazo') trab,
least(s.fin,l.fin)-greatest(s.ini,l.ini) b
from p s join p l on l.aid=s.aid and l.lado=1
where s.lado=0 and s.t='armado' and l.f<=s.f
and least(s.fin,l.fin)>greatest(s.ini,l.ini))
select coalesce(sum(b) filter (where not trab),0) cajon,
round(coalesce(sum(b*cb) filter (where not trab),0),2) plata,
coalesce(sum(b) filter (where not trab and cb is null),0) sin_costo,
coalesce(sum(b),0) armado
from cru;
