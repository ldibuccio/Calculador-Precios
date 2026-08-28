-- ============================================================================
-- Verificación de agregar_senas_valor_historial.sql. Correr en CADA base
-- DESPUÉS de la migración.
--
-- Devuelve UNA sola tabla, una fila por chequeo, con OK o FALLA. Sin
-- NOTICE y sin result sets intermedios: el editor SQL de Supabase muestra
-- solo el último y no muestra los NOTICE.
--
-- No rompe nada si la tabla no existe: en ese caso el primer chequeo dice
-- FALLA y los demás dicen "no se pudo chequear" en vez de reventar.
--
-- Todo OK = la migración quedó bien. Cualquier FALLA = no marcar el ✅.
-- ============================================================================

with
tabla as (
    select to_regclass('public.senas_valor_historial') as oid
),
existe as (
    select (select oid from tabla) is not null as si
),
-- Las columnas tal como quedaron, con su tipo real.
columnas as (
    select a.attname::text                             as nombre,
           format_type(a.atttypid, a.atttypmod)        as tipo,
           a.attnotnull                                as obligatoria
    from pg_attribute a
    where a.attrelid = (select oid from tabla)
      and a.attnum > 0
      and not a.attisdropped
),
-- Las que tiene que haber, con el tipo exacto que usa
-- envases_costo_historial (numeric pelado, sin precisión).
esperadas (nombre, tipo, obligatoria) as (
    values ('id',             'bigint',                     true),
           ('tipo_envase_id', 'bigint',                     true),
           ('monto',          'numeric',                    true),
           ('vigente_desde',  'date',                       true),
           ('creado_en',      'timestamp with time zone',   true)
),
restricciones as (
    select c.contype, pg_get_constraintdef(c.oid) as definicion
    from pg_constraint c
    where c.conrelid = (select oid from tabla)
),
-- Contar filas sin nombrar la tabla en el FROM: si no existe, un
-- "select count(*) from senas_valor_historial" no compila y se cae toda
-- la consulta. query_to_xml la ejecuta recién si hace falta.
conteo as (
    select case
             when not (select si from existe) then null
             else (xpath('/row/c/text()',
                         query_to_xml('select count(*) as c from public.senas_valor_historial',
                                      false, true, '')))[1]::text::bigint
           end as filas
),
resultados (orden, chequeo, veredicto, detalle) as (

    select 1, 'La tabla senas_valor_historial existe',
           case when si then 'OK' else 'FALLA' end,
           case when si then 'creada' else 'NO EXISTE: la migración no se corrió' end
    from existe

    union all
    select 2, 'Las 5 columnas están, con el tipo correcto, y no sobra ninguna',
           case when not (select si from existe) then 'FALLA'
                when (select count(*) from esperadas e
                      join columnas c on c.nombre = e.nombre
                                     and c.tipo = e.tipo
                                     and c.obligatoria = e.obligatoria) = 5
                 and (select count(*) from columnas) = 5
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce(
                       (select string_agg(c.nombre || ' ' || c.tipo ||
                                          case when c.obligatoria then ' not null' else ' NULL' end,
                                          ', ' order by c.nombre)
                        from columnas c), 'sin columnas') end

    union all
    select 3, 'La primary key está sobre id',
           case when not (select si from existe) then 'FALLA'
                when exists (select 1 from restricciones
                             where contype = 'p' and definicion = 'PRIMARY KEY (id)')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select definicion from restricciones where contype = 'p'),
                              'no hay primary key') end

    union all
    select 4, 'La FK apunta a tipos_envase_puesto (id)',
           case when not (select si from existe) then 'FALLA'
                when exists (select 1 from restricciones
                             where contype = 'f'
                               and definicion = 'FOREIGN KEY (tipo_envase_id) REFERENCES tipos_envase_puesto(id)')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select string_agg(definicion, ' / ') from restricciones where contype = 'f'),
                              'no hay foreign key') end

    union all
    select 5, 'El UNIQUE es (tipo_envase_id, vigente_desde)',
           case when not (select si from existe) then 'FALLA'
                when exists (select 1 from restricciones
                             where contype = 'u'
                               and definicion = 'UNIQUE (tipo_envase_id, vigente_desde)')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select string_agg(definicion, ' / ') from restricciones where contype = 'u'),
                              'no hay unique') end

    union all
    select 6, 'El check del monto es >= 0 (el cero explícito se permite)',
           case when not (select si from existe) then 'FALLA'
                when exists (select 1 from restricciones
                             where contype = 'c' and definicion like '%monto >= %0%')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select string_agg(definicion, ' / ') from restricciones where contype = 'c'),
                              'no hay check') end

    union all
    select 7, 'La tabla arranca vacía',
           case when not (select si from existe) then 'FALLA'
                when (select filas from conteo) = 0 then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else (select filas from conteo)::text || ' filas' end
)
select chequeo,
       veredicto,
       detalle,
       -- El veredicto de conjunto, repetido en cada fila para que se vea
       -- sin tener que leer las siete.
       case when (select count(*) from resultados where veredicto = 'FALLA') = 0
            then 'TODO OK'
            else (select count(*) from resultados where veredicto = 'FALLA')::text || ' FALLA(S)'
       end as resultado_general
from resultados
order by orden;
