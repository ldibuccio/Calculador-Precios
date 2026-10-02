do $$
begin
  if to_regclass('tareas') is not null then
    raise exception 'tareas ya existe: este bloque ya corrio';
  end if;
  create table tareas (
    id bigint generated always as identity primary key,
    sector text not null check (sector in ('compras', 'administracion', 'gerencia')),
    titulo text not null check (btrim(titulo) <> ''),
    detalle text,
    tipo text not null check (tipo in ('una_vez', 'cada_dias', 'semanal', 'mensual')),
    vence_el date,
    cada_dias integer,
    dia_semana integer,
    dia_mes integer,
    desde date,
    generada_hasta date,
    estado text not null default 'activa' check (estado in ('activa', 'pausada', 'baja')),
    creado_en timestamptz not null default now(),
    actualizado_en timestamptz not null default now(),
    constraint tareas_campos_de_su_tipo check (
      (tipo = 'una_vez' and vence_el is not null and cada_dias is null
        and dia_semana is null and dia_mes is null and desde is null)
      or (tipo <> 'una_vez' and vence_el is null and desde is not null
        and (tipo = 'cada_dias') = coalesce(cada_dias >= 1, false)
        and (tipo = 'semanal') = coalesce(dia_semana between 0 and 6, false)
        and (tipo = 'mensual') = coalesce(dia_mes between 1 and 31, false))),
    constraint tareas_una_vez_no_se_pausa check (tipo <> 'una_vez' or estado = 'activa')
  );
  comment on table tareas is
    'Tareas que Gerencia le carga a un sector (duenio, 02/10): de una vez, con '
    'su vencimiento, o repetitivas (cada N dias, un dia de la semana con 0 = '
    'lunes, o un dia del mes). Lo que el sector ve y marca son las ocurrencias.';
end $$;

-- TAREAS (duenio, 02/10), bloque 1 de 3: la definicion de cada tarea.
--
-- Una de una vez lleva su vencimiento. Una repetitiva lleva desde cuando y su
-- regla, y se puede pausar o dar de baja; generada_hasta es hasta que fecha
-- ya se generaron sus ocurrencias (lo maneja la aplicacion). El CHECK de los
-- campos de cada tipo cubre las dos direcciones: ningun campo de mas, ninguno
-- de menos. Con coalesce, un NULL no lo deja pasar (corolario 67).
--
-- Se corre SOLO, en las dos bases. Verificacion: tareas_4.
