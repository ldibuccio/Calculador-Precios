do $$
begin
  if exists (select 1 from information_schema.columns
              where table_schema = 'public' and table_name = 'pedidos_renglones_lotes_correcciones'
                and column_name = 'que') then
    raise exception 'lote_dia_anterior_2 ya corrio';
  end if;
  alter table pedidos_renglones_lotes_correcciones
    add column que text not null default 'lote',
    add column en_su_envase_antes boolean,
    add column en_su_envase_ahora boolean,
    add column kilos_antes numeric,
    add column kilos_ahora numeric;
  alter table pedidos_renglones_lotes_correcciones
    add constraint lotes_correcciones_que check (que in ('lote', 'como_salio')),
    add constraint lotes_correcciones_como_salio_entero check (
      (que = 'como_salio') = (en_su_envase_antes is not null and en_su_envase_ahora is not null)),
    add constraint lotes_correcciones_kilos_solo_como_salio check (
      que = 'como_salio' or (kilos_antes is null and kilos_ahora is null));
  if exists (select 1 from pg_roles where rolname = 'lectura_claudia') then
    grant select on pedidos_renglones_lotes_correcciones to lectura_claudia;
    create policy lectura_claudia_lee on pedidos_renglones_lotes_correcciones
      for select to lectura_claudia using (true);
  end if;
end $$;

-- COMO SALIO UN RENGLON DE UN DIA ANTERIOR (dueño, 09/10): el historial de
-- las correcciones pasa a guardar tambien el cambio de "en su envase" a
-- "caja de Dia" (o al reves) y los kilos de antes y de ahora. que = 'lote'
-- para lo que ya habia. Y lectura_claudia (solo existe en Frutamax) puede
-- leer la tabla. Si se corre dos veces, da error y no escribe nada.
-- Verificacion APARTE: lote_dia_anterior_2_verificacion.sql.
