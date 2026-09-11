-- ¿Cuántos casos de diferencia de kilos hay desde el corte, y de qué tamaño?
-- Dimensiona la alerta de kilaje ANTES de escribirla: si "mayor a 1 kilo" da
-- cuarenta por semana, el umbral está mal elegido, no la alerta.
--
-- La diferencia es el TOTAL (cajones × contenido), la misma cuenta del
-- costeo, con el COALESCE de producción. Solo unidad_compra = 'kilo'.
-- Trae el CORTE (el parámetro), la ÚLTIMA RECEPCIÓN (el testigo) y la
-- POBLACIÓN al lado de los conteos.
--
-- VERIFICADA contra db/esquema_completo.sql en Postgres 16 con el caso
-- PLANTADO (corolario 36): cinco compras sembradas —exacta, 3 kg menos,
-- 20 kg más, recepcionada sin real, y una en unidades— dieron
-- recepcionadas 5 · con_real 4 · en_kilos 4 · mayor_1 2 · mayor_5 1 ·
-- mayor_10 1 · mayor_25 0 · de_menos 1 · de_mas 1. El canario del recorte
-- movió mayor_1 de 2 a 3. Sin la fila de corte_modelo vuelve UNA fila con
-- corte en NULL y la última recepción viva al lado (corolario 17).
with c0 as (select fecha as f0 from corte_modelo where id = 1),
d as (
  select (c.cantidad_cajones * c.contenido_por_cajon) as est,
         (coalesce(c.cantidad_cajones_real, c.cantidad_cajones)
          * coalesce(c.contenido_por_cajon_real, c.contenido_por_cajon)) as rea,
         (c.cantidad_cajones_real is not null
          or c.contenido_por_cajon_real is not null) as tiene_real,
         a.unidad_compra as un
  from compras c
  join articulos a on a.id = c.articulo_id
  where c.estado = 'recepcionado'
    and c.fecha_operacion > (select f0 from c0)
)
select (select f0 from c0) as corte,
       (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion,
       (current_date - (select f0 from c0)) as dias,
       count(*) as recepcionadas,
       count(*) filter (where tiene_real) as con_real,
       count(*) filter (where un = 'kilo') as en_kilos,
       count(*) filter (where tiene_real and un = 'kilo' and abs(rea - est) > 1) as mayor_1,
       count(*) filter (where tiene_real and un = 'kilo' and abs(rea - est) > 5) as mayor_5,
       count(*) filter (where tiene_real and un = 'kilo' and abs(rea - est) > 10) as mayor_10,
       count(*) filter (where tiene_real and un = 'kilo' and abs(rea - est) > 25) as mayor_25,
       count(*) filter (where tiene_real and un = 'kilo' and rea - est < -1) as de_menos,
       count(*) filter (where tiene_real and un = 'kilo' and rea - est > 1) as de_mas
from d;
