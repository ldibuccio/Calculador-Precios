WITH dia AS (SELECT DATE '2026-09-17' f, 'America/Argentina/Buenos_Aires' tz),
arts AS (SELECT id, nombre FROM articulos WHERE lower(nombre) LIKE 'ar%nd%n%'),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC)
SELECT 'arandano_2_armados_del_17' QUE_CONSULTA,
  (SELECT f FROM dia) el_dia, x.nombre articulo,
  r.pedido_id, cl.nombre cliente, p.fecha_operacion fecha_pedido,
  CASE WHEN v.id IS NULL THEN 'NO (reemplazado o anulado)' ELSE 'si' END cuenta_para_el_stock,
  r.sucursal, r.cantidad pedida, r.cantidad_armada armada,
  COALESCE(r.cantidad_armada, r.cantidad) LA_QUE_RESTA,
  (r.armado_el AT TIME ZONE (SELECT tz FROM dia))::date armado_el,
  CASE WHEN r.anulado_el IS NOT NULL THEN 'renglon ANULADO' ELSE '' END nota
FROM pedidos_renglones r
JOIN arts x ON x.id = r.articulo_id
JOIN pedidos p ON p.id = r.pedido_id
LEFT JOIN vig v ON v.id = r.pedido_id
LEFT JOIN clientes cl ON cl.id = p.cliente_id
WHERE r.armado_el IS NOT NULL
  AND (r.armado_el AT TIME ZONE (SELECT tz FROM dia))::date = (SELECT f FROM dia)
UNION ALL
SELECT 'arandano_2_armados_del_17', (SELECT f FROM dia),
  'TOTAL que resta del stock ese dia', NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  COALESCE(SUM(COALESCE(r.cantidad_armada, r.cantidad)), 0), NULL,
  'renglones: ' || count(*)
FROM pedidos_renglones r
JOIN arts x ON x.id = r.articulo_id
JOIN vig v ON v.id = r.pedido_id
WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL
  AND (r.armado_el AT TIME ZONE (SELECT tz FROM dia))::date = (SELECT f FROM dia)
ORDER BY 12 NULLS LAST, 4;

-- ---------------------------------------------------------------------------
-- QUÉ ES ESTO. Los renglones de Arándano ARMADOS el 17/09, uno por fila, con
-- su cantidad y de qué pedido. Se corre SOLA. El último renglón es el TOTAL:
-- es lo que ese día le restó al stock.
--
-- `cuenta_para_el_stock` es la columna que hay que mirar. Un pedido RECARGADO
-- no se anula: deja de ser el vigente (`DISTINCT ON (cliente, fecha) ORDER BY
-- creado_en DESC`, igual que `_SQL_SUMAS_STOCK`). Las filas se listan TODAS
-- —así se ve si el mismo armado está cargado dos veces— y el TOTAL suma solo
-- las vigentes y no anuladas.
--
-- PROBADA contra db/esquema_completo.sql con el caso plantado: dos renglones
-- de 30, uno de un pedido recargado, TOTAL 30. El canario que cambia
-- `vigentes` por `anulado_el is null` lo lleva a 60, así que el 30 sale de
-- ese filtro y no de que hubiera un solo renglón.
--
-- CÓMO SE LEEN LAS DOS JUNTAS:
--     STOCK_AL_16 (consulta 1)  −  TOTAL (consulta 2)  =  el saldo al 17/09
-- Si da 12 y 30, el saldo es −18. Cualquier pantalla que diga otra cosa está
-- mirando otro número, y con estas dos filas a la vista se ve cuál.
