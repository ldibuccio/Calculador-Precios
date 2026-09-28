with c0 as (select fecha as corte from corte_modelo where id = 1),
x as (
  select c.id, c.articulo_id, c.fecha_operacion, c.cantidad_cajones as cj,
         c.cantidad_kilos / c.cantidad_cajones as kg,
         c.cantidad_fraccion / c.cantidad_cajones as u
  from compras c join articulos a on a.id = c.articulo_id
  where a.unidad_conteo is not null and c.fecha_operacion > (select corte from c0)
    and c.cantidad_cajones > 0 and c.cantidad_kilos > 0 and c.cantidad_fraccion > 0
),
m as (
  select articulo_id, count(*) as n,
         percentile_cont(0.5) within group (order by kg) as med_kg,
         percentile_cont(0.5) within group (order by u) as med_u
  from x group by articulo_id
)
select x.id as compra, x.fecha_operacion as fecha, a.nombre as articulo, x.cj,
       round(x.u::numeric, 1) as u_por_cj, round(x.kg::numeric, 1) as kg_por_cj,
       round(m.med_u::numeric, 1) as u_habitual, round(m.med_kg::numeric, 1) as kg_habitual,
       m.n as compras_del_articulo
from x join m using (articulo_id) join articulos a on a.id = x.articulo_id
where m.n >= 3
  and abs(ln(x.u / m.med_kg)) + abs(ln(x.kg / m.med_u))
    < abs(ln(x.kg / m.med_kg)) + abs(ln(x.u / m.med_u))
order by x.fecha_operacion, x.id;
