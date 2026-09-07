-- Piso con MAS que el sistema: una entrada que falta o una salida cargada
-- de mas. Busca las cuatro causas visibles en los datos. Devuelve CONTEOS.
with c0 as (select fecha f0 from corte_modelo where id = 1),
a0 as (select id, nombre from articulos
       where nombre ilike any (array['%palta%','%zapallito%','%perita%'])),
d(orden, causa, articulo, cantidad, detalle) as (
 -- 1) Llego y NO se recepciono: esta en el piso y el sistema no la tiene.
 select 1, 'compra SIN recepcionar', a.nombre,
   coalesce(c.cantidad_cajones_real, c.cantidad_cajones),
   'compra '||c.id||' estado '||coalesce(c.estado,'(null)')||' del '||c.fecha_operacion
 from compras c join a0 a on a.id = c.articulo_id, c0
 where c.fecha_operacion >= c0.f0 and coalesce(c.estado,'') <> 'recepcionado'
 union all
 -- 2) Rechazos a segunda o reproceso: salen del stock normal, siguen en el
 --    galpon, y la consulta de entradas los excluye.
 select 2, 'rechazo fuera del stock normal', a.nombre, m.cantidad,
   'mov '||m.id||' destino '||m.destino_rechazo||' del '||m.fecha_operacion
 from movimientos_stock m join a0 a on a.id = m.articulo_id, c0
 where m.anulado_el is null and m.fecha_operacion >= c0.f0
   and m.destino_rechazo in ('segunda','reproceso')
 union all
 -- 3) Una merma cargada que no ocurrio deja al sistema debajo del piso.
 select 3, 'merma o ajuste', a.nombre, m.cantidad,
   'mov '||m.id||': '||m.tipo||' — '||m.motivo||' del '||m.fecha_operacion
 from movimientos_stock m join a0 a on a.id = m.articulo_id, c0
 where m.anulado_el is null and m.fecha_operacion >= c0.f0
   and m.tipo in ('merma','ajuste')
 union all
 -- 4) Si el sistema tiene 11,4 y el piso 12, ese 1 es redondeo y no bulto.
 select 4, 'sistema con decimales', a.nombre, cs.stock_sistema,
   'conteo del '||(cs.creado_en at time zone
    'America/Argentina/Buenos_Aires')::date||' — contado '||cs.cantidad
 from conteos_stock cs join a0 a on a.id = cs.articulo_id, c0
 where (cs.creado_en at time zone 'America/Argentina/Buenos_Aires')::date >= c0.f0
   and cs.stock_sistema <> round(cs.stock_sistema)
)
select causa, count(*) as casos, coalesce(sum(cantidad), 0) as bultos,
 string_agg(articulo||': '||detalle, ' | ' order by orden) as detalle
from d group by causa, orden
union all
-- El total NO suma bultos: cada causa esta en su unidad y sumarlas seria el
-- mismo error de unidades que venimos persiguiendo. Cuenta casos.
select 'CAUSAS ENCONTRADAS EN TOTAL', count(*), null, ''
from d order by 1;
