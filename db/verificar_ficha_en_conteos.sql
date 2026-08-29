-- ============================================================================
-- Verificación de la ETAPA 3 (ficha_id en conteos_stock). Correr en CADA
-- base DESPUÉS de la migración. Se esperan 7 filas, todas OK.
--
-- Sin NOTICE: el editor de Supabase muestra solo el último result set.
-- ============================================================================

with
t as (select to_regclass('public.conteos_stock') as oid),
columna as (
    select a.attnotnull as obligatoria, format_type(a.atttypid, a.atttypmod) as tipo
    from pg_attribute a
    where a.attrelid = (select oid from t)
      and a.attname = 'ficha_id' and a.attnum > 0 and not a.attisdropped
),
fk as (
    select c.confdeltype, pg_get_constraintdef(c.oid) as definicion
    from pg_constraint c
    where c.conrelid = (select oid from t) and c.contype = 'f'
      and pg_get_constraintdef(c.oid) like '%(ficha_id)%'
),
indices as (
    select indexname, indexdef from pg_indexes
    where schemaname = 'public' and tablename = 'conteos_stock'
),
conteo as (
    select
      case when (select oid from t) is null then null
           else (xpath('/row/c/text()', query_to_xml(
                   'select count(*) as c from public.conteos_stock', false, true, '')))[1]::text::bigint
      end as filas,
      case when (select oid from t) is null or not exists (select 1 from columna) then null
           else (xpath('/row/c/text()', query_to_xml(
                   'select count(*) as c from public.conteos_stock where ficha_id is not null',
                   false, true, '')))[1]::text::bigint
      end as con_ficha
),
resultados (orden, chequeo, veredicto, detalle) as (

    select 1, 'La tabla conteos_stock existe',
           case when (select oid from t) is not null then 'OK' else 'FALLA' end,
           case when (select oid from t) is not null then 'está' else 'NO EXISTE' end

    union all
    select 2, 'La columna ficha_id existe, es bigint y es NULLABLE',
           case when not exists (select 1 from columna) then 'FALLA'
                when (select tipo from columna) = 'bigint'
                 and not (select obligatoria from columna) then 'OK'
                else 'FALLA' end,
           coalesce((select tipo || case when obligatoria
                                         then ' NOT NULL (tiene que ser nullable: el NULL son los sueltos)'
                                         else ' nullable' end from columna),
                    'no está: la migración no se corrió')

    union all
    select 3, 'La FK apunta a fichas_logistica (id)',
           case when exists (select 1 from fk
                             where definicion = 'FOREIGN KEY (ficha_id) REFERENCES fichas_logistica(id)')
                then 'OK' else 'FALLA' end,
           coalesce((select string_agg(definicion, ' / ') from fk), 'no hay foreign key por ficha_id')

    union all
    -- El que más importa: con SET NULL, borrar una ficha convertiría un
    -- conteo de cajas en un conteo de sueltos, y el Cotejo mostraría una
    -- diferencia inexplicable en los dos lados a la vez.
    select 4, 'La FK NO es ON DELETE SET NULL',
           case when not exists (select 1 from fk) then 'FALLA'
                when (select confdeltype from fk) = 'a' then 'OK'
                else 'FALLA' end,
           coalesce((select case confdeltype
                              when 'a' then 'NO ACTION, como tiene que ser'
                              when 'r' then 'RESTRICT (sirve igual, pero no es lo escrito)'
                              when 'n' then 'SET NULL: MAL, un conteo de cajas pasaría a ser de sueltos'
                              when 'c' then 'CASCADE: MAL, borraría el conteo entero'
                              else 'otro: ' || confdeltype::text end from fk),
                    'no se pudo chequear: no hay FK')

    union all
    select 5, 'Está el índice del Cotejo, en el orden que usa',
           case when exists (select 1 from indices
                             where indexdef like '%articulo_id%'
                               and indexdef like '%ficha_id%'
                               and indexdef like '%creado_en DESC%')
                then 'OK' else 'FALLA' end,
           coalesce((select string_agg(indexname, ' / ' order by indexname) from indices), 'sin índices')

    union all
    select 6, 'Las columnas viejas siguen intactas',
           case when (select count(*) from pg_attribute
                      where attrelid = (select oid from t) and attnum > 0 and not attisdropped
                        and attname in ('articulo_id', 'cantidad', 'stock_sistema', 'creado_en')) = 4
                then 'OK' else 'FALLA' end,
           (select count(*)::text || ' de 4 presentes' from pg_attribute
            where attrelid = (select oid from t) and attnum > 0 and not attisdropped
              and attname in ('articulo_id', 'cantidad', 'stock_sistema', 'creado_en'))

    union all
    -- Aditiva: no le inventó ficha a ningún conteo viejo. Todos siguen
    -- significando "todo el artículo junto", que es lo que fueron.
    select 7, 'Ningún conteo existente quedó con ficha asignada',
           case when (select con_ficha from conteo) = 0 then 'OK' else 'FALLA' end,
           coalesce((select filas::text || ' conteos en total, ' || con_ficha::text || ' con ficha'
                     from conteo), 'no se pudo contar')
)
select chequeo, veredicto, detalle,
       case when (select count(*) from resultados where veredicto = 'FALLA') = 0
            then 'TODO OK'
            else (select count(*) from resultados where veredicto = 'FALLA')::text || ' FALLA(S)'
       end as resultado_general
from resultados
order by orden;
