-- CARTERA DE CHEQUES, migración cheques_2 (dueño, 13/10): la cuenta del depósito y el freno del rechazo solo al salir.
alter table cheques_salidas add column if not exists cuenta_deposito text
  constraint cheques_salidas_cuenta_no_vacia check (cuenta_deposito is null or btrim(cuenta_deposito) <> '');

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
  if tg_op = 'INSERT' or new.cheque_id is distinct from old.cheque_id
     or new.fecha is distinct from old.fecha then
    if exists (select 1 from cheques_rechazos where cheque_id = new.cheque_id) then
      raise exception 'el cheque % está rechazado: no sale', new.cheque_id
        using errcode = 'check_violation', constraint = 'cheque_rechazado_no_sale';
    end if;
    if new.fecha < ch.fecha_carga then
      raise exception 'el cheque % no puede salir antes de entrar', new.cheque_id
        using errcode = 'check_violation', constraint = 'cheque_salida_fechas';
    end if;
  end if;
  return new;
end $f$;
