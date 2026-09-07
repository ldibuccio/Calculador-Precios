-- ¿De qué comieron las guías R desde el corte? Dos preguntas en una:
-- de lotes de CAJA ARMADA (otra guía R, que es la mezcla de unidades) y
-- de lotes ANTERIORES al corte (que el corte declaró inexistentes).
--
-- Devuelve CONTEOS y no una lista: con conteos siempre viene una fila y el
-- cero se ve; con una lista, "todo bien" y "no corrió" son la misma
-- pantalla vacía.
with corte as (select fecha from corte_modelo where id = 1),
con as (
    select rp.id as guia,
           c.origen,
           c.bultos,
           c.bultos * c.costo_por_bulto as costo,
           case c.origen
               when 'compra' then (select (co.procesada_el
                        at time zone 'America/Argentina/Buenos_Aires')::date
                    from compras co where co.id = c.compra_id)
               when 'reproceso' then (select r2.fecha_operacion
                    from reprocesos r2 where r2.id = c.origen_id)
               else (select m.fecha_operacion
                    from movimientos_stock m where m.id = c.origen_id)
           end as fecha_lote
    from reprocesos rp
    join reprocesos_consumos c on c.reproceso_id = rp.id
    where rp.anulado_el is null
      and rp.tipo = 'normal'
      and rp.fecha_operacion >= (select fecha from corte)
)
select 'guias R desde el corte (todas)' as concepto,
       count(distinct guia) as guias,
       round(sum(bultos), 2) as bultos,
       round(sum(costo), 2) as costo
from con
union all
select 'comieron de CAJA ARMADA (otra guia R)',
       count(distinct guia) filter (where origen = 'reproceso'),
       round(sum(bultos) filter (where origen = 'reproceso'), 2),
       round(sum(costo) filter (where origen = 'reproceso'), 2)
from con
union all
select 'comieron de lote ANTERIOR al corte',
       count(distinct guia) filter (where fecha_lote < (select fecha from corte)),
       round(sum(bultos) filter (where fecha_lote < (select fecha from corte)), 2),
       round(sum(costo) filter (where fecha_lote < (select fecha from corte)), 2)
from con
union all
select 'consumos sin lote (sin_lote)',
       count(distinct guia) filter (where origen = 'sin_lote'),
       round(sum(bultos) filter (where origen = 'sin_lote'), 2),
       round(sum(costo) filter (where origen = 'sin_lote'), 2)
from con;
