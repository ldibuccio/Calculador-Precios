-- Fotos por GUÍA (comanda de un proveedor en un día), en vez de foto_ruta
-- repetida por renglón. Correr en las DOS bases ANTES de mergear el código.
--
-- OJO: NO es aditivo puro. Además de crear la tabla, el backfill:
--   1. CREA filas en guias_compra para las compras históricas que no
--      tienen guía (de antes de que existieran las guías), y les asigna
--      esa guía (UPDATE de compras.guia_id SOLO donde está NULL — nunca
--      cambia una guía ya asignada).
--   2. Puebla fotos_guia con las fotos existentes (una fila por guía,
--      aunque hoy la ruta esté repetida en N renglones).
-- Antes de correrlo, correr la consulta de lectura de abajo (comentada)
-- para saber cuántas filas va a tocar en cada base.
--
-- compras.foto_ruta queda como columna MUERTA (el código deja de
-- escribirla y de leerla): el DROP va en una migración posterior, cuando
-- se verifique que todo anda en producción. Está anotado en APLICADO.md.

-- === CONSULTA DE LECTURA PREVIA (solo SELECT, correr primero) ===
-- SELECT
--   (SELECT COUNT(*) FROM compras WHERE guia_id IS NULL) AS compras_sin_guia,
--   (SELECT COUNT(*) FROM (
--       SELECT DISTINCT c.fecha_operacion, c.proveedor_id FROM compras c
--       WHERE c.guia_id IS NULL
--         AND NOT EXISTS (SELECT 1 FROM guias_compra g
--                         WHERE g.fecha_operacion = c.fecha_operacion
--                           AND g.proveedor_id = c.proveedor_id)
--    ) nuevas) AS guias_a_crear,
--   (SELECT COUNT(DISTINCT foto_ruta) FROM compras WHERE foto_ruta IS NOT NULL) AS fotos_distintas,
--   (SELECT COUNT(*) FROM (
--       SELECT DISTINCT guia_id, foto_ruta FROM compras
--       WHERE foto_ruta IS NOT NULL AND guia_id IS NOT NULL) f) AS filas_fotos_guia_directas;

begin;

create table fotos_guia (
    id         bigint generated always as identity primary key,
    guia_id    bigint not null references guias_compra (id),
    foto_ruta  text not null,
    creado_en  timestamptz not null default now(),
    unique (guia_id, foto_ruta)
);

comment on table fotos_guia is 'Fotos/archivos de una guía (comanda de un proveedor en un día), en el bucket "comandas". Una guía puede tener varias; un mismo archivo (foto_ruta) puede colgar de varias guías (el Listado consolidado comparte una foto entre proveedores). Reemplaza a compras.foto_ruta, que queda muerta hasta su DROP (ver APLICADO.md).';
comment on column fotos_guia.foto_ruta is 'Ruta del archivo en el bucket "comandas". El archivo físico se borra del Storage solo cuando NINGUNA guía lo referencia.';

create index fotos_guia_foto_ruta_idx on fotos_guia (foto_ruta);

-- Backfill 1: compras históricas sin guía — se les crea/asigna la suya.
-- El unique (fecha_operacion, proveedor_id) de guias_compra garantiza que
-- no se duplica ninguna guía existente.
insert into guias_compra (fecha_operacion, proveedor_id)
select distinct c.fecha_operacion, c.proveedor_id
from compras c
where c.guia_id is null
on conflict (fecha_operacion, proveedor_id) do nothing;

update compras c
set guia_id = g.id
from guias_compra g
where c.guia_id is null
  and g.fecha_operacion = c.fecha_operacion and g.proveedor_id = c.proveedor_id;

-- Backfill 2: cada foto existente cuelga de su guía, UNA vez por guía
-- (el DISTINCT colapsa los renglones que hoy repiten la misma ruta).
insert into fotos_guia (guia_id, foto_ruta)
select distinct c.guia_id, c.foto_ruta
from compras c
where c.foto_ruta is not null and c.guia_id is not null
on conflict do nothing;

commit;

-- Verificación posterior (solo SELECT): las dos primeras tienen que dar 0.
-- SELECT
--   (SELECT COUNT(*) FROM compras WHERE guia_id IS NULL) AS compras_sin_guia_quedan,
--   (SELECT COUNT(*) FROM compras c WHERE c.foto_ruta IS NOT NULL
--      AND NOT EXISTS (SELECT 1 FROM fotos_guia f
--                      WHERE f.guia_id = c.guia_id AND f.foto_ruta = c.foto_ruta)) AS fotos_sin_migrar,
--   (SELECT COUNT(*) FROM fotos_guia) AS filas_fotos_guia;
