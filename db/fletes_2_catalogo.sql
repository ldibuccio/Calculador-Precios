do $$
begin
  if to_regclass('fleteros') is not null then
    raise exception 'fleteros ya existe: este bloque ya corrio';
  end if;
  create table fleteros (
    id bigint generated always as identity primary key,
    nombre text not null check (btrim(nombre) <> ''),
    telefono text check (telefono is null or btrim(telefono) <> ''),
    activo boolean not null default true,
    creado_el timestamptz not null default now()
  );
  create unique index fleteros_nombre on fleteros (upper(btrim(nombre)));
  create table fleteros_camiones (
    id bigint generated always as identity primary key,
    fletero_id bigint not null references fleteros (id),
    nombre text not null check (btrim(nombre) <> ''),
    pallets integer not null check (pallets > 0),
    cantidad integer not null check (cantidad >= 0)
  );
  create unique index fleteros_camiones_nombre
    on fleteros_camiones (fletero_id, upper(btrim(nombre)));
  create table fleteros_camiones_precios (
    id bigint generated always as identity primary key,
    camion_id bigint not null references fleteros_camiones (id),
    precio numeric(14,2) not null check (precio > 0),
    vigente_desde date not null,
    cargado_el timestamptz not null default now(),
    unique (camion_id, vigente_desde)
  );
  comment on table fleteros_camiones is
    'Los tipos de camion de un fletero: cuantos pallets lleva y cuantos '
    'tiene. cantidad 0 = ya no lo tiene.';
  comment on table fleteros_camiones_precios is
    'El precio del viaje de un tipo de camion, con historial: vale desde '
    'vigente_desde hasta el siguiente. Es el mismo vaya a la sucursal que '
    'vaya (duenio, 05/10).';
end $$;

-- FLETES, bloque 2 de 4: el catalogo (pestania 1). Un fletero tiene tipos
-- de camion; cada tipo lleva N pallets, el fletero tiene tantos, y su precio
-- por viaje tiene historial. Un camion va a una sola sucursal (duenio).
