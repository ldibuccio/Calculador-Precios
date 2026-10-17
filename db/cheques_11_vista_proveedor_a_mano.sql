-- CHEQUES (dueño, 16/10), migración cheques_3, bloque 3. En Frutamax Y en Palmala.
-- La vista suma, AL FINAL, el proveedor escrito a mano (las demás columnas, igual).
create or replace view cheques_con_estado with (security_invoker = true) as
with hoy as (select (now() at time zone 'America/Argentina/Buenos_Aires')::date as dia)
select ch.*, coalesce(cl.nombre, ch.nombre_a_mano, 'Canje') as de_quien,
       ch.fecha_pago + 30 as vence_el,
       s.fecha as fecha_salida, s.proveedor_id, co.nombre as concepto,
       case when co.destino = 'depositado'
            then greatest(ch.fecha_pago, s.fecha) + 1 end as acreditado_el,
       r.fecha as fecha_rechazo, r.motivo as motivo_rechazo, r.resuelto_el, r.resolucion,
       case
         when r.cheque_id is not null and r.resuelto_el is null then 'rechazado'
         when r.cheque_id is not null then 'reclamo_resuelto'
         when s.cheque_id is null and hoy.dia >= ch.fecha_pago + 30 then 'vencido'
         when s.cheque_id is null then 'en_cartera'
         when co.destino = 'depositado'
              and hoy.dia > greatest(ch.fecha_pago, s.fecha) then 'acreditado'
         else co.destino
       end as estado,
       (s.cheque_id is null and r.cheque_id is null
        and hoy.dia >= ch.fecha_pago + 23) as en_rojo_por_vencer,
       s.proveedor_a_mano
from cheques ch
cross join hoy
left join clientes cl on cl.id = ch.cliente_id
left join cheques_salidas s on s.cheque_id = ch.id
left join cheques_conceptos co on co.id = s.concepto_id
left join cheques_rechazos r on r.cheque_id = ch.id;
