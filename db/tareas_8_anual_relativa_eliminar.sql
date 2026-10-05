do $$
begin
  if exists (select 1 from information_schema.columns
             where table_name = 'tareas' and column_name = 'eliminada_el') then
    raise exception 'tareas_8 ya corrio';
  end if;
  alter table tareas add column anual_dia integer, add column anual_mes integer,
    add column eliminada_el timestamptz, add column eliminada_por text;
  alter table tareas drop constraint tareas_tipo_check;
  alter table tareas add constraint tareas_tipo_check check (tipo in
    ('una_vez', 'cada_dias', 'semanal', 'mensual', 'anual', 'despues_de_hecha'));
  alter table tareas drop constraint tareas_campos_de_su_tipo;
  alter table tareas add constraint tareas_campos_de_su_tipo check (
    (tipo = 'una_vez' and vence_el is not null and cada_dias is null
      and dia_semana is null and dias_mes is null and desde is null
      and anual_dia is null and anual_mes is null)
    or (tipo <> 'una_vez' and vence_el is null and desde is not null
      and (tipo in ('cada_dias', 'despues_de_hecha')) = coalesce(cada_dias >= 1, false)
      and (tipo = 'semanal') = coalesce(dia_semana between 0 and 6, false)
      and (tipo = 'mensual') = coalesce(cardinality(dias_mes) >= 1
        and 1 <= all(dias_mes) and 31 >= all(dias_mes), false)
      and (dias_mes is null or cardinality(dias_mes) >= 1)
      and (tipo = 'anual') = coalesce(anual_mes between 1 and 12
        and anual_dia between 1 and 31, false)
      and (tipo = 'anual') = (anual_dia is not null or anual_mes is not null)));
  alter table tareas drop constraint tareas_una_vez_no_se_pausa;
  alter table tareas add constraint tareas_una_vez_no_se_pausa
    check (tipo <> 'una_vez' or estado in ('activa', 'baja'));
  alter table tareas add constraint tareas_eliminada_coherente check (
    (eliminada_el is null) = (eliminada_por is null)
    and (eliminada_por is null
      or eliminada_por in ('compras', 'administracion', 'gerencia'))
    and (eliminada_el is null or estado = 'baja'));
  alter table tareas_ocurrencias drop constraint tareas_ocurrencias_estado_check;
  alter table tareas_ocurrencias add constraint tareas_ocurrencias_estado_check
    check (estado in ('pendiente', 'hecha', 'no_hecha', 'eliminada'));
end $$;

-- TAREAS (duenio, 05/10): repetir anual o X dias despues de hecha
-- (cada_dias), y eliminar con quien y cuando. EXPAND.
