-- ============================================================================
-- Verificación de la ETAPA 2 (fecha de corte + stock inicial). Correr en CADA
-- base DESPUÉS de la migración agregar_corte_y_stock_inicial.sql.
--
-- Una sola tabla, una fila por chequeo, con OK o FALLA. Sin NOTICE: el editor
-- de Supabase muestra solo el último result set y no muestra los NOTICE.
--
-- Todo OK = quedó bien. Cualquier FALLA = no marcar el ✅ en APLICADO.md.
-- ============================================================================

with
t_mov as (select to_regclass('public.movimientos_stock') as oid),
t_rep as (select to_regclass('public.reprocesos') as oid),
t_cor as (select to_regclass('public.corte_modelo') as oid),

-- Las definiciones normalizadas por Postgres (con sus ::text y sus ARRAY[]).
checks as (
    select c.conrelid, c.conname, pg_get_constraintdef(c.oid) as def
    from pg_constraint c
    where c.contype = 'c'
      and c.conrelid in ((select oid from t_mov), (select oid from t_rep),
                         (select oid from t_cor))
),
def_tipo_mov as (
    select def from checks
    where conrelid = (select oid from t_mov) and conname = 'movimientos_stock_tipo_check'
),
def_vinculo as (
    select def from checks
    where conrelid = (select oid from t_mov)
      and conname = 'movimientos_stock_vinculo_solo_reingreso'
),
def_lote as (
    select def from checks
    where conrelid = (select oid from t_mov) and conname = 'movimientos_stock_lote_tipo_check'
),
def_tipo_rep as (
    select def from checks
    where conrelid = (select oid from t_rep) and conname = 'reprocesos_tipo_check'
),
def_tomados as (
    select def from checks
    where conrelid = (select oid from t_rep) and conname = 'reprocesos_bultos_tomados_check'
),
col_tipo_rep as (
    select a.attnotnull as obligatoria,
           format_type(a.atttypid, a.atttypmod) as tipo,
           pg_get_expr(d.adbin, d.adrelid) as por_defecto
    from pg_attribute a
    left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
    where a.attrelid = (select oid from t_rep)
      and a.attname = 'tipo' and a.attnum > 0 and not a.attisdropped
),
-- Contar sin nombrar en el FROM una tabla que puede no existir todavía.
conteos as (
    select
      case when (select oid from t_rep) is null
             or not exists (select 1 from col_tipo_rep) then null
           else (xpath('/row/c/text()', query_to_xml(
                   'select count(*) as c from public.reprocesos', false, true, '')))[1]::text::bigint
      end as reprocesos_total,
      case when (select oid from t_rep) is null
             or not exists (select 1 from col_tipo_rep) then null
           else (xpath('/row/c/text()', query_to_xml(
                   'select count(*) as c from public.reprocesos where tipo <> ''normal''',
                   false, true, '')))[1]::text::bigint
      end as reprocesos_no_normales,
      case when (select oid from t_cor) is null then null
           else (xpath('/row/c/text()', query_to_xml(
                   'select count(*) as c from public.corte_modelo', false, true, '')))[1]::text::bigint
      end as filas_corte,
      -- Con la subconsulta escalar adentro, la fila SIEMPRE existe aunque la
      -- tabla esté vacía. Sacarla afuera devolvía un XML vacío y xpath se caía
      -- con "could not parse XML document": el verificador moría en vez de
      -- avisar que faltaba el insert.
      case when (select oid from t_cor) is null then null
           else (xpath('/row/f/text()', query_to_xml(
                   'select coalesce((select fecha from public.corte_modelo where id = 1)::text,
                                    ''no hay fila con id = 1'') as f',
                   false, true, '')))[1]::text
      end as fecha_corte
),

