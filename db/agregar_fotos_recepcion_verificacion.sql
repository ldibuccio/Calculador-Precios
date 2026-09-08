-- BLOQUE 2 — verificación de agregar_fotos_recepcion.sql. Solo lectura.
-- Devuelve CONTEOS y una sola fila: así el cero se ve. Con una lista,
-- "está todo bien" y "no corrió" serían la misma pantalla vacía.
--
-- Esperado en las dos bases:
--   tabla 1 · columnas 4 · fk_apunta_a "compras" · unicas 1 · pk 1
--
-- ultima_recepcion / recepcionadas son el TESTIGO DE ACTIVIDAD: sin él, una
-- base detenida contesta cero a todo y el cero se lee como "acá está bien".
select
  (select count(*) from pg_class
    where relname = 'fotos_recepcion'
      and relnamespace = 'public'::regnamespace)                         as tabla,
  (select count(*) from information_schema.columns
    where table_schema = 'public'
      and table_name = 'fotos_recepcion')                                as columnas,
  (select confrelid::regclass::text from pg_constraint
    where conrelid = to_regclass('public.fotos_recepcion')
      and contype = 'f')                                                 as fk_apunta_a,
  (select count(*) from pg_constraint
    where conrelid = to_regclass('public.fotos_recepcion')
      and contype = 'u')                                                 as unicas,
  (select count(*) from pg_constraint
    where conrelid = to_regclass('public.fotos_recepcion')
      and contype = 'p')                                                 as pk,
  (select max(fecha_operacion) from compras
    where estado = 'recepcionado')                                       as ultima_recepcion,
  (select count(*) from compras
    where estado = 'recepcionado')                                       as recepcionadas;
