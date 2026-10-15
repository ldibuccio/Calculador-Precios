-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 10. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create or replace view cuentas_todos_los_movimientos with (security_invoker = true) as
select m.cuenta_id, 'movimiento'::text as origen, m.id as origen_id, m.fecha, m.tipo, m.importe,
       c.nombre as concepto, e.nombre as etiqueta, m.detalle, m.foto_ruta, m.anulado, m.creado_en
from cuentas_movimientos m
join cuentas_conceptos c on c.id = m.concepto_id
left join cuentas_etiquetas e on e.id = m.etiqueta_id
union all
select t.cuenta_origen_id, 'transferencia', t.id, t.fecha, 'egreso', t.importe,
       case when o.tipo = 'banco' and d.tipo = 'inversion' then 'Suscripción'
            when o.tipo = 'inversion' and d.tipo = 'banco' then 'Rescate'
            when o.tipo = 'caja' and d.tipo = 'banco' then 'Depósito de efectivo'
            when o.tipo = 'banco' and d.tipo = 'caja' then 'Extracción'
            else 'Transferencia' end,
       d.nombre, t.detalle, t.foto_ruta, t.anulado, t.creado_en
from cuentas_transferencias t join cuentas o on o.id = t.cuenta_origen_id
join cuentas d on d.id = t.cuenta_destino_id
union all
select t.cuenta_destino_id, 'transferencia', t.id, t.fecha, 'ingreso', t.importe,
       case when o.tipo = 'banco' and d.tipo = 'inversion' then 'Suscripción'
            when o.tipo = 'inversion' and d.tipo = 'banco' then 'Rescate'
            when o.tipo = 'caja' and d.tipo = 'banco' then 'Depósito de efectivo'
            when o.tipo = 'banco' and d.tipo = 'caja' then 'Extracción'
            else 'Transferencia' end,
       o.nombre, t.detalle, t.foto_ruta, t.anulado, t.creado_en
from cuentas_transferencias t join cuentas o on o.id = t.cuenta_origen_id
join cuentas d on d.id = t.cuenta_destino_id
union all
select dp.cuenta_id, 'deposito', ch.id, ch.acreditado_el, 'ingreso', ch.importe,
       'Depósito de cheque', ch.de_quien, 'Nº ' || ch.numero, null, false, dp.creado_en
from cuentas_cheques_depositados dp join cheques_con_estado ch on ch.id = dp.cheque_id
where ch.acreditado_el is not null
union all
select dp.cuenta_id, 'rechazo', ch.id, ch.fecha_rechazo, 'egreso', ch.importe,
       'Cheque rechazado', ch.de_quien, 'Nº ' || ch.numero || ' · ' || ch.motivo_rechazo, null, false,
       dp.creado_en
from cuentas_cheques_depositados dp join cheques_con_estado ch on ch.id = dp.cheque_id
where ch.fecha_rechazo is not null;
