-- ¿La diferencia del Cotejo es el trabajo del dia todavia sin cargar?
-- El conteo se toma antes de cargar las guias R, asi que el stock_sistema
-- que se congela NO incluye el trabajo de esa jornada. Esta consulta
-- acredita lo que se cargo DESPUES del conteo y muestra las dos diferencias.
-- Se compara por ARTICULO y no por porcion: una guia R se parte entre las
-- dos —su primera va a las cajas y su tomado a los sueltos— asi que por
-- separado no cierra.
with ult as (
 select distinct on (cs.articulo_id, cs.ficha_id,
   (cs.creado_en at time zone 'America/Argentina/Buenos_Aires')::date)
  cs.articulo_id aid, cs.ficha_id, cs.cantidad, cs.stock_sistema, cs.creado_en,
  (cs.creado_en at time zone 'America/Argentina/Buenos_Aires')::date d
 from conteos_stock cs
 order by cs.articulo_id, cs.ficha_id,
  (cs.creado_en at time zone 'America/Argentina/Buenos_Aires')::date, cs.creado_en desc
),
ses as (
 select aid, d, max(creado_en) hasta, count(*) porciones,
  sum(cantidad) contado, sum(stock_sistema) sistema
 from ult group by aid, d
),
pend as (
 select s.aid, s.d,
  coalesce((select sum(rp.bultos_primera - rp.bultos_tomados) from reprocesos rp
    where rp.anulado_el is null and rp.articulo_id = s.aid
      and rp.fecha_operacion = s.d and rp.creado_en > s.hasta), 0)
  + coalesce((select sum(coalesce(c.cantidad_cajones_real,0)) from compras c
    where c.estado = 'recepcionado' and c.articulo_id = s.aid
      and (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date = s.d
      and c.procesada_el > s.hasta), 0)
  - coalesce((select sum(coalesce(r.cantidad_armada, r.cantidad))
    from pedidos_renglones r join pedidos p on p.id = r.pedido_id
    where p.anulado_el is null and r.anulado_el is null and r.articulo_id = s.aid
      and r.armado_el > s.hasta
      and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date = s.d), 0)
  as sin_cargar
 from ses s
)
select s.d as dia, a.nombre as articulo, s.porciones, s.contado, s.sistema,
 s.contado - s.sistema as dif_cruda,
 p.sin_cargar as trabajo_sin_cargar,
 s.contado - (s.sistema + p.sin_cargar) as dif_real
from ses s join pend p on p.aid = s.aid and p.d = s.d
join articulos a on a.id = s.aid
order by s.d desc, abs(s.contado - s.sistema) desc;
