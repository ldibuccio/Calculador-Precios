-- ALCANCE del lado de A, por articulo, desde el corte.
-- OJO CON LOS NOMBRES: aca A y B son LOS ARREGLOS (A = el reproceso no
-- consume lotes trabajados; B = dos pilas separadas). El archivo viejo
-- e5_1_alcance_de_la_mezcla.sql usaba A y B para otras dos cosas; se
-- renombro a remanente_1_tamanos_y_pilas.sql para que no se confundan.
-- Esto es EXACTO, no aproxima: sale de reprocesos_consumos, que esta
-- congelado. El lado de B lo mide e5_2, que tiene que rejugar el FIFO
-- porque la atribucion de un armado no se guarda en ningun lado.
with c0 as (select fecha f0 from corte_modelo where id=1),
cons as (select rp.articulo_id aid,rp.id gid,sum(rc.bultos) b,
sum(rc.bultos*rc.costo_por_bulto) p,
sum(rc.bultos) filter (where rc.costo_por_bulto is null) sc
from reprocesos rp join reprocesos_consumos rc on rc.reproceso_id=rp.id,c0
where rp.anulado_el is null and rp.fecha_operacion>c0.f0
and rc.origen in ('reproceso','reingreso_rechazo')
group by 1,2)
select (select f0 from c0) corte,coalesce(a.nombre,'TOTAL') articulo,
count(distinct c.gid) guias_r,
coalesce(sum(c.b),0) bultos_de_caja,
round(coalesce(sum(c.p),0),2) plata,
coalesce(sum(c.sc),0) sin_costo
from cons c join articulos a on a.id=c.aid
group by grouping sets ((),(a.nombre))
order by grouping(a.nombre) desc,3 desc;
