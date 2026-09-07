-- Los renglones que SE ARMARON Y SALIERON pero no se pueden facturar: hay
-- kilos grabados y no hay precio vigente para esa ficha a la fecha del
-- pedido. Es el agujero del 05/09. Cambiar el cliente y el rango de abajo.
with cli as (select id from clientes where nombre ilike '%Día%' limit 1),
vigentes as (
    select distinct on (p.fecha_operacion) p.id, p.fecha_operacion
    from pedidos p join cli on cli.id = p.cliente_id
    where p.anulado_el is null
      and p.fecha_operacion > (now() at time zone 'America/Argentina/Buenos_Aires')::date - 30
    order by p.fecha_operacion, p.creado_en desc
)
select v.fecha_operacion, r.sucursal,
       f.id as ficha, a.nombre as articulo, f.nombre_cliente,
       f.creado_en::date as ficha_creada,
       r.kilos_enviados as unidades,
       (select count(*) from precios_venta_historial pv
         where pv.ficha_id = f.id) as precios_cargados_alguna_vez,
       (select min(pv.vigente_desde) from precios_venta_historial pv
         where pv.ficha_id = f.id) as primer_precio,
       case
         when not exists (select 1 from precios_venta_historial pv where pv.ficha_id = f.id)
              then 'NUNCA tuvo precio'
         else 'tiene precio, pero POSTERIOR a esta fecha'
       end as motivo
from vigentes v
join pedidos_renglones r on r.pedido_id = v.id
join fichas_logistica f on f.id = r.ficha_id
join articulos a on a.id = f.articulo_id
where r.anulado_el is null
  and r.kilos_enviados is not null
  and not exists (
      select 1 from precios_venta_historial pv
      where pv.ficha_id = r.ficha_id and pv.vigente_desde <= v.fecha_operacion
  )
order by v.fecha_operacion desc, a.nombre;
