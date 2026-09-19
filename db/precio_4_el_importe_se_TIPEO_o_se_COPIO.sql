with ventana as (select now() - interval '90 days' as desde),
directos as (
    select c.id, c.articulo_id, c.importe, c.cargado_el
    from compras c, ventana v
    where c.retiro_origen is not distinct from 'ingreso_directo'
      and c.importe is not null and c.cargado_el > v.desde
      and (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
        = (c.cargado_el  at time zone 'America/Argentina/Buenos_Aires')::date
),
normales as (
    select c.id, c.articulo_id, c.importe, c.cargado_el
    from compras c, ventana v
    where c.retiro_origen is distinct from 'ingreso_directo'
      and c.importe is not null and c.cargado_el > v.desde
),
anterior as (
    select t.origen, t.id, t.importe,
           (select p.importe from compras p
             where p.articulo_id = t.articulo_id and p.importe is not null
               and p.id <> t.id and p.cargado_el < t.cargado_el
             order by p.cargado_el desc limit 1) as regia
    from (select 'directo' as origen, * from directos
          union all select 'normal', * from normales) t
)
select
    'precio_4_tipeado_o_copiado'                                as QUE_CONSULTA,
    count(*) filter (where origen = 'directo')                  as DIRECTOS,
    count(*) filter (where origen = 'directo' and regia is null)        as directos_sin_previo,
    count(*) filter (where origen = 'directo' and importe = regia)      as directos_IGUAL_al_previo,
    count(*) filter (where origen = 'directo' and importe <> regia)     as directos_DISTINTO,
    count(*) filter (where origen = 'normal')                   as NORMALES_control,
    count(*) filter (where origen = 'normal' and regia is null)         as normales_sin_previo,
    count(*) filter (where origen = 'normal' and importe = regia)       as normales_IGUAL_al_previo,
    count(*) filter (where origen = 'normal' and importe <> regia)      as normales_DISTINTO,
    (select max(cargado_el) from compras)                       as ultima_compra_cargada
from anterior;

-- CONDENA EN UNA SOLA DIRECCION.
--   directos_DISTINTO > 0 CIERRA el caso: un importe distinto del que regia
--   no se pudo copiar de ningun lado — lo tipeo alguien.
--   Al reves NO absuelve: "igual al previo" lo produce una copia Y una
--   persona tipeando el precio de siempre. Por eso el CONTROL: los normales
--   nacen con el precio tipeado en el alta, asi que su tasa de iguales es la
--   de un precio estable TIPEADO. Parecidas, los directos tampoco se copian.
