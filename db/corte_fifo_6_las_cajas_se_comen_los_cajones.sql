-- ¿El armado se esta comiendo los CAJONES? Con el piso, un armado solo
-- puede consumir cajas declaradas al corte (guias R 'inicial') o armadas
-- despues. Si el armado supera a las dos, el FIFO —que tiene UNA sola
-- pila— sigue de largo y se come los cajones, dejando sin materia prima al
-- reproceso del dia siguiente. Es la mezcla de unidades mordiendo al piso.
with c0 as (select fecha from corte_modelo where id = 1),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
cajas as (
 select articulo_id,
  sum(bultos_primera) filter (where tipo = 'inicial') as al_corte,
  sum(bultos_primera) filter (where tipo = 'normal') as armadas_despues
 from reprocesos where anulado_el is null
   and fecha_operacion >= (select fecha from c0)
 group by articulo_id
),
arm as (
 select r.articulo_id, sum(coalesce(r.cantidad_armada, r.cantidad)) as entregado
 from pedidos_renglones r join vig v on v.id = r.pedido_id
 where r.armado_el is not null and r.anulado_el is null
   and (r.armado_el at time zone
   'America/Argentina/Buenos_Aires')::date >= (select fecha from c0)
 group by r.articulo_id
),
caj as (
 select c.articulo_id, sum(coalesce(c.cantidad_cajones_real, 0)) as cajones
 from compras c where c.estado = 'recepcionado'
   and (c.procesada_el at time zone
   'America/Argentina/Buenos_Aires')::date >= (select fecha from c0)
 group by c.articulo_id
)
select a.nombre as articulo,
 coalesce(k.al_corte, 0) as cajas_al_corte,
 coalesce(k.armadas_despues, 0) as cajas_despues,
 coalesce(m.entregado, 0) as entregado,
 coalesce(m.entregado, 0) - coalesce(k.al_corte, 0)
   - coalesce(k.armadas_despues, 0) as come_cajones,
 coalesce(j.cajones, 0) as cajones_compra
from cajas k
full join arm m on m.articulo_id = k.articulo_id
full join caj j on j.articulo_id = coalesce(k.articulo_id, m.articulo_id)
join articulos a on a.id = coalesce(k.articulo_id, m.articulo_id, j.articulo_id)
order by 5 desc;
