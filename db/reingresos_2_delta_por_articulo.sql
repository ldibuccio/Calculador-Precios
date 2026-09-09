-- Qué se mueve DE VERDAD de sueltos a fichas. Las DOS bases, solo lectura.
-- OJO: el total de reingresos NO es lo que se mueve; un reingreso que solo
-- achica un déficit no mueve un bulto. Ver docs/el_deficit_de_la_ficha...md
with corte as (select fecha from corte_modelo where id = 1),
vigentes as (
  select distinct on (cliente_id, fecha_operacion) id
  from pedidos where anulado_el is null
  order by cliente_id, fecha_operacion, creado_en desc
), armadas as (
  select rp.articulo_id, rp.ficha_id, sum(rp.bultos_primera) total
  from reprocesos rp, corte
  where rp.anulado_el is null and rp.ficha_id is not null
    and (rp.fecha_operacion > corte.fecha
         or (rp.tipo = 'inicial' and rp.fecha_operacion >= corte.fecha))
  group by 1, 2
), salidas as (
  select r.articulo_id, r.ficha_id, sum(coalesce(r.cantidad_armada, r.cantidad)) total
  from pedidos_renglones r join vigentes v on v.id = r.pedido_id, corte
  where r.armado_el is not null and r.anulado_el is null
    and r.articulo_id is not null and r.ficha_id is not null
    and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date > corte.fecha
  group by 1, 2
), reing as (
  select pr.articulo_id, pr.ficha_id, sum(m.cantidad) total
  from movimientos_stock m
  join pedidos_renglones pr on pr.id = m.pedido_renglon_id, corte
  where m.anulado_el is null and m.tipo = 'reingreso_rechazo'
    and (m.destino_rechazo is null or m.destino_rechazo = 'stock')
    and pr.ficha_id is not null and m.fecha_operacion > corte.fecha
  group by 1, 2
), por_ficha as (
  select re.articulo_id, re.ficha_id, re.total as reingreso,
         coalesce(a.total, 0) - coalesce(s.total, 0) as saldo_viejo
  from reing re
  left join armadas a on a.articulo_id = re.articulo_id and a.ficha_id = re.ficha_id
  left join salidas s on s.articulo_id = re.articulo_id and s.ficha_id = re.ficha_id
)
select art.nombre as articulo, f.nombre_cliente as ficha,
       p.reingreso, p.saldo_viejo,
       p.saldo_viejo + p.reingreso                                as saldo_nuevo,
       greatest(p.saldo_viejo + p.reingreso, 0)
         - greatest(p.saldo_viejo, 0)                             as sueltos_bajan,
       greatest(least(-p.saldo_viejo, p.reingreso), 0)           as deficit_que_tapa
from por_ficha p
join articulos art on art.id = p.articulo_id
join fichas_logistica f on f.id = p.ficha_id
order by 6 desc, 1;
