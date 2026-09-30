select 'lectura_usuario' as QUE_MIGRACION,
       (select count(*) from pg_roles
         where rolname = 'lectura_claude' and rolcanlogin) as usuario,
       (select count(*) from pg_roles
         where rolname = 'lectura_claude' and rolbypassrls) as ve_todo_rls,
       (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = 'public' and c.relkind in ('r', 'v', 'm', 'p')) as tablas_POBLACION,
       (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = 'public' and c.relkind in ('r', 'v', 'm', 'p')
           and not has_table_privilege('lectura_claude', c.oid, 'SELECT')) as sin_lectura,
       (select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = 'public' and c.relkind in ('r', 'p')
           and (has_table_privilege('lectura_claude', c.oid, 'INSERT')
             or has_table_privilege('lectura_claude', c.oid, 'UPDATE')
             or has_table_privilege('lectura_claude', c.oid, 'DELETE')
             or has_table_privilege('lectura_claude', c.oid, 'TRUNCATE'))) as ESCRIBE,
       has_schema_privilege('lectura_claude', 'public', 'CREATE')::int as CREA_TABLAS,
       (select count(*) from pg_default_acl d join pg_namespace n on n.oid = d.defaclnamespace
         where n.nspname = 'public' and d.defaclobjtype = 'r'
           and d.defaclacl::text like '%lectura_claude=r/%') as tablas_futuras,
       (select max(procesada_el)::date from compras) as ultima_recepcion;

-- Se corre DESPUÉS de lectura_1 y por separado. Lo bueno es:
-- usuario 1 · ve_todo_rls 1 · sin_lectura 0 · ESCRIBE 0 · CREA_TABLAS 0 ·
-- tablas_futuras 1, con la población al lado.
-- ESCRIBE y CREA_TABLAS en mayúsculas porque son las que tienen que dar 0:
-- cualquier otro número es que el usuario puede escribir y no se usa.
