with c as (select fecha f from corte_modelo where id=1),
v as (select distinct on (cliente_id,fecha_operacion) id from pedidos
  where anulado_el is null order by cliente_id,fecha_operacion,creado_en desc),
arm as (select r.articulo_id a,(fl.envase_id is not null) caja,
  coalesce(r.cantidad_armada,r.cantidad)-coalesce(r.bultos_de_segunda,0) b
  from pedidos_renglones r join v on v.id=r.pedido_id
  left join fichas_logistica fl on fl.id=r.ficha_id, c
  where r.armado_el is not null and r.anulado_el is null
    and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date>c.f),
gr as (select articulo_id a,sum(bultos_primera) b from reprocesos,c
  where anulado_el is null and bultos_primera>0
    and (fecha_operacion>c.f or (tipo='inicial' and fecha_operacion=c.f))
  group by 1),
rch as (select articulo_id a,sum(cantidad) b,
  count(*) filter (where costo_por_bulto is null) sin_costo
  from movimientos_stock,c
  where anulado_el is null and tipo='reingreso_rechazo' and cantidad>0
    and (destino_rechazo is null or destino_rechazo='stock') and fecha_operacion>c.f
  group by 1),
mp as (select articulo_id a,-sum(cantidad) b from movimientos_stock,c
  where anulado_el is null and cantidad<0 and ficha_id is not null
    and tipo in ('merma','pase_a_segunda') and fecha_operacion>c.f group by 1)
select 'espera_3' as que_migracion,a.nombre articulo,
  coalesce(gr.b,0) cajas_guia_r,coalesce(rch.b,0) cajas_rechazo,
  coalesce(rch.sin_costo,0) rechazos_sin_costo,
  coalesce(sum(arm.b) filter (where arm.caja),0) armado_CON_caja,
  coalesce(sum(arm.b) filter (where not arm.caja),0) armado_SIN_caja,
  coalesce(mp.b,0) merma_pase_de_cajas,
  coalesce(gr.b,0)+coalesce(rch.b,0)-coalesce(mp.b,0)
    -coalesce(sum(arm.b) filter (where arm.caja),0) sobran_si_nadie_mas,
  (select f from c) corte,
  (select max(fecha_operacion) from reprocesos where anulado_el is null) ultima_guia_r
from articulos a
left join arm on arm.a=a.id left join gr on gr.a=a.id
left join rch on rch.a=a.id left join mp on mp.a=a.id
where a.nombre ilike any (array['%lim_n%','%cherry%','%ombligo%','%redondo%','%berenjena%'])
group by a.nombre,gr.b,rch.b,rch.sin_costo,mp.b
order by a.nombre;


-- SOLO LECTURA. Totales por articulo desde el corte, NO la lista de los 57
-- (esa sale del FIFO: Administracion > Alertas). Con sobran >= 0 y
-- armado_SIN_caja > 0, las cajas estaban y se las llevaron armados en cajon.
