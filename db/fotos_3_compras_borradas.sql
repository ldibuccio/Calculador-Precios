do $$
begin
  if to_regclass('fotos_de_compras_borradas') is not null then
    raise exception 'fotos_de_compras_borradas ya existe: este bloque ya corrio';
  end if;
  create table fotos_de_compras_borradas (
    id bigint generated always as identity primary key,
    compra_id bigint not null,
    foto_ruta text not null unique,
    subida_el timestamptz not null,
    compra_borrada_el timestamptz not null default now()
  );
  create index fotos_de_compras_borradas_compra on fotos_de_compras_borradas (compra_id);
  comment on table fotos_de_compras_borradas is
    'Fotos de pesada de una compra que se BORRO (duenio, 30/09). El archivo '
    'sigue en el bucket; compra_id no tiene FK porque la compra ya no existe '
    '(la fila archivada esta en compras_eliminadas).';
end $$;

-- FOTOS (duenio, 30/09), bloque 3 de 4: las fotos de pesada de una compra
-- borrada NO se borran.
--
-- fotos_recepcion.compra_id es una FK sin cascade, asi que para borrar la
-- compra hay que sacar esas filas. Hasta hoy se borraban con el archivo;
-- desde ahora pasan a esta tabla en la MISMA transaccion y el archivo queda.
-- Se ven en Gerencia -> Fotos: "de la compra N X, borrada el DD/MM".
-- subida_el es el creado_en de la fila original: la regla de 3 anios se
-- cuenta desde que se subio la foto, no desde que se borro la compra.
