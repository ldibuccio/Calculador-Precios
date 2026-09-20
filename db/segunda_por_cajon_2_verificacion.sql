select
    'segunda_por_cajon_2'                                             as QUE_MIGRACION,
    (select count(*) from compras c join articulos a on a.id = c.articulo_id
      where c.segunda_por_cajon_real is null
        and c.cantidad_cajones_real > 0
        and (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
                  then c.cantidad_fraccion_real else c.cantidad_kilos_real end) is not null)
                                                                      as HUECOS_debe_dar_0,
    (select count(*) from compras c join articulos a on a.id = c.articulo_id
      where c.segunda_por_cajon_real is not null
        and c.segunda_por_cajon_real * c.cantidad_cajones_real
            is distinct from (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
                                   then c.cantidad_fraccion_real else c.cantidad_kilos_real end))
                                                                      as NO_VUELVEN_debe_dar_0,
    (select count(*) from compras where segunda_por_cajon_real is not null) as con_segunda_real,
    (select count(*) from compras where estado = 'recepcionado')      as recepcionadas_POBLACION,
    (select max(procesada_el)::date from compras)                     as ultima_recepcion;

-- COMO SE LEE:
--   HUECOS_debe_dar_0      0  <- ninguna compra recepcionada quedo con el
--                                total real cargado y la columna en NULL.
--   NO_VUELVEN_debe_dar_0  0  <- y lo backfilleado multiplica de vuelta exacto.
--   con_segunda_real          las que declararon las dos; las demas quedan en
--                             NULL y eso es correcto, no un hueco.
--
-- `recepcionadas_POBLACION` y `ultima_recepcion` van para poder leer los dos
-- ceros: sobre una base sin recepciones los dos dan 0 y no significan nada.
