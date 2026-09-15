-- kiwi_1 · ¿los pares "unidad de compra ≠ unidad de venta" son un ERROR DE
-- CARGA o UNA COMPRA QUE SIRVE A DOS CLIENTES EN DOS UNIDADES?
--
-- Hasta hoy los dos casos se veían IGUALES: la alerta cuenta pares que
-- difieren y su link manda a alinear. Esto los parte por ARTÍCULO:
--
--   multiunidad -> sus fichas NO se ponen de acuerdo ENTRE SÍ (un cliente
--                  por kilo y otro por unidad). NINGUNA alineación lo
--                  arregla: alinear una ficha la haría mentir sobre lo que
--                  ese cliente compra.
--   alineable   -> todas sus fichas dicen lo mismo, distinto de la unidad de
--                  compra. Ahí sí hay UNA cosa mal cargada.
--
-- UNA fila siempre (conteos, no lista), con la población al lado para leer
-- el cociente y los nombres pegados porque son pocos y se decide uno por
-- uno. Correr en LAS DOS bases y pegar LAS DOS filas con la base adelante.
with por_articulo as (
    select a.id,
           a.nombre,
           a.unidad_compra,
           count(*)                                                  as fichas,
           count(distinct f.unidad_venta)                            as unidades_venta,
           count(*) filter (where f.unidad_venta <> a.unidad_compra) as difieren
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
    string_agg(nombre || ' (compra ' || unidad_compra || ')', ', ')
        filter (where caso = 'multiunidad')      as cuales_multiunidad,
    string_agg(nombre || ' (compra ' || unidad_compra || ')', ', ')
        filter (where caso = 'alineable')        as cuales_alineables,
    -- Testigo: un cero sobre una base parada se lee igual que uno bueno.
    (select max(fecha_operacion) from compras)   as ultima_compra
from clasificado;
