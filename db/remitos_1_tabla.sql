do $$
begin
  if to_regclass('remitos') is not null then
    raise exception 'remitos ya existe: este bloque ya corrio';
  end if;
  create table remitos (
    id bigint generated always as identity primary key,
    pedido_sucursal_id bigint not null references pedidos_sucursales (id),
    cliente_id bigint not null references clientes (id),
    numero text not null check (btrim(numero) <> ''),
    emitido_el timestamptz not null default now(),
    recibido_el timestamptz,
    factura_numero text check (factura_numero is null or btrim(factura_numero) <> ''),
    facturado_el timestamptz,
    constraint remitos_factura_coherente
      check ((factura_numero is null) = (facturado_el is null)),
    constraint remitos_factura_despues_de_recibir
      check (facturado_el is null or recibido_el is not null)
  );
  create unique index remitos_numero_por_cliente
    on remitos (cliente_id, upper(btrim(numero)));
  create unique index remitos_uno_por_orden on remitos (pedido_sucursal_id);
  comment on table remitos is
    'Un remito por orden de compra (pedidos_sucursales). El remito oficial '
    'sale de otro sistema: aca se anota el numero, se congela lo que salio, '
    'lo que el super firmo y el numero de factura. NO SE ANULA: vuelve con '
    'sus observaciones. Gerencia puede corregir el numero (remitos_numeros).';
end $$;

-- REMITOS (duenio, 01/10), bloque 1 de 4: la tabla.
--
-- Estados derivados, sin columna de estado: emitido (sin recibido_el),
-- recibido (con recibido_el y sin factura), facturado (con factura).
-- Un remito no se anula (duenio, 01/10): una vez que salio al super, vuelve
-- con sus observaciones. Por eso uno solo por orden y el numero unico por
-- cliente, sin excepcion. cliente_id se copia del pedido al emitir, porque
-- el indice unico no puede mirar otra tabla.
