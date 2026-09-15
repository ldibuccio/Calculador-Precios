-- Verificación de dos_magnitudes_3. UNA fila siempre. Correr en LAS DOS
-- bases y pegar las dos filas con el nombre de la base adelante.
select
    (select count(*) from information_schema.columns
      where table_name = 'articulos' and column_name = 'unidad_conteo')     as columna,
    (select count(*) from pg_constraint
      where conname = 'articulos_unidad_conteo_check')                      as guarda,
    -- El backfill: cuántos quedaron con conteo, sobre la población.
    (select count(*) from articulos where unidad_conteo is not null)        as con_conteo,
    (select count(*) from articulos where activo)                           as arts_activos,
    -- OFENSOR: el backfill copia unidad_compra, así que los que la tienen en
    -- unidad/cubeta TIENEN que haber quedado con conteo. Distinto de cero
    -- es que el update no corrió o corrió a medias.
    (select count(*) from articulos
      where unidad_compra in ('unidad', 'cubeta') and unidad_conteo is null) as sin_copiar,
    -- Y los que NO se dedujeron, NOMBRADOS en vez de inventados: se compran
    -- por kilo y alguna ficha les pide un conteo. Hay que decidirlos a mano
    -- desde Artículos, uno por uno.
    (select count(*) from articulos a
      where a.unidad_conteo is null
        and exists (select 1 from fichas_logistica f
                     where f.articulo_id = a.id
                       and f.unidad_venta in ('unidad', 'cubeta')))          as a_decidir_a_mano,
    (select string_agg(a.nombre, ', ') from articulos a
      where a.unidad_conteo is null
        and exists (select 1 from fichas_logistica f
                     where f.articulo_id = a.id
                       and f.unidad_venta in ('unidad', 'cubeta')))          as cuales_a_mano,
    -- Testigo: un cero sobre una base parada se lee igual que uno bueno.
    (select max(fecha_operacion) from compras)                              as ultima_compra;
