-- El tamaño de la mezcla, por articulo, desde el corte. Mide DOS cosas
-- distintas que se confunden:
--  A) contenidos: cuantos tamaños de cajon distintos conviven. Si es >1, el
--     numero de SUELTOS del Remanente suma bultos que no son comparables.
--  B) cajones_y_cajas: si el articulo tiene compras Y guias R, su pila del
--     FIFO tiene materia prima y producto terminado juntos, y un reproceso
--     puede consumir cajas ya armadas.
-- Son independientes: un articulo con un solo tamaño de cajon igual tiene
-- el problema B si arma cajas.
with c0 as (select fecha f0 from corte_modelo where id = 1),
comp as (
 select c.articulo_id aid, count(*) compras,
  count(distinct coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon)) contenidos,
  min(coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon)) menor,
  max(coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon)) mayor,
  sum(coalesce(c.cantidad_cajones_real, 0)) cajones
 from compras c, c0 where c.estado = 'recepcionado'
  and (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date > c0.f0
 group by 1
),
rep as (
 select articulo_id aid, count(*) guias, sum(bultos_primera) cajas
 from reprocesos, c0 where anulado_el is null and tipo = 'normal'
  and fecha_operacion > c0.f0
 group by 1
)
select a.nombre as articulo,
 coalesce(m.contenidos, 0) as tamanos_de_cajon,
 m.menor, m.mayor, coalesce(m.cajones, 0) as cajones,
 coalesce(r.guias, 0) as guias_r, coalesce(r.cajas, 0) as cajas,
 case when coalesce(m.contenidos,0) > 1 and coalesce(r.guias,0) > 0 then 'A y B'
      when coalesce(m.contenidos,0) > 1 then 'A: tamaños mezclados'
      when coalesce(r.guias,0) > 0 then 'B: cajones y cajas'
      else '' end as problema,
 count(*) filter (where coalesce(m.contenidos,0) > 1) over () as con_tamanos_mezclados,
 count(*) filter (where coalesce(r.guias,0) > 0) over () as con_cajones_y_cajas
from articulos a
left join comp m on m.aid = a.id
left join rep r on r.aid = a.id
where m.aid is not null or r.aid is not null
order by (coalesce(m.contenidos,0) > 1) desc, coalesce(r.cajas,0) desc, a.nombre;
