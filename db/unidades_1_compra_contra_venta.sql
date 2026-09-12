-- ¿Hay algún artículo donde la unidad de COMPRA y la de VENTA no coincidan?
--
-- POR QUE IMPORTA: `_costear_compras` (app/costeo.py) divide
--   SUM(importe x cajones) / SUM(cajones x contenido_por_cajon)
-- y llama al resultado "costo por unidad de VENTA". El numerador es plata y
-- el denominador es contenido de COMPRA, asi que esa igualdad solo vale si
-- las dos unidades son la misma. No hay ninguna conversion en ningun lado:
-- si este conteo da distinto de cero, esos costos estan mal desde siempre.
--
-- La unidad de venta vive en la FICHA (`fichas_logistica.unidad_venta`), no
-- en el articulo: un mismo articulo puede tener varias fichas. Por eso la
-- comparacion es por PAR articulo-ficha, y `arts_con_dos_ventas` cuenta
-- aparte los articulos cuyas fichas no se ponen de acuerdo entre ellas --
-- ese caso rompe el supuesto aunque cada ficha coincida con la compra.
--
-- CONTEOS Y NO UNA LISTA, cada uno con SU POBLACION al lado: "difieren 0"
-- sin el "pares 137" no se puede leer. Y el TESTIGO dice si la base esta
-- viva: sobre una parada todos estos ceros son verdaderos y no dicen nada.
with pares as (
    select a.id                as articulo_id,
           a.unidad_compra,
           f.id                as ficha_id,
           f.unidad_venta
    from articulos a
    join fichas_logistica f on f.articulo_id = a.id
    where a.activo
),
por_articulo as (
    select articulo_id, count(distinct unidad_venta) as ventas_distintas
    from pares
    group by articulo_id
)
select
    (select count(*) from pares)                                    as pares,
    (select count(*) from pares where unidad_compra is null)        as sin_unidad_compra,
    (select count(*) from pares
      where unidad_compra is not null
        and unidad_compra is distinct from unidad_venta)            as difieren,
    (select count(distinct articulo_id) from pares
      where unidad_compra is not null
        and unidad_compra is distinct from unidad_venta)            as arts_que_difieren,
    (select count(*) from articulos where activo)                   as arts_activos,
    (select count(*) from por_articulo where ventas_distintas > 1)  as arts_con_dos_ventas,
    (select max(creado_en)::date from fichas_logistica)             as ultima_ficha,
    (select max(cargado_el)::date from compras)                     as ultima_compra;
