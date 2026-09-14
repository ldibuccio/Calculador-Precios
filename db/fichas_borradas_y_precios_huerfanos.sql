-- ¿Cuánto historial de precios quedó desconectado de su ficha, y por qué puerta?
--
-- POR QUÉ EXISTE (14/09). Los precios cuelgan de la FICHA, y esa FK es
-- `on delete set null`: borrar una ficha NO borra sus precios, les pone
-- `ficha_id` en NULL. Y todas las lecturas filtran `ficha_id IS NOT NULL`,
-- así que esos precios dejan de existir para el sistema — incluida cualquier
-- consulta retroactiva de "¿a qué precio se le facturó esto en julio?".
--
-- EL DATO NO SE PIERDE, SE DESCONECTA: la fila conserva `cliente_id`,
-- `articulo_id`, `precio` y `vigente_desde`. Lo único que se va es de QUÉ
-- ficha era. Por eso esto se puede contar, y por eso un rescate es posible.
--
-- SON DOS PUERTAS Y LA SEGUNDA NO PARECE UNA PUERTA:
--   1. Eliminar la ficha (Fichas > Eliminar).
--   2. CAMBIARLE EL ARTÍCULO, que por dentro es un DELETE + INSERT con id
--      nuevo — desde la pantalla se ve como editar. Su propio docstring lo
--      dice: "Cambiar el artículo DESCONECTA el historial de precios".
-- Las dos dejan un evento 'borrado' en fichas_logistica_historial, así que
-- las dos se cuentan acá.
--
-- Devuelve UNA fila con conteos y su población al lado. Se corre en las DOS
-- bases y se pega con el nombre de la base adelante.
select (select count(*) from precios_venta_historial)                     as precios_total,
       (select count(*) from precios_venta_historial
         where ficha_id is null)                                          as precios_huerfanos,
       (select count(distinct articulo_id) from precios_venta_historial
         where ficha_id is null)                                          as articulos_afectados,
       (select max(vigente_desde) from precios_venta_historial
         where ficha_id is null)                                          as ultimo_huerfano,
       (select count(*) from fichas_logistica)                            as fichas_vivas,
       (select count(distinct ficha_id) from fichas_logistica_historial
         where evento = 'borrado')                                        as fichas_borradas,
       (select max(registrado_en at time zone 'America/Argentina/Buenos_Aires')::date
          from fichas_logistica_historial where evento = 'borrado')        as ultimo_borrado,
       -- TESTIGO: sin esto, todos los ceros de arriba se explican solos.
       (select max(vigente_desde) from precios_venta_historial)            as ultimo_precio_cargado;
