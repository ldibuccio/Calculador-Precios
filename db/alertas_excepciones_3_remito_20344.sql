-- EXCEPCIONES DE ALERTAS (dueño, 16/10), migración alertas_excepciones_1, bloque 3. SOLO EN FRUTAMAX (el remito es de ahí).
-- El remito 20344 de Día % no cuenta en "remitos_rechazo_distinto": arrastre ya corregido por otro lado.
do $$
declare
  v_cuantos int;
  v_id bigint;
begin
  select count(*), min(re.id) into v_cuantos, v_id
    from remitos re join clientes cl on cl.id = re.cliente_id
   where upper(btrim(re.numero)) = '20344' and cl.nombre = 'Día %';
  if v_cuantos <> 1 then
    raise exception 'esperaba UN remito 20344 de Día %% y hay %', v_cuantos;
  end if;
  insert into alertas_excepciones (alerta, apunta_a, motivo)
  values ('remitos_rechazo_distinto', v_id, 'Arrastre ya corregido');
end $$;
