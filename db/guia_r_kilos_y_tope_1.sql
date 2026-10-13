do $$
begin
  if exists (select 1 from information_schema.columns
              where table_schema = 'public' and table_name = 'reprocesos'
                and column_name = 'kilos_diferencia') then
    raise exception 'guia_r_kilos_y_tope_1 ya corrio';
  end if;
  alter table reprocesos
    add column kilos_diferencia numeric,
    add column kilos_guardo_igual text,
    add column kilos_guardo_igual_el timestamptz;
  alter table reprocesos
    add constraint reprocesos_kilos_guardo_igual_entero check (
      (kilos_diferencia is null and kilos_guardo_igual is null
       and kilos_guardo_igual_el is null)
      or (kilos_diferencia is not null and kilos_guardo_igual_el is not null
          and btrim(coalesce(kilos_guardo_igual, '')) <> ''));
  create or replace function guia_r_no_pasa_la_compra() returns trigger
  language plpgsql as $f$
  declare libres numeric;
  begin
    if new.compra_id is null then return new; end if;
    perform 1 from compras where id = new.compra_id for update;
    select coalesce(c.cantidad_cajones_real, 0) - coalesce((
             select sum(rc.bultos) from reprocesos_consumos rc
             join reprocesos rp on rp.id = rc.reproceso_id
             where rc.compra_id = c.id and rp.anulado_el is null), 0)
      into libres from compras c where c.id = new.compra_id;
    if new.bultos > libres then
      raise exception 'TOPE_COMPRA: a la compra % le quedan % cajones y la guia R pide %',
        new.compra_id, libres, new.bultos
        using errcode = 'check_violation', constraint = 'guia_r_no_pasa_la_compra';
    end if;
    return new;
  end $f$;
  create trigger guia_r_no_pasa_la_compra
    before insert on reprocesos_consumos
    for each row execute function guia_r_no_pasa_la_compra();
end $$;

-- GUIA R (dueño, 13/10), dos cosas en un bloque:
-- 1. LOS KILOS NO DAN: si se guarda igual, la guia anota la diferencia en kg
--    (positiva = faltan), quien y cuando. Las tres juntas o ninguna.
-- 2. TOPE POR COMPRA: una guia R nueva no puede anotar de una compra mas
--    cajones de los que le quedan (los recibidos menos lo que ya anotaron
--    todas las guias R no anuladas). Solo al insertar: lo viejo no se toca.
-- Si se corre dos veces, da error y no escribe nada.
