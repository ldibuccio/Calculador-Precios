-- Verificacion de vales_1 a vales_4. SE CORRE APARTE de los do: pegada a un
-- do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
-- Los CHECK se cuentan por NOMBRE y por lo que DICEN: un `importe > 0` sin
-- coalesce da NULL con el importe vacio, y un CHECK en NULL deja pasar.
select 'vales_a_cobrar' as QUE_MIGRACION,
       (select count(*) from pg_class
         where relname in ('vales_a_cobrar', 'vales_a_cobrar_salidas',
                           'vales_a_cobrar_limites') and relkind = 'r') as tablas_de_3,
       (select count(*) from pg_class where relname = 'vales_papel_listado' and relkind = 'r')
         + (select count(*) from pg_class where relname = 'vales_papel_revision' and relkind = 'v')
         as listado_y_revision_de_2,
       (select count(*) from pg_constraint
         where conname = 'vales_origen_coherente'
           and pg_get_constraintdef(oid) like '%COALESCE((importe > %') as origen_null_safe_de_1,
       (select count(*) from pg_constraint
         where conname in ('vales_salida_cobrado', 'vales_salida_cruzado',
                           'vales_salida_anulado',
                           'vales_salida_campos_de_su_tipo')) as salidas_de_4,
       (select count(*) from pg_constraint
         where conname = 'vales_salida_anulado'
           and pg_get_constraintdef(oid) like '%gerencia%') as anular_gerencia_de_1,
       (select count(*) from pg_constraint
         where conname = 'vales_salida_cobrado'
           and pg_get_constraintdef(oid) like '%COALESCE((importe_cobrado > %') as cobro_null_safe_de_1,
       (select monto || ' / ' || dias from vales_a_cobrar_limites) as limites,
       (select count(*) from vales_a_cobrar) as vales_en_0,
       (select count(*) from vacios_deposito_devoluciones) as POBLACION_devoluciones,
       (select max(procesada_el)::date from compras
         where estado = 'recepcionado') as testigo_ultima_recepcion;
