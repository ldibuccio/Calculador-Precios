-- Limón del 08/09 en Frutamax: a qué porción fue cada movimiento del día.
-- Solo lectura. Reemplazar el nombre del artículo si hace falta.
--
-- Contesta las tres preguntas de una: a qué ficha se le imputó el armado,
-- si el reingreso tiene ficha alcanzable, y de dónde sale el residuo del
-- extracto de sueltos. Devuelve CONTEOS y una sola fila por concepto, así
-- un cero se ve.
with art as (
  select id, nombre from articulos where nombre ilike '%limon%' or nombre ilike '%limón%'
), vigentes as (
  select distinct on (cliente_id, fecha_operacion) id
  from pedidos where anulado_el is null
  order by cliente_id, fecha_operacion, creado_en desc
)
-- 1) EL ARMADO: cuánto salió CON ficha y cuánto SIN ficha. Lo que sale sin
--    ficha no lo ve la cuenta por ficha y cae entero en sueltos.
select 'armado' as concepto, a.nombre as articulo,
       f.nombre_cliente as ficha,
       sum(coalesce(r.cantidad_armada, r.cantidad)) as bultos,
       count(*) as renglones, null::numeric as extra
from pedidos_renglones r
join vigentes v on v.id = r.pedido_id
join art a on a.id = r.articulo_id
left join fichas_logistica f on f.id = r.ficha_id
where r.armado_el is not null and r.anulado_el is null
  and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date = date '2026-09-08'
group by a.nombre, f.nombre_cliente
union all
-- 2) LAS GUIAS R: lo que produjeron para la ficha (primera) contra lo que
--    tomaron de los sueltos (tomados).
select 'guia R', a.nombre, coalesce(f.nombre_cliente, '(sin ficha)'),
       sum(rp.bultos_primera), count(*), sum(rp.bultos_tomados)
from reprocesos rp
join art a on a.id = rp.articulo_id
left join fichas_logistica f on f.id = rp.ficha_id
where rp.anulado_el is null and rp.fecha_operacion = date '2026-09-08'
group by a.nombre, f.nombre_cliente
union all
-- 3) EL REINGRESO: la ficha NO es una columna suya; se alcanza por el
--    renglón del que volvió. Si "ficha" viene con nombre, el dato existe.
select 'reingreso', a.nombre, coalesce(f.nombre_cliente, '(no llega a ninguna ficha)'),
       sum(m.cantidad), count(*), null
from movimientos_stock m
join art a on a.id = m.articulo_id
left join pedidos_renglones pr on pr.id = m.pedido_renglon_id
left join fichas_logistica f on f.id = pr.ficha_id
where m.anulado_el is null and m.tipo = 'reingreso_rechazo'
  and m.fecha_operacion = date '2026-09-08'
group by a.nombre, f.nombre_cliente
order by 1, 3;
