-- PALMALA CRUCES (dueño, 14/10), migración palmala_1. SOLO EN FRUTAMAX: no se corre en Palmala.
create or replace function palmala_movimiento_valido() returns trigger
language plpgsql as $f$
declare
  concepto palmala_conceptos%rowtype;
begin
  select * into concepto from palmala_conceptos where id = new.concepto_id;
  if tg_op = 'INSERT' and not concepto.activo then
    raise exception 'el concepto % ya no se usa', concepto.nombre
      using errcode = 'check_violation', constraint = 'palmala_concepto_activo';
  end if;
  if not concepto.pide_cheque and (new.cheque_numero is not null
     or new.cheque_banco_id is not null or new.cheque_fecha_pago is not null) then
    raise exception 'el concepto % no lleva cheque', concepto.nombre
      using errcode = 'check_violation', constraint = 'palmala_cheque_sin_concepto';
  end if;
  if concepto.pide_cheque and new.como_se_cargo <> 'historico' and (new.cheque_numero is null
     or new.cheque_banco_id is null or new.cheque_fecha_pago is null) then
    raise exception 'un pago con cheque lleva número, banco y fecha de pago'
      using errcode = 'check_violation', constraint = 'palmala_cheque_completo';
  end if;
  return new;
end $f$;
drop trigger if exists palmala_movimiento_valido on palmala_movimientos;
create trigger palmala_movimiento_valido before insert or update on palmala_movimientos
  for each row execute function palmala_movimiento_valido();

create or replace view palmala_movimientos_con_saldo with (security_invoker = true) as
select m.id, m.fecha, m.cuenta, m.sentido, m.importe, m.concepto_id, c.nombre as concepto,
       m.detalle, m.cheque_numero, m.cheque_banco_id, m.cheque_fecha_pago, m.foto_ruta,
       m.como_se_cargo, m.anulado, m.creado_en,
       case when m.anulado then 0 when m.sentido = 'debe' then m.importe else -m.importe end
         as con_signo,
       sum(case when m.anulado then 0 when m.sentido = 'debe' then m.importe else -m.importe end)
         over (partition by m.cuenta order by m.fecha, m.id) as saldo
from palmala_movimientos m
join palmala_conceptos c on c.id = m.concepto_id;
