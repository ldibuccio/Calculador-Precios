do $$
begin
  if exists (select 1 from information_schema.columns
              where table_schema = 'public' and table_name = 'reprocesos'
                and column_name = 'kilos_diferencia') then
    raise exception 'kilos_guia_r_1 ya corrio';
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
end $$;

-- LOS KILOS NO DAN (dueño, 13/10): cuando al cargar una guía R los kilos que
-- entraron (cajones tomados por lo que pesó el cajón de su compra) y los que
-- salieron (primera por los kilos de la ficha, más segunda y merma por el
-- cajón promedio) se separan más de 0,8 kg por cajón, sale un cartel
-- rojo. Si igual se guarda, la guía anota la diferencia en kilos (positiva =
-- faltan, negativa = sobran), quién la guardó y cuándo. Las tres van juntas o
-- ninguna. Las guías viejas quedan en vacío. Si se corre dos veces, da error
-- y no escribe nada. Verificación APARTE: kilos_guia_r_2_verificacion.sql.
