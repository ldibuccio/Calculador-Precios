do $$
begin
  if to_regclass('vales_a_cobrar_fotos') is not null then
    raise exception 'vales_a_cobrar_fotos ya existe: este bloque ya corrio';
  end if;
  create table vales_a_cobrar_fotos (
    id bigint generated always as identity primary key,
    vale_id bigint not null references vales_a_cobrar (id),
    foto_ruta text not null unique,
    sector text not null check (sector in ('administracion', 'gerencia')),
    creado_en timestamptz not null default now()
  );
  create index vales_a_cobrar_fotos_vale on vales_a_cobrar_fotos (vale_id);
  comment on table vales_a_cobrar_fotos is
    'Fotos ANEXADAS a un vale (duenio, 30/09), en cualquier estado. No se borran: '
    'la original (de la devolucion o del vale en papel) no esta aca.';
end $$;

-- FOTOS (duenio, 30/09), bloque 1 de 4: las fotos anexadas a un vale.
--
-- Desde el detalle de un vale, en Administracion y en Gerencia, "Anexar
-- foto" suma una o varias. La foto ORIGINAL no se copia: se sigue leyendo de
-- la devolucion de vacios o de vales_a_cobrar.foto_ruta (vale en papel).
-- Ninguna pantalla borra una anexada; solo la limpieza de 3 anios de Gerencia
-- se lleva el ARCHIVO, y la fila queda.
--
-- Si la tabla ya existe el bloque aborta sin tocar nada.
-- Orden: fotos_1 a fotos_4, cada uno SOLO. Verificacion aparte:
-- fotos_5_verificacion.sql.
