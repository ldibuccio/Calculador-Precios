-- VERIFICADOR de db/agregar_freno_y_desglose_reproceso.sql.
-- UNA sola consulta que devuelve filas: el editor de Supabase muestra solo el
-- resultado de la última, y no muestra los NOTICE. Solo lectura.
-- Se espera OK en las 9.
select n, verificacion, resultado from (
    select 1 as n, '01 - operarios_deposito existe y arranca vacía' as verificacion,
           case when not exists (select 1 from pg_class where relname = 'operarios_deposito')
                then 'FALLA: la tabla no está'
                when (select count(*) from operarios_deposito) = 0 then 'OK — vacía, se carga desde Administración'
                else 'OK — ya tiene ' || (select count(*) from operarios_deposito) || ' operarios' end as resultado

    union all
    select 2, '02 - el nombre del operario es único NORMALIZADO (no entra "juan" y "Juan")',
           case when count(*) = 1 then 'OK' else 'FALLA: falta el índice único sobre lower(btrim(nombre))' end
    from pg_indexes
    where tablename = 'operarios_deposito' and indexname = 'operarios_deposito_nombre_unico'
      and indexdef like '%lower(btrim(nombre))%'

    union all
    select 3, '03 - consumos_editados: boolean, NOT NULL, default false',
           case when count(*) = 1 then 'OK' else 'FALLA: no está o no es como se esperaba' end
    from information_schema.columns
    where table_name = 'reprocesos' and column_name = 'consumos_editados'
      and data_type = 'boolean' and is_nullable = 'NO' and column_default = 'false'

    union all
    select 4, '04 - excepcion_motivo: text y NULLABLE (NULL = no hubo excepción)',
           case when count(*) = 1 then 'OK' else 'FALLA' end
    from information_schema.columns
    where table_name = 'reprocesos' and column_name = 'excepcion_motivo'
      and data_type = 'text' and is_nullable = 'YES'

    union all
    select 5, '05 - excepcion_operario_id apunta a operarios_deposito',
           case when count(*) = 1 then 'OK' else 'FALLA: no está la FK' end
    from pg_constraint c
    where c.conrelid = 'reprocesos'::regclass and c.contype = 'f'
      and c.confrelid = 'operarios_deposito'::regclass

    union all
    select 6, '06 - el check exige motivo Y operario juntos, y el motivo no vacío',
           case when count(*) = 1 then 'OK' else 'FALLA: el check no está' end
    from pg_constraint
    where conrelid = 'reprocesos'::regclass and conname = 'reprocesos_excepcion_completa'

    union all
    select 7, '07 - el índice parcial para contar por operario y por día',
           case when count(*) = 1 then 'OK' else 'FALLA: el índice no está' end
    from pg_indexes
    where tablename = 'reprocesos' and indexname = 'reprocesos_excepcion_idx'
      and indexdef like '%WHERE (excepcion_motivo IS NOT NULL)%'

    union all
    select 8, '08 - las guías que ya existían quedaron sin excepción y sin editar',
           case when count(*) = 0 then 'OK — ' || (select count(*) from reprocesos) || ' guías intactas'
                else 'FALLA: ' || count(*) || ' guías tocadas' end
    from reprocesos
    where consumos_editados or excepcion_motivo is not null or excepcion_operario_id is not null

    union all
    select 9, '09 - las tres columnas y la tabla tienen su comentario',
           case when count(*) = 3 and obj_description('operarios_deposito'::regclass) is not null
                then 'OK' else 'FALLA: falta alguno' end
    from information_schema.columns c
    where c.table_name = 'reprocesos'
      and c.column_name in ('consumos_editados', 'excepcion_motivo', 'excepcion_operario_id')
      and col_description('reprocesos'::regclass, c.ordinal_position) is not null
) todo order by n;
