-- Las 25 diferencias más grandes entre comprado y recibido, desde el corte.
-- ¿Cargas mal hechas o el sistema imputando mal? Trae los CUATRO factores
-- crudos y no solo los dos productos: un error de carga mueve un número que
-- alguien tipeó; uno de imputación, el que el sistema completó solo.
-- `que_se_movio` los separa de un vistazo.
--
-- `contenido_real_nulo` marca el caso sospechoso: Depósito contó cajones y
-- no pesó el bulto, así que el real usa el contenido ESTIMADO y la
-- diferencia sale entera de los cajones — no dice "recibimos menos kilos",
-- dice "no lo pesamos".
--
-- SE LEE AL LADO DE kilos_1: es una LISTA, así que sin la fila de
-- corte_modelo vuelve VACÍA y se ve igual que "no hay diferencias".
--
-- Verificada contra el esquema real con el caso plantado y el canario del
-- recorte; el detalle está en el commit.
with c0 as (select fecha as f0 from corte_modelo where id = 1),
d as (
  select c.id, c.fecha_operacion, a.nombre as articulo, a.unidad_compra as unidad,
         p.nombre as proveedor, p.codigo_puesto as puesto,
         c.cantidad_cajones as caj_e, c.contenido_por_cajon as cont_e,
         c.cantidad_cajones_real as caj_r, c.contenido_por_cajon_real as cont_r,
         coalesce(c.cantidad_cajones_real, c.cantidad_cajones) as caj_u,
         coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon) as cont_u
  from compras c
  join articulos a on a.id = c.articulo_id
  join proveedores p on p.id = c.proveedor_id
  where c.estado = 'recepcionado'
    and c.fecha_operacion > (select f0 from c0)
    and a.unidad_compra = 'kilo'
    and (c.cantidad_cajones_real is not null or c.contenido_por_cajon_real is not null)
)
select (select f0 from c0) as corte, id as compra, fecha_operacion as fecha,
       articulo, unidad, proveedor, puesto,
       caj_e as cajones_est, cont_e as contenido_est,
       caj_r as cajones_real, cont_r as contenido_real,
       (caj_e * cont_e) as total_est,
       (caj_u * cont_u) as total_real,
       (caj_u * cont_u) - (caj_e * cont_e) as diferencia,
       (cont_r is null) as contenido_real_nulo,
       case when caj_u <> caj_e and cont_u <> cont_e then 'los dos'
            when caj_u <> caj_e                      then 'cajones'
            when cont_u <> cont_e                    then 'contenido'
            else 'ninguno' end as que_se_movio
from d
where abs((caj_u * cont_u) - (caj_e * cont_e)) > 1
order by abs((caj_u * cont_u) - (caj_e * cont_e)) desc
limit 25;
