-- MERMAS QUE YA EXISTEN (1 de 3): cuántas, cuántos bultos, y dónde cae el corte.
--
-- CONTEOS, no una lista: con una lista, "no hay ninguna" y "no corrió" son la
-- misma pantalla vacía. Con conteos siempre vuelve una fila y el cero se ve.
--
-- Trae `corte` porque la consulta está parametrizada por un dato de la base
-- (corolario 17), y `ultima_merma` como TESTIGO DE ACTIVIDAD: un cero con
-- "última merma hace tres semanas" es un cero que se entiende; un cero solo
-- tranquiliza sin decir nada (corolario 24 — Palmala está parada).
--
-- Y el día del corte va en su PROPIA columna en vez de esconderse adentro
-- del recorte. No puedo correr el canario del corolario 12 desde acá, así
-- que la asimetría se ve en el resultado: si `en_el_dia_del_corte` no es 0,
-- el criterio de recorte cambia el número y hay que decidirlo a mano.
with c0 as (select fecha as f0 from corte_modelo where id = 1)
select
    (select f0 from c0)                                            as corte,
    count(*) filter (where m.fecha_operacion > (select f0 from c0)
                       and m.anulado_el is null)                   as mermas,
    count(*) filter (where m.fecha_operacion > (select f0 from c0)
                       and m.anulado_el is not null)               as mermas_anuladas,
    count(distinct m.articulo_id) filter (
        where m.fecha_operacion > (select f0 from c0)
          and m.anulado_el is null)                                as articulos_distintos,
    coalesce(-sum(m.cantidad) filter (
        where m.fecha_operacion > (select f0 from c0)
          and m.anulado_el is null), 0)                            as bultos,
    count(*) filter (where m.fecha_operacion = (select f0 from c0)
                       and m.anulado_el is null)                   as en_el_dia_del_corte,
    count(*) filter (where m.lote_tipo is not null
                       and m.anulado_el is null)                   as dirigidas_a_un_lote,
    max(m.fecha_operacion)                                         as ultima_merma
from movimientos_stock m
where m.tipo = 'merma';
