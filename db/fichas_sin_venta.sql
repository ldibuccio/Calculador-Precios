-- Las fichas del cliente que NO facturaron en los últimos 30 días: las que en
-- Márgenes por Artículo muestran "—" en "% de la venta". La columna que
-- decide es ULTIMA_VENTA: NULL = la ficha se cargó y NUNCA se usó (es dato
-- para limpiar); con fecha = se vendía y se dejó de vender (es negocio).
-- Cambiar el nombre del cliente de abajo.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
vigentes as (
    select distinct on (p.fecha_operacion) p.id, p.fecha_operacion
    from pedidos p join cli on cli.id = p.cliente_id
    where p.anulado_el is null
    order by p.fecha_operacion, p.creado_en desc
),
facturado_30 as (
    select r.ficha_id
    from vigentes v join pedidos_renglones r on r.pedido_id = v.id
    where r.ficha_id is not null and r.anulado_el is null
      and r.kilos_enviados is not null
      and v.fecha_operacion > (now() at time zone 'America/Argentina/Buenos_Aires')::date - 30
    group by r.ficha_id
),
ultima_venta as (
    select r.ficha_id, max(v.fecha_operacion) as fecha
    from vigentes v join pedidos_renglones r on r.pedido_id = v.id
    where r.ficha_id is not null and r.anulado_el is null
    group by r.ficha_id
)
select f.id as ficha, a.nombre as articulo, f.nombre_cliente,
       f.creado_en::date as ficha_creada, a.activo as articulo_activo,
       (select count(*) from precios_venta_historial p where p.ficha_id = f.id) as precios_cargados,
       (select max(p.vigente_desde) from precios_venta_historial p where p.ficha_id = f.id) as ultimo_precio,
       uv.fecha as ultima_venta,
       (select max(c.fecha_operacion) from compras c
         where c.articulo_id = f.articulo_id
           and c.estado is distinct from 'rechazado'
           and c.estado is distinct from 'no_ingresado') as ultima_compra
from fichas_logistica f
join cli on cli.id = f.cliente_id
join articulos a on a.id = f.articulo_id
left join ultima_venta uv on uv.ficha_id = f.id
where not exists (select 1 from facturado_30 x where x.ficha_id = f.id)
order by uv.fecha nulls first, a.nombre;
