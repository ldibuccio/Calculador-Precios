do $$
begin
  if to_regclass('fotos_borrados') is not null then
    raise exception 'fotos_borrados ya existe: este bloque ya corrio';
  end if;
  create table fotos_borrados (
    id bigint generated always as identity primary key,
    borrado_el timestamptz not null default now(),
    como text not null check (como in ('plazo', 'a_mano')),
    tipo text not null check (btrim(tipo) <> ''),
    anteriores_a date not null,
    cantidad integer not null check (cantidad >= 0),
    bytes bigint not null check (bytes >= 0),
    salteadas integer not null check (salteadas >= 0)
  );
  comment on table fotos_borrados is
    'HISTORIAL de los borrados de fotos (duenio, 01/10): una fila por tipo en '
    'cada borrado, con el rango (subidas antes de anteriores_a), cuantas, '
    'cuantos bytes y cuantas se saltearon por estar protegidas.';
end $$;

-- FOTOS, bloque 7: el historial de borrados.
--
-- como: 'plazo' es el boton de las vencidas; 'a_mano' es el borrado por
-- tipo y fecha. Las salteadas son las de un vale en cartera o un remito sin
-- facturar: esas no se borran nunca, y el historial dice cuantas quedaron.
