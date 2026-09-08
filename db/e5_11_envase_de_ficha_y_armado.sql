-- ¿Cuantos de los 630 son de renglones con ENVASE FIJO en la ficha?
-- La pregunta es si la preferencia de B deberia ser pared para esos.
-- Ojo con el matiz que trae el esquema: fichas_logistica.envase_variable
-- dice "si es true, el envase de la ficha es solo referencia/default: se
-- decide por compra". Asi que ficha con envase NO es lo mismo que envase
-- obligatorio; la unica lectura dura es envase_id no nulo Y variable=false.
-- Las columnas cruzan eso contra la particion de e5_10.
with c0 as (select fecha f0,'America/Argentina/Buenos_Aires' z
from corte_modelo where id=1),
vig as (select distinct on (cliente_id,fecha_operacion) id from pedidos
where anulado_el is null order by cliente_id,fecha_operacion,creado_en desc),
gr as (select rp.articulo_id aid,rp.fecha_operacion d
from reprocesos rp,c0 where rp.anulado_el is null and rp.bultos_primera>0
and ((rp.tipo='inicial' and rp.fecha_operacion=c0.f0)
     or rp.fecha_operacion>c0.f0)),
ar as (select r.articulo_id aid,(r.armado_el at time zone c0.z)::date d,
coalesce(r.cantidad_armada,r.cantidad) q,
case when r.ficha_id is null then 'sin ficha'
     when f.envase_id is null then 'ficha sin envase'
     when f.envase_variable then 'envase variable'
     else 'envase fijo' end env
from pedidos_renglones r join vig v on v.id=r.pedido_id
left join fichas_logistica f on f.id=r.ficha_id,c0
where r.armado_el is not null and r.anulado_el is null
and (r.armado_el at time zone c0.z)::date>c0.f0)
select (select f0 from c0) corte,coalesce(a.nombre,'TOTAL') articulo,
round(coalesce(sum(q),0),2) armado,
round(coalesce(sum(q) filter (where exists
 (select 1 from gr where gr.aid=ar.aid and gr.d<=ar.d)),0),2) con_caja_previa,
round(coalesce(sum(q) filter (where env='envase fijo'),0),2) envase_fijo,
round(coalesce(sum(q) filter (where env='envase variable'),0),2) env_variable,
round(coalesce(sum(q) filter (where env='ficha sin envase'),0),2) sin_envase,
round(coalesce(sum(q) filter (where env='sin ficha'),0),2) sin_ficha
from ar join articulos a on a.id=ar.aid
group by grouping sets ((),(a.nombre))
having grouping(a.nombre)=1 or coalesce(sum(q),0)>0
order by grouping(a.nombre) desc,5 desc;
