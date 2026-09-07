-- APROXIMADA. Que pierde: docs/el_corte_no_cerraba_el_fifo.md
-- Tuvo una columna "solo_cajones" que estaba MAL y se saco: restaba el
-- armado (CAJAS) de un balde de CAJONES, asi que daba cero siempre.
with c0 as (select fecha from corte_modelo where id = 1),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
mov(articulo_id, bultos) as (
 select c.articulo_id, c.cantidad_cajones_real from compras c
 where c.estado = 'recepcionado' and (c.procesada_el at time zone
 'America/Argentina/Buenos_Aires')::date >= (select fecha from c0)
 union all -- el compensatorio sale por TIPO, no por fecha
 select m.articulo_id, m.cantidad from movimientos_stock m
 where m.anulado_el is null and m.tipo <> 'cierre_modelo_viejo'
   and m.fecha_operacion >= (select fecha from c0) and (m.cantidad < 0
   or m.destino_rechazo is null or m.destino_rechazo = 'stock')
 union all
 select rp.articulo_id, rp.bultos_primera from reprocesos rp
 where rp.anulado_el is null and rp.fecha_operacion >= (select fecha from c0)
 union all select rp.articulo_id, -rp.bultos_tomados from reprocesos rp
 where rp.anulado_el is null and rp.fecha_operacion >= (select fecha from c0)
 union all
 select r.articulo_id, -coalesce(r.cantidad_armada, r.cantidad)
 from pedidos_renglones r join vig v on v.id = r.pedido_id
 where r.armado_el is not null and r.anulado_el is null and (r.armado_el
 at time zone 'America/Argentina/Buenos_Aires')::date >= (select fecha from c0)
),
ritmo as (
 select articulo_id, sum(bultos_tomados)
   / greatest(count(distinct fecha_operacion), 1) as por_dia from reprocesos
 where anulado_el is null and tipo = 'normal'
   and fecha_operacion >= (select fecha from c0) group by articulo_id
),
neto as (
 select a.nombre, r.por_dia, greatest(coalesce(sum(m.bultos), 0), 0) as disp
 from ritmo r join articulos a on a.id = r.articulo_id
 left join mov m on m.articulo_id = r.articulo_id
 where r.por_dia > 0 group by a.nombre, r.por_dia
)
select count(*) filter (where disp < por_dia) over () as frenan_con_el_piso,
 count(*) over () as se_reprocesan, nombre as articulo,
 round(por_dia, 2) as toma_x_dia, round(disp, 2) as disp_aprox,
 case when disp < por_dia then 'SI' else '' end as freno
from neto order by (disp < por_dia) desc, por_dia desc;
