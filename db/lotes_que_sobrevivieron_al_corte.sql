-- LOTES QUE SOBREVIVIERON AL CORTE: los que tienen restante y son ANTERIORES
-- a la fecha de corte. El compensatorio lleva el NETO a cero, pero la suma de
-- los restantes puede ser mayor que el neto —por cada salida vieja que nunca
-- encontró lote— y esa diferencia queda viva como lote disponible.
-- ACÁ NO SE CALCULA EL RESTANTE: el reparto FIFO vive en core/stock.py y
-- escribirlo en SQL sería una segunda versión. Esto lista los CANDIDATOS
-- (lotes anteriores al corte que todavía no están anulados) y lo que el corte
-- les descontó, para mirarlos en Stock por Guía, que corre el reparto real.
with corte as (select fecha from corte_modelo where id = 1)
select a.nombre as articulo, x.tipo_lote, x.origen_id, x.fecha_lote, x.cantidad,
       x.costo_bulto, x.detalle,
       (select coalesce(sum(-m.cantidad), 0) from movimientos_stock m
         where m.articulo_id = a.id and m.anulado_el is null
           and m.tipo = 'cierre_modelo_viejo' and m.cantidad < 0) as bajo_el_compensatorio
from (
    select c.articulo_id, 'guia' as tipo_lote, c.id as origen_id,
           coalesce((c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date,
                    c.fecha_operacion) as fecha_lote,
           c.cantidad_cajones_real as cantidad, c.importe as costo_bulto,
           p.nombre as detalle
    from compras c join proveedores p on p.id = c.proveedor_id
    where c.estado = 'recepcionado'
    union all
    select m.articulo_id, m.tipo, m.id, m.fecha_operacion, m.cantidad,
           m.costo_por_bulto, m.motivo
    from movimientos_stock m
    where m.anulado_el is null and m.cantidad > 0
      and (m.destino_rechazo is null or m.destino_rechazo = 'stock')
    union all
    select rp.articulo_id, 'reproceso', rp.id, rp.fecha_operacion, rp.bultos_primera,
           rp.costo_por_bulto_primera, 'primera de la guía R' || rp.id
    from reprocesos rp
    where rp.anulado_el is null and rp.bultos_primera > 0
) x
join articulos a on a.id = x.articulo_id, corte
where x.fecha_lote < corte.fecha
order by a.nombre, x.fecha_lote;
