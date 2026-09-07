-- Parte 2 de 2. La cuenta 2 SI tiene piso, y ASIMETRICO: entra la foto del
-- corte y todo lo estrictamente posterior. Lo que la 1 cuenta y esta no
-- —el dia del corte— cae entero en los sueltos.
-- Cambiar 'mango' por el articulo que se quiera mirar.
with c0 as (select fecha f0 from corte_modelo where id = 1),
a0 as (select id from articulos where nombre ilike '%mango%'),
vig as (select distinct on (cliente_id, fecha_operacion) id from pedidos
 where anulado_el is null order by cliente_id, fecha_operacion, creado_en desc),
t(orden, concepto, bultos) as (
 select 1, 'foto cajas', sum(rp.bultos_primera)
 from reprocesos rp join a0 on a0.id=rp.articulo_id, c0
 where rp.anulado_el is null and rp.tipo='inicial' and rp.fecha_operacion=c0.f0
 union all select 2, 'primera POST (+)', sum(rp.bultos_primera)
 from reprocesos rp join a0 on a0.id=rp.articulo_id, c0
 where rp.anulado_el is null and rp.tipo='normal' and rp.fecha_operacion > c0.f0
 union all select 3, 'armado POST (-)', -sum(coalesce(r.cantidad_armada,
 r.cantidad)) from pedidos_renglones r join vig v on v.id=r.pedido_id
 join a0 on a0.id=r.articulo_id, c0 where r.armado_el is not null
 and r.anulado_el is null and r.ficha_id is not null
 and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date > c0.f0
)
select concepto, coalesce(bultos,0) as bultos,
 sum(coalesce(bultos,0)) over () as CAJAS_en_fichas
from t order by orden;
