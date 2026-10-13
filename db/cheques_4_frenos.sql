-- CARTERA DE CHEQUES (dueño, 13/10), bloque 4 de 5. Corrido por Lionel en Frutamax y Palmala el 13/10.
create or replace function cheque_salida_valida() returns trigger
language plpgsql as $f$
declare
  ch      cheques%rowtype;
  destino text;
begin
  select * into ch from cheques where id = new.cheque_id;
  select c.destino into destino from cheques_conceptos c where c.id = new.concepto_id;
  if destino = 'entregado' and new.proveedor_id is null then
    raise exception 'un pago a proveedor tiene que decir a qué proveedor'
      using errcode = 'check_violation', constraint = 'cheque_entregado_con_proveedor';
  end if;
  if exists (select 1 from cheques_rechazos where cheque_id = new.cheque_id) then
    raise exception 'el cheque % está rechazado: no sale', new.cheque_id
      using errcode = 'check_violation', constraint = 'cheque_rechazado_no_sale';
  end if;
  if new.fecha < ch.fecha_carga then
    raise exception 'el cheque % no puede salir antes de entrar', new.cheque_id
      using errcode = 'check_violation', constraint = 'cheque_salida_fechas';
  end if;
  return new;
end $f$;
drop trigger if exists cheque_salida_valida on cheques_salidas;
create trigger cheque_salida_valida before insert or update on cheques_salidas
  for each row execute function cheque_salida_valida();

create or replace function cheque_que_salio_no_se_corrige() returns trigger
language plpgsql as $f$
begin
  if exists (select 1 from cheques_salidas where cheque_id = new.id)
     or exists (select 1 from cheques_rechazos where cheque_id = new.id) then
    raise exception 'el cheque % ya no está en cartera: no se corrige', new.id
      using errcode = 'check_violation', constraint = 'cheque_que_salio_no_se_corrige';
  end if;
  return new;
end $f$;
drop trigger if exists cheque_que_salio_no_se_corrige on cheques;
create trigger cheque_que_salio_no_se_corrige before update on cheques
  for each row execute function cheque_que_salio_no_se_corrige();
