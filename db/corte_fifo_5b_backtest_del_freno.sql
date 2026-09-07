-- BLOQUE B de 2. Corre DESPUES del bloque A. Ventana exacta del freno:
-- entradas HASTA la fecha de la guia, salidas HASTA EL DIA ANTERIOR, y sin
-- las guias posteriores (cuando esa se cargo, no existian).
-- Las guias del DIA DEL CORTE quedan afuera: son anteriores a la foto y
-- ninguna foto de la tarde puede cubrirlas.
with c0 as (select fecha f0 from corte_modelo where id = 1),
g as (select rp.id, rp.articulo_id aid, rp.fecha_operacion f, rp.bultos_tomados t
 from reprocesos rp, c0 where rp.anulado_el is null and rp.tipo = 'normal'
 and rp.fecha_operacion > c0.f0),
r as (select g.id, g.f, g.t, a.nombre, greatest(
 (select coalesce(sum(bultos),0) from corte_mov m where m.entrada
  and m.aid = g.aid and m.d <= g.f and (m.rid is null or m.rid < g.id))
 - (select coalesce(sum(bultos),0) from corte_mov m where not m.entrada
  and m.aid = g.aid and m.d < g.f and (m.rid is null or m.rid < g.id)), 0) disp
 from g join articulos a on a.id = g.aid)
select count(*) filter (where t > disp) over () as frenarian,
 count(*) over () as guias_posteriores_al_corte,
 id as guia, f as fecha, nombre as articulo, t as tomo, disp as disponible,
 case when t > disp then 'FRENA' else '' end as res
from r order by (t > disp) desc, f, id;
