-- ============================================================================
-- Verificación de esquema entre dos bases (ej. Frutamax vs. Palmalá)
--
-- CONSULTA 1 (la corta): correrla en el editor SQL de CADA Supabase y
-- comparar las dos salidas. Devuelve UNA fila por tabla viva (13 filas),
-- con la cantidad de columnas y de constraints y una "firma" (hash) de
-- cada cosa — compacta a propósito, para poder copiarla entera desde el
-- celular. Si las 13 filas coinciden en las dos bases, los esquemas son
-- idénticos en todo lo que importa y no hay nada más que mirar.
--
-- Si alguna fila difiere (distinta firma o distinta cantidad), recién ahí
-- correr la CONSULTA 2 en las dos bases, cambiando 'compras' por la tabla
-- que difirió, y comparar el detalle.
--
-- Solo mira las 13 tablas que el código usa. Las tablas muertas del diseño
-- original que quedaron en Frutamax (recepciones, precios_dia, etc.) no
-- entran en la comparación: en la base nueva no existen a propósito.
--
-- Ojo: si los dos proyectos de Supabase corren versiones distintas de
-- Postgres, la firma de constraints puede diferir por formato (no por
-- contenido). En ese caso la CONSULTA 2 muestra las definiciones reales
-- para comparar a ojo.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- CONSULTA 1: resumen compacto (una fila por tabla)
-- ---------------------------------------------------------------------------
with tablas as (
    select unnest(array[
        'articulos', 'proveedores', 'clientes', 'clientes_parametros_historial',
        'envases', 'envases_costo_historial', 'fichas_logistica', 'guias_compra',
        'compras', 'precios_venta_historial', 'disponibles', 'disponibles_detalle',
        'aprendizaje_articulos'
    ]) as tabla
),
cols as (
    select c.table_name as tabla,
           count(*) as columnas,
           substr(md5(string_agg(
               c.column_name || ':' || c.data_type || ':' || c.is_nullable || ':' || coalesce(c.column_default, '-'),
               '|' order by c.column_name
           )), 1, 8) as firma_col
    from information_schema.columns c
    where c.table_schema = 'public'
    group by c.table_name
),
cons as (
    select rel.relname as tabla,
           count(*) as constraints,
           substr(md5(string_agg(
               con.conname || ':' || pg_get_constraintdef(con.oid),
               '|' order by con.conname
           )), 1, 8) as firma_con
    from pg_constraint con
    join pg_class rel on rel.oid = con.conrelid
    join pg_namespace ns on ns.oid = rel.relnamespace
    where ns.nspname = 'public' and con.contype in ('p', 'u', 'f', 'c')
    group by rel.relname
)
select t.tabla,
       coalesce(c.columnas, 0) as cols,
       coalesce(c.firma_col, 'FALTA') as firma_col,
       coalesce(k.constraints, 0) as constr,
       coalesce(k.firma_con, '-') as firma_con
from tablas t
left join cols c on c.tabla = t.tabla
left join cons k on k.tabla = t.tabla
order by t.tabla;

-- ---------------------------------------------------------------------------
-- CONSULTA 2: detalle de UNA tabla (correr solo si la CONSULTA 1 difirió).
-- Cambiar 'compras' por la tabla que difirió, correr en las dos bases,
-- comparar renglón por renglón.
-- ---------------------------------------------------------------------------
-- select column_name, data_type, is_nullable, coalesce(column_default, '-') as col_default
-- from information_schema.columns
-- where table_schema = 'public' and table_name = 'compras'
-- order by column_name;
--
-- select con.conname, pg_get_constraintdef(con.oid) as definicion
-- from pg_constraint con
-- join pg_class rel on rel.oid = con.conrelid
-- join pg_namespace ns on ns.oid = rel.relnamespace
-- where ns.nspname = 'public' and rel.relname = 'compras'
--   and con.contype in ('p', 'u', 'f', 'c')
-- order by con.conname;
