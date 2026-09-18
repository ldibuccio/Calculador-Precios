do $$
begin
  if not exists (select 1 from pg_tables
                  where schemaname = 'public' and tablename = 'tipos_cajon') then
    create table tipos_cajon (
        id                 bigint generated always as identity primary key,
        nombre             text not null,
        nombre_normalizado text not null unique,
        activo             boolean not null default true,
        creado_en          timestamptz not null default now()
    );
    comment on table tipos_cajon is
      'Catalogo de tipos de cajon FISICO de los proveedores de Compras (el envase en el que llega la mercaderia al deposito). NO es tipos_envase_puesto —ese es del circuito del puesto— ni envases, que es el costo de la caja nuestra facturada al cliente.';
    comment on column tipos_cajon.nombre_normalizado is
      'nombre en minusculas, sin acentos ni espacios de mas. El UNIQUE evita el mismo cajon escrito de tres formas, igual que en proveedores_puesto.';
  end if;

  if not exists (select 1 from information_schema.columns
                  where table_name = 'proveedores' and column_name = 'tipo_cajon_id') then
    alter table proveedores
      add column tipo_cajon_id bigint references tipos_cajon (id);
    comment on column proveedores.tipo_cajon_id is
      'En que cajon entrega ESTE proveedor. UNO SOLO y declarado en el alta: un proveedor entrega siempre en el mismo tipo, asi que el stock de vacios del deposito es por PROVEEDOR y el tipo es como se llama su cajon, no una segunda dimension. NULLABLE a proposito: los proveedores que ya estan cargados no lo tienen, y exigirlo dejaria sin poder recepcionarles.';
  end if;
end $$;
