-- Piso con MAS que el sistema: las cuatro causas visibles en los datos.
with c0 as (select fecha f0 from corte_modelo where id = 1),
a0 as (select id, nombre from articulos
       where nombre ilike any (array['%palta%','%zapallito%','%perita%'])),
d(orden, causa, articulo, cantidad, detalle) as (
 select 1, 'compra SIN recepcionar', a.nombre,
   coalesce(c.cantidad_cajones_real, c.cantidad_cajones),
   'compra '||c.id||' '||coalesce(c.estado,'?')||' del '||c.fecha_operacion
 from compras c join a0 a on a.id = c.articulo_id, c0
 where c.fecha_operacion >= c0.f0 and coalesce(c.estado,'') <> 'recepcionado'
 union all
 -- 2) Rechazos a segunda/reproceso: fuera del stock normal, en el galpon.
 select 2, 'rechazo fuera del stock normal', a.nombre, m.cantidad,
   'mov '||m.id||' a '||m.destino_rechazo||' del '||m.fecha_operacion
 from movimientos_stock m join a0 a on a.id = m.articulo_id, c0
 where m.anulado_el is null and m.fecha_operacion >= c0.f0
   and m.destino_rechazo in ('segunda','reproceso')
 union all
 select 3, 'merma o ajuste', a.nombre, m.cantidad,
   'mov '||m.id||' '||m.tipo||': '||m.motivo
 from movimientos_stock m join a0 a on a.id = m.articulo_id, c0
 where m.anulado_el is null and m.fecha_operacion >= c0.f0
   and m.tipo in ('merma','ajuste')
 union all
 select 4, 'sistema con decimales', a.nombre, cs.stock_sistema,
   'conteo del '||(cs.creado_en at time zone
    'America/Argentina/Buenos_Aires')::date||' — contado '||cs.cantidad
 from conteos_stock cs join a0 a on a.id = cs.articulo_id, c0
 where (cs.creado_en at time zone 'America/Argentina/Buenos_Aires')::date >= c0.f0
   and cs.stock_sistema <> round(cs.stock_sistema)
)
select causa, count(*) as casos, coalesce(sum(cantidad), 0) as bultos,
 case orden
  when 1 then 'RECEPCIONARLA: el desvio se cierra solo'
  when 2 then 'NO ajustar: corregir el CONTEO, que los incluyo'
  when 3 then 'MIRAR el motivo de la merma'
  when 4 then 'NADA: es redondeo, no un bulto'
 end as que_hacer,
 string_agg(articulo||': '||detalle, ' | ' order by orden) as detalle
from d group by causa, orden
union all
-- El total cuenta CASOS: cada causa esta en su unidad y no se suman.
select 'CAUSAS ENCONTRADAS EN TOTAL', count(*), null,
 case when count(*) = 0 then 'SIN CAUSA: ajustar por el Cotejo con el motivo'
 else 'mirar cada causa arriba' end, ''
from d order by 1;
