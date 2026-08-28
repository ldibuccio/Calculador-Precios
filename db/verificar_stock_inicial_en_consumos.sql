-- ============================================================================
-- Verificación del arrastre de la ETAPA 2. Correr en CADA base DESPUÉS de
-- agregar_stock_inicial_a_consumos.sql. Se esperan 4 filas, todas OK.
-- ============================================================================

with
t as (select to_regclass('public.reprocesos_consumos') as oid),
def as (
    select pg_get_constraintdef(c.oid) as d
    from pg_constraint c
    where c.contype = 'c' and c.conrelid = (select oid from t)
      and c.conname = 'reprocesos_consumos_origen_check'
),
conteo as (
    select case when (select oid from t) is null then null
                else (xpath('/row/c/text()', query_to_xml(
                        'select count(*) as c from public.reprocesos_consumos',
                        false, true, '')))[1]::text::bigint end as filas
),
resultados (orden, chequeo, veredicto, detalle) as (

    select 1, 'reprocesos_consumos acepta el origen stock_inicial',
           case when (select d from def) like '%''stock_inicial''%' then 'OK' else 'FALLA' end,
           coalesce((select d from def), 'no está el check de origen')

    union all
    -- Lo que NO tenía que perderse al reescribir la lista.
    select 2, 'Los cinco orígenes viejos siguen aceptados',
           case when (select d from def) like '%''compra''%'
                 and (select d from def) like '%''ajuste''%'
                 and (select d from def) like '%''reingreso_rechazo''%'
                 and (select d from def) like '%''reproceso''%'
                 and (select d from def) like '%''sin_lote''%'
                then 'OK' else 'FALLA' end,
           coalesce((select d from def), 'no está el check de origen')

    union all
    select 3, 'El check sigue existiendo (no se dropeó y listo)',
           case when exists (select 1 from def) then 'OK' else 'FALLA' end,
           case when exists (select 1 from def) then 'está'
                else 'NO ESTÁ: la tabla quedó sin candado y acepta cualquier texto' end

    union all
    -- Aditiva: no tocó ninguna fila.
    select 4, 'Los consumos existentes siguen ahí',
           case when (select filas from conteo) is not null then 'OK' else 'FALLA' end,
           coalesce((select filas::text || ' consumos en la tabla' from conteo),
                    'no se pudo contar: falta la tabla')
)
select chequeo, veredicto, detalle,
       case when (select count(*) from resultados where veredicto = 'FALLA') = 0
            then 'TODO OK'
            else (select count(*) from resultados where veredicto = 'FALLA')::text || ' FALLA(S)'
       end as resultado_general
from resultados
order by orden;
