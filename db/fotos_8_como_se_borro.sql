do $$
begin
  if to_regclass('fotos_borrados') is null then
    raise exception 'falta fotos_borrados: corre primero fotos_7';
  end if;
  if exists (select 1 from information_schema.columns
              where table_name = 'fotos_borradas_por_antiguedad' and column_name = 'como') then
    raise exception 'la columna como ya existe: este bloque ya corrio';
  end if;
  alter table fotos_borradas_por_antiguedad
    add column como text,
    add column borrado_id bigint references fotos_borrados (id);
  update fotos_borradas_por_antiguedad set como = 'plazo';
  alter table fotos_borradas_por_antiguedad alter column como set not null;
  alter table fotos_borradas_por_antiguedad
    add constraint fotos_borradas_como check (como in ('plazo', 'a_mano'));
  comment on column fotos_borradas_por_antiguedad.como is
    'Por que se borro el archivo: plazo (vencio segun fotos_plazos) o a_mano '
    '(borrado de Gerencia por tipo y fecha). Las anteriores al 01/10 son plazo.';
end $$;

-- FOTOS, bloque 8: "por plazo / a mano" en cada foto borrada.
--
-- Las filas que ya estaban se borraron por antiguedad, que es el plazo de 3
-- anios: van como 'plazo'. Sin default en la base: el codigo siempre dice
-- cual fue. borrado_id las ata al renglon del historial (las viejas, NULL).
