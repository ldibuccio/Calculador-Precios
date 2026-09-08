-- E5 paso 2: docs/el_corte_no_cerraba_el_fifo.md
with c0 as (select fecha f0,'America/Argentina/Buenos_Aires' z
from corte_modelo where id=1),
vig as (select distinct on (cliente_id,fecha_operacion) id from pedidos
where anulado_el is null order by cliente_id,fecha_operacion,creado_en desc),
mv as (
select c.articulo_id aid,(c.procesada_el at time zone c0.z)::date d,
coalesce(c.cantidad_cajones_real,0) q,null::bigint rid,false trab,true lado
from compras c,c0 where c.estado='recepcionado'
and (c.procesada_el at time zone c0.z)::date>c0.f0
union all
select m.articulo_id,m.fecha_operacion,abs(m.cantidad),null,
m.tipo='reingreso_rechazo',m.cantidad>0
from movimientos_stock m,c0 where m.anulado_el is null
and m.tipo<>'cierre_modelo_viejo'
and (m.cantidad<0 or m.destino_rechazo is null or m.destino_rechazo='stock')
and ((m.tipo='stock_inicial' and m.fecha_operacion=c0.f0 and m.cantidad>0)
or m.fecha_operacion>c0.f0)
union all
select rp.articulo_id,rp.fecha_operacion,rp.bultos_primera,rp.id,true,true
from reprocesos rp,c0 where rp.anulado_el is null
and ((rp.tipo='inicial' and rp.fecha_operacion=c0.f0)
or rp.fecha_operacion>c0.f0)
union all
select r.articulo_id,(r.armado_el at time zone c0.z)::date,
coalesce(r.cantidad_armada,r.cantidad),null,false,false
from pedidos_renglones r join vig v on v.id=r.pedido_id,c0
where r.armado_el is not null and r.anulado_el is null
and (r.armado_el at time zone c0.z)::date>c0.f0
union all
select rp.articulo_id,rp.fecha_operacion,rp.bultos_tomados,rp.id,false,false
from reprocesos rp,c0 where rp.anulado_el is null and rp.fecha_operacion>c0.f0),
g as (select s.rid id,s.aid,s.d f,s.q t,coalesce((select sum(x.q) from mv x
where not x.lado and x.aid=s.aid and x.d<s.d and (x.rid is null or x.rid<s.rid)),0) dd
from mv s where not s.lado and s.rid is not null and s.q>0),
lot as (select g.id,g.t,g.dd,coalesce(e.trab,false) trab,
sum(coalesce(e.q,0)) over w-coalesce(e.q,0) ini,sum(coalesce(e.q,0)) over w fin
from g left join mv e on e.lado and e.aid=g.aid and e.d<=g.f
and (e.rid is null or e.rid<g.id)
window w as (partition by g.id order by e.d,e.rid nulls first)),
res as (select id,t,trab,greatest(fin-greatest(ini,dd),0) rest from lot),
r as (select id,t,sum(rest) hoy,
coalesce(sum(rest) filter (where not trab),0) con_a from res group by id,t)
select (select f0 from c0) corte,count(*) guias,
count(*) filter (where t>hoy) frenan_hoy,
count(*) filter (where t>con_a) frenan_con_a,
coalesce(sum(greatest(t-con_a,0)),0) sin_cubrir
from r;
