-- ============================================================================
-- DROP de compras.foto_ruta — la deuda anotada al pasar a fotos por guía
-- ============================================================================
-- Las fotos viven en fotos_guia desde agregar_fotos_guia.sql (migración
-- verificada: 0 sin migrar en las dos bases) y el código no escribe ni lee
-- esta columna desde entonces. Quedó en la transición para poder volver
-- atrás; las fotos por guía vienen andando bien, así que se limpia.
--
-- ORDEN OBLIGATORIO: correr esto DESPUÉS de que esté deployado el commit
-- que saca la columna de los INSERT de compras y de la limpieza de fotos
-- (si se corre antes, la carga de compras rompe). El DROP arrastra solo
-- el índice compras_foto_ruta_idx.
--
-- IRREVERSIBLE: antes de correr, pasar la verificación de lectura (abajo,
-- comentada) y confirmar que la segunda consulta devuelve 0 filas.
--
-- Correr en las DOS bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

-- Verificación PREVIA (solo lectura, correr antes del DROP):
-- 1) Cuántas filas todavía tienen foto_ruta cargada (puede ser > 0: son
--    las viejas ya migradas; el dato vive en fotos_guia).
-- select count(*) as compras_con_foto_ruta from compras where foto_ruta is not null;
--
-- 2) LA QUE IMPORTA: fotos en compras que NO estén en fotos_guia.
--    TIENE QUE DAR 0 FILAS — si devuelve algo, NO correr el DROP y avisar.
-- select c.id, c.fecha_operacion, c.proveedor_id, c.foto_ruta
-- from compras c
-- where c.foto_ruta is not null
--   and not exists (select 1 from fotos_guia f where f.foto_ruta = c.foto_ruta)
-- order by c.fecha_operacion, c.id;

alter table compras drop column foto_ruta;

-- Verificación POSTERIOR: la columna ya no existe (0 filas) y el índice
-- parcial se fue con ella.
-- select column_name from information_schema.columns
--  where table_name = 'compras' and column_name = 'foto_ruta';
-- select indexname from pg_indexes where indexname = 'compras_foto_ruta_idx';
