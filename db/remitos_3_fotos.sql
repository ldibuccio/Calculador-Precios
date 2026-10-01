do $$
begin
  if to_regclass('remitos') is null then
    raise exception 'falta remitos: corre primero remitos_1';
  end if;
  if to_regclass('remitos_fotos') is not null then
    raise exception 'remitos_fotos ya existe: este bloque ya corrio';
  end if;
  create table remitos_fotos (
    id bigint generated always as identity primary key,
    remito_id bigint not null references remitos (id),
    foto_ruta text not null check (btrim(foto_ruta) <> ''),
    creado_en timestamptz not null default now()
  );
  create index remitos_fotos_por_remito on remitos_fotos (remito_id);
  comment on table remitos_fotos is
    'Las fotos del remito FIRMADO que trae el camionero (una o mas, '
    'obligatorias al recibir). Bucket "comandas", prefijo "remitos".';
end $$;

-- REMITOS, bloque 3 de 3: las fotos del remito firmado.
