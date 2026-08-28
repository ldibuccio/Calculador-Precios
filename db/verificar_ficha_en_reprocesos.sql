-- ============================================================================
-- Verificación de la ETAPA 1 (ficha_id en reprocesos). Correr en CADA base
-- DESPUÉS de la migración.
--
-- Una sola tabla, una fila por chequeo, con OK o FALLA. Sin NOTICE: el
-- editor de Supabase muestra solo el último result set y no muestra los
-- NOTICE.
--
-- Todo OK = quedó bien. Cualquier FALLA = no marcar el ✅ en APLICADO.md.
-- ============================================================================

with
tabla as (
    select to_regclass('public.reprocesos') as oid
),
existe as (
    select (select oid from tabla) is not null as si
),
columna as (
    select a.attnotnull as obligatoria,
           format_type(a.atttypid, a.atttypmod) as tipo
    from pg_attribute a
    where a.attrelid = (select oid from tabla)
      and a.attname = 'ficha_id' and a.attnum > 0 and not a.attisdropped
),
fk as (
    select c.confdeltype, pg_get_constraintdef(c.oid) as definicion
    from pg_constraint c
    where c.conrelid = (select oid from tabla) and c.contype = 'f'
      and pg_get_constraintdef(c.oid) like '%(ficha_id)%'
),
indices as (
    select i.indexname, i.indexdef
    from pg_indexes i
    where i.schemaname = 'public' and i.tablename = 'reprocesos'
),
conteo as (
    select case when not (select si from existe) then null
                else (xpath('/row/c/text()',
                       query_to_xml('select count(*) as c from public.reprocesos', false, true, '')
                     ))[1]::text::bigint end as filas,
           case when not (select si from existe) then null
                when not exists (select 1 from columna) then null
                else (xpath('/row/c/text()',
                       query_to_xml('select count(*) as c from public.reprocesos where ficha_id is not null',
                                    false, true, '')))[1]::text::bigint end as con_ficha
),
resultados (orden, chequeo, veredicto, detalle) as (

    select 1, 'La tabla reprocesos existe',
           case when si then 'OK' else 'FALLA' end,
           case when si then 'está' else 'NO EXISTE' end
    from existe

    union all
    select 2, 'La columna ficha_id existe, es bigint y es NULLABLE',
           case when not exists (select 1 from columna) then 'FALLA'
                when (select tipo from columna) = 'bigint'
                 and not (select obligatoria from columna) then 'OK'
                else 'FALLA' end,
           coalesce((select tipo || case when obligatoria then ' NOT NULL (tiene que ser nullable)'
                                         else ' nullable' end from columna),
                    'no está: la migración no se corrió')

    union all
    select 3, 'La FK apunta a fichas_logistica (id)',
           case when exists (select 1 from fk
                             where definicion = 'FOREIGN KEY (ficha_id) REFERENCES fichas_logistica(id)')
                then 'OK' else 'FALLA' end,
           coalesce((select string_agg(definicion, ' / ') from fk), 'no hay foreign key por ficha_id')

    union all
    -- El chequeo que más importa: SET NULL borraría en silencio la
    -- asignación de un reproceso y la volvería indistinguible de un
    -- "sin asignar".
    select 4, 'La FK NO es ON DELETE SET NULL (protege la asignación)',
           case when not exists (select 1 from fk) then 'FALLA'
                when (select confdeltype from fk) = 'a' then 'OK'
                else 'FALLA' end,
           coalesce((select case confdeltype
                              when 'a' then 'NO ACTION, como tiene que ser'
                              when 'r' then 'RESTRICT (sirve igual, pero no es lo escrito)'
                              when 'n' then 'SET NULL: MAL, nulea la asignación al borrar la ficha'
                              when 'c' then 'CASCADE: MAL, borraría la guía R entera'
                              else 'otro: ' || confdeltype::text end from fk),
                    'no se pudo chequear: no hay FK')

    union all
    select 5, 'Está el índice parcial por ficha_id',
           case when exists (select 1 from indices
                             where indexdef like '%(ficha_id)%' and indexdef like '%WHERE%')
                then 'OK' else 'FALLA' end,
           coalesce((select string_agg(indexname, ' / ' order by indexname) from indices), 'sin índices')

    union all
    -- Lo que NO tenía que tocarse.
    select 6, 'Las columnas viejas siguen intactas',
           case when (select count(*) from pg_attribute
                      where attrelid = (select oid from tabla) and attnum > 0 and not attisdropped
                        and attname in ('articulo_id','cliente_id','bultos_tomados','bultos_primera',
                                        'bultos_segunda','bultos_merma','costo_total','anulado_el')) = 8
                then 'OK' else 'FALLA' end,
           (select count(*)::text || ' de 8 presentes' from pg_attribute
            where attrelid = (select oid from tabla) and attnum > 0 and not attisdropped
              and attname in ('articulo_id','cliente_id','bultos_tomados','bultos_primera',
                              'bultos_segunda','bultos_merma','costo_total','anulado_el'))

    union all
    -- La migración es aditiva: no inventó datos.
    select 7, 'Ninguna fila existente quedó con ficha asignada',
           case when (select con_ficha from conteo) = 0 then 'OK' else 'FALLA' end,
           coalesce((select filas::text || ' guías R en total, ' || con_ficha::text || ' con ficha'
                     from conteo), 'no se pudo contar')
)
select chequeo, veredicto, detalle,
       case when (select count(*) from resultados where veredicto = 'FALLA') = 0
            then 'TODO OK'
            else (select count(*) from resultados where veredicto = 'FALLA')::text || ' FALLA(S)'
       end as resultado_general
from resultados
order by orden;
