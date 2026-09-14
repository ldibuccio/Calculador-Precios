-- Verificación de db/precios_no_se_desconectan_al_borrar_la_ficha.sql.
--
-- Cuenta el constraint POR NOMBRE y separa los DOS comportamientos en dos
-- columnas: un "¿existe algún FK?" daría 1 con SET NULL puesto y taparía el
-- caso. `guarda_no_action 1 · quedo_en_set_null 0` es lo que hay que ver.
--
-- Verificada contra db/esquema_completo.sql con las dos respuestas: sin la
-- migración da 0 y 1; con la migración da 1 y 0. Probado además que borrar
-- una ficha CON precio falla y que borrar una SIN precio sigue andando — el
-- caso feliz es el único que distingue una guarda que funciona de una que
-- frena siempre.
--
-- `huerfanos_viejos` es lo que la migración NO arregla: las filas que ya
-- quedaron desconectadas. Ese número decide si hace falta un rescate.
select (select count(*) from pg_constraint
         where conname = 'precios_venta_historial_ficha_id_fkey'
           and confdeltype = 'a')                                   as guarda_no_action,
       (select count(*) from pg_constraint
         where conname = 'precios_venta_historial_ficha_id_fkey'
           and confdeltype = 'n')                                   as quedo_en_set_null,
       (select count(*) from precios_venta_historial
         where ficha_id is null)                                    as huerfanos_viejos,
       (select count(*) from precios_venta_historial)               as precios_total,
       -- TESTIGO: sin esto, todos los ceros de arriba se explican solos.
       (select max(vigente_desde) from precios_venta_historial)     as ultimo_precio_cargado;
