select 'cobranza_segunda' as QUE_MIGRACION,
       (select count(*) from pg_class
         where relname in ('segunda_cobros', 'segunda_cobros_historial')
           and relkind = 'r') as tablas_de_2,
       (select count(*) from pg_constraint
         where conname in ('segunda_cobros_importe_no_negativo',
                           'segunda_historial_campos_de_su_tipo')) as checks_de_2,
       (select count(*) from pg_trigger
         where tgname in ('segunda_cobro_solo_lote_vigente',
                          'segunda_cobrada_no_se_anula')
           and not tgisinternal) as triggers_de_2,
       (select count(*) from segunda_cobros) as cobros_en_0,
       (select count(*) from remitos_segunda
         where destino = 'puesto' and anulado_el is null) as POBLACION_lotes,
       (select coalesce(sum(bultos), 0) from remitos_segunda
         where destino = 'puesto' and anulado_el is null) as POBLACION_bultos,
       (select min(fecha_operacion) from remitos_segunda
         where destino = 'puesto' and anulado_el is null) as primer_lote,
       (select max(fecha_operacion) from remitos_segunda
         where destino = 'puesto' and anulado_el is null) as testigo_ultimo_lote;

-- Verificacion de cobranza_segunda_1 a _3. SE CORRE APARTE de los do: pegada
-- a un do, el editor se queda con la ultima y el bloque NO SE EJECUTA.
--
-- Esperado en las dos bases: tablas 2 · checks 2 · triggers 2 · cobros 0.
-- En FRUTAMAX la poblacion es la de hoy: 60 lotes y 608 bultos, del 29/08 al
-- 01/10 (o mas, si se remitio segunda despues). Todos pendientes: cobros 0.
-- Palmala no vota: solo confirma que los bloques no explotan.
