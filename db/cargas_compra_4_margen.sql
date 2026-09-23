do $$
begin
  if not exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = 'cargas_compra'
                    and column_name = 'margen_porcentaje') then
    alter table cargas_compra add column margen_porcentaje numeric;
    -- LAS QUE YA ESTAN VAN A CERO y no al sugerido: se cargaron cuando el
    -- margen no existia, o sea sin ninguno. Ponerles 10 las inflaria un 10%
    -- sin que nadie lo haya pedido, y el numero que saldria es plausible.
    update cargas_compra set margen_porcentaje = 0 where margen_porcentaje is null;
    alter table cargas_compra alter column margen_porcentaje set not null;
  end if;
end $$;

alter table cargas_compra drop constraint if exists cargas_compra_margen_check;
alter table cargas_compra add constraint cargas_compra_margen_check
    check (margen_porcentaje >= 0);

comment on column cargas_compra.margen_porcentaje is 'Cuanto se compra de mas para ESTE cliente, en por ciento, SOBRE LO QUE PIDE y no sobre el faltante: el margen existe porque lo que se va a vender es incierto, y el piso esta contado. Es por CARGA y no por listado (dueno, 23/09): cuanto inflar lo de Dia es un hecho sobre Dia, y dos margenes que se multiplican son invisibles — 20% y 10% son 32% y nadie hace esa cuenta de cabeza. SIN DEFAULT EN LA BASE a proposito: el valor de arranque lo propone la pantalla (MARGEN_SUGERIDO, core/que_comprar.py) y dos defaults que no coinciden es como se separan dos reglas. 0 significa sin margen, y es distinto de vacio.';
