-- E5: docs/el_corte_no_cerraba_el_fifo.md
with c0 as (select fecha f0,'America/Argentina/Buenos_Aires' z
from corte_modelo where id=1),
vig as (select distinct on (cliente_id,fecha_operacion) id from pedidos
where anulado_el is null order by cliente_id,fecha_operacion,creado_en desc),
mv as (
select c.articulo_id aid,(c.procesada_el at time zone c0.z)::date d,
c.procesada_el m,c.cantidad_cajones_real q,c.importe cb,false trab,1 lado
from compras c,c0 where c.estado='recepcionado'
and (c.procesada_el at time zone c0.z)::date>c0.f0
union all
select m.articulo_id,m.fecha_operacion,m.creado_en,abs(m.cantidad),
m.costo_por_bulto,m.tipo='reingreso_rechazo',2-(m.cantidad>0)::int
from movimientos_stock m,c0 where m.anulado_el is null
and m.tipo<>'cierre_modelo_viejo'
and (m.cantidad<0 or m.destino_rechazo is null or m.destino_rechazo='stock')
and ((m.tipo='stock_inicial' and m.fecha_operacion=c0.f0 and m.cantidad>0)
or m.fecha_operacion>c0.f0)
union all
select rp.articulo_id,rp.fecha_operacion,rp.creado_en,rp.bultos_primera,rp.costo_por_bulto_primera,true,1
from reprocesos rp,c0 where rp.anulado_el is null and rp.bultos_primera>0
and ((rp.tipo='inicial' and rp.fecha_operacion=c0.f0)
or rp.fecha_operacion>c0.f0)
union all
select r.articulo_id,(r.armado_el at time zone c0.z)::date,r.armado_el,
coalesce(r.cantidad_armada,r.cantidad),null,false,3
from pedidos_renglones r join vig v on v.id=r.pedido_id,c0
where r.armado_el is not null and r.anulado_el is null
and (r.armado_el at time zone c0.z)::date>c0.f0
union all
select rp.articulo_id,rp.fecha_operacion,rp.creado_en,rp.bultos_tomados,null,false,2
from reprocesos rp,c0 where rp.anulado_el is null and rp.fecha_operacion>c0.f0),
p as (select aid,d,cb,trab,lado,sum(q) over w-q ini,sum(q) over w fin
from mv window w as (partition by aid,(lado=1) order by d,m)),
j as (select s.aid,s.ini si,s.fin sf,l.trab,l.cb,l.ini li,l.fin lf
from p s join p l on l.aid=s.aid and l.lado=1 and l.d<=s.d where s.lado=3),
k as (select aid,si,trab,cb,greatest(least(sf,lf)-greatest(si,li),0) ov,
greatest(lf-greatest(li,sf),0) rest from j),
per as (select coalesce(sum(ov) filter (where not trab),0) caj,
coalesce(sum(ov*cb) filter (where not trab),0) pl,
coalesce(sum(rest) filter (where trab),0) disp from k group by aid,si)
select (select f0 from c0) corte,coalesce(sum(caj),0) cajon,
coalesce(sum(least(caj,disp)),0) mal,
coalesce(sum(caj-least(caj,disp)),0) sin_op,
round(coalesce(sum(pl*least(caj,disp)/nullif(caj,0)),0),2) plata
from per;
