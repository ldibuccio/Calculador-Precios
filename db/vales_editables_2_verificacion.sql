select 'vales_editables' as QUE_MIGRACION,
       (select count(*) from pg_constraint
         where conname = 'vales_origen_coherente'
           and pg_get_constraintdef(oid) not like '%(fecha IS NULL)%'
           and pg_get_constraintdef(oid) like '%(importe IS NULL) OR%') as coherente_nuevo_1,
       (select count(*) from vales_a_cobrar
         where origen = 'devolucion' and (importe is not null or fecha is not null))
         as devolucion_corregidos_0,
       (select count(*) from vales_a_cobrar v
          left join vacios_deposito_devoluciones d on d.id = v.devolucion_id
         where coalesce(v.importe, d.importe) is null) as sin_importe_0,
       (select coalesce(sum(coalesce(v.importe, d.importe)), 0) from vales_a_cobrar v
          left join vacios_deposito_devoluciones d on d.id = v.devolucion_id)
         as IMPORTE_VIGENTE_total,
       (select count(*) from vales_a_cobrar) as POBLACION_vales,
       (select max(creado_en)::date from vales_a_cobrar) as testigo_ultimo_vale;

-- Verificacion de vales_editables_1. SE CORRE APARTE del do: pegada a un do,
-- el editor se queda con la ultima y el bloque NO SE EJECUTA.
--
-- Esperado: coherente_nuevo 1 · devolucion_corregidos 0 · sin_importe 0.
-- IMPORTE_VIGENTE_total tiene que dar LO MISMO antes y despues de correr el
-- bloque (se puede correr esta consulta antes: las otras columnas dan 0).
-- Frutamax el 02/10: 13 vales, IMPORTE_VIGENTE_total 4313000.
-- Palmala no vota: solo confirma que el bloque no explota.
