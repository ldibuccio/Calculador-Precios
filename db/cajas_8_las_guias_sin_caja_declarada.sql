with base as (
  select min(fecha_operacion) as f
    from movimientos_envase
   where origen = 'conteo_inicial' and anulado_el is null
),
guias as (
  select r.id,
         case
           when r.creado_en < date '2026-09-16'   then 'vieja_sin_la_columna'
           when r.ficha_id is null                then 'sin_ficha'
           when f.envase_variable is true         then 'ficha_variable'
           when f.envase_id is not null           then 'DERIVABLE_es_un_hueco'
           else 'envase_perdido'
         end as motivo
    from reprocesos r
    left join fichas_logistica f on f.id = r.ficha_id
   cross join base b
   where r.anulado_el is null
     and r.tipo <> 'inicial'
     and b.f is not null
     and r.fecha_operacion >= b.f
     and r.lleva_caja_nuestra is null
)
select (select count(*) from guias) as sin_declarar,
       count(*) filter (where motivo = 'vieja_sin_la_columna') as vieja_sin_la_columna,
       count(*) filter (where motivo = 'sin_ficha') as sin_ficha,
       count(*) filter (where motivo = 'ficha_variable') as ficha_variable,
       count(*) filter (where motivo = 'DERIVABLE_es_un_hueco') as DERIVABLE_es_un_hueco,
       count(*) filter (where motivo = 'envase_perdido') as envase_perdido,
       (select count(*) from reprocesos r2 cross join base b2
         where r2.anulado_el is null and r2.tipo <> 'inicial'
           and b2.f is not null and r2.fecha_operacion >= b2.f) as POBLACION_de_la_ventana,
       (select f from base) as desde_el_conteo,
       (select max(fecha_operacion) from reprocesos
         where anulado_el is null) as TESTIGO_ultima_guia
  from guias;

-- ---------------------------------------------------------------------------
-- POR QUE una guia R no dice en que caja se armo. Motivos EXCLUYENTES, suman
-- `sin_declarar`; si no suman, hay un caso no previsto.
--
--   vieja_sin_la_columna  anterior al 16/09 (envases_3 no backfillea)
--   sin_ficha             "sin asignar" es opcion legitima de Reproceso
--   ficha_variable        el envase lo decide el cajon de ESA compra
--   envase_perdido        ficha sin envase; deberia decir FALSE, no NULL
--   DERIVABLE_es_un_hueco ficha con envase FIJO y columna en NULL. EL UNICO
--                         que importa: la caja salio y el stock no la resta.
--
-- Probada contra db/esquema_completo.sql con los cinco plantados de a uno mas
-- una bien declarada que NO tiene que salir: 5 de 6, un 1 en cada columna.
