select 'backups' as QUE_MIGRACION,
       (select count(*) from pg_class where oid = to_regclass('backups_corridas')) as tabla_1,
       (select count(*) from pg_constraint where conname = 'backups_corridas_parte'
           and pg_get_constraintdef(oid) like '%fotos%') as check_1,
       (select count(*) from pg_roles where rolname = 'backup_estado' and rolcanlogin) as rol_1,
       (select count(*) from pg_roles r where r.rolname = 'backup_estado'
           and has_table_privilege(r.oid, 'backups_corridas', 'INSERT')) as inserta_1,
       (select count(*) from pg_roles r where r.rolname = 'backup_estado'
           and has_table_privilege(r.oid, 'backups_corridas', 'SELECT,UPDATE,DELETE')) as lee_o_cambia_0,
       (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
         cross join pg_roles r
         where r.rolname = 'backup_estado' and c.relkind in ('r', 'p', 'v', 'm')
           and n.nspname not in ('pg_catalog', 'information_schema')
           and c.oid <> to_regclass('backups_corridas')
           and (has_table_privilege(r.oid, c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE')
                or (n.nspname = 'public' and has_table_privilege(r.oid, c.oid, 'SELECT')))) as otras_tablas_0,
       (select count(*) from pg_class where oid = to_regclass('backups_corridas') and relrowsecurity) as rls_1,
       (select count(*) from pg_policies where tablename = 'backups_corridas'
           and policyname = 'backup_estado_inserta' and cmd = 'INSERT'
           and roles = '{backup_estado}') as politica_1,
       (select count(*) from pg_policies where tablename = 'backups_corridas') as politicas_total_1,
       (select count(*) from backups_corridas) as POBLACION_corridas,
       (select count(*) from proveedores) as testigo_proveedores;

-- Verificacion de backups_1 y backups_2. SE CORRE APARTE de los do: pegada a
-- un do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
--
-- Esperado en las dos bases: tabla 1 · check 1 · rol 1 · inserta 1 ·
-- lee_o_cambia 0 · otras_tablas 0 · rls 1 · politica 1 · politicas_total 1. La poblacion arranca en 0 y crece con
-- cada corrida del workflow. El testigo solo identifica la base.
