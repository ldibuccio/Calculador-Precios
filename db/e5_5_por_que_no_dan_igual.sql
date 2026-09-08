-- Por que corte_fifo_1 y e5_1 no dan lo mismo. Descompone la brecha en sus
-- dos causas posibles, cada una en su fila. Conteos, no listas.
-- corte_fifo_1: fecha_operacion >= corte, tipo normal, SOLO origen reproceso.
-- e5_1: fecha_operacion > corte, sin filtro de tipo, reproceso Y reingreso.
with c0 as (select fecha f0 from corte_modelo where id=1),
con as (select rp.id g,rp.fecha_operacion=c0.f0 dia,rp.tipo tp,c.origen o,
c.bultos b,c.bultos*c.costo_por_bulto p
from reprocesos rp join reprocesos_consumos c on c.reproceso_id=rp.id,c0
where rp.anulado_el is null and rp.fecha_operacion>=c0.f0)
select '1 corte_fifo_1 (>=, normal, reproceso)' concepto,
count(distinct g) filter (where o='reproceso' and tp='normal') guias,
round(coalesce(sum(b) filter (where o='reproceso' and tp='normal'),0),2) bultos,
round(coalesce(sum(p) filter (where o='reproceso' and tp='normal'),0),2) plata
from con
union all select '2 e5_1 (>, reproceso+reingreso)',
count(distinct g) filter (where o in ('reproceso','reingreso_rechazo')
and not dia),
round(coalesce(sum(b) filter (where o in ('reproceso','reingreso_rechazo')
and not dia),0),2),
round(coalesce(sum(p) filter (where o in ('reproceso','reingreso_rechazo')
and not dia),0),2)
from con
union all select '3 brecha: guias del DIA DEL CORTE (reproceso)',
count(distinct g) filter (where o='reproceso' and dia),
round(coalesce(sum(b) filter (where o='reproceso' and dia),0),2),
round(coalesce(sum(p) filter (where o='reproceso' and dia),0),2)
from con
union all select '4 brecha: reingreso_rechazo que suma e5_1',
count(distinct g) filter (where o='reingreso_rechazo' and not dia),
round(coalesce(sum(b) filter (where o='reingreso_rechazo' and not dia),0),2),
round(coalesce(sum(p) filter (where o='reingreso_rechazo' and not dia),0),2)
from con
union all select '5 todas las guias con consumos, >= corte',
count(distinct g) filter (where tp='normal'),
round(coalesce(sum(b) filter (where tp='normal'),0),2),
round(coalesce(sum(p) filter (where tp='normal'),0),2)
from con
union all select '6 todas las guias con consumos, > corte',
count(distinct g) filter (where tp='normal' and not dia),
round(coalesce(sum(b) filter (where tp='normal' and not dia),0),2),
round(coalesce(sum(p) filter (where tp='normal' and not dia),0),2)
from con;
