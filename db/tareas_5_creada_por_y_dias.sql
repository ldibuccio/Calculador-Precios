do $$
begin
  if to_regclass('tareas') is null then
    raise exception 'falta tareas: corre primero tareas_1';
  end if;
  alter table tareas add column if not exists creada_por text default 'gerencia';
  update tareas set creada_por = 'gerencia' where creada_por is null;
  alter table tareas alter column creada_por set not null;
  alter table tareas drop constraint if exists tareas_creada_por;
  alter table tareas add constraint tareas_creada_por check (
    creada_por in ('compras', 'administracion', 'gerencia')
    and (creada_por = 'gerencia' or creada_por = sector));
  alter table tareas add column if not exists dias_mes integer[];
  update tareas set dias_mes = array[dia_mes]
   where dia_mes is not null and dias_mes is null;
  alter table tareas drop constraint if exists tareas_campos_de_su_tipo;
  alter table tareas add constraint tareas_campos_de_su_tipo check (
    (tipo = 'una_vez' and vence_el is not null and cada_dias is null
      and dia_semana is null and dia_mes is null and dias_mes is null
      and desde is null)
    or (tipo <> 'una_vez' and vence_el is null and desde is not null
      and (tipo = 'cada_dias') = coalesce(cada_dias >= 1, false)
      and (tipo = 'semanal') = coalesce(dia_semana between 0 and 6, false)
      and (tipo = 'mensual') = (coalesce(dia_mes between 1 and 31, false)
        or coalesce(cardinality(dias_mes) >= 1 and 1 <= all(dias_mes)
                    and 31 >= all(dias_mes), false))
      and (dias_mes is null or cardinality(dias_mes) >= 1)));
end $$;

-- TAREAS POR SECTOR (duenio, 02/10), bloque 1 de 2: se corre ANTES del deploy.
--
-- creada_por: quien cargo la tarea. Las que ya existen quedan de Gerencia.
-- Un sector solo crea tareas para si mismo; Gerencia, para cualquiera. El
-- default 'gerencia' es solo para la ventana hasta el deploy (el codigo
-- viejo inserta sin la columna, y solo Gerencia crea): lo saca tareas_6.
--
-- dias_mes: la mensual sale en varios dias del mes. Se copia dia_mes, y
-- mientras dure la ventana el CHECK acepta las dos formas. Los CHECK son
-- contenido: drop y recrear. Ninguna tarea cambia de regla.
--
-- Se corre SOLO, en las dos bases. Verificacion aparte: tareas_7.
