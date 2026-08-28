-- ============================================================================
-- Verificación de senas_valor_historial_append_only.sql. Correr en CADA
-- base DESPUÉS de esa migración.
--
-- Una sola tabla, una fila por chequeo, con OK o FALLA. Sin NOTICE y sin
-- result sets intermedios: el editor de Supabase muestra solo el último y
-- no muestra los NOTICE.
--
-- Todo OK = quedó bien. Cualquier FALLA = no marcar el ✅.
-- ============================================================================

with
tabla as (
    select to_regclass('public.senas_valor_historial') as oid
),
existe as (
    select (select oid from tabla) is not null as si
),
restricciones as (
    select c.contype, c.conname, pg_get_constraintdef(c.oid) as definicion
    from pg_constraint c
    where c.conrelid = (select oid from tabla)
),
indices as (
    select i.indexname, i.indexdef
    from pg_indexes i
    where i.schemaname = 'public' and i.tablename = 'senas_valor_historial'
),
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
           case when si then 'está' else 'NO EXISTE: falta la migración anterior' end
    from existe

    union all
    -- Lo que vino a hacer esta migración.
    select 2, 'El UNIQUE por (tipo_envase_id, vigente_desde) YA NO ESTÁ',
           case when not (select si from existe) then 'FALLA'
                when not exists (select 1 from restricciones where contype = 'u')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select string_agg(definicion, ' / ') from restricciones where contype = 'u'),
                              'ningún unique, como tiene que ser') end

    union all
    select 3, 'Está el índice (tipo_envase_id, vigente_desde DESC, creado_en DESC)',
           case when not (select si from existe) then 'FALLA'
                when exists (select 1 from indices
                             where indexdef like '%(tipo_envase_id, vigente_desde DESC, creado_en DESC)')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select string_agg(indexname, ' / ' order by indexname) from indices),
                              'sin índices') end

    union all
    -- Lo que NO tenía que tocarse.
    select 4, 'La primary key sigue sobre id',
           case when not (select si from existe) then 'FALLA'
                when exists (select 1 from restricciones
                             where contype = 'p' and definicion = 'PRIMARY KEY (id)')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select definicion from restricciones where contype = 'p'),
                              'no hay primary key') end

    union all
    select 5, 'La FK a tipos_envase_puesto sigue',
           case when not (select si from existe) then 'FALLA'
                when exists (select 1 from restricciones
                             where contype = 'f'
                               and definicion = 'FOREIGN KEY (tipo_envase_id) REFERENCES tipos_envase_puesto(id)')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select string_agg(definicion, ' / ') from restricciones where contype = 'f'),
                              'no hay foreign key') end

    union all
    select 6, 'El check del monto >= 0 sigue',
           case when not (select si from existe) then 'FALLA'
                when exists (select 1 from restricciones
                             where contype = 'c' and definicion like '%monto >= %0%')
                then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else coalesce((select string_agg(definicion, ' / ') from restricciones where contype = 'c'),
                              'no hay check') end

    union all
    -- Y que la migración se haya corrido en el momento barato.
    select 7, 'La tabla sigue vacía',
           case when not (select si from existe) then 'FALLA'
                when (select filas from conteo) = 0 then 'OK' else 'FALLA' end,
           case when not (select si from existe) then 'no se pudo chequear: la tabla no existe'
                else (select filas from conteo)::text || ' filas' end
)
select chequeo,
       veredicto,
       detalle,
       case when (select count(*) from resultados where veredicto = 'FALLA') = 0
            then 'TODO OK'
            else (select count(*) from resultados where veredicto = 'FALLA')::text || ' FALLA(S)'
       end as resultado_general
from resultados
order by orden;
