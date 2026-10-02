do $$
begin
  if to_regclass('remitos_segunda') is null then
    raise exception 'falta remitos_segunda: esta base no tiene salidas de segunda';
  end if;
  if to_regclass('segunda_cobros') is not null then
    raise exception 'segunda_cobros ya existe: este bloque ya corrio';
  end if;
  create table segunda_cobros (
    salida_id bigint primary key references remitos_segunda (id),
    importe numeric(14, 2) not null,
    fecha_cobro date not null,
    sector text not null check (sector in ('administracion', 'gerencia')),
    creado_en timestamptz not null default now(),
    constraint segunda_cobros_importe_no_negativo check (coalesce(importe >= 0, false))
  );
  comment on table segunda_cobros is
    'Cobranzas de segunda (duenio, 02/10): lo que pago el puesto por cada '
    'lote (una salida de remitos_segunda con destino puesto). Una fila por '
    'lote; sin fila, el lote esta pendiente. El importe puede ser 0: cobrado '
    'en cero. Sector y hora dicen quien lo cargo.';
end $$;

-- COBRANZAS DE SEGUNDA, bloque 1 de 3: el cobro de cada lote.
--
-- Un LOTE es una salida al puesto de segunda que ya se registra
-- (remitos_segunda, destino 'puesto', no anulada). Nace pendiente: no hay
-- fila aca. Cobrarlo es insertar su fila, con el importe que pago el puesto
-- por ESE lote (no hay un total para repartir). La clave es salida_id, asi
-- que un lote no se cobra dos veces.
--
-- Los 60 lotes que existen hoy en Frutamax (29/08 al 01/10, 608 bultos)
-- arrancan pendientes: este bloque no inserta nada.
--
-- Se corre SOLO, en las dos bases. Verificacion: cobranza_segunda_4.
