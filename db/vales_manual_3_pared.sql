do $$
begin
  if to_regclass('vales_a_cobrar_salidas') is null then
    raise exception 'falta vales_a_cobrar_salidas: corre primero vales_2';
  end if;
  create or replace function vale_que_salio_no_se_corrige() returns trigger
  language plpgsql as $f$
  begin
    if (new.importe, new.numero, new.fecha)
       is distinct from (old.importe, old.numero, old.fecha)
       and exists (select 1 from vales_a_cobrar_salidas where vale_id = new.id) then
      raise exception 'el vale % ya salio de la cartera: no se corrige', new.id
        using errcode = 'check_violation', constraint = 'vale_que_salio_no_se_corrige';
    end if;
    return new;
  end $f$;
  drop trigger if exists vale_que_salio_no_se_corrige on vales_a_cobrar;
  create trigger vale_que_salio_no_se_corrige
    before update on vales_a_cobrar
    for each row execute function vale_que_salio_no_se_corrige();

  create or replace function vale_que_salio_cambia_de_proveedor() returns trigger
  language plpgsql as $f$
  begin
    if new.proveedor_id is distinct from old.proveedor_id
       and exists (select 1 from vales_a_cobrar_salidas where vale_id = new.id)
       and exists (select 1 from proveedores where id = old.proveedor_id) then
      raise exception 'el vale % ya salio de la cartera: no cambia de proveedor', new.id
        using errcode = 'check_violation', constraint = 'vale_que_salio_no_se_corrige';
    end if;
    return null;
  end $f$;
  drop trigger if exists vale_que_salio_cambia_de_proveedor on vales_a_cobrar;
  create constraint trigger vale_que_salio_cambia_de_proveedor
    after update of proveedor_id on vales_a_cobrar
    deferrable initially deferred
    for each row execute function vale_que_salio_cambia_de_proveedor();
end $$;

-- VALES, CARGA MANUAL (duenio, 02/10), bloque 3 de 3: las paredes.
--
-- Un vale cobrado o cruzado no se corrige. Importe, numero y fecha: nunca,
-- lo frena el primer trigger en el momento.
-- El proveedor: solo si al CERRAR la transaccion el proveedor viejo ya no
-- existe, que es lo que pasa al juntar dos proveedores (mueve los vales y
-- borra el que se va, todo junto). Por eso el segundo es diferido.
--
-- Funciones: create or replace. Triggers: drop + create.
-- Se corre despues del bloque 2, SOLO. Verificacion: vales_manual_4.
