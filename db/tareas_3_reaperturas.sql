do $$
begin
  if to_regclass('tareas_ocurrencias') is null then
    raise exception 'falta tareas_ocurrencias: corre primero tareas_2';
  end if;
  if to_regclass('tareas_reaperturas') is not null then
    raise exception 'tareas_reaperturas ya existe: este bloque ya corrio';
  end if;
  create table tareas_reaperturas (
    id bigint generated always as identity primary key,
    ocurrencia_id bigint not null references tareas_ocurrencias (id),
    motivo text not null check (btrim(motivo) <> ''),
    hecha_el_anterior timestamptz not null,
    hecha_por_anterior text not null,
    nota_anterior text,
    sector text not null check (sector = 'gerencia'),
    creado_en timestamptz not null default now()
  );
  create index tareas_reaperturas_por_ocurrencia on tareas_reaperturas (ocurrencia_id);
  comment on table tareas_reaperturas is
    'Cuando Gerencia volvio a pendiente una tarea hecha: el motivo y lo que '
    'decia antes (cuando, quien y la nota). El sector no puede desmarcar.';
end $$;

-- TAREAS (duenio, 02/10), bloque 3 de 3: el registro de las reaperturas.
-- Solo Gerencia (la base exige sector 'gerencia'), con motivo.
--
-- Se corre despues del bloque 2, SOLO. Verificacion: tareas_4.
