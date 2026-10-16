-- EXCEPCIONES DE ALERTAS (dueño, 16/10), migración alertas_excepciones_1, verificación del bloque 3. SOLO EN FRUTAMAX, aparte.
select 'alertas_excepciones_1 (remito 20344)' as QUE_MIGRACION,
  count(*) as excepciones_1,
  max(re.id) as remito_id_5,
  max(re.numero) as numero_20344,
  max(cl.nombre) as cliente,
  max(e.motivo) as motivo,
  max(e.fecha) as fecha,
  (select count(*) from remitos) as testigo_remitos
from alertas_excepciones e
join remitos re on re.id = e.apunta_a
join clientes cl on cl.id = re.cliente_id
where e.alerta = 'remitos_rechazo_distinto';
