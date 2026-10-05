do $$
declare
  dia bigint;
begin
  if to_regclass('clientes_sucursales') is not null then
    raise exception 'clientes_sucursales ya existe: este bloque ya corrio';
  end if;
  select id into dia from clientes where nombre = 'Día %';
  if dia is null then
    raise exception 'no esta el cliente "Día %%": no se cargan sus sucursales';
  end if;
  create table clientes_sucursales (
    id bigint generated always as identity primary key,
    cliente_id bigint not null references clientes (id),
    codigo text not null check (codigo = upper(btrim(codigo)) and codigo <> ''),
    nombre text not null check (btrim(nombre) <> ''),
    unique (cliente_id, codigo)
  );
  comment on table clientes_sucursales is
    'El nombre de cada codigo de sucursal de un cliente (el de '
    'pedidos_sucursales.sucursal): VL es Vicente Lopez. Lo usan Fletes y su '
    'mensaje de WhatsApp.';
  insert into clientes_sucursales (cliente_id, codigo, nombre) values
    (dia, 'VL', 'Vicente López'), (dia, 'BZ', 'Burzaco'), (dia, 'GR', 'Garín');
end $$;

-- FLETES (duenio, 05/10), bloque 1 de 4: el nombre de las sucursales.
--
-- pedidos_sucursales guarda el codigo (VL, BZ, GR) y ningun lado decia como
-- se llama cada una. El duenio (05/10): Vicente Lopez, Burzaco y Garin. El
-- cliente se busca por NOMBRE y no por id: es el mismo en las dos bases hoy,
-- pero un id es un accidente de carga. Si no esta, el bloque no escribe nada.
