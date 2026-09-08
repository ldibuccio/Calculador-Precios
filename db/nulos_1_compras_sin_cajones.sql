-- ¿Entra al FIFO algun lote con cantidad NULA?
-- La consulta de lotes de app/db.py trae "c.cantidad_cajones_real AS cantidad"
-- PELADA, sin coalesce, y la columna es numeric NULLABLE: el unico check de
-- compras (compras_cantidad_cargada_check) exige kilos o fraccion, no
-- cajones. O sea que NADA obliga a que una compra recepcionada tenga los
-- cajones cargados, y una asi entraria al FIFO como un lote de cantidad NULL.
-- Ojo con no confundir los dos nulos de esa misma fila:
--   cantidad_cajones_real NULL  -> sospechoso, es lo que se mide aca.
--   importe NULL                -> ESPERADO y documentado ("compra sin precio
--                                  todavia"); son los lotes sin costo.
-- Trae el corte como columna porque recorta por el (una consulta
-- parametrizada por un dato de la base miente distinto en cada base), y
-- ultima_recepcion como testigo INDEPENDIENTE del corte: si el corte viniera
-- NULL, los ceros se explicarian solos y esta columna lo contradice.
with c0 as (select fecha f0 from corte_modelo where id = 1),
x as (
  select c.cantidad_cajones_real q, c.importe imp, c.procesada_el pe,
    (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
      > (select f0 from c0) post
  from compras c where c.estado = 'recepcionado'
)
select (select f0 from c0) corte,
  count(*) filter (where post) recep_post_corte,
  count(*) filter (where post and q is null) sin_cajones_post,
  count(*) filter (where post and q = 0) cero_cajones_post,
  count(*) filter (where post and imp is null) sin_importe_post,
  count(*) recep_total,
  count(*) filter (where q is null) sin_cajones_total,
  count(*) filter (where pe is null) sin_procesada_el,
  max((pe at time zone 'America/Argentina/Buenos_Aires')::date) ultima_recepcion
from x;
