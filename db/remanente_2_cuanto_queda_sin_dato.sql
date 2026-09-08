-- ¿ALCANZA el dato para desglosar el Remanente por contenido, y cuanto cae
-- en "sin dato"? Cada bulto que entra al stock tiene una fuente distinta y
-- solo DOS de las tres saben cuanto trae:
--  - compra:    coalesce(contenido_por_cajon_real, contenido_por_cajon).
--               contenido_por_cajon es NOT NULL: la compra SIEMPRE sabe.
--  - guia R:    el contenido de la caja sale de la FICHA
--               (fichas_logistica.contenido_caja). Es nullable, y ficha_id
--               tambien: por eso hay cajas con dato y cajas sin dato.
--  - movimiento (stock_inicial del corte, ajuste, reingreso): NO TIENE
--               columna de contenido. Nunca sabe. Todo esto es "sin dato".
-- Mide ENTRADAS y no restantes: para dimensionar la mezcla alcanza y no
-- necesita rejugar el FIFO. El desglose real va a mostrar restantes, asi
-- que estos numeros son la proporcion esperada, no la de la pantalla.
with c0 as (select fecha f0,'America/Argentina/Buenos_Aires' z
from corte_modelo where id=1),
b(aid,fuente,dato,q) as (
 select c.articulo_id,'compra',true,coalesce(c.cantidad_cajones_real,0)
 from compras c,c0 where c.estado='recepcionado'
  and (c.procesada_el at time zone c0.z)::date>c0.f0
 union all
 select rp.articulo_id,'caja',f.contenido_caja is not null,rp.bultos_primera
 from reprocesos rp left join fichas_logistica f on f.id=rp.ficha_id,c0
 where rp.anulado_el is null and rp.bultos_primera>0
  and ((rp.tipo='inicial' and rp.fecha_operacion=c0.f0)
       or rp.fecha_operacion>c0.f0)
 union all
 select m.articulo_id,'movimiento',false,m.cantidad
 from movimientos_stock m,c0 where m.anulado_el is null and m.cantidad>0
  and m.tipo<>'cierre_modelo_viejo'
  and (m.destino_rechazo is null or m.destino_rechazo='stock')
  and ((m.tipo='stock_inicial' and m.fecha_operacion=c0.f0)
       or m.fecha_operacion>c0.f0))
select (select f0 from c0) corte,coalesce(a.nombre,'TOTAL') articulo,
round(coalesce(sum(q) filter (where fuente='compra'),0),2) cajones,
round(coalesce(sum(q) filter (where fuente='caja' and dato),0),2) cajas_con_dato,
round(coalesce(sum(q) filter (where fuente='caja' and not dato),0),2) cajas_sin_ficha,
round(coalesce(sum(q) filter (where fuente='movimiento'),0),2) movimientos,
round(100*coalesce(sum(q) filter (where not dato),0)
 /nullif(sum(q),0),1) pct_sin_dato
from b join articulos a on a.id=b.aid
group by grouping sets ((),(a.nombre))
order by grouping(a.nombre) desc,7 desc nulls last;