resultados (orden, chequeo, veredicto, detalle) as (

    select 1, 'movimientos_stock acepta el tipo stock_inicial',
           case when (select def from def_tipo_mov) like '%''stock_inicial''%' then 'OK' else 'FALLA' end,
           coalesce((select def from def_tipo_mov), 'no está el check de tipo')

    union all
    -- Que no se haya perdido ninguno de los tres viejos al reescribir el check.
    select 2, 'Los tres tipos viejos siguen aceptados',
           case when (select def from def_tipo_mov) like '%''ajuste''%'
                 and (select def from def_tipo_mov) like '%''merma''%'
                 and (select def from def_tipo_mov) like '%''reingreso_rechazo''%'
                then 'OK' else 'FALLA' end,
           coalesce((select def from def_tipo_mov), 'no está el check de tipo')

    union all
    -- El que más importa de movimientos_stock: sin esto el stock inicial
    -- nace sin costo y nunca se le puede poner.
    select 3, 'El stock inicial PUEDE llevar costo_por_bulto',
           case when (select def from def_vinculo) like '%''stock_inicial''%' then 'OK' else 'FALLA' end,
           coalesce((select def from def_vinculo), 'no está el check de vínculo')

    union all
    -- Y que la puerta no se haya abierto de más: un ajuste con costo sigue
    -- siendo un error.
    select 4, 'Un ajuste o una merma siguen SIN poder llevar costo',
           case when (select def from def_vinculo) like '%costo_por_bulto IS NULL%'
                 and (select def from def_vinculo) not like '%''ajuste''%'
                 and (select def from def_vinculo) not like '%''merma''%'
                then 'OK' else 'FALLA' end,
           coalesce((select def from def_vinculo), 'no está el check de vínculo')

    union all
    select 5, 'pedido_renglon_id sigue siendo solo del reingreso',
           case when (select def from def_vinculo) like '%pedido_renglon_id IS NULL%'
                then 'OK' else 'FALLA' end,
           coalesce((select def from def_vinculo), 'no está el check de vínculo')

    union all
    -- Sin esto no se le puede dar de baja por merma a un lote inicial podrido.
    select 6, 'Una merma puede apuntar a un lote de stock inicial',
           case when (select def from def_lote) like '%''stock_inicial''%' then 'OK' else 'FALLA' end,
           coalesce((select def from def_lote), 'no está el check de lote_tipo')

    union all
    select 7, 'reprocesos.tipo existe, es texto, NOT NULL y default normal',
           case when not exists (select 1 from col_tipo_rep) then 'FALLA'
                when (select tipo from col_tipo_rep) = 'text'
                 and (select obligatoria from col_tipo_rep)
                 and coalesce((select por_defecto from col_tipo_rep), '') like '%''normal''%'
                then 'OK' else 'FALLA' end,
           coalesce((select tipo || case when obligatoria then ' NOT NULL' else ' NULLABLE (mal)' end
                            || ' default ' || coalesce(por_defecto, 'ninguno (mal)')
                     from col_tipo_rep),
                    'no está: la migración no se corrió')

    union all
    select 8, 'reprocesos.tipo solo admite normal o inicial',
           case when (select def from def_tipo_rep) like '%''normal''%'
                 and (select def from def_tipo_rep) like '%''inicial''%'
                then 'OK' else 'FALLA' end,
           coalesce((select def from def_tipo_rep), 'no está el check de tipo de reproceso')

    union all
    -- El corazón de la etapa: el reproceso inicial PRODUCE SIN CONSUMIR, y eso
    -- vive en el dato (bultos_tomados = 0), no en una excepción del código.
    select 9, 'El reproceso inicial toma CERO y el normal sigue tomando > 0',
           case when (select def from def_tomados) like '%''inicial''%'
                 and (select def from def_tomados) like '%''normal''%'
                 and (select def from def_tomados) like '%bultos_tomados = %'
                 and (select def from def_tomados) like '%bultos_tomados > %'
                then 'OK' else 'FALLA' end,
           coalesce((select def from def_tomados), 'no está el check de bultos_tomados')

    union all
    -- La migración es aditiva: no convirtió ninguna guía R vieja en inicial.
    select 10, 'Ninguna guía R existente quedó marcada como inicial',
           case when (select reprocesos_no_normales from conteos) = 0 then 'OK' else 'FALLA' end,
           coalesce((select reprocesos_total::text || ' guías R en total, '
                          || reprocesos_no_normales::text || ' con tipo distinto de normal'
                     from conteos),
                    'no se pudo contar: falta la tabla o la columna')

    union all
    select 11, 'corte_modelo existe y es de una sola fila',
           case when (select oid from t_cor) is null then 'FALLA'
                when (select filas_corte from conteos) = 1
                 and exists (select 1 from checks
                             where conrelid = (select oid from t_cor) and def like '%id = 1%')
                then 'OK' else 'FALLA' end,
           case when (select oid from t_cor) is null then 'no existe la tabla'
                else coalesce((select filas_corte::text from conteos), '?') || ' fila(s), '
                     || case when exists (select 1 from checks
                                          where conrelid = (select oid from t_cor) and def like '%id = 1%')
                             then 'con el candado check (id = 1)'
                             else 'SIN el candado check (id = 1)' end
           end

    union all
    select 12, 'La fecha de corte quedó en el lunes 31/08/2026',
           case when (select fecha_corte from conteos) = '2026-08-31' then 'OK' else 'FALLA' end,
           coalesce((select fecha_corte from conteos), 'no hay fila con id = 1')
)
select chequeo, veredicto, detalle,
       case when (select count(*) from resultados where veredicto = 'FALLA') = 0
            then 'TODO OK'
            else (select count(*) from resultados where veredicto = 'FALLA')::text || ' FALLA(S)'
       end as resultado_general
from resultados
order by orden;
