do $$
begin
  create table if not exists vacios_deposito_asignaciones (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint  not null references proveedores (id),
    marca_desde_id  bigint,
    marca_hasta_id  bigint  not null,
    cantidad        integer not null,
    stock_sistema   integer not null,
    creado_en       timestamptz not null default now(),
    anulado_el      timestamptz
  );
  alter table vacios_deposito_asignaciones drop constraint if exists vacios_asig_desde_del_proveedor;
  alter table vacios_deposito_asignaciones add constraint vacios_asig_desde_del_proveedor
    foreign key (marca_desde_id, proveedor_id) references marcas_vacio (id, proveedor_id);
  alter table vacios_deposito_asignaciones drop constraint if exists vacios_asig_hasta_del_proveedor;
  alter table vacios_deposito_asignaciones add constraint vacios_asig_hasta_del_proveedor
    foreign key (marca_hasta_id, proveedor_id) references marcas_vacio (id, proveedor_id);
  alter table vacios_deposito_asignaciones drop constraint if exists vacios_asig_cantidad_y_pilas;
  alter table vacios_deposito_asignaciones add constraint vacios_asig_cantidad_y_pilas
    check (cantidad > 0 and marca_desde_id is distinct from marca_hasta_id);

  comment on table vacios_deposito_asignaciones is 'Pasar N cajones de una pila (marca_desde NULL = sin asignar) a una marca, sin tocar ninguna recepción. Una fila con las dos puntas: anularla deshace las dos.';
end $$;

-- LA ASIGNACIÓN, en Administración (dueño, 25/09): "agarrar una cantidad de
-- vacíos y asignarle una marca, sin depender de la recepción". UNA fila con
-- las dos puntas y no dos filas sueltas: anular una sola dejaría los
-- cajones en las dos pilas a la vez. Corre después del bloque 1.
