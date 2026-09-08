-- Mango: la cuenta 2 por ficha SIN el piso (el Cotejo la muestra con
-- max(saldo,0), asi que un negativo se ve igual que un cero), y si los
-- renglones de esa ficha salieron completos. Una fila por ficha + TOTAL.
with c0 as (select fecha f0,'America/Argentina/Buenos_Aires' z
from corte_modelo where id=1),
art as (select id from articulos where nombre ilike '%mango%'),
vig as (select distinct on (cliente_id,fecha_operacion) id,fecha_operacion fo
from pedidos where anulado_el is null
order by cliente_id,fecha_operacion,creado_en desc),
prod as (select rp.ficha_id fid,sum(rp.bultos_primera) q
from reprocesos rp,c0 where rp.anulado_el is null and rp.ficha_id is not null
and rp.articulo_id in (select id from art)
and (rp.fecha_operacion>c0.f0 or (rp.tipo='inicial' and rp.fecha_operacion>=c0.f0))
group by rp.ficha_id),
ren as (select r.ficha_id fid,
sum(coalesce(r.cantidad_armada,r.cantidad)) filter (where r.armado_el is not null
and (r.armado_el at time zone c0.z)::date>c0.f0) armado,
sum(r.cantidad) filter (where r.armado_el is null and v.fo>c0.f0) b_sin_armar,
count(*) filter (where r.armado_el is not null and r.cantidad_armada is not null
and r.cantidad_armada<r.cantidad) cortos,
count(*) filter (where r.armado_el is null and v.fo>c0.f0) sin_armar
from pedidos_renglones r join vig v on v.id=r.pedido_id,c0
where r.anulado_el is null and r.ficha_id is not null
and r.articulo_id in (select id from art)
group by r.ficha_id)
select coalesce(f.nombre_cliente,f.codigo_cliente,'ficha '||f.id,'TOTAL') ficha,
coalesce(sum(p.q),0) producidas,
coalesce(sum(n.armado),0) armado,
coalesce(sum(p.q),0)-coalesce(sum(n.armado),0) saldo_sin_piso,
coalesce(sum(n.cortos),0) reng_cortos,
coalesce(sum(n.sin_armar),0) reng_sin_armar,
coalesce(sum(n.b_sin_armar),0) bultos_sin_armar
from fichas_logistica f
left join prod p on p.fid=f.id
left join ren n on n.fid=f.id
where f.articulo_id in (select id from art)
group by grouping sets ((),(f.id,f.nombre_cliente,f.codigo_cliente))
having grouping(f.id)=1 or coalesce(sum(p.q),0)<>0
or coalesce(sum(n.armado),0)<>0 or coalesce(sum(n.sin_armar),0)<>0
order by grouping(f.id) desc,4;
