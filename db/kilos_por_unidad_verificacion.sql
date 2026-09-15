-- Verificación de db/kilos_por_unidad_en_el_articulo.sql. UNA fila siempre.
-- Correr en LAS DOS bases y pegar LAS DOS filas con el nombre de la base
-- adelante: las columnas que importan dan lo mismo en las dos por diseño,
-- así que las filas son indistinguibles entre sí y el testigo es lo único
-- que dice de cuál base es cada una.
--
-- `columna` y `guarda` cuentan POR NOMBRE: un "¿existe alguna columna?"
-- daría 1 igual con el constraint sin poner.
--
-- SE CORRE DESPUÉS DE LA MIGRACIÓN. Corrida antes, no devuelve una fila de
-- ceros: FALLA con `column "kilos_por_unidad" does not exist`, y ese error
-- ES la respuesta —la columna no está— no una consulta rota. Se deja así a
-- propósito: una fila de ceros se confunde con "migró y no hay datos", y el
-- error no se confunde con nada.
select
    (select count(*) from information_schema.columns
      where table_name = 'articulos' and column_name = 'kilos_por_unidad') as columna,
    (select count(*) from pg_constraint
      where conname = 'articulos_kilos_por_unidad_check')                  as guarda,
    (select count(*) from pg_description d
       join pg_class c on c.oid = d.objoid
      where c.relname = 'articulos' and d.objsubid = (
            select ordinal_position from information_schema.columns
             where table_name = 'articulos' and column_name = 'kilos_por_unidad'))
                                                                           as comentario,
    -- Cuántos artículos tienen factor cargado, sobre cuántos podrían
    -- necesitarlo. El segundo es la población: sin ella el cero de la
    -- izquierda no se puede leer.
    (select count(*) from articulos where kilos_por_unidad is not null)    as con_factor,
    (select count(*) from articulos where activo)                          as arts_activos,
    -- Ofensor: un factor cargado donde no puede significar nada. La cubeta
    -- no tiene peso estable y el factor no la convierte.
    (select count(*) from articulos
      where kilos_por_unidad is not null and unidad_compra = 'cubeta')     as factor_en_cubeta,
    -- Testigo de actividad: un cero sobre una base parada se lee igual que
    -- uno bueno.
    (select max(fecha_operacion) from compras)                             as ultima_compra;
