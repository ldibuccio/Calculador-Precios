-- El tamaño de la mezcla, por articulo, desde el corte. Mide DOS cosas
-- distintas que se confunden, y NO son los arreglos A y B de E5 (este
-- archivo se llamaba e5_1_alcance_de_la_mezcla.sql y usaba esas letras
-- para estas dos, que es exactamente la colision que habia que sacar):
--  1) tamaños_de_cajon: cuantos contenidos distintos conviven. Si es >1, el
--     numero de SUELTOS del Remanente suma bultos que no son comparables.
--  2) cajones_y_cajas: si el articulo tiene compras Y guias R, su pila del
--     FIFO tiene materia prima y producto terminado juntos, y un reproceso
--     puede consumir cajas ya armadas.
-- Son independientes: un articulo con un solo tamaño de cajon igual tiene
-- el problema 2 si arma cajas.
-- La fila TOTAL trae CONTEOS de articulos (arts_mezclados, arts_con_cajas):
-- con una lista, "ninguno" y "no corrio" son la misma pantalla. OJO que en
-- la fila TOTAL, tamanos_de_cajon es el MAXIMO que convive en un articulo,
-- no cuantos tamanos hay en total: el numero que decide es arts_mezclados.
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
select (select fecha from corte_modelo where id=1) corte,
coalesce(a.nombre,'TOTAL') articulo,
max(m.contenidos) tamanos_de_cajon,
min(m.menor) menor, max(m.mayor) mayor,
round(coalesce(sum(m.cajones),0),2) cajones,
coalesce(sum(r.guias),0) guias_r,
round(coalesce(sum(r.cajas),0),2) cajas,
count(*) filter (where coalesce(m.contenidos,0)>1) arts_mezclados,
count(*) filter (where coalesce(r.guias,0)>0) arts_con_cajas
from articulos a
left join comp m on m.aid = a.id
left join rep r on r.aid = a.id
where m.aid is not null or r.aid is not null
group by grouping sets ((),(a.nombre))
order by grouping(a.nombre) desc, 3 desc nulls last, 8 desc;
