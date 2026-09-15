-- kiwi_1 · los pares "unidad de compra <> unidad de venta": ¿ERROR DE CARGA
-- o UNA COMPRA QUE SIRVE A DOS CLIENTES EN DOS UNIDADES?
--
-- La alerta de hoy no los distingue. Esto parte por ARTÍCULO:
--   multiunidad -> sus fichas NO se ponen de acuerdo ENTRE SÍ. Ninguna
--                  alineación lo arregla: alinear una haría que la ficha
--                  mienta sobre lo que ese cliente compra.
--   alineable   -> todas dicen lo mismo, distinto de la unidad de compra.
--                  Ahí sí hay UNA cosa mal cargada.
--
-- difieren_con_envase_variable mide la OTRA rotura, la del ENVASE. Ver
-- CLAUDE.md. UNA fila siempre. Correr en LAS DOS bases.
with por_articulo as (
    select a.id,
           a.nombre,
           a.unidad_compra,
           count(*)                                                  as fichas,
           count(distinct f.unidad_venta)                            as unidades_venta,
           count(*) filter (where f.unidad_venta <> a.unidad_compra) as difieren,
           count(*) filter (where f.unidad_venta <> a.unidad_compra
                              and f.envase_variable)                  as difieren_env_var
    from articulos a
    join fichas_logistica f on f.articulo_id = a.id
    where a.unidad_compra is not null
    group by a.id, a.nombre, a.unidad_compra
),
clasificado as (
    select *,
           case when unidades_venta > 1 then 'multiunidad'
                when difieren > 0      then 'alineable'
                else                        'coincide'
           end as caso
    from por_articulo
)
select
    count(*)                                     as arts_con_ficha,
    count(*) filter (where caso = 'multiunidad') as arts_multiunidad,
    count(*) filter (where caso = 'alineable')   as arts_alineables,
    coalesce(sum(difieren), 0)                   as pares_que_difieren,
    coalesce(sum(fichas), 0)                     as pares_totales,
    coalesce(sum(difieren_env_var), 0)           as difieren_con_envase_variable,
    string_agg(nombre || ' (compra ' || unidad_compra || ')', ', ')
        filter (where caso = 'multiunidad')      as cuales_multiunidad,
    string_agg(nombre || ' (compra ' || unidad_compra || ')', ', ')
        filter (where caso = 'alineable')        as cuales_alineables,
    -- Testigo: un cero sobre una base parada se lee igual que uno bueno.
    (select max(fecha_operacion) from compras)   as ultima_compra
from clasificado;
