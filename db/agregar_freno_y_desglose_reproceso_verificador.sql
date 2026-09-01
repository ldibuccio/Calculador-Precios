-- VERIFICADOR de db/agregar_freno_y_desglose_reproceso.sql.
-- UNA sola consulta que devuelve filas: el editor de Supabase muestra solo el
-- resultado de la última, y no muestra los NOTICE.
-- Se espera OK en las 7.
select n, verificacion, resultado from (
    select 1 as n, '01 - consumos_editados existe, boolean y NOT NULL con default false' as verificacion,
           case when count(*) = 1 then 'OK'
                else 'FALLA: no está o no es como se esperaba' end as resultado
    from information_schema.columns
    where table_name = 'reprocesos' and column_name = 'consumos_editados'
      and data_type = 'boolean' and is_nullable = 'NO' and column_default = 'false'

    union all
    select 2, '02 - excepcion_motivo existe y es NULLABLE (NULL = no hubo excepción)',
           case when count(*) = 1 then 'OK' else 'FALLA' end
    from information_schema.columns
    where table_name = 'reprocesos' and column_name = 'excepcion_motivo'
      and data_type = 'text' and is_nullable = 'YES'

    union all
    select 3, '03 - excepcion_operario existe y es NULLABLE',
           case when count(*) = 1 then 'OK' else 'FALLA' end
    from information_schema.columns
    where table_name = 'reprocesos' and column_name = 'excepcion_operario'
      and data_type = 'text' and is_nullable = 'YES'

    union all
    select 4, '04 - el check exige motivo Y operario juntos, y ninguno vacío',
           case when count(*) = 1 then 'OK' else 'FALLA: el check no está' end
    from pg_constraint
    where conrelid = 'reprocesos'::regclass and conname = 'reprocesos_excepcion_completa'

    union all
    select 5, '05 - el índice parcial para contar por operario y por día',
           case when count(*) = 1 then 'OK' else 'FALLA: el índice no está' end
    from pg_indexes
    where tablename = 'reprocesos' and indexname = 'reprocesos_excepcion_idx'
      and indexdef like '%WHERE (excepcion_motivo IS NOT NULL)%'

    union all
    select 6, '06 - las guías que ya existían quedaron sin excepción y sin editar',
           case when count(*) = 0 then 'OK — ' || (select count(*) from reprocesos) || ' guías intactas'
                else 'FALLA: ' || count(*) || ' guías con excepción o editadas' end
    from reprocesos
    where consumos_editados or excepcion_motivo is not null or excepcion_operario is not null

    union all
    select 7, '07 - las tres columnas tienen su comentario',
           case when count(*) = 3 then 'OK' else 'FALLA: hay ' || count(*) || ' de 3' end
    from information_schema.columns c
    where c.table_name = 'reprocesos'
      and c.column_name in ('consumos_editados', 'excepcion_motivo', 'excepcion_operario')
      and col_description('reprocesos'::regclass, c.ordinal_position) is not null
) todo order by n;
