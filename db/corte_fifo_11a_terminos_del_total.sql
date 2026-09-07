-- SUELTOS = (este total) - (el de corte_fifo_11b). Parte 1 de 2.
-- La cuenta 1 NO tiene piso de fecha: la rebasea el compensatorio, asi que
-- cuenta TODA la historia y el dia del corte entero.
-- Cambiar 'mango' por el articulo que se quiera mirar.
with c0 as (select fecha f0 from corte_modelo where id = 1),
a0 as (select id from articulos where nombre ilike '%mango%'),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
t(orden, concepto, bultos) as (
 select 1, 'compensatorio', sum(m.cantidad)
 from movimientos_stock m join a0 on a0.id=m.articulo_id
 where m.anulado_el is null and m.tipo = 'cierre_modelo_viejo'
 union all select 2, 'foto cajones', sum(m.cantidad)
 from movimientos_stock m join a0 on a0.id=m.articulo_id, c0
 where m.anulado_el is null and m.tipo='stock_inicial' and m.fecha_operacion=c0.f0
 union all select 3, 'otros mov', sum(m.cantidad)
 from movimientos_stock m join a0 on a0.id=m.articulo_id where m.anulado_el is null
 and m.tipo not in ('cierre_modelo_viejo','stock_inicial')
 union all select 4, 'compras', sum(coalesce(c.cantidad_cajones_real,0))
 from compras c join a0 on a0.id=c.articulo_id where c.estado = 'recepcionado'
 union all select 5, 'primera TODA (+)', sum(rp.bultos_primera)
 from reprocesos rp join a0 on a0.id=rp.articulo_id where rp.anulado_el is null
 union all select 6, 'tomado TODO (-)', -sum(rp.bultos_tomados)
 from reprocesos rp join a0 on a0.id=rp.articulo_id where rp.anulado_el is null
 union all select 7, 'armado TODO (-)', -sum(coalesce(r.cantidad_armada,
 r.cantidad)) from pedidos_renglones r join vig v on v.id=r.pedido_id
 join a0 on a0.id=r.articulo_id where r.armado_el is not null and r.anulado_el is null
)
select concepto, coalesce(bultos,0) as bultos,
 sum(coalesce(bultos,0)) over () as TOTAL_del_articulo
from t order by orden;
