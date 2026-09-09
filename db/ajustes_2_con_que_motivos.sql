-- AJUSTES DE STOCK (2 de 2): la lista completa de motivos, tal como se escribieron.
--
-- A PROPÓSITO NO CLASIFICA. La tentación era una columna `parece_merma` con
-- un `motivo like '%podr%'`, y esa columna sería el número que después se
-- cita. Un derivado de texto libre no falla ruidosamente: acierta en la
-- mayoría y miente en un tercio (corolario 20), y acá fallaría justo en el
-- caso común — "se echó a perder", "no servía", "estaba feo" son la misma
-- merma y ninguna dice podrido.
--
-- Lo que sí sirve: la lista ENTERA, ordenada por frecuencia, para leerla. Son
-- pocos días de ajustes cargados a mano; se lee de una pasada y el que
-- clasifica es el que conoce el galpón. La columna que decide algo sin
-- interpretar nada es el SIGNO, y está en la 1.
--
-- Pliega mayúsculas y espacios: "Podrido" y "podrido " son el mismo motivo y
-- separados inflan la lista y esconden cuál se repite.
--
-- Con renglón TOTAL: agrupada sin él, cero ajustes devuelve CERO FILAS, que
-- en el editor se ve igual que la consulta que no corrió.
with c0 as (select fecha as f0 from corte_modelo where id = 1)
select
    coalesce(lower(regexp_replace(btrim(m.motivo), '\s+', ' ', 'g')),
             'TOTAL')                                            as motivo,
    count(*)                                                     as veces,
    coalesce(-sum(m.cantidad) filter (where m.cantidad < 0), 0)  as bultos_bajados,
    coalesce(sum(m.cantidad) filter (where m.cantidad > 0), 0)   as bultos_subidos,
    count(distinct m.articulo_id)                                as articulos,
    max(m.fecha_operacion)                                       as ultimo
from movimientos_stock m
where m.tipo = 'ajuste'
  and m.anulado_el is null
  and m.fecha_operacion > (select f0 from c0)
group by rollup (lower(regexp_replace(btrim(m.motivo), '\s+', ' ', 'g')))
order by (grouping(lower(regexp_replace(btrim(m.motivo), '\s+', ' ', 'g'))) = 1) desc,
         2 desc, 3 desc;
