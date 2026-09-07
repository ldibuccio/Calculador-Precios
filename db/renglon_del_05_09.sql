-- El renglón del 05/09, campo por campo y SIN NINGÚN JOIN que pueda
-- excluirlo: todo lo que cuelga va por LEFT y con subconsulta. Un INNER a
-- fichas_logistica es justo lo que hizo que armado_sin_precio.sql no lo
-- viera. Cambiar la fecha y el cliente si hace falta.
select r.id as renglon, p.fecha_operacion, p.origen, r.sucursal,
       r.articulo_id,
       (select a.nombre from articulos a where a.id = r.articulo_id) as articulo,
       r.texto_codigo, r.texto_descripcion,
       r.ficha_id,
       (select f.nombre_cliente from fichas_logistica f where f.id = r.ficha_id) as ficha_nombre,
       r.cantidad, r.cantidad_armada, r.kilos_enviados,
       (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date as armado_el,
       r.anulado_el,
       (select count(*) from precios_venta_historial pv
         where pv.ficha_id = r.ficha_id) as precios_de_esa_ficha,
       (select pv.precio from precios_venta_historial pv
         where pv.ficha_id = r.ficha_id and pv.vigente_desde <= p.fecha_operacion
         order by pv.vigente_desde desc limit 1) as precio_vigente,
       case
         when r.ficha_id is null and r.articulo_id is null
              then 'SIN IDENTIFICAR: no se sabe ni que articulo es'
         when r.ficha_id is null
              then 'SIN FICHA: se sabe el articulo, no a que producto de venta fue'
         when not exists (select 1 from precios_venta_historial pv
                           where pv.ficha_id = r.ficha_id
                             and pv.vigente_desde <= p.fecha_operacion)
              then 'CON FICHA pero sin precio vigente a esa fecha'
         else 'tiene todo: la plata no deberia dar NULL'
       end as diagnostico
from pedidos_renglones r
join pedidos p on p.id = r.pedido_id
where p.fecha_operacion = date '2026-09-05'
  and p.anulado_el is null
order by r.id;
