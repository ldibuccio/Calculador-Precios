do $$
begin
    if not exists (select 1 from information_schema.columns
                   where table_schema = 'public' and table_name = 'compras'
                     and column_name = 'segunda_por_cajon') then

        alter table compras add column segunda_por_cajon      numeric;
        alter table compras add column segunda_por_cajon_real numeric;

        -- EL BACKFILL ES EXACTO, no una deduccion: el total se guardo como
        -- cajones * lo-que-se-tipeo, asi que dividirlo por cajones devuelve
        -- el numero tipeado. En NUMERIC, que es decimal: 42.9/3 da 14.3
        -- clavado. (En float da 14.300000000000002, y por eso la division
        -- va en SQL y no en Python.)
        update compras c
           set segunda_por_cajon = (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
                                         then c.cantidad_fraccion else c.cantidad_kilos end)
                                   / c.cantidad_cajones
          from articulos a
         where a.id = c.articulo_id
           and c.cantidad_cajones > 0
           and (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
                     then c.cantidad_fraccion else c.cantidad_kilos end) is not null;

        update compras c
           set segunda_por_cajon_real = (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
                                              then c.cantidad_fraccion_real else c.cantidad_kilos_real end)
                                        / c.cantidad_cajones_real
          from articulos a
         where a.id = c.articulo_id
           and c.cantidad_cajones_real > 0
           and (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
                     then c.cantidad_fraccion_real else c.cantidad_kilos_real end) is not null;

        comment on column compras.segunda_por_cajon is
            'La SEGUNDA magnitud POR CAJON, como la declaro el comprador. Hasta el 20/09 no tenia columna: se guardaba solo el total y la pantalla la dividia de vuelta. Cual magnitud es la dice articulos.unidad_conteo. NULL = esta compra no declaro la segunda.';

        comment on column compras.segunda_por_cajon_real is
            'Lo mismo, de lo que Deposito conto al recepcionar. NULL = no se declaro o no se recepciono.';
    end if;
end $$;
