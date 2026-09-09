-- MERMAS QUE YA EXISTEN (3 de 3): con qué motivos se cargaron.
--
-- ES LA QUE DECIDE ALGO. La merma de stock normal tiene motivo de TEXTO
-- LIBRE; la del pool de segunda, de lista corta ('podrido', 'sobremadurado',
-- 'deshidratado', 'golpeado', 'no se llego a remitir'). Si lo que la gente
-- viene escribiendo entra en esas cinco, la lista sirve para las dos y la de
-- stock normal puede pasar a lista también. Si escriben otra cosa, la lista
-- está mal armada y hay que corregirla ANTES de que la copien.
--
-- El motivo se pliega —minúsculas y espacios colapsados— o "Podrido" y
-- "podrido " salen como dos y el conteo miente por presentación.
--
-- `en_la_lista` no deduce nada del texto: compara contra las cinco palabras
-- exactas del CHECK. Un motivo que diga lo mismo de otra forma ("se pudrió")
-- cae afuera, y está bien: la pregunta es si la lista alcanza tal como está.
-- Y lleva renglón TOTAL: agrupada sin él, una base sin mermas devuelve CERO
-- FILAS, que en el editor se ve idéntico a la consulta que no corrió. Con el
-- total siempre vuelve una fila y el cero se ve.
with c0 as (select fecha as f0 from corte_modelo where id = 1)
select
    coalesce(lower(regexp_replace(btrim(m.motivo), '\s+', ' ', 'g')),
             'TOTAL')                                            as motivo,
    count(*)                                                    as veces,
    -sum(m.cantidad)                                            as bultos,
    -- En el renglón TOTAL va NULL y no el bool_or: "el total está en la
    -- lista" es una afirmación que no significa nada, y una rama por defecto
    -- que afirma algo es una aserción sin verificar.
    case when grouping(lower(regexp_replace(btrim(m.motivo), '\s+', ' ', 'g'))) = 1
         then null
         else bool_or(lower(regexp_replace(btrim(m.motivo), '\s+', ' ', 'g'))
              in ('podrido', 'sobremadurado', 'deshidratado', 'golpeado',
                  'no se llego a remitir'))
    end                                                          as en_la_lista,
    max(m.fecha_operacion)                                       as ultima
from movimientos_stock m
where m.tipo = 'merma'
  and m.anulado_el is null
  and m.fecha_operacion > (select f0 from c0)
group by rollup (lower(regexp_replace(btrim(m.motivo), '\s+', ' ', 'g')))
order by (grouping(lower(regexp_replace(btrim(m.motivo), '\s+', ' ', 'g'))) = 1) desc,
         2 desc, 3 desc;
