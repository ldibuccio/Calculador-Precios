do $$
begin
  if to_regclass('vales_a_cobrar_salidas') is null then
    raise exception 'falta vales_a_cobrar_salidas: corre primero vales_2';
  end if;
  create or replace function vale_que_salio_no_se_corrige() returns trigger
  language plpgsql as $f$
  begin
    if (new.importe, new.numero, new.fecha, new.proveedor_id)
       is distinct from (old.importe, old.numero, old.fecha, old.proveedor_id)
       and coalesce(current_setting('app.juntando_proveedores', true), '') <> 'si'
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
end $$;

-- VALES, CARGA MANUAL (duenio, 02/10), bloque 3 de 3: la pared.
--
-- Un vale cobrado o cruzado (con fila en vales_a_cobrar_salidas) no se
-- corrige: ni importe, ni numero, ni fecha, ni proveedor. La pantalla no
-- ofrece el boton; esto frena el POST armado a mano.
--
-- EXCEPCION a proposito: juntar dos proveedores mueve proveedor_id de los
-- vales, tambien de los que ya salieron. Esa funcion hace
-- `set local app.juntando_proveedores = 'si'` en su transaccion y la pared la
-- deja pasar (ver juntar_proveedores en app/db.py). No es una correccion: es
-- el mismo proveedor con dos fichas.
--
-- La funcion es CONTENIDO (create or replace) y el trigger drop + create.
-- Se corre despues del bloque 2, SOLO. Verificacion: vales_manual_4.
