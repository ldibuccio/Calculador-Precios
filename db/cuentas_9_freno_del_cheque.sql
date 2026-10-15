-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 9. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create or replace function cuentas_cheque_depositado_valido() returns trigger
language plpgsql as $f$
begin
  if not exists (select 1 from cheques_salidas s join cheques_conceptos c on c.id = s.concepto_id
                 where s.cheque_id = new.cheque_id and c.destino = 'depositado') then
    raise exception 'el cheque % no salió depositado', new.cheque_id
      using errcode = 'check_violation', constraint = 'cuentas_cheque_depositado';
  end if;
  if (select tipo from cuentas where id = new.cuenta_id) <> 'banco' then
    raise exception 'un cheque se deposita en una cuenta de banco'
      using errcode = 'check_violation', constraint = 'cuentas_cheque_en_banco';
  end if;
  return new;
end $f$;
drop trigger if exists cuentas_cheque_depositado_valido on cuentas_cheques_depositados;
create trigger cuentas_cheque_depositado_valido before insert or update on cuentas_cheques_depositados
  for each row execute function cuentas_cheque_depositado_valido();
