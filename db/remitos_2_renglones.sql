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
    bultos_recibidos numeric check (bultos_recibidos >= 0),
    kilos_recibidos numeric check (kilos_recibidos >= 0),
    constraint remitos_renglones_recibidos_tope
      check (coalesce(bultos_recibidos <= bultos_enviados, true)),
    constraint remitos_renglones_recibido_entero
      check ((kilos_recibidos is null) = (bultos_recibidos is null)),
    unique (remito_id, pedido_renglon_id)
  );
  create index remitos_renglones_por_renglon
    on remitos_renglones (pedido_renglon_id);
  comment on table remitos_renglones is
    'Lo que salio, CONGELADO al emitir (bultos y kilos enviados), y lo que '
    'el super firmo que recibio: bultos y kilos recibidos. No mueve stock: '
    'enviados - recibidos se coteja contra los rechazos de deposito.';
  comment on column remitos_renglones.kilos_enviados is
    'La magnitud de la ficha (kilos, unidades o cubetas), igual que '
    'pedidos_renglones.kilos_enviados, de donde se copia.';
end $$;

-- REMITOS, bloque 2 de 4: los renglones congelados.
--
-- Enviado y recibido conviven en la misma fila: lo enviado no se toca
-- nunca, y lo recibido se carga UNA vez, cuando vuelve el remito firmado.
-- Un renglon cambio si recibido <> enviado, en bultos o en kilos, y la hora
-- es remitos.recibido_el. bultos_recibidos y kilos_recibidos van juntos.
