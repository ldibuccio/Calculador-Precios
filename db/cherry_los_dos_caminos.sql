-- Los dos caminos del cherry: qué entró por cada uno y qué se armó, desde el
-- corte. El corte "descartable" (cajón <= ficha) copia _envases_por_unidad_
-- ponderado (app/costeo.py); los COALESCE _real y el filtro de estado copian
-- listar_compras_para_costeo (app/db.py).
with corte as (select fecha from corte_modelo where id = 1),
fc as (
    select f.id, f.contenido_caja, f.envase_variable, f.nombre_cliente,
           f.articulo_id, a.nombre as articulo, cl.nombre as cliente,
           coalesce(e.nombre, 'ENVASE PERDIDO') as envase
    from fichas_logistica f
    join articulos a on a.id = f.articulo_id
    join clientes cl on cl.id = f.cliente_id
    left join envases e on e.id = f.envase_id
    where a.nombre ilike '%cherry%'
),
ent as (
    select fc.id as ficha_id,
           sum(case when coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon)
                         <= fc.contenido_caja
                    then coalesce(c.cantidad_cajones_real, c.cantidad_cajones)
                    else 0 end) as cajones_descartable,
           sum(case when coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon)
                         > fc.contenido_caja
                    then coalesce(c.cantidad_cajones_real, c.cantidad_cajones)
                    else 0 end) as cajones_con_carton
    from fc
    join compras c on c.articulo_id = fc.articulo_id
    where c.fecha_operacion >= (select fecha from corte)
      and c.estado is distinct from 'rechazado'
      and c.estado is distinct from 'no_ingresado'
      and c.importe is not null
    group by fc.id
),
arm as (
    select rp.ficha_id, sum(rp.bultos_primera) as cajas_armadas
    from reprocesos rp
    where rp.ficha_id is not null and rp.anulado_el is null
      and rp.fecha_operacion >= (select fecha from corte)
    group by rp.ficha_id
)
select fc.articulo, fc.cliente, fc.id as ficha, fc.nombre_cliente,
       fc.contenido_caja, fc.envase_variable, fc.envase,
       coalesce(ent.cajones_descartable, 0) as cajones_descartable,
       coalesce(ent.cajones_con_carton, 0)  as cajones_con_carton,
       coalesce(arm.cajas_armadas, 0)       as cajas_armadas
from fc
left join ent on ent.ficha_id = fc.id
left join arm on arm.ficha_id = fc.id
order by fc.articulo, fc.cliente, fc.id;
