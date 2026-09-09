-- MERMAS QUE YA EXISTEN (2 de 3): qué artículos, y cuántos bultos cada uno.
--
-- Acá SÍ es una lista, y por eso lleva un renglón TOTAL al final: es lo que
-- hace que el vacío se distinga de "no corrió" (si no vuelve ni el total, la
-- consulta no corrió). El total tiene que cerrar contra `bultos` de
-- mermas_1: si no cierra, una de las dos está midiendo otra cosa.
--
-- Mismo recorte que mermas_1 (`> corte`, sin las anuladas) escrito acá de
-- nuevo porque el editor no sostiene una vista temporal entre sentencias.
with c0 as (select fecha as f0 from corte_modelo where id = 1),
mermas as (
    select m.articulo_id, m.cantidad, m.fecha_operacion
    from movimientos_stock m
    where m.tipo = 'merma'
      and m.anulado_el is null
      and m.fecha_operacion > (select f0 from c0)
)
select
    coalesce(a.nombre, 'TOTAL')          as articulo,
    count(*)                             as mermas,
    -sum(x.cantidad)                     as bultos,
    min(x.fecha_operacion)               as primera,
    max(x.fecha_operacion)               as ultima
from mermas x
left join articulos a on a.id = x.articulo_id
group by rollup (a.nombre)
order by (a.nombre is null) desc, 3 desc, 1;
