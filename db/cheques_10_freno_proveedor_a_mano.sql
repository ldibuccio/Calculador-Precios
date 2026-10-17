-- CHEQUES (dueño, 16/10), migración cheques_3, bloque 2. En Frutamax Y en Palmala.
-- Un pago a proveedor dice a quién: de la lista O escrito a mano.
create or replace function cheque_salida_valida() returns trigger
language plpgsql as $f$
declare
  ch      cheques%rowtype;
  destino text;
begin
  select * into ch from cheques where id = new.cheque_id;
  select c.destino into destino from cheques_conceptos c where c.id = new.concepto_id;
  if destino = 'entregado' and new.proveedor_id is null and new.proveedor_a_mano is null then
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
