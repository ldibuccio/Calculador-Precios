select 'vales_manual' as QUE_MIGRACION,
       (select count(*) from information_schema.columns
         where table_name = 'vales_a_cobrar'
           and column_name in ('cargado_desde', 'nota')) as columnas_de_2,
       (select count(*) from pg_constraint
         where conname = 'vales_a_cobrar_origen_check'
           and pg_get_constraintdef(oid) like '%carga_manual%') as origen_nuevo_1,
       (select count(*) from pg_constraint
         where conname = 'vales_origen_coherente'
           and pg_get_constraintdef(oid) like '%carga_manual%') as coherente_nuevo_1,
       (select count(*) from pg_constraint
         where conname in ('vales_carga_manual_con_sector', 'vales_nota_no_vacia',
                           'vales_correcciones_distinto')) as checks_de_3,
       (select count(*) from pg_class
         where relname = 'vales_correcciones' and relkind = 'r') as tabla_1,
       (select count(*) from pg_trigger
         where tgname in ('vale_que_salio_no_se_corrige', 'vale_que_salio_cambia_de_proveedor')
           and not tgisinternal) as triggers_de_2,
       (select count(*) from pg_trigger
         where tgname = 'vale_que_salio_cambia_de_proveedor'
           and tgdeferrable and tginitdeferred) as diferido_1,
       (select count(*) from pg_proc
         where prosrc like '%juntando_proveedores%') as marca_vieja_0,
       (select count(*) from vales_a_cobrar where origen = 'carga_manual') as manuales_en_0,
       (select count(*) from vales_a_cobrar) as POBLACION_vales,
       (select count(*) from vales_a_cobrar where origen = 'anterior_al_sistema')
         as POBLACION_anteriores,
       (select max(creado_en)::date from vales_a_cobrar) as testigo_ultimo_vale;

-- Verificacion de vales_manual_1 a _3. SE CORRE APARTE de los do: pegada a
-- un do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
--
-- Esperado en las dos bases: columnas 2 · origen 1 · coherente 1 · checks 3 ·
-- tabla 1 · triggers 2 · diferido 1 · marca_vieja 0 · manuales 0. La poblacion es la que haya hoy: ninguna
-- fila cambia. Palmala no vota: solo confirma que los bloques no explotan.
