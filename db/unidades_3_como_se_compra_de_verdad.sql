-- ¿Como se compro DE VERDAD cada uno de estos articulos, y de donde sale el
-- nombre del cliente de su ficha?
--
-- Contesta las dos preguntas del caso de Kiwi sin que nadie tenga que
-- acordarse:
--
-- 1. `unidad_compra` es una sola marca en `articulos` y dice como se compra
--    HOY. Lo que se compro de verdad esta en las compras: la ruta escribe
--    `cantidad_kilos` cuando la unidad es kilo y `cantidad_fraccion` cuando
--    es unidad o cubeta. Asi que `compras_en_kilos` contra
--    `compras_en_fraccion` muestra con que unidad se cargaron, incluso si
--    la marca del articulo cambio despues.
--
-- 2. El nombre que muestra `unidades_2` sale de
--    `coalesce(f.nombre_cliente, cl.nombre)`, asi que un cliente que se
--    llama igual que el articulo puede ser CUALQUIERA de los dos. Aca van
--    SEPARADOS para poder distinguirlos.
--
-- Los contenidos distintos (`contenidos`) dicen si el articulo entra en un
-- formato o en varios: 12 y 12 y 12 es una cubeta fija; 5, 9 y 15 no.
select a.id, a.nombre as articulo, a.unidad_compra, a.contenido_referencia,
       f.id as ficha_id, f.unidad_venta, f.contenido_caja,
       cl.nombre        as cliente_de_la_tabla,
       f.nombre_cliente as nombre_puesto_en_la_ficha,
       f.codigo_cliente,
       (select count(*) from compras c where c.articulo_id = a.id)      as compras_totales,
       (select count(*) from compras c where c.articulo_id = a.id
         and c.cantidad_kilos is not null)                              as compras_en_kilos,
       (select count(*) from compras c where c.articulo_id = a.id
         and c.cantidad_fraccion is not null)                           as compras_en_fraccion,
       (select count(distinct c.contenido_por_cajon) from compras c
         where c.articulo_id = a.id)                                    as contenidos,
       (select max(c.fecha_operacion) from compras c
         where c.articulo_id = a.id)                                    as ultima_compra
from articulos a
join fichas_logistica f on f.articulo_id = a.id
join clientes cl on cl.id = f.cliente_id
where a.nombre ilike any (array['%kiwi%', '%frutilla%', '%arandano%', '%arándano%'])
   or f.unidad_venta = 'cubeta'
   or a.unidad_compra = 'cubeta'
order by a.nombre, f.id;
