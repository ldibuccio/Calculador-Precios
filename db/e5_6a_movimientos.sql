-- BLOQUE A de 3. Deja en una tabla REAL los movimientos con su TIPO de lote
-- y su costo. Se parte en tres porque entero no entra en 2500.
-- lado: 1 = entrada (lote), 2 = salida que no es armado, 3 = armado.
-- Los dos lados llevan el mismo piso asimetrico del corte que produccion.
drop table if exists e5_mov;
create table e5_mov as
with c0 as (select fecha f0,'America/Argentina/Buenos_Aires' z
from corte_modelo where id=1),
vig as (select distinct on (cliente_id,fecha_operacion) id from pedidos
where anulado_el is null order by cliente_id,fecha_operacion,creado_en desc)
select c.articulo_id aid,(c.procesada_el at time zone c0.z)::date d,
c.procesada_el m,c.cantidad_cajones_real q,c.importe cb,false trab,1 lado
from compras c,c0 where c.estado='recepcionado'
and (c.procesada_el at time zone c0.z)::date>c0.f0
union all
select m.articulo_id,m.fecha_operacion,m.creado_en,abs(m.cantidad),
m.costo_por_bulto,m.tipo='reingreso_rechazo',2-(m.cantidad>0)::int
from movimientos_stock m,c0 where m.anulado_el is null
and m.tipo<>'cierre_modelo_viejo'
and (m.cantidad<0 or m.destino_rechazo is null or m.destino_rechazo='stock')
and ((m.tipo='stock_inicial' and m.fecha_operacion=c0.f0 and m.cantidad>0)
or m.fecha_operacion>c0.f0)
union all
select rp.articulo_id,rp.fecha_operacion,rp.creado_en,rp.bultos_primera,
rp.costo_por_bulto_primera,true,1
from reprocesos rp,c0 where rp.anulado_el is null and rp.bultos_primera>0
and ((rp.tipo='inicial' and rp.fecha_operacion=c0.f0)
or rp.fecha_operacion>c0.f0)
union all
select r.articulo_id,(r.armado_el at time zone c0.z)::date,r.armado_el,
coalesce(r.cantidad_armada,r.cantidad),null,false,3
from pedidos_renglones r join vig v on v.id=r.pedido_id,c0
where r.armado_el is not null and r.anulado_el is null
and (r.armado_el at time zone c0.z)::date>c0.f0
union all
select rp.articulo_id,rp.fecha_operacion,rp.creado_en,rp.bultos_tomados,
null,false,2
from reprocesos rp,c0 where rp.anulado_el is null and rp.fecha_operacion>c0.f0;

select count(*) filas,count(*) filter (where lado=1) lotes,
count(*) filter (where lado=1 and trab) lotes_trabajados,
count(*) filter (where lado=3) armados,
count(*) filter (where lado=2) otras_salidas,
min(d) desde,max(d) hasta from e5_mov;
