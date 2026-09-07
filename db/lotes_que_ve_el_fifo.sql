-- LOS LOTES QUE EL FIFO VE de un artículo, y las salidas que los consumen.
-- Copia las tres ramas de _entradas_y_salidas_stock_varios (app/db.py) con
-- los mismos filtros: por eso sirve para saber si un lote ENTRA o no.
--
-- OJO: acá NO va el "restante" de cada lote. El reparto FIFO se calcula en
-- Python (core/stock.py) y escribirlo en SQL sería una segunda versión de la
-- misma regla — que es lo que este proyecto viene evitando. El restante se
-- mira en Stock por Guía, que corre el reparto de verdad.
-- Cambiar el nombre del artículo de abajo.
with art as (select id from articulos where nombre ilike '%Morron Rojo%' limit 1)
select 'ENTRADA' as que, x.tipo_lote, x.origen_id, x.fecha_lote,
       x.cantidad, x.costo_bulto, x.detalle
from (
    select 'guia' as tipo_lote, c.id as origen_id, g.fecha_operacion as fecha_lote,
           c.cantidad_cajones_real as cantidad, c.importe as costo_bulto,
           p.nombre as detalle
    from compras c join art on art.id = c.articulo_id
    join proveedores p on p.id = c.proveedor_id
    left join guias_compra g on g.id = c.guia_id
    where c.estado = 'recepcionado'
    union all
    select m.tipo, m.id, m.fecha_operacion, m.cantidad, m.costo_por_bulto, m.motivo
    from movimientos_stock m join art on art.id = m.articulo_id
    where m.anulado_el is null and m.cantidad > 0
      and (m.destino_rechazo is null or m.destino_rechazo = 'stock')
    union all
    select 'reproceso', rp.id, rp.fecha_operacion, rp.bultos_primera,
           rp.costo_por_bulto_primera, 'primera de la guía R' || rp.id
    from reprocesos rp join art on art.id = rp.articulo_id
    where rp.anulado_el is null and rp.bultos_primera > 0
) x
union all
select 'SALIDA', 'reproceso_toma', rp.id, rp.fecha_operacion,
       rp.bultos_tomados, null, 'la tomó la guía R' || rp.id
from reprocesos rp join art on art.id = rp.articulo_id
where rp.anulado_el is null and rp.bultos_tomados > 0
order by 4, 1, 2;
