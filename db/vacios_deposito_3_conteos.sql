do $$
begin
  if exists (select 1 from pg_tables where schemaname = 'public'
              and tablename = 'conteos_vacios_deposito') then
    return;
  end if;

  create table conteos_vacios_deposito (
      id             bigint generated always as identity primary key,
      proveedor_id   bigint  not null references proveedores (id),
      cantidad       integer not null check (cantidad >= 0),
      fecha          date    not null,
      stock_sistema  integer not null,
      creado_en      timestamptz not null default now()
  );

  comment on table conteos_vacios_deposito is
    'Conteo fisico de los cajones de un proveedor que hay en el galpon. El primero de cada proveedor es su BASE: antes de el no hay cuenta, y las recepciones anteriores a su fecha quedan absorbidas.';
  comment on column conteos_vacios_deposito.fecha is
    'El dia del conteo, que es lo que decide que recepciones se suman y cuales quedan absorbidas. Va aparte de creado_en porque se puede contar hoy y fechar ayer.';
  comment on column conteos_vacios_deposito.stock_sistema is
    'Stock derivado EN el instante del conteo, guardado del lado del server: el que cuenta no lo ve. Si lo viera, transcribe en vez de contar.';
end $$;
