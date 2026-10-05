do $$
begin
  if to_regclass('fleteros_camiones') is null then
    raise exception 'falta fleteros_camiones: corre primero fletes_2';
  end if;
  if to_regclass('fletes') is not null then
    raise exception 'fletes ya existe: este bloque ya corrio';
  end if;
  create table fletes (
    id bigint generated always as identity primary key,
    fecha date not null,
    cliente_id bigint not null references clientes (id),
    fletero_id bigint not null references fleteros (id),
    confirmado_el timestamptz not null default now(),
    unique (fecha, cliente_id, fletero_id)
  );
  create table fletes_sucursales (
    id bigint generated always as identity primary key,
    flete_id bigint not null references fletes (id) on delete cascade,
    sucursal text not null,
    pallets_frutamax integer not null check (pallets_frutamax >= 0),
    pallets_palmala integer not null check (pallets_palmala >= 0),
    constraint fletes_sucursales_con_pallets
      check (pallets_frutamax + pallets_palmala > 0),
    unique (flete_id, sucursal)
  );
  create table fletes_viajes (
    id bigint generated always as identity primary key,
    flete_sucursal_id bigint not null
      references fletes_sucursales (id) on delete cascade,
    camion_id bigint not null references fleteros_camiones (id),
    precio numeric(14,2) not null check (precio >= 0),
    parte_frutamax numeric(14,2) not null check (parte_frutamax >= 0),
    parte_palmala numeric(14,2) not null check (parte_palmala >= 0),
    pagado_el date,
    constraint fletes_viajes_partes_suman
      check (parte_frutamax + parte_palmala = precio)
  );
  create index fletes_viajes_por_sucursal on fletes_viajes (flete_sucursal_id);
  create index fletes_por_fecha on fletes (fecha);
end $$;

-- FLETES, bloque 3 de 4: el flete del dia (pestania 2) y su cuenta (3).
--
-- Un flete = fecha + cliente + UN fletero. Por sucursal, los pallets de cada
-- empresa; por camion, un viaje con el precio de ESE dia congelado y la
-- parte de cada empresa por pallets (las dos partes suman el precio). El
-- pago es por viaje: pagado_el vacio = a pagar.
