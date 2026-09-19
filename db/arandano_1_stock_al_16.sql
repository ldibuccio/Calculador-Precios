WITH tope AS (SELECT DATE '2026-09-16' f, 'America/Argentina/Buenos_Aires' tz),
arts AS (SELECT id, nombre FROM articulos WHERE lower(nombre) LIKE 'ar%nd%n%'),
ent AS (
  SELECT c.articulo_id a, SUM(c.cantidad_cajones_real) t
  FROM compras c, tope
  WHERE c.estado = 'recepcionado'
    AND COALESCE((c.procesada_el AT TIME ZONE tope.tz)::date, c.fecha_operacion) <= tope.f
  GROUP BY 1),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC),
sal AS (
  SELECT r.articulo_id a, SUM(COALESCE(r.cantidad_armada, r.cantidad)) t
  FROM pedidos_renglones r JOIN vig v ON v.id = r.pedido_id, tope
  WHERE r.armado_el IS NOT NULL AND r.anulado_el IS NULL AND r.articulo_id IS NOT NULL
    AND (r.armado_el AT TIME ZONE tope.tz)::date <= tope.f
  GROUP BY 1),
rei AS (
  SELECT articulo_id a, SUM(cantidad) t FROM movimientos_stock, tope
  WHERE anulado_el IS NULL AND tipo = 'reingreso_rechazo' AND fecha_operacion <= tope.f
    AND (destino_rechazo IS NULL OR destino_rechazo = 'stock')
  GROUP BY 1),
aju AS (
  SELECT articulo_id a, SUM(cantidad) t FROM movimientos_stock, tope
  WHERE anulado_el IS NULL AND tipo <> 'reingreso_rechazo' AND fecha_operacion <= tope.f
  GROUP BY 1),
rep AS (
  SELECT articulo_id a, SUM(bultos_primera) e, SUM(bultos_tomados) s
  FROM reprocesos, tope
  WHERE anulado_el IS NULL AND fecha_operacion <= tope.f
  GROUP BY 1)
SELECT 'arandano_1_stock_al_16' QUE_CONSULTA, x.id articulo_id, x.nombre,
  (SELECT f FROM tope) hasta_inclusive,
  COALESCE(e.t,0) p1_compras, COALESCE(s.t,0) p2_armados,
  COALESCE(r.t,0) p3_reingresos, COALESCE(j.t,0) p4_ajustes,
  COALESCE(p.e,0) p5_repro_primera, COALESCE(p.s,0) p6_repro_tomados,
  COALESCE(e.t,0)+COALESCE(r.t,0)+COALESCE(j.t,0)+COALESCE(p.e,0)
    -COALESCE(p.s,0)-COALESCE(s.t,0) STOCK_AL_16,
  (SELECT count(*) FROM arts) arts_que_matchean,
  (SELECT max(fecha_operacion) FROM compras WHERE articulo_id = x.id) ult_compra
FROM arts x
LEFT JOIN ent e ON e.a = x.id LEFT JOIN sal s ON s.a = x.id
LEFT JOIN rei r ON r.a = x.id LEFT JOIN aju j ON j.a = x.id
LEFT JOIN rep p ON p.a = x.id
ORDER BY x.nombre;

-- ---------------------------------------------------------------------------
-- QUÉ ES ESTO. El stock de Arándano AL CIERRE DEL 16/09, o sea entradas menos
-- salidas hasta ese día inclusive. Se corre SOLA (no la pegues con la otra:
-- el editor de Supabase muestra únicamente el resultado de la última).
--
-- LAS SEIS PATAS SON LAS DE `_SQL_SUMAS_STOCK` (app/db.py), copiadas y no
-- reescritas: p1 compras recepcionadas, p2 armados, p3 reingresos, p4
-- ajustes, p5/p6 el reproceso. STOCK = p1 + p3 + p4 + p5 − p6 − p2. Una
-- consulta con menos patas no es una simplificación: es otra cuenta, y ya me
-- costó un número falso hoy (corolario 85).
--
-- DOS RECORTES QUE NO SON DE ESTILO:
--   · Las COMPRAS se fechan por `procesada_el` —cuándo el depósito las
--     recepcionó—, no por `fecha_operacion`. Una comprada el 16 y recibida el
--     17 NO estaba en el piso el 16.
--   · `<= 2026-09-16` es "hasta el 16 inclusive": lo del 17 queda afuera.
--
-- PROBADA contra db/esquema_completo.sql en Postgres 16 con el caso plantado
-- (una compra de 12 recibida el 15, otra de 9 recibida el 17): devuelve 12.
-- Y los dos canarios mueven el número, así que el 12 no es un cero de
-- construcción: con `fecha_operacion` da 21, y con el tope al 17 da −9.
--
-- `arts_que_matchean` es el denominador: si dice 2, el LIKE agarró dos
-- artículos y hay que mirar las dos filas. `ult_compra` es el testigo de
-- actividad: sin él, un 0 de una base quieta se lee igual que un 0 real.
