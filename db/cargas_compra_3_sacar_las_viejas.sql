do $$
begin
  drop table if exists listados_compra_manual;
  drop table if exists listados_compra_clientes;
  alter table listados_compra drop column if exists margen_porcentaje;
end $$;

-- SE CORRE DESPUÉS DE QUE EL CÓDIGO NUEVO ESTÉ DESPLEGADO, no con los otros
-- dos bloques. Hasta el deploy, `borrador_de_compra` y
-- `guardar_borrador_de_compra` todavía leen y escriben estas dos tablas:
-- dropearlas antes deja "Qué comprar hoy" en 500 durante la ventana entre la
-- migración y el push. Los dos bloques de arriba solo CREAN, así que se
-- pueden correr en cualquier momento sin romper nada.
--
-- Las reemplazan `cargas_compra` (la carga vive sola, con su cliente y su
-- fecha) y `listados_compra_cargas` (qué cargas arma cada listado). El
-- rediseño del 22/09 partió "Qué comprar hoy" en dos pasos, y un listado
-- dejó de estar identificado por una fecha: ahora toma dos días de Día y uno
-- de Tailem, que la estructura vieja no podía expresar.
--
-- El orden importa y por eso van en un solo `do`: listados_compra_manual
-- tiene una FK contra listados_compra_clientes, así que la hija va primero.
--
-- Las dos estaban en CERO en las dos bases el 22/09 (`listados_ya_cargados`
-- 0 en la verificación de listados_compra), así que no hay nada que migrar.
--
-- Y EL MARGEN DEL LISTADO SE VA EN EL MISMO BLOQUE: vive en cada carga desde
-- el 23/09, y el código nuevo ya no lo lee ni lo escribe. Dejarlo en cero
-- sería el apagado que alguien toca: vuelve la multiplicación, invisible.
-- Su CHECK se va con la columna.
--
-- Verificación, APARTE: tiene que dar 0 · 0 · 0 · <clientes>.
--   select 'sacar_las_viejas' as QUE_MIGRACION,
--          (select count(*) from pg_class c join pg_namespace n
--                 on n.oid = c.relnamespace
--            where n.nspname = 'public'
--              and c.relname = 'listados_compra_clientes') as clientes_de_0,
--          (select count(*) from pg_class c join pg_namespace n
--                 on n.oid = c.relnamespace
--            where n.nspname = 'public'
--              and c.relname = 'listados_compra_manual') as manual_de_0,
--          (select count(*) from information_schema.columns
--            where table_schema = 'public' and table_name = 'listados_compra'
--              and column_name = 'margen_porcentaje') as margen_de_0,
--          (select count(*) from clientes) as POBLACION_clientes;
