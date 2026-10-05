do $$
begin
  if exists (select 1 from information_schema.columns
             where table_name = 'remitos_fotos' and column_name = 'cargada_por') then
    raise exception 'remitos_fotos_1 ya corrio';
  end if;
  -- Las que hay entraron TODAS por Recibir, que es de Administracion: el
  -- default las llena, y el codigo nuevo escribe el sector siempre.
  alter table remitos_fotos add column cargada_por text not null
    default 'administracion'
    constraint remitos_fotos_cargada_por_check
    check (cargada_por in ('administracion', 'gerencia'));
  comment on column remitos_fotos.cargada_por is 'El sector que subio la foto: al recibir (Administracion) o agregada despues desde el remito recibido (Administracion o Gerencia). Las fotos solo se agregan.';
end $$;

-- FOTOS DE UN REMITO RECIBIDO (dueño, 05/10): se pueden AGREGAR despues de
-- recibido, con fecha (creado_en) y quien (cargada_por, el sector). Nunca
-- se reemplazan ni se borran desde el remito. Si se corre dos veces, da
-- error y no escribe nada. Verificacion APARTE:
-- remitos_fotos_1_verificacion.sql.
