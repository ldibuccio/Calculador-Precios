-- ¿EL ARMADO SE ADELANTA A LA GUIA R? Es la pregunta de procedimiento, y NO
-- se contesta con `mal` de e5_4: ahi la caja tiene que existir POR FECHA
-- (l.d <= s.d), igual que en produccion, donde lote_posterior_a_la_salida
-- compara FECHAS y no relojes — una guia R cargada a la tarde cubre un
-- armado de esa misma mañana. Si la guia R quedo fechada DESPUES, el armado
-- no cae en `mal` sino en `sin_opcion`, y ahi es donde hay que buscar.
-- Parte los bultos de armado en tres:
--  - con_caja_previa: habia guia R fechada ese dia o antes. Territorio de B.
--  - solo_posterior:  no habia, pero SI hay una despues. Firma de guia R
--                     cargada tarde: la caja existia en el piso y el sistema
--                     no la tenia. Eso no lo arregla ninguna regla de FIFO.
--  - nunca:           el articulo no se reprocesa. Cajon legitimo.
with c0 as (select fecha f0,'America/Argentina/Buenos_Aires' z
from corte_modelo where id=1),
vig as (select distinct on (cliente_id,fecha_operacion) id from pedidos
where anulado_el is null order by cliente_id,fecha_operacion,creado_en desc),
gr as (select rp.articulo_id aid,rp.fecha_operacion d
from reprocesos rp,c0 where rp.anulado_el is null and rp.bultos_primera>0
and ((rp.tipo='inicial' and rp.fecha_operacion=c0.f0)
     or rp.fecha_operacion>c0.f0)),
ar as (select r.articulo_id aid,
(r.armado_el at time zone c0.z)::date d,
coalesce(r.cantidad_armada,r.cantidad) q
from pedidos_renglones r join vig v on v.id=r.pedido_id,c0
where r.armado_el is not null and r.anulado_el is null
and (r.armado_el at time zone c0.z)::date>c0.f0)
select (select f0 from c0) corte,coalesce(a.nombre,'TOTAL') articulo,
round(coalesce(sum(ar.q),0),2) armado,
round(coalesce(sum(ar.q) filter (where exists
 (select 1 from gr where gr.aid=ar.aid and gr.d<=ar.d)),0),2) con_caja_previa,
round(coalesce(sum(ar.q) filter (where not exists
 (select 1 from gr where gr.aid=ar.aid and gr.d<=ar.d)
 and exists (select 1 from gr where gr.aid=ar.aid and gr.d>ar.d)),0),2)
 solo_posterior,
round(coalesce(sum(ar.q) filter (where not exists
 (select 1 from gr where gr.aid=ar.aid)),0),2) nunca
from ar join articulos a on a.id=ar.aid
group by grouping sets ((),(a.nombre))
having grouping(a.nombre)=1 or coalesce(sum(ar.q),0)>0
order by grouping(a.nombre) desc,4 desc;
