do $$
begin
  if not exists (select 1 from information_schema.columns
                  where table_name = 'tareas' and column_name = 'dias_mes') then
    raise exception 'falta dias_mes: corre primero tareas_5';
  end if;
  update tareas set dias_mes = array[dia_mes]
   where dia_mes is not null and dias_mes is null;
  alter table tareas alter column creada_por drop default;
  alter table tareas drop constraint if exists tareas_campos_de_su_tipo;
  alter table tareas add constraint tareas_campos_de_su_tipo check (
    (tipo = 'una_vez' and vence_el is not null and cada_dias is null
      and dia_semana is null and dias_mes is null and desde is null)
    or (tipo <> 'una_vez' and vence_el is null and desde is not null
      and (tipo = 'cada_dias') = coalesce(cada_dias >= 1, false)
      and (tipo = 'semanal') = coalesce(dia_semana between 0 and 6, false)
      and (tipo = 'mensual') = coalesce(cardinality(dias_mes) >= 1
        and 1 <= all(dias_mes) and 31 >= all(dias_mes), false)
      and (dias_mes is null or cardinality(dias_mes) >= 1)));
  alter table tareas drop column dia_mes;
end $$;

-- TAREAS POR SECTOR (duenio, 02/10), bloque 2 de 2: se corre DESPUES del
-- deploy (corolario 94). Hasta entonces el codigo viejo lee dia_mes.
--
-- Copia otra vez dia_mes a dias_mes (por si en la ventana se cargo una
-- mensual con el codigo viejo), saca el default de creada_por (desde aca el
-- codigo siempre dice quien) y deja el CHECK solo con dias_mes. Despues
-- borra dia_mes.
--
-- Se corre SOLO, en las dos bases. Verificacion aparte: tareas_7.
