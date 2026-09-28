with c0 as (select fecha as corte from corte_modelo where id = 1),
x as (
  select c.id, c.articulo_id,
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
),
d as (
  select x.*, m.n,
         abs(ln(x.kg / m.med_kg)) + abs(ln(x.u / m.med_u)) as tal_cual,
         abs(ln(x.u / m.med_kg)) + abs(ln(x.kg / m.med_u)) as dado_vuelta
  from x join m using (articulo_id)
)
select 'cruzadas_1' as QUE_CONSULTA,
       (select corte from c0) as corte,
       count(*) as compras_con_las_dos,
       count(distinct articulo_id) as articulos,
       count(*) filter (where n >= 3) as con_historia,
       count(*) filter (where n >= 3 and dado_vuelta < tal_cual) as CRUZADAS,
       (select max(fecha_operacion) from compras) as ultima_compra
from d;
