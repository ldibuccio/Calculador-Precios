select 'tareas_por_sector' as QUE_MIGRACION,
       (select count(*) from information_schema.columns
         where table_name = 'tareas' and column_name in ('creada_por', 'dias_mes'))
         as columnas_de_2,
       (select count(*) from information_schema.columns
         where table_name = 'tareas' and column_name = 'dia_mes') as dia_mes_viejo,
       (select count(*) from information_schema.columns
         where table_name = 'tareas' and column_name = 'creada_por'
           and column_default is not null) as con_default,
       (select count(*) from pg_constraint where conname = 'tareas_creada_por') as check_creada_1,
       (select count(*) from pg_constraint where conname = 'tareas_campos_de_su_tipo'
           and pg_get_constraintdef(oid) like '%dias_mes%') as check_dias_1,
       (select count(*) from tareas where creada_por <> 'gerencia') as de_un_sector_0,
       (select count(*) from tareas where tipo = 'mensual' and dias_mes is null)
         as mensual_sin_dias_0,
       (select count(*) from tareas) as POBLACION_tareas,
       (select count(*) from proveedores) as testigo_proveedores;

-- Verificacion de tareas_5 y tareas_6. SE CORRE APARTE de los do: pegada a
-- un do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
--
-- Despues de tareas_5 (antes del deploy): columnas 2 · dia_mes_viejo 1 ·
-- con_default 1 · check_creada 1 · check_dias 1 · de_un_sector 0 ·
-- mensual_sin_dias 0.
-- Despues de tareas_6 (despues del deploy): columnas 2 · dia_mes_viejo 0 ·
-- con_default 0 · check_creada 1 · check_dias 1 · de_un_sector 0 (o las que
-- ya hayan cargado los sectores) · mensual_sin_dias 0.
-- La poblacion es la que haya: ninguna tarea cambia. Palmala no vota.
