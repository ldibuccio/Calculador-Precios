-- Verificacion de tareas_8. SE CORRE APARTE del do.
select 'tareas_8' as QUE_MIGRACION,
       (select count(*) from information_schema.columns where table_name = 'tareas'
         and column_name in ('anual_dia', 'anual_mes', 'eliminada_el', 'eliminada_por'))
         as columnas_de_4,
       (select count(*) from pg_constraint where conname = 'tareas_tipo_check'
         and pg_get_constraintdef(oid) like '%despues_de_hecha%') as tipos_nuevos_1,
       (select count(*) from pg_constraint where conname = 'tareas_campos_de_su_tipo'
         and pg_get_constraintdef(oid) like '%anual_mes%') as campos_1,
       (select count(*) from pg_constraint where conname = 'tareas_una_vez_no_se_pausa'
         and pg_get_constraintdef(oid) like '%baja%') as una_vez_se_elimina_1,
       (select count(*) from pg_constraint where conname = 'tareas_eliminada_coherente') as eliminada_1,
       (select count(*) from pg_constraint where conname = 'tareas_ocurrencias_estado_check'
         and pg_get_constraintdef(oid) like '%eliminada%') as ocurrencia_eliminada_1,
       (select count(*) from tareas) as POBLACION_tareas,
       (select count(*) from tareas_ocurrencias) as ocurrencias,
       (select max(creado_en)::date from tareas) as testigo_ultima_tarea;
