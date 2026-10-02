do $$
begin
  if to_regclass('segunda_cobros') is null then
    raise exception 'falta segunda_cobros: corre primero cobranza_segunda_1';
  end if;
  create or replace function segunda_cobro_solo_lote_vigente() returns trigger
  language plpgsql as $f$
  begin
    if not exists (select 1 from remitos_segunda
                    where id = new.salida_id and destino = 'puesto'
                      and anulado_el is null) then
      raise exception 'la salida % no es un lote al puesto vigente', new.salida_id
        using errcode = 'check_violation', constraint = 'segunda_cobro_solo_lote_vigente';
    end if;
    return new;
  end $f$;
  drop trigger if exists segunda_cobro_solo_lote_vigente on segunda_cobros;
  create trigger segunda_cobro_solo_lote_vigente
    before insert or update on segunda_cobros
    for each row execute function segunda_cobro_solo_lote_vigente();

  create or replace function segunda_cobrada_no_se_anula() returns trigger
  language plpgsql as $f$
  begin
    if new.anulado_el is not null and old.anulado_el is null
       and exists (select 1 from segunda_cobros where salida_id = new.id) then
      raise exception 'la salida % tiene cobro: primero hay que volverla a pendiente', new.id
        using errcode = 'check_violation', constraint = 'segunda_cobrada_no_se_anula';
    end if;
    return new;
  end $f$;
  drop trigger if exists segunda_cobrada_no_se_anula on remitos_segunda;
  create trigger segunda_cobrada_no_se_anula
    before update of anulado_el on remitos_segunda
    for each row execute function segunda_cobrada_no_se_anula();
end $$;

-- COBRANZAS DE SEGUNDA, bloque 3 de 3: las dos paredes.
--
-- 1. Solo se cobra un lote al PUESTO y NO anulado: una merma de segunda o
--    una salida anulada no tienen nada que cobrar.
-- 2. Una salida con cobro NO SE ANULA: primero Gerencia la vuelve a
--    pendiente (con motivo, queda en el historial) y recien ahi se anula.
--
-- Las funciones son CONTENIDO, asi que van con create or replace y los
-- triggers con drop + create: correrlo dos veces deja lo ultimo que se
-- mando, no lo primero.
--
-- Se corre despues del bloque 2, SOLO. Verificacion: cobranza_segunda_4.
