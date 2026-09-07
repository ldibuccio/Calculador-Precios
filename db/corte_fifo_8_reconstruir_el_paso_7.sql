-- Cuantas cajas habia en el piso al corte, POR FICHA (crear_reproceso_inicial
-- exige ficha). No se estima: se deduce.
--   faltaban_al_corte = entregadas DESPUES del corte - armadas DESPUES
-- Una caja entregada que nadie armo despues del corte, ya estaba al corte.
-- EL DIA DEL CORTE NO CUENTA en ninguno de los dos: la foto se toma a la
-- tarde y ya viene neta del trabajo de ese dia. Contarlo lo duplica.
-- Es un PISO exacto: faltan las que siguen en el piso hoy sin entregar, y
-- esas hay que contarlas (cajas_al_corte = este numero + lo contado hoy).
-- costo_ref es el promedio ponderado por caja de las guias R de esa ficha
-- desde el corte: la misma mercaderia, los mismos dias.
with c0 as (select fecha from corte_modelo where id = 1),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
ent as (
 select r.articulo_id aid, r.ficha_id fid,
  sum(coalesce(r.cantidad_armada, r.cantidad)) as entregadas
 from pedidos_renglones r join vig v on v.id = r.pedido_id
 where r.armado_el is not null and r.anulado_el is null
   and (r.armado_el at time zone
   'America/Argentina/Buenos_Aires')::date > (select fecha from c0)
 group by 1, 2
),
arm as (
 select articulo_id aid, ficha_id fid,
  sum(bultos_primera) filter (where tipo = 'normal') as armadas,
  sum(bultos_primera) filter (where tipo = 'inicial') as ya_declaradas,
  sum(costo_total) filter (where tipo = 'normal' and costo_total is not null) as pl,
  sum(bultos_primera) filter (where tipo = 'normal' and costo_total is not null) as bl
 from reprocesos where anulado_el is null
   and (tipo = 'inicial' or fecha_operacion > (select fecha from c0))
   and fecha_operacion >= (select fecha from c0)
 group by 1, 2
)
select a.nombre as articulo,
 coalesce(f.codigo_cliente, 'ficha ' || f.id::text) as ficha,
 f.id as ficha_id,
 coalesce(e.entregadas, 0) as entregadas,
 coalesce(m.armadas, 0) as armadas,
 coalesce(m.ya_declaradas, 0) as ya_declaradas,
 coalesce(e.entregadas, 0) - coalesce(m.armadas, 0)
   - coalesce(m.ya_declaradas, 0) as faltaban_al_corte,
 round(m.pl / nullif(m.bl, 0), 2) as costo_ref
from ent e
full join arm m on m.aid = e.aid and m.fid is not distinct from e.fid
join articulos a on a.id = coalesce(e.aid, m.aid)
left join fichas_logistica f on f.id = coalesce(e.fid, m.fid)
order by 7 desc, 1;
