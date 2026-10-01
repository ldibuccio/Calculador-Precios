do $$
begin
  if to_regclass('remitos') is null then
    raise exception 'falta remitos: corre primero remitos_1';
  end if;
  if to_regclass('remitos_renglones') is not null then
    raise exception 'remitos_renglones ya existe: este bloque ya corrio';
  end if;
  create table remitos_renglones (
    id bigint generated always as identity primary key,
    remito_id bigint not null references remitos (id),
    pedido_renglon_id bigint not null references pedidos_renglones (id),
    bultos_enviados numeric not null check (bultos_enviados > 0),
    kilos_enviados numeric not null check (kilos_enviados >= 0),
    kilos_recibidos numeric check (kilos_recibidos >= 0),
    bultos_rechazados numeric check (bultos_rechazados >= 0),
    constraint remitos_renglones_rechazo_tope
      check (coalesce(bultos_rechazados <= bultos_enviados, true)),
    constraint remitos_renglones_recibido_entero
      check ((kilos_recibidos is null) = (bultos_rechazados is null)),
    unique (remito_id, pedido_renglon_id)
  );
  create index remitos_renglones_por_renglon on remitos_renglones (pedido_renglon_id);
  comment on table remitos_renglones is
    'Lo que salio en el remito, CONGELADO al emitir (bultos y kilos_enviados '
    'del renglon), y lo que el remito firmado dice que se recibio: kilos '
    'recibidos y bultos rechazados. Los rechazos NO mueven stock: se cotejan '
    'contra los que cargo deposito (movimientos_stock).';
  comment on column remitos_renglones.kilos_enviados is
    'La magnitud de la ficha (kilos, unidades o cubetas), igual que '
    'pedidos_renglones.kilos_enviados, de donde se copia.';
end $$;

-- REMITOS, bloque 2 de 3: los renglones congelados.
--
-- kilos_recibidos y bultos_rechazados van juntos (los dos o ninguno): se
-- cargan en la misma pantalla al recibir el remito firmado. Lo que se cobra
-- es kilos_recibidos x precio vigente a la fecha del pedido.
