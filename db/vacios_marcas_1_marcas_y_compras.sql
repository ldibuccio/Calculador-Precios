do $$
begin
  create table if not exists marcas_vacio (
    id                 bigint generated always as identity primary key,
    proveedor_id       bigint not null references proveedores (id),
    nombre             text not null,
    nombre_normalizado text not null,
    activo             boolean not null default true,
    creado_en          timestamptz not null default now()
  );
  alter table marcas_vacio drop constraint if exists marcas_vacio_nombre_unico;
  alter table marcas_vacio add constraint marcas_vacio_nombre_unico
    unique (proveedor_id, nombre_normalizado);
  if not exists (select 1 from pg_constraint where conname = 'marcas_vacio_id_proveedor') then
    alter table marcas_vacio add constraint marcas_vacio_id_proveedor
      unique (id, proveedor_id);
  end if;

  alter table compras add column if not exists marca_vacio_id bigint;
  alter table compras add column if not exists marca text;
  alter table compras drop constraint if exists compras_marca_vacio_del_proveedor;
  alter table compras add constraint compras_marca_vacio_del_proveedor
    foreign key (marca_vacio_id, proveedor_id) references marcas_vacio (id, proveedor_id);

  comment on table marcas_vacio is 'Las marcas de los cajones de CADA proveedor de Compras. Se cargan en Vacíos y Recepción solo elige entre ellas.';
  comment on column compras.marca_vacio_id is 'La marca del cajón con que llegó esta compra con seña. NULL = sin asignar.';
  comment on column compras.marca is 'La marca de la MERCADERÍA (texto libre, lo carga Recepción). NULL = sin asignar.';
end $$;

-- LAS MARCAS (dueño, 25/09). Dos cosas distintas con la misma palabra:
--   · marca del VACÍO: catálogo por proveedor (marcas_vacio). El stock de
--     vacíos se lleva por proveedor y por marca.
--   · marca de la MERCADERÍA: texto libre en la compra (compras.marca).
--
-- LA FK COMPUESTA (marca, proveedor) hace que la BASE rechace una marca de
-- otro proveedor: una compra de Kleppe no puede llevar un cajón de Almana.
-- Decide la base; el código traduce el error. Con la marca en NULL no se
-- controla nada, que es "sin asignar".
--
-- nombre_normalizado lo calcula el código (normalizar_texto). El UNIQUE de
-- (id, proveedor_id) no se recrea: es estructura y las FK compuestas cuelgan
-- de él, así que borrarlo rompería la segunda corrida.
