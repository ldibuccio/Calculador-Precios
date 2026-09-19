WITH tz AS (SELECT 'America/Argentina/Buenos_Aires' z),
hoy AS (SELECT (now() AT TIME ZONE (SELECT z FROM tz))::date d),
vig AS (
  SELECT DISTINCT ON (cliente_id, fecha_operacion) id, cliente_id, fecha_operacion
  FROM pedidos WHERE anulado_el IS NULL
  ORDER BY cliente_id, fecha_operacion, creado_en DESC),
sin AS (
  SELECT r.id, v.id pedido_id, v.fecha_operacion,
         ((SELECT d FROM hoy) - v.fecha_operacion) antiguedad,
         r.cantidad bultos, p.armado_cerrado_el
  FROM pedidos_renglones r
  JOIN vig v ON v.id = r.pedido_id
  JOIN pedidos p ON p.id = v.id
  WHERE r.armado_el IS NULL AND r.anulado_el IS NULL
    AND r.articulo_id IS NOT NULL AND r.cantidad > 0
    AND v.fecha_operacion < (SELECT d FROM hoy))
SELECT 'sin_tildar_1_cuantos_hay' QUE_CONSULTA,
  (SELECT d FROM hoy) hoy,
  count(*) RENGLONES_SIN_TILDAR,
  COALESCE(sum(bultos), 0) BULTOS_SIN_TILDAR,
  count(DISTINCT pedido_id) PEDIDOS_CON_ALGUNO,
  count(*) FILTER (WHERE antiguedad = 1) de_AYER,
  count(*) FILTER (WHERE antiguedad BETWEEN 2 AND 7) de_2_a_7_dias,
  count(*) FILTER (WHERE antiguedad > 7) de_MAS_DE_7,
  count(DISTINCT pedido_id) FILTER (WHERE antiguedad = 1) pedidos_de_ayer,
  count(*) FILTER (WHERE armado_cerrado_el IS NOT NULL) EN_PEDIDO_YA_TERMINADO,
  COALESCE(max(antiguedad), 0) el_mas_viejo_dias,
  (SELECT count(*) FROM pedidos_renglones r2 JOIN vig v2 ON v2.id = r2.pedido_id
    WHERE r2.anulado_el IS NULL AND r2.articulo_id IS NOT NULL
      AND v2.fecha_operacion < (SELECT d FROM hoy)) renglones_de_dias_pasados_TOTALES,
  (SELECT max(fecha_operacion) FROM vig) ultimo_pedido,
  (SELECT count(*) FROM articulos) arts_en_la_base
FROM sin;

-- ---------------------------------------------------------------------------
-- CUÁNTOS RENGLONES QUEDARON SIN TILDAR de días pasados. Se corre SOLA.
-- ES LA MEDICIÓN QUE DECIDE SI LA ALERTA SE CONSTRUYE, y va antes por lo
-- mismo que con el pesaje: un aviso que dispara sobre decenas de renglones
-- viejos que nadie va a tildar no se mira a la semana.
--
-- LO QUE CUENTA: renglón vivo, de un pedido VIGENTE de un día ANTERIOR a
-- hoy, con artículo identificado, cantidad > 0 y sin `armado_el`. El de HOY
-- no cuenta: se está armando, y avisar de eso sería avisar del trabajo en
-- curso.
--
-- LAS COLUMNAS QUE DECIDEN, y cada una manda a un diseño distinto:
--   · de_AYER — el caso de VL: salió y falta anotarlo. Es el que la alerta
--     puede hacer que alguien tilde HOY, y el único que se apaga solo.
--   · de_MAS_DE_7 — el que nadie va a tildar nunca. Si esto es grande, la
--     alerta nace con una lista que no se vacía, y entonces la ventana tiene
--     que cortar por antigüedad o el aviso se ignora en dos semanas.
--   · EN_PEDIDO_YA_TERMINADO — el más fuerte de los tres. Alguien cerró el
--     pedido con renglones sin tildar, así que no está esperando: se dio por
--     terminado y quedó incompleto. Si la alerta cuenta UN conjunto, es éste.
--   · RENGLONES_SIN_TILDAR sobre `renglones_de_dias_pasados_TOTALES` — si el
--     primero es del orden del segundo, no es un olvido: es cómo se trabaja,
--     y un aviso no lo va a cambiar (más hallazgos que población).
--   · PEDIDOS_CON_ALGUNO — decide la UNIDAD. Muchos renglones en pocos
--     pedidos se atienden por pedido; repartidos, por renglón.
--
-- Y `arts_en_la_base` + `ultimo_pedido` son la identidad (corolario 17): dos
-- bases no pueden imprimir la misma fila.
--
-- PROBADA contra db/esquema_completo.sql en Postgres 16 con los cuatro casos
-- plantados —uno de ayer en un pedido YA TERMINADO, uno de hace 20 días, uno
-- de hoy que NO tiene que contar, y uno tildado— y con el control de todo
-- tildado: devuelve 2/17/2 con `de_MAS_DE_7 1` y `EN_PEDIDO_YA_TERMINADO 1`,
-- y 0/0/0 con el control, sin que el denominador se mueva de 3.
