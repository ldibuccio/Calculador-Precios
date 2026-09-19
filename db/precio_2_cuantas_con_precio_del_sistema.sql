-- Cuantos ingresos directos tienen importe puesto, partidos por camino.
with directos as (
    select c.*,
           (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
             = (c.cargado_el at time zone 'America/Argentina/Buenos_Aires')::date as mismo_dia
    from compras c
    where c.retiro_origen is not distinct from 'ingreso_directo'
      and c.cargado_el > now() - interval '90 days'
)
select
    count(*)                                                    as INGRESOS_DIRECTOS_90d,
    count(*) filter (where importe is not null)                 as con_importe,
    count(*) filter (where importe is null)                     as en_blanco,
    count(*) filter (where importe is not null and mismo_dia)       as con_importe_DEPOSITO,
    count(*) filter (where importe is not null and not mismo_dia)   as con_importe_RETROACTIVO,
    (select count(*) from compras
      where cargado_el > now() - interval '90 days')            as TODAS_LAS_COMPRAS_90d,
    (select count(*) from compras
      where importe is null and estado = 'recepcionado')        as sin_precio_en_todo_el_sistema,
    (select max(cargado_el) from compras)                       as ultima_compra_cargada
from directos;

-- LO QUE ESTA CONSULTA **NO** PUEDE CONTESTAR, y hay que decirlo antes de
-- leer el numero: cuales de esos importes los tipeo una persona y cuales los
-- puso el sistema. `compras` no guarda quien escribio el importe ni cuando,
-- asi que un importe puesto por Gerencia en el formulario retroactivo y uno
-- cargado despues en "Compras sin precio" son la MISMA fila.
--
-- Lo que si separa es POR DONDE entro la mercaderia. Y eso alcanza para la
-- pregunta que importa: el ingreso directo de DEPOSITO pasa importe NULL
-- (medido corriendo la ruta), asi que `con_importe_DEPOSITO` mayor que cero
-- son ingresos a los que alguien les cargo el precio DESPUES — no el sistema.
--
-- El denominador va al lado a proposito: `con_importe 4` sin
-- `INGRESOS_DIRECTOS_90d` no se puede leer (corolario 45).
