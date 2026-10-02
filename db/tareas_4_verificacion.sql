select 'tareas' as QUE_MIGRACION,
       (select count(*) from pg_class
         where relname in ('tareas', 'tareas_ocurrencias', 'tareas_reaperturas')
           and relkind = 'r') as tablas_de_3,
       (select count(*) from pg_constraint
         where conname in ('tareas_campos_de_su_tipo', 'tareas_una_vez_no_se_pausa',
                           'tareas_ocurrencias_una_por_fecha',
                           'tareas_ocurrencias_hecha_coherente')) as constraints_de_4,
       (select count(*) from pg_indexes
         where indexname in ('tareas_ocurrencias_pendientes',
                             'tareas_reaperturas_por_ocurrencia')) as indices_de_2,
       (select count(*) from tareas) as tareas_en_0,
       (select count(*) from tareas_ocurrencias) as ocurrencias_en_0,
       (select count(*) from proveedores) as testigo_proveedores;

-- Verificacion de tareas_1 a _3. SE CORRE APARTE de los do: pegada a un do,
-- el editor se queda con la ultima y el bloque NO SE EJECUTA.
--
-- Esperado en las dos bases: tablas 3 · constraints 4 · indices 2 · tareas 0 ·
-- ocurrencias 0. El testigo solo dice de que base es la fila. Palmala no
-- vota: solo confirma que los bloques no explotan.
