do $$
begin
  if to_regclass('remitos') is null then
    raise exception 'falta remitos: corre primero remitos_1';
  end if;
  if to_regclass('remitos_numeros') is not null then
    raise exception 'remitos_numeros ya existe: este bloque ya corrio';
  end if;
  create table remitos_numeros (
    id bigint generated always as identity primary key,
    remito_id bigint not null references remitos (id),
    numero_anterior text not null check (btrim(numero_anterior) <> ''),
    numero_nuevo text not null check (btrim(numero_nuevo) <> ''),
    corregido_el timestamptz not null default now(),
    constraint remitos_numeros_distinto
      check (upper(btrim(numero_anterior)) <> upper(btrim(numero_nuevo)))
  );
  create index remitos_numeros_por_remito on remitos_numeros (remito_id);
  comment on table remitos_numeros is
    'Las correcciones del numero de un remito (error de tipeo), solo '
    'Gerencia: el anterior, el nuevo y cuando. remitos.numero tiene el '
    'ultimo; esto es el registro y no se borra.';
end $$;

-- REMITOS, bloque 4 de 4: el registro de las correcciones del numero.
