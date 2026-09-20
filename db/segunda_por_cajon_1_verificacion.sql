select
    'segunda_por_cajon_1'                                            as QUE_MIGRACION,
    (select count(*) from information_schema.columns
       where table_schema = 'public' and table_name = 'compras'
         and column_name in ('segunda_por_cajon', 'segunda_por_cajon_real')) as columnas_de_2,
    -- LA EXACTITUD DEL BACKFILL, que es lo unico que este archivo viene a
    -- probar: si multiplicar de vuelta no devuelve el total guardado, el
    -- backfill perdio precision y hay que mirarlo ANTES de cablear nada.
    (select count(*) from compras c join articulos a on a.id = c.articulo_id
      where c.segunda_por_cajon is not null
        and c.segunda_por_cajon * c.cantidad_cajones
            is distinct from (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
                                   then c.cantidad_fraccion else c.cantidad_kilos end))
                                                                     as NO_VUELVEN_debe_dar_0,
    (select count(*) from compras where segunda_por_cajon is not null) as con_segunda,
    (select count(*) from compras)                                   as compras_POBLACION,
    (select max(cargado_el)::date from compras)                      as ultima_compra_cargada;

-- COMO SE LEE, con el esperado al lado:
--   columnas_de_2            2
--   NO_VUELVEN_debe_dar_0    0   <- si da distinto de 0, el backfill perdio
--                                   precision y el numero de esa compra ya no
--                                   es el que se tipeo. NO cablear hasta verlo.
--   con_segunda                  las compras que declararon la segunda; las
--                                anteriores al modelo de dos magnitudes quedan
--                                en NULL y eso es correcto, no un hueco.
--
-- SE CORRE APARTE del bloque `do`.
