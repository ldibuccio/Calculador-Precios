do $$
begin
  if exists (select 1 from pg_tables where schemaname = 'public'
              and tablename = 'vacios_deposito_devoluciones') then
    return;
  end if;

  create table vacios_deposito_devoluciones (
      id             bigint generated always as identity primary key,
      proveedor_id   bigint  not null references proveedores (id),
      compra_id      bigint  not null references compras (id),
      cantidad       integer not null check (cantidad > 0),
      importe        numeric check (importe is null or importe >= 0),
      foto_ruta      text,
      stock_sistema  integer not null,
      creado_en      timestamptz not null default now(),
      anulado_el     timestamptz
  );

  comment on table vacios_deposito_devoluciones is
    'Salida: se le devuelven al proveedor SUS cajones vacios. Es lo unico que se carga a mano del circuito del deposito — las entradas se derivan de las recepciones.';
  comment on column vacios_deposito_devoluciones.compra_id is
    'CONTRA QUE COMPRA se aplica el vale. Obligatorio: el descuento no es una cuenta corriente contra el proveedor, vive pegado a la compra concreta contra la que se entrego el vale.';
  comment on column vacios_deposito_devoluciones.importe is
    'Lo que ese vale descuenta, si tiene importe. NO toca compras.importe ni el costeo: el descuento vive SOLO aca. NULLABLE porque una devolucion puede no tener plata atras.';
  comment on column vacios_deposito_devoluciones.stock_sistema is
    'Stock derivado (entradas − devoluciones, sin este movimiento) EN el instante de guardar. Mismo criterio que vacios_devueltos del puesto.';
  comment on column vacios_deposito_devoluciones.anulado_el is
    'NULL = vigente. Se anula, nunca se borra: el stock lo excluye y el registro queda como correccion.';
end $$;
