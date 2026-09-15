-- Verificación de dos_magnitudes_1 y el tamaño de lo que falta para el
-- modelo nuevo. UNA fila siempre. Correr en LAS DOS bases y pegar las dos
-- filas con el nombre de la base adelante.
--
-- LO QUE NO HACE, y es la respuesta a "acomodá lo ya cargado": NO deduce la
-- magnitud que falta, porque NO SE PUEDE. Hoy cada compra tiene una sola
-- —kilos o conteo— y la otra no está en ningún lado. Inventarla sería el
-- factor otra vez. Por eso esto CUENTA y NOMBRA, no escribe.
select
    -- El factor, ido.
    (select count(*) from information_schema.columns
      where table_name = 'articulos' and column_name = 'kilos_por_unidad')  as factor_que_quedo,
    -- Con UNA sola magnitud: el estado normal de todo lo viejo, no un defecto.
    (select count(*) from compras
      where cantidad_kilos is null or cantidad_fraccion is null)            as compras_con_una,
    (select count(*) from compras)                                          as compras_totales,
    -- De esas, las que HOY le faltan a alguien: el artículo tiene una ficha
    -- que vende en la unidad que la compra no declaró. No hay con qué
    -- arreglarlas.
    (select count(*) from compras c
      where (c.cantidad_kilos is null or c.cantidad_fraccion is null)
        and exists (select 1 from fichas_logistica f
                     where f.articulo_id = c.articulo_id
                       and f.unidad_venta is distinct from
                           (select a.unidad_compra from articulos a where a.id = c.articulo_id))
    )                                                                       as compras_que_hoy_faltan,
    -- EL LÍMITE DE cantidad_fraccion: un artículo con fichas en unidad Y en
    -- cubeta no entra en dos columnas. > 0 = hace falta una tercera.
    (select count(*) from (
        select f.articulo_id from fichas_logistica f
         where f.unidad_venta in ('unidad', 'cubeta')
         group by f.articulo_id
        having count(distinct f.unidad_venta) > 1) x)                       as arts_unidad_y_cubeta,
    (select string_agg(nombre, ', ') from articulos a
      where a.activo and exists (
            select 1 from fichas_logistica f
             where f.articulo_id = a.id
               and f.unidad_venta is distinct from a.unidad_compra))        as cuales_piden_la_otra,
    (select max(fecha_operacion) from compras)                              as ultima_compra;
