do $$
begin
  create table if not exists vacios_deposito_ajustes (
    id              bigint generated always as identity primary key,
    proveedor_id    bigint  not null references proveedores (id),
    marca_vacio_id  bigint,
    cantidad        integer not null,
    motivo          text,
    stock_sistema   integer not null,
    creado_en       timestamptz not null default now(),
    anulado_el      timestamptz
  );
  alter table vacios_deposito_ajustes drop constraint if exists vacios_aj_marca_del_proveedor;
  alter table vacios_deposito_ajustes add constraint vacios_aj_marca_del_proveedor
    foreign key (marca_vacio_id, proveedor_id) references marcas_vacio (id, proveedor_id);
  alter table vacios_deposito_ajustes drop constraint if exists vacios_aj_cantidad_y_motivo;
  alter table vacios_deposito_ajustes add constraint vacios_aj_cantidad_y_motivo
    check (cantidad <> 0 and btrim(coalesce(motivo, '')) <> '');

  comment on table vacios_deposito_ajustes is 'AJUSTE de stock de vacíos del depósito: el número no cierra y nadie sabe por qué. Con signo y motivo obligatorio. No es una devolución: una devolución lleva la foto del vale.';
end $$;

-- EL AJUSTE, en Administración (dueño, 25/09): "sin foto no es una
-- devolución, es un ajuste de stock — y eso es otra cosa, que tiene que
-- quedar registrada como tal". Con signo, por pila (proveedor y marca, NULL
-- = sin asignar) y con MOTIVO OBLIGATORIO. La regla del motivo la decide la
-- base. Corre después de los bloques 1 y 2. Verificación aparte.
