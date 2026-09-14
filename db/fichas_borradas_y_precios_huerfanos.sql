-- ¿Cuánto historial de precios quedó desconectado de su ficha, y por qué puerta?
--
-- CONTESTADA EL 14/09, Y LA PUERTA YA ESTÁ TAPADA. `huerfanos_viejos 0` en las
-- DOS bases (Frutamax 75 precios, Palmala 86): nunca se desconectó un precio,
-- no hubo nada que rescatar.
--
-- SU CERO YA NO INFORMA. Desde
-- db/precios_no_se_desconectan_al_borrar_la_ficha.sql la FK es NO ACTION, así
-- que el número no puede crecer: correrla de nuevo da cero POR CONSTRUCCIÓN,
-- no porque se haya verificado algo — el cero del corolario 47. Si se sospecha
-- que la FK se movió, eso lo contesta
-- db/precios_no_se_desconectan_verificacion.sql, que separa los dos
-- comportamientos en dos columnas; un "¿existe algún FK?" da 1 igual.
--
-- QUÉ MEDÍA. Esa FK ERA `on delete set null`: borrar una ficha no borraba sus
-- precios, les ponía `ficha_id` en NULL, y como todas las lecturas filtran
-- `ficha_id is not null` dejaban de existir para el sistema. El dato no se
-- perdía, se DESCONECTABA: por eso se podía contar.
--
-- ERAN DOS PUERTAS Y LA SEGUNDA NO PARECÍA UNA: eliminar la ficha, y CAMBIARLE
-- EL ARTÍCULO (por dentro un DELETE + INSERT con id nuevo). Las dos dejan un
-- evento 'borrado' en fichas_logistica_historial, y hoy las cierra la guarda
-- de app/db.py.
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
