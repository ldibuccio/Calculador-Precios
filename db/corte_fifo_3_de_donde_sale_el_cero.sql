-- ENTRADAS desde el corte, por articulo. No resta nada: no hay neto acá.
with c0 as (select fecha from corte_modelo where id = 1),
ent(articulo_id, clase, bultos) as (
 select c.articulo_id, 'cajones', coalesce(c.cantidad_cajones_real, 0)
 from compras c where c.estado = 'recepcionado' and (c.procesada_el at time zone
 'America/Argentina/Buenos_Aires')::date >= (select fecha from c0)
 union all -- en la ventana pero SIN cantidad real cargada
 select c.articulo_id, 'sin_cantidad', 1 from compras c
 where c.estado = 'recepcionado' and c.cantidad_cajones_real is null
   and (c.procesada_el at time zone
   'America/Argentina/Buenos_Aires')::date >= (select fecha from c0)
 union all -- fecha del hecho en la ventana, procesada ANTES
 select c.articulo_id, 'fuera_ventana', coalesce(c.cantidad_cajones_real, 0)
 from compras c where c.estado = 'recepcionado'
   and c.fecha_operacion >= (select fecha from c0)
   and (c.procesada_el at time zone
   'America/Argentina/Buenos_Aires')::date < (select fecha from c0)
 union all
 select m.articulo_id, m.tipo, m.cantidad from movimientos_stock m
 where m.anulado_el is null and m.cantidad > 0
   and m.fecha_operacion >= (select fecha from c0)
 union all
 select rp.articulo_id, 'cajas_armadas', rp.bultos_primera from reprocesos rp
 where rp.anulado_el is null and rp.fecha_operacion >= (select fecha from c0)
),
ritmo as (
 select articulo_id, sum(bultos_tomados)
   / greatest(count(distinct fecha_operacion), 1) as por_dia from reprocesos
 where anulado_el is null and tipo = 'normal'
   and fecha_operacion >= (select fecha from c0) group by articulo_id
)
select (select fecha from c0) as corte, a.nombre as articulo,
 round(coalesce(r.por_dia, 0), 2) as toma_x_dia,
 coalesce(sum(e.bultos) filter (where e.clase = 'cajones'), 0) as caj_compra,
 coalesce(sum(e.bultos) filter (where e.clase = 'stock_inicial'), 0) as stk_inicial,
 coalesce(sum(e.bultos) filter (where e.clase = 'reingreso_rechazo'), 0) as reingr,
 coalesce(sum(e.bultos) filter (where e.clase = 'ajuste'), 0) as ajustes,
 coalesce(sum(e.bultos) filter (where e.clase = 'cajas_armadas'), 0) as cajas_arm,
 coalesce(sum(e.bultos) filter (where e.clase = 'sin_cantidad'), 0) as sin_cant,
 coalesce(sum(e.bultos) filter (where e.clase = 'fuera_ventana'), 0) as fuera_vent
from ritmo r join articulos a on a.id = r.articulo_id
left join ent e on e.articulo_id = r.articulo_id
group by a.nombre, r.por_dia order by 4, 2;
