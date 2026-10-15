-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 8. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create or replace function cuentas_movimiento_valido() returns trigger
language plpgsql as $f$
declare
  concepto cuentas_conceptos%rowtype;
begin
  select * into concepto from cuentas_conceptos where id = new.concepto_id;
  if concepto.cuenta_id <> new.cuenta_id then
    raise exception 'el concepto % es de otra cuenta', concepto.nombre
      using errcode = 'check_violation', constraint = 'cuentas_concepto_de_la_cuenta';
  end if;
  if tg_op = 'INSERT' and not concepto.activo and new.como_se_cargo <> 'historico' then
    raise exception 'el concepto % ya no se usa', concepto.nombre
      using errcode = 'check_violation', constraint = 'cuentas_concepto_activo';
  end if;
  if concepto.tipo is not null and concepto.tipo <> new.tipo and new.como_se_cargo <> 'historico' then
    raise exception 'el concepto % es un %', concepto.nombre, concepto.tipo
      using errcode = 'check_violation', constraint = 'cuentas_concepto_del_tipo';
  end if;
  return new;
end $f$;
drop trigger if exists cuentas_movimiento_valido on cuentas_movimientos;
create trigger cuentas_movimiento_valido before insert or update on cuentas_movimientos
  for each row execute function cuentas_movimiento_valido();

create or replace function cuentas_transferencia_valida() returns trigger
language plpgsql as $f$
begin
  if (select moneda from cuentas where id = new.cuenta_origen_id)
     <> (select moneda from cuentas where id = new.cuenta_destino_id) then
    raise exception 'una transferencia es entre dos cuentas de la misma moneda'
      using errcode = 'check_violation', constraint = 'cuentas_transferencia_misma_moneda';
  end if;
  return new;
end $f$;
drop trigger if exists cuentas_transferencia_valida on cuentas_transferencias;
create trigger cuentas_transferencia_valida before insert or update on cuentas_transferencias
  for each row execute function cuentas_transferencia_valida();
