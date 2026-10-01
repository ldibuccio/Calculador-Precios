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
    anulado_el timestamptz,
    anulado_motivo text check (anulado_motivo is null or btrim(anulado_motivo) <> ''),
    constraint remitos_factura_coherente
      check ((factura_numero is null) = (facturado_el is null)),
    constraint remitos_factura_despues_de_recibir
      check (facturado_el is null or recibido_el is not null),
    constraint remitos_anulado_con_motivo
      check ((anulado_el is null) = (anulado_motivo is null)),
    constraint remitos_facturado_no_se_anula
      check (anulado_el is null or facturado_el is null)
  );
  create unique index remitos_numero_por_cliente
    on remitos (cliente_id, upper(btrim(numero))) where anulado_el is null;
  create unique index remitos_uno_vivo_por_orden
    on remitos (pedido_sucursal_id) where anulado_el is null;
  comment on table remitos is
    'El remito OFICIAL de una orden de compra (pedidos_sucursales), duenio 01/10. '
    'Sale de otro sistema: aca se anota su numero, se congela lo que salio, '
    'se carga lo recibido y el numero de factura. Uno vivo por orden.';
end $$;

-- REMITOS (duenio, 01/10), bloque 1 de 3: la tabla.
--
-- Estados derivados, sin columna de estado: emitido (sin recibido_el),
-- recibido (con recibido_el y sin factura), facturado (con factura). Anulado
-- lo hace Gerencia con motivo, y uno facturado no se anula (CHECK).
-- El numero es unico por cliente entre los vivos: anular libera el numero
-- para volver a emitirlo. cliente_id se copia del pedido al emitir, porque
-- el indice unico no puede mirar otra tabla.
