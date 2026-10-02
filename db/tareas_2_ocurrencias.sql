do $$
begin
  if to_regclass('tareas') is null then
    raise exception 'falta tareas: corre primero tareas_1';
  end if;
  if to_regclass('tareas_ocurrencias') is not null then
    raise exception 'tareas_ocurrencias ya existe: este bloque ya corrio';
  end if;
  create table tareas_ocurrencias (
    id bigint generated always as identity primary key,
    tarea_id bigint not null references tareas (id),
    vence_el date not null,
    titulo text not null,
    detalle text,
    estado text not null default 'pendiente'
      check (estado in ('pendiente', 'hecha', 'no_hecha')),
    atrasada boolean not null default false,
    hecha_el timestamptz,
    hecha_por text check (hecha_por in ('compras', 'administracion', 'gerencia')),
    nota text,
    no_hecha_el date,
    creado_en timestamptz not null default now(),
    constraint tareas_ocurrencias_una_por_fecha unique (tarea_id, vence_el),
    constraint tareas_ocurrencias_hecha_coherente check (
      (estado = 'hecha') = (hecha_el is not null and hecha_por is not null)
      and (estado = 'hecha' or nota is null)
      and (estado = 'no_hecha') = (no_hecha_el is not null))
  );
  create index tareas_ocurrencias_pendientes on tareas_ocurrencias (estado, vence_el);
  comment on table tareas_ocurrencias is
    'Cada vez que una tarea sale: su vencimiento, el titulo y detalle de ese '
    'momento, y si se hizo (cuando, que sector, nota) o quedo no hecha porque '
    'llego la siguiente. Una repetitiva tiene UNA pendiente a la vez.';
end $$;

-- TAREAS (duenio, 02/10), bloque 2 de 3: lo que sale y se marca.
--
-- Titulo y detalle se COPIAN al generar: editar la tarea despues no cambia lo
-- que ya salio. Una repetitiva no acumula: cuando llega la fecha de la
-- siguiente y la anterior sigue pendiente, la anterior pasa a no_hecha (con
-- no_hecha_el) y la nueva sale con atrasada = true. La clave
-- (tarea_id, vence_el) impide generar dos veces la misma.
--
-- Se corre despues del bloque 1, SOLO. Verificacion: tareas_4.
