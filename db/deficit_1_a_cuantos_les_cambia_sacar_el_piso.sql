-- ¿A cuántas fichas y cuántos bultos les cambia el número si la ficha resta
-- la salida COMPLETA en vez de frenar en cero? Solo lectura. LAS DOS BASES.
--
-- El piso de hoy (max(saldo,0), _cajas_por_ficha) manda el excedente a los
-- sueltos. Sacarlo mueve exactamente ese excedente: la ficha baja y los
-- sueltos suben, en la misma cantidad y para el mismo artículo.
--
-- LA PARTICIÓN QUE DECIDE, y es por envase:
--   con_envase -> la ficha declara que la mercadería se reenvasa. Un armado
--                 suyo NO puede salir de un cajón: acá el déficit es real y
--                 es lo que se quiere ver.
--   sin_envase -> envase perdido (manzana, pera, arándano): salen en el
--                 cajón del proveedor y NUNCA se reprocesan, así que su
--                 saldo es negativo puro y crece todos los días. Sacarles
--                 el piso reproduce el incidente del 04/09 (Manzana Gob:
--                 total 63, sueltos 233, ajuste destructivo precargado
--                 por 170) — ver el docstring de _cajas_por_ficha.
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
), saldos as (
  select coalesce(a.articulo_id, s.articulo_id) articulo_id,
         coalesce(a.ficha_id, s.ficha_id) ficha_id,
         coalesce(a.total, 0) - coalesce(s.total, 0) saldo
  from armadas a full join salidas s
    on s.articulo_id = a.articulo_id and s.ficha_id = a.ficha_id
)
select
  count(*) filter (where sd.saldo < 0)                                as fichas_en_deficit,
  count(*) filter (where sd.saldo < 0 and f.envase_id is not null)    as con_envase,
  count(*) filter (where sd.saldo < 0 and f.envase_id is null)        as sin_envase,
  coalesce(-sum(sd.saldo) filter (where sd.saldo < 0), 0)             as bultos_que_se_mueven,
  coalesce(-sum(sd.saldo) filter (where sd.saldo < 0
                                    and f.envase_id is not null), 0)  as bultos_con_envase,
  count(distinct sd.articulo_id) filter (where sd.saldo < 0)          as articulos,
  (select fecha from corte) as corte,
  (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion
from saldos sd
left join fichas_logistica f on f.id = sd.ficha_id;
