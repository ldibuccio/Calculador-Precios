-- ============================================================================
-- SACAR LA EXCEPCIÓN AL FRENO DEL REPROCESO
--
-- El 02/09 se dio marcha atrás con la salida de escape del freno: el
-- reproceso es 100% o nada, y una excepción con motivo es "avisa y sigue"
-- con más pasos. Se sacó el código (la pantalla de Operarios, las cuatro
-- rutas, las tres funciones) y esto saca lo que quedó en la base.
--
-- ORDEN, y no es prolijidad: primero deja de usarse, después se borra.
-- excepcion_operario_id es una FK a operarios_deposito, y la pantalla que
-- consultaba esa tabla estuvo desplegada. Este script se corre DESPUÉS de
-- que ese código ya no está en producción.
--
-- BORRA CINCO OBJETOS:
--   1. reprocesos.excepcion_motivo
--   2. reprocesos.excepcion_operario_id
--   3. el check reprocesos_excepcion_completa
--   4. el índice reprocesos_excepcion_idx
--   5. la tabla operarios_deposito (con su índice único normalizado)
--
-- NO TOCA reprocesos.consumos_editados: esa columna la usa el desglose
-- editable, que sí quedó, y Guías R la muestra.
--
-- SI ENCUENTRA UN SOLO DATO CARGADO, NO BORRA NADA Y ABORTA. La excepción
-- se saca porque nunca se usó; si tiene datos, alguien la usó y eso lo
-- mira una persona antes de perderlo.
--
-- Es idempotente: correrlo dos veces no rompe.
-- Se corre a mano en el editor de Supabase, en las DOS bases.
-- ============================================================================

do $$
declare
    con_motivo   bigint := 0;
    con_operario bigint := 0;
    operarios    bigint := 0;
begin
    -- ---------------------------------------------------------------------
    -- 1. LAS GUARDAS. Van todas antes de tocar nada: en un bloque `do` esto
    --    es una sola sentencia, así que el raise deshace todo lo de abajo.
    --    Los execute son porque la columna puede no existir (segunda
    --    corrida): sin ellos el bloque ni siquiera compila.
    -- ---------------------------------------------------------------------
    if exists (
        select 1 from information_schema.columns
        where table_name = 'reprocesos' and column_name = 'excepcion_motivo'
    ) then
        execute 'select count(*) from reprocesos where excepcion_motivo is not null'
            into con_motivo;
    end if;

    if exists (
        select 1 from information_schema.columns
        where table_name = 'reprocesos' and column_name = 'excepcion_operario_id'
    ) then
        execute 'select count(*) from reprocesos where excepcion_operario_id is not null'
            into con_operario;
    end if;

    if to_regclass('public.operarios_deposito') is not null then
        execute 'select count(*) from operarios_deposito' into operarios;
    end if;

    if con_motivo > 0 or con_operario > 0 or operarios > 0 then
        raise exception
            'NO SE BORRÓ NADA. Hay % guías con motivo de excepción, % con operario y % operarios cargados. La excepción se saca porque NUNCA se usó: si tiene datos, alguien la usó y hay que mirarlo antes de perderlo.',
            con_motivo, con_operario, operarios;
    end if;

    -- ---------------------------------------------------------------------
    -- 2. Los cinco objetos. El check y el índice se van solos con las
    --    columnas, pero se nombran igual: lo que se borra tiene que estar
    --    escrito, no deducirse de un CASCADE.
    -- ---------------------------------------------------------------------
    alter table reprocesos drop constraint if exists reprocesos_excepcion_completa;
    drop index if exists reprocesos_excepcion_idx;
    alter table reprocesos drop column if exists excepcion_operario_id;
    alter table reprocesos drop column if exists excepcion_motivo;
    drop table if exists operarios_deposito;
end $$;

-- ============================================================================
-- LO QUE HAY QUE VER. Una sola consulta: el editor muestra solo el
-- resultado de la última, y los NOTICE no los muestra nunca.
-- Los cinco primeros tienen que decir "borrado". Los dos últimos son los
-- que NO se tocan: si alguno cambió, algo se llevó puesto de más.
-- ============================================================================
select orden, objeto, estado from (
    select 1 as orden, 'reprocesos.excepcion_motivo' as objeto,
           case when exists (select 1 from information_schema.columns
                             where table_name = 'reprocesos' and column_name = 'excepcion_motivo')
                then '❌ TODAVÍA ESTÁ' else '✅ borrado' end as estado
    union all
    select 2, 'reprocesos.excepcion_operario_id',
           case when exists (select 1 from information_schema.columns
                             where table_name = 'reprocesos' and column_name = 'excepcion_operario_id')
                then '❌ TODAVÍA ESTÁ' else '✅ borrado' end
    union all
    select 3, 'check reprocesos_excepcion_completa',
           case when exists (select 1 from pg_constraint
                             where conrelid = 'reprocesos'::regclass
                               and conname = 'reprocesos_excepcion_completa')
                then '❌ TODAVÍA ESTÁ' else '✅ borrado' end
    union all
    select 4, 'índice reprocesos_excepcion_idx',
           case when to_regclass('public.reprocesos_excepcion_idx') is not null
                then '❌ TODAVÍA ESTÁ' else '✅ borrado' end
    union all
    select 5, 'tabla operarios_deposito',
           case when to_regclass('public.operarios_deposito') is not null
                then '❌ TODAVÍA ESTÁ' else '✅ borrada' end
    union all
    select 6, 'reprocesos.consumos_editados (SE QUEDA)',
           case when exists (select 1 from information_schema.columns
                             where table_name = 'reprocesos' and column_name = 'consumos_editados')
                then '✅ está, como tiene que estar' else '❌ FALTA: se borró de más' end
    union all
    -- Las TRES cifras, no una. Un solo número acá invita a compararlo con
    -- otro que se midió distinto: el verificador del 01/09 anotó 78 con un
    -- count(*) PELADO (anuladas incluidas), y "vigentes" solo son las que
    -- tienen anulado_el en NULL. Comparar esos dos números da una
    -- diferencia que no existe. Un conteo suelto, sin decir qué contó, es
    -- una alarma falsa esperando fecha.
    select 7, 'guías R: total / vigentes / anuladas (no las toca nadie)',
           (select count(*)::text || ' total · '
                || count(*) filter (where anulado_el is null)::text || ' vigentes · '
                || count(*) filter (where anulado_el is not null)::text || ' anuladas'
            from reprocesos)
) resultado
order by orden;
