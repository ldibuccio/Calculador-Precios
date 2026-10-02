do $$
begin
  if to_regclass('segunda_cobros') is null then
    raise exception 'falta segunda_cobros: corre primero cobranza_segunda_1';
  end if;
  if to_regclass('segunda_cobros_historial') is not null then
    raise exception 'segunda_cobros_historial ya existe: este bloque ya corrio';
  end if;
  create table segunda_cobros_historial (
    id bigint generated always as identity primary key,
    salida_id bigint not null references remitos_segunda (id),
    tipo text not null check (tipo in ('correccion', 'a_pendiente')),
    importe_anterior numeric(14, 2) not null,
    importe_nuevo numeric(14, 2),
    fecha_cobro_anterior date not null,
    motivo text,
    sector text not null check (sector = 'gerencia'),
    creado_en timestamptz not null default now(),
    constraint segunda_historial_campos_de_su_tipo check (
      (tipo = 'correccion' and coalesce(importe_nuevo >= 0, false)
        and importe_nuevo <> importe_anterior)
      or (tipo = 'a_pendiente' and importe_nuevo is null
        and btrim(coalesce(motivo, '')) <> ''))
  );
  create index segunda_cobros_historial_por_lote on segunda_cobros_historial (salida_id);
  comment on table segunda_cobros_historial is
    'Lo que Gerencia le cambio a un cobro de segunda: correccion del importe '
    '(anterior y nuevo) o volver el lote a pendiente (con motivo). Sector y '
    'hora dicen quien. No se borra.';
end $$;

-- COBRANZAS DE SEGUNDA, bloque 2 de 3: el historial de las correcciones.
--
-- Un importe mal cargado lo corrige SOLO Gerencia, y queda el anterior, el
-- nuevo, la fecha y quien (el sector), igual que el numero de remito.
-- Volver un lote a pendiente borra su fila de segunda_cobros y deja aca el
-- importe que tenia y el motivo. Las dos cosas las hace cumplir la base:
-- sector 'gerencia' y los campos de cada tipo.
--
-- Se corre despues del bloque 1, SOLO. Verificacion: cobranza_segunda_4.
