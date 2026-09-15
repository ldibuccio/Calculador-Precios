-- ¿EN QUÉ MAGNITUD ESTÁ LA REFERENCIA DE CADA ARTÍCULO, Y CUÁNTOS HAY DE CADA UNA?
--
-- La referencia se precarga en UN campo de la compra (`contenido_por_cajon`),
-- y cuál de las dos magnitudes es ése lo decide `unidad_compra`: kilos en casi
-- todo el catálogo, y el CONTEO en los que ya se compraban contados. O sea que
-- el mismo número significa kilos en unos y unidades en otros.
--
-- Esto decide si la referencia se puede clavar en KILOS. Clavarla re-etiqueta
-- en silencio la de los contados que tengan una cargada — así que lo que hay
-- que mirar es `contados_CON_referencia`: si da 0, no hay nada que re-etiquetar
-- y clavarla sale gratis.
--
-- Va en las DOS bases y se pegan las DOS filas (corolario 17): salen idénticas
-- por diseño salvo el testigo, y eso es lo esperado, no una razón para pegar una.
select
    count(*)                                                            as articulos_activos,
    count(*) filter (where a.unidad_compra is distinct from 'kilo')     as contados,
    count(*) filter (where a.unidad_compra is distinct from 'kilo'
                       and a.contenido_referencia is not null)          as contados_CON_referencia,
    count(*) filter (where a.unidad_compra is distinct from 'kilo'
                       and a.contenido_referencia is null)              as contados_sin_referencia,
    count(*) filter (where coalesce(a.unidad_compra, 'kilo') = 'kilo'
                       and a.unidad_conteo is not null)                 as en_kilos_pero_con_conteo,
    -- El testigo (corolario 24): sin esto, todos los ceros se explican solos.
    (select max(c.cargado_el)::date from compras c)                      as ultima_compra
from articulos a
where a.activo;
